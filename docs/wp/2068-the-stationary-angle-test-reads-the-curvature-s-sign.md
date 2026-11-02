# WP-2068 — The stationary-angle test builds its angle block analytically

Milestone: unscheduled · Status: 🔄 2026-11-02 — claimed by @yue-here (ghostshift runner): tasks 2-4, the analytic angle block
Track: What fires, and what stays silent
Depends on: — (1327 soft: the moment derivative `d_magnetic_f2_d_dofs` from #1206, merged 2026-10-31)
Priority: P3 2026-11-02 — task 1 found no fit on main that stops on a maximum the test then passes wrongly, so only the cost half is left: 85-93 % of a moment-only fit at k ≥ 8, about 3 % of MAGNDATA structures

## Goal

`stationary_angle_test` builds the moment-angle columns and their second-derivative block from
the analytic moment derivative instead of central differences, so the test's cost stops growing
as k^2.7 with the number of free moment angles.

*Superseded in part, 2026-11-02 (task 1).* The goal also had the test read the curvature's
sign, so that a fit stopped on a maximum along an angle would no longer pass. Task 1 measured
that no such stop reaches the test on main, and that the one stall it could produce passes
correctly. That half is now a non-goal with a condition attached (§ Non-goals).

## Context

From issue #1207 (mustachefeeling, 2026-10-28), a proposal written as a WP for the maintainer
to file. It depends on #1206 (the analytic moment derivative, merged 2026-10-31).

**What runs today.** `optimize/least_squares.py`: `stationary_angle_test` (`:803`) calls
`_joint_newton` (`:674`), which builds the angle columns C = ∂r/∂α and the block
∂²r/∂α_a∂α_b by central differences of the whole residual: 2k² + 1 evaluations per Newton
iteration for k free moment angles, up to `STATIONARY_ANGLE_MAX_ITER` = 8 iterations a round
(`:593`, an `_audit` row at tier 3). `_half_widths` (`:779`) reads the curvature for the
profile half-widths. The test is WP-1929's (✅), whose closed file is not to be reopened.

**Two halves, of different weight.**

- *Correctness (the reason for P2).* At a symmetry-fixed direction the angle column is zero, so
  d²χ²/dα² = 2(‖∂r/∂α‖² + rᵀ∂²r/∂α²) reduces to 2·rᵀ∂²r/∂α². The sign that separates a minimum
  from a maximum sits entirely in the residual-curvature term. A Gauss-Newton JᵀJ is positive
  semi-definite and cannot see it. The reporter states that a maximum the fit starts on passes
  today, because Δχ² to the stationary point is 0 when the stop *is* the point; #1206 saw two
  fits of `test_magnetic_moment_frame` stop on φ = 0, a maximum along φ. Not reproduced by
  this triage.

  *Superseded in part, 2026-11-02 (task 1, macOS arm64, `[dev]`, tree a8f679858).* The test is
  blind to the sign, as stated: handed a stop that is the stationary point, it reads Δχ² = 0
  and passes. But no fit on main hands it a stop on a maximum. Every moment-angle column on
  main is a forward difference (`least_squares._moment_reach_ok` declines the analytic angle
  column by name, #1206). A forward difference reads ½·r″·h at an even point, so the solver's
  step walks off a maximum. Measured: six one-site starts placed exactly on a symmetry
  direction that is a maximum (tilt or azimuth truth 0.05-0.8 rad, `test_stationary_moment_angle`'s
  Pnma fixture, seed 2) all reached χ²_red 1.031-1.033 at the truth or its mirror image, and
  `test_magnetic_moment_frame`'s three PLAN_2/PLAN_3 fits reached φ = 0.0470 under LM and
  under TRF. With the analytic angle column let through (a patch of `_moment_reach_ok`,
  #1206's declined arm), #1206's stall comes back: PLAN_3 stops at φ = −5e-17, χ²_red 0.97951
  against 0.97821 at φ = ±0.047. The test passes it, at statistic 0.000. That pass is the
  right verdict, because from the minimum the same test reads 0.137 against the cut of 2.71:
  the data cannot separate the maximum from the minima beside it. The six deep maxima did not
  stall even under that arm. Under it, the existing rows
  `test_the_written_back_moment_is_the_fitted_one_after_the_angle_moved[101.1]` and `[103.0]`
  go red (|m| 3.1804 against the pinned 3.1772 ± 5e-4), so a change that lets a fit reach
  this stall is already caught.
- *Cost.* Reporter's measurement (macOS arm64, `[dev,jax]`, on #1206's head `5788bf322`),
  moment-only synthetic fits: the test takes 24 % of the fit at k = 2, 54 % at k = 4, 85 % at
  k = 8 and 93 % at k = 16 (33.6 s of 36.0 s). On the two vendored real fits (Cr₂WO₆ HB-2A,
  LaMnO₃ BT-1; k = 1) it takes 0.3 % and 0.7 %. Over MAGNDATA (1124 of 2447 `.mcif` files
  read), k ≥ 4 for 19.3 % of structures and k ≥ 8 for 3.3 %. These are upper bounds: a held
  flat direction never reaches the test.

**The proposal.** ∂²|F_⊥|²/∂a∂b = 2·Re[(P·∂_aF)ᴴ·∂_bF + F_⊥ᴴ·∂²_abF]. ∂²F is non-zero only for
two angles of the same site, so it is one more orbit sum per site; the cross-site terms are
the first product alone. With extinction off, y is linear in |F_⊥|², so ∂²r chains through the
intensity factors; with extinction live a G′ term joins, or the declared FD fallback #1206
uses. numpy only: the traced twin declines a moment model.

**Alternatives the reporter weighed**, each giving up something: Broyden updates of ∂C/∂α
(loses the exact curvature the verdict reads); testing only angles near a fixed direction
(adds a threshold and an `_audit` row, misses a stop between cuts); block-diagonal by site
(drops couplings that are not zero); parallel corner evaluations (wall clock only, verdicts
bit-identical). Only the analytic route gives the sign exactly.

**Invariants that bind it.** "A branch's oracle must be exact where the branch is" (root
CLAUDE.md): the second-derivative block needs its own exact oracle, never a forward
difference. The FD path stays as the fallback and is kept exercised.

### Inherited

## Non-goals

- Seeding a moment angle off a maximum before the stage: proposed separately on #1206.
- Any change to which angles are candidates (WP-1929's "every free angle is a candidate").
- The traced backends.
- A sign check in the verdict (2026-11-02, task 1). No fit on main reaches a maximum the test
  passes wrongly. The condition: if the analytic angle column is ever let through
  `_moment_reach_ok` (the seeding PR #1206 proposes), re-run task 1's six deep starts under
  it. A stall on a maximum deeper than the cut would then make the sign check live. The
  check belongs at the **stop**, never at the stationary point: from φ = 0.047 the Newton
  step lands on the maximum at φ = 0, and that pass is correct.

## Tasks

- [x] Reproduce: a fit started on a maximum along one moment angle, and what `stationary_angle_test` returns for it today. If it passes, keep it as the failing test; if it does not, record why and re-rate to P3. — *2026-11-02: no fit on main stops there (forward-difference columns walk off); the one stall the declined analytic arm produces passes correctly, at 0.000 against a cut of 2.71. Re-rated P3; Context's correctness bullet has the numbers.*
- [ ] Analytic angle columns and second-derivative block from `d_magnetic_f2_d_dofs`, extended one order, with an exact oracle.
- [ ] `_joint_newton` reads the analytic block where the branch applies, FD elsewhere.
- [ ] Tests (agreement with the FD block; evaluation counts at k = 2, 4, 8; verdicts unchanged on the two acceptance files) + obs/calc/diff PNGs to `tests/output/`
- [ ] Skill: none expected (no new verb or code).

## Acceptance

The analytic block agrees with the exact oracle to round-off. Every verdict in the two
acceptance files is unchanged. The k = 8 synthetic test spends at least 10× fewer residual
evaluations than at the WP's start.

```sh
.venv/bin/python -m pytest tests/test_stationary_moment_angle.py tests/test_magnetic_moment_frame.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Q. Huang et al., *Phys. Rev. B* **55**, 14987 (1997) (the LaMnO₃ data in the GSAS-II tutorial).
- S. V. Gallego et al., *J. Appl. Cryst.* **49**, 1750 and 1941 (2016) (MAGNDATA).
- Issue #1207; PR #1206.

## Handover log

- **2026-11-02** — task 1 (reproduce), PR #1320. The reported defect does not happen on main.
  The stationary-angle test cannot tell a maximum from a minimum, as the issue says. But no
  fit on main ever stops on a maximum along a moment angle. The solver's angle columns are
  forward differences, and those push it off such a point. The one stall that could be
  forced, with the analytic angle column #1206 declined, passes the test correctly: the
  maximum there is shallower than the data can resolve. So the correctness half is gone, the
  WP is P3, and what is left is the cost half: about 85-93 % of a moment-only fit once eight
  or more angles are free. *Done:* Context's correctness bullet carries the measurement as a
  dated "superseded in part" note. The Goal, Tasks and Acceptance lose the sign check. The
  sign check becomes a non-goal with its condition. The title follows the narrower goal; the
  filename is kept so links stay live. *Measured* (macOS arm64, `[dev]`, tree `a8f679858`;
  probes in the maintainer-local `~/.cache/ghostshift/rietx/wp-2068/probe/`): six one-site
  starts exactly on a direction that is a maximum (truth tilt or azimuth 0.05-0.8 rad, Pnma
  fixture, seed 2) all converge to χ²_red 1.031-1.033, about 1 s a fit. The frame fixture's
  PLAN_2 and PLAN_3 reach φ = 0.0470 under LM and TRF. Under the analytic angle column
  (`_moment_reach_ok` patched to accept a lone angle), PLAN_3 from β₀ = 101.0° and 100.9°
  stops at φ = −5e-17, χ²_red 0.97951 against 0.97821, and the test passes it at 0.000. From
  the minimum it reads 0.137, cut 2.71. The two acceptance files pass on the tree (27 passed,
  2:14). Under the patch, 2 fail and 25 pass: `test_the_written_back_moment_is_the_fitted_one_after_the_angle_moved`
  `[101.1]` and `[103.0]`, the pinned |m| 3.1772. Those two rows are the existing guard
  against a change that lets a fit reach the stall, so no new test was added. *Not done:*
  tasks 2-4, the analytic second-derivative block and its evaluation counts. *Settled by
  Claude* under the WP's own written branch for a non-reproduction (re-rate P3, cost half
  only): dropping the sign check from the goal. The alternative was keeping it as cheap
  insurance; it was dropped because no measured fit reaches it and a guard nothing fires is a
  declared claim with no writer. *Forward:* WP-1327's `### Inherited` has the measurement and
  the condition, for its angle-seed PR. *Next:* nothing urgent. Whoever takes the cost half
  starts at task 2. The reporter's k = 2, 4, 8, 16 table in Context is the baseline to beat,
  re-measured first on the then-current tree.
- **2026-10-31** — created, from the 2026-10-31 issue triage (issue #1207). Checked against the tree at d87c8cc91: `stationary_angle_test`, `_joint_newton`, `_half_widths` and `STATIONARY_ANGLE_MAX_ITER` = 8 exist as the issue describes, and #1206 is merged; the maximum-passes case and the cost table were not re-run. No open WP owns it: WP-1929 built the test and is closed; WP-1327's Jacobian work covers first-derivative columns only.
