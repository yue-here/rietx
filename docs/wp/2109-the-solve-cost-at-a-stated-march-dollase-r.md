# WP-2109 — the solve cost at a stated March-Dollase r

Milestone: structure-solution · Status: ✅ 2026-11-07 — closed by Yue; PR #1420 (`c1596ff82`) gives χ², s and ∂χ²/∂r at a stated March-Dollase (r, axis); nothing calls it until S9 (#677)
Depends on: 1902 (shipped, the cost)

## Goal

`SolveCost` evaluates χ² at a stated March-Dollase r and axis for the solved phase, with
∂χ²/∂r. M is not rebuilt, and Ω·F at that r agrees with Rietveld-mode `evaluate`.

## Context

**Where this comes from.** @mustachefeeling proposed this on #562 on 2026-10-30, and
WP-1515's entry of 2026-10-31 recorded it. `SolveCost` folds each reflection's
preferred-orientation factor into Ω at extraction. So the cost is a function of |F|² at one
texture. The proposal's motivating measurement is the contributor's private run, and it was
not re-run here. On a strongly textured molecular pattern, their body search outside the
package reached the structure's basin only once r was a search coordinate. With r held at
the extraction's value, no seed came near it. Nothing in this WP's acceptance rests on that
run.

**Placement: in `SolveCost`, never in the engine.** Settled by Claude under Yue's
2026-11-05 instruction to action clear calls. The alternative was a factor the engine
applies to |F|². The contributor asked which on #562, and the 2026-10-31 reply deferred the
answer to S9. Four grounds, each checked below.
- `SolveCost` folds the factor in at construction, so that is where the extraction's r can
  be read.
- Ω at a new r is Ω·D, so M need not be rebuilt.
- The free-intensity floor does not move, so `ratio` stays comparable across r.
- `model/preferred_orientation.py` stays the one formula. An engine holding its own factor
  would need the extraction's r and orbit too.

**The form.** Let T(a, r) be the per-reflection factor, the mean of `march_term` over the
reflection's orbit, with a the axis. Let T₀ be its value at the extraction's a₀ and r₀.
`phase_peaks` multiplies T into a line-independent `base` before any per-line term, so T is
the same on every emission line. Then, with D = diag(T(a, r)/T₀),

    Ω(a, r) = Ω·D,    M(a, r) = D·M·D,    b(a, r) = D·b,    c unchanged,
    χ²(F; a, r) = χ²(D·F),

and the scale returned beside χ² is the scale at r. D is positive for every r > 0, since the
March bracket is positive. Its derivative is one more matvec. With G = D·F, s the
closed-form scale and D′ = diag((∂T/∂r)/T₀),

    ∂χ²/∂r = −2s·(b − s·M·G)ᵀ(D′·F).

The ∂s/∂r term drops because χ² is stationary in s. Where s = 0, χ² = c and the derivative
is 0. The function has a kink at that boundary.

The floor is the minimum over free I. D is invertible, so I ↦ D·I maps that set onto itself
and `chi2_floor` is the same at every r. So χ²(F; a, r) ≥ `chi2_floor` holds throughout, and
`ratio` and the engine's J = χ²/χ²_floor (`solve/tempering.py`) stay comparable. An engine
gets the value from `chi2_batch(D·F)` with no new code.

**What the tree adds to the proposal**, checked at `85ce3f287`.
1. `SolveCost` does not hold r₀, a₀, the orbit or G\*. `from_model` has them in `values` and
   `model.phases[phase]`, and drops them. The dataclass needs them as new fields, or it
   cannot state a ratio.
2. The orbit does not exist in the common case. `compile_model` freezes `po_members`,
   `po_seg` and `po_counts` only where the phase declares `preferred_orientation`. An
   extraction with no block has T₀ ≡ 1 and no orbit. `CompiledPhase` holds no space group,
   and `from_model` takes no structure. So the group has to come in from outside:
   `resolve_group(phase.space_group, phase.symmetry_operations)`, `reflection_orbits` and
   `orbit_layout`, as `compile_model` does. `from_pawley` holds the structure. `from_model`
   needs a keyword for it.
