# WP-2313 — a large cell fits as fast as its reflections allow: the case, the bar, and the rulings in the way

Milestone: unscheduled · Status: ⬜
Track: A large cell
Depends on: —
Priority: P2 2026-11-27 — the scoping WP of a track with a user at the wall (slowdowns reported on a 12 × 36 × 4 Å cell); 2314, 2315 and 2316 read its case and its rulings

A large cell has a named benchmark case in `examples/bench_refinement.py`, and
the cases its three slow paths need (many atoms, a Pawley block past 128 columns,
a Le Bail partition over ~1 000 reflections). Each earlier ruling that trades
speed for accuracy beyond what the established programs deliver has been put to
the maintainer and answered. The maintainer's bar for this track is written down
where every successor reads it. A cross-code timing on the same pattern says how
far rietx is from the established programs.

## Context

**Who is at the wall.** A rietx user reported slowdowns on a 12 × 36 × 4 Å cell
(V ≈ 1 730 Å³). We don't know their mode, plan, atom count, data or radiation.
Getting that case, or a stand-in the user agrees resembles it, is task 1. The
probe below is synthetic.

**The bar, ruled 2026-11-27 by the maintainer for this track:** "accuracy on par
with other codes is sufficient. speed as fast as possible by any means
necessary." Read against DESIGN-RULES:

