# WP-1901 — the difference-Fourier map: a missing atom shows as a peak

Milestone: structure-solution · Status: 🔄 2026-11-16 — first slice in PR #1613; two test bars wait on a ruling
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
- The tier of each rule this WP adds (written 2026-11-16, at the first
  slice): the synthesis, the no-aliasing grid floor, the Friedel-averaged
  phase and the omitted F(000) are physics or arithmetic (1). The
  significance is height over the map's rms, a reported statistic that no
  code acts on (2: the map rms is the residual-density statistic the CIF
  core records). The default grid of d_min/3 and the one-grid-spacing orbit
  merge are ours (3), measured on 11-BM NAC alone and untested beyond it;
  the merge leaves a count, `FourierMap.n_merged`. No threshold is applied.

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

- **2026-11-16** — first slice, PR #1613 (ghostshift runner). A
  converged Rietveld fit now gives its observed and difference Fourier maps,
  with every peak and hole listed by significance and by the nearest model
  atom. On the public 11-BM NAC pattern, taking out Al1, Na1 or F3 and
  refitting puts the missing atom at the top of the difference map, above
  anything the complete model's own map holds. Two of the WP's bars do not
  hold as written: the peak lands 0.11-0.12 Å from Na1 and F3 (the bar is
  0.10 Å), and the complete model's map has peaks to 4.9σ of its rms, so
  "no peak above 3σ" is false. Those are physics calls, left to the user
  and the maintainer; the tests assert what the data support meanwhile.
  - *Done:* `structure_factor.structure_factors_ab`, the public (A, B) pair.
    `solve/fourier.py`: `fourier_maps(refinement, phase)` and
    `fourier_maps_from_model`, returning `FourierMaps` (two `FourierMap`s,
    each with its grid, rms σ, unthresholded peaks and holes as `MapPeak`s,
    and `n_merged`), plus d_min, the drawn grid step, reflection counts,
    units (e/Å³ or fm/Å³), the phase convention and the caveats, model bias
    first. Le Bail/Pawley, magnetic and modulated phases are refused.
    `tests/test_fourier_map.py`: 7 fast (self-partition ΔF ≡ 0 and six
    observed sites; NAC minus Na1 with no refit; a LaMnO₃ mirror-split peak;
    the f″ path at Cu Kα; two refusals; FFT sizes) and 4 slow (refitted NAC).
    `rietx.solve` is untouched apart from the new module: its `__init__`
    docstring, which lists the modules, is in #1262's diff and gains a line
    for this one after that PR lands.
  - *Measured* (11-BM NAC protocol of `test_acceptance_nac.py`, `[dev]`
    venv, darwin/arm64, default grid 32³ at d_min 0.977 Å; distances to the
    removed site over all its images):

    | removed | Rwp | top ΔF peak | σ (rms) | distance |
    |---|---|---|---|---|
    | none | 0.093 | 1.11 e/Å³ at (½, ¼, 0.253), 1.92 Å from F2 | 4.91 | — |
    | Al1 (8a) | 0.410 | 5.42 e/Å³ | 6.7 | 0.008 Å |
    | Na1 (8a) | 0.341 | 3.27 e/Å³ | 5.29 | 0.119 Å (0.125 at a 0.15 Å step, 0.093 at 0.08 Å) |
    | F3 (8a) | 0.347 | 4.07 e/Å³ | 6.8 | 0.110 Å (0.128 at 0.15 Å) |
    | F1 (24c) | 0.563 | top peak on Ca1; F1 is the 4th, 0.050 Å | 5.9 | — |
    | F2 (24c) | — | top peak 0.32 Å from Ca1; F2 is the 6th, 0.33 Å | 5.9 | — |
    | Ca1 (12b) | — | top peak 0.22 Å from the site | 7.6 | 0.22 Å |

    The complete model's map has six peaks above 3σ. Its observed map's
    six highest maxima are the six sites, within 0.079 Å. Without the Biso
    stage every removed atom ranks below peaks on atoms already present,
    because the scale absorbs the missing density (McCusker 1999 §6 says
    to scale on the part the partial model explains). Each NAC fit takes
    about 1.4 s, Le Bail included, and each map pair under 1.5 s.
  - *Review:* a read-only reviewer found that a strict 26-neighbour test
    drops an atom whose peak a mirror splits evenly between two grid points
    (LaMnO₃ La1 on a 54-point b axis): fixed with a tie-break and pinned by
    a test that fails without it. It also corrected the f″ phase bound to
    asin(|B|/|A|) and removed a test assertion that could not fail. The
    generality review: grid default *weak* (no step-error bar on an oblique
    cell), significance *holds*, orbit merge *weak* (radius follows the
    grid; `n_merged` added in answer), f″ convention *holds* after the bound
    fix, F(000) *holds*, refusals *hold*.
  - *Questions for the user and the maintainer:* (1) is 0.10 Å the bar,
    given 0.11-0.12 Å for Na1 and F3 at d_min 0.98 Å, or should it scale
    with d_min? (2) "the intact model has no peak above the threshold": with
    σ the map rms the complete model reaches 4.9σ, so either the threshold
    rises, σ becomes a counting-statistics esd propagated through the
    partition (an edit to `model/forward.py`), or the clause becomes the
    comparison the tests assert now (the missing atom's peak above every
    peak of the complete model's map).
  - *Next:* the rulings above, then the task line's remainder; then the
    GUI panel WP from `### Inherited` (still true: grid, σ and peaks are
    public returns) when this one closes.
- **2026-09-30** — created, from the 2026-09-30 issue triage (issues #562,
  #197). No open WP owns it.
