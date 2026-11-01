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

- **2026-10-23, from [1510](1510-what-the-chemist-knows-reaches-the-search.md) (closed):
  `VOLUME_RATIO_BOUNDS` (`_audit.py:1038`) fails on inorganic cells.** The formula window
  misses the true cell for 7 of 9 known cells measured (WP-2030's table). Hofmann's (2002)
  citation covers organic and metal-organic crystals only, so a tier-2 reading would cover a
  population the source excludes. [2030](2030-a-formulas-volume-window-fits-inorganic-cells.md)
  owns the rule. Tier the row with that evidence, or leave it to 2030.
- **From WP-2002 (2026-10-21, 4th session): tier 2 names seven programs.** `docs/milestones/generality.md` § The rule's tier 2 now reads "by default in an established Rietveld program": GSAS-II, FullProf, TOPAS, RIETAN-FP, BGMN, MAUD and EasyDiffraction, the list rietx-bench runs (the maintainer's instruction). A row resting on a program default names the programs it checked and what each does; a program doing otherwise by default is a dissenter, one without the feature is neither. What each does on peak windows, staging, roughness starts, width limits, dispersion, solver, mode and background seed is in `docs/wp/2002-batch/practice.md`; where each program's manual or source sits is in the maintainer's memory (`foreign-code-sources-on-disk`), and rietx-bench's `tools/` holds BGMN, MAUD, RIETAN-FP and EasyDiffraction's environment beside GSAS-II and FullProf.
- **2026-10-20, from [1986](1986-guides-and-theory-move-over-and-the-old-tree-retires.md), found while moving the manual's reference pages: declared names with no writer.** `PhaseMicrostructure.separable` and `.size_strain_collinearity` are `None` on every `RefinementResult.microstructure`; only the report's deep copy writes them (`report/__init__.py:190-212,273-274`). `ProjectFormat.refuses` is set by no registry member, and no member produces `reports_at="read"` (`io/projects/registry.py:107,128-132`). `SuggestedAction.vetoed_by`'s docstring adds "or a guard forbids it", which no code writes (`report/schemas.py:1150`; `layer2.py:1059-1062` sets it from the plan and already-free paths only). Each Reference page states what the code does today (`derived.md`, `foreign-files.md`, `report.md`); the surface walk is where write, retire or document gets decided.

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
