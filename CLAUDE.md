# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Markov-chain name generator: a Python backend (Flask API + n-gram sampling engine) with a React/TypeScript frontend. Trains character n-gram models on word lists, generates names under constraints, and optionally scores them with an LLM.

## Running

```bash
# Backend (Flask API on http://localhost:5001) — requires Flask, Flask-CORS, PyYAML, openai
uv run api_server.py

# Frontend (CRA dev server on http://localhost:3000, proxies to :5001)
cd react_gui && npm start

# CLI generation (no GUI, reads config.yaml)
uv run markov_namegen.py
```

Frontend build/test: `npm run build` / `npm test` in `react_gui/`. There are no Python tests.

LLM scoring uses the OpenAI client directly (`ai/llm.py`) — requires `OPENAI_API_KEY`.

## Architecture

Two entry points share the same engine:

- **`api_server.py`** — Flask REST API consumed by the React GUI. Holds global state: current config (persisted to `config.yaml` on every change), saved name ratings (`saved_ratings.json`), word-list ratings, and a cached `MarkovNameGenerator` keyed by a hash of (word lists + model params) to avoid retraining. Key endpoints: `/api/generate-stream` (SSE streaming generation), `/api/ai/score`, `/api/word-lists`, `/api/config`, `/api/ratings`.
- **`markov_namegen.py`** — CLI wrapper; `MarkovNameGenerator` class loads `config.yaml`, trains, generates, filters (dedup, exclude training words, min edit distance), sorts, optionally writes output.

The Markov engine (`markov/`), layered bottom-up:

1. `markov_model.py` — single n-order model: frequency tables → probability distributions with temperature scaling + Dirichlet smoothing.
2. `generator.py` — orchestrates models of order 1..N with backoff to lower orders for unseen contexts.
3. `constraint_sampler.py` — integrates constraints (prefix/suffix/includes/excludes/length/regex) *during* sampling rather than generate-then-filter; `GenerationConstraints` dataclass is the constraint container.
4. `multi_component_sampler.py` — template-based generation with fixed components and Markov-filled variable segments.
5. `name_generator.py` — public `NameGenerator` facade used by both entry points.

AI scoring (`ai/`): `llm_scorer.py` (`LLMScorer`) chunks names and scores them in parallel against the natural-language `description` in config, using already-rated names as few-shot examples. `llm.py` (`LLMWrapper`) wraps the OpenAI client with disk caching (`.cache/`), retries, and cost tracking (`cost_tracker.py`).

React GUI (`react_gui/src/`): tabbed UI — `TrainingDataTab` (select/rate word lists), `SamplingParametersTab`, `ResultsTab` (star ratings), `SavedResultsTab`, `AITab` (LLM scoring). All backend calls go through `services/api.ts`.

## Conventions & gotchas

- `config.yaml` is the single source of truth for all generation/model/LLM settings, and is *mutated by the GUI* — expect it to be dirty in git.
- `saved_ratings.json` accumulates user star-ratings and feeds the LLM scorer as few-shot examples — don't clobber it.
- Training data lives in `word_lists/*.txt` (~121 datasets, one word per line, lowercased on load).
- All generation is lowercase; constraints are lowercased in `GenerationConstraints.__post_init__`.
