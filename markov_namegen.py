import os
import json
import csv
import yaml
import random
from typing import Iterable, List
from rapidfuzz import process as _rf_process
from rapidfuzz.distance import Levenshtein
from markov.name_generator import NameGenerator

# Cleaned dataset (produced by scripts/clean_word_lists.py) is preferred;
# fall back to the raw originals if it hasn't been generated yet.
WORD_LISTS_DIR = "word_lists_clean" if os.path.isdir("word_lists_clean") else "word_lists"


def load_word_list(filepath: str) -> List[str]:
    """Load words from a text file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return [line.strip().lower() for line in f if line.strip()]


def edit_distance(s1: str, s2: str) -> int:
    """Calculate edit distance between two strings"""
    return Levenshtein.distance(s1, s2)


def too_close_to_training(name: str, training_words: Iterable[str], min_distance: int) -> bool:
    """True if any training word is within edit distance < min_distance of `name`.

    Uses rapidfuzz's C++ Levenshtein with a score cutoff (banded DP + early
    abort per pair). The pure-Python DP scan over the full training set was
    ~200ms per candidate on ~43k words — the dominant cost of generation,
    dwarfing the Markov sampling itself (~0.06ms per attempt).
    """
    if min_distance <= 0:
        return False
    return _rf_process.extractOne(
        name, training_words,
        scorer=Levenshtein.distance,
        score_cutoff=min_distance - 1,
    ) is not None


class MarkovNameGenerator:
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize the generator with configuration"""
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Load training data
        self.training_words = self._load_training_data()
        
        # Create name generator
        model_config = self.config['model']
        self.generator = NameGenerator(
            data=self.training_words,
            order=model_config['order'],
            temperature=model_config['temperature'],
            backoff=model_config['backoff']
        )
    
    def _load_training_data(self) -> List[str]:
        """Load training data from specified sources"""
        words = []
        sources = self.config['training_data']['sources']
        filter_special_chars = self.config['training_data'].get('filter_special_chars', True)
        
        for source in sources:
            filepath = os.path.join(WORD_LISTS_DIR, source)
            if os.path.exists(filepath):
                words.extend(load_word_list(filepath))
            else:
                print(f"Warning: Word list {source} not found")
        
        # Filter out words with special characters if enabled
        if filter_special_chars:
            words = [word for word in words if word.isalpha()]
        
        # Ensure all training data is lowercase
        words = [word.lower() for word in words]
        
        return words
    
    def generate_names(self) -> List[str]:
        """Generate names according to configuration"""
        gen_config = self.config.get('generation', {})
        
        # Check if components are specified
        components = gen_config.get('components', [])
        
        if components:
            # Use multi-component generation
            names = self.generator.generate_names_with_components(
                components=components,
                n=gen_config.get('n_words', 20),
                min_length=gen_config.get('min_length', 6),
                max_length=gen_config.get('max_length', 12),
                starts_with=gen_config.get('starts_with', ''),
                ends_with=gen_config.get('ends_with', ''),
                includes=gen_config.get('includes', ''),
                excludes=gen_config.get('excludes', ''),
                component_order=gen_config.get('component_order'),
                component_separation=tuple(gen_config.get('component_separation', [0, 3])),
                max_time_per_name=gen_config.get('max_time_per_name', 1.0),
                regex_pattern=gen_config.get('regex_pattern') if gen_config.get('regex_pattern') else None
            )
        else:
            # Use standard generation
            names = self.generator.generate_names(
                n=gen_config.get('n_words', 20),
                min_length=gen_config.get('min_length', 4),
                max_length=gen_config.get('max_length', 12),
                starts_with=gen_config.get('starts_with', ''),
                ends_with=gen_config.get('ends_with', ''),
                includes=gen_config.get('includes', ''),
                excludes=gen_config.get('excludes', ''),
                max_time_per_name=gen_config.get('max_time_per_name', 1.0),
                regex_pattern=gen_config.get('regex_pattern') if gen_config.get('regex_pattern') else None
            )
        
        # Apply filtering
        names = self._filter_names(names)
        
        # Sort names
        names = self._sort_names(names)
        
        return names
    
    def _filter_names(self, names: List[str]) -> List[str]:
        """Apply filtering criteria to generated names"""
        filter_config = self.config.get('filtering', {})
        filtered_names = names.copy()
        
        # Remove duplicates
        if filter_config.get('remove_duplicates', True):
            filtered_names = list(set(filtered_names))
        
        # Remove names identical to training data
        if filter_config.get('exclude_training_words', True):
            training_set = set(self.training_words)
            filtered_names = [name for name in filtered_names if name not in training_set]
        
        # Remove names too similar to training data
        min_distance = filter_config.get('min_edit_distance', 0)
        if min_distance > 0:
            unique_training = list(set(self.training_words))
            filtered_names = [
                name for name in filtered_names
                if not too_close_to_training(name, unique_training, min_distance)
            ]
        
        return filtered_names
    
    def _sort_names(self, names: List[str]) -> List[str]:
        """Sort names according to configuration"""
        output_config = self.config.get('output', {})
        sort_by = output_config.get('sort_by', 'random')
        ascending = output_config.get('sort_ascending', True)
        
        if sort_by == "length":
            names.sort(key=len, reverse=not ascending)
        elif sort_by == "alphabetical":
            names.sort(reverse=not ascending)
        elif sort_by == "random":
            random.shuffle(names)
        
        return names
    
    def save_names(self, names: List[str]) -> None:
        """Save names to file according to configuration"""
        output_config = self.config['output']
        
        if not output_config['save_to_file']:
            return
        
        filename = output_config['output_file']
        format_type = output_config['format']
        
        if format_type == "json":
            with open(filename, 'w') as f:
                json.dump(names, f, indent=2)
        elif format_type == "csv":
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["name"])
                for name in names:
                    writer.writerow([name])
        else:  # list format
            with open(filename, 'w') as f:
                for name in names:
                    f.write(name + "\n")
    
    def run(self) -> List[str]:
        """Main method to generate and optionally save names"""
        names = self.generate_names()
        
        if self.config['output']['save_to_file']:
            self.save_names(names)
        
        return names


def main():
    """Main function to run the name generator"""
    generator = MarkovNameGenerator()
    names = generator.run()
    
    print(f"Generated {len(names)} names:")
    for i, name in enumerate(names, 1):
        print(f"{i:2d}. {name}")


if __name__ == "__main__":
    main()