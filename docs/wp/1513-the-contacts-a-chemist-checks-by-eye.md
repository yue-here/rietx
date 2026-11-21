# WP-1513 — The contacts a chemist checks by eye

Milestone: unscheduled · Status: 🔄 2026-11-16 — task 1 landed (PR #1608), tasks 2-6 open
Track: Data and metadata in, a structure out
Depends on: —
Priority: P3 2026-09-28 — a view over what the package already computes, plus the diagnostic that reads it; the person caught the clash by eye

## Goal

The bond and contact census rietx already computes for a converged Rietveld
fit can be asked of any coordinates, with the periodic images right. A fit
whose structure holds a non-bonded contact shorter than chemistry allows
says so. An agent writing its own search loop has a correct census to call,
and the skill tells it where that census and the evaluate-only path are.

## Context

**Source.** `solution case 1` (private corpus map § 5), described in
WP-1510. The agent solved the structure with its own annealing loop on
`Refinement.predict()` and wrote its own contact code for the chemistry
terms of the cost (a clash penalty and a coordination prior). Two defects in
that code cost the run most:

- **The images were shifted before they were wrapped.** The code applied
  ±1 cell shifts to symmetry images without first bringing each image into
  the cell. Contacts from any atom with a coordinate above 0.5 were
  evaluated a whole cell away and missed. The chemistry terms were blind
  through every annealing and polish stage, while the diffraction terms
  were right. No diagnostic fired. The person found it by opening an
  ordered-configuration CIF and seeing a ring sitting on its own inversion
  image in the next layer.
- **A pure-Python O(N²) contact loop ran about 7 h.** The vectorised
  rewrite finished in about 4 min.

**What exists.** `src/rietx/model/geometry.py`: `geometry_table` (line 421)
fills `RefinementResult.geometry` (`schemas/results.py:1159`) with bonds and
contacts out to `CONTACT_MAX_ANG` = 3.5 Å, using `_neighbours` (line 230),
whose completeness is proved by orbit counting (root CLAUDE.md). Limits:
Rietveld mode only, only on a result, `MAX_ASYM_ATOMS` = 200, and nothing
reads the contacts. No diagnostic code in `src/` names a short contact or a
clash.

*Superseded in part, 2026-11-16 (checked at `bc77a934e`).* The line numbers
moved: `geometry_table` is `model/geometry.py:639`, `_neighbours` `:268`,
the result field `schemas/results.py:2247`. "Only on a result" no longer
holds: `Refinement.geometry()` (WP-1815) answers with no live fit, at the
current model's values with every esd `None`, but it needs a `Refinement`
in Rietveld mode, so a bare `Structure` or a search loop's coordinates
still had no census. `rietx.solve.chemistry` (WP-1997, #562 S3) landed the
solve's own contact search, `contacts()`: a minimum-image search over the
expanded P1 cell, wrapped before shifted, checked pair for pair against
`_neighbours` on WP-1466's 21 phases, with this WP's boundary defect as its
test (`test_an_atom_past_its_inversion_image_clashes`), and the occupancy
rule below as its first cut (`site_clash` skips a pair whose occupancies
sum to at most 1 and names it in the notes). It is not exported and returns
bare index pairs, no labels, no symmetry codes and no bond/contact split, so
task 1 shares `_neighbours` through the geometry table's own assembly rather
than reusing it; task 2 can take its clash radii and occupancy rule. Still
true: nothing outside `solve` reads the contacts, and no diagnostic code
names a short contact or a clash.

**Occupancy is the design problem.** In a split-site model two
half-occupied sites overlap on purpose, and the run's clash was invisible in
the average structure. It showed only in an ordered configuration's CIF. So
the diagnostic must know which atoms coexist. The first cut can skip pairs
whose occupancies sum to at most 1 and say that it did. A configuration-aware
check waits for a representation of configurations. The rigid-body
milestone WP-1514 scopes carries the disorder copies.

**The skill gap beside it.** The agent wrote its own SNIP background,
although `rietx.background.snip` ships (WP-1323's fold carries that half),
and built its loop on `predict()` plus `set_values` on the `…dof.k` paths.
It had to learn that a coordinate DOF is relative (root CLAUDE.md, WP-1432),
so it tracked the current value and pushed deltas. The skill describes
neither pattern.

## Non-goals

- Hydrogen placement, and restraint kinds such as a tether (the milestone
  WP-1514 scopes).
- Figures of contacts. The person's asks (metal···metal contacts drawn, a longer
  bond cutoff, one picture per configuration) belong to WP-1468's controls.
- A configuration-aware clash check (after that milestone).

## Tasks

- [x] A public census over a `Structure` or bare fractional coordinates
      without a fit, sharing `_neighbours`, with its limits stated. A test
      puts an image pair across the cell boundary at a coordinate above 0.5
      (the run's defect class) and asserts the pair is found.
- [ ] A diagnostic on Rietveld results for a non-bonded, fully occupied pair
      closer than a stated floor (a sum of van der Waals radii less a
      tolerance, the source cited). Code named at review, with its `help.py`
      entry and a `Diagnostic.suggestion`.
- [ ] Partial occupancy handled as above, with a test on a split site.
- [ ] Cost stated for a large cell: the census on a few-hundred-atom P1
      supercell, timed as a range.
- [ ] Manual Part 1 and the api surface partition.
- [ ] Skill: a reference row for the shape "writing your own search loop":
      `predict()`, `set_values` on DOF deltas, this census. Tagged
      `(Measured: solution case 1)`.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_geometry_table.py tests/test_diagnostics_geometry.py -n auto --dist loadgroup
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The boundary-image test passes, and the diagnostic fires on a structure
with a planted clash and on none of the bundled acceptance structures.

## References

- Bondi, A. (1964). *J. Phys. Chem.* 68, 441–451. Van der Waals radii, one
  candidate for the floor. Read before citing.

## Handover log

- **2026-11-16** — task 1 (ghostshift runner, PR #1608). Anyone can now ask
  rietx for the bond and contact list of a structure without fitting it,
  including for coordinates a search loop is trying, and gets the very table a
  fit would report, found by the search whose completeness is already proved.
  The run's defect (images shifted before they were wrapped) cannot happen
  inside it: an atom above ½, or handed in at x = 3.95 by a loop that never
  wraps, still finds its 0.5 Å neighbour. The premise was half stale: a
  no-fit table already existed behind `Refinement.geometry()`, and the solve
  already had its own contact search (`solve.chemistry.contacts`), so nothing
  new was searched for; the work was a door and its tests.
  - *Done.* `rx.geometry_census(structure, coordinates=None)` in
    `model/geometry.py`, exported. `geometry_from_sites` now hands its loop to
    `_assemble(sites_of, values, phases, table, covariance)`, which the census
    calls with a values dict built from the structure, no table and no
    covariance (every esd `None`). It takes a `Structure` or a `Phase`;
    `coordinates` is an (n_atoms, 3) array for one phase or one entry per phase
    (`None` keeps a phase's own). The orbit split is decided at the coordinates
    given (`phase_orbit_split`, no form factor looked up). Before measuring it
    does what a `Refinement` does to its model first: the setting's cell ties
    (`cell_constraints(...).ties`) and `merge_site_twins`, the merge's message
    joining `GeometryTable.notes`; without the merge a site 3·10⁻⁴ off a special
    position listed its own images 0.003 Å apart as bonds. Occupancy is read
    once, by the merge's gate (corrected 2026-11-16 after review; this entry
    first said it was not read): a site whose occupancy marks it as a split
    pair is kept (`SITE_TWINS_KEPT`), and its halves are listed at whatever
    distance they sit, as bonded within the radii. A half-occupied O 3·10⁻⁴
    off a mirror lists a 0.0036 Å O1–O1 bond; a test pins that for task 3 to
    settle. The census also refuses a symmetry-fixed angle the cell disagrees
    with (`check_cell_angles`), as a `Refinement` does. Documented in `reference/derived.md` § Without a fit (executed
    example) and in the skill's `api.md` Results section (the verb gate
    required a door; task 6's search-loop row is still to write).
  - *Reuse answer.* `solve.chemistry.contacts` is a minimum-image search over
    the expanded P1 cell returning index pairs: no labels, no symmetry codes, no
    bond/contact split, and not exported. The census needed all three, which
    `_neighbours` plus the table's assembly already give, so it shares those.
    `chemistry.contacts` stays the solve's (it is already checked pair for pair
    against `_neighbours`); task 2 can reuse its radii and occupancy rule.
  - *Tests* (`tests/test_geometry_table.py`, +10): the P -1 boundary pair at
    x = 0.95 and 0.05 with the shifted-before-wrapped stand-in as positive arm
    (it misses at 0.95, finds at 0.05); bare coordinates across x = 1; x = 3.95
    and −6.05 never wrapped; census equals `Refinement.geometry()` before a fit
    on corundum, zincite and fluorite; a hexagonal cell stored b ≠ a with sites
    near ⅓,⅔ (ties and merge); rutile Ti moved off 2a (m 2 → 16) with orbit
    counting over the bonds; refusals.
  - *Revert checks (2026-11-16).* `base = 0` and a ±1 shell in `_neighbours`:
    the x = 0.95 boundary row fails, nothing else in the file. `base = 0`
    alone: only the x = 3.95 row fails (`_shell`'s spare cell covers stored
    coordinates in [0, 1)). Merge removed, or ties removed: the b ≠ a row fails.
  - *Review.* A read-only Opus subagent reviewed the diff (in place of
    `/code-review`, which edits the main checkout under the shift's rules). Its
    four findings were all taken, in `bf3fc4eb7`: the ties and the merge above,
    the x = 3.95 test, the cap-note assertion naming the contact cap, and
    clearer refusals for a one-phase structure's coordinates.
  - *Tier.* The census adds no flag, threshold, default or action, and no
    `_audit` row: it reads `CONTACT_MAX_ANG`, `MAX_CONTACTS_PER_ATOM`,
    `MAX_TORSIONS_PER_ATOM`, `MAX_ASYM_ATOMS` and `TWIN_COORD_TOL` as they are.
  - *Measured* (the workstation, Linux x86_64, py3.12 venv, `bf3fc4eb7` on
    `bc77a934e`, under load 14-37 from other jobs). Fast selection at `-n 4`:
    14860 passed, 280 skipped, 32 xfailed, 0 failed, in 1411 s (+10 passed
    against 14850 on main the same day; no new skip), 6.1 GB peak. The added
    tests cost 0.20 s together on that run (`tests.added_test_times`).
    Canary (`-n 4`, geometry_table, manual_api, skill, audit_table, help): 288
    passed, 78 s, 428 MB. Mac `.[dev]` arm64, file by file: geometry_table 37,
    manual_api 19, skill 174, skill_cli 13, audit_table 23, docs_consistency 26.
    `python -m tests.reader_output`: exit 0, unchanged against `bc77a934e`.
  - *Questions for Yue.* (1) The name and the top-level export,
    `rx.geometry_census`; documenting it freezes it. (2) `MAX_ASYM_ATOMS` = 200
    skips a phase in the census as at fit close, so task 4's few-hundred-atom
    P1 supercell gets an empty table and a note. Should the census lift it (a
    keyword, or no cap off the fit-close path), given it costs the caller's
    time rather than a fit's? Task 4 times it either way. (3) The merge moves
    coordinates the caller handed in (and says so); a search loop sees its trial
    atom snapped. That is what its fit would do; say if you want it a choice.
  - *Next.* Task 2, the clash diagnostic, reading this census over
    `result.geometry`'s fully occupied non-bonded pairs; the floor and its
    source (Bondi 1964 is the WP's candidate; `solve.chemistry` already cites
    Shannon, Pauling and Pyykkö radii per #677) are a physics choice to put to
    Yue before code. Then task 3 (occupancy, `solve.chemistry`'s rule), task 4
    after question 2, then 5 and 6.

- **2026-09-28** — created from the review of `solution case 1`, with
  WP-1510 to 1512 and 1514 to 1517. Nothing started.
