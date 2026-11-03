# WP-2054 — the report names an asymmetric residual the model cannot draw

Milestone: unscheduled · Status: 🔄 2026-11-03 — direction (b) in PR #1363, both rulings carried out; waits on merge and the reply on #1106
Track: What fires, and what stays silent
Depends on: 1977 soft (the flank-lobe half of the same symptom); 2004 soft (a new template's thresholds take audit rows there)
Priority: P2 2026-10-26 — a report that names the wrong cause: on a lab Bragg–Brentano fit with the apertures at their default 0, Layer 2 suggests an impurity phase at 0.50 and nothing mentions asymmetry (#1106, NIST SRM 660c)

## Goal

When a fit's residual is one-sided about its peaks, the FitReport says so whatever the
instrument declares. With the axial apertures at 0, a significant asymmetric residual
produces `refine_axial_asymmetry` with the instruction to declare the apertures (or take
them from a standard), and no longer reads as a missing phase.

## Context

**Source.** Issue #1106 (2026-10-22, @mustachefeeling), on the bundled NIST SRM 660c
pattern (`tests/data/nist_srm660c_100a.cif`, the `_meas` block) with LaB₆ and
`Instrument.bragg_brentano(radiation="CuKa", monochromator_two_theta=26.6)`. The issue
carries a self-contained script.

**Measured at c0e32ab29** (`[dev]`, macOS arm64), the issue's script:

| | apertures 0 (default) | apertures declared (0.025) and refined |
|---|---|---|
| Rwp / GoF | 0.1288 / 2.78 | 0.0867 / 1.87 |
| Layer-1 columns | intensity, mixing, position, width | + asymmetry |
| `unmatched_obs` below 45° | 10, each 0.1-0.3° below a LaB₆ line, up to 25.4 σ at 21.28° | 7, all ≤ 6.7 σ |
| active actions | `add_impurity_phase` 0.50, `increase_background_flexibility` 0.47 | `refine_sample_strain_broadening` 0.12 |

`report.layer2.compare_freed` on the pair: t = 7.4 and 11.7 for the two apertures, ΔBIC +280
at N/f² (N 5332, N_eff 368).

**Why the report cannot see it.**
- Layer 1's `asymmetry` kind (`report/layer1.py:12`, `_KINDS` at :71) is the FCJ
  derivative ∂Ω/∂(S/L). `derivative_bases` builds it only while FCJ is live
  (`model/forward.py:2814`, `build_axial = axial_derivs and fcj_live(sl, hl)`).
- `Geometry.axial_sl`/`axial_hl` default to 0.0 (`schemas/instrument.py:1255-1260`), and
  the `bragg_brentano` preset keeps that.
- `refine_axial_asymmetry` (`report/layer2.py:1009-1021`) fires only on a significant
  `asymmetry` coefficient in a gated region below 40°, so it cannot fire when the model has
  no asymmetry.
- At exactly zero the FCJ column is dead (issue #1075, repro 1): the profile's first-order
  change in S/L vanishes there. So computing the physical column at 0 is not a fix.

**Candidate directions** (the issue's points 1 and 2, plus one from triage).
- (a) A model-free asymmetry column, always present: the odd-cubic direction u³·Ω̂ that
  peak fitting already reads for `PEAK_ASYMMETRY_UNMODELLED`
  (`indexing/peakfit.py:385-404`, u = (2θ − 2θ_j)/Γ). Odd-cubic because a free position
  absorbs the odd-linear part.
- (b) The FCJ column evaluated at a nominal aperture when the model's is 0. The package
  already sizes FCJ nodes as if S/L = H/L = `forward.AXIAL_SIZING_FLOOR` (0.02) when both are
  0 and one is free; that is the natural nominal value.
- (c) The preset declares a nominal nonzero aperture, so the existing column and action
  work. This moves every lab fit built from the preset.
- Point 2 in every case: when the column is significant and FCJ is off, the action says the
  apertures must be declared nonzero first, or taken from a standard or resolution file.

**Practice** (`docs/practice.md` § Axial divergence at zero, checked 2026-10-25 by
WP-1421's survey). GSAS-II never computes a zero aperture: one SH/L, floored at 0.002 for
the profile at every evaluation, refined or not. RIETAN-FP and FullProf do not describe a
zero case. MAUD and EasyDiffraction use an empirical or Bérar–Baldinozzi asymmetry instead
of FCJ (§ Axial divergence quadrature). No code surveyed has a report layer, so none has
the report-side question.

**Tier.** Direction (a) is a new template in an existing basis; its significance is read
through the four existing region gates, so it adds no threshold unless the action needs
one. Direction (c) is a default (a declared aperture), tier 2 if GSAS-II's floor is the
named practice. Either way the action is the "rank with evidence" kind (DESIGN § Rules, 1):
the report names asymmetry beside the other candidates; it does not choose.

**What would fool the new column.** A position error that is not a constant shift inside a
region, a Kα2 weight error (one-sided about Kα1 by construction, see issue #1166), and a
flank lobe from a width error. The column must be measured against all three before it
ranks anything.

**Licensing.** Concepts only from the issue and from FCJ (Finger, Cox & Jephcoat 1994);
nothing ported.

### Inherited

- 2026-11-02, from WP-1977 (PR #1295, reworked to Yue's ruling of
  2026-11-01): every `unmatched_obs` row stays listed and carries
  `UnmatchedPeak.flank`. On #1106's script with the apertures at 0, all 11
  rows say `on_flank`, at 0.9-3.0 FWHM below their LaB₆ line and one 1.0
  above, and `add_impurity_phase` 0.50 is gone, because Layer 2 no longer
  counts a row on a flank (rebuilt from the stored fit, `[dev]`,
  darwin/arm64). The other active action, `increase_background_flexibility`
  0.47, is untouched. So the failing test this WP plans must assert on the
  asymmetry action's absence; its "suggests `add_impurity_phase`" half no
  longer reproduces once WP-1977 merges, and the Acceptance clause
  "`add_impurity_phase` is not the top action" holds already. The flank rows'
  offsets and their `lines_with_lobe` counts are evidence an asymmetry test
  can read.

- 2026-10-31, from the issue triage (issue #1106): the reporter (2026-10-29)
  brings evidence for direction (a) and one new ask, with no code and no
  threshold. Per peak region they fit the residual on the model's own net line
  P and its derivatives P′, P″, P‴ (P‴ the odd direction left once a free
  position takes P′), each with a counting-noise t not divided by the
  serial-correlation factor f, rolled up per term as a coherent z, an
  incoherent χ² and an rms t. Synthetic (rietx's own forward model, so one
  source): axial asymmetry 0.02 with FCJ off, which Layer 1 reads today as
  position (rms t 4.6–5.0), shows shift rms 5.9–6.6 and odd rms 3.4–3.8 in 3
  of 3; a 5 % high-angle second line, silent in Layer 1 today, shows odd rms
  2.83–3.51; the null over 20 clean fits has the largest per-term rms at 1.32.
  Dividing by f biases the null low and eats the signal (the second line falls
  to 1.99–2.17 against 1.18). On four public patterns with FCJ refined every
  term reads far above N(0,1); the odd term is one-signed on SRM 1976a
  (coherent z +31.5) and FAP (+16.3) and has no net sign on SRM 660c (+0.5),
  so an always-present odd column would report something on most lab fits. The
  ask: a `t_noise` field on `BasisCoefficient` beside `stderr` and
  `significant`, the per-term rollups printed ungated on both maturity
  branches, `significant` untouched until WP-2004 rules on the gates; about
  1.6 ms in `report()`; one extra run per additive fixed component reads a
  blank mismatch (2e-4 in d gives 3/3, its control 0/3). They recommend the
  Layer 1 seat over a Layer 0 field and leave it to the maintainer. Tiers as
  they state them: the statistic tier 2 (Rao 1948 score test, Ramsey 1969,
  Turin 1960), the null tier 1, the region rule (4 % of peak height, ≥ 6
  points) tier 3, a BH q per region that never gates. Checked against the tree
  at d87c8cc91: `BasisCoefficient` (`report/schemas.py:922`) carries `kind`,
  `value`, `stderr`, `significant`, `share`, and no noise-only t. A new field
  on the report is a public schema change; the decision belongs with this WP's
  first task.

## Non-goals

- The `unmatched_obs` matching window and a flank-lobe filter on `add_impurity_phase` (the
  issue's point 3): WP-1977, which has the cpd-1c/1f cases and now this one.
- The numpy FCJ column's accuracy at one zero aperture: WP-1955.
- S/L ↔ H/L interchangeability: WP-2012.
- An empirical (Bérar–Baldinozzi) asymmetry model: issue #1090's own placement.
- Tiering the report's existing gates: WP-2004.

## Tasks

- [x] Maintainer decision: (a), (b), (c) or a combination, recorded here as
      `Decided YYYY-MM-DD:` and answered on #1106.
      Settled 2026-11-03 by Claude under measurement and practice: (b), the FCJ
      column of a twin drawn at `AXIAL_SIZING_FLOOR`, read only while both apertures
      are 0. The label was a triage session's, so it was assessed against the
      triggers first. (c) moves a preset default, which is the maintainer's, and
      was not taken. Between (a) and (b) the measurement chose: the reporter's own
      survey has an always-present odd column reading far above noise on most lab
      fits with FCJ refined, while (b) leaves every fit that declares an aperture
      untouched and passes all five controls below. GSAS-II's practice is the same
      move: it evaluates its one aperture at a floor, never at zero. The reply on
      #1106 is the maintainer's to post.
- [x] A failing test: SRM 660c with the apertures at 0 reports no asymmetry and suggests
      `add_impurity_phase` (the issue's script, trimmed).
- [x] Land the chosen direction. If (a): the column joins Layer 1's basis, passes the four
      gates, and its correlation with `position` and `mixing` on SRM 660c and two other
      families (cpd-1c, FAP) is recorded.
- [x] The action: `refine_axial_asymmetry` fires from the new column when FCJ is off, and
      its rationale says the apertures are 0 and must be declared or calibrated first.
- [x] Controls: a synthetic symmetric pattern with a Kα2 weight error and one with a width
      error do not fire the action; a synthetic with known S/L does.
- [x] Audit rows for any new threshold or action site (`rietx._audit`), and a
      `THRESHOLDS_VERSION` bump if one moves (coordinate with WP-2004).
- [x] Tests + obs/calc/diff PNGs of SRM 660c at both settings to `tests/output/`.
- [x] Skill: the `refine_axial_asymmetry` reference row says it can now fire with the
      apertures at 0, and what to do then; `help.py` if the action text changes.

## Acceptance

On SRM 660c with the apertures at 0, the report's active actions include
`refine_axial_asymmetry` and its rationale names the zero apertures; `add_impurity_phase`
is not the top action. With the apertures declared and refined, the report is unchanged
from today. The synthetic controls hold.

```sh
.venv/bin/python -m pytest tests/test_fitreport_layers.py tests/test_report_loop.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_audit_table.py tests/test_help.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- Finger, L. W., Cox, D. E. & Jephcoat, A. P. (1994). *J. Appl. Cryst.* 27, 892-900 (FCJ).
- NIST SRM 660c certificate (LaB₆), `tests/data/README.md`.
- Issues #1106, #1075 (repro 1), #1090 (the related model proposal), #1166.

## Handover log

- **2026-11-03 (second session)** — the maintainer's two rulings are carried out on
  PR #1363. The report's nominal aperture is now a constant of its own,
  `rietx.report.NOMINAL_AXIAL_APERTURE` = 0.02, and the report no longer reads
  `AXIAL_SIZING_FLOOR`. Next: merge, and the reply on #1106 once approved.

  *Ruled by Yue 2026-11-03.*
  - The reader-output change (the `refine_axial_asymmetry` suggestion at zero
    apertures, its rationale clause, and each region's `asymmetry` coefficient entry) is
    approved as written. Closes open item (1) below.
  - The nominal aperture gets its own constant, 0.02, so a later change to the FCJ
    quadrature floor cannot move the report. It carries a tier-3 audit row whose evidence
    is the nominal sweep below, `approved="2026-11-03"`. `AXIAL_SIZING_FLOOR`'s row stays
    as it was. Closes open item (4) and supersedes the "no new audit row" settlement below.

  *Done.* `NOMINAL_AXIAL_APERTURE` sits beside `report._nominal_axial` with its comment;
  `_nominal_axial` and `layer1.nominal_axial_columns`' docstring name it. The `_audit`
  row is added at tier 3 with grounds and the sweep's numbers. No value moved, so no
  reported number changes.

  *Measured* (`[dev]`, darwin/arm64, after merging origin/main at cef9aef7c).
  `tests.audit_delta`: 1 added (this row), 0 changed, 0 new at `unaudited`.
  `tests.reader_output`: unchanged against the merge-base. Report tests, the SRM 660c
  zero-aperture slow row and the validation matrix: 815 passed. `test_audit_table` and
  `test_docs_consistency`: 48 passed. Ruff clean. Fast suite, alone under the suite lock:
  13642 passed, 319 skipped, 34 xfailed, 0 failed. No test was added in this session; the
  first session's two failures now pass, and the rest of the difference is main's merge.

  *Merged with #1356 (WP-2012, 01ef7b61a).* `refine_axial_asymmetry` now names S/L alone,
  and the zero-aperture rationale clause follows that rule. It read "take them from a standard's calibration, or add a stage freeing them to the plan and run it again, since the widths and positions fitted without them have absorbed part of it".
  It now reads "take S/L from a standard's calibration, or add a stage freeing S/L to the plan and run it again, since the widths and positions fitted without it have absorbed part of it". The skill row says the same. This wording postdates the
  2026-11-03 approval, so it is the maintainer's to confirm. After the merge:
  `tests.reader_output` unchanged, `tests.audit_delta` 1 added, ruff clean.

  *Open for the maintainer.* (2) The reply on #1106: drafted, unposted, at
  `~/.cache/ghostshift/rietx/wp-2054/reply-1106.md`. (3) The reporter's `t_noise` ask stays
  open on #1106. The new tier-3 row is measured on two families (SRM 660c and the cpd
  round-robin) where WP-2017's second pass asks three; it is not on WP-2017's list.

- **2026-11-03** — direction (b) landed (PR #1363). A lab fit that leaves both axial
  apertures at 0 now gets a report that names the one-sided low-angle residual as axial
  asymmetry and says the apertures are 0, where before it named nothing. The report
  draws the asymmetry column from a copy of the model with both apertures at 0.02 and
  leaves every fit that declares an aperture exactly as it was. On SRM 660c the
  three regions below 40° now read asymmetry first, and freeing the apertures from 0
  inside the plan takes Rwp from 0.129 to 0.087. Next: the maintainer approves the
  reader-output change and answers #1106.

  *Done.* `report._nominal_axial` compiles the shapes model again with
  S/L = H/L = `AXIAL_SIZING_FLOOR` when `fcj_live` is false at the fit's values, and
  Layer 1 (`layer1.nominal_axial_columns`) takes that twin's ∂Ω/∂(S/L) for each peak
  that has none of its own. The misfit and the other four columns stay the fit's own,
  and the borrowed column is projected off their span in each region before the solve,
  so the four keep the coefficients they have without it (Frisch-Waugh-Lovell) and the
  asymmetry coefficient is the joint one.
  `suggest_actions(axial_off=True)` counts only a positive coefficient, since a
  negative one asks for less asymmetry than a model that draws none, and appends the
  zero-aperture clause to the rationale. Pawley and hand-built models get no twin,
  for `_reading_models`' reason. Tests: four new cases in
  `tests/test_fitreport_layers.py` (seven with the parametrised controls) and
  `test_srm660c_zero_apertures_report_names_axial_asymmetry` (slow), which writes
  `tests/output/srm660c_zero_apertures_{fit,lowangle}.png`. The declared-aperture
  PNGs are the baseline row's `srm660c_fit*.png`. The low-angle PNG shows the
  classic axial tail on (100). Skill row in `references/numbers.md` updated;
  `help.py` carries no action text, so it is unchanged.

  *Measured* (`[dev]`, darwin/arm64, at d0c4bded0 + this branch).
  - #1106's script, apertures 0: Layer-1 columns 4 → 5; regions 21.4°, 30.4°, 37.5°
    read asymmetry +0.0205, +0.0204, +0.0247 (7-9 esd), shares 0.15, 0.27, 0.36;
    gated regions 12/15 → 15/15. Active actions: `refine_axial_asymmetry` 0.50 and
    `increase_background_flexibility` 0.47 (unchanged), nothing else. Apertures
    declared and refined: report identical.
  - Before the projection (the first commit), the borrowed column took the position
    reading: a zero error of +0.02° put the asymmetry action first and
    `refine_zero_shift` at 0.30 (found by `/code-review`, confirmed here by switching
    the projection off: both new position tests fail). With it, zero error ±0.02°
    and displacement ±0.03 mm leave every position action at its pre-WP confidence
    (top 1.0, runners-up 0.5). For the positive sign the asymmetry action also fires
    at 0.5, ranked with the runners-up: a 0.02° shift is a third of the FWHM, and its
    nonlinear part is one-sided. Not fixed; it never leads.
  - Synthetic LaB6 (`_truth`), apertures 0 in the model: S/L = H/L = 0.02 in the data
    fires the action (coefficients +0.0078 to +0.0092, the tangent at 0.02 against a
    secant from 0, so about half the aperture). No action on: the unperturbed
    symmetric pattern, Kα2 weight ×0.8 and ×1.2, W ×0.7 and ×1.4 (every low-angle
    coefficient insignificant). A position error inside a region was not run as a
    control; the four-column position term absorbs it first.
  - Apertures freed from 0 on SRM 660c: inside the plan, before or after the profile
    stages, both reach Rwp 0.0867 (the same as starting at 0.025); one stage appended
    to the converged zero-aperture fit reaches 0.012 and Rwp 0.1251, because the
    widths and positions are not refitted. The rationale says to re-run the plan.
  - `report()` on SRM 660c: +45-65 ms with the twin (about 11 %), with a fast suite
    running beside it.
  - `python -m tests.reader_output`: unchanged (exit 0), because the standard fit
    declares its apertures. Every zero-aperture fit's printed report does change.
  - The nominal value decides the reading (asked by the generality judge). Gated
    regions and whether the action fires, by nominal aperture, with the projection:
    | fit (apertures 0) | before WP | 0.005 | 0.01 | 0.02 | 0.03 | 0.05 |
    |---|---|---|---|---|---|---|
    | SRM 660c | 12/15, no | 14/15, fires | 15/15, fires | 15/15, fires | — | 14/15, no |
    | cpd-1c | 5/14, no | — | 5/14, fires | 9/14, fires | 9/14, fires | 7/14, no |
    | cpd-1a | 4/14, no | — | — | 6/14, fires | — | — |
    | cpd-1f | 3/14, no | — | — | 11/14, fires | — | — |
    Above the data's own aperture (SRM 660c refines to about 0.025/0.037, cpd-1c to
    S/L 0.040 with H/L held 0) the tangent points elsewhere and the low-angle
    coefficients fall insignificant: the failure is silence, never a wrong call.
    Without the projection, 0.01 also collapsed the gates (1/15 and 2/14), because a
    small aperture's smear is a shift. The secant from 0 was tried and was no less
    sensitive (3/15 gated at 0.02 on SRM 660c before the projection), so the tangent
    stays. 0.02 sits inside the working range on both real families.
  - Freeing the axial term in the QPA protocol on cpd-1c moves Rwp 0.1076 → 0.1052
    (S/L 0.040), so the three cpd samples do carry the asymmetry the action names.

  - Fast suite (`[dev]`, darwin/arm64, 2026-11-03, beside another session's suites):
    13611 passed, 319 skipped, 34 xfailed, 2 failed. One failure was this branch's
    (the new acceptance test had no `tests/validation_matrix.py` row; added, and
    `test_validation_matrix.py` then 745 passed). The other,
    `test_display.py::test_a_plot_in_a_kernel_shows_once_and_leaves_the_backend_alone`,
    is this machine's Jupyter kernel spec pointing at a deleted venv. Nine fast cases
    added, 1.40 s in all (`tests.added_test_times`, local junit). No baseline was run
    for the passed+skipped delta; CI's counts are the comparison.
  - The full suite did not run: two other sessions' suites held the machine lock.
    In its place, the slow suites whose fits reach a Layer-1 report: magnetic,
    LaMnO₃, Stephens and FAP (15 passed), and SRM 660c with SRM 676a (5 passed,
    the new row included). The nightly's full job is the full-suite check.

  *Settled by Claude* (each could have gone the other way).
  - (b) over (a) and (c), on the grounds in the first task above.
  - The tangent at the nominal aperture over the secant from 0: the twin's existing
    bases give it with no new arithmetic, and the sweep above has it no more
    sensitive to the value than the secant.
  - The sign rule at zero apertures: a physical bound (an aperture cannot go below 0),
    not a tuned threshold, so no audit row.
  - No new audit row and no `THRESHOLDS_VERSION` bump: no threshold moved.
    `AXIAL_SIZING_FLOOR` gains a second consumer, the report's nominal aperture,
    and the sweep shows the value matters there, though only above the data's
    aperture. Its row is approved (2026-10-22),
    so its evidence was not edited, and a row of its own at tier 3 needs an
    `approved` date. Both are the maintainer's (open item 4).
  - The skill row carries the description only: the generality judge read its
    Rwp parenthesis as an Rwp comparison offered as evidence, and the rationale
    already carries the advice.

  *Open for the maintainer.* (1) Approve the reader-output change: every fit with
  both apertures at 0 gains an asymmetry coefficient per region and, where the
  residual is one-sided, the action with its new clause. (2) Reply on #1106. (3) The
  reporter's further ask, a `t_noise` field on `BasisCoefficient` and ungated
  per-term roll-ups, is not done: it adds a public report field, which is reader
  output and a schema change, and nothing in this WP needed it. (4) The nominal
  aperture: keep reading it off `AXIAL_SIZING_FLOOR` (its approved row then needs
  an evidence line for the report's use), or give the report its own constant at
  0.02 with a tier-3 row, which needs an `approved` date.

  *Review* (`/code-review high --fix`). Seven findings. Fixed: the position-error
  takeover (the projection above), the controls now assert Layer 1 ran and carried
  the column, and the twin's bases kwarg has its own name (`axial_bases`). Declined:
  the action's `two_theta_range` spans every gated low-angle region, counted or not;
  narrowing it would change the report of a fit that declares its apertures, which
  the Acceptance holds unchanged (a class for WP-2004 or a follow-up). The twin's
  bases also compute the ∂Ω/∂(H/L) planes nothing reads (part of the +45-65 ms);
  skipping them needs a `derivative_bases` option, outside this diff. The column
  reaching regions above 40° is kept: with the projection it moves no other
  coefficient, and those regions' gates now pass more often, not less.

  *Generality* (the judge's sections, condensed by this session to the verdicts,
  with the answers).
  - `AXIAL_SIZING_FLOOR` as the report's nominal: **weak**. The value decides which
    reflections get a column and so which regions pass the gates; GSAS-II floors
    at 0.002; one real family. *Answer:* measured from 0.005 to 0.05 on SRM 660c
    and cpd-1c, and at 0.02 on cpd-1a and -1f (table above). It moves above the
    data's aperture, so per the judge it needs its own constant and row; that row's
    `approved` is open item 4. The judge read the tree before the projection.
  - Sign rule at zero apertures: **holds** (tier 1, a physical bound). Minor gap:
    nothing records that a negative coefficient was left out of the action.
  - Rationale clause **holds**; skill row's measured parenthesis **weak** (an Rwp
    comparison, one family). *Answer:* cut.

- **2026-10-26** — created, from the 2026-10-26 issue triage (issue #1106). Checked against
  the tree at c0e32ab29: the issue's script reproduces (Rwp 0.1288 → 0.0867 with the
  apertures refined; with them at 0, no `asymmetry` column, 10 low-angle `unmatched_obs` up
  to 25.4 σ, `add_impurity_phase` 0.50); every code line it cites holds, a few lines moved.
  No open WP owns it: WP-1977 owns the flank-lobe filter (the issue's point 3) and excludes
  Layer 1's ranking; WP-1955 and WP-2012 are the FCJ column's accuracy and the aperture
  pair's symmetry; WP-2004 tiers existing gates and adds no column. *Next:* the decision.
