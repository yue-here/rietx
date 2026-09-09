---
name: rietx
description: >-
  Refine powder diffraction data with the rietx Python package (Rietveld, Le
  Bail, Pawley, phase quantification, indexing an unknown cell, judging a
  FitReport) — read it before the first fit() whenever a task involves a powder
  pattern, a CIF to fit against one, phase fractions, a cell to determine, an
  in-situ series, a batch of candidates or of patterns fitted as separate
  jobs, or an existing rietx result to judge.
license: MIT
compatibility: Requires the rietx Python package (pip install rietx) and Python 3.11+. Works offline — this file and its references ship in the wheel; the user manual it names is hosted at https://rietx.org.
metadata:
  version: "1.3.0"
  homepage: "https://rietx.org"
---

# Refining powder diffraction data with rietx

**Audience: an agent driving `rietx` on real data.** Not a tutorial and not an
API reference. A *protocol*: what to do, in what order, what to check before
believing a number, and where the package will tell you your answer is wrong
even though it looks right.

Rwp is not the objective function of your job. A refinement can converge, report
an excellent Rwp, and return displacement parameters biased by 100 %, phase
fractions wrong by 5 wt % and a cell that is right for the wrong reason. Every
rule below exists because one of those happened and was measured. Sections 1-4
are ordinary Rietveld discipline that would apply in any code; sections 5-10 are
specific to running it with no human at the plot.

## Load these when the task calls for them

This file is the judgement core: what holds for every fit. The lookup tables, and
the rules one task *shape* needs, live beside it, loaded on demand, one file
each. The user manual holds the object model this protocol drives and is not
restated here; a page named `x` below is `https://rietx.org/using/x.html`.

| When | Load | Manual page |
|---|---|---|
| you are about to call rietx: entry points, constructors, the four answer types and their fields, the report | [`references/api.md`](references/api.md) | `quickstart`, `model`, `refining`, `results`, `agents` |
| you were handed another program's input file: a PowderLine recipe | [`references/api.md`](references/api.md) § In | `recipe` |
| §7/§7g — a `Diagnostic` fired and you need its row: every engine code, and a foreign project file's import-time codes | [`references/diagnostics.md`](references/diagnostics.md), [`references/diagnostics-projects.md`](references/diagnostics-projects.md) | `results` |
| §6 — something declined to answer: abstentions, caveats, gate failures, `best_or_none()` returning `None` | [`references/abstention.md`](references/abstention.md) | `report` |
| §5 — you are about to quote a number: which field carries which fact, and read numbers rather than pixels | [`references/numbers.md`](references/numbers.md) | `report`, `results` |
| §4/§4b — a judging or deliverable rule needs its measurement, before you override one | [`references/judging.md`](references/judging.md) | `report`, `qpa`, `constraints` |
| §8 — the fit did something that makes no sense: twenty-one measured results that contradict an intuition | [`references/surprises.md`](references/surprises.md) | `refining` |
| §7b-7f — the phase is unknown: peak picking, indexing, the closed loop, the extinction screen | [`references/diagnostics-indexing.md`](references/diagnostics-indexing.md) | `indexing` |
| §9 — one fit is not the answer: the trajectory, and the history DAG as a search structure | [`references/history.md`](references/history.md) | `history` |
| §9b — an in-situ ramp, a sweep or a tray: chaining N patterns, and checking the chain both ways | [`references/series.md`](references/series.md) | `series` |
| §9c, deciding: ranking, differencing, auditing, identifiability | [`references/batch.md`](references/batch.md) | `history`, `series` |
| §9c, operating: budget, cost, timing, the log, inventory, fault tolerance | [`references/batch-operating.md`](references/batch-operating.md) | `history`, `series` |
| writing the answer out: CIF, QPA table, reflection table, plots | [`references/api.md`](references/api.md) § Out | `exports` |

---

## 1. Before you refine: what the method can and cannot do

Rietveld refinement **fits a structural model you already believe** to a whole
powder pattern. It is a local, gradient-based optimisation of a strongly
non-convex, strongly correlated problem. It is not structure solution, not phase
identification, and not a search.

Preconditions, all of which must hold before `fit()` is meaningful:

