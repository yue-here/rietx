# WP-2006 — Readers, crystallography and GUI codes, and the dead surface

Milestone: generality · Status: 🔄 2026-11-17 — claimed by ghostshift (part 2, the tiers; part 1 merged as PR #1101)
Track: The audits
Depends on: 2001
Priority: P3 2026-10-19 — 2001 closed, so nothing blocks it; expected mostly tier 1 (records of what was done to a file); the fast one

## Goal

The codes raised in `src/rietx/io/` (90 `code="…"` literals, plus five the GSAS instrument
readers raise through a name), `crystallography/` (20) and `gui/` (27) are in the audit
table with a tier, and the public surface's 2 238 entries have been walked for
reachability, with the unreached ones listed for the maintainer. Inventory from
`docs/reference_pages.diagnostic_index()`, never from the literal grep (2001).

## Context

The rule is `../milestones/generality.md` § The rule. The record § Scope says the reader
codes were measured and not pruned at the open, being *records of a repair*: "I applied the
attenuator", "I snapped β to 90", "σ withheld because the scale is unknown". A record is
tier 1 by construction. This WP confirms that row by row rather than assuming it, because
"nothing wrong here" is weaker than a finding (memory `a-clear-is-weaker-than-a-finding`),
and because `io/CLAUDE.md`'s rule "a reader may repair a file only where it can say that it
did" has thresholds of its own: `CIF_ANGLE_CORRECT_MAX_DEG` (0.1°, in
`src/rietx/crystallography/cif.py`, not under `io/`) decides whether a fixed angle is
snapped or refused (WP-1028, ≤ 830 ppm in d), and that number is a tier-3 threshold under
a tier-1 action.

The GUI's 27 are HTTP error names (`NOT_RUNNING`, `PROJECT_ERROR`), not `Diagnostic`s;
they are in the 276 literals and not the 256 codes. The table's code rows are held equal
to `DIAGNOSTIC_HELP`'s keys (2001), so these get no row; the handover lists them as not
heuristics.

**The dead surface** is the API half of DESIGN.md's purpose (§ Why this package
exists: the API follows current Python practice), not the heuristics half this milestone
mostly audits; it rides here
because the walk is cheap and the seam is the same session's. 3 of 193 top-level exports are used by nothing in `src`, `examples`
or `gui`: `IndexingEvidence` (named in the skill), `CaveatEvidence`, `CandidateEvidence`
(tests only). The derived surface (`tests/api_surface.py`, `derive_surface()`) is 2 238
entries; reachability over those has not been run. This is a mechanical job for a cheap
model: for each entry, is it reached from an example, the skill, the GUI, the manual's
Part 1, or another public entry? An entry reached by tests alone is a candidate the
maintainer rules on. **The maintainer rules; this WP removes nothing** (a removed entry
fails `test_manual_api.py`'s partition until documented as removed, and the compatibility
promise stages every break).

### Inherited

