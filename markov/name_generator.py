import time
import re
from typing import List, Optional
from .generator import Generator


class NameGenerator:
    def __init__(self, data: List[str], order: int, prior: float, backoff: bool = False):
        """
        Create a procedural name generator.
        
        Args:
            data: Training data for the generator, an array of words
            order: Highest order of model to use - models 1 to order will be generated
            prior: The dirichlet prior/additive smoothing "randomness" factor
            backoff: Whether to fall back to lower order models when highest order model fails
        """
        self.generator = Generator(data, order, prior, backoff)
    
    def generate_name(self, min_length: int = 1, max_length: int = 20, 
                     starts_with: str = "", ends_with: str = "", 
                     includes: str = "", excludes: str = "",
                     regex_pattern: Optional[str] = None) -> Optional[str]:
        """
        Generate a single name within constraints.
        
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
        name = self.generator.generate()
        name = name.replace("#", "")
        
        # Check constraints
        if (min_length <= len(name) <= max_length and
            name.startswith(starts_with) and
            name.endswith(ends_with) and
            (not includes or includes in name) and
            (not excludes or excludes not in name) and
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
        names = []
        start_time = time.time()
        max_total_time = max_time_per_name * n
        
        while len(names) < n:
            name = self.generate_name(min_length, max_length, starts_with, 
                                    ends_with, includes, excludes, regex_pattern)
            if name is not None:
                names.append(name)
            
            # Safety check to prevent infinite loops - if we've spent too much time
            # and haven't found any valid names recently, break
            if (time.time() - start_time) > max_total_time:
                # If we haven't found any names at all, break to avoid infinite loop
                if len(names) == 0:
                    break
        
        return names