| Requirement | How to satisfy it | If you cannot |
|---|---|---|
| Every crystalline phase present is in the model | `Structure.from_cif` per phase | An unmodelled phase's peaks land in the residual; Layer 0's `unmatched_obs` list is how you find them |
| The starting cell is within ~1 % | from the CIF, or from `index_pattern` when the phase is unknown (§7d) | The peaks are outside their frozen evaluation windows and the refinement cannot walk there; Layer 2 says so with `reindex_or_recheck_cell` rather than reporting a small shift (§6) |
| The wavelength is right | from the beamline `.prm`, the file header, or `Instrument.bragg_brentano(radiation=...)` — `"CrKa"`, `"FeKa"`, `"CoKa"`, `"CuKa"`, `"MoKa"`, `"AgKa"`, or any of them suffixed `1` for a Kα1-only monochromated beam | Every cell you report is wrong by the same scale factor and *nothing in the fit will tell you*. Do not hand-enter a wavelength from a textbook to "match" one of these: the table is one scale end to end (§8.11) and mixing scales is a ~100 ppm cell error |
| The geometry is right | `Instrument.debye_scherrer` vs `.bragg_brentano` | The aberration model is wrong; displacement/transparency/roughness/absorption are geometry-gated and silently absent |
| The intensities are un-manipulated counts, with esds if available | `read_pattern` reads the file's esd column when present | Weights are wrong ⇒ every esd and every χ² is wrong |
| The starting peak **width** is within a factor of ~2 | measure it: median FWHM of the dozen most prominent peaks, then `W ≈ (FWHM/2)²`, `X ≈ FWHM` | `ProfileTCHZ`'s `W = 1e-3 deg²` default is a *synchrotron* line (FWHM ≈ 0.03°). On lab data with 0.15-0.40° peaks the frozen evaluation windows are an order of magnitude narrower than the lines, and nothing recovers from that — see §2 and §6 |

**Never subtract a background before refining.** Subtraction invalidates the
counting-statistics weights and can make intensities negative. Hold an estimated
background *additively* (`BackgroundFixedPlusChebyshev`) or co-refine it under a
smoothness penalty (`BackgroundPSpline`). `rx.auto_background(data)` does the
right thing.

---

## 2. The turn-on order, and why it is not negotiable

Free parameters in groups, cumulatively, in a stable order (McCusker, Von Dreele,
Cox, Louër & Scardi, 1999, *J. Appl. Cryst.* **32**, 36), each group running to
convergence before the next is freed. The reason is not tradition: the
correlations between groups are severe, and a simultaneous release from a poor
starting point walks into a local minimum that a staged release avoids. Toby
(2024, *J. Appl. Cryst.* **57**, 175, the "recipe problem"): once parameters have
refined to unphysical values, adding more parameters no longer lets the fit
recover.

The plans encode this. Use them; do not hand-roll a free set unless you have a
reason you can state. The staged *discipline* is what is not negotiable; the
preset *sequence* is a default, because the right next group depends on the data
and the current values — and `ref.suggest(data)` answers that at the current
state, one analytic-Jacobian evaluation ranking every held parameter by predicted
Δχ², with no fit and no mutation.

```python
plan="mccusker_default"      # scale+bkg → zero → cell → W → U,V,X,Y      (profile only)
plan="mccusker_structural"   # …then coordinates → displacement → PO → extinction → roughness
plan="lab_bragg_brentano"    # …with sample displacement, Kα2 ratio, FCJ axial
plan="lab_calibrate"         # instrument calibration on a standard, certified cell HELD
plan="lab_sample_refine"     # sample against a frozen calibrated instrument
plan="profile_only"          # Le Bail
plan="pawley_default"        # Pawley
```

`rx.PLAN_INFO` carries a title, description, modes and when-to-use for each.

**Three ordering rules.** None is in the guidelines; each is this package's own
measured finding.

1. **Widths last among the profile terms, `W` before `U,V,X,Y`.** `W` is the
   constant term; freeing the tanθ and 1/cosθ terms first lets them absorb a
   constant offset and then fight it.
