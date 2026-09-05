# 9c. Many fits as one job: candidates against one pattern, patterns fitted separately

Load it when one refinement is a unit of a larger job — candidate models
screened against one pattern, or many patterns fitted independently rather
than chained (§9b is the chain, whose fits share an order and a path).

*A reference file of the `rietx` skill. The body it belongs to is
[`SKILL.md`](../SKILL.md); section numbers are the ones the body cites. Every
row carries its evidence: `(Measured: …)` names the run and its number,
`(Hypothesis: …)` names what would decide it. Where that run belongs to the
**archive screening campaign**, the tag names that corpus instead of a run a
reader can open — a screening campaign over a private diffraction archive of
laboratory, synchrotron and reactor-neutron patterns, refined against the
existing TOPAS, GSAS and XND answers for the same data wherever those survive.
The archive is unpublished and ships in no wheel, so those rows cannot be
reproduced from this repository; every number in them still comes from the log,
and no scientific magnitude of any specimen in it appears in any row.*

A batch is N separate `rx.Refinement` runs, or N branches of one history tree
([`references/history.md`](history.md)), each a whole §1-§10 job with its own
deliverable, stop rule and report. It is not `rx.refine_sequential` (§9b: each
fit is warm-started from its neighbour, so the set has an order and its
trajectory a path) and not `rx.refine_multi` (one joint residual over patterns
that share structural parameters). What the body settles for one fit is
settled here too and is not restated: the deliverable and its deciding rows
(§4b), the three stop conditions (§10), abstention (§6). This file holds only
what exists once fits are **compared, budgeted or stopped as a set**.

## Writing a row

A row is a rule an operator of a batch needs and a single fit never does, with
the measurement that produced it. From a run's logs the form is: the rule as
one imperative sentence in bold, numbered `9c.N`; what was measured — the
dataset or episode, N, the number that decides — in two to four sentences;
then the tag. `(Measured: …)` names the run. Where the run is in this
repository — a WP, an eval round, a dataset in `tests/data/README.md` — name
it so a reader can go and look. Where it is not, name the **corpus** the file
declares in its provenance line above, and name it the same way every time:
the package has to be tested on data it cannot ship, so a row measured on data
a reader cannot open is admitted, but it must be recognisable as one before
the reader acts on it. Two things the private case does not relax. Every
number still comes from the log, and anything the log does not decide is a
`Hypothesis` row: unverifiable is not a licence to be vaguer. And a scientific
magnitude derived from unpublished data stays out. The line is what the row is
about: what the *run* did may be quoted — counts, rates, wall clock, a ratio of
fit qualities, which is what the rows below are made of anyway — and what the
*specimen* is may not: a cell, a phase fraction, a domain size, a transition
temperature, and a ratio of two of those is still one of those. Quote the
shape, or a published figure, instead, which is where the lesson was anyway.
`(Hypothesis: …)` is for a
rule the logs suggest but do not decide, and names what would decide it. A
hypothesis row is not a weaker rule; it is an open question stated as one, and
§6 applies to it — do not act on it as if it were measured. Before adding a
row, ask whether it holds for one fit alone: if it does, it belongs in the
body or in §8, not here. All rows sit under *The rows*, one after another,
each closed by its tag; `tests/test_skill.py` refuses a row without one, and
`CONTRIBUTING.md` § The agent skill has the sync step.

## The rows

**9c.1 Declare each job's deliverable and stop rule before the batch starts,
and read the stop on the report, never on Rwp.** §4b's *Stop when* column is
the stop rule per job and it differs by deliverable; a batch launched without
one stops on whatever its author reached for — in the campaign's six refining
runs an external comparison, a script exit, an instruction, and for three of
them nothing: they ended waiting. *(Measured: WP-1307 round 1.1, R11 — three
of four ramp cells stopped on a §4b deliverable row, against 0 of 6 in the
86-run campaign and 0 in round 1.0, when §4b had no such row to reach for.)*

