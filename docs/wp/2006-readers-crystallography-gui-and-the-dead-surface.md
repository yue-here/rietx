# WP-2006 — Readers, crystallography and GUI codes, and the dead surface

Milestone: generality · Status: 🔄 2026-11-24 — PR #1636 merged with main and carries Mike's magnetic rows; three rows and a 4-fold reader defect back to Mike, a read-time tier question to Yue; the successor writes the 2026-11-21/22 rulings
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
- [ ] `read_pattern` refuses a multi-scan file read with no `scan=`, listing the scans, in
      place of `PATTERN_MULTISCAN_DEFAULTED`'s scan 0 (ruled by Yue 2026-11-21, § Rulings 23).
- [ ] The import wizard's scan picker for a file holding several scans (ruled by Yue
      2026-11-21, § Rulings 23). It may move to a gui-overhaul WP if the rebuilt page
      owns the wizard by then.
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

## Rulings

From the rulings triage of 2026-11-21, over this file and PR #1636's batch
(`2006-batch/tiers.md` and `surface.md` on that branch). Nothing here is the maintainer's
approval, and no tier-3 row is recorded as approved.

**Settled by Claude, 2026-11-21.**

1. *"The gate ruling" in the status line* is stale. Yue ruled on 2026-11-16 that 2005 to 2007
   run now (`generality.md` § The order), and PR #1636 ran part 2 under it.
2. *The 29 unreached surface entries and the three indexing evidence exports* are kept.
   Settled under the reading that a keyword constructor uses its fields by construction and
   a return type is surface whether or not anyone spells it. Keeping deletes nothing. The
   alternative was to list them for removal.
3. *`PhaseMicrostructure.separable` and `.size_strain_collinearity`* stay `None` on the
   result and are documented. Settled under the root CLAUDE.md WP-1076 invariant: `None` is
   the honest empty state and cannot read as an answer. The alternative was to write them on
   the result or retire them from it.
4. *`magnetic.supercell.CHILD_SITE_TOL`* takes `SITE_TOL`'s tier. Settled under
   `generality.md` § The rule: a threshold derived with no free factor inherits its source's
   tier. The alternative was to route it to Mike as a magnetic row.
5. *`bruker_raw.py:346`'s `np.isclose`* passes `rtol=0` when its closing test is written.
   Settled under a measurement: on the one real v4 file every tolerance from 0 to under 5°
   picks the same drive, so the change moves nothing. The alternative was to keep numpy's
   default `rtol`.
