"""Embedding "vibe" ranking of generated names against keyword "anchors".

Embeds a handful of user-supplied vibe/meaning keywords plus all candidate
names via OpenRouter's embeddings endpoint, then ranks names by cosine
similarity to the anchors. Near-free, but a weak signal: on nonce words the
similarity tracks shared letters more than meaning (Spearman ~0.1 with the
judge panel's score, measured 2026-10). That is why it no longer gates which
names get judged (the quick screen in ai/judge.py does); it only fills the
GUI's Vibe column on demand.

Scoring rule: for each name, the anchor similarities are aggregated with a
softmax-weighted average: score = sum_i softmax(sims / tau)_i * sims_i.
This smoothly interpolates between max-pooling (tau -> 0: only the closest
anchor matters) and the plain mean (tau -> inf: all anchors matter equally),
so a name is rewarded most for nailing one vibe but still gets credit for
resonating with the other anchors.
"""

import asyncio
import sqlite3
from typing import Callable, Dict, List, Tuple, Any, Optional

import numpy as np

from ai.llm import make_async_openrouter_client, _get_nested
from ai.utils import get_cache_path, load_json, ensure_dir, hash_text
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
# concurrently cuts wall time to roughly the slowest single batch. (At 8, a
# 3000-name run with text-embedding-3-large took ~35s.)
MAX_CONCURRENT_BATCHES = 16

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


def softmax_pool(sims: np.ndarray, tau: float = SOFTMAX_TEMPERATURE) -> np.ndarray:
    """Row-wise softmax-weighted average of similarities
    (tau->0: max, tau->inf: mean). ``sims`` is (names, anchors)."""
    weights = np.exp((sims - sims.max(axis=1, keepdims=True)) / tau)
    return (weights * sims).sum(axis=1) / weights.sum(axis=1)


def _unit_rows(vectors: List[List[float]]) -> np.ndarray:
    matrix = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.where(norms == 0, 1, norms)


class EmbeddingStore:
    """Embedding cache: one SQLite file of float32 blobs.

    Replaces the old one-JSON-file-per-vector cache (~48KB of text per vector:
    ~19k files / ~900MB, and ~2s just to parse 3000 of them). Vectors still in
    that legacy directory are migrated lazily on first read.
    """

    def __init__(self, cache_dir: str = ".cache"):
        root = ensure_dir(cache_dir)
        self.path = root / "embeddings.sqlite"
        self.legacy_dir = root / "embeddings"
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS vectors (key TEXT PRIMARY KEY, vec BLOB NOT NULL)")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=30)

    def get_many(self, keys: List[str]) -> Dict[str, List[float]]:
        found: Dict[str, List[float]] = {}
        with self._connect() as db:
            for i in range(0, len(keys), 900):  # SQLite caps bound variables
                chunk = keys[i:i + 900]
                rows = db.execute(f"SELECT key, vec FROM vectors WHERE key IN ({','.join('?' * len(chunk))})",
                                  chunk).fetchall()
                for key, blob in rows:
                    found[key] = np.frombuffer(blob, dtype=np.float32).tolist()
        migrated = {}
        for key in keys:
            if key not in found:
                legacy = get_cache_path(self.legacy_dir, key)
                if legacy.exists():
                    try:
                        migrated[key] = load_json(legacy)
                    except Exception:
                        continue
        if migrated:
            self.put_many(migrated)
            found.update(migrated)
        return found

    def put_many(self, items: Dict[str, List[float]]) -> None:
        with self._connect() as db:
            db.executemany("INSERT OR REPLACE INTO vectors (key, vec) VALUES (?, ?)",
                           [(key, np.asarray(vec, dtype=np.float32).tobytes()) for key, vec in items.items()])


class EmbeddingPrefilter:
    """Embeds texts via OpenRouter with disk caching and cost tracking."""

    def __init__(self, model: str = DEFAULT_EMBEDDING_MODEL, cache_dir: str = ".cache"):
        self.model = model or DEFAULT_EMBEDDING_MODEL
        self.store = EmbeddingStore(cache_dir)
        self.cost_tracker = get_cost_tracker()

    def _cache_key(self, text: str) -> str:
        # Key on (model, text) so switching embedding models never mixes vectors.
        return hash_text(f"{self.model}::{text}")

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
        cached = self.store.get_many([self._cache_key(t) for t in texts])
        results: List[Optional[List[float]]] = [cached.get(self._cache_key(t)) for t in texts]
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
            self.store.put_many({self._cache_key(texts[i]): vec for i, vec in zip(uncached, fresh)})
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
        anchors = _unit_rows(all_vectors[:len(keywords)])
        candidates = _unit_rows(all_vectors[len(keywords):])
        pooled = softmax_pool(candidates @ anchors.T)

        ranked = sorted(zip(names, (float(s) for s in pooled)), key=lambda x: x[1], reverse=True)
        cost = self.cost_tracker.get_total_cost() - initial_cost
        return (ranked, cost)

