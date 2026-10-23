"""LLM judging of Markov-generated names: a parallel panel pass plus an
optional listwise final round.

Why a panel: a single model scoring independent chunks is noisy — the same
name can get a 3 or a 6 depending on which neighbours share its chunk and on
sampling luck. Each judge model therefore sees the names in its own shuffled
chunking, and a name's score is the mean over judges. Two cheap, fast judges
(the defaults) already halve the score variance at a fraction of a cent per
hundred names.

Why a quick screen first: generating thousands of names is free, judging them
properly is not. A score-only pass by the same panel, 50 names per call, costs
~1/6 of a full verdict and predicts it well: on one brief (2026-10) keeping the
top sixth by screen score kept 75% of the names the panel later rated >= 5
(the embedding "vibe" prefilter it replaced kept 30%, barely above chance).

Why a final round: absolute scores are poorly calibrated at the top end, but
LLMs are good at *comparing*. The best few dozen names go to one (stronger)
model in a single call that ranks them against each other and pitches each.

Scale: each judge gives integer 0-10 for `sound`, `fit`, `distinct` and an
overall `score`, plus a short `note` (what the name evokes) and a `flag`
(existing brand / common word / unfortunate meaning). A chunk that fails is
retried; names still missing come back with score None — never a silent 0.
"""

import asyncio
import hashlib
import random
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from ai.llm import DEFAULT_MODEL, LLMWrapper

ProgressCallback = Callable[[int, int], None]

DEFAULT_JUDGES = ["anthropic/claude-haiku-5.5", "openai/gpt-6-luna"]
DEFAULT_FINAL_MODEL = "anthropic/claude-sonnet-5.5"
CRITERIA = ("sound", "fit", "distinct")

# Requests in flight per judge model. These judges are cheap, fast endpoints
# built for burst traffic; the sliding window keeps a slow call from stalling.
DEFAULT_CONCURRENCY = 24
# Names per quick-screen call: output is a bare number per name, so large
# chunks keep the repeated brief cheap without hurting recall.
SCREEN_CHUNK_SIZE = 50
# User star ratings shown to the judges as taste examples.
MAX_EXAMPLES = 60

JUDGE_SYSTEM_PROMPT = """You are a sharp, experienced naming strategist on a branding jury.

The candidate names were NOT written by a person or a language model: they were sampled letter by letter from Markov chains trained on word lists, precisely to escape the predictable, internet-average names language models come up with. Most candidates are noise. Your job is to find the rare gems: names that sound good, carry the right associations and stick in the mind.

Score every candidate with integers from 0 to 10:
- sound: how it sounds and reads aloud: easy to pronounce and spell, pleasant rhythm and mouthfeel.
- fit: how well its sound, roots and echoes of real words (in any language) evoke the brief.
- distinct: memorable, ownable and fresh; not generic, not a common word, not forgettable.
- score: your overall verdict as a name for the brief (your judgement, not an average).

Calibrate hard and use the full range: a typical random candidate is a 2-4, a decent one 5-6, a strong one 7-8; reserve 9-10 for names you would genuinely put on a shortlist.

For each name also give:
- note: at most 12 words on what it evokes or why it works or fails (associations, roots, feel).
- flag: "" normally; otherwise a few words of warning if it is an existing well-known brand or product, a common dictionary word, or has an unfortunate meaning or sound in a major language.

Reply with JSON only, covering every candidate exactly once, spelled exactly as given:
{"names": [{"name": "...", "sound": 0, "fit": 0, "distinct": 0, "score": 0, "note": "...", "flag": ""}]}"""

SCREEN_SYSTEM_PROMPT = """You are screening raw candidates for a naming jury. The candidates were sampled letter by letter from Markov chains; most are noise. Quickly rate each one 0-10 as a name for the brief (sound, fit, memorability). A typical candidate is 2-4; give 6+ only to names worth the jury's time.

Reply with JSON only, every candidate exactly once, spelled exactly as given:
{"scores": {"name": 0}}"""

