# WP-0308 — Multi-histogram stacked residuals

Milestone: v0.3 · Status: ⬜ not started
Depends on: —

## Goal

Refine one structural model against several patterns at once (different
instruments, wavelengths, or temperatures) with an explicit parameter-sharing
map, exercised end to end.

## Context

The API surface already accepts lists — this WP makes that real rather than
nominal. Start by auditing exactly how far list support currently goes in
[`refine.py`](../../src/pxrdref/refine.py) and
[`optimize/least_squares.py`](../../src/pxrdref/optimize/least_squares.py)
before designing anything.

The mechanics: each histogram contributes its own residual block (its own
background, scale, profile terms, and 2θ range); the blocks are stacked into
one residual vector and one Jacobian, with shared parameters (cell,
coordinates, occupancies, ADPs) contributing to every block's columns. This is
the same "extra rows in the residual" pattern the penalized P-spline already
uses for its √λ·D₂·c penalty rows — read
[`background/models.py`](../../src/pxrdref/background/models.py) and the
statistics handling in
[`optimize/statistics.py`](../../src/pxrdref/optimize/statistics.py) first,
because that code already faced the "which rows count for statistics" question
and answered it (penalty rows are excluded from Rwp/Durbin-Watson/
Bérar-Lelann but kept in the covariance).

Decisions this WP must make and document:

- **Statistics reporting**: a combined Rwp plus per-histogram Rwp. A single
  pooled number hides a badly-fitting histogram, which is exactly the failure
  mode this package's whole reporting design exists to prevent. Per-histogram
  numbers are not optional.
- **Weighting between histograms**: whether a histogram carries a relative
  weight, and what the default is. Default to unit weight (each point's own
  esd governs) and make any deviation explicit and recorded in provenance —
  silent inter-histogram weighting is a reproducibility hazard.
- **Parameter-sharing map**: dot-paths gain a histogram scope for the
  per-histogram terms. Keep fnmatch glob semantics working (CLAUDE.md: no
  brackets in paths — fnmatch treats `[..]` as a character class).
- **Frozen-per-stage discreteness applies per histogram**: each gets its own
  frozen hkl list, windows and FCJ node counts at stage compile.

History and FitReport both need to cope: a node's `RefinementState` currently
carries one `two_theta_limits`, and the report's regions are per-pattern.
Decide and record whether reports are per-histogram (recommended) and how a
multi-histogram node serializes.

## Design (audit + decisions — 2026-07-24)

**Audit — how far list support goes today.** None, for histograms. The only
lists in the fitting surface are `Structure.phases` (multi-*phase*, one pattern)
and `Source.lines` (multi-*wavelength*, one pattern). `refine.py`,
`optimize/least_squares.py`, `model/forward.py`, `params/vector.py` all take a
single `PatternData` + single `Instrument`. `RefinementState` carries one
`two_theta_limits`; `RefinementTree` fingerprints exactly one pattern. So this
is built fresh, reusing the per-pattern primitives (`compile_model`,
`_make_residual`/`_make_jacobian`, `compute_statistics`, `covariance_estimates`,
`compute_qpa`, `check_guards`) unchanged.

**Architecture: one shared `Structure` + N `Instrument`s; one
`CompiledModel`+`ParameterTable` per histogram; stacked residual/Jacobian over a
single combined θ.** Each histogram compiles its own model (⇒ per-histogram
frozen hkl list / windows / FCJ node counts, the invariant, for free). A
`MultiParameterTable` (`params/multi.py`) owns the N tables and a column map
that folds *shared* structural columns to one combined column while giving each
*per-histogram* column its own.

**Sharing map.** Default rule: a free path is **per-histogram** iff it starts
with `instrument.` **or** ends with `.scale` (incident flux × illuminated
volume differ per measurement). Everything else under `phases.*` (cell, coords,
occ, ADP/biso, size/strain, extinction, preferred_orientation) is **shared** —
one specimen, one crystal. Overridable per glob (`SharingMap.per_histogram` /
`.shared`), fnmatch-compatible, no brackets. Rationale: the instrument-vs-sample
split this package already draws (resolution U V W X Y in `Instrument`, sample
size/strain in `Phase`) *is* the shared/per-histogram split.

