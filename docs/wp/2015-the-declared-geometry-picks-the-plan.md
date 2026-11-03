# WP-2015 — The declared geometry picks the plan, and a geometry can be unstated

Milestone: generality · Status: ⬜
Track: The audits
Depends on: —
Priority: P2 2026-10-19 — a generality-audit ruling (WP-2002 B7, B9) waits on it; a Bragg-Brentano pattern on the default plan leaves specimen displacement unrefined and nothing says so, and an instrument built without a geometry is read as a capillary

## Goal

The default plan follows the geometry the caller declared. A Bragg-Brentano instrument
frees specimen displacement with the zero, and an unstated geometry frees nothing
geometry-specific. `Geometry.kind` gains an unstated value, which a hand-built instrument
gets by default, and a fit on it tells the user to state the geometry.

## Context

**The rulings** (WP-2002's batch, `2002-batch/rulings.md`, 2026-10-19). B7: "If the user
knows it's BB geometry, that information should lead to the preset. If unknown, we should
not free factors which might not be appropriate for a given refinement." B9: a "geometry not
stated" state, "indicating that the user should state geometry as a warning/notification".
Both are tier 3 on that approval.

**Today.**
- `Geometry.kind` (`schemas/instrument.py`, ~line 1207) has no unstated value and
  defaults to `debye_scherrer`, so a hand-built `Instrument` is treated as a capillary.
  The presets `Instrument.bragg_brentano`, `Instrument.debye_scherrer` and the
  transmission one state their geometry already, so only hand-built instruments change.
- The default plan `mccusker_default` frees the zero but no displacement.
  `lab_bragg_brentano` frees displacement, the Kα2 weight and the axial terms
  (`strategy/staged.py`, ~lines 351-425). The B7 ruling adds a fence: the geometry-picked
  plan keeps a calibrated instrument's Kα2 ratio and axial terms fixed, so it is not
  `lab_bragg_brentano` as it stands.
- The report's position actions are keyed by geometry
  (`report/layer2._POSITION_ACTIONS_BY_GEOMETRY`, `report/layer1.POSITION_TEMPLATES`) and
  meta-tested against each other and a real `ParameterTable` (root CLAUDE.md, WP-1073).
  Today they suggest capillary corrections for a hand-built instrument. Under the unstated
  value they name the shape of a position error they see (a displacement error is
  cos θ-shaped and leaks into the cell when nothing absorbs it), suggest no
  geometry-specific parameter, and ask the user to state the geometry.

**Every reader first.** About 70 references to the geometry kind sit in 15 files:
`refine.py`, `model/forward.py`, `model/absorption.py`, `model/preferred_orientation.py`,
`report/__init__.py`, `io/instrument_profile.py`, `io/exporters.py`, `io/recipe.py`,
`io/projects/fullprof.py`, `viz/compare.py`, `gui/imports.py`, the GUI bundle,
`indexing/diagnostics.py`, `indexing/workflow.py` and the schema itself (grep
`geometry.kind`, 2026-10-19). Each needs a reading of "unstated" before the value exists.
This is the rule the extra-components union taught (root CLAUDE.md): counts and builders
that were right only while the union had one kind.

**Old files.** A stored instrument should keep its stated kind on load (inferred, not
checked). Check whether `_InheritsDeclaredDefaults` writes a default kind into
`project.json` and `history.jsonl`, and what a file without the key reads as.

**Practice** (read 2026-10-19 by WP-2002). TOPAS assumes no geometry: a correction applies
only when a macro names it (Technical Reference Version 9, § 1.3, § 22.1.7). GSAS-II 5.8.4
always picks one, Bragg-Brentano when the instrument file has a Kα1/Kα2 pair or its source
says "lab data", Debye-Scherrer otherwise (`GSASIIfiles.py:509-519`,
`GSASIIdataGUI.py:2075-2081`).

**Assumed instrument facts** (B9's fourth bullet). The result records which instrument
facts the package assumed rather than read: the geometry, the polarisation (0.99 in the
capillary preset, 0.5 with no preset) and the Kα2/Kα1 ratio of 0.5.

**Kind of ambiguity** (DESIGN.md § Rules, 1). The geometry is a fact about the caller's
instrument. Where it is unknown the package acts on nothing geometry-specific and reports
that it did not.

### Inherited

- **From WP-2002 (2026-10-21, 5th session, PR #1085).** Every preset now ends in a closing stage that frees the union of its globs at 1e-3 windows (`RefinementPlan.closing_stage`); a geometry-picked preset inherits it with nothing to add, and its stage-list tests count it (`plan.run_stages()`).
- **Renumbered 2026-10-20.** Filed on WP-2002's branch as WP-2013 while main gave 2013 to
  the stale-text WP; this file is the same WP under its new number.
- **From the second read of WP-2002's batch (Mike Gaultois, PR #1050, 2026-10-20), agreed
  by the maintainer the same day.** Four cases the geometry-led plan should answer.
  (1) A caller who arrives with a calibrated instrument profile (an instrument-parameter
  file, or `load_instrument_profile`) still gets `instrument.profile.u, v, w, x, y` freed by
  `mccusker_default` (`strategy/staged.py`, ~line 379), where practice holds the instrument
  and refines the sample broadening; the instrument/sample split is degenerate within one
  pattern, so this is caller information like the geometry (B7.1 (a)). (2) A QPA caller
  holds a minor phase's cell, coordinates and B and refines only its scale, while the
  default plans free every phase's structure; the absent-phase hold covers only a phase
  under 3σ (B7.1 (b)). (3) The `debye_scherrer` preset holds polarisation K at 0.99, which
  matches 11-BM's instrument files and not a lab capillary with a Cu tube; K trades with
  Biso (a wrong K moved Biso by 12σ in WP-2002's batch). Make it required, or default it to
  the "not stated" state this WP introduces (B9.13). (4) The preset goniometer radius of
  217.5 mm scales the reported displacement by R/217.5 on any other goniometer; the preset
  could refuse a missing radius, as `Geometry(kind="bragg_brentano")` already does (B9.15).

- 2026-10-31, from the issue triage (issue #1233): on the NIST SRM 660c
  certification pattern (`tests/data/nist_srm660c_100a.cif`, Bragg-Brentano,
  Cu Kα, R = 217.5 mm, 20.3-150.9°), `pawley_default` and `profile_only` free
  the zero and leave specimen displacement at 0, and return a = 4.157067 /
  4.157065 Å, +69 ppm from the certificate cell at the scan's temperature
  (4.156780 Å). The NIST protocol (zero held at 0, displacement and axial
  divergence freed) returns +24 ppm in both modes, so the plan accounts for
  about 45 ppm of cell bias, with the offset and axial terms not separated.
  The mechanism: below 90° the zero and the −2s·cosθ/R displacement are
  near-collinear (correlation −0.9999 with the cell, 20-90°), above 90° they
  separate, and a displacement fitted as a zero leaves a tanθ-shaped remainder
  the cell absorbs (about 80 ppm on unweighted positions at s = 0.079 mm).
  Checked against the tree at d87c8cc91: both structure-free presets free
  `instrument.zero_shift` and no displacement, and `PLAN_PRESETS` remaps
  `mccusker_default` to them for `mode="lebail"` and `mode="pawley"`, so this
  WP's geometry-picked default must cover that remap too, not only
  `mccusker_default`. The numbers were not re-run in triage. The issue's other
  two suggestions (a report finding when the free offset's angular form does
  not match the declared geometry; documentation that cell accuracy from a
  standard needs the instrument's aberration model) fit this WP's notification
  and manual tasks. SRM 660c is a candidate for the lab Bragg-Brentano family
  in the measurement task, with the certificate as the reference; issue #1259
  asks for the Le Bail/Pawley validation row on the same data.

## Non-goals

- The limits half of B9 (occupancy, March-Dollase r): WP-2002's demotions.
- A geometry inferred from the data or the file. GSAS-II's wavelength guess is the
  practice this WP declines.

## Tasks

- [ ] The reader table: every reader of the geometry kind, with its reading of "unstated",
      written into this file before any code.
- [ ] The unstated value, the default for a hand-built `Geometry`; old projects open with
      their stated kind (a test on a file written before this WP).
- [ ] The default plan picks by geometry: Bragg-Brentano frees displacement with the zero,
      and keeps a calibrated instrument's Kα2 ratio and axial terms fixed; unstated runs
      `mccusker_default`.
- [ ] The notification asking the user to state the geometry, and the report's position
      action under the unstated value.
- [ ] The assumed instrument facts recorded in the result.
- [ ] Measured on three families (a lab Bragg-Brentano pattern, a capillary and a third):
      the cell and Rwp under the old default and the new. Goldens re-pinned only if no
      further from their reference.
- [ ] Audit rows: the plan default and any new code, with tier 3 and approval 2026-10-19
      (`src/rietx/_audit.py`).
- [ ] `help.py`, the manual's plan chapter, and a `tests/test_compare_ui.py` row if a
      standard exercises the change.
- [ ] Tests + obs/calc/diff PNGs to `tests/output/`.
- [ ] Skill: the body or reference row telling an agent to state the geometry, or "none"
      and why.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_audit_table.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest -n auto --dist loadgroup                # once, on the final tree: goldens
.venv/bin/python -m ruff check src tests examples
```

## References

- McCusker, L. B. et al. (1999). J. Appl. Cryst. 32, 36-50, § 5 (position corrections by
  geometry).
- WP-2002 `2002-batch/rulings.md` § B7, § B9 and § Third round.

## Handover log

- **2026-10-19** — created by WP-2002's third session from the B7 and B9 rulings. No open
  WP owns the geometry default: the WPs that name `geometry.kind` are closed GUI work
  (1203, 1205, 1216) or texture (1960 closed, 1974 open and about the texture order).
