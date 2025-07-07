import random
from typing import List, Dict, Optional
from collections import defaultdict


class MarkovModel:
    def __init__(self, data: List[str], order: int, prior: float, alphabet: List[str]):
        assert alphabet is not None and data is not None
        assert len(alphabet) > 0 and len(data) > 0
        assert 0 <= prior <= 1
        
        self.order = order
        self.prior = prior
        self.alphabet = alphabet
        
        self.observations: Dict[str, List[str]] = defaultdict(list)
        self.chains: Dict[str, List[float]] = {}
        
        self._train(data)
        self._build_chains()
    
    def generate(self, context: str) -> Optional[str]:
        """Generate next letter given context"""
        chain = self.chains.get(context)
        if chain is None:
            return None
        
        return self.alphabet[self._select_index(chain)]
    
    def retrain(self, data: List[str]) -> None:
        """Retrain model on new data"""
        self.observations.clear()
        self._train(data)
        self._build_chains()
    
    def _train(self, data: List[str]) -> None:
        """Train the model on training data"""
        for word in data:
            # Add padding characters
            padded_word = "#" * self.order + word + "#"
            
            # Extract n-grams
            for i in range(len(padded_word) - self.order):
                key = padded_word[i:i + self.order]
                value = padded_word[i + self.order]
                self.observations[key].append(value)
    
    def _build_chains(self) -> None:
        """Build Markov chains from observations"""
        self.chains = {}
        
        for context in self.observations.keys():
            chain = []
            for prediction in self.alphabet:
                count = self._count_matches(self.observations[context], prediction)
                chain.append(self.prior + count)
            self.chains[context] = chain
    
    def _count_matches(self, arr: List[str], value: str) -> int:
        """Count occurrences of value in array"""
        return arr.count(value)
    
    def _select_index(self, chain: List[float]) -> int:
        """Select index using weighted random selection"""
        totals = []
        accumulator = 0.0
        
        for weight in chain:
            accumulator += weight
            totals.append(accumulator)
        
        rand = random.random() * accumulator
        for i, total in enumerate(totals):
            if rand < total:
                return i
        
        return 0