**9c.2 A candidate the data cannot see is unseen, not refuted.**
`PHASE_UNCONSTRAINED` says the phase was held for the stage because nothing of
it moved the residual (§6, rule 22): its scale at the floor is not a
measurement of 0 wt %, and its cell is the one you handed in. Screening
candidates, sort such a fit into "not testable on this pattern", never into
the rejects — and never let the batch walk it: before the hold existed, one
absent phase cost 27 % of a 35-minute session, and its chain, reproduced on 13
sub-onset patterns, took 6.7 s with cell bounds and was killed unfinished at
13 minutes without them. *(Measured: WP-1301, and WP-1307's baseline ramp run
— the flat direction's share of wall.)*

**9c.3 Rank candidates only on fits of the same channels, the same excluded
regions and the same background flexibility.** §4 makes Rwp a relative number
between fits *of the same data over the same channels*, and §4 step 17 makes
R_B flatter whichever model partitioned the intensities, so neither ranks
across protocols. A batch that varies the background order or the excluded
regions per candidate has ranked protocols, not models: on one fit, the
over-flexible background won on every agreement index while being wrong, and
`worst_absorption` (0.46 against 0.08) was the only row that separated the
two. Compare `rwp_background_subtracted` pairs, the Le Bail gap ratio and ΔBIC
for nested models, each on an identical protocol. *(Hypothesis: follows from
§4's same-channels rule and WP-1055's single-fit measurement; no batch has
measured the ranking itself.)*

**9c.4 A ranking is only as strong as the best null you actually reached, so
fit the null as hard as the candidate.** A protocol held constant across
candidates still ranks them wrongly if the baseline was left underfitted: one
symmetry adjudication's cubic baseline was **1.1 pp of Rwp worse than
achievable on the same data**, and the richer candidate's extra freedom
absorbed that deficit and won on every global statistic. The guard is to
localise the improvement where the physics predicts it rather than to total it
— windowing the six largest-multiplicity reflection families that the claimed
symmetry-breaking actually splits, **6.2 % of points captured −28 % of the
total Δχ²**, i.e. net *negative* exactly where a real distortion must
concentrate its advantage while the global numbers pointed the other way. The
same asymmetry appears in plan hygiene: restoring two Gaussian terms silently
dropped from a copied plan moved one weight fraction by **0.09 in absolute
terms** and Rwp by **0.04**, so a candidate compared against a copied
predecessor is being compared against nothing in particular. *(Measured: archive screening campaign — the cubic-versus-rhombohedral NiO adjudication,
whose ΔBIC −5553 for the richer model was real and reproducible while the
interpretation was wrong, and its windowed Δχ²; the dropped Gaussian terms are
from a low-temperature scan of a spinel series.)*

**9c.5 Budget a job from what a converged job costs on this batch, and read a
job past its budget as a diagnosis.** §8.13: a stage that takes minutes is
telling you it is degenerate. On a chain the rung budget is a factor times the
dearest *converged* first rung, never a fixed wall (WP-1127); a job several
times the median converged job is a flat direction or a degeneracy to read in
its trajectory, not a fit to wait for. *(Hypothesis: the mechanism is measured
on a chain, WP-1127, and on the ramp run's 27 %; the factor for independent
jobs is not.)*

**9c.6 Cost tracks solver iteration count and almost nothing else, so predict
a batch from iterations rather than from the model.** Stratified by pattern
size, cost against iteration count gave r = **+0.859 and +0.988** within
stratum on the two stratified batches with no sign flip, and **+0.983** pooled
on a third whose single frozen protocol needed no strata; peak broadening,
minimum phase fraction and reflection count **all flip sign** between pooled
and stratified, so each of them correlates with "which protocol is this"
rather than with work done. Stratify by (protocol × geometry) before
correlating anything against cost — pooling warm chain fits with cold ones,
and 180-point windows with 4787-point ones, manufactured a reflection-count
correlation of **+0.398 pooled (n = 976) against a stratified median of +0.052
(12 strata, n = 961)**. *(Measured: archive screening campaign R3 — three
batches, the (La,Sr)FeO₃ chemical-looping series, YBaCo₄O₇ and the six-phase
CuO/Cu₂O tranche; the pooled-vs-stratified reversal replicates, though its
magnitude does not on a batch with only two pattern sizes.)*

**9c.7 Do not carry a per-iteration cost model from one batch to another.**
The same fit machinery costs a different amount per iteration on different
data, so a regression fitted on one batch is not a package constant. One
batch's `s/iter = 4.4 µs × n_points + 2.9 ms` (r = **+0.972** there) predicted
**8.61 ms/iter** for a six-phase batch that measured **28.82 — 3.35× low** —
and sat at **0.34–0.49×** on a third. The missing term is model complexity:
six phases on the *smallest* patterns was the dearest per iteration of
anything measured, which is the opposite of what point count alone predicts.
*(Measured: archive screening campaign R3 — the regression is the (La,Sr)FeO₃
series', the 3.35× miss is the six-phase CuO/Cu₂O tranche and the 0.34–0.49×
is YBaCo₄O₇, i.e. two batches on opposite sides of the same line.)*

**9c.8 A stage that exhausts its iteration budget is not by itself waste —
pair `max_nfev` with the cost reduction it bought.** Across three batches,
`max_nfev`-terminated stages took **46.6 % / 42.9 % / 23.5 %** of stage time
at **72× / 53.6× / 18.0×** the median converging stage; the shape replicates
and weakens each time, so the multiplier is not quotable but the sink is real.
Splitting them by what they achieved is what separates the two populations: on
one batch twelve exhausted `warm_refit` stages returned a **17 % median cost
reduction** — real work needing more budget — while five exhausted `refit_all`
stages burned 30.8 s for **0.018 %**, and the pooled median of 12.7 % hides
the split entirely. Report it per stage name, and do not key a *guard* on the
stage name: three batches put the waste in three different stages
(`warm_refit`/`biso`, then `refit_all`, then `strain`), so a name-keyed guard
misses two of three. *(Measured: archive screening campaign R3 — three
batches; the waste signal is `max_nfev` **and** near-zero fractional cost
reduction.)*

**9c.9 Read terminations before blaming the iteration cap for a slow batch.**
The quieter sink is the larger one: of 63 stages exceeding 5× the median on
one batch — **9.9 % of stages and 52.5 % of stage time** — **43 terminated on
`ftol` and only 19 on `max_nfev`**. Long *converging* stages cost more in
aggregate than exhausted ones, so raising the cap addresses the smaller half
of the problem. *(Measured: archive screening campaign R3, the six-phase
CuO/Cu₂O tranche's full stage census — the run whose 40 minutes had been
attributed to the iteration cap.)*

**9c.10 Compare populations conditioned on a diagnostic; do not regress a
number against whether it fired.** Whether an unsupported phase costs or saves
time is a **threshold, not a slope**: `PHASE_UNCONSTRAINED` holds that phase's
7–9 structural parameters (9c.2), which made fits slightly *faster* on one
batch and **13.8× slower** on another, reconciled by whether holding it leaves
a flat direction behind for the solver to grind on. The methodological point
is the transferable one — on the batch where the effect is **13.8×**, the
linear correlation against the flagged fraction is **r = +0.073**, which a
regression would have reported as "no relationship". *(Measured: archive
screening campaign rounds 2–3 — the (La,Sr)FeO₃ and 11-BM GeNi₂O₄ batches,
whose signs are opposite; the same trap applies to any guard finding whose
effect is conditional rather than graded.)*

**9c.11 Sum `fit_start`→`fit_end` for a fit's cost; never sum its stage
durations.** Inter-stage bookkeeping belongs to no stage, so stage-level
totals are **systematically** low: fit-level agreed with an independent wall
clock to **0.62 %** while stage-level undercounted by **19.9 %** on one batch
and **~27 %** on another. Anyone budgeting a batch from summed stage durations
is 20–27 % low before any other error. *(Measured: archive screening campaign
R3 — YBaCo₄O₇ at −19.9 % and the CuO/Cu₂O tranche at ~27 %, both audited
against an external clock, fit-level agreeing to 0.62 %.)*

**9c.12 Pair timing events in order; never bucket them by pattern index.** A
pattern index recurs — reseed retries, verification refits, restarted segments
— so `max(fit_end) − min(fit_start)` within a bucket spans everything that
happened in between, and nothing about the result looks wrong: one segmented
recovery chain reported **700.686 s of fit time against a 147.988 s wall
clock, 4.73×**. Ordered `fit_start`→`fit_end` pairing is the fix, but it can
also *overstate* where fits are silently re-executed with no retry marker
(2.7× on one audit), so cross-check against a per-part table before quoting.
Assert event-log-summed fit time against an independently measured wall clock
on every unit of the batch — it is the only check that caught any of this.
*(Measured: archive screening campaign R3, the (La,Sr)FeO₃ chemical-looping
series and its segmented-recovery audit.)*

**9c.13 Rotate or re-path the event log before every run.** `EventStream`
opens its file in **append mode unconditionally** and writes no run marker, so
re-running a batch silently interleaves two runs into one file and every
derived duration is a mixture. It corrupted timings on two independent
batches, once reporting a **10.276 s calibration as 458.995 s — 44.67×**.
Truncate or re-path before every write, and note concurrent load on the
machine as a confound to state rather than to absorb. *(Measured: archive
screening campaign R3, the (La,Sr)FeO₃ series among two affected batches;
`history/events.py` opens with mode `"a"` on current main.)*

**9c.14 Pilot the model on a dozen patterns before multiplying it by N.** The
dominant failure at scale is not a bad fit but a *good* fit to a wrong model,
N times, and the errors that do it are invisible in the residual: a
space-group setting resolved from a bare Hermann-Mauguin symbol (**40 symbols
in gemmi's own table carry more than one setting**, and origin-2 coordinates
under an origin-1 setting converge at an ordinary Rwp with a whole reflection
class silently zeroed and **no diagnostic firing**), a unit conversion made
once in a shared calibration and therefore wrong in every pattern that uses
it, and a mis-parsed axis (**a GSAS FXYE with its `BANK` line commented out
returned `[50.0, 4399.6]°` instead of `[0.5, 43.996]°`** — same point count,
no exception, `provenance` `None`). Total cost is near-linear in length, so a
dozen patterns is a few per cent of a long run and tests all of it;
per-pattern cost is *sub*-linear in model size (**1.489 s → 4.170 s, 2.80× for
a 5.35× increase in reflections**), so the pilot's per-pattern time is an
upper bound — time it as well as reading it (9c.31). Assert a sanity bound on
every parsed 2θ axis, check a transcribed phase's cell mass against the source
file's own (**286.182 against 286.184, 7 ppm**, settled an ambiguous Cu₂O
setting whose origin-1 alternative was a 1:2 Cu:O compound — though mass
balance cannot catch the origin error above, so the two checks complement
rather than substitute), and validate any reference-file reader against check
values you did not derive. *(Measured: archive screening campaign — the Cu₂O
transcription against its own TOPAS `.inp`, the FXYE reader fallback on a
ZnCr₂O₄ pattern, and the CuO/Cu₂O tranche's five-to-six-phase cost scaling and
12-pattern timing pilot.)*

