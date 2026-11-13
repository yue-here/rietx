# WP-2056 — a low-angle asymmetry the CW neutron lines cannot calibrate

Milestone: unscheduled · Status: ✅ 2026-11-09 — point 2 shipped in PR #1493 (`LOW_ANGLE_ASYMMETRY_UNCALIBRATED`); point 1 and the scope ruling moved to #1499
Track: The specimen is not an angle, and the neutron follow-through
Depends on: 2054 soft (a Layer-1 asymmetry column that does not need FCJ live)

## Goal

On a constant-wavelength pattern whose lowest lines belong to a class that cannot calibrate
the asymmetry (magnetic lines below every nuclear line), the fit report states the
low-angle centroid residual against a cot 2θ shape and says whether the asymmetry is
determinable from this sample. If the scope decision admits it, an opt-in
Bérar–Baldinozzi term draws an area-preserving asymmetry with no long tail.

## Context

**Source.** Issue #1090 (2026-10-21, @mustachefeeling), with an amendment in its comment
the same day. Two real G4.1 cases with the same geometry needing opposite treatment:

- **Ba₂FeSbSe₅** (λ 2.426 Å; vendored by PR #1073, CC BY 4.0; fixture
  `tests/test_magnetic_series.py:1333-1425`). The lowest line, 9.35°, is magnetic; the first
  resolved nuclear line is at 21.7°. The line is centred about 50 mdeg low, shrinking
  roughly as cot 2θ (−18 mdeg at 18.2°, about −3 mdeg at 21-22°); zero shift and cell
  cannot remove it. Reporter's numbers: a cot 2θ-shaped shift of the magnetic component
  lowers χ² by 525, a constant shift by 340, Gaussian broadening by ≤ 40. One tied FCJ
  ratio fitted on the 100 K pattern (0.032(13)) halves the centroid error but draws a
  tail (calculated η 0.40 against 0.17 observed). Freed separately, one ratio sits at 0
  with esd 15-28. The moment moves +0.03 to +0.06 μ_B.
- **LaMnO₃** (#1089). The lowest line, (010) at 11.5°, is magnetic too. Here the
  instrument file's S/L 0.040, H/L 0.030 is wrong for the pattern (FWHM 0.360° against
  0.325°, η 0.31 against 0.19, centroid 24 mdeg low), and one tied ratio refined on all
  lines (0.026) matches it: FWHM 0.330°, η 0.15, centroid within 7 mdeg, χ² over the line
  386 → 176.

These are the reporter's numbers; none was re-run at triage. The tree already records the
Ba₂FeSbSe₅ half in the fixture's protocol comment (`test_magnetic_series.py:1372-1377`).

**What exists.** FCJ (`model/profiles/fcj.py`) is the only asymmetry. Layer 1's
`asymmetry` column is its derivative and exists only while FCJ is live
(`model/forward.py:2814`); see WP-2054 for the report half. No empirical term exists
in `model/profiles/`.

**The proposal.**
1. A Bérar–Baldinozzi term (Bérar & Baldinozzi 1993): the profile is multiplied by
   1 + [P₁F_a(z) + P₂F_b(z)]/tan θ + [P₃F_a(z) + P₄F_b(z)]/tan 2θ, with F_a, F_b odd
   Hermite-type functions of z = (2θ − 2θ_k)/FWHM, so the correction integrates to zero
   against any symmetric profile and moves intensity across the line without changing its
   area. Check the exact F_a, F_b against the paper before coding.
2. A diagnostic: when the lowest observed lines lie below every line of the class that
   would calibrate the asymmetry, report their centroid residual against a cot 2θ shape
   and say the asymmetry is not determinable from this sample.
3. A recipe (the amended form): refine one tied ratio, compare the lowest line's observed
   and calculated FWHM, η and centroid; adopt when they agree (LaMnO₃), keep it out and
   name the shift as a systematic when it draws a tail the line lacks (Ba₂FeSbSe₅); apply
   the same check to a value from an instrument file.

