"""
Constraint-aware sampling system for Markov name generation.
Provides modular, extensible constraint handling integrated into the sampling process.
"""

import random
import math
from typing import List, Dict, Optional, Tuple, Callable
from dataclasses import dataclass
from .markov_model import MarkovModel


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
        self.starts_with = self.starts_with.lower()
        self.ends_with = self.ends_with.lower()
        self.includes = self.includes.lower()
        self.excludes = self.excludes.lower()


class ProbabilityModifier:
    """Utility functions for modifying probability distributions based on constraints"""
    
    @staticmethod
    def mask_forbidden_transitions(probs: List[float], alphabet: List[str], 
                                 current_word: str, excludes: str) -> List[float]:
        """
        Mask probabilities for characters that would create forbidden patterns.
        
        Args:
            probs: Original probability distribution
            alphabet: Character alphabet
            current_word: Word being generated so far
            excludes: Pattern to exclude
            
        Returns:
            Modified probability distribution with forbidden transitions masked
        """
        if not excludes:
            return probs.copy()
            
        modified_probs = probs.copy()
        
        for i, char in enumerate(alphabet):
            if char == "#":  # Skip termination character for this check
                continue
                
            # Create hypothetical next word state
            hypothetical_word = current_word + char
            
            # Check if this would create the forbidden pattern
            if ProbabilityModifier._would_create_forbidden_pattern(
                hypothetical_word, excludes, len(excludes)
            ):
                modified_probs[i] = 0.0
        
        # Renormalize probabilities
        total = sum(modified_probs)
        if total > 0:
            modified_probs = [p / total for p in modified_probs]
        else:
            # If all transitions forbidden, return original (will be handled upstream)
            modified_probs = probs.copy()
            
        return modified_probs
    
    @staticmethod
    def _would_create_forbidden_pattern(word: str, excludes: str, max_check_length: int) -> bool:
        """Check if adding a character would create a forbidden pattern"""
        # Check the last max_check_length characters for the forbidden pattern
        check_segment = word[-max_check_length:]
        return excludes in check_segment
    
    @staticmethod
    def bias_toward_termination(probs: List[float], alphabet: List[str], 
                              current_length: int, target_length: int, 
                              termination_bias: float = 2.0) -> List[float]:
        """
        Bias probabilities toward termination when approaching target length.
        
        Args:
            probs: Original probability distribution
            alphabet: Character alphabet  
            current_length: Current word length
            target_length: Target word length
            termination_bias: Multiplier for termination probability
            
        Returns:
            Modified probability distribution with termination bias
        """
        if current_length < target_length:
            return probs.copy()
            
        modified_probs = probs.copy()
        
        # Find termination character index
        try:
            term_idx = alphabet.index("#")
            modified_probs[term_idx] *= termination_bias
            
            # Renormalize
            total = sum(modified_probs)
            if total > 0:
                modified_probs = [p / total for p in modified_probs]
                
        except ValueError:
            pass  # No termination character found
            
        return modified_probs


