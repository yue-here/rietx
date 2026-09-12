# WP-1103 — Sharp extra peaks: the second component member

Milestone: v1.4 · Status: ⬜
Depends on: WP-1102 (the component seam this member lands in)

## Goal

`PeakComponent` — user-declared sharp pseudo-Voigt peaks the phases cannot
model (a sample holder at a different specimen distance, an unidentified
sharp impurity) — so overlapping channels stay in the fit instead of being
excluded along with the sample peaks under them. The package recommends
through evidence and never refuses or gates; the operando good-unit-cells
use is the design case.

## Context

- **The design case.** An operando series where the user wants unit-cell
  trajectories to demonstrate a phenomenon: strong holder reflections from a
  mount at its own specimen distance overlap sample peaks, no phase at the
  right geometry can model them, and `excluded_regions` would also mask the
  sample peaks underneath. The user knows what they are doing; the package's
  job is honest evidence, not a gate ("agent-first" thesis: report evidence,
  never refuse).
- **`PeakComponent` joins the `ExtraComponent` union** — a closed-vocabulary
  member addition per [1102](1102-component-seam-humps.md)'s contract, moot
  while both land inside the same 1.1.0 release. Not a phase kind (TOPAS
  `xo_Is`): `Phase` is crystallographic through and through, and a cell-less
  phase breaks every consumer; the seam gives the power without the schema
  violence.
- **Fields**: `kind: Literal["peak"]`; `label: str | None` (rendered in
  diagnostics, not a Parameter); `center` (Parameter, deg 2θ — the
  **apparent** primary-line position: no zero_shift, no displacement
  corrections, because the holder sits at its own distance and its
  aberrations are its own, absorbed into the free center; the docstring says
  so); `area` (Parameter, counts·deg — **never named `scale`**:
  `refine.mode_fixed_path` force-fixes `*.scale` under lebail/pawley and
  peak components must stay refinable there); `fwhm` (Parameter, deg);
  `eta` ([0, 1], default 0.5); `all_lines: bool = True`. Validators:
  `center` and `fwhm` must carry finite min/max — they size the frozen
  window, and the refusal message suggests a default — and
  `fwhm.min ≥ EXTRA_PEAK_FWHM_MIN = 0.005` (pole guard only; sharp is the
  point here). All `vary=False` by default.
- **Emission lines: all of them by default.** The holder diffracts the same
  source, so its Kα2 is physically present: Bragg-law splitting from the
  apparent center, per-line weight × Lp intensity ratios — `peakfit`'s
  measured precedent (holding the bare weight biased the fitted Kα1 by
  −2e-4° and −0.26 mean σ pull), and `CompiledModel._peak_terms` already has
  the machinery. `all_lines=False` covers non-diffraction artifacts
  (fluorescence, detector). No FCJ: the holder's axial geometry is not the
  specimen's; the symmetric pV is the honest simple model.
