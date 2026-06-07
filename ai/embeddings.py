"""Embedding-based pre-filtering of generated names against keyword "anchors".

Embeds a handful of user-supplied vibe/meaning keywords plus all candidate
names via OpenRouter's embeddings endpoint, then ranks names by cosine
similarity to the anchors. This is a cheap pre-filter stage that lets us
generate far more Markov samples and only send the most on-vibe ones to the
(much more expensive) LLM scorer.

Scoring rule: for each name, the anchor similarities are aggregated with a
softmax-weighted average: score = sum_i softmax(sims / tau)_i * sims_i.
This smoothly interpolates between max-pooling (tau -> 0: only the closest
anchor matters) and the plain mean (tau -> inf: all anchors matter equally),
so a name is rewarded most for nailing one vibe but still gets credit for
resonating with the other anchors.
"""

import asyncio
import math
from typing import Callable, Dict, List, Tuple, Any, Optional

from ai.llm import make_async_openrouter_client, _get_nested
from ai.utils import get_cache_path, load_json, save_json, ensure_dir, hash_text
from ai.cost_tracker import get_cost_tracker

# Progress callback signature: (texts_embedded_so_far, total_texts).
# Called from the embedding event loop as batches complete — keep it cheap
# and thread-safe (e.g. queue.put).
ProgressCallback = Callable[[int, int], None]

# Default embedding model on OpenRouter.
DEFAULT_EMBEDDING_MODEL = "google/gemini-embedding-2"

# Names per embeddings API request — Google AI Studio caps batches at 100
# inputs ("at most 100 requests can be in one batch").
EMBED_BATCH_SIZE = 100

# Batches in flight at once. Batches are independent requests, so issuing them
# concurrently cuts wall time to roughly the slowest single batch.
MAX_CONCURRENT_BATCHES = 8

# Retries per batch on transient errors (rate limits, 5xx, connection blips).
MAX_RETRIES = 3
RETRY_DELAY_BASE = 1.0

# Per-request timeout. A healthy 100-text batch embeds in ~4s, but requests to
# this endpoint occasionally hang — and the OpenAI SDK's default timeout is
# 600s, which turned one stuck request into a 10+ minute stall (measured with
# scripts/time_embeddings.py). Fail fast instead and let the retry loop re-issue.
EMBED_REQUEST_TIMEOUT = 30.0

# Temperature of the softmax aggregation over anchor similarities.
# Cosine sims of distinct anchors typically differ by ~0.05-0.15, so 0.1
# gives the closest anchor a strong (but not winner-take-all) majority weight.
SOFTMAX_TEMPERATURE = 0.1


def _softmax_pool(sims: List[float], tau: float = SOFTMAX_TEMPERATURE) -> float:
    """Softmax-weighted average of similarities (tau->0: max, tau->inf: mean)."""
    m = max(sims)  # subtract max for numerical stability
    weights = [math.exp((s - m) / tau) for s in sims]
    total = sum(weights)
    return sum(w * s for w, s in zip(weights, sims)) / total


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


