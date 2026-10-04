# WP-1420 — a held phase re-enters, or the chain says it cannot

Milestone: unscheduled · Status: ⬜
Track: A long run is not one fit
Depends on: — (1301 shipped, the hold this is about; 1333 soft, the same
chain's other silent shape; 1342 soft, the freeze's blind tie; 1419 soft,
the metric symmetry point a probe needs)
Priority: P2 2026-09-23 — a held phase stays out of every later pattern and the chain says nothing, on the series path

## Goal

A phase that WP-1301 held in one pattern of a series and that the data
support in a later one gets back in. Where the chain cannot get it back in,
the series result says so, at the pattern where the hold stopped being
right. A subgroup seeded at its parent's identity point is named as the
case the hold cannot judge on the data's authority.

## Context

Issue #267 (2026-09-05), a design proposal with a fully synthetic
reproduction: an eight-pattern series through `SequentialRefinement`, both
directions, defaults, run at three fractions. Read against the tree at
`28429810`: the `prepare` hook, `on_result`, `first_rung_factor`,
`RESEED_FACTOR = 1.25`, the `warm`/`warm_staged`/`cold` ladder with
`_prefer`, `StageResult.held`, `cell_window` and
`PHASE_SUPPORT_SIGMA = 1.0` are all as the issue quotes them.

**The hold's escape route.** WP-1301 holds every free structural path of
a phase below 1σ support and never its scale, "the one direction that is
not flat, and the only way the phase can come back" (`refine.py`, the
hold's docstring). Release is tested where the frozen structure is right
(`tests/test_held_phase.py::test_the_phase_is_refined_in_the_pattern_where_it_appears`,
CaF₂ at its true cell). The issue measures the route where the frozen
structure is *collinear* with a supported phase.

**The measurement.** Cu (`F m -3 m`) throughout; a tetragonal subgroup
(`I 4/m m m`, same atom, fcc → bct) appears at p004 at a fraction f of the
parent's scale with c/(a√2) − 1 = +6.0e-3. The subgroup is seeded at the
group–subgroup identity point at 2 % of the parent's scale, `carry=("*",)`,
`direction="both"`, ladder on.

| f | forward | backward |
|---|---|---|
| 0.40 | p004 deadlocked at 1.26× the running median; the 1.25× fence fired and `warm_staged` rescued it (16σ, tet +6.0) | cold start at p007 fell to the wrong sign (tet −8.0, `max_iter`), carried down p006–p004 |
| 0.25 | p004 deadlocked at 1.11×, under the fence; p005's first-rung budget forced `warm_staged` (1.3σ); p006 role swap, subgroup 332σ, parent cell jumped 0.011 Å (`SEQUENTIAL_DISCONTINUITY` on `phases.0.cell.*`) | correct: found at the cold start, carried down, held at p003 |
| 0.15 | p004 deadlocked at 1.03×; p005–p007 released into the wrong basin (tet −6.7) | cold start found the phase absent (0.00σ, held) and carried "absent" through all eight (`max_iter` ×7); `PHASE_UNCONSTRAINED` 5 of 8 |

The forward chain fails at every fraction, three ways. The backward chain
fails at two of three. "Absent everywhere one way, present the other",
which the reporter had seen from a hand-rolled chain on real data,
reproduces from the package's own chain with its ladder on.

**The mechanism, as far as measured.** At the identity point every
subgroup line sits under a parent line, so its support is a coordinate
along the two-scale ridge and the hold decides on that coordinate. At
re-entry the free scale's gradient is what the parent leaves in the
residual, about zero where the parent's model already carries the unsplit
intensity. That is the deadlock. When the scale does climb, release happens
at the identity point, a saddle of the symmetry-breaking direction, and
which sign it falls to is set by nothing in the data: three of the runs
above fell to the wrong sign with a "significant" scale (5–16σ) and an Rwp
10–15 % above the right basin. The fence is a symptom threshold. It
reopened the route at 1.26× and stayed shut at 1.11× and 1.03×. Nothing in
the chain reads the held state itself.

