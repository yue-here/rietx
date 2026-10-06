# WP-1912 — a polar axis has no origin, and the fit walks along it

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-10-05 — the default structural preset reaches it on every polar space group with a free coordinate, and the CIF it writes carries an absolute coordinate hundreds of cells out with an esd; flagged only by `FLAT_DIRECTION` on the result, so not P1

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
- [ ] `crystallography.wyckoff`: the group-level free-origin basis, tested on
      the ten groups above and on every gemmi setting, asserting **which**
      directions, not how many (root CLAUDE.md, the cell-ties rule).
- [ ] `ParameterTable`: the fix applied in the table, never at call sites;
      skipped where user ties or variables already fix the origin; the
      `ParameterRow` held-reason or tie, with its `held_because` text and its
      writer named (WP-1076).
- [ ] The diagnostic naming the phase, the direction and the atom(s), and
      the ZnO regression: coordinates stay in [0, 1), CIF quotes an honest
      esd, no `FLAT_DIRECTION` on the coordinate pair.
- [ ] `help.py` entry for any new field; Manual Part 2 (the constraint with a
      *Source* line beside the Wyckoff DOFs) and Part 1 (one paragraph).
- [ ] Tests + obs/calc/diff PNGs to `tests/output/` for the ZnO case.
- [ ] Skill: a row keyed by the new code. `references/diagnostics.md` is closed
      to growth (`tests/skill_caps.py`), so pay for it with a cut, or let
      the diagnostic's own `suggestion` carry it.

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
  Least-squares restraints for origin fixing in polar space groups. **Check
  the paper before quoting a weight scheme**; it is cited here from memory.
- Hahn, T., ed. (2005). *International Tables for Crystallography, Vol. A*,
  Part 15 (normalizers of space groups) for the continuous translations.
- `crystallography/wyckoff.py` (`coordinate_basis`, `_nullspace_int`); WP-0301,
  WP-0302, WP-1432, WP-1435; `schemas/params.py` (`needs_held_cell`).

## Handover log

- **2026-10-06** — Maintainer decision on #727, through draft PR #749,
  recorded on the decision task above. Holding one coordinate is the common
  powder practice, and the abstract of Flack & Schwarzenbach (1988)
  describes it as the common definition. SHELXL instead restrains the centroid automatically. GSAS-II
  computes each group's polar axes (`GSASIIspc.SGpolar`). GitHub's code
  search finds them used nowhere in refinement, and its solver drops a parameter when the
  normal matrix goes singular. What TOPAS and FullProf do was not confirmed.

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
