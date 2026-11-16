# WP-1513 — The contacts a chemist checks by eye

Milestone: unscheduled · Status: 🔄 2026-11-16 — claimed by @mustachefeeling
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

- [ ] A public census over a `Structure` or bare fractional coordinates
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

- **2026-09-28** — created from the review of `solution case 1`, with
  WP-1510 to 1512 and 1514 to 1517. Nothing started.
