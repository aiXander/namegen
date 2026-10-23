# Markov constraint sampling — design & rationale

How `markov/constraint_sampler.py` and `markov/multi_component_sampler.py` turn
constraints into high per-attempt success rates without distorting the model's
character statistics. For the layer map, see [CLAUDE.md](../../CLAUDE.md).

## The core problem

Naive generate-then-filter collapses under constraint combinations: with
`includes=co + ends_with=a` on a typical dataset, raw rejection sampling
succeeds ~1% of attempts → the GUI's "no success in N seconds" timeout fires →
user sees zero results. The redesign (2026-06) integrates each constraint into
sampling and reached ~35% on that combo (~40x), with `ends_with` alone going
56% → ~92%.

## Mechanisms (in `ConstraintSampler.generate_constrained_name`)

- **Backoff on dead ends, not just unseen contexts.** `_constrained_probs`
  walks models highest-order-first and backs off to a lower order when
  constraint masking *zeroes out* every transition, not only when the context
  is missing. Without this, any mask (excludes, termination) can strand a
  sample mid-word.
- **`includes` guidance.** One OR-group of the pattern is picked per attempt;
  the next character that advances an unmet token gets its probability
  multiplied by `INCLUDES_BOOST` (8.0) — but *only if the model already allows
  it* (nonzero prob), so guided names stay data-plausible. Correctness is
  still enforced by the posterior check; the boost just makes hits common
  instead of vanishingly rare.
- **`ends_with` splice with grow-and-retry.** The body is sampled to a random
  target, then the suffix is spliced on only if every junction transition (and
  termination after it) passes the **strict** plausibility check. If not, the
  body keeps growing and the splice is retried at every length up to
  `max_length`, instead of rejecting the whole attempt.
- **Length steering.** Termination is masked below `min_length` and boosted
  exponentially past the sampled target (`TERMINATION_BIAS ** overshoot`).
  Words that hit `max_length` are accepted only if `#` is strictly plausible
  there — this is what killed the chopped-off endings ("aalfre").
- **`excludes` masking + posterior.** Transitions completing a forbidden
  substring are masked during sampling (cheap `endswith` check since the
  invariant holds for the prefix); the final posterior check also catches
  patterns introduced by the suffix splice. Multiple tokens are supported
  (comma/semicolon-separated).
- **Feasibility precheck.** `GenerationConstraints.is_feasible()` rejects
  self-contradictory combos (min>max, prefix+suffix>max, excludes inside
  ends_with, all includes-groups violating excludes) in O(1). Both
  `NameGenerator.generate_names` and `/api/generate-stream` call it so
  impossible settings fail instantly with a clear error instead of burning the
  retry/time budget. (The old retry loop *doubled* its time budget on zero
  results — an effectively infinite loop on impossible constraints.)

## Strict vs lenient plausibility (`_is_plausible`)

Two notions of "the model could have produced this transition":

- **Lenient** (default): nonzero at *any* order — backs off past
  zero-probability high-order contexts (Katz-style).
- **Strict** (`strict=True`): the highest-order model that knows the context
  decides; zero there = implausible.

Strict is used where a weak junction is very visible and retrying is cheap:
suffix splices, end-of-word checks. Lenient is used where being strict would
zero out the search space: component-mode endings and component entry
junctions (tight arrangements like `[co,mind]` at length 6 have zero freedom —
a forced component beats returning nothing). Component-mode *suffix* junctions
are strict again. If you tune this, re-run the tight cases in
`scripts/test_constraints.py` — they're the canary for over-strictness.

## Component mode (`MultiComponentSampler`)

Per attempt: shuffle component orderings (≤8 permutations) → pick a target
length → start gaps at their minimums (`component_separation` between
components, 0 at boundaries; `starts_with`/`ends_with` are pinned fixed parts)
→ sprinkle spare length randomly over gaps → build left-to-right, sampling
each gap segment with the *real accumulated word* as Markov context and gating
each junction into a fixed part on plausibility. Characters *inside*
user-given components are exempt from plausibility — users may demand
components the training data could never produce. `includes` still steers the
gap-filling (same guide-token boost as single-word mode); correctness is the
posterior `_validate`'s job either way.

