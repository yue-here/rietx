# WP-2239 — a joint stage seeds and holds a Stephens block as a single fit does

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: —
Priority: P3 2026-11-22 — a joint fit ignores `Stage.strain_seed` and holds no strain cone, and nothing says so; on a path few fits run, and a block declared on the isotropic ray by hand is the workaround

## Goal

A joint fit (`MultiHistogramRefinement.fit`) treats a freed Stephens block the
way `Refinement.fit` does. A stage's `strain_seed` puts an all-zero block on
the isotropic ray and records it in `StageResult.seeded`. The default LM step
holds the strain cone, and the texture positivity rows beside it, in every
histogram.

## Context

Issue #1663 (mustachefeeling, 2026-11-17). The defect travelled three WPs
before it got one of its own. WP-2002 found it (PR #1113). WP-1467's close
carried it to WP-1946's `### Inherited`. WP-1946 is closing 🛑 in PR #1662,
whose body names #1663 as left over.

**What a Stephens block needs at the start.** The anisotropic strain width
goes as √σ²(M), and σ²(M) is linear in the fifteen S_HKL coefficients. At
S ≡ 0 the square root has unbounded slope. So a stage that frees an all-zero
block first moves it onto the isotropic ray, S = ε²·[M²], the one point of the
allowed subspace with σ²(M) > 0 for every reflection.
`ParameterTable.seed_stephens` (`params/vector.py:4221`) does this. It touches
only a phase whose whole block is still zero, so a deliberate start is never
overwritten.

**The two runners disagree.** Line numbers are as of `2ce794581`.
- `refine._run_stage` (`refine.py:5272-5294`) calls `seed_floored` for
  `Stage.seed`, then `seed_stephens` for `Stage.strain_seed`. It adds the
  strain rows to `seeded`, which becomes `StageResult.seeded`. It also adds
  their phases to `seeded_phases`, so the support hold drops the previous
  answer's significance for them (WP-1523).
- The joint stage loop (`multi.py:2061-2063`) calls
  `self.mtable.seed_floored(freed, stage.seed)` alone. `multi.py` never reads
  `strain_seed`. `MultiParameterTable` (`params/multi.py`) has
  `seed_floored` (`:1364`) and no `seed_stephens`.
- `StageResult.seeded`'s docstring (`schemas/results.py:1418-1435`) records
  the gap: "The joint fit's runner seeds no Stephens block".
- The joint loop's support hold reads `seeded` too (`multi.py:2099`), so the
  strain rows must enter that dict before it, as in the single runner.

**The cone is missing on the same path.** `run_least_squares` builds the LM
inequalities from `strain_cone_inequalities`,
`texture_positivity_inequalities`, the two width builders and the tied-bound
rows (`optimize/least_squares.py:3506-3511`). The joint path builds
`_joint_width_inequalities` (`:2907`, the Γ_G² and Γ_L rows per histogram,
laid on the joint columns by `mtable.col_map`) and the tied-bound rows
(`:4000-4002`). It builds no strain cone and no texture positivity row. The
manual says so (`theory/microstructure.md` § The positivity cone, the seed
and the guard: "A joint fit builds no cone under either driver"). WP-1960's
Context line saying joint fits hold no inequality at all is stale since
WP-2002 added the width rows. The width builder's shape is the template: ask
each histogram's own table and model, then move the columns.

**Sharing.** Stephens' S_HKL are λ-free, so the default `SharingMap` shares
one block across histograms (`params.multi.SIZE_LAMBDA_POWER` lists only the
size terms). The seed is a fan-out like `seed_floored`'s: a shared column is
written in every histogram or in none, in column units (root CLAUDE.md, the
size-sharing invariant). The isotropic ray reads the cell, so a per-histogram
cell (WP-1325's `SharingMap(per_histogram=...)`) gives each histogram its own
ray. That case needs a rule: seed from histogram 0's cell, or decline for a
shared block whose histograms disagree.

**Measured at `f590981ab`** (`[dev]`, darwin arm64, numpy). Probe: a cubic
`P m -3 m` phase with an all-zero block, two synthetic patterns made at
800 ppm (Cu Kα 15-80°, Mo Kα 7-36°), one stage freeing the scale and
`phases.*.microstrain.dof.*` with `strain_seed=1000`. The patterns are
`compile_model(...).evaluate` of the 800 ppm structure plus a flat 10 counts,
as `tests/test_strain_cap.py`'s `_flat_pattern` builds them.
- One iteration through `Refinement.fit` on the Cu pattern seeds
  `dof.0 = 7812.5` and `dof.1 = 3906.25`. The same stage through
  `MultiHistogramRefinement.fit` on both patterns seeds nothing
  (`StageResult.seeded == {}`).
- At 60 iterations under the default LM, the joint fit from S ≡ 0 converges
  to `dof.0 = 5043.7`, Rwp 0.100954 and 0.072712. Started by hand at 1000 ppm
  it lands at 5087.1, Rwp 0.100945 and 0.072704, and at 800 ppm at 5080.8. So
  on this fixture the ignored seed moves the coefficient by about 0.9 % and
  Rwp in the sixth decimal.
- The reporter's single-histogram brucite numbers (WP-1467, 43 reflections)
  bound the size: under LM the start moves χ²_red within 7.8939-7.8945;
  under TRF it spans 7.7965-7.9267, with 19-23 reflections outside the cone.
  A joint fit holds no cone under LM either, so the LM number is the
  optimistic one there.

**Tier.** No new judgement. The seed and the cone are the single fit's rules,
already audited (`_audit.py` rows for `Stage.strain_seed` and
`STRAIN_SEED_PPM`). This WP extends them to the second runner.

**What moves.** Every joint fit whose plan frees a Stephens block. The
shipped one is `lab_sample_refine`, whose sample stage carries
`strain_seed=STRAIN_SEED_PPM` (`strategy/staged.py:751`). A golden that
records such a fit moves, and the WP says which.

### Inherited

## Non-goals

- A formulation of the block that cannot leave the cone: WP-1946 tried it and
  closed 🛑 (PR #1662).
- TRF's cone, which stays the guard's (`STEPHENS_STRAIN_NOT_POSITIVE`) in
  both runners.
- A joint fit's guards reading every histogram: WP-2028.

## Tasks

- [ ] `MultiParameterTable.seed_stephens(scoped_paths, microstrain)`, the
      fan-out counterpart of `seed_floored`, with the per-histogram-cell
      rule decided and written in its docstring.
- [ ] Call it in the joint stage loop after `seed_floored`. Add each DOF at
      its seeded value to `seeded`, so `StageResult.seeded` and the support
      hold's `seeded_phases` read it. Rewrite the `StageResult.seeded`
      docstring's joint-fit sentence.
- [ ] Add `strain_cone_inequalities` and `texture_positivity_inequalities` to
      the joint LM rows, per histogram on the joint columns, as
      `_joint_width_inequalities` does. Rewrite the manual's joint-fit
      sentence in `theory/microstructure.md`. WP-1960 is closed, so its
      stale Context line stays as history.
- [ ] Tests: a one-histogram joint fit and `Refinement.fit` on the same
      stage write the same `seeded` mapping; a two-histogram joint stage with
      `strain_seed` starts an all-zero shared block on the isotropic ray in
      both histograms; a joint LM fit whose box-only step would leave the
      cone counts the cone block in `LSQOutcome.truncated_by`.
- [ ] Measure which joint goldens and acceptance fits move, and by how much,
      before and after, and record it in the handover.
- [ ] Skill: none expected. `references/surprises.md` says a block needs
      `Stage.strain_seed`; check it makes no joint-fit exception.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_multi_histogram.py tests/test_strain_cap.py tests/test_cross_backend.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m sphinx -W -q -b html docs/docs docs/docs/_build/html
```

## References

- Stephens, P. W. (1999), *J. Appl. Cryst.* 32, 281-289: the strain model
  and its isotropic limit.
- WP-1467 (the frozen floor), WP-1946 (the cone-free form, 🛑), WP-2002
  (the joint width rows).

## Handover log

- **2026-11-22** — created, from the 2026-11-22 issue triage (issue #1663).
  Checked against the tree at `f590981ab`: reproduced and measured as in
  § Context. No open WP owns it: WP-1946 carries it only in its Inherited
  section and closes 🛑 with PR #1662, WP-2028 is about a joint fit's
  guards, and WP-1995 about restraint rows. The joint cone and texture rows
  are its siblings on the same seam, so they come with it. Next: the first
  task.
