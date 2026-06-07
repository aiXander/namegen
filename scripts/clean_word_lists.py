#!/usr/bin/env python3
"""Cleanup pass over word_lists/ — fixes the statistical problems that poison the Markov models.

Problems fixed, per entry:
  1. Unicode noise      → NFKD-normalize, strip diacritics (münchen → munchen) instead of dropping the word.
  2. Multi-word entries → split on spaces/hyphens/underscores into component tokens (each is valid training data).
  3. Glued compounds    → segment long concatenations with wordninja ("alabamaslammer" → alabama, slammer);
                          the cross-boundary n-grams of glued entries are linguistic garbage.
  4. Punctuation        → strip apostrophes/periods/digits-only junk.
  5. Duplicates         → dedup per file (duplicates double-weight transitions for no reason).
  6. Degenerate tokens  → drop tokens shorter than MIN_TOKEN_LEN.

Originals are never touched: cleaned lists are written to word_lists_clean/.

Usage:
    uv run scripts/clean_word_lists.py [--src word_lists] [--dst word_lists_clean] [--verbose]
"""

import argparse
import os
import re
import sys
import unicodedata

import wordninja

MIN_TOKEN_LEN = 3
# Only attempt wordninja segmentation on words at least this long — short words
# are almost never glued compounds, and segmenting them risks false splits.
SEGMENT_MIN_LEN = 9
# Accept a wordninja split only if every part is at least this long; unknown words
# tend to shatter into 1-2 char fragments, which signals "not actually a compound".
SEGMENT_MIN_PART_LEN = 3

NON_ALPHA = re.compile(r"[^a-z]")


def strip_diacritics(text: str) -> str:
    """münchen → munchen, café → cafe"""
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def segment_glued(token: str) -> list:
    """Try to split a glued compound into real words. Returns [token] if it doesn't look like one."""
    if len(token) < SEGMENT_MIN_LEN:
        return [token]
    parts = wordninja.split(token)
    if len(parts) >= 2 and all(len(p) >= SEGMENT_MIN_PART_LEN for p in parts):
        return parts
    return [token]


def clean_entry(line: str) -> list:
    """Turn one raw line into zero or more clean lowercase alpha tokens."""
    text = strip_diacritics(line.strip().lower())
    # apostrophes/periods join their neighbours (o'brien → obrien, st. → st)
    text = re.sub(r"[''`.]", "", text)
    tokens = []
    for raw in re.split(r"[\s\-_/,&+()]+", text):
        token = NON_ALPHA.sub("", raw)
        if not token:
            continue
        tokens.extend(segment_glued(token))
    return [t for t in tokens if len(t) >= MIN_TOKEN_LEN]


def clean_file(src_path: str, dst_path: str, verbose: bool = False) -> dict:
    with open(src_path, "r", encoding="utf-8") as f:
        raw_lines = [line.strip() for line in f if line.strip()]

    seen = set()
    cleaned = []
    n_split = 0
    for line in raw_lines:
        tokens = clean_entry(line)
        if len(tokens) > 1:
            n_split += 1
            if verbose:
                print(f"    split: {line!r} -> {tokens}")
        for token in tokens:
            if token not in seen:
                seen.add(token)
                cleaned.append(token)

    cleaned.sort()
    with open(dst_path, "w", encoding="utf-8") as f:
        f.write("\n".join(cleaned) + "\n")

    return {
        "raw": len(raw_lines),
        "clean": len(cleaned),
        "dups_removed": len(raw_lines) - len(set(raw_lines)),
        "split": n_split,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--src", default="word_lists")
    parser.add_argument("--dst", default="word_lists_clean")
    parser.add_argument("--verbose", action="store_true", help="print every compound split")
    args = parser.parse_args()

    if not os.path.isdir(args.src):
        sys.exit(f"Source directory not found: {args.src}")
    os.makedirs(args.dst, exist_ok=True)

    files = sorted(f for f in os.listdir(args.src) if f.endswith(".txt"))
    totals = {"raw": 0, "clean": 0, "dups_removed": 0, "split": 0}
    print(f"Cleaning {len(files)} word lists: {args.src}/ -> {args.dst}/\n")
    print(f"{'file':<48} {'raw':>6} {'clean':>6} {'dups':>5} {'split':>5}")
    print("-" * 75)
    for filename in files:
        stats = clean_file(os.path.join(args.src, filename), os.path.join(args.dst, filename), args.verbose)
        for k in totals:
            totals[k] += stats[k]
        flags = []
        if stats["dups_removed"]:
            flags.append(f"-{stats['dups_removed']} dups")
        if stats["split"]:
            flags.append(f"{stats['split']} split")
        print(f"{filename:<48} {stats['raw']:>6} {stats['clean']:>6} {stats['dups_removed']:>5} {stats['split']:>5}")
    print("-" * 75)
    print(f"{'TOTAL':<48} {totals['raw']:>6} {totals['clean']:>6} {totals['dups_removed']:>5} {totals['split']:>5}")


if __name__ == "__main__":
    main()
