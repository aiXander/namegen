"""
Multi-component sampling system for Markov name generation.

Generates names that contain a set of fixed components (e.g. ["co", "mind"])
connected by Markov-sampled filler segments. Each attempt:

1. Picks a component ordering (user-forced or a random permutation).
2. Picks a target length and randomly distributes the spare space across the
   gaps (before, between — honoring ``component_separation`` — and after).
3. Builds the word left to right, sampling each filler segment with the real
   accumulated word as Markov context and verifying every junction into a
   fixed part is a transition the (backed-off) model could have produced —
   so components blend into the word instead of being glued on.

``starts_with``/``ends_with`` are treated as additional fixed parts pinned to
the word boundaries. A single posterior validation guarantees correctness.

Multi-word output: ``word_breaks`` (the word count minus one, from the
``generation.word_counts`` setting) literal space separators are placed among
the fixed parts. A space is a structural
separator the model never emits, so on each side of one the Markov context is
reset to fresh ``#``-padding — i.e. each space starts a brand-new word. The
junction plausibility checks are skipped *across* a space (the model has no
opinion about spaces) but still enforced when a real fixed part begins a new
word. This is how two words + ``ends_with='a'`` yields e.g. ``code noda``.
"""

import random
import itertools
from typing import List, Optional, Tuple
from dataclasses import dataclass, field
from .markov_model import MarkovModel
from .constraint_sampler import (ConstraintSampler, GenerationConstraints,
                                 meets_includes_constraint, dequote, MIN_WORD_LEN)


@dataclass
class ComponentConstraints(GenerationConstraints):
    """Extended constraints supporting multi-component generation"""
    components: List[str] = field(default_factory=list)  # Required word components
    component_order: Optional[List[int]] = None  # Specific component ordering (indices)
    component_separation: Tuple[int, int] = (0, 5)  # Min/max chars between components
    word_breaks: int = 0  # Number of space separators (multi-word output)

    def __post_init__(self):
        super().__post_init__()
        # Ensure all components are lowercase, quote-free, and non-empty
        self.components = [dequote(comp).strip().lower() for comp in self.components
                           if dequote(comp).strip()]