**Histogram-scoped dot-paths.** Per-histogram paths are reported and freed as
`hist.{h}.{path}` (`hist.0.instrument.zero_shift`, `hist.1.phases.0.scale`);
shared paths stay unscoped (`phases.0.cell.a`). A turn-on glob `G` frees a path
`P` when `fnmatch(P, G)` on either the scoped **or** unscoped form — so every
existing plan (`phases.*.scale`, `instrument.background.*`) frees all
histograms' copies unchanged, and a scoped glob (`hist.1.*`) targets one.

**Stacked residual/Jacobian.** Combined rows = [all histograms' *data* rows]
then [all histograms' *background-penalty* rows], so `covariance_estimates(...,
n_data=N_data)` (its "first N_data rows are data" contract) is reused verbatim
for χ²/Bérar-Lelann. For histogram `h`, `J_h` from the existing per-histogram
Jacobian is scattered by the column map: a shared column lands in the one shared
combined column (disjoint rows per histogram ⇒ no collision), a per-histogram
column in `h`'s own. This is exactly the "extra rows in the residual" pattern the
P-spline penalty already uses.

**Statistics.** Per-histogram Rwp/Rp/DW/rwp_bs (independent of N_free — the
headline numbers, never optional) computed on each histogram's own data via
`compute_statistics`. Top-level `RefinementResult.statistics` = the pooled
combined fit (n_free = combined column count) — reported but never alone, since
pooling hides a bad histogram (per-hist n_free for a joint fit is genuinely
ambiguous, so per-hist χ²/Rexp uses `shared + own` free counts and is documented
as conservative). New `HistogramResult` schema carries each histogram's arrays,
ticks, statistics, qpa, diagnostics; `RefinementResult.histograms` is `[]` for
single-histogram fits (backward compatible). `result.for_histogram(h)` returns a
Layer-0-ready `RefinementResult` view ⇒ **reports are per-histogram**.

**Weighting.** Default unit weight — each point's own esd governs. An optional
per-histogram scalar `w_h` multiplies that histogram's residual **and** its
penalty rows by `√w_h` (keeps the background prior's relative strength fixed);
recorded in `Provenance.notes["histogram_weights"]`. Any deviation from unit is
explicit and in provenance — silent inter-histogram weighting is a repro hazard.

**Restriction.** Rietveld mode only. Le Bail / Pawley intensities are
per-pattern empirical extractions, not shared across histograms, so a
multi-histogram Le Bail is just independent single fits — not the joint-residual
point of this WP. The driver raises `NotImplementedError` for those modes.

**History serialization — decision.** The branching DAG (`RefinementTree`)
fingerprints one pattern; extending it to N is a deeper change than this WP
warrants. Decision: multi-histogram fits run **without** the per-stage DAG
(like the functional `refine`, history off), and the *result* is what persists —
`RefinementResult` (with `histograms`) already JSON round-trips, so the full
per-histogram state is serializable and reloadable. A multi-pattern DAG is a
documented future seam (noted in DESIGN.md), not a v0.3 deliverable.

## Non-goals

- Sequential/in-situ series with warm start (WP-0505) — that is many *separate*
  refinements chained, not one joint residual.
- Neutron/TOF histograms (v2 fence); this is multiple CW X-ray patterns.
- `vmap`-batched series (v2).

## Tasks

- [x] Audit and document what list support exists today; write the sharing-map
      design into this file before coding
- [ ] Stacked residual + Jacobian across histograms, per-histogram frozen
      compile state
- [ ] Per-histogram *and* combined statistics; provenance records the weighting
- [ ] Parameter-sharing map with histogram-scoped dot-paths, fnmatch-compatible
- [ ] History serialization for multi-histogram state; FitReport per histogram
- [ ] Tests: two synthetic patterns of the same phase at different wavelengths
      recover the shared cell better than either alone; a deliberately
      bad second histogram shows up in its own Rwp rather than being masked
- [ ] PNGs per histogram to `tests/output/`

## Acceptance

Joint refinement of two synthetic histograms of one phase recovers the shared
cell within esds, with per-histogram Rwp reported separately; a deliberately
mis-scaled histogram is visible in its own Rwp.

```sh
.venv/bin/python -m pytest tests/test_multi_histogram.py -q
```

## References

- Von Dreele (1997) J. Appl. Cryst. 30, 517 — multi-histogram Rietveld
  practice (GSAS lineage).

## Handover log

- **2026-07-22** — created from the ROADMAP split; not started.