**9c.15 Re-derive the batch's inventory from the archive and de-duplicate by
file identity.** A batch scoped from a list someone wrote is scoped to that
list: one brief's own per-series counts summed to **638 rather than the 658 it
stated**, and of those 638 only **624 were diffraction patterns** — the other
14 gas-monitor markers with no diffraction angles and furnace temperature logs
— inside a directory set holding 1055 raw files in all; a whole-archive
manifest elsewhere carried **1372 rows but 1366 distinct members**, six
byte-identical duplicates that would have double-weighted four temperatures.
Assert the expected file count immediately after the selection glob, so a
wrong pattern set fails loudly instead of fitting. *(Measured: archive
screening campaign — the (La,Sr)FeO₃ tranche's 1055/638/624 count, and the
whole-archive 11-BM manifest whose 1372 entries were 1366 distinct scans, of
which the GeNi₂O₄ series contributed 215 fitted after the sentinel row.)*

**9c.16 Scope from one level above the data, and write the unrun remainder
down.** A batch scoped from the files it had already chosen looks complete
against itself, and the gap is invisible from inside the scope: one campaign
covered **3 of 10 series and left 771 patterns unrun** while reading as
finished. Two smaller instances from the same inventory — a series-looking
name that was **2 patterns with no temperature recorded**, and a folder whose
reference row count disagreed with its pattern count because it held two scan
geometries, to be filtered by filename rather than reconciled by arithmetic.
Where an arm is time-boxed out, record it as **undetermined rather than
passed** and name the exact excluded set, because an omitted arm in a summary
table reads as a clean one. *(Measured: archive screening campaign — the
inventory rebuilt one directory above the fitted set.)*

