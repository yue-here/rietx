# 9b. Series: refine a ramp as a chain, and check it both ways

Load it for an in-situ ramp, a parametric sweep or a tray of related specimens.

*A reference file of the `rietx` skill. The body it belongs to is [`SKILL.md`](../SKILL.md); section numbers are the ones the body cites.*

An in-situ ramp, a parametric sweep or a tray of related specimens is
`rx.SequentialRefinement` / `rx.refine_sequential`: N separate refinements,
each warm-started from its predecessor.  (One *joint* residual over patterns
that share structural parameters is the different verb `rx.refine_multi`.)
What comes back is a `SeriesResult` — per-pattern summaries plus
`trajectory(path)`, `qpa_trajectory(phase)`, `to_table()`, `write_csv()`.

```python
series = rx.refine_sequential(patterns, structure, instrument,
                              x=temperatures, x_label="T (K)",
                              plan="lab_sample_refine")
a_of_T = series.trajectory("phases.0.cell.a")     # x, value, stderr
```

`x` is the series coordinate, and where it comes from is the file: a reader
puts a scan's own temperature in `data.metadata["temperature_k"]`, and
`rx.io.readers.list_scans(path)` reports the same number per scan before any of
them is read.  Today the Bruker `.raw` v3 range header is the one format here
with such a field; the others record no specimen temperature and none is
guessed from an axis named for something else.  A missing key is a file that
recorded nothing — **refuse rather than substitute an ambient value**, because
an invented coordinate makes the trajectory a fiction while every fit in it
stays perfectly good.

What an operator must know, all measured:

- **Chaining is worth ~3x in iterations, not in accuracy.**  On the eight
  round-robin sample-1 mixtures: 2863 iterations unchained, 904 chained, at
  identical Rwp and identical weight fractions.  Use it to make a long series
  affordable, never to make an individual fit better.
- **What licenses a chain is physical continuity, and a *tray* has none** — so
  of the three cases above, the tray is the one to think twice about.  Chaining
  eight ex-situ YBaCo₄O₇ specimens that shared only a method *created* the
  disagreement it was then used to measure: refitting them as independent cold
  points shrank the referenced pattern's Rwp gap by **13×** and its cell-*a* gap
  by **12×**, and what had been recorded as
  that campaign's largest cell-*a* disagreement with TOPAS was the chain's own
  artefact.  Warm chaining is ~10x cheaper per pattern (**0.16 s against
  1.82 s** measured on one series), and on specimens with no physical ordering
  that is the wrong saving.  Inside a *genuine* ramp the same test is worth
  running step by step rather than once: on that series a different, larger
  jump survived having no chain, so that one was real — chaining artefacts are
  established or refuted transition by transition.
- **The default `refit="single"` collapses the plan into one stage** for every
  pattern after the first.  The staged turn-on order exists to keep early
  stages conditioned from a *poor* starting model; a converged neighbour is not
  one.  A pattern where that turns out to be wrong is caught by the reseed
  fence, which **escalates one rung at a time** — the full staged plan from the
  warm state, then the full staged plan cold — and keeps the best attempt.
  `entry.rung` says which one produced the values and `entry.rungs_tried` says
  what else was tried; `entry.reseeded` still means only the cold rung won, so
  a `"warm_staged"` point is one whose chain is unbroken.
- **A pattern that no rung recovers is quarantined, not merely flagged**
  (`SEQUENTIAL_UNRECOVERED`): it seeds no successor and its Rwp is left out of
  the median that decides every later trigger.  So a single failure cannot
  propagate down the chain or quietly raise the bar for the patterns after it —
  but it is still *reported*, and reading its parameters is on you.
- **A sequential trajectory is path-dependent by construction**, so a smooth
  curve is exactly what a poisoned chain produces.  `direction="both"` runs the
  series each way and reports `SEQUENTIAL_PATH_DEPENDENT` per parameter.  For
  any trajectory you intend to publish, run it — it is the only check that
  separates a measurement from an ordering artefact.
