# WP-2031 — a history log holds one tree, and a stage is timed in one place

Milestone: unscheduled · Status: ✅ 2026-11-03 — a reused history path is refused, a doubled old log loads its last tree (ruled by Yue), one stage timer; PR #1358
Track: Render what the fit already knows
Depends on: — (1322 soft, closed: the event log's run header is the precedent)

## Goal

A second `Refinement(..., history=path)` on a path that already holds a tree
either refuses or starts a tree the reader can tell apart. A stage's elapsed
time is computed by one helper that both the aggregator and the progress line
call.

## Context

- **A reused `history=` path breaks the log the way a reused `events=` path once
  did.** WP-1986 found it on 2026-10-20, measuring on the fluorapatite example.
  Two `Refinement(..., history="fit.jsonl")` runs on one existing path append a
  second header and restart node ids at `n0000`. `RefinementTree.load` then
  reports 4 nodes where its dict holds 2, and its summary draws `n0001` twice.
  The cause, still true at `3e0dc6f`: `RefinementTree.for_data` appends a header
  to any path (`history/tree.py`; the call at `refine.py:2121`), and `load` adds
  every node record to `order`. Meanwhile `docs/docs/reference/history.md`
  tells the reader to load the log and continue with `Refinement.from_node`.
- **The event log already solved the same case** (WP-1322, PR #902). Each opened
  `EventStream` starts with a `record: "run"` header line, and the reader splits
  on it. The file stays in append mode because a series writes every pattern
  into one log and `rietx watch` tails it. A history log needs the same split,
  or a refusal of a path that already holds a tree. Which one is this WP's
  first decision. A refusal is simpler. A series already keeps one tree per
  file (`sequential.py:1902`, `_history_spec`, WP-1051), so a refusal costs it
  nothing on a first run. But a series rerun into the same directory reuses
  every `<label>.jsonl`, and the decision must say what that rerun does.
- **The stage-timing rule lives twice.** `history.aggregate` and
  `events.progress_writer` each time a stage from the first `stage_start` of
  its name to its `stage_end`. The aggregator clears its open stages at each
  `fit_start` (`history/aggregate.py:185`). `progress_writer` does not
  (`history/events.py:326-350`). So a stage that started and never ended
  leaves its start behind, and the next `stage_end` of the same name reports
  the time since then. One writer serves a whole series
  (`sequential.py:1252`), so the stale start can cross patterns. The
  fix is one shared helper that both call. This was noted as not done in
  1322's 2026-10-12 handover, and no run has reproduced it yet.
- **Tier.** Nothing here is a heuristic. A refusal or a split is a file-format
  rule, and the timing helper is bookkeeping. No `_audit` row is expected.

## Non-goals

- Rebuilding a tree from two interleaved runs' records. A reader that splits
  on a header reads each run alone.
- The joint fit's history (it keeps none; `multi.py`).

## Tasks

- [x] Reproduce the doubled node on a reused `history=` path in a test, then
      refuse or split (decide, and record why here). `load` and the summary
      agree on the node count either way.
      **Decided: refuse** (settled by Claude under the history store's written
      format and its one-writer rule, `history/store.py`'s docstring: one
      header, then that tree's records, one writer per file; and under
      `Project.create`'s precedent, which refuses a directory already holding a
      `project.json` with `FileExistsError`). A split would make one file hold
      several trees, and `RefinementTree.load` returns one, so it would need a
      new way to say which. An overwrite would delete evidence, which the
      retention rule forbids. Three places now refuse.
      `Refinement(..., history=path)` raises `FileExistsError` naming the path
      at construction, before a fit is paid for. `RefinementTree.for_data` asks
      again when the tree is made, for a file written in between. An empty or
      blank file holds no tree and is used. **A series rerun into the same
      directory is refused before its first fit**
      (`SequentialRefinement._refuse_a_reused_history`), over `<label>.jsonl`
      and every rung's `<label>.<suffix>.jsonl`. Pattern by pattern, a rung's
      log would have raised mid-chain, since it exists only where the earlier
      run escalated. **A log a release before this WP doubled loads its last
      tree** (ruled by Yue 2026-11-03, under "old files must always open"),
      and each earlier tree is reported as `HISTORY_EARLIER_TREE_SKIPPED` on
      `load`'s `diagnostics=` list with its line range. Reading it as one tree
      reported nodes neither run committed. Tests: `test_history.py`
      (`…reused_history_path_is_refused…`, `…empty_history_file…`,
      `…two_trees_loads_the_last…`) and `test_sequential.py`
      (`…rerun_into_a_used_history_directory…`).
- [x] One stage-timing helper, called by `history.aggregate` and
      `events.progress_writer`. A test whose stage starts and never ends
      shows that the next same-named stage is timed from its own start.
      `history.events.StageClock`: a stage's `stage_start` to its
      `stage_end`. A release's second `stage_start` (it carries `released`)
      keeps the first start, and any other `stage_start` replaces an open one
      of its name, since `Refinement.run_stage` emits no `fit_start` (found by
      the handover's review). Every `fit_start` still forgets the open
      starts. The aggregator's test
      (`test_a_stage_that_raised_does_not_lend_its_start_to_the_next_fit`) now
      feeds the same log to `progress_writer` and asserts `2s` from both. The
      pre-WP writer printed `102s` on that log, timed from the dead start
      (checked by running the old function on it).
- [x] `docs/docs/reference/history.md`: replace the workaround with the rule.
      Also one sentence each in `guides/branch.md` and `reference/series.md`,
      and the `Refinement` and `SequentialRefinement` docstrings.
      (`reference/series.md`'s sentence came back out at the close: main's
      growth put that page 84 characters over the manual's 50 000-character
      page cap, and `reference/history.md` already states the series rule.)
- [x] Skill: a row only if the refusal raises something an agent meets;
      otherwise "none" and why.
      **None.** An agent does meet it: the skill's canonical loop
      (`references/history.md`) passes `history="session.jsonl"`, and a rerun
      of that script raises. But the message names both ways on (load and
      `Refinement.from_node`, or another path), and the package's own output is
      the cheapest place that holds the guidance (WP-1338). The error is a
      `FileExistsError`, not a diagnostic code. The ruling's new code,
      `HISTORY_EARLIER_TREE_SKIPPED`, has its row in §7i
      (`references/diagnostics-reading.md`), beside the history reader's other
      codes.

## Acceptance

- Two fits on one `history=` path either raise, naming the path, or load as
  two trees, each with its own node count.
- The aggregator and the progress line report the same elapsed time for every
  stage of a log in which one stage never ends.

```sh
.venv/bin/python -m pytest tests/test_history*.py tests/test_events*.py -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1322 (the event log's run header, PR #902); WP-1986's 2026-10-20 note.

## Handover log

### 2026-11-03 (2nd session) — the ruling carried out; the WP closes

An old history file that a rerun doubled now opens again. Before this PR it
read as one tree with every node id twice. The PR's first landing made it
raise, so the user had to split the file by hand. Now the file loads its most
recent run and warns once for each earlier run it skipped, giving the lines
that hold it and how many nodes it has. Nothing in the file is deleted, and
the warning says how to read a skipped run. A new run on a used path is still
refused, since that is a new write and not an old file.

*Ruled by Yue 2026-11-03:* a history log an older release already doubled
must load, not raise, under the standing rule that old files must always
open. Build: load the last tree, report the earlier ones under a new warning
code on `load`'s `diagnostics=` list.

*Done.* `RefinementTree.load` keeps the last header's records and emits one
`HISTORY_EARLIER_TREE_SKIPPED` (warning, `value` = the skipped tree's node
count) per earlier tree, before the declared-range and twin notes. `load`
already had the `diagnostics=` channel (WP-1321), so none was added.
`help.py` entry; `_audit.py` code and suggestion rows at tier 1 (none enters
at `unaudited`); a silence pair in `tests/silence.py`; a §7i skill row, copies
re-synced; `reference/history.md`; the `Project.history_diagnostics` comment;
an inherited note in WP-1522 (the GUI shows that list). The GUI help-key
fixture gained the code.

*Settled by Claude.* (1) The **last** tree, as the ruling proposed, kept on
the store's own grounds: it only appends, so a node committed on the loaded
tree lands at the end of the file, inside the last tree. Loading any other
tree would put the next commit in a tree that was not loaded. The test commits
on the loaded tree and reloads it. (2) The history reader's codes file under
the manual's **Reading files** diagnostics page, not Refinement
(`docs/reference_pages.DIAGNOSTIC_GROUPS` gains `rietx/history/`). Grounds:
the page contract's 50 000-character cap, which the Refinement page's twin
passed by 594 characters with the new entry, and the code is a file reader's.
This is the only code raised there. (3) `reference/series.md` drops its
sentence on the series refusal, under the same cap (main's growth put the
page 84 over); `reference/history.md` already states it. (4) The code's
name follows `CIF_EMPTY_BLOCK_SKIPPED` and `TOPAS_BLOCK_SKIPPED`.

*What a reader receives* (text approved by Yue 2026-11-03). On a
real doubled log of two four-node fits:

```text
warning[HISTORY_EARLIER_TREE_SKIPPED]: <dir>/session.jsonl holds 2 trees; loaded the last, from line 6, and skipped the tree at lines 1-5 (4 nodes, recorded 2026-11-03T10:15:35Z).
  help: To read the skipped tree, copy lines 1-5 into a file of their own and load that file with RefinementTree.load.
```

Its explanation (`help.py`, also the manual's entry): title "Earlier tree in
a history file skipped"; "A history file holds one refinement's tree.
Releases before 1.11 appended a second refinement to a reused history file,
so an old file can hold two or more trees. Loading it returns the last tree,
the most recent run, and skips each earlier one. A refinement continued from
the loaded tree adds its nodes to the last tree. Nothing was deleted, and the
skipped tree's lines are still in the file." A fit prints and returns the
same: `tests.reader_output` unchanged against `cef9aef7c`.

*Measured* (`[dev]` venv, darwin/arm64, another shift on the machine):
`test_history`, `test_silence`, `test_gui_help`, `test_docs_consistency`,
`test_help`, `test_audit_table`, `test_manual_api`, `test_project`,
`test_skill`, `test_skill_claims`, `test_skill_surface`, `test_manual`,
`test_gui_manual`, `-m "not slow"`: 501 passed. `tests.audit_delta`: 2 added,
0 new at `unaudited`. Ruff clean. The fast selection is CI's gate.

*Generality* (`generality-review` agent, unedited verdict lines):
`HISTORY_EARLIER_TREE_SKIPPED` (code) **holds**. "A file the store only
appends to admits one self-consistent tree to load, and the action deletes
nothing, rewrites nothing and is reported." Its one case against: an old
script that crashed after writing a header and before its first commit leaves
an empty last tree, while the earlier tree holds the work. The warning's node
count makes that visible, and every alternative puts the next commit in a
tree that was not loaded. `HISTORY_EARLIER_TREE_SKIPPED.suggestion`
**holds**: "the test runs that recipe and recovers the skipped tree exactly."

Next: none. WP-1522 inherits showing the code in the GUI.

- **2026-11-03** — all four tasks landed (PR #1358, ghostshift runner). A
  history file now holds one refinement's tree. Running a second refinement
  onto a file that already holds one stops at once with an error naming the
  file and the two ways on: continue it, or use another path. Before, the
  second run was silently appended, and reloading the file reported each
  node twice. A series rerun into the same directory stops before its first
  fit, so it cannot fail halfway through on a retry's log. The progress line
  and the event summary now time a stage by one shared rule, so a stage that
  crashed no longer inflates the next stage of the same name. One ruling is
  owed (below): what a file an older release already doubled should do on
  load.

  *Done.* Refusal in `store.refuse_existing_log`, asked by the `Refinement`
  constructor, `RefinementTree.for_data`,
  `SequentialRefinement._refuse_a_reused_history` (exact names: label, pass
  suffix, rung suffix) and `Project.create` (a directory a failed create left
  a `history.jsonl` in). `RefinementTree.load` raises on a second header,
  naming the file and line. `history.events.StageClock` serves
  `summarize_events` and `progress_writer`. Manual: `reference/history.md`,
  `guides/branch.md`, `reference/series.md`. `READ_POINTS` names
  `store.read_numbered_records`, where the migration now runs.

  *Review* (`/code-review high --fix`, 8 findings). Applied three:
  `run_stage` emits no `fit_start`, so a non-release `stage_start` now
  replaces an open start of its name (a release's carries `released` and
  keeps the first); the series check builds exact names, where a
  `<label>.` prefix refused another series' `run1.2.jsonl`; a non-UTF-8 file
  is refused like any other. Applied a fourth here: the `Project.create`
  sibling. Declined two. `RefinementTree.save(path)` still rewrites a path
  that holds another tree, because `save` is the explicit rewrite verb and
  its docstring says so. The `READ_POINTS` wording was fixed rather than
  declined. Left open one: doubled old logs, below.

  *Measured* (`[dev]` venv, darwin/arm64, another shift's runners on the
  machine): the fast selection did not run locally. It queued an hour behind another tree's slow suite and three other waiters, so CI's fast matrix is its gate. The eleven touched test files on the final tree (`test_history`, `test_events_aggregator`, `test_events_viz_history`, `test_progress`, `test_sequential`, `test_project`, `test_extra_components`, `test_site_twins_merged`, `test_params_surface`, `test_named_variables`, `test_docs_consistency`, `-m "not slow"`): 642 passed. The manual's three suites (`test_manual_api`, `test_manual`, `test_docs_consistency`) 107 passed before the review fixes. WP acceptance selection
  (`test_history*.py test_events*.py`) 78 passed before the review fixes.
  `tests.reader_output`: unchanged against `62724a30f`. The change alters
  what three calls raise, never what a fit prints or returns.
  The five added tests cost 0.98 s together on this machine, the largest 0.49 s (`test_a_reused_history_path_is_refused…`), so none joins the fast tier's tail.

  *Generality.* Not dispatched. The branch does not touch `_audit.py`, and a
  refusal of a reused path and a stage timer are a file-format rule and
  bookkeeping, as the WP's tier line says.

  *Open, for the maintainer.* **A log an older release doubled now raises on
  `RefinementTree.load`.** Such a file exists wherever a script was rerun on
  one `history=` path, the skill's canonical loop included. Before this
  branch it loaded as one tree holding each id twice, with HEAD in the last
  run. Two ways: (a) as landed, raise `ValueError` naming the file and the
  second header's line, so the user splits the file by hand; (b) load the
  last tree and report the earlier ones through `load`'s `diagnostics=`
  channel, under a new warning code. (b) keeps old files opening (the
  memory index's "old files must always open") and follows the package's
  read-and-report practice for old files (`DECLARED_RANGE_RESTORED`). It
  costs a new reader-facing code: an `_audit` row, a `help.py` entry, a
  silence pair, a skill row and a note in WP-1522. (a) is what landed
  because the code's text and name are reader output, which comes to the
  maintainer before it is written.

  Next: the ruling on (a) or (b). Under (b), add the code and note WP-1522
  (the GUI shows the history reader's diagnostics); then close.

- **2026-10-23** — created by WP-1322's close. No open WP owns either item.
  1986 (🔄) found the history defect but moves the manual, not code. 1522 (⬜)
  shows the history reader's diagnostics in the GUI and changes no reader.
  1947 (⬜) keeps reporting verbs from writing history. 1317 (🔄) reads
  `SeriesResult`, not the event stream. 1949 (⬜) is about `eval` events.
