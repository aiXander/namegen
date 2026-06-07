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
components the training data could never produce.

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
(banded DP + per-pair early abort): 20s → 0.3s end-to-end. Both the API
(`should_keep_name`) and CLI (`_filter_names`) route through it.

If generation ever feels slow again, run the profiler first — don't assume
the sampler. Parallel/threaded sampling was considered and rejected: the
sampler is pure Python (GIL-bound) and microseconds per attempt; threads
would add overhead, not speed.

## Verifying changes

- `uv run scripts/test_constraints.py` — every emitted name must satisfy every
  constraint; infeasible combos must return `[]` in <0.5s; edge params
  (T=0/0.01/3, order 1/5, no backoff) must not crash.
- `uv run scripts/profile_generation.py` — end-to-end timing split between
  sampling and filtering (uses current `config.yaml`).
- `uv run scripts/benchmark_sampling.py` — per-attempt success rates and
  unique-name yield per constraint combo. Reference numbers (2026-06, ~22k
  training words): plain ~99%, `ends_with=a` ~92%, `includes=co` ~41%,
  `includes=co+ends_with=a` ~35%, components ~100%.
  Note: the benchmark reads `config.yaml` for training sources, which the GUI
  mutates — pin sources when comparing runs.