2. **Intensity-scaling corrections go last, after the structure has settled.**
   Preferred orientation, extinction and surface roughness rescale intensities in
   a Q-dependent way, and so do the scale, the occupancies and the displacement
   parameters. Freeing a correction early lets it eat structure that belongs to
   the structure.
3. **Anisotropic strain is freed *inside* the sample-broadening stage, not
   after.** A Stephens block locks `lor_strain` — its isotropic direction *is*
   that column — so deferring it leaves the isotropic width unrefined right up to
   the moment fifteen correlated coefficients turn on at once.

**Structure-free first when you can.** Le Bail (`mode="lebail"`) extracts
intensities from the data instead of computing them, so it converges the cell,
zero and profile with no structural assumption. Do that first, then switch to
Rietveld with the converged cell and profile: it is the single most reliable way
to avoid a structural minimum that is really a profile error. Two rules about it
the API does not tell you, both measured on third-party lab data.

4. **Iterate the whole plan to a fixed point; one `fit()` is not enough**, and
   **keep the best pass, not the last.** The extracted per-hkl intensities are
   frozen inside each least-squares run, so intensities and profile converge only
   by *alternating*, and the alternation is not a descent on one objective, so a
   later pass can come back worse.
5. **Seed the background before the first pass, always.** `auto_background`
   starts every coefficient at 0.0, so the first `lebail_update` runs before the
   background has ever been fitted, is handed the whole pedestal, and gives it to
   the Bragg reflections. Seed the constant term from a low percentile of
   `y_obs`.

Both measurements, and multi-phase Le Bail's one surviving caveat:
[`references/judging.md`](references/judging.md).

---

## 3. The degeneracies. Memorise these

Almost every wrong-but-good-looking Rietveld result is one of these. They are not
bugs; they are the geometry of the problem.

| Degenerate group | Their angular signatures | Consequence of getting it wrong |
|---|---|---|
| zero shift · sample displacement · cell | const · cosθ · tanθ | Over a narrow 2θ range these are collinear. A cell "refined" against a free zero on 20° of data is not measured. Bragg-Brentano only — the two flat-plate aberrations are held fixed on any other geometry. |
| zero shift · the two capillary offsets · cell | const · sin2θ · cos2θ · tanθ | The same trap in Debye-Scherrer's own shapes (McCusker eq 4, §8.18). Separable over 5–160°, not over 5–25°: the unit-column Gram's smallest eigenvalue is 5.2e-2 against 1.1e-5, a factor of ~4600. |
| crystallite size · microstrain | 1/cosθ · tanθ | Williamson-Hall separability. Over a short range they are one parameter, not two. |
| phase scale · Biso/ADPs · background · absorption · surface roughness · extinction | all smooth in Q | This is the big one. Every member depresses or lifts intensity as a smooth function of angle. Any of them can absorb any other. |
| capillary µR · phase scale · Biso | exp(c·sin²θ) — *exactly* | Not "correlated": singular. µR is computed from the specimen and never refined, and the fit is identical with and without it (§8.1). |
| flat-plate µt · phase scale · Biso | mostly, but not exactly | 60–99 % absorbable, so it is also computed rather than refined — but the remainder does move Rwp, and a wrong thickness lands partly in the fit and partly in the ADPs (§8.12). |
| preferred orientation · site occupancy | both rescale specific hkl | An occupancy refined against uncorrected texture is a texture measurement. |
| overlapped reflection intensities (Pawley/Le Bail) | identical | The *sum* is determined; the split is not. |

6. **Do not free the second member of a group without checking the first is
   pinned by something outside the fit.** `lab_calibrate` exists for this:
   refining a certified standard with its **cell held fixed** is what decorrelates
   zero from displacement from cell, because the cell is supplied rather than
   fitted.
7. **A correlation of 0.98+ means you refined one parameter and reported two.**
   `HIGH_CORRELATION` fires for you. The right response is almost never "widen the
   bounds"; it is to fix one, or to extend the data range until the signatures
   separate.
