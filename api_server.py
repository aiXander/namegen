#!/usr/bin/env python3

"""
API Server for Markov Name Generator React GUI
Provides REST API endpoints for the React frontend to communicate with the Python backend
"""

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import hashlib
import logging
import os
import json
import urllib.request
import yaml
import threading
import queue
import time
from typing import Any, Callable, Dict, Iterator, List, Optional
from markov_namegen import MarkovNameGenerator, WORD_LISTS_DIR, nearest_training_word
from markov.constraint_sampler import GenerationConstraints
from ai.judge import NameJudge, build_brief, select_examples, DEFAULT_JUDGES, DEFAULT_FINAL_MODEL
from ai.embeddings import prefilter_names, EmbeddingPrefilter, DEFAULT_EMBEDDING_MODEL
from markov.dataset_stats import compute_dataset_stats

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("api_server")

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

# Global state. state_lock guards the cached generator + rating mutations
# across concurrent requests.
state_lock = threading.Lock()
current_config: Dict[str, Any] = {}
saved_ratings: Dict[str, int] = {}
word_list_ratings: Dict[str, int] = {}
cached_generator: Optional[MarkovNameGenerator] = None
cached_generator_key: Optional[str] = None

SSE_HEADERS = {'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}


def load_config() -> Dict[str, Any]:
    """Load configuration from YAML file"""
    try:
        with open("config.yaml", 'r') as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


def save_config(config: Dict[str, Any]):
    """Save configuration to YAML file"""
    try:
        with open("config.yaml", 'w') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
    except Exception as e:
        logger.error("Failed to save config: %s", e)


def load_saved_ratings():
    """Load saved ratings from file"""
    global saved_ratings
    try:
        if os.path.exists("saved_ratings.json"):
            with open("saved_ratings.json", 'r') as f:
                saved_ratings = json.load(f)
    except Exception as e:
        logger.error("Error loading saved ratings: %s", e)
        saved_ratings = {}


def save_ratings_to_file():
    """Save ratings to file"""
    try:
        with open("saved_ratings.json", 'w') as f:
            json.dump(saved_ratings, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error("Error saving ratings: %s", e)


def get_word_lists() -> List[str]:
    """Get list of available word lists"""
    word_lists = []
    if os.path.exists(WORD_LISTS_DIR):
        word_lists = [f for f in os.listdir(WORD_LISTS_DIR) if f.endswith('.txt')]
    return sorted(word_lists)


DATASET_STATS_CACHE_PATH = os.path.join(".cache", "dataset_stats.json")
_dataset_stats_cache = None  # filename -> {"mtime": float, "stats": {...}}
_dataset_stats_lock = threading.Lock()


def get_dataset_stats(filename: str) -> Dict[str, Any]:
    """Markov-health stats for a word list, cached on disk keyed by file mtime."""
    global _dataset_stats_cache
    file_path = os.path.join(WORD_LISTS_DIR, filename)
    mtime = os.path.getmtime(file_path)
    with _dataset_stats_lock:
        if _dataset_stats_cache is None:
            try:
                with open(DATASET_STATS_CACHE_PATH, 'r') as f:
                    _dataset_stats_cache = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                _dataset_stats_cache = {}
        entry = _dataset_stats_cache.get(filename)
        if entry and entry.get("mtime") == mtime:
            return entry["stats"]

        with open(file_path, 'r', encoding='utf-8') as f:
            words = [line.strip().lower() for line in f if line.strip()]
        stats = compute_dataset_stats(words)
        _dataset_stats_cache[filename] = {"mtime": mtime, "stats": stats}
        os.makedirs(".cache", exist_ok=True)
        with open(DATASET_STATS_CACHE_PATH, 'w') as f:
            json.dump(_dataset_stats_cache, f)
        return stats


# Initialize on startup
current_config = load_config()
load_saved_ratings()
word_list_ratings = current_config.get('word_list_ratings', {})


def _sse(event: Dict[str, Any]) -> str:
    return f"data: {json.dumps(event)}\n\n"


def _sse_error_response(message: str) -> Response:
    return Response(iter([_sse({'type': 'error', 'message': message})]),
                    mimetype='text/event-stream', headers=SSE_HEADERS)


def _stream_worker(work: Callable[[Callable[[Dict[str, Any]], None]], Dict[str, Any]]) -> Response:
    """Run `work(emit)` in a worker thread (the AI stages own their own asyncio
    loops) and stream every emitted event, then the returned payload as
    {type: complete, ...} — or {type: error, message} if it raises."""
    events: queue.Queue = queue.Queue()

    def worker():
        try:
            events.put({'type': 'complete', **work(events.put)})
        except ValueError as e:
            events.put({'type': 'error', 'message': str(e)})
        except Exception as e:
            logger.exception("Streaming task failed")
            events.put({'type': 'error', 'message': str(e)})

    threading.Thread(target=worker, daemon=True).start()

    def stream() -> Iterator[str]:
        while True:
            event = events.get()
            yield _sse(event)
            if event['type'] in ('complete', 'error'):
                return

    return Response(stream(), mimetype='text/event-stream', headers=SSE_HEADERS)


# ----------------------------------------------------------------------
# Word lists
# ----------------------------------------------------------------------

@app.route('/api/word-lists', methods=['GET'])
def get_word_lists_api():
    """Get available word lists with ratings, word counts and Markov health"""
    result = []
    sources = current_config.get('training_data', {}).get('sources', [])
    for word_list in get_word_lists():
        try:
            with open(os.path.join(WORD_LISTS_DIR, word_list), 'r') as f:
                word_count = sum(1 for line in f if line.strip())
        except Exception as e:
            logger.error("Error counting words in %s: %s", word_list, e)
            word_count = 0

        try:
            health = get_dataset_stats(word_list)
        except Exception as e:
            logger.error("Error computing dataset stats for %s: %s", word_list, e)
            health = None

        result.append({
            'filename': word_list,
            'display_name': word_list.replace('_', ' ').replace('.txt', '').title(),
            'rating': word_list_ratings.get(word_list, 0),
            'selected': word_list in sources,
            'word_count': word_count,
            'health': health
        })
    return jsonify(result)


@app.route('/api/word-lists/<filename>', methods=['GET'])
def get_word_list_content(filename):
    """Get content of a specific word list"""
    try:
        file_path = os.path.join(WORD_LISTS_DIR, os.path.basename(filename))
        with open(file_path, 'r') as f:
            words = [line.strip() for line in f if line.strip()]
        return jsonify({'filename': filename, 'words': words, 'total_count': len(words)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/word-lists/<filename>/rate', methods=['POST'])
def rate_word_list(filename):
    """Rate a word list"""
    try:
        word_list_ratings[filename] = int(request.json.get('rating', 0))
        current_config['word_list_ratings'] = word_list_ratings
        save_config(current_config)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------

@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    return jsonify(current_config)


@app.route('/api/config', methods=['POST'])
def update_config():
    """Replace the configuration (the GUI always sends the whole thing)"""
    global current_config
    try:
        config = request.json or {}
        # Ratings are owned by their own endpoints; never let a stale GUI copy
        # of the config roll them back.
        config['word_list_ratings'] = word_list_ratings
        current_config = config
        save_config(current_config)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _safe_config_filename(filename: str) -> str:
    """Restrict config filenames to .yaml files in the current directory
    (prevents path traversal like '../../etc/passwd')."""
    filename = os.path.basename(filename or '')
    if not filename:
        raise ValueError('Invalid filename')
    if not filename.endswith('.yaml'):
        filename += '.yaml'
    return filename


@app.route('/api/config/save', methods=['POST'])
def save_config_as():
    """Save configuration to a specific file"""
    try:
        data = request.json
        filename = data.get('filename')
        config = data.get('config')
        if not filename or not config:
            return jsonify({'error': 'Filename and config are required'}), 400
        with open(_safe_config_filename(filename), 'w') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/config/list', methods=['GET'])
def list_config_files():
    """List available config files"""
    try:
        return jsonify({'configs': sorted(f for f in os.listdir('.') if f.endswith('.yaml'))})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/config/load/<filename>', methods=['GET'])
def load_config_from_file(filename):
    """Load configuration from a specific file"""
    try:
        filename = _safe_config_filename(filename)
        if not os.path.exists(filename):
            return jsonify({'error': f'Config file {filename} not found'}), 404
        with open(filename, 'r') as f:
            return jsonify(yaml.safe_load(f) or {})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ----------------------------------------------------------------------
# Name ratings (the shortlist; also the judges' taste examples)
# ----------------------------------------------------------------------

@app.route('/api/ratings', methods=['GET'])
def get_ratings():
    """Get all saved ratings"""
    return jsonify(saved_ratings)


@app.route('/api/ratings', methods=['POST'])
def rate_name():
    """Rate a name: {name, rating}. Rating 0 removes it from the shortlist.
    (Names travel in the body, not the URL — they may contain spaces.)"""
    data = request.json or {}
    name = str(data.get('name', '')).strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    rating = int(data.get('rating', 0))
    with state_lock:
        if rating > 0:
            saved_ratings[name] = rating
        else:
            saved_ratings.pop(name, None)
        save_ratings_to_file()
    return jsonify({'success': True})


@app.route('/api/ratings/rename', methods=['POST'])
def rename_rating():
    """Rename a saved name, keeping its rating: {old, new}"""
    data = request.json or {}
    old, new = str(data.get('old', '')).strip(), str(data.get('new', '')).strip()
    if not new or old not in saved_ratings:
        return jsonify({'error': 'Unknown name or empty new name'}), 400
    with state_lock:
        saved_ratings[new] = saved_ratings.pop(old)
        save_ratings_to_file()
    return jsonify({'success': True})


@app.route('/api/ratings', methods=['DELETE'])
def clear_all_ratings():
    """Clear all ratings"""
    with state_lock:
        saved_ratings.clear()
        save_ratings_to_file()
    return jsonify({'success': True})


# ----------------------------------------------------------------------
# AI: embedding vibe ranking, judge panel, final round
# ----------------------------------------------------------------------

def _keywords(data: Dict[str, Any]) -> List[str]:
    return [k.strip() for k in (data.get('keywords') or '').split(',') if k.strip()]


def _brief(data: Dict[str, Any], names: List[str]) -> str:
    """Judge context: the user's brief plus their star ratings as taste
    examples (excluding the names being judged)."""
    description = (data.get('description') or '').strip()
    if not description:
        raise ValueError('Write a brief first (Judge tab): what are these names for?')
    return build_brief(description, _keywords(data), data.get('guidance') or '',
                       select_examples(saved_ratings, exclude=names))


@app.route('/api/ai/judge-stream', methods=['POST'])
def ai_judge_stream():
    """Two-stage AI scoring as an SSE stream.

    1. Optional embedding prefilter: with vibe keywords set, every name is
       ranked by similarity and only the top `prefilter_keep` (and >=
       `min_similarity`) reach the judges.
    2. Judge panel: every model in `judges` scores every remaining name.

    Events: {type: embed_progress|judge_progress, done, total}, then
    {type: complete, verdicts, similarities, prefilter, cost}.
    """
    data = request.json or {}

    def work(emit):
        names = list(dict.fromkeys(data.get('names') or []))
        if not names:
            raise ValueError('No names to judge — generate some first')
        brief = _brief(data, names)
        keywords = _keywords(data)
        judges = data.get('judges') or DEFAULT_JUDGES
        cost = {'embedding': 0.0, 'judging': 0.0}

        similarities: Dict[str, float] = {}
        prefilter = None
        if keywords:
            min_similarity = float(data.get('min_similarity') or 0.0)
            result = prefilter_names(
                names, keywords, keep_top=int(data.get('prefilter_keep') or 200),
                model=data.get('embedding_model') or DEFAULT_EMBEDDING_MODEL,
                min_similarity=min_similarity,
                progress_callback=lambda done, total: emit(
                    {'type': 'embed_progress', 'done': done, 'total': total}))
            # Similarities for ALL names, so the Vibe column survives the cut.
            similarities = dict(result['ranked'])
            names = [name for name, _ in result['kept']]
            cost['embedding'] = result['cost']
            prefilter = {'total': result['total'], 'kept': len(names), 'min_similarity': min_similarity}
            logger.info("Vibe prefilter kept %d/%d names (cost=$%.5f)", len(names), result['total'], result['cost'])
            if not names:
                raise ValueError(f'No names passed the vibe cutoff (>= {min_similarity:.2f}). '
                                 'Lower the cutoff in the Judge tab.')
        else:
            names = names[:int(data.get('prefilter_keep') or 200)]

        judge = NameJudge(models=judges, chunk_size=int(data.get('chunk_size') or 20))
        verdicts, cost['judging'] = judge.judge(
            names, brief,
            progress_callback=lambda done, total: emit({'type': 'judge_progress', 'done': done, 'total': total}))
        logger.info("Judged %d names with %s (cost=$%.5f)", len(names), judges, cost['judging'])
        return {
            'verdicts': verdicts,
            'similarities': similarities,
            'prefilter': prefilter,
            'judges': judges,
            'cost': {**cost, 'total': cost['embedding'] + cost['judging']},
        }

    return _stream_worker(work)


@app.route('/api/ai/final-round', methods=['POST'])
def ai_final_round():
    """Rank a shortlist head to head in one call to a stronger model."""
    data = request.json or {}
    try:
        names = list(dict.fromkeys(data.get('names') or []))
        if len(names) < 2:
            return jsonify({'error': 'The final round needs at least two judged names'}), 400
        model = data.get('model') or DEFAULT_FINAL_MODEL
        ranking, cost = NameJudge().final_round(names, _brief(data, names), model=model)
        logger.info("Final round: %d names with %s (cost=$%.5f)", len(names), model, cost)
        return jsonify({'ranking': ranking, 'model': model, 'cost': cost})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.exception("Final round failed")
        return jsonify({'error': str(e)}), 500


@app.route('/api/ai/embed-rank-stream', methods=['POST'])
def ai_embed_rank_stream():
    """Rank names by embedding similarity to the vibe keywords (no LLM).

    Events: {type: progress, done, total}, then {type: complete, ranked, cost}.
    """
    data = request.json or {}

    def work(emit):
        names = data.get('names') or []
        keywords = _keywords(data)
        if not names:
            raise ValueError('No names provided')
        if not keywords:
            raise ValueError('Add some vibe keywords in the Judge tab first')
        embedding_model = data.get('embedding_model') or DEFAULT_EMBEDDING_MODEL
        ranked, cost = EmbeddingPrefilter(model=embedding_model).rank_names(
            names, keywords,
            progress_callback=lambda done, total: emit({'type': 'progress', 'done': done, 'total': total}))
        logger.info("Embedding rank: %d names against %s (cost=$%.6f)", len(names), keywords, cost)
        return {'ranked': [{'name': name, 'similarity': sim} for name, sim in ranked], 'cost': cost}

    return _stream_worker(work)


_model_prices: Optional[Dict[str, Dict[str, float]]] = None


def _openrouter_prices() -> Dict[str, Dict[str, float]]:
    """USD per million tokens for every OpenRouter chat model (fetched once;
    empty if OpenRouter is unreachable — prices are just a GUI nicety)."""
    global _model_prices
    if _model_prices is None:
        try:
            with urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=5) as response:
                models = json.load(response)['data']
            _model_prices = {
                m['id']: {'prompt': round(float(m['pricing']['prompt']) * 1e6, 4),
                          'completion': round(float(m['pricing']['completion']) * 1e6, 4)}
                for m in models if m.get('pricing')
            }
        except Exception as e:
            logger.warning("Could not fetch OpenRouter prices: %s", e)
            return {}
    return _model_prices


@app.route('/api/ai/models', methods=['GET'])
def get_ai_models():
    """Selectable models (config `llm.available_models`) with prices and defaults"""
    llm = current_config.get('llm', {})
    ids = list(dict.fromkeys([*(llm.get('judges') or DEFAULT_JUDGES),
                              llm.get('final_model') or DEFAULT_FINAL_MODEL,
                              *(llm.get('available_models') or [])]))
    prices = _openrouter_prices()
    return jsonify({
        'models': [{'id': model, **({'price': prices[model]} if model in prices else {})} for model in ids],
        'default_judges': DEFAULT_JUDGES,
        'default_final_model': DEFAULT_FINAL_MODEL,
    })


# ----------------------------------------------------------------------
# Generation
# ----------------------------------------------------------------------

def _generator_key(config: Dict[str, Any]) -> str:
    """Everything that changes the trained model."""
    training = config.get('training_data', {})
    weighting = training.get('weighting', 'natural')
    key = {
        'sources': sorted(training.get('sources', [])),
        'model': config.get('model', {}),
        'weighting': weighting,
        'ratings': {s: word_list_ratings.get(s) for s in training.get('sources', [])} if weighting == 'rating' else None,
    }
    return hashlib.md5(json.dumps(key, sort_keys=True).encode()).hexdigest()


def _get_generator(config: Dict[str, Any]) -> MarkovNameGenerator:
    """Train a generator for this config, reusing the cached one when the
    training data and model parameters haven't changed."""
    global cached_generator, cached_generator_key
    key = _generator_key(config)
    with state_lock:
        if cached_generator is not None and cached_generator_key == key:
            return cached_generator
        model = config.get('model', {})
        logger.info("Training generator: %d sources, order=%s, temp=%s, backoff=%s, weighting=%s",
                    len(config['training_data']['sources']), model.get('order', 3), model.get('temperature', 1.0),
                    model.get('backoff', True), config['training_data'].get('weighting', 'natural'))
        generator = MarkovNameGenerator(config={
            'training_data': config['training_data'],
            'model': {'order': model.get('order', 3), 'temperature': model.get('temperature', 1.0),
                      'backoff': model.get('backoff', True)},
            'word_list_ratings': word_list_ratings,
        })
        generator.unique_training_words = sorted(set(generator.training_words))
        cached_generator, cached_generator_key = generator, key
        return generator


@app.route('/api/generate-stream', methods=['POST'])
def generate_names_stream():
    """Generate names as an SSE stream.

    Events: {type: name, name, naturalness, nearest, distance} per accepted
    name, then {type: complete, stats} (or {type: error, message}).
    """
    config = request.json or {}
    if not config.get('training_data', {}).get('sources'):
        return _sse_error_response('Select at least one word list in the Sources tab')

    # Bail out immediately on self-contradictory constraints instead of
    # silently timing out with zero results
    gen_cfg = config.get('generation', {})
    constraints = GenerationConstraints(
        min_length=gen_cfg.get('min_length', 4),
        max_length=gen_cfg.get('max_length', 12),
        starts_with=gen_cfg.get('starts_with', ''),
        ends_with=gen_cfg.get('ends_with', ''),
        includes=gen_cfg.get('includes', ''),
        excludes=gen_cfg.get('excludes', '')
    )
    if not constraints.is_feasible():
        return _sse_error_response(
            'These constraints contradict each other (check min/max length, '
            'prefix + suffix length vs max length, and includes vs excludes)')

    try:
        generator = _get_generator(config)
    except Exception as e:
        logger.exception("Generator creation failed")
        return _sse_error_response(f"Generator creation failed: {e}")

    def stream() -> Iterator[str]:
        try:
            stats: Dict[str, Any] = {}
            for event in generate_names_with_progress(generator, config, stats):
                yield _sse({'type': 'name', **event})
            logger.info("Generation complete: %s", stats)
            yield _sse({'type': 'complete', 'stats': stats})
        except Exception as e:
            logger.exception("Error during streaming generation")
            yield _sse({'type': 'error', 'message': str(e)})

    return Response(stream(), mimetype='text/event-stream', headers=SSE_HEADERS)


def generate_names_with_progress(generator: MarkovNameGenerator, config: Dict[str, Any],
                                 stats: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
    """Yield accepted names one by one with their local metrics, filling
    `stats` with attempt / rejection counts (so the GUI can explain a short
    batch, e.g. "most candidates were too close to a training word")."""
    gen_config = config.get('generation', {})
    filters = config.get('filtering', {})

    target_count = int(gen_config.get('n_words', 20))
    max_time_per_name = float(gen_config.get('max_time_per_name', 2.0))
    regex_pattern = gen_config.get('regex_pattern') or None
    components = gen_config.get('components') or []
    kwargs = dict(
        min_length=gen_config.get('min_length', 4),
        max_length=gen_config.get('max_length', 12),
        starts_with=gen_config.get('starts_with', ''),
        ends_with=gen_config.get('ends_with', ''),
        includes=gen_config.get('includes', ''),
        excludes=gen_config.get('excludes', ''),
        regex_pattern=regex_pattern,
    )
    if components:
        kwargs.update(components=components,
                      component_order=gen_config.get('component_order'),
                      component_separation=tuple(gen_config.get('component_separation', [0, 3])))
    sample = (generator.generator.generate_name_with_components if components
              else generator.generator.generate_name)

    remove_duplicates = filters.get('remove_duplicates', True)
    exclude_training = filters.get('exclude_training_words', True)
    min_distance = int(filters.get('min_edit_distance', 0) or 0)

    logger.info("Generating %d names: %s", target_count, kwargs)
    names: set = set()
    training_set = set(generator.training_words)
    counts = {'attempts': 0, 'failed': 0, 'duplicate': 0, 'training_word': 0, 'too_similar': 0}
    start_time = time.time()
    last_success_time = start_time
    max_total_time = max_time_per_name * target_count

    while len(names) < target_count:
        counts['attempts'] += 1
        name = sample(**kwargs)
        if name is None:
            counts['failed'] += 1
        elif remove_duplicates and name in names:
            counts['duplicate'] += 1
        elif exclude_training and name in training_set:
            counts['training_word'] += 1
        else:
            nearest = nearest_training_word(name, generator.unique_training_words)
            if nearest and nearest[1] < min_distance:
                counts['too_similar'] += 1
            else:
                names.add(name)
                last_success_time = time.time()
                yield {
                    'name': name,
                    'naturalness': generator.generator.naturalness(name),
                    'nearest': nearest[0] if nearest else None,
                    'distance': nearest[1] if nearest else None,
                }

        # Stop when nothing new turns up for a while, or the total budget is spent
        now = time.time()
        if now - last_success_time > max_time_per_name * 2 or now - start_time > max_total_time:
            logger.info("Generation timeout after %.1fs: %d/%d names", now - start_time, len(names), target_count)
            break

    stats.update(counts, accepted=len(names), elapsed=round(time.time() - start_time, 2))


if __name__ == '__main__':
    logger.info("Starting Markov Name Generator API Server on http://localhost:5001")
    app.run(debug=True, host='0.0.0.0', port=5001, threaded=True)
