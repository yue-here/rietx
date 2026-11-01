# WP-1322 — the run is instrumentable, and nothing says so

Milestone: unscheduled · Status: ✅ 2026-10-23 — `rietx events` reads an event log run by run, every opened log starts with a run header, and the skill says how to keep a run record (PR #902)
Track: Render what the fit already knows
Depends on: —

## Goal

The telemetry the package already emits becomes legible without a GUI — a
post-hoc aggregator over an `events.jsonl`, sibling to `watch` and `html` —
and becomes discoverable, so the next agent that drives a series does not
switch it off. The defaults asymmetry that made switching it off the
accidental norm is decided, either way, on the record.

## Context

From issue #207 (the 2026-09-01 benchmarking campaign; the contributor has
offered the aggregator as a PR).

**The finding.** Three independent subagents, each given a benchmarking
task and no instructions about how to drive rietx, all found and read the
packaged skill in full by three different routes — and **all three wrote
`history=False`**, five occurrences, on both `Refinement` and
`SequentialRefinement`. No event log existed afterwards; reconstructing
timing from the agents' own transcripts recovered **2.7–16.6 %** coverage
and nothing inside a solve. One instrumented fit
(`EventStream(path=…)` + `stage_reports=True`) emitted 288 records —
`fit_start`, 7× `stage_start`, 274× `eval`, 5× `stage_end`, `fit_end` —
with `stage_end` carrying `termination` and `held`/`released`: strictly
better than anything external instrumentation can recover.

**Two causes, both cheap.** (1) The defaults are asymmetric and the
asymmetry is deliberate: `Refinement.history` defaults `True`
(`refine.py`), `SequentialRefinement.history` defaults `False`
(`sequential.py` — "a long series makes a lot of files", a documented
reason). (2) Nothing in the skill's fitting path says the run is
instrumentable: the series and judging references teach what to check in a
result and never mention `events=`, `history=` or `stage_reports=`.

**Task 1 — `rietx events <log.jsonl> [--json]`.** Dependency-free,
consuming only rietx's own format through the existing primitives
(`read_events`/`read_records`, today consumed only by `history/tree.py`).
Reports: fits and stages counted, wall-clock total and per stage name, a
histogram of `termination` values, the most frequently `held` parameter
paths, first/last Rwp. On the campaign's runs the per-stage timing showed
one stage dominating a whole series, and the held-path histogram was a
faster route to "the data cannot see this phase" than reading per-pattern
reports. The contributor asked for the shape rather than guessing: this WP
records it — a CLI subcommand sibling of `watch`/`html`, thin over a plain
function in `rietx.history` so a CI job can call either. If the offered PR
arrives, this WP becomes its review against that spec plus the two
rietx-side tasks below.

**Task 2 — the defaults decision. DISCHARGED 2026-09-15 (WP-1406), by
removal of its premise, and neither flipped nor deferred.** The task was to
decide which knob to flip so that an agent would have a log. WP-1403 shipped
2026-09-15 and every fit now writes a run directory whether or not `history` or
`events=` was passed, so no defaults asymmetry decides coverage any more. The
asymmetry itself survives, `Refinement.history` defaulting `True` and
`SequentialRefinement.history` `False`, and it is now a question about history
nodes alone rather than about whether a run leaves a record.

Nothing was flipped, so there is no behaviour change and nothing to release-note.
Its original text, for anyone reopening it: flip `SequentialRefinement.history`
to match `Refinement`'s, or keep it and make the skill carry the asymmetry out
loud, decided against the 3/3 evidence and the documented disk-cost reason.

**Task 3 — the skill line.** `references/series.md` (all committed copies)
gains the sentence the campaign says would have saved the reconstruction:
pass `history=<path>`/`events=EventStream(path)` when you need a run
record; `stage_end` carries the termination criterion.