**9c.17 Give every per-unit iteration its own `try`, not just the innermost
loop.** A batch driver is judged by what one failure costs, and the guard
belongs at each level that can lose work independently: the same
reflection-enumeration guard that kills a fit fired inside a *calibration*
fit, and because that loop had no per-geometry `try`, **all of that series'
minority geometries were lost — 8 of 9 series produced them and that one
produced none**. Persist each unit's result as it lands rather than at the
end. *(Measured: archive screening campaign R3, the minority-geometry pass.)*

**9c.18 Read a code that fires on every fit as a statement about the model,
and reduce the volume before reading it at all.** Per-pattern diagnostics do
not scale and are not meant to: on 275 patterns `BOUND_HIT` fired **1289
times, 4.7 per pattern**, and `BACKGROUND_ABSORPTION` **841**. A code with no
per-pattern variation carries no per-pattern information —
`PHASE_UNCONSTRAINED` on a fifth phase fired **275/275** and a
species-fallback code **36/36** — and the finding is one level up: a single
`BOUND_HIT` is a pattern that hit a bound, while a `BOUND_HIT` in most of them
is **a bound that is wrong**, including one you imposed yourself (a
`lor_strain` floor the operator had set, flagged in **178 of 215** patterns).
Change the model or the plan; refitting reproduces it. Read *which* parameter
`where` names rather than merely that the code fired — two draft conclusions
in this campaign were wrong because a `BOUND_HIT` was attributed to the wrong
parameter. *(Measured: archive screening campaign — the 275-pattern CuO/Cu₂O
reduction series for the volume and the rollup, and the 11-BM GeNi₂O₄ series
for the operator-set `lor_strain` floor at 178 of 215 patterns, 83 % of that
series.)*

