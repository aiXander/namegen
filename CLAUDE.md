# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Markov-chain name generator: a Python backend (Flask API + n-gram sampling engine) with a React/TypeScript frontend. Trains character n-gram models on word lists, generates names under constraints, and optionally scores them with an LLM.

## Running

```bash
# Backend (Flask API on http://localhost:5001) — deps declared in pyproject.toml, uv resolves them automatically
uv run api_server.py

# Frontend (CRA dev server on http://localhost:3000, proxies to :5001)
cd react_gui && npm start

# CLI generation (no GUI, reads config.yaml)
uv run markov_namegen.py
```

Frontend build/test: `npm run build` / `npm test` in `react_gui/`. Python: `uv run scripts/test_constraints.py` (constraint-correctness checks) and `uv run scripts/benchmark_sampling.py` (per-attempt success rates) — run both after touching `markov/`.

LLM scoring goes through OpenRouter (`ai/llm.py`, OpenAI SDK pointed at openrouter.ai) — requires `OPENROUTER_API_KEY` in the repo-root `.env`. Model is configurable in the GUI / `config.yaml` (`llm.model`); default is `google/gemini-3.1-flash-lite-preview`.

## Architecture

Two entry points share the same engine:

- **`api_server.py`** — Flask REST API consumed by the React GUI. Holds global state: current config (persisted to `config.yaml` on every change), saved name ratings (`saved_ratings.json`), word-list ratings, and a cached `MarkovNameGenerator` keyed by a hash of (word lists + model params) to avoid retraining. Key endpoints: `/api/generate-stream` (SSE streaming generation), `/api/ai/score` + `/api/ai/score-stream` (SSE variant with embed/LLM-chunk progress; the GUI uses the stream), `/api/ai/embed-rank` + `/api/ai/embed-rank-stream` (embedding-only ranking, no LLM), `/api/word-lists`, `/api/config`, `/api/ratings`.
- **`markov_namegen.py`** — CLI wrapper; `MarkovNameGenerator` class loads `config.yaml`, trains, generates, filters (dedup, exclude training words, min edit distance), sorts, optionally writes output.

The Markov engine (`markov/`), layered bottom-up:

1. `markov_model.py` — single n-order model: frequency tables → probability distributions with temperature scaling (log-space, zeros preserved) + precomputed cumulative sums.
2. `generator.py` — orchestrates models of order 1..N with backoff to lower orders for unseen contexts.
3. `constraint_sampler.py` — integrates constraints (prefix/suffix/includes/excludes/length) *during* sampling rather than generate-then-filter; `GenerationConstraints` dataclass is the constraint container and owns feasibility checking (`is_feasible()`). See [docs/reference/markov-sampling.md](docs/reference/markov-sampling.md) for the sampling design.
4. `multi_component_sampler.py` — generation with fixed components placed in sampled arrangements, connected by Markov-filled gap segments.
5. `name_generator.py` — public `NameGenerator` facade used by both entry points.

AI scoring (`ai/`): `embeddings.py` (`EmbeddingPrefilter`) is an optional cheap pre-filter stage — embeds user-supplied vibe keywords as vector anchors plus all candidate names (OpenRouter embeddings endpoint, `llm.embedding_model`, default `google/gemini-embedding-2`; `encoding_format="float"` is required), ranks names by softmax-pooled cosine similarity to the anchors, and only the top `max_names` (optionally also gated by the `llm.min_similarity` cutoff) proceed to LLM scoring. Embedding requests use a 30s timeout + retries — the endpoint occasionally hangs, and the SDK's 600s default turned one stuck request into a 10-minute stall (`scripts/time_embeddings.py` measures this). `llm_scorer.py` (`LLMScorer`) chunks names and scores them in parallel against the natural-language `description` in config, using already-rated names as few-shot examples. `llm.py` (`LLMWrapper`) wraps an async OpenRouter client (chat completions + JSON mode) with disk caching (`.cache/`), retries, and cost tracking via OpenRouter's native usage accounting (`cost_tracker.py`).

React GUI (`react_gui/src/`): tabbed UI — `TrainingDataTab` (select/rate word lists), `SamplingParametersTab`, `ResultsTab` (star ratings), `SavedResultsTab`, `AITab` (LLM scoring). All backend calls go through `services/api.ts`.

## Conventions & gotchas

- `config.yaml` is the single source of truth for all generation/model/LLM settings, and is *mutated by the GUI* — expect it to be dirty in git.
- `saved_ratings.json` accumulates user star-ratings and feeds the LLM scorer as few-shot examples — don't clobber it.
- Training data lives in `word_lists/*.txt` (~121 raw datasets, one word per line, lowercased on load). `scripts/clean_word_lists.py` produces a cleaned copy in `word_lists_clean/` (dedup, diacritics stripped, glued compounds segmented via wordninja); when that folder exists, both entry points prefer it (`WORD_LISTS_DIR` in `markov_namegen.py`). Don't edit `word_lists_clean/` by hand — regenerate it.
- `markov/dataset_stats.py` computes per-list "Markov health" (branching factor + memorization rate → 0–100 score), cached in `.cache/dataset_stats.json` keyed by file mtime, surfaced in `/api/word-lists` and the TrainingDataTab health column/filter.
- All generation is lowercase; constraints are lowercased in `GenerationConstraints.__post_init__`.
