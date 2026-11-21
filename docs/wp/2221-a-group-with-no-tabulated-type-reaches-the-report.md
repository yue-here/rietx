# WP-2221 — A phase whose group has no tabulated type still gets its report and its CIF

Milestone: unscheduled · Status: 🔄 2026-11-21 — the raise fixed, PR #1721 merged 2026-11-20; Mike ruled on #1688 (R-group k-points, parent-frame wording) and the two tasks from that ruling remain
Track: What fires, and what stays silent
Depends on: — (1918 soft: its I-d reads phases of this kind)
Priority: P2 2026-11-21 — the raise is fixed (PR #1721); what remains is Mike's ruling: every R group's satellite candidates include two k-points that are not points of symmetry, and a child's moment note prints a direction that sits 2.19° off its axis when read as a lattice direction; a path few fits run

## Goal

`Refinement.report()` and the nuclear CIF writer return for a phase whose space group is an
operation list that gemmi's table cannot name. Where a consumer needs the crystal system, it
takes it from the operators, or skips that one item and says so.

## Context

Issue #1688 (mustachefeeling, 2026-11-18).

**What fails.** `magnetic_supercell` can return a child whose `space_group` is an unnamed
operation list, for NiO on `R -3 m:R` at k = (½ ½ ½), BNS 2.7:
`R-3m [unnamed in 2a,a+b,a+c]`, 24 operations. The fit runs. `report()` raises in the
satellite analysis, which runs for every phase. Path at 7a4a6cd20:
`report/satellites.py:491` (`analyse_satellites`) → `crystallography/satellites.py:729`
(`zone_boundary_candidates`) → `:746` (`_zone_boundary_candidates` asks
`sg.crystal_system_str()` to decide whether to add the trigonal points) →
`crystallography/symmetry.py:443` → `:421` (`OperatorGroup.closest_type` finds no symmorphic
group in gemmi's table and raises `ValueError`).

**Reproduced on 7a4a6cd20** (macOS arm64, this worktree's venv) with the issue's script: the
child prints `R-3m [unnamed in 2a,a+b,a+c]`, the fit completes, and `report()` raises the
issue's message.

**One sibling found, one cleared.** Same child, same tree:
`io/cif/blocks.py:217` (`write_structure_block`, the nuclear CIF block) raises the same
`ValueError`, because `_space_group_crystal_system` is written from `sg.crystal_system_str()`.
`gui/symmetry.phase_summary` returns. Other callers of `crystal_system_str()` or
`closest_type` not probed: `io/projects/gsas2.py:1537`, `crystallography/superspace/*`,
`indexing/priors.py:140`, `indexing/extinction.py:272`, `gui/symmetry.py:106/161`
(the last two through other routes than `phase_summary`). Each is checked before ticking.

**Why the raise is wrong.** The crystal system is a property of the point group, which the
rotation parts of the operators determine in any setting. What gemmi's table lacks is a named
type in this setting. So "neither its crystal system nor its cell constraints are defined"
overstates it. The fit already works, so the cell ties came by another route (the #614 fix,
reached through `compile_model`). Whether `closest_type` itself changes, or each consumer reads
a crystal system derived from the operators, is the implementer's call. A raise inside a report
section that drops every other section is the defect either way.

**Which phases reach it.** The magnetic children of `magnetic_supercell` (WP-1327's builder;
NiO and MnO on rhombohedral axes, the only rock-salt k = (½ ½ ½) statement rietx can build
today, #757). WP-1918's I-d is to read magCIFs in untabulated orientations and set
`parent_cell` where `_closest_type` is `None`, so its phases are this kind by construction.
WP-1419's displacive children are labelled the same way (`Pm [unnamed in 2a,b,a+c]`) and are
nuclear phases. A test covers one of each kind the tree can build.

**Who decides what.** Making the report return is a defect fix. What a magnetic report then
says about such a phase (for example `MomentEvidence.note`, which the issue names as the
place D24's ruled action writes) is a magnetic-path decision, and those are Mike's
(mustachefeeling) under #1075.

## Non-goals

- Naming the group. The bracketed label is the honest one (WP-1419's ruling).
- The child-cell route that would state these children in an unmixed cell (WP-1418's
  Inherited, #1690; WP-1918 I-c).

## Tasks

- [x] A crystal system read from the operators for an `OperatorGroup` with no closest type, or
      each consumer skipping its one item with a recorded reason. Pin the NiO child.
      Landed as `symmetry.crystal_system_of`, which reads the traces of the rotations'
      proper parts. It agrees with gemmi on all 564 tabulated settings.
      `OperatorGroup.crystal_system_str` always reads it. `cell_constraints` still reads an
      operation list through `closest_type`, so a list in unconventional axes still refuses
      rather than taking conventional ties.
- [x] `report()` returns on the NiO child; the satellite section either runs or says why it
      did not, and every other section is present. The satellite section runs.
- [x] `write_structure_block` writes the NiO child's block, with
      `_space_group_crystal_system trigonal` and no IT number.
- [x] Probe the unprobed callers listed in Context on the NiO child and on a WP-1419 child.
      Five cleared by reading, because no operation list reaches them: `gsas2.py:1537` (its
      group is `gemmi.SpaceGroup(symbol)`), `crystallography/superspace/*` (gemmi groups
      from a superspace group's basic part), `indexing/priors.py:140` and
      `indexing/extinction.py:272` (symbols and gemmi's table). Probed on both children:
      `gui/symmetry.phase_facts` returns its designed error row, whose text now names the
      crystal system; `setting_phrase` raises inside it and is reached nowhere else for these
      phases; `held_causes` raised `AttributeError` on any operation-list phase carrying a
      Stephens block (`OperatorGroup` has no `laue_str`), now fixed.
- [x] Tests (unit, synthetic, no data file) + obs/calc/diff PNGs to `tests/output/`
      (`tests/test_unnamed_group_report.py`; `wp2221_nio_child.png`, `wp2221_pnma_child.png`).
- [x] Skill: none. No section is skipped, so nothing new reaches a reader.

**Ruled by Mike, 2026-11-20 on #1688** (issuecomment-7038491624; the magnetic path is his
under #1075). PR #1721 merged without these, as the ruling allowed ("this PR or a
follow-up"). The ruling's measurements are on the issue.

- [ ] (b) Satellite k-points by lattice. (⅓, ⅓, 0) and (⅓, ⅓, ½) are the K and H points of
      the hexagonal P lattice only (Bradley & Cracknell 1972, Table 3.6; Hinuma et al. 2017,
      Tables 84–86). Drop them from every R group in both settings, so `:H`, `:R` and the NiO
      child list T, L and F alone and agree as sets of stars. Keep them on a hexagonal P
      group, and carry them through (P, p) to a child whose `parent_cell` names a hexagonal P
      parent. The gate is the lattice read from the tabulated setting (the parent's when
      `parent_cell` is set), never the crystal system. The code comment "(⅓, ⅓, ·) is K/H only
      on a tabulated setting's axes" becomes "on a hexagonal P lattice". Tests: `R -3 m:H`
      gets exactly (0, 0, 3/2), (½, 0, ½), (½, ½, 0) and `R -3 m:R` exactly (0, 0, ½),
      (0, ½, ½), (½, ½, ½), which changes the `R -3 m:H` row of `CENTRED_SETS` and the
      primitive-setting identity test's literal in `tests/test_satellites.py`; setting
      invariance as stars on all seven R groups (146, 148, 155, 160, 161, 166, 167), and the
      NiO child's set equal to the `:R` set mapped by (2a,a+b,a+c;0,0,0); `P 6/m m m` and
      `P -3 m 1` keep both points, and a hexagonal P child with `parent_cell` gets them mapped.
- [ ] (a) The magnetic sections state a `parent_cell` phase in the parent's frame. The phase
      is named by the parent's setting, the transform and its BNS number ("child of
      `R -3 m:R` by (2a,a+b,a+c;0,0,0), magnetic group BNS 2.7"), saying which crystal system
      belongs to which. Every direction a magnetic note names is a lattice direction [uvw] of
      the parent first, with this cell's beside it. One rule covers `MomentEvidence.note`,
      the direction in `MOMENT_ANGLE_STATIONARY` and #1576's warning when it lands. A phase
      without `parent_cell` keeps its own cell. Tests on the NiO `R -3 m:R` child with
      moments: the note names [1, 1, 1] of the parent and [-0.5, 1, 1] in this cell; the
      printed child vector, taken through the direct-lattice matrix, lies on the stage's
      recorded flat axis to < 1e-6°; `MomentEvidence.phase` names the parent setting, the
      transform and BNS 2.7; #599's named control keeps its own-cell wording and numbers. This
      changes what a fit prints, so the texts go to the maintainer before merge.

## Acceptance

The issue's script runs to the end, and `report()` returns a FitReport whose sections are all
present.

```sh
.venv/bin/python -m pytest tests/test_magnetic_supercell.py tests/test_satellites.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #1688; related #614, #612 (both closed), #757.

## Handover log

- **2026-11-21** — the merge recorded, by a ghostshift runner (PR #1735). The defect this
  WP was filed for is fixed on `main`. PR #1721 merged at 2026-11-20 18:45Z as merge commit
  21b328f49 and closed #1688. A phase whose group no tabulated setting names now gets its
  report and its nuclear CIF block. The WP stays in flight for Mike's ruling. He answered
  the question the last entry left for him at 11:33Z the same day, before the merge, and
  ruled on two points. On an R lattice the two ⅓ k-points are not points of symmetry in
  either setting, so they leave every R group's candidate list. A child with `parent_cell`
  states its magnetic group and its directions in the parent's frame. Nothing in the package
  changed in this session.

  *Done.* Status and `Priority:` rewritten. The ruling's two parts are now the WP's two open
  tasks, each with the tests Mike named. WP-1418's Inherited note on the NiO route now
  records that the report-side raise is fixed.

  *Settled by Claude.* (1) The ruling's work stays in this WP rather than a new one. Grounds:
  the fold-first rule in `docs/wp/TEMPLATE.md`, and the ruling answers this WP's own open
  question on its own issue. Alternative: a new WP for the parent-frame wording, which
  reaches `MomentEvidence` beyond this WP's report fix. (2) The WP stays P2 with its reason
  rewritten. Grounds: the rubric's P2 row for a defect that fires wrongly; a candidate list
  that names two non-special points is one. Alternative: P3, since a reader can discard the
  two candidates by hand.

  Next: task (b) first. It is self-contained in `crystallography/satellites.py` with pinned
  test changes. Task (a) changes reader output, so its texts go to Yue before merge.

- **2026-11-20** — implemented, by a ghostshift runner (PR #1721). A phase whose space group
  is an operation list that no tabulated setting names can now be reported and written to a
  CIF. The crystal system is a property of the point group, so the package now reads it from
  the rotations of the operations, in any cell. The fix checks that rule against gemmi on all
  564 tabulated settings, and the two agree on every one. What still needs a tabulated
  setting still raises: a symbol, an IT number, `ext`, a monoclinic unique axis, and the cell
  ties read from the table. The children of this kind state their cell through the parent's,
  so none of them needs those.

  *Done.* `symmetry.crystal_system_of` reads the traces of the proper parts of the distinct
  rotations (1 + 2cos φ is basis-free). `OperatorGroup.crystal_system_str` always uses it.
  `cell_constraints` now reads an operation list through `closest_type` explicitly, so a
  list in unconventional axes still refuses, rather than taking conventional ties from the
  newly answerable system. The `closest_type` refusal no longer says the crystal system is
  undefined; it names it. `gui/symmetry._strain_causes` asked an `OperatorGroup` for
  `laue_str`, which it lacks, so any operation-list phase with a Stephens block crashed
  `held_causes`. It now reads the Laue class off the closest type, or names the operators.

  *Measured.* macOS arm64, this worktree's `[dev]` venv (no jax), on the branch tree before
  the WP-1918 note. Fast selection: 14951 passed, 433 skipped, 32 xfailed. No base run was
  made, so the delta is not measured. The new file adds 11 cases in 7 tests, which ran 3.87 s
  in total on one local run; the slowest is the two report fits, 2.75 s together. The
  related files (`test_magnetic_supercell`, `test_satellites`, `test_operator_list_phase`,
  `test_parent_cell`, `test_magcif`, `test_wyckoff`, `test_magnetic_p1`,
  `test_distortion_candidates` and the new file): 582 passed, before the step-6 review
  fixes. `tests.reader_output`: unchanged. The PNGs `tests/output/wp2221_nio_child.png` and
  `wp2221_pnma_child.png` were looked at: GoF 1.00 on both, and the NiO child's magnetic
  (½ ½ ½) line sits at 22.6° as d = 4.82 Å predicts.

  *Review (step 6).* `/code-review high --fix` found six items. Two were applied: the
  hexagonal k points read off the setting, and one shared proper-rotation helper. Declined:
  filling the GUI symmetry row (a panel change, Yue's call, see below); the refusal
  message's wording for a list that is not a group (only reachable past the schema's
  closure check); the pre-existing `:R` k points (named-group output, a question for
  Mike); and a note that the `laue_str` fix also covers a listed group whose closest type
  resolves, which it does.

  *Generality.* Not dispatched. No `_audit` row was added or changed, and the two
  fallbacks added are definedness conditions, not tuned choices: a setting exists or it
  does not. Settled by Claude under the judge's trigger list in `/wp-handover` step 7; a
  reviewer could read the satellite gate as a fallback chain and dispatch it.

  *Not generalised, deliberately.* `gui/symmetry.group_facts` still returns its error row
  for these children, because its Laue class, point group and Sohncke flag come from the
  closest type. A point-group symbol in unconventional axes has no tabulated spelling, so
  filling those fields would mean a new rule. The error row is the panel's designed state
  for a group it cannot describe, and its text is now accurate. The setting-bound members
  (`hm`, `ext`, `number`, `monoclinic_unique_axis`) still raise; deriving them would mean
  choosing a setting, which is #1330's standardisation route (Mike's PR #1332).

  *Settled by Claude.* (1) The crystal system comes from the operators for every operation
  list, not only as a fallback. Grounds: the trace rule equals gemmi's answer on all 564
  settings, and the closest type has the same point group by construction, so the two
  routes cannot disagree where both exist. One rule beats a rule with an exception
  (DESIGN Rule 5). The alternative was a fallback used only where `closest_type` is `None`.
  (2) The satellite generator decides on its hexagonal points, (⅓, ⅓, 0) and (⅓, ⅓, ½), from
  the tabulated setting, not from the basis-free crystal system. An operation list with no
  tabulated setting in its axes gets none. Grounds: accuracy. In the NiO child's
  2a,a+b,a+c axes, (⅓, ⅓, 0) is no special point, so listing it would rank a k-vector that
  WP-1326's rule never meant. Named groups and lists that resolve are unchanged, and these
  children listed no candidates before, because the report raised. The alternative was the
  rule keyed on the crystal system alone, which would add the two points in the child's own
  axes. This came from the step-6 review; the first draft had taken the alternative.

  *Question for Mike (magnetic path, #1075), not settled here.* On such a child, should the
  generator carry the hexagonal points through the cell transform rather than leave them
  out? A related case predates this WP: a named `:R` setting such as `R -3 m:R` also gets
  (⅓, ⅓, 0) in rhombohedral axes, where it is no special point either.

  *Overlap.* `crystallography/symmetry.py` is also touched by Mike's open PR #1332, in
  `refuse_distortion_modes` (line ~119); this branch edits lines ~330-460 and
  `cell_constraints`. No other open PR of Mike's touches these files.

  Next: none in this WP once the PR merges, apart from the question for Mike, which belongs
  to WP-1326's successor if he wants a change.
- **2026-11-19** — created, from the 2026-11-19 issue triage (PR #1697; issue #1688). A magnetic child
  that rietx itself builds can be fitted and then cannot be reported or written to a CIF.
  Checked against the tree at 7a4a6cd20: the issue's script reproduces, and the nuclear CIF
  writer raises the same error on the same child. No open WP owns it: WP-1326 built the
  satellite analysis and is closed; WP-1327 owns the builder, whose output is a valid group; WP-1918 I-d will
  produce such phases and is pointed here. Next: task 1.
