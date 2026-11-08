# WP-1528 — the cell box is declined where the cell is declared

Milestone: unscheduled · Status: ✅ 2026-11-03 — `Cell`'s docstring says why the cell carries no default box (PR #1365)
Track: What fires, and what stays silent
Depends on: —

## Goal

`Cell`'s docstring says why its six parameters carry no default box, and issue
#283 closes on that reason.

## Context

Issue #283 reported a degenerate cell running away in the solver. The guard
landed under WP-1321 (`DegenerateCellError`, `CELL_DEGENERATE_PROBE`, commit
`0ae0e063`). A default box on `Cell` was tried and withdrawn (`178e6017`). WP-1321
is ✅, so what its fix did not cover is filed here.

**The reason, checked at `e3e6486a`:** a finite stored bound is the caller's
claim. `params.vector.cell_window` keeps it (`vector.py:~467-472`) and skips its
own support-based window, and `ParameterTable.bounds()` is ordered on purpose so
that nothing makes a side finite ahead of it (`:2344-2351`). A schema box would
therefore act on every free cell: it changes TRF's trust-region scaling even
when never hit (cpd-1c went from 82 to 400 iterations, 6.30 to 9.04 wt % with
windows on every phase, per the `cell_window` docstring), and it would appear in
`ParameterRow` and the `.rxt` document as a claim the user never made.

**What other programs do** (read, with gaps): TOPAS uses a value-relative
default window, a, b, c within Max(1.5, 0.995·Val − 0.05) to 1.005·Val + 0.05 and
angles within Val ± 0.2, read from a search summary of the manual; cctbx checks
validity (`unit_cell.is_degenerate`, `unit_cell_angles_are_feasible`) and
bounds nothing; FullProf limits are optional and per file. No program read
ships a fixed hard default box on a cell. GSAS-II, SHELXL, Jana2020 and scipy
were skimmed or not checked.

**Decided 2026-09-30:** keep the limit as a window built at table-build time
(`freeze_cell_windows`, `cell_window`, the post-solve `clamp_cell_runaway`) and
put no box on `Cell`. Still open, and only if a measurement asks for it: a
*visible* phase whose cell runs to a degenerate angle inside one stage. The
guard neutralises and counts each probe. If it needs anything, it is a finding,
not a bound.

## Non-goals

- Any new bound, window or clamp.
- Measuring how often a visible phase probes a degenerate angle since the guard
  landed: a separate WP if someone wants the number.

## Tasks

- [x] `Cell`'s docstring (`schemas/structure.py:136-145`) states the reason above in a few sentences
- [x] Skill: none

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_docs_consistency.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- Foadi & Evans (2011), the paper cctbx's header cites for the angle feasibility check (not read).
- Issue #283; WP-1321.

## Handover log

- **2026-11-03** — `Cell`'s docstring now says, in a few sentences, why
  the cell's six parameters carry no default box. A finite stored bound is
  read as the caller's own claim, so a box in the schema would act on every
  free cell: it switches off the runaway window on its side, and it would show
  to a reader as a limit nobody set. Under `solver="trf"` it also changes the
  solver's step even when never reached; the default `lm` reads a box only when
  a step reaches it (Yue's review, 2026-11-05). The docstring names where the
  limit lives instead. Issue #283 was already closed; this closes the WP. PR
  #1365.

  *Done:* the docstring (`src/rietx/schemas/structure.py`, class `Cell`),
  checked against the tree at `d0c4bded`: `cell_window` keeps a finite side
  and the cpd-1c numbers are its docstring's; `ParameterTable.bounds` states
  the ordering rule. *Gotcha:* the Context's `clamp_cell_runaway` no longer
  exists. WP-2002 (`b9ed0b36`) replaced it with `refine.reset_cell_runaway`,
  which puts a runaway phase's whole cell back at the stage's start, so the
  docstring names that. The Context is left as written, as the record of what
  was decided on 2026-09-30. The `### Inherited` entry (#719) was consumed by
  PR #736 per the entry below, and was deleted on close.

  *Measured* (`[dev]` venv, macOS arm64): `ruff check src tests examples`
  clean; `tests/test_docs_consistency.py` 25 passed. No fast or full suite:
  the change is a docstring. `/code-review` was not run: the only `.py` hunk
  is a docstring, every name it cites was checked to resolve, and the shift
  budget was short. No CLAUDE.md edits, no heuristic, no skill row.

  *Next:* nothing for this WP.

- **2026-10-06** — PR #736 (#719) merged from outside as `3b8882b7`.
  Where the clamp would leave a phase's cell with no volume,
  `clamp_cell_runaway` now restores every free cell parameter of that phase
  to the stage's starting values. `CELL_RUNAWAY` reports which parameters it
  clamped and which it restored. The determinant is taken after
  `refresh_ties()`, so a tied angle is read at the value the table would
  hold. Gated together on a seven-PR stack replayed onto `main` at `7c8a0316` (stack `ee39adb9`, macOS arm64, `[dev,jax]`). The fast suite gave 8523 passed, 103 skipped and 2 failed. Both failures fail identically on bare `main`: the `toy_anomalous` golden (#760) and a hypothesis case in `test_indexing_reduce.py`. The whole slow tier gave 291 passed and 12 skipped. After the last merge, `main` at `0cbb1b70` is content-identical to the gated tree. This WP's own task, `Cell`'s docstring, is untouched. Gotcha:
  nothing pins #719's symptom at fit level deterministically. The
  public-path test only asserts that a `CELL_RUNAWAY` fired, because on
  py3.13 its trajectory never reaches the degenerate corner. The restore is
  pinned at table level.

- **2026-09-30** — created, from the 2026-09-30 issue triage (issue #283).
  Checked against the tree at `e3e6486a`: the `Cell` fields are still bare
  `Parameter` objects and the guard is in place. No open WP owns it: WP-1321,
  which closed the guard half, is ✅.
