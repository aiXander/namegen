# AI in the loop — brief lexicon, quick screen, judge panel, final round, breeding

Where AI touches the pipeline. The premise of the whole tool: LLMs are bad at
*inventing* names (they produce the internet-average "slop" token), so Markov
chains invent and LLMs only *retrieve vocabulary* and *judge*. Everything here
is in `ai/` plus the `/api/ai/*` routes in `api_server.py`; the GUI side is
`App.tsx` (pipeline actions, gene pool) and `BriefTab.tsx`. For the layer map
see [CLAUDE.md](../../CLAUDE.md).

## The flow (GUI tabs Brief → Sources → Sampling → Judge → Results)

1. **Brief lexicon** (`ai/lexicon.py`, `/api/ai/lexicon`, Brief tab). One
   Sonnet call collects ~150 *real* words/roots evoking the brief across many
   languages (koru, noos, myc, lokahi, ujamaa…), stored in
   `training_data.lexicon` as `{word, lang, meaning}` and user-prunable. It is
   mixed into Markov training at `training_data.lexicon_share` (default 0.5)
   — see [markov-sampling.md](markov-sampling.md#extra-training-words-lexicon--breeding).
   The sampler still invents every name; the lexicon just seeds meaningful
   morphemes (`flokahi` ← flokkr + lokahi). "More words" passes the current
   list as `exclude`.
2. **Quick screen** (`NameJudge.screen`, inside `/api/ai/judge-stream`). When
   there are more names than `ai_settings.max_names`, every judge gives every
   name a bare 0–10 (`SCREEN_SYSTEM_PROMPT`, `{"scores": {name: n}}`,
   `SCREEN_CHUNK_SIZE`=50, same shuffle/retry machinery as the panel); the
   top `max_names` by mean go on. Unscreened names rank last, never vanish
   silently (count reported as `screen.failed`).
3. **Judge panel** (`NameJudge.judge`). Every model in `llm.judges` scores
   every surviving name, concurrently. Each judge sees its own deterministic
   shuffle (seeded by model id → re-runs hit the cache) chunked by
   `llm.chunk_size`. Per name: 0–10 `sound` / `fit` / `distinct` / `score` +
   `note` + `flag`. Panel value = mean over judges; first non-empty note/flag
   wins.
4. **Final round** (`/api/ai/final-round`, `NameJudge.final_round`). The GUI
   picks the top `llm.final_size` by panel score **skipping near-duplicates**
   (`diverseTop` in `lib/names.ts`: Levenshtein similarity ≥ 0.75 to a name
   already taken, e.g. murmurata/murmurat) and sends them to
   `llm.final_model` in ONE call that ranks them head to head with a pitch +
   concern each. Absolute scores are poorly calibrated at the top; LLMs
   compare far better than they score.
5. **Breeding** (GUI "breed from N" toggle → `training_data.breed`). On
   Generate, `App.tsx` snapshots the gene pool into `training_data.seeds`:
   names rated 4+, this session's judged names scoring ≥ 5.5 (top 40), then
   the previous pool (cap 80). Seeds train at `seed_share` (0.2) and names
   within edit distance < 2 of a seed are rejected as re-spellings.

The prompt context (`build_brief`) is the user's `llm.description` + vibe
keywords + optional `llm.guidance` + their star ratings as taste examples
(`select_examples`: stratified across star levels so dislikes are shown too,
and **excluding the names being judged** — otherwise judges parrot the rating
back). The system prompts tell the judges the names are statistically
generated and to calibrate hard (typical candidate 2–4).

**Vibe rank** (`ai/embeddings.py`, `/api/ai/embed-rank-stream`) still exists
as an optional Results column, but no longer gates judging — see the
measurements below.

## Measurements behind this design (2026-10, collective-mind brief)

Single-word mode, same 16 sources, 300 names per arm, *every* name judged by
the 2-judge panel (so no gate bias):

| Arm | names ≥5 | ≥6 | top-20 mean |
|---|---|---|---|
| word lists only | 22 | 1 | 5.17 |
| + lexicon 25% | 29 | 7 | 5.53 |
| + lexicon 50% | 43 (32 on a re-run) | 12 (8) | 6.10 (5.88) |
| + lexicon 70% | 45 | 14 | 5.97 |
| + lexicon 40% + round-1 winners 20% | 56 | 16 | 6.12 |

Judge noise between runs is ~±10 gems, so read trends, not single cells.
Lexicon-adjacent names (1 edit from a lexicon word) score highest but get
flagged as "real word" most; > ~70% share drifts toward respellings. Breeding
without the seed-distance rule produced ~20% one-letter seed variants.

Gate recall on the same 883 judged names (gem = panel ≥5; 94 gems, 20 at ≥6),
keeping the top sixth: **embedding vibe 28/94 (10/20)** — barely above chance
(16), Spearman 0.08 with the panel score, because on nonce words embeddings
track shared letters, not meaning; naturalness 35/94; **quick screen with
both panel models 71/94 (18/20)**, Spearman 0.74. (The screen uses the panel's
own models, which is the point: it predicts what the panel will pick.)

End to end in the GUI (two-word `'co '`+`a` config, 3000 generated → 500
judged): round 1 with lexicon 66 names ≥5 / 11 ≥6; round 2 bred from 38
seeds 99 / 17. The pre-lexicon session on the same brief topped out at 5.5.

## Load-bearing decisions

- **Missing ≠ 0.** A chunk that errors or skips names gets one retry pass
  (fresh cache key); names still missing come back `score: None` and the GUI
  says so. The old scorer silently wrote 0 for every name in a failed chunk.
- **Model choice is constrained by the OpenRouter account's zero-data-retention
  (ZDR) setting.** Endpoints that log prompts 404 with "0 endpoints … ZDR
  violation". This killed the old defaults `google/gemini-3.1-flash-lite-preview`
  (judge) and `google/gemini-embedding-2` (embeddings). Verified OK (2026-10):
  `anthropic/claude-haiku-5.5`, `openai/gpt-6-luna` (default judges, $0.10/$0.50
  per M, ~3s per 20-name call), `anthropic/claude-sonnet-5.5` (default final),
  `openai/text-embedding-3-large` (default embeddings). When adding a model,
  probe it with one real call first.
- **Reasoning off by default** (`reasoning_effort="none"`): with reasoning on,
  Haiku 5.5 spends ~1k tokens per call for no visible quality gain. Some
  endpoints *reject* `none` ("Reasoning is mandatory") — `ai/llm.py` retries
  those at `low` and remembers the model in `_reasoning_mandatory_models`.
- **Concurrency is a sliding window** (`batch_json_complete`'s semaphore,
  `DEFAULT_CONCURRENCY=24` per judge), not fixed waves — one slow call no
  longer stalls a whole batch. Never reintroduce a "cancel all pending tasks"
  cleanup at the end of `batch_json_complete`: the panel runs several
  wrappers in one event loop and it would cancel the other judges.
- **Embedding cache** is one SQLite file (`.cache/embeddings.sqlite`, float32
  blobs, key = hash(model::text)). The legacy one-JSON-per-vector cache in
  `.cache/embeddings/` (~19k files, ~900MB, 2s to parse 3000) is migrated
  lazily on read and can be deleted once you no longer need old vectors.
  Ranking math is numpy (was ~11s of pure-Python cosine per 3000 names).
- `llm.min_similarity` (the old vibe cutoff) is gone with the vibe gate; an
  old `config.yaml` may still carry it — harmless, ignored.

## Costs and timing (2026-10, 2 default judges)

Lexicon once per brief (one Sonnet call, ~$0.05). Per round: 3000 names
generated (~2s) → quick screen of all 3000 (~$0.035, ~25s) → top 500 judged
(~$0.04, ~20s) → final round of 30 on Sonnet 5.5 (~$0.018, ~25s). The Judge
tab shows a live cost estimate (screen + panel) from OpenRouter prices
(`/api/ai/models`).

## Verifying changes

`uv run scripts/test_scoring.py` covers panel + screen aggregation (stubbed
LLM, no network), lexicon parsing, lexicon/seed mixing, example selection,
weighting and naturalness. Prompt/model changes
need a real run: generate in the GUI and judge ~50 names, then read the notes.
