# WP-2076 — The extinction screen names a wrong class at a correct cell

Milestone: unscheduled · Status: 🔄 2026-11-13 — option (c)'s allowance measured (2·ln N + d). Ruled by Yue 2026-11-13: option (a); the landing task is open (PR #1466)
Track: What fires, and what stays silent
Depends on: — (1910 soft: its second screen agrees with the wrong class here; 2062 soft: its decision 2 moves the screen's fits to Pawley)
Priority: P2 2026-11-07 — a silent wrong answer on a path few fits run: at a prefit cell within 600 ppm the default screen names a class excluding the true group on 318 of 1082 synthetic rows (41 groups), and nothing fires. Yue ruled the repair on 2026-11-07, so it is ready to build

## Goal

At a cell the data have refined, `determine_extinction_symbol` names a class
containing the true group, or it names none and says which position it could
not decide. It never names a class that excludes the true group when the
evidence for that class is a fit-path difference rather than an absence.

## Context

**Source.** A synthetic sweep run 2026-11-01 for PR #1286 (WP-1910's second
screen, the task "The default's confident misses"). The data, the scripts and
the per-row results are on the maintainer's machine at
`~/.cache/ghostshift/rietx/wp-1910-sweep/`. That directory is a private cache,
cited here as the measurement's location. It is not in the repository.
`sweep_core.py` builds each pattern and runs one row. `rows_main.csv` and
`rows_extra.csv` hold the 1230 rows. `diag_p63mmc_bkg.txt` and
`diag_fm3m_bkg.txt` hold the per-class tables of two rows.

**The sweep.** All patterns come from rietx's own forward model.
- 41 space groups, one per extinction situation (`sweep_core.GROUPS`).
- Three atoms (Ca, Si, O) at random general positions, one structure per
  group (`seed=11`), Biso 0.8 Å².
- Cu Kα1+Kα2, Bragg-Brentano, 10-80° 2θ at 0.02°.
- 20 000 net counts at the strongest line on a Chebyshev background of about
  200 counts, then Poisson noise.
- The candidate cell is the true cell scaled by one of six factors (×0.985 to
  ×1.0075). The default `refine_cell=True` refines it in the cell-free prefit.
- Arms: the declared instrument carries an all-zero background (`clean`,
  `profile`, `zero`) or the true background (`+bkg`). `profile` scales the true
  widths by 1.3; `zero` adds a 0.02° zero shift.
- "Default" below is `ExtinctionScreen._own_best()`, which is main's ranking.
  "Held" is #1286's `held_screen.best_or_none()`.

**What fails.** Over the rows whose prefit cell lies within 600 ppm of the
truth on every axis, both screens name the same class, and that class excludes
the true group:

| group | both screens name | rows | prefit cell, worst axis |
|---|---|---|---|
| P 6₃/m m c | `P 63 - -` | 9 of 12 `+bkg` rows | 48-101 ppm |
| P 6/m c c | `P 63 - -` | 6 of 12 `+bkg` rows | 339-453 ppm |
| P n -3 n | `P 41 - -` | 9 of 12 `+bkg` rows | 47-599 ppm |
| P 4/n m m | `P - 21 -` | 16 of 30 rows, 4 of them `+bkg` | 14-178 ppm |
| F m -3 m | `F 41 - -` | 8 of 30 rows, 7 of them `+bkg` | 13-264 ppm |

