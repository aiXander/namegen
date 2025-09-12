import random
import math
from typing import List, Dict, Optional
from collections import defaultdict

class MarkovModel:
    def __init__(self, data: List[str], order: int, temperature: float, alphabet: List[str]):
        assert alphabet is not None and data is not None
        assert len(alphabet) > 0 and len(data) > 0
        assert temperature > 0, "Temperature must be positive"
        
        self.order = order
        self.temperature = temperature
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
        
        index = self._select_index(chain)
        letter = self.alphabet[index]
        return letter
    
    def retrain(self, data: List[str]) -> None:
        """Retrain model on new data"""
        self.observations.clear()
        self._train(data)
        self._build_chains()
    
    def _train(self, data: List[str]) -> None:
        """Train the model on training data"""
        print(f"🧠 Training Markov model (order={self.order}, temp={self.temperature:.2f}) on {len(data)} words")
        
        for word in data:
            # Add padding characters
            padded_word = "#" * self.order + word + "#"
            
            # Extract n-grams
            for i in range(len(padded_word) - self.order):
                key = padded_word[i:i + self.order]
                value = padded_word[i + self.order]
                self.observations[key].append(value)
                
        print(f"📊 Extracted {len(self.observations)} unique n-gram contexts from training data")
    
    def _build_chains(self) -> None:
        """Build Markov chains from observations with temperature scaling"""
        print(f"🔗 Building Markov chains for {len(self.observations)} contexts...")
        self.chains = {}
        
        for context in self.observations.keys():
            raw_counts = []
            total_count = len(self.observations[context])
            
            # Get raw counts for each character
            for prediction in self.alphabet:
                count = self._count_matches(self.observations[context], prediction)
                raw_counts.append(count)
            
            # Handle temperature scaling
            if total_count == 0:
                # No observations for this context, use uniform distribution
                chain = [1.0 / len(self.alphabet)] * len(self.alphabet)
            else:
                if self.temperature == 0:
                    # Temperature 0: always pick most likely (argmax)
                    chain = [0.0] * len(self.alphabet)
                    max_idx = raw_counts.index(max(raw_counts))
                    chain[max_idx] = 1.0
                else:
                    # Convert counts to log probabilities and apply temperature
                    log_probs = []
                    for count in raw_counts:
                        if count == 0:
                            # Add small epsilon to avoid log(0)
                            log_prob = math.log(1e-10)
                        else:
                            log_prob = math.log(count / total_count)
                        log_probs.append(log_prob / self.temperature)
                    
                    # Convert back to probabilities using softmax
                    max_log_prob = max(log_probs)
                    exp_log_probs = [math.exp(lp - max_log_prob) for lp in log_probs]
                    total_exp = sum(exp_log_probs)
                    chain = [exp_prob / total_exp for exp_prob in exp_log_probs]
                    
            
            self.chains[context] = chain
            
        print(f"✅ Built {len(self.chains)} Markov chains with alphabet size {len(self.alphabet)}")
    
    def _count_matches(self, arr: List[str], value: str) -> int:
        """Count occurrences of value in array"""
        return arr.count(value)
    
    def _select_index(self, chain: List[float]) -> int:
        """Select index using weighted random selection from probability distribution"""
        totals = []
        accumulator = 0.0
        
        for prob in chain:
            accumulator += prob
            totals.append(accumulator)
        
        # Normalize in case of floating point errors
        if accumulator > 0:
            rand = random.random() * accumulator
            for i, total in enumerate(totals):
                if rand < total:
                    return i
        
        return 0