6. *The inherited pdCIF weight-column note* is stale, as PR #1636 found. Yue ruled the
   whole-column fallback on 2026-10-26 (`PATTERN_WEIGHT_UNUSABLE`, issue #1181).

**The consent lines, answered 2026-11-22.** Each was "I will X, unless you object". A rule sent
it to him: a tier-3 keep needs his dated approval, and a reader-output change or a deletion is
his.

Answered 2026-11-22 under the maintainer's routing rules of that day (WP-2238): each item was
settled by Claude and checked by a fresh agent that did not see the pick, or brought to the
maintainer, who answered "All as recommended".

7. `fullprof._OCCUPANCY_RTOL`: tighten its nuclear use to the file's printed rounding, so a
   site at Occ × 0.996 is refused rather than built full with no record. The magnetic
   Scale × f² use goes to Mike. **Settled by Claude 2026-11-22, checked blind:** proposal as written. Grounds: the constant's own
   docstring rule, "a real partial occupancy is refused rather than rounded off".
8. `FULLPROF_OCCUPANCY_UNCHECKED`: fire only for a one-atom phase whose symbol has a second
   origin setting (clause 1 of *Attention is a cost*). **Settled by Claude 2026-11-22, checked blind:** proposal as written. Grounds: *Attention is a cost*, clause 1.
9. The three writer notices that fire on every write (`GSAS2_CIF_FIELD_NOT_WRITTEN`,
   `GSAS2_INSTPRM_FIELD_NOT_WRITTEN`, `GSAS_PRM_FIELD_NOT_WRITTEN`): the fixed part moves to
   each writer's docstring and help entry, and a code stays only for a dropped item that
   varies with the model (clause 1). **Settled by Claude 2026-11-22, checked blind:** proposal as written. Grounds: *Attention is a cost*, clause 1.
10. `RECIPE_FIELD_DROPPED`: split into one code per level (clause 2). **Settled by Claude 2026-11-22, checked blind:** proposal as written. Grounds: *Attention is a cost*, clause 2.
11. The recipe hump's `0.0 if pos is None`: refuse a background peak with no position, under
    the 2026-11-02 ruling that made `HumpComponent.position` required. **Settled by Claude 2026-11-22, checked blind:** proposal as written. Grounds: that ruling.
12. A symmetry-fixed angle within 1e-3° of its value (`cif.py:98`): snap it and record
    `CIF_CELL_ANGLE_CORRECTED`, as the reader already does from 1e-3° to 0.1°. **Settled by Claude 2026-11-22, checked blind:** NOT the proposal: leave a symmetry-fixed angle within 1e-3° as stored, with no record; the proposal (snap it and record `CIF_CELL_ANGLE_CORRECTED`) was the alternative. Grounds: nothing changes, so there is no repair to report, and a record would fire on rounding noise (*Attention is a cost*, clause 1).
13. `gui.imports.WAVELENGTH_RTOL`: match a header to the rounding of its own printed digits,
    so 0.71 Å reads as Mo and 0.56 Å as Ag. **Settled by Claude 2026-11-22, checked blind:** proposal as written. Grounds: the printed-digit convention (`CIF_PRINTED_ROUNDING`).
14. `ProjectFormat.refuses`: retire it. No member has set it since WP-2013 (Rule 5). It is a
    deletion, staged in the release notes. **Ruled by Yue 2026-11-22:** retire it, as proposed. `capabilities()` also exposes it as `ProjectFormatCapability.refuses` (`capabilities.py:248`), so the release note names that output change too.
15. `CIF_STATED_MULTIPLICITY_SNAP_TOL`, `DUPLICATE_U_TOLERANCE`, `OCCUPANCY_TOLERANCE`: take
    `CIF_PRINTED_ROUNDING`'s per-file printed-digit rule and become tier 1 (Rule 5,
    convention). **Settled by Claude 2026-11-22, checked blind:** proposal as written. Grounds: the printed-digit convention (`CIF_PRINTED_ROUNDING`).
16. Keep at tier 3 as written: `TWIN_DISTANCE`, `CIF_ANGLE_CORRECT_MAX_DEG` (the WP-1028 band
    in the root CLAUDE.md), `SYMMETRY_ANGLE_TOL_DEG`, `MAX_HKL_GRID_POINTS` (the shape of the
    approved memory caps), `LINE_DISPERSION_TOL`, `NEAR_EDGE_EV` (an XAFS citation would move
    it to tier 2), `GSAS_EXP_REFINE_FLAG_MERGED` and `PATTERN_ROWS_DROPPED` sites 2 and 3. **Settled by Claude 2026-11-22, checked blind:** the six constants (`TWIN_DISTANCE`, `CIF_ANGLE_CORRECT_MAX_DEG`, `SYMMETRY_ANGLE_TOL_DEG`, `MAX_HKL_GRID_POINTS`, `LINE_DISPERSION_TOL`, `NEAR_EDGE_EV`) stay at tier 3. Each takes `approved_by="checked"` when its row is written and the
generality judge calls it `holds`; any other verdict sends it to the maintainer. **Ruled by Yue 2026-11-22:** `GSAS_EXP_REFINE_FLAG_MERGED` and `PATTERN_ROWS_DROPPED` sites 2 and 3: tier 3 approved, dated 2026-11-22 ("All as recommended").
17. Keep at tier 3 under the rare-feature clause, each naming its one family:
    `GSAS_BANK_COMMENTED`, `RECIPE_BACKGROUND_PEAK_DEGENERATE`,
    `RECIPE_ENGINE_DEFAULT_DECLINED`, `RECIPE_PLAN_STAGED`, `TOPAS_PHASE_TERM_READ`. **Ruled by Yue 2026-11-22:** tier 3 approved for the five, dated 2026-11-22 ("All as recommended").