- **But forward/backward *agreement* is not evidence of correctness**, and the
  two failures it cannot see were both measured.  A flat degenerate band
  reproduces the same wrong answer in both directions — **|Δweight| median
  0.000, max 0.030, 0 of 35 patterns disagreeing by more than 5 pp** on a
  construction that was physically wrong — because the check compares two
  paths, not two basins.  And where findings *are* present the set is not the
  signal: `SEQUENTIAL_PATH_DEPENDENT` was non-empty on all four series of one
  tranche, and the single chain actually sitting in a wrong basin was localised
  by **σ magnitude** (98.9σ and 84.4σ on the scales the QPA is built from,
  against ≤8.8σ everywhere else).  Read what was flagged before reading physics
  into it: two of the largest flags measured anywhere — **81.5σ** for *a* and
  *b* exchanging in `Fddd` and **15.8σ** for *a* and *c* in `Pnma` — are
  degenerate axis relabellings, and the largest on
  another run (16.6σ) was a *held* cell reaching the pattern with two different
  held histories, which is bookkeeping rather than two measurements.
- **`SEQUENTIAL_RESEED` is not the net for a wrong basin.**  Its trigger is
  Rwp > `reseed_factor` × the running median of accepted patterns (default
  1.25), so it needs roughly a **25 % relative Rwp jump** — and a polymorph
  swap does not cost that.  Tested directly on 20 such patterns it fired **0
  times**; where it *can* fire it works, 6 firings elsewhere in the same run
  all keeping the chain out of the disagreement set.  A wrong basin at
  negligible Rwp cost is the case for `direction="both"` and for cold refits,
  not for the reseed ladder.
- **The `SEQUENTIAL_*` codes live on `SeriesResult.diagnostics`, one level up
  from the entries.**  Reading `entry.diagnostics` for them returns zero on
  every series, which presents as a clean run rather than as a lookup in the
  wrong place — it cost one operator a full re-run of the chain stage for nine
  series, caught only by distrusting a suspiciously flat all-zero result.
  Per-entry diagnostics are real and carry every per-pattern occurrence; the
  rollups are not among them.
- **An unrun check is indistinguishable from a passed one.**  A series whose
  forward pass completed all 125 patterns and whose **backward pass crashed**
  reports **zero** `SEQUENTIAL_PATH_DEPENDENT` findings — byte-for-byte what a
  clean series reports.  Confirm both passes completed before reading an empty
  set as a pass, and report the empty set as a measured result rather than
  omitting it.  Both safety checks are also worth pricing up front: on one
  series the backward pass was **43.9 %** of wall clock and the
  `verify_discontinuities` refits **15.1 %**, so **59 % of the run bought
  assurance rather than answers** — the right trade for a trajectory you will
  publish, the wrong one for a screen.
- **A flagged step can check itself.**  `verify_discontinuities=True` refits
  each `SEQUENTIAL_DISCONTINUITY`'s two patterns **cold and independently** and
  writes the cold step over the chain's step to the diagnostic's `value`, signed:
  near 1.0 the step is in the data, near 0 the chain made it, negative a cold
  pair that moved the other way.  Off by default because
  a cold fit is the full staged plan from the initial models; measured on a
  68-pattern ramp flagging four steps over four patterns it costs 5 % of the
  chain, and the cost scales with the patterns flagged rather than with the
  series length.  Nothing else moves: the refits are separate `Refinement` runs
  writing to their own `<label>.verify` histories.  **An abstaining
  verification is a finding, not a pass:** on a polymorph-swap exhibit the refit
  fired and then reported *"an independent cold refit of both patterns does not
  determine this parameter, so the step could not be re-measured"* — the check
  needs the parameter determined and the pathology is that it is not.  Read that
  message as `PHASE_UNCONSTRAINED` about the step, and go to a cold refit sample
  rather than concluding the step was real.

