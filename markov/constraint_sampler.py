"""
Constraint-aware sampling system for Markov name generation.

Constraints are integrated *during* sampling wherever possible:

- ``starts_with`` seeds the sampling context.
- ``excludes`` masks transitions that would complete a forbidden substring.
- ``includes`` softly boosts transitions that make progress toward a required
  token (only transitions the model already allows), so matching names are
  found orders of magnitude faster than generate-then-filter.
- ``ends_with`` is spliced on at a sampled splice point; the junction must be
  a transition the (backed-off) model could actually have produced, and if it
  isn't, the body keeps growing and the splice is retried at every length up
  to the maximum — instead of rejecting the whole attempt.
- Length is steered by masking termination below ``min_length`` and
  progressively boosting it past a sampled target length.

Whenever a constraint mask zeroes out every transition at the highest model
order, sampling backs off to lower-order models (Katz-style) before giving up.
A single posterior validation at the end guarantees correctness of whatever
the integrated sampling produced.
"""

import random
from typing import List, Optional
from dataclasses import dataclass
from .markov_model import MarkovModel

# Multiplier on '#' once the sampled target length is reached (compounds per
# extra character, so words rarely overshoot the target by much).
TERMINATION_BIAS = 4.0
# Multiplier on the next character that advances an unmet `includes` token.
# Only applied to transitions the model already allows (nonzero probability),
# so guided names stay statistically consistent with the training data.
INCLUDES_BOOST = 8.0


def parse_includes_groups(includes_pattern: str) -> List[List[str]]:
    """Parse an includes pattern into OR-groups of AND-tokens.

    Format: 'x,a' = x AND a; 'x;a' = x OR a; 'x,a;b' = (x AND a) OR b.
    """
    groups = []
    for group in includes_pattern.split(';'):
        tokens = [token.strip() for token in group.split(',') if token.strip()]
        if tokens:
            groups.append(tokens)
    return groups


def meets_includes_constraint(word: str, includes_pattern: str) -> bool:
    """Check a word against an includes pattern with AND/OR logic."""
    groups = parse_includes_groups(includes_pattern)
    if not groups:
        return True
    return any(all(token in word for token in group) for group in groups)


def parse_excludes_tokens(excludes_pattern: str) -> List[str]:
    """Parse forbidden substrings; ',' and ';' both separate multiple tokens."""
    return [token.strip() for token in excludes_pattern.replace(';', ',').split(',')
            if token.strip()]


@dataclass
class GenerationConstraints:
    """Container for all generation constraints"""
    min_length: int = 1
    max_length: int = 20
    starts_with: str = ""
    ends_with: str = ""
    includes: str = ""
    excludes: str = ""
    regex_pattern: Optional[str] = None

    def __post_init__(self):
        """Ensure all text constraints are lowercase"""
        self.starts_with = self.starts_with.strip().lower()
        self.ends_with = self.ends_with.strip().lower()
        self.includes = self.includes.strip().lower()
        self.excludes = self.excludes.strip().lower()

    def includes_groups(self) -> List[List[str]]:
        return parse_includes_groups(self.includes)

    def excludes_tokens(self) -> List[str]:
        return parse_excludes_tokens(self.excludes)

    def is_feasible(self) -> bool:
        """Cheap static check that the constraints aren't self-contradictory,
        so callers can bail out immediately instead of burning their retry
        budget on attempts that can never succeed."""
        if self.min_length > self.max_length:
            return False
        if len(self.starts_with) + len(self.ends_with) > self.max_length:
            return False

        excludes = self.excludes_tokens()

        def violates(text: str) -> bool:
            return any(token in text for token in excludes)

        if violates(self.starts_with) or violates(self.ends_with):
            return False

        groups = self.includes_groups()
        if groups:
            # At least one OR-group must be satisfiable: none of its tokens may
            # contain a forbidden substring or exceed the maximum length.
            if not any(
                all(not violates(token) and len(token) <= self.max_length for token in group)
                for group in groups
            ):
                return False

        return True