FINAL_SYSTEM_PROMPT = """You chair a naming jury. The shortlist below already survived a first round in which hundreds of statistically generated candidates were scored. Now compare them head to head.

Rank ALL of them from best to worst for the brief, weighing sound, fit with the brief, memorability and ownability, and the client's taste as shown by their ratings. For each give:
- pitch: at most 15 words on why it could be the one.
- concern: at most 10 words on its biggest risk, or "".

Reply with JSON only, including every name exactly once, spelled exactly as given:
{"ranking": [{"name": "...", "pitch": "...", "concern": ""}]}"""


def build_brief(description: str, keywords: Sequence[str], guidance: str,
                examples: Sequence[Tuple[str, int]]) -> str:
    """The shared context block: what the name is for and the client's taste."""
    parts = [f"BRIEF (what the name is for):\n{description.strip()}"]
    if keywords:
        parts.append(f"VIBE (words that capture the intended feel): {', '.join(keywords)}")
    if guidance.strip():
        parts.append(f"EXTRA GUIDANCE from the client:\n{guidance.strip()}")
    if examples:
        lines = "\n".join(f"- {name}: {stars}/5" for name, stars in examples)
        parts.append("THE CLIENT'S OWN STAR RATINGS of earlier candidates (learn their taste; "
                     f"don't reuse these names):\n{lines}")
    return "\n\n".join(parts)


