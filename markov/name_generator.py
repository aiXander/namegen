import time
import re
from typing import List, Optional, Tuple
from .generator import Generator


class NameGenerator:
    def __init__(self, data: List[str], order: int, temperature: float, backoff: bool = False):
        """
        Create a procedural name generator.
        
        Args:
            data: Training data for the generator, an array of words
            order: Highest order of model to use - models 1 to order will be generated
            temperature: Temperature for sampling (0=deterministic, 1=training distribution, >1=more random)
            backoff: Whether to fall back to lower order models when highest order model fails
        """
        self.generator = Generator(data, order, temperature, backoff)
    
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
        
        # Check constraints
        if (min_length <= len(name) <= max_length and
            (not starts_with or name.startswith(starts_with)) and
            (not ends_with or name.endswith(ends_with)) and
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
        attempts = 0
        max_attempts_per_name = 1000
        
        while len(names) < n:
            name = self.generate_name(min_length, max_length, starts_with, 
                                    ends_with, includes, excludes, regex_pattern)
            attempts += 1
            
            if name is not None:
                names.append(name)
                attempts = 0  # Reset attempts counter when we find a valid name
            
            # Safety check to prevent infinite loops - break if we've tried too many times
            # or spent too much total time
            current_time = time.time()
            if (current_time - start_time) > max_total_time:
                # If we haven't found enough names but have some, return what we have
                break
            
            # If we've tried many times without success and have no names, give more time
            if attempts > max_attempts_per_name and len(names) == 0:
                # Increase max_total_time if we haven't found any names yet
                max_total_time *= 2
                attempts = 0
            elif attempts > max_attempts_per_name:
                # If we have some names but struggling to find more, stop trying
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
            
            # Safety check to prevent infinite loops
            current_time = time.time()
            if (current_time - start_time) > max_total_time:
                break
            
            if attempts > max_attempts_per_name:
                if len(names) == 0:
                    # Increase max_total_time if we haven't found any names yet
                    max_total_time *= 2
                    attempts = 0
                else:
                    # If we have some names but struggling to find more, stop trying
                    break
        
        return names