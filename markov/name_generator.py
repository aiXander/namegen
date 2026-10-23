import time
import re
import random
from bisect import bisect_left
from typing import List, Optional, Sequence, Tuple
from .generator import Generator
from .constraint_sampler import (GenerationConstraints, meets_includes_constraint,
                                 parse_excludes_tokens)


# Novel reference names sampled to calibrate the naturalness percentile.
NATURALNESS_SAMPLE = 1000


class NameGenerator:
    def __init__(self, data: List[str], order: int, temperature: float, backoff: bool = False,
                 weights: Optional[Sequence[float]] = None):
        """
        Create a procedural name generator.
        
        Args:
            data: Training data for the generator, an array of words
            order: Highest order of model to use - models 1 to order will be generated
            temperature: Temperature for sampling (0=deterministic, 1=training distribution, >1=more random)
            backoff: Whether to fall back to lower order models when highest order model fails
            weights: Optional per-word training weight (see MarkovModel)
        """
        self.generator = Generator(data, order, temperature, backoff, weights)
        # Reference distribution for naturalness(): log-likelihoods of novel
        # names sampled at temperature 1. (Scoring against the training words
        # themselves doesn't work — they're in-sample, so every novel name
        # would rank near 0.)
        self._reference = sorted(self.generator.log_likelihood(name)
                                 for name in self._reference_names(set(data)))

    def _reference_names(self, training: set) -> List[str]:
        """Sample novel names from the untempered training distribution."""
        rng = random.Random(0)
        names: List[str] = []
        for _ in range(NATURALNESS_SAMPLE * 5):
            word = ""
            while len(word) < 20:
                history = "#" * self.generator.order + word
                for model in self.generator.models:
                    probs = model.probabilities.get(history[-model.order:])
                    if probs:
                        break
                if not probs:
                    break
                char = rng.choices(list(probs), weights=list(probs.values()))[0]
                if char == "#":
                    break
                word += char
            if len(word) >= 3 and word not in training:
                names.append(word)
                if len(names) >= NATURALNESS_SAMPLE:
                    break
        return names or [""]

    def naturalness(self, name: str) -> int:
        """0-100 percentile of this name's per-character likelihood among novel
        names the model produces at temperature 1. ~50 = a typical, fluent
        sample; low = odd letter combos that only high temperature or forced
        constraints/components could produce."""
        # In multi-word names, skip 1-2 letter fragments ("co murma"): they are
        # usually forced by constraints, and the reference has no words that short.
        words = name.lower().split()
        scored = " ".join(w for w in words if len(w) >= 3) or name.lower()
        ll = self.generator.log_likelihood(scored)
        return round(100 * bisect_left(self._reference, ll) / len(self._reference))
    
    def generate_name(self, min_length: int = 1, max_length: int = 20, 
                     starts_with: str = "", ends_with: str = "", 
                     includes: str = "", excludes: str = "",
                     regex_pattern: Optional[str] = None) -> Optional[str]:
        """
        Generate a single name within constraints using improved constraint-integrated sampling.
        
        Args:
            min_length: Minimum length of the word
            max_length: Maximum length of the word
            starts_with: Text the word must start with
            ends_with: Text the word must end with
            includes: Text the word must include
            excludes: Text the word must exclude
            regex_pattern: Optional regex pattern the word must match
            
        Returns:
            A word that meets constraints, or None if generated word doesn't meet constraints
        """
        # A space in `includes` means "split into separate words". Only the
        # component sampler can emit a literal space (the model's alphabet has
        # none), so route there — and skip the single-word fallback below, which
        # could never produce the space.
        if " " in includes:
            return self.generate_name_with_components(
                components=[],
                min_length=min_length,
                max_length=max_length,
                starts_with=starts_with,
                ends_with=ends_with,
                includes=includes,
                excludes=excludes,
                regex_pattern=regex_pattern,
            )

        # Try new constraint-integrated approach first
        name = self.generator.generate_with_constraints(
            min_length=min_length,
            max_length=max_length,
            starts_with=starts_with,
            ends_with=ends_with,
            includes=includes,
            excludes=excludes,
            regex_pattern=regex_pattern
        )
        
        if name is not None:
            # Final regex validation if provided
            if regex_pattern and not re.match(regex_pattern, name):
                return None
            return name
        
        # Fallback to original approach if constraint-integrated fails
        name = self.generator.generate()
        name = name.replace("#", "")

        # Check constraints (same includes/excludes semantics as the sampler)
        if (min_length <= len(name) <= max_length and
            (not starts_with or name.startswith(starts_with)) and
            (not ends_with or name.endswith(ends_with)) and
            (not includes or meets_includes_constraint(name, includes)) and
            all(token not in name for token in parse_excludes_tokens(excludes)) and
            (not regex_pattern or re.match(regex_pattern, name))):
            return name

        return None
    
    def generate_names(self, n: int, min_length: int = 1, max_length: int = 20,
                      starts_with: str = "", ends_with: str = "", 
                      includes: str = "", excludes: str = "",
                      max_time_per_name: float = 0.02,
                      regex_pattern: Optional[str] = None) -> List[str]:
        """
        Generate multiple names that meet constraints within time limit.
        
        Args:
            n: Number of names to generate
            min_length: Minimum length of words
            max_length: Maximum length of words
            starts_with: Text words must start with
            ends_with: Text words must end with
            includes: Text words must include
            excludes: Text words must exclude
            max_time_per_name: Maximum time in seconds to spend per name
            regex_pattern: Optional regex pattern words must match
            
        Returns:
            List of names that meet constraints
        """
        # Bail out immediately on self-contradictory constraints instead of
        # burning the whole time budget on attempts that can never succeed
        constraints = GenerationConstraints(
            min_length=min_length, max_length=max_length,
            starts_with=starts_with, ends_with=ends_with,
            includes=includes, excludes=excludes, regex_pattern=regex_pattern
        )
        if not constraints.is_feasible():
            return []

        names = []
        start_time = time.time()
        max_total_time = max_time_per_name * n
        attempts = 0
        max_attempts_per_name = 1000

        while len(names) < n:
            name = self.generate_name(min_length, max_length, starts_with,
                                    ends_with, includes, excludes, regex_pattern)
            attempts += 1

            if name is not None:
                names.append(name)
                attempts = 0  # Reset attempts counter when we find a valid name

            # Safety checks to prevent unbounded loops: stop on total-time
            # budget or after too many consecutive failed attempts
            if (time.time() - start_time) > max_total_time:
                break
            if attempts > max_attempts_per_name:
                break

        return names
    
    def generate_name_with_components(self, components: List[str], min_length: int = 6, max_length: int = 12,
                                    starts_with: str = "", ends_with: str = "", 
                                    includes: str = "", excludes: str = "",
                                    component_order: Optional[List[int]] = None,
                                    component_separation: Tuple[int, int] = (0, 3),
                                    regex_pattern: Optional[str] = None) -> Optional[str]:
        """
        Generate a single name with component constraints.
        
        Args:
            components: List of required components (e.g., ["co", "mind"])
            min_length: Minimum word length
            max_length: Maximum word length
            starts_with: Required prefix
            ends_with: Required suffix
            includes: Required substring (applied as posterior filter)
            excludes: Forbidden substring
            component_order: Specific ordering of components (indices into components list)
            component_separation: Min/max characters between components
            regex_pattern: Optional regex pattern to match
            
        Returns:
            Generated name meeting constraints, or None if constraints impossible
        """
        name = self.generator.generate_with_components(
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
        
        if name is not None:
            # Final regex validation if provided
            if regex_pattern and not re.match(regex_pattern, name):
                return None
            return name
        
        return None
    
    def generate_names_with_components(self, components: List[str], n: int, 
                                     min_length: int = 6, max_length: int = 12,
                                     starts_with: str = "", ends_with: str = "", 
                                     includes: str = "", excludes: str = "",
                                     component_order: Optional[List[int]] = None,
                                     component_separation: Tuple[int, int] = (0, 3),
                                     max_time_per_name: float = 0.5,
                                     regex_pattern: Optional[str] = None) -> List[str]:
        """
        Generate multiple names with component constraints.
        
        Args:
            components: List of required components (e.g., ["co", "mind"])
            n: Number of names to generate
            min_length: Minimum word length
            max_length: Maximum word length
            starts_with: Required prefix
            ends_with: Required suffix
            includes: Required substring (applied as posterior filter)
            excludes: Forbidden substring
            component_order: Specific ordering of components (indices into components list)
            component_separation: Min/max characters between components
            max_time_per_name: Maximum time in seconds to spend per name
            regex_pattern: Optional regex pattern to match
            
        Returns:
            List of names meeting constraints
        """
        names = []
        start_time = time.time()
        max_total_time = max_time_per_name * n
        attempts = 0
        max_attempts_per_name = 1000

        while len(names) < n:
            name = self.generate_name_with_components(
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
            attempts += 1

            if name is not None:
                names.append(name)
                attempts = 0  # Reset attempts counter when we find a valid name

            # Safety checks to prevent unbounded loops: stop on total-time
            # budget or after too many consecutive failed attempts
            if (time.time() - start_time) > max_total_time:
                break
            if attempts > max_attempts_per_name:
                break

        return names