3. The entry points are one layer up. `march_term` is per equivalent, and the factor is its
   orbit mean, so the code calls `march_dollase_factors` and `march_dollase_and_dr`. Those
   are built on `march_term` and `march_term_and_dr`, so the formula stays single.
4. The extraction never fitted r₀. A Le Bail or Pawley compile applies no March factor, so
   r's column is dead there (`refine.py`, 1.7e-13 from its start). r₀ is the value the
   structure declares, read by the Rietveld-mode compile `from_pawley` makes.
5. `intensities` (I_P = M⁺b) belongs to r₀ and does not carry across r. M is singular under
   exact overlap, and M⁺b is the minimum-norm solution, which does not transform by D⁻¹.
   Only the floor is invariant.
6. A spherical-harmonics `texture` block on the solved phase is folded into Ω the same way.
   `Phase` refuses that block beside March-Dollase, so a stated r over it is a model the
   schema refuses. The evaluation refuses it too.
7. `tests/test_solve_cost.py` has no preferred-orientation arm. The fold is stated in the
   docstring and has no test, so the first verification row below is new coverage of
   existing behaviour.
8. The r belongs to the solved phase alone. A `"scale"` nuisance phase's own texture sits
   inside X and does not move.

**Measured, a probe outside the tree.** Run at `85ce3f287` on an arm64 Mac (Python 3.12,
worktree venv). FAP has 329 reflections and a Kα₁/Kα₂ doublet, and NAC has 129 and one line.
Each case compared a cost rebuilt at (a, r) against the scaled cost, background projected.
Cases: no block to (100) r = 0.6; (100) r₀ = 0.8 to 0.6; (100) r₀ = 1.3 to 0.75; (001)
r₀ = 0.8 to (100) r = 0.6. In the first three, D ran from 0.44 to 1.97. The fourth
measured b, the floor and χ² only.

| Quantity | Worst disagreement |
|---|---|
| M, relative to max\|M\| | 3.2e-15 |
| b, relative to max\|b\| | 8.6e-15 |
| c | 0 |
| `chi2_floor`, relative | 9.7e-14 |
| χ²(F), in units of c | 6.6e-16 |
| scale, relative | 8.6e-16 |
| ∂χ²/∂r against a central difference at h = 1e-5·r, relative | 2.8e-9 |
| max\|D·I_P(r) − I_P(r₀)\| / max\|I_P(r₀)\|, which is why item 5 holds | 3.2e-3 to 6.2e-3 on FAP, 3.6e-2 to 0.43 on NAC |

This checks the algebra. It does not run the Ω·F row against `evaluate`, which is still
owed.

The probe also sized two wrong factors, in χ² against the rebuilt cost, in units of c. The
existing bar on χ² is 1e-13·c.
- **T(a, r) without dividing by T₀**: 3.9e-2 to 1.1e-1 on FAP, 4.8e-4 on NAC, at r₀ = 0.8.
  At r₀ = 1 or with no block, T₀ ≡ 1 and this arm cannot fail.
- **T from the representative alone, no orbit mean**: 1.5e-2 on FAP at (100), 1.3e-3 on NAC
  at (100). On FAP at (001) it measures 1.3e-16. Every equivalent there sits at one angle
  from the unique axis, so this arm cannot fail.

So the wrong-factor arm needs r₀ ≠ 1, and FAP needs an axis off its unique axis.

**Tier.** Physics and algebra: Dollase (1986) for the factor, and the rest is derived above.
This WP adds no default, threshold or automatic action. Nothing new needs a row in
`rietx._audit`. The reference is Rietveld-mode `evaluate` on the public NAC and FAP data.
`rietx.solve` is not exported, so no name joins the manual's surface and no Theory equation
is owed yet. The form goes in `solve/cost.py`'s docstring.

## Non-goals