class ConstraintHandlers:
    """Modular handlers for different constraint types"""
    
    @staticmethod
    def handle_starts_with(starts_with: str, order: int) -> str:
        """
        Initialize word with starts_with constraint.
        
        Args:
            starts_with: Required prefix
            order: Markov model order
            
        Returns:
            Initial word state with prefix applied
        """
        if not starts_with:
            return "#" * order
            
        if len(starts_with) >= order:
            return starts_with
        else:
            padding_needed = order - len(starts_with)
            return "#" * padding_needed + starts_with
    
    @staticmethod
    def handle_ends_with(word: str, ends_with: str, current_length: int,
                        target_length: int) -> Tuple[str, bool]:
        """
        Handle ends_with constraint by checking if we should apply ending.
        
        Args:
            word: Current word being generated
            ends_with: Required suffix
            current_length: Current word length (excluding padding)
            target_length: Target total length
            
        Returns:
            Tuple of (modified_word, should_terminate)
        """
        if not ends_with:
            return word, False
            
        # Check if we're at or near the right length to apply ending
        body_length = target_length - len(ends_with)
        
        if current_length >= body_length:
            # Apply the ending
            clean_word = word.replace("#", "")
            # Trim to exact body length if needed
            if len(clean_word) > body_length:
                clean_word = clean_word[:body_length]
            elif len(clean_word) < body_length:
                # If we're short, pad with a common character or return as-is
                pass
                
            return clean_word + ends_with, True
                
        return word, False
    
    @staticmethod
    def validate_constraints(constraints: GenerationConstraints) -> bool:
        """
        Validate that constraints are feasible.
        
        Args:
            constraints: Constraint configuration
            
        Returns:
            True if constraints are feasible, False otherwise
        """
        # Check basic length constraints
        if constraints.min_length > constraints.max_length:
            return False
            
        # Check prefix/suffix length constraints
        required_length = len(constraints.starts_with) + len(constraints.ends_with)
        if required_length > constraints.max_length:
            return False
            
        # Only reject if required length exceeds max_length
        # We can always generate words >= required_length by adding middle content
            
        return True