8. **Where chemistry says two quantities are one quantity, constrain them rather
   than refining both.** `ref.tie_equal([paths])` makes an equality group,
   `ref.tie(path, source, scale=, offset=)` the general affine form (`occ₁ =
   1 − occ₀` on a mixed site is `scale=-1, offset=1`), `ref.untie` releases them.

   A constraint *removes* a parameter, unlike a restraint, which adds a weighted
   observation and leaves the count alone, so it is the one move that raises the
   observation-to-parameter ratio. The two cases worth reaching for are
   McCusker's: equal displacement parameters across atoms in the same
   environment, and occupancies summing to a known total. Measured on
   fluorapatite's three phosphate oxygens, tying them gives a B(O) tighter than
   the best free value.

   **Check the premise before you tie, and not with Rwp** — it moved by 0.05 % of
   itself there. The check is in the free refinement: if each free value lies
   within its own esd of the others, the data does not contradict the claim that
   they are one parameter. Where they disagree by more than their esds, the atoms
   are saying they are *not* in the same environment, and tying them replaces a
   measurement with an assumption. Symmetry always outranks a user tie, and a
   refused tie says so by name.

---

## 4. Judging a fit — and what Rwp is actually for

Rwp compares your model to the *data you have*, weighted by counting statistics.
It is dominated by the strongest peaks and by the background level: a useful
*relative* number between two fits of the same data over the same channels, and a
nearly useless absolute one. Measured, 18 refinements of one identical PbSO₄
dataset returned Rwp 8.2–20.0 % (Hill, 1992, *J. Appl. Cryst.* **25**, 589), and
Toby (2006, *Powder Diffr.* **21**, 67) finds "no simple way to distinguish a good
fit from one that is just plain wrong based on R factors".

Judge a fit in this order. `print(result)` renders steps 9 and 17 (per-stage
status, every diagnostic, provenance, agreement indices last), and
`ref.summary(deliverable=…)` adds the rows that need the compiled model. The
measured evidence behind each rule is
[`references/judging.md`](references/judging.md).

9. **Status and guards outrank every statistic.** `result.status`, then
   `result.diagnostics`. `statistics.max_shift_over_esd` is the measured quantity
   behind "converged" (McCusker §7 converges at ≤ 0.1). A converged solve
   satisfies it a fortiori, so read it where a stage stopped on `STAGE_MAX_ITER`:
   its magnitude says how far the solve was still moving, in esd units.
10. **Read the shape of the difference curve region by region, not its size.**
    `report.regions` carries per-region local Rwp and χ² share, and
    `cumulative_chi2_breakpoints` locates where the model starts failing.
11. **Read the unmatched peaks.** `report.unmatched` with `kind="unmatched_obs"`
    is an impurity or a missing phase; `"unmatched_calc"` is a phase you modelled
    that is not there, or an absence error.
12. **Ask whether the refined values are physically possible** — negative Biso,
    occupancies above 1, a cell that moved 0.5 %, an ADP tensor that is not an
    ellipsoid — **and ask it of the structure too.** `result.geometry` is a
    `GeometryTable` of `bonds`, `contacts` and `angles`, which McCusker §11 ranks
    *with* the profile fit and above every R value, so read it before step 16.
    Nothing scores it: a Si–O at 1.75 Å or a 60° O–M–O is yours to recognise. The
    number of rows naming an atom is its coordination number, and a `None` esd
    means no covariance behind the row or fixed by symmetry, never zero.
13. **Quote no esd without its inflation.** `statistics.esd_inflation` is the
    Bérar-Lelann factor for serial correlation, and it has an expected value of
    ≈1.51 even for perfectly white residuals, so it is an upper bound on the
    damage rather than a measurement of it. `report.identifiability` carries the
    trio to pass on with any esd — raw χ²_red, the inflation, Durbin-Watson —
    plus the δR line. Scaling variances by GoF² alone is "highly questionable"
    (Schwarzenbach, 1989): the same data under different protocols spread by
    ×17–25 of the quoted esds on cell dimensions.
