# WP-1913 — what the benchmark agents wrote by hand: a mixed site, a special-position retry loop, and `.esd`

Milestone: unscheduled · Status: ⬜
Track: Data and metadata in, a structure out
Depends on: —
Priority: P3 2026-10-05 — a workaround covers each: the by-hand ties are documented, the refusal names its fix, and `.esd` gets a field-list pointer

## Goal

Three API-shape frictions that headless benchmark agents worked around by hand
are each closed or declined with a reason. A model that cannot have a parameter
table is refused when the `Refinement` is built, and the refusal names every
offending atom. A mixed site is declared in one call that derives its ties.
And `.esd` on a refined parameter points straight at the field.

## Context

Issue #728 (mustachefeeling, 2026-10-05), parts 3, 4 and 5, from headless
agent runs on `961f2eb5` that indexed, solved and refined laboratory and
synchrotron standards with only the repo's documentation. Parts 1 and 2 of
that issue went to WP-1511 and WP-1532. None of the three here is a wrong
number. Each is a helper the next agent would write again: the by-hand
mixed-site ties, the retry loop, and `.esd`.

**Part 4, the special-position refusal: reproduced at `32ef5a6`.** NaCl
(F m -3 m) with `Na.x.vary=True`: `rx.Refinement(...)` constructs;
`ref.parameters()` and `ref.fit(...)` both raise "phases.0.atoms.0 sits on a
fully fixed special position; its site symmetry allows no positional freedom
— set vary=False" (`params/vector.py:1229-1232`). The agent hit it after a
solve step produced fixed and free sites together, and wrote a retry loop.
Two facts constrain the fix.
- **`edit` already does what `__init__` does not** (WP-1035): it builds the
  *proposed* pair's `ParameterTable` and refuses before recording
  (`refine.py:2018-2057`), because pydantic knows no crystallography. The same
  check in `__init__` costs the table build that the first `parameters()` or
  `fit()` performs anyway.
