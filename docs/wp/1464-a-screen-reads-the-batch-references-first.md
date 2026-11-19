# WP-1464 — a screen reads the batch references first

Milestone: unscheduled · Status: 🔄 2026-11-19 — claimed by @yue-here (ghostshift runner): task 6, the `rietx runs` verb; tasks 1-5 merged in PR #1681
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
  mode of `rietx events` or another verb is a new CLI surface, now task 6.
- **Superseded in part 2026-11-18: the body's budget.** The 2026-09-28 entry
  from [1338](1338-the-skills-own-gates.md) put `SKILL.md`'s body at 30 509 B
  against a 17 000 B budget. On `37bda00b` it is 16 989 B, so a rewritten
  routing row may grow it by 11 B before a body cut pays for it.
- Folded: the 2026-10-11 issue-triage entry (#898 (b), `OMP_NUM_THREADS`) is
  now part of task 1. Checked 2026-11-18: `model.compiled.n_threads()`
  (`compiled.py:231-247`) still reads only `RIETX_COMPILED_THREADS`.
  Still open from that entry: `os.cpu_count()` ignores CPU affinity and
  cgroup limits (inferred), so a job allowed four cores on a large node starts
  `min(8, node cores)` kernel threads per process. `os.process_cpu_count()`
  (Python 3.13+) reads affinity. No run limited that way was measured, and the
  2026-11-18 session changed nothing here.

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
- [x] From Inherited (2026-11-18): decide whether a job's count, failures,
      wall and slowest run are a second mode of `rietx events` or another
      verb, and name the answer in `batch-operating.md`. A new CLI surface,
      so the name goes to the maintainer.
      **Decided 2026-11-19 by Yue: (b), a new verb, `rietx runs [root]
      [--label NAME] [--json]`**, over (a) a second mode of `rietx events`
      and (c) Python only. A person checks an overnight batch from the
      shell; the verb names what it points at, `.rietx/runs`, and `runs.py`
      already uses the word; (a) would branch on what a directory holds.
      The verb is a thin printer over `runs.job_summary(root, label=None)`,
      built on `runs.discover` and `runs.read_run`; the ratio to the median
      is displayed and gates nothing.

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

### 2026-11-18 — tasks 1-5, PR #1681

An agent about to run a screen of candidate fits is now sent to the batch
references before it launches. Those references now carry both lessons, and one
of them turned out the other way round. Pinning rietx's kernel pool to one
thread per worker, which the skill advised, made a 10-worker screen about twice
as slow, so the advice is reversed and the package keeps its default. The
imitation lesson reproduces on public data: on the CPD zincite pattern an
absent fluorite candidate shrank its cell 10.8 %, too little for any code to
fire, and took 14 ± 12 wt %. A ±1 % cell bound did not stop it.

*Done.*
- Task 2: `SKILL.md`'s one §9c row (the two rows had merged since 2026-09-25)
  now reads "§9c a screen or pool of fits, before launch". It grew the body by
  11 B to exactly its 17 000 B budget. `batch.md`'s first line now says to load
  it before a screen and again once the fits are in hand.
- Task 3: `batch.md` 9c.35, the imitation row. It sits at the file's end,
  because `test_skill.py` requires row numbers to increase, and 9c.2 now ends
  with a pointer to it. Its tag opens `Measured: WP-1464` and names in-situ
  series 1 inside: the corpus gate admits a `Measured` tag only when it opens
  with `WP-` or the file's declared corpus, and the task's suggested
  `(Measured: in-situ series 1, …)` fails it.
- Task 4: 9c.33 reversed (leave `RIETX_COMPILED_THREADS` unset; pin BLAS only)
  and 9c.5 gains the screen's 84× job and "time the jobs that raise".
- Task 1's decision, settled by Claude on the measurement and joblib's
  documented practice: no package change. A pool worker keeps
  `min(8, cores)` kernel threads, and `n_threads()` does not fall back to
  `OMP_NUM_THREADS`. loky sets that variable to `cpu_count() // n_jobs` in
  each worker (1 for a 10-worker pool on 10 cores) and 9c.31's BLAS pinning
  sets it to 1, so a fallback would select the setting measured slower.
  Recorded in `docs/practice.md` § Inner threads in a process pool.

*Measured.* All on this machine (arm64 Mac, 10 cores as 4 performance and 6
efficiency, `[dev]` venv, rietx-kernels compiled tier on), never quiet: other
sessions' suites held the load at 9-84 throughout. Driver and raw JSON lines
in `~/.cache/ghostshift/rietx/wp-1464/` (`driver.py`, `screenjobs.py`,
`series*.jsonl`, `imitation.py`/`.log`).
- Job set: six patterns (CPD corundum, zincite, fluorite, brucite; GSAS-II
  fluorapatite; 11-BM NAC) each fitted alone and with each other CPD phase
  added, every cell free, the compare standards' plans: 26 cold fits, 10
  spawn workers, BLAS and OpenMP variables at 1 in both arms.
- Walls, default pool against `RIETX_COMPILED_THREADS=1`, interleaved:
  23.6/44.0, 27.3/75.9 (a `find /` of mine overlapped the second), 49.6/117.6,
  47.7/116.5 s. Ratio 1.9-2.8× over four pairs (1.9-2.4× in the three no other job of mine disturbed). Summed job time 1.17× in the one pair at load
  9-13, 1.5-1.6× in the rest. 104 fits (the set ×4): 145.9/297.2 and
  99.8/200.8 s, 2.0× both. Every fit ran the same iterations to the same Rwp
  in both arms.
- Splits: every job's kernel calls split across the pool, 187-4464 times a
  fit, so the pool does work here.
- Most of the wall gap is the slowest job (fluorite + corundum, 19.6-40.1 s
  against 40.2-107.2 s), which the default pool spreads over the cores the
  finished workers leave idle.
- Imitation (CPD patterns, 12 pairs, free and at ±1 %): absent candidates
  were held or sat at 0 wt % on 10 of 12 with the cell free. zincite + fluorite: cell −10.8 %,
  Rwp 10.60 → 10.23 %, 14 ± 12 wt %; at ±1 %: on its bound, 10.07 %,
  66 ± 24 wt %. fluorite + corundum: Rwp 17.64 → 16.01 %, 89 ± 40 wt %,
  `CELL_RUNAWAY` fired; at ±1 %: 16.00 %, 89 ± 75 wt %.
- Acceptance: `tests/test_skill.py tests/test_skill_cli.py
  tests/test_docs_consistency.py` 222 passed (same venv and machine). ruff
  clean. Vale: 0 errors, 272 warnings, none on a line of this branch (it
  touches no `docs/docs` page). `python -m tests.reader_output` exit 0.

*Generality* (the `generality-review` judge's verdicts, summarised, with the
author's answer under each weak one).
- 9c.33, weak: the row said six pairs at 1.9-2.4×, where `series.jsonl` holds
  four at 1.9-2.8×, and "Pin BLAS (9c.31)" said more than 9c.31 does. One
  machine under load; joblib's loky dissents (1 thread at `n_jobs = cores`);
  without the one degenerate slow job the light-load pair's summed time is
  1.01×. Author: figures and wording corrected; the quiet-machine gap stays a
  hypothesis in the tag.
- 9c.5, holds. 9c.35, holds: two families, both development data, and the
  bound's width is rightly a hypothesis. Moved cells a refiner accepts
  (thermal expansion, Vegard) bear on the width, never on the rule.
- The practice decision, weak: strong for no `OMP_NUM_THREADS` fallback,
  moderate for the default in general; the prune dropped the `os.cpu_count()`
  note. Author: restored as open in Inherited.
- The routing row is a routing key, not a heuristic.

*Not done.* Task 6 (the job-summary verb) is a new CLI surface and stays open.
No code changed, so neither the fast nor the full suite ran locally; CI runs
the fast one. `/code-review` skipped: the branch is prose only.

*Gotchas.* The machine was never quiet, so the ratios are measured under
contention. The one pair at load 9-13 bounds the quiet-machine gap only
loosely (1.17× summed, 1.86× wall); 9c.33's tag keeps that as a hypothesis.

Also forwarded: the thread measurement to WP-1950's Inherited, for its
embedding section.

Next: task 6, after the maintainer names the surface. Then close.

- **2026-09-25** — created by a transcript review of a second agent session on
  `in-situ series 1`. The screen's numbers are from that session's timeline and
  `screen.json`. The imitation case is from this review's replay on main.
  Next: the thread measurement, on a quiet machine.
