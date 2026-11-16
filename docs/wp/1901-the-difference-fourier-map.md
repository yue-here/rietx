# WP-1901 — the difference-Fourier map: a missing atom shows as a peak

Milestone: structure-solution · Status: 🔄 2026-11-16 — claimed by @mustachefeeling
Depends on: —
Priority: P3 2026-09-30 — a view over what a converged fit already knows, and the first user-visible rung of the structure-solution milestone

## Goal

`solve/fourier.py` computes an observed and a difference electron-density map
from a converged Rietveld fit and lists its peaks with a significance. A phase
missing one atom shows that atom as the top difference peak.

## Context

Scoped in issue #562 (chunk S1) and WP-1515, reviewed adversarially on
2026-09-30. #197 leaves the fence with direct-space solution (decided
2026-09-30, `docs/DESIGN.md` § Structure fence revised). **Maximum-entropy maps
stay fenced.**

Amendments from the review:

- **A free function, not a `Refinement` method.** `refine.py` is busy with v1.6
  (PR #546 edits it) and the issue's own note calls it so. A method can follow.
- **The public test is NAC with one atom removed**, single line and public
  (`tests/data/11BM_NAC.fxye`). The proposal's PbSO₄ case needs a `.gpx` that is
  not vendored.
- `crystallography/structure_factor.py` has `_structure_factors_ab` (line 285 on
  `4de25284`, re-find it); the phase list is what a map needs, so a small public
  alias is the one edit outside `solve/`. Check that no v1.6 PR touches it.
- **State the phase convention when f″ ≠ 0**: A against A + iB. The package
  returns the Friedel average (root CLAUDE.md § anomalous scattering).
- Carry `structure_intensity_partition`'s documented model bias into every map
  record, and never let the map be the evidence of its own fit (a model-biased
  map flatters the model that partitioned it).

### Inherited

- **2026-10-02, from the issue triage (issue #653): the GUI panel this WP
  fences out has a written proposal.** It draws the maps this WP computes in
  the structure viewer and in `render_structure`: ΔF isosurfaces at ±nσ with
  a slider in σ units, the peak list as linked markers, a slice plane, the
  structure's own extent rules, and the map's caveats on screen (model bias,
  d_min and completeness, negative nuclear density being real for negative-b
  species). The package computes the mesh and the browser draws triangles,
  per WP-1015's rule; mesh against a ~1 MB 64³ grid is to be measured. It is
  **not this WP's scope**, and nothing here changes. It reaches this WP in one
  place: the map's grid, σ and peak list are the inputs the panel would read,
  so keep them a public return rather than a private intermediate. File the
  panel as its own WP when this one closes, from #653's text.

## Non-goals

- Charge flipping, direct space, the cost function (WP-1902 and later).
- A GUI panel, a skill reference, a capabilities flag.

## Tasks

- [x] `solve/fourier.py`: F_obs and F_calc maps from a fit, peak picking, a significance in σ of the map
- [x] The alias in `structure_factor.py`
- [ ] Tests: NAC minus one atom puts the top ΔF peak within 0.10 Å of the removed site and above 3σ; the intact model has no peak above the threshold; the observed map has NAC's six maxima at the six sites
  — **2026-11-16, landed in part** (`tests/test_fourier_map.py`): the six
  observed maxima, and NAC minus Na1, F3 or Al1 putting the top ΔF peak
  nearest the removed site, above 3σ and above the complete model's top
  peak. Two clauses do not hold as written and wait on a ruling (handover
  entry): the 0.10 Å bar holds for Al1 (0.008 Å) but not Na1 (0.119 Å) or
  F3 (0.110 Å), and the complete model's map has peaks to 4.9σ of its rms.
- [x] Skill: a routing row only if it ships a public entry point, otherwise none — none: `rietx.solve` exports nothing from `rietx` yet (2026-11-16)

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_fourier_map.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #562, #197; WP-1515; `docs/DESIGN.md` § Structure fence revised.

## Handover log

- **2026-09-30** — created, from the 2026-09-30 issue triage (issues #562,
  #197). No open WP owns it.
