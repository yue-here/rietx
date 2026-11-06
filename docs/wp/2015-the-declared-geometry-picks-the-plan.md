# WP-2015 — The declared geometry picks the plan, and a geometry can be unstated

Milestone: generality · Status: 🔄 2026-11-04 — in review (PR #1405): Bragg-Brentano's default frees the displacement, a hand-built geometry is `unstated` and warns; seven provisional choices await the maintainer, leftovers in #1409
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

**The reader table** (2026-11-04, read against `ba3719f06`). What each reader of
`Geometry.kind` does with `"unstated"`. "Falls through" means its `else`
branch already does nothing geometry-specific, which is the reading B7 asks
for; every other row is a change this WP makes.

| reader | reading of `"unstated"` |
|---|---|
| `schemas/instrument.Geometry` | the new default. `mu_r`, `capillary_radius_mm`, the capillary offsets and `surface_roughness` are refused as today (they test `== debye_scherrer` / `== bragg_brentano`); `mu_t`/`thickness_mm`, refused today only under `debye_scherrer`, are refused under `unstated` too, since a flat-specimen correction needs a flat kind. A stored document without the key reads `debye_scherrer` (`STORED_DOCUMENT`) |
| `model/forward` `_position_shift_deg`, `_shift_key`, `_shift_est`, `_absorption` | falls through: no displacement, transparency or offset term, no absorption |
| `model/preferred_orientation.TEXTURE_SAMPLE_PSI_DEG` (forward compile) | **refused**: ψ is a property of the geometry and there is none to read; the compile raises naming `Geometry.kind` |
| `params/vector` displacement/transparency/offset locks | falls through: force-fixed as on every non-BB / non-DS kind |
| `refine._resolve_specimen_absorption`, `_absorption_record` | falls through (the schema refuses the inputs) |
| `refine._capillary_offset_diagnostics` | silent (DS only); `GEOMETRY_UNSTATED` speaks instead |
| `strategy/staged.resolve_plan` | runs the name as it stands (B7: free nothing geometry-specific) |
| `report/layer1.POSITION_TEMPLATES` | all five position shapes, as evidence: with no geometry every cause is possible |
| `report/layer2._POSITION_ACTIONS_BY_GEOMETRY` | zero and cell only; a `cos_theta`, `sin_2theta` or `cos_2theta` trend is reported with no action (the flat-plate-transmission precedent, WP-1003). The fallback for a key it lacks stays BB, reachable only from a caller with no instrument |
| `report/__init__` | passes the kind through to the two maps |
| `io/exporters._INSTR_GEOMETRY` (pdCIF) | `_pd_instr_geometry ?`, CIF's unknown value |
| `io/projects/fullprof` writer | falls through (no absorption under it) |
| `io/instrument_profile` `.instprm` writer | refused, as `flat_plate_transmission` is: GSAS-II has no unstated `Type` |
| `io/instrument_profile` `.instprm`/`.prm` readers, `io/recipe`, `cli index --geometry`, neutron presets, `gui/imports.suggest_instrument` | unchanged: each states a kind and already says when it assumed one (`GSAS2_INSTPRM_GEOMETRY_ASSUMED`, `GSAS_PRM_GEOMETRY_ASSUMED`). Whether they should read unstated instead is a question for the maintainer, not decided here |
| `io/instrument_tof` GSAS `.iparm` and TOF `.instprm` readers (added at review, 2026-11-04) | state `debye_scherrer`, as `Instrument.tof_neutron_bank` does; they built a bare `Instrument` and would otherwise have fallen to `unstated` |
| plan-name readers outside `fit` (added 2026-11-04): `Refinement.report(plan=name)`, `Project.create(plan=name)`, the text document's `plan` line, `PlanSpec.preset_name` | resolve the name through `resolve_plan` with the mode and geometry, as `fit` and the GUI preset route do |
| `indexing/diagnostics` `INDEX_CELL_SYSTEMATIC_UNQUANTIFIED` | the "geometry unknown" variant, as for no instrument |
| `indexing/workflow`, `viz/compare` | fall through |
| `gui/src/lib/model.ts` (geometry select) | lists `unstated` and shows no geometry-specific field under it; dist rebuilt |
| `multi.py` | **not changed**: it runs `PLAN_PRESETS` directly, with no mode substitution either, so it bypasses this WP's geometry addition; left to an issue |

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

- **2026-11-05, from the issue triage (issue #1409): ten leftovers from PR #1405.** The issue
  holds each in full, by number. Most describe the PR's head, so they were read, not run.
  Checked at `541f0daf7`:
  - **Items 1 and 6, joint fits.** Item 1 is stale in part. `multi.py` no longer runs
    `PLAN_PRESETS[name]()`: WP-2102 (#1413) moved both call sites to `resolve_plan(plan, mode)`,
    at lines 1667 and 1784, so a joint fit now takes the mode substitution. What stays open is
    the geometry addition, which is a per-histogram fact, and `assumed_instrument`, which
    `multi.py` still never writes. WP-2103 (the joint fit's verbs) touches the same call sites.
  - **Items 3, 4 and 5.** These are cases (4), (1) and (2) of the Mike Gaultois entry below.
    PR #1405 left them open.
  - **Items 2 and 8 ask for a ruling.** Item 2: whether the importers that assume a geometry
    read `unstated` instead, which changes what a stored calibration opens as. Item 8: whether
    an explicitly named preset that frees the zero also gains the displacement on Bragg-Brentano.
    Both travel with PR #1405's seven provisional choices.
  - **Items 7, 9 and 10** stand on the PR's code: a stored plan keeps the geometry it was stored
    under, Le Bail and Pawley fits list a held polarisation they do not rest on, and a texture
    block on an unstated geometry is refused at compile and not at build.

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

- [x] The reader table: every reader of the geometry kind, with its reading of "unstated",
      written into this file before any code.
- [x] The unstated value, the default for a hand-built `Geometry`; old projects open with
      their stated kind (a test on a file written before this WP).
- [x] The default plan picks by geometry: Bragg-Brentano frees displacement with the zero,
      and keeps a calibrated instrument's Kα2 ratio and axial terms fixed; unstated runs
      `mccusker_default`.
- [x] The notification asking the user to state the geometry, and the report's position
      action under the unstated value.
- [x] The assumed instrument facts recorded in the result.
- [x] Measured on three families (a lab Bragg-Brentano pattern, a capillary and a third):
      the cell and Rwp under the old default and the new. Goldens re-pinned only if no
      further from their reference.
- [x] Audit rows: the plan default and any new code, with tier 3 and approval 2026-10-19
      (`src/rietx/_audit.py`).
- [x] `help.py`, the manual's plan chapter, and a `tests/test_compare_ui.py` row if a
      standard exercises the change.
- [x] Tests + obs/calc/diff PNGs to `tests/output/`.
- [x] Skill: the body or reference row telling an agent to state the geometry, or "none"
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

- **2026-11-04 (3rd and 4th sessions)** — handed over, PR #1405 ready for review, leftovers in issue #1409.
  A Bragg-Brentano fit on the default plan now refines the specimen
  displacement with the zero, and an instrument built by hand states no
  geometry: it gets no geometry-specific correction, and the fit warns and
  says what it assumed. On the NIST LaB6 certification pattern that moves the
  cell from 70 ppm above the certificate to 20 ppm below it, in both Rietveld
  and Le Bail, and the displacement it finds matches NIST's. On the two other
  lab patterns measured it does not help: the round-robin corundum's Rietveld
  cell does not move and its Le Bail cell moves 200 ppm further from the
  certificate, and the GSAS-II tutorial fluorapatite's cell moves about
  400 ppm with the zero and displacement trading along a direction the fit
  itself reports as flat. That mixed result is the maintainer's to rule,
  with seven provisional choices.
  *Done* (`e55422c40` and this entry): the eleven fast failures of the 2nd
  session fixed as its list said, plus three readers of a plan *name* that
  bypassed the geometry: `Refinement.report(plan=name)` (the strategy veto),
  `Project.create(plan=name)` (`project._as_plan_spec`, the stored spec runs
  as an object and no longer resolves) and the text document's `plan` line
  (`textdoc.apply`) now call `resolve_plan` with the mode and geometry, as
  `fit` and the GUI preset route already did; two tests for them.
  `GEOMETRY_UNSTATED` is raised per histogram in a joint fit too
  (`multi.DIAGNOSTIC_SCOPES`, HISTOGRAM) and has a silence pair. The stage
  and watch guides re-measured: the preset's zero stage is `zero_disp` on
  their Bragg-Brentano instrument, and the stage guide's hand-run cell stage
  frees the displacement so the two still free the same parameters.
  *Measured* (`[dev]`, darwin/arm64; old = the preset object, new = the name,
  resolved against the geometry):

  | family | mode | cell vs reference, old → new | Rwp old → new | displacement (mm) |
  |---|---|---|---|---|
  | NIST SRM 660c LaB6, lab BB | Rietveld | a +70.3 → −19.8 ppm | 0.1010 → 0.0982 | −0.073(14) |
  | NIST SRM 660c LaB6, lab BB | Le Bail | a +68.6 → −20.7 ppm | 0.0950 → 0.0920 | −0.072(13) |
  | IUCr CPD corundum (SRM 676a), lab BB | Rietveld | c/a +32.4 → +32.0 ppm; a −329 → −316, c −297 → −284 | 0.14632 → 0.14632 | 0.008(48) |
  | IUCr CPD corundum (SRM 676a), lab BB | Le Bail | c/a −86.6 → −89.8 ppm; a −311 → −510, c −398 → −600 | 0.1524 → 0.1520 | −0.125(45), zero −0.085 → −0.171° |
  | GSAS-II LabData fluorapatite (FAP), lab BB, 15-130° | Rietveld | a −6 → −386 ppm, c −9 → −390, c/a −2 → −4 | 0.0911 → 0.0906 | −0.245(69), zero −0.037 → −0.173° |
  | GSAS-II LabData fluorapatite (FAP), lab BB, 15-130° | Le Bail | a −9 → −429 ppm, c −2 → −427, c/a +7 → +3 | 0.1024 → 0.1019 | −0.270(84), zero −0.036 → −0.187° |
  | APS 11-BM NAC, capillary | Le Bail | identical (control) | 0.1436 | — |

  References: 660c the CIF's recomputed a = 4.156780 Å at 20.85 °C; 676a
  a = 4.759355, c = 12.99231 Å (c/a the certificate-grade ratio,
  `tests/CLAUDE.md`); FAP the GSAS `.EXP` converged cell (9.371724,
  6.885867 Å), a cross-code reference fitted with the displacement held, so
  its distance measures the departure from that protocol, not from truth.
  On FAP the new default also raises `FLAT_DIRECTION`: the zero and the
  displacement are a near-flat pair there, and the cell leaves the ±300 ppm
  band the FAP acceptance suite holds (that suite runs its own plan object
  and does not move). `HIGH_CORRELATION` fires on every Bragg-Brentano arm
  under the new default (zero with displacement).
  Gates, on the branch with origin/main `da5e7aa36` merged in (`[dev]`,
  darwin/arm64, Mac at `-n 4`; pearl unreachable, so `serial.py` queued
  them): fast `-m "not slow"` on `77d10607a` **13866 passed, 318 skipped,
  36 xfailed, 0 failed**. The 17 tests this WP added (33 cases) cost 1.25 s
  together in that run, so none joins the slow tail. Full on the same tree:
  5 failed, 14780 passed, 329 skipped, 53 xfailed. Four of the failures were
  this WP's: the N1, C1 and E8p rows of
  `tests/eval_report_agent/test_landing_states.py` (two for E8p) pin the
  episodes' lazy path, which held the displacement and is now freed by
  name on Bragg-Brentano. They now run the preset object (the request runner
  gets it as a spec), the path they were registered on, and the file passes
  (9 passed). The fifth, `test_pair_diagnostic_class.py::
  test_the_two_site_winner_finds_each_site_its_own_moment`, fails the same
  way on origin/main `da5e7aa36` in the same venv (m₁ 0.6995 against 3.5),
  so it predates this WP and is left alone. Whether the eval episodes' lazy
  path should be re-registered under the new default is question (8).
  Vale 0 errors (241 warnings, as on main); ruff clean.
  *Review* (`/code-review high --fix` over `origin/main..e55422c40`): nine
  findings. The pass fixed three in `b131bdd4f` (`PlanSpec.preset_name` takes
  the mode and geometry, so a Bragg-Brentano project's resolved default is
  named again in the GUI menu and the text document; `Refinement.report`
  resolves under the geometry the fit compiled with; the indexing "geometry
  unknown" branch shares the no-instrument one). The author fixed two more
  there (both GSAS TOF readers state `debye_scherrer`, as
  `Instrument.tof_neutron_bank` does; `assumed_instrument`'s `None` says a
  joint fit does not record it yet); the rest are issue #1409 items 6-10.
  *Generality* (the judge's sections, condensed with verdicts and pointers kept; it ran on `b131bdd4f`, before
  the FAP measurement; the author's answers follow each `weak`):

  **GEOMETRY_UNSTATED — weak.** The case for acting is stronger: an unstated
  geometry is a fact outside the pattern, and saying so is the right
  response. But as written the warning does not reach the readers it names.
  1 Decides: reports and acts on nothing (`refine.py:8550-8571`); the schema
  default it reports on moved from `debye_scherrer` to `unstated` — agrees.
  2 Ambiguity: `ambiguity=1` on grounds that are Rule 1's third kind (facts
  outside the pattern); `Source:polarization` with the same grounds is
  `ambiguity=3` — label disagrees with its grounds. 3 Case against: neither
  TOPAS nor GSAS-II warns, so the warning is rietx's own; its `where` was
  `["instrument.geometry.kind"]`, which matches none of the `cell` or
  `phase_id` globs, so under `purpose="cell"` the code reads info — the
  stated response is not delivered; on a hand-built capillary or transmission
  instrument stating the geometry would not change the default fit. 4 Case
  for: real; the row quoted the issue's untested 45 ppm rather than this
  session's +70.3 → −19.8 ppm — strong. 5 Tier: 3, B9 covers it — holds.
  6 Families: a flag on a categorical input, silence pair — holds. 7 Record:
  `assumed_instrument` lists the kind — holds. Would change the verdict: a
  `where` bearing on `cell` and `phase_id` plus a test that it reads
  `warning` under `purpose="cell"`, and an ambiguity label matching the
  grounds. *Author:* both done in `a10aac9ce` (`where` names
  `instrument.geometry.sample_displacement`, tested under `cell` and
  `phase_id`; `ambiguity=3`; the row quotes this WP's measurement).

  **GEOMETRY_UNSTATED.suggestion — holds.** Names a field and three presets
  and ranks none.

  **rietx.refine._SUPPLIED_POLARIZATION — holds.** A membership test with no
  free factor. Minor: its comment says a preset that changes its number
  changes this with it, true only for 0.99; the 0.5 is a literal here and at
  `schemas/instrument.py:900, 1020, 2200, 2671, 2735`. *Author:* left; a
  named 0.5 constant is a refactor across the schema, noted here.

  **RefinementResult.assumed_instrument — holds.** Records and changes
  nothing; disclosed false positives. Gap, deferred: the preset goniometer
  radius 217.5 mm, which scales the reported displacement by R/217.5 and is
  now an assumed value under every default Bragg-Brentano fit, is not
  listed. *Author:* issue item 3.

  **Refinement.fit:plan — weak.** B7 backs the direction, but the evidence
  for this exact action is thinner than the row said and the case against
  went unstated. 1 Decides: frees the displacement in the zero's stage, the
  cell one stage later — agrees. 2 Ambiguity: 1, contested (dissenters
  below). 3 Case against: the plan page told an uncalibrated user to use
  `mccusker_default` because it frees the zero alone (`staged.py:972-979`);
  `theory/peak-positions.md:313-317` says decorrelate them by calibration;
  corundum Le Bail moved away from its reference with the pair trading;
  brucite on the CPD instrument has the zero/displacement direction at
  eigenvalue 1.4e-10 (`docs/practice.md:656`); FAP shows ρ = +1.000 between
  them and was not measured; MAUD's wizard frees cell, zero and B, not the
  displacement; the NIST protocol and `lab_sample_refine` hold the zero —
  strong, and not in the row. 4 Case for: real on one family (SRM 660c,
  displacement −0.073(14) mm against NIST's −0.07877) — strong on one
  family. 5 Tier: 3 on approval; MAUD a dissent unnamed. 6 Families: two
  Bragg-Brentano families, both development data; NAC a control that cannot
  move — short of the mechanical ground. 7 Record: stage name and free paths
  in the history; `HIGH_CORRELATION` now fires on default Bragg-Brentano
  fits, an attention cost not measured. Would change the verdict: a third
  Bragg-Brentano family (FAP) and a short-range (≤ 90°) scan measured; the
  corundum Le Bail move written into the row; `lab_bragg_brentano`'s
  when-to-use reconciled. *Author:* FAP measured (above: −386 ppm,
  `FLAT_DIRECTION`), which strengthens the case against; the rows now carry
  all three families, the corundum and FAP failure cases and MAUD's
  dissent (`a10aac9ce`, `bfb720230`); the when-to-use no longer says the
  default frees the zero alone. No short-range scan was measured. Whether
  the default stands is question (7) for the maintainer.

  **refine:plan — weak.** Byte-identical to `Refinement.fit:plan`; also
  `SequentialRefinement.fit:plan` now reaches the addition and no series was
  measured. *Author:* as above; a series is unmeasured, said here.

  **DEBYE_SCHERRER_POLARIZATION, KA2_RATIO, Source:polarization — hold.**
  Only grounds/evidence changed, to name the record that now exists.

  **_GEOMETRY_ADDITIONS (outside the table) — weak.** Keyed on the typed
  name, so `profile_only` and `pawley_default` typed on Bragg-Brentano (issue
  #1233's two presets) gain nothing; `preset_name` tries the bare presets
  first, so a project that stored the bare expansion before this change and
  one storing the new expansion are both labelled `mccusker_default` while
  running different stages. *Author:* issue items 7-8; the keying is a
  question for the maintainer.

  **TOF readers state debye_scherrer (outside the table) — holds.** They
  keep the behaviour they had and match the preset; minor gap: no
  "geometry assumed" diagnostic, unlike the CW readers.

  **A stored geometry without `kind` reads debye_scherrer — holds.** No
  package writer omits the key; minor gap: no diagnostic says the fill
  happened.
  *Questions for the maintainer* (provisional, kept as the 2nd session set
  them): (1) the name `unstated`; (2) the default plan name plus a
  displacement addition on Bragg-Brentano rather than a new preset, and the
  stage renamed `zero_disp`; (3) a stored instrument without a `kind` opens
  as `debye_scherrer`, what it was written as; (4) no schema version bump
  beyond the 0.60 already on main; (5) `assumed_instrument` reads values, so a
  caller who typed 0.5 or 0.99 is listed too; (6) importers keep their stated
  fallbacks (issue #1409 item 2); and (7) the measurement above: one
  family better (SRM 660c), corundum neutral or worse, FAP 400 ppm off its
  cross-code reference with `FLAT_DIRECTION` raised. Does the displacement
  addition stand as the default on that evidence, or should it wait on a
  test that the pair is separable on the pattern in hand?
  (8) The eval rows N1, C1 and E8p (`tests/eval_report_agent/PROTOCOL.md`)
  register a lazy path that holds the displacement. By name, that path now
  frees it on Bragg-Brentano, so a live agent round on those episodes no
  longer lands where they were registered. The tests now pin the preset
  object. Should the episodes be re-registered or redesigned?
  *Next*: the maintainer's rulings on the questions above, which decide
  whether the displacement addition stays the Bragg-Brentano default; then
  issue #1409's ten items, item 1 (joint fits) first since items 6 and 7
  follow from it.
- **2026-11-04** — partial handover (context limit), draft PR #1405. The code
  for every task but the measurement is written: a hand-built geometry is now
  `unstated`, the default plan frees the displacement on Bragg-Brentano only,
  a fit on an unstated geometry warns, and the result lists the instrument
  values it held at the package's number. It is not yet green, so no task
  past the reader table is ticked.
  *Done* (commits `be5d8094e` plan mechanism, `7ffdf4577` reader table,
  `87e6005f8` the rest): `Geometry.kind` "unstated" + stored-document fill
  (`Geometry`/`Instrument` before-validators, `STORED_DOCUMENT`); µt refused
  under unstated; texture refused at compile; layer1/2 "unstated" maps;
  pdCIF `?`; indexing "geometry unknown" variant; `GEOMETRY_UNSTATED`
  (warning) and `RefinementResult.assumed_instrument` in `refine.py`; help,
  audit rows (tier 3, 2026-10-19), plan-row evidence; manual
  `concepts/plans.md`; skill rows + copies; GUI `model.ts` + dist (vitest 604
  passed, svelte-check 0 errors); `tests/test_geometry_unstated.py` (25
  passed, `[dev]`, darwin/arm64).
  *Measured*: fast suite `[dev]`, darwin/arm64, on a tree before the skill and
  manual edits: 11 failed, 13796 passed, 318 skipped, 36 xfailed.
  *Next*, in order: (1) fix the 11 — `test_report_loop.py` e1/e2 (BB fits on
  the default name now free displacement: pass `PLAN_PRESETS["mccusker_default"]()`
  as `test_fitreport_layers._fit_and_report` now does), `test_examples.py`
  [watch]/[stage] (guide output moved; re-run the scripts, update the pages),
  `test_gui_help.py` help-key fixture (regenerate), `test_multi_diagnostics.py`
  scope (add `_geometry_unstated_diagnostics` to its table),
  `test_portability.py` (an encoding on `read_text`/`write_text` in the new
  test), `test_silence.py` (a silence pair for `GEOMETRY_UNSTATED`),
  `test_skill.py` budget + api index (regenerate `make_api_index.py`, trim the
  SKILL.md row); (2) run the scratch `measure.py` (SRM 660c, corundum, NAC;
  old = plan object, new = name) and write the numbers here; (3) Vale,
  ruff, full suite via serial.py; (4) file the leftovers issue (draft in the
  scratch dir: multi.py bypass, importers' assumed geometry, radius 217.5,
  calibrated profile, QPA minor phase); (5) `/wp-handover` to ready.
  *Questions for the maintainer* (provisional, kept): the name `unstated`;
  default + displacement on BB with no new preset; a stored instrument without
  a key opens as `debye_scherrer`; no schema bump beyond 0.60;
  `assumed_instrument` reads values, so a typed 0.5/0.99 is listed too;
  importers keep their stated fallbacks.

- **2026-10-19** — created by WP-2002's third session from the B7 and B9 rulings. No open
  WP owns the geometry default: the WPs that name `geometry.kind` are closed GUI work
  (1203, 1205, 1216) or texture (1960 closed, 1974 open and about the texture order).