**What user code can do today.** `on_result` runs after each accepted
pattern with the full `RefinementResult`, before the next pattern's
`prepare`, so a re-entry policy is expressible as a closure over the
previous result. The issue measured one (re-seed the held phase's cell off
the identity point at 10 % of the parent's scale): worse than the ladder at
0.40, no better at 0.25 and 0.15. Three things a closure cannot do: probe
and keep the best, since a reseed is unconditional for that pattern; know
the sign; or tell "absent, correctly frozen" from "present but
unreachable", which look identical in the previous result.

**The framing that survives.** A re-entry attempt is a bet, WP-1127's word
for the collapsed first rung, and the chain already has the machinery for
bets: the ladder with `_prefer`. The rungs vary the plan and the starting
*state*. None varies the starting *structure* of a held phase.

**Four options, from the issue,** each checked against WP-1051's rule for a
trigger (a property of this pattern's own fit, readable when it finishes,
plausibly fixed by a different starting point):

1. **A re-entry probe rung.** Trigger: a phase held in this pattern and in
   the previous accepted one, and this pattern's Rwp risen against the
   accepted median by a factor well under `RESEED_FACTOR`. Probe: the held
   phase re-seeded off its metric symmetry point in both signs of its
   symmetry-breaking DOFs, at a scale that clears support; keep the best by
   `_prefer`. Passes all three clauses. Cost: two extra fits on
   held-and-rising patterns only, zero on a chain with no held phase. The
   0.40 rescue already is this, minus the sign and minus the lower
   threshold.
2. **A lower, held-only fence.** Same trigger, escalate to `warm_staged`
   at about 1.05× when a phase is held. Cheapest. Would have fired at 0.25
   and stayed shut at 0.15, and cannot fix the sign.
3. **Report only.** A series-level finding when a phase is held for a run
   of patterns and the chain's Rwp trend rises across it, with the ± two-seed
   check documented as the user's job. Leaves the deadlock in place.
4. **Documentation only.** `using/series.md` and the skill's
   `references/series.md` state that a subgroup seeded at its identity point
   is collinear with its parent and cannot be held or released on the
   data's authority, that the seed is a saddle, and that both signs must be
   tried. Owed whatever else is chosen.

**Triage recommendation (2026-09-15):** 4 and 3 first, then 1 on a measured
trigger. The docs are owed. The finding costs nothing, passes 1051's rule,
and is the package's "evidence, not verdicts" shape (1043). Option 1 is the
only one that fixes the sign, and the ladder has the seam for it, but its
trigger threshold and its two-fit cost have one synthetic series behind
them. Before it lands: the trigger measured on a real held-phase series
(the issue's own hand-rolled case, or 1329's onset data once 1327 is in),
and the threshold set with 1127's margin rule, a win/lose gap and not a
number picked from three runs. One design note for option 1: "re-seeded
off its metric symmetry point" needs that point found from the child cell
alone. That is the invariant metric subspace #293 and 1419 describe, so
the probe's seed is 1419's `MetricConstraints` read the other way.
Option 2 is dominated by 1 and is not recommended on its own.

Two neighbours. 1333 is the same chain's other silent shape (a pattern that
died reading as passed); this one is a pattern that converged to the wrong
basin reading as right. 1342 is the hold's blind tie, the freeze one rank
down.

### Inherited

- **2026-10-03, from a cleanup session: the guard is 300 s.** This WP's own
  commit `b333ca09` (2026-09-30) had widened `RAMP_RUNAWAY_GUARD_S` to 300 s
  and fixed the root CLAUDE.md's count of λ-scaled size terms, but was never
  pushed from its tree. It is cherry-picked as `6336c65c` (CLAUDE.md rewrapped
  to hold its line cap) and closes issue #539. The ramp-guard halves of the
  three entries below are discharged; the iteration bar's name (#538,
  WP-1334) is not.
- **2026-10-02, from WP-1534: a fifth trip of the ramp guard.**
  `test_the_ramp_reproduction_no_longer_runs_away` measured 81.6 s on
  WP-1534's branch and 81.9 s on its untouched base, against the 60 s guard.
  Both ran under `-n auto` in a 15-file selection, `[dev]`, Linux x86-64,
  4 cores. Alone it took 16.6 and 17.2 s. The chain ran the same 1609
  iterations with WP-1534's new scale–B probe on and off, so the probe adds
  nothing to this fixture.
