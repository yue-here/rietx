# WP-2006 — Readers, crystallography and GUI codes, and the dead surface

Milestone: generality · Status: 🔄 2026-11-17 — part 2's tiers in PR #1636: 218 rows tiered; 36 tier-3 candidates, the FullProf occupancy repair and three writer warnings wait on the maintainer
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
      (2026-11-17: 218 of 290 rows tiered, 56 responses given; 36 tier-3 candidates and
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

- **2026-11-17** — part 2, the tiers, by a ghostshift runner. PR #1636.
  Ruled by Yue, 2026-11-16 (decision walk): run 2005-2007 now under the gate as written.
  Three of every four reader, crystallography and GUI rows in the audit table now carry a
  tier with its evidence. Almost all of them are tier 1, because a reader's code records a
  repair the file's format forces, which is what the WP expected. The rest are rietx's own
  numbers or conventions. They need the maintainer's approval or a test before they can be
  tiered, and each is written up with what it waits on. Nothing was removed, and no level or
  message changed, so a reader receives the same text. One inherited suspicion is now a
  confirmed defect: the FullProf reader builds a 0.4 % vacancy as a full site and says
  nothing.

  *Done*: 218 of the 290 unaudited rows tiered (98 codes, 56 of them given a response; 58
  suggestion sites; 62 constants): 190 tier 1, 25 tier 2, 2 caller, 1 invariant. `2006-batch/tiers.md` holds the other 72: 36
  tier-3 candidates with both grounds and their stakes (14 codes, 22 constants, the magnetic
  ones marked for Mike) and 36 constants left at `unaudited` with the test that would close
  each, plus the three reader decisions audited by hand and 59 lanes' notes on tiered rows.
  `2006-batch/surface.md`: the walk re-run at HEAD (2 504 entries), 29 entries reached by no
  use, all rigid-body and restraint constructor fields, each recommended kept; the three
  exports the WP named, kept; the declared names with no writer. `SuggestedAction.vetoed_by`'s
  two docstrings now say what sets it. `docs/practice.md` gained this session's tier-2
  program-default rows. Inherited pruned: the `VOLUME_RATIO_BOUNDS` entry went (tiered 2 under
  the #1121 ruling, 2026-10-24); the seven-programs rule went (it is in `generality.md`); the
  WP-2001 mechanics went, and its GUI guard note with it (`Plan.svelte`'s 0.98 is an initial
  value replaced by `GET /api/plan` on load, so the GUI holds no second copy); the five reader
  decisions went (dif, peaklist and gsas are walked rows, bruker_raw and pdcif are audited in
  `tiers.md`, and pdcif's zero-weight note was stale: WP-1952 excludes the point and reports
  it); the B15 entry went (the form-factor rows follow 2002's ruling); the #1058 triage line
  went (part 1 landed). `PATTERN_DEAD_CHANNELS` is shared with `refine.py` and left to WP-2005.
  `/code-review high --fix` did not run: the branch's python is table data and two docstrings,
  and the generality judge read the table.
  *Measured* (Darwin arm64, `[dev]`, merged with `origin/main`): fast selection 14 685 passed, 433
  skipped, 32 xfailed, 1 failed in 645 s: `test_silence.py`, because a code row declaring a
  `warning` response needs a silence pair (a fixture where it fires and one where it stays
  silent). The 31 warning responses without one were held back, each proposed sentence kept in
  `tiers.md`'s notes; `test_silence.py` and `test_audit_table.py` then passed (59). No test added. `tests.reader_output` exits 0 (unchanged against the merge-base). `session_usage.py lanes` finds no lanes
  under this runner's id; three read-only lanes wrote the rows (Opus on crystallography,
  Sonnet on the pattern readers and the project readers).
  *Findings, nothing fixed*: (1) `fullprof._OCCUPANCY_RTOL` (5e-3) builds a site at Occ ×0.996
  beside full ones as full, with no record; ×0.995 is refused (probed); it also gates the
  magnetic Scale × f² match. (2) `FULLPROF_OCCUPANCY_UNCHECKED` warns on every one-atom phase,
  including symbols with one setting (F m -3 m probed). (3) `GSAS2_CIF_FIELD_NOT_WRITTEN`,
  `GSAS2_INSTPRM_FIELD_NOT_WRITTEN` and `GSAS_PRM_FIELD_NOT_WRITTEN` warn on every write, which
  § Attention is a cost's clause 1 does not admit. (4) `CIF_MAGNETIC_SYMMFORM`,
  `GSAS2_GPX_PHASE_MAGNETIC` and `RECIPE_FIELD_DROPPED` raise at two levels under one code. (5)
  `cif.py:98`: a fixed angle within 1e-3° of its value is neither snapped nor reported (≤ 8.3
  ppm in d). (6) `gui/imports.WAVELENGTH_RTOL` (5e-4) matches Cu but not a header's 0.71 (Mo)
  or 0.56 (Ag). (7) `bruker_raw.py:346`'s `atol=1e-6` runs with numpy's default `rtol=1e-5`, so
  the tolerance applied is about 1e-4°. (8) GSAS-II 5.8.4's CW `.prm` importer never reads
  PRCF12 (in `docs/practice.md`).
  *Gotchas*: a reader code's `where` is an interval or a column name, never a parameter path,
  so every reader row with a response declares `scope`. Seven code rows are tiered on the act
  alone, and each holds only as far as the threshold rows it names, all of them in `tiers.md`.
  *Generality* (judge, 2026-11-17; 104 of 222 rows read in full, 31 evidence claims checked):
  tier 2, 23 of 26 hold; caller, both hold; warning sentences, 33 of 37 name a result number;
  tier-1 sample, 44 of 45 hold; escalation family, none. Weak: `RECIPE_PLAN_STAGED` (PowderLine
  dissents; author: agreed, now a tier-3 candidate); `GSAS2_INSTPRM_GEOMETRY_ASSUMED` (kind 3,
  sentence named no number; author: fixed); `CALC_POINTS_PER_FWHM` (the tests do not exercise
  it; author: agreed, back to unaudited); `K_FLOAT_TOL` and `_SNAP_MESSAGE_SITES` (no invariance
  or cap test; author: agreed, back to unaudited); the three writer warnings' level (author:
  agreed, a level change is the maintainer's). Cannot tell: `FULLPROF_ORIGIN_CHOICE`'s manual
  quote (author: checked in FullProf 8.20's manual, cited in the row). Magnetic rows that settle
  a reading default: `CIF_MAGNETIC_CENTERING_ASSUMED`, `CIF_MAGNETIC_ION_UNCHARGED` (info, yet
  its sentence asks for an act), `TOPAS_MOMENT_ION_UNCHARGED`, for Mike.
  *Settled by Claude* (most important first): code rows tiered on their act with the
  threshold left separate, under § The rule's "each part tiered on its own" (the alternative
  held the code row back with its threshold); `RAS_ATTENUATOR_PRESENT` at tier 2 on GSAS-II's
  default although no `.ras` on disk varies the column, under tier 2's program-default clause
  (alternative: a tier-3 candidate); two caller rows, under the caller class's two conditions;
  the judge's weak rows taken back to unaudited rather than argued, under B10 and the
  invariance rule; `/code-review` skipped, under its prose-only clause read for table data;
  `vetoed_by` documented rather than written, under WP-1076; `PATTERN_DEAD_CHANNELS` left to
  WP-2005 to avoid a shared row.
  *For the maintainer*: approve or demote the 36 tier-3 candidates (`tiers.md`; magnetic ones
  are Mike's); rule on the FullProf occupancy repair, the one-atom warning and the three
  writer warnings (each changes what a reader receives); the recipe hump `0.0` (still on the
  2026-11-16 list); write or retire the declared names in `surface.md`.
  Next: the maintainer's batch. Then the 31 silence pairs, which give the held warning responses. Then the approved rows dated into the table, and the 36 left
  constants closed by the tests `tiers.md` names (one small test each), then the numbers
  inside dicts and lists (still unaudited by hand).

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
