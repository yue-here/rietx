# WP-2076 — The extinction screen names a wrong class at a correct cell

Milestone: unscheduled · Status: 🔄 2026-11-07 — the ruled repair landed (PR #1460); measuring the margin tightening is next
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

Both answered by Yue on 2026-11-07, in § Handover log's newest entry. The questions and their
measurements are in the entry of 2026-11-05.

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
- [ ] Measure option (c)'s allowance (2·ln N plus an allowance derived from the
      count of silent positions) and real patterns from the eleven groups that
      abstain on every row at margin 18, then bring the allowance's `_audit` row
      to the maintainer before any margin moves. Ruled 2026-11-07.

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
- Test counts: TESTCOUNTS

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
