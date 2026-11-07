# WP-2012 — The two axial-divergence ratios are interchangeable, and a fit reports one branch

Milestone: unscheduled · Status: ✅ 2026-11-05 — every calibration path frees S/L alone, the recipe import included (PR #1422); the tie S/L = H/L is issue #1426
Track: What fires, and what stays silent
Depends on: —

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

## Tasks

- [x] Read Finger, Cox and Jephcoat (1994) on the S ↔ H symmetry, and check `profiles/fcj.py`
      against it. **Done 2026-11-02 from the derivation; the paper itself was not read.**
      It is in none of the three local corpora (`~/Zotero yue-here/storage`, `~/Zotero/storage`,
      `~/Code/rietx-refs-misc`; searched for "Jephcoat"). The symmetry is the model's, not
      this implementation's: the weight of an axial offset is the overlap of the specimen's
      axial extent and the slit's, the convolution of two boxcars of half-widths S and H,
      and a convolution commutes. `fcj.py`'s W(ξ) = clip(s + h − ξ, 0, 2·min(s, h)), its
      ξmax = min(s + h, |tan 2θ|) and its normalising integral are each symmetric in s and
      h, which is why `calibrate.py`'s swap assertion holds to the bit.
- [x] Decide the fix with the maintainer: `lab_calibrate` frees S/L alone with H/L held at
      its declared value; or one combined parameter, as GSAS-II has; or a finding when both
      are free. **Decided 2026-11-01 (maintainer): option 1.** `lab_calibrate` frees S/L
      alone and holds H/L at its declared value, the receiving slit's height over the
      goniometer radius (the calibration guide's 3 mm / 200 mm). H/L left at its default 0
      gives a one-ratio model, close to GSAS-II's single SH/L. Its fit-quality cost on a
      real instrument is not measured.
- [x] Build option 1: the `lines_axial` stage of `lab_calibrate` drops
      `instrument.geometry.axial_hl` (`strategy/staged.py:628-630`). A sibling found while
      recording the decision: `lab_bragg_brentano`'s `lines_axial` stage frees both ratios
      too (`:599-601`), so the same symmetry reaches it. Apply the same change there, and
      say so in the handover, since the ruling named `lab_calibrate` alone. Then drop the
      Biso start row's strict xfail if it XPASSes; the other lab6 start rows carry no mark
      since WP-2036 ordered the pair (§ Inherited, WP-2036). **Done 2026-11-02.** Both
      presets, the `refine_axial_asymmetry` suggestion, and the three NIST protocol
      mirrors of `lab_bragg_brentano` (`test_acceptance_srm660c._nist_calibrated_plan`,
      `examples/srm660c_lab.py`, `examples/validate_cuda_mixed_precision.py`) free S/L
      alone. The Biso row XPASSed and lost its mark. The axial-floor row turned red at
      0.582 plain esd on u: the protocol has two minima in the widths that the axial
      mirror did not make. It is a non-strict xfail citing WP-2084, filed for it.
- [x] Rewrite the two `help.py` entries to say the pair is interchangeable, and follow a
      changed preset into the skill's `lab_calibrate` row (`docs/skill/rietx/SKILL.md`, the
      presets table) and the calibration guide's axial paragraph. **Done 2026-11-02.** The
      skill's `lab_calibrate` row stays as it was: the body sits 32 B over its budget with
      any added clause (`tests/skill_caps.py`), and `help.py` is the cheaper place for it
      (root CLAUDE.md, WP-1338). The `lab_bragg_brentano` row and the
      `refine_axial_asymmetry` row in `references/numbers.md` name S/L. The guide drops
      its now-redundant hold on H/L and the `HOLD_BLOCKED_PLAN` it printed; its both-free
      demonstration builds its own plan. Tutorial 04, the theory chapter's FCJ section and
      the concepts plans table follow.
- [x] Look for the class's siblings: any other pair of parameters the model treats
      symmetrically, where a fit can land on either assignment. **Done 2026-11-02.** Two
      more surfaces freed the pair and now free S/L alone: the `refine_axial_asymmetry`
      suggestion (`report/layer2.py`, which a stage applies as written) and the three
      NIST protocol mirrors named in the build item. Left as they are: the Si 640c
      acceptance ties S/L = H/L (`tie_equal`), which removes the mirror its own way; and
      `test_mixed_precision.py`, `test_high_correlation_dedup.py` and the cross-backend
      rows free both on purpose, comparing two arms or two columns rather than quoting
      the pair. Not generalised: X against `lor_size` and Y against `lor_strain` are one
      ridge with only the sum measured, not two mirrored minima (WP-2002's cpd-1a
      entry); a magnetic structure's global moment sign is a mirror by physics, not
      checked here.
- [x] Reproduce the esd difference between the compiled and numpy paths in a test, or show
      it cannot happen once the pair is no longer both free. **Done 2026-11-02: not
      reproduced, either way.** On tutorial 04's synthetic LaB6 (no axial divergence, cell
      held), `lab_calibrate` gives u 0.00407(15), v −0.00303(19), w 0.003005(58),
      x 0.01486(32), y 0.02004(82) on the compiled tier and on `RIETX_COMPILED=0` alike,
      with S/L alone and with H/L freed beside it. Both-free reports `FLAT_DIRECTION` with
      the same "Flagged in stages: lines_axial, biso, closing." on both paths; S/L alone
      reports `FLOOR_HIT` on S/L and no `FLAT_DIRECTION`. The 2026-10-19 difference was on
      another synthetic standard that the WP does not name, so it is unreproduced rather
      than disproved; with one ratio free there is no flat pair for the `rcond` cut to
      straddle.