- **The check that covers both blind spots is a cold-refit sample, and it is
  affordable.**  Neither `SEQUENTIAL_RESEED` (needs a ~25 % Rwp jump) nor
  `direction="both"` (agrees in a degenerate band) sees a wrong basin at
  negligible Rwp cost, and the audited job that did see it refitted **380
  patterns cold against the chain and found 316 material disagreements, 29 of
  them at |ΔRwp| ≤ 0.5 pp** — invisible to both.  Whole job, warm chain plus 380
  cold refits plus 244 minority-geometry fits plus 2 reference fits, **57 minutes
  single-threaded**.  Sample the chain cold; it is the only check here that
  catches a cheap wrong basin.
- **One batch row applies to a chain and lives in §9c**, which a series
  operator never loads: the shared `EventStream` opens its file in append mode,
  so a re-run of a ramp writes into the previous run's log unless the path is
  rotated ([`references/batch.md`](batch.md) § 9c.13) — measured on chains.
  The companion rule — a phase that switches fully in and fully out along the
  ramp is a degenerate split rather than a coexistence, and whether its
  fraction is an observable at all depends on the transition's order — is this
  file's own *Is the transition first order?* section, not a batch row.
- **A trajectory of phase fractions is a QPA question at every point of it, and
  the background is what decides it.**  Fractions ride on scales, and an
  over-flexible background biases scales silently while *improving* every
  agreement index — which is why §4b's QPA row reads
  `report.background.worst_absorption` before any statistic beside it.  Nothing
  in `SeriesResult` repeats that check for you, and no `SEQUENTIAL_*` code can:
  they compare each pattern against its neighbours, and a background too
  flexible for the *specimen* is wrong in the same direction at every point, so
  the trajectory it produces is smooth, self-consistent and false.  Measured on
  a real 68-pattern reel: a 12-term cold fit put LT-ZrMo₂O₈ at **77.9 wt %**
  when that phase is not present at all, Rwp 0.0821 against 0.0822 for the
  correct answer, with a difference curve that looks fine; over the round the
  absent phase took **40-96 wt %** at an Rwp within 0.01 of the right one.
  Neither Rwp nor the plot separates them.  So read
  `background.worst_absorption` per pattern — at least on the first, the last
  and every flagged step — before quoting a fraction trajectory at all.  The
  route is not `SeriesResult`, which carries summaries only, and not
  `rx.refine_sequential`, which discards the per-pattern results: use the class
  form, whose `results_` holds them.  `sr = rx.SequentialRefinement(structure,
  instrument)`, `series = sr.fit(patterns, ...)`, then
  `rx.build_report(sr.results_[i]).background.worst_absorption`.

Driving one: **`fit()` is all-or-nothing, so wire `on_result=` before starting
anything long.**  The per-pattern loop catches `RefinementCancelled` and nothing
else and returns its `SeriesResult` only at the very end, so one exception
discards every pattern already fitted — measured as a `LinAlgError: SVD did not
converge` at pattern 217 of 531 taking all 216 with it, and a deterministic
`LinAlgError: Eigenvalues did not converge` at index 78 destroying **103
already-fitted patterns whose values were fine, because the fit had converged
and only the error bars failed**.  Cell lengths carry no physical upper bound,
so a pattern reaching `a = −347.644 Å` raises out of the reflection enumerator
and takes the chain with it (**3 of 9 chains** on one tranche, one losing 20 of
24 patterns).  The failure mode is reassuringly narrow — across **1846
`fit_start`/`fit_end` pairs the only exceptions raised anywhere were those
reflection-enumeration guards**, no hangs, no NaNs, no silent wrong-shape
results — so a driver only has to survive that one.  `on_result=(index,
result)` fires as each pattern lands; persisting there is what saved the 103
above, and it is the single highest-value line in a series driver.