Pruned 2026-11-17 (part 2's session; the handover entry says why each other entry went).

- **From WP-2013 (2026-11-03, PR #1369): a reader default the hump ruling left standing.** `HumpComponent.position` is now required of a caller (maintainer, 2026-11-02), because the old 0.0 placed a hump below any measured range. `io/recipe.py`'s background-peak builder still writes `0.0 if pos is None`, silently, so a PowderLine recipe whose `single_peaks` entry has no position gets the placeholder the ruling removed, and a flagged position starts its refinement there. Refusing it or reporting it changes what `read_recipe` returns, so it goes to the maintainer before merge (memory rule on reader output). No recipe with a null position has been seen; whether PowderLine writes one is unchecked. Still open; on the maintainer's list of 2026-11-16.
- **From WP-2001 (2026-10-19): numbers inside a dict, list or array.** The constant walk sees module-level numbers and tuples of numbers only, so a number held in a dict, list or array in `crystallography/` and the walked `io/` and `gui/` files is audited by hand. Nobody has looked yet; part 2 did not.
- **From [2014](2014-a-heuristic-meets-the-judge-on-every-path.md)'s close, confirmed 2026-11-17: a silent repair in the FullProf reader.** `fullprof._OCCUPANCY_RTOL = 5e-3` lets per-site occupancy ratios spread 0.5 % and then builds 1.0 on every site with no diagnostic (`io/projects/fullprof.py` around lines 2364 and 3635). A probe that scaled one site's Occ by 0.996 built every site full with no record; 0.995 is refused. The constant's comment puts the file's rounding at 2e-5. The same constant gates the magnetic Scale × f² match (around line 2730). A fix adds a record or narrows the bound, and either changes what `read_project` returns, so it goes to the maintainer. The row is a tier-3 candidate in `2006-batch/tiers.md`.
- **2026-10-20, from [1986](1986-guides-and-theory-move-over-and-the-old-tree-retires.md): declared names with no writer.** `PhaseMicrostructure.separable` and `.size_strain_collinearity` (written only on the report's copy) and `ProjectFormat.refuses` (set by no member). Re-checked 2026-11-17; the write, retire or document choice is in `2006-batch/surface.md` for the maintainer. The third, `SuggestedAction.vetoed_by`'s docstring, was fixed in part 2.

## Non-goals

- `indexing/`: 2007 (its own rulebook, 48 codes, 76 constants, the benchmark).
- Changing a reader's repair (the action) or `io/CLAUDE.md`'s dispatch rules.
- Removing any public entry: a follow-up WP per batch of removals, with the break staged.

## Tasks

- [x] Inventory the 142 codes (io 90 literals plus five by name, crystallography 20, gui
      27): raise site, `level`, condition, whether it records an act or asserts a
      judgement. `LANDE_G_ASSUMED` and `MAGNETIC_ION_ASSUMED` are raised here and in
      `strategy/magnetic.py`; 2002 tiers them on both sites and this WP reads the row.
- [x] The constants of `io/` (~30) and `crystallography/` (66 by AST), entered by 2001's
      walk: tier each, expected mostly tier 1 (byte offsets, physical limits) with the
      few thresholds named above. (2026-11-17: 120 constant rows; 62 tiered, 22 tier-3
      candidates and 36 left, `2006-batch/tiers.md`.)
- [x] Tier each; for the few thresholds (`CIF_ANGLE_CORRECT_MAX_DEG`, the attenuator
      conventions measured per format, the axis refusal), evidence and families.
      (2026-11-17: 218 of 290 rows tiered, 87 responses given; 36 tier-3 candidates and
      36 left rows in `2006-batch/tiers.md`.)
- [x] The reachability walk over `derive_surface()`'s 2 238 entries, as a script in
      `tests/` run by hand (a Haiku-grade task: collate, do not judge), its output a table
      with one row per unreached entry and where it *is* referenced.
- [x] The batch to the maintainer: tier-3 rows with grounds, plus the unreached-entry
      table with a recommendation per row. (2026-11-17: `2006-batch/tiers.md` and
      `2006-batch/surface.md`.)
- [ ] Approved demotions (expected few); rulings dated into the table.
- [ ] Tests; the fast count moved by exactly the tests added.
- [x] Skill: `references/diagnostics-projects.md` and the io rows of `diagnostics.md`
      checked against the table; none expected to move. (2026-11-17: no level, message or
      suggestion changed, so no skill row moves.)

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_audit_table.py -q          # no io/crystallography/gui row at unaudited
.venv/bin/python -m pytest tests/test_readers*.py tests/test_cif*.py tests/test_gui*.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- `docs/milestones/generality.md`; `src/rietx/io/CLAUDE.md`; WP-1028, 1047, 1117 (the
  derived surface).

## Handover log

- **2026-10-24** — PR #1101 merged (`50bc4555`, review round 4), by `/pr-review`.
  *Done*: part 1, which removes and rules on nothing.
  `tests/reachability_walk.py` (run by hand, not collected) writes
  `docs/wp/2006-batch/reachability.csv`, one row per `derive_surface()` entry
  (2 267). `collate_inventory.py` writes `inventory.json` from the tree and the
  one hand-written input, `judgements.json`: 115 codes with raise site, level,
  condition and act or judgement; 225 module-level numbers with what each
  decides; the reader decisions; the GUI's HTTP error names. The maintainer
  accepted the folder's place under `docs/wp/2006-batch/` (2026-10-24).
  *Measured*: `cut_texts()` over `judgements.json` returns nothing at the merged
  head; the review re-scanned all 346 texts by hand over three rounds.
  *Gotchas*: the walk reads text, not imports, so a common member name
  over-counts and a `getattr` with a built string is missed; each cell carries
  its evidence grade. The GUI side has 32 names by AST where the WP says 27.
  Next: part 2, the tiers, after the gate ruling (WP-2004).

- **2026-10-18** — created, from the milestone's opening session.
