"""Markov-health statistics for training word lists.

Quantifies how well a word list supports order-N Markov generation:

- branching_factor: fraction of n-gram contexts with >= 2 distinct successors.
  Low branching means deterministic chains -> the model can only replay training words.
- memorization_rate: fraction of sampled generations that are verbatim training words.
  Estimated by a quick seeded random walk with backoff (mirrors the real generator).
- health score (0-100): composite of the two; higher = better novel-name statistics.

Results are deterministic (fixed RNG seed) so scores are stable across runs.
"""

import random
from collections import defaultdict
from typing import Dict, List

STATS_ORDER = 3
N_SAMPLES = 200
MAX_GEN_LEN = 24
RNG_SEED = 42


def _build_observations(words: List[str], order: int) -> Dict[str, List[str]]:
    """Same n-gram extraction as MarkovModel._train."""
    observations: Dict[str, List[str]] = defaultdict(list)
    for word in words:
        padded = "#" * order + word + "#"
        for i in range(len(padded) - order):
            observations[padded[i:i + order]].append(padded[i + order])
    return observations


def _generate(models: List[Dict[str, List[str]]], order: int, rng: random.Random) -> str:
    """Random walk over raw observation counts with backoff to lower orders."""
    word = "#" * order
    while len(word) < order + MAX_GEN_LEN:
        letter = None
        for o in range(order, 0, -1):
            successors = models[o - 1].get(word[-o:])
            if successors:
                letter = rng.choice(successors)
                break
        if letter is None or letter == "#":
            break
        word += letter
    return word[order:]


def compute_dataset_stats(words: List[str], order: int = STATS_ORDER) -> Dict:
    """Compute Markov-health stats for a word list. Words should be pre-lowercased."""
    unique_words = sorted(set(words))
    if not unique_words:
        return {
            "score": 0, "branching_factor": 0.0, "memorization_rate": 1.0,
            "unique_contexts": 0, "unique_words": 0,
        }

    top = _build_observations(unique_words, order)
    branching = sum(1 for succ in top.values() if len(set(succ)) >= 2) / len(top)

    # Quick generation pass to estimate verbatim-replay rate
    models = [_build_observations(unique_words, o) for o in range(1, order + 1)]
    rng = random.Random(RNG_SEED)
    training_set = set(unique_words)
    samples = [_generate(models, order, rng) for _ in range(N_SAMPLES)]
    valid = [s for s in samples if len(s) >= 3]
    memorization = (sum(1 for s in valid if s in training_set) / len(valid)) if valid else 1.0

    score = round(100 * (0.5 * branching + 0.5 * (1.0 - memorization)))
    return {
        "score": score,
        "branching_factor": round(branching, 3),
        "memorization_rate": round(memorization, 3),
        "unique_contexts": len(top),
        "unique_words": len(unique_words),
    }