**9c.19 Gate every summary statistic on determinacy, state the gate beside the
number, and report the screened n.** Reference and fitted rows alike carry
undetermined parameters, and differencing them silently is how a batch
publishes noise: real rows read a cell edge whose **esd was an order of
magnitude larger than the edge itself**, a microstrain esd of **78011**, and a
phase present at **6e-5 wt %**. Screen by a minimum weight fraction and by the
untrustworthy-value codes (`PHASE_UNCONSTRAINED`, `BOUND_HIT`) before
differencing anything, then say so with the result — a median screened to
patterns above 1 wt % that did not declare its screen could not be reproduced
from the saved rows by a later audit, which is a defect in the record even
where the value is right. The screen is not cosmetic: one unscreened draft
median read **0.329 pp where the screened one was 0.931 pp over 142 rows**.
*(Measured: archive screening campaign, the CuO/Cu₂O tranche's cross-code
agreement medians and their re-audit.)*

**9c.20 Sum each side's weight percents over the phases the comparison shares
before differencing them.** `weight_percent` normalises over the phases *in
the model*, so a model missing a real phase pushes every remaining fraction
toward 100 % — one five-against-six-phase comparison inflated four phases'
apparent disagreement **12–14×** through exactly that, and it was first
written up as a separate "normalisation basis" defect before review reduced it
to the omitted phase itself: one mechanism, not two. The tell sits on the
*reference* side, since a rietx model's own fractions always sum to 100:
exported columns summing **well short of 100 %** say the generating model
carried a phase the export does not. Difference like-for-like sums and print
the assertion rather than claiming it in prose. *(Measured: archive screening
campaign — the CuO/Cu₂O five-against-six-phase comparison, and the audit that
reclassified my first account of it.)*

