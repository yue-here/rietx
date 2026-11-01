# WP-2003 decision batch: what a series decides between patterns

This batch asks your rulings on the 83 WP-2003 entries that still need one: 49 rows of the
audit table and 34 row-less entries, each proposed for a row or for none. WP-2003 audits every
action `refine_sequential` and the joint fit take between patterns. The inventory holds 111
entries. 28 needed no approval and are not asked here: 17 were written into `src/rietx/_audit.py`
on 2026-10-24 and 11 were tiered by the session before (`"applied": true` and
`"status": "tiered 2026-10-24"` in `rows.json` beside this file). The 83 fall into eleven
classes. Five carry a real question: C1, C3 and C9 a judgement each, C2 one left open
(`on_error`) and C10 one (the joint hold's statistic). C2's other parts and C8 ask you to
confirm that an action passes. Four ask you to approve a demotion that the record's § Demotion
already implies: C4, C5, C6 and C7 (C7's constants go to WP-2004). C11 is plain. Each brief
opens with its stakes line (the record § The rule, 2026-10-20), its reference named as
validating or verifying. Answer each class by its numbered questions and option letters; the
rulings are dated into `rows.json` and the table afterwards.

*How this was made.* A survey of the seven programs' series defaults (`docs/practice.md`
§ Sequential refinement, 2026-10-24). A tiering pass over the inventory (`inventory.json` →
`rows.json`, drafted by class in `classes.md`). A reseed measurement on eight chain families
(CPD's closing-off variant among them; CPD with `intermediate_ftol=None` a ninth, two arms)
under five triggers: the Rwp fence (`on`), status only (`status`), `reseed=False` (`off`), and
`status` that also escalates while the best attempt so far ends `max_iter` (`status_maxiter`,
option (ii)) or carries `CELL_RUNAWAY` (`status_runaway`, option (iii)); `on_nobound` and
`off_nobound` put the first-rung bound aside; `ref` and CPD's `ref_seeded` are the independent
cold fits (`reseed/*.json`, `measure_reseed.py --table`). Every JSON was rewritten on
2026-10-25 on `main` at `9ad4d1f6`, after WP-2045 (#1161: the last declared stage converges
behind the closing stage); a number from before WP-2045 says so. A clash pass over seventeen
pairs of actions (`clashes.md`, X1-X17). The picks were then checked against DESIGN.md § Rules
(the WP's *design-principle check*), and each section names what changed. Every figure quoted
from `reseed/` was re-projected from the JSONs (a `rungs_tried` longer than one is an
escalation, `n_iterations` summed is the evaluations).

**Vocabulary** (as WP-2002's batch). Tier 1 is physics or arithmetic; tier 2 a validating
citation or the same default in one of the seven programs; tier 3 rietx's own, kept only with
your dated approval. `invariant`: the setting changes cost and leaves the accepted answer
alone, and a test asserts it. `caller`: only the caller turns it on. Kind 2 ranks alternatives
with their evidence and picks none; kind 3 reports the number with its meaning. `covered`: a
row-less joint-fit act whose record field already has a 2002 row and ruling. A *validating*
reference is outside rietx (a weighed composition, a planted or simulated truth); a *verifying*
one is rietx's own (the independent cold fits, the unbounded chain, the other walk) (DESIGN.md
§ Rules, 2). The "warm rung" is the collapsed warm refit a pattern tries first; "the closing
stage" is WP-2002's, which ends every plan and which `_collapse` carries into each warm refit.

**The families.** Two are real, from different laboratories, instruments and materials. None
of the three families offered on PR #1150 had landed when tiering started (WP Context), so no
tier-3 threshold here meets the mechanical ground's three-family bar, and the picks lean on the
judgement ground and on demotion.

| Family | What it is | Patterns |
|---|---|---|
| CPD | IUCr CPD sample 1, 1a-1h, lab Cu Kα: eight weighed mixtures of corundum, zincite and fluorite (`tests/data/README.md:142-149`). A tray, not a ramp: weighed corundum goes from 1.15 to 94.31 wt % between 1a and 1b | 8 |
| CPD, closing off | the same with `closing_window_tol=None` (declared variant) | 8 |
| CPD, ftol None | the same, closing stage on, `intermediate_ftol=None` (declared variant, X13's arm) | 8 |
| Cr₂WO₆ | HB-2A neutron pair, 4 K then 150 K, nuclear plus magnetic | 2 |
| planted | synthetic perovskite cooling ramp, four planted events: background step at T050, blank frame at T087, unmodelled phase from T124, cubic → tetragonal at T186 (`tests/planted_series.py`) | 248 |
| planted null | its twin with no event | 248 |
| trigger | `examples/bench_refinement.py` `_trigger_series`: four phases, a cell ramp of 100 ppm a step | 10 |
| tut05-jump, tut05-broken | tutorial 05's LaB₆ ramp, 300-900 K, the 700 K cell × 1.02 or × 1.05 | 7 each |

| Class | Rows (pending of all) | What you decide | My pick |
|---|---|---|---|
| C1 What triggers the ladder | 11 of 11 | Whether the Rwp fence stays a trigger; what else sends a warm fit up | The fence becomes a reported ratio; escalate on diverged or raised only. (ii) and (iii) measured and not adopted |
| C2 Ladder, quarantine, kept attempt | 11 of 13 | Confirm the protection; the ranking; `on_error`; an `error`-level attempt | Pass; diverged ranks below truncated; the full cost ranks, `max_iter` ties `converged`; `on_error` yours; an `error`-level attempt counts as diverged, after one arm |
| C3 First-rung budget | 4 of 4 | It moved an accepted value at its default: remove, keep as tier 3, or widen | Default `None` (caller opt-in), its two defects fixed, landing after X16 is fixed |
| C4 Discontinuity scan | 7 of 7 | Approve the demotion; what `verify_discontinuities` refits | Demote to `SeriesResult.steps`; the caller names the pairs or *k* |
| C5 Path dependence | 3 of 6 | Approve demoting the 3σ verdict to a field of gaps | Demote; split the incomplete-check code; each gap carries both walks' rung |
| C6 Persistent-finding summary | 5 of 5 | Approve demoting the half cut to a field of counts | Demote, after the agent harness |
| C7 Width growth | 6 of 6 | A ruling to hand WP-2004 | A field; the three constants to 2004 |
| C8 Moment carry | 5 of 5 | Confirm under the rare-feature clause | Pass; `floored` names the kept attempt; split the onset code |
| C9 Carry policy, closing stage | 8 of 10 | What `carry` decides; whether a warm refit runs the closing stage | The warm start is the caller's (Rule 1's first pick case), what is carried tested for invariance; keep the closing stage |
| C10 Joint fit | 20 of 26 | Confirm 2002's rows cover six joint holds; the joint absent-phase hold's statistic | Covered; align the joint hold with B1's answer test; the form test's hold waits for X14 |
| C11 Caller and invariant | 3 of 18 | Plain | `x`, `x_label`, `labels` invariant once their test arms land |

**Rulings, 2026-10-26.** The maintainer delegated the rulings to the session's judgement
against DESIGN.md § Rules ("check against our design guidelines and use your best judgment").
Every pick below is approved as written, its conditions included: C1 lands after X16 is fixed
(C3's order), C2's question 5 after its one arm, C3's (a) after X16, C9's `"*"` invariant once
its test lands, C10's alignment after its joint fixture. The one open question, C2's 4, is
ruled **`"carry"` stays the default, tier 3**: it reports the failure at `warning`, seeds
nothing from it and keeps every finished pattern, while stopping spends nothing the caller
asked to save; GSAS-II's and MAUD's stop is the named dissent, EasyDiffraction the precedent.
Each entry's `ruling` field in `rows.json` carries the date; the table rows land with the
demotions (WP task 7), each its own commit.

---

## C1. What sends a warm fit up the ladder

**Stakes** (validating: the weighed composition; verifying: the `status` arm and the
independent fits). Every value of an escalated pattern. On `main` no trigger beyond divergence
moves a value in the default configuration: the fence's 116 escalations moved none past 7.2e-4
esd. Option (iii) acts on CPD 1b alone. With the closing stage on it moved nothing the weighed
composition sees (the chain's mean |ΔW| over 1a-1h 1.79 against 1.82 wt %); with it off it
rescued 1b and lost 1c-1h (13.98 wt %, X17). Dissenter named for the fence: a refiner whose
series gains a lasting misfit (planted from T134, 4.1× the evaluations for nothing). For (iii):
CPD 1b with the closing stage on, whose warm rung fires `CELL_RUNAWAY` at a cell 0.2 esd from
the independent fit's and corundum 0.01 wt % from weighed; a refiner shown it keeps it.

**Rows.** `RESEED_FACTOR`, `fit:reseed_factor`, `fit:reseed`, `_reseed_needed` (row-less),
`SEQUENTIAL_RESEED` (+ suggestion), `SeriesEntry.reseeded`, `SeriesEntry.rwp_fence`,
`SEQUENTIAL_RWP_OUTLIER` (+ suggestion), `_chain.rwp_outlier_carve_out` (row-less).

**The decision.** Two questions.

1. Does the Rwp fence stay a trigger by default? The fence is `reseed_factor` (1.25) × the
   median Rwp of the patterns accepted so far (`sequential.py:171`, `:1992-2009`).
   (a) Yes, as today. (b) No: it becomes a reported number, and a caller who wants it as a
   trigger passes a factor of their own.
2. If (b), what sends a warm fit up besides divergence and a raise? (i) Nothing else.
   (ii) The best attempt so far ending `max_iter`, since WP-2002 the closing stage's status
   (the arm `status_maxiter`). (iii) The best attempt so far carrying `CELL_RUNAWAY`, the
   record of WP-2002's B8 clamp, from any stage (the arm `status_runaway`). Both arms ask
   about the best attempt so far, so a warm rung no later rung displaces climbs to the cold
   one.

**Evidence.** The five arms by family: escalated patterns, then summed evaluations. The last
column compares (ii) and (iii) with `status` pattern by pattern on `values_sha`.

| Family | on (fence) | status | off | (ii) | (iii) | against status |
|---|---|---|---|---|---|---|
| trigger | 0, 275 | 0, 275 | 0, 275 | 0, 275 | 0, 275 | both identical, 10 of 10 |
| tut05-jump | 0, 634 | 0, 634 | 0, 634 | 0, 634 | 0, 634 | both identical, 7 of 7 |
| tut05-broken | 1 (scan12), 162 | 0, 138 | 0, 138 | 0, 138 | 0, 138 | both identical, 7 of 7 |
| planted null | 0, 2 143 | 0, 2 143 | 0, 2 143 | 0, 2 143 | 0, 2 143 | both identical, 248 of 248 |
| Cr₂WO₆ | 0, 482 | 0, 482 | 0, 482 | 0, 482 | 0, 482 | both identical, 2 of 2 |
| planted | 115, 13 034 | 1 (T087), 3 165 | 1 (T087), 3 165 | 1 (T087), 3 165 | 1 (T087), 3 165 | both identical, 248 of 248 |
| CPD | 0, 644 | 0, 644 | 0, 644 | 0, 644 | 1 (1b), 785 | (ii) identical, 8 of 8; (iii) 1 of 8 |
| CPD, closing off | 0, 708 | 0, 708 | 0, 708 | 0, 708 | 1 (1b), 2 957 | (ii) identical, 8 of 8; (iii) 1 of 8 |

Planted's one escalation outside the fence is T087, forced by the first-rung bound (C3; in
`off`, against the switch, X2). With the bound off, the fence escalates T088 in its place (X16).

What the arms show:

- **WP-2045 removed the fence's one rescue** (X3). Before it, CPD 1b's warm rung ran away
  with the closing stage on (Rwp 0.7652, zero shift 18.0(74)°), and only the fence caught it.
  The cause was the declared warm stage stopping early as an intermediate stage, not the
  closing stage's own solve: WP-2045 makes the last declared stage converge, and
  `intermediate_ftol=None` now moves the chain ≤ 2.1e-4 esd (X13, moot). On `main` 1b keeps
  its warm rung in every arm but (iii): converged, Rwp 0.13984 (independent 0.13732), corundum
  94.32(23) wt % (weighed 94.31, independent 94.29(23)), *a* 4.75801(41) Å against
  4.75809(38). `CELL_RUNAWAY` still fires on it.
- **The fence's firings buy nothing.** Planted: T087 plus 114 above the fence from T134,
  13 034 evaluations against 3 165 (4.1×), no value past 7.2e-4 esd. tut05-broken: scan12
  climbs all three rungs and keeps the cold one at the same Rwp, 0.96874, `MODEL_FAR_FROM_DATA`
  on both. Its one rescue on disk is outside the default: planted T088 with the bound off (X16).
- **Option (ii) is `status` on `main`**, bit for bit on all eight families: CPD 1b no longer
  ends `max_iter`, and Cr₂WO₆ 150 K's closing stage now converges (377 evaluations). Before
  WP-2045 it escalated 150 K through all three rungs for 3.07× the evaluations and ≤ 0.087 esd
  (X4), the dissent the check named: a refiner extends a fit that ran out of iterations at a
  good answer rather than restart it cold.
- **Option (iii) acts on CPD alone**; no other family's warm rung carries `CELL_RUNAWAY`.
  *Closing on:* 1b climbs to `warm_staged` (Rwp 0.13779, 395 evaluations against 301; corundum
  94.24(23) wt %, *a* 0.13 esd from the independent fit). 1c-1h warm-start from it at lower
  Rwp, but `lor_strain` sits 7.05-14.3 esd from the independent fits on 1b-1h, against ≤ 0.92
  under `status` (whose worst path is `instrument.profile.v`, 2.87-5.62 esd), and
  `RESOLUTION_NOT_POSITIVE` fires on all seven kept rungs (once in the independent fits). 785
  evaluations against 644. *Closing off:* 1b's degraded warm fit (Rwp 0.16333; corundum
  94.84(27) wt %, its cell held and unreported) climbs to `warm_staged`: Rwp 0.13928, the
  independent fit's 0.13932, corundum 94.26(24), `axial_sl` on its floor at 0 in both. 1c's
  warm refit from that state collapses (X17): `converged` at Rwp 10.83, `MODEL_FAR_FROM_DATA`.
  Nothing in (iii) fires, so it seeds 1d-1h, each `max_iter` at 400 evaluations, corundum 55-73
  wt % with esds of 39-71 against 13.5-55.1 weighed. 2 957 evaluations against 708. The fence
  would have escalated 1c; (ii) 1d-1h and not 1c.
- No program restarts a pattern by itself (`docs/practice.md` § Sequential refinement, last
  paragraph), so every trigger beyond divergence is tier 3.
- The fence's median is one or two values for the first patterns (X8): accepted Rwp
  [0.30, 0.10] gives a fence of 0.25, against 0.125 for [0.10, 0.10].
- `SEQUENTIAL_RESEED` fires only when the cold rung is kept (35 on planted, 1 on tut05-broken,
  both under the fence); a rescue to `warm_staged` is on `SeriesEntry.rung`, `.rungs_tried`
  and `.rwp_warm` alone.

**The case against (a).** Rule 4 (DESIGN.md § Rules): a default action's evidence is never an
Rwp comparison, and the fence compares one pattern's Rwp with the median of others'. Its
dissenter is on disk (planted from T134, 4.1× for nothing). Rwp tracks Rexp, so the fence fires
on falling counts under a right model (WP-1469's ramp: +55 % iterations), which is why the width
screen reads GoF (`sequential.py:283-287`). And it misses a degraded warm fit inside it: CPD 1b
with the closing stage off.

**The case against (b).** None in the default configuration on `main`. Its one rescue on disk,
planted T088 with the bound off, catches a freeze the default bound prevents, and the freeze is
a chain defect (X16). It ties (b) to C3: (b) with (i) and C3's (a) is `off_nobound` on planted,
by reading.

**The case against each of (i), (ii) and (iii)** (Rule 1: a named dissent moves an action off
the first kind). (ii) changes nothing on `main`, and practice dissents from it. (iii)'s dissent
is on disk: with the closing stage on it escalates a warm rung a refiner keeps, moving the
strain columns 7-14 esd from the independent fits for no validating gain, and with it off its
one rescue leads into X17. (i) keeps CPD 1b's degraded closing-off warm fit (corundum 1.96 of
its esds from weighed), which `CELL_RUNAWAY` and `PHASE_UNCONSTRAINED` report, in a declared
variant.

**My pick.** 1 (b) and 2 (i): the fence becomes a reported ratio, and a warm rung escalates
only when it diverged or raised. This departs from the check's "(iii) as the pick", which
reasoned from (iii)'s projection (`CELL_RUNAWAY` on CPD 1b alone among 520 kept warm rungs)
before (iii) had run and before WP-2045 removed the runaway it was to catch. Run on `main`,
(iii) escalates one fit that needed no rescue, and in the closing-off variant it rescues one
pattern into a collapse it does not see. (i) loses no measured rescue in the default
configuration. It lands in C3's order: until X16 is fixed the default keeps today's bound, or
planted freezes. I would change my mind on a family where a diverged-or-raised ladder keeps a
warm fit a validating reference rejects and a fact other than Rwp separates it from the fits it
accepts. X17 offers one, the package's own `error` level, which C2's fifth question asks about.
Changed 2026-10-25: the 10-24 pick was (ii), on a rescue WP-2045 has since removed.

**Rows that follow.**
- 1 (b): `RESEED_FACTOR` removed. `fit:reseed_factor` loses its default and becomes the
  caller's opt-in fence (caller), refused unless finite and positive (fix 4).
  `SEQUENTIAL_RWP_OUTLIER` and its suggestion removed (the threshold decides whether the code
  exists). The statistic becomes each pattern's Rwp over the median of those accepted before
  it, under a name that asserts no verdict, replacing `SeriesEntry.rwp_fence` (tier 1, a
  record); its help entry says the first patterns are judged against a median of one or two.
  `_chain.rwp_outlier_carve_out` lapses; its scan half leaves with C4.
- 2 (i): `_reseed_needed` tests `diverged` alone (a raised rung escalates at its own site),
  tier 3, kind 1, approved with C2's ladder. `SEQUENTIAL_RESEED` tier 3, response `warning`,
  suggestion tier 1. `SeriesEntry.reseeded` tier 3. `fit:reseed` tier 3, approved with C2.
- 1 (a): every part tier 3 with approval, against Rule 4; the fence armed only after a minimum
  of accepted patterns (X8).

---

## C2. The ladder, the quarantine and the kept attempt

**Stakes** (validating: the planted truth, the weighed composition). The quarantine moves
every successor of a diverged pattern: none on disk (its kept case is the injected divergence
at `tests/test_sequential.py:1158`); dissenter none found. A `converged` fit the package marks
`error` is not quarantined: X17's 1c seeded five successors (corundum 55-73 wt % against
13.5-55.1 weighed). The ranking moves the pattern's own values: at planted T087 `_prefer` kept
`warm_staged` (Rwp 0.048071) over the truncated warm rung (0.048022), at the truth (scale 0,
zero shift 0.00597 held against 0.006) where the unbounded chain reads −0.0231(48), 6.06 esd
off. Dissenter for the ranking none found; for `on_error="carry"`, GSAS-II and MAUD.

**Rows.** `_ladder`, `_prefer`, `_chain.quarantine`, `_chain.on_error_carry` (all row-less),
`SeriesEntry.rung`, `.rungs_tried`, `.rungs_raised`, `SEQUENTIAL_UNRECOVERED` (+ suggestion),
`fit:on_error`, `fit:refit`. Applied already: `SERIES_PATTERN_FAILED` (+ suggestion, tier 1).

**The decision.** Two of Rule 1's four protections are here (keep the best attempt; seed no
successor from a diverged fit), judged as those protections, with their criteria still tiered.

1. Does the quarantine pass, and with it the ladder's parts: three rungs (collapsed warm
   refit, the staged plan from the warm state, the staged plan cold; `RUNGS`,
   `sequential.py:362`), that order, and giving up after the cold rung?
