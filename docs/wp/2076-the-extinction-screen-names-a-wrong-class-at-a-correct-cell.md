# WP-2076 — The extinction screen names a wrong class at a correct cell

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: — (1910 soft: its second screen agrees with the wrong class here; 2062 soft: its decision 2 moves the screen's fits to Pawley)
Priority: P2 2026-11-02 — a silent wrong answer on a path few fits run: on five of 41 synthetic groups the default screen and PR #1286's held screen agree on a class that excludes the true group, at a prefit cell within 600 ppm of the truth (13-599 ppm on the worst axis), and nothing fires

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

## Non-goals

- #1286's disagreement rule and the held screen (WP-1910).
- A cell the prefit gets wrong (WP-1910).
- Loosening the absence test or `_model_is_quiet` (WP-1077's fence, restated in
  WP-1910 § Non-goals).
- Moving the screen's fits to Pawley as a default for every caller. That is
  WP-2062's decision 2. This WP may measure it as a candidate repair.
- The Bayesian posterior (v2 fence).

## Tasks

- [ ] Reproduce the five on main from `sweep_core.py` (`+bkg` arms, ×0.995-
      ×1.0075). Add four more seeds per group, so a structure-specific
      accident is told apart from the screen's behaviour. Record per class:
      χ², n_testable, ΔBIC, refuted position, and the reference χ².
- [ ] Find which reflections decide each case. For every position the winning
      class and the true class treat differently, give its 2θ, its noise-free
      height over the strongest line, its integrated signal over σ in the
      absence window, and whether it was testable. For a refuted true class,
      say what the class's own model predicts at the refuting position.
- [ ] Test the lead. Count the classes whose χ² falls below the reference's on
      all 1230 rows. Fit the absence-free class under `_screen_plan` and compare
      it with the reference. Fit the five under Pawley (WP-2062's A2 row) and
      record whether the ranking changes.
- [ ] Classify the siblings above by the same mechanism, and say which share
      it and which do not.
- [ ] Repair the mechanism task 3 names. If the fix is a new abstention or a
      diagnostic code, bring its audit row to the maintainer before landing.
      The corundum, FAP, NAC and PbSO₄ rows of `tests/test_extinction_symbol.py`,
      `tests/test_extinction_margin.py` and `tests/test_extinction_gate.py` keep
      their classes.
- [ ] Tests: the five synthetic groups as rows, built in-test from rietx's
      forward model (no data file), with obs/calc/diff PNGs to `tests/output/`.
- [ ] Skill: a row in `references/diagnostics-indexing.md` if a code is added,
      or "none" and why.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_extinction_symbol.py tests/test_extinction_margin.py tests/test_extinction_gate.py -n auto --dist loadgroup
.venv/bin/python -m pytest tests/test_acceptance_indexing.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

On P 6₃/m m c, P 6/m c c, P n -3 n, P 4/n m m and F m -3 m, with the true
background declared and the cell within 600 ppm, `best_or_none()` returns a
class containing the true group or `None` with a finding naming the undecided
position. It never returns a class that excludes the true group. The certified
corundum, FAP, NAC and PbSO₄ rows keep their classes.

## References

- Schwarz, G. (1978). *Ann. Statist.* 6, 461-464. The BIC.
- Kass, R. E. & Raftery, A. E. (1995). *J. Am. Stat. Assoc.* 90, 773-795. The
  margin `DECISIVE_DELTA_BIC` quotes.
- Markvardsen, A. J., David, W. I. F., Johnson, J. C. & Shankland, K. (2001).
  *Acta Cryst.* A57, 47-54. The Bayesian screen; a v2 fence.
- PR #1286 and WP-1910 (the second screen); WP-1077 (testability); WP-2011 and
  WP-2062 (Le Bail against Pawley).

## Handover log

- **2026-11-02** — created from the 2026-11-01 sweep for PR #1286. No open WP
  owns the screen's ranking at a correct cell. WP-1910 is the cell error and the
  centring twin, and fences the absence test. WP-2062 owns which fit mode the
  screen uses, not its ranking. WP-2033 filters members by Z. WP-1956 ranks
  cells in the indexer, not classes. Numbers re-derived from the sweep's CSVs
  and two diagnostic tables; the weak-line heights re-measured on this tree
  (`02d507226`, `[dev]`, macOS arm64). *Next:* task 1.