**9c.21 Count how many units actually carry a reference before quoting an
agreement statistic.** A median over data with no reference is a fabrication,
and partial coverage is invisible in the aggregate: one folder had **1 paired
point out of 8** fitted patterns, and that lone point sat at 0.572 pp — **3.4×
above the ceiling the series had been credited with** — while another had zero
paired points and only an aggregate range. Where coverage is partial, a
qualitative event both codes agree on, such as the unit at which an onset
occurs, is more defensible than a Δ-statistic that silently assumes uniform
coverage. Match a reference's blocks by their reported statistics, too, rather
than taking the tail of the file: its last converged block is not necessarily
the published one. *(Measured: archive screening campaign, the cross-code
pairing audit.)*

**9c.22 Run a negative control through the identical machinery, and expect the
threshold you pre-registered to be wrong.** A control is what fixes the
false-positive floor, and without one a threshold is a guess about the noise:
the control's apparent distortion fixed a floor that the real claim sat **7.8×
above**, and so survived — but the threshold written in advance sat **below
that floor**, so it was guaranteed to fire whatever the data said. Committing
to a threshold early is right; committing before the quantity's noise floor is
known is a coin flip, and here a threshold a few times the measured floor
would have separated true from false. Relatedly, gate secondary criteria on
the candidate being competitive at all: one criterion rejected a model
everywhere and the next then read that rejected model's `c/a` and found it ≠
1, which is a parameter being non-zero inside a model nothing supports. Pair
the control with a **positive** arm: a detector that has never fired on a true
case licenses nothing, and this floor was only interpretable because the same
machinery reproduced a **published** distortion magnitude, to ~1 %, on the one
case in the batch known to be real. *(Measured: archive screening campaign,
11-BM variable-temperature series — the distortion claim, its negative
control, and the published positive it reproduced.)*

