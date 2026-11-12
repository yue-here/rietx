# WP-2143 — a case-only rename works on Windows, and its recovery copy follows the folder

Milestone: unscheduled · Status: ✅ 2026-11-12 — both fixes landed; the first Windows nightly after the merge is the check
Track: The repo's own process
Depends on: —

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
`_project_name` adds `.rex` unless the name already ends in it, case-sensitively, so a name
typed as `Sample.REX` becomes `Sample.REX.rex` on every platform. That is a naming question
rather than a case-insensitive volume's, and it is left as it is.

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

- **2026-11-12** — closed. On Windows, renaming a project from `sample.rex` to `Sample.rex`
  now renames the folder. The person's unapplied edits follow it. Before, the folder kept its
  old name, and on that rename the edits were left where the project could not find them.
  Neither fault reached a release, since the File menu and the recovery copy are both new
  since v1.11. The fix is checked on Windows only by the nightly, so the first Windows
  nightly after the merge is the acceptance. PR #1539.

  *Done.* `project_rename` compares the old and new folder names as text. `recovery.move`
  keys the old copy by the resolved path its caller took before the move, through a new
  `_read_key` that `read` shares. The case-only rename test now writes a draft first and
  checks it follows the folder. A new test makes the old name resolve to the moved folder
  through a symlink, as Windows does, so it runs on every platform.

  *Reproduced?* Not as a failure. The test runs here, because APFS is case-insensitive, and
  it passes on main's code: `pathlib` compares POSIX paths with case, so the rename reaches
  the move. The cause was shown instead: `PureWindowsPath("C:/t/work/sample.rex") ==
  PureWindowsPath("C:/t/work/Sample.rex")` is `True` and the POSIX pair is `False`. The new
  recovery test failed on main's `recovery.py` (`move` returned `False`) and passes on the fix.

  *Measured* (`[dev]`, macOS arm64, main `a86dcf9d4` merged in, other sessions' suites
  queued on the same machine; main `59a4f96ba`, one WP file, merged after). Fast selection: 14 558 passed, 424 skipped, 32 xfailed, plus
  1 failed, the stale WP index, regenerated and green on its rerun (`test_docs_consistency.py`,
  26 passed). One test added, 0.01 s. `tests/test_gui_file_menu.py` and
  `tests/test_gui_recovery.py`: 24 passed. The full selection did not run: the change is GUI
  server code and moves no measured number. `python -m tests.reader_output`: exit 0,
  unchanged. Lint as CI runs it: ruff, format, `skill_caps`, `skill_surface`, `audit_delta`
  all exit 0; Vale 0 errors, 268 warnings, none on a line this WP wrote.

  *Review.* `/code-review high --fix` found no correctness bug. Applied: the shared key
  check, and the draft in the end-to-end test. Declined: normalising `source` inside `move`,
  which would bring back the re-resolve this WP removed; `_relocate` swallowing an `OSError`
  from the move, and the case-sensitive `.rex` suffix test, both older than this WP (the
  suffix is in Context's list of what was not generalised).

  *Generality.* Not dispatched: `_audit.py` untouched, and nothing here reads a pattern.

  *Elsewhere.* WP-2209's `### Inherited` says `move` now keys by the path it is given. The
  nightly of 2026-11-11 was also red on the Linux `full` job, on
  `test_pair_diagnostic_class.py::test_the_two_site_winner_finds_each_site_its_own_moment`
  (0.699 against 3.5 ± 0.01). WP-1418 took that row up in PR #1542; nothing here touches it.

  Next: read the Windows row of the first nightly after #1539 merges. If
  `test_gui_file_menu.py` is still red there, reopen this WP.
- **2026-11-12** — created by the ghostshift runner main-nightly-windows from the nightly's
  red Windows row. No open WP owns it: WP-2133 is closed, and WP-2036's open PR #1425 closes
  that WP.
