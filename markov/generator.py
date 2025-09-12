import random
from typing import List, Optional
from .markov_model import MarkovModel
from .constraint_sampler import ConstraintSampler, GenerationConstraints


class Generator:
    def __init__(self, data: List[str], order: int, temperature: float, backoff: bool = False):
        assert data is not None
        assert order >= 1
        assert temperature > 0
        
        self.order = order
        self.temperature = temperature
        self.backoff = backoff
        
        # Build alphabet from training data
        letters = set()
        for word in data:
            for char in word:
                letters.add(char)
        
        # Sort alphabet and add padding character
        domain = sorted(list(letters))
        domain.insert(0, "#")
        
        # Create models
        self.models = []
        if self.backoff:
            # Create models from highest to lowest order
            for i in range(order):
                model_order = order - i
                self.models.append(MarkovModel(data.copy(), model_order, temperature, domain))
        else:
            # Create single model of specified order
            self.models.append(MarkovModel(data.copy(), order, temperature, domain))
        
        # Initialize constraint sampler with primary model
        self.constraint_sampler = ConstraintSampler(self.models[0])
    
    def generate(self) -> str:
        """Generate a word"""
        word = "#" * self.order
        
        letter = self._get_letter(word)
        while letter != "#" and letter is not None:
            if letter is not None:
                word += letter
            letter = self._get_letter(word)
        
        return word
    
    def _get_letter(self, word: str) -> Optional[str]:
        """Generate next letter in word"""
        assert word is not None
        assert len(word) > 0
        
        letter = None
        context = word[-self.order:]
        
        for model in self.models:
            letter = model.generate(context)
            if letter is None or letter == "#":
                # Remove first character from context for next model
                context = context[1:] if len(context) > 1 else ""
            else:
                break
        
        return letter
    
    def generate_with_constraints(self, min_length: int = 1, max_length: int = 20,
                                starts_with: str = "", ends_with: str = "",
                                includes: str = "", excludes: str = "",
                                regex_pattern: Optional[str] = None) -> Optional[str]:
        """
        Generate a word using constraint-integrated sampling for improved efficiency.
        
        Args:
            min_length: Minimum word length
            max_length: Maximum word length  
            starts_with: Required prefix
            ends_with: Required suffix
            includes: Required substring (applied as posterior filter)
            excludes: Forbidden substring
            regex_pattern: Optional regex pattern to match
            
        Returns:
            Generated word meeting constraints, or None if constraints impossible
        """
        constraints = GenerationConstraints(
            min_length=min_length,
            max_length=max_length,
            starts_with=starts_with,
            ends_with=ends_with,
            includes=includes,
            excludes=excludes,
            regex_pattern=regex_pattern
        )
        
        return self.constraint_sampler.generate_constrained_name(constraints)