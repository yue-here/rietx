# WP-2006 — Readers, crystallography and GUI codes, and the dead surface

Milestone: generality · Status: 🔄 2026-10-24 — part 1 merged from outside (PR #1101, `50bc4555`): the inventory and the reachability walk; the tiers wait on the gate ruling
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

- **From WP-2013 (2026-11-03, PR #1369): a reader default the hump ruling left standing.** `HumpComponent.position` is now required of a caller (maintainer, 2026-11-02), because the old 0.0 placed a hump below any measured range. `io/recipe.py`'s background-peak builder still writes `0.0 if pos is None`, silently, so a PowderLine recipe whose `single_peaks` entry has no position gets the placeholder the ruling removed, and a flagged position starts its refinement there. Refusing it or reporting it changes what `read_recipe` returns, so it goes to the maintainer before merge (memory rule on reader output). No recipe with a null position has been seen; whether PowderLine writes one is unchecked.

- **2026-10-23, from [1510](1510-what-the-chemist-knows-reaches-the-search.md) (closed):
  `VOLUME_RATIO_BOUNDS` (`_audit.py:1038`) fails on inorganic cells.** The formula window
  misses the true cell for 7 of 9 known cells measured (WP-2030's table). Hofmann's (2002)
  citation covers organic and metal-organic crystals only, so a tier-2 reading would cover a
  population the source excludes. [2030](2030-a-formulas-volume-window-fits-inorganic-cells.md)
  owns the rule. Tier the row with that evidence, or leave it to 2030.
- **From WP-2002 (2026-10-21, 4th session): tier 2 names seven programs.** `docs/milestones/generality.md` § The rule's tier 2 now reads "by default in an established Rietveld program": GSAS-II, FullProf, TOPAS, RIETAN-FP, BGMN, MAUD and EasyDiffraction, the list rietx-bench runs (the maintainer's instruction). A row resting on a program default names the programs it checked and what each does; a program doing otherwise by default is a dissenter, one without the feature is neither. What each does on peak windows, staging, roughness starts, width limits, dispersion, solver, mode and background seed is in `docs/wp/2002-batch/practice.md`; where each program's manual or source sits is in the maintainer's memory (`foreign-code-sources-on-disk`), and rietx-bench's `tools/` holds BGMN, MAUD, RIETAN-FP and EasyDiffraction's environment beside GSAS-II and FullProf.
- **2026-10-20, from [1986](1986-guides-and-theory-move-over-and-the-old-tree-retires.md), found while moving the manual's reference pages: declared names with no writer.** `PhaseMicrostructure.separable` and `.size_strain_collinearity` are `None` on every `RefinementResult.microstructure`; only the report's deep copy writes them (`report/__init__.py:190-212,273-274`). `ProjectFormat.refuses` is set by no registry member, and no member produces `reports_at="read"` (`io/projects/registry.py:107,128-132`; that member was dropped by WP-2013 in PR #1369, 2026-11-03, so only `refuses` is left here). `SuggestedAction.vetoed_by`'s docstring adds "or a guard forbids it", which no code writes (`report/schemas.py:1150`; `layer2.py:1059-1062` sets it from the plan and already-free paths only). Each Reference page states what the code does today (`derived.md`, `foreign-files.md`, `report.md`); the surface walk is where write, retire or document gets decided.

- **From WP-2001 (2026-10-19, PR #1047).** The table is `src/rietx/_audit.py`; this WP's rows are the ones `_audit.WALKED` and `_audit.DEFAULT_SEATS` map to 2006, plus the codes and suggestion rows of its subsystem. Auditing a row means giving it a tier and evidence in place and deleting its line from `UNAUDITED_BASELINE`; `tests/test_audit_table.py` fails until both are done. The walk sees module-level numbers and tuples of numbers only, so a number held in a dict, list or array is audited here by hand, in `crystallography/` and the two `io/` files alike; nobody has looked yet. The GUI keeps its own copy of the correlation guard, `let guard = $state(0.98)` in `gui/src/panels/Plan.svelte` (about line 93), pinned again in `App.test.ts` and `rxt.test.ts`; the python side is now one constant, `rietx.schemas.plan.CORRELATION_GUARD`, and the GUI copy needs the dist rebuilt (`gui/CLAUDE.md`).
- **From WP-2001's generality judge (2026-10-19).** Five reader decisions sit outside the walk, which keeps the third review's exclusion of reader byte offsets: `io/formats/dif.py` `_MIN_ROWS = 3` (three hkl rows make a peak list, refused); `io/formats/peaklist.py` `_MIN_ROWS = 8`; `io/formats/gsas.py`'s 64 kB sniff bound (a larger `TIME_MAP` table falls to the `xy` reader, refused for the wrong cause); `io/formats/bruker_raw.py`'s `atol=1e-6` drive pick and its counting-time windows, which decide whether σ can be derived; and `io/formats/pdcif.py`, which drops a whole weight column on one zero weight and falls back to Poisson with no diagnostic, while `xy.py` and `chi.py` adopt any positive third column as σ. Audit them by hand, or widen `WALKED` with a reason.
- **From [2014](2014-a-heuristic-meets-the-judge-on-every-path.md)'s close (2026-10-20, PR #1070).** `_audit.NOT_WALKED` now declares, with a reason, every top-level entry the walk leaves out, and a test holds it and `WALKED` equal to the package. On the judge's reading, nine more files joined the walk under this WP, their 36 constants at `unaudited` on the baseline: `io/formats/dif.py`, `gsas.py` and `peaklist.py` (the sniff floors and the 64 kB `TIME_MAP` bound in this mailbox's previous bullet), `io/instrument_profile.py` (`_PRM_CUTOFF`, a tail cutoff GSAS-I computes with), `io/projects/fullprof.py`, `registry.py` and `topas_input.py` (`CALC_POINTS_PER_FWHM` sets TOPAS's `convolution_step`; `DEFAULT_RADIUS_MM` claims to cancel and no test says so), `gui/imports.py` (`WAVELENGTH_RTOL` picks the pre-filled instrument: a header 0.71 Å matches no Mo line and is offered as a single-wavelength capillary) and `gui/symmetry.py` (`ORBIT_COLLISION_TOL` and `POSITION_TOL` gate a model edit). **A possible silent repair, read from the code and not run:** `fullprof._OCCUPANCY_RTOL = 5e-3` lets per-site occupancy ratios spread 0.5 % and then writes 1.0 on every site with no diagnostic (`io/projects/fullprof.py` around line 1980), so a site at 0.996 beside full ones is built full, while the constant's comment puts the file's rounding at 2e-5 and says a real partial occupancy is refused.

- **From WP-2002 (2026-10-19, PR #1050).** 2002 tiers `MAGNETIC_ION_ASSUMED` and `LANDE_G_ASSUMED` on both raise sites. Its batch class B15 proposes splitting `crystallography/magnetic/form_factor.py`'s assumed-ion table by element: Ce, Eu, Sm and Yb tier 1 (Sm in question), the other lanthanides tier 2 with a citation, and U, Np and Pu demoted. GSAS-II 5.8.4 maps bare U to U³⁺ where rietx picks U⁴⁺ (`atmdata.py:1706-1709`, checked). Read 2002's ruling before tiering that table.

- 2026-10-26 issue triage: #1058 is the outside contributor's (mustachefeeling) claim on this WP. Part 1 (the walk and the inventory) landed as PR #1101; the tiers wait on the gate ruling after WP-2004, as the status line says. Checked against the tree at c0e32ab29.

## Non-goals

- `indexing/`: 2007 (its own rulebook, 48 codes, 76 constants, the benchmark).
- Changing a reader's repair (the action) or `io/CLAUDE.md`'s dispatch rules.
- Removing any public entry: a follow-up WP per batch of removals, with the break staged.

## Tasks

- [x] Inventory the 142 codes (io 90 literals plus five by name, crystallography 20, gui
      27): raise site, `level`, condition, whether it records an act or asserts a
      judgement. `LANDE_G_ASSUMED` and `MAGNETIC_ION_ASSUMED` are raised here and in
      `strategy/magnetic.py`; 2002 tiers them on both sites and this WP reads the row.
- [ ] The constants of `io/` (~30) and `crystallography/` (66 by AST), entered by 2001's
      walk: tier each, expected mostly tier 1 (byte offsets, physical limits) with the
      few thresholds named above.
- [ ] Tier each; for the few thresholds (`CIF_ANGLE_CORRECT_MAX_DEG`, the attenuator
      conventions measured per format, the axis refusal), evidence and families.
- [x] The reachability walk over `derive_surface()`'s 2 238 entries, as a script in
      `tests/` run by hand (a Haiku-grade task: collate, do not judge), its output a table
      with one row per unreached entry and where it *is* referenced.
- [ ] The batch to the maintainer: tier-3 rows with grounds, plus the unreached-entry
      table with a recommendation per row.
- [ ] Approved demotions (expected few); rulings dated into the table.
- [ ] Tests; the fast count moved by exactly the tests added.
- [ ] Skill: `references/diagnostics-projects.md` and the io rows of `diagnostics.md`
      checked against the table; none expected to move.

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

**Consent lines, awaiting Yue.** Each is "I will X, unless you object". A rule sends it to
him: a tier-3 keep needs his dated approval, and a reader-output change or a deletion is his.

7. `fullprof._OCCUPANCY_RTOL`: tighten its nuclear use to the file's printed rounding, so a
   site at Occ × 0.996 is refused rather than built full with no record. The magnetic
   Scale × f² use goes to Mike.
8. `FULLPROF_OCCUPANCY_UNCHECKED`: fire only for a one-atom phase whose symbol has a second
   origin setting (clause 1 of *Attention is a cost*).
9. The three writer notices that fire on every write (`GSAS2_CIF_FIELD_NOT_WRITTEN`,
   `GSAS2_INSTPRM_FIELD_NOT_WRITTEN`, `GSAS_PRM_FIELD_NOT_WRITTEN`): the fixed part moves to
   each writer's docstring and help entry, and a code stays only for a dropped item that
   varies with the model (clause 1).
10. `RECIPE_FIELD_DROPPED`: split into one code per level (clause 2).
11. The recipe hump's `0.0 if pos is None`: refuse a background peak with no position, under
    the 2026-11-02 ruling that made `HumpComponent.position` required.
12. A symmetry-fixed angle within 1e-3° of its value (`cif.py:98`): snap it and record
    `CIF_CELL_ANGLE_CORRECTED`, as the reader already does from 1e-3° to 0.1°.
13. `gui.imports.WAVELENGTH_RTOL`: match a header to the rounding of its own printed digits,
    so 0.71 Å reads as Mo and 0.56 Å as Ag.
14. `ProjectFormat.refuses`: retire it. No member has set it since WP-2013 (Rule 5). It is a
    deletion, staged in the release notes.
15. `CIF_STATED_MULTIPLICITY_SNAP_TOL`, `DUPLICATE_U_TOLERANCE`, `OCCUPANCY_TOLERANCE`: take
    `CIF_PRINTED_ROUNDING`'s per-file printed-digit rule and become tier 1 (Rule 5,
    convention).
16. Keep at tier 3 as written: `TWIN_DISTANCE`, `CIF_ANGLE_CORRECT_MAX_DEG` (the WP-1028 band
    in the root CLAUDE.md), `SYMMETRY_ANGLE_TOL_DEG`, `MAX_HKL_GRID_POINTS` (the shape of the
    approved memory caps), `LINE_DISPERSION_TOL`, `NEAR_EDGE_EV` (an XAFS citation would move
    it to tier 2), `GSAS_EXP_REFINE_FLAG_MERGED` and `PATTERN_ROWS_DROPPED` sites 2 and 3.
17. Keep at tier 3 under the rare-feature clause, each naming its one family:
    `GSAS_BANK_COMMENTED`, `RECIPE_BACKGROUND_PEAK_DEGENERATE`,
    `RECIPE_ENGINE_DEFAULT_DECLINED`, `RECIPE_PLAN_STAGED`, `TOPAS_PHASE_TERM_READ`.
18. `SITE_TOL`: widen to GSAS-II's reach (2e-4 per coordinate) at tier 2 if the 564-setting
    orbit sweep and the rigid-body tilt case pass at it, else keep it at tier 3 with the
    four-decimal case named.
19. `HEAD_BYTES` and `gsas._GSAS_TIME_MAP_SCAN_BYTES`: one 64 kB sniff window, dropping the
    two escalations it makes redundant. The 2026-11-17 probe found no change in which reader
    claims any of the 210 files in `tests/data`.
20. The phase-scale start of 1e-3 (`GSAS2_GPX_SCALE_NOT_COMPARABLE`,
    `GSAS_EXP_SCALE_NOT_COMPARABLE`): a start-invariance test from 1e-3 and from a
    data-seeded scale. If both answers agree, the start is answer-invariant. If not, it
    stays at tier 3 with the case named.
21. `RECIPE_BACKGROUND_RESEEDED`: compare GSAS-II 5.8.4's Chebyshev basis with rietx's. If
    they are equal, carry the coefficients (tier 1). If not, refuse a held background
    rather than zero it.
22. `GSAS_PRM_GEOMETRY_ASSUMED`: adopt GSAS-II's rule (one wavelength is Debye-Scherrer, a
    doublet is Bragg-Brentano) at tier 2, keeping the warning.

**Awaiting Yue, with a brief.** 23. Two reader picks where careful refiners differ:
`PATTERN_MULTISCAN_DEFAULTED` and `SPACE_GROUP_SETTING_ASSUMED`. The brief is in the
2026-11-21 handover entry.

**Mike's** (#1075): the nine other magnetic tier-3 candidates in `tiers.md`,
`_OCCUPANCY_RTOL`'s Scale × f² use, `_MAGNETIC_MATCH_ATOL`, the two-level
`CIF_MAGNETIC_SYMMFORM` and `GSAS2_GPX_PHASE_MAGNETIC`, and the judge's three magnetic
reading defaults.

## Handover log

- **2026-11-21** — A rulings triage, docs only (PR #PENDING), over this file and PR #1636's
  batch. The gate ruling this WP waited on was made on 2026-11-16, and PR #1636 has since
  tiered 218 rows under it. So what waits now is that PR's batch. Of its items, six are
  settled by a written rule or a measurement, 16 are consent lines Yue can wave through,
  one is a brief, and the magnetic ones are Mike's. § Rulings above lists each. Nothing was
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
