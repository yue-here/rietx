# WP-1913 — what the benchmark agents wrote by hand: a mixed site, a special-position retry loop, and `.esd`

Milestone: unscheduled · Status: 🔄 2026-11-18 — part 4's every-site refusal and part 5 landed (PR #1675); part 4's construction half and part 3's verb name wait on the maintainer
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

**The reporter's picks** (#728, posted 2026-10-12 08:29Z, folded from
`### Inherited` 2026-11-18). Item 4: refuse at construction, and name every
atom on a fully fixed special position, not only the first. Item 3: a
one-call mixed-site helper that derives the occupancy, Biso and coordinate
ties, with an info finding where the data cannot separate the pair; they
named `Phase.mix_sites`, but ties live on `Refinement` (WP-1070). Item 5: the
pointer names `stderr`, with no alias.

**The seed ask** (#728's unnumbered fifth ask, folded 2026-11-18).
`Refinement.suggest` reports an FCJ axial term seeded at 0 as "without
leverage", since its derivative vanishes there; the showcase agent seeded it
at 0.02 by hand. `strategy/suggest.py` holds probe seeds for softplus,
roughness and Stephens only. The 2026-11-16 decisions walk put a probe seed
for the axial term on Yue's consent list, taking the plan's own seed constant
once PR #1372 (WP-1955's aperture lift) settles it.

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
      refusal (draft PR #754). Part 5 settled by Claude 2026-11-16 (a
      pointer, no alias). Part 3's name and part 4's construction half wait
      on the maintainer (the 2026-11-18 entry).*
- [ ] Part 4: `Refinement.__init__` builds the table as `edit` does and
      refuses there, naming every fully fixed atom with a free coordinate;
      the GUI, `.rxt` and project open paths checked for a second builder.
      *Half landed 2026-11-18: the table's refusal names every site, a rigid
      body's origin included, and `fix_special_positions()` clears origins.
      Moving the refusal into `__init__` waits on the maintainer: it leaves
      no `Refinement` to call `fix_special_positions()` on.*
- [ ] Part 3: the mixed-site verb over `tie`/`tie_equal`, refusing two atoms
      that do not share an orbit (the lifted `orbit_collisions`), and usable
      through a series' `constrain=`; then the measurement deciding whether
      `OCC_PAIR_ILL_CONDITIONED` is needed at all.
- [x] Part 5: `esd` → `stderr` in the attribute pointer, with a test that
      the message names the field. *Both ways, through `_nearmiss.SYNONYMS`,
      so every schema hint and path hint shares it (2026-11-18).*
- [ ] `help.py` and Manual Part 1 for every new public name (the api-surface
      partition fails until each is documented).
- [ ] Tests (unit; no acceptance dataset needed).
- [ ] The seed ask: `suggest` probes the FCJ axial term at the plan's seed
      constant, after PR #1372 merges (the 2026-11-16 consent item).
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

- **2026-11-18** — a caller whose model asks for free coordinates on several
  fully fixed special positions now hears about all of them in one refusal,
  so the benchmark agent's retry loop (fix one site, rebuild, meet the next)
  is no longer needed. `RefinedParameter(...).esd` now says "did you mean
  'stderr'?". A rigid body's origin on a fixed site was a gap: the table
  refused it while `fix_special_positions()` returned `[]`, and now the verb
  clears it. Two halves wait on the maintainer: whether `rx.Refinement(...)`
  itself refuses (below), and part 3's verb name (the 2026-11-16 brief Y2).
  PR #1675 (ghostshift runner).
  *Done.* Part 5: `_nearmiss.SYNONYMS` maps `esd` ↔ `stderr`, one dot- or
  underscore-delimited word at a time, so every near-miss surface (schema
  attributes, plan fields, paths) points both ways, `weight_fraction_esd`
  included; a meta-test holds each word to a real schema field spelling.
  `difflib` alone scored the pair at 0.22, under its 0.6 cutoff. Settled by
  Claude under `schemas/common.py`'s "a pointer, not an alias" and the
  Non-goals' fence on a rename (the 2026-11-16 walk, item 91, which the
  reporter also picked); the alternative was leaving the field list as it was.
  Part 4's message half: `params.vector.fixed_sites_asking_to_vary` walks the
  structure as `_collect` routes it (an atom a body places or a mode moves is
  its owner's; every other atom and every body origin is checked against its
  stabiliser). `ParameterTable.__init__` refuses every site it returns before
  the walk, in walk order, and one site keeps its sentence byte for byte.
  `fix_special_positions()` reads the same list, so it clears exactly what the
  table refuses, body origins included. The refusal sits in `__init__`, clear
  of `_collect_cell`, which WP-2150 edits next. Inherited pruned: both entries
  folded into Context (the reporter's picks; the seed ask), and the seed ask
  became a task.
  *Measured.* `ParameterTable` build against `Refinement` construction, min of
  5, macOS arm64, `[dev]`, on 14 test CIFs: the table costs 1.2-6.9 ms where
  construction costs 0.5-2.3 ms, and one magnetic file (cod_4002052) 576 ms
  against 0.9 ms. Fast selection on this branch merged with main `8996cc5cf`, macOS arm64,
  `[dev]`: 14777 passed, 433 skipped, 32 xfailed, 0 failed; the 5 added tests
  cost 0.21 s together. `tests.reader_output` exit 0.
  *Review* (`/code-review high`, run without `--fix` because its test runs
  would bypass the shift's one-suite lock; fixes applied by hand). Taken: the
  gathered refusal had run after the walk, so every other table refusal
  outranked it, and the verb kept its own copy of the walk (the copy that had
  missed body origins); both now read one walk, which refuses first. Taken: a
  meta-test for `SYNONYMS`. Declined: walk-order return from the verb (its
  docstring and test promise sorted paths); a cap on a long list of sites
  (the caller needs every name, and the verb fixes them in one call).
  Declined as another track's: `gui/session.py`'s `_edit_on` marks only the
  first path a refusal names, so the GUI highlights one of several sites. It
  highlighted one before as well, so nothing regressed; the GUI track owns it.
  *Not generalised, deliberately:* the refusals of `vary=True` on an atom a
  rigid body places or a distortion mode moves still stop at the first atom.
  Each names a different owner and remedy, no bulk verb clears them, and the
  benchmark report was the special-position one.
  *Decision for the maintainer: should `rx.Refinement(...)` itself refuse a
  free coordinate on a fully fixed special position?* Today construction
  succeeds and the first `parameters()` or `fit()` refuses. That is what PR
  #754 shipped, and the 2026-10-06 ruling on #754 approved it ("as this draft
  does"). This WP's task and the reporter's 2026-10-12 pick ask for the
  refusal at construction. The two conflict: a construction refusal leaves no
  `Refinement` to call `fix_special_positions()` on, so the verb you asked for
  would serve only a structure edited in place after construction. With every
  site now named, the agent's loop is one call: `ref.fix_special_positions()`
  before the fit. Options: (a) leave construction as it is (recommended, a
  lean; nothing to build); (b) refuse at construction and accept that
  `fix_special_positions()` mostly goes unused, at one extra table build per
  construction (above); (c) refuse at construction and add a structure-level
  fixer, a new public name. The crux is whether refusing one call earlier is
  worth the verb's reach. (a) wins there, since the refusal already comes
  before any fit work. Evidence that callers keep building a `Refinement` they
  never list or fit would flip it.
  *Not done.* Part 4's construction half (above). Part 3, which waits on its
  name. The seed ask, which waits on PR #1372. The skill sentence, which is
  part 3's.
  *Next:* the maintainer's answers on the construction refusal and on part
  3's name. Then part 3 (lift `gui/symmetry.orbit_collisions` into the core,
  the verb over `tie`/`tie_equal`, the `constrain=` route, the measurement
  for `OCC_PAIR_ILL_CONDITIONED`) and the skill sentence; the seed ask after
  #1372 merges.

- **2026-10-08** — a caller whose model marks a fixed special position as
  refinable can now clear every such flag in one call instead of meeting the
  refusal atom by atom. PR #754 (#728 items 4 and 2, head `b1c82ff9`) merged as
  `133d6287` after three rounds, behind an opt-in decided on the PR.
  *Done.* `Refinement.fix_special_positions()` clears `vary` on every coordinate
  of a fully fixed special position and returns the paths. The table's refusal now
  names the method. Item 2 is documentation only: the indexing manual shows the
  one-call `determine_extinction_symbol(data, idx.candidates[0], ...)` screen.
  *Gate:* stacked with the run's other merges (#829, #825, #809, #754, #749, #815)
  on `main` `a3f9140a` as `166d362e`, macOS 26.6.2 arm64, `[dev,jax]`. The full
  suite, fast and slow together, gave 9231 passed, 116 skipped, 1 xfailed and 2
  failed. Both failures also fail on `main` alone on that machine: `toy_anomalous`
  (#760, which open PR #828 fixes) and a hypothesis counterexample in
  `test_indexing_reduce.py`. `main` after the merges is content-identical to that
  tree.
  *Not done here.* Part 4's task above is the default (`__init__` building the
  table as `edit` does). Parts 3 and 5 are untouched. #728's item 1 is WP-1511's.
  *Next:* the maintainer's decision on which of the three are wanted.

- **2026-10-06** — Maintainer decision on part 4 of #728, through draft
  PR #754: `Refinement.fix_special_positions()` is wanted, and construction
  and `fit()` still refuse a free coordinate on a fully fixed special
  position. #754 also documents the one-call extinction screen, which is
  #728's part 2 and WP-1532's. Parts 3 and 5 are not decided.
  *Recovered 2026-10-10: committed after PR #796 merged, so it reached main
  only now.*

- **2026-10-05** — created, from the 2026-10-05 issue triage (issue #728,
  parts 3-5). Checked against the tree at 32ef5a6: part 4 reproduced
  (construction succeeds, `parameters()`/`fit()` raise naming only the first
  atom); part 3 has no constructor, and the by-hand ties are the documented
  route; part 5's `.esd` raises with a field list that includes `stderr`. No
  open WP owns them: 1528 is a `Cell` docstring, 1532 places #661's skill
  rows (it took #728's part 2), 1517 replays steers, 1460 deduplicates
  correlation rows, and 1035 and 1337, the refusal WPs, are closed. Next: the
  maintainer's pick of the three.