## Multi-word mode (`generation.word_counts`)

`word_counts` is the list of allowed word counts (GUI: "Words per name"
checkboxes 1/2/3, at least one always ticked). `allowed_word_counts()` in
`constraint_sampler.py` parses it; **unset falls back to the old switch** — a
space in `includes` meant two words — so pre-setting configs keep sampling what
they used to (`[2]` if `includes` has a space, else `[1]`; the GUI mirrors this
default). Otherwise a space in `includes` means nothing and is stripped
(a trailing space copied in with `'co' ` silently forced two words — the
reason the setting exists).

Each attempt, `NameGenerator._pick_word_count` picks one count uniformly from
the allowed counts that fit `max_length` (`feasible_word_counts`: k words need
`3k - 1` chars). The mix of the output therefore also reflects per-count
success rates. None fit → infeasible (fast `[]`, and an SSE error in the API).

The model's alphabet has **no space** (cleaned word lists are one word per
line), so the constraint sampler can never *emit* one. Multi-word attempts go
through the component sampler, which *places literals*:

- `word_breaks = k - 1` is passed explicitly into `ComponentConstraints`
  (also on the fixed-components path). `generate_name` skips the single-word
  fallback for these (it could never produce a space).
- `_insert_separators` drops `word_breaks` literal `" "` parts at random slots,
  adjacent ones included — the gap minimums below turn the gap between two
  separators into a real word (this is what makes 3+ words work).
- Building across a separator **resets the Markov context to fresh
  `#`-padding** — each space starts a brand-new word, so word 2 is sampled as a
  word-initial Markov walk, not as a continuation of word 1. Junction
  plausibility is skipped *into* a space (the model has no transition for it)
  but still enforced when a real part begins the next word.
- `MIN_WORD_LEN` (2, in `constraint_sampler.py`) is forced on each side of
  every break via the gap minimums, counting an adjacent fixed part's letters,
  so you never get `x noda`. `_validate` re-checks: exactly `word_breaks`
  spaces, no empty word, and the usual length/`includes`/`ends_with`/excludes
  over the whole joined string.

Worked example: `word_counts=[2]`, `includes='co'`, `ends_with='a'` → fixed
parts `[" ", "a"]`, gaps guided toward `co` → `code noda`, `temp coa`. The
spaces count toward length; short `max_length` with 3 words yields 2-letter
fragments (`cor sh gaba`).

## Source weighting (`training_data.weighting`)

Selected lists are concatenated, so with `natural` weighting a 40k-word list
drowns a 100-word one. `source_weights()` in `markov_namegen.py` gives every
word a weight: `balanced` = equal total mass per list, `rating` = balanced ×
the list's star rating (unrated = 3). Weights are normalised so total mass
equals the natural word count, so temperature/backoff behave identically in
every mode. `MarkovModel` stores observations as weighted counts
(`context -> {char: weight}`); with no weights the chains are bit-identical to
the old `Counter`-based model (verified 2026-10). The API's generator cache key
includes the weighting mode, and the ratings when weighting by rating.

## Extra training words: lexicon + breeding

Two word sets that aren't word lists ride on top of the source weighting
(`extra_sources()` / `mix_extra_words()` in `markov_namegen.py`, applied in
`MarkovNameGenerator._load_training_data`, so CLI and API agree):

- `training_data.lexicon` — real words evoking the brief (see
  [ai-judging.md](ai-judging.md)), at `lexicon_share` (default 0.5).
- `training_data.seeds` — earlier winners, only when `training_data.breed`
  is on, at `seed_share` (default 0.2). Multi-word seeds are split and words
  under 3 letters dropped (`SEED_MIN_LENGTH`).