- **Frozen windows sized from bounds, not values.** Per (line, peak), the
  window spans the line's Bragg image of `[center.min, center.max]` widened
  by `30·fwhm.max + 0.3°` — the phase-window rule with the bound in place of
  the compile-time width — so a free center stays inside its frozen window
  by construction, and the frozen-per-stage invariant
  ([../DESIGN.md](../DESIGN.md#architecture-invariants)) holds with no
  `free_paths=` plumbing. A window containing zero fitted channels is
  refused at compile, naming the peak: a dead-column refusal (the
  `check_interval` sentence shape), not an expertise gate.
- **Le Bail / Pawley: subtraction side, never the denominator.** The
  component curve joins the background subtraction at both seams
  (`lebail_update`, `structure_intensity_partition`) per 1102's member
  contract — denominator membership would hand phases shares of holder
  counts. Peak components stay refinable under lebail (`mode_fixed_path`
  matches `.atoms.`, `*.scale`, `.source.lines.` only).
- **Jacobian**: unknown paths fall to the whole-model FD column (data rows
  only — exact, no penalty rows); analytic columns out of scope (1102's
  stance). `tests/test_cross_backend.py` gains a peak-component CONFIGS row.
- **Ticks.** The sole builder (`refine._build_result`) gains one reserved
  key `"(extra)"` carrying every line's positions for every peak component,
  so Layer 0's `unmatched_obs` stops flagging declared peaks as unindexed
  impurities — the Kα2-ticks lesson one rank over. A phase actually named
  `"(extra)"` is refused at fit build (parenthesized names are no CIF's).
  Accepted wrinkle, recorded here: Layer 0's `Region.n_reflections` counts
  ticks, so `"(extra)"` ticks inflate that count in their regions — right
  for segmentation and unmatched logic, mislabeled as a count; noted rather
  than special-cased.
- **Presets never free them** (no stage glob matches the
  `instrument.extra_components.` prefix — 1102's pin, extended to this
  member). Freeing is the caller's explicit act; the cumulative-stages
  recipe and its stage-1 caveat are 1102's Context, restated in this WP's
  manual section. Adding or removing a component is a model edit →
  `Refinement.edit` ([1035](1035-symmetry-surfaced.md): builds the proposed
  table, refuses rather than records); the schema validators carry the
  refusals; overlapping windows are fine by design.
- **Statistics and evidence** (recommend, never refuse): `n_free` is
  automatic (table paths); `effective_observations` counts reflections —
  peak components add none, stated in the manual. `EXTRA_PEAK_ON_REFLECTION`
  fires when a component sits within Layer 0's match tolerance (0.08°, the
  same constant) of a phase's predicted position: it may be absorbing model
  misfit — the honest warning for the impurity-shortcut use.
  `extra_peak_absorption`: block projection R² of structural columns onto
  the component span (reusing `block_projection_r2`), carried as a defaulted
  FitReport field **evidence-only at first** — the 0.25 background threshold
  was measured for background blocks (0.01–0.03 vs 0.46 separation) and
  nothing has measured component blocks, so no firing threshold ships until
  this WP's acceptance measurement supplies one (record the measured
  separation either way). `at_bound`/`HIGH_CORRELATION` guards work
  unchanged. `../AGENT_PROTOCOL.md` §7 rows for both codes + a §3 degeneracy
  line ("an extra peak on a reflection is a scale/intensity degeneracy by
  construction").
- **Sequential / operando recipe** (document in the manual, beside
  `using/series.md`): `carry=["*"]` warm-starts components per pattern —
  holder area/position trajectories come free; excluding
  `instrument.extra_components.*` from carry pins them to the initial model,
  a fixed holder ([1051](1051-sequential-escalation.md)/[1016](1016-sequential-series-panel.md)
  carry semantics). Esd honesty, stated once: the package reports what it
  measured; the writeup owns the claim.
- GUI: parameter rows and the `.rxt` instrument block render for free
  (whole-table rule); no model editor (Non-goal) — a python/agent feature
  first. Manual: Part 1 in `using/model.md` (declaration, freeing, lebail
  behavior, the operando recipe); Part 2 equation in
  `../manual/profiles.md` (peak-shaped, beside the TCHZ equations; 1102's
  hump equation lives in `background.md`) with a `*Source:*` line.
  Capabilities: the seam key landed in 1102; no second key. Release-notes
  line.

## Non-goals

- Auto-detection of extra peaks, or any refusal/approval gate on declaring
  them — evidence only.
- FCJ asymmetry, per-component profile shapes beyond pV, restraints between
  components.
- A compare variant: no standard carries holder peaks, so a variant row
  would measure nothing on every standard — a justified skip of the "add a
  row" rule, recorded here.
- A GUI editor; `.rxt` model-item addition.
- d-spacing / phase-ID interpretation of component positions
  ([1101](1101-standalone-peak-fitting.md) and indexing territory).

## Tasks

- [ ] Schema: `PeakComponent` + validators (finite center/fwhm bounds with a
      suggesting refusal, `EXTRA_PEAK_FWHM_MIN`); JSON round-trip;
      release-notes line.
- [ ] Forward model: windows-from-bounds + all-lines evaluation
      (weight × Lp) + empty-window refusal; frozen-window test — a center
      freed to its bound stays inside its window.
- [ ] Le Bail/Pawley: unbiased-extraction test (a declared synthetic holder
      line leaves extracted phase intensities unbiased) + lebail-refinable
      test + multi-histogram `SharingMap` test.
- [ ] Jacobian: FD assertion + cross-backend CONFIGS row.
- [ ] Ticks `"(extra)"` + the phase-name collision refusal + the Layer 0
      unmatched-obs test.
- [ ] Evidence: `EXTRA_PEAK_ON_REFLECTION` + `extra_peak_absorption`
      (evidence-only; threshold only if the acceptance measurement supplies
      one) + FitReport carry + `../AGENT_PROTOCOL.md` rows.
- [ ] Manual (`using/model.md` + operando recipe + `profiles.md` equation
      with `*Source:*`) + api-surface documentation + the preset-non-freeing
      pin extended to this member.
- [ ] Acceptance measurement + tests: inject two overlapping holder pV
      doublet lines into a standard fixture — the refined cell with declared
      components lands within tolerance of the clean-pattern cell; quote
      (not gate) the excluded-regions alternative's cell and lost-channel
      count; measure the component-block absorption separation; obs/calc/diff
      PNGs to `tests/output/`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_extra_components.py tests/test_cross_backend.py tests/test_sequential.py tests/test_capabilities.py tests/test_manual.py tests/test_manual_api.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
```

## References

- McCusker, Von Dreele, Cox, Louër & Scardi (1999), J. Appl. Cryst. 32, 36 —
  the impurity-handling guidance this WP deliberately extends past, with
  evidence in place of refusal.
- `indexing/peakfit.py`'s measured Lp-weight bias (restated in Context).
- TOPAS `xo_Is` as prior art — concept only (closed source).
- [1035](1035-symmetry-surfaced.md) (edit refuses, never records),
  [1051](1051-sequential-escalation.md) / [1016](1016-sequential-series-panel.md)
  (sequential carry semantics).

### Inherited

**From WP-1101 (2026-09-13) — v1.4 is open, and three things it built are
yours to reuse rather than rebuild.**

The milestone opened on 2026-09-13 (`pyproject.version` → `1.4.0.dev0`,
[`milestones/v1.4.md`](../milestones/v1.4.md)). **Your acceptance row in that
record is deliberately unfinished**: it says only what `../ROADMAP.md` already
commits to, and is marked for sharpening at your open, because a bar written by
a session that has not read this WP is a bar set too low. Sharpening it is the
first act of the session that starts here — before the work, not after it.

Three seams 1101 left behind:

* `indexing.peaks.window_indices` and `group_at` are now the **one** window
  sizing — detection, the GUI peak editor and `fit_peaks` all go through them,
  and `group_at` carries the refusals a *given* position needs (off the end of
  the pattern, in a gap).
* `peakfit.reseed_candidate` is the one authority for "does this window hold a
  component that is not declared?" — the residual proposes a position and ΔBIC
  decides. `fit_group` walks it; `fit_peaks` asks it once. It is what a
  component seam should ask rather than measuring seed distances, which 1101
  tried first and which stayed silent on a 26-esd bias.
* `rx.fit_peaks(data, instrument, positions)` fits named peaks with no model at
  all. It is the *measurement* half of the same question this WP models, so a
  component's declared position can be checked against a free fit of the same
  window without building a refinement.

One mechanical cost, if this WP adds a `PeakFlag` member: it is a four-surface
edit — the schema `Literal`, `help.py`, `gui/src/lib/rxt.ts`'s `PEAK_FLAGS`,
and the committed `tests/data/gui/help_keys.json` — and touching `gui/src`
means `npm --prefix gui ci && npm --prefix gui run build`, because the dist
digest covers it.


**From WP-1110 item 14 (2026-08-21) — a declared component that is not in the
specimen has an unidentifiable position, and this is now measurable.**

A `PeakComponent` a user declares for a sharp impurity that turns out not to be
present will refine to no intensity. A peak reaches the pattern only through
`intensity × profile`, so at that point nothing constrains its **position**
either — it is the zero-scale phase of WP-1110 item 13, one rank down. Until
this session the covariance hid that: `pinv` cut eigenvalues at
`rcond × |λ|max`, so the flat direction came back at *zero* variance and the
position read as precisely measured. It is now equilibrated, so such a
parameter reports **no** esd rather than a small one.

Two things follow for this WP, which says it "recommends through evidence and
never refuses or gates". The evidence for "this component is not needed" is now
*available* and is the honest one — an absent esd on its position, not an Rwp
comparison. And the peak-list side already chose a vocabulary for the same
fact, `no_intensity` in `PEAK_UNUSABLE_FLAGS`; reuse the wording rather than
inventing a second one, and reuse `strategy.staged.BOUND_HIT_RTOL` for the "at
its zero bound" test, which is the one place that question is answered.

## Handover log

- **2026-08-18** — created from the single-peak planning session; numbering
  opens the 11xx block (v1.1). Second member of
  [1102](1102-component-seam-humps.md)'s seam; the two were designed
  together and the member contract is stated there.
