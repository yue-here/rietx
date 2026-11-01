# WP-2031 — a history log holds one tree, and a stage is timed in one place

Milestone: unscheduled · Status: ⬜
Track: Render what the fit already knows
Depends on: — (1322 soft, closed: the event log's run header is the precedent)
Priority: P3 2026-10-23 — a wrong node count and a doubled node on a reused path, with a documented workaround (load the log and continue with `Refinement.from_node`)

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

- [ ] Reproduce the doubled node on a reused `history=` path in a test, then
      refuse or split (decide, and record why here). `load` and the summary
      agree on the node count either way.
- [ ] One stage-timing helper, called by `history.aggregate` and
      `events.progress_writer`. A test whose stage starts and never ends
      shows that the next same-named stage is timed from its own start.
- [ ] `docs/docs/reference/history.md`: replace the workaround with the rule.
- [ ] Skill: a row only if the refusal raises something an agent meets;
      otherwise "none" and why.

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

- **2026-10-23** — created by WP-1322's close. No open WP owns either item.
  1986 (🔄) found the history defect but moves the manual, not code. 1522 (⬜)
  shows the history reader's diagnostics in the GUI and changes no reader.
  1947 (⬜) keeps reporting verbs from writing history. 1317 (🔄) reads
  `SeriesResult`, not the event stream. 1949 (⬜) is about `eval` events.
