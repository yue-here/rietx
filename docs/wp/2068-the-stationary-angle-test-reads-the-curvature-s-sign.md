# WP-2068 — The stationary-angle test reads the curvature's sign, analytically

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: — (1327 soft: the moment derivative `d_magnetic_f2_d_dofs` from #1206, merged 2026-10-31)
Priority: P2 2026-10-31 — a fit stopped on a maximum along a moment angle passes the test with no flag, on a path few fits run; unreproduced, so task 1 reproduces it, and a non-reproduction leaves only the cost half, P3

## Goal

`stationary_angle_test` builds the moment-angle columns and their second-derivative block from
the analytic moment derivative instead of central differences, and reads the sign of the
curvature, so a fit that stopped on a maximum along an angle no longer passes as stationary.

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

## Tasks

- [ ] Reproduce: a fit started on a maximum along one moment angle, and what `stationary_angle_test` returns for it today. If it passes, keep it as the failing test; if it does not, record why and re-rate to P3.
- [ ] Analytic angle columns and second-derivative block from `d_magnetic_f2_d_dofs`, extended one order, with an exact oracle.
- [ ] `_joint_newton` reads the analytic block where the branch applies, FD elsewhere; the verdict checks the curvature's sign.
- [ ] Tests (the maximum case; agreement with the FD block; evaluation counts at k = 2, 4, 8) + obs/calc/diff PNGs to `tests/output/`
- [ ] Skill: none expected (no new verb or code); a new diagnostic code for a maximum would add its row.

## Acceptance

A fit stopped on a maximum along a moment angle no longer passes the test. The analytic block
agrees with the exact oracle to round-off. The k = 8 synthetic test spends at least 10× fewer
residual evaluations than at the WP's start.

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

- **2026-10-31** — created, from the 2026-10-31 issue triage (issue #1207). Checked against the tree at d87c8cc91: `stationary_angle_test`, `_joint_newton`, `_half_widths` and `STATIONARY_ANGLE_MAX_ITER` = 8 exist as the issue describes, and #1206 is merged; the maximum-passes case and the cost table were not re-run. No open WP owns it: WP-1929 built the test and is closed; WP-1327's Jacobian work covers first-derivative columns only.
