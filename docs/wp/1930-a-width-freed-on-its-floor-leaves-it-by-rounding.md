# WP-1930 — a width freed on its floor leaves it by rounding

Milestone: unscheduled · Status: 🔄 2026-10-13 — claimed by @yue-here
Track: What fires, and what stays silent
Depends on: —
Priority: P1 2026-10-08 — a published acceptance number (VALIDATION.md, the landing page) that `main` reproduces on no platform, χ²_red 12.48 on Linux against 9.69 on macOS, every assertion green; `profile.y` defaults to 0.0, its floor, and six preset plans free it there

## Goal

A stage that frees a softplus row sitting on its floor reaches the same
minimum on every platform, either because the row starts where its gradient
is order one or because the plan says why it stays held. The LaB₆ + cBN
acceptance case has one minimum, VALIDATION.md quotes it, and a bar tight
enough to see a 12.5 against 9.7 change guards it.

## Context

Issue #832 (mustachefeeling, 2026-10-08), found while investigating #831
(WP-1929). The third item of #836 (seed a floor row before freeing it, or
fire `SOFTPLUS_FREED_AT_FLOOR`) is the same work and lands here.

**The mechanism.** A softplus entry with `min=0` maps 0 to an internal
coordinate of about −27.6 (the `to_internal` clamp, physical 1e-12), where
dp/du ≈ 1e-12 and the Jacobian column is about 1e-8 of its neighbours. TRF
starts there with a gradient near zero, so whether a step ever lifts the row
depends on rounding. `TCHZ_DEFAULTS` has `"y": 0.0`
(`schemas/instrument.py:1036`), and `strategy/staged.py` frees
`instrument.profile.y` in six preset plans (lines 366, 387, 423, 452, 499,
552), so every default-instrument fit that runs one of them is exposed.

**What was measured** (#832's comment; Linux x86-64 WSL2 numpy 2.5.3, macOS
arm64 numpy 2.5.2 with Accelerate; each fit 1-4 s):

| tree | χ²_red | Rwp | LaB₆ wt % | `profile.y` |
|---|---|---|---|---|
| published (VALIDATION.md, landing page) | — | 0.1645 | 17.874 ± 0.314 | — |
| `d2f683a0`, both machines | 9.6615 | 0.16453 | 17.874 ± 0.314 | 0.0384 |
| `a3f9140a`, Linux | 12.4753 | 0.18696 | 17.656 ± 0.383 | 1e-12 (floor) |
| `a3f9140a`, macOS | 9.6917 | 0.16478 | 17.841 ± 0.314 | 0.0376 |

- The published row was written at `d2f683a0` (WP-1541's re-measure,
  2026-10-03), when both machines agreed. A bisect over all 77 first-parent
  merges to `a3f9140a`, on both machines, finds one step: **#700**
  (`c6eaff7d`, WP-1534, `Atom.biso` unbounded). Before it, the `biso` stage
  (where `profile.y` is still free, the free set being cumulative) lifts the
  row on both machines to one point. After it, Linux leaves it on the floor
  and macOS escapes in 60 iterations. The reporter's reading, not measured:
  unbounding Biso changes TRF's bound-distance scaling of those columns.
- The `profile` stage already ended 41 apart in cost before #700 (289199.582
  against 289158.745), harmlessly.
- **Every assertion in `test_acceptance_lab6_cbn.py` passes at both minima**
  (8 of 8). Nothing asserts χ², and the Rwp bar is a factor of 4
  (0.081-0.324). The nightly slow suite runs on Linux, so it passes at 12.48.
- **Seeding probe (option a).** Lifting `profile.y` at the start of the
  `profile` stage (to ln 2 internal, to 0.05°, or `Stage(..., seed=0.05)`)
  gives one minimum on both machines at both trees: χ²_red 9.8402, Rwp
  0.16604, LaB₆ 17.761 ± 0.312. It is a *higher* minimum, and there the
  Gaussian is clamped (Γ_G² < 0 at 98-100 % of points), so u, v, w are
  undetermined: esds `None` or ρ = ±1.000, `RESOLUTION_UNCONSTRAINED` in
  every arm. QPA, cBN cell and B x agree across arms to 5 digits. So seeding
  alone trades platform dependence for three dead columns; it would need the
  clamped triple held, or option (b) (free the row in its own short stage with
  what it trades against held).