def select_examples(ratings: Dict[str, int], exclude: Sequence[str] = (),
                    limit: int = MAX_EXAMPLES) -> List[Tuple[str, int]]:
    """Rated names as few-shot taste examples, stratified across star levels
    so the judges also see what the user dislikes (not just the top-rated).
    Names in `exclude` (the ones being judged) are left out, or the judges
    just parrot the user's rating back."""
    skip = set(exclude)
    by_stars: Dict[int, List[str]] = {}
    for name, stars in ratings.items():
        if stars and stars > 0 and name not in skip:
            by_stars.setdefault(int(stars), []).append(name)
    if not by_stars:
        return []
    rng = random.Random(0)
    per_level = max(1, limit // len(by_stars))
    chosen: List[Tuple[str, int]] = []
    for stars in sorted(by_stars, reverse=True):
        names = sorted(by_stars[stars])
        rng.shuffle(names)
        chosen.extend((name, stars) for name in names[:per_level])
    return chosen[:limit]


def _as_score(value: Any) -> Optional[float]:
    try:
        return max(0.0, min(10.0, float(value)))
    except (TypeError, ValueError):
        return None


def _entries(result: Any) -> Dict[str, Dict[str, Any]]:
    """Normalise a judge response into {lowercased name: entry dict}.

    Accepts the requested {"names": [...]} shape, the screen's
    {"scores": {name: score}}, a bare list, or the looser {name: score} /
    {name: {...}} dicts some models fall back to.
    """
    if isinstance(result, dict) and isinstance(result.get("names"), list):
        result = result["names"]
    elif isinstance(result, dict) and isinstance(result.get("scores"), dict):
        result = result["scores"]
    entries: Dict[str, Dict[str, Any]] = {}
    if isinstance(result, list):
        for item in result:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                entries[item["name"].strip().lower()] = item
    elif isinstance(result, dict):
        for name, value in result.items():
            entry = value if isinstance(value, dict) else {"score": value}
            entries[str(name).strip().lower()] = entry
    return entries


def _cache_key(*parts: str) -> str:
    return hashlib.md5("\x1f".join(parts).encode()).hexdigest()


class NameJudge:
    """Scores names with a panel of LLM judges running concurrently."""

    def __init__(self, models: Optional[Sequence[str]] = None, chunk_size: int = 20,
                 concurrency: int = DEFAULT_CONCURRENCY, reasoning_effort: str = "none",
                 cache_dir: str = ".cache"):
        self.models = list(dict.fromkeys(models or DEFAULT_JUDGES))
        self.chunk_size = max(1, int(chunk_size))
        self.concurrency = concurrency
        self.reasoning_effort = reasoning_effort
        self.cache_dir = cache_dir

    def _wrapper(self, component: str) -> LLMWrapper:
        wrapper = LLMWrapper(cache_dir=self.cache_dir, reasoning_effort=self.reasoning_effort)
        wrapper.set_component(component)
        return wrapper

    # ------------------------------------------------------------------
    # First round: panel scoring
    # ------------------------------------------------------------------

    def judge(self, names: List[str], brief: str,
              progress_callback: Optional[ProgressCallback] = None) -> Tuple[List[Dict[str, Any]], float]:
        """Score `names` with every judge. Returns (verdicts in input order,
        cost in USD). Each verdict: name, score (mean over judges, None if no
        judge returned it), sound/fit/distinct, note, notes {model: note},
        flag, judges {model: score}."""
        if not names:
            return [], 0.0
        wrapper = self._wrapper("name_judge")
        start_cost = wrapper.cost_tracker.get_total_cost()
        per_model = asyncio.run(self._judge_all(names, brief, JUDGE_SYSTEM_PROMPT, self.chunk_size,
                                                progress_callback))
        cost = wrapper.cost_tracker.get_total_cost() - start_cost
        return [self._aggregate(name, per_model) for name in names], cost

    def screen(self, names: List[str], brief: str,
               progress_callback: Optional[ProgressCallback] = None) -> Tuple[Dict[str, Optional[float]], float]:
        """Quick score-only pass by every judge, to pick which names get a
        full verdict. Returns ({name: mean 0-10 score, None if no judge
        returned it}, cost in USD)."""
        if not names:
            return {}, 0.0
        wrapper = self._wrapper("name_screen")
        start_cost = wrapper.cost_tracker.get_total_cost()
        per_model = asyncio.run(self._judge_all(names, brief, SCREEN_SYSTEM_PROMPT, SCREEN_CHUNK_SIZE,
                                                progress_callback))
        cost = wrapper.cost_tracker.get_total_cost() - start_cost
        return {name: self._aggregate(name, per_model)["score"] for name in names}, cost

    @staticmethod
    def _chunks(names: List[str], model: str, size: int) -> List[List[str]]:
        """Shuffle per judge (deterministically, so re-runs hit the cache) so
        chunk-neighbour effects average out across the panel."""
        order = list(names)
        random.Random(_cache_key(model)).shuffle(order)
        return [order[i:i + size] for i in range(0, len(order), size)]

    async def _judge_all(self, names: List[str], brief: str, system_prompt: str, chunk_size: int,
                         progress_callback: Optional[ProgressCallback]) -> Dict[str, Dict[str, Dict[str, Any]]]:
        chunked = {model: self._chunks(names, model, chunk_size) for model in self.models}
        done = {model: 0 for model in self.models}
        total = sum(len(chunks) for chunks in chunked.values())

        def report(model: str):
            def callback(model_done: int, _model_total: int):
                done[model] = model_done
                if progress_callback:
                    progress_callback(sum(done.values()), total)
            return callback

        results = await asyncio.gather(*(
            self._judge_with_model(model, chunked[model], brief, system_prompt, report(model))
            for model in self.models))
        return dict(zip(self.models, results))

    async def _judge_with_model(self, model: str, chunks: List[List[str]], brief: str, system_prompt: str,
                                progress_callback: ProgressCallback) -> Dict[str, Dict[str, Any]]:
        """{name: entry} from one judge; names it skipped get one retry pass."""
        verdicts: Dict[str, Dict[str, Any]] = {}
        missing = await self._score_chunks(model, chunks, brief, system_prompt, verdicts, progress_callback)
        if missing:
            print(f"{model}: retrying {len(missing)} names it skipped or failed")
            size = len(chunks[0])
            retry_chunks = [missing[i:i + size] for i in range(0, len(missing), size)]
            still_missing = await self._score_chunks(model, retry_chunks, brief, system_prompt, verdicts, None,
                                                     retry=True)
            if still_missing:
                print(f"{model}: no verdict for {len(still_missing)} names: {still_missing[:10]}")
        return verdicts

    async def _score_chunks(self, model: str, chunks: List[List[str]], brief: str, system_prompt: str,
                            verdicts: Dict[str, Dict[str, Any]],
                            progress_callback: Optional[ProgressCallback], retry: bool = False) -> List[str]:
        prompts = [f"{brief}\n\nCANDIDATES ({len(chunk)}):\n" + "\n".join(chunk) for chunk in chunks]
        # A retry must not be served the cached (bad) response.
        keys = [_cache_key(model, system_prompt, prompt, "retry" if retry else "") for prompt in prompts]
        results = await self._wrapper("name_judge").batch_json_complete(
            prompts=prompts, model=model, cache_keys=keys, batch_size=self.concurrency,
            system_prompt=system_prompt, progress_callback=progress_callback)

        missing: List[str] = []
        for chunk, result in zip(chunks, results):
            entries = {} if isinstance(result, Exception) else _entries(result)
            for name in chunk:
                entry = entries.get(name.strip().lower())
                if entry is None or _as_score(entry.get("score")) is None:
                    missing.append(name)
                else:
                    verdicts[name] = entry
        return missing

    @staticmethod
    def _aggregate(name: str, per_model: Dict[str, Dict[str, Dict[str, Any]]]) -> Dict[str, Any]:
        entries = {model: verdicts[name] for model, verdicts in per_model.items() if name in verdicts}

        def mean(field: str) -> Optional[float]:
            values = [v for v in (_as_score(e.get(field)) for e in entries.values()) if v is not None]
            return round(sum(values) / len(values), 2) if values else None

        notes = {model: str(e.get("note") or "").strip() for model, e in entries.items()}
        # Judges flag the same problem in different words; one is enough.
        flags = [str(e.get("flag") or "").strip() for e in entries.values()]
        return {
            "name": name,
            "score": mean("score"),
            **{criterion: mean(criterion) for criterion in CRITERIA},
            "note": next((note for note in notes.values() if note), ""),
            "notes": notes,
            "flag": next((flag for flag in flags if flag), ""),
            "judges": {model: _as_score(e.get("score")) for model, e in entries.items()},
        }

    # ------------------------------------------------------------------
    # Final round: listwise comparison
    # ------------------------------------------------------------------

    def final_round(self, names: List[str], brief: str, model: str = DEFAULT_FINAL_MODEL,
                    reasoning_effort: str = "low") -> Tuple[List[Dict[str, Any]], float]:
        """Rank a shortlist head to head in one call. Returns ([{name, rank,
        pitch, concern}] best first, cost). Names the model drops are
        appended at the end without a pitch."""
        if not names:
            return [], 0.0
        wrapper = LLMWrapper(cache_dir=self.cache_dir, reasoning_effort=reasoning_effort)
        wrapper.set_component("final_round")
        start_cost = wrapper.cost_tracker.get_total_cost()
        prompt = f"{brief}\n\nSHORTLIST ({len(names)}):\n" + "\n".join(names)
        [result] = asyncio.run(wrapper.batch_json_complete(
            prompts=[prompt], model=model or DEFAULT_MODEL,
            cache_keys=[_cache_key(model, FINAL_SYSTEM_PROMPT, prompt)],
            system_prompt=FINAL_SYSTEM_PROMPT))
        if isinstance(result, Exception):
            raise result
        cost = wrapper.cost_tracker.get_total_cost() - start_cost

        by_lower = {name.strip().lower(): name for name in names}
        ranking: List[Dict[str, Any]] = []
        seen = set()
        items = result.get("ranking", []) if isinstance(result, dict) else result
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            name = by_lower.get(str(item.get("name", "")).strip().lower())
            if name and name not in seen:
                seen.add(name)
                ranking.append({"name": name, "pitch": str(item.get("pitch") or ""),
                                "concern": str(item.get("concern") or "")})
        ranking += [{"name": name, "pitch": "", "concern": ""} for name in names if name not in seen]
        for rank, entry in enumerate(ranking, 1):
            entry["rank"] = rank
        return ranking, cost
