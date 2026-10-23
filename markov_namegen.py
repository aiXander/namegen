import os
import json
import csv
import yaml
import random
from typing import Dict, Iterable, List, Optional, Tuple
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


def nearest_training_word(name: str, training_words: Iterable[str]) -> Optional[Tuple[str, int]]:
    """(closest training word, Levenshtein distance) — the name's provenance.
    Multi-word names are matched on their longest word."""
    probe = max(name.split(), key=len) if " " in name else name
    match = _rf_process.extractOne(probe, training_words, scorer=Levenshtein.distance)
    return (match[0], int(match[1])) if match else None


# How word lists are mixed into one training set:
#   natural  — every word counts once, so big lists dominate the statistics
#   balanced — every selected list contributes the same total weight
#   rating   — balanced, then scaled by the list's star rating (unrated = 3)
WEIGHTING_MODES = ("natural", "balanced", "rating")
UNRATED_LIST_STARS = 3


def source_weights(sizes: Dict[str, int], mode: str,
                   ratings: Optional[Dict[str, int]] = None) -> Dict[str, float]:
    """Per-word weight for each source so the mix follows `mode`. Weights are
    normalised so the total mass equals the natural word count — temperature
    and backoff then behave the same in every mode."""
    sizes = {source: n for source, n in sizes.items() if n > 0}
    if mode not in ("balanced", "rating") or not sizes:
        return {source: 1.0 for source in sizes}
    ratings = ratings or {}
    share = {source: float(ratings.get(source) or UNRATED_LIST_STARS) if mode == "rating" else 1.0
             for source in sizes}
    total_words = sum(sizes.values())
    total_share = sum(share.values())
    return {source: total_words * share[source] / total_share / sizes[source] for source in sizes}


class MarkovNameGenerator:
    def __init__(self, config_path: str = "config.yaml", config: Optional[dict] = None):
        """Train a generator from a config dict, or from the YAML at config_path."""
        if config is None:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
        self.config = config
        self.build()

    def build(self) -> None:
        """(Re)load the training data and train the model from self.config."""
        self.training_words, weights = self._load_training_data()
        model_config = self.config['model']
        self.generator = NameGenerator(
            data=self.training_words,
            order=model_config['order'],
            temperature=model_config['temperature'],
            backoff=model_config['backoff'],
            weights=weights
        )

    def _load_training_data(self) -> Tuple[List[str], List[float]]:
        """Load training words from the configured sources, plus a per-word
        weight implementing `training_data.weighting`."""
        training_config = self.config['training_data']
        filter_special_chars = training_config.get('filter_special_chars', True)

        per_source: Dict[str, List[str]] = {}
        for source in training_config['sources']:
            filepath = os.path.join(WORD_LISTS_DIR, source)
            if not os.path.exists(filepath):
                print(f"Warning: Word list {source} not found")
                continue
            words = load_word_list(filepath)
            if filter_special_chars:
                words = [word for word in words if word.isalpha()]
            per_source[source] = words

        weight_of = source_weights({source: len(words) for source, words in per_source.items()},
                                   training_config.get('weighting', 'natural'),
                                   self.config.get('word_list_ratings'))
        words = [word for source_words in per_source.values() for word in source_words]
        weights = [weight_of[source] for source, source_words in per_source.items() for _ in source_words]
        return words, weights
    
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