class MultiComponentSampler:
    """Orchestrates component-based sampling with junction plausibility."""

    MAX_ORDERINGS_PER_ATTEMPT = 8
    SEPARATOR = " "        # literal word separator inserted for word breaks

    def __init__(self, markov_models):
        if isinstance(markov_models, MarkovModel):
            markov_models = [markov_models]
        self.models = markov_models
        self.model = markov_models[0]
        # Reuse the constraint sampler's masking/backoff/plausibility machinery
        self.sampler = ConstraintSampler(markov_models)

    def generate_with_components(self, constraints: ComponentConstraints) -> Optional[str]:
        """
        Generate a name containing all required components.

        Returns a name meeting all constraints, or None for this attempt
        (callers retry with fresh randomness).
        """
        if not constraints.components and not constraints.word_breaks:
            return None
        if not constraints.is_feasible():
            return None

        excludes = constraints.excludes_tokens()
        if any(token in comp for comp in constraints.components for token in excludes):
            return None  # a required component contains a forbidden substring

        # `includes` tokens still steer the Markov gap-filling toward a match
        # (correctness is enforced by the posterior _validate either way).
        guide_tokens = self.sampler._pick_guide_tokens(constraints, excludes)

        min_sep, max_sep = constraints.component_separation
        min_sep = max(0, min_sep)
        max_sep = max(min_sep, max_sep)

        for ordering in self._orderings(constraints):
            result = self._sample_arrangement(ordering, constraints, excludes,
                                              min_sep, max_sep, guide_tokens)
            if result is not None and self._validate(result, constraints, excludes):
                return result
        return None

    def _orderings(self, constraints: ComponentConstraints) -> List[List[str]]:
        """Component orderings to try this attempt (shuffled permutations,
        or the single user-forced order)."""
        if constraints.component_order:
            return [[constraints.components[i] for i in constraints.component_order]]
        orderings = [list(p) for p in itertools.permutations(constraints.components)]
        random.shuffle(orderings)
        return orderings[:self.MAX_ORDERINGS_PER_ATTEMPT]

    def _insert_separators(self, components: List[str], word_breaks: int) -> List[Tuple[str, str]]:
        """Lay the ordered components out as ``(text, kind)`` parts and sprinkle
        ``word_breaks`` separators at random slots. Adjacent separators are fine:
        the gap between them gets a minimum length, so it becomes a real word."""
        parts: List[Tuple[str, str]] = [(comp, "comp") for comp in components]
        for _ in range(max(0, word_breaks)):
            parts.insert(random.randint(0, len(parts)), (self.SEPARATOR, "sep"))
        return parts

    def _sample_arrangement(self, components: List[str], constraints: ComponentConstraints,
                            excludes: List[str], min_sep: int, max_sep: int,
                            guide_tokens: List[str]) -> Optional[str]:
        """Sample one word for a specific component ordering, or None."""
        prefix = constraints.starts_with
        suffix = constraints.ends_with
        order = self.model.order
        max_length = constraints.max_length

        # Fixed parts in order: prefix and suffix are pinned to the boundaries;
        # word-break separators are interleaved among the components.
        parts = ([(prefix, "prefix")] if prefix else []) \
            + self._insert_separators(components, constraints.word_breaks) \
            + ([(suffix, "suffix")] if suffix else [])
        if not parts:
            return None
        fixed_parts = [text for text, _ in parts]
        kinds = [kind for _, kind in parts]
        n_gaps = len(fixed_parts) + 1  # before, between each pair, after

        # Gap length bounds: real components are separated by min_sep..max_sep;
        # the leading/trailing gaps (and gaps adjacent to prefix/suffix, which
        # ARE the word boundaries) are unconstrained except that prefix must
        # start the word and suffix must end it.
        gap_min = [0] * n_gaps
        gap_max = [max_length] * n_gaps
        for gap in range(1, len(fixed_parts)):
            if kinds[gap - 1] == "comp" and kinds[gap] == "comp":
                gap_min[gap] = min_sep
                gap_max[gap] = max_sep
        if prefix:
            gap_min[0] = gap_max[0] = 0  # nothing before the prefix
        if suffix:
            gap_min[-1] = gap_max[-1] = 0  # nothing after the suffix

        # Each separator must have a real word on either side. Bump the gap that
        # feeds a word whenever no adjacent fixed part already supplies letters.
        for i, kind in enumerate(kinds):
            if kind != "sep":
                continue
            left_fixed = len(fixed_parts[i - 1]) if i > 0 and kinds[i - 1] != "sep" else 0
            gap_min[i] = max(gap_min[i], MIN_WORD_LEN - left_fixed)
            right_fixed = len(fixed_parts[i + 1]) if i + 1 < len(fixed_parts) and kinds[i + 1] != "sep" else 0
            gap_min[i + 1] = max(gap_min[i + 1], MIN_WORD_LEN - right_fixed)

        fixed_length = sum(len(part) for part in fixed_parts)
        required = fixed_length + sum(gap_min)
        if required > max_length:
            return None

        target = random.randint(max(constraints.min_length, required), max_length)
        gaps = self._distribute_space(target - required, gap_min, gap_max)
        if gaps is None:
            return None

        # Build the word left to right with real Markov context.
        word = "#" * order  # padded sampling state
        clean = ""
        for i, part in enumerate(fixed_parts):
            segment = self._sample_segment(word, clean, gaps[i], excludes, guide_tokens, max_length)
            if segment is None:
                return None
            word += segment
            clean += segment
            # The junction into a real fixed part must be model-plausible (chars
            # *inside* a user-given part are exempt — users may ask for parts the
            # training data could never produce). A separator is exempt entirely:
            # the model has no transitions for spaces. The pinned suffix gets the
            # strict check — a weak junction there is very visible, retries cheap.
            if part and part[0] in self.sampler.char_index and clean:
                strict = bool(suffix) and i == len(fixed_parts) - 1
                if not self.sampler._is_plausible(word, part[0], strict=strict):
                    return None
            # Append the fixed part. Each separator char ends the current word,
            # so the Markov context resets to fresh padding for the next one.
            for ch in part:
                clean += ch
                word = word + ch if ch in self.sampler.char_index else "#" * order
            if any(token in clean for token in excludes):
                return None

        trailing = self._sample_segment(word, clean, gaps[-1], excludes, guide_tokens, max_length)
        if trailing is None:
            return None
        word += trailing
        clean += trailing

        # The word must also end somewhere the model could end a word
        # (lenient any-order check: tight component arrangements often have
        # zero freedom left, and a forced component beats returning nothing).
        if not self.sampler._is_plausible(word, "#"):
            return None
        return clean

    @staticmethod
    def _distribute_space(extra: int, gap_min: List[int], gap_max: List[int]) -> Optional[List[int]]:
        """Start every gap at its minimum and sprinkle the spare characters
        over gaps that still have headroom, uniformly at random."""
        gaps = list(gap_min)
        headroom = [gap_max[i] - gap_min[i] for i in range(len(gaps))]
        for _ in range(extra):
            open_gaps = [i for i, room in enumerate(headroom) if room > 0]
            if not open_gaps:
                return None  # target length unreachable with these gap caps
            choice = random.choice(open_gaps)
            gaps[choice] += 1
            headroom[choice] -= 1
        return gaps

    def _sample_segment(self, word: str, clean: str, length: int,
                        excludes: List[str], guide_tokens: List[str],
                        max_length: int) -> Optional[str]:
        """Sample exactly `length` filler characters continuing from the
        current word state, or None on a dead end. `guide_tokens` softly steer
        the fill toward an unmet `includes` token, exactly as in single-word
        sampling."""
        segment = ""
        for _ in range(length):
            probs = self.sampler._constrained_probs(
                word, clean, allow_termination=False, termination_bias=1.0,
                guide_tokens=guide_tokens, capacity=max_length - len(clean),
                excludes=excludes)
            if probs is None:
                return None
            char = self.sampler._sample_from_probabilities(probs)
            segment += char
            word += char
            clean += char
        return segment

    def _validate(self, word: str, constraints: ComponentConstraints,
                  excludes: List[str]) -> bool:
        """Single authoritative check of all constraints on the final word."""
        if not (constraints.min_length <= len(word) <= constraints.max_length):
            return False
        # Word-break structure: exactly the requested number of separators, and
        # no empty word (no leading/trailing/double space).
        if word.count(self.SEPARATOR) != constraints.word_breaks:
            return False
        if constraints.word_breaks and any(not w for w in word.split(self.SEPARATOR)):
            return False
        if any(comp not in word for comp in constraints.components):
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