**`on_result` fires on the forward pass only, and so does `results_`.**  With
`direction="both"` the backward chain is passed `None` for the callback, so
backward-pass patterns have event-log timings and **no `RefinementResult`** — 53
of them on one run.  The backward `SeriesResult` is on `.backward_` and on
`series.backward`; any per-pattern instrumentation you plan is half-populated by
design, which matters most for exactly the check above, since
`background.worst_absorption` is unreachable for the backward pass.

**Turn history on explicitly — the two defaults disagree.**  `Refinement`'s
`history` defaults to `True` and `SequentialRefinement`'s to **`False`**, and
one harness silently lost the restorable per-pattern tree for **550 fits** by
never passing it.  Here the path becomes a *directory* of one JSONL per pattern
holding **more files than patterns**, because reseed retries write their own
(291 files for 275 patterns) — so file count is not a completion check.

When the deliverable *is* the trajectory, print its deciding rows:
`series.summary(deliverable="series")` — §4b's fourth row, and the two
statements no diagnostic can make for you.

```python
print(series.summary(deliverable="series"))
```

`carry` (dot-path globs) restricts what crosses a pattern boundary.  Reach for
it when a parameter must provably not be chained; do **not** reach for it
because a parameter jumps.  That hypothesis was tested on a series whose
composition swings 1 → 94 wt % and it is false: carrying everything is cheaper
there than excluding the scales.

`prepare=(index, data, structure, instrument)` is the other half of that, and
the case above is what forces it: excluding a parameter from `carry` only falls
back to the **first** pattern's guess, which is not the same as re-estimating
it.  `prepare` runs on the *warmed* models just before each fit, so a scale
that must be estimated from *this* pattern rather than carried or left at an
initial value has somewhere to be set.  Two smaller hooks worth passing on any
long run: `progress=` (a stream or path) emits one line per stage boundary per
pattern and is the cheap way to know a run is alive, and `labels=` names the
entries — without it every downstream table is keyed by integer.  A cancelled
series **returns** what completed, with `SEQUENTIAL_CANCELLED`.  Note that
`stage_reports=True` does *not* exist here; it is a `Refinement.fit()` argument
and raises `TypeError`, and per-stage Rwp lives on the `stage_end` events of the
shared `EventStream` instead (present on **637 of 637** payloads in one run,
where `StageResult` carries no `rwp` field at all).

Where `stage_reports=True` *does* apply — the single `Refinement.fit()` calls of a batch — it
is expensive, and the name suggests only that it adds output.  On the bundled NAC fixture it
cost **6.5×**: 1.923 s against 0.296 s, median of three, with Rwp identical to six decimal
places, so it changes nothing about the refinement.  `cProfile` puts 75 % of the fit inside
`_stage_report`, whose March-Dollase texture and Stephens strain analyses re-run at *every*
stage and each cost more than the optimiser step they describe; the solve itself is 23 %.
Sample it — the first fit, the last, anything you will plot — rather than setting it on every
fit of a long run.

That cost also sits **outside** the stage brackets, which makes one natural way of totalling a
run wrong.  Σ(`stage_start`→`stage_end`) is 11 % of wall clock with stage reports on and 50 %
with them off, and the bracketed total is unchanged between the two (0.225 s against 0.223 s)
because it only ever covered the solve.  The log is not missing the time —
`fit_start`→`fit_end` accounts for ~100 % either way — so take a fit's cost from that span,
and never from a sum of per-stage durations.

## Microstrain evolves along a chain — leave it free, or it lands in the fractions

Hold the **instrument** profile after calibrating it once, and let the **per-phase** width
terms refine per pattern.  That is not a stylistic preference: in an in-situ reaction, an
electrochemical cycle or a temperature ramp, microstrain and domain size genuinely change
along the series, and a chain that holds sample broadening fixed has nowhere to put that
change.  It goes into whatever *is* free — usually the scales, and therefore the weight
fractions, which is the one number such a run is normally for.  Measured on an 11-BM
cryostat ramp, a phase's `lor_strain` rose 0.019° → ~0.11° toward low temperature,
reproducibly and in both directions; a chain with that term pinned would have had to absorb
the same intensity redistribution somewhere else.

