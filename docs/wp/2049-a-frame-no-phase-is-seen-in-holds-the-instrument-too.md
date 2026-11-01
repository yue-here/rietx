# WP-2049 — a frame no phase is seen in holds the instrument's peak terms too

Milestone: unscheduled · Status: ✅ 2026-11-01 — a frame no phase is seen in holds its peak-only instrument columns, single and joint; PR #1305 awaits the maintainer on the widened tier-3 hold
Track: What fires, and what stays silent
Depends on: —

## Goal

When no phase in a stage is seen, the instrument parameters that reach the
pattern only through phase peaks (zero shift, displacement, the profile terms)
are held for the stage like the unseen phases' own structural paths, and the
record says so. No result reports one of them with an esd fitted to noise.

## Context

WP-1301's hold (`refine._run_stage`, the `held` set; root CLAUDE.md § Invariants,
"A phase the data cannot see is a flat direction") holds every free structural
path of a phase whose scale is under 3σ of its counting-noise esd. It never
holds an instrument path, because one visible phase gives a shared column real
gradient ("all, never any", WP-1342). The case it misses is the frame where
**every** phase is unseen: then a peak-position or peak-width column reaches
nothing but unseen phases, and it is exactly as flat as their cells.

**Measured 2026-10-25** (`deff4c301`, macOS arm64, `[dev]`), on
`tests/planted_series.py`'s 248-frame series (seed 0), frame 87, the blank
frame. A 1e-14 nudge to the start cell picks which rung the ladder accepts:

| | rung | scale | zero shift | U..Y |
|---|---|---|---|---|
| outcome A (k = 0, −1) | `warm_staged` | 0, at its floor | held, no esd | held |
| outcome B (k = +1, ±2, +3) | `warm` | 8.6e-8 (1.8σ) | −0.02292 ± 0.00476 | refined |

Outcome B also fires `FLOOR_HIT` on `x`, `RESOLUTION_NOT_POSITIVE` twice, two
`HIGH_CORRELATION` pairs among U, V, X and Y, and `STAGE_MAX_ITER`.
`PHASE_UNCONSTRAINED` fires and holds `phases.0.cell.a` only. The zero shift's
step from frame 86 is −0.0289° against a series median of 1.2e-4°, so
`tests/test_planted_series.py::test_the_full_length_series_reproduces_its_committed_signals`
gains `['instrument.zero_shift', 86, 87]` in its `steps`. That row was red on
the Linux nightly on `deff4c301` (run 40184228951) for this reason. Outcome A
is what the committed signals record. The probe is
`docs/wp/2049-batch/frame87.py`.

Which rung wins is rounding. That an instrument column is refined on a frame
with no seen phase is not: it happens whenever the warm rung is accepted.

**Superseded in part, 2026-11-01** (`62034506e`, macOS arm64, `[dev]`). The
series no longer reaches outcome B: at k = −3, −2, −1, 0, +1, +2, +3 and +5
the ladder accepted `warm_staged` on frame 87, with the scale at 0 and the
instrument rows carrying no esd. So the nightly row this WP was filed for
is not red here by that route. The class still stands. Frame 87 fitted
alone from `cubic_model` under `mccusker_default` returns a zero shift of
−0.0129 ± 0.0015° (8.7σ, truth 0.006°), U..Y refined beside it, and
`HIGH_CORRELATION` on U and V at ρ −0.991. That direct fit is the test this
WP pins (`tests/test_held_phase.py`, `blank_frame`). Probe:
`~/.cache/ghostshift/rietx/wp-2049/direct87.py` (not committed).

**What qualifies, as built.** An instrument entry is peak-only when
`CompiledModel.scalar_chain_supported` claims it, or it is one of the two FCJ
axial ratios. That predicate is the authority that already says which paths
reach the pattern only through per-peak scalars. It already knows that a
declared sharp peak (`extra_components`) reads the polarisation and the line
weights, so with one compiled those stay free. The hold reads the column's
reach off C and asks the predicate of each reached entry.

The tier of the rule this WP adds: physics. A column whose every reach is an
unseen phase is flat by the same argument WP-1301 made for a cell, so the
action is of Rule 1's first kind (`docs/DESIGN.md` § Rules). Which columns
qualify is read off C (`column_reach`), never off a path's name (WP-1342).

## Non-goals

