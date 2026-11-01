# WP-1912 — a polar axis has no origin, and the fit walks along it

Milestone: unscheduled · Status: ✅ 2026-10-23 — a polar group's floating origin can be fixed on request, by holding one atom or by restraining a weighted centroid of all of them; both stay off by default, and whether the centroid becomes the default is WP-2029
Track: What fires, and what stays silent
Depends on: —

## Goal

In a space group whose origin is free along one or more directions (a polar
axis, or P1's three), a refinement that frees atomic coordinates fixes the
origin itself, says so by name, and returns coordinates inside the range they
started in, with esds that measure what the data measures. A caller can lift
the fix.

## Context

Issue #727 (mustachefeeling, 2026-10-05). In P 6₃ m c (ZnO) each site has one
free DOF along c, and the common shift of all of them changes no intensity.
Nothing in the package fixes that origin. `ParameterTable._collect_atom_coords`
(`params/vector.py:1213`) builds each atom's DOFs from its *own* stabilizer
(`wyckoff.coordinate_basis(stabilizer_rotations(sg, xyz))`), and no code under
`src/` derives a group-level origin constraint.

**Measured at `32ef5a6`** (synthetic Cu Kα ZnO, a = 3.2499, c = 5.2066,
z(O) = 0.3826, Biso 0.55, `Dispersion()` declared, 20-140° in 0.02°, Poisson
seed 3; scripts in the 2026-10-05 triage scratch, rebuilt in a minute):

- The issue's snippet lists `phases.0.atoms.0.dof.0` and `.1.dof.0`, both
  refinable.
- Both z shifted by +0.05 change the calculated pattern by 6.2e-16 of its
  maximum. The direction is exactly flat.
- A plan freeing scale, background, cell and `phases.*.atoms.*.dof.*` from
  z(O) + 0.02 ends `converged`, Rwp 0.098616, with z(Zn) = 634.1318 and
  z(O) = 634.5125. The difference, 0.38069, is the measurement. Each z is
  quoted at ±0.00111 and `structure_to_cif` writes `634.1318(11)`.
  `HIGH_CORRELATION` and `FLAT_DIRECTION` (ρ = −1.000) fire on the result. The
  CIF carries no flag.
- `plan="mccusker_structural"` walks the same pair to 147.837 / 148.218.
- `ref.hold(["phases.0.atoms.0.dof.0"])` gives the same Rwp, z(O) =
  0.3807(22), no flat-direction rows, and `HOLD_BLOCKED_PLAN` (info). The
  ±0.0011 on each free z was half of the honest 0.0022 on the difference.

*Superseded in part, 2026-10-12 (at `e1d19359`).* The walk now depends on
the driver. On the same fixture under `mccusker_structural` the default LM
driver moves the pair together by 0.010 (z(Zn) = 0.0101, z(O) = 0.3925),
while TRF still walks it to z ≈ 150. Both quote ±0.00029 on each z and fire
`FLAT_DIRECTION`. The half-the-honest-esd finding holds on both drivers.

**The floating-origin directions are already computable.** The same
`wyckoff.coordinate_basis`, given the rotation parts of *every* operation of
the group instead of a site's stabilizer, returns the subspace of translations
that commute with the point group, which is the continuous part of the
Euclidean normalizer. Measured: [001] for P6₃mc, Pna2₁, P4mm and R3m:H;
[010] for P2₁; [100] and [001] for Cc; all three axes for P1; none for
P2₁2₁2₁, Pnma and Fd-3m:1. No ITA table is needed. Cell setting does not matter,
because the rotations are read in the setting the phase states.

**Two shapes of fix, and the choice is the maintainer's (task 1):**

1. **A hold on one coordinate** per free origin direction (the issue). The
   cheapest form. The held atom then has no esd, and the others carry the
   relative uncertainty. The issue takes "the first atom with a free polar
   DOF"; the conventional choice is the heaviest scatterer, which conditions
   the rest best. Careful: `Refinement._user_holds` is the *caller's*
   authority (WP-1435) and `unhold` lifts it; a table-derived fix is a
   different population. `ParameterRow.needs_held_cell` (the flat
   wavelength-against-cell direction) is the precedent: a dynamic,
   table-derived held-reason with its own `held_because` text.
2. **A floating-origin constraint on a weighted centroid**: Σᵢ wᵢ·δᵢ = 0 along
   each free direction, wᵢ ∝ the atom's scattering power × multiplicity. This
   is what SHELXL does with a restraint (Flack & Schwarzenbach 1988); here it
   can be exact, because the condition is affine and C already carries affine
   rows. One DOF becomes a tie on the others, every atom keeps an esd, and no
   atom is singled out. It touches the Jacobian gate: the tied DOF's column
   reaches every atom on that axis, so `_column_extras` must see it (root
   CLAUDE.md, "An analytic Jacobian branch claims what one parameter *name*
   reaches").

Either way the rules that already govern coordinate DOFs apply. A DOF is
*relative* and anchored (WP-1432): `rebase_anchored_dofs` and
`anchored_dof_paths` must cover whatever this adds. A user tie onto a
coordinate DOF, or a named variable driving one, can already fix the origin.
The derivation must then add nothing, or it over-constrains.
`moving_paths` / `column_reach` (WP-1342), not names, decide what is free.
A phase with no free polar DOF needs nothing, and a phase with one such atom
has exactly one flat direction, so the same rule holds it.

**What moves:** the free-parameter count of every fit that frees coordinates
on a polar phase, so N − P, GoF and ΔBIC shift by one per direction. Zincite
appears in `tests/test_acceptance_qpa_roundrobin.py`, `tests/test_scale_b_ridge.py`
and the dispersion suites. Check which free its DOFs before claiming
bit-identity anywhere.

Licensing: SHELXL is closed. Use the paper only.

**Where the default stands (2026-10-13, folded from § Inherited).** The
reporter withdrew the hold-one default on #727 (2026-10-12) and asked for the
floating-origin restraint on a weighted centroid (Flack & Schwarzenbach 1988,
*Acta Cryst.* A44, 499-506): it chooses no atom, does not depend on atom
order, leaves every atom an esd, and is one rule for every case
`floating_origin_basis` returns. The maintainer's two comments on #727 that
day disagree (07:38 "the hold becomes the default now"; 15:16, after #929
merged off by default, "the default is still to decide"). Resolved in session
the same day: **the aim is to move quickly to the centroid**, so the hold
stays opt-in and the default is not flipped twice. The centroid lands as a
second value of `Phase.floating_origin`, built as the paper's restraint in
a row block of its own (task below; it needs nothing from WP-1942's unbuilt
user-declared restraint), is measured against the hold on ZnO, Cc and P1, and becomes the candidate
default. A default change moves the reported origin and the spread of esds,
never the structure, Rwp or any interatomic distance, and goes in the release
notes. *Decided 2026-10-23 by the maintainer:* both modes stay opt-in and off
by default, and whether the centroid becomes the default is WP-2029.

## Non-goals

- Discrete origin choices of non-polar groups (`:1`/`:2`); nothing floats.
- Choosing the origin for a *structure solution* search (1515's scope).
- The magnetic moment: an axial vector, not a position, so it has no origin.
- Changing `FLAT_DIRECTION` or `HIGH_CORRELATION` (1460 owns their dedup).

## Tasks

- [x] Decide with the maintainer: hold (and which atom) or centroid
      constraint; whether a caller lifts it with `unhold` or a new verb;
      the diagnostic's name (`ORIGIN_FIXED_ON_POLAR_AXIS` proposed) and level.
      *Decided 2026-10-06, through draft PR #749: a hold, on the first atom
      whose free DOF runs along the direction, lifted with `unhold`, and
      reported as `ORIGIN_FIXED_ON_POLAR_AXIS` (info), with
      `ORIGIN_NOT_FIXED` (warning) where no atom's DOF runs along it. For
      now it is an option the caller invokes
      (`Refinement.hold_floating_origin()`). Applying it by default in the
      table is not decided. The centroid restraint (Flack & Schwarzenbach
      1988, SHELXL's default) may come later as a second mode, because it
      keeps an esd on every atom and does not depend on which atom is held.*
- [x] `crystallography.wyckoff`: the group-level free-origin basis, tested on
      the ten groups above and on every gemmi setting, asserting **which**
      directions, not how many (root CLAUDE.md, the cell-ties rule).
      *Done 2026-10-12: `floating_origin_basis` landed with #749; the tests
      now name all ten groups, and every one of gemmi's 564 settings is held
      to a physics oracle (a site moved along each row and re-expanded leaves
      40 intensities unchanged, a shift off the span changes them, and the
      dimension matches the point-group symbol's polar class). A basis with
      its axes permuted fails at `P 1 2 1`. A basis built from transposed
      rotations gives the same answer on all 564, so the Rᵀ trap does not
      bite here.*
- [x] `ParameterTable`: the fix applied in the table, never at call sites;
      skipped where user ties or variables already fix the origin; the
      `ParameterRow` held-reason or tie, with its `held_because` text and its
      writer named (WP-1076).
      *Done 2026-10-12, behind a switch that is off by default:
      `Phase.floating_origin = "hold"` (schema 0.52). `ParameterTable`
      holds the first DOF running exactly along each floating direction
      through `Entry.held`, re-decided at every build, tie and hold. It adds
      nothing where an exact solve on the affine block finds the caller's
      ties or holds have fixed the origin already
      (`ParameterTable._origin_floats`). `ParameterRow.origin_axis`, written
      by `Refinement.parameters` from `ParameterTable.origin_holds`, gives
      the row its own `held_because`. `hold_floating_origin()` now sets the
      field, and `unhold` on a held DOF sets it back to `None`. A joint
      fit's per-histogram tables hold the same atom.*
- [x] The diagnostic naming the phase, the direction and the atom(s), and
      the ZnO regression: coordinates stay in [0, 1), CIF quotes an honest
      esd, no `FLAT_DIRECTION` on the coordinate pair.
      *Done 2026-10-12: `refine._origin_diagnostics` words what the table
      holds, on `fit` and `run_stage` results. `ORIGIN_FIXED_ON_POLAR_AXIS`
      (info) fires only where a stage's glob met the hold, and names the
      phase, the space group, the direction and the atom label.
      `ORIGIN_NOT_FIXED` (warning) fires only where a stage freed a DOF of a
      phase with an unfixed direction. `HOLD_BLOCKED_PLAN` leaves the origin
      hold out, so one fact gets one diagnostic. On the zincite fixture under
      `mccusker_structural` (LM and TRF), Zn stays at 0 with no esd and O
      refines to 0.38231(57), while the unheld pair quotes ±0.00029 on each
      z.*
- [x] `help.py` entry for any new field; Manual Part 2 (the constraint with a
      *Source* line beside the Wyckoff DOFs) and Part 1 (one paragraph).
      *Done 2026-10-12: `help.py` has no arm for a `Phase` field or a row
      extra, so the coordinate-DOF entry gained one sentence naming the hold.
      Part 2 carries `par-origin-floats` and `par-origin-hold` beside
      `par-origin`. Part 1 rewrites the `concepts.md` paragraph around the
      field and adds the origin hold to `model.md`'s held-reasons table. The
      1.9.0 staged notes carry the addition.*
- [x] Tests + obs/calc/diff PNGs to `tests/output/` for the ZnO case.
      *Done 2026-10-12: `tests/test_floating_origin.py` writes the three
      zincite fits (LM unheld, LM and TRF held), whole range and 30-40°, and
      checked by eye they are the same picture at Rwp 0.0993. A P 2₁2₁2₁
      and a Pnma fixture fit to the same free set and the same values bit
      for bit, declared or not, and raise no origin code.*
- [x] Skill: a row keyed by the new code. `references/diagnostics.md` is closed
      to growth (`tests/skill_caps.py`), so pay for it with a cut, or let
      the diagnostic's own `suggestion` carry it.
      *Done 2026-10-12, without a `diagnostics.md` row: it has 7 B left under
      its budget, and both codes now carry a `suggestion` saying what to do.
      The `references/numbers.md` paragraph #749 wrote, which names both
      codes, now describes the field, the quote rule for the held atom and
      the measured esds (+315 B, 23 766 B left). `api.md` regenerated for
      the two new fields, and the two committed copies re-synced.*
- [x] #929's open review items (handoff of 2026-10-13, below): item 5,
      `magnetic/supercell.py` copies `floating_origin` to the child phase
      (and any other `Phase(...)` builder copying field by field); item 8,
      a joint fit raises the origin codes; the pending tests for items 2
      (every candidate tied to a freed variable → `ORIGIN_NOT_FIXED`), 9 (a
      Le Bail fit raises no `ORIGIN_FIXED_ON_POLAR_AXIS`) and 11
      (`hold_floating_origin()` declines where nothing is holdable); and the
      "runs exactly along" wording in `using/concepts.md`, the 1.9.0 note and
      the skill paragraph.
      *Done 2026-10-13: `magnetic_supercell` copies the field (no other
      builder copies a phase field by field); a joint stage records
      `blocked_by_hold` (`MultiParameterTable.blocked_by_hold`) and
      `multi._joint_origin_findings` asks `_origin_diagnostics` of each
      histogram's table, a shared coordinate told once, so the
      `DIAGNOSTIC_SCOPES` row moves from ABSENT to SPECIMEN; four tests in
      `test_floating_origin.py` and one in `test_magnetic_supercell.py`; the
      candidate wording fixed in `concepts.md`, the 1.9.0 note, `numbers.md`
      and `help.py`, and `ORIGIN_NOT_FIXED`'s suggestion now names what the
      tied coordinates follow. A joint result's `blocked_by_hold` was always
      empty and now is not.*
- [x] `floating_origin="centroid"`, the restraint of Flack &
      Schwarzenbach (1988), read 2026-10-13 from the copy the maintainer
      supplied. *Superseded in part, 2026-10-13: the "exact affine tie in C"
      this task first named is the paper's infinite-weight limit, which it
      shows does not give the near-diagonal matrix the method exists for
      (§ Concluding remarks), so it is a restraint after all — but an
      internal one, not WP-1942's.* What the paper fixes:
      one pseudo-observation per floating direction p,
      Z_p = Σₙ aₙ·Δ_pᵀ(xₙ − xₙ⁰) = 0 (eq 9), Δ_p orthonormal in fractional
      components, x⁰ the values at the start of the cycle so the row adds
      nothing to the gradient; the solve then satisfies it **exactly at any
      weight** (eq 11 and the paragraph after), and only the covariance
      depends on aₙ. The aₙ are not ∝ Z² by fiat (that is the mean-matrix
      answer, and imposed as a constraint it is not diagonal): they solve
      aₘ·Σ_{n≠m} aₙ = bₘ (eq 21, A1), bₘ = Σ_{ij} A_{im,jm}Ω_ij / Σᵢ Ω_ii
      from the **unrestrained** normal matrix, by the (A6) iteration; this
      zeroes each column's Ω-collapsed off-diagonal sum (eq 20), handles
      special positions and multiplicity by itself, and exists iff
      Σb − 2b_r > 0 for every r (A5). In this package's terms
      bₘ = Σ_p ‖J·αₘ,ₚ‖²/P, αₘ,ₚ the θ step moving atom m alone by Δ_p
      (the paper's [111] example, z alone refined, gives A_zz/3 either
      way). Three cases the paper leaves open: N = 2 has b₁ = b₂ identically
      (rows of A sum to zero, eq 8), so aₘ·aₙ = b fixes only the product —
      take a₁ = a₂ = √b, which makes A′ diagonal and gives each z the
      difference's esd over √2, uncorrelated; (A5) failing is the limit of a
      hold on the dominant atom, so fall back to that and say so; and the
      row is added **only where the stage's free set realises the uniform
      shift** (`_origin_floats`), since on a fixed origin the same row is a
      structural restraint and biases the answer. Where it lives: a row
      block of its own in `model/rows.BLOCK_ORDER`, never `soft_restraint`,
      whose √c_w would silence it at c_w = 0 and free the origin; aₙ and x⁰
      frozen at stage compile (one J·α product per atom, 2N residual
      evaluations); partials constant, chained through C like
      `restraint_partials`; rows excluded from the observation count; the
      covariance read **with** them, that being the point. Every backend
      through `rows.assemble`, a `test_cross_backend.py` config, Part 2
      equation with *Source* lines (eqs 9, 21, A6).
      *Done 2026-10-13 (schema 0.54, renumbered from 0.53 at the merge of main, which took 0.53 for time of flight): `model/origin.py` (the eq 21 solve,
      Δ by QR, bₘ by central difference, the frozen block), an
      `origin_restraint` block last in `BLOCK_ORDER`, its analytic rows in
      `least_squares`, `ParameterTable.origin_slides` sharing
      `_origin_floats`' solve over the free set, compiled before each solve
      in `_run_stage` (a release re-solves) and in `suggest`'s probe;
      `ORIGIN_FIXED_ON_POLAR_AXIS` names each site's aₙ/Σa; a joint fit
      refuses it by name; a direction one site can move along is held as
      `"hold"` holds it. Zincite, LM and TRF: Rwp equal to the hold's to
      1.4e-14, z(O) − z(Zn) = 0.382313 the held z(O), each z ±0.000394
      against the hold's 0.000574/√2 = 0.000406, neither flat-direction
      code. Three P 4 m m sites meet eq 21 to 1e-3 and eq 20 to 1e-6 on the
      fit's own Jacobian; P 1 gets three rows and C c two. Part 2
      `par-origin-centroid` and `par-origin-weights`, Part 1 `concepts.md`,
      `help.py`, `numbers.md`, the 1.9.0 note. `replay` is evaluate-only
      and quotes no esd, so it needs no rows. Untested: a rigid body's
      origin as a site (moved to WP-2029).*
- [x] Measure hold against centroid on the ZnO, Cc and P1 fixtures and the
      round-robin zincite (origin, esds, Rwp, free count), then propose the
      default with a read-time pin for documents older than the schema that
      flips it.
      *Done 2026-10-13 (`[dev,jax]`, Linux). Round-robin
      `qarr/zincite.prn`, `compare.py`'s zincite standard,
      `mccusker_structural`:*

      | solver | `None` | `"hold"` | `"centroid"` |
      |---|---|---|---|
      | LM | Zn −0.00011(76), O 0.38271(76); `FLAT_DIRECTION`, `HIGH_CORRELATION`; 20 free | Zn 0, O 0.38283(152); 19 free | Zn −0.00011(105), O 0.38271(105); 20 free |
      | TRF | Zn 21102.46729(76), O 21102.85011(76) | as LM | as LM |

      *Rwp 0.114703 in all six; the difference 0.38283 in all six. The
      centroid's ±0.00105 is the hold's ±0.00152 over 1.44 (√2 is 1.41),
      no flat-direction code, and TRF stays in the cell. The synthetic C c
      (two rows) and P 1 (three) converge with no flat direction
      (`test_one_row_per_floating_direction`). Proposed default:
      `"centroid"`, behind a `mode="before"` pin reading documents older
      than the flipping schema as `None`; it needs the joint fit to stop
      refusing it first (a default that makes every polar joint fit raise
      is not one), either one origin row per joint structure or a fallback
      to `"hold"` there. Cost: 2·N·P extra forward evaluations per stage
      that slides a phase. The maintainer's call on #727.*
      *Decided 2026-10-23: the default stays off. The proposal, its
      conditions and the pin moved to WP-2029.*

## Acceptance

On the ZnO fixture above, freeing every coordinate DOF under
`mccusker_structural` returns z(Zn) and z(O) within [0, 1), their difference
within 2σ of 0.3826, an esd on every coordinate the fix leaves free, no
`FLAT_DIRECTION` on the pair, and the new diagnostic once. A P2₁2₁2₁ and a
Pnma fixture are unchanged, asserted on the free set. The fast suite is green,
with each moved number named.

```sh
.venv/bin/python -m pytest tests/test_wyckoff.py tests/test_params.py tests/test_params_surface.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #727.
- Flack, H. D. & Schwarzenbach, D. (1988). *Acta Cryst.* A**44**, 499–506.
  On the use of least-squares restraints for origin fixing in polar space
  groups. Read 2026-10-13 (the maintainer's copy); the centroid task quotes
  its eqs 9, 11, 20, 21, A1, A5 and A6.
- Hahn, T., ed. (2005). *International Tables for Crystallography, Vol. A*,
  Part 15 (normalizers of space groups) for the continuous translations.
- `crystallography/wyckoff.py` (`coordinate_basis`, `_nullspace_int`); WP-0301,
  WP-0302, WP-1432, WP-1435; `schemas/params.py` (`needs_held_cell`).

## Handover log

### 2026-10-23 — closed: the origin is fixed on request, and the default moves on

A fit in a polar space group can now fix the origin the data cannot see, in
one of two ways the caller picks. It can hold one atom
(`Refinement.hold_floating_origin()`, `Phase.floating_origin = "hold"`), or
restrain a weighted centroid of all of them (`"centroid"`, Flack &
Schwarzenbach 1988). Either keeps the coordinates in the cell with esds that
measure what the data measures. A caller who sets neither gets what every
earlier version gave: `FLAT_DIRECTION` on the result, and a walk under TRF.
The maintainer decided today that both stay off by default and that this WP
closes, which discharges the call on #727 it waited on. So the Goal's "fixes
the origin itself" holds on request only. The default is WP-2029.

*Closed.* Every task box was already ticked; the last two now point at
WP-2029. The acceptance holds with a mode declared:
`tests/test_floating_origin.py`, 73 passed today (`[dev]`, Linux, `2ff746f`).
*Inherited.* WP-1986's bullet (no Guides page on fixing the origin until the
default settles) went back to WP-1986 as a forward note: the behaviour is
settled as opt-in, and a flip in 2029 carries the guide with it. Its pointer
to `using/concepts.md` was stale, as that tree retired; the text now lives in
`docs/docs/reference/data.md` and `theory/parameterisation.md`.
*Re-measured today* (same venv): two review findings still hold.
`hold_floating_origin()` on a `"centroid"` phase returns `[]` and leaves the
field. After `unhold` of the origin DOF, Zn's row reads `vary=False`; after
`edit(floating_origin=None)` it reads `vary=True`. The others were not checked.
*Next.* Nothing owed here. WP-2029 holds the joint-fit seam, the open
findings, the read-time pin, the rigid-body test and the default; WP-1986
holds the guide.

*For the issue thread* (to batch, none posted): #727 gets a line saying both modes
stay opt-in and off, and that the default, the joint-fit seam and the analytic
weights are WP-2029's. #727 stays open, cited by 2029.

### 2026-10-13 (2nd session) — the centroid, built from the paper

A polar-group fit can now fix its origin the way single-crystal codes do. It
restrains a data-weighted centroid of the atoms instead of freezing one of
them, so every coordinate along the axis is refined and keeps an esd that can
be quoted on its own. On the round-robin zincite it gives the same structure
and Rwp as the hold, and each z's esd is the hold's divided by √2. It also
stops the TRF driver's walk to z ≈ 21 000. Reading the paper changed the plan:
an exact constraint gives the same values but loses the near-diagonal
covariance the method exists for, so it is a restraint. That restraint needs
nothing from WP-1942. Both modes stay off by default. A joint fit refuses the
centroid on a polar phase. Whether either mode becomes the default is the
maintainer's call on #727.

*Inherited, pruned.* The 2026-10-13 decision note moved into Context as
"Where the default stands". The two #727 comments that day disagree (hold now,
against still to decide). The maintainer settled it in this session: aim for
the centroid quickly and flip no default twice.

*Done.* Three tasks.
1. #929's review items, laned. The supercell copy, joint-fit origin codes
   (`blocked_by_hold` on joint stages), four tests and the candidate wording.
2. `"centroid"`, laned, schema 0.54. The mechanics are in the task's done
   note. In this session I added the origin rows to `suggest`'s probe.
   `replay` is evaluate-only, so it needs none.
3. The real-data measurement, in the task's table.

The paper (the maintainer's copy, read in full) is cited by equation in
`model/origin.py` and Part 2 `par-origin-centroid`/`par-origin-weights`.

*Review.* `/code-review high --fix` found eight issues and fixed three:
- (A6) stalls where (A5) holds by a hair (b = [6724, 6724, 1] missed eq 21 by
  27×; a 1e-30 site gave NaN). eq 21 is now also solved through S = Σa with
  Brent, and the better answer kept, and a test pins it.
- The origin partials are built once per solve and one C serves both blocks.
- A docstring claimed one origin across stages. Each stage restrains its own
  start.

I fixed a fourth: a joint fit refused a non-polar phase declaring centroid,
and now refuses only a polar one (with a test). Four I leave, as findings for
the next session:
- `site_curvatures` costs 2·N·P full evaluations per compile (a 60-site P1 is
  360). The derivative bases could give them analytically.
- A stage whose second solve cannot slide the phase records only that solve,
  so the first solve's restraint goes unreported.
- `hold_floating_origin()` returns `[]` for a phase already declaring
  centroid.
- A centroid phase whose sites scatter nothing gets no row and no
  `ORIGIN_NOT_FIXED`.

*Measured.* Real data: the task's table (`[dev,jax]`, Linux). Lanes: two, plus
one item kept. The tool's table:

| lane | est | requests | main at dispatch | lane $ | saved $ |
|---|---|---|---|---|---|
| review-items | 30 | 65 | 153K | 3.14 | +0.32 |
| centroid | 60 | 130 | 227K | 10.55 | +2.19 |

Kept: measure, est 15, 6 requests, at 288K. The selective policy's replay row
is +12% for this session (+2.52, +10% of the session in the trial row). The
estimates ran 2.17× short. The fast selection was run on this branch with main merged at
`4366289` (`[dev,jax]`, Linux, one run, 23 min 15 s). It gave 9 497 passed,
128 skipped and 1 xfailed, with no failure. There is no main baseline on this
venv, so the count's move against main was not measured. The 21 added tests
(22 cases) cost 22.6 s in that run, 22.3 s of it in `test_floating_origin.py`.
The module fixture's two added centroid fits come on top of that and are not
attributed to a test. The full selection did not run: the default stays off,
so no measured number moves.

*Gotchas.*
- The venv in this worktree has `[dev,jax]`: the centroid lane installed jax.
  Every count above is for that venv.
- The goldens are pinned to darwin/arm64 and skip on Linux. Default-off
  bit-identity here rests on the P 2₁2₁2₁/Pnma bit-for-bit tests and on
  `compile_origin` returning `None` before anything else.
- The rigid-body site path (a body origin as one site) has no test.

*Next.*
1. The maintainer decides the default on #727. The proposal is `"centroid"`
   with a read-time pin, and the task gives the conditions.
2. If the centroid is to become the default, a joint fit must take it first:
   one origin row per structure in `multi.py`, or a fallback to `"hold"`.
3. Then the four review findings above, the analytic curvatures first,
   because they are the cost a default would impose on every polar fit.

### 2026-10-13 — the hold moves into the table, and the default is measured

The floating-origin hold is now something the parameter table does, behind a
switch on the phase. With it set, every fit, series pattern, joint histogram
and history replay holds the same atom. A tie or hold of the caller's that
already fixes the origin gets no second one. The switch is off by default, so
nothing moves for a caller who does not set it. Whether to turn it on is the
maintainer's decision on #727, and the numbers for that decision are below.

*Done.* Tasks 2-7, one commit each, on PR #929. Schema 0.52 adds
`Phase.floating_origin` and `ParameterRow.origin_axis`.
`ParameterTable._fix_origin` holds the first DOF that runs exactly along each
floating direction, through `Entry.held`, and re-decides at every build, tie
and hold. `_origin_floats` decides "already fixed" by an exact solve on the
affine block. `hold_floating_origin()` is now a wrapper that sets the field,
and `unhold` on a held DOF sets it back to `None`. `ORIGIN_FIXED_ON_POLAR_AXIS`
joins `fit` and `run_stage` results where a stage's glob met the hold, and
`HOLD_BLOCKED_PLAN` leaves that DOF out. `refine.py` was touched only in
`parameters`, `hold_floating_origin`, `unhold`, `_prepare_table`'s restore, the
two diagnostic call sites and `_hold_diagnostics`.

*Review.* My own pass found the free-set restore warning "no longer exists"
for a DOF the table held. `/code-review high --fix` found eight things and
fixed three: `unhold` asks the table again after removing a caller's hold, and
`set_tie`/`set_held` rebuild once. It left five, and so do I. A cross-phase tie
between two declaring phases makes the solve report "fixed" while the joint
shift is flat; no shipped fixture has one. One `unhold` matching both a user
hold and the origin hold records two nodes. A taken-back origin hold keeps
`vary=False`, as documented. A joint fit raises neither origin code
(`multi.DIAGNOSTIC_SCOPES`). `edit(floating_origin=None)` restores a DOF that
was free before, where `unhold` leaves it fixed.

*Measured* (`[dev]` venv, darwin arm64; the machine ran 5-6 other sessions'
suites at load 100-150 throughout). Fast selection on `f691115a`, this branch
with main merged after the review: 9 364 passed, 181 skipped, 1 xfailed and 1
failed, in 19 min 43 s. The failure was
`test_structure_extent.py::test_three_cells_a_side_build_in_no_more_than_a_moment`,
a wall-clock test, and it passed alone. The branch adds 24 test cases, all in
`test_floating_origin.py` (15 to 39). They cost 20.2 s in that run, 8.9 s of it
the module fixture's three zincite fits, which is the WP's acceptance fixture
and so stays in the fast tier. With the default off,
every golden is bit-identical:
`test_numpy_path_bit_identical_to_golden` on all ten states (`srm660c` and
`nac` included) and `test_the_compiled_path_holds_the_goldens_to_its_own_bar`
on its three. The full selection did not run, because the default moves no
number. With the default flipped to `"hold"` in a snapshot of `cc7ad7fc`, the
fast selection moves four tests: the `toy_anomalous` golden (zincite with
`phases.0.atoms.*.dof.*` free), two tests in `test_floating_origin.py` that pin
the default, and the generated `api.md`, which prints the default. Eleven
other failures and 16 errors there fail identically on an unflipped snapshot,
because a `git archive` tree is not a repository. No slow test frees a
coordinate on a polar phase. No shipped CIF is in a polar group. The shipped
polar fixtures are `compare.py`'s zincite and test-built phases.

Real data, the IUCr CPD round-robin `qarr/zincite.prn` with `compare.py`'s
zincite standard:

| protocol | off | `"hold"` |
|---|---|---|
| QPA (the acceptance protocol, frees no coordinate) | Rwp 0.109274 | bit-identical values |
| `mccusker_structural`, LM | Zn −0.00011(76), O 0.38271(76); `FLAT_DIRECTION`, `HIGH_CORRELATION`; 20 free | Zn 0, O 0.38283(152); neither code; 19 free |
| `mccusker_structural`, TRF | Zn 140.12849(76), O 140.51132(76) | as LM |
| QPA + a coordinate stage, LM | each z ±0.0092; the pair in `COVARIANCE_DIRECTION_DISCARDED` | O 0.38213(136); the pair out of it |

Rwp agrees to six figures in every pair. Coordinate rows in
`RefinementResult.parameters` go from 4 to 3 (Zn's DOF leaves, its z stays
with no esd), and rows with an esd from 4 to 2. On the WP's synthetic fixture
O comes to 0.38231(57) held, against ±0.00029 on each z unheld.

*Decision menu for #727.*

1. Keep the default off. Nothing moves. A polar fit that frees coordinates
   keeps `FLAT_DIRECTION` and esds half the honest size, and walks under TRF.
2. Default `"hold"` with a read-time pin. Documents written before 0.52 read
   as `None`, so old projects and histories replay unchanged. Moves the
   `toy_anomalous` golden (declare `None` in its state or re-capture it), the
   two default-pinning tests and `api.md`, plus the real-data rows above.
3. Default `"hold"` with no pin. As 2, and every older document reopens holding
   its first atom, so a replayed history node refits with one fewer free
   parameter.
4. A centroid mode (`"centroid"`), which @mustachefeeling asked for on #727 on
   2026-10-12 in place of the hold default. Not built. It needs the weights
   from Flack & Schwarzenbach (1988) and an affine tie over every atom along
   the axis, which widens one column's reach through `_column_extras`. It could
   become the default instead of `"hold"`.

*Not generalised.* No `diagnostics.md` row: it is 7 B under its budget, both
codes carry a `suggestion`, and `numbers.md` names them. A rigid body's origin
is a candidate after the atoms, untested on a fixture.

*Next.* The maintainer picks from the menu on #727. Option 2 is a small change:
the default, a `mode="before"` pin on `Phase` for documents older than 0.52, and
`toy_anomalous` declaring `None`. Option 4 is its own task on this WP.

*Handoff, 2026-10-13* (head `15d0b646`, main merged at `557df56b` before it). PR #929
was held at the merge gate by a `/code-review medium` pass with twelve findings.
Item 7 came first. Design: `ParameterTable.held_by(path)` returns `"caller"`,
`"origin"` or `None` from the table's own two sets (`_caller_held`,
`_origin_held`), and `Refinement.set_vary`, `_prepare_table`'s restore and
`unhold` now read it in place of `_user_holds` or `origin_holds`. The twelve,
verbatim, with status:

7. `refine.py:2374` the table's origin hold is a second writer of `Entry.held`, special-cased by hand at `_prepare_table`, `unhold` and `_hold_diagnostics` and missed at `set_vary`. Root CLAUDE.md's rule is that a hold is honoured in the table, never at call sites: give the table one answer, e.g. `ParameterTable.held_by(path) -> 'caller' | 'origin' | None` (or `set_vary` returning the declined held paths), and make every verb read it. **Fixed.** (`_hold_diagnostics` still takes `table.origin_holds`, which is the same set.)
1. `refine.py:2389` `set_vary` refuses a held literal only when the path is in `_user_holds`; on zincite with `floating_origin='hold'`, `set_vary('phases.0.atoms.0.dof.0')` returns `[]` silently, where a user hold raises; through the GUI the checkbox is a 200 that changes nothing. **Fixed**: refused with a message naming `Phase.floating_origin`; test `test_a_literal_set_vary_on_the_origin_hold_is_refused`. The GUI path is not re-tested.
2. `refine.py:6115` ORIGIN_NOT_FIXED is gated on a stage freeing a DOF of the phase by name, so the one unfixed case the docstring names (every candidate tied to a variable, plan frees `vars.*`) is never reported and the flat direction is walked in silence. Test the freed set against the columns that reach the phase's coordinate rows (`entry_reach`/`column_reach`), never DOF names (root CLAUDE.md, "a freeze resting on flatness needs the other reading of C"). **Fixed** in `_origin_diagnostics` (reach of each freed path through `entry_reach`). **Pending: a test** with both DOFs tied to a freed variable.
3. `params/vector.py:2547` when the origin fix moves off an entry, the take-back resets `held` but leaves `vary=False`: Zn declared free ends `vary=False, held=False, held_because ''`, `_free_paths == []`, nothing says so. Restore the entry's pre-hold `vary`, or report the take-back. **Fixed**: `_origin_wanted` keeps the vary the caller last asked for (at the hold, then from any glob reaching the row) and the take-back restores it; test `test_a_take_back_restores_the_vary_a_glob_asked_for`.
4. `refine.py:3102` `unhold` re-asks `origin_matches` after releasing the caller's own hold, so `unhold('phases.0.atoms.*.dof.*')` after `hold('…atoms.1.dof.0')` also sets `Phase.floating_origin` to None; a redundant hold()+unhold() on the origin DOF deletes the declaration (the test `test_unholding_a_callers_hold_on_the_origin_dof_leaves_it_free` pins the wrong behaviour). Lift only what the caller held; withdraw the declaration only when the released path was the table's own origin hold and nothing else. **Fixed**; the test is now `test_unholding_a_callers_hold_leaves_the_declaration_standing`.
5. `crystallography/magnetic/supercell.py:1427` the magnetic supercell builder builds the child Phase from named fields and never copies `floating_origin` (it copies `scale` and `magnetic_symmetry`); copy it, with a test on a polar parent. **Pending.** Also grep the other `Phase(...)` builders that copy a parent field by field.
6. `params/vector.py:1416` a candidate must have a basis row exactly ±f, so rhombohedral-axes polar settings (R 3:R, R 3 m:R, R 3 c:R, f = [1,1,1]) with general-position atoms get ORIGIN_NOT_FIXED although holding one coordinate DOF fixes the slide. Accept a DOF whose row has a nonzero component along f, or document the limitation in the suggestion; add the :R settings to the test matrix either way. **Fixed** by the first option: a site states the shift in its own basis as Bᵀa = f, and any DOF with aₖ ≠ 0 is a candidate (a general site on R 3 m:R holds its x). Part 2's `par-origin-hold` says so. The three `:R` settings are in the basis matrix and R 3 m:R in the table matrix.
8. `multi.py:272` a joint fit applies the hold but emits neither ORIGIN_FIXED_ON_POLAR_AXIS nor HOLD_BLOCKED_PLAN; add the diagnostic (root CLAUDE.md: a new correction ships with a diagnostic stating what it changed). **Pending.** Read how `multi.py` builds its `StageResult`s first; `DIAGNOSTIC_SCOPES` then moves the entry from ABSENT.
9. `refine.py:6097` ORIGIN_FIXED_ON_POLAR_AXIS fires in a Le Bail/Pawley fit whose glob matched the DOF although every coordinate was mode-fixed; gate on another DOF of the phase actually freed, as the NOT_FIXED arm does. **Fixed** with item 2's reach gate (the mode drops coordinates from `freed`). **Pending: a Le Bail test.**
10. `params/vector.py:282` `Entry.held`'s docstring says only `_apply_holds` writes it and "nothing the table derives from a structure could rebuild it"; now false. Rewrite it around item 7's answer. **Fixed.**
11. `refine.py:3106` a phase with `floating_origin` set but no holdable candidate cannot be released through `unhold` (no held path to name); give the verb a way to withdraw the declaration, or make `hold_floating_origin()` decline to set it when nothing can be held. **Fixed** by the second option: the verb probes the table (`Refinement._table_for`) and leaves a phase undeclared where nothing would be held; a declaration set by hand is withdrawn with `edit`. **Pending: a test.**
12. `refine.py:3082` `unhold` builds the working table up to four times; build one, read `origin_holds` off it, pass it to `_commit_hold_edit`. **Fixed** (one working table; `edit` still builds its own when a declaration is withdrawn).

Also pending: `docs/manual/using/concepts.md` still says "runs exactly along" for `ORIGIN_NOT_FIXED`; the 1.9.0 note and the skill paragraph need the same check. The fast selection has not run on `15d0b646`; the touched tests (252) and all fifteen golden tests passed there (`[dev]`, darwin arm64). The D1 default menu above is unchanged.

Next command: `.venv/bin/python -m pytest tests/test_floating_origin.py -n 4 --dist loadgroup`, then fix item 5 at `src/rietx/crystallography/magnetic/supercell.py:1427`.

- **2026-10-08** — a caller can now hold a polar group's floating origin in one
  call, and the fit then stops walking the structure along the polar axis. Nothing
  changes for a caller who does not ask. PR #749 (#727, head `f9f3c27e`) merged as
  `9465d2cf` after four rounds, behind an opt-in decided on the PR.
  *Done.* `wyckoff.floating_origin_basis(space_group)` returns the translations
  that commute with every rotation of the group (ITA Part 15).
  `Refinement.hold_floating_origin()` holds, per direction, the first atom whose
  free site DOF runs exactly along it, through `hold`, so `unhold` lifts it. It
  returns `ORIGIN_FIXED_ON_POLAR_AXIS` (info), or `ORIGIN_NOT_FIXED` where no DOF
  runs exactly along a direction. Part 2 has the equation, Part 1 a paragraph in
  `concepts.md`, and the skill a paragraph in `references/numbers.md`. On
  synthetic ZnO the held fit keeps Zn where it started and loses `FLAT_DIRECTION`.
  *Gate:* stacked with the run's other merges (#829, #825, #809, #754, #749, #815)
  on `main` `a3f9140a` as `166d362e`, macOS 26.6.2 arm64, `[dev,jax]`. The full
  suite, fast and slow together, gave 9231 passed, 116 skipped, 1 xfailed and 2
  failed. Both failures also fail on `main` alone on that machine: `toy_anomalous`
  (#760, which open PR #828 fixes) and a hypothesis counterexample in
  `test_indexing_reduce.py`. `main` after the merges is content-identical to that
  tree.
  *Not done here.* The tasks above assume the fix lives in `ParameterTable` by
  default. What landed is a `Refinement` verb nobody runs by accident, and the
  hold-or-centroid choice (Flack & Schwarzenbach 1988) is still open.
  *Next:* the maintainer decides #727's default; the remaining tasks follow from
  it.

- **2026-10-06** — Maintainer decision on #727, through draft PR #749,
  recorded on the decision task above. Holding one coordinate is the common
  powder practice, and the abstract of Flack & Schwarzenbach (1988)
  describes it as the common definition. SHELXL instead restrains the
  centroid automatically. GSAS-II computes each group's polar axes
  (`GSASIIspc.SGpolar`). GitHub's code search finds them used nowhere in
  refinement, and its solver drops a parameter when the normal matrix goes
  singular. What TOPAS and FullProf do was not confirmed.
  *Recovered 2026-10-10: committed after PR #796 merged, so it reached main
  only now.* The 2026-10-08 entry's "hold-or-centroid choice is still open"
  was written without this decision. The default is still open.

- **2026-10-05** — created, from the 2026-10-05 issue triage (issue #727).
  Checked against the tree at 32ef5a6: the issue's snippet lists both ZnO z
  DOFs as refinable, a free fit walked them to z = 634.13 / 634.51
  (`converged`, CIF `634.1318(11)`, `FLAT_DIRECTION` on the result) and
  `mccusker_structural` to ≈148, and a hand hold restored z(O) = 0.3807(22)
  at the same Rwp; `wyckoff.coordinate_basis` over the whole group's
  rotations gives the free-origin directions. No open WP owns it: 1460 only
  deduplicates the correlation rows, 1528 is a `Cell` docstring, 1514 and
  1803 are rigid bodies, and the WPs this extends (0301, 0302, 1311, 1432,
  1435, 1535) are closed. Next: task 1, the maintainer's choice of shape.