18. `SITE_TOL`: widen to GSAS-II's reach (2e-4 per coordinate) at tier 2 if the 564-setting
    orbit sweep and the rigid-body tilt case pass at it, else keep it at tier 3 with the
    four-decimal case named. **Settled by Claude 2026-11-22, checked blind:** proposal as written: the measurement decides. Run the orbit sweep and the tilt case; widen to 2e-4 at tier 2 if they pass, else tier 3 naming the case.
19. `HEAD_BYTES` and `gsas._GSAS_TIME_MAP_SCAN_BYTES`: one 64 kB sniff window, dropping the
    two escalations it makes redundant. The 2026-11-17 probe found no change in which reader
    claims any of the 210 files in `tests/data`. **Settled by Claude 2026-11-22, checked blind:** proposal as written. Grounds: the 2026-11-17 probe.
20. The phase-scale start of 1e-3 (`GSAS2_GPX_SCALE_NOT_COMPARABLE`,
    `GSAS_EXP_SCALE_NOT_COMPARABLE`): a start-invariance test from 1e-3 and from a
    data-seeded scale. If both answers agree, the start is answer-invariant. If not, it
    stays at tier 3 with the case named. **Settled by Claude 2026-11-22, checked blind:** proposal as written: the measurement decides.
21. `RECIPE_BACKGROUND_RESEEDED`: compare GSAS-II 5.8.4's Chebyshev basis with rietx's. If
    they are equal, carry the coefficients (tier 1). If not, refuse a held background
    rather than zero it. **Settled by Claude 2026-11-22, checked blind:** proposal as written, with one addition: compare the bases first. If equal, carry (tier 1). If not, the refuse-or-reseed choice comes back to the maintainer before it is built, since a reader's refuse-versus-repair form is his (reversal of 2026-11-21).
22. `GSAS_PRM_GEOMETRY_ASSUMED`: adopt GSAS-II's rule (one wavelength is Debye-Scherrer, a
    doublet is Bragg-Brentano) at tier 2, keeping the warning. **Settled by Claude 2026-11-22, checked blind:** proposal as written. Grounds: GSAS-II's own rule (tier 2).

**Ruled by Yue, 2026-11-21.** 23. The two reader picks where careful refiners differ (the
brief is in the 2026-11-21 handover entry).

- `PATTERN_MULTISCAN_DEFAULTED`: "we do need a scan picker for the gui". The import wizard
  gains a scan picker, so a person chooses the scan rather than receiving scan 0. Owed as a
  task. And "scan: refuse" (Yue, 2026-11-21, correcting Claude's first reading that python
  kept scan 0 with a warning): `read_pattern` with no `scan=` on a file of more than one
  scan refuses, listing each scan's range and step. A one-scan file reads as before. This
  changes reader output, so it lands with a release note.
- `SPACE_GROUP_SETTING_ASSUMED`: "this shouldn't be statistical—if unknown, warn the user".
  No count of which origin the files in the corpora mean decides the pick. Where a bare
  symbol leaves the origin unknown, the reader keeps today's pick, origin choice 1, and
  warns, quoting the cell contents each setting implies. The row is approved as it stands.

**Mike's** (#1075): the nine other magnetic tier-3 candidates in `tiers.md`,
`_OCCUPANCY_RTOL`'s Scale × f² use, `_MAGNETIC_MATCH_ATOL`, the two-level
`CIF_MAGNETIC_SYMMFORM` and `GSAS2_GPX_PHASE_MAGNETIC`, and the judge's three magnetic
reading defaults.

## Handover log

