# WP-2051 — Windows resized at every evaluation, fast enough to measure

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: 2047 (`forward.rewindow`, `fcj.fcj_node_counts` and probes 7 and 8 land with it)
Priority: P2 2026-10-25 — the decision the maintainer asked to test soon: whether rietx adopts per-evaluation windows

## Goal

A version of windows that follow the parameters at every evaluation that is
fast enough to judge on cost: the resizing profiled, vectorised in numpy, and
compiled only where numpy cannot reach, with a window edge that tapers so the
cost no longer steps when an edge crosses a point. Probes 7 and 8 re-run
against the shipped tree give the maintainer the table to choose from: adopt
as the default, offer as an opt-in, or file.

## Context

**Where this comes from.** WP-2047 measured a prototype (its Context, "The
prototype, measured"; probes in [`2047-batch/`](2047-batch/README.md), probe 7
written by a lane and its hostile result re-run by the session). Every
stage today sizes its peak windows and FCJ node counts once, at its start
(root CLAUDE.md § Invariants, the first). The prototype resized them before
every residual and Jacobian evaluation by wrapping the solver's two closures
(`optimize/least_squares._make_residual`, `_make_jacobian`) with
`forward.rewindow`'s rule. Measured on macOS arm64, `[dev]`, compiled tier on:

| | NAC | LaB6 | Fluorapatite | cpd-1a |
|---|---|---|---|---|
| Fit time ratio (median of 5, interleaved) | 1.24 | 1.63 | 1.66 | 2.08 |
| Resizing seconds a fit (Python) | 0.12 | 0.21 | 0.35 | 1.25 |
| Evaluations, shipped → per evaluation | 46 → 49 | 90 → 110 | 49 → 83 | 175 → 216 |
| Ratio left if resizing were free (inferred from the split) | ~1.0 | ~1.2 | ~1.4 | ~1.35 |

It removed the one known runaway (the QPA chain cpd-1a → cpd-1b under the
pre-WP-2045 schedule: cpd-1b Rwp 0.13944 at `axial_sl` 0.00758 in 41
evaluations, against 557.8 shipped). Accuracy on the four protocols was a
wash: fluorapatite and NAC polish to one point; cpd-1a reaches a second
minimum 0.95 esd away on `profile.v` with χ² 0.1 % lower; LaB6's polished
points sit 5 esd apart on `profile.u`, inside its known Γ_G² floor defect.
Every stage still converged at `ftol` 1e-9.

**Why the evaluations rise, and the taper.** Near an answer a window edge
crossing a data point steps the cost by 1e-10 to 1.6e-5 of itself (probe 7's
`step` mode), 10² to 10⁴ times what `ftol` 1e-9 resolves, so LM rejects more
trials late in each stage. A faster resizing cannot remove that part. A
profile that goes to zero continuously at its window edge (the tail value at
the edge subtracted, or a smooth taper over the outer points) makes the
residual continuous in θ, and should recover most of those evaluations. GSAS-II
avoids most of the step by width instead: its windows run 50 FWHM below a
peak and 75 above (`GSASIIstrMath.py:4071-4077`, 5.8.4, read 2026-10-25),
where rietx's reach about 16 FWHM of a Lorentzian at the 2 % tolerance. Wider
windows cost points; a taper costs a little area, which the area tolerance
already budgets.

**Where the resizing time goes**, unmeasured in detail: 2-5 ms a call, in
`phase_peaks`, `np.searchsorted`, `fcj.fcj_node_counts` and
`forward._batch_layout`, per phase and emission line, in Python. Profile
first. A compiled kernel is the expensive route: a new function in the
`rietx-kernels` crate (`kernels/`), a minor wheel release raising rietx's
floor, and the numpy fallback kept exercised (root CLAUDE.md § the compiled
tier, its four rules). Only the part numpy cannot vectorise goes there.

