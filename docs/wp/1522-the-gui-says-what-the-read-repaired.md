# WP-1522 — the GUI says what reading the project repaired

Milestone: unscheduled · Status: ⬜
Track: Render what the fit already knows
Depends on: — (1321 landed the history channel this shows)
Priority: P3 2026-09-29 — a view over what the readers already report; the python API is the workaround

## Goal

Opening a project in `rietx gui` shows what the readers repaired or assumed on
that open — the pattern reader's `Project.data_diagnostics` and the history
reader's `Project.history_diagnostics` — where a person sees it before the next
fit, so a repair that changes how that fit moves is never invisible there.

## Context

Filed from WP-1321's review (2026-09-29). Both lists are built by
`Project.open` and held in memory only (a deterministic function of the files
and the release, so storing them would be a second authority; `project.py`'s
comments). The GUI server's `project_open` (`src/rietx/gui/session.py`)
discards both, so:

- `DECLARED_RANGE_RESTORED` (warning): a parameter a release before 0.35
  left unbounded gets its declared range and transform back on open, and a
  phase scale passed as a bare `Parameter` now refines under softplus from
  zero. The next fit walks a different path and nothing on screen says why.
- `DECLARED_RANGE_NOT_RESTORED` (warning): a parameter left unbounded because
  a stored value lies outside its declared range. The person should give it a
  range before fitting, and cannot learn that it needs one.
- `HISTORY_EARLIER_TREE_SKIPPED` (warning, WP-2031): a `history.jsonl` a
  release before 1.11 doubled loads its last tree and skips each earlier one.
  The GUI then resumes from the last run, and nothing on screen says the file
  holds another.
- The pattern reader's own repairs (`PATTERN_SCAN_REVERSED`,
  `PATTERN_ROWS_DROPPED`, `PATTERN_INTENSITY_SCALED`, …) have never reached
  the GUI either.

Root CLAUDE.md's rule is that a reader may repair a file only where it can say
that it did. The readers do say it, on their channel; this WP carries the
saying to the one surface that opens projects for people. `gui/CLAUDE.md`
holds the server contract and the panel rules; read it first.

## Non-goals

- New repairs, or changing what either reader reports.
- Persisting the lists in `project.json` (the reason above).

## Tasks

- [ ] The route that opens a project carries both lists, as `Diagnostic`
      dumps, and `test_gui_manual.py`'s route partition is kept whole.
- [ ] A panel or the existing diagnostics surface shows them on open,
      warning level first, with the code, the message and the `where`.
- [ ] Tests: a project whose log predates schema 0.35 (the aging helper in
      `tests/test_project.py`) opens in the server with both codes reported.
- [ ] Manual: `using/gui-guide.md` (or the chapter the panel belongs to).
- [ ] Skill: none expected (an agent reads the lists off `Project`), say so.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_gui_server.py tests/test_gui_manual.py
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1321 — the history and instrument-profile readers' repair, and the
  review finding this is filed from.
- Issue #204 and #209 — the defect the repair answers.

## Handover log

- **2026-09-29** — filed from WP-1321's review; no code touched.
