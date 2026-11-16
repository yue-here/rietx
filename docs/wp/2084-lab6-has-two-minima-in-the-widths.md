# WP-2084 — The SRM 660c protocol has two minima in the Gaussian widths, and the shipped start reaches the shallower

Milestone: unscheduled · Status: 🔄 2026-11-16 — three of four tasks landed; the plan choice waits on the maintainer (PR #1583)
Track: What fires, and what stays silent
Depends on: —
Priority: P3 2026-11-02 — a start-dependent answer on the absolute anchor's widths; the cell moves 0.18 esd between the two and nothing fires; a reader quotes u, v and w, which `RESOLUTION_UNCONSTRAINED` already says not to quote

## Goal

Either the NIST protocol on SRM 660c reaches one answer from every start and every
window setting the start tests try, or the result says that its widths sit in one of
two minima.

## Context

**Measured 2026-11-02** (WP-2012's session; macOS arm64, worktree venv `[dev]`, compiled
tier on, dispersion declined). WP-2012 made the NIST protocol
(`tests/test_acceptance_srm660c.py::_nist_calibrated_plan`) free S/L alone and hold H/L
at its declared 0.025. That removed the S/L ↔ H/L mirror, and the protocol still has
two minima:

| arm | χ²_red | u | v | w | S/L |
|---|---|---|---|---|---|
| shipped (`AXIAL_SIZING_FLOOR` 0.02), cold | 3.557722 | −0.000506 | 0.001733 | 0.000505 | 0.037039 |
| floor 0.05, cold | 3.549273 | −0.000547 | 0.001822 | 0.000463 | 0.037098 |
| floor 0.02, warm from the 0.05 answer | 3.549378 | −0.000554 | | | 0.037108 |

So at the shipped floor a deeper point exists and the shipped start misses it. The gap
is 0.24 % of χ², about 45 in absolute χ² over 5332 points. Between the two the cell
moves 0.18 plain esd and u, v and w 0.58, 0.54 and 0.42 (the larger of the two arms'
plain esds). The probe fitted `test_window_domain._protocol("lab6")` cold at each floor,
then refitted each answer under the other floor with the same plan. Every arm reports `RESOLUTION_UNCONSTRAINED`, `RESOLUTION_NOT_POSITIVE` and
`CONSTRAINT_ACTIVE`: the Gaussian width is on its Γ_G² ≥ 1e-8 cone somewhere in range,
which is where to look first.

**The same pair of minima was seen before and blamed on the axial mirror.**
`tests/test_seed_invariance.py::test_the_peak_width_start_does_not_change_the_answer`'s
docstring records starts with x at 0.02 or 0.03 landing 0.38 esd away in u at χ² 0.25 %
lower, 46.7 apart in absolute χ² (WP-2002's B10 lane, 2026-10-21). With both ratios free
the two were near mirror images in S/L and H/L. With H/L held the gap is the same size,
so the mirror rode along and does not cause it.

**What it fails.** `tests/test_staged_start_invariance.py`'s lab6 axial-floor row reads
0.582 plain esd on u against a 0.1 bar. WP-2012 marked it a non-strict xfail citing this
WP, non-strict because only one platform was measured and rounding has picked these
minima differently on Linux before (WP-2036).

### Findings, 2026-11-16: one row of the Γ_G² cone separates them

Measured on origin/main bc77a934e with `docs/wp/2084-measure/probe2084.py` (one fit of
`_protocol("lab6")` through the closing stage, about a second), on macOS arm64 (worktree
venv `[dev]`, compiled tier on) and on Linux x86_64 (numpy 2.5.3, rietx-kernels 1.5.0
installed; the tier was requested and its state not recorded on that run). The two
platforms agree to every printed digit on all twenty arms both ran. The table's
Γ_G² < 0 counts and every esd shift below are computed from the probe's JSON (its `rows`,
`uvw` and `reflections`) with `test_window_domain._shift`'s rule, not printed by it.

**Which row.** The cone's rows sit at the frozen Bragg angles. LaB6's last reflection in
range (20.30–150.91°) is h² + k² + l² = 27, (333) and (511), with its Kα1 image at 148.68°
and its Kα2 image at 149.71°. The shipped answer has Γ_G² on its face at the Kα2 image
(Γ_G² = 0 at 149.7137°). The floor-0.05 answer has it on its face at the Kα1 image
(148.6797°), with Γ_G² clamped at ε past it.

**Why a start reaches one or the other.** `gaussian_width_inequalities` drops a row the
stage's start violates by more than `lm._ON_FACE` (1e-9 of max(|slack|, 1)). The closing
stage starts with the Kα2 row's Γ_G² at 2.59e-8 under the shipped floor, so the row is kept
(slack +1.6e-8, 48 rows) and the stage stops on it. Under the 0.05 floor it starts at
4.35e-9 (slack −5.7e-9), so the row is dropped (47 rows) and the stage walks on to the
Kα1 row. Floors 0.02, 0.025 and 0.03 land on the Kα2 face; 0.04 and 0.05 on the Kα1 face.
So the floor acts through the sizing it gives every earlier stage, which moves where the
closing stage starts against that row's face; the row kept or dropped then makes two
answers out of a difference of 2e-8 in Γ_G².

**The shipped answer is not a fixed point of its own plan.** Refitted from its own answer
under the same floor, the Kα2 row reads −1.2e-9 (slack −1.1e-8) at the start of the
first stage that frees w and is dropped there, and the fit lands deep: χ²_red 3.549230, 0.134 plain esd on w
from the floor-0.05 arm, 0.473 on u from the shipped answer. Re-running the plan from its
own answer moves it.

**Not the FCJ nodes or the windows at the answers, not rounding.**

| arm (shipped floor unless named) | χ²_red | largest shift from the shipped answer |
|---|---|---|
| shipped: 12 closing nodes per FWHM, `closing_window_tol` 1e-3 | 3.557722 | — |
| 24 closing nodes per FWHM | 3.557722 | 0.000 |
| 6 closing nodes per FWHM | 3.557745 | 0.048 on `axial_sl` |
| `closing_window_tol` 1e-4 | 3.557391 | 0.003 on x |
| w start × (1 + k·1e-14), k = ±1, ±3, ±7, ±20 | 3.557722 | identical digits, both platforms |
| floor 0.05, k = ±1, ±7 | 3.549273 | stays deep, identical digits |

The shipped answer and the deep answer the shipped floor reaches from its own answer,
both compiled at 0.02, differ in their closing node counts at 3 of 60 (line, reflection)
pairs and in their windows by at most 5 points. (Against the floor-0.05 arm the counts
differ almost everywhere, since that floor sizes every compile wider.) Both floors keep
their minimum for nudges of the w start up to ±1e-6 relative as well (the read-only
review's re-run), so the strict xfail does not rest on a rounding.

**Holding a near-face row does not make the answer unique.** With `lm._ON_FACE` raised to
1e-7, floors 0.02, 0.04 and 0.05 all land on the Kα2 face, 0.004 plain esd apart. On that
face the answer still moves with the path: floor 0.03 lands 0.442 esd on w away, and the
shipped arm refitted from its own answer 0.580 on w. The deep face shows the same spread:
its four other arms land up to 0.266 esd on w from the floor-0.05 arm.

**What χ² cannot fake.** With no cone rows in any stage (the clamp in the model left as it
is), both floors land at a third point.

| arm | χ²_red | points with Γ_G² < 0 (of 5332) | Γ_G² = 0 at | a (Å) | displacement against NIST's −0.07877 mm |
|---|---|---|---|---|---|
| shipped | 3.557722 | 75 | 149.71° | 4.1568832(54) | −0.92 esd |
| floor 0.05 | 3.549273 | 140 | 148.68° | 4.1568842(53) | −1.14 esd |
| no cone | 3.491663 | 674 | 133.97° | 4.1568955(52) | −3.25 esd |

Each step down in χ² is bought by letting the Caglioti Gaussian width go negative, held at
the clamp, over more of the range, and the displacement walks away from the certificate's
as it does. At the 0.24 % step the walk is 0.22 esd, inside its noise, so the reference does
not separate the shallow answer from the deep one; it separates both from the no-cone
answer (7.02 esd on u and 2.28 on the cell from the shipped answer). The certificate cell
separates none of them: all three sit near 4.15688 Å against 4.156780 at 20.85 °C. Every arm
reports `RESOLUTION_UNCONSTRAINED` (the Gaussian carries 44 % of the width), so u, v and w
are not quotable at any of them.

**The other two LaB6 start rows** both land on the Kα2 face: `intermediate_ftol` 1e-6
against None reads 0.000 plain esd (1.8e-7 on w), and Biso 0.5 against 1.5 reads 0.009 on x.

## Tasks

- [x] Find what separates the two minima: the Γ_G² cone's active rows, the FCJ node
      counts at each, or the windows. Start from the three arms above. *Done 2026-11-16:
      the Kα2 row of (333)/(511), kept or dropped at the closing stage's start (Findings).*
- [ ] Decide between a plan change that reaches the deeper minimum from the shipped start
      and a finding that says which minimum the fit is in. The deeper χ² is not by itself
      the evidence (root CLAUDE.md: never an Rwp comparison).
- [x] Make the lab6 axial-floor row strict, or drop its mark. *Done 2026-11-16: strict,
      since both platforms land the same way at every 1e-14 nudge (Findings). If the
      ruling on the task above makes the floors agree, the mark drops then.*
- [x] Re-word three `_audit.py` evidence strings that still quote LaB6 from before WP-2012:
      `AXIAL_SIZING_FLOOR` (the floors' answers agreeing behind the closing stage, now
      0.582 plain esd on u), and `INTERMEDIATE_FTOL` with `StageResult.ftol` ("fails on
      SRM 660c, 8.82 esd on axial_sl"; the row passes since WP-2036 ordered the pair and
      still passes with H/L held). WP-2012 left them because a table edit sends the
      branch to the generality judge. The three LaB6 strict xfails in
      `tests/test_window_domain.py` also quote both-free numbers; they still fail as
      expected and were not re-measured. *Done 2026-11-16: `AXIAL_SIZING_FLOOR` gains the
      0.582 and its cause; the same SRM 660c sentence sat in four rows (`INTERMEDIATE_FTOL`,
      `StageResult.ftol`, `PlanSpec:intermediate_ftol`, `StageSpec:ftol`), each now 0.000
      (1.8e-7 on w) and 101/76 evaluations (1.33×), re-measured three interleaved rounds on
      macOS arm64 `[dev]`, None 0.56-0.62 s against 1e-6's 0.50-0.60 s, Rwp equal to 7
      digits. The manual's row and its two sentences (the Inherited item) say the same. Only
      evidence strings moved; `AXIAL_SIZING_FLOOR`'s approved grounds still say the floor
      "passes on LaB6", which is a question for the maintainer (handover entry). The three
      `test_window_domain.py` xfails were not re-measured.*

## Acceptance

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup tests/test_staged_start_invariance.py -k lab6
```

## Handover log

- **2026-11-16** — a ghostshift runner's session (PR #1583). The two SRM 660c minima are
  not two basins of one fit. They are two stopping places on the guard that keeps the
  Gaussian width real: the fit stops where that guard holds at the last reflection's
  Kα2 image, or, when a stage starts a hair past it and the guard drops it, one reflection
  image further down. Which happens turns on a 2e-8 difference at the closing stage's
  start, the same on macOS and Linux and under every small nudge of the start, so the
  floor test fails deterministically and is now a strict xfail. The deeper answer is not
  the better one: each step down in χ² comes from letting the Gaussian width go negative
  over more of the range, and the displacement moves away from NIST's as it does. Picking
  what the protocol should do about it is the maintainer's call, written below.

  *Done.* Task 1 (Findings, 2026-11-16) with its probe at `docs/wp/2084-measure/`. Task 3:
  the lab6 axial-floor row is strict, its reason the cone row. Task 4: the SRM 660c
  sentence re-worded in five `_audit.py` rows (`AXIAL_SIZING_FLOOR`; `INTERMEDIATE_FTOL`,
  `StageResult.ftol`, `PlanSpec:intermediate_ftol` and `StageSpec:ftol`, which carried one
  sentence four times), the manual's tolerance row and its two sentences (the Inherited
  item, folded and removed), and the same stale clause in `schemas/plan.py`'s comment.
  Evidence strings only: no tier, value, grounds or approval moved.

  *Measured* (macOS arm64 worktree venv `[dev]`, compiled tier on, unless named). The
  Findings tables; the tolerance row three interleaved rounds, 101 → 76 evaluations
  (1.33×), 0.56-0.62 s → 0.50-0.60 s, 0.000 esd, Rwp equal to 7 digits. Linux x86_64 on
  the workstation reproduced every printed digit of twenty probe arms. Acceptance
  (`tests/test_staged_start_invariance.py -k lab6`, `-n 3`): 2 passed, 1 xfailed. Fast
  suite on Linux x86_64 (workstation venv, `-n 6`, at 9e6bce19f): 14849 passed, 280
  skipped, 32 xfailed, 1 failed, 653 s. The failure was this branch's: the manual note put
  `reference/refinement` 61 characters over the 50000-character page cap. The note was
  cut to one line and `test_manual.py`'s twin test then passed on macOS. No test added;
  one row went from non-strict to strict, so passed + skipped does not move.

  *Review.* A read-only Opus reviewer re-ran the probe and found no bug; it confirmed each
  monkeypatch takes effect and reproduced every number. Its wording points were taken:
  the floor acts by moving where the closing stage starts, not "not the sizing"; the node
  comparison names its pair; "ten times a rounding" became the measured robustness (both
  arms hold for w nudges up to ±1e-6 relative); the dropped-row value is quoted at the
  stage that drops it; the probe records the compiled tier and whether the cone was
  applied.

  *Generality* (the judge's verdicts, its tables in PR #1583's body): `AXIAL_SIZING_FLOOR`
  **weak**: the added sentence is supported, but the row now contradicts its approved
  grounds, which say the floor "passes on LaB6 … and misses on cpd-1a"; today LaB6 misses
  (0.582) and cpd-1a passes (0.010 since the width twin hold). Author: left the grounds
  alone because they are the maintainer's ruling text; the question is below.
  `INTERMEDIATE_FTOL`, `StageResult.ftol`, `PlanSpec:intermediate_ftol`, `StageSpec:ftol`
  **hold**, with one unmeasured margin noted: a start difference of 2e-8 in Γ_G² can move
  u by 0.58 esd on LaB6, and the tolerance arm missed that only by where it landed. The
  second trigger (a heuristic outside the table) is confirmed absent.

  *Questions for the maintainer* (task 2 stays open on them):
  1. The plan choice. (a) A change that reaches the deeper minimum from the shipped start
     buys 0.24 % χ² by putting Γ_G² under zero at 140 points instead of 75, with the
     displacement 0.22 esd further from NIST's; the evidence here does not favour it.
     (b) Keep a cone row the stage's start violates by a small margin (measured with
     `lm._ON_FACE` at 1e-7): every floor then lands on the Kα2 face, 0.004 esd apart, so
     the floor row would pass, but the start rows would not, because along that face the
     answer still moves 0.44-0.58 esd on w with the path. It changes a tier-1 constant
     the guards share. (c) A finding: the result says which reflection's Γ_G² row the
     answer stops on and that a stage dropped one, and the floor row stays a strict xfail.
     (d) The test's bar includes u, v and w, which every arm's `RESOLUTION_UNCONSTRAINED`
     already marks unquotable; whether a start test should hold rows the result tells the
     reader not to quote is a test-design question. Which, if any?
  2. `AXIAL_SIZING_FLOOR`'s grounds: does ruling (a) of 2026-10-22 stand with LaB6's 0.582
     as the strict xfail in place of cpd-1a's 0.138, and will you re-word the grounds
     and re-date the approval?
  3. `lm._ON_FACE` is tier 1 on "the last-bit disagreement of two association orders";
     here it decides a row at ±1e-8 slack and moves u by 0.58 esd. Should its row's
     evidence say so, and in which WP?

  *Not done.* The three LaB6 strict xfails in `tests/test_window_domain.py` still quote
  both-free numbers and were not re-measured. The `AXIAL_SIZING_FLOOR` evidence still
  calls cpd-1a's corundum c a strict xfail, which it no longer is; that clause is the
  cpd-1a family's, outside this WP's SRM 660c scope.

  *Overlap.* PR #1422 (WP-2012) also edits `docs/wp/README.md`, the generated index; this
  branch rewrites only WP-2084's row there.

  *Next:* the maintainer answers question 1. On (a) or (b), write the change and drop the
  floor row's mark; on (c), build the finding and keep the strict xfail; on (d), change
  the bar. Then question 2 settles the audit row's grounds.

- **2026-11-02, filed by WP-2012's session.** No open WP owns the SRM 660c width minima:
  the index's open rows name WP-2080 (a warm series rung in a wrong basin, a different
  path) and WP-2072 (the Le Bail and Pawley cell), and neither covers the Rietveld
  protocol's widths.
