# WP-0505 — SequentialRefinement with warm start

Milestone: v0.5 · Status: ✅ shipped 2026-07-28
Depends on: —

## Goal

Refine an ordered *series* of patterns — one in-situ ramp, one parametric
sweep, one tray of related specimens — as a chain, each pattern warm-started
from the previous converged state, and return the **trajectory** of every
refined parameter against the series coordinate (T, t, P, …) rather than N
unrelated `RefinementResult`s. The chain is the point *and* the risk: a warm
start propagates error as readily as it propagates a good starting model, so
the deliverable includes the fences that make a trajectory quotable.

## Context

### What a sequential refinement is here

N separate refinements, pattern by pattern, where pattern *k*'s starting
parameter values are pattern *k−1*'s fitted ones. **Not** one joint residual —
that is WP-0308 (multi-histogram), which shipped and is *not* the substrate
(see `### Inherited`). Each pattern keeps its own everything; the only thing
that crosses the boundary is the starting point.

Two things follow immediately and shape the whole design:

- **The output is a trajectory, not a fit.** a(T), Biso(T), the weight
  fractions vs time. A `list[RefinementResult]` is not that: it makes the user
  re-derive the series axis, the esds and the per-pattern status by hand.
- **A sequential fit is path-dependent by construction.** Every pattern's
  answer depends on its predecessor's, so the *method* can imprint a trend that
  the data do not carry (a bad pattern's error is inherited by all its
  successors, and a smooth-looking curve is exactly what that failure produces).
  This is the sequential-refinement analogue of the "never return a confident
  wrong singleton" rule the FitReport is built around, and it needs the same
  treatment: measure it, fence it, report it.

### Source files to touch

- **New** `src/pxrdref/sequential.py` — the `SequentialRefinement` class +
  `refine_sequential` one-shot, mirroring `multi.py`'s shape (which is the
  closest existing sibling: a class wrapping repeated compile/solve, a
  functional one-shot, both exported from `__init__.py`).
- **New** `src/pxrdref/schemas/sequential.py` — `SeriesEntry`, `SeriesResult`,
  `Trajectory`. Pydantic, `extra="forbid"`, JSON round-trip like every other
  schema.
- `src/pxrdref/refine.py` — reuse, do not fork: `Refinement.fit` already runs a
  plan from whatever the working state holds, so the warm start is "construct
  the next `Refinement` from the previous fitted models". `cherry_pick` (already
  written, and its docstring already names this WP) replays a recorded stage
  *action* on the current state — that is the mechanism when the caller wants
  pattern 0's *actual* stage sequence, including any hand-added stages, rather
  than a plan object.
- `src/pxrdref/viz/plots.py` — `plot_trajectory`.
- `src/pxrdref/__init__.py`, `docs/AGENT_PROTOCOL.md`, `README.md`.

### Invariants and existing machinery that constrain the design

- **A history tree is bound to one pattern.** `TreeHeader.data_fingerprint` is
  a sha256 of (2θ, intensity) and `replay` *raises* on a mismatch
  (`refine.py:1226`). So a series cannot be one tree: it is **one tree per
  pattern**, and the cross-pattern link has to be recorded as node metadata
  (`Annotation.notes`, which is append-only and free-form) rather than as a
  parent edge. Do not weaken the fingerprint check to make one tree work — it
  is what stops a node being replayed against the wrong data.
- **Nodes store state, not curves** (~10 kB vs ~1.24 MB). `SeriesResult` obeys
  the same rule: it serializes per-pattern *summaries* (statistics, refined
  values + esds, diagnostics, QPA, node/tree ids), never `y_obs`/`y_calc` ×
  N patterns. The full `RefinementResult`s stay reachable in memory on the
  `SequentialRefinement` object for plotting.
- **Le Bail extracted intensities are path-dependent state outside θ**, already
  serialized per node as `ReflectionState` and restored by
  `refine._restore_lebail` via `Refinement._pending_reflections`. A sequential
  Le Bail series wants exactly that carried pattern-to-pattern — it is the
  single best warm start there is for Le Bail, since a flat re-seed throws away
  everything the previous pattern learned.
- **Frozen-per-stage discreteness** is untouched by this WP: every pattern gets
  its own `compile_model` at its own starting values, which is the legitimate
  between-stage refresh. Nothing here reaches inside a least-squares run.
- **Weights**: each pattern carries its own σ (file esds when present, Poisson
  fallback). Never pool patterns' σ.

### Inherited

