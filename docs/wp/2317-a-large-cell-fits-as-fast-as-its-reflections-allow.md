# WP-2317 — a large cell fits as fast as its reflections allow: the case, the bar, and the rulings in the way

Milestone: unscheduled · Status: 🔄 2026-11-28 — R0, R2, R3 and R5-R7 ruled, R4 unruled; R7 built on wp2317-window-slack, its suites and PR open; task 1 waits on the maintainer; R6, 5, 7 and 8 open
Track: A large cell
Depends on: —
Priority: P2 2026-11-27 — the scoping WP of a track the maintainer opened for a user at the wall (slowdowns on a 12 × 36 × 4 Å cell); 2314, 2315 and 2316 read its case, its bar and its rulings

## Goal

The track has five things in place:
- a large cell has named benchmark cases in `examples/bench_refinement.py`;
- the user's own case (or a stand-in they accept) is recorded as its
  acceptance case;
- the bar every speed change on the track is judged by is ruled;
- each earlier ruling that costs speed on a large cell has been put to the
  maintainer and answered;
- a cross-code timing on the same pattern says how far rietx is from the
  established programs.

## Context

**Who is at the wall.** A rietx user reported slowdowns on a 12 × 36 × 4 Å cell
(V ≈ 1 730 Å³). We don't yet know their mode, plan, atom count, data or radiation;
getting them is task 1. Until then, **which** of 2314-2316 is the user's path is
unknown, and the three stay provisional at P2.

**The maintainer's instruction, 2026-11-27, verbatim:** "accuracy on par with other
codes is sufficient. speed as fast as possible by any means necessary. surface any
questionable choices I made previously. leave room for exploring angles of attack."

**What that means for a moved number: ruling R0, put back to the maintainer.**
DESIGN-RULES Rule 2 says a pinned number that moves has moved for the right reason
only if the new value is no further from its **reference value** than the old.
Rule 5's *Arithmetic accuracy* says a speed-for-accuracy setting matches what the
established programs deliver. The instruction above fits both, but it leaves
open how to judge two different kinds of move.

- **(a) A rounding-only move**: reassociation, a vectorised loop, a compiled kernel
  computing the same expression. The proposed bar is that every moved converged
  number sits within a stated rounding-scale bound of the old one: |Δ| ≤ 1e-3 of
  its esd, Rwp to 1e-7 relative. Goldens are then re-pinned in the same change,
  with the bound asserted. No reference value is needed, because nothing about
  the model or the stopping rule changed.
- **(b) A real move**: a tolerance, a stopping rule, a method (VarPro, a clamp,
  partitioning inside the solve). It is judged by Rule 2 against an independent
  reference where one exists (WP-2072's SRM 660c certificate, the QPA round
  robins), and otherwise against Rule 5's bar: an answer on par with the
  established programs' on the same pattern, measured by task 6.

Until the maintainer answers, a successor WP treats (a) as the working reading and
holds (b) for a ruling. The compiled tier already has a bar of kind (a):
`compiled.py` rule 3 holds `solve_orbit_sums` to 1e-13 relative. R0 asks whether
that bar extends to a converged fit.

**Ruled 2026-11-27 (R0): allow both kinds of move.** The 1e-3 esd and 1e-7 Rwp
figures in (a) were Claude's proposal and were never ruled. A second independent
review withdrew them the same day: a 1-ulp change in `exp` already moves a
converged fit 0.2-0.5 esd (WP-1940), so no regrouping could meet them. A
regrouping is verified at fixed parameters (`compiled.py` rule 3) and guarded on
the whole fit by the measured spread (`test_compiled_kernels.FIT_THETA_ESD`), with
old and new goldens recorded in the WP. The maintainer generalised it (dictated, one word corrected): "our accuracy threshold should just
be comparable with other Rietveld refinement codes. We don't need to be much more
accurate than them. Consider the user and the amount of accuracy they need on
different measurements. For common applications. This should be a general rule
for the repo." It is now DESIGN-RULES Rule 5 *Arithmetic accuracy*, so a speed
change answers to that bar and Rule 2's pinned-number test governs model changes.

**Ruled 2026-11-27, later (R0 clarified), "in spirit".** A Claude draft had set the
level at a tenth of each quantity's esd, borrowed from McCusker et al. (1999, §7).
The maintainer never ruled that number, and it would have reversed the 2026-11-19
window ruling. His words: "all my comments arise from the same intent: rietx should
strive for a level of accuracy sufficient for users rather than wasting compute.
evidence for this comes from other codes, which clearly have been sufficient for
existing users." Then: "Whether or not 1e-9 should be the bar is not important to
me: as long as you understand the intent and are able to make appropriate judgement
on this tradeoff based on that knowledge going forward, I'd like to leave the
details of judgement and implementation to you." So the level is what the
established programs deliver to their users, and the esd is the unit an error is
read in. Claude settles each speed-accuracy trade under that intent and lists it
under *Settled for you*. Rule 5 *Arithmetic accuracy* carries the level. The window
ruling of 2026-11-19 stands: 2 % windows, closing stage off.

**Probe 1, the synthetic stand-in** ([`2317-probe/probe1_bigcell.py`](2317-probe/probe1_bigcell.py)):
- 12 × 36 × 4 Å, P2₁2₁2₁;
- invented atoms on general positions, placed over the whole cell with every
  symmetry image ≥ 1.5 Å from every other;
- Cu Kα doublet with FCJ, simulated Poisson data;
- the start carries the truth's atoms and is off only in the cell (500 ppm), the
  widths and the background;
- `ins.source.dispersion = None` declared.

Linux x86_64, 4 cores, `[dev]`, compiled tier on, rietx 1.13.0.dev0 at `4e099d68`.

Reflection counts for this cell (unique, absence-allowed, `generate_reflections`;
the compiled model carries a few more past the range end, e.g. 913 against 899):

| radiation, range | P2₁2₁2₁ | Pmmm | Cmcm |
|---|---|---|---|
| Cu Kα1, 2θ ≤ 90° | 899 | 924 | 451 |
| Cu Kα1, 2θ ≤ 120° | 1 601 | 1 630 | 802 |
| Cu Kα1, 2θ ≤ 150° | 2 143 | 2 177 | 1 071 |
| 0.459 Å, 2θ ≤ 50° | 6 477 | 6 525 | 3 227 |

The v1.1 "trigger" case, the largest the bench carries, had 1 188
(line, reflection) pairs over four phases.

Readings, 2026-11-27: one run each, unprofiled wall, so a figure rather than a
range. Task 2's bench cases replace them with min-max ranges.

| case | wall | Rwp | the leading cost (from a profiled run) |
|---|---|---|---|
| Rietveld, `mccusker_default`, 10 atoms, 899 refl | 2.8 s | 0.0517 | spread evenly; nothing to fix |
| Rietveld, `mccusker_structural`, **40 atoms**, 899 refl | **75.0 s** | 0.0867 | the Jacobian is 99 % of the solve, and the coordinate columns rebuilding A are 53.5 of its 72.4 s (**WP-2314**) |
| Pawley, 899 intensity columns | 23.7 s | 0.0447 | the constrained step (**WP-2315**) |
| Pawley, 1 601 columns | **125.4 s** | 0.0420 | `lm._solve_constrained_step` 72.8 s (31 calls), plus 23.9 s in 1 056 `spilu` builds; the Jacobian is 7.5 s (**WP-2315**) |
| Le Bail, 899 refl | **154.9 s** | **0.1512** | 95 % in `_settled_partition`, first probe's profile (**WP-2316**) |
| Le Bail, 1 601 refl | **351.8 s** | **0.1449** | 97 % in `_settled_partition`, first probe's profile (**WP-2316**) |
| `report()` after the 40-atom fit | 5.6 s | | not a cost here (WP-1335 owns the report path) |

**The bench cases (task 2), 2026-11-27.** `examples/bench_refinement.py`, three
repeats, `--configs off`, darwin/arm64 (Apple M-series, 10 cores), Python
3.12.10, numpy 2.5.5, `[dev]` venv, compiled tier on, rietx 1.13.0.dev0 at
`af159cf7` (after WP-2314's hoist and WP-2315's first step). Other runners
shared the machine; each run held the suite lock, and the load fell over the
session, so each range spans the blocks that measured it (two for the first
three, three for Pawley at 90°). These are probe 1's invented structure. The
cases now carry a real one (the next table), and a speed WP re-measures its
"before" beside its own arm.