- Same mechanism, milder, on BT-1 neutron: `profile.y` on its floor on both
  machines, at a different internal coordinate (WP-1929's case).

**Checked against the tree at `a3f9140a`** (this worktree's `[dev]` venv,
macOS arm64): the macOS row reproduces to every printed digit. χ²_red
9.6916891, Rwp 0.16478432, `profile.y` 0.037593 ± 0.001422, `profile.x`
0.003082, `w` 7.48e-6, diagnostics `CAPILLARY_OFFSET_UNAVAILABLE`,
`DISPERSION_NEGLECTED`, `RESOLUTION_NOT_POSITIVE`,
`RESOLUTION_UNCONSTRAINED`. The Linux row was not reproduced here (no Linux
machine; the nightly does not print χ²).

**Decided 2026-10-08 (maintainer), after a precedent search.**

- **Package:** a stage that frees a softplus row sitting on its floor starts
  it a short way inside, through `Stage.seed`'s existing path. This is #836's
  third item. The seed's size and where it comes from are this WP's to
  measure and state in the docstring.
- **LaB₆ + cBN:** option (a) with the Gaussian held. `profile.y` starts
  inside its floor, and u, v and w are held, because at that minimum the data
  cannot determine them (Γ_G² < 0 at 98-100 % of points). Option (b) has no
  precedent found. Option (c) is refused: on macOS the data put `y` at
  0.0376 ± 0.0014, 26σ from zero.
- **Order:** the reporter measures (a) with the Gaussian held on both
  platforms before it is adopted, then VALIDATION.md's row is re-measured.
  Asked on the issue the same day.

The precedents: MINUIT warns that a transformed parameter at its limit sees
a zero derivative and can stay blocked there, which is this WP's mechanism.
TOPAS gives width parameters a positive minimum (`pv_fwhm` 1e-6, `la` 1e-5,
`lh`/`lg` 0.001; Technical Reference Table 2.1) and applies limits inside
its solver, so a parameter at its minimum still sees its real slope. GSAS-II
sets no limits by default. scipy's TRF moves a start strictly inside its own
bounds, but rietx's floor is the softplus transform and not a scipy bound
(`internal_bounds` maps a lower bound ≤ 1e-12 to −∞), so that protection
does not apply.

**Measured 2026-10-09** (this worktree's `[dev]` venv, macOS arm64; the
handover log has the tables).

- **Rounding picks the minimum on one machine.** On the shipped plan,
  multiplying `w`'s start by (1 + k·1e-14) for k = ±1, ±3, ±7, 20 put five
  of seven starts at χ²_red 12.4753, `y` on its floor: Linux's number to
  every digit. The unperturbed macOS start is the minority outcome.
- **#700 is the trigger, not the cause.** With `biso` bounded (0, 25) again,
  k = 0 gives the published 9.661528, and k = −1 still lands on the floor
  (12.95). The floor trap predates #700, which moved where the coin lands.
- **Exposure.** Six presets free `instrument.profile.y` on its floor in
  their `profile` stage, on all three instrument presets, and
  `lab_sample_refine` frees the four phase widths on theirs. Extinction,
  roughness and the magnetic widths were already seeded. A hump's height
  (counts) and an extra peak's area are the floor rows left with no size.
- **The held protocol** reaches χ²_red 10.1518150 at every seed from 0 to
  0.05° and every perturbation, the reporter's two-platform 10.15182. BT-1's
  `y` goes back to its floor from every seed (χ²_red 1.9279825 throughout).
- **The seed is 1e-3°, not 0.05°.** At 0.05° nine synthetic suites whose
  true width is zero ran out of iterations or moved, and the free-Gaussian
  plan stopped at 9.84. At 1e-3° all nine pass unchanged and the free plan
  reaches 9.661408 at every perturbation, with `w` on its floor and the
  resolution diagnostics firing, so holding the Gaussian still stands.

### Inherited

- **2026-10-11, from WP-1938 (in flight, PR #883): the floor seed is
  deleted on that branch.** Under physical coordinates the trap it worked
  around is gone, so `seed_floor`, `SOFTPLUS_FLOOR_VALUE`,
  `SOFTPLUS_FREED_AT_FLOOR` and `StageResult.floor_unseeded` go (a
  before-validator drops the stored key). `FLOOR_SEEDS` stays as the FD step
  table. `Stage.seed` survives as `seed_floored`, lifting only a freed row
  sitting on a floor at or above 0. LaB₆ + cBN's shared fit then seeds
  nothing and `profile.y` leaves 0 on its own: 0.0369 at Rwp 0.168656, inside
  the reporter's 2 % band, and `test_acceptance_lab6_cbn` asserts
  `seeded == {}`. That figure was measured in a venv later found to run
  x86_64 under Rosetta, so re-measure it on arm64 before this WP's band task
  quotes it. The Caglioti W is now floored at 1e-8 deg²
  (`caglioti._MIN_GAMMA_G2`) and LM holds Γ_G² ≥ 1e-8 at every reflection as
  a linear inequality (WP-1938's D7/D8), so the free-Gaussian LaB₆ plans
  reach one answer, χ²_red 9.692771, where they split between 9.661 and 9.840.

- **2026-10-09, from WP-1929: the floor's column is rounding noise, and a
  finite softplus floor may make the seed unnecessary.** The Jacobian
  differences each column with h = 1e-6·max(1, |u|) in *internal*
  coordinates (`optimize/least_squares.py:592`, and `:1061` for the FD
  fallback). At u ≈ −27.6 that step moves the width by about 3e-17, below
  its own last digit, so the gradient TRF sees at a freed floor row is noise.
  This is the mechanism 1930's Context describes as "depends on rounding".
  On BT-1, differencing the width itself and chaining by dp/du made the esds
  agree to 1e-8 at u = −25.54, −25.5 and −514. WP-1929's session proposed
  probing a **finite internal floor** for softplus parameters, at TOPAS's
  defaults (widths 1e-6, scale 1e-11; TOPAS 5 Technical Reference § 2.5).
  There dp/du ≈ 1e-6, which is enough for both an accurate column and a usable
  gradient. If that probe closes the LaB₆ + cBN split, it replaces this WP's
  seed. Read 1929's 2026-10-09 handover entry and
  https://claude.ai/artifact/CYGoz3cF63QUJ345z4zKMY before landing the seed.
- **2026-10-10, from WP-1547: the nightly after #849 is red on this WP's
  two-site test.** Nightly 38048650490 ran on 32a2b473.
  `test_pair_diagnostic_class.py::test_the_two_site_set_reaches_one_minimum_and_pairs_nothing`
  found a pair: "class 2: phases.0.atoms.0.moment.dof0 and
  phases.0.atoms.1.moment.dof0 are a powder-degenerate moment pair". The
  job ended 1 failed, 9349 passed, 131 skipped. The nightly before,
  37928572815 on 9219e886, was green. Eleven merges sit between, among them
  #849 (this WP), #855 (WP-1936's FD step) and #861 (spglib 2.8). Which one
  moved it was not checked.
- **2026-10-11, from the issue triage (#865, in PR #870): the two-site test
  this WP re-baselined fails by CPU, and its class 2 reading was backwards.**
  The 2026-10-10 nightly went red at `32a2b473` on
  `test_the_two_site_set_reaches_one_minimum_and_pairs_nothing` (the entry
  above). No merge moved it: the runner's CPU did. The reporter
  ran it twelve times on `ubuntu-latest`: 7 of 7 AMD EPYC 7763 runners fail
  and 5 of 5 Intel Xeon runners pass, at one sha. Only class 2 moves. Intel
  and macOS stop at m ≈ 0, where |F_m|² ∝ m² gives the column no gradient; AMD
  walks past it from two of three starts to χ² lower by 41, with
  ρ(Mn1, Mn2) = −0.99997. So class 2's m ≈ 0 is itself a stopping point, the
  same kind as the pairs this WP removed, and the docstring's "collapses to
  m ≈ 0" names the worse minimum. PR #870 asserts the winner only (8 of 8
  runners pass). Whether a moment trial should be seeded off m = 0, as this
  WP seeds a width off its floor, is the open question it leaves. Checked
  against the tree at 7d9be3cb: `tests/test_pair_diagnostic_class.py:42-73`
  still asserts no `MOMENT_PAIR_DEGENERATE` from any class.

- **2026-10-11, from the issue triage (#832): the band's Linux run has
  happened, and the reporter's sweep left three splits in no WP.** The
  2026-10-10 nightly (run 38048650490, `32a2b473`, containing #849) ran the
  Linux full suite at 9349 passed, 1 failed, and the failure was the two-site
  test (#865, above), so `test_the_shared_fit_reaches_one_minimum_on_every_platform`
  passed on Linux. The reporter's sweep of 2026-10-08 11:55 (19 acceptance
  files, 222 fits, Linux and macOS) found lab6_cbn's shared plan the only
  split that started at #700. Three others it found are in no WP: (a) the
  degenerate LaB₆ plan, χ²_red 5.470 on Linux against 6.001 on macOS, with the
  quoted "Rwp 0.1294, QPA 16.542" reproduced by neither; (b) Stephens brucite,
  where TRF stops at `max_iter` on Linux (Rwp 0.18030) and converges on macOS
  (0.17844), so `docs/VALIDATION.md:765`'s 17.84 % is the macOS value; (c)
  five indexing Le Bail fits split after #741, the short-wavelength P
  candidate leaving `profile.y` on its floor on Linux (χ²_red 32.27 against
  29.38). The Next list's "still stale" Cr₂WO₆ number is done
  (`docs/VALIDATION.md:1471` reads 0.2035). Checked against the tree at
  7d9be3cb: the nightly's failure list read from its log, `seed_floor` at
  `params/vector.py:2901`; (a)-(c) not re-measured.

## Non-goals

- Which esds a floor row's neighbours report: WP-1929.
- A coefficient read off its floor after the fit: WP-1914.
- The PVII/FPA peak-shape gap the suite's own comments name as why Rwp is
  worse than TOPAS's.

## Tasks

- [x] Reproduce the Linux minimum on one machine: the `biso` stage started
      from each platform's `profile`-stage end state, or the probe the
      reporter offers. Confirm or refute the bound-scaling reading of #700.
- [x] Count the exposure: of the acceptance suites and the six presets, which
      free a softplus row at its floor, and which of those end on it.
- [x] The decided protocol on LaB₆ + cBN, option (a) with u, v and w held,
      measured on both platforms (the reporter's run, or this WP's on Linux
      CI), and on BT-1 to see whether it moves.
- [x] The package side: `Stage` seeds a floor row it frees (#836 item 3),
      through `Stage.seed`'s existing path, with the seed's size and source in
      the docstring. A diagnostic only if a caller can still free one unseeded.
- [ ] A χ² or Rwp band on `test_acceptance_lab6_cbn.py` tight enough to see
      12.5 against 9.7 (the reporter suggests Rwp within 2 % of the
      re-measured value), run on both nightly platforms. *Landed and green
      on macOS 2026-10-09; the Linux nightly after merge is the second run.*
- [x] Re-measure VALIDATION.md's row and the landing page's copy on the
      chosen protocol (`docs/landing/README.md` says how the page's numbers
      are rebuilt).
- [x] Tests, with obs/calc/diff PNGs to `tests/output/`.
- [x] Skill: if a diagnostic lands, its `references/judging.md` row; if the
      protocol is a rule an agent applies by hand, SKILL.md §2's seed rule.
      *The row went to `diagnostics.md`, beside the stage codes, paid for by
      two cuts; no hand rule, since the package now seeds.*

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_acceptance_lab6_cbn.py tests/test_acceptance_wavelength.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

Linux and macOS reach the same χ²_red on LaB₆ + cBN to 1e-4 relative, the
new band fails at 12.48, and VALIDATION.md's row is reproduced to every
printed digit on both.

## References

- Issues #832, #831, #836; PR #700 (WP-1534).
- WP-1541 (the re-measure the published row came from), WP-1929, WP-1914.
- TOPAS 5 Technical Reference, § 2.5 and Table 2.1 (default limits); ROOT
  `TMinuit` documentation, parameter limits.
- Coleman, T. F. & Li, Y. (1996). *SIAM J. Optim.* 6, 418-445 (the
  trust-region reflective method scipy's TRF implements, strictly feasible
  iterates).

## Handover log

- **2026-10-09, after the PR's Linux CI** — two fast tests failed on every
  Linux leg and passed on macOS. Both were bars on a number rounding now
  chooses.

  *Le Bail alternation.* At +0.3 %, pass 1 read 13.718 on both platforms.
  Pass 2 read 13.766 on Linux and 13.751 on macOS, a 1.5e-4 spread against
  the 1e-4 bar. Pass 2 is the discarded pass, so the test now pins pass 1
  and asserts only that pass 2 is worse.

  *Wrong triclinic cell* (`test_cell_runaway_safety.py`). Linux returned
  Rwp 1.1e9 under `converged`, where the test wanted below 1. Ten nudges of
  k·1e-14 to `profile.w` on macOS: on `main` both plans read 0.3316 every
  time; with the seed the second plan read 0.33-6.55, and 1.8e7 at k = −20.
  Neither is a fit. On `main` U and V went negative, so every peak drew at
  the 1e-4° floor and only the background was fitted. With the seed some
  runs take the widths to their upper bounds, and the frozen windows cut
  those peaks short while solving. The test's claim is that `fit` returns
  instead of raising, so it now asserts a finite, positive Rwp beside the
  `CELL_RUNAWAY` it already pinned. It passes in all ten nudged runs.
  `FROZEN_COMPILE_STALE` called that gap of 3.1e4 % "not biased" at `info`.
  That claim went to WP-1421 § Inherited, which owns the message.

- **2026-10-09** — LaB₆ + cBN now has one answer on every machine, and the
  package no longer leaves a freed width on its floor for rounding to decide.
  The split was never Linux against macOS: on one Mac, a 3e-14 change to one
  start value reproduced Linux's 12.48 in five of seven tries, and it did so
  before #700 too. The fix is two parts: the Gaussian triple held, as decided,
  giving χ²_red 10.1518 everywhere, and a package-wide floor seed at 1e-3 of a
  width's unit. The larger 0.05° seed was tried and refuted; it broke nine
  suites whose true width is zero. Three published numbers moved with the
  protocol: QPA 17.791 ± 0.319 wt % (was 17.874), Rwp 0.1687, cBN +16 ppm.

  *Done.* `ParameterTable.seed_floor` + `FLOOR_SEEDS`/`SOFTPLUS_FLOOR_VALUE`
  (`params/vector.py`), called after `Stage.seed` in `_run_stage` and
  `multi.py`; `StageResult.seeded`/`.floor_unseeded` (schema 0.43 → 0.44);
  `SOFTPLUS_FREED_AT_FLOOR` for a floor row with no seed size (a hump's
  height). `test_acceptance_lab6_cbn.py`: triple held in both plans, silence
  restored in the correlation test, a 2 % Rwp band, render test. Re-baselined
  with reasons: the Le Bail alternation scenarios (every pass ~3 pp lower, so
  the shapes moved to +0.3 % and +0.4 % starts), NAC's `at_bound` count, the
  GUI last rung (as-optimised staleness, 8e-6), corundum's anisotropy bar
  (rides a flat direction, 2.02 → 4.51 at one χ²), FAP's window test (now
  runs the screen's own `two_theta_max`), the two-site magnetic pair test
  (pairs were stopping points; naming check moved to the 150 K solution).
  VALIDATION.md, the landing row, the manual's `StageResult` table and the
  skill's diagnostics row (net −63 B) updated. API index cap 39 700 → 39 800,
  WP-1920 owning the split.

  *Measured* (`[dev]`, macOS arm64). Seed sweep (0 / 1e-3 / 1e-2 / 0.05°, two
  perturbations each): LaB₆ held χ²_red 10.1518150 in every arm, 47-52 →
  41-45 → 36-40 iterations; BT-1 1.9279825, `y` back on its floor from every
  seed; brucite 8.313117. Free-triple plan at 1e-3°: 9.661408 at every
  perturbation, `w` on its floor and the resolution diagnostics firing, so the
  hold stands; at 0.05° it stopped at 9.8402. Degenerate plan: one minimum,
  χ²_red 5.934160, LaB₆ 16.850 ± 0.192 (5.5σ out). On the bare branch the
  full suite found three slow failures (FAP window, corundum, two-site pair),
  fixed above. On `main` merged in (8 commits, `5aaec31b`): fast 8905 passed,
  172 skipped, 0 failed, 8:40 with three other pytest processes running; full
  9190 passed, 184 skipped, 0 failed, 30:02, nothing else running at its start.
  The 13 added fast tests cost 1.91 s together, the dearest 0.59 s. Main moved
  under the branch, so the delta is not attributable test by test. Lanes:

  | lane | est | requests | main at dispatch | lane $ | saved $ |
  |---|---|---|---|---|---|
  | fap-window | 20 | 23 | 385K | 1.01 | +0.97 |
  | magnetic-pair | 20 | 35 | 392K | 1.45 | +1.31 |

  Selective policy (lane when main > 150K and item ≥ 20): −21 % over 90
  replayed sessions.

  *Review* (`/code-review high --fix`, 10 findings). Fixed: a named
  variable lost its unit, so `vars.X` was never floor-seeded; a shared joint
  column could take two seeds through per-histogram box caps; three copies of
  the stage-list wording became `_stage_list`; a floored `.scale` fired the
  new warning against PHASE_UNCONSTRAINED's advice and is now left to it; the
  manual overclaimed that every width is softplus; the 1.8 notes and record
  now stage the change. Declined, with reasons: re-seeding a row a later stage
  names again is what "a stage that frees it" means, and the answer stage
  converges it back (BT-1); the TOPAS protocol departure is the maintainer's
  decided option (a), documented in the suite. Open: `suggest()` still probes
  every floor candidate at a flat 1e-3 (`SUGGEST_SEED_SOFTPLUS`,
  `refine.py` near the `seed_softplus(cand_paths` call), so a deg² width is
  probed from a start no stage takes; and `RWP_PLATFORM_SPREAD` 1e-4 in the
  Le Bail alternation suite rests on the pre-seed Linux spread, which the PR's
  Linux CI measures.

  *Gotchas.* The acceptance's second platform is unrun: the reporter measured
  the held protocol on Linux (10.15182, 1e-12 agreement), but not this tree's
  seed. Other suites' VALIDATION rows were not swept for moved figures; only
  the tests that failed were re-measured.

  Next: (1) watch the PR's Linux CI for the alternation suite's 1e-4 bar,
  and the first Linux nightly after merge for the band, then tick it and
  close; (2) size `suggest()`'s probe seed by unit through `seed_floor`,
  re-measuring its ranked rows; (3) ask the reporter whether their fit recorder can sweep this
  PR against `main` for VALIDATION rows that moved silently, and re-measure
  what it finds (their Cr₂WO₆ 0.2047 → 0.2035 is #700's and still stale).

- **2026-10-08** — created, from the 2026-10-08 issue triage (issue #832,
  and #836's third item). Checked against the tree at `a3f9140a`: the macOS
  minimum reproduces to every printed digit; the Linux one was not tried. No
  open WP owns it: 1534, whose merge is the bisect's step, is closed; 1541,
  which wrote the published row, is closed; 1929 takes the esds and 1914 the
  after-fit reading. Rated P1 for the published number no platform
  reproduces. Decided the same day by the maintainer: seed a floor row a
  stage frees, and option (a) with the Gaussian held for LaB₆ + cBN, measured
  by the reporter on both platforms before it is adopted.