- Rule 5's *Arithmetic accuracy* direction already says a speed-for-accuracy
  setting "matches the accuracy the established programs deliver". The new part
  is **"by any means"**. On this track, **bit-identity is not the bar**. Every
  speed WP since WP-1109 held itself to it, and WP-1945 still does ("every
  column stays bit-identical"). Here the bar is the reference value's distance:
  a change may move a pinned number when the new value is no further from its
  reference than the established programs' answers are. Rule 2's
  "moved for the right reason" test still applies, and a golden that moves says
  so in its WP.
- It does **not** lift Rule 1, Rule 2's verification gate or the fp64 invariant.
  A faster path still ships verified: an analytic column against an exact oracle,
  two paths agreeing on one residual, and the agreement matrix extended.
- Where this bar conflicts with a ruling below, the ruling is put to the
  maintainer (task 3). It is never overridden in a WP.

**Probe 1, the synthetic case** ([`2313-probe/probe1_bigcell.py`](2313-probe/probe1_bigcell.py)):
12 × 36 × 4 Å, P2₁2₁2₁, invented general-position atoms, Cu Kα doublet with FCJ,
simulated Poisson data, a cold start 500 ppm high on the cell. Linux x86_64,
4 cores, `[dev]`, compiled tier on, rietx 1.13.0.dev0 at `4e099d68`, one run
each, under cProfile (the profiler inflates Python-heavy paths; the unprofiled
walls are task 2's first reading).

Reflection counts for this cell (unique, absence-allowed, `generate_reflections`):

| radiation, range | P2₁2₁2₁ | Pmmm | Cmcm |
|---|---|---|---|
| Cu Kα1, 2θ ≤ 90° | 899 | 924 | 451 |
| Cu Kα1, 2θ ≤ 120° | 1 601 | 1 630 | 802 |
| Cu Kα1, 2θ ≤ 150° | 2 143 | 2 177 | 1 071 |
| 0.459 Å, 2θ ≤ 50° | 6 477 | 6 525 | 3 227 |

The v1.1 "trigger" case, the largest the bench carries, had 1 188
(line, reflection) pairs over four phases. The 0.459 Å row alone is ×5.

| case | wall (profiled) | the leading cost |
|---|---|---|
| Rietveld, `mccusker_default`, 10 atoms, 899 refl | 3.4 s | spread evenly; nothing to fix |
| Rietveld, `mccusker_default`, 10 atoms, 1 601 refl | 5.0 s | the same |
| Rietveld, `mccusker_structural`, **40 atoms**, 899 refl | **268.7 s** | 207 s (77 %) in `_structural_column` → `d_f2_d_xyz` → `_orbit_terms`, called 964 760 times for 20 880 columns (**WP-2314**) |
| Pawley, 899 intensity columns | 23.6 s | 10.3 s in `lm._solve_constrained_step`, a dense `eigh` and `nnls` over every column (**WP-2315**) |
| Pawley, 1 601 columns | 89.5 s | 53.5 s in the same step; 10.6 s in 1 099 `spilu` factorisations (**WP-2315**) |
| Le Bail, 899 refl | **150.0 s** | 144 s (96 %) in `_settled_partition`, ~7 900 partition cycles per update (**WP-2316**) |
| Le Bail, 1 601 refl | **364.2 s** | 354 s (97 %), ~9 100 cycles per update (**WP-2316**) |
| `report()` after the 40-atom fit | 5.6 s | not a cost here (WP-1335 owns the report path) |

So on this cell Le Bail is the slowest structure-free route, and Pawley is
4-6× faster. That is the reverse of the practice survey's expectation: RIETAN-FP's
manual says Le Bail "needs no large normal matrix", and Le Bail (2005, §VI)
quotes Kariuki et al. (1999) on Le Bail being faster than Pawley. The reason is
ruling R2 below.

**The rulings in the way.** Each is an earlier choice that costs speed on a large
cell, taken under a bar stricter than "on par with other codes". For each:
where it was ruled, what the established programs do, and what it costs here.
None is changed by this file; task 3 puts each to the maintainer.

- **R1 — bit-identity as the bar for a speed change** (the v1.1 speed WPs
  1109-1121, WP-1945, `compiled.py` rule 3's "associations as written").
  Practice: no surveyed program states a bit-identity bar. Cost: every
  reassociation is forbidden, among them `np.bincount` for `np.add.at`, a BLAS
  contraction for a Python loop, a vectorised atom loop and a fused kernel. The
  bar above replaces it for this track, and a successor should confirm that
  reading before relying on it.
- **R2 — a Le Bail partition settles to 1e-7 of the Bragg counts with the model
  frozen** (WP-1542, B11 of WP-2002's rulings; `lebail_tol` = 1e-7 settled by
  Claude under the maintainer's delegation of 2026-11-05; cap 25 000). Its yardstick is
  `tests/test_window_domain.py` bar 1, max|Δy|/σ ≤ 0.1 against a 1e-10
  reference. That is a rietx-internal bar, not a comparison with another code.
  Practice (`docs/practice.md` § Structure-free fitting): GSAS-II, FullProf,
  TOPAS and RIETAN-FP extract **once per least-squares cycle** and let the
  partition converge across the refinement, and GSAS-II's whole refinement stops
  at a 1e-3 relative χ² change. Cost: 96-97 % of a Le Bail fit here, and
  WP-1542 itself named LaMnO₃'s 12 293 cycles as a 150× cost. WP-2316 owns it.
- **R3 — a Le Bail change that moves every fit's numbers waits for WP-2062**
  (DESIGN-RULES Rule 5, *Structure-free fitting*, ruled 2026-11-05, #1434).
  Under R1's bar any faster partition moves every Le Bail fit's last bits, so as
  written, R3 holds WP-2316's every non-identical angle behind a WP that is not
  started. The question for the maintainer is whether "moves every fit's numbers"
  meant a change of *method* (as it reads in context) or any change of the
  arithmetic.
- **R4 — the width floor is held inside the step, in every mode** (WP-1938 D8,
  WP-2153; Coelho 2005 on bounds inside the solve). Practice
  (`docs/practice.md` § Peak-width limits): GSAS-II floors the Gaussian variance
  per reflection **by value**, FullProf sets Γ_G = 1e-10, and neither
  constrains the step. WP-1938's fifth session left the dense constrained step
  past `BVLS_MAX_COLUMNS` alone because "neither reaches a fit". This cell
  reaches it 18-24 times a fit. WP-2315 owns it.
- **R5 — every Pawley intensity is a full column of θ** (WP-0306; WP-1125's
  invariant: profiling a linear block out "cannot buy an evaluation", but Pawley
  *dimension* is "a per-step cost"). On a large cell, the dimension is the cost.
  WP-2315 weighs it, with the invariant's own caveat that a bounded block leaves
  the VarPro identity once a bound is active.
- **R6 — the last stage converges at `ftol` 1e-9, intermediate stages at 1e-6,
  and a closing stage is appended** (WP-1123, WP-2045, WP-2002). Practice
  (`docs/practice.md` § When a fit stops): GSAS-II stops at 1e-3 relative change
  and 3 cycles per `Refine` call. FullProf stops when every shift is under
  `Eps` × its esd (0.2 "or lower" advised). The 40-atom fit's `coordinates`
  stage ran **119 iterations from the true coordinates**. That count is itself a
  finding (task 4) whatever the tolerance.
- **R7 — the bench measures the shapes it was built on.** No `bench_refinement.py`
  case has more than ~1 200 (line, reflection) pairs or more than ~15 atoms in
  a phase, so v1.1's ranking under-weights the terms that grow with the atom
  count and the reflection count (WP-1111 said this of its own baselines).

**Angles beyond the three WPs** (kept open, not yet measured):

- `backend="jax"`: one jitted `jacfwd` over the whole residual. Its cost grows
  with the parameter count and amortises the structure-factor expansion. This
  is the cheapest "by any means" test of whether the numpy analytic chain is the
  right architecture for a large cell at all. Measure it on the case first.
- Threads: the compiled tier's pool covers the plane kernels only. The
  structure factor, the partition and the step solve run single-threaded Python
  or LAPACK.
- Iterations, not only cost per iteration: R6 and task 4.
- A cross-code reference (task 5). GSAS-II is the one we can run (its licence
  permits reading the source; it's pip-installable under some name, unverified),
  and it is the program whose speed a user compares against.

## Non-goals

- The fixes themselves: WP-2314 (structural columns), WP-2315 (Pawley step),
  WP-2316 (Le Bail partition).
- The report path (WP-1335), the peak-chain columns (WP-1945), per-evaluation
  windows (WP-2051, filed).
- Which structure-free method is the default: WP-2062. This WP asks only about
  R3's reach.

## Tasks

- [ ] Ask for the user's case: mode, plan, free parameters, atoms in the
      asymmetric unit, space group, radiation and range, point count. Record it,
      or the stand-in the user accepts, as this track's acceptance case.
- [ ] Add `bigcell-structural` (40 atoms, `mccusker_structural`), `bigcell-pawley`
      (899 and 1 601 columns) and `bigcell-lebail` cases to
      `examples/bench_refinement.py`, built like `_trigger` (simulated, the
      truth's atoms invented, dispersion declared). Take the unprofiled readings,
      best of three, interleaved (the harness's rules 1-2). The probe-1 table
      above is the profiled "before".
- [ ] Put R1-R6 to the maintainer as one batch, each with the cost above and what
      practice does. Record each answer here as a ruling with its date, and push
      each into the `### Inherited` of the WP it unblocks.
- [ ] Why the 40-atom `coordinates` stage takes 119 LM iterations from the true
      coordinates. Check whether the invented atoms sit on top of each other (a
      degenerate model) or the stage is slow to converge on a sound one. Rerun
      with atoms ≥ 1.5 Å apart before reading anything into it.
- [ ] Cross-code timing: GSAS-II on probe 1's pattern under the same free set
      (structural, Pawley, Le Bail), with its own wall and Rwp beside rietx's.
      This becomes the reference for "as fast as possible".
- [ ] `backend="jax"` on the three bench cases: wall, compile time, Rwp.
- [ ] Skill: none until a fix lands; the interim advice (Pawley over Le Bail on a
      large cell, restraints and Biso ties to cut the free coordinates) is a
      measurement on rietx's own runs, so Rule 3 keeps it out of the skill.

## Acceptance

The three bench cases exist and print. Every ruling R1-R6 carries the maintainer's
answer with a date. The user's case, or the accepted stand-in, is recorded.

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

- **2026-11-27** — created.