**Practice.** `docs/practice.md` § Axial divergence quadrature: MAUD and EasyDiffraction
use an empirical or Bérar–Baldinozzi asymmetry; GSAS-II, RIETAN-FP and FullProf (`Npr = 7`)
use FCJ; TOPAS a ray model. FullProf's non-FCJ profiles use B–B (recalled, not checked).

**Tier.** Point 1 is a published model (tier 2), opt-in, adding no threshold. Point 2 is
a report of a number with its meaning (DESIGN § Rules, 1, third kind); its "below every
calibrating line" test is geometry, and any significance bar on the cot 2θ fit needs an
audit row. Point 3's agreement test needs a tolerance on FWHM, η and centroid, which is
new judgement measured on two families only (Ba₂FeSbSe₅, LaMnO₃): it ships as a skill
recipe, not a package rule, unless a third family is found.

**Licensing.** The paper only for B–B. Check MAUD's and cryspy's licences before reading
either's code; nothing is ported.

## Non-goals

- The report's asymmetry column when FCJ is off, in general: WP-2054.
- The numpy FCJ column at a zero aperture: WP-1955.
- S/L ↔ H/L interchangeability: WP-2012.
- FPA and the full axial model (Cheary & Coelho 1998): § v2+.
- Magnetic peak widths: WP-1343.

## Tasks

- [ ] Maintainer decision on scope: point 2 alone, points 1 and 2, or neither; recorded
      here as `Decided YYYY-MM-DD:` and answered on #1090.
      **Not made** (2026-11-09). Point 2 was built, being common to both readings that
      build anything, and the ruling is asked in PR #1493's body. Point 1's half of the
      question moved to issue #1499.
