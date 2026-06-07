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
import yaml
import threading
import queue
import time
from typing import Dict, List, Any, Generator, Set
from markov_namegen import MarkovNameGenerator, WORD_LISTS_DIR
from markov.constraint_sampler import GenerationConstraints
from ai.llm_scorer import LLMScorer
from ai.llm import DEFAULT_MODEL
from ai.embeddings import prefilter_names, EmbeddingPrefilter, DEFAULT_EMBEDDING_MODEL
from markov.dataset_stats import compute_dataset_stats

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("api_server")

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

# Global variables to store state.
# state_lock guards the cached generator + config mutations across concurrent requests.
state_lock = threading.Lock()
current_config = {}
saved_ratings = {}
word_list_ratings = {}
generator = None
cached_generator = None
cached_word_list_hash = None
cached_model_params_hash = None

def load_config() -> Dict[str, Any]:
    """Load configuration from YAML file"""
    try:
        with open("config.yaml", 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {}

def save_config(config: Dict[str, Any]):
    """Save configuration to YAML file"""
    try:
        with open("config.yaml", 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
    except Exception as e:
        print(f"Failed to save config: {str(e)}")

def load_saved_ratings():
    """Load saved ratings from file"""
    global saved_ratings
    try:
        if os.path.exists("saved_ratings.json"):
            with open("saved_ratings.json", 'r') as f:
                saved_ratings = json.load(f)
    except Exception as e:
        print(f"Error loading saved ratings: {e}")
        saved_ratings = {}

def save_ratings_to_file():
    """Save ratings to file"""
    try:
        with open("saved_ratings.json", 'w') as f:
            json.dump(saved_ratings, f, indent=2)
    except Exception as e:
        print(f"Error saving ratings: {e}")

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

@app.route('/api/word-lists', methods=['GET'])
def get_word_lists_api():
    """Get available word lists with ratings and word counts"""
    word_lists = get_word_lists()
    result = []
    for word_list in word_lists:
        display_name = word_list.replace('_', ' ').replace('.txt', '').title()
        
        # Efficiently count words without loading full content
        word_count = 0
        try:
            file_path = os.path.join(WORD_LISTS_DIR, word_list)
            with open(file_path, 'r') as f:
                word_count = sum(1 for line in f if line.strip())
        except Exception as e:
            print(f"Error counting words in {word_list}: {e}")
            word_count = 0

        try:
            health = get_dataset_stats(word_list)
        except Exception as e:
            print(f"Error computing dataset stats for {word_list}: {e}")
            health = None

        result.append({
            'filename': word_list,
            'display_name': display_name,
            'rating': word_list_ratings.get(word_list, 0),
            'selected': word_list in current_config.get('training_data', {}).get('sources', []),
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
        return jsonify({
            'filename': filename,
            'words': words,
            'total_count': len(words)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/word-lists/<filename>/rate', methods=['POST'])
def rate_word_list(filename):
    """Rate a word list"""
    try:
        data = request.json
        rating = data.get('rating', 0)
        word_list_ratings[filename] = rating
        current_config['word_list_ratings'] = word_list_ratings
        save_config(current_config)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    return jsonify(current_config)

@app.route('/api/config', methods=['POST'])
def update_config():
    """Update configuration"""
    global current_config
    try:
        current_config = request.json
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
            yaml.dump(config, f, default_flow_style=False)

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/config/list', methods=['GET'])
def list_config_files():
    """List available config files"""
    try:
        config_files = []
        # Look for .yaml files in the current directory
        for file in os.listdir('.'):
            if file.endswith('.yaml'):
                config_files.append(file)
        return jsonify({'configs': sorted(config_files)})
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
            config_data = yaml.safe_load(f)
            
        return jsonify(config_data or {})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ratings', methods=['GET'])
def get_ratings():
    """Get all saved ratings"""
    return jsonify(saved_ratings)

@app.route('/api/ratings/<name>', methods=['POST'])
def rate_name(name):
    """Rate a name"""
    try:
        data = request.json
        rating = data.get('rating', 0)
        saved_ratings[name] = rating
        save_ratings_to_file()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ratings/<name>', methods=['DELETE'])
def delete_rating(name):
    """Delete a rating"""
    try:
        if name in saved_ratings:
            del saved_ratings[name]
            save_ratings_to_file()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ratings', methods=['DELETE'])
def clear_all_ratings():
    """Clear all ratings"""
    try:
        saved_ratings.clear()
        save_ratings_to_file()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def _run_ai_scoring(data: Dict[str, Any],
                    embed_progress=None, score_progress=None) -> Dict[str, Any]:
    """Shared two-stage AI scoring pipeline (embedding prefilter -> LLM).

    Raises ValueError for user-facing input problems. ``embed_progress`` /
    ``score_progress`` are optional (done, total) hooks for the streaming
    endpoint (embedded texts and completed LLM chunks respectively).
    """
    names = data.get('names', [])
    description = data.get('description', '')
    instructions = data.get('instructions', '')
    model = data.get('model', DEFAULT_MODEL)
    max_chunk_size = data.get('max_chunk_size', 10)
    # Embedding pre-filter: comma-separated vibe keywords act as vector
    # anchors; only the prefilter_keep most-similar names go to the LLM.
    keywords = [k.strip() for k in (data.get('keywords') or '').split(',') if k.strip()]
    prefilter_keep = int(data.get('prefilter_keep') or 20)
    embedding_model = data.get('embedding_model') or DEFAULT_EMBEDDING_MODEL
    min_similarity = float(data.get('min_similarity') or 0.0)

    if not names:
        raise ValueError('No names provided')
    if not description:
        raise ValueError('Description is required')
    if not instructions:
        raise ValueError('Instructions are required')

    # Stage 1 (optional, cheap): embedding similarity pre-filter
    similarities = {}
    prefilter_info = None
    if keywords:
        result = prefilter_names(names, keywords, keep_top=prefilter_keep,
                                 model=embedding_model, min_similarity=min_similarity,
                                 progress_callback=embed_progress)
        # Keep similarities for ALL names (not just the kept ones) so the
        # GUI's Vibe Sim column survives the cutoff — dropped names are
        # simply never LLM-scored.
        similarities = {name: sim for name, sim in result['ranked']}
        names = [name for name, _ in result['kept']]
        prefilter_info = {
            'keywords': keywords,
            'total': result['total'],
            'kept': len(names),
            'dropped': result['dropped'],
            'min_similarity': min_similarity,
            'embedding_model': embedding_model,
            'cost': result['cost'],
        }
        logger.info("Embedding prefilter: kept %d/%d names (keywords=%s, min_sim=%.2f, cost=$%.6f)",
                    len(names), result['total'], keywords, min_similarity, result['cost'])
        if not names:
            raise ValueError(
                f'No names passed the vibe similarity cutoff (>= {min_similarity:.2f}). '
                'Lower the cutoff in the AI tab or adjust the keywords.')

    # Get scored examples from saved ratings
    scored_examples = []
    for name, rating in saved_ratings.items():
        if rating > 0:
            scored_examples.append((name, rating))
    scored_examples.sort(key=lambda x: x[1], reverse=True)
    scored_examples = scored_examples[:50]  # Limit to top 50

    # Stage 2: LLM scoring in parallel chunks
    llm_scorer = LLMScorer(model=model, max_chunk_size=max_chunk_size)
    scored_names, total_cost = llm_scorer.score_names(
        names=names,
        description=description,
        scored_examples=scored_examples,
        instructions=instructions,
        progress_callback=score_progress
    )

    # Sort by score (highest first), tie-broken by embedding similarity
    scored_names.sort(key=lambda x: (x[1], similarities.get(x[0], 0.0)), reverse=True)

    embedding_cost = prefilter_info['cost'] if prefilter_info else 0.0
    # Names cut by the prefilter still get returned with their similarity
    # (just no LLM score), appended after the scored ones in sim order.
    llm_scored = {name for name, _ in scored_names}
    unscored = sorted(
        ((name, sim) for name, sim in similarities.items() if name not in llm_scored),
        key=lambda x: x[1], reverse=True
    )
    return {
        'scored_names': [
            {'name': name, 'score': score,
             **({'similarity': similarities[name]} if name in similarities else {})}
            for name, score in scored_names
        ] + [
            {'name': name, 'similarity': sim} for name, sim in unscored
        ],
        'prefilter': prefilter_info,
        'total_cost': total_cost + embedding_cost
    }

@app.route('/api/ai/score', methods=['POST'])
def ai_score_names():
    """Score names using AI"""
    try:
        return jsonify(_run_ai_scoring(request.json))
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/score-stream', methods=['POST'])
def ai_score_names_stream():
    """Like /api/ai/score, but an SSE stream with two-phase progress.

    Events: {type: embed_progress, done, total} while the prefilter embeds,
    {type: score_progress, done, total} per completed LLM chunk, then
    {type: complete, ...same payload as /api/ai/score} (or
    {type: error, message}).
    """
    data = request.json
    # The pipeline runs in a worker thread (it owns its own asyncio loops);
    # progress events flow back through a queue that the SSE generator drains.
    events: queue.Queue = queue.Queue()

    def worker():
        try:
            result = _run_ai_scoring(
                data,
                embed_progress=lambda done, total: events.put(
                    {'type': 'embed_progress', 'done': done, 'total': total}),
                score_progress=lambda done, total: events.put(
                    {'type': 'score_progress', 'done': done, 'total': total}))
            events.put({'type': 'complete', **result})
        except ValueError as e:
            events.put({'type': 'error', 'message': str(e)})
        except Exception as e:
            logger.exception("AI scoring stream failed")
            events.put({'type': 'error', 'message': str(e)})

    threading.Thread(target=worker, daemon=True).start()

    def stream():
        while True:
            event = events.get()
            yield f"data: {json.dumps(event)}\n\n"
            if event['type'] in ('complete', 'error'):
                return

    return Response(stream(), mimetype='text/event-stream', headers=SSE_HEADERS)

@app.route('/api/ai/embed-rank', methods=['POST'])
def ai_embed_rank():
    """Rank names by embedding similarity to vibe keywords (no LLM call)."""
    try:
        data = request.json
        names = data.get('names', [])
        keywords = [k.strip() for k in (data.get('keywords') or '').split(',') if k.strip()]
        embedding_model = data.get('embedding_model') or DEFAULT_EMBEDDING_MODEL

        if not names:
            return jsonify({'error': 'No names provided'}), 400
        if not keywords:
            return jsonify({'error': 'No keywords provided'}), 400

        prefilter = EmbeddingPrefilter(model=embedding_model)
        ranked, cost = prefilter.rank_names(names, keywords)
        logger.info("Embedding rank: %d names against keywords=%s (cost=$%.6f)",
                    len(names), keywords, cost)
        return jsonify({
            'ranked': [{'name': name, 'similarity': sim} for name, sim in ranked],
            'total': len(names),
            'embedding_model': embedding_model,
            'cost': cost,
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/embed-rank-stream', methods=['POST'])
def ai_embed_rank_stream():
    """Like /api/ai/embed-rank, but an SSE stream with embedding progress.

    Events: {type: progress, done, total} per completed batch, then
    {type: complete, ranked, cost} (or {type: error, message}).
    """
    data = request.json
    names = data.get('names', [])
    keywords = [k.strip() for k in (data.get('keywords') or '').split(',') if k.strip()]
    embedding_model = data.get('embedding_model') or DEFAULT_EMBEDDING_MODEL

    if not names:
        return _sse_error_response('No names provided')
    if not keywords:
        return _sse_error_response('No keywords provided')

    # The embedding runs in a worker thread (it owns its own asyncio loop);
    # progress events flow back through a queue that the SSE generator drains.
    events: queue.Queue = queue.Queue()

    def worker():
        try:
            prefilter = EmbeddingPrefilter(model=embedding_model)
            ranked, cost = prefilter.rank_names(
                names, keywords,
                progress_callback=lambda done, total: events.put(
                    {'type': 'progress', 'done': done, 'total': total}))
            logger.info("Embedding rank (stream): %d names against keywords=%s (cost=$%.6f)",
                        len(names), keywords, cost)
            events.put({
                'type': 'complete',
                'ranked': [{'name': name, 'similarity': sim} for name, sim in ranked],
                'total': len(names),
                'embedding_model': embedding_model,
                'cost': cost,
            })
        except Exception as e:
            logger.exception("Embedding rank stream failed")
            events.put({'type': 'error', 'message': str(e)})

    threading.Thread(target=worker, daemon=True).start()

    def stream():
        while True:
            event = events.get()
            yield f"data: {json.dumps(event)}\n\n"
            if event['type'] in ('complete', 'error'):
                return

    return Response(stream(), mimetype='text/event-stream', headers=SSE_HEADERS)

@app.route('/api/ai/models', methods=['GET'])
def get_ai_models():
    """Get available AI models (from config.yaml `llm.available_models`, falling back to defaults)"""
    try:
        models = current_config.get('llm', {}).get('available_models') or LLMScorer.get_available_models()
        # Always include the currently-configured model so a hand-edited
        # config.yaml model still shows up in the GUI dropdown.
        configured = current_config.get('llm', {}).get('model')
        if configured and configured not in models:
            models = [configured] + models
        return jsonify({'models': models})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

SSE_HEADERS = {'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}

def _sse_error_response(message: str) -> Response:
    def error_stream():
        yield f"data: {json.dumps({'type': 'error', 'message': message})}\n\n"
    return Response(error_stream(), mimetype='text/event-stream', headers=SSE_HEADERS)

@app.route('/api/generate-stream', methods=['POST'])
def generate_names_stream():
    """Generate names with streaming progress updates"""
    global generator, cached_generator, cached_word_list_hash, cached_model_params_hash

    try:
        config = request.json
        current_config.update(config)

        # Check if any word lists are selected
        selected_sources = config.get('training_data', {}).get('sources', [])
        if not selected_sources:
            return _sse_error_response('Please select at least one word list')

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

        # Create generator, reusing the cached one when the training data and
        # model parameters haven't changed
        current_word_list_hash = hashlib.md5(str(sorted(selected_sources)).encode()).hexdigest()
        model_params = config.get('model', {})
        current_model_params_hash = hashlib.md5(str(model_params).encode()).hexdigest()

        with state_lock:
            if (cached_generator is not None and
                cached_word_list_hash == current_word_list_hash and
                cached_model_params_hash == current_model_params_hash):
                logger.info("Using cached generator")
                generator = cached_generator
            else:
                logger.info("Building new generator: sources=%s, order=%s, temp=%s, backoff=%s",
                            selected_sources, model_params.get('order', 3),
                            model_params.get('temperature', 1.0), model_params.get('backoff', True))
                try:
                    generator = MarkovNameGenerator()
                    generator.config = current_config
                    generator.training_words = generator._load_training_data()
                    logger.info("Loaded %d training words", len(generator.training_words))

                    from markov.name_generator import NameGenerator
                    generator.generator = NameGenerator(
                        data=generator.training_words,
                        order=model_params.get('order', 3),
                        temperature=model_params.get('temperature', 1.0),
                        backoff=model_params.get('backoff', True)
                    )

                    cached_generator = generator
                    cached_word_list_hash = current_word_list_hash
                    cached_model_params_hash = current_model_params_hash
                except Exception as e:
                    logger.exception("Generator creation failed")
                    return _sse_error_response(f"Generator creation failed: {str(e)}")

        # Fill in filtering/output defaults (matching config.yaml semantics)
        config.setdefault('filtering', {
            'remove_duplicates': True,
            'exclude_training_words': True,
            'min_edit_distance': 0
        })
        config.setdefault('output', {
            'sort_by': 'random',
            'sort_ascending': True
        })

        generator.config.update(config)

        def generate_stream():
            try:
                name_count = 0
                for name in generate_names_with_progress(generator, config):
                    name_count += 1
                    yield f"data: {json.dumps({'type': 'progress', 'name': name})}\n\n"

                logger.info("Generation complete, %d names", name_count)
                yield f"data: {json.dumps({'type': 'complete'})}\n\n"
            except Exception as e:
                logger.exception("Error during streaming generation")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        return Response(generate_stream(), mimetype='text/event-stream', headers=SSE_HEADERS)

    except Exception as e:
        logger.exception("Error in generate-stream endpoint")
        return _sse_error_response(str(e))

def generate_names_with_progress(generator: MarkovNameGenerator, config: Dict[str, Any]) -> Generator[str, None, None]:
    """Generate names one by one, yielding each valid name as it's found"""
    gen_config = config.get('generation', {})

    target_count = gen_config.get('n_words', 20)
    min_length = gen_config.get('min_length', 4)
    max_length = gen_config.get('max_length', 12)
    starts_with = gen_config.get('starts_with', '')
    ends_with = gen_config.get('ends_with', '')
    includes = gen_config.get('includes', '')
    excludes = gen_config.get('excludes', '')
    max_time_per_name = gen_config.get('max_time_per_name', 2.0)
    regex_pattern = gen_config.get('regex_pattern') if gen_config.get('regex_pattern') else None
    
    # Multi-component parameters
    components = gen_config.get('components', [])
    component_order = gen_config.get('component_order')
    component_separation = tuple(gen_config.get('component_separation', [0, 3]))

    logger.info("Generating %d names (length %d-%d, starts='%s', ends='%s', includes='%s', excludes='%s', components=%s)",
                target_count, min_length, max_length, starts_with, ends_with, includes, excludes, components)

    names: Set[str] = set()
    training_set = set(generator.training_words or [])
    start_time = time.time()
    last_success_time = start_time
    max_total_time = max_time_per_name * target_count

    while len(names) < target_count:
        try:
            # Use component-based generation if components are specified
            if components:
                name = generator.generator.generate_name_with_components(
                    components=components,
                    min_length=min_length,
                    max_length=max_length,
                    starts_with=starts_with,
                    ends_with=ends_with,
                    includes=includes,
                    excludes=excludes,
                    component_order=component_order,
                    component_separation=component_separation,
                    regex_pattern=regex_pattern
                )
            else:
                # Use standard generation
                name = generator.generator.generate_name(
                    min_length=min_length,
                    max_length=max_length,
                    starts_with=starts_with,
                    ends_with=ends_with,
                    includes=includes,
                    excludes=excludes,
                    regex_pattern=regex_pattern
                )
        except Exception:
            logger.exception("Error during name generation")
            break

        if name is not None:
            # Apply filtering to this single name
            if should_keep_name(name, names, training_set, config):
                names.add(name)
                yield name
                last_success_time = time.time()  # Reset success timer

        # Safety check to prevent infinite loops:
        # stop if we haven't found a name in too long OR total time exceeded
        current_time = time.time()
        time_since_last_success = current_time - last_success_time
        if time_since_last_success > max_time_per_name * 2 or (current_time - start_time) > max_total_time:
            logger.info("Generation timeout: %.1fs since last success, %.1fs total, %d/%d names found",
                        time_since_last_success, current_time - start_time, len(names), target_count)
            break

def should_keep_name(name: str, existing_names: Set[str], training_set: Set[str], config: Dict[str, Any]) -> bool:
    """Check if a name should be kept based on filtering rules"""
    filter_config = config.get('filtering', {})

    # Remove duplicates
    if filter_config.get('remove_duplicates', True):
        if name in existing_names:
            return False

    # Remove names identical to training data
    if filter_config.get('exclude_training_words', True):
        if name in training_set:
            return False

    # Remove names too similar to training data
    min_distance = filter_config.get('min_edit_distance', 0)
    if min_distance > 0:
        from markov_namegen import too_close_to_training
        if too_close_to_training(name, training_set, min_distance):
            return False

    return True

if __name__ == '__main__':
    logger.info("Starting Markov Name Generator API Server on http://localhost:5001")
    app.run(debug=True, host='0.0.0.0', port=5001)