- **2026-09-30, from the issue triage (issue #539, which is this note's
  fourth trip): the ramp guard fails on every loaded 4-core run.**
  `RAMP_RUNAWAY_GUARD_S` is still 60 s at `tests/test_held_phase.py:685`
  (*checked at `e3e6486a`*). The reporter's table: 76.2, 138.3, 96.9 and
  135.1 s under `-n auto` (load 9-11) against 18.85 s alone, `[dev,jax]`,
  Linux x86-64, 4 vCPU; every other assertion passed, `iterations <
  RAMP_MAIN_UNBOUNDED_ITERATIONS` included. That is 3.2× serial, under
  `tests/CLAUDE.md` § Budgets' "several times". The suggested fix is the one
  already written below: keep the iteration bar, widen the guard to the
  runaway (300-600 s, the `REAL_DATA_BUDGET_SECONDS` precedent). **One
  caution from issue #538:** `n_iterations` holds scipy's `nfev`, so the
  2164 bar is an evaluation count. It still separates 1609/1659 from a
  runaway, but the name is wrong until #538 is settled (WP-1334 holds it).
  Because it is a required-check-shaped flake on merges, consider taking the
  guard change now rather than with the rest of this WP.
- **2026-09-29, from [1469](1469-what-the-series-fences-cannot-see.md): a
  phase fitted to noise can pass the support test, which is this WP's hold.**
  Issue #481's blank frame, fitted alone, released its held cell after the
  `cell` stage and reported it with no `PHASE_UNCONSTRAINED`: the phase's
  support at the answer was 2.14σ on a scale 1.3σ from zero. It needs no
  chain, so it is filed as
  [1523](1523-a-phase-fitted-to-noise-passes-the-support-test.md); read it
  before relying on the hold's release rule here, since a fix there changes
  which phases this WP sees held. **And the ramp guard below tripped a third
  time**: 112 s against its 60 s `RAMP_RUNAWAY_GUARD_S` while a second
  selection ran beside a `-n 4` run on four cores, 17.1 s alone (`[dev]`,
  Linux x86-64). The runaway it guards ran past 13 minutes, so a guard of
  300-600 s still separates the two; this WP remains the one to widen it or
  move the claim to the iteration count, as the WP-1333 note says. (Briefly
  filed as its own WP from 1469's session, then folded back here.)
- **2026-09-28, from [1338](1338-the-skills-own-gates.md): `references/diagnostics.md` is closed to growth.**
  Every skill file now has a ceiling and a budget below it
  (`tests/skill_caps.py`), and the budget fails a change that grows a file
  past it. `diagnostics.md` (35 111 B) and `diagnostics-indexing.md`
  (35 124 B) sit over their 34 600 B budget, so a row this WP adds there
  comes with an equal cut in the same change, or goes to the file a reader
  meets the code in (the criterion in the `REFERENCE_MAX_BYTES` comment).
  CI's lint job reports each changed file's headroom on the draft PR.

**From WP-1463 (2026-09-28): the 16-of-48 side effect below is resolved.** A
leaving phase whose scale ends anywhere down to about 1e-300 now keeps every
weight-fraction esd, equal to the 1e-135 answer. At exactly 0.0 the esds stay
`None` and `QPA_ESD_UNAVAILABLE` names the phase, which `PHASE_UNCONSTRAINED`
never did when the scale was the phase's only free parameter. Its scale row
reads `at_bound=None`. So the presence-window recipe this WP writes can tell a
reader to expect that code on patterns where the phase has left, and to take
`profile_fraction` for an interval there.

**From WP-1333 (2026-09-26): 1333 closed, so the soft dependency is
discharged, and a refined coordinate now crosses the pattern boundary.** Three
facts this WP's chain work meets. (1) `_carry_into` carries a site's
displacement, so a held phase's coordinates carry whatever value they were
held at, where before every pattern restarted them from the model. (2) A
coordinate DOF's value in a chain is the step from where that pattern's fit
began, so any judgement across patterns skips `sequential._relative_paths`
and reads the coordinate rows. Both fences and the GUI's disagreement column
do this, so a re-entry check comparing trajectories should too. (3) The
ramp reproduction's 60 s guard tripped once more under 4-worker load
(`[dev]`, Linux x86-64), and passed alone in 14.6-14.9 s against 15.6 s on
`main`'s code. So it is still the load sensor the note below describes, and
the carry did not slow it.

**From the 2026-09-24 transcript review (PR #444, which filed WPs 1453-1456):
a real held-phase series for task 3, and a deferred question.** The series is
`in-situ series 1` in the private `yue-here/rietx-corpus-map`, which says
where the data, the scripts and the transcript live. It is 48 synchrotron
patterns in which phases enter and leave. Quote only what the runs did
(CONTRIBUTING, WP-1450). An agent refined it at `644dff84` with a
hand-written chain, because `SequentialRefinement` takes one `Structure` for
the whole chain. That chain fitted one to four candidates per pattern, and
two candidates were proxies sharing one structure with a neighbour, which is
this WP's collinear case by construction. It declared a window of patterns
per phase, pruned a phase under 1 wt % or under 2σ, and bounded each phase's
cell to about ±0.15 % of a reference to keep its identity. Its first chain
swapped two phases' identities across a transition while Rwp stayed smooth.
The hand chain ran no series check, so the package never had the chance to
see it.

**Deferred into this WP: can the fixed list carry such a series?** Run it
through `refine_sequential` with every candidate in one `Structure`, in both
directions. If it cannot, because a proxy takes its neighbour's reflections
or because carrying every candidate costs too much, file the follow-up: a
phase set declared per pattern, with carry, trajectories and path dependence
keyed by phase name. Read first how GSAS-II's sequential refinement and a
TOPAS batch file treat a phase that enters mid-series. If the fixed list
serves, the docs task here takes the recipe, because `references/series.md`
has no route for a changing phase set.

**From the 2026-09-25 review of a second session on the same series: the
deferred question, answered with the caller's help.** A second agent session,
at `2d42303a`, ran `in-situ series 1` through `SequentialRefinement` with every
candidate in one `Structure`, in both directions. All 48 patterns converged.
The caller supplied two things the package does not. One was a presence window
per phase, found by three screens of 336 cold fits in all. The other was cell
bounds of ±0.3 % around a template per phase. About 25 lines of hooks did the
rest. `prepare` set an absent phase's scale to 0 and re-seeded an entering
phase from its template. `constrain` held every path of an absent phase
through `ref.hold`, and after the leaving phase's transition it held that
phase's cell and widths while its scale refined. With ±1 % bounds and no
presence windows, the first chain raised 8 `SEQUENTIAL_PATH_DEPENDENT`. The
final one raised none. So the fixed list serves when the caller states
presence, and the docs task here takes that recipe, including how the windows
were found. Two details for the recipe. Those were user holds
(`_user_holds`), not WP-1301's `_held`. And `HOLD_BLOCKED_PLAN` fired on 48 of
48 results, because the plan's cell glob met them, which is that report
working as designed. Whether the package should find the windows itself stays
this WP's question. This session shows a caller can, at about 336 fits. One
side effect belongs elsewhere. On 16 of the 48 results a leaving phase's scale
at zero withheld every weight-fraction esd, which is WP-1463.

**From WP-1333 (2026-09-23): the ramp reproduction's wall-clock guard is a
load sensor.** `tests/test_held_phase.py::test_the_ramp_reproduction_no_longer_runs_away`
failed in WP-1333's full run (`[dev]`, Linux x86-64, 4 cores, 1:24:44). It
passed alone, and in that session's slow-series run. Measured serially, the
chain takes 9.1 s compiled and 11.2 s on the numpy path, against its 60 s
`RAMP_RUNAWAY_GUARD_S`, with 1609 and 1659 iterations against the 2164 bar. So
every deterministic assertion holds on both paths, and only the guard can
move with load, on a run whose fixtures were up to 3.4× slower than CI's
nightly. About 6× margin is under what `tests/CLAUDE.md` § Budgets calls
several times, and this WP will add rows to that file, so it is the one to
widen the guard or move the claim to the iteration count, which already
carries it.

**From WP-1333 (2026-09-22).** The chain now says one of this WP's silences
out loud. `SEQUENTIAL_PATH_CHECK_INCOMPLETE` at `info` names every path some
chain measured that no pattern could judge in the `direction="both"`
comparison, and a phase held throughout one direction is exactly that case
(issue #269). So "the chain says it cannot" has a first member for held paths
under `"both"`. It says nothing about re-entry within one direction, which
stays this WP's. Two rules came with it that a re-entry diagnostic should
reuse. A path is named only if *some* chain measured it, and only if the two
chains differ above `_noise_floor`. Without both it fired on every clean
series (a tie row off a never-freed source, `profile.y` on its floor). And a
rung whose fit raises now escalates the ladder (`SeriesEntry.rungs_raised`),
so a held phase that makes a warm rung raise is rescued cold, not failed.

**From WP-1342 (2026-09-19).** A held path is now a **column**, and it need
not be a phase path at all: a caller's `vars.X` driving that cell is what the
freeze stops, so `StageResult.held` can read `vars.caf2_a` where this WP
expects `phases.1.cell.a`. Three consequences for the re-entry question.
`_released_phases` is handed that column list, so whatever this WP builds on
top of it inherits the same shape. The phase behind a held column is found
through `StageResult.held_reach`, which maps each held column to the tied
entries it also stopped — `_held_by_phase` is the worked example. And a column
reaching a *supported* phase as well as an unsupported one is never held
(`refine._only_moves`), so the "cannot get back in" case this WP is about
cannot arise for a shared column; it is already free.

**From WP-1435 (closed 2026-09-18), which put a second hold on the same
object.** There are now two holds on a `Refinement` and they mean opposite
things, so name them carefully in anything this WP writes.

- `Refinement._held` is WP-1301's and this WP's subject: the *package's*
  reading of what one stage's data can see, lifted at the start of the next
  stage, recorded on `StageResult.held`/`.released`.
- `Refinement._user_holds` is the *caller's* declaration that a parameter
  does not move whatever a plan asks, lifted only by `unhold`, carried on
  `RefinementState.holds` and recorded on `StageResult.blocked_by_hold`.
  It was deliberately **not** named `_holds`, which would have sat one letter
  from `_held` in the same method bodies meaning the reverse.

They never overlap today, and the reason is worth keeping true: WP-1301's
`_hold_unsupported_phases` only holds paths that are *free*, and a
user-held path is never free. A re-entry mechanism that lifts a hold has to
respect that split, because lifting a user hold is not this WP's to do.

## Non-goals

- Per-iteration re-anchoring (1301's stated non-goal).
- `PHASE_SUPPORT_SIGMA`, or the package deciding whether a phase is present.
- Passing `phase_support` or `held` into `prepare`: the previous result is
  already reachable through `on_result`, and the plumbing buys convenience
  only.
- A general sign-of-distortion search. Two signs of a one-parameter
  symmetry-breaking DOF is the scope; a higher-dimensional order-parameter
  space is 1418's M-7.

## Tasks

- [ ] Docs: the collinear-seed paragraph in `using/series.md` and the
      `references/series.md` row (Measured: issue #267's three fractions),
      paid for by a cut if the reference is at its cap.
- [ ] The series-level finding: a phase held over a run of patterns with the
      chain's Rwp rising across the run, naming the pattern where the hold
      stopped being right; `GuardFinding` constructor, `help.py` entry,
      `references/diagnostics.md` row.
- [ ] Measure the probe's trigger on a real held-phase series and on the
      issue's synthetic one at the three fractions; the table in the
      handover sets the threshold by 1127's margin rule.
- [ ] The probe rung, if the table supports it: both signs, `_prefer` keeps
      the best, the seed off the metric symmetry point, `entry.rung` records
      it; goldens bit-identical on every chain with no held phase.
- [ ] Tests: the issue's synthetic series at f = 0.15, 0.25, 0.40 in both
      directions, asserting the finding fires at the right pattern and, with
      the rung, that the forward chain reaches the right basin at all three.
      Obs/calc/diff PNGs to `tests/output/`.

## Acceptance

The synthetic series at f = 0.15 forward, the worst case, ends with the
subgroup in the right basin or with the finding naming p004; every shipped
series golden is bit-identical.

```sh
.venv/bin/python -m pytest tests/test_held_phase.py tests/test_sequential.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
```

## References

- Issue #267 (2026-09-05), with its `repro_deadlock.py` and outputs at three
  fractions.
- WP-1301 (the hold), WP-1051 (the trigger rule), WP-1127 (the first rung is
  a bet), WP-1043 (never a confident singleton), WP-1333, WP-1342, WP-1419.

## Handover log

- **2026-10-03** — **The ramp test's timeout is 300 s.** This WP's own
  commit from 2026-09-30 had widened it and was never pushed; a cleanup
  session cherry-picked it (`6336c65c`), so issue #539 closes with its PR.
  Nothing else of this WP started, and the status stays ⬜. *Done:*
  `RAMP_RUNAWAY_GUARD_S` 60 → 300 s, and the root CLAUDE.md's count of
  λ-scaled size terms (three of seven, rewrapped to hold its line cap); a note
  in Inherited says which entries that discharges. *Next:* the WP's own tasks.

- **2026-09-15** — created, from the 2026-09-15 issue triage (issue #267).
  Added in the round's second pass: the first pass read the issue and
  placed nothing. Checked against the tree: every hook, constant and rung
  the issue names exists as quoted; the hold's own docstring calls the
  scale the way a phase comes back, which is the route the issue measures
  shut. Recommendation recorded: docs and the finding first, the probe rung
  on a measured trigger.