- [x] Reproduce the two cases on the tree: the Ba₂FeSbSe₅ 1.5 K fit from the fixture, the
      lowest line's centroid residual and its cot 2θ fit; LaMnO₃ from #1089's data if it
      is in the tree, else say so.
      **Reproduced 2026-11-09** on `00cd6db80` (macOS arm64, `[dev]`, numpy path). The
      fixture's protocol on the 1.5 K pattern alone (nuclear fit, then the
      `SOLVE_STAGE_PATHS` plan with the fixture's ties): Rwp 0.1171 nuclear, 0.0611 with
      the moment, |m| = 3.875(121) μ_B. Per-line centroid shift (the residual regressed
      on each seen line's ∂P/∂2θ and its own profile, counting-noise esd; negative = observed
      lower): −51.3(2.2)
      mdeg at 9.38° (1 0 1)/(1 0 0), −20.8(8.0) at 17.99°, −6.2(5.7) at 18.27°, all three
      magnetic-only; the first line that is not, (0 1 1) at 21.67°, −5.1(2.1). A cot 2θ shape
      through the three magnetic lines gives A = −8.2(4) mdeg and predicts −20.7(9) at
      21.67°, so the nuclear line does not follow them: the shift falls faster than
      cot 2θ, as #1090 reported (−50, −18, −3). Layer 1 already reads the 8.2-12.0° region
      as position −0.054(2)° and the nominal-aperture asymmetry column (WP-2054) +0.029(3);
      no diagnostic named it and the only action was `decrease_background_flexibility`.
      LaMnO₃ is in the tree (`tests/data/gsas2_bt1_lamno3_50K.gsas`, the WP-1327
      acceptance protocol, apertures from the instrument file, S/L 0.040, H/L 0.030):
      (0 1 0) at 11.53° is the only line below the first nuclear one at 22.32°, and sits
      +19.6(1.8) mdeg (the drawn line too low, as #1089's "centroid 24 mdeg low"), the
      nuclear line +9.2(2.7). Not re-run: #1089's tied-ratio refinement.
- [x] Point 2: the diagnostic, with its audit row and `help.py` entry.
      `LOW_ANGLE_ASYMMETRY_UNCALIBRATED` (info), `report.magnetic.low_angle_asymmetry_findings`,
      called in the result build beside `magnetic_width_findings`. Fires on geometry alone: a
      seen magnetic-only line below the lowest seen line that is not (WP-1343's
      `MAGNETIC_WIDTH_PURITY` cut; "seen" is the line's own t ≥ `MIN_COEF_SIGNIFICANCE`). Says
      each such line's centroid shift, the first other line's, and what a one-term cot 2θ
      shape through the magnetic lines predicts there; no threshold on any number, so no new
      tunable constant (one numerical step, `_SHIFT_STEP_FWHM`, tier 1). Rows: the code tier 1
      / ambiguity 3 / info, its suggestion tier 2 (asymmetry from a standard's calibration, the
      instrument-parameter workflow), the step tier 1.
- [ ] Point 1 (if in scope): the term in `model/profiles/`, its analytic derivatives, a
      `test_cross_backend.py` config, a Layer-1 column, `help.py` entries for its four
      parameters, and the Theory tab's equation.
      **Not built; moved to issue #1499** (2026-11-09), with the scope ruling it waits on.
- [x] Tests + obs/calc/diff PNGs of the lowest lines at each treatment to `tests/output/`.
      `tests/test_low_angle_asymmetry.py` (fast, synthetic CrSBr k = (0 0 ½), the magnetic
      (0 0 1) at 8.88°, first nuclear line 17.80°): truth S/L = H/L = 0.03 fitted at 0 reads
      −33.7(8) mdeg; the null arm (no asymmetry anywhere) +0.4(6), still firing because the
      geometry fires it; silent from 12° up and on the paramagnetic pattern. PNGs
      `low_angle_asymmetry_{positive,null}.png` (6-20°). Acceptance on the real case beside its
      fixture (`test_ba2fesbse5_the_report_names_the_low_angle_shift_the_protocol_holds`,
      slow): the 1.5 K entry names three magnetic-only lines below 21.67° and a shift in
      (−60, −35) mdeg; silent at 100-200 K. Treatments of point 1 have no PNG: point 1 is out
      of this PR.
- [x] Skill: point 3's recipe as a `references/` row keyed by the diagnostic's code, tagged
      `(Measured: Ba₂FeSbSe₅, LaMnO₃)`. In `references/magnetic.md` § Moment codes, both
      committed copies synced; the numbers in it are #1089/#1090's, not re-run.

## Acceptance

On the Ba₂FeSbSe₅ 1.5 K fixture the report names the low-angle centroid shift with its
size and says the asymmetry is not determinable from this sample. If point 1 lands, the
term at P = 0 is bit-identical to today, and the cross-backend matrix covers its columns.

```sh
.venv/bin/python -m pytest tests/test_magnetic_series.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_cross_backend.py tests/test_help.py tests/test_audit_table.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- Bérar, J.-F. & Baldinozzi, G. (1993). *J. Appl. Cryst.* 26, 128-129.
  doi:10.1107/S0021889892009725.
- Finger, L. W., Cox, D. E. & Jephcoat, A. P. (1994). *J. Appl. Cryst.* 27, 892-900.
- Issues #1090, #1089, #1073 (PR), #1106.

## Handover log

- **2026-11-09** — closed (ghostshift runner, one session; PR #1493; remainder issue #1499).
  On a constant-wavelength neutron pattern whose lowest lines are magnetic, the fit report now
  says so. It also says that no nuclear line in the sample can check the axial asymmetry there,
  and how far each of those lines sits from where the model draws it. Before this, the
  Ba₂FeSbSe₅ protocol carried that −50 mdeg systematic in a test comment, and the report named
  nothing. The finding decides nothing: on LaMnO₃ a refined asymmetry matches the lowest line,
  and on Ba₂FeSbSe₅ it draws a tail, so choosing between them is the recipe in the skill. The
  maintainer's scope ruling was never made. This session built point 2, the part common to both
  readings that build anything. The Bérar–Baldinozzi term (point 1) and the ruling went to
  #1499.

  *Done.* Task 2 reproduced (numbers in its checklist item, updated for the final estimator).
  Point 2: `report.magnetic.low_angle_asymmetry_findings`, wired in `refine._build_result`
  beside `magnetic_width_findings`, reusing that function's `y_calc`. Its pieces are
  `_magnetic_fraction`, factored out of `_classified_reflections` with no change in
  behaviour; `_phase_lines`, which builds lines from every phase, merges reflections within
  0.4 FWHM, weights the width by the drawn components, keeps lines with t ≥ 3 and lines whose
  ±2 FWHM window lies inside the fitted range; `_solve_shifts`, a joint weighted least squares
  on ∂P/∂2θ and P per line over overlapping windows, falling back to one line at a time when
  singular; `_line_shifts`; and `_cot_through`. Audit rows: the code (tier 1, ambiguity 3,
  info), its suggestion (tier 2) and `_SHIFT_STEP_FWHM` (tier 1). Also a `help.py` entry, the
  regenerated `tests/data/gui/help_keys.json`, the fast `tests/test_low_angle_asymmetry.py`
  (3 tests), the slow Ba₂FeSbSe₅ acceptance in `tests/test_magnetic_series.py`, and a skill
  row in `references/magnetic.md`, with both copies synced.

  *Review.* `/code-review` was invoked first, but its forked run reviewed and edited the
  **main checkout** (another branch, `local-vt-patches`), not this worktree. Its uncommitted
  edits there were reversed from a saved patch, and the main checkout is clean again. The
  review was then rerun as a read-only agent on this branch. No serious finding. Six were
  fixed in `f143275a7`:
  - a line off the fitted range counted as seen;
  - a line's intensity misfit leaked into its shift under an asymmetric profile (each line's
    P is now a nuisance column, which moved the Ba₂FeSbSe₅ numbers from −47.1/−31.3/−14.7 to
    −51.3/−20.8/−6.2 mdeg, closer to #1090's −50/−18);
  - the nuclear width was used under `mag_split`;
  - the anchor was searched per phase, not across phases;
  - an all-magnetic range was silent;
  - a singular block was dropped whole.

  Declined: vectorising the line loop. It costs 0.02 s on Ba₂FeSbSe₅ and an estimated 0.4-3.5 s
  at 10⁴ reflections, once per result build, on magnetic fits only.

  *Measured.* Synthetic CrSBr arms: −33.7(8) mdeg with the asymmetry planted, +0.4(6) mdeg in
  the null arm. Per-line shifts on Ba₂FeSbSe₅ and LaMnO₃ are in the task items above. The
  finding takes 0.02 s on the Ba₂FeSbSe₅ fit. `python -m tests.reader_output` exits 0: the
  reader corpus has no magnetic fit. A reader of any magnetic CW-neutron fit whose lowest seen
  line is magnetic-only receives one new info diagnostic by default.

  *Generality* (the `generality-review` brief, run as a general-purpose Opus agent; its sections
  condensed here, the full text in the session; the verdicts were weak or holds, none fails). After it ran, `9315c1fab` took
  three of its asks: the anchor is now a nuclear-only line (frac ≤ `MAGNETIC_WIDTH_PURITY`),
  so a half-magnetic line neither fires the finding nor silences it; the suggestion names a
  standard in the same container and fill, and asks for the shape check whatever the source;
  and the skill tag says the numbers are the reporter's. A structured field for the shifts
  and an in-package ranking of the treatments went to #1499 for the maintainer.

  - **LOW_ANGLE_ASYMMETRY_UNCALIBRATED (code, tier 1, ambiguity 3, info) — weak.** Nothing
    acts, so the case against acting is met. The case for doing more is the stronger side: in
    both measured cases the pattern settled the choice (the lowest line's FWHM, η and centroid
    under each treatment), which is Rule 1's second kind, a ranking, not the third. The
    "geometry" trigger rests on four borrowed, unaudited constants (`MAGNETIC_WIDTH_PURITY`,
    `MIN_COEF_SIGNIFICANCE`, `VALIDITY_RADIUS_FWHM`, `MAGNETIC_WIDTH_TAIL_FWHM`), so "no
    threshold" holds for the shift and not for the firing. Two real families, both used in
    development, plus one synthetic family; the per-line shifts exist only in message text.
    Would change the verdict: the shifts in a structured field, plus either an in-package
    ranking of the two treatments or a stated reason why the lowest line's shape does not
    decide.
  - **…suggestion (tier 2, ambiguity 3) — weak.** Taking instrument parameters from a
    calibration is established practice. But S in S/L is the sample's axial length, so a
    standard in a different can does not transfer. And on LaMnO₃ the instrument file's value
    was the wrong one, so the shape check should cover a standard's or a file's value too.
    *(Taken in `9315c1fab`.)*
  - **`_SHIFT_STEP_FWHM` (constant, tier 1) — holds.** A central-difference step on the right
    scale, feeding only a report; the precedent is `ORIGIN_FD_STEP`. Would change it: a test
    comparing the column against a 10× smaller step on an FCJ-live line.
  - **Four existing constants reused for new jobs — weak.**
    - 0.4 FWHM is a linearisation radius, not a resolution limit.
    - t ≥ 3 lets a weak nuclear line silence the finding.
    - The purity cut was used one-sidedly *(fixed: the anchor is now nuclear-only)*.
    - The ±2 FWHM range margin drops a magnetic line just above the scan start.
    - Would change the verdict: a test arm with a weak or half-magnetic line below the
      magnetic one.
  - **The trigger — holds in direction, weak at its edges.** It is the WP's own goal, and the
    null arm shows it states something about the sample, not the shift. It fires on null
    shifts inside its geometry ("Attention is a cost", clause 1). It is pooled across phases,
    so an impurity's nuclear line silences it.
  - **The one-term cot 2θ shape — holds.** It is a reported shape with no threshold. On
    Ba₂FeSbSe₅ it does not carry to the nuclear line, and the message prints both numbers. The
    only source is the issue. Would change it: a cited source for the cot 2θ form, and A in a
    structured field.
  - **The skill row — holds** on Rule 4: it is keyed by a code and adds no tolerance. **Weak**
    on its evidence tag, since its numbers are #1089/#1090's and were not re-run
    *(tag reworded in `9315c1fab`)*.

  *Tests* (macOS arm64, `[dev]`). The fast selection through `serial.py` and `testslot`, at
  `-n 4`, gave 14344 passed, 416 skipped, 32 xfailed in 21:00. It ran on `f143275a7`. The final
  commit, `9315c1fab`, changed only the anchor rule, the message and suggestion wording, the
  skill tag and the audit text, and its touched files were re-run: `test_audit_table`,
  `test_low_angle_asymmetry` and `test_skill_cli` gave 39 passed, and the Ba₂FeSbSe₅
  acceptance 1 passed. The added fast tests cost 3.24 s in all, nearly all of it the module
  fixture, so none joins the slow tail. The slow Ba₂FeSbSe₅ acceptance passed alone in 41-110 s
  (the ramp fixture). The full suite was not run, because the change moves no fitted value; CI
  and the nightly own it.

  *Gotchas.* A forked `/code-review` runs in the session's own cwd. In a ghostshift runner that
  cwd is the main checkout, not the worktree, so run the review as an agent pointed at the
  worktree. The shifts' esds are counting-noise esds with no factor for GoF.

  *Next.*
  1. The maintainer rules on scope at review of #1493: point 2 alone, or point 1 too (on #1499).
  2. If point 1 goes ahead, #1499 is its spec. It also carries the structured field and the
     ranking the generality review asked for.

- **2026-10-26** — created, from the 2026-10-26 issue triage (issue #1090). Checked against
  the tree at c0e32ab29: the Ba₂FeSbSe₅ G4.1 data and protocol are in the tree (PR #1073),
  and its fixture comment already records the asymmetry held at 0 and the −50 mdeg
  cot 2θ systematic; no empirical asymmetry exists in `model/profiles/`; the reporter's χ²
  and shape numbers were not re-run. No open WP owns it: grep of `docs/wp/` finds no
  Bérar–Baldinozzi or #1090; WP-1955 and WP-2012 are FCJ's column and its pair symmetry;
  WP-1343 is magnetic widths; the report's asymmetry column is WP-2054's, a separate
  owner because #1106 changes the report and leaves the model alone. *Next:* the scope
  decision.
