import logging
import math
import random
from bisect import bisect_right
from itertools import accumulate
from typing import List, Dict, Optional, Sequence
from collections import defaultdict

logger = logging.getLogger(__name__)

class MarkovModel:
    def __init__(self, data: List[str], order: int, temperature: float, alphabet: List[str],
                 weights: Optional[Sequence[float]] = None):
        """``weights`` (one per word, default 1.0) scale each word's n-gram
        counts — used to balance word lists of very different sizes so a
        40k-word list doesn't drown out a 100-word one."""
        assert alphabet is not None and data is not None
        assert len(alphabet) > 0 and len(data) > 0
        assert weights is None or len(weights) == len(data)
        assert temperature >= 0, "Temperature must be non-negative (0 = deterministic argmax)"

        self.order = order
        self.temperature = temperature
        self.alphabet = alphabet
        self.char_index: Dict[str, int] = {c: i for i, c in enumerate(alphabet)}

        # context -> {next char -> (weighted) count}
        self.observations: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self.chains: Dict[str, List[float]] = {}
        self.cumulative: Dict[str, List[float]] = {}
        # Untempered transition probabilities (the training distribution), used
        # to score how natural a finished name is independent of temperature.
        self.probabilities: Dict[str, Dict[str, float]] = {}

        self._train(data, weights)
        self._build_chains()

    def generate(self, context: str) -> Optional[str]:
        """Generate next letter given context"""
        cumulative = self.cumulative.get(context)
        if cumulative is None:
            return None

        rand = random.random() * cumulative[-1]
        index = bisect_right(cumulative, rand)
        return self.alphabet[min(index, len(self.alphabet) - 1)]

    def probability(self, context: str, char: str) -> Optional[float]:
        """Training-distribution P(char | context), or None if the context was
        never observed (caller should back off to a lower order)."""
        probs = self.probabilities.get(context)
        if probs is None:
            return None
        return probs.get(char, 0.0)

    def _train(self, data: List[str], weights: Optional[Sequence[float]] = None) -> None:
        """Train the model on training data"""
        logger.debug("Training Markov model (order=%d, temp=%.2f) on %d words", self.order, self.temperature, len(data))

        for n, word in enumerate(data):
            weight = 1.0 if weights is None else weights[n]
            # Add padding characters
            padded_word = "#" * self.order + word + "#"

            # Extract n-grams
            for i in range(len(padded_word) - self.order):
                key = padded_word[i:i + self.order]
                value = padded_word[i + self.order]
                self.observations[key][value] += weight

        logger.debug("Extracted %d unique n-gram contexts from training data", len(self.observations))

    def _build_chains(self) -> None:
        """Build Markov chains from observations with temperature scaling.

        Characters never observed after a context keep probability 0 — temperature
        only reshapes the distribution over *observed* transitions. (The previous
        log(1e-10) epsilon leaked real probability mass to unseen characters at
        temperatures > 1, producing un-name-like letter combinations.)

        Scaling is done in log space relative to the max count so that very low
        temperatures cannot overflow (count ** (1/T) blows up for T << 1) and
        degrade gracefully into argmax. Per-context cumulative sums are
        precomputed so unconstrained sampling is a single bisect.
        """
        logger.debug("Building Markov chains for %d contexts...", len(self.observations))
        self.chains = {}
        self.cumulative = {}

        for context, counts in self.observations.items():
            raw_counts = [counts.get(prediction, 0.0) for prediction in self.alphabet]
            total_count = sum(raw_counts)
            self.probabilities[context] = {char: count / total_count for char, count in counts.items()}

            if self.temperature == 0:
                # Temperature 0: always pick most likely (argmax)
                chain = [0.0] * len(self.alphabet)
                chain[raw_counts.index(max(raw_counts))] = 1.0
            else:
                # Temperature scaling over observed transitions only:
                # p_i ∝ count_i^(1/T); unseen characters stay at 0.
                inv_t = 1.0 / self.temperature
                log_max = math.log(max(raw_counts))
                scaled = [math.exp((math.log(count) - log_max) * inv_t) if count > 0 else 0.0
                          for count in raw_counts]
                total = sum(scaled)
                chain = [s / total for s in scaled]

            self.chains[context] = chain
            self.cumulative[context] = list(accumulate(chain))

        logger.debug("Built %d Markov chains with alphabet size %d", len(self.chains), len(self.alphabet))