14. **Ask whether the converged answer is the only one, and settle it by a
    swap.** `report.identifiability.exchanges` and `.soft_modes` outrank the
    statistics, and **the verdict that licenses is `ambiguous`, not
    `converged`.**

    They are about what "converged" *means*: `converged` is a statement about
    the free set, while an `exchangeable=True` row says a **held** parameter's
    signature is reproducible inside the fitted span *and* that a fitted partner
    stands many σ from its null.

    The swap resolves it and is a measurement: fit each member of the pair
    *alone*, the other held at its **null**, and compare χ² — two warm fits,
    seconds, and `rx.report.compare_rivals(ref, data, finding)` runs exactly that.
    R² cannot stand in for it. Read the outcome on
    `RIVAL_DECISIVE_MIN_CHI2_RATIO` (= 1.10, `rietx.report`), the losing rival's
    χ² over the winner's: at or above it **the data has chosen, and you quote the
    winner without caveat**, since hedging a won swap is a measured failure rather
    than caution; below it the pair is genuinely unresolved and the resolution is
    protocol or a declared ambiguity. No sentence converts a tie into an answer.
    The licence also travels as `result.statistics.identifiability_clause`.

    What you must **not** do is free the held parameter alongside its partner and
    refit: both free lands on §3's degenerate ridge and reports the unconstrained
    combination at a *better* Rwp — the most common misreading of the clause.
15. **Read what the background is doing before you read Rwp**, because it decides
    how to read Rwp. In `report.background`, `worst_absorption` (with
    `worst_absorption_path`) is how much of a structural parameter the background
    column span can reproduce, and `off_region_chi2_reduced` with
    `off_region_durbin_watson` is whether the residual *between* the peak regions
    is systematic. Layer 0's regions are peak clusters, so that second failure
    lands in no `report.regions` entry and step 10 cannot see it.
16. **Only then Rwp and GoF, and never alone** — as a pair with
    `background.rwp_background_subtracted`. Measured, a sharp LaB₆ fit and one
    under 0.6° of broadening both report Rwp **0.0137**, and 0.0490 against
    0.0766 subtracted: the raw number is flattered by whatever the background
    carries, the subtracted one separates the two fits.
