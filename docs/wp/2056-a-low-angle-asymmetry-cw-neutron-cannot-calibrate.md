# WP-2056 — a low-angle asymmetry the CW neutron lines cannot calibrate

Milestone: unscheduled · Status: ⬜
Track: The specimen is not an angle, and the neutron follow-through
Depends on: 2054 soft (a Layer-1 asymmetry column that does not need FCJ live)
Priority: P3 2026-10-26 — a workaround covers it: the Ba₂FeSbSe₅ protocol holds asymmetry at 0 and names the centroid shift as a systematic (+0.03 to +0.06 μ_B on a 3.9 μ_B moment); waits on a scope decision

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
- [ ] Reproduce the two cases on the tree: the Ba₂FeSbSe₅ 1.5 K fit from the fixture, the
      lowest line's centroid residual and its cot 2θ fit; LaMnO₃ from #1089's data if it
      is in the tree, else say so.
- [ ] Point 2: the diagnostic, with its audit row and `help.py` entry.
- [ ] Point 1 (if in scope): the term in `model/profiles/`, its analytic derivatives, a
      `test_cross_backend.py` config, a Layer-1 column, `help.py` entries for its four
      parameters, and the Theory tab's equation.
- [ ] Tests + obs/calc/diff PNGs of the lowest lines at each treatment to `tests/output/`.
- [ ] Skill: point 3's recipe as a `references/` row keyed by the diagnostic's code, tagged
      `(Measured: Ba₂FeSbSe₅, LaMnO₃)`.

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

- **2026-10-26** — created, from the 2026-10-26 issue triage (issue #1090). Checked against
  the tree at c0e32ab29: the Ba₂FeSbSe₅ G4.1 data and protocol are in the tree (PR #1073),
  and its fixture comment already records the asymmetry held at 0 and the −50 mdeg
  cot 2θ systematic; no empirical asymmetry exists in `model/profiles/`; the reporter's χ²
  and shape numbers were not re-run. No open WP owns it: grep of `docs/wp/` finds no
  Bérar–Baldinozzi or #1090; WP-1955 and WP-2012 are FCJ's column and its pair symmetry;
  WP-1343 is magnetic widths; the report's asymmetry column is WP-2054's, a separate
  owner because #1106 changes the report and leaves the model alone. *Next:* the scope
  decision.
