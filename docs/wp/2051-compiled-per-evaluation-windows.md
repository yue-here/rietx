# WP-2051 — Windows resized at every evaluation, fast enough to measure

Milestone: unscheduled · Status: ✅ 2026-10-25 — measured and ruled: per-evaluation windows filed for now, kept for the future; the fast sizing shipped
Track: What fires, and what stays silent
Depends on: 2047 (`forward.rewindow`, `fcj.fcj_node_counts` and probes 7 and 8 land with it)

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

**Where the resizing time goes, measured 2026-10-25** (task 1,
[`2051-batch/resize_profile.py`](2051-batch/resize_profile.py); macOS arm64,
`[dev]`, compiled tier on; median over 40 sizing calls spread through each
perEval fit, each part the minimum of 5 repeats; the `rewindow` row measured
at b70ba5972, before task 2 gave it the table). A whole `rewindow` costs
0.86-2.49 ms. Most of it is `window_fwhm_mult`, the 60-step bisection for the
FWHM multiple k(η). It costs a fixed ~0.36 ms per phase and emission line,
whatever the reflection count, because each step is a handful of numpy calls:

| ms a call | NAC | LaB6 | Fluorapatite | cpd-1a |
|---|---|---|---|---|
| Phases × lines, points | 2 × 1, 22 003 | 1 × 2, 5332 | 1 × 2, 5750 | 3 × 2, 7251 |
| `rewindow`, whole | 1.09 | 0.86 | 1.55 | 2.49 |
| k(η) bisection | 0.80 | 0.72 | 1.11 | 2.18 |
| `_batch_layout` | 0.19 | 0.05 | 0.30 | 0.16 |
| `phase_peaks`, memo warm (cold) | 0.04 (0.45) | 0.02 (0.14) | 0.03 (0.49) | 0.07 (0.45) |
| bounds, FCJ extent and node counts | 0.01 | 0.04 | 0.07 | 0.02 |
| Sizing calls a fit | 118 | 241 | 184 | 442 |

The memo-warm `phase_peaks` is the marginal cost, since the residual that
follows reads the same memo. So a resize without the bisection and without
rebuilding unmoved layouts is ~0.1-0.4 ms, and the WP's ~0.5 ms bar for a
compiled kernel is not reached by any part. A compiled kernel is the expensive route: a new function in the
`rietx-kernels` crate (`kernels/`), a minor wheel release raising rietx's
floor, and the numpy fallback kept exercised (root CLAUDE.md § the compiled
tier, its four rules). Only the part numpy cannot vectorise goes there.

**The fast resizing, measured 2026-10-25** (task 2). `forward.window_sizing`
is `rewindow`'s loop with k(η) read off a table built once per window
tolerance (`window_fwhm_mult_interp`: 8192 nodes, uniform plus geometric
toward η = 0, within 1.2e-5 of the bisection; `test_window_loss.py` holds it
to 2e-5 at four tolerances). `compile_model` keeps the bisection, so no
compiled window and no golden moves. Probe 9
([`2051-batch/probe9.py`](2051-batch/probe9.py)) is probe 7 with that sizing;
probe 7's `sync` already rebuilt the layout only for a phase that moved. Same
machine, alone, median of 5 interleaved pairs:

