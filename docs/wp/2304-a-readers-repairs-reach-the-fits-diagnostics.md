# WP-2304 — A reader's repairs reach the fit's diagnostics

Milestone: unscheduled · Status: ✅ 2026-11-25 — every fit repeats what the reader repaired or noticed, whether or not a list was passed; PR #1842
Track: What fires, and what stays silent
Depends on: —

## Goal

What `read_pattern` repaired or noticed in a file reaches `result.diagnostics` of every fit
on that pattern, once per code, whether or not the caller passed `diagnostics=[]`.

## Context

**Today** (`io/readers.py`, `read_pattern` docstring, on `f9adf0e57`): "The refusal runs on
every call; the report ... only when a caller passed the list." So `PATTERN_INTENSITY_SCALED`
(an attenuator applied, σ withheld where the scale cannot be established),
`PATTERN_SIGMA_CONSTANT` and `PATTERN_SIGMA_NONPOSITIVE` reach no one unless the caller asked.
The fit repeats one of them on its own, `PATTERN_DEAD_CHANNELS` (`refine.py`). The rule for
repairs is root CLAUDE.md § Invariants, WP-1047: "A pattern reader may repair a file only
where it can say that it did." `src/rietx/io/CLAUDE.md` holds the dispatch and the repairs.

**The rule.** [DESIGN § Rules](../DESIGN.md#rules), 4, as amended 2026-11-23, and Rule 4's
test for a new output: an agent can write the next call from it without a rerun. An agent
reads `result.diagnostics` on every fit (the skill's rule 9). A python warning is the weak
channel: `Refinement.set_vary`'s docstring says a warning "can scroll past or show once per
call site", so one warning would cover a batch of 200 files.

**The design.** Carry the reader's notes on `PatternData` and have the fit copy them into
`result.diagnostics`, deduplicated by code against what the fit raises itself. The history
fingerprint is the sha256 of the 2θ and intensity bytes only (`schemas/history.py`,
`TreeHeader.data_fingerprint`), so a new field leaves it alone. A project stores the pattern
file's bytes, not a `PatternData`. Check every other place a `PatternData` is serialised
(the GUI's wire, `model_dump` round-trip tests, `SeriesResult`) before adding the field.

**In the review** (2302-batch/plans.md, Plan 2 D), a first draft also warned when no list was
passed. That was dropped for the channel reason above.

Tier: none. The notes are the reader's existing codes, already in `_audit`.

## Non-goals

- `Structure` and `Instrument` carry CIF and instrument-file repairs too
  (`CIF_SPECIES_NORMALISED`, `CIF_CELL_ANGLE_CORRECTED`). Both are stored in history nodes, so
  a field there is a stored-format change. It needs its own decision and its own WP.
- Changing any repair itself.

## Tasks

- [x] List every place a `PatternData` is serialised or compared, and confirm a new field
  breaks none of them. No schema field holds a `PatternData`. Every fingerprint hashes the
  arrays alone: `TreeHeader.data_fingerprint`, `DataRef.fingerprint` and `refine._refit_key`.
  A `model_dump`/`model_validate` round trip (`test_tof_axis.py`, the report-eval fixtures)
  loads an old dump with the default empty list.
- [x] `PatternData` carries the reader's notes; `read_pattern` fills it whether or not a list
  was passed, and still extends the list when one was. The caller's list is extended in a
  `finally`, so a refusal's notes still reach it. `crop` carries the notes.
- [x] Each fit entry point copies the notes into `result.diagnostics`, one per code;
  `PATTERN_DEAD_CHANNELS` appears once. One seam: `compile_model` copies them onto
  `CompiledModel.reader_notes`, and `refine._build_result` (every single-pattern entry point:
  `fit`, `run_stage`, `cherry_pick`, `replay`) appends them last. A note whose code the fit
  already raised is left out. The fit owns `PATTERN_DEAD_CHANNELS`: it asks again on the fitted
  channels, so the reader's copy is never handed on.
- [x] A series and a joint fit carry each pattern's notes (per pattern in a series, per
  histogram in a joint fit). A series fits each pattern through `refine`, so it inherits the
  seam. The joint fit calls the helper in its per-histogram loop, with a `DIAGNOSTIC_SCOPES`
  row.
- [x] `src/rietx/io/CLAUDE.md` § the repairs: the notes reach the fit.
- [x] Tests: one fixture per repair code, read without a list, asserting the code in
  `result.diagnostics`. `tests/test_reader_notes.py`, seven cases.
- [x] Skill: none. The codes already have rows; they now arrive where the skill already sends
  the agent. One row named only the reader's list as its channel (`PATTERN_SCAN_REVERSED`)
  and now names both; the manual's pattern-files page says the same in one sentence.

## Acceptance

A file that triggers `PATTERN_INTENSITY_SCALED`, read with no `diagnostics=` list and fitted,
carries that code in `result.diagnostics` exactly once.

```sh
.venv/bin/python -m pytest tests/test_readers_robust.py tests/test_reader_notes.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- Thomson, M. & Schinazi, D. (2023), RFC 9413, "Maintaining Robust Protocols": tolerance needs
  defined, visible handling.

## Handover log

- **2026-11-25** — closed. What a pattern reader repaired or noticed in a file now reaches
  every fit on that file, whether or not the caller passed a `diagnostics=` list. Before, a
  file whose intensities were rescaled, or whose σ was withheld, constant or partly zero, was
  fitted with no word in `result.diagnostics` unless the caller had asked the reader. Now the
  notes ride on the pattern, and every single fit, series member and joint-fit pattern repeats
  them once. Two kinds stay behind: the dead-channel check, which the fit asks again on the
  channels it fits, and a note whose advice the caller took before fitting.

  *Done.* `PatternData.diagnostics` (default empty, carried by `crop`). `read_pattern` fills it
  on every call and extends a passed list in a `finally`, so a refusal's notes still reach the
  caller. `compile_model` copies the notes onto `CompiledModel.reader_notes`.
  `refine._reader_diagnostics` appends them last in `refine._build_result` (so `fit`,
  `run_stage`, `cherry_pick`, `replay` and each series member) and in the joint fit's
  per-pattern loop (a `DIAGNOSTIC_SCOPES` row, HISTOGRAM). A note is left out where the fit
  already raised its code; where the code is in `refine._FIT_OWNED_READER_CODES`
  (`PATTERN_DEAD_CHANNELS`); or where `refine._reader_note_settled` finds its advice taken
  (`PATTERN_X_AXIS_IMPLAUSIBLE` with no fitted channel at or below 0°, `PATTERN_SIGMA_CONSTANT`
  once the fit has no measured σ). An exact repeat is dropped; two reader notes sharing a code
  with different messages both pass. `Project.create` puts its option pre-filter's
  `READER_OPTION_IGNORED` on the pattern too, and `rietx compare`'s FAP standard keeps the notes
  when it rebuilds its pattern. `read_pattern`'s docstring, `io/CLAUDE.md`, the manual
  (`reference/data.md` field row, one sentence in `reference/pattern-files.md`), the
  `PATTERN_SCAN_REVERSED` skill row and the generated skill API index name the new channel; the
  skill copies are re-synced.

  *Serialisation survey (task 1).* No schema field holds a `PatternData`. Every fingerprint
  hashes arrays alone: `TreeHeader.data_fingerprint`, `DataRef.fingerprint`,
  `refine._refit_key`. A project stores the file's bytes. JSON round trips (`test_tof_axis.py`,
  the `tests/eval_report_agent` fixtures) load an old dump with the empty default.

  *Measured* ([dev], darwin/arm64, this worktree's venv). `tests/test_reader_notes.py`: 8
  passed; with the hand-on in `_build_result` disabled, the four that fit a read file through it fail. Fast suite on the final tree: 15746 passed, 452 skipped, 30 xfailed, 18-19 min wall beside WP-2305's suite on the same machine. A run during the review had three failures: the skill API index was stale (regenerated), and two whole-tree checks read files the review was editing mid-run and pass on rerun. Passed+skipped moved by one between the two runs, the test the review added. The eight added tests cost 4.40 s in that run (`tests.added_test_times`), none near the slow tail.
  `tests.reader_output`: exit 0, unchanged against the merge-base. CI's lint steps, Vale
  included: 0 errors. Full suite not run: no measured number moves, and a grep of the slow
  tests found none asserting a whole diagnostics list on a fit of a read file.

  *Review.* `/code-review high --fix` found five; all landed in one commit. Two were stale
  advice (the axis and constant-σ notes above). Three were missed sites or hygiene
  (`Project.create`, the compare FAP standard, the test module's xdist group). Not fixed, by
  the review's own account: `PATTERN_SIGMA_NONPOSITIVE` and `PATTERN_INTENSITY_SCALED` can go
  stale the same way when a caller edits σ before fitting, and no reliable test separates
  that, the second code being raised for reasons other than σ too; and `crop` keeps notes about
  points it removed, the axis note excepted.

  *Gotchas.* WP-2305 renames the joint call and "histogram" in a parallel branch. This branch
  adds one `DIAGNOSTIC_SCOPES` row and one call in `multi.py`'s per-pattern loop, so whichever
  merges second resolves two lines. Info-level reader notes (`PATTERN_SCAN_REVERSED`,
  `PATTERN_DUPLICATE_POINTS`, `READER_OPTION_IGNORED`, …) now print as one line each in
  `str(result)` for a file that triggers them; the standard fit's file triggers none.

  *Generality.* No judge dispatched: no `_audit.py` change and no new code. The rules added
  choose which of two copies of one report is shown, and when a report no longer describes the
  fit; neither sets a number or an action. The WP's own tier line says none.

  Next: none. PR #1842.
- **2026-11-23** — created from the API review (2302-batch/plans.md). No open WP owns
  where a reader's notes land: WP-1952 is the xy reader's own skips, and WP-2146 the ISIS iparm
  repairs. Next: the serialisation survey.
