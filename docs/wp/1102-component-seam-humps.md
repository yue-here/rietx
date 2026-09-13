# WP-1102 — The additive component seam, and broad humps as its first member

Milestone: v1.4 · Status: ⬜
Depends on: — (independent of 1101; [1103](1103-peak-components.md) lands its
second member in this seam)

## Goal

`Instrument.extra_components` — a discriminated union of declared parametric
components added to the calculated pattern, this package's serializable,
differentiable, agent-visible answer to TOPAS's `fit_obj` — with
`HumpComponent` (a broad pseudo-Voigt: amorphous humps, very broad
impurities) as its first member. A hump refines center/fwhm/area/eta with
esds and reports an **area, never a weight fraction**.

## Context

- **Why a union seam and not two ad-hoc features.** A hump and a sharp extra
  peak ([1103](1103-peak-components.md)) are the same mathematical object —
  `area · pseudo_voigt(tt − center, fwhm, eta)`
  (`model/profiles/pseudovoigt.py`, unit-area, xp ops) — differing only in
  which aggregates they join. One extensible seam (the `Background`-union /
  backend-registry pattern) means a future shape (exponential tail, Debye
  amorphous term, split-pV) is one member + one evaluator + one cross-backend
  row. TOPAS prior art, concepts only (closed source): `fit_obj` is the
  capability; its *textual* form is not portable here — see the fence below.
- **The seam.** `ExtraComponent = HumpComponent` union alias (bare PEP-604 +
  `kind` Literals, the `Background` precedent in `schemas/instrument.py`);
  `Instrument.extra_components: list[ExtraComponent] = []`. An additive
  defaulted field — no `SCHEMA_VERSION` event (the events precedent) — and it
  rides `RefinementState` (which stores the full `Instrument`) into history,
  checkout and replay with nothing to add. Paths
  `instrument.extra_components.{i}.{field}`: matched by **no** preset glob
  (presets free `instrument.background.*`, the profile letters, zero,
  geometry singletons, line weights), so freeing is always the caller's
  explicit act — the microstrain "declared block, freed deliberately"
  precedent, pinned by test.
