# Word lists — what belongs in the library and how it's cleaned

The Markov model learns nothing but the letter statistics of the selected
lists, so list quality *is* output quality. `word_lists/*.txt` (raw, one entry
per line, 69 lists) is the source you edit; `word_lists_clean/` is generated
from it by `uv run scripts/clean_word_lists.py` and is what both entry points
train on. For how lists are mixed during training (natural / balanced /
rating weighting) see [markov-sampling.md](markov-sampling.md#source-weighting-trainingdataweighting).

## What earns a place

A list is valuable when its words share a distinctive, consistent sound
(deities, fantasy names, one culture's forenames or places, dinosaurs,
minerals) with enough variety to recombine. The 2026-10 curation (121 → 69
lists) removed or merged by these rules:

- **Plain English vocabulary** (furniture, meats, colours, emotions, sports,
  professions…) teaches English phonotactics → outputs read as mangled English.
  Removed.
- **One dominant affix** (banks "…bank", genders "…gender", boat_types
  "…boat", superlatives "-iest") → the model just emits the affix. Removed, or
  stripped to stems where the stems have character (norwegian_fjords,
  american_companies).
- **Technical junk** (unix_commands, data_structures) removed.
- **Tiny same-flavour lists merged** — e.g. `pokemon` (+ pokemon_modern),
  `world_places` (countries + capitals + cities), `fantasy_creatures`,
  `edible_plants`, `consumer_brands`, `pastries_and_desserts`,
  `stars_and_constellations`, `cumbrian_places`, `american_places`.
- **Category leakage cleaned** (Greek gods in roman_deities, English names in
  swedish/german forenames, planets in satellites_natural, modern Italian names
  in roman_place_names → Latin forms).

Suffix-heavy lists whose suffix *is* the character (minerals "-ite",
dinosaurs "-saurus") were kept deliberately. Markov health
(`markov/dataset_stats.py`, shown in the Sources tab) is one signal, not the
verdict: generic-English lists can score fine.

## Cleaner traps (`scripts/clean_word_lists.py`)

- **Transliterate before NFKD.** `þ ð æ ø œ ß ł đ ı` don't decompose, so
  diacritic stripping used to *delete* them (`þrúðr` → `rr`, ~870 Nordic and
  German entries damaged). `TRANSLITERATE` maps them first.
- **wordninja segmentation only for English-compound lists** (`SEGMENT_LISTS`:
  common-name animals/plants/birds/fish, English place names, fabrics…). On
  names it shatters real words (`ulfhildur` → ulf/hil/dur, `therosaurus` →
  the/rosa/urus). Add a new list to `SEGMENT_LISTS` only if its entries are
  glued English words.
- The script doesn't delete outputs for removed sources — after removing or
  renaming a raw list, delete its orphan in `word_lists_clean/` too.

Renaming or merging a list orphans its entries in `config.yaml`
(`training_data.sources`, `word_list_ratings`) and in any saved `*.yaml`
config — migrate them. `scripts/test_constraints.py` / `test_scoring.py`
hard-code roman_deities, tolkienesque_forenames, swedish_forenames, pokemon,
websites.