- Which rung the ladder accepts on a blank frame (WP-1051's ladder).
- Background terms: they reach the pattern without any phase and stay free.

## Tasks

- [x] Hold, in `_run_stage`'s support pass, each free instrument column whose
      reach (`column_reach`) lies wholly in unseen phases, beside the phases'
      own paths; record it in `StageResult.held` and `PHASE_UNCONSTRAINED`'s
      message.
- [x] The joint twin in `multi.py`, and a series' carry: a held instrument
      value carries from the last frame that measured it.
- [x] Tests: frame 87 at both nudges gives a held zero shift; the planted
      series' committed signals hold at k = 0 and k = +1.  The k = +1 series
      is a measurement, not a row (settled by Claude under cost: the fast
      direct-fit rows pin the mechanism at both nudges, and a second
      248-frame series would add 35-60 s to every nightly to re-test it).
- [x] Skill: `PHASE_UNCONSTRAINED`'s row says the instrument can be held too.

## Acceptance

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup tests/test_planted_series.py tests/test_held_phase.py tests/test_absent_phase.py
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1301 (the hold), WP-1342 (reach, "all, never any"), WP-1051 (the ladder),
  WP-2036 (found it on the nightly).

## Handover log

- **2026-11-01** — closed by a ghostshift runner. PR #1305. A blank frame no
  longer quotes a zero shift or a peak width fitted to noise. When no phase is
  seen, the stage holds every instrument term the pattern reads only through
  phase peaks, beside the phase's own cell. It releases them as soon as any
  phase is seen. A joint fit does this per histogram, and a series carries the
  last measured value across the blank frame. The nightly route the WP was
  filed for no longer reproduces on main, but the class did, by a direct fit.
  One question is the maintainer's: the tier-3 `StageResult.held` audit row was
  approved for a narrower hold.

  *Done.* `refine._peak_only_instrument_path` asks
  `CompiledModel.scalar_chain_supported`, plus the two FCJ axial ratios.
  `refine._every_phase_unseen` gates it. `_only_moves`, `_unsupported_phase_paths`
  (hold and collapse), `_released_phases` and `_answer_significance` read it.
  `multi._unseen` / `_only_unseen` / `_unsupported_paths_multi` / `_rehold_multi`
  and `_parametric_unseen` take `models`. `refine._instrument_held` reads the
  last stage's record, and the `PHASE_UNCONSTRAINED` clause quotes it once.
  `where` is unchanged. The skill row, `help.py` and the audit row's evidence
  are updated, and v1.11's record has the paragraph. Seven tests are in
  `tests/test_held_phase.py`. Against main's source, the two blank-frame rows,
  the series carry and the joint row fail (measured). Two rows import the new
  helpers. The all-never-any row passes on both, as it should.

  *Measured* (macOS arm64, `[dev]`, `62034506e`). Frame 87 alone under
  `mccusker_default`: on main the zero shift read −0.0129 ± 0.0015° (truth
  0.006°), with U~V at ρ −0.991. Here it is held. The 86-88 chain read
  −0.0229 ± 0.0039° at frame 87 on main. Here frame 87 quotes none, and frames
  86 and 88 land within 4 esd of truth. Series signals equal the committed
  record at k = 0 and k = +1. A misregistered start (frame 86, zero shift
  started 0.03-0.4° off) is bit-identical to main at 0.03-0.1°. At 0.2-0.4°
  both branches fail at Rwp 0.4332, so the hold closed no recovery route.
  `tests.reader_output` exit 0. Acceptance files before the new tests: 105
  passed, 2 xfailed. FAST_COUNTS

  *Review.* `/code-review high --fix` made seven findings. Fixed: 1, the
  parametric report called an instrument target seen; 4, the clause reported
  holds a later stage had released; 5, a stale number in a docstring.
  Declined: 2 (no joint diagnostic names a blank histogram's held instrument
  rows), which went to WP-2028's Inherited as reader output. 3 (the clause
  infers the hold from the record, and a field would be reader output). 6
  (instrument paths kept out of `where`, so `sequential`'s aggregation key
  holds). 7 (a misregistered start), answered by the measurement above.

  *Generality* (the judge's verdicts, condensed; full report in the session).
  Item 1, `StageResult.held`: **weak**. The flatness argument is sound and
  has one measured cost, but `grounds` and `approved` (2026-10-23) cover only
  the phase hold. The judge also named an unmeasured misregistered start;
  author's answer: measured since, as above, no route closed. Item 2, the
  predicate and gate: **holds**. Item 3, the clause and the help sentence:
  **weak**. The help list read as complete, so it now says "for example". The
  instrument paths stay out of `where`; that is latent until the code gets a
  response row.

  *Settled by Claude.* No full-length series row at k = +1, under cost: the
  fast rows pin the mechanism at both nudges. Instrument paths stay out of
  `PHASE_UNCONSTRAINED.where`, under `sequential`'s aggregation key.

  Next: the maintainer re-approves or narrows the widened `StageResult.held`
  row, then merges #1305. The reader-output change on a blank frame comes
  with it: instrument rows leave `result.parameters`, and one sentence joins
  `PHASE_UNCONSTRAINED`.
- **2026-10-25** — filed by WP-2036's session after a measurement lane
  reproduced the nightly's planted-series red on an arm64 Mac. No open WP owns
  the hold: WP-1301 is closed, and what its fix did not cover is a new WP.
  Next: the first task.
