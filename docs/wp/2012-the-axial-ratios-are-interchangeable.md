# WP-2012 — The two axial-divergence ratios are interchangeable, and a fit reports one branch

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-10-19 — a silent wrong pair of numbers on `lab_calibrate`, the one preset that frees both ratios; the profile it fits is right, so only a reader of S/L and H/L is misled

## Goal

A fit never reports S/L and H/L as two measured numbers when swapping them leaves the pattern
unchanged. Either the presets free one of the two, or the result says the pair is
interchangeable, and the help text stops telling a reader to fit them together.

## Context

**The symmetry, measured 2026-10-19** (WP-1986's calibration guide, `[dev]`, darwin/arm64).
`Refinement.predict` on LaB₆ under Cu Kα with `instrument.geometry.axial_sl = 0.025,
axial_hl = 0.015` and with the two swapped gives arrays equal to the last bit
(`examples/guides/calibrate.py` asserts it below its markers). So the profile in
`profiles/fcj.py` is symmetric under S ↔ H, and no pattern can choose between the two
assignments.

**What a fit does with it.** `lab_calibrate`'s `lines_axial` stage frees
`instrument.geometry.axial_*`. On the guide's synthetic LaB₆ standard (made with S/L 0.025 and
H/L 0.015), the fit started from both at 0 returned S/L 0.01451(76) and H/L 0.02531(66): the
swapped branch, each about 14 esd from its true value. The only finding was
`HIGH_CORRELATION` on zero shift against displacement. No finding names the axial pair,
because at the swapped minimum the two are not strongly correlated: the two minima are
separate points, not a ridge.

**Where the package tells a reader to do this.** `src/rietx/help.py`'s
`instrument.geometry.axial_sl` entry says "Fit it on a standard together with `axial_hl`. The
two are strongly correlated and are usually reported as a pair." The `axial_hl` entry says
"refining one and holding the other is a common protocol". The guide
`docs/docs/guides/calibrate.md` now holds H/L at the receiving slit's height over the
goniometer radius and says why.

**A second, smaller finding on the same pair.** On a synthetic standard with no axial
divergence at all, both ratios free, the fit reports `FLAT_DIRECTION` (ρ = −1.000). There the
compiled and numpy paths (`RIETX_COMPILED=0`) agree on every value but not on the esds of the
other width terms: W 0.003032(58) against 0.00303(12), U 0.00399(15) against 0.00399(21). The
`FLAT_DIRECTION` message also differs: only the numpy path appends "Flagged in stages:
lines_axial, biso." That points at `statistics.normal_covariance`'s `rcond` cut landing on
either side of the flat eigenvalue, by path. Not reproduced in a test yet.

**Practice (recalled, not checked this session).** GSAS-II refines one combined SH/L. FullProf
refines S_L and D_L separately. TOPAS's full axial model takes the slit and Soller dimensions,
not these ratios. Finger, Cox and Jephcoat (1994, *J. Appl. Cryst.* **27**, 892) define both.
Read the paper for whether the symmetry is the model's or this implementation's before
choosing a fix.

### Inherited

