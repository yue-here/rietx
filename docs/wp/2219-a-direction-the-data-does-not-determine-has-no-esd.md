# WP-2219 — A direction the data does not determine has no esd

Milestone: unscheduled · Status: 🔄 2026-11-19 — claimed by @yue-here (ghostshift runner)
Track: What fires, and what stays silent
Depends on: 2028 soft (its joint-fit covariance fix, PR #1668)
Priority: P2 2026-11-19 — a quoted esd too small by up to 140×, and the CIF that carries it says nothing; a path few fits run

## Goal

A parameter on a combination the data does not determine reports no esd (`None`), in every
runner: a single fit, a joint fit and a Pawley fit. The one exact width degeneracy that standard
presets can still reach is held at its source, the way WP-2002 holds the other width pairs.

## Context

**What happens today.** The esd calculation equilibrates the normal matrix and inverts it with
a cut at `statistics.PINV_RCOND` (1e-15 of the largest eigenvalue). A direction under the cut is
dropped. Each parameter on it then reports its spread along the directions the data did
measure, which is at least √2 too small by construction. `COVARIANCE_DIRECTION_DISCARDED`
(WP-1535) names those parameters and tells the reader not to quote them
(`staged.check_discarded_directions`, `statistics.discarded_directions` and its "touched"
test, `blocked.discarded_directions` for the joint layout). The esds themselves stay in
`RefinementResult.parameters`, in the CIF and in the GUI.

**How bad that number is.** WP-2028 measured synthetic LaB6 with W, `gauss_size` and
`gauss_strain` free. Γ_G² = W + `gauss_size`/cos²θ + `gauss_strain`·tan²θ, and
1/cos²θ = 1 + tan²θ, so the move (δW, δsize, δstrain) = (+1, −1, +1) changes no width at
any angle. Two starts landed 140 esd apart in W (3.94e-4 and 3.04e-4, each ± 6.3e-7). A start
whose smallest eigenvalue fell just over the cut gave ± 5.5 on the same parameters. So the
reported esd jumps by 10⁷ across the cut.

### Decisions

**Ruled 2026-11-19, settled by Claude on the maintainer's delegation ("your call").**
WP-1535 chose a short esd beside a warning. That choice is reversed: a parameter the
discarded-direction test names gets no esd.

- *Grounds.* Linear-models practice is settled: a parameter that is not estimable has no
  standard error, and a generalized inverse's variance for it depends on which inverse was
  taken (Searle 1971, *Linear Models*, p. 169). R's `lm` prints `NA`; SAS PROC GLM flags "B"
  and leaves the error missing. Prince (2004), § Correlation, calls such a precision
  "illusory" and asks for a constraint. The survey is `docs/practice.md` (PR #1668's row).
- *Where this departs.* GSAS-II and TOPAS quote the truncated-SVD esd; GSAS-II adds a
  warning naming the parameters. That is today's rietx behaviour, and it is the choice
  reversed here. FullProf stops on a singular matrix.
- *Runner-up.* Keeping the short esd (WP-1535). It loses on accuracy: the number is wrong by a
  factor nothing bounds, and a CIF reader never sees the warning.
- *Measured cost to ordinary practice* (2026-11-19, `[dev]` venv, macOS arm64, Python 3.12;
  a pytest plugin wrapping both `check_discarded_directions`, the `-m slow` selection on
  WP-2081's branch). 13 solves fired, hits recorded without the denominator. None of the nine
  presets frees instrument and sample widths in one stage. One hit was the exact width triple
  (`test_acceptance_stephens`'s corundum: `gauss_size`, `gauss_strain`, W). Twelve were weak
  directions near the cut in deliberately hard fits: a Le Bail fit on a wrong triclinic cell
  (U, V, W; zero shift, displacement, X, Y), the Le Bail hand loop of `lebail_alternation`
  (zero shift, V, W, Y and background c0–c7; `cell.a`, zero shift, U, V), and Cr₂WO₆ at 150 K
  with zero moments (six to eight Biso; two moment pairs). No scale and no QPA fraction.
  WP-1535's October count (183 of 1 899) was mostly width pairs that WP-2002's twin hold
  (`refine.WIDTH_TERMS`, `_width_twin_flats`) has since removed.
- *Accepted consequence.* A weak Le Bail fit can show a cell edge or zero shift with no esd.
  Pawley replaces Le Bail as the structure-free default (WP-2062), so this work adds nothing
  Le Bail-specific.

### Where the code is

- `params/vector.py`: `_cov_free` (`:4857`) drops gradient-free columns, and
  `unmeasured_rows` (`:4913`) names what they reach. A discarded direction's touched set
  joins that path, so every consumer already marking an unmeasured row marks these too
  (root CLAUDE.md: consumers mark, never clamp; a tie inherits its source's blindness).
- `strategy/staged.py:2347` `check_discarded_directions`, and `:2477`, which skips any solve
  with `outcome.n_aux`. **So a Pawley fit's discarded direction is never named.** Its
  intensity block lives outside `outcome.jac`. WP-1535's probe of `normal_factors` found 24
  such solves in the fast selection, all Pawley overlap groups.
- `multi.py:2994` and `optimize/blocked.py:541` for the joint fit (WP-2028 made the blocked
  and dense layouts agree).
- `io/cif/numbers.py:57` `number(tag, value, su)` writes a bare value when `su is None`, which a
  CIF reader takes as a fixed parameter. `su_or_dot` (`:80`) writes `.`. Neither is right for
  "refined, precision undetermined".
- `help.py:2119` and the skill's `references/diagnostics.md` row carry the warning's text.
- Tier: the statistics rule is physics-of-estimation (named practice above). The triple hold
  is the WP-2002 rule extended to a member it left out; its ambiguity kind is "every
  competent refiner would act" (DESIGN § Rules, 1).

### Inherited

(none yet)

## Non-goals

- Changing `PINV_RCOND` or the equilibration.
- Indexing's per-peak covariance (WP-1915 owns it).
- Pawley overlap groups already reported as `PAWLEY_OVERLAP_UNRESOLVED` keep that report.
  This WP decides only what esd their intensities carry.
- Retiring Le Bail (WP-2062).

## Tasks

- [ ] Hold the width triple at its source. When W, `gauss_size` and `gauss_strain` are free for
  a seen phase and the null space of `_width_twin_flats` contains their move, hold W, the
  instrument member, as U, X and Y are held already. Record it where WP-2002's holds are
  recorded. Check the WIDTH_TERMS comment's warning: holding W unconditionally moved three
  acceptance answers. This hold fires only on the exact triple, so measure that no
  acceptance answer moves beyond `test_acceptance_stephens`'s corundum row, and say what
  that row's answer did.
  *Declined on measurement* (settled by Claude under § Acceptance, "either held or with no
  esd", and "no acceptance number moves except where this WP names it"). Built and measured,
  then reverted. On the Stephens fits it moved corundum at most 0.40 esd, Rwp 14.5745 % →
  14.5720 %. The full suite then showed it moved what this WP does not name: the cpd-1 chain
  (`test_chained_agrees_with_independent_fits`, 0.1469 against 0.1373 ± 0.005), the
  hostile-pairs runaway no longer raised, `RESOLUTION_NOT_POSITIVE` newly fired on brucite and
  zincite, and `test_corundum_block_is_inert_and_hamilton_blesses_it_only_at_raw_n` failed.
  The triple is left to the no-esd rule, which meets the acceptance line by itself.
- [x] No esd on a discarded direction, dense path. The touched set from
  `statistics.discarded_directions` joins `unmeasured_rows`. Esds, correlations and every
  derived esd follow the existing marking rules. `COVARIANCE_DIRECTION_DISCARDED` keeps
  firing and its text changes from "do not quote" to "these parameters have no esd".
- [x] The same in the joint fit (`multi.py`, `blocked.discarded_directions`).
- [x] The same in a Pawley fit: run the test on the matrix augmented by the intensity block,
  so the guard stops skipping `n_aux` solves. Measure the fast and slow selections' Pawley
  hits first and report how many are overlap groups already flagged.
  *Measured* over the full suite (2026-11-20, `[dev]`, macOS arm64; a probe plugin wrapping
  `_guarded_covariance`, run with the since-reverted W hold in place): 357 Pawley solves
  discarded a direction, 356 of them through the intensity block. They touched 6 758
  intensity columns: 5 800 in overlap groups, which `PAWLEY_OVERLAP_UNRESOLVED` now reports
  as "an individual value has no esd", 423 off the data, and 535 in neither, which no code
  names. Two of the 357 touched a table path. `test_acceptance_indexing.py` held 126 of them
  and passed.
- [x] CIF: a refined value with no esd writes its uncertainty as unknown, never as a bare
  value. Check the CIF core dictionary for the form (`?` beside the value is not legal inside
  one number; the likely answer is the value with a separate `_refine` note, or `?` for the
  su item where one exists). Fetch the dictionary per memory note `cif-dictionaries-via-gh`.
- [x] GUI and text output: the parameter table shows the missing esd the way an unmeasured row
  shows today; check by looking.
  *Done, no GUI code changed:* `/api/params` already sends `esd: null`, and after a Refine
  click on a scratch LaB6 project the Text tab printed `cell.a … esd 5.85e-05` and the tied
  `atoms.0.biso` with no esd, as a locked row prints. The Text tab writes no `vars.` rows at
  all, before and after this WP.
- [x] Tests: the LaB6 triple (held, so no warning), a deliberately exact pair with no esd in all
  three runners, a CIF round trip. Re-run the slow-suite probe and quote the count.
  *Done*, with the triple tested for no esd since the hold was declined. The probe over the
  full suite: 441 solves discarded a direction, in 38 test files, five touching a scale (two
  of them this WP's own exact pairs). That run had the W hold in place, so the triple's fits
  are missing from it.
- [x] Skill: the `COVARIANCE_DIRECTION_DISCARDED` row says the esds are absent and what to hold.
  Manual: `reference/result.md`'s esd section, and the Theory tab if the covariance chapter
  describes the cut.
- [x] Release fragment: what a reader now receives (`tests.reader_output`), and Yue sees it
  before merge (a change to what a fit returns).

## Acceptance

- The LaB6 triple from WP-2028 reports W, `gauss_size` and `gauss_strain` either held or with no
  esd, from both starts, in the single and the joint fit.
- No acceptance number moves except where this WP names it.

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest -n auto --dist loadgroup tests/test_acceptance_stephens.py tests/test_parametric_series.py
.venv/bin/python -m ruff check src tests examples
```

## References

- Searle, S. R. (1971). *Linear Models*. Wiley, p. 169.
- Prince, E. (2004). *Mathematical Techniques in Crystallography and Materials Science*, 3rd ed.
  Springer, § Correlation and § Constraints.
- van der Sluis, A. (1969). Condition numbers and equilibration of matrices. *Numer. Math.* 14,
  14–23 (the equilibration this WP leaves alone).
- `docs/practice.md`, the row on esds along undetermined directions (WP-2028, PR #1668).

## Handover log

- **2026-11-19** — created from WP-2028's open question and the maintainer's delegation. No
  open WP owns it: WP-2028's own handover says the answer is its own WP, and WP-1535 is closed.
  The ruling, its grounds and the measured cost are under § Decisions. Next: the triple hold
  first, because it removes the one exact case presets can reach, and the slow-suite probe
  re-run after it shows how much the no-esd rule still has to cover.