class ConstraintSampler:
    """
    Main constraint-aware sampler that coordinates all constraint handling.
    """
    
    def __init__(self, markov_model: MarkovModel):
        """Initialize with a Markov model"""
        self.model = markov_model
        self.prob_modifier = ProbabilityModifier()
        self.handlers = ConstraintHandlers()
    
    def generate_constrained_name(self, constraints: GenerationConstraints) -> Optional[str]:
        """
        Generate a name with integrated constraint handling.
        
        Args:
            constraints: All generation constraints
            
        Returns:
            Generated name meeting constraints, or None if impossible
        """
        if not self.handlers.validate_constraints(constraints):
            return None
            
        # 1. Initialize with starts_with constraint
        word = self.handlers.handle_starts_with(constraints.starts_with, self.model.order)
        
        # 2. Calculate target length range
        target_length = self._calculate_target_length(constraints)
        if target_length is None:
            return None
            
        # 3. Generate middle section with constraint awareness
        word = self._generate_middle_section(word, constraints, target_length)
        
        # 4. Handle ends_with constraint
        if constraints.ends_with:
            word, terminated = self.handlers.handle_ends_with(
                word, constraints.ends_with, 
                len(word.replace("#", "")), target_length
            )
            if terminated:
                final_word = word
            else:
                # Force termination with ending if we didn't naturally terminate
                clean_word = word.replace("#", "")
                body_length = target_length - len(constraints.ends_with)
                if len(clean_word) >= body_length:
                    if len(clean_word) > body_length:
                        clean_word = clean_word[:body_length]
                    final_word = clean_word + constraints.ends_with
                else:
                    final_word = word.replace("#", "") + constraints.ends_with
        else:
            # 5. Standard termination if no ends_with
            final_word = word.replace("#", "")
        
        # 6. Apply includes constraint as posterior filter with AND/OR logic
        if constraints.includes and not self._meets_includes_constraint(final_word, constraints.includes):
            return None
            
        return final_word if self._meets_length_constraints(final_word, constraints) else None
    
    def _calculate_target_length(self, constraints: GenerationConstraints) -> Optional[int]:
        """Calculate a valid target length given constraints"""
        min_body = constraints.min_length - len(constraints.starts_with) - len(constraints.ends_with)
        max_body = constraints.max_length - len(constraints.starts_with) - len(constraints.ends_with)
        
        min_body = max(0, min_body)
        max_body = max(0, max_body)
        
        if min_body > max_body:
            return None
            
        # For ends_with, we need precise length control
        if constraints.ends_with:
            body_length = random.randint(min_body, max_body)
            return len(constraints.starts_with) + body_length + len(constraints.ends_with)
        else:
            return random.randint(constraints.min_length, constraints.max_length)
    
    def _generate_middle_section(self, word: str, constraints: GenerationConstraints, 
                               target_length: int) -> str:
        """Generate the middle section of the word with constraint awareness"""
        max_iterations = 1000
        iteration = 0
        
        while iteration < max_iterations:
            current_clean_length = len(word.replace("#", ""))
            
            # Check if we should terminate based on length and ends_with
            if constraints.ends_with:
                body_target = target_length - len(constraints.ends_with)
                if current_clean_length >= body_target:
                    break
            elif current_clean_length >= target_length:
                # For non-ends_with constraints, allow natural termination
                break
            
            # Get context for next character prediction
            context = word[-self.model.order:]
            
            # Get base probabilities with proper backoff
            base_probs = None
            original_context = context
            
            # Try progressively shorter contexts until we find one that works
            while base_probs is None and len(context) > 0:
                base_probs = self.model.chains.get(context)
                if base_probs is None and len(context) > 1:
                    context = context[1:]
                else:
                    break
                    
            # If we still can't find anything, try single character contexts
            if base_probs is None and len(original_context) > 0:
                for i in range(len(original_context)):
                    single_char_context = original_context[i]
                    base_probs = self.model.chains.get(single_char_context)
                    if base_probs is not None:
                        break
                        
            if base_probs is None:
                break
                
            # Apply constraint modifications
            modified_probs = self._apply_constraint_modifications(
                base_probs, word, constraints, current_clean_length, target_length
            )
            
            # Check if all probabilities are zero (no valid transitions)
            if sum(modified_probs) <= 0:
                break
            
            # Sample next character
            next_char = self._sample_from_probabilities(modified_probs)
            if next_char is None:
                break
            elif next_char == "#":
                # Only break on termination if we're not forcing an ending
                if not constraints.ends_with or current_clean_length >= target_length - len(constraints.ends_with):
                    break
            else:
                word += next_char
            
            iteration += 1
        
        return word
    
    def _apply_constraint_modifications(self, base_probs: List[float], word: str,
                                     constraints: GenerationConstraints,
                                     current_length: int, target_length: int) -> List[float]:
        """Apply all relevant constraint modifications to probabilities"""
        modified_probs = base_probs.copy()
        
        # Apply excludes constraint
        if constraints.excludes:
            modified_probs = self.prob_modifier.mask_forbidden_transitions(
                modified_probs, self.model.alphabet, word, constraints.excludes
            )
        
        # Apply length-based termination bias
        if not constraints.ends_with:  # Don't bias termination if we have specific ending
            modified_probs = self.prob_modifier.bias_toward_termination(
                modified_probs, self.model.alphabet, current_length, target_length
            )
        
        return modified_probs
    
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
                return self.model.alphabet[i]
                
        return None
    
    def _meets_includes_constraint(self, word: str, includes_pattern: str) -> bool:
        """
        Check if word meets includes constraint with AND/OR logic.
        
        Format:
        - 'x,a' = must contain BOTH x AND a (comma = AND)
        - 'x;a' = must contain EITHER x OR a (semicolon = OR)  
        - 'x,a;b,c' = must contain (x AND a) OR (b AND c)
        
        Args:
            word: Generated word to check
            includes_pattern: Pattern string with AND/OR logic
            
        Returns:
            True if word meets the includes constraint
        """
        if not includes_pattern.strip():
            return True
            
        # Split by semicolon for OR groups
        or_groups = [group.strip() for group in includes_pattern.split(';')]
        
        for group in or_groups:
            # Split by comma for AND conditions within each group
            and_conditions = [condition.strip() for condition in group.split(',') if condition.strip()]
            
            # Check if all AND conditions in this group are met
            if and_conditions and all(condition in word for condition in and_conditions):
                return True
        
        return False
    
    def _meets_length_constraints(self, word: str, constraints: GenerationConstraints) -> bool:
        """Check if word meets length constraints"""
        return constraints.min_length <= len(word) <= constraints.max_length