- [x] An imported GSAS-II recipe frees both ratios from one flag (found by
      `/code-review` on 2026-11-02). `io/recipe.py` splits `SH/L` into
      `axial_sl = axial_hl = SH/L / 2` and gives both its refine flag, so `_read_plan`
      frees the pair from the swap-symmetric diagonal. GSAS-II refines one `SH/L`, so the
      faithful mirror is a tie S/L = H/L, which `Recipe` has no field to carry; freeing
      S/L alone is the other option. Either changes what an import refines, and the
      reader's `RECIPE_CONVENTION_ASSUMED` text follows it. **Done 2026-11-05: S/L
      alone**, as the presets do under the 2026-11-01 ruling. The flag frees `axial_sl`
      and holds `axial_hl` at SH/L / 2, so the read profile is unchanged and only the
      free set moves; the convention note says so where the flag is set. The tie was not
      taken: it needs a `Recipe` field. No committed recipe flags `axial_divergence`, so
      no fixture's fit moves.
- [x] Rule between the hold and the tie for the recipe import (2026-11-05, the generality
      judge's "weak" on the hold). Freeing both is excluded by the exact swap symmetry. The
      choice left is which one-parameter model replaces GSAS-II's: S/L free with H/L held at
      SH/L / 2 (built on PR #1422), or S/L = H/L moving together, which is GSAS-II's own
      model and needs a `Recipe` field (or a plan) that carries a tie. Against the hold: the
      2026-11-01 ruling held H/L at a *declared* slit height, and here H/L is half a number
      the recipe flags. The hold also starts exactly at s = h, where the analytic S/L column
      is one-sided. Nothing measures the two models against each other, because no committed
      recipe flags the term.
      **Ruled 2026-11-05 (Michael): keep the hold as built.** The tie is "the more proper
      thing to do" and is left for later: issue #1426, which needs a `Recipe` tie field.
- [x] The skill-placement episode's colleague script reads H/L as a result row, which the
      2026-11-03 nightly found raising `KeyError` (a slow row, so #1356's fast gates could not
      see it). **Done 2026-11-03 (PR #1387).** The script prints S/L alone, and
      `tests/eval_skill_placement/PROTOCOL.md` records the changed episode as a dated amendment.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_examples.py -k calibrate -n auto --dist loadgroup
```

## Handover log

- **2026-11-05 (ghostshift runner, the ruling; WP closed)** — The maintainer ruled to keep
  the hold. An imported GSAS-II recipe frees S/L from its one `SH/L` flag and holds H/L at the
  half the recipe states, as PR #1422 built it. With that, every path that refines axial
  divergence frees one ratio, and the WP closes. Tying the pair S/L = H/L is GSAS-II's own
  model and the more proper one, so it is filed as issue #1426. It needs a tie field on
  `Recipe`, which nothing carries today.

  *Done.* No code changed in this session. The open task is ticked with the ruling. The
  status is ✅, and the `Priority:` line is gone. The narrative went to
  `docs/milestones/v1.12.md`. The branch was rebased onto `origin/main` (`541f0daf7`). Issue
  #1426 says what the hold does, what the tie would do and why it is more proper. It also
  says what the tie needs: a `Recipe` tie field, a check of the tied column at the FCJ
  corner, and a recipe that flags the term, to measure the two models against GSAS-II.

  *Correction to the entry below.* That entry says the skill's `RECIPE_CONVENTION_ASSUMED`
  row ("Treat the split as measured") contradicts `help.py` ("assumed and not measured").
  It does not. The row sits in the table headed "What it means you must not do", so it says
  what `help.py` says. Nothing was changed. Issue #1426 quotes both wordings and records the
  check.

  *Review.* This session made no code change, so `/code-review` had nothing new to read. The
  previous session's pass, and the generality judge's, cover the code (entry below). No
  heuristic was added, so the judge was not run again.

  *Gates.* Measured on darwin/arm64, worktree venv `[dev]`, on the rebased tree. See the PR
  body for the counts. The fast selection was not rerun, because nothing under `src/` changed
  after its 13931-passed run (entry below). The full suite did not run, for the reason given
  below.

  *Next:* none on this WP. The tie is issue #1426.

- **2026-11-05 (ghostshift runner, the recipe sibling)** — An imported GSAS-II recipe no
  longer frees both axial-divergence ratios from its one `SH/L` flag. It frees S/L and holds
  H/L at the half the recipe states, matching the lab presets. Nothing a committed recipe
  reads or fits changes, because none flags the term. The WP does not close. The generality
  judge rated the hold weak against the other one-parameter model, a tie S/L = H/L, which
  is GSAS-II's own. Which of the two a recipe import should use is the maintainer's call
  (the open task above). PR #1422 stays a draft until it is made.

  *Done.* `io/recipe.py`'s `_read_instrument` applies the `axial_divergence` entry to S/L
  once. H/L is a copy of S/L with the flag held, so a stated bound is honoured and reported
  once. `RECIPE_CONVENTION_ASSUMED` now fires wherever a split was made. Before, an entry
  carrying its own value beside a zero `SH/L` was split silently. Where the flag is set, the
  note says S/L alone is freed and H/L is held. A flag with no `SH/L` stated no longer
  reports an `SH/L = 0` that the recipe never wrote. `help.py`'s entry, the recipe
  reference chapter and `tests/data/README.md`'s convention row follow. Four tests in
  `test_recipe.py`.

  *Review.* `/code-review high --fix` found seven issues. It fixed three in `1aa04c665`:
  the silent entry-only split, the invented `SH/L = 0`, and the doubled bound report. It
  added three of the four tests. Declined, each for the ruling below:
  - `RECIPE_FLAG_DROPPED` at `warning` in place of `info`;
  - a flag with no `SH/L` starting S/L at the off state. Both ratios started there before
    this change too.

  Finding 7 (Status and Priority stale) is answered by this entry.

  *Generality* (the judge, on this branch's diff). The hold is a heuristic the audit table
  cannot see. It has two parts:
  - **Not freeing both:** tier 1, verified by the bit-identical swap.
  - **Holding H/L in place of a tie:** "weak". The judge names a dissenter: a refiner
    reproducing the GSAS-II refinement the recipe encodes would tie the pair.
    `io/CLAUDE.md` § Project writers prefers freeing to holding where a flag is narrower
    than the model. The 2026-11-01 ruling held H/L at a declared slit height, and here
    H/L is half a flagged number. No family measures the hold against the tie.
  - **The note's widened trigger:** "holds".

  Author's answer: the hold follows the presets' ruling, and the tie needs a `Recipe`
  field. That makes it a design choice, so it goes to the maintainer and is not settled
  here. The judge also called the s = h start the FCJ corner (`docs/docs/theory/method.md`
  § The FCJ corner). That is true. The default instrument and both presets start there
  too, so the corner is not specific to the recipe.

  *Gates.* Measured on darwin/arm64, worktree venv `[dev]`, compiled tier on. The touched-area files (recipe, help, audit table, audit delta, docs consistency, manual API, GUI help, skill): 345 passed before the review added three tests. `test_recipe.py` alone gave 60 passed after it. The fast selection (`-m "not slow"`, `-n 4` through testslot, 12:10–12:20Z, code at `1aa04c665`) gave 13931 passed, 239 skipped, 36 xfailed. This branch adds four tests, and there was no local base run to difference against. `tests.reader_output`: exit 0, unchanged against `078f10644`. Ruff
  clean. Vale: 0 errors. The full suite did not run. The change cannot move a measured
  number, because no committed recipe flags the term (`tests/CLAUDE.md` § Running). Pearl
  did not answer (SOCKS error 1, and the wake got no answer within 120 s), so the gates ran
  on the Mac.

  *Next:* the maintainer rules on hold against tie.
  - **Hold:** mark #1422 ready, tick the open task, close the WP and move its narrative to
    `docs/milestones/v1.12.md`.
  - **Tie:** add a tie channel to `Recipe` (or to the plan), apply `tie_equal` to the
    axial pair in `read_recipe`'s plan, and rewrite the note and the four tests.

  Either way, the judge's evidence would settle it: fit one recipe with the flag set under
  each model, and compare the refined values with GSAS-II's own refined `SH/L` under the
  same recipe. That needs a recipe file, and none is committed. The skill's
  `RECIPE_CONVENTION_ASSUMED` row ("Treat the split as measured") contradicts `help.py`
  ("assumed and not measured"). The row has said this since #287, and it was left as it is
  and flagged on the PR.

- **2026-11-03 (second ghostshift runner, the nightly)** — The 2026-11-03 nightly's one
  failure was this WP's. Since #1356 the lab plan no longer refines H/L, so H/L is not a row
  of the result. The skill-placement episode's colleague script still asked the result for
  it and stopped with a `KeyError`. The script now prints S/L alone, and the eval protocol
  records the changed episode. The episode loses its two findings on the S/L ~ H/L pair and
  keeps all five scored codes. Nothing the library returns or prints changed. PR #1387.

  *Done.* Bisected over `main`'s first parents: `fa7ec8599` passes, and the first bad merge
  is `01ef7b61a` (#1356). The row is `@pytest.mark.slow`, so #1356's fast gates could not
  reach it. `tests/eval_skill_placement/colleague_fit.py` drops `axial_hl` from its printed
  paths and keeps setting it to 0.02. `tests/eval_skill_placement/PROTOCOL.md` gains
  § Amendment, 2026-11-03. Siblings: nothing else in `tests/`, `examples/`, `docs/docs/` or the
  skill reads `axial_hl` off a result, and the nightly ran every executed reader green. The
  eval harnesses' other scripts read no result rows.

  *Measured* (darwin/arm64, worktree venv `[dev]`, compiled tier on). The episode before and
  after: S/L 0.020126 ± 1.168 → 0.020237(890), cell a 9.369048 → 9.369045 Å (0.3 ppm), c
  6.883869 → 6.883866, each Biso within 0.0001 Å². The `HIGH_CORRELATION` and
  `FLAT_DIRECTION` on S/L ~ H/L (ρ = −1.000) are gone. `FLAT_DIRECTION` still fires on zero ~
  displacement. That 0.3 ppm also answers a review question on `tests/eval_skill`'s `fap-fit`
  envelope (measured with both ratios free): an envelope 255 ppm wide is not moved by it.

  *Review.* `/code-review high --fix` found six and fixed two in `b59449776` (the amendment's
  wording on which codes still fire; the script's docstring cites both amendments).
  Declined: a fast guard that every printed path is freed by the plan, since it would copy
  the script's path list and the nightly is the slow rows' guard; `PROTOCOL.md` § The
  episode still says six codes, a registered section the amendments correct; a pooling note
  in `tests/eval_skill/PROTOCOL.md`, since the placement amendment names `fap-judge` and
  `build_episode` is the placement round's. One sibling went to WP-2084's `### Inherited`:
  the manual's SRM 660c ftol row still quotes the both-free 8.82 esd.

  *Gates.* The placement row passes, and with the touched files 169 passed on the tree
  merged with `origin/main` `cd2596f43`. The fast selection (`-m "not slow"`, at
  `ffcfd79aa`, before that merge) gave 13720 passed, 319 skipped, 34 xfailed; this branch
  adds no test. `tests.reader_output`: exit 0, unchanged. The full suite did not run: a
  test-only change (`tests/CLAUDE.md` § Running).

  *Next:* as the entry below says. The maintainer's recipe task is the one open item.

- **2026-11-03 (ghostshift runner, started 2026-11-02)** — `lab_calibrate` and `lab_bragg_brentano`
  now refine the axial-divergence ratio S/L and hold H/L at the value the user sets, as the
  maintainer ruled on 2026-11-01. A calibration no longer reports two interchangeable numbers
  as two measurements. The same change reached the report's axial suggestion and the NIST
  SRM 660c protocol, which mirrors `lab_bragg_brentano`, so the absolute anchor's numbers
  moved by small amounts and the PR waits for the maintainer. Holding H/L did not give
  LaB6 one answer: the protocol still has two minima, in the Gaussian widths, and that is
  filed as WP-2084. The FCJ paper itself was not read, because no local corpus holds it;
  the symmetry follows from the model's own weight function. One sibling stays open: an
  imported GSAS-II recipe still frees both ratios from its single SH/L flag.

  *Done.* The six tasks the WP was filed with; a seventh, the recipe, is new. `### Inherited`
  is consumed and deleted: its WP-2036 and WP-2002 entries were the lab6 start rows
  (settled above), its cpd-1a x/`lor_size` note is the sibling task's not-generalised line,
  and its SRM 660c two-minima entry is WP-2084. The build edited both presets
  (`strategy/staged.py`) with their docstrings and `PLAN_INFO` text; the ruling named `lab_calibrate` alone, and
  `lab_bragg_brentano` follows because its `lines_axial` stage freed the same pair.
  Siblings changed the same way: `report/layer2.py`'s `refine_axial_asymmetry` names S/L
  alone, and `test_acceptance_srm660c._nist_calibrated_plan`,
  `examples/srm660c_lab.py:nist_protocol_plan` and
  `examples/validate_cuda_mixed_precision.py:nist_plan` free S/L alone with H/L held at the
  protocol's declared 0.025. Settled by Claude under the protocol's own docstring
  ("`lab_bragg_brentano` minus the zero error") and this WP's build task, which expected the
  Biso row to XPASS. The other choice was to leave the absolute anchor's protocol freeing
  both. The repo's other lab acceptance protocols already freed S/L alone (FAP's
  `_gsas_protocol_plan`, the QPA round robin's `qpa_plan`). `help.py`'s two entries, the calibration guide (its H/L hold and the
  `HOLD_BLOCKED_PLAN` it printed are gone, every quoted number unchanged), tutorial 04
  (rebuilt; three diagnostics fewer), the theory chapter's FCJ section, the concepts plans
  table and two skill rows follow. The skill's `lab_calibrate` row did not grow: the body is
  at its byte budget and `help.py` holds the rule.
  `test_seed_invariance`'s width-start test stops ordering the pair and asserts H/L is not
  refined. `test_staged_start_invariance`: the lab6 Biso row lost its strict xfail (it
  XPASSed), and the lab6 axial-floor row is a non-strict xfail citing WP-2084.

  *Measured* (macOS arm64, worktree venv `[dev]`, compiled tier on, dispersion declined), the
  NIST protocol on SRM 660c, `origin/main` `62724a30f` → this branch, value(esd) as
  `RefinedParameter.stderr`:

  | quantity | before | after |
  |---|---|---|
  | cell a (Å) | 4.1568817(214) | 4.1568832(152) |
  | specimen displacement (mm) | −0.07903(184) | −0.07917(123) |
  | Kα2/Kα1 weight | 0.51251(479) | 0.51252(479) |
  | S/L | 0.02546(357) | 0.03704(74) |
  | H/L | 0.03667(328) | 0.025, held |
  | Biso La, B (Å²) | 0.4380(189), 0.5704(727) | 0.4381(189), 0.5706(728) |
  | u, v, w (deg²) | −0.000504(202), 0.001723(473), 0.000513(286) | −0.000506(200), 0.001733(463), 0.000505(277) |
  | x, y (deg) | 0.02807(209), 0.01518(286) | 0.02813(208), 0.01512(285) |
  | Rwp, GoF | 0.087429, 1.88633 | 0.087431, 1.88619 |

  The cell moved 0.36 ppm, a fifteenth of its esd, against the acceptance band of ±2e-4 Å
  (48 ppm). The cell and displacement esds fell to 0.71 and 0.67 of their old size, because
  the near-degenerate pair no longer inflates them. The diagnostics are the same four codes.
  `tests/reader_output.py` (the `srm660c_lab.py` fit, background from `auto_background`):
  exit 1, no line added or removed; the displacement reads −0.0791139 at 66σ against
  −0.0789974 at 44σ, the `CONSTRAINT_ACTIVE` count 7 against 12, and three stages' evaluation
  counts move.

  *The second minimum* (WP-2084's Context has the table). With H/L held, the axial-floor row's
  0.05 arm reaches χ²_red 3.549273 against the shipped arm's 3.557722, and a warm refit at
  the shipped floor from the 0.05 answer stays at 3.549378. So the shipped start reaches the
  shallower of two minima 0.24 % apart, which differ in u by 0.58 plain esd. The same gap,
  0.25 % and 46.7 in absolute χ², is in `test_seed_invariance`'s docstring from WP-2002's B10
  lane, where it was read as the S/L ↔ H/L mirror; that sentence now says the mirror rode
  along. The esd split on the compiled and numpy paths did not reproduce on tutorial 04's
  data with one ratio free or both (task 6).

  *Gates.* Rows run on this branch, each green: `tests/test_acceptance_srm660c.py` (2),
  the lab6 rows of `tests/test_staged_start_invariance.py` (Biso and intermediate pass,
  axial-floor xfails), `test_seed_invariance.py::test_the_peak_width_start_does_not_change_the_answer`,
  `tests/test_acceptance_dispersion.py` with `tests/test_acceptance_extra_peaks.py` (19),
  the acceptance command `tests/test_examples.py -k calibrate` (1), `-k srm660c` (2),
  `tests/test_tutorials.py` (35), and the touched-area fast files (help, skill, report-apply,
  roughness, audit, manual, reported-rows, FitReport layers: 475 after two fixes). The full
  suite did not run, by the runner brief: targeted LaB6 rows instead. The fast selection
  (`-m "not slow"`, on `01e22d1ab`, `origin/main` unmoved) gave 13597 passed, 319 skipped,
  34 xfailed, 3 failed; this branch adds no test. Two failures were this branch's and are
  fixed in `f9bc40e3b`, the 29 guide and glob rows re-run green: the hold guide (below) and
  `tests/data/gui/fnmatch_cases.json`, regenerated because a preset glob left. The third,
  `test_display.py::test_a_plot_in_a_kernel_shows_once_and_leaves_the_backend_alone`, is
  this machine's Jupyter kernel spec pointing at a deleted venv, unrelated.

  *A third moved number.* `docs/docs/guides/hold.md` fits FAP under `lab_bragg_brentano`
  with the cell free, and its a now moves 215.6 ppm from the held cell on both macOS paths,
  against 281 (compiled) and 324 (numpy) on 2026-10-21. The page's printed floor drops from
  "more than 250 ppm" to "more than 150 ppm"; Linux, at 351.9 before, was not re-measured.

  *Review.* `/code-review high --fix` found seven; four fixed in `01e22d1ab` (the
  `rietx compare` srm660c standard still freed H/L, and its anti-drift test never compared
  the plan; `PLAN_INFO` said `lab_bragg_brentano` frees the transparency; the SRM 660c
  test's H/L range check checked an input). Two not fixed: the recipe sibling (the new
  task) and the three lab6 strict xfails in `test_window_domain.py`, whose reasons quote
  numbers from the both-free protocol; they still fail as expected and were not
  re-measured (WP-2084's last task, with three stale `_audit.py` evidence strings). One dropped: "hold" in prose is the `hold()` verb's effect too.

  *Gotchas.* A help entry's growth lands in `reference/parameters.html.md`, whose twin is
  capped at 50 000 characters and sat within ~30 of it; this branch's text is net shorter.

  *Next:* the maintainer approves the moved SRM 660c numbers above (or asks for the anchor's
  protocol to keep both ratios free), then merge. Then the recipe task: `Recipe` carries no
  ties, so the faithful mirror of GSAS-II's one SH/L (a tie S/L = H/L) needs a field or a
  plan that frees S/L alone; that choice changes what an import refines. WP-2084 is the
  width-minima follow-up.

- **2026-11-02** — the fix is decided. The maintainer chose option 1 on 2026-11-01:
  `lab_calibrate` frees S/L alone, with H/L held at its declared value. A calibration then
  reports S/L as a measurement whenever the user declares the slit height, and the two
  mirrored minima disappear. Recorded only; nothing is built or run. While recording it,
  `lab_bragg_brentano` turned out to free both ratios as well, so the build task covers
  both presets. PR #1317. *Next:* task 1 (FCJ 1994 on the symmetry), then the build.

- **2026-10-19, filed by WP-1986's sixth session.** No open WP owns the axial ratios: a
  `git grep` for `axial_sl`/`axial_hl` over `docs/wp/` on `origin/main` finds only closed WPs
  (0402-0605, 1014, 1018), and WP-1460 (one finding per degeneracy) is about ridges reported
  once per pair, not about two separate minima. Measured on `[dev]`, darwin/arm64, against
  `origin/main` at `2df48c95` plus WP-1986's branch.
