"""Checks for the scoring side: source weighting, naturalness calibration and
the judge panel's aggregation (no network — the LLM call is stubbed with
canned responses in the shapes real models return).

Usage:
    uv run scripts/test_scoring.py
"""

import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from markov.markov_model import MarkovModel
from markov.name_generator import NameGenerator
from markov_namegen import WORD_LISTS_DIR, load_word_list, source_weights
from ai import judge as judge_module
from ai.judge import NameJudge, select_examples

failures = []


def check(label, condition, detail=""):
    status = "ok" if condition else "FAIL"
    print(f"  [{status}] {label}{(' — ' + str(detail)) if detail and not condition else ''}")
    if not condition:
        failures.append(label)


def test_source_weights():
    print("Source weighting:")
    sizes = {"big.txt": 1000, "small.txt": 10}
    for mode in ("balanced", "rating"):
        w = source_weights(sizes, mode, {"big.txt": 1, "small.txt": 4})
        mass = {s: w[s] * n for s, n in sizes.items()}
        check(f"{mode}: total mass equals the natural word count",
              abs(sum(mass.values()) - 1010) < 1e-6, mass)
    w = source_weights(sizes, "balanced")
    check("balanced: each list contributes equally", abs(w["big.txt"] * 1000 - w["small.txt"] * 10) < 1e-6)
    w = source_weights(sizes, "rating", {"big.txt": 1, "small.txt": 4})
    check("rating: mass is proportional to stars", abs(w["small.txt"] * 10 / (w["big.txt"] * 1000) - 4) < 1e-6)
    w = source_weights({"a.txt": 5, "b.txt": 5}, "rating", {"a.txt": 0})
    check("rating: unrated lists count as 3 stars", abs(w["a.txt"] - w["b.txt"]) < 1e-6)

    # The weights must actually move the learned statistics: 'q' follows the
    # context 'a' in the small list only.
    data = ["ab"] * 1000 + ["aq"] * 10
    alphabet = ["#", "a", "b", "q"]
    natural = MarkovModel(data, 1, 1.0, alphabet)
    weights = [w for size, word_w in ((1000, 1 / 1000), (10, 1 / 10)) for w in [word_w] * size]
    balanced = MarkovModel(data, 1, 1.0, alphabet, weights)
    check("weighted training reshapes transition probabilities",
          natural.probability("a", "q") < 0.02 and abs(balanced.probability("a", "q") - 0.5) < 1e-9,
          (natural.probability("a", "q"), balanced.probability("a", "q")))


def test_naturalness():
    print("Naturalness calibration:")
    words = []
    for source in ["roman_deities.txt", "tolkienesque_forenames.txt", "swedish_forenames.txt", "pokemon.txt"]:
        words.extend(load_word_list(os.path.join(WORD_LISTS_DIR, source)))
    words = [w for w in words if w.isalpha()]
    random.seed(1)
    gen = NameGenerator(words, order=3, temperature=1.0, backoff=True)
    names = [n for n in (gen.generate_name(4, 10) for _ in range(400)) if n and n not in set(words)]
    scores = [gen.naturalness(n) for n in names]
    median = statistics.median(scores)
    check("typical novel samples land mid-scale (not all 0 or 100)", 25 <= median <= 75, median)
    check("a garbled string scores 0", gen.naturalness("xqzvtkp") == 0, gen.naturalness("xqzvtkp"))
    check("short forced fragments don't sink multi-word names",
          gen.naturalness("co " + names[0]) == gen.naturalness(names[0]))


def test_judge_panel():
    print("Judge panel (stubbed LLM):")
    names = ["aurel", "mivo", "kesta", "pondro"]
    # Judge A uses the requested shape but never returns 'pondro'; judge B
    # answers in the loose {name: score} shape and also drops 'pondro' and 'kesta'.
    canned = {
        "a/judge": lambda chunk: {"names": [
            {"name": n.upper() if n == "aurel" else n, "score": 8, "sound": 7, "fit": 9, "distinct": 6,
             "note": f"note {n}", "flag": "brand" if n == "mivo" else ""}
            for n in chunk if n != "pondro"]},
        "b/judge": lambda chunk: {n: 4 for n in chunk if n in ("aurel", "mivo")},
    }

    async def fake_batch(self, prompts, model, **kwargs):
        if kwargs.get("progress_callback"):
            kwargs["progress_callback"](len(prompts), len(prompts))
        return [canned[model]([line for line in p.split("\n") if line in names]) for p in prompts]

    original = judge_module.LLMWrapper.batch_json_complete
    judge_module.LLMWrapper.batch_json_complete = fake_batch
    try:
        verdicts, _ = NameJudge(models=["a/judge", "b/judge"], chunk_size=2).judge(names, "BRIEF")
    finally:
        judge_module.LLMWrapper.batch_json_complete = original
    by_name = {v["name"]: v for v in verdicts}

    check("verdicts come back in input order", [v["name"] for v in verdicts] == names)
    check("score is the mean over judges (case-insensitive name match)", by_name["aurel"]["score"] == 6.0,
          by_name["aurel"]["score"])
    check("a name one judge skipped uses the other judge only", by_name["kesta"]["score"] == 8.0,
          by_name["kesta"])
    check("a name no judge returned is unscored, never a silent 0", by_name["pondro"]["score"] is None,
          by_name["pondro"]["score"])
    check("flags and notes survive aggregation",
          by_name["mivo"]["flag"] == "brand" and by_name["mivo"]["note"] == "note mivo", by_name["mivo"])


def test_examples():
    print("Taste examples:")
    ratings = {f"n{i}": 1 + i % 5 for i in range(200)}
    examples = select_examples(ratings, exclude=["n0", "n1"], limit=40)
    check("names being judged are never shown as examples", not {"n0", "n1"} & {n for n, _ in examples})
    check("examples span every star level (dislikes included)", {s for _, s in examples} == {1, 2, 3, 4, 5})
    check("example count respects the limit", len(examples) <= 40, len(examples))


def main():
    test_source_weights()
    test_naturalness()
    test_judge_panel()
    test_examples()
    print()
    if failures:
        print(f"{len(failures)} check(s) failed: {failures}")
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()
