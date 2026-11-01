# WP-2003 — The chain actions: what a series decides between patterns

Milestone: generality · Status: 🔄 2026-10-26 — X16 fixed (an LM-driver tolerance), task 3 and C4 landed, X17 handed to WP-1955; next C1 and C3 (unblocked), C2 question 5, C5-C10
Track: The audits
Depends on: 2002, 2037
Priority: P2 2026-10-24 — 2037 closed, so its clause 1 and the response column this WP's first demotion takes are in place; the maintainer's next after 2037; the seam the maintainer's own example (a series discontinuity) lives in

## Goal

Every action `refine_sequential` and the joint fit take between patterns is in the audit
table with a tier: the reseed fence, the rung ladder and quarantine, the kept-attempt
choice, the width-growth fences, the moment-floor carry. Opt-in tools are classified as
such and left alone; answer-invariant items get their invariance test. Each surviving
tier-3 action carries its two grounds and approval; the rest are demoted by their kind of
ambiguity (DESIGN.md § Rules, 1), to a ranking or to the number in a record field.

## Context

The rule is `../milestones/generality.md` § The rule. This WP applies it to
`src/rietx/sequential.py` (3 070 lines) and `src/rietx/multi.py` (2 482 lines).

**The maintainer's example.** "In a series there may be many types of discontinuity due to
phase transitions etc. We don't need to (and can't) cover all of them. It might be useful
to suggest a symmetry-mode refinement, but we shouldn't enforce a test by default." The
discontinuity test (`SEQUENTIAL_DISCONTINUITY`, 5× the median step and 3σ, ~lines
226–227) is DESIGN.md § Rules, 1's own example of the third kind: what a jump means depends
on facts outside the pattern (a transition, a sample shift, a beam dump), so it fails the
judgement ground. Since its threshold is its trigger, no diagnostic remains: the statistic
becomes a **record field with no threshold**, `SeriesResult.steps` (every step in esds,
largest first, under a name that asserts no jump), its explanation in `rietx.help` keyed to
the field, one line naming it in the trajectory block, and **no diagnostic** (the record
§ Demotion and *Attention is a cost* clause 1, ruled 2026-10-23 by WP-2037, reversing the
`info`-record shape ruled 2026-10-18; `2037-attention/examples.md` § 5 is the mock-up). The
explanation carries the reading: what a jump can be, and that a symmetry-mode refinement
separates the cases. The third review had put that reading in the skill's
`references/series.md`, because a suggestion inside the package needed a trigger; a field
with no threshold needs none. `SeriesResult.discontinuities`, the trajectory plot's shading
and `verify_discontinuities` all read the flagged pairs today, so each moves to the largest
steps or is ruled in the batch.

**The seats this WP lands in exist** (WP-2037, closed 2026-10-24). `rietx.help.RESULT_FIELD_HELP`
describes every field of `RefinementResult`, `StageResult`, `SeriesEntry` and `SeriesResult`
keyed `Type.field`, crossed both ways by `tests/test_help.py::test_every_result_field_has_an_entry`,
so `SeriesResult.steps` fails until its entry is written and `rietx.help.explain(…)` then answers
it. Every code row in `rietx._audit` carries `response`/`responds`/`scope` or sits on the
shrink-only `RESPONSE_BASELINE`: a code this WP keeps leaves that list with a response (one
level at every raise site), and a code given `response="warning"` adds a fire/silent pair to
`tests/silence.py`. `SeriesResult.summary(levels=…, deliverable="series")` and
`rx.diagnostics_summary(results)` read those responses. One cost is this WP's: with no
deliverable a `SEQUENTIAL_PERSISTENT_FINDING` row prints as one line,
`SEQUENTIAL_PERSISTENT_FINDING: warning under every purpose`, which no longer says *which*
per-pattern code persisted (tutorial 05, cells 19 and 34); a wrapper code's one-line form is
shaped when its row is tiered.