- **The table stops at the first refusal** (WP-1035's caveat). A message
  naming every offending site needs a loop over the atoms, the way
  `_site_rows` walks them, not the raise.

The issue also asks for `Refinement.fix_special_positions()`, which sets those
coordinates' `vary=False`. A verb the caller invokes is not a silent repair,
so it does not conflict with the root rule that a table never corrects
silently. Whether it commits a history node is part of the design.

**Part 3, mixed sites: no constructor.** Today a site shared by two species
takes `ref.tie(occ_B, occ_A, scale=-1, offset=1)`, then `tie_equal` on Biso
and on every coordinate DOF. This route is taught in the skill
(`SKILL.md:193`) and the manual (`using/concepts.md:143`). The issue proposes
`Phase.mix_sites(i, j)` or `Atom.shares_site_with`. Ties live on the
`Refinement`, though: `Refinement._ties` is their one authority (WP-1070) and
they auto-commit `set_tie` nodes. So a helper is a `Refinement` verb over
`tie`/`tie_equal`, not a schema field. A series re-declares ties per pattern
through `constrain=(index, ref)` (WP-1441), and the verb must work there too.
Which atoms share a site is already computed: `gui/symmetry.orbit_collisions`
(`gui/symmetry.py:873`) groups co-located orbits and tells a legal mixed site
from over-occupancy. It lives under `gui/`, so a core verb lifts it rather
than copying it. The proposed `OCC_PAIR_ILL_CONDITIONED` has no measurement
behind it. With the occupancies tied, one occupancy column remains, scaled by
the difference of the two scattering factors. The covariance already gives a
weak column an honest, large esd (WP-1110, WP-1463: "a tiny column is live").
Measure whether that esd and `HIGH_CORRELATION` already say it before adding
a code.

**Part 5, `stderr` against `esd`: checked.** `RefinedParameter` declares
`stderr` (`schemas/results.py:55`), and so do the geometry rows and QPA's
`weight_fraction_stderr`. `ParameterRow.esd` and the microstructure readings
use `esd`. `RefinedParameter(...).esd` raises "'RefinedParameter' object has
no attribute 'esd'; its fields are ['path', 'value', 'stderr', 'vary',
'at_bound']". `Base.__getattr__` (`schemas/common.py:444`) is "a pointer, not
an alias" by design. So the cheap fix is a pointer that names `stderr` for
`esd` (the near-miss table in `rietx._nearmiss`); an alias or a rename is a
schema change across every result reader.

## Non-goals

- Parts 1 and 2 of #728 (WP-1511, WP-1532).
- Repairing a stored `vary=True` silently, at read or in the table.
- Occupancy constraints across *different* sites (TOPAS's `occ_merge`; the
  GUI's docstring records why rescaling is not copied).
- Renaming `stderr` across the schemas.

## Tasks

- [ ] Decide with the maintainer which of the three are wanted, and for
      part 4 whether `fix_special_positions()` ships beside the earlier refusal.
      *Part 4 decided 2026-10-06: `fix_special_positions()` ships, beside the
      refusal (draft PR #754). Parts 3 and 5 are not decided.*
- [ ] Part 4: `Refinement.__init__` builds the table as `edit` does and
      refuses there, naming every fully fixed atom with a free coordinate;
      the GUI, `.rxt` and project open paths checked for a second builder.
- [ ] Part 3: the mixed-site verb over `tie`/`tie_equal`, refusing two atoms
      that do not share an orbit (the lifted `orbit_collisions`), and usable
      through a series' `constrain=`; then the measurement deciding whether
      `OCC_PAIR_ILL_CONDITIONED` is needed at all.
- [ ] Part 5: `esd` → `stderr` in the attribute pointer, with a test that
      the message names the field.
- [ ] `help.py` and Manual Part 1 for every new public name (the api-surface
      partition fails until each is documented).
- [ ] Tests (unit; no acceptance dataset needed).
- [ ] Skill: `SKILL.md:193` teaches the by-hand ties. Replace that sentence
      with the verb at no net growth, since the body is over its budget
      (`tests/skill_caps.py`).

## Acceptance

`rx.Refinement` over the NaCl model above raises at construction, naming
`phases.0.atoms.0` and every other fully fixed atom with a free coordinate.
A two-species site declared with the new verb refines with occupancies
summing to 1 and one shared Biso and position, and so does the by-hand tie
set it replaces, to the same numbers. `.esd` on a `RefinedParameter` names
`stderr`.

```sh
.venv/bin/python -m pytest tests/test_params.py tests/test_params_surface.py tests/test_schemas.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #728 (parts 3-5). WP-1035 (the proposed-table check on `edit`),
  WP-1070 (user ties), WP-1441 (ties per pattern in a series), WP-1463 (a
  tiny column is live).

## Handover log

- **2026-10-06** — Maintainer decision on part 4 of #728, through draft
  PR #754: `Refinement.fix_special_positions()` is wanted, and construction
  and `fit()` still refuse a free coordinate on a fully fixed special
  position. #754 also documents the one-call extinction screen, which is
  #728's part 2 and WP-1532's. Parts 3 and 5 are not decided.

- **2026-10-05** — created, from the 2026-10-05 issue triage (issue #728,
  parts 3-5). Checked against the tree at 32ef5a6: part 4 reproduced
  (construction succeeds, `parameters()`/`fit()` raise naming only the first
  atom); part 3 has no constructor, and the by-hand ties are the documented
  route; part 5's `.esd` raises with a field list that includes `stderr`. No
  open WP owns them: 1528 is a `Cell` docstring, 1532 places #661's skill
  rows (it took #728's part 2), 1517 replays steers, 1460 deduplicates
  correlation rows, and 1035 and 1337, the refusal WPs, are closed. Next: the
  maintainer's pick of the three.
