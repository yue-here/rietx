# WP-1902 — the solve cost as a quadratic form, and the doublet question first

Milestone: structure-solution · Status: ✅ 2026-10-03 — the spike, `solve/cost.py` (PR #580), its two named refusals (PR #648), and the "poor" refusal reading `RefinementResult.usable`
Depends on: —

## Goal

`solve/cost.py` evaluates the profile χ² of a structure from its intensity
vector alone, as a quadratic form built once from a compiled Le Bail / Pawley
model, agreeing with Rietveld-mode `evaluate`. The first task settles whether
lab doublet data can use it.

## Context

Scoped in issue #562 (chunk S0, plus the prototype comment's amendment (a)) and
WP-1515, reviewed adversarially on 2026-09-30. With Ω (per-reflection profiles),
the cell and the background held, and W = diag(1/σ²):
χ²(I) = c − 2rᵀI + IᵀMI, with M = ΩᵀWΩ, r = ΩᵀW(y − b), c = (y − b)ᵀW(y − b).

**What the review measured** (Cu LaB₆, exact overlaps, scratch probes):

- The identity holds to 4e-16 about S0's **own** unconstrained least-squares
  answer. About rietx's fitted Pawley intensities it is 1e-7 (restraint rows,
  ≥ 0 bounds, `ftol`), and about Le Bail intensities 2.4e-2. So **the floor
  comes from S0's own solve**, never from `lebail_update` or the Pawley buffers,
  and I_P may go negative.
- **The proposed identity test is tautological**: χ² − χ²_min against the same
  quadratic form passes for any Ω, a wrong one included. The failing test is
  Ω·I(structure) against Rietveld-mode `evaluate`.
- **Lab doublets are the open question.** Le Bail and Pawley share one I across
  emission lines and apply no per-line Lp (`model/forward.py`, `lp_lines = None`),
  so Lp(Kα2)/Lp(Kα1) − 1, which runs −0.6 % to +1.4 % over 20–130°, is missing.
  NAC is single-line and hides it. The FAP lab pattern does not.
  **Spike first**: does Ω built per line (from `derivative_bases` or by
  linearity, never from batch internals) match Rietveld `evaluate` on FAP? If
  not, the cost refuses multi-line data by name, which would exclude the common
  case.
- The restraint rows in `pb.restraint` include WP-1459's off-data ridge rows as
  well as the equal-split ones. S0 builds M from Ω directly and excludes both.
- V = M⁻¹ does not exist under exact overlap. Any covariance view goes through
  `statistics.normal_covariance` (equilibrated, rootless directions absent).
- M is banded plus a rank-q update after the background is projected out
  (prototype, amendment (a)). Store it sparse plus low rank when N_refl is large.

Refusals by name: a magnetic phase; a Rietveld-mode model; a poor or
unconverged extraction. "Poor" means `not result.usable` (WP-1336), set
2026-10-01; a tighter bar waits for a measurement on public data.

## Non-goals

- Engines, moves, tempering, grading (later WPs).
- The compiled |F|² kernel (S4): defer until its own measurement, since the
  prototype showed incremental moves, not the kernel, set throughput.

## Tasks

- [x] Spike: per-line Ω against Rietveld `evaluate` on FAP (lab doublet) and NAC; record the residuals and the decision
- [x] `solve/cost.py`: c, r, M, the floor from S0's own solve, χ² from I
- [x] Tests: Ω·I equals `evaluate` to 1e-14 at ten random moves on NAC and on FAP; a wrong Ω fails; the three refusals
- [x] Skill: none until a public entry exists
- [x] `from_pawley`'s "poor" refusal reads `result.usable` instead of its own
      Rwp test; a test refuses a converged extraction that carries an
      error-level diagnostic (set 2026-10-01; done 2026-10-03)

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_solve_cost.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- David (2004), *J. Appl. Cryst.* 37, 621: equivalence of the Rietveld and correlated-intensity costs (cited for the concept; abstract read only).
- Spillman & Shankland (2021), *CrystEngCommun* 23, 6481 (GALLOP is GPL-3: concepts only).
- Issue #562; WP-1515.

## Handover log

### 2026-10-03 — the last task, and closed

A structure trial can now be scored against an extraction without a pattern
evaluation, and the extraction it is built from must be one the package itself
calls usable. That last rule is what this session added: `from_pawley`
refuses any converged extraction carrying an error-level diagnostic, rather
than re-testing one code's Rwp threshold. Today the two agree; a future
error-level code now refuses with no edit here.