- Whether, and from where, a search moves r. That stays with S9 (#677). WP-1997's non-goal
  on preferred orientation is unchanged. Nothing calls the new evaluation until then.
- A derivative in the axis. The axis is integer and stated.
- A stacked derivative for replicas, and a compiled kernel for one. S9 adds them if it needs
  them.
- Spherical-harmonics texture in the solve cost.

## Tasks

- [x] `SolveCost` keeps a₀, T₀, the orbit layout and G\* from construction. `from_pawley` supplies the group, and `from_model` takes it by keyword
- [x] The ratio D and D′ at a stated (r, axis), through `march_dollase_and_dr`; a refusal for r below `MARCH_R_MIN`, for a `texture` block on the solved phase, and for a cost built without a group
- [x] χ², s and ∂χ²/∂r at a stated (r, axis), through the existing `chi2`
- [x] Tests: the Acceptance rows, each revert-checked as `tests/test_solve_cost.py`'s header says; the header gains the new row's numbers
- [x] `solve/cost.py`'s docstring: the form above, and the note that `intensities` belongs to r₀
- [x] Skill: none expected, as `rietx.solve` is not public; say why at handover

## Acceptance

`.venv/bin/python -m pytest tests/test_solve_cost.py` passes with these rows.
- **Ω·F at r against `evaluate`.** Ω·D·F matches Rietveld-mode `evaluate` with
  `PreferredOrientation` at that r, at ten moved structures, on NAC and on FAP, to
  `OMEGA_BAR` (1e-14 of max|y|). The extraction is covered both with no block and with
  r₀ ≠ 1. FAP's axis is off its unique axis.
- **The wrong-factor arms fail that row.** Both the arm without T₀ and the representative-only
  arm fail by the margin the file's existing arms use, `> 1e3 * OMEGA_BAR`. The cases are the
  ones above where each arm can fail.
- **The identity at the extraction's own r.** At (a₀, r₀), D is exactly 1 and the result
  equals `chi2` bit for bit. With no block the same holds at r = 1 on any axis.
- **∂/∂r against finite differences.** Central differences to 1e-7 relative, 35× above the
  probe's worst. r enters nonlinearly, so the step is stated and the error is seen to fall
  with it.
- **The floor.** A cost rebuilt at r has the same `chi2_floor` to 1e-12 relative, 10× above
  the probe's worst.

## References

- March, A. (1932), *Z. Kristallogr.* 81, 285.
- Dollase, W. A. (1986), *J. Appl. Cryst.* 19, 267.
- Issue #562, the comment of 2026-10-30. Issue #677 (S9).
- WP-1902 (the cost), WP-1515 (the scoping), WP-1997 (the engine).

## Handover log

- **2026-11-07** (rulings, PR #1455) — closed. Decided 2026-11-07 (Yue): close it. The
  solve cost can now say what χ² would be at a stated March-Dollase r and axis, and how
  fast it changes with r. No search in the package moves r yet. That waits on S9 (#677).
  *Checked before closing:* all six tasks are ticked, and PR #1420 merged on 2026-11-05.
  The file had no `### Inherited` section. The `Priority:` line is deleted, and the
  narrative moved to `docs/milestones/v1.12.md`. No WP depends on this one.
  *Carried to S9:* the two review points in the entry below (orbit layouts built at every
  extraction, and the redundant `group=`) still have no ruling. No S9 WP exists, so they
  moved to WP-1515's `### Inherited`, the open WP that cuts S9.
  *Next:* none here.

- **2026-11-05** (post-merge record) — PR #1420 merged at `c1596ff82`. Every task
  was already ticked, so this entry ticks nothing. The merge makes χ² and ∂χ²/∂r
  available at a stated March-Dollase r and axis. It does not make a search move
  r, and nothing in the package calls the new methods.
  *Status:* `/pr-review` step 9 keeps a close with the maintainer, so the glyph
  stays 🔄 until Yue sets ✅. The close also deletes the `Priority:` line and moves
  the narrative to the release record (ROADMAP rule 5).
  *After the entry below:* commit `115169d4a` landed on the PR.
  `texture_ratio` now raises a plain `ValueError` on a non-integer axis, which it
  used to truncate to int64, and on an infinite r, which used to give NaN.
  `TextureRefused`'s four reasons did not change. `tests/test_solve_cost.py`
  collects 63 tests on `main` (arm64 Mac, worktree venv), up from the 58 below.
  *Owed to S9 (#677):* `from_model` builds the orbit layout whenever it gets a
  `group`, and `from_pawley` always passes one. So every extraction pays for orbits
  that nothing reads until S9 exists. S9 decides whether to build them at first
  use instead. The contributor's PR comment of 2026-11-05 left this point to
  review, with a second one, a redundant `group=`. Neither has a ruling. Neither
  appears on #677, and no S9 WP exists yet, so this entry holds both until S9 is
  cut.
  *Next:* Yue closes this WP. Nothing else, until S9 decides whether a search
  moves r.

- **2026-11-05** — built. `SolveCost` can now say what χ² would be if the solved phase
  were textured at a March-Dollase r and axis that the caller states, and how fast χ²
  changes with r. It does this without rebuilding the quadratic form: each reflection's
  column is rescaled by the ratio of the new texture factor to the one folded in at
  extraction. Nothing in the package calls it, and nothing chooses r. Searching over r stays
  with S9 (#677).
  *Done:* `SolveCost.texture_ratio(r, axis)` → (D, D′); `chi2_at_texture(f2, r, axis)` →
  (χ², s, ∂χ²/∂r), through the existing `chi2`; new fields `gstar`, `po_axis`, `po_r`,
  `po_factors` (T₀), `po_orbits`, `sh_texture`; `from_model(..., group=)`, with
  `from_pawley` passing `resolve_group` of the solved phase. Refusals raise
  `TextureRefused` (a `ValueError`) with a `.reason` of `r_below_floor` (also NaN),
  `texture_block`, `no_group` or `no_axis`. `no_axis` is new beside the task list: with no
  block there is no a₀ to default to. The module docstring carries the form, the floor
  invariance and the r₀-only reading of `intensities`.
  *Measured* (arm64 Mac, Python 3.12, worktree venv `[dev]`, tree b282a772a + this
  branch): Ω·D·F against Rietveld `evaluate` ≤ 1.1e-15 of max|y| over NAC and FAP, five
  extraction cases, r ∈ {0.6, 1.0, 1.45}, ten moves each, D from 0.31 to 10.2. Wrong arms:
  no ÷T₀ ≥ 6.6e-2 where it can fail (≤ 8.2e-16 with no block, asserted as such);
  representative-only ≥ 0.33 (≤ 9.1e-16 at r = 1 and on FAP's (001), where it equals the
  mean). Floor of a cost rebuilt at r: 9.7e-14 relative; χ² 4.0e-16·c. Derivative at
  h = 1e-5·r: 3.3e-10 relative, falling with h. Every row was revert-checked (ten mutants,
  each failing its aimed test). `tests/test_solve_cost.py`: 58 tests (+27). Fast selection
  on the Mac (pearl offline): 13954 passed, 239 skipped, 36 xfailed in 601.74 s. Ruff clean;
  `tests.audit_delta`: no row changed; `tests.reader_output`: no change.
  *Gotchas:* `chi2` of a strided view and of a contiguous copy can differ by an ulp (two
  numpy dot paths), so the bit-identity test passes `np.ascontiguousarray`. The
  representative-only arm is exact wherever its numerator and denominator both equal the
  orbit mean: at r = 1, and on FAP's unique axis.
  *Skill:* none, since `rietx.solve` is not public.
  *Next:* review and merge; then nothing until S9 (#677) decides whether a search moves r.

- **2026-11-05** — filed from WP-1515's 2026-10-31 entry, PR #1414. No open WP owns this:
  WP-1997 fences preferred orientation out, WP-1515 builds nothing, and S9 has no WP yet. The
  block 19xx is full, so the number is the next free one in the newest block. *Next:* the
  first task, whenever someone takes it up. The contributor offered to build it on #562.