The mirror-image mistake is a **numeric floor carried across instruments**.  A microstrain or
size floor is a hedge against the term collapsing to zero and capturing no broadening at all,
and it has to be re-derived from the peak widths of the data in front of you.  A 0.02° floor
that behaved well on lab Cu Kα data was reused on 11-BM, where the instrumental width is one
to two orders of magnitude smaller; it pinned `lor_size` **and** `lor_strain` to the bound on
every pattern of a series and inflated Rwp 3–4× (0.546 with the floor, 0.148 without, same
pattern and seed), while `BOUND_HIT` fired on the width paths on essentially every fit.  The
package's own suggested remedy for the resulting misfit — free `instrument.profile.u` — did
not help (0.546 → 0.544).  So: measure the FWHM of two or three strong isolated peaks off the
**observed** data, keep any floor well below the narrowest of them, and say which number you
used and why.  A floor at or above the instrumental width is not a floor, it is the profile.

## A symmetry test that has not been run against a null is not yet a test

A trajectory that ends in "the symmetry changes at T\*" needs the claim checked against a
compound, or a sub-series, where the symmetry is reported **not** to change — and the check
has to be able to fail.  The reason is specific and it defeated two candidate methods on one
tranche: a lower-symmetry model carries freedom that a naive parameter count does not see —
more resolved reflections, and more atoms once sites split — so a bare ΔBIC comparison tilts
toward the lower symmetry regardless of the physics.  Applied to a cubic control it "found" a
distortion below 235 K in a compound reported cubic throughout.

What survived that control was a two-part criterion: a jump in Rwp(T) against its own
baseline scatter, **confirmed by the shape of the ΔBIC curve** — a step followed by a new
plateau, rather than a smooth decay.  Write the threshold down before running it, report the
null arm's result next to the positive one, and if the null fires too, say that the detector
measured flexibility rather than physics.  A shuffled-coordinate run on the same patterns is
the cheapest null available when no second compound is to hand: on one series it gave ~12×
the β scatter and ~3× the Rwp scatter of the true ordering.

## Is the transition first order? The order decides whether a phase fraction is an observable at all

**Establish the order before reading any phase fraction across the transition.** A first-order transition genuinely coexists, so a
parent-plus-distorted two-phase model is correct and its fraction *is* the
measurement: ZnCr₂O₄ and MgCr₂O₄ hold *both* low-temperature phases in
near-equal amounts down to base temperature, and Mn₃O₄ does the same below its
T_N — all explicit in the papers cited below, whose figures are the ones to
quote. A continuous transition never coexists, and a parent whose distortion
is undetectable never has a second phase at all — in either case the child's
metric approaches the parent's, the two become one phase, and the weight split
is unidentifiable **by construction**, which is exactly what
`HIGH_CORRELATION` on the two scales reports (ρ ≈ −0.98 on **87 of 182**
patterns, all of them above T_N). Read the symptom correctly: a candidate that
is fully in (**ΔBIC ≈ −10⁴**) at the coldest scan, out (**+9.5, weight exactly
0**) at the next, back at a third and gone at a fourth is a profile-shaping
device switched on wherever the peak shape is imperfect, so **ΔBIC across a
batch is not by itself a discriminator** even at −8 700 to −41 300 — only a
**distortion magnitude against a published value** separated them, and it
agreed with the paper to ~1 %. The observable across a continuous transition
is the order parameter, never the fraction. *(Measured: archive screening
campaign, 11-BM variable-temperature series — a compound published as showing
no detected structural transition, modelled as two phases; the first-order
coexistence figures are Kemei et al., J. Phys.: Condens. Matter 25, 326001
(2013) and Phys. Rev. B 90, 064418 (2014).)*