class EmbeddingPrefilter:
    """Embeds texts via OpenRouter with disk caching and cost tracking."""

    def __init__(self, model: str = DEFAULT_EMBEDDING_MODEL, cache_dir: str = ".cache"):
        self.model = model or DEFAULT_EMBEDDING_MODEL
        self.cache_dir = ensure_dir(cache_dir) / "embeddings"
        ensure_dir(self.cache_dir)
        self.cost_tracker = get_cost_tracker()

    def _cache_key(self, text: str) -> str:
        # Key on (model, text) so switching embedding models never mixes vectors.
        return hash_text(f"{self.model}::{text}")

    def _load_cached(self, text: str) -> Optional[List[float]]:
        path = get_cache_path(self.cache_dir, self._cache_key(text))
        if path.exists():
            try:
                return load_json(path)
            except Exception:
                return None
        return None

    def _save_cached(self, text: str, vector: List[float]):
        try:
            save_json(vector, get_cache_path(self.cache_dir, self._cache_key(text)))
        except Exception as e:
            print(f"Warning: failed to cache embedding: {e}")

    def _record_usage(self, response: Any):
        """Record embedding cost via OpenRouter's native usage accounting."""
        usage = getattr(response, "usage", None)
        tokens = int(_get_nested(usage, "prompt_tokens") or _get_nested(usage, "total_tokens") or 0)
        cost = _get_nested(usage, "cost")
        self.cost_tracker.record_call(
            component="embedding_prefilter",
            call_type="embedding",
            model=self.model,
            input_tokens=tokens,
            output_tokens=0,
            cost=float(cost) if cost is not None else 0.0,
        )

    @staticmethod
    def _is_transient_error(error: Exception) -> bool:
        """Rate limits, 5xx and connection/timeout blips are worth retrying."""
        error_str = str(error).lower()
        transient = [
            "rate limit", "429", "too many requests", "throttle",
            "500", "502", "503", "504", "overloaded",
            "internal server error", "bad gateway", "service unavailable",
            "gateway timeout", "timeout", "timed out", "connection", "temporarily",
        ]
        return any(t in error_str for t in transient)

    async def _embed_batch(self, client, batch: List[str]) -> List[List[float]]:
        """Embed one <=EMBED_BATCH_SIZE batch with retries on transient errors."""
        for attempt in range(MAX_RETRIES + 1):
            try:
                # encoding_format must be explicit: the OpenAI SDK defaults to
                # base64, which OpenRouter's embeddings endpoint doesn't support.
                # max_retries=0: this loop owns retries; stacking the SDK's own
                # internal retries on top would multiply the worst-case stall.
                response = await client.with_options(max_retries=0).embeddings.create(
                    model=self.model, input=batch, encoding_format="float",
                    timeout=EMBED_REQUEST_TIMEOUT,
                )
                # OpenRouter passes provider-side errors back as a 200 body with
                # data: null and an error field, so the SDK never raises. Surface
                # it as a clear exception instead of a downstream TypeError.
                if response.data is None:
                    err = getattr(response, "model_extra", {}) or {}
                    raise RuntimeError(
                        f"Embedding API returned no data (model={self.model}): "
                        f"{err.get('error', response)}"
                    )
                self._record_usage(response)
                # API guarantees order matches input; sort by index defensively.
                data = sorted(response.data, key=lambda d: d.index)
                return [d.embedding for d in data]
            except Exception as e:
                if attempt < MAX_RETRIES and self._is_transient_error(e):
                    delay = RETRY_DELAY_BASE * (2 ** attempt)
                    print(f"Transient embedding error, retrying in {delay:.1f}s: {e}")
                    await asyncio.sleep(delay)
                else:
                    raise
        raise RuntimeError("Unexpected end of retry loop")  # unreachable

    async def _embed_uncached(self, client, texts: List[str],
                              progress_callback: Optional[ProgressCallback] = None,
                              progress_offset: int = 0,
                              progress_total: int = 0) -> List[List[float]]:
        """Embed texts via concurrent batched requests on one shared client.

        ``progress_offset``/``progress_total`` let the callback report progress
        in terms of the caller's full text count (including cache hits).
        """
        batches = [texts[i:i + EMBED_BATCH_SIZE] for i in range(0, len(texts), EMBED_BATCH_SIZE)]
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_BATCHES)
        completed = 0

        async def run_batch(batch: List[str]) -> List[List[float]]:
            nonlocal completed
            async with semaphore:
                vecs = await self._embed_batch(client, batch)
            completed += len(batch)
            if progress_callback:
                progress_callback(progress_offset + completed, progress_total)
            return vecs

        results = await asyncio.gather(*(run_batch(b) for b in batches))
        return [vec for batch_vecs in results for vec in batch_vecs]

    async def _embed_all(self, texts: List[str],
                         progress_callback: Optional[ProgressCallback] = None) -> List[List[float]]:
        """Embed texts, serving from disk cache where possible."""
        results: List[Optional[List[float]]] = [self._load_cached(t) for t in texts]
        uncached = [i for i, v in enumerate(results) if v is None]
        if progress_callback:
            # Cache hits count as instantly done (often the bulk on re-runs)
            progress_callback(len(texts) - len(uncached), len(texts))
        if uncached:
            print(f"Embedding {len(uncached)} texts ({len(texts) - len(uncached)} cached) with {self.model}")
            client = make_async_openrouter_client()
            try:
                fresh = await self._embed_uncached(
                    client, [texts[i] for i in uncached],
                    progress_callback=progress_callback,
                    progress_offset=len(texts) - len(uncached),
                    progress_total=len(texts))
            finally:
                await client.close()
            for i, vec in zip(uncached, fresh):
                results[i] = vec
                self._save_cached(texts[i], vec)
        return results  # type: ignore[return-value]

    def rank_names(
        self,
        names: List[str],
        keywords: List[str],
        progress_callback: Optional[ProgressCallback] = None,
    ) -> Tuple[List[Tuple[str, float]], float]:
        """Rank names by blended cosine similarity to the keyword anchors.

        Returns ([(name, similarity)] sorted descending, cost in USD).
        ``progress_callback(done, total)`` reports embedding progress.
        """
        keywords = [k.strip().lower() for k in keywords if k.strip()]
        if not names or not keywords:
            return ([(n, 0.0) for n in names], 0.0)

        initial_cost = self.cost_tracker.get_total_cost()

        # One flat embed call: anchors first, then names.
        all_vectors = asyncio.run(self._embed_all(keywords + names, progress_callback))
        anchor_vecs = all_vectors[:len(keywords)]
        name_vecs = all_vectors[len(keywords):]

        ranked: List[Tuple[str, float]] = []
        for name, vec in zip(names, name_vecs):
            sims = [_cosine(vec, a) for a in anchor_vecs]
            ranked.append((name, _softmax_pool(sims)))

        ranked.sort(key=lambda x: x[1], reverse=True)
        cost = self.cost_tracker.get_total_cost() - initial_cost
        return (ranked, cost)


def prefilter_names(
    names: List[str],
    keywords: List[str],
    keep_top: int,
    model: str = DEFAULT_EMBEDDING_MODEL,
    cache_dir: str = ".cache",
    min_similarity: float = 0.0,
    progress_callback: Optional[ProgressCallback] = None,
) -> Dict[str, Any]:
    """Convenience wrapper: rank names against keyword anchors and keep the top N.

    ``min_similarity`` additionally drops names below that similarity cutoff
    (0 disables it), so the LLM never sees clearly off-vibe candidates even
    when fewer than ``keep_top`` names remain.

    Returns {kept: [(name, sim)], ranked: [(name, sim)] for ALL names,
    dropped: int, total: int, cost: float}. ``ranked`` is included so callers
    can keep reporting similarities for names the filter dropped.
    """
    prefilter = EmbeddingPrefilter(model=model, cache_dir=cache_dir)
    ranked, cost = prefilter.rank_names(names, keywords, progress_callback=progress_callback)
    keep_top = max(1, int(keep_top))
    kept = [(n, s) for n, s in ranked[:keep_top] if s >= min_similarity]
    return {
        "kept": kept,
        "ranked": ranked,
        "dropped": len(ranked) - len(kept),
        "total": len(ranked),
        "cost": cost,
    }