`screens_disagree()` is false on every row counted, so `best_or_none()`
returns the wrong class and no diagnostic fires. Outside the table the three
hexagonal and cubic P groups fare no better. In the zero-background arms their
held screen is `unreliable` (#1286's reference gate), so the default stands
alone and names the same wrong class. F m -3 m differs by arm. Under `zero` and
`zero+bkg` both screens name `F - - -` wherever they name a class. Under `clean`
and `profile` the default names `F 41 - -`, the held screen names `F - - -`, and
#1286 abstains.

**Which lines are weak** (re-measured 2026-11-02 on this tree from the sweep's
structures, noise-free, Kα1 only, peak height over the strongest line's):
- F m -3 m: {200} at 21.39° is 1.1 × 10⁻³ of the strongest line. That is about
  22 counts on a 200-count background. `F 41 - -` forbids it in the cubic
  setting.
- P n -3 n: {200} is 2.4 × 10⁻⁴, {400} 1.5 × 10⁻³.
- P 6₃/m m c and P 6/m c c: (002) is 2.9 × 10⁻³, (004) 2.4 × 10⁻⁴. Both
  groups and `P 63 - -` allow them, so these lines do not decide the hexagonal
  cases.
- P 4/n m m: the n-glide's forbidden (100), (300) and (210) carry 1 × 10⁻⁴ or
  less, which is the tails of neighbours. `P - 21 -` allows (210), so the screen
  failed to prefer the more specific true class.

So the five are two failures. F m -3 m (and part of P n -3 n) is an
**over-read**: a class forbids a weak allowed line. P 6₃/m m c, P 6/m c c and
P 4/n m m are **under-reads**: the true class forbids more, and it lost.

**A lead from the two diagnosed rows.** The ranking is ΔBIC against the
absence-free reference fit (`extinction.py:1374`, `report.layer2.delta_bic`):
ΔBIC = N·ln(χ²_class/χ²_ref) − n_testable·ln N. Here N = 3501 points and
ln N = 8.16. One testable position therefore buys a class 8.2 at most.
- F m -3 m, `clean+bkg` ×1.0: `F 41 - -` reads ΔBIC −127.4 (default) and −147.8
  (held), each on one testable position. So its own fit has χ² 3.3 % and 4.0 %
  **below** the reference fit's. The reference allows every line the class
  allows, plus {200}.
- P 6₃/m m c, same arm: `P 63 - -` reads −67.1 on one position and −105.9 on
  two. The true class `P - - c` reads +137.8 and is refuted (default), or +37.2
  and not refuted (held).

*Superseded in part 2026-11-05: § Findings measures this lead. The first of
the two causes below is false, because the reference is itself a `_fit_class`
fit under `_screen_plan` (`extinction.py`, `ref_fit, ref_result`). The second
cause holds.*

A model with fewer lines that fits better than the model that contains it is
not a nested comparison. The ΔBIC then reads the fit's path, not the absence.
Two causes are possible and neither is measured. Each class's Le Bail fit runs
under `_screen_plan` from the frozen shared state, while the reference is the
shared `validation_plan` fit. And a Le Bail pass partitions intensity
iteratively without minimising χ² over the intensities, so its χ² is
path-dependent (WP-2011 measured one Le Bail pass stalling on true corundum and
zircon; WP-2062's decision 2 is whether the screen moves to Pawley). P 6/m c c,
P n -3 n and P 4/n m m were not diagnosed.

**Siblings in the same sweep** (rows where both screens agree on a wrong class
with the prefit cell within 600 ppm, all arms; 20 groups in all). P 3₁21 names
the absence-free `P - - -` on 4 of its 12 `+bkg` rows (32-41 ppm). It is the one
sibling that persists with the true background declared, so task 4 treats it as
a sixth case. The rest sit mostly in the zero-background arms, where #1286's
held screen is weak by design (WP-1910 § Tasks, the ruling of 2026-10-26):
P 4/m b m `P - 21 -` 8 rows (3 `+bkg`), C 2/c `C 1 - 1` 7 (2), P 2/c and P 2₁/m
`P 1 - 1` 7 each (0), P 2₁/c 6 (0), F d d d and C m c e 5 each, I 4₁/a and
I 4₁/a m d 3 each, P b c a and P -3 c 1 2 each, P 4₁22, P 6₁22 and I b a m 1
each.

**What the screen already does.** The module docstring (`extinction.py:31-100`)
holds the three rules this WP must keep. A count is over positions, not orbits.
A position is evidence only when it is testable (`_model_is_quiet`, WP-1077).
A less restrictive class is never refuted, only outranked. `best_or_none()`
needs a margin of `DECISIVE_DELTA_BIC` = 10 (Kass & Raftery 1995) over the next
surviving class.

**Tier.** The ranking is named practice: a nested BIC comparison (Schwarz 1978)
read at Kass & Raftery's margin. Restoring nesting is a fix to that practice and
adds no judgement. Any new abstention or diagnostic code is a new rule: it needs
an `_audit` row, and its tier and dated approval are the maintainer's.

**Licensing.** Concepts only. Markvardsen et al. (2001) is the Bayesian form of
the screen and stays a v2 fence.

## Findings

Measured 2026-11-05 on main at `29b75345a`, `[dev]`, macOS arm64. Scripts, rows and the candidate
patch are on the maintainer's machine at `~/.cache/ghostshift/rietx/wp-2076/` (`probe/`,
`candidate.diff`). `determine_extinction_symbol` was run through `sweep_core.py`, on `best_or_none()`
of main, without #1286.

**The mechanism.** A Le Bail χ² is not a minimum, so the comparison the screen calls nested is not
nested. Two parts of `CompiledModel.lebail_update` produce this.

- A line with no neighbour takes a share of 1 at every channel of its window. Its intensity is then
  Σ net / Σ Ω over the whole window, and no profile weighting is applied.
- `net` is clamped at zero per channel. On a background of 200 counts that hands each window about
  0.4 σ per channel of rectified noise. That figure is the mean of a rectified Gaussian, computed
  and not measured.

The result is a false peak at every weak or forbidden position. On the F m -3 m row (`clean+bkg`,
×1.0, seed 11) the reference calculates 408 counts at the {200} peak, where 250 were observed and the
true line stands 22 above the background. The reference's χ² is 9854 over 3501 points. A Pawley fit
of the same model reads 4555, and with its profile refined too 3531. The Le Bail background then sits
about 10 counts low at high angle (mean over 70-80°: 160 against Pawley's 171).

- **The over-read.** The reference pays for false peaks that a class forbidding the line does not.
  Removing a 22-count line improves χ² by 330, so `F 41 - -` reads ΔBIC −127.
- **The under-read.** The class fit keeps false peaks of 8-25 σ at every position it allows
  (P n -3 n: 12 such positions, true heights 4 × 10⁻⁶ to 5 × 10⁻⁵ of the strongest line), and the
  sunken background reads +3.3 to +7.2 σ at positions the true class forbids. That refutes it.

Partitioning the signed net removes most of the excess (χ² 4117) and does not restore nesting
(`F 41 - -` still −96), so the clamp is one part of the cause. Raising the Le Bail cycles from 3 to
100 moves χ² by 0.04 %.

**Every certified answer on main reads through the same break.** With nesting, ΔBIC cannot go below
−n_testable·ln N. Main passes that floor on all of these rows:

| pattern | class | ΔBIC, main | testable positions | floor | class χ² against reference χ² |
|---|---|---|---|---|---|
| SRM 676a corundum | `R - c -` | −1301 | 6 | −49 | 12 205 < 17 453 |
| FAP | `P 63 - -` | −84 | 1 | −8.2 | 11 486 < 11 719 |
| PbSO₄ X-ray | `P c - n` | −564 | 7 | −61 | 24 561 < 26 789 |
| synthetic Si | `F d - -` | −1058 | 2 | −19 | 15 401 < 16 797 |

So an abstention on "class χ² below the reference" abstains on every row the suite certifies.

**Task 1: the five, five seeds.** 375 rows (three `+bkg` arms, ×0.995-×1.0075), 356 of them at a
prefit cell within 600 ppm.

| group | main: right / none / wrong | candidate: right / none / wrong |
|---|---|---|
| F m -3 m | 66 / 0 / 9 | 70 / 5 / 0 |
| P 4/n m m | 0 / 21 / 54 | 75 / 0 / 0 |
| P 6/m c c | 8 / 1 / 63 | 72 / 0 / 0 |
| P 6₃/m m c | 44 / 0 / 28 | 72 / 0 / 0 |
| P n -3 n | 0 / 0 / 62 | 57 / 0 / 5 |
| all | 118 / 22 / 216 | 346 / 5 / 5 |

F m -3 m fails on seed 11 alone, so that row is specific to its structure. P 6₃/m m c fails on four
seeds of five. P 4/n m m, P 6/m c c and P n -3 n fail on all five, so those are the screen's behaviour.

**Task 2: which reflections decide.** `decide.py`, one row per group, `clean+bkg`, ×1.0, seed 11.

- F m -3 m: only {200} at 21.39° differs (height 1.15 × 10⁻³). Against `F 41 - -` it reads +2.8 σ,
  under the 3 σ test, and the model there is 0.0 σ. Testable.
- P 6₃/m m c: five positions, all forbidden by the true class only. Four carry 2 × 10⁻⁶ to 3 × 10⁻⁵
  and one 7 × 10⁻⁴.
  The refutation is (4 -2 3) at 65.40°, height 1.8 × 10⁻⁶, reading +3.8 σ against the true class, whose
  own model predicts 0.4 σ there. So the refuting intensity is the sunken background.
- P n -3 n: 13 positions, {200} forbidden by `P 41 - -` and twelve by the true class. The true class
  is refuted at +3.3 to +4.9 σ on heights of 4 × 10⁻⁶ to 2 × 10⁻⁵, with its model at 0.0-1.3 σ.
- P 6/m c c: 16 positions, all forbidden by the true class only. It is refuted at (2 -1 3), (1 0 5)
  and (4 -2 3), reading +3.2, +6.2 and +7.2 σ on heights of 4 × 10⁻⁶, 3 × 10⁻⁶ and 2 × 10⁻⁶.
- P 4/n m m: three positions differ, (2 1 0), (3 2 0) and (4 1 0). The true class is not refuted.
  `P - 21 -` keeps those lines and reads χ² 6565 against the true class's 6619, so it wins by ΔBIC 21.

**Task 3: the lead.** Over all 1230 rows on main, 2410 of 14 788 class fits land below the reference,
on 828 rows. The absence-free class under `_screen_plan` is the reference, so that comparison has no
content (§ Context's note). Under Pawley the ranking changes on all five groups:

| variant | nested? | five groups, 356 rows | certified rows |
|---|---|---|---|
| main | no | 118 / 22 / 216 | all keep their classes, through the break |
| Pawley for the class and reference fits | mostly | 261 / 69 / 26 | corundum → `R - - -` (+70) |
| all four fits Pawley | mostly | 341 / 10 / 5, and the prefit cell passes 600 ppm on more rows of the hexagonal groups | corundum → `R - - -` (+59) |
| Le Bail, scored on testable lines | no | no change on the two rows run | |
| **candidate**: Le Bail prefit, Pawley shared and class fits, scored on testable lines | 29 of 12 513 class fits below the reference (good-cell rows) | 346 / 5 / 5 | below |

Pawley alone loses corundum because the reference's four extra lines at *untestable* positions soak
up the misfit of neighbouring tails (χ² 11 021 against 11 401), while the BIC charges for only the six
testable ones. So the score must drop only the lines the class is charged for. The candidate fits one
more model per class: the lattice minus that class's testable forbidden lines. Corundum's χ² then
differs by 10 over six positions, as a nested comparison should.

A Pawley screen is unit-independent on the two rows tried (pattern and σ × 5 × 10⁻⁵, every printed
digit the same). That was run with Pawley for the class and reference fits, without testable-line
scoring. WP-2062's open unit-dependence task does not reach it there.

**The candidate over all 1230 rows** (1082 with the prefit cell within 600 ppm):

| | right | none | wrong |
|---|---|---|---|
| main | 731 | 33 | 318 |
| candidate | 914 | 158 | 10 |

No row goes from right to wrong. 259 go from wrong to right and 49 from wrong to none. 89 go from
right to none: F d -3 m 30, P m m m 30, F d d d 20, I 4₁/a m d 9. CPU cost: 525 s against 575 s over the
375 rows, and 37 s against 70 s on PbSO₄ under load.

**What the candidate costs on certified rows.** With nesting restored the scores are small, so three
rows change.

| pattern | candidate | why |
|---|---|---|
| corundum, NAC | keep their classes | `R - c -` −46; NAC `I - - -` |
| FAP | None | `P 63 - -` −8.2 on one position, Δχ² 0.0. One position buys ln N = 8.2, under the margin of 10 |
| Si | None | `F d - -` −17.7 against `F 41 - -` −8.4, margin 9.3 |
| PbSO₄ X-ray | **`P c - a`, wrong**, margin 17.0 | `P c - a` has eight testable positions and `P c - n` six. χ² differs by 0.8, so the margin is the count alone |

In the three extinction test files main reads 74 passed, 5 xfailed. The candidate reads 19 failed,
59 passed, 1 xfailed. Of the 19, four are strict xfails of WP-1910's confident misses that now pass.
Four are `does_not` rows, where the margin widened and the true class now returns. Seven are FAP, three
are Si and one is PbSO₄, as in the table.

**The margin is doing real work.** `DECISIVE_DELTA_BIC` under the candidate, replayed offline from the
stored classes of the 1082 rows. The certified columns are arithmetic from their class tables, and no
test ran at a margin other than 10.

| margin | right | none | wrong | FAP, Si | PbSO₄ | corundum, NAC |
|---|---|---|---|---|---|---|
| main, 10 | 731 | 33 | 318 | keep | keep | keep |
| 8 | 999 | 43 | 40 | keep | wrong | keep |
| 10 | 914 | 158 | 10 | None | wrong | keep |
| 15 | 841 | 231 | 10 | None | wrong | keep |
| 18 | 720 | 360 | 2 | None | None | keep |
| 20 | 720 | 360 | 2 | None | None | keep |

At 8 all 30 new wrong rows are P m m m named as a class on one quiet position. That is FAP's evidence
with the opposite truth, so a single silent position cannot tell the two apart. PbSO₄'s margin of 17.0
is two silent positions at ln N = 8.5, with no χ² behind it.

`best_or_none()` is what these columns count. The ranked list stays on the result. Of the 360 rows that
abstain at 18, the true class leads the list on 314 and sits in the top two on 352. The other eight are
rows where it was refuted. At 18 eleven groups abstain on every row: C m c e, F d -3 m, F d d d,
I 4₁/a m d, I a -3 d, P 4/n m m, P 4₁22, P 4₂/m, P 6₁22, P a -3 and P m m m.

A rule aimed at PbSO₄ alone failed. "Abstain when a class not nested with the winner stays within 10 on
χ²" takes 333 of the 914 right rows to None and fixes none of the ten wrong ones (replayed offline,
nesting read position by position off the symbols). At a χ² margin of 4 it still costs 241.

**Task 4: the siblings.** Main is wrong at a good cell in 23 groups. On 204 of its 318 wrong rows the
winner reads below the reference. On the other 114 the winner is the absence-free class itself, because
every class with an absence was refuted. The true class is refuted on 280 of the 318. Under the
candidate 21 of the 23 groups have no wrong row left, the sixth case P 3₁21 among them, so those 21 share
the mechanism. P 4/m b m (8 rows) and P -3 c 1 (2 rows) keep wrong rows in the zero-shift arms. Those
were not diagnosed, and they may share it only in part. The sweep's sibling list counted rows where #1286's
two screens agree, so its counts are lower than these.

**A residual, not this mechanism.** The five P n -3 n rows left wrong under the candidate are one
pattern (`clean+bkg`, seed 13). `P n - -` wins because the true class is refuted once at (5 1 1), 57.66°,
among 13 tested positions. That reads as the 3 σ test's false rate over many positions, and it was not
diagnosed further. WP-1077's fence covers that test.

## Questions for the maintainer

Questions 1 and 2 were answered by Yue on 2026-11-07 (handover entry of that date); the
questions and their measurements are in the entry of 2026-11-05. Question 3, the allowance's
`_audit` row, was answered by Yue on 2026-11-13: **option (a)**. `best_or_none()` names the leading
class only when its lead over the runner-up strictly exceeds max(`DECISIVE_DELTA_BIC`, 2·ln N + d),
d the tested positions where the two classes differ. The tier-3 row is approved, dated 2026-11-13.
The question and its measurements are in the handover entry of 2026-11-08 (second session).

## Non-goals

- #1286's disagreement rule and the held screen (WP-1910).
- A cell the prefit gets wrong (WP-1910).
- Loosening the absence test or `_model_is_quiet` (WP-1077's fence, restated in
  WP-1910 § Non-goals).
- Moving the screen's fits to Pawley as a default for every caller. That is
  WP-2062's decision 2. This WP may measure it as a candidate repair.
- The Bayesian posterior (v2 fence).

## Tasks

- [x] Reproduce the five on main from `sweep_core.py` (`+bkg` arms, ×0.995-
      ×1.0075). Add four more seeds per group, so a structure-specific
      accident is told apart from the screen's behaviour. Record per class:
      χ², n_testable, ΔBIC, refuted position, and the reference χ².
- [x] Find which reflections decide each case. For every position the winning
      class and the true class treat differently, give its 2θ, its noise-free
      height over the strongest line, its integrated signal over σ in the
      absence window, and whether it was testable. For a refuted true class,
      say what the class's own model predicts at the refuting position.
- [x] Test the lead. Count the classes whose χ² falls below the reference's on
      all 1230 rows. Fit the absence-free class under `_screen_plan` and compare
      it with the reference. Fit the five under Pawley (WP-2062's A2 row) and
      record whether the ranking changes.
- [x] Classify the siblings above by the same mechanism, and say which share
      it and which do not.
- [x] Repair the mechanism task 3 names. If the fix is a new abstention or a
      diagnostic code, bring its audit row to the maintainer before landing.
      Corundum and NAC keep their classes; FAP and Si abstain; PbSO₄ names
      `P c - a`, the known wrong answer the ruling accepts.
      *Decided 2026-11-07 (Yue): land the candidate here at margin 10, once the
      screen times under 30 s on NAC. At margin 10 FAP and Si give None and PbSO₄
      names `P c - a`, so the rows' clause is rewritten to that. Measure option
      (c)'s allowance before any tightening. Handover entry of 2026-11-07.*
- [x] Tests: the five synthetic groups as rows, built in-test from rietx's
      forward model (no data file), with obs/calc/diff PNGs to `tests/output/`.
      `tests/test_extinction_nesting.py`.
- [x] Skill: a row in `references/diagnostics-indexing.md` if a code is added,
      or "none" and why. None: no code was added. The existing
      `EXTINCTION_SYMBOL_AMBIGUOUS` now names the tested positions two leading
      classes differ at, so the package's own output carries the guidance, and
      the `EXTINCTION_FORBIDDEN_INTENSITY` row's stale Le Bail and held-cell
      wording was corrected.
- [x] A class fit or scoring fit that raises leaves its class unscored, not
      refuted, so the screen abstains and names the error. Consented 2026-11-07
      (shift bundle item 3). `tests/test_extinction_symbol.py`.
- [x] Re-measure `SCREEN_LEBAIL_CYCLES` on the prefit alone (shift bundle item 4).
      The measurement separated nothing, and the constant was removed: the prefit's
      partition now settles like every other Le Bail fit's. Settled by Claude under
      Yue's delegation of 2026-11-07 ("whatever best fits our design ethos").
- [x] Measure option (c)'s allowance (2·ln N plus an allowance derived from the
      count of silent positions) and real patterns from the eleven groups that
      abstain on every row at margin 18, then bring the allowance's `_audit` row
      to the maintainer before any margin moves. Ruled 2026-11-07.
      *Measured 2026-11-08 (handover entry of that day, second session): the
      allowance is d, the count of tested positions where the two leading classes
      differ. The row is Question 3 below; no margin moved.*
- [ ] Ruled by Yue 2026-11-13: option (a). Land the margin in
      `ExtinctionScreen.best_or_none` with its `_audit` row, flip PbSO₄'s pinned
      row to `None`, and rewrite the acceptance clause to match. The row carries
      `approved="2026-11-13"` and the grounds quoted in the handover entry of 2026-11-13.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_extinction_symbol.py tests/test_extinction_margin.py tests/test_extinction_gate.py tests/test_extinction_nesting.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

On P 6₃/m m c, P 6/m c c, P n -3 n, P 4/n m m and F m -3 m, with the true
background declared and the cell within 600 ppm, `best_or_none()` returns a
class containing the true group or `None` with a finding naming the undecided
position. It never returns a class that excludes the true group. The certified
corundum and NAC rows keep their classes, FAP and Si abstain with the undecided
position named, and PbSO₄ names `P c - a`: the known wrong answer the ruling of
2026-11-07 accepts at margin 10 (handover log), pinned so a tightening shows.

## References

- Schwarz, G. (1978). *Ann. Statist.* 6, 461-464. The BIC.
- Kass, R. E. & Raftery, A. E. (1995). *J. Am. Stat. Assoc.* 90, 773-795. The
  margin `DECISIVE_DELTA_BIC` quotes.
- Markvardsen, A. J., David, W. I. F., Johnson, J. C. & Shankland, K. (2001).
  *Acta Cryst.* A57, 47-54. The Bayesian screen; a v2 fence.
- PR #1286 and WP-1910 (the second screen); WP-1077 (testability); WP-2011 and
  WP-2062 (Le Bail against Pawley).

## Handover log

### 2026-11-08 (second session) — option (c)'s allowance, measured; its row goes to the maintainer (PR #1466)

Option (c) now has a value that is derived rather than tuned: the screen names a class only when
it beats the runner-up by more than two silent positions' worth (2·ln N) plus d, where d is the
number of tested positions at which the two classes differ. On a rebuilt 41-group synthetic
sweep it gives the same answers as the fixed 18 at this N, while scaling with N. It stops the
certified PbSO₄ miss and one real wrong answer (CuCr₂O₄ at 289 K), and it costs real Si 640c its
right answer. It does not fix the synthetic P 2₁/c at ×0.995, which wins on three silent
positions. Nothing in `src` moved. The row below is for the maintainer to rule on before any
margin changes.

*The derivation.* Under the nested Pawley scoring a tested forbidden position p moves its class's
ΔBIC by z_p² − ln N, where z_p is the position's Pawley intensity over its esd. So between two
unrefuted classes W (leading) and R (runner-up), D = ΔBIC_R − ΔBIC_W is a sum over the positions
where they differ only: (ln N − z²) for each position W alone forbids, (z² − ln N) for each R alone
forbids. Every such position is silent (an unrefuted class carries no intensity at a position it
forbids), so with no line anywhere D = (net count)·ln N plus chance in the z² terms. Option (c)
says a net count of two never decides. The allowance covers the chance: d silent positions carry
χ²_d by chance, whose mean is d. So the bar is 2·ln N + d, strictly exceeded. Strict matters:
P 4/m b m's `P - 21 -` rows win by exactly 2·ln N, to 1e-6 relative, because the winner's two
0k0 intensities sit at their Pawley bound of zero.

*Measured* (this worktree's `[dev]` venv, macOS arm64, main `63d7c120a`; pearl did not answer
two wake attempts, so everything ran on the Mac, two processes, ~25 min). The 2026-11-01 sweep's
files are on the maintainer's machine, so the sweep was rebuilt from § Context:
`~/.cache/ghostshift/rietx-src/wp-2076/probe/sweep.py` on the contributor's machine. It covers
41 groups (the 25 this WP names plus 16 chosen to cover the remaining extinction situations), five
arms (`clean`, `profile`, `zero`, `clean+bkg`, `zero+bkg`) and six factors (×0.985 to ×1.0075),
with seed 11 and the five specimens' own builder in `tests/test_extinction_nesting.py`. That gives
1230 rows, 974 of them with the prefit cell within 600 ppm, all at N = 3501 (2·ln N = 16.3).
`replay.py` replays `best_or_none()` from the stored class tables. Its positive arm is that at
margin 10 the replay returns the package's own answer on all 1230 rows.

| margin rule (974 rows) | right | none | wrong |
|---|---|---|---|
| 10, main | 858 | 105 | 11 |
| 18, fixed | 634 | 339 | 1 |
| 2·ln N, strict | 640 | 328 | 6 |
| **2·ln N + d** | **634** | **339** | **1** |
| 2·ln N + χ²_d at Φ(1) | 632 | 341 | 1 |
| 2·ln N + χ²_d at 3 σ (`ABSENT_SIGMA`) | 506 | 467 | 1 |
| 2·ln N + χ² of R's own positions only, at 1 σ or 3 σ | 640 / 638 | 328 / 330 | 6 |

The rebuilt sweep reproduces the shape of § Findings (main 914 / 158 / 10, 18: 720 / 360 / 2 on
1082 rows), with different groups. The ten wrong rows at 10 that the rule stops are all P 4/m b m
naming `P - 21 -` on two silent 0k0 positions, its true class refuted in the zero-shift arms. The
one wrong row no margin stops is P -3 c 1 (`zero`, ×0.995): every class but `P - - -` is refuted.
At 2·ln N + d the 339 abstentions all come from the margin, and the true class leads the ranked
list on 329 of them. Twelve groups abstain on every row: F d -3 m, F d d d, I 4₁/a m d, I a -3 d,
P 2₁/c, P 2₁/m, P 4/n m m, P 4₁22, P 4₂/m, P 4₂/n m c, P 6₁22 and P a -3. Nine of these are among
§ Findings' eleven. C m c e and P m m m answer here, so which groups fall is
structure-dependent. The rule that counts only R's own positions leaves the P 4/m b m ties
standing, because with no such position it adds nothing and a solver-tolerance difference
decides. So the allowance counts both sides.

Certified and real rows (`real.py`, `real_table.txt`; class tables of the screen as it stands,
×1.0 unless stated). D is the runner-up's ΔBIC minus the leader's. "Need" is 2·ln N + d.

| pattern | N | leader, D, d | 10 | 18 | 2·ln N + d (need) |
|---|---|---|---|---|---|
| SRM 676a corundum | 3501 | `R - c -`, 45.9, 6 | right | right | right (22.3) |
| 11-BM NAC | 22 003 | `I - - -`, alone | right | right | right |
| FAP | 3751 | `P 63 - -`, 8.2, 1 | none | none | none |
| synthetic Si (gate test) | 11 976 | `F d - -`, 9.4, 1 | none | none | none |
| PbSO₄ X-ray | 5800 | `P c - a`, 17.0, 2 | **wrong** | none | none (19.3) |
| synthetic P 2₁/c (test) | 2750 | `P 1 21/c 1`, 21.8, 3 | right | right | right (18.8) |
| same, ×0.995 | 2750 | `P 1 21 1`, 23.6, 3; true refuted | **wrong** | **wrong** | **wrong** (18.8) |
| Si 640c, 11-BM, ×0.995/1/1.0075 | 40 001 | `F d - -`, 19.7, 3 | right | right | none (24.2) |
| CuCr₂O₄ 289 K, 11-BM, ×0.995/1 | 11 001 | `I 41 - -`, 11.1/17.2, 2; true refuted | **wrong** | none | none (20.6) |
| zircon, CPD lab, ×3 | 3751 | `I 41/a - d`, 8.2, 1 | none | none | none |
| magnetite, CPD lab, ×3 | 3751 | `F 41 - -`, 8.2, 1; true refuted | none | none | none |
| Nd₂Ru₂O₇ 11-BM ×1/1.0075, BT-1 ×3 | 27 001 / 3001 | `F 41 - -`, 8.0-9.9, 1; true refuted | none | none | none |
| Nd₂Ru₂O₇ 11-BM ×0.995; Co₃O₄ and YIG garnet D1B 300 K ×3; CuCr₂O₄ 7 K ×3 | | the absence-free class alone | **wrong** | **wrong** | **wrong** |

The real patterns cover four of the eleven groups (F d -3 m ×5 patterns, I a -3 d, I 4₁/a m d ×2,
F d d d). The other seven have no committed real pattern. Zircon behaves like its synthetic rows:
the true class leads by one silent position and abstains at every margin tried. The ten real
rows wrong at every margin are not margin failures. In each, the true class is refuted by
intensity at a forbidden position: (2 0 0) on the D1B patterns at λ = 2.52 Å, where λ/2 puts
(4 0 0) intensity; (1 1 0) at 5.55° on CuCr₂O₄, beside its CuO impurity; (4 2 0) on the CPD
magnetite; (6 4 0) on BT-1 Nd₂Ru₂O₇. Those causes are read off positions and not tested. The
absence test is WP-1077's fence, and a declared λ/2 is the caller's (`harmonics=`). Si 640c is the
"fixed 18 slips with N" case, seen from the other side: at N = 40 001 two silent positions buy
21.2, and `F d - -` leads `F 41 - -` by 19.7 on three positions with χ² 12 against it.

**Question 3: the allowance's `_audit` row.**

- *The decision.* Whether `best_or_none()` demands max(`DECISIVE_DELTA_BIC`, 2·ln N + d), strictly
  exceeded, in place of 10. It comes to the maintainer because the 2 is tier 3, which needs a dated
  approval, and because the change withholds right answers.
- *Why it matters.* At margin 10 a user sees a wrong class on 11 of 974 rebuilt rows, on PbSO₄ and
  on CuCr₂O₄ 289 K, and nothing fires. At 2·ln N + d they see 1 wrong row, and None on 234 more
  rows, 224 of which were right at 10; the true class leads the list on 329 of the 339 abstentions. Importance: serious.
- *Options.*
  (a) 2·ln N + d, the recommendation. 634 / 339 / 1. PbSO₄ and CuCr₂O₄ 289 K give None, while Si
  640c, FAP and the synthetic Si give None too. Corundum, NAC and the test's P 2₁/c keep their
  answers.
  (b) 2·ln N + the 3 σ quantile of χ²_d (`ABSENT_SIGMA`, no new number). 506 / 467 / 1. It also
  stops the P 2₁/c ×0.995 miss (need 31.5), and costs that pattern its ×1.0 answer (D 21.8 against
  the same 31.5) and 128 more synthetic rows.
  (c) Keep 10. 858 / 105 / 11. PbSO₄ stays wrong, as ruled 2026-11-07.
  Dropped: a fixed 18 (identical tallies here, but it slips with N, as Si 640c shows), and counting
  only the runner-up's positions (it leaves the ties at exactly 2·ln N to the solver).
- *Practice.* None found. ExtSym reports ranked probabilities and leaves the bar to its reader
  (§ Questions of 2026-11-05). Kass & Raftery's 10 assumes the evidence is in the likelihood, and
  under nested scoring a silent position's evidence is the count alone.
- *Unanimity.* Would every competent refiner decline to name a class whose lead is two positions
  showing nothing? Not every one. A refiner who reads ΔBIC > 10 as "very strong" names `P c - a`,
  and on an ExtSym-style reading the more absent class is the more probable. So the action is
  withholding the singleton while keeping the ranked list, which is a report and not a decision,
  per DESIGN.md § Rules, 1.
- *Recommendation.* (a). It meets the ruling's form (2·ln N plus an allowance from the count),
  has no fitted number beyond the 2 the ruling chose, and stops every wrong row a margin can
  reach except the three-position one, which (c) excludes by construction.
- *The row as proposed* (constant name to be settled at landing):

  ```python
  Row("rietx.indexing.extinction.SILENT_POSITIONS_UNDECIDED", "constant", tier=3, value=2,
      evidence=("best_or_none() names the leading class only when the runner-up's ΔBIC exceeds "
                "it by more than max(DECISIVE_DELTA_BIC, value·ln N + d), d the tested positions "
                "where the two differ. Under nested Pawley scoring each such position moves ΔBIC "
                "by z² − ln N, so a silent one buys ln N and nothing else (Schwarz 1978), and d "
                "is the mean of the χ²_d chance gives d silent positions: arithmetic. The value is "
                "ours: PbSO4 X-ray (Hill 1992) names P c - a over P c - n on two silent positions "
                "(17.0 at N 5800). Rebuilt WP-2076 sweep, 974 rows within 600 ppm: right/none/"
                "wrong 858/105/11 at 10, 634/339/1 here. Real: PbSO4 and CuCr2O4 289 K (11-BM) "
                "wrong -> None; Si 640c (11-BM, N 40 001) right -> None; corundum (SRM 676a), "
                "NAC keep. Measured on one synthetic family (rietx forward model, Cu Bragg-Brentano, "
                "Ca/Si/O) and thirteen real patterns, untested beyond."),
      grounds="...", approved=None)  # as proposed 2026-11-08; the ruled form is in the entry of 2026-11-13
  ```

*Not done.* No code, so no test suite ran beyond step 10's checks, and `/code-review` did not
run (prose-only branch). The generality judge was not dispatched, because no `_audit` row changed;
the row above is a proposal for the maintainer. The sweep has one seed per group, where § Findings'
task 1 used five on five groups.

*Next.* The maintainer answers Question 3. On (a) or (b): the open task above, which lands the
margin in `ExtinctionScreen.best_or_none` with d read off `tested_two_theta` (rounded to 1e-3°,
as the replay did, because two classes can name different hkl at one position), adds the row,
and flips `test_pbso4_xray_gets_its_class_only_through_the_seeded_prefit` to `None`. The suite's
FAP and synthetic Si rows already abstain, and its corundum, NAC and P 2₁/c rows keep their
answers under both. On (c): close the WP.

- **2026-11-13** — Yue ruled Question 3 on PR #1466: **option (a)**. `best_or_none()` names the leading
  class only when its lead over the runner-up strictly exceeds max(`DECISIVE_DELTA_BIC`,
  2·ln N + d), d the tested positions where the two classes differ. The tier-3 row is approved, dated
  2026-11-13. The row for the landing task, with the ruling in place of the proposal's
  `approved=None` and `grounds="..."`:

  ```python
  approved="2026-11-13",
  grounds="Ruled by Yue 2026-11-13: 2·ln N + d, strictly exceeded, as max(DECISIVE_DELTA_BIC, 2·ln N + d)",
  ```

  The constant name is still to be settled at landing. Correction to the PR #1466 description: Si 640c
  at N = 40 001 needs 2·ln N + d = 21.2 + 3 = 24.2 against a lead of 19.7, as this file has it; the
  description's 21.2 omitted the d. No code moved. *Next:* the open task above lands the margin, adds
  the row, and flips PbSO₄'s pinned row to `None`.

- **2026-11-08** — CI on PR #1461 failed one row on both Linux legs: FAP at a start ×0.99 read
  `failed` where the gate test expects `unreliable`. The cause predates this branch. Outside the
  prefit's basin the prefit runs W to its 32 400 deg² bound, and whether any reflection then
  survives the window filter flips on rounding. With none, the screen took the "this cell
  predicts no reflections" branch, whose advice (the cell is far too small) is wrong there.
  Measured on macOS arm64 over 12 relative nudges of the start (±1e-14 to ±1e-4): 6 of 12 hit
  it with the settled prefit, 1 of 12 with three cycles, so main's CI was lucky on the row.
  *Done.* When the reference kept no reflection but the lattice group predicts some in range
  (`generate_reflections`), the screen now reads the reference gate first, and a reference
  past `REFERENCE_NET_RWP_MAX` gives `unreliable` with `EXTINCTION_SCREEN_UNRELIABLE`, as at any
  other cell outside the basin. A lattice that predicts nothing in range still gives `failed`.
  All 12 nudges now read `unreliable`. Test:
  `test_extinction_gate.py::test_a_prefit_whose_widths_left_no_reflection_reads_unreliable`,
  five nudges, each failing without the fix. Every test reaching the screen, slow rows
  included: 357 passed, 2 skipped, 1 xfailed (`[dev]`, macOS arm64). The generality judge was
  not re-dispatched: this reorders two existing verdicts (the gate before the empty-table
  failure) and adds no threshold. *Next:* unchanged, the margin task.

### 2026-11-07 (fourth session) — a raised fit abstains; the prefit's partition settles

The screen no longer treats a solver failure as evidence against a class. If a class's fit, or
the refit that scores it, raises, the class stays unrefuted and unscored, and the screen
declines to name a class and says which fit raised. Before, a crash refuted the class. That
could hand a rival a confident answer. One exception keeps evidence: when only the scoring
refit raises, the class's own fit still stands, and its forbidden intensity can still refute
it. Separately, the prefit's 3 Le Bail cycles were measured against a settled partition. The
measurement does not separate them. Settling recovers a synthetic cell that 3 cycles lose, and
it moves FAP's cell by up to 1474 ppm. Shown that, Yue delegated the call to the design ethos.
The prefit now settles its partition like every other Le Bail fit in rietx, and the constant is
gone. No test that reaches the screen moved.

**Done.**
- Shift bundle item 3 (consented 2026-11-07): `determine_extinction_symbol` records a raised
  class fit or scoring refit in a per-screen map and sets `screened=False`. Then
  `best_or_none` abstains, and `EXTINCTION_SYMBOL_AMBIGUOUS` names the first error and counts
  the rest. When the error is the only reason, its suggestion becomes "Run the screen again".
  A raised scoring refit is cached like a fit, so a class sharing its line set does not
  repeat it. The absence test still runs on the class's own fit. Schema docstrings for
  `screened`, `n_testable`, `chi2` and `refuted`, and the manual's extinction page, now say
  this. Test: `test_a_class_fit_that_raises_leaves_the_class_unscored[class|scoring]`
  injects a `LinAlgError`. It fails on `main` and passes here.
- Shift bundle item 4: `SCREEN_LEBAIL_CYCLES` and `_fixed_partition` are removed, with the
  constant's `_audit` row. The prefit runs `profile_only` at the `StageSpec` defaults (25 000
  cycles to `lebail_tol` 1e-7). Yue answered the brief with "whatever best fits our design
  ethos" (2026-11-07). Settled by Claude on three grounds. rietx's convention since WP-1542 is
  a settled partition (Yue's ruling B11), and one rule beats a rule with an exception. The 3
  had no source, and its stated term ("until the screen moves to Pawley") had run out. And
  the measurement below is a draw on cells. Practice does not decide it: no surveyed program
  settles a partition at a fixed model, and GSAS-II's `DoLeBail` runs a fixed 10
  (`docs/practice.md`). The one answer that changed went against settling, inside the margin
  task's known failure. An earlier commit on this branch had rewritten the row's grounds to
  keep 3; that lean is superseded. WP-2062's `### Inherited` note says the constant is gone.
- The prefit's partition can now hit its 25 000-cycle cap, and the screen dropped the fit's
  `LEBAIL_CYCLES_AT_CAP`. It now carries it onto `ExtinctionScreen.diagnostics`, prefixed as
  the prefit's and pointing at `refine_cell=False`, since the caller has no stage to raise.
  The judge found this. Test: `test_a_prefit_partition_stopped_on_its_cap_is_reported_on_the_screen`,
  which fails without the hand-off.

**Measured** (`[dev]` venv, macOS arm64, alone on the machine). Prefit at 3 fixed cycles
against settled (25 000 cycles to `lebail_tol` 1e-7), eleven screens:

| pattern | start | 3 cycles: answer, prefit cell | settled: answer, prefit cell |
|---|---|---|---|
| corundum | ×0.995/×1/×1.005 | `R - c -` ×3, dBIC −45.9 | same, cells agree ≤ 10 ppm |
| FAP | ×0.995 | None, −33 ppm | None, +313 ppm (prefit Rwp 0.22 vs 0.12) |
| FAP | ×1.005 | None, −6 ppm | None, −1474 ppm (Rwp 0.54 vs 0.11) |
| synthetic P 1 21/c 1 | ×0.995 | None (`unreliable`): cell lost, a = 6.83 Å | `P 1 21 1`, wrong, at a cell 0.07 % short |
| synthetic | ×1 | `P 1 21/c 1`, −127.87 | same, −127.77 |
| synthetic | ×1.005 | `P 1 21/c 1`, a 1034 ppm off | same, 65 ppm off |
| PbSO₄ | ×0.99/×1 | `P c - a` (known wrong) | same |

The settled ×0.995 wrong class is the Pawley margin failing near the right cell. The third
session found `P 1 21 1` at a held ×0.9994, so this belongs to the open margin task.
Wall time is the same in both arms (0.3-29 s a screen). The eight `tests/test_extinction*.py`
files gave 176 passed, 2 skipped, 1 xfailed in both arms. Fast suite on the final tree (main
`b6ff8e71f`, which the branch contains): 14 294 passed, 416 skipped, 32 xfailed, 0 failed, in
8:42 with this session alone on the machine. An earlier run, before the cap test, gave 14 292
passed and 1 failed (the indexing `CLAUDE.md` line cap, since trimmed), so the cap test is the
+1. This session added 3 test cases; the first two cost 1.12 s in all (local junit). No base
count was measured on this main, so the +3 is not checked against one.

**Review.** `/code-review high --fix` reported nine findings. Fixed: a raised scoring refit
was repeated per class (now cached); the manual's "a fit that raised refutes"; the `screened`
and `n_testable` meanings; the unapproved-grounds provenance. The generality judge's two
gaps also landed: the absence test before the abstention, and the solver-failure suggestion.
Declined: the GUI's "not screened" tooltip in `gui/src/panels/Peaks.svelte` still says "cap or
cancel". Fixing it means rebuilding the committed GUI dist under node 22, and this machine has
node 24. The path is reached by no dataset. Also declined: a per-class error field, which is a
schema change; the first error plus a count rides the screen's message instead. And the
unreachable "every class was refuted" branch, because `extinction_diagnostics` can be handed a
hand-built screen.

*Generality* (the `generality-review` agent, pasted unedited).

**rietx.indexing.extinction.SCREEN_LEBAIL_CYCLES (changed row, tier 3, value 3)**

**holds, but its grounds need two corrections before approval.** The case for keeping 3 is stronger. On the eleven screens, settling the partition improved no answer and cost the same time. The grounds misread the one row where the arms differ. They also leave out the case where 3 cycles fails.

(The prefit: the cell-free Le Bail fit that refines the candidate cell and peak widths before any extinction class is fitted. A partition is one Le Bail redistribution of observed intensity among overlapping reflections. The reference gate is `REFERENCE_NET_RWP_MAX`, 0.7071: above it, the absence-free fit's background-subtracted Rwp sets status `unreliable` and `best_or_none` (the screen's pick verb) returns None. WP-1542 is the change that made rietx's Le Bail partition run until it settles.)

| Question | Author's answer, and where | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | `_audit.py` evidence: "this count governs the cell-free Le Bail prefit alone". Comment at `extinction.py:929-931`: "Settling it was measured on eleven screens". | Confirmed. `_prefit` runs `_fixed_partition(...)` at `extinction.py:1083`, which sets 3 cycles with `lebail_tol=0.0`, so nothing stops it early. The prefit runs by default (`refine_cell=True`, `extinction.py:1160`). Its cell and widths are what every class is then compared at. The package's own default elsewhere is a settled partition: `StageSpec` `lebail_cycles=25000`, `lebail_tol=1e-7` (`strategy/staged.py:143,147`). | holds |
| 2. Kind of ambiguity | Not stated (constant rows carry no `ambiguity` field). | A numerical setting of a fit that feeds a kind-2 ranking (the classes ranked by ΔBIC, the difference in Bayesian information criterion). It is not a verdict of its own. | n/a |
| 3. Case against (keeping 3) | Grounds: "it is the pre-WP-1542 default … The count has no published source". | From the raw output (`p4_fixed.jsonl`, `p4_settled.jsonl`). **Synthetic P 1 21/c 1 at ×0.995: 3 cycles lost the cell.** It landed at a = 6.826, b = 8.734, c = 6.298 Å against the true 8, 10, 7 (10-15 % off), with prefit Rwp 0.85 and net Rwp 0.996. The screen abstained only because the reference gate caught that failure. Settled, the cell came back to within 506-759 ppm of the truth. **At ×1.005**, 3 cycles left a 1034 ppm off and settled 65 ppm. Everywhere else in rietx the partition settles. The practice survey (`docs/practice.md:536-544`, the repository's survey; I did not check the programs) says every program with Le Bail stops on convergence (GSAS-II and FullProf at a 1e-3 relative change in χ²). It also cites Le Bail (2005) that "one pass is not enough to reach the minimum Rwp". | real, partly unstated |
| 4. Case for (keeping 3) | Grounds: "a settled prefit partition gave one confident wrong class and no right answer the 3-cycle prefit missed"; "no competent caller depends on it settling". | **The facts are right but the attribution is wrong.** Settled at ×0.995, the synthetic screen named `P 1 21 1` (ΔBIC −23.6), which excludes the true group. That happened at a prefit cell about 0.07 % short. The third session's held-cell scan already found `P 1 21 1` at ×0.9994. So the wrong class is the Pawley screen's margin failing near the right cell, which is the open option-(c) task (the margin-allowance measurement). It is not settling that misleads. The comment's "a cell 0.5 % short" is the starting cell, not the cell the classes were screened at. Supporting facts that hold: (a) 10 of 11 answers are identical, and at ×1.0 ΔBIC moves by ≤ 0.10 (synthetic −127.87 against −127.77). (b) FAP's settled cells are further from the ×1.0 answer at both offsets: +313 ppm against −33 ppm at ×0.995 (prefit Rwp 0.22 against 0.12), and −1474 ppm against −6 ppm at ×1.005 (Rwp 0.54 against 0.11). The row quotes only the second. (c) Time is the same (0.28-28.8 s in both arms). (d) `armA.log`/`armB.log`: 176 passed, 2 skipped, 1 xfailed in both arms. So WP-1542's "a settled partition failed 10 rows" no longer holds for the prefit alone. The evidence keeps that sentence without saying it is superseded. | stronger, on the answers |
| 5. Tier | 3; "no published source and was not tuned to these rows". | Tier 3 is honest. The survey offers a partial anchor the row does not cite: GSAS-II caps a refinement at 3 cycles by default, `DoLeBail` runs a fixed 10, and MAUD runs up to 5. So 3 lies at the low end of the programs' extraction counts. Those programs also stop on χ² and move the model only one least-squares iteration per extraction, so it is not the same choice made by default. From `docs/practice.md`; I did not check the programs. | holds |
| 6. Dataset families | "SRM 676a corundum, GSAS-II FAP and the synthetic P 1 21/c 1 … and GSAS-II PbSO4". | Four families: three real (NIST corundum from the IUCr round robin; GSAS-II tutorial fluorapatite; GSAS-II tutorial PbSO₄) and one synthetic (rietx's own forward model). References, which the row does not name: for the class, the known space group of each specimen; for the synthetic cell, the truth by construction; for FAP's cell, GSAS-II's converged fit (cross-code, so it only verifies). Corundum's certified cell was not compared; the two arms agree on it to ≤ 10 ppm. **All four are development data** (the screen's own test rows), and the row does not say so. NAC, named in the last review's request, was not run. PbSO₄ ×0.99: both arms leave the cell about 3400 ppm off and name `P c - a`, so no difference there. | holds, with omissions |
| 7. What reports it | none given | `ExtinctionScreen.prefit_rwp` and `.cell` show the outcome. No field records the cycle count or whether the partition settled. Unchanged from the last review. | weak |

Evidence that would change the verdict: a prefit row where settling changes the class at a cell the Pawley margin is known to handle (outside ×0.9994-×1.0012 on the synthetic). For approval, the grounds should say three things: the ×0.995 wrong class arises at a near-correct cell (the open margin task), 3 cycles lost that cell, and FAP's ×0.995 prefit got worse when settled.

**Fallback: a raised class fit or scoring refit leaves the class unscored, not refuted (flagged; the table cannot see it)**

**holds.** The case for abstaining is stronger. A solver failure carries no information about absences, and the package already abstains on a question it left unasked. One branch still throws away a refutation it could have made, and the advice the abstention prints does not fit a solver failure.

(`EXTINCTION_SYMBOL_AMBIGUOUS`: the warning the screen raises when it declines to name a class. The scoring refit is the Pawley fit of the lattice minus only the forbidden lines this class can be tested on.)

| Question | Author's answer, and where | What I found | Verdict |
|---|---|---|---|
| 1. What the caller must now decide | `diagnostics.py:1027-1029`: "Such a class is unscored rather than refuted, and the abstention names the error, since a solver failure is no evidence about the absences." | Confirmed at `extinction.py:1447-1451` and `:1485-1492`. Any raise in either fit now makes `best_or_none` return None (`schemas/indexing.py:2642`). Before, it would have ranked the survivors. The caller must decide whether to rerun, or how to work around the failed class. No verb rescores one class. | holds |
| 2. Kind of ambiguity | Schema text, `schemas/indexing.py` `screened`: "A raised fit is no evidence about the absences, so the class is left unscored rather than refuted". | Kind 2: a ranking that picks only on a clean result, in the pick verb. The old rule ("raised, so refuted") claimed kind 1 and failed unanimity in the last review. There is no row, so nothing records the kind. | holds |
| 3. Case against acting (for abstaining) | Test docstring, `test_extinction_symbol.py`: "Before this either raise marked the class refuted, which took it out of `best_or_none`'s margin test and could hand a rival a confident answer." | Strong. An unscored class could be the true one, since classes do not nest in general. `best_or_none` already abstains for a `max_classes` cap or a cancel, for the same reason. | strong |
| 4. Case for acting (for refuting, or for ranking anyway) | none given | **One real cost.** In the scoring-refit branch the class's own fit has succeeded, and the absence test reads that fit (`extinction.py:1505-1507`), not the refit. The `continue` at `:1492` skips that test. So a class whose own fit shows forbidden intensity, and would be refuted on evidence, now blocks every answer. The old code refuted it, for the wrong reason but with the right outcome. Running the absence test before the `continue` would keep the abstention and lose nothing. How often this happens: no case on disk reaches either branch. Both arms of the prefit measurement pass the same 176 tests, and the only case is the injected `LinAlgError`. **The printed advice misleads:** the code's `suggestion=` is fixed ("Count longer at the forbidden positions … or extend the 2θ range", `diagnostics.py:1188-1189`), which is the wrong next step after a solver failure. | some, unmeasured |
| 5. Tier | none given | No row: the table cannot see a fallback. "A failed fit carries no evidence" is arithmetic (tier 1). I found nothing in `docs/practice.md` on how any program treats a failed class fit. | holds |
| 6. Dataset families | Test `test_a_class_fit_that_raises_leaves_the_class_unscored[class\|scoring]`. | Only an injected raise on the synthetic monoclinic. generality.md accepts an injected case for a guard ordinary fits never reach. The test asserts abstention, no refutation, and the error text in the message. | holds |
| 7. What reports it | `EXTINCTION_SYMBOL_AMBIGUOUS` message: "N class(es) could not be scored … : {error}". | Only the first error's text appears ("(and N more)"). No per-class field carries the error: `refuted_reason` is now None. A cap and a raise both read as `screened=False`, so with two or more failures an agent cannot tell from the record which classes raised. In the scoring branch, `screened=False` sits beside a set `n_testable`, `rwp` and `tested_hkl`. The schema documents this. It departs from the indexing rulebook's "`n_testable` is `None` until `screened`". `EXTINCTION_SYMBOL_AMBIGUOUS`'s own row is still `unaudited` (`_audit.py:688`, on the baseline). | weak |

Evidence that would change the verdict: a case where a raised scoring refit sits on a class the absence test refutes. Running the absence test before the `continue`, plus a per-class error field, would remove both weak rows.

Author's answers. Row 1's "grounds need two corrections": both landed, and then the row was
deleted when the constant went (see *Done*). The judge's review of the deletion follows.
Item 2's weak rows 4 and 7: the absence test now runs before the abstention; a per-class error
field is declined above.

*Generality, second dispatch* (the deletion; the `generality-review` agent, pasted unedited).

**rietx.indexing.extinction.SCREEN_LEBAIL_CYCLES (deleted row, was tier 3, value 3)**

**Verdict: holds.** The case for the deletion is stronger. It rests on the maintainer's own ruling, not on the measurement. The stated reason for the exception has lapsed. The measurement is a draw on cells. Its one answer change goes against settling. That change is the open margin problem's, and the handover records it honestly. Three of the author's claims are overstated: "separated nothing", the practice ground, and the record of what fired.

Terms used below:
- **The prefit** is the cell-free Le Bail fit that refines the candidate cell and widths before any extinction class is fitted.
- **A partition** is one Le Bail redistribution of the observed intensity among overlapping reflections.
- **A settled partition** repeats until the intensities stop changing, at `StageSpec` (the stage schema) defaults `lebail_cycles` 25 000 and `lebail_tol` 1e-7.
- **B11** is the maintainer's ruling of 2026-10-19: "repeat until the intensities stop changing, with a cap".
- **WP-1542** is the change that made rietx's partition settle.
- **The margin task** is this WP's open work on how far from the true cell the Pawley-based class screen stays right.
- **`best_or_none`** is the screen's pick verb.
- **The reference gate** is `REFERENCE_NET_RWP_MAX`, 0.7071. Above it the screen reads `unreliable` and picks nothing.

| Question | Author's answer, and where | What I found | Verdict |
|---|---|---|---|
| 1. What the deletion leaves to whom | WP-2076 handover, fourth session: "The prefit runs `profile_only` at the `StageSpec` defaults (25 000 cycles to `lebail_tol` 1e-7)." | Confirmed at `extinction.py:1073`. `staged.py:143,147` holds those defaults, and no stage of `profile_only` overrides them. The package still decides how far the partition runs. It now uses its package-wide rule instead of a special count, so the caller is handed nothing new. This is a change of rule, not a demotion. No dangling reference to `SCREEN_LEBAIL_CYCLES` or `_fixed_partition` is left outside `docs/wp/`. | holds |
| 2. Kind of ambiguity | none given. Constant rows carry no `ambiguity` field. The governing row `StageSpec:lebail_tol` states `ambiguity=1`. | This is a numerical setting: how far an iterative solve is taken. It feeds a kind-2 ranking (classes ranked by ΔBIC, the difference in Bayesian information criterion). It is no verdict of its own. Kind 1 under `lebail_tol`'s row is consistent. | holds |
| 3. Case against the deletion (for keeping 3) | Handover table (`docs/wp/2076-…md:417-428`): FAP's settled prefit cell is +313 ppm (prefit Rwp 0.22 against 0.12) and −1474 ppm (0.54 against 0.11). Synthetic ×0.995 settled: "`P 1 21 1`, wrong, at a cell 0.07 % short". Attributed: "this belongs to the open margin task." | Checked against `p4_fixed.jsonl` and `p4_settled.jsonl`. **(a) One answer changed, toward a confident wrong class.** Synthetic P 2₁/c started at ×0.995 went from 3-cycle `None` (status `unreliable`, net Rwp 0.996) to settled `P 1 21 1` (status `converged`, ΔBIC −23.6). A user would see an abstention become a named wrong class. The attribution is fair: the third session's held-cell scan found `P 1 21 1` at ×0.9994, and the settled cell sits in that zone. But 3 cycles reached the abstention only by losing the cell (a = 6.83 Å against 8). So neither arm is right on that row, and until the margin task lands this release ships the wrong name there. **(b) FAP's cell moved away from its ×1.0 answer at both offsets.** That answer is a cross-code reference, so this measures drift only. FAP is also the declared failing case of `StageSpec:lebail_tol` (`_audit.py:4613`, "a pair 1e-4 A apart … that 3000 more cycles swap"). That could be the same cause. I did not test it. **(c)** The code comment's "separated nothing" (`extinction.py:1070-1072`) is true of the cells on balance (two better, two worse). It is not true of the answers, where the one difference goes against settling. | real, bounded |
| 4. Case for the deletion (for settling) | Handover: "rietx's convention since WP-1542 is a settled partition, and one rule beats a rule with an exception. Practice stops Le Bail on convergence (`docs/practice.md`). And the measurement below separated nothing." | **The rule ground is strong.** The deleted row's own grounds gave the 3 a term: "Kept until WP-2062 moves the screen to Pawley" (WP-2062 is the WP that owns the Le Bail-to-Pawley move). It also said: "B11 did not exempt the screen: the exemption was settled by Claude". This WP moved every compared fit to Pawley, so the term has run out. The deletion returns the prefit to a maintainer ruling from a Claude-settled exemption. The 3 had "no stated source". The tests WP-1542 said a settled partition failed now pass in both arms: 176 passed, 2 skipped, 1 xfailed across `tests/test_extinction*.py`. Settling also recovers the synthetic cell that 3 cycles lose (×0.995 lost against ~0.07 % short; ×1.005 at 1034 against 65 ppm). Wall time is the same (0.28-28.8 s against 0.27-28.7 s). **The practice ground is overstated.** `docs/practice.md:536-541` says "No surveyed program stops on the extracted intensities at a fixed model". GSAS-II's `DoLeBail` runs "a fixed `cycles=10`". Inside a refinement the programs stop the *refinement* on χ². So practice does not settle a fixed-model partition either way. | stronger, on the rules |
| 5. Tier, with source | Deleted row: tier 3, "no stated source for the 3". Governing rows: `StageSpec:lebail_cycles` is tier `invariant` (`_audit.py:4592`); `StageSpec:lebail_tol` is tier 3, approved 2026-11-05 (`_audit.py:4606`). | Tier 3 for the 3 was honest. The heuristic now sits under rows already audited and approved. The `invariant` row names its test, `tests/test_lebail_cycles.py::test_the_tolerance_meets_its_bar`, which asserts a 2× margin on "six patterns from four kinds of instrument, the largest 329 reflections". **That domain was measured on refinements, not on prefits.** A prefit of a large low-symmetry candidate in its lattice group could exceed 329 reflections. No measurement covers that. GSAS-II's fixed 10 comes from `docs/practice.md` (source checked there). I did not check the programs myself. | holds, domain unshown for the prefit |
| 6. Dataset families | Handover: corundum, FAP, synthetic P 1 21/c 1, PbSO₄; "eleven screens". | Four families: NIST corundum, the GSAS-II tutorial FAP, the GSAS-II tutorial PbSO₄, and one synthetic made with rietx's own forward model. References: the known space group for the class; the construction for the synthetic cell; GSAS-II's answer for FAP's cell (verifies only); corundum's certified cell not compared (both arms agree within 10 ppm). **All four are development data** (the screen's own test rows), and the handover does not say so. NAC was not run. | holds, with omissions |
| 7. What reports it | none given | **Weaker than before.** With a cap the partition can now be cut short. When it is, the fit raises `LEBAIL_CYCLES_AT_CAP` (the code for a partition that hit its cycle cap) and sets `StageResult.lebail_settled`. But `_prefit` returns only the instrument, the candidate and the Rwp (`extinction.py:1077-1080`), so the screen drops both. A prefit that hit the cap would pass silently. Only `ExtinctionScreen.prefit_rwp` and `.cell` show the outcome. | weak |

Evidence that would change the verdict: a prefit row where settling changes the class at a cell the Pawley margin is known to handle (outside ×0.9994 to ×1.0012 on the synthetic). Or a large low-symmetry prefit that hits the 25 000-cycle cap, since nothing would report it.

Author's answers. Row 3(c) and row 4's practice: the comment and the entry now say what the judge found. Row 7: the prefit's `LEBAIL_CYCLES_AT_CAP` now reaches the screen (see *Done*). Row 5's domain (no prefit above 329 reflections measured) stays open, and the cap warning is what would show it.

After the removal, `tests/test_extinction*.py`, `test_gui_peaks.py`, `test_tof_axis.py`,
`test_audit_table.py` and `test_docs_consistency.py` gave 351 passed, 2 skipped, 1 xfailed,
slow rows included (`[dev]`, macOS arm64).

**Next.** The margin task: measure option (c)'s allowance. Include the synthetic P 2₁/c at a
start ×0.995 as a case it should fix: with the settled prefit the screen now names `P 1 21 1`
there, at a cell 0.07 % short, where 3 cycles lost the cell and abstained.

### 2026-11-07 (third session) — the repair landed, PR #1460

The ruled repair is in. The extinction screen now compares Pawley fits, and it scores each class
on the lattice less only the forbidden lines it can test, so a class can no longer fit better than
the model that contains it. On the five synthetic specimens this WP was opened on, the screen now
returns a class containing the true group, where it named a wrong class on all five. As ruled, FAP
and synthetic Si now abstain, and PbSO₄ names `P c - a` where the specimen is `P c - n`. When the
screen abstains on the margin, its message now names the tested positions where the two leading
classes differ. The NAC timing that gated the ruling costs nothing worth asking about: about 0.05 s.

*Done.*
- `model.forward._omitting_reflections`: a private, context-scoped compile seam that drops named
  hkl from each phase's nuclear reflection list. It is the one way to fit "the lattice less these
  lines", a reflection set no space group describes. It replaces the candidate's monkey-patch of
  `generate_reflections`.
- `extinction.SCREEN_MODE = "pawley"` for the shared profile fit, the reference and every class.
  The cell-free prefit stays Le Bail at `SCREEN_LEBAIL_CYCLES`; its `_audit` evidence says so now.
  A class with 0 < `n_testable` < `n_absent` gets a second fit of the lattice less its testable
  lines; `n_testable == 0` scores as the reference (ΔBIC 0). Hamilton's restricted parameter count
  is the scored fit's own `n_free_parameters` (Pawley counts its intensities).
- `ExtinctionCandidate.tested_hkl` / `tested_two_theta` (new fields), and `chi2` documented as the
  scored χ². `EXTINCTION_SYMBOL_AMBIGUOUS`'s margin reason appends "and the two differ at the
  tested position(s) …" (no new code, so no audit row and no skill row).
- Rows rewritten to the ruling: FAP abstains (`P 63 - -` leads on one testable line, (0 0 5) at
  68.0°, ΔBIC −8.2); Si and the halo rows lead with `F d - -` and abstain; PbSO₄'s row pins
  `P c - a` as the accepted wrong answer. WP-1910's four strict xfails pass and became plain rows.
  #726's held arm (corundum ×1.0012) now returns `R - c -`, so that row says so.
- `tests/test_extinction_nesting.py`: the five specimens built in-test, ten rows (acceptance and
  nesting), ~5 s in the fast tier. All ten fail on `main` before this branch, with the five wrong
  classes the sweep found. PNGs `tests/output/extinction_nesting_*_true.png`, looked at.
- Manual `reference/extinction.md`: Pawley pipeline, the scored χ², the new fields, the one-line
  limit of the margin, and the real-data paragraph re-measured (below).

*Measured* (macOS arm64, `[dev]` venv of this worktree, compiled tier on).
- NAC, the test file's protocol (2-24°, I cubic, dispersion declined), 3 runs each in one process,
  through the shift's serial queue: `main` 0.92-0.97 s, this branch 0.97-1.04 s. Both `I - - -`.
- Held-cell margins (`edge_scan`): corundum returns `R - c -` at every factor from ×0.995 to ×1.002
  (Le Bail: ×0.998 to ×1.0004); the monoclinic from ×0.9996 to at least ×1.0012, and `P 1 21 1`
  at ×0.9994; FAP abstains at ×0.999, ×1.0 and ×1.001.
- Manual's real data: FAP ranks `P 63 - -` first and abstains, 3.4 s; corundum 20-90° `R - c -`
  at ΔBIC −45.9 (was −3435), `profile_rwp` 0.134 (was 0.259); corundum 5-150° on the declared
  widths now returns `R - c -` at −74.6, `profile_rwp` 0.137, where the Le Bail screen refuted it.
- Test counts, on the tree merged with `main` at b17d28273 (`[dev]` venv, macOS arm64, each through
  the serial queue). Fast selection: 14283 passed, 416 skipped, 32 xfailed, 1 failed in 9:04; the
  failure was this entry's own headings (`test_docs_consistency`), fixed and re-run green (25
  passed). The seven extinction files, slow rows included: 133 passed, 1 xfailed. The indexing
  acceptance file: 45 passed in 14:42. Added tests' local cost (`tests.added_test_times`): 19.9 s
  over four, the FAP abstention rows 10.8 s of it (five cases, ~2 s each). They stay in the fast
  tier beside the margin file's other real-data held rows, which pin the same edge.

*Not done, in order.*
1. The tightening the ruling deferred, now an open task: measure option (c)'s allowance (2·ln N
   plus an allowance derived from the count of silent positions), and real patterns from the
   eleven groups that abstain on every row at margin 18. Its `_audit` row goes to Yue before any
   margin moves. PbSO₄'s row flips when it lands.
2. The default-prefit margin table in `tests/test_extinction_margin.py`'s docstring is the Le Bail
   screen's record; only the rows below it were re-measured. Re-scan the 24 factors if a later
   change needs the default margin as a number.

*Gotchas.* A test that patches `extinction._fit_class` must accept `omit=` and keep only the
calls without it, or it records the scoring refit as the class's fit (both patching tests do).

*Review.* `/code-review high --fix` made two fixes, each committed: one scoring refit per set of
charged lines, shared by classes that differ only in untestable lines, and an "Also in 0.61" note
for the two new fields in `schemas/common.py`. This session documented the third finding (a raised
scoring refit keeps `n_testable` and `rwp`, with `chi2` at ∞). Declined, with reasons: the two
scoring branches (Pawley absorbs the difference in χ²); the ambiguity message's wording (it also
names positions only one class could test, and the tests pin the phrase); a cancel check before the
scoring refit (it would leave a class fitted and unscored); and moving the omission seam from a
ContextVar onto an explicit argument (it reaches far outside the diff, and no caller recompiles
outside the block). Its finding that `REFERENCE_NET_RWP_MAX`'s evidence was Le Bail's was acted on:
the gate was re-measured on the Pawley reference and the row records it. Right cells read
0.11-0.16. SRM 676a ×1.02 and FAP ×0.99 read 1.00. PbSO₄ ×1.02 reads 0.80 against the 0.71 gate,
and PbSO₄ ×0.99 reads 0.30 (was 0.45).

*Generality* (the `generality-review` agent, pasted unedited).

**rietx.indexing.extinction.SCREEN_LEBAIL_CYCLES (changed row, tier 3, value 3)**

**weak.** The case against keeping the row as written is stronger. Its `grounds` still say the 3 is kept "until WP-2062 moves the screen to Pawley", and this change has now done that for every fit the screen compares. The one fit the 3 still governs, the cell-free prefit, has no measurement of its own.

(WP-2062: the work package moving rietx's structure-free fits from Le Bail to Pawley. The prefit: the Le Bail fit that refines the candidate cell before any extinction class is fitted.)

| Question | Author's answer, and where | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | `_audit.py:2390-2395` evidence: "Since WP-2076 (2026-11-07) the compared fits are Pawley and this count governs the cell-free Le Bail prefit alone". Comment at `extinction.py:927-929`: "The prefit's cell is measured at this count, so a partition that settled would move it." | It now decides how many Le Bail partition cycles the prefit runs, with no stop on the intensities. The prefit's cell and widths are what every class is then fitted at. The package's own default is a settled partition (`StageSpec:lebail_cycles` = 25000 with a 1e-7 stop), so the prefit departs from it. | holds, as a description |
| 2. Kind of ambiguity | Not stated. A constant row carries no `ambiguity` field. | This is a numerical setting of a fit, not a verdict. | n/a |
| 3. Case against | `grounds`: "Kept until WP-2062 moves the screen to Pawley … re-measuring the screen's margins for a method it is about to leave buys nothing." | **That ground has lapsed.** The screen has left Le Bail for every compared fit. WP-2062's new inherited note says the prefit "stays Le Bail at `SCREEN_LEBAIL_CYCLES`", so no later move is planned. The evidence ("a settled partition failed 10 rows", WP-1542) was measured when every screen fit was Le Bail at 3 cycles. Whether a settled partition in the prefit alone moves any answer is **none given**. The WP's own Findings weaken the claim: "Raising the Le Bail cycles from 3 to 100 moves χ² by 0.04 %" (WP-2076 § Findings, one synthetic F m -3 m row). | case against is stronger |
| 4. Case for | Same evidence: "its gates and margins are measured at this count". | The prefit basin rows (`test_extinction_refine_cell.py::test_the_prefit_basin_holds_either_side_of_wp_1910s_acceptance_case`, −0.08 % to +1 %) and the gate rows were measured with this prefit. Leaving the prefit alone kept this change's scope bounded. No measurement shows that a settled prefit would move them. | weak |
| 5. Tier | 3. "no stated source for the 3" (evidence). | Unchanged and honest. For context, `docs/practice.md` § Structure-free fitting records GSAS-II's `DoLeBail(cycles=10)` and "at most 3 cycles by default" inside a refinement, and MAUD at up to 5. A rietx cycle runs between whole solves, so those counts are not the same unit. I checked this in the repository's survey, not in the programs. | holds as tier 3 |
| 6. Dataset families | WP-1542's 10 failing rows in two test files. | These are the screen's development rows: corundum, FAP, a synthetic monoclinic, Si and PbSO₄, all under the old all-Le-Bail screen. None was re-measured for the prefit-only role. | weak |
| 7. What reports it | none given | `ExtinctionScreen.prefit_rwp` reports the prefit's Rwp. No field records the cycle count or whether the partition settled. | weak |

Evidence that would change the verdict: a run of the prefit with a settled partition against 3 cycles, on the screen's real rows (corundum, FAP, PbSO₄, NAC), showing whether any returned class or prefit cell moves. A rewrite of `grounds` to the prefit's own reason would also be needed, with a fresh approval date.

**SCREEN_MODE = "pawley" (flagged; the table cannot see it)**

**holds.** The case for acting is stronger. ΔBIC (difference in Bayesian information criterion) and Hamilton's test (a ratio test of whether removed parameters were needed) both assume each compared χ² is a minimum. A Le Bail partition is not a minimum, and a Pawley fit is. The maintainer ruled the move on 2026-11-07, and accepted its costs: FAP and Si now abstain, and PbSO₄ is now named wrongly.

| Question | Author's answer, and where | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | `extinction.py:932-940`: "The decomposition of every fit the screen **compares**: the shared profile fit, the reference and each class". | Confirmed in the code. `_fit_class` and the shared fit pass `mode=SCREEN_MODE`, and the prefit keeps `mode="lebail"` (`extinction.py:1083`). The caller has no argument to choose the mode. | holds |
| 2. Kind of ambiguity | Not stated. WP-2076 § Context: "Restoring nesting is a fix to that practice and adds no judgement." | The ranking is kind 2 (the data rank the classes). The choice of fit under it is kind 1: given the screen's own statistic, the arithmetic decides. No row exists, so nothing records the kind. | holds |
| 3. Case against | none given | FullProf offers only Le Bail (profile matching), and RIETAN-FP steers Le Bail first (`docs/practice.md` table, the repository's survey). A user of either compares classes by Le Bail χ². Le Bail (2005) cites Kariuki et al. (1999) testing cell hypotheses by Le Bail as "faster than with the Pawley method". That dissent is about the means, though, and the statistic is rietx's. Under a nested ΔBIC a Le Bail χ² is the wrong input: WP-2076 § Findings measured 2410 of 14 788 class fits below the reference that contains them. Nesting is still not exact under the change: "29 of 12 513 class fits below the reference (good-cell rows)" (§ Findings, Task 3 table), with no explanation given. | weak |
| 4. Case for | `extinction.py:932-939`: Le Bail "named a class excluding the true group on 318 of 1082 rows at a correct cell". Handover 2026-11-07, third session: NAC "`main` 0.92-0.97 s, this branch 0.97-1.04 s". | On 1082 synthetic rows, right/none/wrong moved from 731/33/318 to 914/158/10. That figure is for this item and the next one together, since Pawley alone gave 261/69/26 on 356 rows and lost corundum. Corundum's held-cell margin widened from ×0.998–×1.0004 to ×0.995–×1.002. Corundum over 5–150° now returns `R - c -` where the Le Bail screen refuted it. | strong |
| 5. Tier | none given (no row). WP § Context: "a nested BIC comparison (Schwarz 1978)". | Tier 1 for "the compared fits must minimise χ²", since that is arithmetic. Tier 2 supports Pawley as the means. TOPAS defaults structure-free fits to Pawley ("The default is Pawley refinement", TR v5 §8). ExtSym reads Pawley-type intensities. BGMN's "LeBail" mode is Pawley-type. All three are from `docs/practice.md`, the repository's survey; I did not check the programs. That survey's `rietx (main)` row in § Ranking extinction symbols still says "a Le Bail χ² per class", and this change does not update it. | holds |
| 6. Dataset families | WP § Findings and the handover. | **Synthetic sweep:** one family (rietx's own forward model, one simulated Cu Bragg-Brentano instrument, Ca/Si/O structures). The reference is the true group by construction. Development data. **SRM 676a corundum** (IUCr round robin): certified `R -3 c`, which validates; it keeps `R - c -` at ΔBIC −45.9. **GSAS-II FAP** tutorial: reference `P 6₃/m` from a published refinement; now abstains. **GSAS-II PbSO₄ X-ray** (Hill 1992): reference `P n m a` ≡ `P c - n`; now **`P c - a`, wrong**, where it was right before. **11-BM NAC**: keeps `I - - -`; the change does not state the source of its space group. All are development data, since their rows were rewritten to the new outcomes. Under generality.md § A moved golden, PbSO₄ moved away from its reference and goes back through the two grounds. The maintainer ruled that outcome accepted on 2026-11-07 and opened a follow-up task. The handover attributes the PbSO₄ miss to the margin and the per-position ln N count ("χ² differs by 0.8, so the margin is the count alone"), not to Pawley. | holds, with one real family moved away from its reference by ruling |
| 7. What reports it | none given | No field on `ExtinctionScreen` records which decomposition produced `chi2`, `delta_bic` or `reference_chi2`, and the screen carries no provenance stamp (I checked `schemas/indexing.py:2538-2584`). A screen stored before this change reads the same fields with values about 30× larger (corundum −3435 against −45.9 now). Only `refuted_reason` names the mode, and only on a failure. Whether the table should carry this item: the constant walk holds numbers and tuples of numbers only (`_audit.py` docstring, "constant" kind). `determine_extinction_symbol` is not in `DEFAULT_SEATS`. The docstring's list of what the guard cannot see does not name a mode string. So carrying it needs a new seat or kind, or at least a line in that list. | weak |

Evidence that would change the verdict: an explanation of the 29 class fits still below their reference, for example Pawley's equal-split restraint on overlapped groups making the data χ² not a minimum. If that cause holds, nesting is approximate by construction, and the ln N per position arithmetic loses part of its footing.

**Testable-only scoring (flagged; the table cannot see it)**

**holds.** The case for acting is stronger. Scoring each class on the lattice less exactly the lines its ΔBIC charges for makes the χ² comparison match the BIC's parameter count. Pawley without it lost certified corundum. Two inputs stay open: which lines count is decided by an unaudited 3σ threshold, and the consistent alternative was not measured.

("Testable" here means a forbidden position where the class's own calculated pattern is quiet enough that intensity there could be seen.)

| Question | Author's answer, and where | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | `schemas/indexing.py`, `ExtinctionCandidate.chi2`: "a Pawley fit of the lattice less only this class's `n_testable` forbidden lines … this class's own fit when every forbidden line is testable, and the reference's when none is". | Confirmed at `extinction.py:1466-1493`. Hamilton's test now takes `scored.statistics.n_free_parameters`, where before it took `n_lines + n_free_parameters`. That is right for Pawley, whose intensities are parameters. Whether Pawley's restrained overlap groups are counted as free parameters is not checked. The checkout at `extinction.py:1429` and `:1471-1480` also caches one refit per charged line set, shared between classes. The diff file does not show that cache. | holds |
| 2. Kind of ambiguity | none given | Kind 2 (a ranking). It ranks every class with ΔBIC and Hamilton beside it. It picks only through `best_or_none` (the screen's pick verb) at `DECISIVE_DELTA_BIC` = 10 (the decisive margin). | holds |
| 3. Case against | none given | A refiner could score differently and stay consistent. One way: score each class on its own fit and charge all `n_absent` forbidden lines. Another, ExtSym's: weigh every extracted intensity by its error, so untestable lines enter softly rather than not at all. Neither was measured. WP § Findings measured only "Le Bail, scored on testable lines: no change on the two rows run". Which lines are charged is set by `_model_is_quiet` at `ABSENT_SIGMA` = 3.0 (`indexing/workflow.py:106`). That threshold is still `unaudited` (`_audit.py:2504`, on the baseline). It now also decides which reflections the scored model contains, a wider reach than before. | some, unmeasured |
| 4. Case for | `extinction.py:1176-1182`: "Scoring the class's own fit charged it, or credited it, for lines its `n_testable` does not count: on certified corundum the reference's untestable lines soak up neighbouring tails, and Pawley alone then lost `R - c -`". | Measured in § Findings, Task 3: Pawley alone gave 261/69/26 on 356 rows with corundum → `R - - -` (+70). With this scoring it gave 346/5/5, and corundum keeps its class at −46. "Corundum's χ² then differs by 10 over six positions, as a nested comparison should." Cost: one extra Pawley fit per class whose forbidden lines are partly testable. That is ×1.1 CPU over 375 rows and ×1.9 on PbSO₄ (Question 1 brief), and NAC +0.05 s. | strong |
| 5. Tier | none given | Tier 1 for the consistency: the compared models differ by exactly the counted parameters (Schwarz 1978, cited in the manual). The free choice inside it is the testability threshold, which inherits `ABSENT_SIGMA`'s tier, still unaudited. | holds, inherits an unaudited threshold |
| 6. Dataset families | as for SCREEN_MODE | Same families, same caveats. The corundum result (certified `R -3 c`) is the one real-data case that separates this item from SCREEN_MODE. | holds |
| 7. What reports it | `ExtinctionCandidate.chi2` docstring; new `tested_hkl` and `tested_two_theta` | Which fit a class was scored on can be read off `n_testable` against `n_absent`: 0 means the reference, fewer means a refit, equal means its own fit. No field names it directly. | holds |

Evidence that would change the verdict: the alternative (own fit, charge all `n_absent`) run on the 1082 rows and on corundum. If it did as well, the choice between them would become a ranking judgement rather than arithmetic.

**A scoring refit that raises refutes the class (flagged; the table cannot see it)**

**weak.** The case against is stronger. A numerical failure of a model that is not the class becomes a refutation. A refuted class leaves the margin comparison in `best_or_none`, so a failure on the leader or its runner-up can let a rival through as a confident answer. The package's own rule for an unasked question is to abstain.

| Question | Author's answer, and where | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | Handover, third session: not mentioned. Code `extinction.py:1481-1487`: `refuted_reason` = "the pawley fit of {symbol} without this class's {n} testable forbidden line(s) raised …". | The class's own fit succeeded. Only the refit of the lattice less its testable lines failed. The class is marked refuted. `continue` skips its absence test and leaves `chi2` at ∞ and `delta_bic` at 0.0. | holds, as a description |
| 2. Kind of ambiguity | Existing schema text (`schemas/indexing.py:2517-2518`): "The one other way in is a screen fit that raised … with no χ² it cannot be the answer." | "Cannot be the answer" is kind 1. "Is refuted" goes further: it also removes the class from the margin test (`best_or_none`, `schemas/indexing.py:2644-2657`). | fails unanimity |
| 3. Case against | none given | A competent refiner reads a solver failure as inconclusive, not as evidence against the absences. The repository says so itself: `test_extinction_symbol.py::test_a_cancelled_screen_abstains_and_says_which_classes_it_reached` keeps cancellation out of class fits because "a cancelled run would come back looking like a refutation". `best_or_none` already abstains when "an unrefuted class was left unfitted … an unasked question, which must not read as a clean answer" (`schemas/indexing.py:2618-2621`). A raised scoring refit is that situation. No test exercises this branch: I found no match for its message in `tests/`. | strong |
| 4. Case for | The schema text above, which predates this change, for a class fit that raised. | Consistent with the old rule for a class's own fit raising. A refit of a subset of a reference that already succeeded should rarely raise. How often it does is **none given**. | weak |
| 5. Tier | none given | An action with no row. "No χ², so not the answer" is tier 1. "Refuted, so out of the margin" has no source. | weak |
| 6. Dataset families | none given | No case on disk reaches the branch. | none found |
| 7. What reports it | `ExtinctionCandidate.refuted_reason` | `refuted_reason` names the failure. No diagnostic code fires. `EXTINCTION_FORBIDDEN_INTENSITY` reads `n_present`, which stays unset here. | holds |

Evidence that would change the verdict: an injected raise in the scoring refit, with a test showing what `best_or_none` returns. Alternatively, treat the class as unscored and not refuted, so `best_or_none` abstains, and show that this costs nothing on the existing rows.

**`_undecided_positions(a, b, limit=4)` in `indexing/diagnostics.py` (flagged; display cap)**

**holds.** The case for is stronger. The cap only shortens a message. The message counts what it leaves out, and the full lists stay on the two classes' records.

(`EXTINCTION_SYMBOL_AMBIGUOUS`: the diagnostic the screen raises when it declines to name a class.)

| Question | Author's answer, and where | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | Docstring at `diagnostics.py:1181-1186`: "The tested forbidden positions one of two classes has and the other lacks … where counting longer would separate the two." | It names at most four positions, the lowest in 2θ, then adds "and N more". The ranking and the pick do not change. | holds |
| 2. Kind of ambiguity | none given | Kind 3: it reports where the margin rests and stops. | holds |
| 3. Case against | none given | Taking the lowest four in 2θ may skip the positions with the most counts behind them, which are the ones most worth recounting. That cost falls on a message whose full content sits in `tested_hkl` and `tested_two_theta`. | weak |
| 4. Case for | Manual `reference/extinction.md`: "names the tested positions the two classes differ at, which is where counting longer would separate them." | This closes the WP acceptance clause "`None` with a finding naming the undecided position". Tests assert the position appears in the message: `test_extinction_margin.py::test_fap_abstains_on_its_one_testable_position`, `test_extinction_nesting.py::test_the_screen_never_names_a_class_excluding_the_true_group`, and `test_extinction_gate.py::_leads_with_fd_and_abstains`. | holds |
| 5. Tier | none given | Tier 1 under generality.md § The rule, tier 1's report-cap clause, "once a test shows the report is complete inside the cap and its notes count what lies outside it". The note counts the rest. No test reaches more than four positions, so the "and N more" tail has never run. It is an inline function default, outside `DEFAULT_SEATS`, so the table cannot see it. `EXTINCTION_SYMBOL_AMBIGUOUS`'s own row is still `unaudited` (`_audit.py:688`). | holds, missing a test |
| 6. Dataset families | n/a | No threshold. | n/a |
| 7. What reports it | `ExtinctionCandidate.tested_hkl` and `tested_two_theta` (new fields), and the message | Both fields carry the full lists. The schema's `default_factory=list` reads "empty until screened", which is the right empty state. | holds |

Evidence that would change the verdict: a case with more than four differing positions where the message fails to count the rest.

Author's answer to the raised-refit item: it follows the schema's existing rule for a class fit
that raised, and no case on disk reaches it; treating a raised scoring refit as unscored rather
than refuted belongs with the margin task above. On `SCREEN_LEBAIL_CYCLES`: the grounds' "until
WP-2062 moves the screen to Pawley" has lapsed for the compared fits; rewriting the grounds needs
a new approval, so it is left for Yue with the margin task.

- **2026-11-07** (rulings, PR #1455) — Yue answered both questions. The repair lands in this WP,
  at today's margin, once a timing on the largest suite pattern says it is affordable. A user of the
  screen then gets a wrong class on 10 of the 1082 synthetic rows instead of 318. FAP and Si stop
  naming a class, and PbSO₄ stays confidently wrong for now. A tighter bar comes only after it is
  measured.

  **Question 1.** Decided 2026-11-07 (Yue): (b). The Pawley-scored repair lands in WP-2076, ahead of
  WP-2062's order. One condition comes first. Before landing, time the screen on NAC, the largest
  pattern in the suite. If the screen takes more than 30 s there, bring it back to Yue.

  **Question 2.** Decided 2026-11-07 (Yue): the middle path. Land at margin 10, today's
  `DECISIVE_DELTA_BIC` and Kass & Raftery's band. Measured on the 1082 rows: wrong 318 → 10, right
  731 → 914, none 33 → 158. PbSO₄ stays confidently wrong, named `P c - a` over the true `P c - n`.
  Then measure two things before tightening. One is option (c)'s allowance: 2·ln N plus a small
  allowance, derived from the count of silent positions, never tuned to rows. It gets an `_audit` row
  that goes to Yue for approval. The other is real patterns from the eleven groups that abstain on
  every row at margin 18 (§ Findings lists them). Yue weighed (c) a lean and chose to measure first.

  *Next*, in order, for a runner starting task 5:
  1. Port `~/.cache/ghostshift/rietx/wp-2076/candidate.diff` onto a branch. It was never committed,
     so if the file is gone, rebuild it from § Findings.
  2. Time `determine_extinction_symbol` on NAC under the candidate and on main, at the protocol of
     NAC's row in the extinction test files. Quote both as ranges with machine and venv. Over 30 s
     under the candidate: stop, record the numbers here and bring them to Yue.
  3. Under 30 s: land the candidate at margin 10. Name the undecided position in the finding (task
     5's open half). Rewrite the acceptance clause and the certified rows to the ruled outcome:
     corundum and NAC keep their classes, FAP and Si give None, PbSO₄ names `P c - a`. State
     PbSO₄'s row as the known wrong answer this ruling accepts, citing this entry, so the tightening
     can flip it.
  4. Tasks 6 and 7: the five synthetic rows with their PNGs, and the skill row or "none". Run the
     three extinction files and `tests/test_acceptance_indexing.py`. Show the `tests.reader_output`
     diff to Yue.
  5. Then measure (c)'s allowance and the eleven groups' real patterns, and bring the allowance's
     `_audit` row to Yue before any margin moves.

  *Forward.* WP-2062's `### Inherited` entry from this WP now records the answer, since this WP takes
  in its Hamilton-count task and its A2 row (the screen's fits).

- **2026-11-05** — Tasks 1-4 are measured, and nothing in `src` changed. The screen's wrong answers
  have one main cause. A Le Bail fit does not minimise χ², so a class with fewer lines can fit better
  than the model that contains it, and the score rewards the removal. The certified answers read
  through the same break: corundum's `R - c -` scores −1301 where six lines can earn at most −49. A
  repair works on synthetic patterns. At a good cell the silent wrong answers fall from 318 to 10 of
  1082 rows. The same repair stops FAP and Si naming a class and makes PbSO₄ name a wrong one, so it
  stays off the branch until the maintainer answers the two questions below.

  *Measured.* § Findings carries every number. Main at `29b75345a`, `[dev]`, macOS arm64, cpython 3.12,
  synthetic rows from rietx's forward model. Extinction test files, three of them: main 74 passed, 5
  xfailed. The candidate 19 failed, 59 passed, 1 xfailed. `tests/test_acceptance_indexing.py` under the candidate, on `-n 4 --dist loadgroup`: 42 passed, 3 skipped.
  The candidate patch is `~/.cache/ghostshift/rietx/wp-2076/candidate.diff`, switched by
  `WP2076_MODE=shared` and `WP2076_MC=1`. It was never on a branch.

  *Premises.* The lead's first cause is false: the reference is a `_fit_class` fit under `_screen_plan`.
  The earlier shift's owed item, the default screen's wrong answers, is this WP's own subject and needs
  no filing. No `### Inherited` section was present. PR #1286 was read: nothing landed here touches its
  lines. Its four strict xfails pass under the candidate. Its held screen reads the same Le Bail path.

  *Not run.* The acceptance suite on the branch, because no `src` changed. `/code-review`, because the
  branch is prose only. Tasks 5-7 stay open, blocked on the questions. So does the acceptance clause "a
  finding naming the undecided position": `EXTINCTION_SYMBOL_AMBIGUOUS` names classes, and a repair
  would owe the position.

  **Question 1: does the repair land here, ahead of WP-2062's order?**

  - *The decision.* Whether the candidate lands in this WP, or waits for WP-2062 to move the screen
    (WP-2062 is the work package moving rietx's structure-free fits from Le Bail to Pawley). It comes
    to the maintainer because it changes a default's output, and because written rules pull apart:
    task 5 asks for the repair here, while this WP's non-goals and WP-2062 place the move there.
  - *Why it matters.* The screen is what the GUI's Peaks panel and an agent read to choose a space
    group after indexing. On main a user at a good cell gets a class excluding the true group on 318 of
    1082 synthetic rows, and nothing warns. Importance: serious.
  - *Aim.* A person or agent reading a class off the screen can trust it, or is told no class is decided.
  - *Options.*
    (a) Do nothing. The 318 stay, no cost, and the certified classes keep reading through the break.
    (b) Land here, once Question 2 is answered. Right 731 → 914 at margin 10, wrong 318 → 10, none
    33 → 158, measured. CPU ×1.1 over the 375 rows and ×1.9 on PbSO₄. The screen fits one extra
    Pawley per class, so a large pattern pays more, unmeasured here: WP-2062 quotes NAC validation at
    107 s under Pawley against 8.5 s under Le Bail. One module changes, so it can be undone. It takes
    in WP-2062's Hamilton-count task (the test now counts Pawley's intensities once) and its A2 row
    (the screen's fits).
    (c) Land inside WP-2062. The same numbers, later, in the written order.
    Dropped: abstain when ΔBIC beats the floor, or when a class χ² is below the reference. Each abstains
    on every certified row. Dropped too: signed-net Le Bail, where `F 41 - -` stays at −96 and every Le
    Bail fit moves.
  - *Practice.* ExtSym (Markvardsen 2001, 2008) reads Pawley-type intensities with errors. GSAS-II lists
    groups with M20 and X20, and no extinction ranking was found in it. Both per `docs/practice.md`
    § Ranking extinction symbols. TOPAS and FullProf were not checked. The candidate follows ExtSym on
    the fit, and departs from it in scoring by BIC where ExtSym computes a probability.
  - *Recommendation.* (b), a lean. The maintainer already ruled that Pawley replaces Le Bail here, and
    only the order is Claude's own settlement of 2026-11-01. The crux is whether that order protects
    anything. Its reason was the Hamilton count, and the candidate fixes that count. So (c) only delays
    the same change. A large-pattern cost the maintainer will not pay flips this to (c).

  **Question 2: what bar must a class clear, now that the scores are honest?**

  - *The decision.* Which margin `best_or_none()` demands under the candidate. It comes to the
    maintainer because the crux is a value judgement, and because every option breaks the written
    acceptance "corundum, FAP, NAC and PbSO₄ keep their classes".
  - *Why it matters.* With nesting restored, one silent position earns ln N, about 8. Main's large
    scores were the break. FAP's `P 63 - -` rests on one silent position, and Si's two classes sit 9.3
    apart. PbSO₄ names `P c - a` over the true `P c - n` by 17.0 because it has two more silent
    positions, with χ² within 0.8. A user who sees a class trusts it, and `best_or_none()` is the
    only gate. Importance: serious.
  - *Aim.* The project's rule that the screen never returns a confident wrong singleton, weighed against
    how often it answers at all.
  - *Options.* All on the 1082 rows, right / none / wrong, replayed offline. Main reads 731 / 33 / 318.
    (a) 10, today's number and Kass & Raftery's band. 914 / 158 / 10. FAP and Si give None. PbSO₄ is
    wrong, so this one cannot land without a further rule.
    (b) 8. 999 / 43 / 40. FAP and Si return. PbSO₄ stays wrong. The 30 new wrong rows are P m m m on
    one silent position, the same evidence FAP has.
    (c) More than two silent positions' worth, about 18 here. 720 / 360 / 2. PbSO₄, FAP and Si give
    None. Corundum (margin 45.9) and NAC keep their classes. Eleven groups abstain on every row. The
    ranked list still leads with the true class on 314 of the 360 abstentions. A fixed 18 would slip at
    a larger N, so the rule would be 2·ln N plus a small allowance, whose value is unmeasured.
    Dropped: abstaining when a non-nested class stays within 10 on χ². It costs 333 right rows and fixes
    none of the ten wrong ones.
    Nothing here is hard to undo. Each option rewrites the acceptance clause and the test rows it moves.
  - *Practice.* The margin 10 is quoted from Kass & Raftery's "very strong" band and has no field
    practice behind it. Option (c) departs from that citation, and its reason would be the count
    argument above. No program's bar was found. ExtSym reports ranked probabilities, per its abstracts,
    so the bar is left to its reader.
  - *Recommendation.* (c), a lean, and the crux is a value judgement. A named wrong class on a certified
    pattern costs more than an abstention whose ranked list still leads with the right answer. Under
    (a) a user gets 194 more right rows and one certified pattern confidently wrong. If the maintainer
    weighs answering above that, (a) with a PbSO₄ rule is the runner-up, and no such rule exists yet. A
    rule that separates PbSO₄'s silent positions from a true absence would flip this.

  *Next.* PR #1433 carries this entry. The maintainer answers Questions 1 and 2. On (b) here: port `candidate.diff` with the chosen
  margin, name the undecided position in the finding (task 5), add the five rows with their PNGs (task
  6), and rewrite the acceptance clause. A new abstention brings its audit row to the maintainer first.
  Then run the three extinction files and `tests/test_acceptance_indexing.py`, and show the
  `tests.reader_output` diff to the maintainer.
- **2026-11-02** — created from the 2026-11-01 sweep for PR #1286. No open WP
  owns the screen's ranking at a correct cell. WP-1910 is the cell error and the
  centring twin, and fences the absence test. WP-2062 owns which fit mode the
  screen uses, not its ranking. WP-2033 filters members by Z. WP-1956 ranks
  cells in the indexer, not classes. Numbers re-derived from the sweep's CSVs
  and two diagnostic tables; the weak-line heights re-measured on this tree
  (`02d507226`, `[dev]`, macOS arm64). *Next:* task 1.