**One vocabulary, shared with 1317.** Issue #133's scrubber is the
interactive consumer of the same substrate ("same substrate, different
consumer" — #207's own framing): the aggregator's `termination` histogram
and held-path counts summarise exactly the marker vocabulary 1317 reads
from `SeriesResult`, so neither surface invents a second set of names.

**How a log splits, and how its events pair.** `EventStream` still opens its
file in append mode, because a series writes every pattern into one log and
`rietx watch` tails the file. So PR #902 starts each opened stream with a
`record: "run"` header line and the reader splits on it. A header is not an
event kind, but a version-2 reader refuses the line, so `EVENT_SCHEMA_VERSION`
went to 3. Within a run, events pair in file order, never by
`(series_index, series_pass)`, which recur on reseeds and restarted segments.

## Non-goals

- **Not the interactive scrubber** — [1317](1317-series-scrubber.md)'s.
- **Not transcript/token attribution** — harness-specific, stays with the
  campaign (the issue offers only the half that consumes rietx's format).
- **Not a new event kind or schema field** — `EventKind` stays closed; the
  aggregator reads what is already written.
- **Not live viewing** — `rietx watch` owns the running case.

## Tasks

- [x] The aggregator: a plain function in `rietx.history` + the
      `rietx events <log.jsonl> [--json]` subcommand over it; fixture logs
      from the package's own emitters, never hand-written JSONL.
- [x] ~~The defaults decision on `SequentialRefinement.history`~~ —
      **discharged 2026-09-15 by WP-1406**, premise removed by WP-1403. Nothing
      flipped, nothing to release-note. See Task 2 above.
- [x] The skill `series.md` instrumentation line (all committed copies
      re-synced via `rietx skill --install . --copy`).
- [x] CLI docs/manual coverage per the standing partition gates
      (`tests/test_manual_api.py`, the CLI chapter) + tests per item.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_events_aggregator.py   # new module, this WP's
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The bar: on a fixture series log the aggregator's counts reconcile exactly
with the emitting run's own records (stages, terminations, held paths,
wall-clock within the events' own timestamps); `--json` round-trips; the
skill line ships in every committed copy.

The shipping PR carries `Closes #207`.

## References

- Issue #207 — the 3/3 finding, the 288-record example, the offer and its
  deliberate fence.
- [1317](1317-series-scrubber.md) — the interactive sibling and the
  one-vocabulary rule; [1305](1305-series-deliverable.md) — the series
  answer both read.
- `history/events.py`, `history/tree.py` — the emitters and today's only
  consumer.

## Handover log

### 2026-10-23 — closed: an event log reads run by run

An agent or a CI job can now ask what a run did after the fact, from its event
log alone, and a log that several runs appended to no longer mixes their times.
Everything this WP asked for landed from outside in PR #902 on 2026-10-12. The
maintainer closed it today, which discharges "closing waits on the maintainer".

- *Closed by* PR #902 (`daca33e5`): tasks 1, 3 and 4, as the 2026-10-12 entry
  checked them. WP-1403 discharged task 2 on 2026-09-15. No box was open.
- *Inherited, deleted as discharged:* 2026-10-11 (#902 was that open PR, now
  merged); 2026-09-24 (`batch-operating.md` § 9c.13 already reads a re-used log
  per run); the WP-1403 and WP-1401 entries (task 2's premise is gone, task 1
  shipped, and the aggregator reads through `runs.tail_events` as 1401 asked);
  2026-09-03 (the run header is #902's fix; why append stays is now in Context).
- *Inherited, forwarded:* 2026-09-25 (one job's many run directories) → 1464,
  which edits `batch-operating.md`; 2026-10-15's per-equation line for a joint
  fit → 1325, its pairing rule kept in Context.
- *Inherited, filed:* 2026-10-20's reused `history=` path → new
  [2031](2031-a-history-log-holds-one-tree.md). Still true at `3e0dc6f`:
  `RefinementTree.for_data` appends a header to any path, and `load` adds every
  node record to `order`.
- *The 2026-10-12 "Not done":* `docs/releases/1.8.0.md` now has both lines. The
  stage-timing rule still lives twice, and `progress_writer` still keeps a
  stage's first start across a `fit_start` (`events.py:326-350`), with one
  writer for a whole series (`sequential.py:1252`). → 2031, beside the
  history log.

*Next.* Nothing owed here. 1464, 1325 and 2031 hold what this WP leaves.

- **2026-10-12** — PR #902 merged from outside as `daca33e5` and closed #207
  and #223. An `events.jsonl` can now be read per run without a GUI:
  `rietx.history.summarize_events` and `rietx events <log | run dir> [--json]`
  print each run's fits, stages, evaluations, Rwp, terminations and most-held
  paths. A log that several runs appended to splits on a header line every
  opened stream now writes, so no duration crosses from one run into the next.
  - *Done.* All three open tasks, each checked against its wording. The
    acceptance bar holds: the fixtures come from the package's own emitters,
    `--json` round-trips (`test_rietx_events_prints_per_run_and_json_round_trips`),
    the skill line is in all three copies, `cli.md` has the chapter, and the PR
    carried `Closes #207`.
  - *Gated* on a four-PR stack, #902, #904, #871 and #880, replayed onto main
    `f22e9a7c` (stack `0e4b7e25`, macOS arm64, `[dev,jax]`). Fast suite: 9274
    passed, 113 skipped, 2 xfailed. Whole slow suite: 306 passed, 12 skipped.
    Sphinx `-W` clean. After the four merges, main `f47c728e` is
    content-identical to the gated tree.
  - *Gotchas.* `EVENT_SCHEMA_VERSION` is 3: a v2 `EventRecord` reader refuses
    the header line, which `compatibility.md` says. The header carries
    `EventStream.header_id`, a fresh id per opened stream. It is **not** the id
    `rietx watch` lists a run directory under (`runs.run_id_for`), and `cli.md`
    says so. A callback-only stream and each `_SeriesStream` have
    `header_id = None`. The split assumes one writer per file.
  - *Not done.* The stage-timing rule lives twice, in `history.aggregate` and
    `events.progress_writer`, and the second copy still keeps a dead stage's
    start across a `fit_start`. `docs/releases/1.8.0.md` has no line for
    `rietx events` or the schema bump.
  - *Next:* the maintainer closes the WP, or files the shared timing helper.

- **2026-09-01** — created, from issue #207 (2026-09-01 triage, second
  batch). Settled: CLI subcommand thin over a `rietx.history` function;
  fixtures from the real emitters; the defaults question is a decision to
  take in-WP, not a bug. If the contributor's PR lands first, start from
  the review.
