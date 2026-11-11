# WP-2143 — a case-only rename works on Windows, and its recovery copy follows the folder

Milestone: unscheduled · Status: 🔄 2026-11-12 — claimed by the ghostshift runner main-nightly-windows
Track: The repo's own process
Depends on: —
Priority: P1 2026-11-12 — a required check red on main: the nightly Windows fast job, a release gate, red on 2026-11-10 and 2026-11-11

## Goal

Renaming an open project from `sample.rex` to `Sample.rex` in the GUI's File menu renames
the folder on Windows, as it already does on macOS. Pending edits kept for that project
(its recovery copy) follow the rename on every platform.

## Context

The nightly `fast suite (Windows)` job failed one test on 2026-11-10 (run 42828726928) and
2026-11-11 (run 43026125239), with `1 failed, 14533 passed, 448 skipped, 32 xfailed` the
second night:

```
FAILED tests/test_gui_file_menu.py::test_a_case_only_rename_is_not_refused_as_an_existing_folder
  - AssertionError: assert 'sample.rex' == 'Sample.rex'
```

The test and the verb came in with WP-2133 (the File menu, PR #1502), which is closed, so
this is a new WP. WP-2036 (every nightly leg green) is open and owns the nightly as a whole,
but its open PR #1425 closes it, so a fold there would conflict with that PR.

**Cause.** `GuiSession.project_rename` (`src/rietx/gui/session.py`) returns early when
`target == source`, to make a rename to the same name a no-op. On Windows `pathlib` compares
paths case-insensitively, so `Path("…/sample.rex") == Path("…/Sample.rex")` is `True` there
and the verb returns the old folder untouched. On macOS and Linux the comparison is
case-sensitive, so the rename reaches `_relocate`, whose `os.path.samefile` branch already
handles a case-insensitive volume. The early return asks a question about spelling and must
compare the names as strings.

**A sibling on the same rename.** `_relocate` then calls `recovery.move(state_dir, source,
target)` to re-key the project's recovery copy (WP-2209). `move` re-resolves `source` to find
the old copy. On Windows `Path.resolve()` returns the on-disk spelling, so after a case-only
rename the old name resolves to `…\Sample.rex`, the key of no copy. The copy stays under the
old key and the project no longer finds it: the person's unapplied edits are lost. Its
docstring already says `source` is the old resolved path, so it can be used as the key as
given.

What was not generalised: the other `Path` equalities in the GUI (`project_move`'s no-op
test, `project_copy`'s and `project_move`'s "into itself" tests) ask whether two paths name
one place. A case-insensitive answer is right for that question on Windows, so they stay.

## Non-goals

- `gui/src` and the committed dist: the client sends the name as typed and needs no change.
- WP-2036's other nightly rows, including the Linux `full` job's magnetic row that failed on
  2026-11-11 (`test_pair_diagnostic_class.py`).

## Tasks

- [x] `project_rename` compares the folder names as strings, so a case-only rename reaches the move on Windows
- [x] `recovery.move` keys the old copy by the path it was given, never a re-resolved one; a test makes the old name resolve to the moved folder, as Windows does, on every platform
- [x] Skill: none. The File menu is a GUI surface and the skill drives the Python API.

## Acceptance

The nightly Windows fast job passes `tests/test_gui_file_menu.py` on `main`. Locally, on
any platform:

```sh
.venv/bin/python -m pytest tests/test_gui_file_menu.py tests/test_gui_recovery.py
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-2133 (the File menu, PR #1502); WP-2209 (the recovery copy).
- Python's `pathlib` documentation: `PureWindowsPath` compares case-insensitively, and
  `Path.resolve()` on Windows returns the final path as the file system spells it.

## Handover log

- **2026-11-12** — created by the ghostshift runner main-nightly-windows from the nightly's
  red Windows row. No open WP owns it: WP-2133 is closed, and WP-2036's open PR #1425 closes
  that WP.