- **2026-11-24** — part 2 brought to merge, by a ghostshift runner. PR #1636.
  The branch now merges cleanly with main, and Mike's ruling on its ten magnetic rows is in
  the table as he gave it, after one pass of the generality judge. Six of those rows are now
  tier 3 with a dated approval. Three are back with Mike, because the judge found each weak.
  Three stay unaudited by his own ruling. The review also found a real defect on the magCIF
  reader's path. A site 5e-4 to 1e-3 off a parent 4-fold axis is read under the parent and
  built with twice the atoms the file states, with only an info note. It is recorded for
  WP-1918 and is Mike's to rule. Mike's question about which ground wins for a read-time
  default is a brief for Yue below. The PR does not wait on it.

  *Done*: merged `origin/main` twice. The first merge had 19 conflicting hunks in
  `_audit.py`. Each row was taken from the side that tiered it, and every hunk had one such
  side. The two shrink-only baselines were merged as sets against the merge-base (a name stays
  only if neither side dropped it). The five `SEQUENTIAL_WIDTH_GROWTH` rows main deleted
  stayed deleted. The WP file's two handover entries were both kept, and the index
  regenerated. Triage's "lint is red" was stale: the PR's last run (11-17, `5afc3cc3d`) was
  green throughout. Mike's rows (comment of 2026-11-23 09:04Z, corrected 11:47Z):
  `CIF_MAGNETIC_NUCLEAR_GROUP` is tier 3 and kind 2 with his approval, recorded as a
  departure, and has its info response. The 1e-3 merge in `magcif._orbit_size` is now
  `_ORBIT_MERGE_TOL` with a tier-3 row on his ruling that it "stays" and an injected mirror
  case (`tests/test_magcif.py`, 1 test added). `MOMENT_DIRECTION_SUPPORT` is tier 3 on his
  ruling. `SEED_TILT` (with his supercell clause) and `K_MAX_DENOMINATOR` (with his corrected
  stakes) are tier 3, judge-checked. Back to Mike at `unaudited`, each with its reason in
  the evidence: `CROSS_IRREP_DRAWS`, `INVARIANCE_MOMENT_TOL`, `INVARIANCE_POS_TOL`. Left
  unaudited as he ruled: `MOMENT_FORM_AGREEMENT_MU_B` (retired, WP-1918 builds the box),
  `WITHIN_IRREP_DRAWS` (its case is owed first), `CHILD_SITE_TOL` (takes `SITE_TOL`'s tier).
  WP-1918's Inherited gained the 4-fold finding and the three returned rows.
  `/code-review high --fix` found 9 items and fixed 5 nits. It declined 4: the 4-fold band
  (Mike's), stale `magcif.py:` line citations in about 15 rows (a class-wide rewrite, left),
  fullprof's own 1e-4 orbit count (another reader), and whether a refusal threshold such as
  `K_MAX_DENOMINATOR` needs Mike rather than the judge (in the reply to Mike).
  *Measured* (Darwin arm64, `[dev]`, merged with `origin/main` at `00f9c6bc3`): fast
  selection 15 218 passed, 450 skipped, 32 xfailed in 565 s, 0 failed (one test added). Added-test cost: the one added test, 0.11 s locally. A first run on a tree I was still
  editing failed `test_audit_delta.py::test_the_reader_agrees_with_the_import` once. It passed
  alone and on the final tree. `tests.reader_output` exits 0. CI's lint steps run
  locally against the merge-base: ruff, tutorial format, skill caps, skill surface, audit
  delta (1 added, 228 changed, 0 new at `unaudited`), code references and rulebook limits
  pass, and Vale reports 0 errors (282 warnings) over the manual and the tutorials. Probe of the 4-fold case: `P m m m` (BNS 47.249) under
  `P 4/m m m`, a = b = 4 Å, O at d along x. At d = 3e-4 it is merged onto the axis. At d =
  7e-4 it is read under the parent with O unmoved, 4 images where the file's group gives 2.
  At d = 1.2e-3 it is read under the file's own group, `P m m m`.
  *Generality* (judge, 2026-11-24, on this session's eleven rows), verdicts:
  `CIF_MAGNETIC_NUCLEAR_GROUP` **weak** ("the keep rests on an unwritten class"; it holds once
  a sentence admits a recorded read-time keep, which is Mike's question to Yue). Author:
  Mike's approval stands, and the grounds now say it is a second-kind pick outside Rule 1's
  two cases. `_ORBIT_MERGE_TOL` **weak** (the 4-fold band; "unexercised", not "measured").
  Author: agreed. The evidence names the band and the grounds say "never exercises", and the
  finding went to Mike. `CROSS_IRREP_DRAWS` **weak** ("`draws=` is the caller's" is false on
  `solve_magnetic`, so it is an action's threshold). Author: agreed, back to Mike.
  `MOMENT_DIRECTION_SUPPORT` **holds**. `SEED_TILT` **holds**. `INVARIANCE_MOMENT_TOL`
  **weak** (Mike's 2-decimal FYI is a dissent). Author: agreed, back to Mike.
  `INVARIANCE_POS_TOL` **weak** (a 3-decimal hexagonal pair can be 1.5e-3 apart). Author:
  agreed, back to Mike. `K_MAX_DENOMINATOR` **holds**. The three left unaudited **hold**
  (`WITHIN_IRREP_DRAWS` reworded: pairs at 3 draws do run, and what is missing is a case
  where 3 and 12 differ). These are the verdicts and reasons only: the judge's full tables (about 10 kB) stay in the shift's scratch, a deliberate departure from pasting them whole.
  *Settled by Claude* (most important first; checked blind by a fresh agent, which agreed on
  all seven):
  (1) `MOMENT_DIRECTION_SUPPORT` and `_ORBIT_MERGE_TOL` carry Mike's dated ruling, not the
  judge's check. Grounds: each sets an automatic action's threshold, and WP-2238 keeps such
  a constant off the judge (`CONTRIBUTING.md`, `/wp-handover` step 7). Alternative: the
  judge's check, as his review routed rows 3-8.
  (2) The merge was named and tiered in this PR. Grounds: Mike asked for its row, and a new
  name may not enter at `unaudited`. Alternative: leave the literal and owe the row to
  WP-1918.
  (3) The three weak rows went back to Mike. Grounds: § The rule, "a disagreement goes to
  the maintainer", and his "if the judge disagrees on one, send it back to me". Alternative:
  keep them checked.
  (4) `WITHIN_IRREP_DRAWS` stays unaudited until its case lands. Grounds: § The rule, a guard
  no ordinary fit reaches is "recorded kept" only on its injected case. Alternative: tier 3
  now.
  (5) `MOMENT_FORM_AGREEMENT_MU_B` stays unaudited. Grounds: Mike retires it. Alternative:
  tier it until WP-1918 lands.
  (6) Kind 2 for the nuclear-group row. Grounds: Rule 1, two nested models the data could
  score. Alternative: kind 3.
  (7) The 4-fold defect was reported, not fixed. Grounds: it changes magnetic-path reader
  output, which is Mike's (#1075). Alternative: fix it in this PR.
  *For Mike* (draft reply in the shift's batch): the three returned rows; the 4-fold band;
  whether a refusal threshold (`INVARIANCE_*`, `K_MAX_DENOMINATOR`) is an "action" for
  WP-2238's exception; his FYI that the nuclear-group code fires at index 1 with nothing
  chosen (777 of 883 MAGNDATA files on his count).

  #### Brief for the maintainer: which ground wins for a read-time default

  **The decision.** When a file reader fills an open choice by default, and some established
  program makes the same choice while another program or a named competent refiner would
  not, is the audit row tier 2 or tier 3? Mike asked for one sentence in `generality.md`
  § The rule to settle it. It comes to you because it reads into your rule a meaning the
  text does not state.

  **Why it matters.** Tier 2 means the field already does this: a citation, or the same
  default in one of the seven programs. Tier 3 means rietx chose it, and a tier-3 code row
  needs a dated approval. The rule says two things that pull apart here. A program default
  stays tier 2 even if another program does otherwise. And a default that switches on an
  action still faces the judgement ground, where a named dissenter outweighs it. A reader's
  pick is both a default and an act on the model. `SPACE_GROUP_SETTING_ASSUMED` is the live
  case. A bare `F d -3 m` reads as origin 1, as TOPAS and gemmi do. GSAS-II 5.8.4 takes
  origin 2, and the wrong origin swaps a spinel's A and B sites. You approved that row
  "as it stands" on 2026-11-21, but its tier is unwritten and depends on this answer. Mike's
  `CIF_MAGNETIC_NUCLEAR_GROUP` is the other: he ruled it tier 3 on the judgement ground. No
  reader output or warning text changes either way. What changes is which rows need a dated
  approval. Without a sentence, each such row comes back as a question, as these two did.
  Importance: minor.

  **Aim.** I read it as keeping the table honest about who decided: a pick a competent
  refiner would make differently should not be filed as settled by the field. Correct me
  if you see tier as provenance alone, kept apart from the approval gate.

  **Options.** (1) The judgement ground wins at read time. A read-time default that changes
  what is refined, with a named dissenter, is tier 3 with a dated approval, and the program's
  default is cited as evidence. `SPACE_GROUP_SETTING_ASSUMED` becomes tier 3 under your
  2026-11-21 approval. (2) Tier 2 wins at read time. The dissent goes in the row's
  `ambiguity`, and the reader still surfaces the choice, as Rule 1's last paragraph requires.
  `SPACE_GROUP_SETTING_ASSUMED` becomes tier 2 on TOPAS and gemmi, with GSAS-II named. (3) Do
  nothing, and argue each row. Each option costs one sentence or none, and each can be undone.

  **Practice.** This is a rule about rietx's own record, so no diffraction program has a
  practice to follow. `generality.md` already says "an action here still faces the judgement
  ground under tier 3 ... a named dissenter outweighs it" (ruled 2026-10-19). Rule 1's last
  paragraph (ruled 2026-11-21) says a reader surfaces an open choice. Neither says whether
  reading is acting.

  **Recommendation.** Option 1, a lean. The crux is whether a read-time pick is an action. It
  decides which parameters refine, or which atoms sit where, so it acts on the model in the
  2026-10-19 ruling's sense. Option 2 lets one program's default stand for a choice Rule 1's
  unanimity test fails. If you see tier as provenance alone, with the dissent recorded in
  `ambiguity`, option 2 is the cleaner split. That part of the crux is a value judgement.

  **Can PR #1636 merge without the answer?** Yes. No row the PR writes depends on it.
  `CIF_MAGNETIC_NUCLEAR_GROUP` is tier 3 either way, since GSAS-II does not share rietx's
  default. The PR's tier-2 reader rows name no dissenting program. The answer sets
  `SPACE_GROUP_SETTING_ASSUMED`'s tier, which the PR leaves unaudited, and rows written later.

  *Next*: Yue answers the brief, and Mike answers the reply (three rows, the 4-fold band,
  the refusal-threshold reading). Then the successor PR writes those answers and the 2026-11-21
  and 2026-11-22 rulings into `_audit.py` (§ Rulings 7-23), builds the consent lines' changes
  with their tests, and closes the 36 rows left at `unaudited`. WP-1918 builds the print box
  and settles the 4-fold band.

- **2026-11-21** — A rulings triage, docs only (PR #1759), over this file and PR #1636's
  batch. The gate ruling this WP waited on was made on 2026-11-16, and PR #1636 has since
  tiered 218 rows under it. So what waits now is that PR's batch. Of its items, six are
  settled by a written rule or a measurement, 16 were consent lines (answered 2026-11-22, § Rulings above),
  one was a brief (answered 2026-11-21), and the magnetic ones are Mike's. § Rulings above lists each. Nothing was
  built, and PR #1636 needs no change for these rulings to stand.

  #### Brief for the maintainer: two reader picks where careful refiners differ

  **The decision.** For two readers that must choose for the caller, whether each keeps
  choosing and warning (you approve the tier-3 row), or refuses and lists the alternatives
  (Rule 1's third kind). It comes to you for three reasons. Both sit on the main reading
  surface. Two written rules point different ways on the second. And the cost of refusing
  depends on what scientists' files look like, which I have not measured.

  **Why it matters.**

  1. *A file with several scans* (`PATTERN_MULTISCAN_DEFAULTED`). Bruker, PANalytical and
     Rigaku files can hold more than one scan. With no `scan=`, `read_pattern` reads scan 0
     and warns "scan 0 of N". The scans may be repeats, and then scan 0 is fine. They may
     be adjacent ranges, and then scan 0 is part of the measurement. Or the file is a map:
     `panalytical_mesh.xrdml` holds 101 scans, and slice 0 refines as if it were the
     sample. The GUI's import wizard has no scan picker, so it always takes scan 0. If the
     default is wrong, every refined number is a fit to the wrong data, and the warning is
     the only signal. Importance: moderate.
  2. *A bare space-group symbol with two settings* (`SPACE_GROUP_SETTING_ASSUMED`). A
     symbol such as `F d -3 m` with no origin choice and no operator list names two
     settings. The reader takes gemmi's first (origin choice 1) and warns, quoting the cell
     contents each setting implies. A file that lists its operators never reaches this
     code. The wrong origin swaps a spinel's A and B sites: A2BO4 in place of AB2O4, and
     wrong weight fractions. Importance: moderate.

  **Aim.** I read the aim as Rule 1: a default acts only where every competent refiner
  would act the same way, and nobody fits the wrong pattern or structure without being
  told. Correct me if convenience on the common file should weigh more.

  **Options.**

  - Multi-scan file. (keep) Read scan 0 and warn, with the tier-3 row approved. Nothing
    changes, and a mesh can still be fitted as one slice under the warning. (refuse)
    Refuse when there is more than one scan and no `scan=`, listing each scan's range and
    step. A python caller pays one rerun with the list in hand. The GUI needs a scan
    picker, about a day. It changes reader output and is undoable. Dropped: returning
    every scan, as GSAS-II imports each as its own pattern, because `read_pattern` returns
    one pattern and the series reader serves many.
  - Bare symbol. (keep) Origin choice 1 with both settings quoted: tier 3 approved, or
    tier 2 on TOPAS's and gemmi's default with GSAS-II named as the dissenter. (origin 2)
    Origin choice 2 for a centrosymmetric group, as GSAS-II does. Published structures
    mostly state origin 2 (issue #217). A TOPAS `.inp` keeps origin 1, which is that
    format's own rule. It changes reader output. (refuse) Refuse a bare two-setting symbol
    and list both settings with their contents, so the caller adds `:1` or `:2`.

  **Practice.** For multi-scan files, GSAS-II 5.8.4 imports every scan as its own pattern
  (`G2pwd_Panalytical.py:50-76`, `G2pwd_rigaku.py:222-250`, read on 2026-11-17). The other
  six programs were not checked, and `docs/practice.md` has no section on this. For bare
  symbols, GSAS-II 5.8.4 takes origin choice 2 (`G2phase_CIF.py:729-783`), and TOPAS and
  gemmi take origin choice 1. FullProf was not checked. The rule conflict is in
  `generality.md` § The rule's tier 2: a program's default stays at tier 2 despite a
  dissenter, while for an action a named dissenter outweighs the default. Reading a symbol
  is both a default and an action.

  **Recommendation.**

  - Multi-scan: refuse, as a lean, and a close call. The pick is right only when the scans
    are repeats. For ranges and maps the warning forces the same rerun a refusal would, but
    only after a fit to the wrong data. A mesh user and GSAS-II would both choose
    otherwise, so Rule 1's unanimity test fails. Keep loses on that. Its one advantage is
    the GUI, which needs a picker anyway before it can read anything but scan 0. Finding
    that most multi-scan files on users' disks are repeats would flip me.
  - Bare symbol: keep origin choice 1, as a lean with low confidence. Nobody has counted
    which files reach this code. Formats that state their operators never do, and TOPAS
    files mean origin 1. The crux is whether the files that do reach it are mostly typed
    from papers (origin 2) or written by programs that mean origin 1. A count of bare
    two-setting symbols in the corpora by source would settle it. A majority typed from
    papers would flip me to origin 2. Refuse loses to both, because the warning already
    quotes both settings' contents, which is the ranking Rule 1's second kind asks for.

  *Next.* Yue answers the consent lines and the brief, and Mike answers the magnetic rows.
  Then PR #1636's successor dates the approved rows into `_audit.py`, builds the consent
  lines' changes with their tests, and writes the closing tests for the 36 rows left at
  `unaudited`.

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