2. Should a finite truncated attempt beat a diverged completed one? Today `_prefer` asks
   "truncated?" before `_better` asks "diverged?" (`sequential.py:1961-1990`). Under a forced
   escalation, a diverged `warm_staged` rung is then kept over a truncated first rung with a
   finite Rwp, and the pattern is quarantined.
3. Does `max_iter` rank below `converged`? Today the two tie and Rwp decides.
4. **Open, not a pick.** When every rung of a pattern raises, does the series carry on from the
   last good state (`on_error="carry"`, today) or stop (`"raise"`)?
5. Does a kept attempt carrying an `error`-level diagnostic count as diverged, for the ladder
   and the quarantine alike? Today only `status == "diverged"` does.

**Evidence.**
- The rungs cost 838-904, 1 623 and 2 863 iterations on CPD sample 1 (WP-1051,
  `sequential.py:550-555`). A diverged kept attempt seeds no successor, joins no median and
  gives no first-rung sample (`:1685-1724`). EasyDiffraction moves its start values only on a
  successful fit (checked); GSAS-II and MAUD end the chain (`docs/practice.md`).
- The record names the pattern and its rung, not the state that seeded each successor
  (`README.md` § Quarantine's record); `SeriesEntry.seeded_from` lands whatever the ruling
  (task 3).
- Question 2 has no case on disk; the one truncation, T087, escalated to a converged rung.
- Question 3 has no case on disk on `main` (X17's 1d-1h end `max_iter` but never escalated).
- The ranking's last step reads Rwp (`_better`, `sequential.py:1965`). The solver minimised the
  full cost S, the data rows plus the background-penalty, Pawley-restraint and soft-restraint
  rows (`model/rows.py`, `BLOCK_ORDER`; the last stage's `StageResult.cost_final`), and Rwp sees
  the data rows alone (`RestraintReport`'s docstring). Of two minima under one weighting the
  better fit by the objective's definition is the lower S; the orders agree only where no
  penalty or restraint row exists. Two rungs are compared on one compiled model, since each
  closing stage recompiles its windows at its own answer. No case on disk is known to separate
  the two (penalty rows not checked).
- Question 4, the two readings. *Carry:* a 200-pattern batch finishes past a pattern it could
  not fit, the failure seeds nothing and `SERIES_PATTERN_FAILED` names it, as EasyDiffraction
  does (checked); Rule 1 counts such a batch among the reruns whose work the package protects.
  *Raise:* GSAS-II and MAUD stop (checked), `"raise"` keeps what converged on `self`
  (`sequential.py:1622-1638`), and the caller fixes the model before the rest is spent. Both
  protect finished work. They differ in whether the package decides to spend the rest of the
  batch past a pattern it could not fit, an action with a named dissent.
- Question 5. X17's 1c is `converged` at Rwp 10.83 with `MODEL_FAR_FROM_DATA`, level `error`:
  "do not read the values, for any purpose" (the record § Attention is a cost, clause 2).
  `RefinementResult.usable` is already `False` there (`schemas/results.py:2142`), and the code's
  docstring names the case: a `converged` status that "a batch caller reads … and believes"
  (`refine.py:8996-8999`). Seeding a successor reads the values. On disk an `error` code sits on
  a kept warm rung twice: tut05-broken scan12 in every arm, its cold rung too, so it would end
  quarantined and scan13 start from scan11 (unmeasured); and X17's 1c, under (iii) only. It
  misses X16's freeze (Rwp 0.43, under `MODEL_FAR_FROM_DATA_RWP` 0.8). `max_iter` also reads
  `usable = False` and is left out on question 3's grounds.
- `refit="single"`: GSAS-II and EasyDiffraction fit every pattern with one vary list
  (checked); the dissent is on cost only (trigger: staged 1 253 evaluations, collapsed 1 603).

**The case against.** The rungs and their order rest on one real family's iteration counts,
and the give-up point on an injected divergence. A refiner whose model makes the staged plan
the cheaper first rung would order it first; `refit="stages"` is that caller's way. On
question 3, a refiner ranks an unfinished fit below a finished one. On question 5, a refiner
whose model is wrong at that pattern (tut05-broken's cell × 1.05) fixes the model, and a cold
restart buys nothing there (24 evaluations); and the trigger would rest on the `error` codes'
own thresholds (`MODEL_FAR_FROM_DATA_RWP`, not yet audited, not 2003's).

**My pick.** 1: pass. 2: yes, test `diverged` before `truncated`; no refiner keeps a diverged
fit over a finite one. 3: keep the tie, and rank by the full cost S, not Rwp; a `max_iter`
status can mean the closing stage's last iterations at a good answer. I would change my mind
if a `max_iter` attempt with the lower cost is found farther from its family's reference than
a converged one. 4: no pick; the two readings go to you as they stand. 5: yes, after one arm
(`status` with an `error`-level kept attempt read as diverged, on tut05-broken and on CPD
closing off under (iii)): "seed no successor from a diverged fit", read as the package already
reads `error`. Changed 2026-10-25: the ranking reads the full cost (it read Rwp); `on_error` is
a question (it was tier 2 with the dissent named, which a default switching on an action
cannot be under the record's "a dissent counts"); 5 is new, from X17.

**Rows that follow.** `_chain.quarantine` and `_ladder` tier 3, kind 1, grounds naming the
injected case (and, under 5, X17). `SEQUENTIAL_UNRECOVERED` tier 3, response `warning`; its
suggestion tier 1. `SeriesEntry.rung`, `.rungs_tried`, `.rungs_raised` tier 3, the ladder's
records. `_prefer` tier 1 for its cost step; its truncated and diverged steps tier 3, in the
order ruled in 2. `fit:refit` tier 2. `fit:on_error` and `_chain.on_error_carry`: under
`"carry"`, tier 3, approved as the series' protection of a long batch, GSAS-II's and MAUD's
stop named; under `"raise"`, the default changes and `"carry"` becomes the caller's.
`seeded_from` tier 1, a record. If 1 fails, the ladder becomes the caller's (`reseed=False` by
default) and the quarantine stays, since it does not depend on `reseed` (`sequential.py:1699`).

---

## C3. The first-rung budget

**Stakes** (validating: the planted truth; verifying: the unbounded chain). Every value of a
pattern whose winning first rung the bound cuts. On `main`, at 3.0, it moves one pattern of
the 514 run with and without it (CPD, planted, its null twin, trigger): planted T087, the blank
frame, and toward the truth. With the bound the scale is 0 and the zero shift 0.00597, held
esd-less (truth 0 and 0.006), worst key path the background's c0 at 1.5 esd; without it, scale
7.32(70)e-8 and zero shift −0.0231(48), 6.06 esd from truth. Against the unbounded chain: 6.06
esd at T087, 1.65e-4 at T088, ≤ 8.5e-6 after. Under `reseed=False` its forced escalation is
what keeps 40 patterns from freezing (X16). Dissenter named: a refiner on a chain where one
pattern's winning rung costs several times its neighbours'. T087's unbounded first rung cost
108 evaluations against a running maximum of 11 (9.8×); the constant was calibrated on a worst
ratio of 1.29 (`sequential.py:196-199`).

**Rows.** `FIRST_RUNG_FACTOR`, `FIRST_RUNG_SAMPLES`, `fit:first_rung_factor`,
`_first_rung_budget` (row-less).

**The decision.** The record put this bound in the answer-invariant class on two chains (0 of
1 030 and 0 of 392 accepted values moved, 2.3× margin). It is not invariant at its default:

- Since the closing stage, a truncated warm stage that the closing stage then converges reads
  `converged` (`refine.py:5171`). Neither the forced escalation (`sequential.py:1563`) nor
  `_prefer` sees the truncation (X1, outcome 1).
- `closing_stage()` copies the last stage's `max_iter` (`strategy/staged.py:392`), so the cap
  reaches the closing stage too, stage by stage, while the budget's sample sums the warm and
  closing stages (`sequential.py:1604`).
- With both fixed, T087's winning rung is still 9.8× the running maximum, past any margin at
  3.0. The ratio, not the defects, breaks invariance.

So: (a) default `None`, no bound unless a caller asks, which makes `first_rung_factor` the
caller's; (b) keep 3.0 at tier 3 and judge it on the ground, since it moves values; (c) fix the
defects and raise the factor until planted is covered, then `invariant` with a biting arm in
the test. And under `reseed=False`, should a bound apply at all?

**Evidence.** The saving the bound was built for (1.36× the chain's evaluations where it binds,
`sequential.py:1102`, measured under the fence) is 49 evaluations of 13 083 on planted on
`main`, none on CPD, the null twin or trigger; T087 itself cost 2 more (110 against 108). Under
C1's (i) a warm rung loses only by diverging or raising, so a bound would truncate nothing but
winners. T087's move comes through the forced escalation: `warm_staged` floors the scale, and
the absent-phase hold (WP-1301) holds what a blank frame cannot see. The unbounded warm rung
converges instead with the widths walked (`RESOLUTION_NOT_POSITIVE`). Both invariance tests
assert bit-identity and every kept first rung under its budget, so they see neither outcome.
Under `reseed=False` a bitten first rung escalates anyway (`sequential.py:1563`, `:1571-1573`),
against the docstring at `:1079-1085` (X2). Without the bound there (`off_nobound`), T088-T127
freeze at the state T087 hands on (Rwp 0.433-0.435 against 0.041-0.044, the scale 40-61 esd
from truth), nothing escalates, and the chain recovers at T128 (X16). `status` without the
bound escalates neither T087 nor T088, both `converged`, so by reading it freezes the same way;
the fence catches it (`on_nobound` sends T088 to its cold rung).

**The case against (a).** It gives up WP-1127's saving, which on `main` is 0.4 % on one family.
And it exposes X16 in the default: with C1's (i), no bound is `off_nobound` on planted. That
argues for fixing X16 first, not for keeping a tier-3 number because it hides a defect.

**The case against (c).** Any factor above 9.8 is fitted to T087, the data it would be tuned
on.

**My pick.** (a), with both defects fixed so an opt-in bound does what its docstring says (read
the truncation off the rung's own stages; cap and sample one quantity), and no budget under
`reseed=False` (X2). The pick holds against Rule 1: the bound is an efficiency bet that moves
an accepted value, so it is neither invariant nor an act every refiner would take, and no
program truncates a first rung. It lands after X16 is fixed, not before: removing the bound by
default, or under `reseed=False`, reproduces the 40-pattern freeze until X16's cause is found.
Changed 2026-10-25: re-based on `main` (T087 moves 6.06 esd, toward the truth, not 39.3 esd),
and ordered after X16. I would change my mind if X16's cause cannot be fixed in the chain, or if
the fixed bound at 3.0, re-run on planted and both invariance families, moved no accepted value.

**Rows that follow.** (a): `fit:first_rung_factor` caller; `FIRST_RUNG_FACTOR` removed (the
caller names the factor); `FIRST_RUNG_SAMPLES` stays inside the opt-in at tier 3, or becomes a
second caller argument; `_first_rung_budget` rides the caller's row. (b): all four tier 3 with
approval, both docstrings corrected. (c): all four `invariant`, the fast test gaining planted
and an arm where the bound bites a winner.

---

## C4. The discontinuity scan

**Stakes** (validating: the planted events; no value moves). The scan reports, and
`verify_discontinuities` refits only when asked. On disk it flagged planted's background step
(T050) and blank frame (T087), did not flag its unmodelled phase (from T124) or its transition
(T186), flagged CPD 1a → 1b with the closing stage off (corundum's scale, where the weighed
fraction goes 1.15 → 94.31 wt % by design), flagged three steps on tut05-jump, and flagged
tut05-broken only under an infinite fence. Dissenter named: the maintainer's own example, a
jump that is a transition, a sample shift, a beam dump or a wrong model.

**Rows.** `SEQUENTIAL_DISCONTINUITY` (+ suggestion), `DISCONTINUITY_FACTOR`,
`DISCONTINUITY_SIGMA`, `MIN_POINTS_FOR_DISCONTINUITY`, `_verify_discontinuities` (row-less),
`_relative_paths` (row-less).

**The decision.**
1. Approve the demotion the WP's Context states: the code, its suggestion and its three
   constants go. The statistic becomes `SeriesResult.steps`: every step in esds, largest first,
   no threshold. Its `rietx.help` entry carries the reading (what a jump can be, and that a
   symmetry-mode refinement separates the cases), and the trajectory block gets one line naming
   it.
2. With no flagged pair left, what does `verify_discontinuities=True` refit? (i) The pairs the
   caller names. (ii) The largest *k* steps, *k* the caller's. (iii) The largest *k* with a
   package default *k*, which is a package number inside an opt-in switch and would be tiered
   here before it lands (WP Context).

**Evidence.** The thresholds (5× the median step and 3σ, from 5 points; `sequential.py:228-229`,
`:249`; no measurement) decide whether the diagnostic exists, so § Demotion leaves none. Three
readers of the flagged pairs move: `SeriesResult.discontinuities`, the trajectory plot's
shading, and `_verify_discontinuities` (`sequential.py:1813-1903`). The cold-refit ratio lives
in the removed code's `Diagnostic.value`, so it needs a field (`SeriesStep.cold_ratio`, name to
choose). Each verify refit pays the automatic profile interval (X10; a fix below).
`_relative_paths` is arithmetic.

**The case against.** Agents stop on stated criteria (v1.3: 7 of 8), and `steps` states none.
The record's answer: a contested demotion is measured on agents and lands whatever the result,
the explanation reworked if the result is poor.

**My pick.** 1: yes. 2: (i) or (ii), both the caller's; not (iii). Unchanged from the draft.

**Rows that follow.** `SEQUENTIAL_DISCONTINUITY`, its suggestion and the three constants
removed, the reading moving to the help entry of `SeriesResult.steps` (tier 1, a record).
`_verify_discontinuities` caller; `_relative_paths` tier 1; `fit:verify_discontinuities`
re-read as caller once 2 lands. If 1 is refused, the three constants are tier 3 and owe the
mechanical ground, which two real families cannot meet.

---

## C5. Path dependence

**Stakes** (verifying: the chain against its reverse; no value moves). The reported entries are
the forward chain's either way. None on disk in this WP's reseed arms, which ran no
`direction="both"`; on three synthetic families the largest gap was 0.351σ (trigger,
`phases.1.lor_strain`), with no flag (X12, before WP-2045). Dissenter named: a refiner reading
n paths × m patterns at 3σ, where chance flags are expected; the largest flags on record were
axis relabellings (81.5σ in Fddd, `docs/skill/rietx/references/series.md:136-150`).

**Rows.** `PATH_DEPENDENCE_SIGMA`, `SEQUENTIAL_PATH_DEPENDENT` (+ suggestion). Applied already:
`NOISE_FLOOR_REL` (tier 1), `SEQUENTIAL_PATH_CHECK_INCOMPLETE` (+ suggestion, caller).

**The decision.** The switch is the caller's (`fit:direction`, caller since 2026-10-24), but 3σ
is a package number used once it is on. It has no provenance (`sequential.py:245`) and decides
whether the code exists. 1: approve demoting it to a record field of each path's
forward-backward gap in combined esds, per pattern, largest first, with each walk's `rung`
beside each gap (X15: one pattern can be kept cold in one walk and warm in the other, and the
gap then measures the ladder). 2: split `SEQUENTIAL_PATH_CHECK_INCOMPLETE` into a `warning`
code (the comparison did not run) and an `info` one (it ran on fewer patterns), so each takes
one literal response.

**Evidence.** X12: with the closing stage the gaps shrink 17× and 37× on the two toy ramps and
7 % on trigger, at 1.2-1.35× the evaluations; no flag appears or vanishes (before WP-2045, not
re-run). CPD with `direction="both"` was not run. X15 is unmeasured; planted with
`direction="both"` would test it (about five minutes an arm).

**The case against.** As C4's: a field states no criterion to stop on.

**My pick.** 1 and 2: yes. Unchanged from the draft, plus the `rung` column from X15.

**Rows that follow.** `SEQUENTIAL_PATH_DEPENDENT` and `PATH_DEPENDENCE_SIGMA` removed; the
suggestion's three alternatives move to the field's help entry; the field tier 1.
`fit:direction` stays caller. If 1 is refused: 3σ tier 3 with approval, the code at response
`warning`.

---

## C6. The persistent-finding summary

**Stakes** (validating: the planted impurity; no value moves). It fired 34 times on trigger, 26
on CPD with the closing stage on, 25 with it off, twice on each tut05 family, and never on
planted or its twin. On planted, `FLOOR_HIT` fired on 63 of 248 patterns, 62 of them from T124
on, where the unmodelled phase is planted; at 25 % the summary stays silent (whether those hits
are the impurity's doing was not traced). Dissenter named: a refiner whose impurity appears in
the last 40 % of a ramp, hidden by "more than half".

**Rows.** `SEQUENTIAL_PERSISTENT_FINDING` (+ suggestion), `MIN_POINTS_FOR_PERSISTENCE`,
`_persistent_diagnostics.half` (row-less), `NOT_A_SERIES_FINDING` (row-less).

**The decision.** The count is arithmetic. The half cut and the five-pattern minimum
(`sequential.py:256`, `_persistent_diagnostics` at `:2445`) decide whether the code exists, and
its level is the worst occurrence's, computed at run time (`:2505`), so it can take no literal
response. Approve demoting it to a record field of counts: each per-pattern code and path with
its count, n and worst level, largest first, and one report line per top count naming the code
and the path?

**Evidence.** Origin: WP-1110's 68-pattern series, 425 `BOUND_HIT` read as "42 of 68". The
field also answers the WP's one-line-form cost: with no deliverable the code prints as one line
that no longer says which per-pattern code persisted (tutorial 05, cells 19 and 34). The
suggestion ("change the model or the plan") also fires on a declared `info` choice.

**The case against.** "42 of 68" is a stated criterion agents act on, and the field states
none. A contested demotion of a stated criterion runs the agent harness before it lands.

**My pick.** Demote, after the agent harness. Unchanged from the draft.

**Rows that follow.** The code, its suggestion, `MIN_POINTS_FOR_PERSISTENCE` and the half cut
removed; the field tier 1. If the code stays: the half cut and the minimum tier 3 with
approval, and `NOT_A_SERIES_FINDING` tier 1 by its own rule.

---

## C7. Width growth (a ruling for WP-2004)

**Stakes** (validating: #451's soak, its width planted; no value moves). Silent on CPD (real);
fires on issue #451's synthetic soak; #451's operando chain is not on disk. Dissenter named: a
refiner whose strain grows for real while GoF rises for a second, independent reason; the
suggestion names only the missing component.

**Rows.** `SEQUENTIAL_WIDTH_GROWTH` (+ suggestion), `WIDTH_GROWTH_FACTOR`,
`WIDTH_GROWTH_GOF_FACTOR`, `WIDTH_GROWTH_SIGMA` (`sequential.py:281`, `:299`, `:305`),
`_WIDTH_SUFFIXES` (row-less, tier 1).

**The decision.** Three tier-3 thresholds decide whether the code exists, on one real family.
Hand WP-2004 the ruling that it becomes a record field: per phase width, its ratio to its first
measured value with that ratio's esd, the growth in esds, the GoF ratio and the pattern's
`rung`, largest first, with a help entry naming both readings?

**Evidence.** X6 (before WP-2045, not re-run): on the soak, three trigger arms. With the fence
on, all four soaked patterns climbed all three rungs (254 evaluations against 71), and every
value lay within 5.1e-5 esd of the other arms; the finding was identical in all three (3.6×
from fB = 0.00 to 0.10 with GoF 3.1×, 6.8× at 0.20). The ladder can only lower a pattern's GoF,
so it cannot create a finding.

**My pick.** Yes; the three constants go to WP-2004's `### Inherited` with that ruling, and
nothing is bumped here. Unchanged from the draft, plus the `rung` column from X6.

**Rows that follow.** The code, its suggestion and the three constants are WP-2004's to remove
under `THRESHOLDS_VERSION`; their rows record the ruling and the hand-off. `_WIDTH_SUFFIXES`
tier 1, no row.

---

## C8. The moment carry (rare feature)

**Stakes** (no reference: none on disk). The floor moves a successor's starting modulus, never
an entry's own value. Cr₂WO₆ 150 K fires `SEQUENTIAL_MOMENT_HOLD` in every arm, but it is the
last pattern and seeds no successor. Dissenter none found (an ascent out of the floor
terminates at once, `tests/test_magnetic_series.py:23-27`).

**Rows.** `_floor_unsupported_moments` (row-less), `SEQUENTIAL_MOMENT_HOLD` (+ suggestion),
`SEQUENTIAL_MOMENT_ONSET` (+ suggestion).

**The decision.** 1: does the floor pass under the rare-feature clause (one synthetic ramp, one
real neutron pair), tier 3 with grounds saying so? 2: split `SEQUENTIAL_MOMENT_ONSET`, which
raises at a computed level and again through `model_copy` (`sequential.py:2699`, `:2784-2858`),
into an `info` bracket and a `warning` code for an unconverged supported side or two chains
that disagree?

**Evidence.** `floored[k]` is written at the start of pattern k, before its ladder runs
(`sequential.py:1531-1532`). If k then keeps its cold rung, which starts from the initial
models, `floored` still lists it and `SEQUENTIAL_MOMENT_HOLD`'s "reseeded to its floor on N
successor patterns" counts it (`:2656-2674`; X7). A quarantined pattern's moments seed nothing:
the floor passes through it to the next pattern (comment `:1495-1501`). No test combines a
floor with an escalation or a quarantine.

**My pick.** 1 and 2: yes. `SeriesEntry.floored` (task 3) is set where the kept attempt started
from the floor, so the message can stop cutting its list at four labels (`:2666-2673`).
Unchanged from the draft, plus X7's placement of `floored`. Test to add: the magnetic ramp with
an injected divergence on the pattern after an unsupported one.

**Rows that follow.** `_floor_unsupported_moments` tier 3, rare feature, keyed on
`SeriesEntry.floored` (tier 1, a record). `SEQUENTIAL_MOMENT_HOLD` tier 3, response `warning`;
its suggestion tier 1. `SEQUENTIAL_MOMENT_ONSET` split: the bracket tier 1, response `info`
(read off the per-pattern verdicts, never the values); the warning half tier 3 on WP-2004's
`MOMENT_SUPPORT_SIGMA`. If 1 fails, the floor goes and a successor warm-starts from the
unsupported modulus, reported through the onset bracket.

---

## C9. The carry policy and the closing stage on a warm refit

**Stakes** (validating: the weighed composition; verifying: the independent fits). The warm
start moves every value of a chain. On `main`, CPD with the closing stage on sits 2.87-5.62 esd
from the independent fits (worst path `instrument.profile.v`, `lor_strain` within 0.92), and
its mean |ΔW| over 1a-1h is 1.82 wt %, the independent fits' too. (The 10-24 figure, 7.05-14.2
esd on `lor_strain`, was a chain carrying 1b's `warm_staged` rescue; on `main` only (iii)
reproduces it.) The closing stage on a warm refit moves CPD 1b's corundum from 94.84(27) wt %,
its cell held and unreported, to 94.32(23), against 94.31 weighed. Dissenter named: GSAS-II's
default, where each histogram starts from its own values unless `Copy2Next` is ticked.

**Rows.** `refine_sequential:carry`, `:carry_hkl_intensities`, `fit:plan`, `_carry_into`,
`_reanchor_carried`, `_carry_variables`, `_collapse`, `_fit_one.declared_wavelengths` (the last
five row-less). Applied already: `fit:mode`, `fit:two_theta_limits` (tier 2).

**The decision.**
1. The warm start as Rule 1's first pick case: the caller asked for a warm-started chain by
   calling the verb made for one (`refine_sequential`, `SequentialRefinement`), and no default
   path reaches the verb's `carry` default (the GUI's series route passes its own
   `setup.carry`, `src/rietx/gui/session.py:1695-1699`). The package then chooses only *what*
   is carried: every entry (`carry=("*",)`), or only the varied ones, as GSAS-II's `Copy2Next`
   and EasyDiffraction carry. Approve that reading, with the `"*"` default `invariant` once a
   test shows the two agree?
2. `carry_hkl_intensities=True` at tier 3, pending a Le Bail and a Pawley chain run carried and
   not?
3. `fit:plan` at tier 3, by extending B7's approval to the series seat?
4. Does a warm refit run the closing stage (`_collapse`, `sequential.py:470`, carrying
   `closing_window_tol`)? (a) Yes, as today. (b) No.

**Evidence.**
- The warm start is EasyDiffraction's (checked) and FullProf's cyclic mode's (inferred);
  GSAS-II's default is `carry=()` here, every entry restarting from the initial models. No
  program carries extracted intensities by default; GSAS-II does under its opt-in `Copy2Next`.
- Every entry against only the varied ones: the two differ only where an entry no stage frees
  changes during a fit, which only a package action does (a re-derived tie, a seed, a restored
  hold, a cell reset, the moment floor). The test: the chain with `carry=("*",)` against
  `carry` set to the plan's `turn_on` globs, accepted values asserted bit-identical and every
  differing path named. Each such path belongs to an action tiered on its own; where one moves
  an accepted value, `carry`'s default is tiered on that path (tier 3, the two programs its
  dissent). Not run.
- Question 4 on `main`. X3's runaway was the declared warm stage stopping early, which WP-2045
  fixed; `intermediate_ftol=None` moves the CPD chain ≤ 2.1e-4 esd (X13, moot). With the
  closing stage every CPD pattern keeps its warm rung (644 evaluations, 708 without), and 1b's
  corundum sits 0.04 of its esds from weighed, against 1.96 without. X12 (before WP-2045): it
  narrows the path-dependence gaps (17×, 37×, 7 %) at 1.2-1.35× the evaluations. Its cost can
  be large: Cr₂WO₆ 150 K's warm rung spends 377 evaluations in its closing stage, against 115
  for the whole independent fit (WP-2036's).
- X11 (before WP-2045): with the width twin hold, a chain carrying everything but the scales
  averages Rwp 0.1282 on CPD 1a-1h, against 0.1256 carrying everything and 0.1258 independent
  (a strict xfail, `tests/test_acceptance_sequential.py:229-259`); values not compared. The
  default carry is not the one that degrades.
- X16 and X17 each start from a carried row the previous pattern could not determine (T087's
  walked widths; CPD 1b's `axial_sl` on its floor, esd 251). Whether *what is carried* should
  skip a row `ParameterTable.unmeasured_rows` names is for their investigations.

**The case against.** For 1: GSAS-II's default dissents from the warm start, which the caller
decided by calling the verb; it survives as `carry=()`. For 4 (b): dropping the closing stage
leaves CPD 1b degraded and uncaught. For 4 (a): its cost along a chain is unmeasured
(WP-2036's).

**My pick.** 1: yes. 2: tier 3, pending. 3: yes. 4: (a). For X11, measure QPA against weighed
for the two carry policies on CPD 1a-1h before touching the twin hold (candidate: hold the twin
columns at pattern 0's instrument-only value, `docs/practice.md` § Instrument and specimen
widths refined together). Changed 2026-10-25: 1 was tier 2 with GSAS-II's dissent approved,
which a default switching on an action cannot be under "a dissent counts"; the warm start is
the caller's request and only what is carried is the package's. 4 is re-based on `main`: the
10-24 brief read X3's runaway as the closing stage's own, which WP-2045 and X13 refute.

**Rows that follow.** `carry`: the warm start caller (the verb is the request), its `"*"`
default `invariant` once the test lands; `_carry_into` with it, keyed on `seeded_from`.
`carry_hkl_intensities` tier 3. `fit:plan` tier 3 on B7's approval. `_reanchor_carried`,
`_carry_variables` and `declared_wavelengths` tier 1, no row (no choice beyond `carry`'s, or a
diagnostic's reference). `_collapse` tier 3 for its details (no stage seed, the plan's largest
`max_iter`, the closing stage carried); its `seed=0.0` is re-read with X17's investigation. If
4 (b): `_collapse` drops `closing_window_tol`, and every closing-on chain number in this batch
is re-run.

---

## C10. The joint fit

**Stakes** (no reference: no joint family in the reseed measurement). The joint holds move the
shared columns they hold. None on disk beyond the synthetic fixtures; dissenter none found
beyond those of the 2002 rulings they inherit.

**Rows.** Proposed with a row: `PARAMETRIC_TARGET_UNSEEN` (tier 3 on B1's threshold, response
`warning`), `PARAMETRIC_FORM_REJECTED` (tier 2 on `FORM_TEST_LEVEL` once X14 is measured,
response `warning`), and their suggestions (tier 1). Sixteen row-less entries, two of them (the
joint absent-phase hold and its release) proposed a row of their own. Applied already:
`SIZE_NORMALISED_ACROSS_WAVELENGTHS` and `STAGE_FREED_NOTHING` (tier 1), `PARAMETRIC_OUT_OF_RANGE`
(caller), each with its suggestion.

**The decision.**
1. Confirm that 2002's rows cover six joint holds, each of which writes the single runner's
   record field from the single runner's statistic: `_hold_scale_b_ridges_multi` →
   `scale_b_held` (tier 1); `_hold_flat_moments_multi` → `moment_flat_axes` (tier 1) and
   `moment_turned` (B2); `_hold_width_twins_multi` → `width_twins_held` (approved
   2026-10-23); `_reset_cell_runaway_multi` → `cell_reset` (B8); `_run_plan.seed` → `seeded`
   (approved 2026-10-21); `_freeze_cell_windows_multi` → the single runner's cell-window row
   (B8, approved 2026-10-20). The joint fit refuses Le Bail and Pawley, so no force-fix exists
   here.
2. The joint absent-phase hold is not covered. `_hold_unsupported_phases_multi` and
   `_rehold_multi` write B1's fields (`held`, `released`, `collapsed`) but judge support by
   `CompiledModel.phase_support` alone, the scale's conditional z, at the stage start and the
   answer (`_joint_unsupported_phases`, `multi.py:401-431`). The single runner reads the
   marginal significance (`refine._answer_significance`, WP-1523) at the answer and beside the
   screen at the start (`refine.py:1510-1516`), and the screen bounds it from above
   (`refine.py:2081-2083`). So under the same 3σ the joint fit holds and restores less. (a)
   Align the joint path with `_answer_significance`. (b) Give the screen its own row, tier 3
   with approval: B1's 3σ on a second statistic.

**Evidence.** The joint docstring defers the alignment: "its report is WP-1341's to define"
(`multi.py:418-421`). Aligning moves which phases a joint fit holds; no joint case on disk
differs, and no joint family was measured here. Tier 1, no row: `size_value_scales`
(Scherrer), `bound_intersection` (a shared column satisfies every histogram's box),
`_joint_unmeasured_phases` (the joint face of `RefinementResult.qpa`'s row),
`_freeze_strain_cap_multi` (the strain cap's rule over the union of ranges; no test names it).
`fit:weights` (1.0: the joint χ² is the sum of each histogram's own) and `SharingMap.is_shared`
(Von Dreele 1997, cited at `multi.py:6`, not read here) sit at no `DEFAULT_SEATS` seat.
`_ticks.extra_components` decides nothing. `_parametric_form_tests.at_bound_hold` (tier 3)
holds `staged.bound_findings`' columns on their bounds in both fits of the form test
(`multi.py:2422-2444`); a joint fit can pass `BVLS_MAX_COLUMNS` (128) and leave the exact
active set, where B16's margin was not measured (X14).

**The case against (a).** It moves joint answers before WP-1341 defines the joint report. And
(b): two statistics under one approved threshold for one act, where the record tiers a
statistic and a threshold separately and the joint statistic was never on trial in B1.

**My pick.** 1: covered as listed. 2: (a), after one joint fixture where the two statistics
disagree shows what moves; until then the two entries carry tier 3 on (b)'s wording.
`PARAMETRIC_FORM_REJECTED` and `at_bound_hold` wait for X14 (a joint parametric fit above 128
columns, its at-bound set checked against a ≤ 128-column refit). The `vars.X` escape is a fix
below. Changed 2026-10-25: the joint absent-phase hold was listed as covered by B1.

**Rows that follow.** The six holds `covered`, no row of their own. The joint absent-phase hold
and its release a row of their own (a hand row, B14), tier 3 until 2 lands. The four tier-1
entries no row. `PARAMETRIC_TARGET_UNSEEN` tier 3, response `warning`. `fit:weights` and
`is_shared`: a hand row each, or a `DEFAULT_SEATS` seat for `MultiHistogramRefinement.fit`.

---

## C11. Caller and invariant rows

**Stakes** (none: no reported value moves). Dissenter none found.

**Rows.** Proposed: `fit:x`, `fit:x_label`, `fit:labels`. Already tiered: the eleven caller rows
of 2026-10-24 and, applied, `SEQUENTIAL_CANCELLED` (+ suggestion), `fit:prepare`,
`fit:constrain`.

**The decision.** `x`, `x_label` and `labels` are `invariant` once an arm each joins
`test_a_series_observed_is_the_series_unobserved` (`tests/test_answer_invariant_defaults.py:171`);
`labels` needs a label-blind compare, since `chain_answer` carries the labels.

**My pick.** Yes. `fit:direction` and `fit:verify_discontinuities` are re-read when C5 and C4
land.

---

## Fixes that need no ruling

Each contradicts the package's own docstring or invariant and moves no reported value. Where a
fix would move one, it is in its class instead: no budget under `reseed=False` and the two
budget defects (C3), `diverged` before `truncated` in `_prefer` and the full cost (C2), and
aligning the joint fit's support statistic (C10).

1. **`first_rung_factor`'s docstring and `FIRST_RUNG_FACTOR`'s comment.** "A bound that bites
   costs an escalation and never an answer" (`sequential.py:1104-1107`) and "cannot reach the
   answer" (`:202-212`) are false twice: a hidden truncation costs no escalation (X1, outcome
   1), and planted T087 cost an answer (6.06 esd on `main`). Rewritten to whatever C3 rules.
   Moves nothing.
2. **`reseed`'s docstring** (`sequential.py:1079-1085`): "Switching it off leaves each pattern
   with its first rung" is broken by the forced escalation (X2). Rewritten with C3's answer.
   Moves nothing by itself; the fix the docstring describes (no budget under `reseed=False`)
   is `off_nobound`, so it waits on X16.
3. **`_ladder`'s and `_better`'s docstrings** (`sequential.py:559-561`, `:1962`) say
   "convergence first"; `_better` prefers a non-diverged fit, and `max_iter` ties `converged`
   (X5). `docs/practice.md`'s rietx row says the same ("convergence before Rwp"). Moves
   nothing.
4. **`reseed_factor` is not validated** (`sequential.py:1030`). `inf` or `nan` turns off the
   fence, `SEQUENTIAL_RWP_OUTLIER` and the scan's above-fence drop together (X9: four outlier
   findings to none on the soak, a discontinuity gained on tut05-broken); zero or a negative
   factor escalates every warm rung. Refuse non-finite and non-positive values. It lands with
   C1's answer, since today `inf` is the only way to ask for status-only (the measurement uses
   it).
5. **Every rejected rung and every verify refit pays the automatic profile interval** (X10).
   `_fit_one` builds a plain `Refinement`, whose `_auto_intervals` defaults to `True`
   (`refine.py:2334`; the trial path sets it `False`, `:2608`). Cr₂WO₆ 4 K on `main`: 55
   evaluations recorded against 277 run, in 31 solver calls. Set it `False` in `_fit_one` and
   run `attach_stationary_intervals` once on the kept attempt; the interval never moves a value
   (`refine.py:5199-5208`), and the test asserts the kept attempt's interval unchanged.
6. **A `vars.X`-driven cell escape in a joint fit is neither reset nor named.**
   `_cell_runaway_diagnostic(cell_runaway)` at `multi.py:1632` never folds
   `refine._vars_driven_cell_escapes` (`refine.py:1705`), which the single runner folds into
   `CELL_RUNAWAY` (`refine.py:4481`, `:4711`) and names without resetting, since resetting the
   driver would move whatever else it drives (`refine.py:1664-1670`). Folding it in the joint
   fit adds a finding and moves no value.
7. **`SEQUENTIAL_MOMENT_HOLD` overcounts** (X7): it counts a floored pattern whose kept attempt
   started cold (`sequential.py:2656-2674`, `floored[k]` written at `:1531-1532`), and cuts its
   list at four labels (`:2666-2673`). Fixed by setting `SeriesEntry.floored` on the kept
   attempt (C8) and reading the message from it. Moves nothing.

### Investigations owed (not fixed here)

Two chain defects the re-measurement found, each moving every value of the patterns it
reaches; neither mechanism is verified. The measurements are `clashes.md` X16 and X17.

8. **The freeze** (X16). *Reproduce:* `measure_reseed.py --family planted --arm off_nobound`
   (about a minute), T087-T128: T087's warm rung converges with the widths walked
   (`RESOLUTION_NOT_POSITIVE`), and T088-T127 keep its state at Rwp 0.433-0.435 against
   0.041-0.044, recovering at T128 for a reason not traced. *Hypotheses:* (a) a scale just above
   its floor is lifted by no seed while the absent-phase hold holds the phase's structure;
   against it, `_collapse` seeds nothing (`sequential.py:506`), and from the bounded arm's scale
   exactly on the floor T088 recovers. (b) The width state T087 hands on separates the arms
   (T086's, held, with the bound; a resolution function that is not positive without it).
   Blocks C3's (a) and fix 2. **Resolved 2026-10-26**, neither hypothesis: the LM driver's
   `LinearInequality.violated` dropped every Γ_L row once X and Y both sat at 0, so T087's
   second solve walked Y to −0.0137 with Γ_L negative everywhere (`clashes.md` X16; fixed in
   `0bd7823`). C3's (a) and fix 2 are unblocked.
9. **The cascade** (X17). *Reproduce:* `--family cpd-noclose --arm status_runaway` (about 20
   minutes), 1c-1h; or, with no option (iii), warm-start 1c from `ref_seeded`'s 1b with the
   closing stage off, which tests whether the floored `axial_sl` alone does it. *Hypotheses:*
   (a) `_collapse`'s `seed=0.0` (`sequential.py:506`) leaves the floored row where it is.
   (b) The windows are compiled at `axial_sl` 0 and the parameter walks to 34.8 inside one
   solve, with no closing stage to recompile: `MODEL_FAR_FROM_DATA`'s docstring names that
   frozen-window signature (`refine.py:9003-9008`), and `_collapse`'s comment records a plateau
   at `axial_sl` 555 on 1b before WP-2045 (`sequential.py:510-515`); against (b) alone,
   `FROZEN_COMPILE_STALE` fires on 1c under `status` too, which did not collapse. C2's
   question 5 catches it. **Narrowed 2026-10-26**: the second reproduction ran. From the
   independent 1b, both apertures on 0, the warm 1c collapses with the closing stage off
   (Rwp 10.724) and with it on (0.791); with `axial_sl` lifted to 0.011 it recovers
   (0.10881). The default chain is spared only because its kept 1b ends off the floor. Reading (b) through
   WP-1938's rule: a floor where the axial column is nearly flat (`clashes.md` X17). The fix
   is a real floor or lift for the apertures, owed in a WP of its own.

---

## Appendix: findings that are not decisions

- **`SeriesEntry.n_iterations` leaves out the interval refits** (X10): Cr₂WO₆ 4 K records 55
  against 277 evaluations run. Every evaluation count in this batch is the recorded one, so
  real cost is higher wherever an interval ran (any pattern with a stationary moment angle).
- **The joint runner seeds no Stephens block** where the single runner does
  (`Stage.strain_seed`; WP Context).
- **CPD 1b with the closing stage off reports its majority phase with its cell held.** Corundum,
  94.84(27) wt %, has no cell rows in the warm rung's result, and `PHASE_UNCONSTRAINED` fires
  (reproduced on `main`). The warm start carries scales from 1a, where corundum is 1.15 wt %
  weighed. Not traced; if the support test at the warm stage's start reads the carried scale,
  it is a carry × absent-phase-hold clash the clash table does not list.
- **The middle rung's Rwp is recorded nowhere** (`rwp_of` is local, `sequential.py:1545`); only
  the first rung's (`rwp_warm`) and the kept one's are.

Line numbers in the sections revised 2026-10-25 are this branch's after `main`'s `9ad4d1f6`
merged; elsewhere they are `dd13648`'s, where `src/` matches `clashes.md`'s `ded5c3f`, within a
line or two of the revised ones. `classes.md`'s have drifted by a few lines.