class ConstraintSampler:
    """
    Main constraint-aware sampler that coordinates all constraint handling.
    """

    def __init__(self, markov_models):
        """Initialize with a list of Markov models (highest order first) for
        backoff, or a single model."""
        if isinstance(markov_models, MarkovModel):
            markov_models = [markov_models]
        self.models = markov_models
        self.model = markov_models[0]  # Primary (highest-order) model
        self.alphabet = self.model.alphabet
        self.char_index = {char: i for i, char in enumerate(self.alphabet)}
        self.term_index = self.char_index["#"]

    def generate_constrained_name(self, constraints: GenerationConstraints) -> Optional[str]:
        """
        Generate a name with integrated constraint handling.

        Returns a name meeting all constraints, or None for this attempt
        (callers retry; None is also returned immediately for infeasible
        constraint combinations).
        """
        if not constraints.is_feasible():
            return None

        suffix = constraints.ends_with
        excludes = constraints.excludes_tokens()
        guide_tokens = self._pick_guide_tokens(constraints, excludes)

        # Seed sampling state with the required prefix after full padding.
        word = "#" * self.model.order + constraints.starts_with
        clean = constraints.starts_with

        # The "body" is everything except the spliced-on suffix.
        body_max = constraints.max_length - len(suffix)
        body_min = max(constraints.min_length - len(suffix), len(clean))
        target = random.randint(body_min, body_max)

        final = None
        while True:
            clean_length = len(clean)

            if suffix:
                # Try splicing the suffix at every length from the sampled
                # target up to the maximum, instead of rejecting outright.
                if clean_length >= target and self._can_splice(word, clean, suffix, excludes):
                    final = clean + suffix
                    break
                if clean_length >= body_max:
                    break  # no plausible splice point found in the window
            elif clean_length >= body_max:
                # Hard length cap: only accept if the model could plausibly
                # end a word here (avoids chopped-off endings).
                if self._is_plausible(word, "#", strict=True):
                    final = clean
                break

            allow_termination = not suffix and clean_length >= constraints.min_length
            termination_bias = (TERMINATION_BIAS ** (clean_length - target + 1)
                                if not suffix and clean_length >= target else 1.0)
            capacity = body_max - clean_length

            probs = self._constrained_probs(word, clean, allow_termination,
                                            termination_bias, guide_tokens,
                                            capacity, excludes)
            if probs is None:
                break  # dead end at every model order

            char = self._sample_from_probabilities(probs)
            if char == "#":
                final = clean  # only reachable when termination was allowed
                break
            word += char
            clean += char

        if final is None:
            return None
        return final if self._validate(final, constraints, excludes) else None

    # ------------------------------------------------------------------
    # Sampling internals
    # ------------------------------------------------------------------

    def _pick_guide_tokens(self, constraints: GenerationConstraints,
                           excludes: List[str]) -> List[str]:
        """Pick one satisfiable OR-group to guide sampling toward. Callers
        retry per attempt, so random choice covers all groups over time."""
        groups = [group for group in constraints.includes_groups()
                  if all(not any(t in token for t in excludes) for token in group)]
        return random.choice(groups) if groups else []

    def _constrained_probs(self, word: str, clean: str, allow_termination: bool,
                           termination_bias: float, guide_tokens: List[str],
                           capacity: int, excludes: List[str]) -> Optional[List[float]]:
        """Next-character distribution with all constraint masks applied.

        Backs off to lower-order models not only when a context is unseen,
        but also when constraint masking zeroes out every transition at the
        current order — only giving up when every order is a dead end.
        """
        for model in self.models:
            chain = model.chains.get(word[-model.order:])
            if chain is None:
                continue

            probs = chain.copy()

            # Mask characters that would complete a forbidden substring.
            if excludes:
                for i, char in enumerate(self.alphabet):
                    if i == self.term_index or probs[i] <= 0:
                        continue
                    candidate = clean + char
                    if any(candidate.endswith(token) for token in excludes):
                        probs[i] = 0.0

            if not allow_termination:
                probs[self.term_index] = 0.0
            elif termination_bias != 1.0:
                probs[self.term_index] *= termination_bias

            # Boost transitions that progress toward an unmet includes token.
            for token in guide_tokens:
                if token in clean:
                    continue
                overlap = self._suffix_prefix_overlap(clean, token)
                if len(token) - overlap > capacity:
                    continue  # can't fit anymore this attempt
                index = self.char_index.get(token[overlap])
                if index is not None and probs[index] > 0:
                    probs[index] *= INCLUDES_BOOST

            if sum(probs) > 0:
                return probs
            # All transitions masked at this order — back off and retry.

        return None

    @staticmethod
    def _suffix_prefix_overlap(word: str, token: str) -> int:
        """Length of the longest suffix of `word` that is a prefix of `token`."""
        for k in range(min(len(word), len(token) - 1), 0, -1):
            if word.endswith(token[:k]):
                return k
        return 0

    def _is_plausible(self, word: str, char: str, strict: bool = False) -> bool:
        """Whether `char` is a transition the model could have produced after
        `word`.

        Lenient (default): backs off past zero-probability higher-order
        contexts — plausible if *any* order allows the transition. Strict:
        the highest-order model that knows this context decides — used for
        suffix junctions, where growing the body and retrying the splice
        makes rejection cheap and quality matters most.
        """
        index = self.char_index.get(char)
        if index is None:
            return False
        for model in self.models:
            chain = model.chains.get(word[-model.order:])
            if chain is None:
                continue
            if chain[index] > 0:
                return True
            if strict:
                return False
        return False

    def _can_splice(self, word: str, clean: str, suffix: str,
                    excludes: List[str]) -> bool:
        """Check that splicing `suffix` onto the current state yields a
        junction and ending the model could actually have produced, and
        doesn't introduce a forbidden substring."""
        candidate = clean + suffix
        if any(token in candidate for token in excludes):
            return False
        state = word
        for char in suffix:
            if not self._is_plausible(state, char, strict=True):
                return False
            state += char
        return self._is_plausible(state, "#", strict=True)

    def _sample_from_probabilities(self, probs: List[float]) -> Optional[str]:
        """Sample a character from probability distribution"""
        total = sum(probs)
        if total <= 0:
            return None

        rand = random.random() * total
        accumulator = 0.0

        for i, prob in enumerate(probs):
            accumulator += prob
            if rand < accumulator:
                return self.alphabet[i]

        return self.alphabet[-1]

    # ------------------------------------------------------------------
    # Posterior validation
    # ------------------------------------------------------------------

    def _validate(self, word: str, constraints: GenerationConstraints,
                  excludes: List[str]) -> bool:
        """Single authoritative check that the assembled word meets every
        constraint (integrated sampling makes passing likely, not certain)."""
        if not (constraints.min_length <= len(word) <= constraints.max_length):
            return False
        if constraints.starts_with and not word.startswith(constraints.starts_with):
            return False
        if constraints.ends_with and not word.endswith(constraints.ends_with):
            return False
        if any(token in word for token in excludes):
            return False
        if constraints.includes and not meets_includes_constraint(word, constraints.includes):
            return False
        return True
