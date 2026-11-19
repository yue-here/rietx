# WP-2221 — A phase whose group has no tabulated type still gets its report and its CIF

Milestone: unscheduled · Status: 🔄 2026-11-19 — claimed by @yue-here (ghostshift runner)
Track: What fires, and what stays silent
Depends on: — (1918 soft: its I-d reads phases of this kind)
Priority: P2 2026-11-19 — a fit completes and then `report()` raises, so no section of the FitReport can be read; the NiO and MnO rhombohedral magnetic children reach it, a path few fits run

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

- [ ] A crystal system read from the operators for an `OperatorGroup` with no closest type, or
      each consumer skipping its one item with a recorded reason. Pin the NiO child.
- [ ] `report()` returns on the NiO child; the satellite section either runs or says why it
      did not, and every other section is present.
- [ ] `write_structure_block` writes the NiO child's block.
- [ ] Probe the unprobed callers listed in Context on the NiO child and on a WP-1419 child.
- [ ] Tests (unit, synthetic, no data file) + obs/calc/diff PNGs to `tests/output/`
- [ ] Skill: none expected. A raise that stops raising needs no routing row; if a section is
      skipped with a reason, that reason is the package's own output.

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

- **2026-11-19** — created, from the 2026-11-19 issue triage (PR #1697; issue #1688). A magnetic child
  that rietx itself builds can be fitted and then cannot be reported or written to a CIF.
  Checked against the tree at 7a4a6cd20: the issue's script reproduces, and the nuclear CIF
  writer raises the same error on the same child. No open WP owns it: WP-1326 built the
  satellite analysis and is closed; WP-1327 owns the builder, whose output is a valid group; WP-1918 I-d will
  produce such phases and is pointed here. Next: task 1.