From **WP-0308** (multi-histogram, landed 2026-07-24) — it shipped, and it is
**not** the substrate for this WP. `MultiParameterTable` and
`run_multi_least_squares` build *one joint residual* over patterns that share
structural parameters; a sequential series is N separate refinements chained
pattern to pattern, so neither is reusable here. 0308 fenced it from its side.
The enabling piece stays history `cherry_pick`.

Two inherited constraints worth knowing before designing:

- **Multi-histogram fits deliberately run with history OFF** and do not enter
  the `RefinementTree` DAG — a multi-pattern fingerprint was judged a deeper
  change and left as a documented future seam. This WP is the opposite case: it
  is *built* on the DAG, one node chain per pattern, so it does not inherit
  that limitation but should not assume 0308 solved any of the persistence
  question either.
- **Rietveld only, upstream.** 0308 raises `NotImplementedError` for Le Bail
  and Pawley because per-pattern extracted intensities are not shared. A
  *sequential* Le Bail series has no such problem (each pattern is its own
  extraction), so that restriction does not carry over — but the per-node
  `ReflectionState` serialization that makes Le Bail restorable across a
  checkout is what this WP depends on for warm starts.

## Design decisions

Settled before coding; anything measured differently during the work replaces
the bullet here and says so.

1. **Warm start is per-parameter, not all-or-nothing.** `carry` is a list of
   path globs (fnmatch on dot paths, the `set_vary` convention), default
   `["*"]`. Paths that match take the previous pattern's fitted value; paths
   that do not are reset to the *initial* model's value.

   The motivating hypothesis — that chaining a phase scale across mixtures
   whose composition swings from 1 to 94 wt % (qarr 1a → 1b) would start the
   next fit further from its answer than a cold start — **was measured and is
   false**. Carrying everything costs 838 iterations against 904 for a carry
   that excludes the scales and re-seeds them per pattern, with identical Rwp
   and identical weight fractions. The knob stays, because a series where a
   parameter must provably not be chained is a real thing; what changed is its
   documentation, which now says "control, not tuning" rather than asserting a
   benefit the data refuse to show. A hostile real series was the only way to
   find that out, which is why the acceptance runs both passes and keeps them.

   The *other* half of the same problem turned out to be real, and needed a
   second mechanism: a phase scale on a series of different mixtures must be
   re-estimated **from this pattern**, which excluding it from `carry` cannot
   express (that only falls back to the first pattern's guess). Hence the
   `prepare` hook — `(index, data, structure, instrument) -> None`, called on
   the warmed models just before each fit.
2. **The refit strategy is measured, not assumed.** Two modes:
   `refit="stages"` re-runs the whole plan on every pattern (safe: the same
   staged turn-on order, just from a better starting point), `refit="single"`
   collapses the plan into one stage freeing the union of its `turn_on` globs
   (fast: what an in-situ operator actually does once the model is stable).
   **Measured on the acceptance series: `single` wins and is the default** —
   904 iterations against 1623 staged and 2863 unchained, at identical mean Rwp
   (0.1278) and identical QPA accuracy (RMS |ΔW| 2.26 vs 2.27 wt %). The staged
   turn-on order exists to keep early stages conditioned from a *poor* starting
   model, and a converged neighbour is not one; when it turns out not to be a
   good one either, decision 3 catches it and refits cold with the full plan.
3. **Reseed on failure, and say so.** After pattern *k*: if `status` is
   `"diverged"`, or Rwp exceeds `reseed_factor ×` the reference Rwp (median of
   the accepted ones so far — a median, not the previous value, so one bad
   pattern cannot ratchet the threshold), re-run pattern *k* cold from the
   initial models and keep the better of the two. Emit `SEQUENTIAL_RESEED`.
   Without this, one bad pattern poisons every successor and the failure is
   invisible in a trajectory plot, which is the worst property this feature
   could have. Default `reseed_factor = 1.25`.
4. **Path-dependence is measurable, so measure it.** `direction="both"` runs
   the series forward and backward and compares the two trajectories per path:
   where |forward − backward| exceeds `k·σ` combined, the parameter is reported
   `SEQUENTIAL_PATH_DEPENDENT` and *that* is the honest statement about it — a
   trajectory that survives both directions is evidence, one that does not is
   an artefact of the chain. This is the WP's headline diagnostic.
5. **Discontinuities are reported, never smoothed.** A jump between adjacent
   patterns much larger than the local scatter is either the science (a phase
   transition) or a chain failure. `SEQUENTIAL_DISCONTINUITY` says both, and
   nothing in this WP interpolates, smooths or constrains a trajectory — that
   would be parametric refinement (Stinton & Evans 2007), which is a different
   thing and stays out of scope.
6. **`SeriesResult` is summaries + a trajectory API**, per the state-not-curves
   rule above. `trajectory(path)` returns x/value/stderr arrays;
   `to_table()`/`write_csv()` write the wide table (one row per pattern, one
   column per refined parameter + its esd) that is what anyone actually plots.

## Non-goals

- **Parametric refinement** — constraining a parameter to a functional form of
  T/t across the whole series and refining that function's coefficients
  (Stinton & Evans 2007, J. Appl. Cryst. 40, 87). That is one joint residual
  over the series with a shared trajectory model; it needs the 0308 stacked
  machinery, not this one. Explicitly fenced; this WP's smoothness fences exist
  precisely so nobody mistakes a sequential trajectory for a parametric fit.
- **`vmap`-batched series execution** — v2 fence (DESIGN.md), and WP-0408
  measured what it would be worth (≈2.5-3× at ≥10 synchrotron patterns). This
  WP runs patterns one at a time on whatever backend it is given.
- **Reading a directory of patterns / instrument-vendor series formats.** The
  API takes a `list[PatternData]`; `read_pattern` already exists and a
  `sorted(glob(...))` is one line at the call site.
- **Automatic phase appearance/disappearance** across a series (a phase that
  nucleates mid-ramp). Interesting, and squarely a v0.6+ agent-surface problem.

## Tasks

- [x] Expand this stub into a full WP before writing code
- [x] `schemas/sequential.py`: `SeriesEntry` / `SeriesResult` / `Trajectory`,
      state-not-curves, JSON round-trip test
- [x] `sequential.py`: `SequentialRefinement.fit` warm chain, `carry` globs,
      `refit="stages"|"single"`, `refine_sequential` one-shot; exports
- [x] Reseed guard + `SEQUENTIAL_RESEED` diagnostic
- [x] History: one tree per pattern, cross-linked by annotation notes
- [x] Le Bail series: carry extracted intensities pattern-to-pattern
- [x] Trajectory API + `write_csv` + `viz.plots.plot_trajectory`
- [x] `SEQUENTIAL_DISCONTINUITY` + `direction="both"` /
      `SEQUENTIAL_PATH_DEPENDENT`
- [x] `prepare` hook (found necessary by the acceptance — see decision 1)
- [x] Acceptance: synthetic in-situ thermal series (injected ramp recovered,
      `tests/test_sequential.py`, fast) and the qarr sample-1 series as a
      real-data chain (`tests/test_acceptance_sequential.py`, slow)
- [x] Docs: AGENT_PROTOCOL §9b + three diagnostic rows, README, CLAUDE.md,
      ROADMAP, forward notes into 0602/0605/1001, handover log

## Acceptance

**Synthetic in-situ series (controlled truth).** A 7-pattern thermal ramp
generated from a known structure with a linear cell expansion: the sequential
fit recovers the injected expansion coefficient (as the *slope* of a(T)) to
within 5 %, and every pattern converges. This is the only place in the WP where
the true trajectory is known, so it is where the trajectory machinery is
actually validated — and it is deliberately a **fast** test, not a slow one, so
every run of the unit suite exercises it. It lives in `tests/test_sequential.py`
alongside the fence regressions rather than in the acceptance module.

*Measured 2026-07-28*: recovered, with the tied cubic b/c tracking a exactly;
`refit="single"` 82 iterations against `"stages"` 154 on the same four patterns.

**Real-data series (qarr sample 1a-1h).** The eight round-robin mixtures share
one instrument and three phases, so they are a legitimate — and deliberately
hostile — series: the compositions swing from 1 to 94 wt %. Criterion: the
sequential chain reproduces the *independent* per-pattern QPA fractions of
`test_acceptance_qpa_roundrobin.py` within its stated participant-spread
tolerance, and the total iteration count is reported against the independent
baseline. A speedup is expected but **not** asserted as a pass/fail gate.

*Measured 2026-07-28*, protocol imported wholesale from the QPA acceptance so
only the chaining differs:

| pass | iterations | mean Rwp | RMS \|ΔW\| | worst \|ΔW\| | reseeds |
|---|---|---|---|---|---|
| independent (v0.3 protocol, per mixture) | 2863 | 0.1278 | 2.26 | 5.13 | — |
| chained, `refit="stages"`, carry ∌ scales | 1623 | 0.1276 | 2.27 | 5.15 | 0 |
| chained, `refit="single"`, carry ∌ scales | 904 | 0.1278 | 2.26 | 5.13 | 0 |
| chained, `refit="single"`, carry = `*` | 838 | 0.1278 | 2.26 | 5.13 | 0 |

Wall clock for the two `single`/`stages` passes: 43.5 s against 74.1 s. Every
sample-1 fraction stays inside the participant-spread band, the three cells are
flat across the series to < 2e-3 Å (they are the same materials in every
mixture, so a drifting cell would be the chain imprinting a trend), and the
chained fractions sit within 1 wt % of the independent ones everywhere.

```sh
.venv/bin/python -m pytest tests/test_sequential.py -q             # 25 tests
.venv/bin/python -m pytest tests/test_acceptance_sequential.py -q  # 13, slow
.venv/bin/python -m ruff check src tests examples
```

## References

- Le Bail, Duroy & Fourquet (1988) *Mater. Res. Bull.* 23, 447 — the extracted
  intensities that a Le Bail warm start carries.
- Madsen, Scarlett, Cranswick & Lwin (2001) *J. Appl. Cryst.* 34, 409 — the
  qarr sample-1 mixtures and their participant spread.
- Stinton & Evans (2007) *J. Appl. Cryst.* 40, 87 — parametric refinement; the
  named non-goal, and the reason the fences here are about *reporting*
  path-dependence rather than suppressing it.

## Handover log

- **2026-07-28 (ship)** — **done**, all checklist items landed, 890 tests green
  (810 fast in 2.8 min), ruff clean. Five commits: WP expansion, the core module
  + unit tests, the real-data acceptance + the two defaults it moved, the docs
  and forward notes, and a self-review fix (below).

  *Two defaults were set by measurement, not by design.* `refit="single"` is
  the default because the collapsed refit is 1.8× cheaper than re-walking the
  staged plan and 3.2× cheaper than not chaining, for the same answer to three
  decimals. And the `carry` glob's motivating hypothesis is **refuted** — see
  decision 1; the docstring and the acceptance module both say so, deliberately,
  because the tempting alternative was to quietly keep the knob and imply it
  earns its place.

  *Gotcha that will recur.* Both trajectory fences are ratio tests, and a
  softplus coefficient sitting on its floor breaks them in a way the σ leg
  cannot catch: dp/du → 0 there, so the esd collapses *with* the value and
  "significance" inverts. Measured on the synthetic ramp: `instrument.profile.y`
  with a median step of 4e-16, one step of 1.3e-11 (29 000× the median) and
  σ ≈ 4e-55 passed both legs, and the forward/backward chains "disagreed" at
  1e16 σ over 1e-60 vs 1e-74. `NOISE_FLOOR_REL` (1e-9 of the parameter's own
  magnitude, never below 1e-9 absolute) is the fix; `test_sequential.py` pins
  both cases. Any future statistic shaped as "is this change large relative to
  that change" wants the same floor.

  *Found in self-review, after the acceptance.* `direction="both"` ran its
  verification chain through the same per-pattern history targets as the
  reported one, so with a history directory both passes appended to
  `<label>.jsonl` — and since `RefinementTree.load` takes the last header it
  sees, a reloaded tree would silently mix two chains' nodes under one header.
  The backward pass now writes `<label>.backward.jsonl`. The general shape:
  anything that runs the chain a *second* time for verification has to be
  checked for side effects on the first run's artefacts, and history is
  append-only precisely so that a collision is silent rather than an error.

  *Not built, deliberately.* Parametric refinement (Stinton & Evans 2007) stays
  a non-goal — it is one joint residual with a shared trajectory model, i.e.
  the 0308 machinery, not this one. Automatic phase appearance/disappearance
  across a series is a v0.6+ agent-surface problem. `vmap`-batched execution
  stays v2-fenced; a note went into 0605 explaining why a *warm-started* chain
  cannot simply be batched (pattern k's start is pattern k−1's answer).

  *Forward notes written* (protocol step 3b): 0602 (`SeriesResult` is a second
  top-level result type its single-call API must express; three new diagnostic
  codes; per-entry tree ids), 1001 (a new acceptance suite whose anchor is this
  package's own other result — a third tier beside absolute and cross-code —
  and which moves in lockstep with the round-robin protocol), 0605 (the
  batching constraint above).

- **2026-07-28** — stub expanded into a full WP (goal, design decisions 1-6,
  non-goals, task checklist, two-part acceptance). Key findings from the
  survey that shaped it: a history tree is pinned to one pattern by
  `TreeHeader.data_fingerprint` (so a series is one tree *per pattern*, linked
  by annotation notes — do not weaken the fingerprint), and `Refinement.fit`
  already runs a plan from arbitrary working state, so the warm start is
  construction, not a new solver path. Next: `schemas/sequential.py`.
- **2026-07-22** — created as a stub from the ROADMAP split.
</content>
</invoke>