| case | wall (min-max) | Rwp | per-stage nfev |
|---|---|---|---|
| `bigcell-structural` (40 atoms) | 10.90-11.30 s | 0.08675 | coordinates 10, biso 16; 100 over 11 stages |
| `bigcell-pawley` (2θ ≤ 90°) | 11.82-12.69 s | 0.04466 | 68 over 5 stages; profile 29 |
| `bigcell-pawley-120` (2θ ≤ 120°) | 54.89-64.88 s | 0.04199 | 77 over 5 stages; profile 37 |
| `bigcell-lebail` (2θ ≤ 90°), background seeded | 61.69-61.75 s | 0.04685 | 34 over 5 stages; 25 free |
| the same, unseeded (probe 1's start) | 58.39-83.92 s | 0.15121 | 96 over 5 stages; cell 41 |

`bigcell-lebail` seeds its background with `rx.auto_background(data,
kind="chebyshev", seed=True)`, as WP-2316's inherited entry below asks; the
unseeded start lands in the background valley that entry describes. Seeded, it
spends 34 evaluations and still about 62 s, so the partition is the cost
(WP-2316). The seeded case also carries 16 Chebyshev terms, the order scan's
cap, against the unseeded start's 6, so the two rows differ in the seed and
in ten background columns.

The Linux single runs above and these Mac ranges are on two machines, so their
ratios are not speed-ups. The harness's own `nfev` and `njev` columns print 0
and `-` here: `_counting` wraps scipy's `least_squares`, and the default LM
driver does not call it. The per-stage counts come from `StageResult`.

**The bench cases on a real structure, 2026-11-27 (4th session).** The
maintainer asked for real large cells in place of the invented one: "Don't
use your randomly generated ones", then "the COD cells are fine … so long as
it's not an extremely pathological case". The four `bigcell-*` keys now carry
Nb₁₈W₁₆O₉₃ (COD 2107344, Stephenson 1968), a tetragonal-tungsten-bronze
superstructure:
- Pbam, 12.195 × 36.740 × 3.951 Å, V = 1 770 Å³, the real cell closest to
  the user's 12 × 36 × 4 Å;
- 43 sites, eight of them Nb 0.6 / W 0.4 pairs at one position, which
  `bigcell-structural` ties (two site-symmetry steps and the Biso per pair);
- Biso declared (0.5 Å² for metals, 1.0 Å² for O), since the file carries
  Uiso = 0;
- scale 3e-5, so the strongest peak is about 4 × 10⁴ counts over the
  900-count background, the 40-atom probe's order.

The instrument, the ranges, the Poisson seed and the start protocol are
probe 1's unchanged: the start carries the truth's atoms, Biso and scale, and
is off in the cell (500 ppm high), W and X, the held axial ratios (0.02
against 0.03) and the background. So the pattern is still simulated, and
every row verifies. The cell has no exact b = 3a overlap, unlike probe 1's.
Compiled reflections: 886 at 2θ ≤ 90° and 1 569 at 2θ ≤ 120° (probe 1: 913
and 1 606). The structural case frees 66 coordinate and 35 Biso columns
(probe 1: 120 and 40).

Three repeats, `--configs off`, darwin/arm64 (Apple M-series, 10 cores),
Python 3.12.10, numpy 2.5.5, `[dev]` venv, compiled tier on, rietx
1.13.0.dev0 at `52866c321`. No test suite ran during the block. Old is the
table above (probe 1, another session), so the two columns compare two
structures, not two codes.

| case | wall, Nb₁₈W₁₆O₉₃ (min-max) | Rwp | per-stage nfev | wall, probe 1 |
|---|---|---|---|---|
| `bigcell-structural` | 17.33-17.90 s | 0.03518 | 118 over 11 stages; coordinates 19, biso 33 | 10.90-11.30 s |
| `bigcell-pawley` (2θ ≤ 90°) | 5.24-5.34 s | 0.03086 | 46 over 5 stages; profile 17 | 11.82-12.69 s |
| `bigcell-pawley-120` (2θ ≤ 120°) | 13.81-14.07 s | 0.02997 | 43 over 5 stages; profile 14 | 54.89-64.88 s |
| `bigcell-lebail` (2θ ≤ 90°), background seeded | 14.90-15.71 s | 0.03714 | 26 over 5 stages; 24 free | 61.69-61.75 s |

Read the last column as the old case's cost, not as a "before". The
structural fit costs more on the real cell with fewer columns. It takes 118
evaluations against 100, and Pbam has eight operators against
P2₁2₁2₁'s four; which of the two sets the cost was not measured. The
structure-free fits cost 2-4× less. The seeded Le Bail background has 15
Chebyshev terms here (16 on probe 1's pattern).

Two old readings do not carry over. WP-2316's 25 000-cycle partitions came
partly from probe 1's b = 3a degeneracy, and WP-2315's GSAS-II tie count
(352 intensities against 913) came wholly from it. The GSAS-II rows below are
probe 1's; `2317-probe/export_bigcell.py` now refuses the new phase, since
the driver writes P2₁2₁2₁ at full occupancy.

**Cross-code timing (task 6), 2026-11-27: GSAS-II 5.8.4 on the same four
patterns.** Same Mac, same session, run in blocks under the suite lock:
rietx (the bench), GSAS-II three times per case interleaved by case, rietx
again, then GSAS-II's two Pawley cases again with the final protocol, then
rietx's two structure-free cases again. The machine's load fell over the
session: GSAS-II's Pawley case took 47.03-54.60 s in the first GSAS-II block
and 33.73-34.10 s in the second, at an identical answer. So each range below
spans every block that measured it, the ratio is the ratio of the ranges'
ends, and a block-to-block swing of up to 1.5× sits inside it. GSAS-II ran
single-process (its `Multiprocessing_cores` default, 0); rietx's compiled tier
uses threads.

| case | rietx wall | GSAS-II wall | GSAS-II ÷ rietx | rietx Rwp | GSAS-II Rwp | GSAS-II cycles, variables |
|---|---|---|---|---|---|---|
| `bigcell-structural` | 10.90-11.30 s | 18.13-20.41 s | 1.6-1.9× | 0.08675 | 0.08753 | 20, 176 |
| `bigcell-pawley` | 11.82-12.69 s | 33.73-34.10 s | 2.7-2.9× | 0.04466 | 0.07022 | 35, 367 |
| `bigcell-pawley-120` | 54.89-64.88 s | 164.79-165.57 s | 2.5-3.0× | 0.04199 | 0.06103 | 89, 555 |
| `bigcell-lebail`, unseeded start | 58.39-83.92 s | 79.05-87.19 s | 0.9-1.5× | **0.15121** | 0.0831-0.0835 | 156-161, 15 |

The protocol, matched to rietx's:
- *Data and weights:* the bench's pattern written as 2θ, counts and
  σ = √max(y, 1), rietx's Poisson fallback; 4 250 (5 750) points fitted by
  both, checked on GSAS-II's own count.
- *Free set:* rietx's plan, stage for stage and cumulative, through
  `do_refinements`: background (+ scale in Rietveld), zero, cell, W, then U,
  V, X, Y; then coordinates and Uiso for the structural case. Scale is held in
  the structure-free modes, as rietx force-fixes it. Both hold the axial
  terms, and both start them at 0.02 against the truth's 0.03, which is the
  low-angle misfit both curves share.
- *Model:* Cu Kα doublet at rietx's wavelengths, graphite monochromator at
  26.6° (Polariz. 0.5557), Bragg-Brentano at 250 mm. rietx's Γ_G² (deg²) is
  8 ln 2 times GSAS-II's σ² (centideg²); X (1/cosθ) and Y (tanθ) mean the
  same in both, and rietx's held `lor_size` folds into GSAS-II's X. GSAS-II's
  single FCJ term is SH/L = S/L + H/L. **Dispersion off on both sides**: the
  driver patches GSAS-II's `GetFprime` to f′ = f″ = 0, since rietx declines
  dispersion here and GSAS-II offers no switch.
- *Start:* the same cell (500 ppm high), widths, background and atoms. The
  Rietveld scale is seeded by one untimed zero-cycle calculation, as rietx's
  start carries the true scale.
- *Pawley:* GSAS-II's own "Pawley create" and "Pawley estimate" (re-done in
  the driver, which has no GUI), every intensity flagged to refine, `Pawley
  dmin` at 2θ_max and the default `dmax`. GSAS-II then ties reflections whose
  d agree to 1e-4 (`GetPawleyConstr`). This cell has b = 3a exactly, so
  (h k l) and (k/3 3h l) coincide in d, and **GSAS-II refines 352 (540)
  independent intensities where rietx carries one column per reflection**
  (913 and 1 606 in the compiled model). rietx holds such a pair by an
  equal-split restraint row instead. This bears on R5.
- *Le Bail:* the GUI's "reset Le Bail structure factors? Yes" path: unity
  start, one Le Bail-only pass (`DoLeBail`, 1 cycle), then least squares,
  which re-extracts once per cycle.
- *Stopping:* GSAS-II's default, a 0.1 % change in χ² per cycle (`min dM/M`),
  with 100 cycles a step as rietx-bench caps it. rietx stops at 1e-6
  (intermediate stages) and 1e-9 (the last). That is R6's question.
- *Timed:* `do_refinements` alone, its `.gpx` writes included; rietx's
  `fit()` alone.

The driver and exporter are `2317-probe/gsas2_bigcell.py` and
`2317-probe/export_bigcell.py`. Three readings, each a measurement whose
mechanism was not measured:
- **Structural:** rietx is 1.6-1.9× faster at the same Rwp to 1 %.
- **Pawley:** rietx is 2.5-3.0× faster and lands lower: Rwp 0.0447 against
  0.0702 at 90°, 0.0420 against 0.0610 at 120°. 41 % and 43 % of GSAS-II's χ²
  sits below 6°. That is the tail of (0 2 0) at 4.9°, which rietx carries and
  GSAS-II does not draw. GSAS-II's Rwp is the same to five digits with that
  reflection in its Pawley list or out of it, and with it in, each of the five
  steps drops its intensity as singular. From 6° up GSAS-II's Rwp is 0.054
  (0.046 at 120°).
- **Le Bail, from probe 1's unseeded background:** the walls overlap, and
  **rietx lands at 1.8× GSAS-II's Rwp**. The plot shows rietx drawing peaks
  where the data have none (near 7.5° and 20°) and its background pulled under
  the data; its b came out 2 400 ppm low (35.914 Å) with a zero of −0.075°.
  GSAS-II's curve follows the data except the first degree, but its a came out
  1 700 ppm low (11.980 Å). From the same all-zero background, GSAS-II's
  Le Bail reaches a better curve than rietx's. WP-2316 found the cause on
  rietx's side (the inherited entry below). From the seeded background the
  bench case now uses, rietx lands at 0.0469 in 61.7 s. GSAS-II was not run
  from that seed. Its `chebyschev-1` is rietx's basis, T_n over 2θ mapped
  onto [-1, 1] (`GSASIIpwd.getBackground`), so the exporter's coefficients
  carry over term for term and the driver can run it as committed.

Three readings shape the track.

- **Le Bail is 3-7× slower than Pawley here (6.5× at 899 reflections, 2.8× at 1 601)**, against the practice survey's
  expectation (RIETAN-FP: Le Bail "needs no large normal matrix"). This is
  consistent with R2 below.
- **Le Bail also lands at three times Pawley's Rwp on the same pattern** (0.151
  against 0.045). That is a correctness question before it is a speed one: a
  wrong valley, the background protocol (WP-1542's subject), or the partition.
  WP-2316 task 1 answers it before any speed work. *Answered 2026-11-27:
  a wrong valley entered through the probe's unseeded background (§ Inherited).*
- **The first probe drew its atoms inside a 1/15.6 sub-box**, 65 % of nearest
  neighbours under 1 Å (the review's S3). It read 251 s for the 40-atom case, with
  119 `coordinates` iterations, measuring the degenerate model. The readings
  above use atoms ≥ 1.5 Å apart. The Pawley and Le Bail cases barely moved
  between the two models (20.7 → 23.7 s, 82.7 → 125.4 s, 144.6 → 154.9 s,
  351.3 → 351.8 s): the Pawley 1 601 case crossed rows 31 times rather than 24.

**The earlier rulings that cost speed on a large cell, as the instruction asked.**
None is changed by this file; task 3 puts each to the maintainer. Each entry gives
where the choice was made, the reasoning given for it, what practice does, and
what it costs here.

- **R1 — bit-identity as a speed WP's own bar.** This is *not* a ruling. It is a
  convention some speed WPs set themselves, most explicitly WP-1109 ("the bar this
  WP set") and WP-1945 ("Bit-identity per family is the bar"; "kept only if
  bit-identical"). Others moved numbers when they had cause:
  - WP-1123 moved the tolerance;
  - WP-1953 moved FAP's Pawley Rwp, 0.0803 → 0.0782;
  - WP-2011 moved NAC's Pawley Rwp, 0.12591 → 0.12592;
  - WP-2222 turned the closing stage off.

  `compiled.py` rule 3 already admits a stated bound for a transcendental. The
  convention forbids every reassociation (`np.bincount` for `np.add.at`, a
  vectorised atom loop, a fused kernel), and R0 (a) is the proposed replacement.
  *Closed 2026-11-27 by R0.*
- **R2 — a Le Bail partition settles to 1e-7 of the Bragg counts with the model
  frozen.**
  - *Where:* WP-1542, under WP-2002's ruling B11; `lebail_tol` = 1e-7 settled by
    Claude under the maintainer's delegation of 2026-11-05; cap 25 000.
  - *Reasoning:* `tests/test_window_domain.py` bar 1, max|Δy|/σ ≤ 0.1 at fixed
    parameters against a 1e-10 reference. 1e-7 was "the largest decade under the
    bar on all seven from flat", with FAP failing it warm at 1.23. Note that this
    reference is rietx's own, not another code.
  - *Practice* (`docs/practice.md` § Structure-free fitting): GSAS-II, FullProf,
    TOPAS and RIETAN-FP extract **once per least-squares cycle** and let the
    intensities converge across the refinement, and GSAS-II's refinement stops at
    a 1e-3 relative change.
  - *Cost:* 95-97 % of a Le Bail fit here (the first probe's profiled runs).
    WP-1542 named LaMnO₃'s 12 293 cycles (from a flat start; 8 495 in-fit) at
    150× the wall clock.
  - *Owners:* WP-2316 owns the cost. **WP-2017's group Q owns the number**
    (`StageSpec:lebail_tol`, on LaB₆ + cBN, `fap`, `cpd1a`).
- **R3 — DESIGN-RULES Rule 5, *Structure-free fitting* (ruled 2026-11-05, #1434),
  in full:** "Pawley is the structure-free method rietx leads with. WP-2062
  carries the move to it as the default. Le Bail gets only what a ruling already
  asked of it, in its smallest correct form. A change to Le Bail that moves every
  fit's numbers waits for WP-2062."
  - Read whole, the clause argues for routing a large cell to Pawley (on this case
    already 3-7× faster than Le Bail), not for a Le Bail speed project. The third
    sentence also fences even a bit-identical Le Bail kernel that no ruling asked
    for.
  - *Question:* does a user at the wall on Le Bail count as the ruling that asks?
  - **Ruled 2026-11-27 (R2, R3): follow best practice and lift the fence.** The
    maintainer also ruled that the Le Bail and Pawley speed work goes ahead
    whatever the user's case shows, since cells this size are met in the wild.
    He asked why rietx diverged from practice here, and that every cascading
    change is found and made with it. Rule 5 *Structure-free fitting* now says
    Le Bail follows the established programs' practice.
- **R4 — the width floor is held inside the step in every mode** (WP-1938 D8,
  WP-2153).
  - *Reasoning* (the `gaussian_width_inequalities` docstring): without the row,
    LM stalled:

    | case | LM Rwp | TRF Rwp |
    |---|---|---|
    | NAC | 0.18028 | 0.13375 |
    | Cr₂WO₆ | 0.25458 | 0.09924 |
    | LaB₆ with a free width equation | 0.195 | 0.0416 |

    The same docstring says GSAS-II's by-value clamp works because its Marquardt
    takes no bounds.
  - *Practice:* GSAS-II and FullProf clamp per reflection, by value.
  - *Cost here:* a dense step past `BVLS_MAX_COLUMNS`, which WP-1938 left because
    no fit it ran crossed a row. The probe's crossings may come from its instrument
    (U = V = Y = 0 truth) and need confirming on real data (WP-2315 task 1).
- **R5 — every Pawley intensity is a full column of θ** (WP-0306). WP-1125's
  invariant says profiling a linear block out "cannot buy an evaluation", but that
  Pawley *dimension* is "a per-step cost", and that a bounded block leaves the
  identity once a bound is active. On a large cell the dimension is the cost.
  - **Ruled 2026-11-27 (R5): "go (b)".** Reflections whose d coincide for every
    metric of their Laue class (cubic 333/511, hkl/khl under 4/m) merge into one
    intensity column, the sum measured and each member's share unmeasured.
    Accidental coincidences (b ≈ 3a) keep the restraint while their practice is
    surveyed. Built under WP-2315.
  - **Ruled 2026-11-27 (R5 c): "follow your recommendations".** Accidental
    coincidences keep the soft restraint, retargeted to equal F², and report the
    group sum as the measurement. Practice mostly ties nothing (TOPAS), or ties
    only in low symmetry (GSAS-II) or in a hybrid step (RIETAN-FP)
    (`docs/practice.md` § Accidental overlaps during extraction).
- **R6 — the stopping rule.**
  - *rietx:* intermediate stages at 1e-6 (`intermediate_ftol`, WP-1123), the last
    declared stage at the solver's 1e-9. The closing stage is **off by default
    since WP-2222** (`closing_window_tol = None` on both `mccusker_*` presets).
  - *Practice* (`docs/practice.md` § When a fit stops): GSAS-II stops at 1e-3
    relative change and 3 cycles a `Refine` call; FullProf stops when every shift
    is under `Eps` × its esd (0.2 "or lower").
  - *The question:* is 1e-9 on the last stage more than "on par" buys? It is a
    kind (b) move under R0.
  - **Ruled 2026-11-27 (R6): "Start with your recommendation. Consider best
    practice."** The recommendation: the last stage stops on a FullProf-style
    test, every free parameter's last shift under a fraction of its esd, with the
    fraction measured against FullProf's 0.2 and GSAS-II's answer on the bench
    cases. The three compounding places keep 1e-9 through a plan field. The change
    is measured before the default moves.
  - **Measured 2026-11-27 (`2317-probe/convnoise/RESULTS.md`), and the
    recommendation withdrawn: settled by Claude under that measurement.** Five single
    fits (SRM 660c, FAP, NAC, cpd-1a, the COD large cell) and two series (CuCr₂O₄,
    17 patterns; cpd-1, 8 patterns) ran each stop as a real stop on the last stage.
    - A FullProf 0.2 or GSAS-II-like stop **alone** is unsafe. On cpd-1f both
      stopped mid-crawl with `axial_sl` 18 esd from the answer and χ²_red 9 % high,
      and reported converged. The 1e-4 and FullProf 0.1 stops landed within 0.1 esd.
    - Single fits: every stop holds every family under 0.06 reported esd; 1e-6
      under 0.0075. The last stage is 9-29 of 40-165 evaluations, so 1e-6 saves
      0-9 % of a fit.
    - Series: the stop is most of the bill (CuCr₂O₄ 1 293 evaluations at 1e-9,
      1 089 at 1e-8, 695 at 1e-6). At 1e-6 the 1 wt% CuO cell sits 0.68 esd off.
      At 1e-8 every quantity is under 0.072 esd (cpd-1 profile), a margin of 1.4×
      on development data.
    - The floor is zero on single fits (≤ 4.5e-6 esd) and not on a series: on
      cpd-1 one start in ten moves `axial_sl` 0.5 esd. The large cell's apparent
      second minimum was a fixture defect (`co_sited()` rounds to 1e-4, so the
      nudge decided two ties), found by `2317-probe/errmeasure/`.
    - χ²-based decisions keep ≥ 100× margin over a single fit's stop, except
      profile-interval refits, whose settle tolerance a GSAS-like stop exceeds.
    - ~~**Settled:** the shipped schedule stays (1e-6 intermediate, 1e-9 last). The
      runner-up, 1e-8 on the last stage, saves 7-16 % of a series and 0-4 % of a
      single fit, at a 1.4× margin measured only on development data.~~ That
      margin was against the tenth-of-an-esd draft level, which R0 clarified
      withdrew.
    - **Re-settled 2026-11-27 by Claude under R0 clarified: the last stage stops
      when every free parameter's shift is under 0.1 of its esd.** That is the
      field's test of a published refinement (McCusker et al. 1999 §7; checkCIF
      alert B above 0.10), so it is parity with what other programs' users
      publish. Their default stops are not parity: GSAS-II's 1e-3 and FullProf's
      0.2 ended cpd-1f 18 esd off and reported convergence. Measured against the
      1e-9 answer (`2317-probe/convnoise/RESULTS.md`, addendum for 1e-7):

      | stop | CuCr₂O₄ ramp evals | worst (esd) | cpd-1 evals | worst (esd) |
      |---|---|---|---|---|
      | 1e-9 (shipped) | 1 293 | 0 | 517 | 0 |
      | 1e-8 | 1 089 | 0.006 | 479 | 0.072 |
      | 1e-7 | 917 | 0.022 | 442 | 0.22 |
      | shift/esd < 0.1 | 363 | 1.2 | 322 | 0.071 |
      | FullProf 0.2 | 300 | 1.7 | 312 | 18 |
      | GSAS-II 1e-3 | 183 | 1.8 | 269 | 18 |

      The worst entry on the ramp is the cell of CuO at about 1 wt%, on a flat
      valley; the main phase stays under 0.053 esd. A departure of one esd is
      inside the error bar the user is shown, and it is what a FullProf user
      reporting shift/esd 0.1 gets. Single fits stay under 0.06 esd at every
      stop. Runner-up 1e-7 holds every quantity to 0.22 esd at 2.5× the
      evaluations on the ramp; it loses on the intent (accuracy no user reads,
      paid in compute). The three compounding places (WP-2222) keep 1e-9 through a
      plan field. The measured test used the damped LM step, and a crawl takes
      short damped steps, so the implementing change tests the shift of the
      undamped Gauss-Newton step, which a crawl cannot shrink. It re-pins goldens
      (R0) and checks that profile-interval refits still settle.
    - **The two programs' stops in their own programs** (Measured 2026-11-27,
      `2317-probe/foreign_stops/RESULTS.md`). Each program was compared with
      itself, default stop against tight, from its own warm start on cpd-1f.
      - GSAS-II's 1e-3 test leaves the answer short at home too, and says
        converged: on cpd-1f 13 cycles, χ² 0.38 % high, zincite c* 16 esd off,
        Zero 14, Shift 12. One default `Refine` (3 cycles) is 34 esd off and says
        not converged. Its own floor between two tight starts is 1.5 esd. On the
        CuCr₂O₄ ramp in sequential mode, 1e-3 alone has all 17 patterns say
        converged with the CuO Dij 10.5 esd and U 52 esd off.
      - FullProf's Eps 0.2 does not: 12 cycles and 0.08 esd from its tight run,
        with `S_L` held. Its steps are undamped Gauss-Newton, so a crawl does not
        shrink them. That is why the implementation tests the undamped step.
      - For GSAS-II, the in-solver failure (18 esd) carries over to its own
        program. For FullProf, it came from rietx's damped steps. Either way the
        rule's sentence ("their thresholds do not carry over") stands.
      - Program defects seen (recorded, not acted on): GSAS-II accepted
        χ²-raising steps and still said converged; it lets W go negative; it
        refuses cell refinement in sequential mode. FullProf printed
        "Convergence reached" after diverging to NaN from rietx's `seed_scales`
        start, froze U, V, W once the Gaussian FWHM² went negative, and quotes an
        `S_L` esd about 23× GSAS-II's (inference: too small).
    - Unexplained, recorded for a later WP: the reported χ² differs from the χ²
      the solver minimised by 0.2-2.1 χ²_red at the answer, and that gap moves
      0.1 χ²_red between nearby answers.
- **R7 — `WINDOW_MIN_DEG` = 0.3° of movement slack per window side**
  (`src/rietx/model/forward.py:234`).
  - About 30 of the probe's ~122 points a window (~25 %) are slack at a 0.02°
    step, and the share grows as 1/step on synchrotron data.
  - The slack could be sized from the stage's own moving position parameters
    instead. This is a kind (b) move, and it is not WP-2051's per-evaluation
    windows.
  - **Ruled 2026-11-27 (R7): "follow your recommendations".** The slack is sized
    per stage from the stage's free position parameters, with a refit on fresh
    windows when `window_loss` passes its tolerance. No surveyed program adds
    movement slack, since they rebuild windows or freeze them with none
    (`docs/practice.md` § Room for a peak to move inside its window).
- **R8 — the bench measures the shapes it was built on.** No
  `bench_refinement.py` case has more than ~1 200 (line, reflection) pairs or
  ~15 atoms in a phase. So v1.1's ranking under-weights every term that grows with
  the atom count or the reflection count, which WP-1111 said of its own
  baselines.
  *Closed 2026-11-27: task 2's four bench cases (PR #1864).*

**Angles beyond the three WPs** (kept open, not yet measured):

- **Threads.** The compiled pool already runs the plane kernels and
  `solve_orbit_sums` / `solve_orbit_sums_one`, the per-site orbit sums the
  structure solver uses (wheel ≥ 1.4.0, held to 1e-13). The refinement's own
  structure factor, the partition and the per-column Python chains do not use
  them. OpenBLAS threads `eigh` and GEMM already.
- **fp32 Jacobian columns on CPU.** The fp64 invariant allows them (the trust
  region re-measures each step in fp64), so a structural column block in fp32 is
  within "by any means", with the residual and the solve still fp64. It moves the
  solver's path, so it is a kind (b) move under R0, and is measured as one.
- **`backend="jax"`: expect little.** Its own docstring says the cost is "one
  tangent per column ≈ one forward evaluation each, the same order as plain FD",
  and the traced residual unrolls `_phase_component_scalar`'s per-reflection loop
  into the jit graph (~1 800 windows at 899 reflections under the Cu Kα
  doublet, ~6 500 at 6 477 on one 0.459 Å line). So compile time likely
  dominates. Run it once under a runaway guard, for the
  record. It gates nothing.
- **Iterations, not only cost per iteration:** R6, and task 5.

### Inherited

- **2026-11-27, research for the rulings (three read-only agents; file:line in
  their reports, summarised here).**
  - *Why Le Bail diverged (R2).* The extraction has sat between solves since v0.1
    (`f51e8e67b`), under the frozen-per-stage rule written the same day. WP-2062
    states the reason: the trust region judges each step against one fixed
    objective. Ruling B11 (2026-10-19) asked to "repeat until the intensities stop
    changing" on the premise that every refiner does so; none surveyed does
    (`docs/practice.md` § Structure-free fitting). WP-1542 built the settled
    partition to it, on issue #740 (Rwp 4.56 % at 3 cycles against 1.09 % for the
    true structure) and on `test_window_domain.py` bar 1, a bar written for peak
    windows. The fence came from a delegated settlement in WP-1542, not a ruling of
    the maintainer's.
  - *Cascade of a per-cycle extraction.* LM needs a between-iteration hook and a
    gain-ratio rule for a moving objective. The intensity snapshots
    (`least_squares._lebail_snapshot`, `traced.py`) freeze per solve.
    `lebail_passes`, `LEBAIL_CONVERGED_REL`, `LEBAIL_CYCLES_AT_CAP`,
    `StageResult.lebail_cycles_run`/`.lebail_settled` and `StageSpec.lebail_tol`/
    `lebail_cycles` change meaning. A new `NodeAction` field is a stored-format
    change and goes to the maintainer. The extinction screen's prefit, the GUI
    (wizard default, Adopt, `.rxt` words, dist), `help.py`, `_audit.py` rows, the
    manual's `fm-lebail-stop` equation, the skill's two rows and WP-2017 group Q
    follow. Tests: `test_lebail_cycles.py`, `test_lebail_alternation.py`, NAC,
    SRM 676a and indexing acceptance, validation-matrix rows. Unchanged: the
    Pawley seed, the report's `lebail_gap`, the `toy_lebail` goldens. Risk:
    #740's 3-cycle plateau returns unless the stop reads the χ² change per
    extraction and an initial extraction runs first (FullProf: "say 10").
  - *R0's cascade into the root CLAUDE.md.* The compiled tier's rule 3
    ("associations as written") and the `_orbit_terms` association clause predate
    R0. The off-state clause stays bit-identical (Rule 4). Rule 3 is revisited
    when a kernel first regroups.
  - *R5.* GSAS-II's merged Pawley intensities are not symmetry equivalents, which
    both codes already merge into one reflection. GSAS-II ties (b) lattice-forced
    coincidences by integer identity in the higher Laue classes, and (c) any pair
    within 1e-4 in d in -1, 2/m and mmm. The b = 3a case is (c). rietx groups
    within 0.5 FWHM and restrains toward equal peak intensity, where the
    equipartition convention is equal F². TOPAS ties nothing automatically.
  - *R4.* GSAS-II clamps by value and its derivative ignores the clamp, so a
    clamped reflection keeps pulling U, V, W back. FullProf's peaks vanish at
    1e-10. RIETAN-FP refuses a step to a negative width. Every probe crossing was
    on the Lorentzian rows.
  - *R6.* `ftol` is the relative decrease in S over three consecutive accepted
    iterations. GSAS-II stops at 1e-3 relative χ² (about 2 esd of joint movement
    at N = 5 000, inferred), FullProf at shifts under 0.2 esd, TOPAS on
    `chi2_convergence_criteria` for three cycles. Nothing looser than 1e-8 was
    ever run on the last stage. WP-2045 kept 1e-9 after cpd-1b stalled at 1e-6.
  - *R7.* 0.3° dates from v0.1 and became capture slack in WP-1112. WP-2002 B10
    measured a largest move of 0.21° over four families. Sizing it per stage from
    the free position parameters needs a bound on each one's movement.

- **From WP-2316, 2026-11-27 (task 1): probe 1's Le Bail fit sat in a wrong
  valley, and the cause is its background seed.** Probe 1 starts every
  Chebyshev coefficient at 0. Le Bail's first partition hands the 900-count
  pedestal to the reflections, and the fit ends with the background at c0 261
  and Rwp 0.151. Seeded with `rx.auto_background(data, seed=True)`, as SKILL.md
  §2 rule 5 says, it lands at 0.047 against Pawley's 0.044 with
  `kind="chebyshev"`, and at 0.048 with the default P-spline. So the Le Bail row
  of the readings table timed a fit at the wrong answer. Two points for task
  2's `bigcell-lebail` case:
  - seed its background as the skill does, or WP-2316 measures the speed of
    the wrong answer;
  - the invented cell has b = 3a exactly, so 779 of its 899 reflections share
    a d-spacing with a neighbour. A refined cell splits each pair by about
    1e-4, and the partition then runs to its 25 000-cycle cap. Restoring
    b = 3a at Pawley's answer still runs to the cap, so the degeneracy is not
    the whole cause. A case meant to stand for real large cells may want a
    cell without it.
  WP-2316's 2nd-session entry has the tables.
  *Taken 2026-11-27: `bigcell-lebail` seeds its background (Context, the
  bench table); the cell is unchanged, so the bench keeps probe 1's pattern.*

- **From WP-2315, 2026-11-27 (task 1).** R4's "may come from its instrument"
  is half answered. Real patterns on the tree reached the constrained step
  once in 32 least-squares runs (FAP.XRA, 11-BM NAC whose Pawley block has
  1 499 columns, FAP.XRA's `index_pattern` validations, QPA round robin
  cpd-1a and cpd-1h). Probe 1 crosses 22 times at 90° and 31 at 120°, every
  time on the **Lorentzian** rows (Γ_L ≥ 0), not the Γ_G² floor. A true
  `lor_strain` of 0.03 in its truth removes the crossings at 90° and raises
  them to 53 at 120°. So the probe's zero strain is not the whole cause.
  `solver="trf"` ran 159.5 s at 90° against LM's 13.6 s (one run each) and stopped its
  `profile` stage at the cap (Rwp 0.0511 against 0.0447), so R4's cost model
  has no TRF shortcut. Task 1 here (the user's pattern) decides whether
  WP-2315 stays P2. WP-2315's Context § Task 1's count has the table.
  For R0: WP-2315's blockwise G·E⁻¹ (its Angle 0) is byte-equal under
  macOS Accelerate but not under x86_64 OpenBLAS. A BLAS fixes no reduction
  order, so even a cost-only rewrite of a matrix product is a rounding move
  under R0 (WP-2315's 3rd-session handover).

- **From WP-2314 (2026-11-27, PR #1862):** angle 1, the structure-factor
  hoist, landed byte-equal, so probe 1's `bigcell-structural` numbers are
  stale for the coordinate columns. On one Mac (arm64, `[dev]`), main against
  the branch, interleaved: the fit took 29.7-29.9 s against 11.2-11.3 s, and
  one Jacobian 0.348 s against 0.106 s (profiled). What remains of the
  Jacobian is mostly the Biso, occupancy and cell columns by finite
  difference: 6.6 s of 8.8 s. Those are WP-2314's angle 3, waiting on R0.
  Task 1's re-rating of 2314-2316 starts from these numbers. The driver,
  `2314-probe/drive_bigcell.py`, runs both arms and prints a bit-level digest.

- **From WP-2315, 2026-11-28:** for R4's cost, the real-structure bench cases
  never reach the constrained step. `bigcell-pawley` and `bigcell-pawley-120`
  carry 3 544 and 6 272 width rows in their last stage and cross none, so the
  in-step floor costs them nothing. Probe 1 still crosses on the same tree,
  with the same instrument and start, so its crossings came from its
  invented structure, not the U = V = Y = 0 truth. On the 120° case about
  half the 15 s fit is `spilu`'s factorisation (WP-2315 Angle 4). WP-2315's
  Context § Re-read on the real structure has the table.

## Non-goals

- The fixes themselves: WP-2314 (structural columns), WP-2315 (Pawley step),
  WP-2316 (Le Bail partition).
- The report path (WP-1335), the peak-chain columns (WP-1945), per-evaluation
  windows (WP-2051, filed).
- Which structure-free method is the default: WP-2062. This WP asks only about
  R3's reach.
- The Le Bail tolerance's number: WP-2017's group Q. R2 here asks the prior
  question, whether a partition must settle inside a frozen solve at all.

## Tasks

- [ ] Ask for the user's case: mode, plan, free parameters, atoms in the
      asymmetric unit, space group, radiation and range, point count, and the wall
      clock they see. Record it, or the stand-in the user accepts, as this track's
      acceptance case. Re-rate 2314-2316 on it.
- [x] Add bench cases built from probe 1's generator (atoms ≥ 1.5 Å apart, the
      start carrying the truth's atoms, dispersion declared): `bigcell-structural`
      (40 atoms, `mccusker_structural`), `bigcell-pawley` (2θ ≤ 90° and ≤ 120°)
      and `bigcell-lebail`. Each WP measures its own before and after on them,
      **interleaved, on one machine, in one session, quoted as a min-max range**
      (the harness's rules 1-3). A figure in another WP's file is never a "before".
      *Done 2026-11-27: four cases (`bigcell-pawley-120` is the 120° one), each
      reproducing probe 1's pattern bit for bit; the ranges are in Context.*
      *Rebuilt 2026-11-27 (4th session) on a real structure, as the
      maintainer asked ("Don't use your randomly generated ones"): the same
      four keys, modes, ranges, instrument and start protocol, on Nb₁₈W₁₆O₉₃
      (COD 2107344, Pbam, 12.195 × 36.740 × 3.951 Å, 43 sites). The new
      ranges are in Context, § The bench cases on a real structure.*
- [ ] Put R0-R7 to the maintainer as one batch, each with the cost above and what
      practice does. Record each answer here as a dated ruling, and push each into
      the `### Inherited` of the WP it unblocks: 2314-2316, and WP-2017 for R2's
      number.
- [ ] R6 as re-settled: the last declared stage stops when every free shift of
      the undamped Gauss-Newton step is under 0.1 esd, and a plan field keeps 1e-9
      in WP-2222's three compounding places. Re-pin the goldens in the
      same change (R0), and check that profile-interval refits still settle.
- [x] Why the 40-atom `coordinates` stage took 119 LM iterations from the true
      coordinates. *Answered 2026-11-27 by the review: the first probe drew its
      atoms inside a 1/15.6 sub-box, 65 % of nearest neighbours under 1 Å. On
      atoms ≥ 1.5 Å apart the stage takes 10.*
- [ ] Watch the iteration counts on the user's case once task 1 has it. A
      structural stage started at the answer should stop in a few iterations,
      and one that does not says something about the model, not the code.
- [x] Cross-code timing: GSAS-II (whose source rietx may read; installability to
      be checked) on probe 1's pattern under the same free set (structural, Pawley,
      Le Bail), with its own wall and Rwp beside rietx's. It supplies R0 (b)'s
      "on par" comparison, and it is the reference for "as fast as possible".
      *Done 2026-11-27 for all three modes (Context, Cross-code timing). Not
      done: GSAS-II from the seeded Le Bail background.*
- [ ] R7 as ruled: window slack sized per stage from its free position
      parameters, one re-solve on fresh windows past the window fraction.
      *Built 2026-11-27/28 on `wp2317-window-slack`; suites and PR open.*
- [ ] The joint runner's re-solve (`multi.py`), which R7 left out.
- [ ] `backend="jax"` on the three bench cases once, under a runaway guard: wall,
      compile time, Rwp.
- [ ] Skill: none until a fix lands. The interim advice (Pawley over Le Bail on a
      large cell; restraints and Biso ties to cut the free coordinates) is a
      measurement on rietx's own runs, so Rule 3 keeps it out of the skill.

## Acceptance

- The bench cases exist and print.
- R0-R7 each carry the maintainer's dated answer.
- The user's case, or the accepted stand-in, is recorded, and 2314-2316 are
  re-rated on it.
- GSAS-II's timing on probe 1 is recorded, or the reason it could not be.

```sh
.venv/bin/python examples/bench_refinement.py --cases bigcell-structural,bigcell-pawley,bigcell-lebail
.venv/bin/python -m pytest tests/test_docs_consistency.py
```

## References

- Le Bail, A. (2005). *Powder Diffr.* 20, 316-326.
- Kariuki *et al.* (1999), as cited by Le Bail (2005, §VI); not read.
- Coelho, A. A. (2005). *J. Appl. Cryst.* 38, 455-461.
- `docs/practice.md` § Structure-free fitting, § When a fit stops, § Peak-width limits.

## Handover log

### 2026-11-28 (2nd session) — R7's handover: the slack follows what a later stage refits, the Le Bail warning read, the PR opened (runner 3)

R7 is in a pull request, #PRNUM, which waits on the maintainer for a
stored-format change. The generality judge found that a stage sized its
windows whenever any stage came after it, while the rule says "a stage a later
stage refits". A stage whose cell a later stage fixes now keeps the old
uniform windows, as the last stage does. The Le Bail warning that runner 2
flagged is a correct reading. The package gave the same warning at the same
state before R7, and R7 now reaches that state from every near start. The
Le Bail slow row did run away under R7, past twice its documented time. A
stage now re-solves only an answer that fits the data better than the
stage's start, each read on windows that hold its peaks.

**For the maintainer** (the top of the PR body).
1. *Stored-format change.* `NodeAction.movement_slack: bool = False` is
   written to `history.jsonl` on every stage node. A new build reads an old
   node as `False`, which is what it ran. An older build refuses a new node
   (`extra="forbid"`), the shape WP-2315's `ReflectionState.merged_groups` had
   when it was ruled (a) on 2026-11-27. Options: (a) keep the field, so replay
   reproduces the stage exactly; (b) drop it, so replay compiles the uniform
   slack and differs by up to 2e-3 in Rwp, a staleness the history docs
   already allow, with the exact-replay test relaxed; (c) derive it, which the
   node cannot, since it does not know whether a later stage followed.
   Recommendation: (a), a clear call on the sibling ruling.
2. *Reader output, two cases.* (i) The cpd-1b hostile runaway (reached only
   under the pre-WP-2045 tolerance schedule) now re-solves, and
   `STAGE_WINDOWS_STALE` reads the second solve, so the warning no longer
   fires; the 73 % stays on `StageResult.window_refit_loss`. The judge called
   this weak: the code has no fit-level case left that fires it. The re-solve
   gate below does not change this case, since its answer beats its start on
   fresh windows (`test_the_hostile_pairs_runaway_reports_its_stale_windows`
   passed alone, 41 s). (ii) A fit
   with `lebail_passes` > 1 from a near start now ends with the
   `LEBAIL_ALTERNATION_STOPPED` warning where it ended with `info`. Settled
   by Claude as a correct reading (below), and a blind reviewer agreed.
3. *Audit rows the judge did not pass.* `WINDOW_MOVE_FWHM` (3 FWHM) lost its
   `approved_by="checked"`: the judge called it weak, since no series was run
   sized against uniform. It needs the maintainer's approval or that
   measurement (the cpd-1 chain or the CuCr₂O₄ ramp, worst departure in esd).
   `StageSpec:window_slack_deg`'s approval moved to R7's ruling date,
   2026-11-27, since its meaning changed then.

**Done (runner 3).**
- `staged.refit_later`: a stage sizes its slack only where every path it
  frees is free again in a later stage, read as `fixed_at_end` reads a plan.
  The decision rides `_StageHold.movement_slack` to the history node, so
  replay compiles what ran (`79d6f4bc9`). Tests: a later `turn_off` keeps the
  uniform slack and records `False`; the closing stage refits what the plan
  leaves free, and a declared `turn_off` reaches it (`373f6f42e`).
- **The slow row's runaway, fixed** (`63d154e1c`). Alone, through
  `serial.py`, it was killed at the 3 208 s cap. The same fit on the base tree
  took 246 s. A stage-event probe showed why: the `profile` stage of pass 1
  ends on windows dropping 87-95 % of the intensity, and R7 re-solved it from
  there. That walk widened the peaks until the closing stage's Le Bail
  partition, on windows at 1e-3 of those peaks, ran for minutes (a stack dump
  sat in `_settled_partition`). `refine._improved_on_fresh_windows` compares
  the weighted residual at the stage's start, on its own windows, with the one
  at its answer, on windows sized there. A stage no better keeps its first
  answer and its loss, as before R7, and `STAGE_WINDOWS_STALE` reports it on
  the last stages. The probe now ends in 435 s (pass 1 of 2 kept, 91.2 % then
  335.1 %), on a machine running a suite beside it. The near Le Bail starts
  read the same to three decimals. Tests: the gate both ways on the synthetic
  fit, and a stage it refuses keeps its loss.
- The judge's stale texts: `STAGE_WINDOWS_STALE`'s help, the skill row's
  73 % moved to `window_refit_loss`, `WINDOW_MIN_DEG`'s comment (it is tail
  room too), a test docstring. Audit evidence for `window_refit_loss` now
  cites what the re-solve moved rather than an Rwp pair.
- Merged `origin/main` (`5a06184af`).
- WP-2017 `### Inherited`: group Q's threshold now warns on every near start.

**The Le Bail warning, measured** (5.1-25°, `profile_only`, 8 passes, Rwp %
per pass, macOS arm64, `[dev]`, development data).

| cell start | before R7 | R7 |
|---|---|---|
| −1 % | 84.032, 84.032 (info, stuck) | 15.162, 13.943, 13.929, 13.928 (info) |
| −0.15 % | 19.417, 14.127, 13.950, 13.937, 13.937 (info) | 13.918, 13.927 (warning) |
| +0.2 % | 13.918, 13.935 (warning) | 13.918, 13.927 (warning) |
| +0.36 % | 13.919, 13.935 (warning) | 13.918, 13.927 (warning) |

The rule is unchanged, and R7 lands pass 1 at the state where the package
already warned. The kept answer is 0.019 Rwp points lower than the old fixed
point. The alternation's own fixed point (13.928 % from −1 %) sits above its
best single pass, which is group Q's threshold question in WP-2017.

**Measured.** RESULT_NUMBERS

**Generality** (the judge's verdicts, `generality-review`, on the branch at
`792d98170`; its full tables are in the PR body).
- `WINDOW_MOVE_FWHM`: weak. Claim and code differed on "a later stage
  refits" (answered: `refit_later`); no series measured (open, item 3).
- `StageResult.window_refit_loss`: holds; replace the Rwp evidence (done).
- `STAGE_WINDOWS_STALE`: weak; its firing case went silent (item 2 (i)).
- `WINDOW_MIN_DEG`: holds. `StageSpec:window_slack_deg`: weak on the
  condition (answered) and the approval date (moved).
- The family shapes and the uniform-slack exceptions: hold.

**Blind review** (a fresh subagent, given the evidence and not the picks):
the reader diff moves numbers only, and `window_refit_loss` is not junk; the
Le Bail warning is a correct reading; `refit_later` is right for every plan
shape traced. Its one gap, a closing-stage test, is added. It also noted that
an intermediate stage's report and node carry the narrower windows' esds,
which a branch from that node inherits.

**Next.** (1) The maintainer's three items. (2) The joint runner's re-solve
(`multi.py`'s stage loop is inline, so the stage body is factored first). (3)
The series measurement item 3 names, if the maintainer wants it before
approving 3 FWHM.

### 2026-11-28 — R7 implemented on `wp2317-window-slack`; suite fixes, handed off mid-handover (runner 2)

R7 is built and most of the fast suite's fallout is fixed. A stage that a
later stage refits now sizes each window's room for peak movement from the
position parameters it frees, and any stage of the single-pattern runners
solves once more on fresh windows when its frozen windows dropped more than
its tolerance at its answer. The re-solve also makes some fits more accurate.
A solo width stage that widens its peaks now reads the synthetic specimen's
400 Å as 400.35 and 401.91 Å, where it read about 409. The joint runner does
not re-solve yet and still reads 409.8. Not done: the second fast run, the
full suite, `tests.reader_output`, the generality judge and the PR. Two
stored-format and reader-output questions wait on the maintainer (below).

**Done (runner 1, commits `c1b8f48d1`..`50d0f0dd7`).** `forward.WINDOW_MOVE_FWHM`
= 3 FWHM per position family a stage frees (zero, displacement, transparency,
capillary offsets, cell or λ), shaped by each family's 2θ dependence, plus
half a point step, capped at the old 0.3°. The answer stage, a stage run on
its own, a joint fit, a shift equation and a declared `window_slack_deg` keep
0.3°. `StageResult.window_refit_loss` records the first solve's loss. Audit
rows, help, manual, practice.md, skill row, the guides re-pinned. Runner 1's
evidence: every refined value moved under 0.06 esd against the uniform slack,
background coefficients under 0.08 esd, Rwp to 1e-5 (macOS arm64, `[dev]`,
four acceptance families, all development data, and four Nb₁₈W₁₆O₉₃ bench
cases). Points per evaluation in declared stages: 0.20-0.22× on 11-BM NAC,
0.76-0.85× on SRM 660c, 0.98-0.996× elsewhere.

**Done (runner 2).**
- `NodeAction.movement_slack` (stored, default `False`) so `replay` compiles
  the windows the stage solved (`4b570f857`, recovered from runner 1's
  uncommitted tree). Documented in `reference/history.md`.
- Merged `origin/main` (WP-2315's merged groups); export guide re-pinned.
- Tests that pinned a pre-R7 path: the joint-size test's solo arms, the
  width-floor trap, the sulfate body's and the split pair's stage boundaries
  declare the uniform slack (claims about joint sharing, the clamp and site
  multiplicity, not windows). The tutorial-step test runs the tutorial's own
  plan. The extinction gate's out-of-basin cell starts 2 % off (R7 brings a
  1 % cell back). The Le Bail converging and cap tests start at −1 %.
- `/code-review high --fix`: a re-solved stage keeps its `fixed` paths, and
  the first solve's resets and collapses stay only for paths the answer cannot
  move (`7f1dc2c90`). Declined: the non-finite message after a non-finite
  re-solve (says nothing moved, while the first solve's values stand; a safe
  fix restores the free set and holds, not a local patch), and replay sizing
  families from the end-of-stage free set (exact only where the free set did
  not change at the answer).

**Measured** (macOS arm64, this worktree's `[dev]` venv, shared machine).
- Fast suite on the merged tree before the fixes: 12 failed, 15 888 passed,
  457 skipped, 30 xfailed. Each failure is listed above as fixed, except the
  Le Bail file, which was running when the session stopped.
- Replay with the stored flag: a `scale_bkg` node replays bit-exact
  (synthetic, FAP). Without it, replay's Rwp moves −2.0e-4 and −2.1e-3
  relative, and `test_history`'s exact-replay pin fails.
- Tutorial 05's 2 % jump: under the tutorial's plan (no closing stage) R7
  reaches it warm (Rwp 0.0395) where the uniform slack took `warm_staged`. With
  the closing stage declared, R7 takes `warm_staged` (0.0389) where the uniform
  slack stayed warm (0.0390).
- Le Bail, 5.1-25°: from −0.15 % to +0.6 % pass 1 now lands at Rwp 13.918 %
  and pass 2 at 13.927 %.

**In flight.**
- **A hang.** `pytest tests/test_lebail_alternation.py -n 4` ran 67 minutes
  with one worker at 100 % CPU, killed by the shift lead. That command omitted
  `-m "not slow"`, and the file's one slow row says its partitions took 1 604 s
  alone on an arm64 Mac, so the slow row is the likely cause. The file's fast
  rows then passed serially under a 470 s cap: 12 passed, 1 deselected, 8 s.
  Not yet known: whether the slow row
  (`test_the_state_the_loop_keeps_is_the_state_a_hand_loop_would_continue_from`)
  hangs under R7 or only takes its documented time. Run it alone through
  `serial.py` under a cap before the full suite.
- Not run: fast suite 2 with junit, full suite (`serial.py`), reader_output,
  generality judge (runner 1's verdict on the audit rows is not on disk), CI
  lint steps after the latest commits (ruff and Vale were clean at the merge).

**For the maintainer** (to go at the top of the PR body).
1. *Stored-format change.* `NodeAction.movement_slack: bool = False` is
   written to `history.jsonl` on every stage node. A new build reads an old
   node as `False`, which is what it ran. An older build refuses a new node
   (`extra="forbid"`), the shape WP-2315's `ReflectionState.merged_groups` had
   when it was ruled (a) on 2026-11-27. Options: (a) keep the field, so replay
   reproduces the stage exactly; (b) drop it, so replay compiles the uniform
   slack and differs by up to 2e-3 in Rwp, a staleness the history docs
   already allow, with the exact-replay test relaxed; (c) derive it, which the
   node cannot, since it does not know whether a later stage followed.
   Recommendation: (a), a clear call on the sibling ruling.
2. *Reader output, two cases.* (i) The cpd-1b hostile runaway (reached only
   under the pre-WP-2045 tolerance schedule) now re-solves, and
   `STAGE_WINDOWS_STALE` reads the second solve, so the warning no longer
   fires; the 73 % stays on `StageResult.window_refit_loss`. (ii) A fit with
   `lebail_passes` > 1 from a near start now ends with the
   `LEBAIL_ALTERNATION_STOPPED` *warning* ("stopped at the first pass that did
   not lower Rwp … Check the cell and the background") though pass 1 is the
   best pass, because pass 2 rises 6.5e-4 relative, past `LEBAIL_CONVERGED_REL`
   (1e-4). Before R7 the same start converged over five passes and said
   "fixed point" at info level.

**Gotchas.** The worktree harness refuses `git -C` into another tree: take
over a dormant tree by copying its files, restoring it with `git show`, and
`git worktree remove`. `rietx.refine` the attribute is a function, so a probe
imports the module with `importlib.import_module`.

**Next.** (1) Time the Le Bail slow row alone, capped. (2) Fast suite with junit, then the full suite through
`serial.py`. (3) `tests.reader_output`; dispatch the generality judge on the
audit rows. (4) Open the PR as a draft with the two maintainer items at the
top, name it here, push, mark it ready. (5) Follow-up, unowned: the joint
runner's re-solve (`multi.py`'s stage loop is inline, so it needs the stage
body factored first).

### 2026-11-27 (5th session) — the rulings recorded, accuracy set by what users need, and the stopping rule re-settled

The maintainer answered the rulings that held up the large-cell track, except R4.
The one with the widest reach is the accuracy level. rietx aims for accuracy
sufficient for users rather than spending compute past it, the established
programs being the evidence of what suffices. Claude settles each speed-accuracy
trade under that intent. A Claude draft of the rule had put the level at a tenth
of an esd. That was never ruled, and it would have reversed the 2026-11-19 window
ruling, so it is withdrawn. Measured: the last stage's 1e-9 stop costs little on
one fit but most of a series. The field's published-fit test, every shift under
0.1 esd, cuts a 17-pattern ramp from 1 293 evaluations to 363, and its worst
quantity, a 1 wt% phase's cell, lands about one esd off. The programs' own default
stops, run inside rietx, left a series pattern 18 esd off while reporting
convergence. The large cell's apparent second minimum was a fixture defect, fixed
separately (PR #1870).

**Done.**
- Rulings R0 (and R0 clarified), R2-R3, R5 (b) and (c), R6 and R7 recorded in
  Context with the maintainer's words. Rule 5 *Arithmetic accuracy* rewritten to
  the clarified R0, reviewed blind three times for the earlier drafts and once for
  this one (wording adopted from the last review). Rule 5 also gained the *Intent*
  test. The 2026-11-01 validation amendment moved to DESIGN.md for room.
- `docs/practice.md`: the seven-program survey behind R4, R5 (c), R6 and R7.
- R6 measured (`2317-probe/convnoise/`), then re-settled twice the same day: to
  1e-8 on the clarified level, then to the 0.1-esd shift test on parity. The
  table is in R6's entry. A new task carries the implementation.
- `2317-probe/errmeasure/`: how a speed setting's error is measured (mean shift
  over paired nudged starts), and the co-sited tie defect it found.
- R0's note in 2314's and 2316's `### Inherited` updated to the clarified level.

**Measured** (macOS arm64, rietx's `.venv` on this worktree, shared machine).
- Single fits: every stop tried holds every family under 0.06 esd of the 1e-9
  answer; the last stage is 9-29 of 40-165 evaluations.
- Series, evaluations and worst departure from 1e-9 (esd): CuCr₂O₄ ramp 1e-8 1 089
  / 0.006, 1e-7 917 / 0.022, shift/esd 0.1 363 / 1.2, FullProf 0.2 300 / 1.7,
  GSAS-II 1e-3 183 / 1.8; cpd-1 chain 1e-7 442 / 0.22, shift/esd 0.1 322 / 0.071,
  FullProf 0.2 and GSAS-II 18 (cpd-1f, `axial_sl`). The 1e-7 rerun reproduced the
  earlier 1e-9, 1e-8 and 1e-6 counts exactly.
- No test count moved: the branch adds no test. The fast suite was not run (prose
  and probe scripts only).

**In flight.**
- Landed the same session: GSAS-II's and FullProf's default stops measured in
  their own programs (`2317-probe/foreign_stops/`, R6's entry). GSAS-II's 1e-3
  stops short at home too (14-16 esd on cpd-1f); FullProf's 0.2 does not (0.08).
- Stopped runners, not restarted: WP-2316's Le Bail fix on `wp2316-lebail-practice`
  (4 pushed commits, untracked probes and a design patch in its worktree), and
  R7's window slack on `wp2317-window-slack` (state not checked).
- PR #1869 (WP-2315's lattice merge): its stored field
  `ReflectionState.merged_groups` was ruled (a), kept as is, and the PR merged
  the same day.

**Gotchas.**
- A ruling that picks a unit (the esd) sets no level. Read the maintainer's
  intent, and never invent a tighter bar.
- A program's stop threshold is not its users' accuracy. The probe tested shifts
  on the damped LM step, which a crawl keeps short; the implementation tests the
  undamped Gauss-Newton step.

**Next.** (1) Done the same session: the GSAS-II/FullProf result is in R6, and the
rule's sentence stands. (2) Get R4 ruled by the
maintainer. (3) Implement R6 (its task), re-pinning goldens. (4) Task 1, the
user's case, still decides the re-rating of 2314-2316.

### 2026-11-27 (4th session) — the bench and the suite carry real large cells

The maintainer asked for real large cells in the testing, not the invented
one. Two published structures from the Crystallography Open Database are now
vendored, and the four `bigcell-*` bench cases fit patterns simulated from
Nb₁₈W₁₆O₉₃. A new test module puts both structures through Rietveld and
Pawley fits. PR #1866.

**Done.**
- `tests/data/cod_2107344.cif` (Nb₁₈W₁₆O₉₃, Pbam, 1 770 Å³, 43 sites) and
  `tests/data/cod_2107337.cif` (H-Nb₂O₅, P2/m, 1 358 Å³, 51 sites), whole
  as fetched, with a provenance row each in `tests/data/README.md`. Both were
  checked on the vendored file before use: cell content against the formula,
  each metal's nearest oxygens 1.64-2.48 Å, no two images under 1.6 Å apart
  except a mixed site's two species.
- `examples/bench_refinement.py`: the four `bigcell-*` cases keep their keys,
  modes, ranges, instrument, seed and start protocol, on Nb₁₈W₁₆O₉₃. `Setup`
  gained `prepare`, a hook called on each repeat's `Refinement` before the
  timed fit. `bigcell-structural` uses it to tie the co-sited pairs.
- `tests/test_large_cell_refinement.py` (six tests). It reads both files
  whole, then runs a structural fit from displaced coordinates and a Pawley
  fit from a cell 500 ppm high on each. The patterns are simulated, so these
  verify. Measured walls (darwin/arm64, `[dev]`): 0.02-0.03 s for the reads,
  1.6 s and 2.6 s for Pawley, 4.3 s for the Nb₁₈W₁₆O₉₃ structural fit, and
  6.0 s for H-Nb₂O₅'s, which is marked `slow`.
- `tests/test_bench_refinement.py`'s large-cell test now pins the COD
  structure and the 22 ties.
- Inherited entries in 2314, 2315 and 2316 say their quoted figures are
  probe 1's.

**Measured.** The bench table is in Context, § The bench cases on a real
structure. Fast suite on this tree: 15 828 passed, 452 skipped, 30
xfailed (`[dev]`, darwin/arm64, 7 min 52 s). The branch adds five fast tests
and one slow one. `tests.reader_output` exits 0, unchanged against the
merge-base. Ruff is clean. Not run: the full suite (no number in `src/`
moves), and the generality judge (no `_audit.py` change).

**Gotchas.**
- At ten times the counts (strongest peak ~10⁶), a structural fit started
  from the truth lands at GoF 1.30, not 1. The simulator's peak windows and
  the fit's are cut at different places, and the cut tail is then above the
  noise. The tests keep a lab pattern's counts.
- H-Nb₂O₅'s oxygen positions are weakly determined below 2θ = 70°: at 50°
  the fit's RMS position error (0.081 Å) exceeded the start's (0.071 Å).
  The test runs to 70° at three times the counts.
- `2317-probe/export_bigcell.py` refuses the new phase. The GSAS-II driver
  writes P2₁2₁2₁ at full occupancy, so the cross-code rows stay probe 1's.

**Settled by Claude.**
1. All four bench cases moved to Nb₁₈W₁₆O₉₃, keeping their keys. Settled
   under the brief's "keep the cases' names if the shape is unchanged": modes,
   ranges and reflection counts are within 3 % of probe 1's. The alternative
   was new keys beside the old cases.
2. `bigcell-structural` ties each co-sited Nb/W pair (steps and Biso).
   Settled under established practice (recall, not a survey): a refiner
   constrains two species on one site to one position and one displacement,
   since their columns differ only by the ratio of form factors. The alternative
   was H-Nb₂O₅, which has no mixed sites, for the structural case.
3. The second structure, H-Nb₂O₅, lives in the tests only. Settled under the
   brief ("more than one crystal system if cheap"): a fifth bench case would
   add minutes to every bench run. The alternative was a monoclinic bench case.
4. Biso 0.5 Å² for metals and 1.0 Å² for oxygen. Settled as a declared
   value, since the files carry Uiso = 0 and a pattern needs one. The
   alternative was one value for every site.

**Next.** Unchanged from the 3rd session's entry. A GSAS-II row on the new
cases needs the driver to read the space group and occupancies.

### 2026-11-27 (3rd session) — four large-cell bench cases, and GSAS-II timed on the same pattern

The bench now carries the large cell this track is about, so 2314-2316 each
have a case to measure their own before and after on. GSAS-II was run on the
same pattern under the same free sets. On its default settings it takes
1.6-3.0× rietx's wall clock in structural and Pawley fits. The
Le Bail fits ran from probe 1's unseeded background: GSAS-II took 0.9-1.5× rietx's wall,
and it landed nearer the right answer. PR #1864.

**Done.**
- `examples/bench_refinement.py`: `bigcell-structural`, `bigcell-pawley`,
  `bigcell-pawley-120` and `bigcell-lebail`, built from probe 1's generator and
  reproducing its pattern bit for bit. `bigcell-lebail` seeds its background with
  `auto_background(kind="chebyshev", seed=True)`, as WP-2316's Inherited entry
  asked. `tests/test_bench_refinement.py` pins the cell's shape (one test).
- `docs/wp/2317-probe/gsas2_bigcell.py` (the GSAS-II 5.8.4 driver) and
  `export_bigcell.py` (its xye and start-model writer). Their docstrings give the
  protocol and how to run them.
- Inherited entries pushed into 2314, 2315 and 2316 with each one's case and the
  GSAS-II numbers.

**Measured.** Both tables are in Context: the bench ranges, and § Cross-code
timing beside GSAS-II. Fast suite on this tree: 15 820 passed, 452 skipped,
30 xfailed (`[dev]`, darwin/arm64). The one added test takes 0.09 s.
`tests.reader_output` exits 0, unchanged against the merge-base.

**Gotchas.**
- The harness's nfev and njev columns print 0 under the default LM driver, since
  `_counting` wraps only scipy's `least_squares`. Read per-stage counts off
  `StageResult`. Not fixed here: the column's meaning is the docstring's rule 6.
- Machine load moved wall clock by up to 1.5× between blocks, so every range in
  the cross-code table spans all blocks.
- GSAS-II draws no peak below its lower 2θ limit. The tail of (0 2 0) at 4.9°
  stays unfitted and its intensity is dropped as singular, which puts 41-43 % of
  its Pawley χ² below 6°. Its default Pawley tie also merges reflections whose d
  agree within 1e-4, giving 352 intensities at 90° (540 at 120°) where rietx
  carries 913 (1 606), because b = 3a exactly.
- `bigcell-lebail`'s seed carries 16 Chebyshev terms, the order scan's cap, where
  the other cases carry 6. Its seeded and unseeded rows differ in both.
- GSAS-II was not run from the seeded background. Its `chebyschev-1` is rietx's
  shifted Chebyshev, so the exported seed carries over term for term.

**Settled by Claude.**
1. The Le Bail seed is `kind="chebyshev"`, not the P-spline default. Settled by
   Claude under convention (the other three cases' family) and WP-2316's
   measurement of it at Rwp 0.047. The alternative was the default P-spline.
2. The seed keeps the 16 terms `auto_background` returns. Settled by Claude
   under WP-2316's Inherited entry, which names `auto_background(seed=True)` as
   the seed. The alternative was holding 6 terms and seeding c0 alone.
3. The 120° Pawley fit is a separate key, `bigcell-pawley-120`. Settled by Claude
   under the Acceptance command, which names `bigcell-pawley` alone. The
   alternative was one key fitting both ranges.
4. The bench runs every case by default, the large cells adding 7-9 minutes.
   Settled by Claude under the file's existing convention of documenting runtime
   instead of gating cases. The alternative was an opt-in flag.
5. GSAS-II ran on its own defaults: Pawley dmax, the stopping rule (min dM/M
   0.001, 100 cycles), single process, the GUI's Le Bail reset path; its scale
   was seeded outside the timed region. Settled by Claude under CLAUDE.md
   § Conventions ("adopting its protocol"). The alternative was tightening
   GSAS-II to rietx's tolerances.
6. The Pawley and Le Bail cases use 10 atoms, as probe 1's readings did. Settled
   by Claude under probe 1. The intensities are free in both modes, so the atom
   count sets only the start pattern.

**Next.** Task 1 (the user's case) and task 3 (R0-R7 as one batch) wait on the
maintainer. Task 7 (jax) is open. A seeded GSAS-II Le Bail row needs one more
run of the driver (its unseeded run took 79-87 s).

### 2026-11-27 (2nd session) — renumbered from 2313 to 2317

This WP was filed as WP-2313. While its PR (#1860) was open, main took WP-2313
for another WP ("the bench reads what the GUI build runs"). A number is never
recycled, so this one became WP-2317, the next free number, when main was merged
in. The commits before that merge carry the `WP-2313:` prefix; they are this
WP's. Every cross-reference was rewritten: 2314-2316, the ROADMAP track, and the
`### Inherited` notes in WP-1945, WP-2017 and WP-2062. The probe directory is
now `2317-probe/`. 2314-2316 were free on main and keep their numbers.

CI's lint job then failed `tests.rulebook_limits`: ROADMAP is closed to growth,
and the track paragraph added 743 B. The track is now one line, because its
evidence already lives in this file. The Unscheduled intro's provenance sentence
was cut to pay for the remaining bytes (which triage the 13xx, 1119/1130/1133
and 1414-1420 rows came from). Each of those WP files carries its own issues.

Next: unchanged from the entry below.

### 2026-11-27 — filed the track: three slow paths measured, the rulings in their way listed, the plans reviewed

A large cell is slow in rietx for three separate reasons, and none of them is the
forward model. On a synthetic 12 × 36 × 4 Å stand-in a profile-only Rietveld fit
takes 2.8 s. A 40-atom structural fit takes 75 s, because every coordinate column
rebuilds the whole structure factor. A Pawley fit at 1 601 reflections takes
125 s, most of it in a dense constrained step over every intensity. A Le Bail fit
takes 155-352 s in its partition loop, and lands at three times Pawley's Rwp on
the same pattern. The track now has a written bar, the maintainer's "on par with
other codes, speed by any means". It has the earlier choices that cost speed on a
large cell (R0-R8), each with its original reasoning and what the other programs
do. And it has three fix plans whose premises a fresh reviewer checked against
the code. Nothing in `src/` changed.

- *Fold-first:* no open WP owns any of the three costs. WP-1945 owns the
  peak-chain columns and one bit-identical Biso task (split recorded in 2314).
  WP-2062 owns which structure-free method is the default, not either method's
  speed. WP-2017 group Q owns `lebail_tol`'s number, not the partition's cost.
  WP-1335 owns the report, which costs 5.6 s here. WP-2051 is filed, and
  WP-1323 is closed.
- *Done:*
  - this WP (scoping) and WP-2314/2315/2316 (plans), and the ROADMAP track
    "A large cell";
  - probe 1 (`2317-probe/probe1_bigcell.py`);
  - task 4 answered.
- *Measured:* Linux x86_64, 4 cores, Python 3.12.3, numpy 2.5.5, `[dev]` venv,
  compiled tier on, rietx 1.13.0.dev0 at `4e099d68`, one run per case. The
  table is in Context.
  - The first probe drew atoms in a sub-box. Unprofiled walls for 10 atoms were
    Rietveld 2.6 / 3.7 s, Pawley 20.7 / 82.7 s and Le Bail 144.6 / 351.3 s
    (899 / 1 601 reflections); the 40-atom structural fit was 251.1 s.
  - The physical model's readings are the Context table.
  - Profiled splits come from one profiled run per case.
- *Review* (a fresh general-purpose subagent, read-only, 2026-11-27): 2 blockers
  and 18 should-fix findings, all taken. Among them:
  - `reduceat` is pairwise, not sequential, so WP-2316's "bit-identical kernel"
    was false;
  - the bar paragraph contradicted Rule 2, which became R0;
  - R1 and R6 were mis-stated (no bit-identity ruling exists; the closing stage
    has been off since WP-2222);
  - the probe's atoms overlapped (fixed, all cases re-measured);
  - the call arithmetic in 2314 was off (120×, not 60×);
  - the Ω·∂I block and cross-atom reach were missing from 2314;
  - ILU reuse already exists (2315);
  - the bench case is one overlap component (2316 angle dropped);
  - jax is oversold;
  - WP-2017 and WP-1945 overlaps;
  - priorities were provisional;
  - the measurement protocol (interleaved, same session, min-max).

  None was declined.
- *Code review* (`/code-review high --fix`, handover step 6): 10 findings, 9
  fixed. Among the fixes:
  - the probe's docstring still described the sub-box draw;
  - 2314's remainder after the hoist was quoted from the first probe;
  - R3 named the wrong sentence of Rule 5;
  - R1's quote is WP-1109's;
  - jax's window count on one 0.459 Å line;
  - 2315's ILU counts are now the physical model's;
  - the Le Bail share is now 95-97 %, from the first probe's profile.

  Declined: re-quoting the single-run walls as ranges, which is task 2's job,
  since it needs repeated interleaved runs. The probe's import order was fixed
  by ruff (the lint scope does not cover `docs/`).
- *Not run:*
  - the fast and full suites, since the branch adds no test and changes no code
    in `src/`, `tests/` or `examples/`;
  - the generality judge: no `_audit.py` change, and no heuristic in code;
  - the `tests.reader_output` check, which runs at step 11.
- *Gotchas:*
  - Probe walls are single runs on one machine, so no figure here is a "before"
    for another WP (task 2).
  - The probe's crossing of Pawley width rows may come from its U = V = Y = 0
    truth; WP-2315 task 1 checks real data.
- *Next:*
  1. Ask the user for their case (task 1). It decides which of 2314-2316 is the
     user's path and re-rates all three.
  2. Put R0-R7 to the maintainer as one batch (task 3). R0 and R3 gate the most:
     R0 decides whether rounding-only moves may re-pin goldens; R3 decides
     whether WP-2316 starts at all or the answer is "route to Pawley".
  3. Add the bench cases (task 2).
  4. In parallel with 2-3: WP-2314's hoist and WP-2315's angle 0-1 need no ruling
     and can start now.
