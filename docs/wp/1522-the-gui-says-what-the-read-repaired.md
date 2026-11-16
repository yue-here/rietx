# WP-1522 — the GUI says what reading the project repaired

Milestone: unscheduled · Status: 🔄 2026-11-16 — server half in #1616; the panel and its manual chapter wait for the frontend rebuild (WPs 2202, 2216)
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

- [x] The route that opens a project carries both lists, as `Diagnostic`
      dumps, and `test_gui_manual.py`'s route partition is kept whole.
      (2026-11-16: on `project_doc`, so `GET /api/project` after a reload
      says it too; no route added, so the partition is unchanged.)
- [ ] A panel or the existing diagnostics surface shows them on open,
      warning level first, with the code, the message and the `where`.
- [x] Tests: a project whose log predates schema 0.35 (the aging helper in
      `tests/test_project.py`) opens in the server with both codes reported.
      (`test_open_says_what_the_readers_repaired`: a reversed scan plus a log
      aged to 0.16, `DECLARED_RANGE_RESTORED` and `_NOT_RESTORED`.)
- [ ] Manual: `using/gui-guide.md` (or the chapter the panel belongs to).
      (2026-11-16: the route half is in `reference/gui-power.md`'s project
      row; the panel's chapter goes with the panel.)
- [x] Skill: none expected (an agent reads the lists off `Project`), say so.
      (2026-11-16: none; the change is a GUI wire field, no agent verb.)

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

- **2026-11-16** — The GUI server now hands over what reading a project
  repaired: a reversed scan, a declared range restored to an old log, or one
  left off because a stored value lies outside it now reaches the browser
  with every open and every reload, where before it stopped in memory on the
  server. Nothing on screen shows it yet: the panel is the frontend's, and
  the frontend is being rebuilt under the maintainer's claims on WPs 2202 and
  2216, so this session (a ghostshift runner) touched no `gui/src`. Server
  half in PR #1616.
  - *Premise checked* against `origin/main` `bc77a934e`: `project_open` and
    `project_doc` dropped both lists, as filed.
  - *Done:* `project_doc` carries `data_diagnostics` and
    `history_diagnostics` as `Diagnostic` dumps in the readers' order (the
    ordering, warning first, is the panel's job). On the document rather
    than on the open route's answer alone, so `GET /api/project` after a
    reload says the same; create, rename and move return it too (rename and
    move keep the same `Project`, so the lists carry over). No route added,
    so `test_gui_manual.py`'s partition is untouched. The project row of
    `docs/docs/reference/gui-power.md` names both fields.
  - *Test:* `test_open_says_what_the_readers_repaired` opens a clean project
    (both lists empty), then a reversed-scan copy whose log is aged to schema
    0.16 with a bare phase scale and an occupancy of -2.0: one
    `PATTERN_SCAN_REVERSED`, `DECLARED_RANGE_RESTORED` on `phases.0.scale`,
    `DECLARED_RANGE_NOT_RESTORED` on `phases.0.atoms.1.occ`. Aged to 0.34
    the occupancy is a choice and is not reported (`Atom` inherited at 0.17),
    so 0.16 is what puts both codes in one log. Made to fail once by emptying
    the history list (`assert set() == …`).
  - *Measured* (Mac arm64, worktree `.venv` `[dev]`): `test_gui_server.py`
    188 passed, `test_gui_manual.py` 10 passed, `test_audit_table.py` 23
    passed, serial; ruff clean. Workstation canary (5 files, `-n 4`): 284 passed.
    Fast suite: the workstation lost it twice to memory pressure; rerun on the Mac (in flight at pause, 18:07Z).
  - *Review:* a read-only review agent found nothing (callers of
    `project_doc`, non-finite `value` through the server's JSON writer, no
    key-set assertion on the document in tests or `gui/src`).
  - *Reader output:* `python -m tests.reader_output` exit 0, unchanged.
  - *Generality:* no row, threshold, default or action added; the judge was
    not dispatched.
  - *Next:* the panel task and the manual chapter, in the rebuilt frontend
    once WPs 2202/2216 land: read `data_diagnostics` and
    `history_diagnostics` off the project document on open, warning first,
    with code, message and `where`, then the chapter that panel belongs to.
- **2026-09-29** — filed from WP-1321's review; no code touched.
