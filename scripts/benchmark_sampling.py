"""Benchmark the constraint sampler across representative settings combos.

Measures per-attempt success rate, unique-name yield, and wall time for each
combo so sampler changes can be compared before/after.

Usage:
    uv run scripts/benchmark_sampling.py [--attempts 2000]
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml

from markov.name_generator import NameGenerator
from markov_namegen import WORD_LISTS_DIR, load_word_list


def load_training_words():
    with open("config.yaml") as f:
        config = yaml.safe_load(f)
    words = []
    for source in config["training_data"]["sources"]:
        path = os.path.join(WORD_LISTS_DIR, source)
        if os.path.exists(path):
            words.extend(load_word_list(path))
    return [w for w in words if w.isalpha()]


# (label, generator kwargs, generate_name kwargs)
CASES = [
    ("plain 4-10", {}, {}),
    ("ends_with=a", {}, {"ends_with": "a"}),
    ("includes=co", {}, {"includes": "co"}),
    ("includes=co + ends_with=a (GUI config)", {}, {"includes": "co", "ends_with": "a"}),
    ("starts_with=br + ends_with=a", {}, {"starts_with": "br", "ends_with": "a"}),
    ("excludes=an", {}, {"excludes": "an"}),
    ("includes OR: co;mi + excludes=an", {}, {"includes": "co;mi", "excludes": "an"}),
    ("ends_with=a, no backoff", {"backoff": False}, {"ends_with": "a"}),
    ("ends_with=ra + min8", {}, {"ends_with": "ra", "min_length": 8}),
]

COMPONENT_CASES = [
    ("components [co,mind] 6-10", {"components": ["co", "mind"], "min_length": 6, "max_length": 10}),
    ("components [lu,na] 4-8", {"components": ["lu", "na"], "min_length": 4, "max_length": 8}),
    # Tight fit: 'comind' itself is the only 6-char arrangement
    ("components [co,mind] 6-7 (tight)", {"components": ["co", "mind"], "min_length": 6, "max_length": 7}),
    ("components [vi,ra] + ends_with=a", {"components": ["vi", "ra"], "min_length": 5, "max_length": 9,
                                          "ends_with": "a"}),
]


def run_case(gen, label, kwargs, attempts, component_mode=False):
    names = set()
    successes = 0
    start = time.perf_counter()
    for _ in range(attempts):
        if component_mode:
            name = gen.generate_name_with_components(**kwargs)
        else:
            name = gen.generate_name(min_length=kwargs.get("min_length", 4),
                                     max_length=kwargs.get("max_length", 10),
                                     starts_with=kwargs.get("starts_with", ""),
                                     ends_with=kwargs.get("ends_with", ""),
                                     includes=kwargs.get("includes", ""),
                                     excludes=kwargs.get("excludes", ""))
        if name:
            successes += 1
            names.add(name)
    elapsed = time.perf_counter() - start
    rate = successes / attempts * 100
    print(f"{label:45s} success {rate:5.1f}%  unique {len(names):5d}  "
          f"{attempts / elapsed:8.0f} att/s  sample: {sorted(names)[:5]}")
    return names


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempts", type=int, default=2000)
    args = parser.parse_args()

    words = load_training_words()
    print(f"Training on {len(words)} words from {WORD_LISTS_DIR}/\n")

    generators = {}

    def get_gen(order=3, temperature=0.9, backoff=True):
        key = (order, temperature, backoff)
        if key not in generators:
            generators[key] = NameGenerator(words, order=order, temperature=temperature, backoff=backoff)
        return generators[key]

    for label, gen_kwargs, name_kwargs in CASES:
        gen = get_gen(**gen_kwargs)
        run_case(gen, label, dict(name_kwargs), args.attempts)

    print()
    for label, kwargs in COMPONENT_CASES:
        gen = get_gen()
        run_case(gen, label, dict(kwargs), max(200, args.attempts // 10), component_mode=True)

    # Edge-case temperatures: 0 is documented as deterministic argmax, and
    # very low temperatures must not overflow during chain building.
    print()
    for temp in (0, 0.01):
        try:
            NameGenerator(words[:500], order=3, temperature=temp, backoff=True)
            print(f"temperature={temp}: OK")
        except Exception as e:
            print(f"temperature={temp}: FAILS ({type(e).__name__}: {e})")


if __name__ == "__main__":
    main()