**What WP-2002 handed on** (closed 2026-10-23; its rows settled, so the holds inside one stage
are fixed ground here). Tier 2 names seven programs (GSAS-II, FullProf, TOPAS, RIETAN-FP,
BGMN, MAUD, EasyDiffraction; `docs/practice.md` holds each one's defaults by topic), and a row
resting on a program default names what each does. Two record fields reach a chain:
`StageResult.collapsed` (columns a stage restored and held, from all three runners) and the
Stephens seed's rows in `StageResult.seeded`; the joint runner seeds no Stephens block. Every
plan ends in a closing stage and a warm refit carries it (`_collapse` passes
`closing_window_tol`), 1.05-2.05× a single fit's time a pattern, its cost along a chain and its
effect on path dependence unmeasured (`closing_window_tol=None` is the bit-identical way back).
The **width twin hold** makes the carry policy matter: on CPD sample 1a-1h the chain carrying
the widths but not the scales averages Rwp 0.1282 against 0.1256 carrying everything and 0.1258
independent, a strict xfail in
`tests/test_acceptance_sequential.py::test_warm_start_iteration_cost_is_reported`; the
iteration saving stands (388 against 1218). Superseded in part 2026-10-25 (WP-2045, PR #1161,
the last declared stage converged behind the closing stage): that xfail is gone, both chains
reading mean Rwp 0.1282 against 0.1258 independent at 408 (restricted carry) and 655 (`carry=*`)
iterations against 1255 (macOS arm64, `[dev]`); the kept first rungs fell to 0.064-0.080 of
the running maximum, about 40× inside `FIRST_RUNG_FACTOR`, and every CPD pattern after 1a is
kept on its warm rung. The **held-out family** is the Nd₂Ru₂O₇ pair
(`tests/data/mg090*`), which no audit may use as evidence. Two of 2002's clash candidates
reach the chain (`2002-batch/clashes.md`): B16, `multi.py`'s parametric test holding at-bound
columns through `staged.bound_findings`, whose margin falls to 13/f if class B4 lands; and B7,
the 0.03-esd bound on `intermediate_ftol`, a one-fit bound whose chain effect is this WP's.

**The table's mechanics** (WP-2001). This WP's rows are those `_audit.WALKED` and
`_audit.DEFAULT_SEATS` map to 2003 (`sequential.py`, `multi.py`, `params/multi.py`;
`refine_sequential` and `SequentialRefinement.fit`, the latter a seat because
`refine_sequential` reaches its `reseed`, `refit`, `on_error` and `direction` defaults through
`**kw`), plus the codes and suggestion rows of the subsystem. Auditing a row gives it a tier
and evidence in place and deletes its line from `UNAUDITED_BASELINE`; `tests/test_audit_table.py`
fails until both are done. The walk sees module-level numbers and tuples of numbers only, so a
number in a dict, list or array is audited by hand. The series floor-reseed of an unsupported
moment (near the `SEQUENTIAL_MOMENT_HOLD` raise) has no record field, only that code's message,
so it has no action row yet; `SeriesEntry.rungs_raised` and `rungs_tried` do.

**The inventory**, keyed on `SeriesEntry` (`schemas/sequential.py`) fields `rung`,
`reseeded`, `rwp_fence` and on the constants:

- `RESEED_FACTOR = 1.25` (~line 168): Rwp above this multiple of the accepted-so-far median
  triggers a cold refit. No citation, no measurement in its comment; WP-1469 already
  carved an exception out of it (~lines 1682–1690). The second review proposed escalating
  on status alone (diverged or non-finite) with the Rwp fence opt-in. **A finding to
  measure here, not a decision taken at filing.**
- The rung ladder and quarantine (~lines 1677–1715, WP-1051): a rejected warm fit retried
  from colder starts, then `SEQUENTIAL_UNRECOVERED`, seeding no successor. Under the
  judgement ground this is kept unless a competent caller can be named who would let a
  diverged fit seed its successors (fourth review; the record § The rule names it as the
  case that flipped from contested to kept when visibility gave way to judgement). Rule 1
  also names it among the protections of expensive work ("seeds no successor from a
  diverged fit"). What
  is on trial is the *ladder*: its rungs, the order of colder starts and the point at
  which it gives up are choices, so tier them. Measure what the caller sees: does the
  returned `SeriesResult` show which pattern diverged and which were seeded from it? If
  not, that record field is added whatever the ruling.
- `DISCONTINUITY_FACTOR = 5.0` and `DISCONTINUITY_SIGMA = 3.0` (~lines 226–227): the
  threshold the removed code was keyed on. The walk enters both at `unaudited`; when the
  code goes, the constants go with it or are re-tiered as the trajectory field's own
  (the step size needs no threshold), so the baseline can shrink past them.
- `FIRST_RUNG_FACTOR = 3.0` (~line 218): measured bit-identical, 0 of 1030 and 0 of 392,
  with 2.3× margin; its docstring calls it a bet, since the budget truncates only a losing
  rung while a winning one stays cheaper than the budget. The answer-invariant class; the
  invariance test asserts the accepted values *and* the margin (every kept first rung
  under the budget), not a comment.
- `_better` / `_prefer` (~lines 1952–1959): which attempt is kept, by Rwp, with a truncated
  attempt ranked below any completed one. Keeping the best attempt is one of Rule 1's
  protections; what is on trial is the criterion that names the best, so tier it.
- `WIDTH_GROWTH_FACTOR = 3.0`, `WIDTH_GROWTH_GOF_FACTOR = 2.0`, `WIDTH_GROWTH_SIGMA = 3.0`
  (~lines 279–303): under `THRESHOLDS_VERSION`, which 2004 owns. Hand 2004 the rulings;
  do not bump the version here.
- `_floor_unsupported_moments` (~line 851, WP-1329): the moment-floor carry across
  patterns. Not in the first plan; the review found it.
- `direction="both"` and `verify_discontinuities` (~lines 1020–1024): opt-in, the caller
  asks. Classified, not audited; a row each at tier `caller` (2001).
- `SEQUENTIAL_PERSISTENT_FINDING` ("42 of 68"): a count across patterns, tier 1 as a
  statistic; whether it carries a verdict is the question.
- `multi.py`: the joint residual's own holds and its second builder of the extra
  components (root CLAUDE.md § extra_components names it as the miss). Its cell runaway
  resets and holds the phase's cell like the single runner's (`StageResult.cell_reset`), but
  `_cell_runaway_diagnostic(cell_runaway)` (~line 1632) never passes
  `refine._vars_driven_cell_escapes`, which the single runner folds into `CELL_RUNAWAY`, so a
  `vars.X`-driven escape goes unnamed in a joint fit (WP-2002, PR #1050; checked 2026-10-24).

**A chain is measured, never assumed.** Root CLAUDE.md: cumulative staging's bound holds
for one fit and is unbounded in a chain, both signs measured. So every family here is a
chain family: the Durham in-situ tutorials, the 13-pattern sub-onset ramp (the v1.3 row),
the ten-pattern warm series of v1.1, the corpus series cited by number. Three families is
the bar.

**Three real families with independent truths were offered on PR #1150** (2026-10-24, by
contributor mustachefeeling; the comment carries the citations), each differing from CPD,
Durham and the synthetic series in lab, instrument and material:
- **Ba₂FeSbSe₅**, LLB G4.1 neutron, 1.5-200 K (PR #1073), with T_N = 58 K from χ and C_p.
  It exercises the moment-floor carry, the onset, and path dependence on the two-site split.
- **CuCr₂O₄ + 1.1 wt % CuO**, APS 11-BM, 17 patterns from 7 to 300 K (the GSAS-II
  SeqRefine tutorial). A continuous tetragonal → Fddd transition near 130 K means an
  I4₁/amd chain is a misfit with a known onset, so the fence and the width growth should
  fire there. An Fddd chain should stay silent, which makes it the fence's
  false-positive case.
- **Co₃O₄ quench series**, ILL D1B neutron, ten samples at 1.5 K plus 300 K patterns
  (CC BY). A second family for the moment carry.

None of the three has a known-bad pattern, so quarantine and `on_error` still need planted
ones. The maintainer accepted the offer to vendor the tutorial and Co₃O₄ files on
2026-10-24, and the reply on the PR asked for planted bad patterns too. Each file
lands with a `tests/data/README.md` row giving its source, its licence and its reference
values (root CLAUDE.md § Licensing, the per-file data fence). Measure on whichever have
landed when tiering starts. None had on 2026-10-24 (second session): `tests/data` holds no
CuCr₂O₄, Co₃O₄ or Ba₂FeSbSe₅ file, and #1073 is still open.

**The tier of each rule this WP adds** (written 2026-10-24, the WP predating the template's
line). It adds no flag, threshold or automatic action of its own: it tiers existing ones.
The record fields it plans (`SeriesEntry.seeded_from`, `SeriesEntry.floored`,
`SeriesResult.steps`) report an act or a statistic and carry no threshold, so they are
arithmetic (tier 1, ambiguity kind 1 as records). Whatever replaces `SEQUENTIAL_DISCONTINUITY`
as `verify_discontinuities`' choice of which steps to refit is a package number inside an
opt-in switch, so it is tiered in the batch before it lands (the judge's item 5,
2026-10-24). No new topic, so no new reference.

### Inherited

## Non-goals

- The holds inside one stage: 2002, already landed when this starts.
- `THRESHOLDS_VERSION` and the width-growth thresholds' version bump: 2004.
- The series panels of the GUI and `rietx watch`: a demoted code's row changes in
  `gui/src/lib/history.ts`'s `PLACES` only if a family is renamed, which this WP does not
  do.
- A new discontinuity classifier or a symmetry-mode suggestion engine: a follow-up WP if
  the batch wants one.

## Tasks

- [x] Inventory: one row per action and constant, with what it decides, what the caller
      sees without it, and whether it is opt-in or answer-invariant. `2003-batch/inventory.json`
      (2026-10-24): the 77 table rows 2003 owns (not 65: `SERIES_PATTERN_FAILED` and the
      joint fit's five codes, with their suggestion rows) and 34 row-less actions; task 3's
      question answered in `2003-batch/README.md`.
- [x] Tier each row per part, with evidence. The `RESEED_FACTOR` question measured on
      three chain families with the fence on, off and status-only: patterns reseeded,
      accepted values that differ, and the cost in evaluations. Second session (2026-10-24/25):
      a proposal for all 111 entries (`2003-batch/rows.json`, by class in `classes.md`); the 17
      that need no approval are in the table (`7c37469`); the rest wait for the batch's rulings.
      A fourth arm, `status_maxiter` (status-only that also escalates while the best attempt so far ends
      `max_iter`), measured on all eight families (`ded5c3f`, `dd13648`, `634bede`). Third
      session (2026-10-25): every family and arm re-measured on main after WP-2045, CPD on all
      eight patterns (`3c45728`-`891a6f9`, the JSONs written over), plus option (iii) as the
      arm `status_runaway`, the first-rung bound off (`on_nobound`, `off_nobound`) and X13's
      `cpd-ftolnone` (`7e03411`, a lane). Ruled 2026-10-26 (every entry's `ruling` in
      `rows.json`); the table rows land with task 7's demotions.
- [x] Quarantine's record: does the returned `SeriesResult` name the pattern that
      diverged, the rung it reached, and the successors seeded from an earlier pattern
      instead? Quarantine is one of Rule 1's protections and stays; a protection records
      each time it acts, so a missing field is added. The ladder's rungs and give-up point
      are tiered as above. A rejected rung and `_verify_discontinuities`' cold refits each
      pay the automatic moment-angle profile interval (20-32 refits an angle, 2.6-16.7 s on
      fits of 0.2-1.2 s; `strategy/parameter_interval.attach_stationary_intervals`) on a
      result the chain discards: gate them with `_auto_intervals = False` until an attempt
      is accepted (WP-2002, PR #1050; no gate in `sequential.py` on 2026-10-24).
      Answered 2026-10-24 (`2003-batch/README.md` § Quarantine's record): the pattern and
      its rung are on the record; the successors seeded from an earlier pattern are not,
      nor is the moment-floor carry. Proposed fields: `SeriesEntry.seeded_from` (the
      index whose fitted state seeded this pattern's warm rungs, `None` on a cold-only
      pattern) and `SeriesEntry.floored` (the moment paths floored before its warm start,
      from `_chain`'s local `floored`). Each is an action row a name new to the table
      cannot enter at `unaudited`, so they land with the quarantine's ruling in the batch.
      Fields landed 2026-10-26 (fourth session), tier 3 as ruled: `floored` names the kept
      attempt (empty when it started cold, X7), `SEQUENTIAL_UNRECOVERED` names where the
      successor started instead, `SEQUENTIAL_MOMENT_HOLD` reads `floored` and names every
      pattern. The interval gate landed with them: `_fit_one` declines it on every rung
      and verify refit, and the chain attaches it once to the kept attempt.
- [x] `FIRST_RUNG_FACTOR`'s invariance test (accepted values bit-identical with the bound
      on and off, on two chain families), replacing the comment's claim. 2026-10-24: the
      thermal ramp (`tests/test_sequential.py`) and the CPD chain (slow,
      `tests/test_acceptance_sequential.py`), both asserting the margin too. The row stays
      `unaudited`: the closing stage now hides a bitten first rung (clash table, below).
      Superseded in part 2026-10-25: the tests stand, but the invariance they assert does not
      hold everywhere. At the default 3.0 the bound cut planted T087's winning rung in its
      closing stage and moved its scale 39.3 esd (`2003-batch/clashes.md` X1); both tests
      run chains where the bound never bites a winner.
- [x] The clash table: reseed × rung × `_prefer` × width growth × the moment carry, both
      orderings where order matters; plus the carry policy × the width twin hold, the
      closing stage × path dependence, and 2002's B7 and B16 (Context). Found 2026-10-24:
      the first-rung bound × the closing stage (a truncated warm stage the closing stage
      converges reads `converged`, so WP-1127's forced escalation never fires);
      `reseed=False` × the forced escalation (`sequential.py:1561`, `1569-1571`: a bitten
      first rung escalates against a switch the caller turned off, against `reseed`'s
      docstring); the closing stage × the fence (cpd-1b escalates with it, not without it).
      Done 2026-10-25: `2003-batch/clashes.md` (`5212338`), fifteen clashes X1-X15, eleven
      measured on synthetic chains or read off the reseed JSONs.
- [x] The batch to the maintainer, each brief opening with its stakes line (the record
      § The rule, 2026-10-20); rulings dated into the table. Drafted 2026-10-25
      (`2003-batch/batch.md`, `86ffb9a`), not yet put to the maintainer: four picks are
      revised against DESIGN.md § Rules first (the 2026-10-25 handover's *Next*). Revised on
      main's numbers (`03ec3da`, a lane) and ruled 2026-10-26 (`ca3f354`): the maintainer
      delegated the rulings to the session's judgement against DESIGN.md § Rules, every pick
      approved, `on_error` kept at `"carry"`, tier 3.
- [ ] Approved demotions, each its own commit; `SEQUENTIAL_DISCONTINUITY` replaced by the
      `SeriesResult.steps` field and its help entry (no diagnostic), if the batch agrees; the
      release notes staged. C4 landed 2026-10-26 (fourth session, a lane): the code, its
      suggestion and three constants gone, `SeriesResult.steps` (every step in esds of the
      later fit, largest first) and `verify_steps: int` (C4 question 2, option (ii), the
      caller's *k*) in place of `verify_discontinuities`, schema 0.60 annotated, release note
      staged. The GUI's series panel still reads the route's `discontinuous` key, now true
      only for a verified step (`gui/src/lib/series.ts:65`, `Series.svelte:613`): plotting
      `steps` there is owed. C1, C3, C5, C6, C9, C10 owed.
- [ ] Goldens re-pinned only if no further from reference. A series golden's first
      reference is the cold-fit chain, rietx's own result on the same data, so it
      verifies and does not validate (DESIGN.md § Rules, 2). Where a series member has a
      certified value or a second engine's answer, that reference is measured too and
      the handover says which each number was held to.
- [x] Width-growth rulings handed to 2004 as an `### Inherited` entry there (2026-10-26).
- [ ] Tests + PNGs; the fast count moved by exactly the tests added.
- [ ] Skill: none here. List each `references/series.md` row (5 308 words) that names a
      demoted verdict, for 2008 (DESIGN.md § Rules, 3; the record § Decisions, the
      skill's role).

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_audit_table.py -q          # no sequential.py/multi.py row at unaudited
.venv/bin/python -m pytest tests/test_sequential*.py tests/test_multi*.py -q
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest -n auto --dist loadgroup                # once, final tree
```

The handover carries the three-family measurement for the reseed fence and the
quarantine, with the per-pattern table (WP-1124's rule: judged on the table, never a
summary).

## References

- `docs/milestones/generality.md`; WP-1051 (quarantine), 1127 (the first rung), 1016,
  1441, 1469 (the carve-out), 1329 (the moment carry), 1124 (the per-pattern table).
- Root CLAUDE.md § Series.

## Handover log

- **2026-10-30** (`/pr-review`) — family B's data merged from outside as PR #1163 (`c1214688`), after a rebase that kept #1162's README section first. `tests/data/seqrefine_cucr2o4/` holds 20 files, byte-identical to `SeqRefine/data/SeqTut.zip` in the GSAS-II tutorials repo at `924e9eb8`, under the GSAS-II licence: 17 CuCr₂O₄ + CuO patterns from APS 11-BM (λ = 0.413263 Å, 12 799 points each, header temperatures 6.778 to 288.7 K, seven patterns below the transition near 130 K and ten above), the tutorial's instrument `.prm` and its two starting CIFs. The set is 7.1 MB, and the contributor offered a ten-pattern subset at 4.2 MB. The reference values come from Suchomel et al. (2012, Phys. Rev. B 86, 054406), read as the preprint, and none from rietx or the tutorial. Gotchas: the tutorial cites no paper, so the link to the paper rests on composition, source and λ. The files' 0.002° step differs from the paper's 0.001°, so these are ramp scans of the same specimen and not necessarily Table I's scans. The CIF cells are GSAS-II values and not references. The new test (40 cases, about 1 s) runs no fit and plants no bad pattern, since family D carries those. No task is ticked. Gate (a stack of eleven PRs on main `b40bc994`, tree `307eff83`; macOS arm64, `[dev,jax]`, Python 3.12): 13 217 passed, 216 skipped, 48 xfailed, 0 failed, with ruff, the `-W` manual build and the GUI ladder green.

- **2026-10-29** (`/pr-review`) — family D's data merged from outside as PR #1162 (`843e27bf`): the Co₃O₄ D1B quench series under `tests/data/d1b_co3o4_quench/`, with its provenance, licence, errata and the planted known-bad patterns, which the test builds in memory. Review established two things for this WP. `read_pattern` passes a NaN block through with only `PATTERN_DEAD_CHANNELS` on two channels, so nothing names the NaNs (#1187 owns that, and the planted file is its fixture). And no code path sets `"diverged"` today, so the quarantine cannot fire on this family yet. Family B (#1163) waits on a rebase over this one's README section. No task here is ticked by it.

### 2026-10-26 (fourth session) — X16 fixed in the LM driver, X17 traced to a zero aperture, the quarantine's record, C4 demoted

The 40-pattern freeze (X16) was not a chain defect. It was a one-line tolerance bug in the
least-squares driver that any single fit could hit: once both Lorentzian width coefficients
sat at zero, the driver read every width limit as already broken, dropped them all, and the
next stage drove the width negative. That is fixed, and it moves no number in any default
configuration: every family and arm re-measured is bit-identical except the planted ramp
with the first-rung bound off, where the 40 frozen patterns now recover. X17's collapse has a
cause too: a warm start from a pattern whose two axial apertures both sit on their floor of
zero collapses the next fit, with or without the closing stage, and the default chain
escapes only because its own neighbour lands just off that floor. That needs a floor where
the parameter is live, which changes every fit freeing an aperture, so it is handed to
WP-1955 rather than fixed here. A series now records where each warm start came from and
which moments were floored, a discarded rung no longer pays the moment-angle interval, and
the discontinuity threshold is gone: every step is listed in esds and none is called a jump.

*Done.*
- Claimed (`158eace`; PR #1169 had merged, so the branch restarted from `origin/main`),
  draft PR #1183. `### Inherited` was empty; the findings checked were today's.
- **X16** (`0bd7823`). `optimize/lm.py` `LinearInequality.violated` judged "on the face"
  against the block's largest |slack| alone; the guards it names floor that scale at 1. A
  probe warm-started T088 from T087's state one part at a time from T086: X alone, Y alone or
  V alone recovered it. A builder log found T087's second solve starting at X = 3e-20,
  Y = −6e-19 and building no Γ_L row. Two regression tests, each confirmed to fail with the
  floor reverted. `clashes.md` X16 and `batch.md` investigation 8 rewritten (`4be3f98`).
- **Task 3** (`038ee92`, `f4785d3`): `SeriesEntry.seeded_from` and `.floored` (tier 3, the
  rulings' rows, help entries, manual rows); `SEQUENTIAL_UNRECOVERED` names where the
  successor started; `SEQUENTIAL_MOMENT_HOLD` reads `floored`; `_fit_one` sets
  `_auto_intervals = False` and the chain attaches the interval to the kept attempt (X10).
- **X17** narrowed (`d4e7196`, `e4bfdce`): `clashes.md` X17, `batch.md` investigation 9,
  handed to WP-1955.
- **C4** (`4bd5ab9`, a lane, below): `SEQUENTIAL_DISCONTINUITY`, its suggestion and three
  constants removed; `SeriesResult.steps` (every step in esds of the later fit, largest
  first, `None` last); `verify_steps: int` (question 2, option (ii)); the cold ratio on
  `SeriesStep.cold_ratio`; the plot shades verified steps only; an old document's
  `discontinuities` key dropped at read; schema 0.60 annotated; release note staged. Checked
  here: the lane's selection re-run green, its core read by range.
- Code review (`/code-review high --fix`, the branch): seven findings, five fixed
  (`c9c59b3`, `82eb24d`). Fixed: the backward chain's successor named in walk order, no step
  across a failed pattern, a cancel read after the interval, the hold message capped at four
  again (it now points at `SeriesEntry.floored`), an unexpected raise in the interval no
  longer ends the series, and the skill's seven lines naming the removed keyword or code
  renamed (an agent following them got a `TypeError`). Declined: `verify_steps=k` counts
  rows, so a cubic cell's tied a, b, c take three of k for one pair (the path guide asserts
  it; a "distinct pairs" count is a choice for C4's next touch); a requested verify step that
  could not be re-measured reads `cold_ratio=None`, the same as one not requested (needs a
  field).
- `measure_reseed.py` records the ten largest `steps` in place of the flagged pairs; every
  family re-measured on the fix (`aa40cdc`, `ae876a0`, `c0f4151`-`20c3047`).

*Measured* (Linux x86-64, 4-core cloud container, worktree venv `[dev]`, one BLAS thread).
- The X16 fix against the committed JSONs (`6eb010a0`), every family and arm: planted
  `off_nobound` T088-T127 recover (moved up to 434 esd; T088 Rwp 0.04155 against 0.43341),
  later patterns ≤ 5.5e-4 esd; `on_nobound` ≤ 0.172 esd (T087's scale); `ref` 0.007 esd at
  T087. Every other arm of all nine families bit-identical, `cpd-noclose_status_runaway`
  included. Arms new to the record (no-bound arms on cr2wo6, tut05, cpd-ftolnone): written,
  no prior to compare.
- X17 probe (closing stage off unless named; from an independent 1b, Rwp 0.13932, S/L and
  H/L both 0): 1c warm 10.724 (S/L 64.8, corundum 3.7 wt %); closing on 0.79140 (S/L 4284,
  fluorite 0.0 wt %); S/L lifted to 0.011, 0.10881 in 39 evaluations (independent 0.10901).
- Fast suite on the X16 fix alone: 11 842 passed, 284 skipped, 32 xfailed, 31:27, nothing
  else running (one BLAS thread; the first attempt with BLAS threads unset reached 37 % in
  30 min and was killed).
- The final tree, `origin/main` merged in (`70d133f`), alone on the machine, one BLAS thread:
  fast selection 1 failed, 11 850 passed, 284 skipped, 32 xfailed (28:44); the slow tier
  (`-m slow`) 3 failed, 408 passed, 19 skipped, 15 xfailed (1:09:03). The fast failure was this
  branch's: the series guide's quoted summary lacked C4's `largest step` line; fixed
  (`docs/docs/guides/series.md`), and all 24 guide-script cases then pass. The three slow
  failures are red on `main`'s nightly of 2026-10-26 (`7b5181bb`, run 40317456318, the full
  suite job) with the same messages and numbers: `test_the_axial_sizing_floor_does_not_change_the_answer[lab6]`
  (8.820 esd on `axial_sl`), `test_a_wrong_triclinic_le_bail_fit_raises_no_degenerate_cell_error`
  (`ValueError: array must not contain infs or NaNs`) and `test_suite_alarms` (one warning fewer
  per result under every purpose). Not this branch's, not fixed here.
- Count: passed+skipped 12 126 on the X16 commit, 12 134 + the fixed case on the final tree.
  The +9 is this branch's added tests (22 added names, several replacing the removed scan's)
  together with `main`'s two merged commits; not separated. Added tests' cost (`added_test_times`,
  the local junit, this machine): 35.87 s over 22; `test_the_background_step_is_the_largest_step_of_its_constant`
  26.93 s, the planted fixture's rename of the scan test it replaces, at that test's cost; the
  chain's interval test 5.17 s (stubbed; 70 s with the real interval); the rest under 2.5 s.
- Lanes (`session_usage.py lanes 5442497d-…`): main 217 requests, peak 471K, $22.77; one
  lane $15.38.

  | lane | est | requests | main at dispatch | re-read | lane $ | saved $ |
  |---|---|---|---|---|---|---|
  | C4-steps | 40 | 165 | 416K | 1K of 2K | 15.38 | +8.03 |

  Trial row appended. Baseline replay, the selective policy (u = 1K): 0K-300K +0 %,
  300K-450K +0 %, 450K-up +36 % (two sessions).

*Gotchas.*
- One BLAS thread per worker is not optional on this container: the fast suite took 31 min
  with it and reached 37 % in 30 min without (`OPENBLAS_NUM_THREADS=1`).
- `planted` runs with the compiled tier off (`numpy_path`); a probe of it must say so.
- `measure_reseed.py` broke on `result.discontinuities` the moment C4 landed; a family run
  started before a schema change finishes on the old code (one process per family).

*Generality.* The `generality-review` judge's sections, unedited, are in
`2003-batch/generality-2026-10-26.md` (15 KB, kept out of this file, which successors read
whole). Nine items, none `fails`:
1. `SeriesEntry.seeded_from`, tier 3: holds (rows weak on the X17 failure case, a tier
   disagreement with `batch.md` C2's "tier 1, a record", and `None` meaning "not recorded" too).
2. `SeriesEntry.floored`, tier 3: holds (evidence should cite Ba₂FeSbSe₅, not Cr₂WO₆, which
   seeds no successor; C8's injected-divergence test is owed).
3. `fit:verify_steps`, caller: holds. 4. `NOISE_FLOOR_REL`, tier 1: holds.
5. `SEQUENTIAL_DISCONTINUITY` and its constants deleted: holds (no agent run on the demotion).
6. `fit:verify_discontinuities` deleted: holds. 7. `LinearInequality.violated`'s floor: holds
   (`_ON_FACE`'s row text is stale).
8. The interval gate: **weak**. Author: the swallow leaves no record; narrowing it, or a
   finding naming the pattern, rides the next commit to `_chain` (Next 3).
9. `_series_steps`: **weak**. Author: right on the above-fence drop, which `rows.json` ruled
   out with the scan and the lane kept (the planted transition is masked, `_MASKED`); and on
   the later-only esd, where the removed scan used the combined one. Both are C4 follow-ups,
   Next 2.

*Next*, in order:
1. C1 and C3, now unblocked by X16: the Rwp fence becomes a reported ratio and a warm fit
   escalates only on diverged or raised (C1); `first_rung_factor=None` by default with its
   two defects fixed (C3), and X2's no-budget-under-`reseed=False`. Re-run planted
   `off_nobound` as C3's check: it is now the default it would become.
2. C4's follow-ups from the judge (items 8-9): drop the above-fence exclusion from
   `_series_steps` as `rows.json` ruled, size a step over the combined esd √(σ₁²+σ₂²), and
   record a failed interval rather than swallow it; then the two declined review findings
   (`verify_steps` counting tied rows, a failed verify reading as not requested). Then C2's
   question 5 arm (an `error`-level kept attempt read as diverged) on tut05-broken and CPD
   closing off, and C2's ranking fix (diverged below truncated).
3. C5, C6, C9's carry-invariance test, C10's joint hold row; each its own commit with its
   `_audit.py` row. Then goldens (task 8), tests (task 10) and the skill list (task 11: the
   seven renamed lines are in WP-2008's Inherited).
4. The two declined review findings on `verify_steps` when C4 is next touched.

### 2026-10-26 (third session) — re-measured on main, revised against DESIGN § Rules, ruled

On `main` (after WP-2045) the chain no longer needs any trigger beyond divergence, so the batch
now takes that as its first ruling. Every family was re-run: the Rwp fence's one rescue is gone
with the runaway it caught, and its 116 escalations move nothing, at 4.1× the evaluations on
planted. Escalating on `max_iter` changes nothing on any family. Escalating on a cell runaway
restarts one good fit, and in the closing-off variant it rescues a pattern and then lets the
chain collapse unnoticed. The first-rung bound moved one accepted value, toward the truth. Two
chain defects surfaced and are filed as investigations, not fixed: a 40-pattern freeze when the
bound is off, and a collapse warm-started from a floored row. The maintainer delegated the
rulings to the session's judgement against DESIGN.md § Rules. Every pick in the revised batch is
approved, `on_error` keeps `"carry"`, and the ordering matters: C1 and C3 land only after X16 is
fixed.

*Done.*
- Claimed (`8f88166`; PR #1156 had merged, so the branch restarted from `origin/main`); draft
  PR #1169. Inherited from WP-2045 folded into Context as a dated superseded-in-part note
  (`837dbd6`); its content was the measurement this session re-ran.
- Every family and arm of `measure_reseed.py` re-run on main (`3c45728`-`0f70a7f`), CPD on all
  eight patterns now that its chain takes ~41 s (it took 2 310-2 617 s an arm before WP-2045).
  All 62 JSONs written over, none pre-2045 left.
- A lane added option (iii) as the arm `status_runaway`, the no-bound arms and `cpd-ftolnone`
  (`7e03411`), and ran them on every family.
- A lane revised `batch.md`, `clashes.md` (X16, X17; X1-X5 and X13 superseded in part),
  `rows.json` (23 proposals), `classes.md` and `README.md` (`03ec3da`). I checked its three
  corrections of my own readings off the JSONs; all three hold. (1) Planted T088 under
  `on_nobound` is a rescue by the fence: the warm rung froze at Rwp 0.4334, `warm_staged`
  raised a LinAlgError, and the cold rung recovered at 0.04155. (2) CPD's 7-14 esd
  `lor_strain` gap from the independent fits is (iii)'s alone; `status`'s worst path is
  `profile.v`, 2.89-5.59 esd. (3) `axial_sl` sits on its floor at 0 in the independent 1b too
  (esd 253), and 1c's `MODEL_FAR_FROM_DATA` is raised at `error` (`refine.py:9021`).
- Rulings (`ca3f354`): a dated section heads `batch.md`, and every pending entry of `rows.json`
  (94) carries `ruling`. `fit:on_error` and `_chain.on_error_carry` are tier 3.
- `reseed.md` re-rendered. WP-2004 Inherited: C7's width-growth ruling, and its Priority
  re-rated. The 2026-10-25 trial row appended to `process.md`.
- Code review (`/code-review high --fix`, on `measure_reseed.py`, the branch's only code): ten
  findings, nine fixed (`0297842`). The reference arms now carry the chain's labels; the
  trigger family stored `p000` ten times, and its `ref` was re-run bit-identically to fix it
  (`598a355`). The table no longer breaks past a cut or without an `on` arm. The venv is read,
  not asserted. CLI edge cases are refused. Partly fixed: a pattern whose every rung raised
  still charges its cost to the next row, which now names it (`charged_failures`). `--table`
  output is byte-identical over the committed JSONs.

*Measured* (Linux x86-64, 4-core cloud container, worktree venv `[dev]`, compiled tier on, one
BLAS thread; escalated patterns, summed evaluations):

| family | on | status | off | (ii) | (iii) | on_nobound | off_nobound |
|---|---|---|---|---|---|---|---|
| CPD (8) | 0, 644 | 0, 644 | 0, 644 | 0, 644 | 1 (1b), 785 | 0, 644 | 0, 644 |
| CPD closing off | 0, 708 | 0, 708 | 0, 708 | 0, 708 | 1 (1b), 2 957 | — | — |
| planted | 115, 13 034 | 1, 3 165 | 1, 3 165 | 1, 3 165 | 1, 3 165 | 115, 13 083 | 0, 3 906 |
| planted null | 0, 2 143 in every arm | | | | | | |
| trigger | 0, 275 in every arm | | | | | | |
| Cr₂WO₆ | 0, 482 in every arm | | | | | | |
| tut05-jump | 0, 634 in every arm | | | | | | |
| tut05-broken | 1, 162 | 0, 138 | 0, 138 | 0, 138 | 0, 138 | | |

- CPD 1b on main: warm rung kept in every arm but (iii), converged at Rwp 0.13984 (independent
  0.13732), corundum 94.32(23) wt % against 94.31 weighed, *a* 4.75801(41) Å against the
  independent 4.75809(38), `CELL_RUNAWAY` still firing. Under (iii) it is kept at `warm_staged`:
  94.24(23), 0.135 esd. With the closing stage off, (iii) rescues 1b (94.26(24)). 1c then
  collapses: Rwp 10.83 `converged`, zero shift −6.33°, corundum 3.9 wt %. 1d-1h end `max_iter`
  at corundum 55-73 wt % (X17).
- First-rung bound: it moves only T087. With the bound, scale 0 (truth 0) and worst key path
  1.54 esd. Without it, the zero shift is −0.0231(48) against a true 0.006, 6.06 esd off.
  Under `off_nobound`, T088-T127 freeze at scale 7.35e-8, Rwp 0.433 against 0.042 (X16).
- `cpd-ftolnone` against `cpd`: ≤ 2.1e-4 esd, so X13 is moot.
- Reproducibility: `cpd-noclose_status_runaway` and `trigger_ref`, each run twice in separate
  processes, are bit-identical pattern for pattern.
- Lanes (`session_usage.py lanes 000445b0-…`): main 141 requests, peak 299K, $9.07; two lanes, $22.06.

  | lane | est | requests | main at dispatch | re-read | lane $ | saved $ |
  |---|---|---|---|---|---|---|
  | new-arms | 25 | 101 | 179K | 26K of 39K | 8.12 | +4.21 |
  | batch-revision | 40 | 117 | 253K | 64K of 107K | 13.94 | +7.79 |

  Trial row appended. Baseline replay, the selective policy (u = 45K): 0K-300K +0 %, 300K-450K
  +0 %, 450K-up +23 % (one session each).
- Tests: none added; the branch changes no `src/` or `tests/` file, so neither selection moves.
  Neither selection was run; `test_docs_consistency.py` and ruff were (step 10).

*Gotchas.*
- `gh` does not answer in this container; the GitHub MCP tools stand in.
- The measurement loop starts one process per family, so a lane's edit to `ARMS` reached my
  later families mid-loop. The runs are deterministic, so the duplicate JSONs matched.
- A worker restart moved the session to the main checkout. `EnterWorktree` with the tree's
  `path` re-enters it.
- The worktree guard refuses inline Python that names the VCS. Write the helper to the
  scratchpad instead.
- A lane wrote over two of my scratchpad helpers; lanes share the scratchpad.

*Generality.* Not dispatched. `_audit.py` is untouched on this branch. The rulings sit in
`rows.json` and reach the table with task 7, and that branch's handover dispatches the judge
over each row. The session wrote those tiers itself under delegation, so the judge's read is
owed there.

*Next*, in order:
1. X16 (the 40-pattern freeze under `off_nobound`, planted T088-T127) and X17 (the warm refit
   from 1b's floored `axial_sl`, cpd-noclose 1c). Reproductions and both hypotheses are in
   `clashes.md` and `batch.md` § Investigations owed. They come first because C1 (i) and C3 (a)
   both reproduce X16 in the default chain until it is fixed. A fix in `sequential.py` is this
   WP's.
2. Task 3's fields (`SeriesEntry.seeded_from`, `.floored`) and C2's question 5 arm (`status`
   with an `error`-level kept attempt read as diverged, on tut05-broken and CPD closing off).
3. Task 7, the approved demotions, each its own commit with its `_audit.py` row: C4's
   `SeriesResult.steps`, C5, C6, C1's ratio field and `RESEED_FACTOR`'s removal, C3's
   `first_rung_factor=None`, after 1; C9's carry-invariance test; C10's joint hold row. Then
   goldens (task 8), tests (task 10) and the skill list (task 11).

### 2026-10-25 — the batch drafted (a practice survey, a proposal for every row, the clash table, a fourth trigger arm); its picks not yet checked against DESIGN § Rules, so not sent

Every decision a series or a joint fit makes now has a proposed tier, and the 17 that needed no approval are in the table. A survey of the seven programs found that none restarts a pattern by itself, compares a chain with its reverse, or tests the step between neighbours, so nearly every chain action here is rietx's own. Two measurements change what the last session left. The Rwp fence's one real rescue, CPD 1b, is caught bit for bit by escalating a warm rung that ends unfinished, without the fence's 115 idle escalations elsewhere, though that rule has its own dissenter on disk (Cr₂WO₆ at 150 K, restarted twice for nothing). And the first-rung budget, filed as answer-invariant, moved an accepted value at its default (planted T087's scale, 39.3 esd), so it cannot be tiered invariant as built. The batch is drafted but was not put to the maintainer. Asked whether its picks were judged against DESIGN.md § Rules, the honest answer was not fully: four picks need revising first, listed under *Next*. And `main` moved under the batch: WP-2045 landed while it was being written, so the stage before the closing stage now converges, and on CPD no pattern after 1a leaves its warm rung. The fence's one real rescue, which the C1 brief rests on, does not happen on `main`. Every closing-on chain number here predates that fix and is re-measured before anyone rules.

*Done.*
- Claimed (`b8ff437`): PR #1150 had merged, so the branch restarted from `origin/main`. The push was a fast-forward, the old tip being an ancestor of main; the classifier refuses a force-push. Draft PR #1156. The Context's tier line (`bb46ef3`): this WP adds no rule of its own; the fields it plans are records, and whatever picks `verify_discontinuities`' pairs is tiered before it lands. No offered family had landed (`tests/data` holds no CuCr₂O₄, Co₃O₄ or Ba₂FeSbSe₅; #1073 open).
- `docs/practice.md` § Sequential refinement (`773a873`, a lane): GSAS-II 5.8.4, EasyDiffraction 0.21.1 and MAUD 3.07 read in source; FullProf, TOPAS and Profex inferred from search excerpts, their hosts refused (only GitHub and PyPI answered); RIETAN-FP and BGMN not reached. The lead checked two load-bearing claims in the fetched source: `Copy2Next` and `Reverse Seq` default `False` (`GSASIIobj.py:22`), and EasyDiffraction propagates only a successful fit (`sequential.py:1251-1262`).
- Task 2's tiering half (`7c37469`, a lane): `2003-batch/rows.json` (111 proposals) and `classes.md` (eleven classes). Seventeen rows written into `_audit.py`: tier 1 `SERIES_PATTERN_FAILED`, `SIZE_NORMALISED_ACROSS_WAVELENGTHS`, `STAGE_FREED_NOTHING` (each with its suggestion) and `NOISE_FLOOR_REL`; tier 2 `fit:mode` and `fit:two_theta_limits`; caller `SEQUENTIAL_CANCELLED`, `SEQUENTIAL_PATH_CHECK_INCOMPLETE`, `PARAMETRIC_OUT_OF_RANGE` (each with its suggestion), `fit:prepare` and `fit:constrain`. Five codes got their response (off `RESPONSE_BASELINE`); `SEQUENTIAL_PATH_CHECK_INCOMPLETE` did not, raising at two levels.
- `measure_reseed.py` gains the `status_maxiter` arm (`ded5c3f`): status-only, plus escalating while the ladder's best attempt so far ends `max_iter` (so a warm `max_iter` no later rung displaces climbs to the last rung, as on Cr₂WO₆), by wrapping `_reseed_needed` for that run alone. Run on all eight families (`dd13648`, `634bede`).
- The clash table (`5212338`, a lane): `2003-batch/clashes.md`, X1-X15.
- The batch (`86ffb9a`, a lane): `2003-batch/batch.md`, 47 KB, eleven classes, each opening with its stakes line, plus seven fixes that need no ruling and an appendix.
- Task 4 annotated as superseded in part (X1), task 5 ticked, tasks 2 and 6 annotated with what is left.
- Code review (`/code-review high --fix`), nine findings, eight fixed (`34f0202`). (1) The three codes given `response="warning"` (`PARAMETRIC_OUT_OF_RANGE`, `SEQUENTIAL_CANCELLED`, `SERIES_PATTERN_FAILED`) had no fire/silent pair, so `tests/test_silence.py` was red on the branch; the pairs are added. (2) `SEQUENTIAL_CANCELLED`'s `scope=("series",)` made a cancel `info` under every other purpose; it is now `("all",)`. (3) Both codes' `responds` now say what each means for the forward and the backward chain. (4) `PARAMETRIC_OUT_OF_RANGE` reads the schema's default bounds where the caller set none, and now says so. (5-8) Citations corrected, and `measure_reseed.py`'s `status_maxiter` docstring fixed: the arm escalates while the ladder's *best attempt so far* ends `max_iter`, which is why Cr₂WO₆ climbed all three rungs. Declined: whether `SEQUENTIAL_CANCELLED` stays `caller` when every recorded series carries a token (`sequential.py:1275`) is a tier question for the batch.

*The design-principle check* (the maintainer's question, 2026-10-25, answered in the session against `docs/DESIGN.md` § Rules 1-4; the batch is unrevised).
- Holds: C3 (the budget becomes the caller's), C4 (`SeriesResult.steps`, Rule 1's own third-kind example), C5, C6 and C7 (each threshold decides existence and has no source), C8 (the moment floor, no dissenter), C11, and C2's first two questions (the quarantine; a finite attempt over a diverged one).
- **C1 fails Rule 1's unanimity gate on its own evidence.** "Escalate on `max_iter`" has a dissenter on disk: Cr₂WO₆ 150 K ran out of iterations at a good answer, where a refiner extends the fit rather than restarting it cold. The trigger that matches Rule 1 acts only on facts every refiner reads as failure: diverged, raised, or a guard already ruled first-kind firing (`CELL_RUNAWAY`, B8). That is the batch's option (iii), unmeasured; `max_iter` alone is then reported (`STAGE_MAX_ITER` already does) and not acted on. The brief also never cites Rule 4 against today's fence, which compares one pattern's Rwp with other patterns': "an Rwp comparison is never its evidence".
- **C2's `_prefer` ranks by Rwp, which is the objective only up to the penalty and restraint rows Rwp leaves out.** The arithmetic criterion is the full cost.
- **C2's `on_error="carry"` and C9's `carry` are each "tier 2 with the dissent named"**, against the record's "a dissent counts" for a default that switches on an action. `carry` reads better as Rule 1's first pick case: the caller asked for a warm-started chain by calling `refine_sequential` by name. The package's choice is then only *what* is carried, every entry against only the varied ones, which differ only where a fixed value moves and can be tested for invariance. `on_error` needs a real question to the maintainer, not a pick.
- **C10 calls the joint absent-phase hold "covered by B1", and it is not.** It judges support by `phase_support` (`multi.py:413-417`), not B1's 3σ scale significance, so it needs its own row.
- **Rule 2.** The stakes lines do not say which reference validates (a weighed composition) and which only verifies (the independent fit, the unbounded chain). C3's T087 move is not measured against the planted truth.
- **A correction to C1's and C9's mechanism.** The batch says "the closing stage on a warm refit made CPD 1b's runaway" (X3). The JSONs record no per-stage Rwp, and WP-2045's macOS probe shows the declared warm stage already ending "converged" at Rwp 0.760. Here that stage stopped at 136 evaluations as an intermediate stage (`intermediate_ftol` 1e-6), against 410 to Rwp 0.1633 as the last stage. The likelier cause is the looser stop the closing-stage schedule gives the warm refit, which is X13's open arm, not the closing stage's own solve. WP-2045 has since built that reading (#1161, merged before this handover: the last declared stage converges), and its Inherited entry above says cpd-1b now stays on its warm rung. A forward reference this session wrote into WP-2045 saying the same was dropped at the merge, since that WP had consumed its Inherited section.

*Measured* (Linux x86-64, 4-core cloud container, worktree venv `[dev]`, compiled tier on, `OPENBLAS_NUM_THREADS=1`).
- The fourth trigger arm, by family (escalated patterns, summed evaluations), beside the earlier three:

  | family | on (fence) | status | off | status_maxiter |
  |---|---|---|---|---|
  | trigger | 0, 269 | 0, 269 | 0, 269 | 0, 269 |
  | tut05-jump | 0, 551 | 0, 551 | 0, 551 | 0, 551 |
  | tut05-broken | 1, 157 | 0, 135 | 0, 135 | 0, 135 |
  | planted null | 0, 2 080 | 0, 2 080 | 0, 2 080 | 0, 2 080 |
  | Cr₂WO₆ | 0, 873 | 0, 873 | 0, 873 | 1, 2 582 (150 K differs by ≤ 0.087 esd) |
  | planted | 115, 11 790 | 1, 2 716 | 1, 2 716 | 1, 2 716 |
  | CPD, closing off | 0, 708 | 0, 708 | 0, 708 | 0, 708 |
  | CPD, first 2, closing on | 1 (1b), 796 | 0, 703 | 0, 703 | 1 (1b), 796, `values_sha` equal to `on`'s |

  `status_maxiter` matches `status` pattern by pattern (`values_sha`) except the two rows marked. cpd-1b under it: rungs `[warm, warm_staged]`, kept `warm_staged`, Rwp 0.13779, 629 evaluations, sha `bca5f63866`, as under the fence.
- The clash lane's runs (synthetic chains, one BLAS thread): planted with the bound at 3.0 against `None` under `reseed=False`. T087's warm stage took 24 evaluations and its closing stage 43 against a per-stage cap of 32; the escalation kept `warm_staged` at Rwp 0.048071 against 0.047958, and T087's scale moved 39.3 esd. Nothing after T088 moved past 7.3e-6 esd, and T087's winning rung is 6.7× the running maximum. Path dependence, `direction="both"`, largest gap with the closing stage on and off: thermal 0.00105σ and 0.0177σ, jump 2.4e-4σ and 9.0e-3σ, trigger 0.351σ and 0.379σ, with no flag either way. B7 (`intermediate_ftol=None` against the default) at most 2.7e-4 esd on the three. The soak's fence arm climbed all three rungs on four patterns (254 evaluations against 71), values within 5.1e-5 esd.
- Wall clock (context only): cpd-1b's closing-on warm rung took 2 310-2 617 s in every arm, all four at one BLAS thread, so the thread setting does not remove its cost. The rest of a family ran in seconds to a minute.
- Lanes (`session_usage.py lanes 2e162871-…`): main 88 requests, peak 363K, $8.15; four lanes, $31.70.

  | lane | est | requests | main at dispatch | re-read | lane $ | saved $ |
  |---|---|---|---|---|---|---|
  | practice-survey | 35 | 107 | 232K | 0K of 74K | 7.73 | +3.30 |
  | tier-proposals | 80 | 101 | 262K | 27K of 94K | 9.67 | +4.35 |
  | clash-table | 50 | 109 | 307K | 0K | 8.71 | +5.46 |
  | batch-draft | 25 | 55 | 326K | 0K of 10K | 5.59 | +2.95 |

  Trial row `| 2026-10-24 | 2e162871 | 4 | 0 | 0K | 5 | 17K | 2.19 | 0 / 0 | +16.05 | +29% |` appended to `process.md`. Baseline replay, the selective policy (main > 150K and item ≥ 20): 5 sessions, +3 %.
- Tests: `tests/test_audit_table.py`, `test_help.py` and `test_answer_invariant_defaults.py`, 65 passed (61 s, serial), after the table edits; with the review's fixes, `test_silence.py`, `test_audit_table.py` and `test_help.py` 63 passed (74 s).
- Fast selection on the branch before main was merged (`b1dd41d`; no other suite running): 11 659 passed, 284 skipped, 27 xfailed, 1 failed, 33:08. The one failure is `test_examples.py::test_every_guide_script_prints_what_its_page_quotes[moment]`, red on Linux x86-64 before this branch (WP-2036's Inherited, from WP-2037), and this branch does not touch it. Added: three cases, `test_silence.py::test_a_warning_fires_on_its_fault_and_stays_silent_beside_it[…]` for `PARAMETRIC_OUT_OF_RANGE` (0.15 s), `SEQUENTIAL_CANCELLED` (0.73 s) and `SERIES_PATTERN_FAILED` (4.26 s), counted by name in the junit file. `tests.added_test_times` counts 0, the test function being older than its new ids. The 4.26 s case runs a three-pattern series with every rung of one pattern raising. It is not `slow` because `test_silence` must cover every warning code in the fast tier. Main's count was not measured (CI's job), so +3 is by name, not by subtraction.
- Full selection: not run, since the branch moves no measured number (table data and responses, a silence pair, docs, measurement JSON, a script under `docs/`).
- The merged tree (main at `f6a85bb`'s merge, WP-2045 included): `test_docs_consistency.py`, `test_audit_table.py`, `test_silence.py` and `test_help.py` 88 passed (66 s), ruff clean. The fast selection was not re-run there; CI runs it on the PR.

*Gotchas.*
- `gh` is not available in this container, so `wp_claim.py`'s pull-request half and every `gh pr` step fail; the GitHub MCP tools do the same jobs.
- A worker restart moved the session's working directory to the main checkout; `EnterWorktree` with the tree's `path` re-enters it.
- The worktree guard refuses a shell line that runs `find` or `python` through a `$VAR` in a loop; split it into plain commands.
- After the branch moved onto main's 1.11.0.dev0, the editable install's metadata still read 1.10.0.dev0; a reinstall fixed it.
- `measure_reseed.py --family cpd` needs `--first 2` to match the earlier status and off arms; a full eight-pattern closing-on chain is about an hour an arm.

*Generality* (the `generality-review` judge on the 17 rows and the three silence pairs; its sections pasted unedited, item headings as bold lines).

**`SERIES_PATTERN_FAILED` (+ `.suggestion`): tier 1, response `warning`**

**Verdict: weak.** The case for the tier is stronger: the code reports a fact, and no refiner would want a failed pattern hidden. The `warning` response is the weak part. On its backward-chain branch it duplicates another code that reports the same fact at `info`.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "fires exactly when every rung the chain tried on a pattern raised, one per SeriesFailure (sequential.py:2244-2278); the policy that carries on past it is SequentialRefinement.fit:on_error's own row, still unaudited" (row `evidence`). A rung is one attempt in the chain's restart ladder. | Confirmed at `sequential.py:1328` (forward) and `:1410` (backward). It reports a fact and gates nothing. The choice to carry on past the failure belongs to `on_error="carry"`, which is the default (`_audit.py`, `fit:on_error` value `"carry"`), so this fires on the default path. | agrees |
| 2. Ambiguity kind | `ambiguity=1` | Kind 1: whether every rung raised is a fact. | agrees |
| 3. Case against | dissenter "none found" (`rows.json`) | Against the tier: none found. Against the response: on the backward branch (`pass_name="backward"`, the reverse chain that `direction="both"` runs only to check path dependence) the message itself says "The reported forward entry stands" (`:2264-2267`). The same failure also raises `SEQUENTIAL_PATH_CHECK_INCOMPLETE` at `info` (`_path_check_coverage`'s `missing` list, `:2215-2226`). So one fact is a `warning` under one code and `info` under the other. generality.md § Attention is a cost, clause 2, says "where two consequences genuinely differ there are two codes". The row's `responds` names both consequences in one sentence. | response weak on the backward branch |
| 4. Case for | `responds`: on the forward chain, read the pattern's place in every trajectory "as a gap rather than a measurement" | On the forward chain the pattern has no entry at all (`:2269-2270`), and a trajectory read as a curve would bridge the gap silently. A warning before quoting a trajectory is earned there. | strong (forward) |
| 5. Tier and source | tier 1, "arithmetic" | Right: it counts raised rungs. The suggestion ("Fit this pattern on its own and read the exception", `:2277`) is the one next step anyone would take. | holds |
| 6. Dataset families | n/a | No threshold. | n/a |
| 7. Record that it fired | the code itself | The code, plus `SeriesResult` failures (`failures=`, `n_failed`). `where` is a pattern label, not a parameter path, so `level_under` (`schemas/results.py:1527-1531`) falls back to the empty `scope` and reads `warning` under every purpose, the same as `SEQUENTIAL_CANCELLED`'s `("all",)`. | adequate |

Would change the verdict: either a separate code (or `info`) for the backward branch, or a reason why a backward-only failure owes the same response as a forward gap.

**`SIZE_NORMALISED_ACROSS_WAVELENGTHS` (+ `.suggestion`): tier 1, response `info`**

**Verdict: holds.** The case for is stronger. The scaling it reports is Scherrer physics, and the code states an action without adding a verdict.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "states that conversion and is silent while no scaled term is off zero (multi.py:2249-2300; WP-1131, WP-1343)" | Confirmed (`multi.py:2268-2278`). The diagnostic decides nothing. The action it reports, sharing one size column across wavelengths through `SIZE_LAMBDA_POWER`, sits in `params/multi.py` and is not this item. | agrees |
| 2. Ambiguity kind | `ambiguity=1` | Kind 1: the λ and λ² powers are fixed by the definitions of the size coefficients. | agrees |
| 3. Case against | "none found" | Against the statement: none found. A point for the maintainer: § Attention is a cost, clause 1, says a diagnostic earns its place when "a careful refiner does something different when it fires", and the row's `responds` opens "nothing to correct". It does fire only on multi-wavelength joint fits with a freed size term, so it separates fits. From memory and unchecked here: GSAS-II keeps size per histogram-phase pair by default. That bears on the sharing default, not on this code. | channel question, not a tier question |
| 4. Case for | the docstring's WP-1076 history: before WP-1131 "the fit reported converged… and nothing named the cause" (`multi.py:2252-2261`) | Without it, a reader takes `phases.0.lor_size` (the Lorentzian size coefficient) as the number for histogram 2. The message carries every histogram's factor and value, so the reader can convert without a rerun. | supports |
| 5. Tier and source | tier 1, "physics: … (180/pi)K lambda/L and the Gaussian one its square (Scherrer…)" | Matches root CLAUDE.md § Invariants (WP-1131/1343). | holds |
| 6. Dataset families | n/a | No threshold. The zero test is exact. | n/a |
| 7. Record that it fired | the code | The code, with `value` = largest factor over smallest. | adequate |

Would change the verdict: a ruling that a statement with "nothing to correct" belongs in a record field plus help text rather than a code.

**`STAGE_FREED_NOTHING` (+ `.suggestion`): tier 1, ambiguity 3, response `info`**

**Verdict: weak.** The tier and kind are right: the code computes a fact and leaves the intent to the caller. The `info` response, though, rests on a case (the stage was meant for one histogram) whose frequency is not given. The one measured case is the other one, where the plan missed what it meant to free.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "names the histograms a stage's globs matched no row of while matching another's… states and gates nothing, since one histogram can be the intent (issue #265, WP-1414)" | Confirmed (`multi.py:2539-2584`). `where` is the globs. Joint fit only. | agrees |
| 2. Ambiguity kind | `ambiguity=3` | Kind 3 fits: intent is outside the pattern. Tier 1 statistic with a kind-3 reading has the same shape as `QPA_FRACTION_RANGE`. | agrees |
| 3. Case against a warning | `responds`: "nothing, where the stage was meant for the other histograms" | The docstring's example is "a hump declared on one histogram is reached on one side only" (`:2552-2553`). How often that is the intent: **none given**. A one-histogram stage scoped as `hist.<k>.…` is already excluded upstream, which narrows the intended case. | thin |
| 4. Case for a warning | none given | Issue #265, quoted in the docstring (`:2543-2548`): a plan written with `instrument.profile.*` freed no width on any bank, and the joint fit "said converged at Rwp 0.115 where globs naming the banks' own rows gave 0.066". This is clause 2's own wording for a warning: "the plan did not reach what it asked". At `info` the default view prints it as one line. That Rwp figure is a cost, not threshold evidence. | real, uncited in the row |
| 5. Tier and source | tier 1, "arithmetic" | Right for the statistic. | holds |
| 6. Dataset families | n/a | No threshold. | n/a |
| 7. Record that it fired | `StageResult.unreached_histograms` | Confirmed as the source it reads. | adequate |

Would change the verdict: a count, over the joint-fit examples or suites, of unscoped one-histogram misses that were intended against ones like #265 that were not.

**`rietx.sequential.NOISE_FLOOR_REL` = 1e-9: tier 1**

**Verdict: holds.** The case for is stronger. It is a numerical floor several decades below any measured step, and no case where it would hide a real step was found.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "a step or a between-chain gap under 1e-9 of the parameter's magnitude (never under 1e-9 absolute, sequential.py:2290)" | Used at `sequential.py:2410` (the discontinuity scan's median step), `:3041` and `:3046` (path dependence), and `gui/series.py:403`. Below the floor a ratio test is skipped. | agrees |
| 2. Ambiguity kind | not required on a constant row | Kind 1. | — |
| 3. Case against | none given | I looked for a parameter whose real steps fall under 1e-9 × max(1, magnitude): a synchrotron cell (relative esd about 1e-6), λ, TOF `difc` (a time-of-flight calibration constant), background coefficients. None found. The row's "five decades" is a lab figure (CPD corundum, 8e-5). At synchrotron precision the margin is nearer 2.5-3 decades, still ample. | none found |
| 4. Case for | the comment (`sequential.py:231-242`): an unrefinable `profile.y` "read as a 29 000x step and 1e16 sigma of path dependence" | Quoted correctly. The comment dates that failure to before WP-1938. | supports |
| 5. Tier and source | tier 1 "numerical floor" | generality.md tier 1: "A numerical floor such as `rcond` belongs here." No test pins it: no file under `tests/` names `NOISE_FLOOR_REL` or `_noise_floor`. | holds; no test |
| 6. Dataset families | one esd quoted (CPD) | Not a tuned threshold, so families do not apply. | n/a |
| 7. Record that it fired | none given | Silent by design: a skipped ratio leaves no record. | acceptable for a floor |

Would change the verdict: a refined parameter in any family whose real step or chain gap is below 1e-9 × max(1, |value|).

**`rietx.sequential.SequentialRefinement.fit:mode` = `"rietveld"`: tier 2**

**Verdict: holds.** The case for is stronger. It copies the single fit's tier-2 row and passes the value through unchanged.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "handed to each pattern's fit unchanged (sequential.py:1799)" | Confirmed. The GUI passes `p.doc.mode` (`gui/session.py:1709`). | agrees |
| 2. Ambiguity kind | 1 | Kind 1. | agrees |
| 3. Case against | none given | none found. `docs/practice.md:278` lists no dissent. | none found |
| 4. Case for | "none defaults to Le Bail; FullProf, RIETAN-FP and TOPAS make the user state it" | Matches `practice.md:278`. Making the user state it is not a dissent. | supports |
| 5. Tier and source | tier 2; "GSAS-II fits each histogram of a series by RefineCore, the single fit's solver (… checked)" | `practice.md:238` says "checked". That shows a series uses the single fit's solver, not its mode default. The mode default is the single-fit row's GSAS-II citation (`_audit.py:3115-3118`, "LeBail defaults False… checked"). I checked practice.md only, not program source. | holds |
| 6–7 | n/a; `RefinementResult` mode per pattern | — | n/a |

Would change the verdict: a program whose series mode defaults to Le Bail. It would stay a dissenter at tier 2.

**`rietx.sequential.SequentialRefinement.fit:two_theta_limits` = `None`: tier 2**

**Verdict: holds.** The case for is stronger, for the same reasons as `mode`.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "handed to each pattern's fit unchanged (sequential.py:1799-1800)" | Confirmed. `None` fits each pattern's full range. The GUI passes the document's limits (`session.py:1693-1711`). | agrees |
| 2. Ambiguity kind | 1 | Kind 1. | agrees |
| 3. Case against | none given | One situation exists: a series whose patterns cover different 2θ ranges gets a trajectory over changing reflection sets, and a refiner might want one common range. No program default for that was found (`practice.md:279`). | weak, no program behind it |
| 4. Case for | "the full range in GSAS-II, FullProf, RIETAN-FP, MAUD and EasyDiffraction, BGMN the instrument function's range, TOPAS's default not stated" | Matches `practice.md:279`. GSAS-II's per-histogram Limits default is "checked" in the single-fit row. | supports |
| 5. Tier and source | tier 2 | Checked in practice.md only. | holds |
| 6–7 | n/a | — | n/a |

Would change the verdict: a program whose series mode defaults to a common range across patterns. It would be a dissenter and keep tier 2.

**`SEQUENTIAL_CANCELLED` (+ `.suggestion`): caller, response `warning`, scope `("all",)`**

**Verdict: weak.** On condition 1, the case for `caller` is stronger. Every recorded series carries a token, but only a person's stop or the caller's own code sets it. The response is weak on the backward branch, for the same reason as `SERIES_PATTERN_FAILED`.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What the caller decides | "fires only on a cancel the caller asked for… reports the requested act, n of N patterns, and moves no value (sequential.py:2153-2167)" | Confirmed. It fires on `bool(cancel)` (`:1329`, `:1413`), not on the token existing. | agrees |
| 2. Ambiguity kind | 1 | Kind 1. | agrees |
| 3. Case against `caller` | dispatch: "every recorded series carries a cancel token (`sequential.py:1275`)" | The token `runs.attach_cancel` makes is set only by `_WatchedToken.stop()`. Its only callers are `poll_cancel` (`runs.py:1459-1493`), on a `CANCEL_FILE` request from `rietx watch`'s Stop, and `.cancel()`. The only package-side `.cancel()` is the GUI's `/api/cancel` route (`gui/session.py:1794`), the stop button. I found no wall-clock or automatic cancel. One wording tension: generality.md counts "the GUI routes" as default paths, and `/api/cancel` is one. But that route is itself the stop asked for by name. | condition 1 holds in substance |
| 4. Case for (a cost the caller bears) | `responds`: past the last completed forward pattern "quote no cell, fraction or width" | Condition 2 holds: the in-flight pattern is abandoned and nothing moves (`:2161-2166`). On the response: a backward cancel also raises `SEQUENTIAL_PATH_CHECK_INCOMPLETE` at `warning` (`:1413-1422`). Under `("all",)` a result whose forward trajectory is whole then carries two warnings under every purpose, one of them about a forward gap that does not exist. That is two consequences in one code. | response weak on the backward branch |
| 5. Tier and source | `caller` | Both conditions hold. The row's dated grep is the only guard, as the record requires. | holds |
| 6. Dataset families | n/a | — | n/a |
| 7. Record that it fired | the code | Plus `RunStatus.cancelled_by` for a recorded run. | adequate |

Would change the verdict: a package path that sets the token without a person's or caller's request (a budget or timeout), or a separate code or `info` for the backward branch.

**`SEQUENTIAL_PATH_CHECK_INCOMPLETE` (+ `.suggestion`): caller, no response**

**Verdict: holds.** The case for is stronger. It reports what the opt-in check left undone, and the author correctly leaves it on `RESPONSE_BASELINE`.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "reports that the requested comparison did not run or ran on less than the series (sequential.py:2170-2241) and moves no value" | Confirmed: the `warning` sites are at `:2183`, the `info` sites at `:2219`/`:2228`. | agrees |
| 2. Ambiguity kind | 1 | Kind 1. | agrees |
| 3. Case against | none given | Inside the switch, the package chooses which unjudged paths to name: only those "some chain measured", gap above `_noise_floor` (`:3041`). That rests on `NOISE_FLOOR_REL`'s own row, so it is not a new number. | none found |
| 4. Case for | none given | The default `"forward"` is visible (`SeriesResult.direction`). See the 2026-10-24 judge's item 4. | n/a |
| 5. Tier and source | `caller`; "the GUI series panel defaults to 'forward', gui/series.py:80" | Accepted from the earlier review of `fit:direction`. Not re-grepped beyond `session.py:1710`, which passes the user's choice. | holds |
| 6–7 | n/a; the code | `rows.json` proposes splitting it into a warning code and an info code. That is not applied, and it is not in this diff. | — |

Would change the verdict: a default path that sets `direction="both"`.

**`PARAMETRIC_OUT_OF_RANGE` (+ `.suggestion`): caller, response `warning`**

**Verdict: holds, with a caveat.** The case for `caller` is stronger, but condition 2 rests on a fact the row does not state: that the schema's default bounds are physical ranges.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "reads the caller's own declaration against each target entry's min/max, the schema's default where the caller set none (multi.py:2316-2322), and applies no threshold of its own" | Confirmed. A parametric equation is a caller-declared formula that sets a parameter across patterns. | agrees |
| 2. Ambiguity kind | 1 | Kind 1: a value outside its declared box is a fact. | agrees |
| 3. Case against `caller` | none given | Condition 2: "a number with a default used once the switch is on… is tiered on its own." Where the caller set no bound, the test reads a package default. `schemas/common.py:838-839` says a field "declares its physical range" (occupancy min 0, `lor_size` min 0), and W's floor is `caglioti._MIN_GAMMA_G2`, a numerical floor. The silence fixture fires on exactly that branch (W driven under its floor). I did not check that every default bound is physical. Schema defaults sit outside `DEFAULT_SEATS` by declaration, so no row tiers them. | rests on an unstated premise |
| 4. Case for | "opt-in twice: parametric=None by default, inside refine_multi / MultiHistogramRefinement, which no default path calls" | Confirmed by grep: nothing outside `multi.py`, the params and schemas modules and the re-exports, and no GUI caller. A value outside its physical range is not quotable to anyone. | supports |
| 5. Tier and source | `caller` | Holds if the bounds are the caller's own or physical. Otherwise tier 1 would read more honestly. | holds |
| 6–7 | n/a; the code with `where=hist.k.target` | `level_under` maps `hist.` paths to purposes (`results.py:1475-1476`). | adequate |

Would change the verdict: a schema default bound that is a package choice rather than a physical limit.

**`rietx.sequential.SequentialRefinement.fit:prepare` = `None`: caller**

**Verdict: holds.** The case for is stronger: the hook is the caller's code. One package rule inside the switch goes unnamed.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "a caller's callable run on each pattern's warmed models (sequential.py:1765)" | Confirmed. No caller passes it in `src/rietx` (grep `prepare=`). | agrees |
| 2. Ambiguity kind | 1 | Kind 1. | agrees |
| 3. Case against | none given | `sequential.py:1779-1783`: after the hook, the wavelength-calibration reference is reset to the series root's λ unless the hook changed the *number* of emission lines. A hook that re-declares λ per pattern on the same line count (a single-line synchrotron series across energies) gets `WAVELENGTH_CALIBRATION` (the code that compares a refined λ with the declared one) measured from the root's λ, not its own. That moves a diagnostic, not a fitted value. | minor, unnamed |
| 4. Case for | "No default path passes one, the GUI series route included (gui/session.py:1706-1716)" | Confirmed. | supports |
| 5–7 | `caller` | Holds. | holds |

Would change the verdict: a ruling that a diagnostic's reference counts as "the answer" under condition 2. The line-count rule would then need a row.

**`rietx.sequential.SequentialRefinement.fit:constrain` = `None`: caller**

**Verdict: holds.** The case for is stronger. What the package does inside the switch is either a correctness rule or already has its own row.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "re-declares ties, variables and holds on each fit (sequential.py:1794), ladder rungs included" | Confirmed. The GUI passes none. Internally only `_verify_discontinuities` forwards it (`:1154`). | agrees |
| 2. Ambiguity kind | 1 | Kind 1. | agrees |
| 3. Case against | none given | Inside the switch the package runs `_reanchor_carried` (`:1795-1796`) and then warms the variables (`_carry_variables`). The first is WP-1432's rule that a rebuild reproduces the coordinate, which is arithmetic rather than a choice. The second is governed by `refine_sequential:carry`, which has its own row (still unaudited). The row names neither. | none found |
| 4–5 | "No default path passes one" | Confirmed. | holds |

Would change the verdict: a default path that passes a hook.

**The 17 names off `UNAUDITED_BASELINE` and 5 off `RESPONSE_BASELINE`**

**Verdict: holds.** The removals match the rows tiered, and nothing was added to any list.

`UNAUDITED_BASELINE` loses exactly the 17 rows above: the six codes with their suggestion rows (12), plus `NOISE_FLOOR_REL`, `fit:mode`, `fit:two_theta_limits`, `fit:prepare` and `fit:constrain`. `RESPONSE_BASELINE` loses the five codes given a response. `SEQUENTIAL_PATH_CHECK_INCOMPLETE` correctly stays on it, so it keeps its literal level under every purpose (`results.py:1522-1526`). No name was added to `UNAUDITED_BASELINE`, `OTHER_RECORD_FIELDS`, `NOT_WALKED`, `WALKED` or `DEFAULT_SEATS`. I did not run `tests/test_audit_table.py`.

Would change the verdict: a removed name whose row is still `unaudited`.

**`tests/silence.py`: three fire/silent pairs**

**Verdict: holds.** Each pair exercises its code's fault and a near miss. None covers the backward branch the response findings above turn on.

| Pair | Fires on | Silent on | Gap |
|---|---|---|---|
| `PARAMETRIC_OUT_OF_RANGE` | slope -2e-3 drives W under its floor | slope 0 and -2e-4 | Only the schema-default bound branch is tested, not a caller-set bound. |
| `SEQUENTIAL_CANCELLED` | stop after pattern 0 of 2 | the same chain with an unset `CancelToken` | Forward only. The suite runs with telemetry off (`RIETX_TELEMETRY=0`), so the recorder's watched token and the `CANCEL_FILE` path are not exercised. |
| `SERIES_PATTERN_FAILED` | every rung of the middle pattern raises (mocked `Refinement.fit`) | warm rungs raise and the cold rung rescues it | Forward only. |

The pairs run real two- and three-pattern series fits. Their added fast-suite time is **none given**: the handover's 65-passed figure predates them.

Would change the verdict: a backward-branch pair showing which level the backward cancel and backward failure should carry.

Author's answers: none fails. The two backward-branch findings (`SERIES_PATTERN_FAILED`, `SEQUENTIAL_CANCELLED`) are accepted: a backward-only failure or cancel leaves the forward answer standing, so it is a second consequence and gets its own `info` code. That split joins C5's split of `SEQUENTIAL_PATH_CHECK_INCOMPLETE` in the batch, with a backward-branch silence pair for each. `STAGE_FREED_NOTHING`'s level is its raise site's literal `info`, and making it a `warning` on #265's evidence is a ruling, so it goes to the batch under C10. The `prepare` hook's line-count rule for the wavelength reference and `PARAMETRIC_OUT_OF_RANGE`'s premise that schema default bounds are physical are noted for the batch's revision.

*Next*, in order:
0. Prune the Inherited entry from WP-2045. Then re-run `measure_reseed.py` on the merged tree, every arm, for `cpd --first 2`, `planted`, `cr2wo6` and `tut05-broken`. That covers X1 (T087), X3 and X4, and whether C1 has any real rescue left. Write over the JSONs and say so in the entry. The batch's C1, C3 and C9 are rebuilt on those numbers, not on this session's.
1. Revise `2003-batch/batch.md` against DESIGN.md § Rules, per the check above. C1: (iii) as the pick, Rule 4 cited, the mechanism corrected, and (ii) described as what was measured (escalate while the best attempt so far ends `max_iter`). C2: rank by the full cost. C9: `carry` under Rule 1's first pick case, with an invariance test proposed for "every entry against the varied ones". `on_error` as an open question. C10: the joint hold its own row. Every stakes line labelled validating or verifying.
2. Measure before asking: T087 against the planted truth with the bound on and off (about a minute), and X13's open arm (CPD's first two patterns, closing on, `intermediate_ftol=None`, about 40 minutes), which decides the mechanism correction. Then option (iii), escalating on the warm rung's `CELL_RUNAWAY`, on CPD's first two patterns with the closing stage on and off (about 40 minutes each), then planted and Cr₂WO₆.
3. Put the batch to the maintainer: one question each on C1, C2's `on_error`, C3 and C9, the rest by pick. Date the rulings into `rows.json` and the table.
4. After the rulings: tasks 3 and 7 (`seeded_from`, `floored`, `SeriesResult.steps`, the demotions), the seven fixes that need no ruling, the width-growth hand-off to WP-2004 (task 9), then tasks 10-11.

### 2026-10-24 — the inventory, the reseed fence measured on eight chain families, the first-rung invariance tests; eleven clear defaults tiered and nothing contested

Every decision a series makes between patterns is now listed: 77 rows the table already had (not the 65 the WP assumed) and 34 actions with no row, each with what it decides and what a caller would see without it. The Rwp fence that sends a bad warm fit back to colder starts carries real load on real data. On the CPD round-robin chain it alone rescues a pattern whose warm fit ended at 3.75× the fence with corundum's cell 5 % off and an 18° zero shift. A status-only fence, the second review's proposal, would have kept that fit. On the synthetic series the fence escalates 115 times for 4.3× the evaluations and moves no value past 0.0007 esd. That contrast is the reseed brief's stakes line. The first-rung budget is shown answer-invariant on two chains, but WP-2002's closing stage now hides a truncated first rung from the ladder, so WP-1127's safety escalation no longer fires; that and `reseed=False` escalating anyway are clash-table items, not fixed here. No contested row was tiered: the batch is next session's.

*Done.*
- Inherited pruned, eleven entries re-checked and folded into Context and Tasks (`9077375`).
- Task 1, the inventory (`f156c9e`): `2003-batch/inventory.json`, 111 entries (77 rowed, 34 row-less: 18 in `sequential.py`, 16 in the joint fit); `2003-batch/README.md` answers task 3's question. The 12 extra rows over the WP's 65 are `SERIES_PATTERN_FAILED` and the joint fit's five codes (`SIZE_NORMALISED_ACROSS_WAVELENGTHS`, three `PARAMETRIC_*`, `STAGE_FREED_NOTHING`), each with its suggestion row.
- Task 3 answered, not built: the pattern and its rung are on the record, the successors seeded from an earlier pattern are not, nor is the moment-floor carry. The two proposed fields are in task 3's text; they wait for the batch because an action row cannot enter the table at `unaudited`.
- Task 4 (`092991c`, `c4edce6`, `f494e2f`, `cc36121`): the invariance test on the thermal ramp (fast) and the CPD chain (slow), each asserting equality to the bit and the margin; `FIRST_RUNG_FACTOR`'s duplicated comment is one paragraph citing the tests, plus one on the closing stage.
- Eleven defaults tiered (`8b78f2c`, `c4edce6`, `db61420`): seven observation channels of the series seat `invariant`, shown by a new series section in `tests/test_answer_invariant_defaults.py` (made to fail once on purpose at `reseed_factor=0.5`); `backend` `caller` and `solver` tier 2 as on the single fit; `direction` and `verify_discontinuities` `caller`, with the judge's two wording corrections.
- Task 2's measurement half (`6ca9e2e`): `2003-batch/measure_reseed.py`, `reseed/*.json` (34 files), `reseed.md` (per-pattern tables, facts only).
- Code review (`/code-review high --fix`), seven findings: six fixed (`f494e2f`: one chain-answer helper comparing every number and code a chain reports, a ratio for every kept first rung including a `max_iter` one, the twin fixtures built by one function, a docstring); one declined, `measure_reseed.py` matching arms by list position, because no committed family recorded a `SeriesFailure`.
- Forward references (`2e15c3e`, `58eb224`): WP-2045 (the hostile series' runaway on Linux, what the ladder does with it, and the new slow test's cost in its acceptance), WP-2036 (the closing stage on a warm chain and the BLAS threads under it; the new slow test's cost in `qpa-sample1`), WP-1317 (`planted_series/signals.json` lists 20 reseeds where the tree gives 49).

*Measured* (Linux x86-64, 4-core cloud container, worktree venv `[dev]`, compiled tier on).
- The reseed fence, per family (`reseed.md` holds the per-pattern tables). Arms: on (1.25), status-only (`reseed_factor=inf`), off (`reseed=False`), plus a cold independent reference.

  | family | on | status-only | off |
  |---|---|---|---|
  | CPD sample 1 (real; status/off on 2 patterns) | 1 escalated (1b), 0 reseeded; 987 evals | 1b kept at Rwp 0.7652, 1 220 esd from on; 703 evals | as status, 1b `SEQUENTIAL_RWP_OUTLIER` |
  | CPD, `closing_window_tol=None` | none escalated; 708 evals | bit-identical | bit-identical |
  | planted, 248 (synthetic) | 115 escalated, 49 reseeded; 11 790 evals | 1 escalated (budget-forced); 2 716 | as status |
  | planted null twin | none; 2 080 | bit-identical | bit-identical |
  | trigger, 10 (simulated) | none; 269 | bit-identical | bit-identical |
  | Cr₂WO₆ HB-2A pair (real neutron) | none; 873 | bit-identical | bit-identical |
  | tutorial 05 jump | none; 551 | bit-identical | bit-identical |
  | tutorial 05 broken | 1 reseeded (pattern 4); 157 | 0; 135 | as status |

  No arm quarantined anything on any family. Planted's 49 reseeds are near-ties (warm and cold Rwp within 7.6e-7 relative) and no value moved past 0.0007 esd. On CPD under on, the chain sits 7.05-14.2 esd from the independent fits, worst path a `lor_strain` each time; mean Rwp 0.12565 against 0.12580 independent; RMS |ΔW| 2.268 against 2.301 wt %. cpd-1b's warm rung came back `max_iter`, not `diverged`, so a status-only fence that also escalated on `max_iter` would have caught it.
- The first-rung bound: thermal ramp, three armed patterns at 1.0× the running maximum; CPD (from the bounded arm), 0.34-0.39×; factor 3.0. At `first_rung_factor=0.5` on the thermal ramp, patterns 4-6 kept a warm stage truncated at `max_iter` and closed by the closing stage, reading `converged`, within 8e-4 esd of the unbounded chain.
- Wall clock (context only): the CPD chain with the closing stage costs about an hour an arm here (the slow CPD test 1 h 17 min for two chains, one BLAS thread, beside the lane's runs), against 33.7 s quoted for `cpd-series`.
- Fast selection, the branch at `f494e2f` (before the matrix row), beside one single-test run of my own: 11 640 passed, 284 skipped, 27 xfailed, 3 failed, 44:57. The three: `test_validation_matrix.py::test_every_acceptance_test_has_a_matrix_row` (mine, fixed in `cc36121`), `test_audit_delta.py::test_the_reader_agrees_with_the_import` (the file was edited mid-run; passes alone), `test_examples.py::…[moment]` (Linux x86-64, recorded in WP-2036's Inherited, not this branch). Added: 8 fast tests (15.65 s locally: 10.09 s the six series channels, 3.82 s the thermal first-rung test, 1.73 s the recorded series), 1 slow (CPD). Main's count not measured (CI's job), so the +8 is by name in the junit file, not by subtraction.
- Full selection: not run, since the branch moves no measured number (tests, table data, docs, one comment).
- Lanes (`session_usage.py lanes`): inventory est 40, 122 requests, +$7.14; reseed-measure est 35, 328 requests, −$7.62; kept prune-inherited est 4. Trial row: re-read 0K, 17 main requests a lane, 36K left in main, actual/estimated 3.05, −1 %. Baseline replay, the selective policy (main > 150K and item ≥ 20): 4 sessions, +22 %.

*Gotchas.*
- The Durham host is denied by this environment's network policy, so the in-situ ZrMo₂O₈, WO₃ and ZrP₂O₇ series (`tests/local_data.py`) were not fetched; the 68-pattern ramp and the corpus series are not on disk here. The families above are what a cloud session has. The held-out Nd₂Ru₂O₇ pair was not used.
- Run any CPD chain with `OPENBLAS_NUM_THREADS=1` on Linux, or `leggauss` alone costs seconds a call (WP-2036's Inherited).
- `tests/test_sequential.py::chain_answer` is the one helper for "every number a chain reports"; both invariance files use it.
- `reseed=inf` is accepted unvalidated (`sequential.py:1028`) and turns every `rwp_fence` to inf, which also disables the discontinuity scan's above-fence drop (tutorial 05 broken gains a `SEQUENTIAL_DISCONTINUITY` under status-only).
- `SeriesEntry.n_iterations` omits the automatic profile-interval refits (Cr₂WO₆: 873 recorded, 1 146 run).

*Generality* (the `generality-review` judge on `_audit.py`'s eleven changed rows; its sections pasted unedited).

**Item 1: the seven observation and control defaults go to `invariant`**
`rietx.sequential.SequentialRefinement.fit:{cancel, events, label, on_result, progress, telemetry}` and `rietx.sequential.refine_sequential:history`

**holds.** The evidence for the tier is stronger: a bit-identity test runs the chain's real code path. The case against comes down to coverage gaps in that test, and none of the code I read turns a gap into a changed answer.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "an observation channel" (events, cancel, progress); "the run recorder, one run a job" (telemetry); "a run's name" (label); "a callback handed each kept fit" (on_result); "one history tree per pattern" (history). Each row's `evidence`, `_audit.py` series rows. | None of these picks a value. `telemetry=None` does do something unasked: it writes a run directory and adds a cancel token to every fit (`sequential.py:1261-1273`; the `_audit.py` docstring: "`telemetry=None` records the run"). That is a side effect, not an answer. `cancel` is a control channel, so calling it "an observation channel" is wrong only in wording. | agrees |
| 2. Ambiguity kind | `ambiguity=1` | Kind 1. No reading of the data is in question. | agrees |
| 3. Case against | none given | The test chain is three patterns: one cold fit and two warm first rungs (`tests/test_answer_invariant_defaults.py:146-149`). `FIRST_RUNG_SAMPLES` is 3, so the first-rung budget (WP-1127's cap on a warm fit's first attempt) never switches on. No rung escalates, no pattern is quarantined, and neither `direction="both"` nor `verify_discontinuities` runs. Those untested paths are exactly where `cancel` is read again (`sequential.py:1327, 1362, 1411`, and `except RefinementCancelled` at 1585) and where `history` changes file names (the `.cold`, `.verify` and `.backward` suffixes in `_history_spec`). Reading the code, none of those reads feeds a value or a choice of rung, so the gap is in the test, not in the claim. Smaller gaps: (a) the suite runs with `RIETX_TELEMETRY=0`, so in the `label` arm the label reaches nothing, and label with the recorder on is never run for a series (the single-fit file does run it, for `run_stage` and `refine`). (b) Nothing checks that the events file or the progress stream received anything, so a channel that `refine_sequential` silently dropped would still pass. (c) `history` is tested with `True` (trees in memory), never with a directory path. | minor coverage gaps |
| 4. Case for | The dispatch says the test compares "every kept value, esd, rung, `rungs_tried`, `reseeded`, `rwp_warm`, `rwp_fence`, Rwp, per-entry codes, series codes and `discontinuities`", and was made to fail once on purpose with `reseed_factor=0.5`. | Confirmed: `chain_answer` (added to `tests/test_sequential.py`) compares all of those. It does not compare `y_calc`, which the single-fit `_same` does. The `on_result` arm checks that the callback ran once per pattern (`seen == [0, 1, 2]`), and the telemetry arm checks that exactly one run directory was written, so those two arms cannot pass without the channel running. The rows match the single-fit precedent (`rietx.refine.refine:events`, `…:history` and the rest, `_audit.py:3164-3180`). | supports |
| 5. Tier and source | `invariant`, tested in `tests/test_answer_invariant_defaults.py` | Tests: `test_a_series_observed_is_the_series_unobserved[events,progress,cancel,label,on_result,history]` and `test_a_recorded_series_is_the_series_unrecorded` (telemetry). generality.md asks an invariant test to also assert its margin. A channel is not a bet like the first-rung budget, so equality is the margin, as in the single-fit rows. | holds |
| 6. Dataset families | none given | Not a threshold, so families do not apply. The one dataset is the synthetic thermal ramp (`tests/test_sequential.py` `_simulate`). | n/a |
| 7. Record that it fired | none given | No field is needed for a channel. Telemetry's record is its run directory (`meta.json`). History's record is `SeriesEntry.tree_id` / `node_id`. | adequate |

What would change the verdict: a channel arm on a chain that escalates or quarantines (the author's own `reseed_factor=0.5` chain would do) giving a different answer from the same chain with the channel off.

**Item 2: `rietx.sequential.refine_sequential:backend` goes to `caller`**

**holds.** The evidence for leaving it to the caller is stronger. It copies the single-fit row word for word in substance, and the chain adds no choice of its own inside the switch.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "each pattern's Refinement gets it unchanged (sequential.py:1765)" (row `evidence`) | Confirmed at `sequential.py:1765`. The constructor checks a non-numpy backend and refuses it when the optional package is missing (`:975-981`). | agrees |
| 2. Ambiguity kind | `ambiguity=1` | Kind 1. | agrees |
| 3. Case against | none given | none found. No competent refiner wants the package to choose a GPU or autodiff backend for them. | — |
| 4. Case for | "jax/torch/torch-mps need an extra no default install has, and agree with numpy only to fp tolerance" | Nothing new falls to the caller. One nuance for a chain: a floating-point difference can flip a reseed-fence verdict that sits near 1.25× the median Rwp (the fence sends a pattern back for a colder refit). A chain's choice of rung can then differ by backend, not only its last digits. That is not measured, and it is still the caller's choice. | — |
| 5. Tier and source | `caller`, citing `rietx.refine.refine:backend` | Both conditions hold. (1) The switch is asked for by name and its off state is `numpy`. (2) Inside it the package picks no number; the floating-point spread comes from the caller's choice of backend. This matches `_audit.py:3155`. | holds |
| 6. Dataset families | n/a | n/a | n/a |
| 7. Record that it fired | none given | `RefinementResult.provenance.backend` on each pattern's result (`schemas/results.py:1848`). I did not check whether `SeriesEntry` or `SeriesResult` carries it. | adequate |

What would change the verdict: a default path that passes a non-numpy backend.

**Item 3: `rietx.sequential.refine_sequential:solver` goes to tier 2**

**holds.** The evidence for the tier is stronger. It inherits the single fit's row, and the one dissenter named keeps it at tier 2 under the rule.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What it decides | "handed to each pattern's Refinement unchanged (sequential.py:1765-1766)" | Confirmed. It sets bounded Levenberg-Marquardt (damped least squares, with an exact set of parameters active at a bound), with TRF (a trust-region solver) available by name. | agrees |
| 2. Ambiguity kind | `ambiguity=1` | Kind 1, as for the single fit. | agrees |
| 3. Case against | "FullProf dissents, Gauss-Newton with relaxation factors" | Matches `docs/practice.md:180`. Under generality.md tier 2, a dissenting program does not move a default off tier 2. Nothing in the change says what any program's *sequential* mode defaults to. | dissent named |
| 4. Case for | "Marquardt-damped in six" | `docs/practice.md:180`: GSAS-II, TOPAS, RIETAN-FP, MAUD, EasyDiffraction, and BGMN (regularised Gauss-Newton). | supports |
| 5. Tier and source | tier 2; "GSAS-II 5.8.4 GSASIImath.HessianLSQ is Marquardt-damped (checked)" | I checked this in the repository's practice.md only, not in GSAS-II's source. That each program's sequential mode uses the same solver as its single fit is not given; I believe it is so for GSAS-II, from memory only, not checked. | holds |
| 6. Dataset families | n/a | No threshold. | n/a |
| 7. Record that it fired | none given | `RefinementResult.provenance.solver` (`schemas/results.py:1848`). | adequate |

What would change the verdict: nothing under the current rule. Even a program whose sequential mode defaults to a different solver would only be one more dissenter.

**Item 4: `rietx.sequential.SequentialRefinement.fit:direction` goes to `caller`**

**holds, but the case for acting is stronger than the row admits, and the row cites none of it.** `direction="both"` runs the chain a second time in reverse and flags parameters whose two trajectories disagree. The caller-class conditions are met, because `'forward'` moves no reported value; it only leaves that check out.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What the caller must now decide | "its off default walks one chain" (row `evidence`) | Under `'both'` the reported entries are still the forward ones (`sequential.py:1076`). So the default changes no value; it leaves out the path-dependence check. The caller decides whether to pay for a second chain. | agrees |
| 2. Ambiguity kind | `ambiguity=1` | The switch is kind 1. What it opens up (path dependence) is reported as a statistic, under `SEQUENTIAL_PATH_DEPENDENT`. | agrees |
| 3. Case against defaulting to `'both'` | none given | Cost: a whole extra chain, at least doubling the wall clock; no figure is in the change. Value: `docs/skill/rietx/references/series.md:136-150` says agreement both ways is not evidence of correctness (0 of 35 patterns disagreed on a physically wrong construction), and the largest flags it measured were axis relabellings (81.5σ in `Fddd`). So a default `'both'` would issue codes that need careful reading. Program practice: `docs/practice.md` has no entry on sequential refinement. I recall GSAS-II's reverse-order option being off by default, but I did not check it. | real, unmeasured |
| 4. Case for defaulting to `'both'` | none given | The package's own words: series.md:131-135, "For any trajectory you intend to publish, run it — it is the only check that separates a measurement from an ordering artefact"; judging.md:418-419, "a one-way chain has not looked"; the root CLAUDE.md says the same. So every caller who publishes a trajectory pays a full rerun of the chain. That cost is not measured. The default is visible: `SeriesResult.direction` (`schemas/sequential.py:699`), and the series summary prints "ordering artefact: NOT measured — this chain ran forward only…" (`schemas/sequential.py:1325-1329`). The row should cite both. | strong, uncited |
| 5. Tier and source | `caller`; "the GUI's series panel defaults to 'forward' (gui/series.py:80) and passes the user's choice (gui/session.py:1710), and no other default path sets it (searched 2026-10-24)" | Checked: `gui/series.py:77-82`, `gui/session.py:1710`, and a grep of `src/rietx` finds no other caller. Condition 2 holds: `PATH_DEPENDENCE_SIGMA` (3.0), `NOISE_FLOOR_REL` (1e-9) and `SEQUENTIAL_PATH_DEPENDENT` have their own rows, still `unaudited`. That matches how WP-2002 treated TRF's tolerances. A side finding: the GUI's `DEFAULTS` dict holds its own copy of `'forward'`. That is a second seat for this default, which the table cannot see because the value sits in a dict. | holds |
| 6. Dataset families | n/a | n/a | n/a |
| 7. Record that it fired | none given | `SeriesResult.direction`, `SeriesResult.backward` and `SEQUENTIAL_PATH_CHECK_INCOMPLETE`. | adequate |

What would change the verdict: a measurement, on the suites' chain families, of how often a forward-only trajectory moves by more than its esds when run both ways, set against the cost of the second chain in evaluations.

**Item 5: `rietx.sequential.SequentialRefinement.fit:verify_discontinuities` goes to `caller`**

**holds for now.** The case for acting is real and the row does not state it. The row will need re-reading once WP-2003's own demotion of `SEQUENTIAL_DISCONTINUITY` (the code that flags a large jump between neighbouring patterns) lands.

| Question | Author's answer (where) | What I found | Verdict |
|---|---|---|---|
| 1. What the caller must now decide | "a cold refit of each flagged pair" (row `evidence`) | Whether to refit each flagged pair of patterns cold and independently, and record the cold step as a signed ratio of the chain's step (`sequential.py:1888-1892`). | agrees |
| 2. Ambiguity kind | `ambiguity=1` | Kind 1 for the switch. It adds a second number to a kind-3 statistic and no threshold. | agrees |
| 3. Case against defaulting on | none given | `sequential.py:1117-1121`: a cold fit is "roughly triple a warm one", and "a series flagging s steps pays up to 2s of them". The WP's task list adds an ungated moment-angle interval (an automatic profile interval on magnetic moment angles) on each cold refit: 20-32 refits an angle, 2.6-16.7 s on fits of 0.2-1.2 s. | real |
| 4. Case for defaulting on | none given | `sequential.py:1115`: "It is the check the diagnostic's own suggestion asks the reader for, run automatically"; `help.py:3719` points the reader at it. Measured "~5 %" on the 68-pattern thermal ramp with four flagged steps (`:1122-1124`, WP-1305), on one dataset family. Leaving it off means the caller refits the pairs by hand or reruns. The docstring's "not cheap" and its own "~5 %" pull opposite ways. | real, uncited |
| 5. Tier and source | `caller`; "no default path sets it, the GUI included (searched 2026-10-24)" | Confirmed by grep: nothing outside `sequential.py` passes it. Condition 2 holds: "no fitted value, entry, rung or median in the reported chain moves" (`:1126-1130`). The row calls what it adds "the verdict added to SEQUENTIAL_DISCONTINUITY", but the code adds a ratio and a reading with no threshold ("near 1.0 … near 0", `:1892-1900`). That is not a verdict, and the row understates its own case. Which pairs get refitted is set by `DISCONTINUITY_FACTOR` 5.0 and `DISCONTINUITY_SIGMA` 3.0, both `unaudited`. The WP's own plan removes that code for `SeriesResult.steps`, a field with no threshold, and says `verify_discontinuities` "moves to the largest steps or is ruled in the batch". Whatever then picks which steps get refitted is a package number inside the switch, and it needs its own row. | holds now |
| 6. Dataset families | n/a | The 5 % cost figure comes from one family. | n/a |
| 7. Record that it fired | none given | `Diagnostic.value` and the message on `SEQUENTIAL_DISCONTINUITY`, plus the `<label>.verify` histories. No result field. Once the code is removed, the ratio needs a new home. | adequate now, orphaned after the demotion |

What would change the verdict: the batch's ruling on `SEQUENTIAL_DISCONTINUITY`. If refitting then picks steps by a package-set count or cutoff, that number needs a row before this row stays `caller`.

**Item 6: eleven names removed from `UNAUDITED_BASELINE`**

**holds.** The eleven names removed are exactly the eleven rows tiered above (backend, solver, history, and the eight `fit:` defaults). Nothing was added to `UNAUDITED_BASELINE`, `OTHER_RECORD_FIELDS`, `NOT_WALKED`, `WALKED` or `DEFAULT_SEATS`. A removal from a list that only shrinks needs no reason. `tests/test_audit_table.py` holds the list equal to the tiers; I did not run it.

What would change the verdict: a name removed whose row is still `unaudited`.

**Second trigger: the findings in the inventory (comment only, not edits)**

- **`reseed=False` still escalates.** The `reseed` docstring (`sequential.py:1077-1083`) says "Switching it off leaves each pattern with its first rung". But `forced` (`:1561`, `:1569-1571`) sends a first rung cut short by the budget to the next rung anyway. So the package acts against a switch the caller turned off. It is visible in `rungs_tried`, but the docstring contradicts the code. This belongs in the `reseed` row's batch brief, and the docstring needs fixing. No new row is needed, since `reseed` has one.
- **The closing stage can hide a budget cut.** If `result.status` reports the closing stage's verdict (`:1603`), a first rung cut by the budget and followed by a converged closing stage is not counted as truncated. Then nothing forces an escalation, and `_prefer` (which ranks a truncated attempt below a completed one) does not rank it down. The budget could then keep a fit that was cut short, which is exactly what `FIRST_RUNG_FACTOR`'s invariance claim rules out. Both new tests assert `max(ratios) < FIRST_RUNG_FACTOR`, meaning the budget never bit, so they cannot see this case. I did not check whether `_bounded_plan`'s cap reaches the closing stage. This should be settled before `FIRST_RUNG_FACTOR` is tiered `invariant`.
- **Quarantine successors and the moment-floor carry** (the floor reset applied to an unsupported magnetic moment before it seeds the next pattern) have no record field. An action row is keyed on its field, so holding them out of the table until WP-2003's task 3 adds the field is correct.

Author's answers: items 4 and 5's wording corrections are applied (`db61420`); item 1's coverage gaps are accepted as gaps (the escalating `reseed_factor=0.5` chain is the arm to add if a channel is ever suspected); `FIRST_RUNG_FACTOR` is deliberately left `unaudited` for the reason the judge gives.

*Next*, in order:
1. Tier the remaining 66 rowed entries and give the 34 row-less ones a row or a reason, working from `inventory.json` (task 2), the reseed fence first, since its stakes line now exists: the fence carried load on the one real chain where it acted, and cost 4.3× for nothing on a synthetic one.
2. The clash table (task 5), with the three clashes found here as its first rows: the bound × the closing stage, `reseed=False` × the forced escalation, the closing stage × the fence.
3. The batch (task 6), one brief per class, with task 3's two fields and the `reseed` docstring fix in the quarantine's and the fence's briefs.
4. After the rulings: tasks 3 and 7 (the fields, the demotions with `SeriesResult.steps`), then the width-growth hand-off to 2004.

- **2026-10-21** — the repair itself: WP-2019's session, started under this
  WP's `repair first` flag, wrote the reconstructed entry below (f036bf9, on
  #1095's branch). No work on this WP's tasks, and Next is unchanged.
- **2026-10-20** (reconstructed post hoc, 2026-10-21, from 5c88100 / #1084) — a
  process edit, not work on this WP's tasks: the brief this WP sends the maintainer now
  opens with a stakes line, and a measured-consequence column was weighed and declined.
  - **What the commit shows.** `docs/milestones/generality.md` § The rule gains the
    paragraph "A brief opens with its stakes": the reported quantity the action can move,
    the case on disk and its distance from reference, the dissenter or `none found`;
    context, never a filter. A kept guard no ordinary fit reaches is kept on an injected
    case its row names (`test_cell_runaway_safety`'s escape for the cell clamp). § Decisions
    gains the declined consequence axis with its three reasons. This file's and 2004's
    batch task each carry the stakes line.
  - **What it does not show.** The session's branch carried this one commit and no
    handover entry; the record names a planning session and the maintainer's note of
    that date as the source. No checklist item moved, and no test or count.
  - **Next** is unchanged: the inventory, after 2002's holds settle.
- **2026-10-18** — created, from the milestone's opening session. 1317 (the series
  scrubber) and 1325 (parametric series) are open and adjacent; neither owns the fences,
  and this WP changes no view.