| | NAC | LaB6 | Fluorapatite | cpd-1a |
|---|---|---|---|---|
| `window_sizing`, ms a call (the bisection's loop: 0.86-2.49) | 0.08 | 0.09 | 0.13 | 0.16 |
| Layouts a sync rebuilds, ms a call (median; a call where a phase moved pays that phase's `_batch_layout`, 0.05-0.30 above) | 0.003 | 0.002 | 0.002 | 0.004 |
| Resizing seconds a fit (probe 7: 0.12, 0.21, 0.35, 1.25) | 0.03 | 0.05 | 0.13 | 0.27 |
| Fit time ratio (probe 7: 1.24, 1.63, 1.66, 2.08) | 1.05 | 1.29 | 1.48 | 1.49 |
| Evaluations, shipped → per evaluation | 46 → 49 | 90 → 110 | 49 → 83 | 175 → 216 |

So the resizing is no longer the cost. What remains is the extra evaluations,
which the taper is for: with the resizing taken out the ratio is 1.0, 1.19,
1.38 and 1.32. Not done, and why: no compiled kernel, since no part is near
0.5 ms; no batching across phases and lines, since a line now costs ~20 µs.
Answers match probe 7's (cpd-1a's 0.99 esd on `profile.v`, the second minimum).

**The taper, emulated 2026-10-25** (task 3, probe 9 with `PROBE9_TAPER`).
After each sizing, every phase's 0/1 window mask becomes mask·T(u), with
u = |2θ − pos|/half at that evaluation's values and T a cos² ramp from 1 to 0
over the ramp, with zero slope at both ends. The mask multiplies the forward Ω
and every partial plane (`forward.py`, `_omega_batch` and
`derivative_bases`), so the cost is continuous where an edge crosses a point.
The Jacobian leaves out ∂T/∂θ alone. FCJ node counts still step. Only the
ramp's points are touched, found by `searchsorted`; the probe copies the
mask each call, which a taper inside `_omega_batch` would not. Two shapes,
both at w = 0.1:

- *Inward*: the ramp is the outer tenth of the half-width. It drops area
  inside the sized edge: 0.053 × the window tolerance for any η ≥ 0.3, but
  0.37 × for a pure Gaussian at the 2 % tolerance and 0.82 × at the closing
  stage's 1e-3 (computed for one pseudo-Voigt without slack, an upper bound).
  At w = 0.25 the Gaussian figure passes the tolerance itself (1.17 ×).
- *Outward* (`PROBE9_TAPER_SIDE=out`): the window widens to 1.1 × the
  half-width and the ramp covers the added strip, so nothing inside the sized
  edge is dropped and the window holds a tenth more points.

Median of 5 interleaved pairs, same machine, alone:

| | NAC | LaB6 | Fluorapatite | cpd-1a |
|---|---|---|---|---|
| Evaluations: shipped / no taper / inward / outward | 46 / 49 / 49 / 47 | 90 / 110 / 91 / 101 | 49 / 83 / 53 / 49 | 175 / 216 / 188 / 186 |
| Fit time ratio, inward / outward | 1.13 / 1.16 | 1.09 / 1.25 | 1.04 / 1.13 | 1.33 / 1.36 |
| The same less the probe's sync (resize, taper, copy) | 0.99 / 0.99 | 0.97 / 1.10 | 0.94 / 1.01 | 1.10 / 1.11 |
| Largest answer shift from shipped, esd, inward / outward | 0.007 / 0.008 | 0.004 / 8.8 | 0.016 / 0.040 | 0.37 / 0.47 |

The taper recovers most of the extra evaluations. LaB6's 8.8 esd is on
`axial_hl`, at Rwp equal to shipped to six figures: the flat direction the
WP's Context names, which a wider inward taper (w = 0.25) reaches too. The
"less sync" row is the inferred ceiling for a taper built into
`_omega_batch`. The probe's sync costs 0.3-1.4 ms a call, most of it the mask
copy.

**Which answer is right, and the runaway, measured 2026-10-25** (task 4:
probe 10, which is probe 8 on probe 9's arms, and probe 9's `fit` mode). Each
arm's answer is polished at 5e-5 windows to a fixed point, as in probe 8.
"Apart" is the distance between the per-evaluation arm's polished point and
shipped's, in esd of the row that differs most:

| | No taper | Inward w = 0.1 | Outward w = 0.1 |
|---|---|---|---|
| NAC: apart; χ² polished (shipped 12.406) | 0.0; 12.406 | 0.0; 12.406 | 0.0; 12.406 |
| LaB6: apart; χ² polished (shipped 3.518) | 5.06 on `profile.u`; 3.549 | 0.0; 3.518 | 9.84 on `axial_hl`; 3.518 |
| Fluorapatite: apart; χ² (shipped 2.747) | 0.0; 2.747 | 0.0; 2.747 | 0.0; 2.747 |
| cpd-1a: apart; χ² (shipped 1.847) | 0.95 on `profile.v`; 1.845 | 0.36 on `lor_strain`; 1.846 | 0.47 on `lor_strain`; 1.847 |
| Each arm to its own polished point, largest, esd | 0.02-0.55 | 0.01-0.03, LaB6 3.92 | 0.01-0.04, LaB6 3.92 |
| Hostile pair, pre-WP-2045 schedule: cpd-1b `axial_sl`, Rwp (shipped 557.8, runaway) | 0.0076, 0.1394 | 0.0080, 0.1397 | 0.0080, 0.1398 |
| Hostile pair, shipped schedule: the same | 0.0076, 0.1394 | 0.0080, 0.1397 | 0.0080, 0.1398 |

Shipped's own answer sits 0.008-0.019 esd from its polished point, LaB6
3.92 esd on `profile.u` (its Γ_G² floor defect). Read together:

- **Accuracy is a wash.** On NAC and fluorapatite every arm polishes to
  shipped's point. Where a polished point differs it is by a flat direction
  (LaB6 outward, `axial_hl`, χ² equal to four figures) or a shallow second
  minimum (cpd-1a, χ² within 0.1 %). The taper brings the arms closer:
  inward reaches shipped's point on LaB6, where the untapered arm found a
  χ² 0.9 % worse.
- **The runaway stays removed** under every arm and either schedule. All six
  hostile runs converged in 39-70 evaluations at `axial_sl` 0.008. Under the
  shipped schedule the shipped arm no longer runs away either (WP-2045).
- **LM terminations** (probe 9's `time` records): every stage of every arm
  converged. NAC's seven end exactly as shipped's. Elsewhere one or two of
  7-9 stages swap `ftol_runs` for `exhausted_fp64` or back, both converged
  endings; no stage ends on a limit.

**The ruling, 2026-10-25: filed for now, kept as a possibility for the
future.** The brief offered default, opt-in or file and recommended filing. Per-evaluation
windows gain no accuracy on the four protocols. The one failure they fix,
the hostile chain's runaway, is already stopped by WP-2045's schedule and
reported by `STAGE_WINDOWS_STALE`. Building them rewrites the first invariant
(frozen-per-stage discreteness) across every backend. The case against,
recorded with it: four of the five programs surveyed recompute windows at
every evaluation, and with a taper built in the runtime cost is inferred at
0.94-1.10× shipped. What ships is the fast sizing alone
(`forward.window_sizing`, `window_fwhm_mult_interp`), which `window_loss`
uses. **To reopen**: a `STAGE_WINDOWS_STALE` firing on a user's fit, or a
chain the schedule does not stop. Start from probes 9 and 10, the outward
taper at w = 0.1 (it drops no area inside the sized edge, where the inward
one drops up to 0.82 × the closing tolerance from a Gaussian), the list under
"What a real implementation must settle" below, and #774's zero case.

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

- [x] Profile one resize on the four protocols: milliseconds by part
      (`phase_peaks`, sizing, node counts, layout), per phase and line
- [x] Vectorise what numpy can (across phases and lines, the layout build);
      re-measure; a compiled kernel only for what remains above ~0.5 ms a
      call, under the compiled tier's four rules
- [x] A tapered window edge, opt-in on the compile: the cost made
      continuous in θ, its area cost against the window tolerance, and both
      Ω builders kept 1-2 ulp apart as root CLAUDE.md requires.
      *Done as an emulation in probe 9 (2026-10-25)*: a taper means nothing
      on frozen windows, so the opt-in on the compile waits for the ruling
      on per-evaluation windows. The mask seam carries it through both Ω
      builders alike, so their 1-2 ulp gap is untouched
- [x] Probes 7 and 8 re-run with the fast resizing, with and without the
      taper: fit time, evaluations, LM terminations, answer shift and the
      polished fixed points, on the four protocols and the hostile pair
- [x] The brief to the maintainer: default, opt-in or file, with the table.
      *Ruled 2026-10-25: file it for now, kept as a possibility for the
      future* (the ruling below)
- [x] #774's zero case (Context), only if the brief is ruled to adopt.
      *Not applicable: filed, not adopted.* The re-check stays with this
      file's Context for whoever reopens per-evaluation windows
- [x] Skill: none until the ruling; an opt-in or a default adds its row.
      *None: filed, nothing a user can turn on*

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

### 2026-10-25 (2nd session) — measured, ruled: filed for now, kept for the future; closed

Windows that follow the parameters at every evaluation can now be judged on
cost. They are not slow any more. The prototype's 1.24-2.08× fit time was
mostly one bisection, solved afresh at every call. With that replaced by a
table the cost falls to 1.05-1.49×. A taper at each window's edge then
removes most of the extra solver work, and built into the forward model it
is inferred at 0.94-1.10× shipped. Answers match shipped's on the four
standards and the old runaway stays removed. The maintainer ruled to file it
for now and keep it as a future possibility. It buys no accuracy, and
building it rewrites the frozen-per-stage invariant on every backend. Only
the fast sizing ships.

*Done.* Profiled one resize (task 1). `forward.window_sizing` and
`window_fwhm_mult_interp` give the resize a k(η) table, and `compile_model`
keeps the bisection, so no compiled window and no golden moves (task 2). The
taper was emulated in probe 9, inward and outward at w = 0.1 (task 3). That
departs from the task's "opt-in on the compile": a taper means nothing on
frozen windows, so it waits on the ruling. Probes 7 and 8 were re-run as
probes 9 and 10 on three arms (task 4). The brief offered default, opt-in or
file and recommended filing, which was ruled (task 5). #774's zero case and
the skill row do not apply, since nothing was adopted. Arrival: no
`### Inherited`, and the findings were today's, so nothing was stale. The
branch is cut from WP-2047's tip, since 2051 needs `rewindow`. It merges the
filing commit of PR #1174, so PR #1175 shows the commits of #1171 and #1174
until those merge. `Track:` was missing from the filed header, so the index put
2051 in a group ROADMAP does not link; it now has 2047's track.

*Measured.* The tables are in Context ("Where the resizing time goes", "The
fast resizing", "The taper, emulated", "Which answer is right, and the
runaway"), all macOS arm64, `[dev]`, compiled tier on, alone. Fast
selection on this branch with origin/main merged (`[dev]`, macOS arm64):
11792 passed, 272 skipped, 28 xfailed, 1 failed in 6:18. The failure was
`test_every_roadmap_heading_with_rows_links_them`, the missing `Track:`, and
that file passes on the fix (25). The one added test,
`test_the_tabled_window_multiple_is_the_compiles` (4 cases), cost 0.08 s in
that run; `test_window_loss.py` total 0.08 s for the added test. The full
selection did not run. This change moves only `window_loss`, by ~1e-5 of a
window width, so its two slow readers ran instead on the merged tree:
`test_acceptance_sequential.py` and `test_window_domain.py`, 39 passed,
9 xfailed in 1:39 (same venv and platform).

*Code review* (`/code-review high --fix`, scoped to this session's commits).
Fixed: the table's node count (8192, not 8193), a redundant clip, the
test's duplicate tolerance (now 1e-2). The profiler's samples pointed at a
model that probe 7's sync later changes, so its "layouts a sync rebuilds"
row compared against the fit's last windows. It now snapshots each sample;
the median re-measured at 0.002-0.004 ms, against the biased 0.003-0.29. The
profiler now names the tree its bisection row came from. Declined: two k(η)
solvers (deliberate, so no golden moves; the test pins them to 2e-5).
Declined: the table's error growing past 1.2e-5 at tolerances under 5e-5 (the
reviewer measured 1.94e-5 at 1e-8; the interpolated k lands on the wide side,
and the window drops no more than its tolerance at any tolerance it tried).
Documented, not re-run: probe 9's outward arm draws a peak symmetric when it
reaches the range only through the added strip.

*Generality.* Not dispatched. `_audit.py` is untouched, and the only new
literals (the 8192-node grid, geometric to 1e-9) set an interpolation's
precision, which a test holds to 2e-5, and judge nothing about data.

*Gotchas.* Probes 9 and 10 import `2047-batch/probe7.py` and patch its
module globals, so they break if probe 7 is renamed. The worktree guard
refuses a compound shell command and runs none of it, so an edit in one
silently did not happen.

*Next.* Nothing on this WP. It reopens only on a `STAGE_WINDOWS_STALE`
firing on a user's fit, or a chain WP-2045's schedule does not stop. Context's
ruling paragraph says where to start.

- **2026-10-25** — filed by WP-2047's session on the maintainer's request
  ("test the compiled version of the resizing soon"), after WP-2047's
  prototype measured per-evaluation windows at 1.24-2.08× fit time with no
  accuracy gain on the protocols and the runaway removed. No open WP owns
  window resizing: 1122 is the peaks buffer, fenced to v2, and 1109, 1114,
  1115 and 1121 are closed. #774's re-check moved here from 2047, since it
  changes only if windows follow the parameters. Next: profile one resize.
