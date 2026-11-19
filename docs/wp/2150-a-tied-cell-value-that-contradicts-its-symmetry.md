# WP-2150 — A tied cell value that contradicts its space group is repaired at read or refused

Milestone: unscheduled · Status: ⬜
Track: What fires, and what stays silent
Depends on: —
Priority: P2 2026-11-18 — a silent wrong answer on a path few fits run: a cell length (or a rhombohedral angle) that its space group ties to another is replaced by that other value with no word, at any size of disagreement (#1669)

## Goal

A structure whose stored cell disagrees with the ties its space group imposes no longer
builds silently. A reader snaps a disagreement within the file's own printed precision and
records it as a `Diagnostic`. A larger one is refused, by the reader or by the table, with
the entry, both values and the symbol named.

## Context

**What the tree does, checked at `3f5167863`** (a one-atom CIF read by
`structure_from_cif`, then `ParameterTable(structure,
Instrument.debye_scherrer(wavelength=1.54))` and `decode(x0())`):

| Case | Stored | Built | Diagnostics |
|---|---|---|---|
| `F m -3 m`, b off by 2 ppm | a = 5.641, b = 5.64101 | b = 5.641 | none |
| `F m -3 m`, b off by 4.6 % | a = 5.641, b = 5.9 | b = 5.641 | none |
| `P 4/m m m`, b off | a = 4.0, b = 4.1 | b = 4.0 | none |
| `P 6/m m m`, b off | a = 3.0, b = 3.2 | b = 3.0 | none |
| `R -3 m:R`, β off | α = 60, β = 61 | β = 60 | none |
| `R -3 m:R`, c off | a = 5.0, c = 5.3 | c = 5.0 | none |

The mechanism is `ParameterTable._collect_cell` (`src/rietx/params/vector.py`). It calls
`check_cell_angles` (`crystallography/symmetry.py`), which checks only the **fixed** angles
of `cell_constraints(sg)` against `SYMMETRY_ANGLE_TOL_DEG` (1e-3°). Every **tied** entry
goes in with `AffineTie.identity` onto its source, and its stored value is never read. That
covers the lengths of every tetragonal, trigonal, hexagonal and cubic setting, and the tied
β and γ of an R lattice on rhombohedral axes. The issue named only lengths. The tied angle
is the sibling found here.

**Who reaches it.** Every reader that builds a `Cell`: `structure_from_cif` and the magCIF
reader (`crystallography/cif.py`, `magcif.py`), the project readers under `io/projects/`
(`gsas2.py`, `gsas.py`, `topas.py`, `fullprof.py`), the recipe reader (`io/recipe.py`), the
Jana reader of PR #1627 (WP-1314, open) once it merges, and a hand-built `Structure`.
`complete_cell` (the GUI's typed-cell route) already refuses a value for a determined
parameter, and `set_values` refuses an edit to a tied path. Neither is affected.

**The rule this follows** (root `CLAUDE.md`, "A silent correction is a reader's to make";
WP-1028, WP-1036). The table has no diagnostics channel, so it refuses and never corrects.
A reader has the channel, so it may repair a deviation that is a report and must leave a
contradiction to raise. The angle half exists: `cif._correct_symmetry_angles` snaps a fixed
angle within `CIF_ANGLE_CORRECT_MAX_DEG` (0.1°) and records `CIF_CELL_ANGLE_CORRECTED`.
The nearest precedent for a band set by the file's own digits is WP-2016 (a U^ij off its
site symmetry by rounding is projected and reported) and `CIF_PRINTED_ROUNDING` (WP-2037,
half the last printed digit).

**Constraints on the design.**
- `complete_cell`'s docstring declined a length tolerance in 2026-08 as "a constant nothing
  else in this package needs, chosen from nothing". This WP needs one for the table's
  refusal, so it must be chosen by consequence, as `SYMMETRY_ANGLE_TOL_DEG` was (8.3 ppm in
  d at its value, under SRM 660c's 48 ppm certificate band). A relative deviation ε in a
  tied length moves the affected d-spacings by at most ε, so the same consequence argument
  gives a relative bound directly. Update that docstring when the constant lands.
- `validate_by_lebail` builds a table from every indexing candidate. The angle constant's
  comment measured candidate angles within 1.4e-14° of exact, 7e10 times under the
  tolerance. Measure the same for candidate tied lengths before choosing the bound, or the
  indexer refuses its own answers.
- A project (`.rex/`) whose history holds a contradicting cell must still open (old files
  always open). Measure whether a saved state can hold one: a fitted project writes the
  tied value back, but a project created from a file and never fitted may not. If it can,
  the open path repairs it with a recorded note, or the refusal names the fix.
- Which band a reader snaps within is a choice between the file's printed precision (the
  issue's proposal, WP-2016's precedent) and the stated su where the file prints one. The
  CIF prints both. A project file usually prints neither, so it may need its own rule.

**Reader output goes to the maintainer before merge** (ruled 2026-11-01). Each new
diagnostic code, its message and suggestion, and the table's refusal text are reader
output. Run `python -m tests.reader_output` and put each added line, with its diff, in the
PR for his decision.

**Tier.** The ties are physics (the space group's metric). The snap band is named practice
(a file's printed digits). The table's relative bound is chosen by consequence. Each new
code and constant takes its `rietx._audit` row.

### Inherited

## Non-goals

- A space group's **fixed** angles: handled by `check_cell_angles` and
  `CIF_CELL_ANGLE_CORRECTED` (WP-1036, WP-1028).
- Choosing a lower-symmetry group for a cell that contradicts its symbol. That is the
  caller's call, and the refusal names it as the fix.
- The special-position refusal on atoms (WP-1913, part 4). It touches `params/vector.py`
  as this WP does, in `_site_rows` and `Refinement.__init__`, not in `_collect_cell`.

## Tasks

- [ ] Measure: tied-length deviations of indexing candidates entering `validate_by_lebail`
      on the indexing acceptance set; whether a saved `.rex` state can hold a contradicting
      tied value.
- [ ] The table: `check_cell_angles` widened (or a sibling beside it) to every tied cell
      entry, refusing beyond a relative length bound and the existing angle tolerance,
      naming the entry, both values and the symbol. `complete_cell`'s docstring updated.
- [ ] The CIF and magCIF readers: snap a tied entry within the file's printed precision
      onto its source and record it (one code for lengths and tied angles, or two; the
      maintainer rules the text). A larger deviation is left as written and raises.
- [ ] The project readers (`gsas2`, `gsas`, `topas`, `fullprof`, `recipe`) and, once
      merged, Jana: the same snap or a refusal by name, through one shared helper.
- [ ] The `.rex` open path, if the measurement says a stored state can contradict.
- [ ] Tests: the six cases above at both sizes; an indexing candidate still validates.
- [ ] `_audit` rows, `help.py` for each new code, the manual's reader page.
- [ ] Skill: a reference row for each new code (root `CLAUDE.md`: a diagnostic code adds
      its row).

## Acceptance

Each of the six cases above either reads with a recorded diagnostic (within printed
precision) or raises naming the entry and both values. No case builds silently. The
indexing acceptance ranking is unchanged.

```sh
.venv/bin/python -m pytest tests/test_robustness_external.py tests/test_params.py tests/test_audit_table.py -q
.venv/bin/python -m pytest tests/test_acceptance_indexing.py
.venv/bin/python -m tests.reader_output
.venv/bin/python -m ruff check src tests examples
```

## References

- Issue #1669 (maintainer, 2026-11-17), found reviewing PR #1627 (the Jana reader).
- WP-1028 (`CIF_CELL_ANGLE_CORRECTED`), WP-1036 (the angle refusal), WP-2016 and WP-2037
  (repairs within printed precision).

## Handover log

- **2026-11-18** — created, from the 2026-11-18 issue triage (issue #1669). Checked against
  the tree at 3f5167863: reproduced, a tied length builds from its source at 2 ppm and at
  4.6 % alike with no diagnostic, and the R-on-rhombohedral-axes tied β does the same (the
  sibling the issue did not name). No open WP owns it: WP-1913 (🔄, runner active in
  `params/`) owns the special-position refusal on atoms, not the cell; WP-1314 is the Jana
  reader that inherits the defect; WP-1028, 1036 and 2016, the precedents, are closed; no
  open WP cites `_collect_cell` or `cell_constraints` for a stored-value check. Next: the
  two measurements in the first task.
