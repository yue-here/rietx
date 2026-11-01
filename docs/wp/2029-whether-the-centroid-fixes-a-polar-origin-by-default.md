# WP-2029 — Whether the centroid fixes a polar origin by default

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: — (1912 soft, closed 2026-10-23: it built both modes and measured the default)
Priority: P3 2026-10-23 — a workaround covers it: an unfixed origin is flagged by `FLAT_DIRECTION` on the result, and both fixes exist opt-in (`Refinement.hold_floating_origin()`, `Phase.floating_origin = "centroid"`)

## Goal

The maintainer decides on #727 whether `Phase.floating_origin` defaults to
`"centroid"`. Before that call, the centroid works in a joint fit, costs a
polar fit no extra forward evaluations, and has no open review finding. If the
default flips, documents written before it replay unchanged and the release
notes say what moved.

## Context

**What WP-1912 shipped** (closed 2026-10-23, issue #727). In a polar space
group (P 6₃ m c, P 4 m m, Cc, P 1, …) the whole structure can shift along the
polar axis without changing any intensity. A fit that frees every coordinate
along it has a flat direction. Unfixed, TRF walks the pair to z ≈ 21 000, and
each z is quoted at half the honest esd.
- `crystallography.wyckoff.floating_origin_basis(space_group)` returns the
  translations that commute with every rotation of the group (ITA Part 15).
  A physics oracle holds it on all 564 gemmi settings.
- `Phase.floating_origin: Literal["hold", "centroid"] | None = None`
  (`schemas/structure.py`; schema 0.52 added `"hold"`, 0.54 added
  `"centroid"`, and the current schema is 0.59). `None` builds the table every
  earlier version built.
- `"hold"`: for each floating direction, `ParameterTable` holds the first atom
  DOF that a shift along the direction moves, through `Entry.held`. It skips a
  direction where the caller's own ties or holds already fix the origin
  (`_origin_floats`, an exact solve on the affine block).
  `ParameterRow.origin_axis` gives the row its `held_because`, and
  `ParameterTable.held_by(path)` answers `"caller"`, `"origin"` or `None` for
  every verb. `Refinement.hold_floating_origin()` sets the field, and `unhold`
  on the held DOF sets it back to `None`. A joint fit's per-histogram tables
  hold the same atom (`multi._joint_origin_findings`).
- `"centroid"`: Flack & Schwarzenbach (1988). It adds one restraint row per
  floating direction, Z_p = Σₙ aₙ·Δ_pᵀ(xₙ − xₙ⁰) = 0 (eq 9), with x⁰ the
  stage's start. The solve meets the row exactly at any weight (eq 11). The
  weights aₙ change only the covariance. They solve aₘ·Σ_{n≠m} aₙ = bₘ (eq 21)
  by the (A6) iteration, with a Brent solve on S = Σa as a fallback. bₘ is the
  unrestrained normal matrix's diagonal block for site m,
  Σ_p ‖J·αₘ,ₚ‖²/P, and is computed today by central difference
  (`model/origin.site_curvatures`). The rows are a block of their own,
  `origin_restraint`, last in `model/rows.BLOCK_ORDER`. They are never
  `soft_restraint`, whose c_w = 0 would silence them and free the origin. They
  are added only where the stage's free set realises the slide
  (`ParameterTable.origin_slides`), since on a fixed origin the same row would
  bias the structure. A direction only one site can move along is held as
  `"hold"` holds it. An (A5) failure clips toward a hold (`A5_CLIP`).
- Diagnostics: `ORIGIN_FIXED_ON_POLAR_AXIS` (info) names the phase, the
  group, the direction, and the held atom or each site's aₙ/Σa.
  `ORIGIN_NOT_FIXED` (warning) fires where a freed column reaches a phase
  whose direction nothing fixes. Both carry a `suggestion`.

**Measured** (1912, 2026-10-13, `[dev,jax]`, Linux): the IUCr round-robin
`qarr/zincite.prn`, `compare.py`'s zincite standard, `mccusker_structural`:

| solver | `None` | `"hold"` | `"centroid"` |
|---|---|---|---|
| LM | Zn −0.00011(76), O 0.38271(76); `FLAT_DIRECTION`, `HIGH_CORRELATION`; 20 free | Zn 0, O 0.38283(152); 19 free | Zn −0.00011(105), O 0.38271(105); 20 free |
| TRF | Zn 21102.46729(76), O 21102.85011(76) | as LM | as LM |

Rwp is 0.114703 in all six fits, and the difference is 0.38283 in all six.
The centroid's ±0.00105 is the hold's ±0.00152 over 1.44 (√2 is 1.41). The
synthetic Cc (two rows) and P 1 (three rows) fixtures converge with no flat
direction (`test_one_row_per_floating_direction`). A default changes the
reported origin and the spread of esds. It never changes the structure, Rwp
or any interatomic distance. The centroid also keeps the free count, where
`"hold"` drops one per direction, so N − P, GoF and ΔBIC move only under the
hold.

**What a flip moves** (1912 flipped `"hold"` in a snapshot of `cc7ad7fc` and
ran the fast selection): four tests moved. They were the `toy_anomalous`
golden (zincite with `phases.0.atoms.*.dof.*` free;
`tests/test_backend_shim.py::_state_toy_anomalous`), two tests in
`tests/test_floating_origin.py` that pin the default, and the generated
`api.md`. No slow test frees a coordinate on a polar phase, and no shipped CIF
is in a polar group. A centroid flip has not been run.

**The joint fit refuses the centroid** (`multi._refuse_centroid_origin`). A
shared structure is compiled once per histogram, so stacked origin rows would
count N times. WP-1995 (⬜) builds the once-per-structure placement for soft
restraints in a joint fit and names this refusal as the same problem. Its
Non-goals lift the refusal only if that falls out for free. A default that
makes every polar joint fit raise is not a default, so either the rows go in
once per structure or a joint fit falls back to `"hold"` and says so.

**The read-time pin.** No writer under `src/` uses `exclude_defaults` or
`exclude_unset`, so every document since 0.52 carries the field and one
older than 0.52 lacks it. A `Phase(...)` built in Python lacks it too, so a
`mode="before"` validator that reads a missing key as `None` would undo the
flip for every caller. The pin has to know the document's schema version, for
example through pydantic's validation `context` passed in at the read points.
`schemas/migrate.py`'s `READ_POINTS` lists every place a stored document is
read.

**Cost.** `site_curvatures` runs 2·N·P full forward evaluations per compile
(N sites, P directions; a 60-site P 1 is 360). It runs once per stage that
slides a phase, again on a release re-solve, and in `suggest`'s probe. bₘ needs
only J·αₘ,ₚ, a fixed combination of the coordinate-DOF columns the analytic
Jacobian already builds (`CompiledModel.derivative_bases()`).

**Tier** ([generality § The rule](../milestones/generality.md#the-rule)). The
statistic, `floating_origin_basis`, is tier 1: a translation that commutes
with every rotation changes no intensity, and the oracle shows it. The action,
fixing the origin by default, is
[DESIGN § Rules](../DESIGN.md#rules) 1's first kind only if it passes the
unanimity gate. The tier-2 evidence is a citation: Flack & Schwarzenbach (1988),
and SHELXL restrains the centroid by default. Of the seven rietx-bench
programs, only GSAS-II was checked (1912, 2026-10-06). It computes polar axes
(`GSASIIspc.SGpolar`) but uses them in no refinement, and its solver drops a
parameter when the normal matrix goes singular. TOPAS and FullProf were not
confirmed, and the other four were not looked at. So the default rests on tier
3's judgement ground. Fixing a flat direction looks unanimous. The dissent to
look for is about the convention: a caller who quotes a structure against a
published origin with one atom held is served by `"hold"`, and a caller's own
hold or tie already turns the derivation off. Which convention is chosen moves
no structure, Rwp or distance. The record is the field and
`ORIGIN_FIXED_ON_POLAR_AXIS`. `Phase` is not among `_audit.DEFAULT_SEATS`, so a
flipped default needs its row in `rietx._audit` (root CLAUDE.md, every
heuristic has a row). `/wp-handover` then sends the change to the
`generality-review` agent.

Licensing: SHELXL, TOPAS and FullProf are closed (papers and user
documentation only). BGMN is GPL, so concepts only.

## Non-goals

- What either mode computes: 1912 shipped both. This WP finishes them and
  decides the default.
- Soft restraints in a joint fit in general (WP-1995). This WP takes only the
  origin rows, and reuses 1995's placement if it has landed.
- Changing `FLAT_DIRECTION` or `HIGH_CORRELATION` (WP-1460 owns their dedup).
- Discrete origin choices of non-polar groups (`:1`/`:2`), and choosing an
  origin for a structure-solution search (WP-1515).

## Tasks

- [ ] A joint fit takes the centroid. Either one origin row block per shared
      structure (not per histogram, unweighted by √w_h, below every
      histogram's data and background rows), or a fallback to `"hold"` in a
      joint fit, named in `ORIGIN_FIXED_ON_POLAR_AXIS`. Drop the polar arm of
      `multi._refuse_centroid_origin`. Test: a joint fit of two identical
      zincite patterns gives the single fit's z(O) − z(Zn) and one row per
      direction. Add a joint config to `test_cross_backend.py`.
- [ ] Analytic curvatures. bₘ comes from the derivative bases instead of
      2·N·P forward evaluations. Check it against today's central difference
      on zincite, three P 4 m m sites and P 1 (eq 21 to 1e-3, eq 20 to 1e-6
      on the fit's Jacobian, as `test_three_sites_solve_eq_21_and_diagonalise_the_z_block`
      asserts now). Quote the compile time before and after on a 60-site P 1.
      `ORIGIN_FD_STEP`'s `_audit` row goes with the difference.
- [ ] The other review findings left open on 2026-10-13, each with a test:
      - a stage whose second solve cannot slide the phase records only that
        solve, so the first solve's restraint goes unreported;
      - `hold_floating_origin()` on a phase declaring `"centroid"` returns
        `[]` and leaves the field (re-measured 2026-10-23). Decide whether it
        switches the mode or says why it did not;
      - a centroid phase whose sites scatter nothing gets no row and no
        `ORIGIN_NOT_FIXED`;
      - a cross-phase tie between two declaring phases makes `_origin_floats`
        report "fixed" while the joint shift is flat (no shipped fixture has
        one);
      - after `unhold` of the origin DOF, Zn's row reads `vary=False`, while
        after `edit(floating_origin=None)` it reads `vary=True` (re-measured
        2026-10-23). Make the two verbs agree;
      - one `unhold` matching both a caller's hold and the origin hold
        recorded two history nodes (2026-10-13; not re-checked since #929's
        item 4 changed what `unhold` lifts);
      - #929 item 1's GUI path: a literal `set_vary` on the origin-held DOF
        is refused, but the parameter checkbox route was not re-tested.
- [ ] The rigid-body site path has no test. `site_curvatures` moves a body's
      origin as one site; test it on a polar phase with a rigid body.
- [ ] The program check the tier needs: what each of the seven rietx-bench
      programs does by default with a floating origin, from papers and user
      documentation.
- [ ] Decide the default with the maintainer on #727: `"centroid"`, `"hold"`
      or off. 1912's conditions for a flip are: (a) the joint fit takes it
      (task 1); (b) its cost is paid analytically (task 2); (c) a read-time pin
      keeps older documents and histories replaying unchanged; (d) the release
      notes say the reported origin and the esd spread move, never the
      structure, Rwp or a distance. Record the decision here.
- [ ] If it flips: change the default in `schemas/structure.Phase` and bump
      the schema. Add the `mode="before"` pin, so a document older than 0.52
      reads as `None`, keyed on the document's version and never on the
      missing key. `toy_anomalous` declares `floating_origin=None` in its
      state. Update the two default-pinning tests in `test_floating_origin.py`
      and regenerate `api.md`. Every test that pins a number on a polar phase
      freeing coordinates declares the field rather than inheriting it (the
      dispersion rule, root CLAUDE.md). Add `rietx.schemas.structure.Phase` to `_audit.DEFAULT_SEATS` and its
      `Phase:floating_origin` default row and a release
      note.
- [ ] Manual: `docs/docs/reference/data.md` § Floating origin ("`None` is
      off") and `theory/parameterisation.md`'s `par-origin-*` prose say what
      the default is. If the default changed, tell WP-1986, or update the
      polar-origin guide if it has been written
      (`docs/docs/guides/<page>.md`, its script in `examples/guides/`).
- [ ] Tests + obs/calc/diff PNGs to `tests/output/`: the joint zincite fit
      beside the three single fits `test_floating_origin.py` already draws.
- [ ] Skill: `references/numbers.md`'s floating-origin paragraph names the
      default. `references/diagnostics.md` had 7 B left at 1912, so the two
      codes' `suggestion`s carry the rest.

## Acceptance

Under `mccusker_structural` on the round-robin zincite, the decided default
reproduces 1912's row for its mode (Rwp 0.114703, difference 0.38283). A joint
fit of two zincite histograms with a centroid phase converges with
z(O) − z(Zn) within 2σ of the single fit and one origin row per direction.
Computing the origin weights costs no forward evaluation beyond the stage's
own Jacobian. If the default flipped, a document written at schema 0.51 replays
bit-identically. The fast suite is green, with each moved number named.

```sh
.venv/bin/python -m pytest tests/test_floating_origin.py tests/test_multi_histogram.py tests/test_cross_backend.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #727.
- Flack, H. D. & Schwarzenbach, D. (1988). *Acta Cryst.* A**44**, 499–506.
  On the use of least-squares restraints for origin fixing in polar space
  groups. Eqs 9, 11, 20, 21, A1, A5, A6 (the maintainer's copy).
- Hahn, T., ed. (2005). *International Tables for Crystallography, Vol. A*,
  Part 15 (normalizers; the continuous translations).
- WP-1912 (closed; its 2026-10-13 entries hold the review lists and the
  decision menu), WP-1995 (once-per-structure rows), WP-1986 (the Guides tab),
  WP-1435 (holds), WP-1432 (anchored DOFs), WP-1342 (`column_reach`), WP-2001
  (`rietx._audit`).
- Code: `crystallography/wyckoff.floating_origin_basis`; `params/vector.py`
  (`_origin_floats`, `origin_slides`, `origin_holds`, `held_by`);
  `model/origin.py` (`site_curvatures`, `compile_origin`);
  `model/rows.BLOCK_ORDER`; `multi._refuse_centroid_origin`,
  `multi._joint_origin_findings`; `refine._origin_diagnostics`;
  `tests/test_floating_origin.py`.

## Handover log

- **2026-10-23** — created by WP-1912's close. The work comes from 1912's
  two 2026-10-13 entries (their `*Next.*` lists and the review findings they
  left open) and from the maintainer's decision of 2026-10-23: both
  floating-origin modes stay opt-in and off, and the default is a follow-up.
  No open WP owned the default. WP-1995 names the centroid's joint-fit refusal
  only as a Non-goal, and WP-1986 waits on the default for a guide. Two
  findings were re-measured that day (`[dev]`, Linux), and both hold (Tasks).
  Next: tasks 1 and 2, which are independent. The decision waits on both.
