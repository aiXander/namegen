"""Brief lexicon: real words and roots that carry the brief's meaning, used as
extra Markov training data.

The premise of the tool is that LLMs are bad at *inventing* names. They are,
however, very good at *retrieving* real vocabulary: the Latin, Greek, Sanskrit,
Māori or Finnish words for the ideas in a brief. Mixed into the Markov training
set at a fixed share, those words seed the chains with meaningful morphemes
(myc-, noo-, murm-, kor-), so the sampler still invents the names, but far
more of them carry an echo of the brief. Measured on one brief (2026-10): see
docs/reference/ai-judging.md.
"""

import asyncio
import hashlib
import re
import unicodedata
from typing import Any, Dict, List, Sequence, Tuple

from ai.llm import LLMWrapper

DEFAULT_LEXICON_MODEL = "anthropic/claude-sonnet-5.5"
DEFAULT_LEXICON_SIZE = 150

LEXICON_SYSTEM_PROMPT = """You are an etymologist and polyglot helping a naming team.

You will NOT invent names. Instead, collect REAL vocabulary whose meaning evokes the brief: words, roots and combining forms from many languages (Latin, Ancient Greek, Sanskrit, Old Norse, Japanese, Māori, Finnish, Swahili, Hebrew, Basque, Welsh, Quechua, Hawaiian, and others), plus the most evocative English words.

Rules:
- Every entry must be a real word or root in its language, romanised to plain lowercase letters a-z (no diacritics, spaces, hyphens or apostrophes).
- Prefer short, sonorous forms (2-9 letters) and bare roots (e.g. "myc", "noo", "koru") over long inflected words.
- Cover every facet of the brief (its purpose, feel and imagery), not just the obvious synonyms. Spread across languages; at most a third English.
- No existing brand or product names.

Reply with JSON only:
{"words": [{"word": "...", "lang": "...", "meaning": "a few words"}]}"""


def _ascii_word(text: str) -> str:
    """'Kōru' -> 'koru'; '' if anything but letters remains."""
    stripped = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower().strip()
    return stripped if re.fullmatch(r"[a-z]{2,14}", stripped) else ""


def parse_lexicon(result: Any) -> List[Dict[str, str]]:
    """Normalise the model's reply into unique [{word, lang, meaning}]."""
    items = result.get("words", []) if isinstance(result, dict) else result
    entries: List[Dict[str, str]] = []
    seen = set()
    for item in items if isinstance(items, list) else []:
        if isinstance(item, str):
            item = {"word": item}
        if not isinstance(item, dict):
            continue
        word = _ascii_word(item.get("word", ""))
        if word and word not in seen:
            seen.add(word)
            entries.append({"word": word, "lang": str(item.get("lang") or "").strip(),
                            "meaning": str(item.get("meaning") or "").strip()})
    return entries


def build_lexicon(brief: str, size: int = DEFAULT_LEXICON_SIZE, model: str = DEFAULT_LEXICON_MODEL,
                  exclude: Sequence[str] = (), cache_dir: str = ".cache") -> Tuple[List[Dict[str, str]], float]:
    """Ask `model` for ~`size` real words evoking `brief`. `exclude` (words
    already in the lexicon) asks for fresh ones. Returns (entries, cost)."""
    wrapper = LLMWrapper(cache_dir=cache_dir, reasoning_effort="low")
    wrapper.set_component("lexicon")
    start_cost = wrapper.cost_tracker.get_total_cost()
    prompt = f"{brief}\n\nCollect about {size} entries."
    if exclude:
        prompt += f"\nAlready collected (do not repeat): {', '.join(exclude)}"
    key = hashlib.md5("\x1f".join([model, LEXICON_SYSTEM_PROMPT, prompt]).encode()).hexdigest()
    [result] = asyncio.run(wrapper.batch_json_complete(
        prompts=[prompt], model=model, cache_keys=[key], system_prompt=LEXICON_SYSTEM_PROMPT))
    if isinstance(result, Exception):
        raise result
    skip = set(exclude)
    entries = [e for e in parse_lexicon(result) if e["word"] not in skip]
    return entries, wrapper.cost_tracker.get_total_cost() - start_cost
