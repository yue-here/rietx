# WP-1404 — what recording every fit costs

Milestone: unscheduled · Status: ⬜
Depends on: 1403 (the layer being measured); 1401 (its baseline)

## Goal

A measured answer, quoted as a range, to whether every fit can afford to record
itself — and the authority to reopen WP-1403's design if it cannot. The number
reaches the handover and the milestone record; none of it becomes a test that
times anything.

## Context

WP-1403 makes recording the default for every `fit()` in the wild. That is a tax
on people who never asked for it, so it is settled by measurement rather than by
argument. This WP exists separately because **a measurement that cannot change
the design is not a gate**: it is licensed to send 1403 back, and if it never
could, it should not be a package.

### What is being priced

Verified in the tree 2026-09-13; WP-1403 carries the same table with the code
references, and this WP is the one that puts numbers against it.

- **Per residual evaluation**: `_free_values` is a second full `table.decode`,
  running *before* the sink is consulted, then `json.dumps` + write + `flush`.
  This is the dominant term and it is CPU as much as syscalls.
- **Per stage**: one extra forward evaluation for a real `stage_end.rwp`, and —
  only once WP-1405 lands — two `model_copy(deep=True)` from
  `_abandon_on_cancel`, whose short circuit a universally attached cancel token
  ends.
- **Per stage**: `decimation_index` buckets in a python loop, so the snapshot's
  own cost is measured here rather than assumed free.

### The matrix

Three cases from `examples/bench_refinement.py`, chosen to bracket both axes
rather than to be representative:

| case | why |
|---|---|
| `nac` | many points, few parameters — evaluation cost high, payload small |
| `cpd-2` | many parameters and phases — payload large per evaluation |
| `trigger` | dispatch-heavy, many evaluations — the syscall and decode term |

Five configurations, three runs each, one machine, one sitting:

0. recording off — **the control, and its own three-run spread is reported
   first**
1. recorder on, stage boundaries only (no eval events)
2. recorder on, eval events buffered — the shipping candidate
3. configuration 2 plus an attached cancel token — isolates
   `_abandon_on_cancel`, and is what WP-1405 actually ships
4. today's `events=LiveSession(dir)` — the reference for what a user pays now
   when they *do* ask

Configurations 0 and 4 need none of this track's code and are measured in
WP-1401; they are repeated here on the same machine in the same sitting, because
a number carried across machines is not a comparison.

Recorded per configuration: wall clock (median of three), **total residual
evaluations**, bytes written, lines written, flush count. The evaluation count is
not decoration — it is the assertion that telemetry changed no number.

### The gate, in three channels

**Asserted in a test**, because these are machine-independent and a count is not
a timer:

- the total residual-evaluation count is identical with and without the recorder;
- the extra forward evaluations number exactly `n_stages`;
- the flush count is bounded by the non-`eval` event count plus the run's
  duration over the flush interval.

**Measured into the handover and the milestone record, never into a test** — a
wall-clock budget in a test is a runaway guard, never a timer:

- recorder-on against off, median of three, **quoted as a range across the three
  cases**, with the venv and the platform named;
- **gate: ≤ 1.05× on every case.** Five per cent because `stage_reports` is
  accepted at 2.5× as an *opt-in*, and the intermediate-ftol schedule was worth
  1.2–1.6× fewer evaluations; a default-on tax must sit well inside both.
- **And the honest clause: if the control's own three-run spread exceeds 5 %,
  the gate becomes that spread and this WP says so.** A gate tighter than the
  measurement's resolution is a coin toss wearing a check's clothes.

**Reported, with no invented number**: bytes per run for each case, as a range.
"How big does this get" is the first question a reader asks, and WP-1406's manual
page quotes this and nothing else.

### What a failure means

If the shipping candidate does not come in under the gate, the outcome is
recorded, not worked around. In order of preference:

1. Adopt WP-1403's mitigation 2 — let the sink answer whether it wants the
   values, so a thinned log is cheap in CPU and not only in bytes — and
   re-measure.
2. Adopt mitigation 3, thinning the eval stream, **and record that the automatic
   log no longer reconstructs the WP-1113 trajectory**. That is a semantic
   change and it is not made quietly.
3. Ship WP-1403 **off by default**, with the env variable turning it on, and say
   plainly in the milestone record that the track's premise did not survive its
   own measurement. That is a legitimate ending, and naming it here is what stops
   it being avoided.

## Non-goals

- **No optimisation of the fit itself.** The two v1.1 speed fronts nobody owns
  (the per-reflection 19.4 %, WP-1121; the `refit=` choice, WP-1124) are not this
  WP's, however tempting they look once a profiler is open.
- **No new benchmark harness.** `examples/bench_refinement.py` is the
  measurement authority every speed WP quotes; add configurations to it, do not
  write a second one.
- **No timing assertion.** Every wall-clock number lands in prose.

## Tasks

- [ ] Add the five configurations to `examples/bench_refinement.py` as named
      keys, and a row per key to `tests/test_bench_refinement.py`.
- [ ] Run the matrix, alone, on one machine in one sitting. Nothing else running:
      these are wall-clock numbers and machine state moves them further than most
      changes do.
- [ ] The counted assertions (evaluation count identical, extra forwards exactly
      `n_stages`, flush count bounded) as ordinary tests.
- [ ] The measured numbers into this WP's handover and into the milestone
      record's appendix, as ranges, with venv and platform named.
- [ ] The verdict, written out: which gate applied (the 5 % or the control's own
      spread), whether the shipping candidate passed, and — if not — which of the
      three failure paths was taken and why.
- [ ] Snapshot and run-directory sizes per case, as a range, for WP-1406 to
      quote.
- [ ] Skill: **none**. WP-1406 carries the track's skill change; if a number
      here changes what an agent should do, say so in that WP's `### Inherited`.

## Acceptance

```sh
.venv/bin/python examples/bench_refinement.py --cases nac,cpd-2,trigger   # × 5 configurations × 3, run alone
.venv/bin/python -m pytest tests/test_bench_refinement.py tests/test_telemetry.py
```

The deliverable is the handover entry, not a green test. A session that ran the
matrix and reported "it seems fine" has not done this WP.

## References

- WP-1121 — the per-reflection 19.4 %, and how a speed claim is quoted here.
- WP-1113 — the evaluation-count mechanism analysis; what a thinned eval stream
  would cost a consumer.
- WP-1335 — the report costing 26× the fit, and the precedent for pricing a
  default before it becomes one.
- `tests/CLAUDE.md` § Running, and the root CLAUDE.md's testing headlines: quote
  wall clock as a range, never a figure; a budget in a test is a runaway guard,
  never a timer.

## Handover log

- **2026-09-13** — created. Separated from WP-1403 deliberately: a measurement
  folded into the WP it measures is a rubber stamp, because the session that
  built the thing is the session deciding whether it is fast enough. The failure
  paths are written down in advance for the same reason — the third one, shipping
  off by default and saying the premise did not survive, is the one that gets
  quietly avoided if it is not named before the numbers arrive.