- **Freeing recipe — stages are cumulative** (`refine.py`: "stages are
  cumulative: start from everything the user left vary=True"). A
  `set_vary("instrument.extra_components.*", True)` before a preset run
  survives the plan — but the components are then free from stage 1
  (scale_bkg) onward, the unseeded-early-freeing failure mode. The
  recommended route, documented in the manual, is a custom plan appending a
  late `Stage("humps", ["instrument.extra_components.*"])`;
  `Stage.seed`/`seed_softplus` already exist to lift a softplus `area` off
  the zero floor in that stage. State both facts in the manual.
- **The member contract** (goes in the union's docstring; every future member
  obeys it): (1) an xp-ops evaluator, whole-grid or frozen-window; (2) every
  member's curve is subtracted from the Le Bail partition net
  (`CompiledModel.lebail_update` and `structure_intensity_partition` — else
  phases are handed shares of component counts); (3) each member declares its
  aggregate memberships — a hump joins the *reported background*
  (`result.y_background`, `BackgroundEvidence`, the absorption span); a peak
  ([1103](1103-peak-components.md)) joins ticks instead; (4) a new member is
  an evaluator + a cross-backend CONFIGS row + a manual equation with
  `*Source:*`, **and is itself a schema closed-vocabulary event** (moot for
  1103 while both land inside the same 1.1.0 release, but stated so a third
  member is not assumed free).
- **The fence, with grounds**: arbitrary callables or an expression DSL
  (`fit_obj` proper) violate three invariants at once — history stores state,
  not code; the traced twin must differentiate the same expression on
  jax/torch; the agent surface is JSON schemas under `extra="forbid"`. TOPAS
  can do textual fit_obj because its equation text *is* its serialization
  format. An expression-DSL member is v2+ material if ever. Not a phase kind
  (TOPAS `xo_Is`) either: `Phase` is crystallographic through and through
  (cell ties, Wyckoff, QPA) and a cell-less phase breaks every consumer.
- **`HumpComponent` fields**: `kind: Literal["hump"]`; `label: str | None`;
  `center` (Parameter, deg 2θ, apparent, required); `area` (Parameter,
  counts·deg, softplus min=0 is safe — zero is the off state); `fwhm`
  (Parameter, deg, default value=5.0, **hard floor `HUMP_FWHM_MIN = 0.1`** +
  reachability validator — the `MARCH_R_MIN` pattern, and for the same
  reason: the profile divides by Γ and a stored `min: 0.0` outlives the
  default); `eta` ([0, 1], default 0.5). All `vary=False` by default.
  Whole-grid evaluation, no windows — broad by declaration, O(n_points) per
  hump.
- **Never in the linear stack.** `bkg_paths` is hand-built at compile
  (`model/forward.py`) and a nonlinear path there gets a silently wrong exact
  Jacobian column (the background branch fires first on `path in bkg_cols`).
  Guard test: `set(bkg_paths) ∩ component paths == ∅` — `area` stays out too,
  one membership rule, no conditional. Jacobian: unknown paths fall to the
  whole-model FD column (data rows only — correct, components own no penalty
  rows; exact, FD decodes through C like the residual). Analytic columns via
  `pseudo_voigt_derivs` are deliberately out of scope: with ≤ ~10 such
  parameters the FD cost is ~10 residual evaluations per Jacobian, and the
  cross-backend agreement matrix is the correctness check.
- **Table wiring**: one authority helper `extra_component_parameters(comp)`
  (`model_fields` minus `kind`/`label` — the `roughness_parameters`
  precedent, `params/vector.py`) feeding **both** `_collect_instrument` and
  `apply_to_models` — a parameter registered in one and forgotten in the
  other silently loses its refined value at the next stage's recompile.
  Test exactly that.
- **Background-aggregate membership**: `result.y_background` gains hump
  curves (one authority — a model method consumed by `_build_result`, every
  renderer through it); `background_absorption`'s column selection
  generalizes from the hard `instrument.background.` prefix
  (`optimize/statistics.py`) to a model-declared background-block set that
  includes hump paths — the R² then measures what the *whole declared
  background* can imitate. Guard/diagnostic chain follows unchanged.
- **Evidence** (a new correction ships with a record field or a diagnostic,
  never an Rwp comparison): the hump rows in `result.parameters` — declared,
  refined, esds — are the record. New diagnostic `BACKGROUND_HUMP_SHARP`: a
  fitted fwhm approaching the instrumental predicted FWHM at its center is a
  crystalline peak being eaten, not a hump. Evidence, never refusal — and
  the width-ratio constant is **not invented up front**: thresholds are
  quoted from a paper or a measurement, never tuned, so the acceptance
  task's width-ladder measurement fixes it, provenance recorded beside it.
- `save_instrument_profile` strips `extra_components` (mount/specimen state,
  not goniometer constants — the roughness/µt precedent in
  `io/instrument_profile.py`).
- Untouched: the `Background` union and all its consumers,
  `background/auto.py`, `gui/imports.py`. GUI: the parameter panel and the
  `.rxt` instrument block render component rows for free (whole-table rule);
  no model editor (the P-spline precedent — it has none either).

## Non-goals

- Arbitrary callables / an expression DSL (fenced above, with grounds).
- A fourth `Background` union kind — humps compose with any base background
  from outside it.
- Amorphous / internal-standard QPA (v2 fence): a hump's quotable number is
  its area (counts·deg) with esd, never a fraction.
- Analytic Jacobian columns for component parameters.
- Preset stages that free components — freeing stays the caller's declared act.
- A GUI component editor.
- Sharp peaks ([1103](1103-peak-components.md)).

## Tasks

- [ ] Schema: `ExtraComponent` union + `HumpComponent` + `HUMP_FWHM_MIN` +
      reachability validator; JSON round-trip tests; release-notes line (the
      1.0.2 notes' "three background models now frozen" neighbourhood gets
      its amendment).
- [ ] Table wiring via `extra_component_parameters` feeding both collect and
      apply; test that refined hump values survive a stage recompile.
- [ ] Forward model: evaluator joins `evaluate()`; Le Bail / partition
      subtraction seams; `bkg_paths` disjointness guard test; test that a
      declared hump leaves Le Bail extracted phase intensities unbiased.
- [ ] Jacobian: FD-fallback assertion + new CONFIGS row in
      `tests/test_cross_backend.py`.
- [ ] Background-aggregate membership: `y_background` authority +
      `background_absorption` generalization + tests.
- [ ] `BACKGROUND_HUMP_SHARP` (constant fixed by the acceptance task's
      width-ladder measurement, provenance beside it) +
      `../AGENT_PROTOCOL.md` §7 row + §3 degeneracy line.
- [ ] Surfaces: capabilities schema-shaped key
      (`"extra_components" in Instrument.model_fields`) + expected-key set;
      `io/exporters._background_description` mentions "+ N humps";
      instrument-profile strip.
- [ ] Manual: `using/data.md` subsection (declare, free late,
      area-not-fraction, when a hump vs P-spline flexibility) +
      `../manual/background.md` equation with `*Source:*`; api-surface
      documentation of the new public names (freezes them).
- [ ] Compare: `_with_hump` variant beside `_with_pspline` (`viz/compare.py`;
      declare a hump + a late freeing stage) + `tests/test_compare_ui.py` row.
- [ ] Acceptance measurement + tests: synthetic crystalline + known hump —
      area recovered within its esd band; the absorption table
      declared-hump vs P-spline-flexibility on the same pattern (the honest
      evidence, not Rwp); the width ladder that fixes
      `BACKGROUND_HUMP_SHARP`; obs/calc/diff PNGs to `tests/output/`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_cross_backend.py tests/test_capabilities.py tests/test_compare_ui.py tests/test_manual.py tests/test_manual_api.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
```

Full suite once on the final tree: the `background_absorption` selection
change touches guard evidence on every state.

## References

- Thompson, Cox & Hastings (1987), J. Appl. Cryst. 20, 79 — the pseudo-Voigt;
  already cited in `../manual/profiles.md`.
- [1055](1055-background-evidence.md) and the v0.5 milestone record — the
  measured background-bias failure this parameterisation answers.
- [1028](1028-robustness-external-data.md) §(e) — `MARCH_R_MIN`, the
  softplus-pole precedent the fwhm floor copies.
- TOPAS `fit_obj` as prior art — concepts only (closed source; papers and
  manual concepts). If the hump parameterisation should cite prior practice,
  the citation comes from the maintainer-local paper corpus, not memory.

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

## Handover log

- **2026-08-26** — **a proposed `BackgroundPeak` implements the humps half
  under a different shape**, from a different starting point. Transcribed from
  PR #115 (**open, not merged** — three review findings outstanding), whose own
  handover draft is not taken verbatim: one of its bullets asserts a claim that
  PR withdraws, corrected below. A data-owner request for "a small number of
  explicit broad peaks summed on top of whatever background model is in use" is
  implemented there as `Instrument.background_peaks: list[BackgroundPeak]`
  (Gaussian; `position`, `height`, `fwhm`), *not* as `extra_components` with a
  `HumpComponent`. Four differences worth knowing before this WP is resumed,
  because three of them are constraints the seam design did not have:
  - **`height`, not `area`.** The parameterisation is TOPAS's `xo_Is`
    (`I` + `gauss_fwhm`), because the motivating case is a published TOPAS fit
    whose numbers had to be comparable term by term. `area` remains the right
    quotable number and is a projection of the three, not a fourth parameter.
  - **The name fences the glob.** `background_peaks` sits outside
    `instrument.background.*` because fnmatch's `*` crosses dots — the same
    reasoning this WP's own log used to prefer `extra_components`, so an
    `extra_components` seam inherits it unchanged.
  - **The width bound is the feature, not a floor.** `HUMP_FWHM_MIN = 0.1` as
    specified here is only a `MARCH_R_MIN` pole floor and does **not** stop a
    free position/height/width from being a Bragg peak with no cell behind it.
    What does is `fwhm ≥ BACKGROUND_PEAK_MIN_WIDTH_MULT · Γ_instrument(2θ₀)`,
    which depends on U,V,W and on the peak's own position and is therefore a
    reported guard (`BACKGROUND_PEAK_TOO_NARROW`), not a bound. Any member of
    the seam that is a *peak* needs this; a `BACKGROUND_HUMP_SHARP` sized from
    a width ladder would not have caught the failure, because the failure is
    not gradual. The multiple itself is calibrated against **one** measured
    case (20.8×, inside a 3–5 band) and no paper backs it — treat it as the
    weakest joint in that design, not as a quoted constant.
  - **`background_absorption` needs a span fix first.** Generalising the block
    to include peak columns saturates every R² at 1.00 unless `_span_basis`
    drops zero-norm columns — LAPACK returns an orthonormal Q whatever the rank
    of A. That defect is real and pre-existing. It does **not**, however, reach
    `BackgroundPSpline.air_scatter` at its off state: `to_internal` clamps, so
    dp/du is 1e-12 rather than 0 and no design row is exactly zero. An earlier
    commit on #115 claimed it did and withdrew the claim; the only exactly-zero
    column comes from the product h·(…) at zero height, which is why the fix is
    a provable no-op on everything shipped so far.
  A `BackgroundPeak` of that shape does not provide the `ExtraComponent` union
  itself, the member contract, `label`-keyed aggregate memberships, a sharp-peak
  member ([1103](1103-peak-components.md)), or `capabilities()`' schema-shaped
  key. A future seam should absorb it rather than sit beside it.
- **2026-08-18** — created from the single-peak planning session; numbering
  opens the 11xx block (v1.1). The seam design replaced an earlier
  humps-inside-`Background` draft: unifying with
  [1103](1103-peak-components.md) under one union deleted that draft's
  riskiest task (retightening `instrument.background.*` in every preset,
  which fnmatch's dot-crossing `*` made necessary there and the
  `extra_components` prefix makes unnecessary here).