17. **Read the structure R factors last, and never in isolation.**
    `result.phase_agreement` carries `r_bragg` (R_B) and `r_f` (R_F) per phase. A
    powder pattern does not measure individual reflection intensities, so I(obs)
    is the pattern *partitioned in proportion to I(calc)*: a wrong model receives
    the intensity it predicted and both flatter it (Toby 2006: R_Bragg "has no
    statistical validity"). Watch R_B fall as you improve a model; never read it
    as evidence a correction helped. Absent in Le Bail and Pawley, where the
    intensities *are* the fit. **Do not compare a trace
    phase's R_B with the major phase's**: neither is weighted, and a minor phase's
    windows sit under the major phase's peaks.

**Adding parameters: use ΔBIC, not Hamilton's R-ratio.** Measured at 7251
channels, Hamilton's test blesses a 0.13 % χ² improvement that is physically
inert; ΔBIC carries the sample-size penalty powder channel counts need.

**Comparing against another code means adopting its protocol, not just reading
its numbers.** Mirror its refined-parameter set, its held parameters and its
excluded regions, then *check the channel count matches* before believing any Rwp
comparison. Measured: guessing a plausible protocol on the GSAS-II fluorapatite
tutorial gave Rwp 16 % and a +390 ppm cell, while mirroring the converged `.EXP`
gave 9.73 % against GSAS's 10.05 % on an identical 5750 channels.

---

## 4b. Declare the deliverable — "good enough" is a question about purpose

Much real work is non-ideal by construction — nanoparticle broadening, intensity
error from unknown pore contents. **No bar moves for such data**: the gates
auto-scale to information content, and "good enough" is a different question
answered exactly, not a relaxed standard. What changes is *which report rows
decide your deliverable*. Declare it, then read its rows: the report is
purpose-neutral and will not infer yours.
`ref.summary(deliverable=…)` prints them for one fit, and a chain's are on
`SeriesResult.summary(deliverable="series")`.

| Deliverable | The rows that decide it | Stop when |
|---|---|---|
| **Phase ID** — which phases are present? | `report.unmatched` (`unmatched_obs`), `report.lebail_gap.ratio`: ≫ 1 → every line indexed, safe **at any Rwp** | no strong unmatched observed peaks and the gap readable, whatever Rwp says. An `abstained_kind="resolution_limited"` does not block this deliverable |
| **QPA** — how much of each? | `report.background.absorption`, then absorption geometry, then impossible values. `lebail_gap` inverted: large ratio → **wrong fractions** | fractions stable under a background-flexibility change, `worst_absorption` below its threshold, and no unresolved scale- or ZMV-family diagnostic. **Never** "Rwp stopped falling", which here points the wrong way |
| **Trajectory** — a parameter against T, t, p or composition | `SeriesResult.summary(deliverable="series")`: `SEQUENTIAL_PATH_DEPENDENT`, `SEQUENTIAL_PERSISTENT_FINDING`, `SEQUENTIAL_DISCONTINUITY`, `PHASE_UNCONSTRAINED`; **2θ anchor**, **precision/accuracy split**, QPA check **every point** | every number you quote names the one thing that would have to be wrong for it to be wrong, and that thing has been checked |
| **Microstructure** — how big are the domains, how strained? | `result.microstructure`: domain size (Å), Δd/d, esd or `MicrostructureTerm.unavailable`; `separable`, `size_agreement` (1 = one), `SIZE_UNUSUALLY_SMALL`/`STRAIN_UNUSUALLY_LARGE`/`BOUND_HIT` | `separable` is True, both readings agree, and you quote the size as an order of magnitude with the `scherrer_k` the block carries. A `separable=False` is not a smaller number to quote, it is a wider 2θ range to collect |
| **Structure** — where are the atoms? | Above, plus `report.texture`, `report.strain`, restraint tension, ADP positive-definiteness, `report.identifiability.exchanges`/`.soft_modes`. Le Bail gap: **blocker**, intensity model carries the claim | §10's full ladder, with no `exchangeable` row unaddressed. Addressed means the swap was run and either **won** (adopt the winner and quote it without caveat) or **tied** (resolve by protocol). Never by freeing the rival into the same fit |

**The QPA row outranks every statistic beside it**: an over-flexible background
wins on *every* agreement index while biasing displacement parameters to 0.958
and 0.000 Å² against a truth of 0.5, and `worst_absorption` (0.46 against 0.08)
is the only row separating the two fits — the plot does not either.

**`resolution_limited` is a stopping point, not a failure**: the edit directions
are indistinguishable on merged peaks, not the model wrong — a legitimate end
state for phase-ID work; for structure-grade work, *collect better data*.

**The capability floor.** Verify before acting (`rx.report.predict_then_verify`,
or a history branch), treat a *capped* confidence as an **unresolved question**
rather than a low-priority instruction, and never execute a vetoed action. There
is no ceiling: the report supplies evidence, judgement stays with the reader.

Every deliverable's worked measurement, and the round robins' two QPA rules:
[`references/judging.md`](references/judging.md).

---

## 6. Abstention is a result. Do not convert it into a number

The package's hardest rule is **never return a confident wrong singleton**.
Several places will decline to answer. When they do, that *is* the answer.

18. **Propagate an abstention; do not paper over it.** `report.abstained_reason`
    set means the global maturity gate refused Layer 1 — branch on
    `abstained_kind` first, and do not read `attribution`. `INDEX_ABSTAINED` means
    the candidates are there so you can see what was considered, not so you can
    pick one.
19. **Never take `candidates[0]` because it is ranked first.** The ranking orders
    the hypotheses, the gate judges them, and the two are different questions.
    `IndexingResult.best_or_none()` returning `None` is the most likely outcome of
    a first indexing run and is not a failure: read each candidate's
    `confidence_caveats` and act on the *refuting* ones first.
20. **A failed gate is not a cause.** `region.gates_passed is False` means the
    coefficients are present for transparency only; read `region.gate_failures`,
    whose codes are closed and typed.
21. **Two collinear templates are not one answer.** A trend reported
    non-separable, a `PAWLEY_OVERLAP_UNRESOLVED` group, an
    `INDEX_GEOMETRIC_AMBIGUITY`, an `EXTINCTION_GROUPS_NOT_SEPARABLE`: the
    information is absent from the measurement, not buried in noise. Extend the
    range, report both, or carry the whole list forward — a group's sum is the
    datum, and no counting time separates space groups differing only by elements
    that produce no absences.
22. **A held or unquotable value is not a measurement.** `PHASE_UNCONSTRAINED`,
    `STEPHENS_STRAIN_NOT_POSITIVE`, `BOUND_HIT` and `HARMONIC_HELD` each say a
    number in the result did not come from the data. Their esds do not make them
    measurements, and a good Rwp does not cover them: a parameter that does not
    move y_calc does not move Rwp either.
23. **Two of these codes are a number to check, not a refusal**:
    `STRAIN_UNUSUALLY_LARGE` and `SIZE_UNUSUALLY_SMALL`. The fit is finished and
    may be right — confirm the broad lines are really that phase's, and not an
    unmodelled peak shape, an amorphous component or a second phase.

Every signal, its meaning and its correct response:
[`references/abstention.md`](references/abstention.md).

---

## 10. A worked default

A lab pattern, a CIF and no other information. Adapt, do not skip the checks —
the right order depends on the data and the starting values (Toby, 2024).

```python
import rietx as rx

data       = rx.read_pattern("sample.xy")
structure  = rx.Structure.from_cif("phase.cif")
instrument = rx.Instrument.bragg_brentano(radiation="CuKa",
                                          monochromator_two_theta=26.6)
instrument.background = rx.auto_background(data)

ref = rx.Refinement(structure, instrument, history="session.jsonl")

# 1. structure-free first: cell + profile without any structural assumption
ref.fit(data, mode="lebail", plan="profile_only")

# 2. Rietveld from the converged cell/profile
result = ref.fit(data, plan="lab_bragg_brentano")

# 3. the termination view: per-stage status, diagnostics, agreement indices last
print(result)

# 4. guards outrank statistics, and each one carries what to do about it
for d in result.diagnostics:
    print(d.level, d.code, d.where, d.message, "->", d.suggestion)

# 5. numbers, not pixels
report = ref.report(plan="lab_bragg_brentano")
if report.abstained_reason:
    print("Layer 1 abstained:", report.abstained_reason, report.abstained_kind)
else:
    for r in report.attribution:
        if r.gates_passed:
            print(r.two_theta_lo, r.two_theta_hi,
                  [(c.kind, c.value, c.stderr, c.share) for c in r.coefficients])

# 6. impurities / missing phases
print([u for u in report.unmatched if u.kind == "unmatched_obs"])

# 7. the whole judgement in one call, for a declared purpose
print(ref.summary(deliverable="structure"))
```

**The three stop conditions.** Stop refining when

24. every diagnostic is understood and either resolved or reported as a caveat;
25. Layer 1 attributes no remaining region above the significance gate; and
26. adding the next parameter group fails a ΔBIC test or trips a guard.

Do **not** stop merely because Rwp stopped falling, and do not continue merely
because it is still falling. These are the *structure-grade* conditions; §4b maps
the earlier stopping points a declared phase-ID or QPA deliverable is entitled to.

**What to report.** The refined values with their (inflated) esds, the
diagnostics you could not resolve named as systematics, the protocol you actually
ran (plan, held parameters, excluded ranges, channel count), and the package
version, backend and solver from `result.provenance`. A number without its
protocol is not a measurement.

---

## The API

**There is one integration surface and it is the Python API.** A caller runs a
verb, reads the typed answer, and dumps it with `model_dump(mode="json")` when a
file is wanted. A failure **raises**: there is no envelope and no error code.

**Do not quote a signature from memory.** `rx.capabilities()` says what this
build supports, `rx.help_for(path)` says what a parameter is, and
`inspect.signature(obj)` or `help(obj)` gives any call's arguments. The names
are [`references/api.md`](references/api.md), every one of them checked against
the installed package by test.

## See also

- The manual, Part 2 (theory): <https://rietx.org/manual.html> — every equation with its
  source, and the bibliography each author-year citation below resolves in
- The repository, <https://github.com/yue-here/rietx>: `README.md`,
  `docs/DESIGN.md` (why the FitReport is shaped this way),
  `tests/data/README.md` (provenance of every bundled dataset); none ships in
  the wheel