**9c.23 Hold the configuration constant before reading a trend along the batch
axis — then do not read the surviving trend as physics either.** Where
configuration is confounded with the axis, a pooled trend mixes two
measurements, so restrict first: one series restricted to its **194
identically-configured scans** still showed the effect cleanly — a monotone
fall of more than two orders of magnitude from the coldest scans to the
warmest. Note what that bought — it *exonerated* the configuration and left a
trend that was **still an artefact**, the negative control's
temperature-driven peak broadening bought as apparent `c/a` by a tetragonal
model fitted to a broadened-but-unsplit reflection (9c.22's floor). Surviving
a configuration hold is necessary and nowhere near sufficient. The same
reasoning retires a *null* result: freezing a covariate removes its dynamic
range, so "broadening does not predict cost" measured under a frozen
instrument is a claim about that protocol only. *(Measured: archive screening
campaign — the 11-BM negative control's configuration restriction, and the
frozen-width CuO/Cu₂O timing null.)*

**9c.25 Once a scale is at its bound, every local identifiability statistic
goes quiet — scan it instead.** On one such phase `background.absorption` gave
0.183 and 0.208, *below* a well-behaved phase's 0.318, the top five
correlations were unrelated pairs, and the phase did not appear in
`soft_modes` at all: three misses. A **pin-and-scan profile likelihood** saw
it at once — **17 pp of weight for +0.20/0.39/0.51 pp of Rwp**, inside the
noise floor. Batch-wide counts corroborate rather than detect (`BOUND_HIT` on
that scale in **180 of 275** patterns, `PHASE_UNCONSTRAINED` in **274 of
275**), so a scan is what turns a suspicion into a bound on the answer.
*(Measured: archive screening campaign, CuO/Cu₂O reduction series — the
pin-and-scan control on the fifth phase.)*

**9c.26 Trustworthiness is a property of the unit, not of the protocol, so do
not credit a batch with its best fit's identifiability.** Identifiability
varies along a batch: a profile-likelihood scan showed **three basins spanning
nearly the whole 0–100 wt % range inside a total Rwp span of ~0.01 pp** at one
temperature and was clean and single-minimum at another with **58× more
signal**, and at the bad point the reported `weight_fraction_stderr`
understated the admissible range by **~2 orders of magnitude** — a covariance
esd describes local curvature and cannot see a second basin. Run any such scan
**warm-started from one common state**: the first attempt, run cold, gave
scattered minima at Rwp 3.5–6.1 and measured the optimiser rather than the
landscape. *(Measured: archive screening campaign, the YBaCo₄O₇ gas-cell
series — the 300 °C pin-and-scan against its 200 °C control.)*

**9c.27 Multi-start agreement is evidence about the landscape only if the
starts were where you think.** Three seeds converging on one basin proved
nothing on a fit whose seed conversion was wrong: both "biased" starts were
**19–42× below** the intended values, so all three began from effectively the
same tiny strain and the agreement measured the seeding bug. Verify each
seed's physical value, not merely that the three differ. Where a term wants to
sit on a floor, seeding and flooring it away from zero is what makes the basin
reachable at all — a `lor_strain` lower bound of 0.02 kept the optimiser off
the bound in **14 of 15 patterns** and moved that phase from a fraction the
reference contradicts to one agreeing with it within **0.5 pp**, at an Rwp
**0.10 pp better** than baseline. *(Measured: archive screening campaign — the
ZnCr₂O₄ size-strain arm, and the YBaCo₄O₇ strain-floor arm.)*

**9c.28 Freeze the model between rounds when the purpose is regression.**
Changing the model destroys the comparison that proves the machinery moved
nothing: one round reproduced a predecessor's **316-of-380 disagreement count
to the pattern across all nine series**, which is a strong pass on the
sequential machinery and is only available because nothing else moved. Where
the protocol has to deviate from the reference, report the deviation rather
than fixing it mid-round. *(Measured: archive screening campaign R3, the
nine-series regression round.)*

**9c.29 Audit the aggregation before publishing it, and recompute every cell
from the machine-readable per-unit rows.** A batch's write-up is a second
dataset with its own error rate: one pass over a campaign's own numbers
returned **61 confirmed, 11 disagreeing, 8 unverifiable and 2 unverifiable
without a refit, with the disagreements concentrated in how results were
written up rather than in the results themselves** — recomputed p90 cells off
by 0.03–0.04 pp, a pilot's prose total **1.9 %** from its own `results.json`,
and a wt % quoted as 16.09 where the row says 16.10. Two of the eleven were
descriptions of upstream defects that had **already been fixed** at the commit
checked, so a reader would have concluded two open issues were still open —
which is the argument for auditing before publishing rather than after. The
audit's own totals were not exempt from its own rule: its header says eleven
disagreements, its closing prose says twelve, and its per-row labels support
nine, so quote the cell you actually recounted rather than the summary above
it. Keep narrative estimates out of the same register as measurements, too: a
prose "~40 min" beside a log-derived "43.8 s" makes an unverifiable number
look measured, and one campaign's own 68.5 min session figure was
**unverifiable from its event logs**, which spanned 25–62 min depending how
generously they were stretched. *(Measured: archive screening campaign, the
full numeric re-audit of its own findings record.)*

**9c.30 Expect model debugging, not the solve, to be the batch's cost.** In the
one batch where both halves were timed, "the batch is expensive" was a claim
about getting the model right: that pilot's summed solve time was **13.2 min**
(409.7 s + 382.0 s, confirmed against `results.json`) after **20–25 min of
setup before the first production fit**, while a fully audited job of **380
chained patterns plus 380 cold refits plus 244 minority-geometry cold fits plus
2 reference fits ran in 57 minutes single-threaded**. Speed was not the
constraint in either job measured, so budget the pilot and the inventory rather
than the cores — and pass an explicit long
timeout, since a production run will outlive a shell's default and being
auto-backgrounded mid-run is indistinguishable from finishing. *(Measured: archive screening campaign — the CuO/Cu₂O pilot's audited solve sums, whose
68.5 min session wall figure is itself unverifiable from the event logs and is
9c.29's own example, and R3's audited nine-series (La,Sr)FeO₃ job at 57
minutes.)*

**9c.31 Pin the compute environment for the whole batch and assert it per
unit, not once at the start.** Thread count and package version are covariates
of every timing and every regression claim you will make: a 12-pattern timing
pilot ran **5.92 s per pattern against the same tranche's 4.17 s in the
previous round**, a **42 % miss** traced to single-threaded BLAS and caught
only because the pilot was timed before a chunk size was committed to. Version
drift is worse because it is silent — one machine's three separately-frozen
baseline environments had all become the *same* release, which unreproduces
every version-difference claim measured against them without any of them
erroring. Set the `*_NUM_THREADS` variables inside the driver rather than in
the shell that launched it, and record `result.provenance` per unit so a later
reader can tell which build produced which number. *(Measured: archive
screening campaign — the CuO/Cu₂O timing pilot's BLAS miss, and the campaign's
collapsed version baselines.)*

**9c.32 Build the `FitReport` on the pilot fit and read `report.background` —
`result.diagnostics` does not carry the between-peak verdict, and
`report.suggested_actions` names the remedy even when Layer 1 abstains.** Almost every
capillary or cryostat pattern holds a container amorphous halo, and a low-order
polynomial cuts straight through one while Rwp stays respectable because the
Bragg channels dominate the weighted residual. A 6-term Chebyshev with no
declared peak left the fitted background **35 % high below 3.5° and up to 2×
low across 4–7°** at Rwp 0.157, and the report said so on three channels at
once — `off_region_chi2_reduced` **2.885** against its 1.5 threshold,
`off_region_durbin_watson` **0.393** against 1.0 over 7 408 off-region
channels, the summary naming the between-peak residual "systematic, not noise",
and the halo's own maximum listed **first** in `report.unmatched` at 7.6σ —
while `result.diagnostics` carried only `BACKGROUND_ABSORPTION`. The remedy was
on the report too, under a `kind` a driver can branch on:
`report.suggested_actions` held `increase_background_flexibility` **active and
unvetoed** even though Layer 1 had abstained as unreadable, because
`background_actions` runs on the abstain path by design — an over-stiff
background is a *cause* of an immature fit, so branch on
`suggested_actions[].kind` and do not read an abstention as "no advice". Model
the feature with a `BackgroundPeak` or a `BackgroundPSpline` rather than more
polynomial terms, which hide it while improving every statistic. *(Measured: archive screening campaign — the 11-BM VT Mn₃O₄ 8.281 K fit, whose report was
rebuilt and read only after the tranche was written up; the package's own
manual measures the same Kapton halo at d = 4.74 Å and needs fourteen Chebyshev
terms to match one Gaussian's three.)*

**9c.33 Never multiply a quoted esd by `esd_inflation` — the esds already carry
it.** `Statistics.esd_inflation` is the Bérar-Lelann serial-correlation factor,
and the fit-side and report-side docstrings both say the reported esds *have
already been multiplied by it*; you divide it out to recover raw χ²·(JᵀJ)⁻¹
esds. It is conservative by construction — perfectly white residuals land at
≈1.51 — so it is an upper bound on serial-correlation damage rather than a
measurement, and a batch acceptance bar set near 2 fires on sound fits. Read a
large value as evidence about the *model*, i.e. unmodelled profile detail whose
residual is serially correlated, which `report.background` and `report.regions`
then localise — never as an uncertainty correction to apply. *(Measured: archive
screening campaign — 8.45 on the 11-BM VT Mn₃O₄ 8.281 K fit, against the 2-4
band the docstring gives for lab data and the ≈1.51 white-residual expectation
the package verifies in its own tests; three independent readings of that number
in one session inverted its direction, one while quoting the docstring that
states it.)*