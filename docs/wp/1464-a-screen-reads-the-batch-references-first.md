# WP-1464 — a screen reads the batch references first

Milestone: unscheduled · Status: 🔄 2026-11-18 — claimed by @yue-here (ghostshift runner)
Track: A long run is not one fit
Depends on: — (PR #385, merged 2026-09-25: a runaway cell no longer raises in a screen)
Priority: P3 2026-09-25 — the references exist and a reader who finds them is covered; one session waited 78 idle minutes on a screen they describe

## Goal

An agent about to run many independent fits (a candidate-phase screen, a
candidates × patterns grid, a process pool) is routed to the batch references
before it launches, not after the fits are in hand. And those references carry
the two lessons one such screen paid for: a free cell lets an absent candidate
take a present phase's peaks, and a process pool needs its kernel threads
pinned.

### Inherited

Pruned 2026-11-18 at `origin/main` `37bda00b`. Two entries were folded into
Context and Tasks, and one was rewritten for the tree as it stands.

- **2026-10-23, from [1322](1322-events-aggregator.md) (closed): a job of many
  fits is many run directories, and nothing summarises them as one job.**
  Still true on 2026-11-18: `rietx events` (`cli._events`) reads one
  `events.jsonl` or one run directory. A 2026-09-25 transcript review of an
  agent session on `in-situ series 1` found the agent counting fits by hand
  while 887 run directories sat in `.rietx/runs` (843 `done`, 44 `failed`). It
  put its first screen at "about 15 min", where the transcript's timeline says
  89. `runs.discover` lists the runs under a root, `runs.read_run` reads each,
  and `label=` ([1431](1431-a-caller-names-its-run.md)) can give a job's runs
  one name. Whether a job's count, failures, wall and slowest run are a second
  mode of `rietx events` or another verb is a new CLI surface. It is not one of
  this WP's tasks, and the 2026-11-18 session left it open.
- **Superseded in part 2026-11-18: the body's budget.** The 2026-09-28 entry
  from [1338](1338-the-skills-own-gates.md) put `SKILL.md`'s body at 30 509 B
  against a 17 000 B budget. On `37bda00b` it is 16 989 B, so a rewritten
  routing row may grow it by 11 B before a body cut pays for it.
- Folded: the 2026-10-11 issue-triage entry (#898 (b), `OMP_NUM_THREADS`) is
  now part of task 1. Checked 2026-11-18: `model.compiled.n_threads()`
  (`compiled.py:231-247`) still reads only `RIETX_COMPILED_THREADS`.

## Context

**The evidence.** A 2026-09-25 transcript review read a second agent session on
`in-situ series 1` in the private `yue-here/rietx-corpus-map`. Quote only what
the runs did (CONTRIBUTING, WP-1450). The session read `SKILL.md`,
`references/series.md` and `references/api.md`. It never opened `batch.md` or
`batch-operating.md`. It then ran a screen of 204 cold fits (48 patterns × 4
candidate pairs, plus 12 single-phase fits) on 10 worker processes, with every
candidate's cell free.

| | |
|---|---|
| session wall to the report | 136 min |
| the screen's wall | 89 min, 78 of them with the agent idle, waiting |
| slowest job / median job | 4559 s / 54 s |
| jobs that raised | 43 of 204 |

The agent's summary printed `median t per fit nans`, because the failed jobs
carried no time. So it never saw the 4559 s job. Its report puts the screen
at "about 15 min" and blames BLAS threads. `batch-operating.md` §9c.5 already
has the row it needed: budget a job from what a converged job costs, and read
a job past its budget as a diagnosis. That row's factor for independent jobs
is still tagged a hypothesis. This screen is a measured point for it: the one
job at 84× the median was a cell runaway.

**Why the references were missed.** `SKILL.md`'s two §9c routing rows were keyed
by topic (superseded in part 2026-11-18: they have since merged into one row,
"§9c a batch: deciding; operating", still keyed by topic): "§9c, deciding: ranking, differencing, auditing, identifiability" and
"§9c, operating: budget, cost, timing, the log, inventory, fault tolerance".
`batch.md` opens "Load it when a batch's fits are in hand". The rule for a
routing row is to key it by the situation (root CLAUDE.md, the skill). This
situation comes before any fit is in hand.

**Lesson 1: a free cell lets an absent candidate imitate a present phase.**
`batch.md` §9c.2 already says a candidate the data cannot see is unseen, not
refuted. The screen showed that case: on patterns 0 to 3 every candidate that
returned agreed with the others to 0.01 in χ²red. The screen also showed the
other half. A candidate the data can see through a walked cell is not
identified. This review replayed the 204 jobs on main (`6641c8cf`). On one
pattern an absent candidate's cell more than doubled along one axis in the
first Le Bail stage, and it kept a nonzero scale to the end. Later in the
session, a minority candidate lowered χ² while its free cell left its own
template's metrics, and the two directions of the chain disagreed on that cell
by 18σ. The agent's remedy was to bound every candidate's cell near a template
(±1 %, then ±0.3 %). It tested each transition as a pinned two-phase fit
against a free one-phase fit. With ±1 % bounds and no per-pattern presence,
its first chain raised 8 `SEQUENTIAL_PATH_DEPENDENT`. The final protocol
raised none. The bound width is specific to this series, whose candidates'
subcells differ by little. The general form is a hypothesis: bound tighter
than the smallest metric difference between candidates.

**Lesson 2: threads in a process pool, not yet measured.** The compiled tier
takes `model.compiled.n_threads()` threads per process, min(8, cores) unless
`RIETX_COMPILED_THREADS` is set (`_about.py`). The skill named that variable
nowhere (superseded in part 2026-11-18: `batch-operating.md` 9c.33, from
WP-1325, now advises `RIETX_COMPILED_THREADS=1` per process and tags the
one-thread pool a hypothesis that no batch has measured). A 10-worker pool can therefore run up to 80 kernel threads, plus BLAS.
The agent saw a load of about 25 on 10 cores and pinned only the BLAS
variables. Its later screens took 0.7 to 2.7 min, but those also changed the
cell bounds, so they do not isolate the threads. Measure on a quiet machine
before writing the row. The 2026-09-25 attempt found the desktop at load 159
from another session's suite.

**The runaway is not this WP's, and the clamp does not remove lesson 1.** The
43 raises, and the 4559 s job whose returned cell had grown about 70× along one
axis, are issue #374. PR #385's post-stage clamp addresses them. This review
replayed the 204 jobs on main (`6641c8cf`) and on main merged with #385, with
one kernel thread per worker:

| | main | main + #385 |
|---|---|---|
| jobs that raised | 30 | 1 (a 300 s budget stop, machine at load ~150) |
| a length ≤ 0 or an angle outside (0°, 180°) | 59 | 0 |
| a length moved > 50 % from its CIF start | 66 | 12 |
| a length moved > 15 % from its CIF start | 75 | 72 |
| `CELL_RUNAWAY` fired | — | 46 |

With the clamp, 31 results still moved a length more than 15 %, up to 80 %,
with no `CELL_RUNAWAY`. That fits a clamp anchored at each stage's start over
the nine stages of a job. So the clamp keeps a screen's cells physical, and a
candidate can still walk far enough to take another phase's peaks. Lesson 1
stands with or without #385.

## Non-goals

- The cell clamp itself (PR #385).
- A package-level presence screen or a per-pattern phase list. WP-1420 owns
  that question, and this session's answer is in its Inherited.

## Tasks

- [x] Measure lesson 2 on a quiet machine: one screen-shaped job set under a
      10-worker pool, with `RIETX_COMPILED_THREADS` unset and set to 1, BLAS
      pinned in both, repeated. Quote walls as ranges. If the gap is large,
      decide whether a pool worker should default to one thread (prior art:
      joblib's loky backend limits its workers' inner threads; read how).
      Decide with it whether `n_threads()` falls back to `OMP_NUM_THREADS`
      (numexpr reads `NUMEXPR_NUM_THREADS`, then `OMP_NUM_THREADS`).
- [x] Re-key the two §9c routing rows by situation, and make `batch.md`'s
      "Load it when" name a screen before its fits. No new body line: a
      rewritten row costs no cap.
- [x] `batch.md`: the imitation row beside §9c.2, tagged
      `(Measured: in-situ series 1, second session)` for the evidence and
      `(Hypothesis: …)` for the width rule.
- [x] `batch-operating.md`: the threads row with lesson 2's numbers. And
      §9c.5 gains this screen as a measured point (one job at 84× the median,
      a cell runaway) and "time the failed jobs too", from the `nan` median
      above.
- [x] Re-sync the committed copies (`rietx skill --install . --copy`).

## Acceptance

The routing rows name the situation, and the two new rows carry tags that
`tests/test_skill.py` accepts.

```sh
.venv/bin/python -m pytest tests/test_skill.py tests/test_skill_cli.py tests/test_docs_consistency.py -q
.venv/bin/python -m ruff check src tests examples
```

## References

- `docs/skill/rietx/references/batch.md` §9c.2, `batch-operating.md`,
  CONTRIBUTING § the agent skill (private-corpus tags).
- Issue #374, PR #385 (the runaway).

## Handover log

- **2026-09-25** — created by a transcript review of a second agent session on
  `in-situ series 1`. The screen's numbers are from that session's timeline and
  `screen.json`. The imitation case is from this review's replay on main.
  Next: the thread measurement, on a quiet machine.