Each set holds exactly its share of the total training mass; the word lists
(already weighted by `weighting`) keep the rest, and the extras are scaled
down if they'd exceed 90% (`MAX_EXTRA_SHARE`) so the lists always keep a say.
Both sets are ordinary training words for the novelty filters (exact copies
excluded, the From column shows provenance like `lokahi +2`). Seeds add one
rule: anything within edit distance < 2 (`MIN_SEED_DISTANCE`) of a seed is
rejected as a re-spelling of a name the user already saw (counted as
`too_similar`; ~6k of 27k attempts on a 38-seed pool, still 3000 names in
~2s). The API's generator cache key includes all five extra fields. Why
these defaults: measured in ai-judging.md.

## Naturalness (`NameGenerator.naturalness`)

A free per-name fluency score (0–100) shown in the GUI's Natural column:
`Generator.log_likelihood` = mean log2 P per transition under the *untempered*
training distribution (stupid backoff, 0.4 per order dropped; floor 1e-4),
turned into a percentile against ~1000 **novel** names sampled from that same
distribution at T=1. Don't calibrate against the training words themselves:
they're in-sample, so every novel name ranked ~0 (the first attempt did
exactly that). Multi-word names skip 1–2 letter words (forced fragments like
`co`). `scripts/test_scoring.py` guards the calibration.

## Temperature semantics (`markov_model.py`)

`p ∝ count^(1/T)` over *observed* transitions only — unseen characters stay at
exactly 0 at any temperature (an epsilon here leaks mass to garbage
transitions at T>1). Computed in log space relative to the max count, so tiny
T degrades gracefully into argmax instead of overflowing (`count ** 100`
overflows a float — this was a real crash, dataset-size dependent). T=0 is
explicit argmax and is allowed (asserts are `>= 0`).

## The real bottleneck is filtering, not sampling

Profiling (2026-06, `scripts/profile_generation.py`) on 43k training words with
`ends_with=a`: sampling cost ~0.06ms/attempt at ~93% per-attempt success —
i.e. the integrated sampler above is effectively free. What made "100 names
ending in a" take ~30s was the `min_edit_distance` filter: a pure-Python
Levenshtein DP against the *entire* training set per accepted candidate
(~200ms each). Fixed by `too_close_to_training()` in `markov_namegen.py`,
which uses rapidfuzz's C++ Levenshtein with `score_cutoff=min_distance-1`
(banded DP + per-pair early abort): 20s → 0.3s end-to-end. The CLI
(`_filter_names`) still routes through it; the API instead calls
`nearest_training_word()` once per accepted name (full rapidfuzz scan, ~2.5ms
against all 36k words) and reuses that distance for both the filter and the
GUI's "From" column.

If generation ever feels slow again, run the profiler first — don't assume
the sampler. Parallel/threaded sampling was considered and rejected: the
sampler is pure Python (GIL-bound) and microseconds per attempt; threads
would add overhead, not speed.

## Verifying changes

- `uv run scripts/test_constraints.py` — every emitted name must satisfy every
  constraint; infeasible combos must return `[]` in <0.5s; edge params
  (T=0/0.01/3, order 1/5, no backoff) must not crash.
- `uv run scripts/test_scoring.py` — source weighting, naturalness
  calibration, judge-panel aggregation (no network).
- `uv run scripts/profile_generation.py` — end-to-end timing split between
  sampling and filtering (uses current `config.yaml`).
- `uv run scripts/benchmark_sampling.py` — per-attempt success rates and
  unique-name yield per constraint combo. Reference numbers (2026-06, ~22k
  training words): plain ~99%, `ends_with=a` ~92%, `includes=co` ~41%,
  `includes=co+ends_with=a` ~35%, components ~100%. Multi-word (~7.5k cleaned
  words): two words ~100%, `+ends_with=a` ~71%, `+includes=co+ends_with=a` ~36%;
  three words `+ends_with=a` (8–14 chars) ~76%.
  Note: the benchmark reads `config.yaml` for training sources, which the GUI
  mutates — pin sources when comparing runs.
