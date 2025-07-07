import random
from typing import List, Optional
from markov_model import MarkovModel


class Generator:
    def __init__(self, data: List[str], order: int, prior: float, backoff: bool = False):
        assert data is not None
        assert order >= 1
        assert prior >= 0
        
        self.order = order
        self.prior = prior
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
                self.models.append(MarkovModel(data.copy(), model_order, prior, domain))
        else:
            # Create single model of specified order
            self.models.append(MarkovModel(data.copy(), order, prior, domain))
    
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