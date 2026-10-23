# AI judging — embeddings prefilter, judge panel, final round

How generated names get scored. The premise of the whole tool: LLMs are bad at
*inventing* names (they produce the internet-average "slop" token), so Markov
chains invent and LLMs only *judge*. Everything here is in `ai/` plus the
`/api/ai/*` routes in `api_server.py`. For the layer map see
[CLAUDE.md](../../CLAUDE.md).

## Pipeline (one "Judge" click → `/api/ai/judge-stream`)

1. **Vibe prefilter** (`ai/embeddings.py`, optional — only when
   `llm.keywords` is set). Keywords + every name are embedded; a name's vibe
   is the softmax-pooled (τ=0.1) cosine to the keyword anchors. Only the top
   `ai_settings.max_names` (and ≥ `llm.min_similarity`) go on. Similarities
   are returned for *all* names so the GUI's Vibe column survives the cut.
   Without keywords the first `max_names` names are judged.
2. **Judge panel** (`ai/judge.py`, `NameJudge.judge`). Every model in
   `llm.judges` scores every name, concurrently. Each judge sees its own
   deterministic shuffle (seeded by model id → re-runs hit the cache) chunked
   by `llm.chunk_size`, so chunk-neighbour effects average out. Per name: 0–10
   `sound` / `fit` / `distinct` / `score` + `note` (what it evokes) + `flag`
   (existing brand, common word, bad meaning in some language). Panel value =
   mean over judges; first non-empty note/flag wins.
3. **Final round** (`/api/ai/final-round`, `NameJudge.final_round`) — the GUI
   sends the top `llm.final_size` by panel score to `llm.final_model` in ONE
   call that ranks them head to head with a pitch + concern each. Rationale:
   absolute scores are poorly calibrated at the top; LLMs compare far better
   than they score in isolation.

The prompt context (`build_brief`) is the user's `llm.description` + keywords
+ optional `llm.guidance` + their star ratings as taste examples
(`select_examples`: stratified across star levels so dislikes are shown too,
and **excluding the names being judged** — otherwise judges parrot the rating
back). The system prompts (`JUDGE_SYSTEM_PROMPT`, `FINAL_SYSTEM_PROMPT`) tell
the judges the names are statistically generated and to calibrate hard
(typical candidate 2–4).

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
- Similarity scales differ per embedding model, so `min_similarity` must be
  re-tuned after switching models (it was reset to 0 on the switch).

## Costs and timing (2026-10, 2 default judges)

3000 names generated → all embedded (~$0.0015, ~15–30s) → top 500 judged
(~$0.04, ~16s) → final round of 25 on Sonnet 5.5 (~$0.015, ~20s). The Judge
tab shows a live cost estimate from OpenRouter prices (`/api/ai/models`).

## Verifying changes

`uv run scripts/test_scoring.py` covers panel aggregation (stubbed LLM, no
network), example selection, weighting and naturalness. Prompt/model changes
need a real run: generate in the GUI and judge ~50 names, then read the notes.