**What a real implementation must settle** (from probe 7, all unmeasured):
- a policy for LM trial points far from the start, since each now builds
  its own windows (one cpd-1a trial at `axial_sl` 1096 built 17.8× the
  compile's window points; LM rejected it);
- LM's width inequalities, built once per solve from the start's windows
  (`least_squares.py:1963`, `:2052`, built at `:2606`);
- the magnetic family (`win_mag`) and the extra peaks, left frozen;
- the traced backends: jax needs static shapes, so a fixed capacity per stage
  with a per-evaluation mask inside it, or a refusal;
- the history: the frozen-per-stage invariant, `NodeMetrics` "as-optimised"
  semantics and `refine.replay` all assume one compile per stage.

**The axial zero case, #774** (moved here from WP-2047 on 2026-10-25,
originally WP-1421's `### Inherited`; re-check it by the maintainer's
instruction). Ruled (c), documented: with both axial ratios at exactly zero
and either free, the compile sizes windows and FCJ nodes as if each were
`forward.AXIAL_SIZING_FLOOR` (0.02), so `predict()` differs from the same
model held at zero by 4.8e-5 of the strongest peak (the issue's rutile
reproducer). Sizing every zero model at the floor made the gap exactly 0 and
a default fluorapatite `mccusker_default` fit 2.0× slower. The floor does two
jobs: a live derivative column at zero (the nodes) and room for the tail the
stage grows (the windows). If windows follow the parameters, the second job
goes, so a model at zero could size its windows from its value and its nodes
from the free set, which may close the gap at no cost. Check that free and
held curves at zero then agree and that `test_cross_backend.py`'s axial rows
pass; `forward.MAGNETIC_SIZING_FLOOR` has the same shape. The sentences to
update if the gap closes are `help.py`'s `axial_sl`/`axial_hl` entries and
`Refinement.predict`'s docstring; `docs/practice.md` § Axial divergence at
zero has the survey. This task applies only if the maintainer adopts.

**Practice** (`docs/practice.md` § How far a peak is computed). GSAS-II, MAUD,
RIETAN-FP and EasyDiffraction recompute windows at every evaluation; TOPAS
rebuilds its peak buffer when a width moves past
`aberration_range_change_allowed`; FullProf holds them for a run.

**The tier of each rule this WP adds.** The resizing is named practice
(tier 2, four of the five programs surveyed). A taper's shape and width are
new judgement (tier 3), measured on the four protocols and the hostile pair
against the 5e-5-window fixed point of `tests/test_window_domain.py`.
Nothing ships as a default without the maintainer's ruling on the brief.

**Files.** `model/forward.py` (`rewindow`, `_batch_layout`, the profile
builders `_profile`/`_profile_basis` and `_omega_batch` for a taper),
`model/profiles/fcj.py`, `model/compiled.py` and `kernels/` if a kernel is
needed, `optimize/least_squares.py` (the closures), `docs/wp/2047-batch/`
(probes 7 and 8 to re-run).

## Non-goals

- Adopting anything as a default: this WP measures and briefs.
- The peaks buffer, shape reuse across reflections (fenced to v2 with FPA,
  WP-1122).
- Recompiling between solves within a stage (dropped in WP-2047's ruling).

## Tasks

- [ ] Profile one resize on the four protocols: milliseconds by part
      (`phase_peaks`, sizing, node counts, layout), per phase and line
- [ ] Vectorise what numpy can (across phases and lines, the layout build);
      re-measure; a compiled kernel only for what remains above ~0.5 ms a
      call, under the compiled tier's four rules
- [ ] A tapered window edge, opt-in on the compile: the cost made
      continuous in θ, its area cost against the window tolerance, and both
      Ω builders kept 1-2 ulp apart as root CLAUDE.md requires
- [ ] Probes 7 and 8 re-run with the fast resizing, with and without the
      taper: fit time, evaluations, LM terminations, answer shift and the
      polished fixed points, on the four protocols and the hostile pair
- [ ] The brief to the maintainer: default, opt-in or file, with the table
- [ ] #774's zero case (Context), only if the brief is ruled to adopt
- [ ] Skill: none until the ruling; an opt-in or a default adds its row

## Acceptance

The table of the fourth task exists for the four protocols and the hostile
pair, measured alone on one machine, and the maintainer has ruled on it.

```sh
OPENBLAS_NUM_THREADS=1 RIETX_TELEMETRY=0 .venv/bin/python docs/wp/2047-batch/probe7.py . time cpd1a
OPENBLAS_NUM_THREADS=1 RIETX_TELEMETRY=0 .venv/bin/python docs/wp/2047-batch/probe8.py . cpd1a
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- WP-2047's Context and `2047-batch/` probes 4-8.
- GSAS-II 5.8.4 `GSASIIstrMath.py` `getPowderProfile`, `GSASIIpwd.getWidthsCW`.
- Finger, Cox & Jephcoat (1994), J. Appl. Cryst. 27, 892-900 (the axial
  asymmetry whose extent sizes the windows).

## Handover log

- **2026-10-25** — filed by WP-2047's session on the maintainer's request
  ("test the compiled version of the resizing soon"), after WP-2047's
  prototype measured per-evaluation windows at 1.24-2.08× fit time with no
  accuracy gain on the protocols and the runaway removed. No open WP owns
  window resizing: 1122 is the peaks buffer, fenced to v2, and 1109, 1114,
  1115 and 1121 are closed. #774's re-check moved here from 2047, since it
  changes only if windows follow the parameters. Next: profile one resize.
