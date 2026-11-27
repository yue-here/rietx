# WP-2317 — a large cell fits as fast as its reflections allow: the case, the bar, and the rulings in the way

Milestone: unscheduled · Status: 🔄 2026-11-27 — claimed by ghostshift (runner, MacBook-Air-c4aacd): task 2 bench cases and the GSAS-II timing; task 4 answered, tasks 1, 3, 5-8 open
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
shared the machine; the run held the suite lock. These are the "before" for
2314-2316, and a speed WP re-measures them beside its own arm.

| case | wall (min-max of 3) | Rwp | per-stage nfev |
|---|---|---|---|
| `bigcell-structural` (40 atoms) | 11.24-11.30 s | 0.08675 | coordinates 10, biso 16; 100 over 11 stages |
| `bigcell-pawley` (2θ ≤ 90°) | 12.10-12.69 s | 0.04466 | 68 over 5 stages; profile 29 |
| `bigcell-pawley-120` (2θ ≤ 120°) | 63.13-64.88 s | 0.04199 | 77 over 5 stages; profile 37 |
| `bigcell-lebail` (2θ ≤ 90°) | 80.38-83.92 s | 0.15121 | 96 over 5 stages; cell 41 |

The Linux single runs above and these Mac ranges are on two machines, so their
ratios are not speed-ups. The harness's own `nfev` and `njev` columns print 0
and `-` here: `_counting` wraps scipy's `least_squares`, and the default LM
driver does not call it. The per-stage counts come from `StageResult`.

Three readings shape the track.

- **Le Bail is 3-7× slower than Pawley here (6.5× at 899 reflections, 2.8× at 1 601)**, against the practice survey's
  expectation (RIETAN-FP: Le Bail "needs no large normal matrix"). This is
  consistent with R2 below.
- **Le Bail also lands at three times Pawley's Rwp on the same pattern** (0.151
  against 0.045). That is a correctness question before it is a speed one: a
  wrong valley, the background protocol (WP-1542's subject), or the partition.
  WP-2316 task 1 answers it before any speed work.
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
- **R6 — the stopping rule.**
  - *rietx:* intermediate stages at 1e-6 (`intermediate_ftol`, WP-1123), the last
    declared stage at the solver's 1e-9. The closing stage is **off by default
    since WP-2222** (`closing_window_tol = None` on both `mccusker_*` presets).
  - *Practice* (`docs/practice.md` § When a fit stops): GSAS-II stops at 1e-3
    relative change and 3 cycles a `Refine` call; FullProf stops when every shift
    is under `Eps` × its esd (0.2 "or lower").
  - *The question:* is 1e-9 on the last stage more than "on par" buys? It is a
    kind (b) move under R0.
- **R7 — `WINDOW_MIN_DEG` = 0.3° of movement slack per window side**
  (`src/rietx/model/forward.py:234`).
  - About 30 of the probe's ~122 points a window (~25 %) are slack at a 0.02°
    step, and the share grows as 1/step on synchrotron data.
  - The slack could be sized from the stage's own moving position parameters
    instead. This is a kind (b) move, and it is not WP-2051's per-evaluation
    windows.
- **R8 — the bench measures the shapes it was built on.** No
  `bench_refinement.py` case has more than ~1 200 (line, reflection) pairs or
  ~15 atoms in a phase. So v1.1's ranking under-weights every term that grows with
  the atom count or the reflection count, which WP-1111 said of its own
  baselines.

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
- [ ] Put R0-R7 to the maintainer as one batch, each with the cost above and what
      practice does. Record each answer here as a dated ruling, and push each into
      the `### Inherited` of the WP it unblocks: 2314-2316, and WP-2017 for R2's
      number.
- [x] Why the 40-atom `coordinates` stage took 119 LM iterations from the true
      coordinates. *Answered 2026-11-27 by the review: the first probe drew its
      atoms inside a 1/15.6 sub-box, 65 % of nearest neighbours under 1 Å. On
      atoms ≥ 1.5 Å apart the stage takes 10.*
- [ ] Watch the iteration counts on the user's case once task 1 has it. A
      structural stage started at the answer should stop in a few iterations,
      and one that does not says something about the model, not the code.
- [ ] Cross-code timing: GSAS-II (whose source rietx may read; installability to
      be checked) on probe 1's pattern under the same free set (structural, Pawley,
      Le Bail), with its own wall and Rwp beside rietx's. It supplies R0 (b)'s
      "on par" comparison, and it is the reference for "as fast as possible".
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
