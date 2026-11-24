# WP-1948 — a public objective for an outside optimiser

Milestone: unscheduled · Status: ⬜
Track: Candidates — named on a use case, not yet on a measurement
Depends on: 1947 (the evaluation without a solve); 1938 (the parameter coordinates)
Priority: P4 2026-10-11 — one embedder drives the pattern half through private names and pins `rietx<1.6` (P3 by the rubric), down a rung until 1947 lands; 1938 settled θ as physical units (#883)

## Goal

A caller who minimises their own objective (for example χ² plus a
force-field energy) gets the pattern half from a public object: χ² and its
gradient over a named free set, the starting vector and its paths, the
decode to physical values with its Jacobian, and a way to recompile when the
cell has moved far.

## Context

**The report (issue #899).** An application ("Crystal Builder") runs
"Rietveld with energies": scipy L-BFGS over rietx's θ (atom steps along
their allowed directions, optionally the free cell parameters), minimising
(1−w)·χ²/χ²₀ + w·(E−E₀)/ΔE. The pattern half imports private names:

```python
table = ParameterTable(refinement.structure, refinement.instrument)
model = compile_model(structure, instrument, pattern, mode="rietveld",
                      moving_paths=set(table.moving_paths))
residual = least_squares._make_residual(model, table)
jacobian = least_squares._jacobian_for(model, table, "numpy")
# χ² = r·r, ∇χ² = 2Jᵀr
```

plus `table.x0()`, `table.decode(θ)`, `model.evaluate(...)` and the model's
`tt`, `y_obs` and `sigma`. They pin `rietx<1.6` because of it. They ask for
`refinement.objective(pattern, free=[paths])` with four parts: value and
gradient (or residual and Jacobian); `x0`, `paths`, `decode(θ)` and
`y_calc(θ)`; ∂decode/∂θ (they finite-difference `decode` today); and an
option to recompile the hkl list and windows once the cell has moved. They
leave two questions open: θ internal or physical, and bounds for L-BFGS-B.

**Checked at `d80ca5f4`.**
- None of `compile_model` (`model/forward.py:3391`), `_make_residual`
  (`optimize/least_squares.py:564`), `_jacobian_for` (`:1220`) or
  `ParameterTable` is exported. `Refinement.parameters()` lists rows, not θ.
- The reporter's recipe is right. Freeing `phases.0.cell.a` and
  `phases.0.scale` on a synthetic LaB6 pattern, 2Jᵀr agrees with central
  differences of r·r to 1.9e-6 and 2.2e-11 relative.
- **∂decode/∂θ exists.** `ParameterTable.local_jacobian(θ)`
  (`params/vector.py:2121`) returns ∂p_phys/∂p_free and handles derived rows
  exactly. It equals the finite-difference Jacobian of `decode` only after
  each column is multiplied by `dphys_dinternal` (1.4e-10 with the chain
  factor, 1.0 without). The scale column is softplus, so the reporter's
  finite differences are exact only where the transform is the identity.
- **Bounds.** `bounds()` (`vector.py:3258`) goes through `internal_bounds`
  (`params/transforms.py:64`), which maps a softplus lower bound ≤ 1e-12 to
  −∞. Both columns above came back (−∞, +∞), so the scale has no floor in
  those coordinates. `bounds()` also adds solver windows (`cell_window`,
  the strain and size caps), so the declared bounds and a stage's bounds
  differ.
- **Recompiling.** Frozen-per-stage discreteness (root CLAUDE.md
  invariant) means the hkl list and windows are fixed for one compile.
  `FROZEN_COMPILE_STALE` (`refine.py:4726`, threshold
  `FROZEN_COMPILE_CHI2_REL = 1e-2` at `:7078`) is the measured staleness
  test. On the LaB6 toy, a compile frozen at a = 4.1606 Å and evaluated at
  +0.02 Å matches a fresh compile's χ² to five digits. At +0.10 Å it reads
  18 % low, and at +0.30 Å the windows lose the peaks (1.2e6 against
  1.19e9). So a recompile has to return a **new** objective. Recompiling
  inside one changes the function under the optimiser.

**Why this waits on WP-1938.** 1938 makes every solver column physical and
passes `min`/`max` as box bounds. Then θ *is* the values, `decode` is C·θ+d
(affine except derived rows, WP-1804), ∂decode/∂θ is `local_jacobian` with
no chain factor, and the L-BFGS-B bounds are the declared ones. That
answers both open questions. An objective built first would document a
coordinate system 1938 deletes.

**Why this builds on WP-1947.** 1947 exposes the compiled model read at its
values, with no solve. This object is that plus a gradient, a free set and
a recompile.

**The surface rule.** The python API is the one integration surface (root
CLAUDE.md, WP-1303). This is a python object on it, so no second surface is
in question. 1303's real demand is evidence of use, and here a named
embedder pins an old version to reach private names.

**A second consumer.** WP-1515 (⬜, scoping structure solution) measured its
source run calling `predict()` at 20-35 ms an evaluation. A structure-solution
search is the next caller of a cheap objective. WP-1513 carries a skill row
for "writing your own search loop".

## Non-goals

- The evaluation without a solve (WP-1947).
- Changing the solver's coordinates (WP-1938).
- A force-field term inside rietx. The energy stays the caller's.

## Tasks

- [ ] Read WP-1938's landed coordinates, and record here what θ is and what
      `bounds` returns.
- [ ] Decide the shape and record it as `Decided YYYY-MM-DD:`: a method on
      `Refinement` (`objective(data, free=..., mode=...)`) returning an
      object with `x0`, `paths`, `bounds`, `residual(θ)`, `jacobian(θ)`,
      `value_and_grad(θ)`, `decode(θ)`, `decode_jacobian(θ)` and
      `y_calc(θ)`. Say what `free=` does with a tied or held path
      (`set_vary`'s return is the authority).
- [ ] `recompile(θ)` returns a new objective at the decoded values, and the
      object says when it is stale on the `FROZEN_COMPILE_STALE` test.
- [ ] Tests: `value_and_grad` against central differences on a small phase,
      and an L-BFGS-B run through the object reaching the same χ² as `fit`
      on the same free paths (the reporter's two checks). obs/calc/diff
      PNGs to `tests/output/`.
- [ ] Manual (`using/`) and the generated skill API index.
- [ ] Skill: WP-1513's "writing your own search loop" row names the object.
      Nothing else expected.

## Acceptance

An L-BFGS-B minimisation driven only through public names reaches the χ² of
`fit` on the same free set within the fit's own tolerance, and
`value_and_grad` agrees with central differences.

```sh
.venv/bin/python -m pytest tests/test_manual_api.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #899.
- Byrd, R. H., Lu, P., Nocedal, J. & Zhu, C. (1995). *SIAM J. Sci. Comput.*
  16, 1190 — L-BFGS-B.

## Handover log

- **2026-10-11** — created, from the 2026-10-11 issue triage (issue #899).
  Checked against the tree at `d80ca5f4`: none of the four names the
  reporter imports is exported, their 2Jᵀr gradient agrees with central
  differences, and `local_jacobian` gives ∂decode/∂θ once the transform
  factor is applied. No open WP owns it: WP-1515 scopes and builds nothing,
  WP-1513 carries a skill row only, and WP-1945 is the Jacobian's build
  cost. *Next:* wait for WP-1938, then task 1.