*Done* (a cleanup session over unowned in-flight WPs). `from_pawley` reads
`result.usable` and names the error-level codes it found; the
`MODEL_FAR_FROM_DATA_RWP` import is gone. One test added,
`test_refuses_a_converged_extraction_carrying_any_error_level_code`, which
injects an invented error-level code. *Measured* (`[dev]`, macOS arm64):
`tests/test_solve_cost.py` 31 passed, 30 before. *Inherited, consumed.* The
WP-1904 reservation (#562's Wyckoff-class enumeration) is forwarded to
WP-1515, which scopes this milestone. The WP-1541 note asked whether any other
solve-cost test on a flat pattern reads the sign or size of `b`: none does.
The three others on `_flat(...)` assert refusal reasons and counts. Nothing
depends on 1902 in a `Depends on:` line. Narrative moved to the v1.7 record.

*Review* (2026-10-04, `/code-review high`): one finding, declined. With the
Rwp bar gone, a result over Rwp 0.8 that carries no error-level diagnostic is
accepted. A result's diagnostics are part of its record, so a reopened one
keeps `MODEL_FAR_FROM_DATA`; only a hand-edited result loses it, and the
2026-10-01 decision made `usable` the one bar.

### 2026-10-01 (3rd session) — the two silent absences refuse by name

The solve cost now refuses the two kinds of reflection it used to leave out
without saying so. `ExtractionRefused` gains `"satellite"` (any phase with a
satellite inside the fitted range, in both nuisance modes) and
`"secondary_line_only"` (under `nuisance="pawley"`, a nuisance reflection only a
λ/n line reaches). Each message names the phase, the count and the first five
reflections. *Done:* PR #648 (`f345ba66`), merged as `9ee59304` by `/pr-review`.
These are the two refusals the 2026-10-01 entry below left for the
contributor's own PR. The review accepted one widening: the satellite refusal
covers a `"scale"` nuisance phase too, because its Rietveld column is also zero
at a satellite. The check reads only frozen state, so an accepted case's arrays
are byte-identical (the contributor's seven cases). *Next:* unchanged, the
"poor" refusal reading `RefinementResult.usable`.

### 2026-10-01 (2nd session) — the "poor" bar set

"A poor extraction" now has a meaning: a fit the package itself calls unusable,
`not result.usable` (WP-1336). That is the converged check plus every
error-level diagnostic. Today it gives the same answer as PR #580's own test,
because `MODEL_FAR_FROM_DATA` at Rwp > 0.8 is the only error-level code the
refinement path emits. The difference comes later: an error-level code added
after today refuses an extraction with no edit here, where the current test
keeps its own copy of one threshold. No tighter quality bar is set, because none
has been measured on public data, which is the reason `from_pawley`'s docstring
already gives. The engine WPs that read this cost should measure one before
they assume one. Set at the maintainer's request in a `/pr-review` session.
*Next:* the new task, a one-line change in `from_pawley` and its test.

- **2026-10-01** — The solve cost is on `main`. `solve/cost.py` turns a Le Bail or
  Pawley extraction into a quadratic form in the reflection intensities, so a
  structure trial is scored without a pattern evaluation. The doublet spike came
  first and showed multi-line data needs no refusal. *Done:* PR #580
  (`4ab339f7`), merged as `604a5bb7` by `/pr-review` after two review rounds.
  *Measured* by the contributor: Ω·I against `evaluate` at ten random moves,
  2.8e-16 on NAC and 3.6e-16 on FAP. The doublet error the review predicted is
  real (2.6e-3 on FAP) and arises only when Ω is built on a Le Bail or Pawley
  compile, which this cost does not do. *Gotchas* from the review: the nuisance
  pseudo-inverse is equilibrated through `column_rescale`, because an impurity's
  stored scale otherwise set the cutoff for the background columns (χ² ×37 at a
  stored scale of 1e4). `nuisance="scale"` takes the impurity's atoms as
  declared, a Le Bail placeholder included. *Open:* the "poor" bar (review
  item 7) is the maintainer's to set here. Two refusals the contributor proposed
  are follow-ups for their own PR: a phase with `propagation_vector`, and a
  declared harmonic under `"pawley"`, both of which now drop out as absent.
  *Next:* the bar, then the engine chunks that read this cost.

- **2026-09-30** — created, from the 2026-09-30 issue triage (issue #562). No
  open WP owns it. The figures above are the review agent's scratch probes at
  `e3e6486a`, not yet reproduced in a session of this WP.
