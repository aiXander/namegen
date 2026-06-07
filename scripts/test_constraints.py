"""Correctness checks for the constraint sampler: every emitted name must
satisfy every constraint, infeasible combos must fail fast, and edge-case
parameters (temperature 0, order 1/5, no backoff) must not crash.

Usage:
    uv run scripts/test_constraints.py
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from markov.name_generator import NameGenerator
from markov.constraint_sampler import meets_includes_constraint
from markov_namegen import WORD_LISTS_DIR, load_word_list

SOURCES = ["roman_deities.txt", "tolkienesque_forenames.txt", "swedish_forenames.txt",
           "pokemon.txt", "websites.txt"]

failures = []


def check(label, condition, detail=""):
    status = "ok" if condition else "FAIL"
    print(f"  [{status}] {label}{(' — ' + detail) if detail and not condition else ''}")
    if not condition:
        failures.append(label)


def main():
    words = []
    for source in SOURCES:
        path = os.path.join(WORD_LISTS_DIR, source)
        if os.path.exists(path):
            words.extend(load_word_list(path))
    words = [w for w in words if w.isalpha()]
    print(f"Training on {len(words)} words\n")

    gen = NameGenerator(words, order=3, temperature=0.9, backoff=True)

    print("Constraint enforcement (1000 attempts each):")
    cases = [
        {"min_length": 5, "max_length": 8},
        {"starts_with": "br", "min_length": 4, "max_length": 10},
        {"ends_with": "ra", "min_length": 4, "max_length": 10},
        {"includes": "co", "min_length": 4, "max_length": 10},
        {"includes": "lu,na;vi", "min_length": 4, "max_length": 12},
        {"excludes": "an", "min_length": 4, "max_length": 10},
        # splice junction must not recreate the excluded substring
        {"excludes": "ra", "ends_with": "a", "min_length": 4, "max_length": 10},
        {"starts_with": "a", "ends_with": "on", "includes": "mi", "excludes": "th",
         "min_length": 5, "max_length": 12},
    ]
    for kwargs in cases:
        produced = []
        for _ in range(1000):
            name = gen.generate_name(**kwargs)
            if name:
                produced.append(name)
        bad = [n for n in produced if not (
            kwargs.get("min_length", 1) <= len(n) <= kwargs.get("max_length", 20)
            and n.startswith(kwargs.get("starts_with", ""))
            and n.endswith(kwargs.get("ends_with", ""))
            and (not kwargs.get("includes") or meets_includes_constraint(n, kwargs["includes"]))
            and (not kwargs.get("excludes") or kwargs["excludes"] not in n)
        )]
        check(f"{kwargs}", len(produced) > 0 and not bad,
              f"{len(produced)} produced, violations: {bad[:5]}")

    print("\nComponent mode (500 attempts each):")
    comp_cases = [
        {"components": ["co", "mind"], "min_length": 6, "max_length": 10},
        {"components": ["co", "mind"], "min_length": 6, "max_length": 6},  # exactly 'comind'/'mindco'
        {"components": ["lu", "na"], "min_length": 4, "max_length": 9, "ends_with": "a"},
        {"components": ["vi", "ra"], "min_length": 6, "max_length": 10,
         "component_separation": (1, 2), "excludes": "an"},
    ]
    for kwargs in comp_cases:
        produced = []
        for _ in range(500):
            name = gen.generate_name_with_components(**kwargs)
            if name:
                produced.append(name)
        bad = [n for n in produced if not (
            kwargs["min_length"] <= len(n) <= kwargs["max_length"]
            and all(c in n for c in kwargs["components"])
            and n.endswith(kwargs.get("ends_with", ""))
            and (not kwargs.get("excludes") or kwargs["excludes"] not in n)
        )]
        check(f"{kwargs}", len(produced) > 0 and not bad,
              f"{len(produced)} produced, violations: {bad[:5]}")

    print("\nInfeasible constraints fail fast (and return empty, not hang):")
    infeasible = [
        {"min_length": 10, "max_length": 5},
        {"starts_with": "abcdef", "ends_with": "ghijkl", "max_length": 8},
        {"excludes": "a", "ends_with": "a"},
        {"includes": "xx", "excludes": "x"},
    ]
    for kwargs in infeasible:
        start = time.perf_counter()
        names = gen.generate_names(n=10, max_time_per_name=2.0, **kwargs)
        elapsed = time.perf_counter() - start
        check(f"{kwargs}", names == [] and elapsed < 0.5, f"{len(names)} names in {elapsed:.2f}s")

    print("\nEdge-case parameters:")
    for label, order, temp, backoff in [
        ("temperature=0", 3, 0, True),
        ("temperature=0.01", 3, 0.01, True),
        ("temperature=3", 3, 3.0, True),
        ("order=1", 1, 0.9, True),
        ("order=5", 5, 0.9, True),
        ("no backoff", 3, 0.9, False),
    ]:
        try:
            g = NameGenerator(words, order=order, temperature=temp, backoff=backoff)
            names = g.generate_names(n=10, min_length=4, max_length=10, max_time_per_name=0.5)
            check(label, len(names) > 0, f"got {len(names)} names")
        except Exception as e:
            check(label, False, f"{type(e).__name__}: {e}")

    print()
    if failures:
        print(f"{len(failures)} FAILURES")
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()