- **From WP-2036 (2026-10-25, PR #1165): rounding picks each arm's minimum, so the lab6 intermediate-tolerance row is no longer a strict xfail.** On `deff4c301` Linux passed the row (XPASS(strict)) while the Mac failed it. Under 1e-14 nudges to cell `a` on an arm64 Mac (`[dev]`), the two minima are (`axial_sl`, `axial_hl`) = (0.025461, 0.036669) and its swap, at Rwp 0.087428899057 and …058. Of 49 nudged arm pairs, 23 crossed minima (8.82 plain esd) and 26 agreed (7.4e-6). WP-2036 made the mark `strict=False`, citing you. When your fix lands, make it strict again or drop it. Two siblings were not re-measured. The Biso row's strict mark may flip the same way. The axial-floor row (`test_the_axial_sizing_floor_does_not_change_the_answer[lab6]`) carries no mark: it failed on Linux on `c9dde14` at 8.820 plain esd on `axial_hl` and passed on `deff4c301`, so rounding picks it too.
- **From WP-2002 (2026-10-23, 9th session, PR #1113): the floor removal makes LaB6's intermediate tolerance reach the mirrored minima too.** With the U, V and Y floors gone (the maintainer's ruling), `tests/test_staged_start_invariance.py`'s `intermediate_tolerance[lab6]` row lands its two schedules 8.82 plain esd apart on `axial_sl` (0.000 before) and is a strict xfail citing this WP. The Biso row on LaB6 now differs by 1.16 esd on `u` (9.36 on `axial_sl` before), still a strict xfail.

- **From WP-2002 (2026-10-22, 6th session, PR #1085): which mirrored minimum LaB6 reaches depends on where the declared stages stop.** Behind the shipped closing stage the two Biso starts land 9.14 plain esd apart on `axial_hl`; with `intermediate_ftol` 1e-4 instead of 1e-6 they land 0.050 apart, on one minimum. A sibling degeneracy on cpd-1a, not generalised here: its QPA protocol frees the instrument Lorentzian `x` and each phase's `lor_size` together, against `help.py`'s advice to calibrate `x` and hold it. Both scale as 1/cosθ, so only their sum is determined: the sums agree between the two starts while fluorite's split differs by a factor 2.5 (0.018° against 0.007°), with esds from 0.011 to 43. `tests/test_staged_start_invariance.py`'s yardstick, the larger of the two plain esds, hides it.

- **From WP-2002 (2026-10-21, 5th session, PR #1085).** Behind the closing stage two Biso starts (0.5 and 1.5 Å²) on SRM 660c still land in the mirrored S/L ↔ H/L minima, 9.36 plain esd apart on `axial_sl`; the closing stage does not choose between them. `tests/test_staged_start_invariance.py`'s lab6 Biso row is a strict xfail citing this WP.
- **From WP-2002 (2026-10-21, 4th session): no window setting moves the split.** Biso started at 0.5 and at 1.5 Å² on every atom lands the two starts in the two mirrored minima, 9.0 esd apart in `axial_sl` with today's windows, 9.0 with `WINDOW_AREA_TOL` 1e-3 on the last stage, and 9.4 with a closing all-free stage at 1e-3. The protocol run at 1e-3 throughout lands in the other basin from today's, 9.2 esd away. So which minimum SRM 660c reaches depends on the start and on the early stages' windows, and the start tests WP-2002 runs will fail on LaB6 until this WP removes the pair's symmetry. Numbers: `docs/wp/2002-batch/rulings.md` § Sixth round.
- **From WP-2002 (2026-10-21, PR #1085).** On NIST SRM 660c under `tests/test_acceptance_srm660c.py`'s protocol there are two distinct minima 46.7 apart in absolute χ² (N = 5332), nearly mirror images under S/L ↔ H/L: (0.0367, 0.0254) from the protocol start and (0.0254, 0.0368) from a start with x at 0.03, the second the deeper. They differ in Caglioti u, v and w by 0.38, 0.20 and 0.12 esd and in the cell by 0.04 esd. The objective is bit-symmetric under the swap, so these are two minima, not one point twice, and the protocol's own answer is the shallower. LM and TRF also land in different minima on that protocol (χ² 18934 against 18594, u −0.00050 against −0.00127, the cell 3 ppm apart). The (100) reflection carries 39 FCJ nodes in one and 40 in the other, measured not to cause the split. Numbers: `tests/test_seed_invariance.py`'s width-start docstring, `docs/wp/2002-batch/waiting.md` § B8 and B9.

## Tasks

- [ ] Read Finger, Cox and Jephcoat (1994) on the S ↔ H symmetry, and check `profiles/fcj.py`
      against it.
- [ ] Decide the fix with the maintainer: `lab_calibrate` frees S/L alone with H/L held at
      its declared value; or one combined parameter, as GSAS-II has; or a finding when both
      are free.
- [ ] Rewrite the two `help.py` entries to say the pair is interchangeable, and follow a
      changed preset into the skill's `lab_calibrate` row (`docs/skill/rietx/SKILL.md`, the
      presets table) and the calibration guide's axial paragraph.
- [ ] Look for the class's siblings: any other pair of parameters the model treats
      symmetrically, where a fit can land on either assignment.
- [ ] Reproduce the esd difference between the compiled and numpy paths in a test, or show
      it cannot happen once the pair is no longer both free.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_examples.py -k calibrate -n auto --dist loadgroup
```

## Handover log

- **2026-10-19, filed by WP-1986's sixth session.** No open WP owns the axial ratios: a
  `git grep` for `axial_sl`/`axial_hl` over `docs/wp/` on `origin/main` finds only closed WPs
  (0402-0605, 1014, 1018), and WP-1460 (one finding per degeneracy) is about ridges reported
  once per pair, not about two separate minima. Measured on `[dev]`, darwin/arm64, against
  `origin/main` at `2df48c95` plus WP-1986's branch.
