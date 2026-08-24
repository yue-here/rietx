# Refinement protocol for agents

**Audience: an LLM agent driving `rietx` to refine real powder diffraction
data.** Not a tutorial and not an API reference — a *protocol*: what to do, in
what order, what to check before believing a number, and where this package
will tell you that your answer is wrong even though it looks right.

Read this before your first `fit()`. Sections 1–4 are ordinary Rietveld
discipline that would apply in any code; sections 5–10 are specific to running
it without a human at the plot, and were learned by building this one.

> **Orientation for the impatient.** Rwp is not the objective function of your
> job. A Rietveld refinement can converge, report an excellent Rwp, and return
> displacement parameters biased by 100 %, phase fractions wrong by 5 wt %, and
> a cell that is right for the wrong reason. Every section below exists because
> one of those happened and was measured. The package's job is to hand you the
> numbers that reveal it; your job is to look at them.

---

## 1. Before you refine: what the method can and cannot do

Rietveld refinement **fits a structural model you already believe** to a whole
powder pattern. It is a local, gradient-based optimisation of a strongly
non-convex, strongly correlated problem. It is not structure solution, not
phase identification, and not a search.

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
counting-statistics weights and can make intensities negative. Hold an
estimated background *additively* (`BackgroundFixedPlusChebyshev`) or co-refine
it under a smoothness penalty (`BackgroundPSpline`). `background.auto_background(data)`
does the right thing.

---

## 2. The turn-on order, and why it is not negotiable

Free parameters in groups, cumulatively, in a stable order (McCusker, Von
Dreele, Cox, Louër & Scardi, 1999, *J. Appl. Cryst.* **32**, 36). Each group
runs to convergence before the next is freed. The reason is not tradition: the
correlations between groups are severe, and a simultaneous release from a poor
starting point walks into a local minimum that a staged release avoids. Toby
(2024, *J. Appl. Cryst.* **57**, 175 — the "recipe problem") states the
mechanism plainly: once parameters have refined to unphysical values, adding
more parameters no longer lets the fit recover.

The plans in `strategy/staged.py` encode this. Use them; do not hand-roll a
free set unless you have a reason you can state. The staged *discipline* is
what is not negotiable; the preset *sequence* is a default, because the right
next group depends on the data and the current values (Toby, 2024) — and
`task="suggest"` (§9c) answers that question at the current state, one
analytic-Jacobian evaluation ranking every held parameter by predicted Δχ².

```python
plan="mccusker_default"      # scale+bkg → zero → cell → W → U,V,X,Y      (profile only)
plan="mccusker_structural"   # …then coordinates → displacement → PO → extinction → roughness
plan="lab_bragg_brentano"    # …with sample displacement, Kα2 ratio, FCJ axial
plan="lab_calibrate"         # instrument calibration on a standard, certified cell HELD
plan="lab_sample_refine"     # sample against a frozen calibrated instrument
plan="profile_only"          # Le Bail
plan="pawley_default"        # Pawley
```

Three ordering rules that carry more weight than they look like. None of the
three is in the guidelines — each is this package's own measured finding, a
house rule labeled as one (the audits: [the v1.0 record](milestones/v1.0.md)
§ Appendix found the manual attributing them to the paper;
[the v1.1 record](milestones/v1.1.md) § Appendix holds the protocol's own
grounding grid):

- **Widths last among the profile terms, `W` before `U,V,X,Y`.** `W` is the
  constant term; freeing the tanθ and 1/cosθ terms first lets them absorb a
  constant offset and then fight it.
- **Intensity-scaling corrections go last, after the structure has settled.**
  Preferred orientation, extinction and surface roughness all rescale
  intensities in a Q-dependent way, and so do the scale, the occupancies and
  the displacement parameters. Freeing a correction early lets it eat structure
  that belongs to the structure. This is why `_ROUGHNESS_STAGE` is the final
  stage of every plan that carries it.
- **Anisotropic strain is freed *inside* the sample-broadening stage, not
  after.** A Stephens block locks `lor_strain` — its isotropic direction *is*
  that column — so deferring it would leave the isotropic width unrefined right
  up to the moment fifteen correlated coefficients turn on at once.

**Structure-free first when you can.** Le Bail (`mode="lebail"`) extracts
intensities from the data instead of computing them, so it converges the cell,
zero and profile without any structural assumption. Do that first, then switch
to Rietveld with the converged cell/profile. It is the single most reliable way
to avoid a structural minimum that is really a profile error.

Two things about Le Bail that the API does not tell you, both measured on
third-party lab data (2026-07-29):

- **Iterate the whole plan to a fixed point; one `fit()` is not enough.** The
  extracted per-hkl intensities are frozen inside each least-squares run (the
  frozen-per-stage invariant), so intensities and profile converge only by
  *alternating*. On PbSO4 pass 1 stops at Rwp 20.756 % with an unphysical
  Caglioti **V = +0.0615**; passes 2-4 reach 10.247 % with the curve sane. Re-run
  the plan until Rwp stops moving — and **keep the best pass, not the last**: the
  alternation is not a descent on one objective, so a later pass can come back
  worse (seen on Tb2BaCoO5, 17.3 % → 18.7 %).
- **Seed the background before the first pass, always — and this is the one
  that bites hardest.** `auto_background` chooses the knot spacing or the
  Chebyshev *order* but starts every coefficient at **0.0**, so the modelled
  background is identically zero, and the first `lebail_update` runs *before*
  the background has ever been fitted. The partition is then handed
  `max(y_obs − 0, 0)` — the whole pedestal — and gives it to the Bragg
  reflections. Measured on a synthetic pattern whose background is 5× its
  strongest peak: cycle one claims **571×** the true Bragg intensity. Seed the
  constant term (a low percentile of `y_obs`) before a Le Bail run.

**Multi-phase Le Bail was broken until v1.0 and is now supported** (WP-1028
§(g), fixed 2026-08-07). This section used to say "do not use it above one
phase", and the reason was a defect rather than the method: `lebail_update`
built its partition denominator per phase, so each phase claimed the entire
observed excess in its own windows and overlapping phases were issued the same
counts twice. The shares now sum to 1 across all phases at every channel —
measured Σ calculated / Σ observed excess **1.79 → 1.0000** on LaB₆ + CaF₂,
with the single-phase path bit-identical. Two caveats survive the fix and are
about the method, not the bug: the intensities of two phases whose reflections
*coincide* are not separately determined by the data (the partition splits them
by the current model, which is a starting value and not a measurement), and the
Rwp figures the old note quoted (742-9 281 % at two phases) were the overcount
compounding through the later profile stages, so treat a high multi-phase Le
Bail Rwp as a reason to look at the seeding above, not as this defect returning.

---

## 3. The degeneracies. Memorise these

Almost every wrong-but-good-looking Rietveld result is one of these. They are
not bugs; they are the geometry of the problem.

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

Two practical consequences:

1. **Do not free the second member of a group without checking the first is
   pinned by something outside the fit.** The `lab_calibrate` workflow exists
   for exactly this: refining a certified standard with its **cell held fixed**
   is what decorrelates zero from displacement from cell, because the cell is
   supplied rather than fitted.

2. **A correlation of 0.98+ means you refined one parameter and reported two.**
   The package raises `HIGH_CORRELATION` for you. The correct response is
   almost never "widen the bounds"; it is to fix one, or to extend the data
   range until the signatures separate.

3. **Where chemistry says two quantities are one quantity, constrain them
   rather than refining both.** `ref.tie_equal([paths])` makes an equality
   group, `ref.tie(path, source, scale=, offset=)` the general affine form
   (`occ₁ = 1 − occ₀` on a mixed site is `scale=-1, offset=1`), `ref.untie`
   releases them. A constraint *removes* a parameter — unlike a restraint,
   which adds a weighted observation and leaves the count alone — so it is the
   one move that raises the observation-to-parameter ratio.

   The two cases worth reaching for are the ones McCusker names: equal
   displacement parameters across atoms in the same environment, and
   occupancies summing to a known total. Measured on fluorapatite's three
   phosphate oxygens: 20 → 18 free parameters, 287.5 → 319.4 observations per
   parameter, and B(O) 0.2763(1810) / 0.5279(1911) / 0.4149(1282) Å² free
   against 0.4138(899) Å² tied — tighter than the best of the three.

   **Check the premise before you tie, and do not check it with Rwp.** Rwp
   moved by 0.05 % of itself there, so it can tell you neither that the
   constraint helped nor that it hurt. The check is in the free refinement: if
   each free value lies within its own esd of the others, the data does not
   contradict the claim that they are one parameter. Where they disagree by
   more than their esds, the atoms are saying they are *not* in the same
   environment, and tying them replaces a measurement with an assumption.

   Every tie is recorded as a `set_tie` history node and restored by a
   checkout, so a constrained protocol replays as one. Symmetry always
   outranks a user tie: a cell axis the space group already ties, a coordinate
   behind its site-symmetry direction, and a `lebail`/`pawley` mode-fixed path
   are refused by name rather than silently ignored.

---

## 4. Judging a fit — and what Rwp is actually for

Rwp compares your model to the *data you have*, weighted by counting
statistics. It is dominated by the strongest peaks and by the background level.
It is a useful *relative* number between two fits of the same data over the
same channels, and a nearly useless absolute one. That is the literature's own
verdict, stated and then measured: Toby (2006, *Powder Diffr.* **21**, 67) —
"no simple way to distinguish a good fit from one that is just plain wrong
based on R factors" — and the IUCr round robin, where 18 refinements of one
identical PbSO₄ dataset returned Rwp 8.2–20.0 % (Hill, 1992, *J. Appl.
Cryst.* **25**, 589).

Judge a fit in this order:

1. **Status and guards.** `result.status`, then `result.diagnostics`. A warning
   here outranks any statistic. `statistics.max_shift_over_esd` is the measured
   quantity behind "converged" (McCusker 1999 §7: converged when ≤ 0.1, a band
   quoted from the paper and gating nothing): a converged solve satisfies it a
   fortiori, so read it on the other branch — where a stage stopped on
   `STAGE_MAX_ITER`, its magnitude says *how far* the solve was still moving
   in esd units, which separates "nearly there" (just over the band) from a
   fit that stopped mid-flight (measured ≈14 on one starved iteration).
2. **The shape of the difference curve**, region by region — not its size.
   Layer 0 gives you this as numbers: `report.regions` with per-region local
   Rwp and χ² share, and `cumulative_chi2_breakpoints` locating where the model
   starts failing.
3. **Unmatched peaks.** `report.unmatched` with `kind="unmatched_obs"` is an
   impurity or missing phase; `"unmatched_calc"` is a phase you modelled that
   is not there, or an absence error.
4. **Whether the refined values are physically possible.** Negative Biso.
   Occupancies above 1. A cell that moved 0.5 %. An ADP tensor that is not an
   ellipsoid. These are all reported, but you have to read them.

   **And the geometry, which is the same question asked of the structure
   rather than of a parameter.** `result.geometry` (also `report.geometry`)
   is a `GeometryTable`: `bonds` and `contacts` — McCusker et al. 1999 §11
   asks for "both bonding and nonbonding" — and `angles` at every vertex.
   This is the paper's criterion (ii), which it ranks *with* the profile fit
   and above every R value, so read it before step 8 and not after. Nothing
   in the package scores it; a Si–O at 1.75 Å or a 60° O–M–O is yours to
   recognise. Each row lists the whole environment of each asymmetric-unit
   atom, so **the number of rows naming an atom is its coordination number**,
   and a bond between two sites appears twice, once from each end.

   Two things about the esd. `stderr` is propagated through the *whole*
   covariance, which §10 requires of any derived quantity, and
   `stderr_diagonal` beside it is what ignoring the correlations would have
   given — quote the first, and use the pair when you need to say how much
   the correlations mattered. And `None` never means zero: it means the row
   had no covariance behind it (an evaluate-only pass) or is fixed by
   symmetry, and an esd of 0 on a symmetry-fixed 90° angle would be a claim
   about precision rather than a statement about constraint.
   `write_refinement_cif` writes the whole table as `_geom_bond_*`,
   `_geom_contact_*` and `_geom_angle_*` loops, with the symmetry codes
   resolvable against the `_space_group_symop_operation_xyz` loop it writes
   beside them.
5. **The esds, with their inflation.** `statistics.esd_inflation` is the
   Bérar-Lelann factor for serial correlation. Note it has an expected value of
   ≈1.51 even for perfectly white residuals — a house derivation, not the
   paper's (chance same-sign runs give E[χ²′]/χ² = 1 + 4/π;
   `optimize.statistics.berar_lelann_factor`, simulation-verified) — so treat
   it as an upper bound on the damage, not a measurement of it.
   `report.identifiability` quotes the
   qualifying trio side by side — raw χ²_red, the inflation (already in every
   quoted esd, dividable back out), Durbin-Watson — plus the δR line
   (`delta_r_slope`/`delta_r_intercept`: sorted Δ/σ against normal quantiles;
   slope ≈ 1, intercept ≈ 0 on honest σ, slope > 1 when σ is underestimated).
   Report the ingredients with any esd you quote onward; scaling variances by
   GoF² alone is the practice Schwarzenbach et al. (1989) call "highly
   questionable". The round robins measured why the ingredients matter: the
   same data refined under different protocols spread by up to ×17–25 of the
   quoted esds on cell dimensions (Hill, 1992; Hill & Cranswick, 1994, *J.
   Appl. Cryst.* **27**, 802 — whose
   explanation is §3's first degeneracy row, the cell compensating 2θ-scale
   errors). Durbin-Watson is in the trio because serial correlation is
   precisely what makes the raw esds untrustworthy, and d stays discriminating
   where Rwp and GoF do not (Hill & Flack, 1987, *J. Appl. Cryst.* **20**,
   356).
6. **Whether the converged answer is the only one** —
   `report.identifiability.exchanges` and `.soft_modes`, and this outranks
   the statistics because it is about what "converged" *means*. `converged`
   is a statement about the free set; an exchange row with
   `exchangeable=True` says a **held** parameter's signature is reproducible
   inside the fitted span (`r2` → 1) *and* a fitted partner stands many σ
   from its null — an E2-shaped answer reads "converged, but the fitted
   zero_shift is exchangeable with the held sample_displacement — **this
   fit** cannot tell you which is physical". **The verdict that licenses is
   `ambiguous`, not `converged`** — measured, the fit carrying a planted
   displacement inside a compensating zero and its clean reference differ in
   *nothing* but this row (χ²_red 1.012 vs 1.010, R² identical to six
   decimals; only the partner's 128σ-vs-1.6σ separates them).

   **The first resolution is the swap, and it is a measurement.** Fit each
   member of the pair *alone* with the other held at its **null** (0 for
   zero, displacement and transparency) and compare χ² — two warm fits,
   seconds. `compare_rivals` (§9) does exactly this. R² is a **geometric**
   statement about column overlap and cannot say whether the counts in hand
   separate the pair: on real SRM 660c an R² of 0.9977 pair comes apart
   decisively, χ² 4.0752 (zero only) against 3.4890 (displacement only) on
   5332 points, with the zero-only model biasing *a* by +100 ppm.

   **Read the outcome by the decision band, and follow through.** The grade
   is `RIVAL_DECISIVE_MIN_CHI2_RATIO` (= 1.10, `rietx.report`), read on
   the losing rival's χ² over the winning rival's. At or above it **the data
   has chosen: the winning rival's fit is the answer, and you quote it
   without caveat.** Hedging a won swap is a measured failure, not caution —
   on the round-3 eval's solvable control (rivals decisive at 1.1679, the
   SRM 660c pair above) the agents that ran the swap recovered the true
   displacement and still declined or hedged the answer; the control went
   0/7 valid. Below the band the pair is genuinely unresolved — the two real
   tie states measure 1.0075 and 1.0001 — and the resolution is protocol (a
   calibrant-fixed zero, a wider angular window) or declaring the ambiguity;
   no sentence converts a tie into an answer.

   **The sentence travels beside the numbers too.** The summary's
   identifiability clause — the finding, the swap and this band's license —
   is also delivered verbatim as `result.statistics.identifiability_clause`
   (`report_thresholds_version` 1.3, WP-1108). Measured consumers pipe the
   JSON response to a file and grep the statistics back, and the summary
   string is what those greps drop (the license reached agent context in 2
   of 12 cells from the summary; 4/4 from the statistics block once placed
   there). So a pipeline that keeps only the statistics still holds the
   license; `None` there means no report was built or nothing crossed a
   comment threshold, never a verdict.

   What you must **not** do is free the held parameter alongside its partner
   and refit: both free lands on the degenerate ridge of §3, and it reports
   the unconstrained combination at a *better* Rwp, which is the trap. This
   is the single most common misreading of the clause — measured over 30
   agent runs, seven of twenty position cells took it (WP-1059). Note the
   difference between the two moves: the swap runs each rival **alone**, the
   ridge runs them **together**. A `soft_modes` entry quoted in the summary
   is the same statement about a fitted *combination*: the named parameters
   trade freely and their individual esds are not independent.
7. **What the background is doing** — `report.background`, and it belongs
   *above* Rwp because it decides how to read Rwp. Two rows:
   `worst_absorption` (with `worst_absorption_path`) is how much of a
   structural parameter the background column span can reproduce, and
   `off_region_chi2_reduced` with `off_region_durbin_watson` is whether the
   residual *between* the peak regions is systematic (the Durbin-Watson d of
   Hill & Flack, 1987, applied off-region — the statistic built to detect
   exactly this). Layer 0's regions are peak clusters, so that second failure
   lands in no `report.regions` entry and step 2 cannot see it at all.
8. **Only then Rwp and GoF** — as a pair with
   `background.rwp_background_subtracted`, never alone. Measured: a sharp
   LaB₆ fit and one under 0.6° of broadening both report Rwp **0.0137**, and
   background-subtracted they read 0.0490 and 0.0766. Raw Rwp is flattered by
   whatever the background carries (89 % of the observed intensity in both),
   so the number that separates two fits is the subtracted one. The
   literature says the same twice: Toby (2006, Fig. 1) shows identical model
   discrepancies reading Rwp 23 % with no background and 3.5 % with one, and
   Hill's 1992 round robin recommends quoting the background-subtracted forms
   for exactly this comparison. It is
   published on every report and deliberately never mentioned in `summary` —
   every background-dominated pattern would trigger it, including converged
   ones.

9. **Last, the structure R factors** — `result.phase_agreement`, one
   `PhaseAgreement` per phase, carrying `r_bragg` (R_B, eq 14 of McCusker et
   al. 1999) and `r_f` (R_F, eq 13). They are last on purpose. A powder
   pattern does not measure individual reflection intensities, so I(obs) is
   the observed pattern *partitioned in proportion to I(calc)*: a wrong model
   receives the intensity it predicted, and both indices flatter it. Both
   papers say so — the guidelines beside eq (13), "biased towards the
   structural model", and Toby (2006): R_Bragg "has no statistical validity". They are
   for watching R_B fall as you improve a model, and for the publication that
   will ask for one — never for judging a model in isolation, and never as
   evidence that a correction helped. Absent (an empty list) in Le Bail and
   Pawley mode, where the intensities *are* the fit and the comparison would
   be circular.

   **Do not compare a trace phase's R_B with the major phase's.** Neither
   index is weighted, so a reflection the fit barely constrains weighs as much
   as one that dominates it — the weighted R_WI of Cox & Papoular (1996,
   *Mater. Sci. Forum* **228–231**, 233) exists to answer exactly this, and is
   not computed here (`optimize.statistics`' docstring holds the pointer) —
   and a minor phase's windows sit under the major
   phase's peaks, where the counts the major phase failed to describe are
   handed out too. Measured on 11-BM NAC with 1.35 wt % CaF₂: 0.052 for the
   major phase against 0.385 for the impurity, all of the latter in four
   reflections at I(obs)/I(calc) ≈ 2.2, each under a strong NAC peak. Read it
   beside `qpa.phases[].weight_fraction`, and treat a trace phase's value as a
   question rather than a measurement.

   `write_refinement_cif` writes them as `_refine_ls_R_I_factor` and
   `_refine_ls_R_factor_all` on each phase's own block, beside a
   `_pd_proc_ls_special_details` that states the esd method in full — the
   base estimator √diag(χ²_red·(JᵀJ)⁻¹), then the Bérar-Lelann factor it was
   multiplied by, which §10 of the guidelines requires any publication to
   state.

**Adding parameters: use ΔBIC, not Hamilton's R-ratio.** Measured on this
package's own data (WP-0503): at 7251 channels Hamilton's test blesses a 0.13 %
χ² improvement that is physically inert. ΔBIC has the sample-size penalty that
makes it meaningful at powder-pattern channel counts.

**Comparing against another code means adopting its protocol, not just reading
its numbers.** Mirror its refined-parameter set, its held parameters and its
excluded regions, then *check the channel count matches* before believing any
Rwp comparison. Measured: guessing a plausible protocol on the GSAS-II
fluorapatite tutorial gave Rwp 16 % and a +390 ppm cell; mirroring the
converged `.EXP` gave 9.73 % against GSAS's 10.05 % on an identical 5750
channels. The round robin measured the same class of error at community
scale: most of its alarming Rwp spread came not from the algorithms but from
what each program's sums *included* — background in or out, peak-only regions
or every channel (Hill, 1992).

---

## 4b. Declare the deliverable — "good enough" is a question about purpose

Much real work is non-ideal by construction: nanoparticle broadening erases
the fine detail a sharp-line protocol assumes, and porous frameworks (MOFs,
zeolites) carry intensity error from unknown pore contents that no profile
correction touches. **No bar moves for such data** — the gates auto-scale to
information content (measured: a zero error read at confidence 0.997 on sharp
data produces silence, GoF 1.02, on the same error under 0.6° broadening),
and "good enough" is a different question answered exactly, not a relaxed
standard. What changes is *which report rows decide your deliverable*.
Declare the deliverable, then read its rows — the report itself is
purpose-neutral, and it will not infer your purpose for you.

**Phase ID — "which phases are present?"** The rows that decide:
`report.unmatched` (`kind="unmatched_obs"`: strong entries are lines your
phase set does not produce) and `report.lebail_gap`, the structural-vs-profile
triage. The gap re-partitions the per-hkl intensities at the frozen converged
state (an evaluate-only Le Bail — θ never moves) and reports both Rwp: a
`ratio` ≫ 1 means positions and profile alone account for the pattern, so
every line is indexed and identification is safe **at any absolute Rwp** —
the misfit lives in intensities, which phase ID does not rest on. Stopping
criterion: no strong unmatched observed peaks, gap readable — done, whatever
Rwp says. An abstention with `abstained_kind="resolution_limited"` does not
block this deliverable (see below).

**QPA — "how much of each?"** Fractions ride on scales, so the deciding rows
are the ones that bias scales silently. The first of them is
`report.background.absorption`, keyed by parameter path: the block projection
R² of each structural parameter's Jacobian column onto the background column
span, the detector for the scale↔Biso↔background degeneracy of §3. A pairwise
ρ cannot see it (measured: ~0.2 per coefficient while the block absorbed
46 %), and the whole table is published rather than only the entries over
`BACKGROUND_ABSORPTION_NOTABLE` — a fired/not-fired bit is a verdict, and the
diagnostic already carries the verdict. Then absorption geometry (µR is
*exactly* a scale/Biso reparameterisation; µt is not, and its ΔBiso is larger
and negative), and physically-impossible refined values (§4.4: a negative
Biso is a background error laundered through a scale). The Le Bail gap must
be read the other way here: a large ratio means the intensity model is wrong,
and wrong intensities *are* wrong fractions.

Measured on this deliverable, and the reason the row outranks every statistic
beside it (LaB₆, broad peaks, same data both times, 2026-08-12): fitted with a
1°-knot unpenalized spline the refinement reports Rwp **0.08852** and GoF
1.022, against **0.08969** and 1.025 with a correct Chebyshev-6 — the wrong
background wins on every agreement index — and its displacement parameters
come back 0.958 and 0.000 Å² against a truth of 0.5, one of them on its bound,
where the correct background gives 0.691 and 0.327. `worst_absorption` reads
0.46 against 0.08. **Nothing else in the report distinguishes these two fits,
and the plot does not either**: the over-flexible residual is white noise
inside ±3σ. Stopping criterion: fractions stable under a
background-flexibility change, `worst_absorption` below its threshold, and no
unresolved scale-family diagnostic — never "Rwp stopped falling", which here
points the wrong way.

Two of this deliverable's rules are the QPA round robins' own findings
(Madsen et al., 2001, *J. Appl. Cryst.* **34**, 409; Scarlett et al., 2002,
*J. Appl. Cryst.* **35**, 383). A Rietveld σ(W) reflects only the fit's
mathematical precision and is "not necessarily related to the accuracy" —
judge a fraction against the published participant spread, never against its
own esd (the policy `tests/data/README.md` applies to the bundled `qarr/`
patterns, which are the round robin's own samples). And microabsorption is
the largest physical obstacle to X-ray QPA — "may prove to be insurmountable
in some circumstances" — with a Brindley correction applied where none is
needed *reducing* accuracy (their sample 1 and synthetic bauxite; §7's
`BRINDLEY_OUTSIDE_REGIME`).

**Structure — "where are the atoms?"** Everything above, plus the
intensity-model rows themselves: per-region intensity coefficients and their
angular trends (ADP vs scale vs texture), `report.texture` / `report.strain`
with their caveats, restraint tension, ADP positive-definiteness — and
`report.identifiability.exchanges` with `.soft_modes` (§4 step 6), because a
structural claim rests on the parameters *meaning* what they say: an
`exchangeable=True` row is a converged fit whose fitted partner and a held
parameter the data cannot separate, and the deliverable it supports is
`ambiguous`, not a structure. Here a
notable Le Bail gap is a *blocker*, not a comfort — the intensity model
carries the structural claim, and the gap says it does not carry the pattern.
Stopping criterion: §10's full ladder (diagnostics resolved, no attributable
region, ΔBIC refuses the next parameter), with no `exchangeable` row
unaddressed — addressed by running the swap (each rival **alone**, the other
at its null: `compare_rivals`, §4 step 6), and where that ties, by protocol (a
calibrant-fixed aberration, a wider window). Where it does **not** tie,
addressed means adopted: a decisive swap (≥ `RIVAL_DECISIVE_MIN_CHI2_RATIO`)
is an answered question, and the winning rival's fit is the structure's
answer, quoted without caveat — re-declaring it ambiguous after winning the
measurement is the mirror image of the ridge, and as wrong. Never by freeing
the rival into the same fit (§3's ridge), which is the
two-parameters-**together** move the swap exists to replace.

**The capability floor.** Whatever is reading this report, the floor is:
verify before acting (`predict_then_verify`, or a history branch), treat a
*capped* confidence (an `add_impurity_phase` at 0.3, a texture call capped
below its likely cause) as an **unresolved question**, never as a
low-priority instruction, and never execute a vetoed action. There is no
ceiling: a consumer able to reason past the floor may — the report supplies
evidence, judgment stays with the reader.

**The worked example, measured (LaB₆ pore proxy: a guest scatterer at the 1b
site in the data only, host model refined to convergence, 2026-08-12).**
Rietveld Rwp 0.0405, GoF 2.97 — a "bad fit" by GoF. The report: zero
suggested actions; intensity carries 83 % of the misfit in per-region errors
of 9–18 % with **alternating sign** ((100) low, (110) high, (111) low —
structure-factor interference, which scale, ADP and texture cannot produce;
the summary names it as un-modelled scattering contents); and
`lebail_gap.rwp_lebail` 0.0170 against 0.0405, ratio ×2.4. Read by
deliverable: phase ID is **done** — stop, at GoF 2.97. A structure
determination is **not** — and its next move is chemistry (what occupies the
pores), never finer profile corrections, which this evidence says cannot
help.

**Resolution-limited is a stopping point, not a failure.** On broad-peak
data a real aggregate misfit can be unattributable per kind: the abstention
then carries `abstained_kind="resolution_limited"` (the shape basis explains
the failing regions at median R² ≳ 0.9 — the edit directions are merely
indistinguishable on merged peaks). For phase-ID-grade work that is a
legitimate end state; for structure-grade work it means *collect better
data* — pushing finer corrections into a fit whose attribution is
resolution-limited changes numbers it cannot justify.

---

## 5. Read numbers, not pixels

This is the design premise of the package and the first thing that changes when
the operator is an agent.

A human judges a fit by looking at it, especially at peak-shape misfit. A
vision model cannot do that reliably: frontier VLMs fail precise value
extraction from dense plots (the CharXiv, ChartMuseum and ExChart benchmarks),
and one PNG costs ~1000–1600 tokens — about the same as 50 regions of exact
numbers. All three prior agentic Rietveld systems (AgentBuild, Rongzai,
guillemot — [DESIGN.md](DESIGN.md) § "Outputs & fit assessment" holds the
survey) fed plot images to a VLM and all three report the same failure:
*locally bad, globally fine* fits that the image hides.

So:

```python
report = ref.report(plan="lab_bragg_brentano")   # the plan supplies the Layer-2 veto
```

- **Layer 0** — model-free, always trustworthy: regions, per-region χ² share,
  cumulative-χ² breakpoints, unmatched peaks. Use this when the fit is bad.
- **Layer 1** — gated linear attribution: per region, how much of the misfit is
  a position error, a width error, an intensity error, a mixing error, an
  asymmetry error, with esds and each term's *share* of the explained misfit.
- **Layer 2** — typed suggested actions from a closed enum, each with a
  confidence, a rationale, `alternatives`, and `vetoed_by`.

The action vocabulary is closed (`ActionKind`, versioned by
`report_thresholds_version`), and each kind is carried out one of three ways —
`how`, quoted from the package's own recipe table (`report/apply.py`) and
stamped on every emitted action as `SuggestedAction.execution` (WP-1106), so a
JSON consumer reads it beside the numbers rather than from this table alone:
**stage** (one `run_stage` over the action's globs), **index** (a search, not a
stage), or **advice** (no verb — the note is the deliverable, and
`parameter_paths` is empty *by design*, not by omission). The table is every
member; emission conditions are the measured ones as of this writing and their
moves are logged in the schema version history:

| Kind | How | Emitted when | `parameter_paths` |
|---|---|---|---|
| `refine_zero_shift` | stage | the `constant` position template is significant (any geometry) | `instrument.zero_shift` |
| `refine_sample_displacement` | stage | the `cos_theta` position template is significant — Bragg-Brentano only (a capillary has no such aberration, WP-1073) | `instrument.geometry.sample_displacement` |
| `refine_sample_transparency` | stage | the `sin_2theta` position template is significant — Bragg-Brentano only | `instrument.geometry.sample_transparency` |
| `refine_capillary_offset_along_beam` | stage | the `sin_2theta` position template is significant — Debye-Scherrer only | `instrument.geometry.capillary_offset_along_beam` |
| `refine_capillary_offset_across_beam` | stage | the `cos_2theta` position template is significant — Debye-Scherrer only | `instrument.geometry.capillary_offset_across_beam` |
| `refine_cell` | stage | the `tan_theta` position template is significant (every geometry) | `phases.*.cell.*` |
| `refine_profile_widths` | stage | a width template is significant — always as the instrument-side peer of the sample action, at half its confidence, because a width trend alone cannot separate the two sides (the instrument's Gaussian polynomial spans the same shapes; Toby 2024 §4's U/V/W example). Try the sample terms first; reach for this when they leave the trend standing (measured: the sample proxy stalls at χ²_red 4.3 on a planted Gaussian deficit, this action takes the same state to the 1.01 noise floor — WP-1106) | `instrument.profile.u`, `…v`, `…w` — the Gaussian half only: a *Lorentzian* instrument width error is column-degenerate with `phases.*.lor_size`/`…lor_strain`, so the sample actions absorb it exactly |
| `refine_sample_size_broadening` | stage | the `inv_cos_theta` width template is significant | `phases.*.lor_size` |
| `refine_sample_strain_broadening` | stage | the `tan_theta` width template is significant | `phases.*.lor_strain` |
| `refine_axial_asymmetry` | stage | a significant asymmetry coefficient in gated regions below 2θ = 40° | `instrument.geometry.axial_sl`, `…axial_hl` |
| `refine_biso` | stage | the relative intensity error trends with sin²θ/λ² — the ADP signature | `phases.*.atoms.*.biso` |
| `refine_preferred_orientation` | stage | `TextureAnalysis.detected` with a best axis (both sides of the maturity gate); capped below a coexisting impurity call (§6's caveat row) | `phases.N.preferred_orientation.r` — named even when the phase declares no such block, on purpose: the rationale says which axis to declare first, and freeing nothing rolls back |
| `refine_scale` | stage | the `constant` intensity template is significant — an angle-independent scale error | `phases.*.scale` |
| `add_impurity_phase` | advice | strong unmatched observed peaks (> 8σ) not explained by the position-error evidence; when *every* one matches that evidence it is still emitted, capped at 0.3 with `reindex_or_recheck_cell` first among alternatives (§6) | empty **by design** — no phase is named yet, so there is nothing to free; the note says what to do instead |
| `increase_background_flexibility` | advice | between-peak misfit is systematic (high off-region χ²_red at low Durbin-Watson) — the too-stiff detector; capped at 0.6 however strong the evidence (§7's code block has why) | empty by design — the edit is to the background's *shape*, not to the free set; `instrument.background.*` would read as "free the background", which every plan already does |
| `decrease_background_flexibility` | advice | the background column span reproduces a notable share of a structural parameter (`report.background.worst_absorption`) — the too-flexible detector | empty by design, same reason |
| `reindex_or_recheck_cell` | index | validity-radius failures are widespread among the misfitting regions — and it survives abstention, where it matters most (§6) | `phases.*.cell.*`, but the verb is a search over cells, not a stage over parameters |
| `collect_better_data` | advice | the abstention classifier read the fit as `resolution_limited` (§6) — the one state whose remedy is the beamline, emitted at 0.5 so the data-quality reading outranks a phantom-impurity call. Its rationale carries the fork the evidence cannot resolve: instrumental breadth means better data exists; specimen breadth (nanocrystallites) means no re-measurement helps and the remedy is fewer free parameters and restraints. A `PATTERN_UNDERSAMPLED`-conditioned emission was measured and rejected — every bundled synthetic fixture trips that diagnostic beside converged GoF ≈ 1.01 fits (WP-1106) | empty by design — no parameter can be freed when the pattern itself is the limit |

**And read it at more than one state.** A report describes the state it was
built at, and the state a staged plan finishes in is routinely the least
informative one in the run: a compensated fit arrives somewhere that looks
converged and suggests nothing, because a real error has been absorbed into
whatever parameter the plan did free. Measured on the WP-1053 fixtures — a
−0.02 mm sample displacement, which no `mccusker_default` stage frees — the
final report reads Rwp 0.0137 with an **empty** action list, while the same
plan's *first* stage names `refine_sample_displacement` at confidence 0.997.
Nothing was hidden; only the last state was ever delivered. So take the
trajectory (§9), and treat a rung's high-confidence action as evidence about
the specimen even when the final report is silent.

Images are secondary evidence. `plot_for_vlm()` exists and renders what VLMs
*can* read (annotated multi-panel montage, worst regions auto-zoomed, Δ/σ panel,
high contrast, never JPEG) — use it to sanity-check a conclusion you already
reached from numbers, not to reach one. The Δ/σ panel is the literature's own
recommendation for human plots too (Toby, 2024: the weighted difference shows
the weighting, stops intense regions dominating with statistically
insignificant deviations, and sits on an absolute scale with expectation 1).

---

## 6. Abstention is a result. Do not convert it into a number

The package's hardest rule is **never return a confident wrong singleton**.
Several places will decline to answer. When they do, that *is* the answer —
propagate it, do not paper over it.

| Signal | Meaning | Correct agent response |
|---|---|---|
| `report.abstained_reason` is set | The global maturity gate refused Layer 1: the model is too far from converged for linearisation to mean anything | **Branch on `abstained_kind` first (WP-1057).** `"immature"` / `"unreadable"`: fix the fit using Layer 0; do not read `attribution`. `"resolution_limited"`: the basis *explains* the failing regions (median local R² ≳ 0.9) but its edit directions are indistinguishable on merged peaks — this is a statement about the data's resolution, **not evidence the model is wrong**, and for phase-ID-grade work a legitimate stopping point (§4b). Either way the actions that survive abstention (WP-1054) are the model-free ones **plus the position-family pointer**: when most misfitting regions have offsets beyond the linearisation radius, `reindex_or_recheck_cell` leads the list with the calibration candidates in `alternatives` — the same signature comes from a wrong cell and a gross zero/displacement error, and the data has not chosen. An `add_impurity_phase` at its capped 0.3 with `reindex_or_recheck_cell` first among alternatives means every "unmatched" peak matches the position-error evidence (displaced pairs / residual lobes) — do not add a phase on it |
| `TextureAnalysis.caveat` is set | Strong unmatched observed peaks coexist with the texture detection, and the per-reflection extraction partitions un-modelled intensity onto its calculated neighbours — an impurity can manufacture exactly this signature | The detection measures the residual, not necessarily the specimen. Resolve the unmatched peaks first; the `refine_preferred_orientation` action is already capped below `add_impurity_phase`, and the axis/r/R² stay readable as evidence |
| `region.gates_passed is False` | This region's coefficients failed resolvability / validity-radius / significance | Read `region.gate_failures`; the coefficients are present for transparency only and must **not** be read as causes |
| A trend is reported non-separable | Two angular templates (e.g. size vs strain) are collinear over this range | Do not pick one. Extend the range or report both |
| `PAWLEY_OVERLAP_UNRESOLVED` | A group's summed intensity is determined; the split is not | Treat the group sum as the datum |
| `STEPHENS_STRAIN_NOT_POSITIVE` | σ²(M) went negative on some reflection — outside the physical cone | The S_HKL are **not quotable**, and this is never evidence *of* anisotropy. Re-run with `solver="lm"`, which enforces the cone directly (measured on brucite: 12 of 43 reflections outside it under the default driver, 0 of 43 under `lm`, at a *higher* Rwp). That makes the answer admissible, not measured — vary the start and quote the coefficients only if they survive it (the `lm` result carries `CONSTRAINT_ACTIVE` when the cone actually bound) |
| `ADP_NOT_POSITIVE_DEFINITE` | The tensor is not an ellipsoid; its Debye-Waller factor diverges at high Q | Revert the site to isotropic `biso` |
| `ROUGHNESS_UNCONSTRAINED` | The refined correction depresses no modelled reflection by >1 % | Drop the block. The value it refined to is arbitrary |
| `PHASE_UNCONSTRAINED` | This phase's strongest modelled point sits below 1σ of the observation noise, so the data cannot distinguish it from absent — and `where` lists its parameters that were refined against it anyway | **Those values are not measurements**, whatever their esds say: they moved in a flat direction, since every structural parameter of a phase reaches the pattern only through `scale × |F|² × profile`. Do not read them, and do not read a converged status or a good Rwp as covering them — a parameter that does not move y_calc does not move Rwp either. Decide which case it is: the phase is not in this specimen and belongs out of the model, or its scale is stuck at its floor and must be seeded before anything else of it is freed. On a series, expect this per pattern — see §7's note on reading it across a run |
| `SEQUENTIAL_PATH_DEPENDENT` | A parameter's trajectory differs between the forward and backward chains by more than their esds allow | That trajectory is an artefact of the refinement order, not a measurement. Hold the parameter, restrain it, or quote the forward/backward spread as its uncertainty |
| `SEQUENTIAL_PERSISTENT_FINDING` | A per-pattern code fired in **more than half** the patterns; `where` names the parameter and `value` is the fraction | Read it as a property of the **model**, not of any pattern. One `BOUND_HIT` is a pattern that hit a bound; a `BOUND_HIT` in most of them is a bound that is wrong. Change the model or the plan — refitting the individual patterns will reproduce it. This exists because no per-pattern diagnostic can say "42 of 68": in the episode this comes from, 425 `BOUND_HIT`s went unread for two hours while `phases.3.cell.c` was pinned in 42 of 68 patterns. The per-entry diagnostics still carry every occurrence |
| `SEQUENTIAL_CANCELLED` | The chain was cancelled: the pattern in flight was abandoned and the rest were never started | The reported entries are complete fits and stand on their own, but the trajectory is **truncated, not finished** — do not read its last point as the end of the ramp, and do not compare a slope over it with one over the whole series |
| `SEQUENTIAL_UNRECOVERED` | A pattern diverged and stayed diverged after every rung of the escalation ladder (`entry.rungs_tried` names them) | Read that point as a **failed fit, not a datum** — do not interpolate across it and do not quote its parameters. Its neighbours are unaffected: the chain stepped over it, so the successor warm-started from the last pattern that converged and the reseed median never saw it. Fit the pattern on its own to find out why (a specimen change the model lacks, a bad scan, a starting model that no longer suits this end of the series) |
| `IndexingResult.best_or_none()` returns `None` | No candidate cell reached the confidence gate | **This is the most likely outcome of a first indexing run, and it is not a failure.** Read each candidate's `confidence_caveats` and act on the *refuting* ones first (§7c). Never take `candidates[0]` because it is ranked first — the ranking orders the hypotheses, the gate judges them, and the two are different questions. Since WP-1046 the order leads with **corroboration** (at least two engines found the lattice) and ranks the panel within that, so `candidates[0]` is now "corroborated, then best on the panel" rather than "best on the panel" — closer to the gate's own reading, and still not it |
| `INDEX_ABSTAINED` | The result declined to name a cell, and says why | Propagate the abstention. The candidates are there so you can see what was considered, not so you can pick one |
| `INDEX_GEOMETRIC_AMBIGUITY` | Two distinct lattices explain the positions equally well (Mighell & Santoro 1975) | Do not pick one. The information is **absent from the measurement**, not buried in noise — collect to the 2θ in `discriminating_two_theta` and look for the reflections named there |
| `INDEX_MULTIPLE_SOLUTIONS` | More than one candidate satisfies the whole gate | Compare the panels and each `lebail.rwp`, and extend the 2θ range: two cells that both explain a range this wide are usually separated by one high-angle reflection |
| `INDEX_SEARCH_INCOMPLETE` | A budget expired before the domain did | Do not read "no cell found" as "no cell exists". Only a *completed* exhaustive search says that, and `search_complete[system]` says which systems finished |
| `INDEX_BUDGET_EXHAUSTED` | The declared whole-run ceiling (`total_budget_seconds`) bound | The answer covers what was *reached*. Read the three states of `systems_searched` (§7c) before treating any absence — of a system, a candidate, or a validation — as evidence |
| `INDEX_SYSTEMS_NOT_COVERED` | Systems were not searched | Read a failure as "no cell in the systems searched", never as a statement about the specimen — and in particular never as "this is multiphase" (§8.15) |
| `ExtinctionScreen.best_or_none()` returns `None` | No extinction class is separated from its rivals by these data | Read the ranked `candidates` and `EXTINCTION_SYMBOL_AMBIGUOUS`, which states every reason at once. The action is a longer count at the *forbidden positions the leading classes disagree about*, or a wider range — never the better Rwp, which always favours the class with more reflections |
| `EXTINCTION_GROUPS_NOT_SEPARABLE` | The leading class holds more than one space group | Nothing. This is **not** a data problem and no counting time fixes it: those groups differ only by elements that produce no absences. Carry the whole list forward and choose with chemistry (§7e) |

`Layer 1`'s gates, for reference, are: resolvability on the **scale-normalised**
Gram matrix, a 0.4·FWHM validity radius (a peak 5 FWHM off must trigger
"re-detect", never a confident small-offset reading), local χ²_red
significance, and share-based global maturity. Confidence weights *importance*
(share of χ²), not only statistical significance — at high counting statistics
the second-order leakage of a peak shift into the width column is significant
but carries a per-cent-level share.

The per-region refusals arrive typed — `region.gate_failures` is a list of
`GateFailure(code, message)` since WP-1003, promoted from formatted strings
precisely so a consumer can branch on the name; the `message` carries the
measured numbers and is display-only. The vocabulary (`GateCode`) is closed,
the global maturity gate has no entry here (it abstains the whole layer,
`abstained_reason`/`abstained_kind` above), and one member is not a failure at
all:

| `GateFailure.code` | Meaning | Correct response |
|---|---|---|
| `no_significant_misfit` | this region's local χ²_red is at the noise floor — there is nothing to attribute | Nothing. This is a region the model already fits, **not** a failure of the basis and not evidence about the model; a report full of these is what a good fit looks like |
| `local_r2` | the region's misfit is real but the basis explained too little of it (low local R²) | Do not read the coefficients as causes. The misfit is not position/width/intensity/mixing/asymmetry-shaped — suspect what the basis cannot express: an unmatched peak (Layer 0), background shape, peak-shape misfit |
| `gram_condition` | the templates' scale-normalised Gram matrix is ill-conditioned here: the edit directions are indistinguishable on these merged peaks | The resolution-limited signature, per region (`abstained_kind="resolution_limited"` is the same statement globally). Do not pick one coefficient — the separation is absent from the data at this resolution, so the fix is a wider range or better resolution, never a preference |
| `outside_validity_radius` | the fitted offset exceeds the 0.4·FWHM linearisation radius, and a linear fit pushed past it *saturates* | **Re-detect, never shift**: read the fitted offset as a lower bound, not a measurement. Widespread across misfitting regions, this is exactly what emits `reindex_or_recheck_cell` with the calibration candidates in `alternatives` (the abstention table's first row, above) |

---

## 7. The diagnostics are the channel for "your answer is wrong although Rwp is fine"

Every code below is a structured `Diagnostic` on `result.diagnostics` with a
`level`, a `where` list of parameter paths, a `message` and a `suggestion`.
**Branch on the code, not on the message text.**

| Code | What it means you must not do |
|---|---|
| `HIGH_CORRELATION` | Quote both members of the pair as independently measured |
| `BOUND_HIT` | Quote a parameter sitting on its bound as a measurement. Iterating `result.parameters` instead of cross-referencing this code by path? `RefinedParameter.at_bound` is the same finding on the row — but it is three-valued, so test `is True`, never truthiness: `None` means the row was not tested (it is tied, or the result came from `replay`), and that is not `False` |
| `BACKGROUND_ABSORPTION` | Quote ADPs, scales or QPA fractions from this fit — the background can imitate them, and Rwp *improved* while they biased. Read the number, not the bit: `report.background.absorption` is the same measurement for **every** screened parameter, fired or not, and `result.identifiability.background_absorption` carries it on the result |
| `ROUGHNESS_ABSORPTION` | Quote roughness and the displacement parameters as two separate results |
| `ROUGHNESS_UNCONSTRAINED` / `ROUGHNESS_OUTSIDE_REGIME` | Interpret the roughness parameters physically |
| `PHASE_UNCONSTRAINED` | Quote **anything** about this phase — its cell, its coordinates, its ADPs, its weight fraction. `HIGH_CORRELATION` on the same fit reports ρ≈1 between the phase's cell and its scale, which is the symptom; this is the cause |
| `ADP_NOT_POSITIVE_DEFINITE` | Report the tensor as measured |
| `STEPHENS_STRAIN_NOT_POSITIVE` | Report any S_HKL |
| `DISPERSION_NEGLECTED` | Quote QPA weight fractions — unequal f′ across phases biases them directly (measured: RMS 2.26 → 0.69 wt % once applied) |
| `ABSORPTION_ESTIMATE_UNAVAILABLE` | Assume the absorption correction ran. It did not; the fit has **no** specimen absorption correction |
| `ABSORPTION_MU_R_OUT_OF_RANGE` | Trust the magnitude of the correction — µR > 1 extrapolates the Rouse fit |
| `ABSORPTION_THICKNESS_MATTERS` | Quote displacement parameters without checking the flat specimen's thickness — part of the correction is not absorbable by the scale and ADPs, so a wrong µt lands in both |
| `ABSORPTION_PLATE_THICKNESS` | (info) Read it as a fit problem — a transmission plate far from µt = 1 costs counts, not accuracy |
| `WAVELENGTH_CALIBRATION` | (info, joint fits only) Quote the cell without saying which histogram's wavelength was **held**. This fires whenever a wavelength was refined, and reports how far it moved from its declared value **in ppm** together with the shift over its own esd. It is the only evidence the refinement offers for that move — deliberately not an Rwp comparison. Read a move inside its own esd as "this measured nothing"; read a move far past the beamline's known calibration drift as a modelling error in *that* histogram (an unmodelled harmonic, a zero shift traded against λ) rather than as a calibration result. The refined cell sits on the scale of the held wavelength, so the held one is part of the number |
| `BRINDLEY_OUTSIDE_REGIME` | Prefer the corrected fractions; past µR ≈ 0.05 the "correction" can be further from truth than none — the QPA round robin's community-wide finding (Madsen et al. 2001; Scarlett et al. 2002: over-correction where none was needed cost more accuracy than the effect it corrects) |
| `MICROABSORPTION_SKIPPED` | Assume microabsorption was handled |
| `PAWLEY_OVERLAP_UNRESOLVED` | Use an individual reflection intensity from the group |
| `DATA_SUPPORT_LOW` | Read the esds as the whole story. There are fewer effective observations per structural parameter than the guidelines ask for (at least three, preferably five), and an over-parameterised Rietveld refinement does not fail — it reports large esds while the algorithm's own N, the number of profile *steps*, hides the shortage. `warning` below three, `info` between three and five; the numbers are on `result.data_support` either way, and the message quotes the effective count, the raw reflection count and the parameter count it divided. The remedy is fewer parameters (start from `result.identifiability`), restraints, or a wider 2θ range — never more points across the same peaks, which raises N and nothing else |
| `PATTERN_UNDERSAMPLED` | Quote integrated intensities, ADPs or QPA fractions and expect the step size not to be the limit. The median resolved peak has fewer than five steps across its FWHM, so those intensities were never measured finely enough — and unlike everything else in this table, **no choice made after the fact repairs it**: the counts do not exist. The fit still runs and the number is on `result.data_support`'s companion `PatternDiagnostics.steps_per_fwhm` before any refinement, from `diagnose(data)`. Above ten steps there is no code at all — oversampling costs beam time, not validity |
| `RESTRAINT_TENSION` | Silently accept the averaged compromise — the data and your prior disagree by >3σ |
| `SEQUENTIAL_RESEED` | Read this point of a series as evidence that the trajectory is continuous — its starting values did not come from its neighbour |
| `SEQUENTIAL_DISCONTINUITY` | Report the jump as physics without opening that pattern's own fit; it is equally the signature of a chain failure |
| `SEQUENTIAL_PATH_DEPENDENT` | Quote that parameter's per-pattern esd as its uncertainty — the between-chain spread is larger and is the honest one |
| `SEQUENTIAL_CANCELLED` | Read the shortened `entries` list as the series — it is where the chain stopped, not where the ramp ended |
| `SEQUENTIAL_UNRECOVERED` | Read that point's values as a measurement, or its failure as evidence about its neighbours — nothing was chained through it |
| `CONSTRAINT_ACTIVE` | (info, `solver="lm"` only) Read the constrained coefficients as free-fit measurements. The driver truncated steps against a linear-inequality constraint (the Stephens cone) in the answer-producing stage, so the optimum sits on or near a constraint face: admissible, not measured. Vary the start before quoting — and note this is the *only* signal a declared constraint was active rather than merely present |
| `QPA_UNAVAILABLE` | Read `result.qpa is None` as "this specimen is single-phase" or as any statement about composition. The refined scales gave a non-positive Σ S·ZMV, so there are no fractions to renormalise — `where` names the scales that died. It is reported rather than raised on purpose: QPA is one field of a result, and raising took a whole 157-pattern sequential run down with one bad pattern |
| `MODEL_FAR_FROM_DATA` | (error) Read `status`, the parameter values or their esds at all. Rwp is past the point where the model is no better than predicting zero everywhere, so this is a mismatch between model and data, not a converged refinement — and the solver may well say `converged`, because driving the phase scale to zero *is* a minimum once the cell is far enough off that every reflection sits outside its frozen evaluation window. The message quotes the share of above-background intensity the model actually accounts for (0.2 % on the reproduction); check the cell (~1 % precondition, §1), wavelength, zero shift and 2θ range, then re-index |
| `STAGE_MAX_ITER` | Read the result's `status` as covering every stage — it is the *last* stage's, so a middle stage can stop on its iteration budget while the fit reports `converged`. The named stages did not converge; they ran out. Raising `max_iter` buys solver evaluations, not a different minimum — the stages that stall are the degenerate groups in §3 (measured: three identical mixtures, same models and parameter counts, 39 s / 858 s / 2838 s with no difference in the answer) |
| `CIF_CELL_ANGLE_CORRECTED` | (warning — from the reader, same channel as `CIF_SPECIES_NORMALISED`) Assume the cell is the file's. A symmetry-fixed angle disagreed with its space group by a *reportable* amount (up to 0.1°) and was read at the exact value, because `ParameterTable` refuses such a cell and has no channel to say why. The deviation is information: if it is real, the symmetry is lower than the symbol claims. A disagreement beyond 0.1° is **not** corrected — it still raises, because the symbol and the angle contradict each other and choosing between them is yours |
| `PATTERN_SCAN_REVERSED` | (info — from the pattern reader: pass `read_pattern(..., diagnostics=[])` to collect it) Assume the point order in the file is the point order you are fitting. The scan was stored high 2θ → low and was reversed, which is lossless — the same measurement written backwards — but it means an index into the file is not an index into the pattern |
| `PATTERN_DUPLICATE_POINTS` | (info — from the reader) Quote the file's point count as the fitted channel count. One or more 2θ values appeared twice with the *same* intensity and the repeats were dropped. A repeat with a *different* intensity is not reported here: it raises, because averaging invents a datum and dropping picks one |
| `PATTERN_MULTISCAN_DEFAULTED` | (warning — from the reader) Read the result as a fit to the file. The file holds several scans, none was named, and **scan 0** was read — a third of a measurement is a choice, and this one was made by default rather than by you. Pass `scan=` (or `list_scans(path)` first) before quoting anything |
| `PATTERN_X_AXIS_ASSUMED` | (warning — from the reader) Trust the 2θ scale. The file states which axis it scanned and named one this reader does not recognise, so the x column was read as 2θ in degrees. Each format states it somewhere different — `.chi`'s line-2 label, `.ras`'s `*MEAS_SCAN_AXIS_X`, `.uxd`'s `_DRIVE`, `.xrdml`'s `scan/@scanAxis` — and the message names both the field and what it held. The code means **unrecognisable**, never "recognisably not 2θ": an axis that *is* recognisably q, d, ω, χ, φ or a translation is **refused**, because such a scan parses perfectly and refines to a confidently wrong cell. Worth taking seriously — most vendor files are not powder scans (4 of the 5 real `.uxd` files obtained are pole figures or rocking curves), and a block marker is not evidence either: a rocking curve is stored under `_2THETACOUNTS` too |
| `PATTERN_INTENSITY_SCALED` | (warning — from the reader) Quote esds, χ² or a σ-normalised residual from this fit as if the weights were measured. The stored intensities are not whole numbers and no counting time in the header makes them whole either, so whether they are counts or a rate **could not be established** — and no σ was supplied. The Poisson fallback √max(y,1) is therefore being applied to a quantity that may already be divided by a counting time, in which case every weight is wrong by √t. The fit still runs and the *parameters* are largely unaffected; it is the uncertainties that are not quotable. Re-export in counts, or supply esds |
| `RAS_ATTENUATOR_PRESENT` | (warning — from the reader) Compare intensities across the 2θ range this names. A Rigaku `.ras` or `.rasx` carried an attenuator factor that is not 1, and it was **not** applied: no specification states whether the intensity column is already corrected for it, so applying it and not applying it are both defensible and guessing corrupts exactly the strong peaks Rietveld weights most. σ is affected too — √counts·attn is not √y. The message names the affected points; check the export against the instrument software before trusting their relative heights. Contrast `XRDML_ATTENUATOR_APPLIED`, where a real file settles what no Rigaku file can |
| `XRDML_ATTENUATOR_APPLIED` | (info — from the reader) Nothing; it is here because the correction is large and invisible in the file's own numbers. A PANalytical beam attenuator dropped a foil in front of the detector for the points named, and the reported intensity is `counts × factor` with σ = √counts·factor — **not** √y. Read it as the opposite of `RAS_ATTENUATOR_PRESENT`: this one is settled, because a real file shows the raw series *dipping* at exactly the attenuated point of a substrate reflection, which is the attenuation and not a profile. A factor of 188 over one point is normal. The case GSAS-II gets wrong, weighting 1/y regardless |
| `BRML_ABSORBER_ENGAGED` | (info — from the reader) Nothing to the intensities; they are already right. A Bruker automatic absorber engaged over the points named, and the stored series is **already corrected** for it, so nothing was multiplied — but those points carry a factor fewer counts than their height suggests, and σ was derived as √(y/a)·a rather than √y. The third answer to one question: `RAS_ATTENUATOR_PRESENT` reports because no Rigaku file settles it, `XRDML_ATTENUATOR_APPLIED` multiplies because a real file shows the raw series dipping, and this one leaves the values alone because a real file shows them continuous |
| `READER_OPTION_IGNORED` | (info — from the reader) Assume a reader option you passed took effect. This format does not take it, so the file was read as if it had not been given — normal when a form carries a value across a change of file, and a mistake when you named a `block` or a `scan` you meant to select. Check `identify_format` claimed the reader you expected |
| `CIF_SPECIES_NORMALISED` | (info — from the reader: pass `Structure.from_cif(..., diagnostics=[])` to collect it; it is not on `result.diagnostics`) Assume the model's species are the file's literal type symbols. The reader rewrote a wild form — a site label in the type-symbol column (`O1`) or a sign-first charge (`O-2`) — onto the canonical grammar, keeping the ion when one was written; each message names its substitution and `where` lists the atoms it touched |

```python
codes = {d.code for d in result.diagnostics}
if "BACKGROUND_ABSORPTION" in codes:
    # stiffen the background BEFORE reporting anything intensity-derived
    ...

# the same measurement as evidence rather than as a bit — and the two
# background hypotheses, which are advice: they change what the background can
# *absorb*, not which parameters move, so there is no stage to run
bg = report.background                      # None only if no background curve
bg.worst_absorption, bg.worst_absorption_path    # 0.46, "…atoms.0.biso"
bg.absorption                                    # every screened path → R²
bg.off_region_chi2_reduced, bg.off_region_durbin_watson   # 12.6, 0.19
report.action("decrease_background_flexibility")  # fewer terms, larger λ
report.action("increase_background_flexibility")  # capped at 0.6 — see below
```

`increase_background_flexibility` is capped however strong its evidence,
because an amorphous hump and an un-modelled broad crystalline phase produce
the same between-peak signature as a too-stiff background, and bending the
background over either of the last two **hides** it while improving every
statistic. `add_impurity_phase` rides in its `alternatives` for that reason,
and each names the other. If you add the flexibility anyway, read any QPA
afterwards as fractions of the crystalline content you did model.

### 7b. Peak picking and indexing (`PeakList.diagnostics`,
`DataQualityReport.diagnostics`)

These arrive from `rietx.pick_peaks` and
`rietx.indexing.assess_peak_list`, *before* any refinement exists — so they
are read on the peak list, not on a `RefinementResult`.

| Code | What it means you must not do |
|---|---|
| `PEAK_LIST_TOO_SHORT` | Read the answer as *scored*. Below 20 usable lines the classical figures (M₂₀, F₂₀, Smith's envelope) are undefined, so the search still runs — over the systems the line count supports — but ranks on the reduced panel, and nothing in the answer is comparable to a published threshold. (Before WP-1043 this code refused the search outright; that conflated scoring with searching, and it refused fluorite's 18 clean lines that all three engines index at −5 ppm) |
| `INDEX_DATA_INSUFFICIENT` | Spend a search budget. The gate has already decided the data cannot support a search *in any system*, and it names which of the two reasons applies (lines per metric degree of freedom, or σ(Q)/Q) |
| `INDEX_PANEL_REDUCED` | Treat an absent figure as zero, or compute your own M on fewer lines and quote it as M₂₀. Each absent member is named with its reason on `quality.fom_undefined`; the members that remain rank every candidate alike, so the *order* means what it always does — the `fom_panel_reduced` caveat (capping) is what says the scoring does not |
| `PEAK_SIGMA_ASSUMED` | Quote a precision, or weight lines by 1/σ² as if that meant something — every σ in the list is the same assumed constant. Re-pick from the pattern if you have it. **You may still index it**: an assumed σ is not grounds for refusing, so the σ(Q)/Q abstention below does not run on such a list (it would be quoting a precision this package invented) |
| `PEAK_NOT_SEPARABLE` | Treat the flagged component as a line, or as noise. It is neither: the fit believes in it as *shape* and disbelieves it as a *line*, so it stays in `peaks` (removing it from the model displaces the real line beside it) and is excluded from `usable()`. If many fire, suspect a **mis-declared instrument profile** rather than a crowded pattern — undeclared axial divergence reproduces the whole effect |
| `PEAK_POSITION_PRECISION` | (info/warning) Ignore it when choosing a tolerance: it *is* the resolving power of the list, and it bounds every tolerance downstream |
| `INDEX_SHIFT_DETECTED` | Absorb the shift into the cell. The named template is the physical cause; correct the instrument (`zero_shift`, `sample_displacement`, `sample_transparency`) rather than the lattice |
| `INDEX_SHIFT_MODEL_AMBIGUOUS` | Pick one cause from this data. The magnitude is measured and the cell is safe to `prediction_spread_deg`; the *cause* is not identified, and extending the 2θ range is the only fix |
| `PEAK_KALPHA2_ALIAS` | Assume the dropped candidates were noise — each is at a stronger line's Bragg-predicted Kα2 position, and a genuine coincident line is indistinguishable from an alias in one pattern |
| `PEAK_AXIAL_TAIL` | (info) Read the flagged components as lattice lines — or exclude them without looking. Each sits on the axial-divergence **tail side** of a much stronger group-mate (low-2θ below 90°, high-2θ above — the one sign flip nothing else has), and they stay *usable* because the side test is evidence, not proof. Measured on SRM 660c (WP-1043): five such components carried 125 ppm of certified-cell bias, and excluding exactly the flagged ones plus measuring the shift took the gate to `high` at −2 ppm — so on a well-aligned Bragg-Brentano pattern, excluding them before indexing is usually right |
| `PEAK_KALPHA2_RESIDUAL` | (info) Treat it as a line of anything. It sits at a strong group-mate's **predicted** Kα2 maximum at a few per cent of its area — the residual of a *modelled* doublet, re-created by a re-seed pass after detection dropped the alias. Kept usable only because a genuine reflection can coincide with an alias position; exclude it before indexing unless you have a reason to believe one does |
| `PEAK_UNRESOLVED_SHOULDER` | Quote one of a pair as an independent line. Their σ already carries the correlation |
| `PEAK_CONTAMINATION_LINE` | Subtract it. Ghosts are flagged and excluded from `usable()`, never stripped |
| `PEAK_ASYMMETRY_UNMODELLED` | Trust the *positions* of the flagged lines. An unmodelled one-sided aberration biases a centroid in one direction, which σ cannot see — and the low-angle lines are the ones indexing depends on most |
| `PEAK_WIDTH_LAW_MISMATCH` | Leave `instrument.profile` as declared. A factor near 13 is the `ProfileTCHZ` synchrotron default (W = 1e-3 deg², FWHM ≈ 0.03°) on lab data |
| `PEAK_SHOULDER_SEEDED` | (info) Read a shoulder-seeded line as a detection. Survival was decided by ΔBIC, not by detection |
| `INDEX_SEARCH_INCOMPLETE` | Read "no cell found" as "no cell exists". Only a *completed* exhaustive search says that; this one ran out of budget, and `search_complete[system]` says which systems it covered |
| `INDEX_DOMINANT_ZONE` | Conclude the pattern cannot be indexed. The exact-solve engine found nothing at its base-line index table but found a cell with a wider one, which means one axis is long enough (or short enough) that the lowest observed lines carry large indices. Use the dichotomy engine, which bounds the metric instead of assuming indices |
| `INDEX_SHIFT_ALLOWANCE` | (info) Quote the winning cell without fitting a shift template. The search *assumed* a systematic allowance (no shift had been measured), and a cell found inside a widened window absorbs the shift — measured, +1400 ppm on a certified pattern. Re-fit with `shift_template` and quote that cell |
| `INDEX_SHIFT_FROM_PAIRS` | (info) Read the reported amplitude as naming a *cause*. It does not: the pair method measures the shift's size from harmonic reflection pairs with no reference, and `constant` and `cos_theta` are collinear over an ordinary range, so `best` is not an attribution. Read `pairs.refuted_templates` for what the data *do* reject, and widen the 2θ range if the cause matters |

### 7c. The answer's own diagnostics (`IndexingResult.diagnostics`, and each
candidate's)

These arrive from `rietx.index_pattern`. **Statements about one candidate live
on that candidate** (`result.candidates[i].diagnostics`); statements about the
result live on the result. `INDEX_ABSTAINED` names the top candidate's caveats,
which is the pointer from one level to the other — so read both, and start at the
result.

| Code | What it means you must not do |
|---|---|
| `INDEX_PREDICTED_BUT_ABSENT` | Keep this candidate. The lattice needs reflections the pattern does not have — the oversized-cell signature, and the one M₂₀ cannot see. Prefer the smaller cell that indexes the same lines: a cell whose extra reflections are systematically absent has a translation it is not using, so the lattice is the sublattice. **Do not check this with Rwp** — measured, an oversized cell scores 0.379 against a correct 0.216, a gap smaller than the spread between specimens |
| `INDEX_IMPURITY_LINES` | Read it as one thing. A handful of unexplained lines is an impurity; most of the pattern is a wrong metric (measured, 95 of them when the metric was 1 % off). And note the fence: this package does **not** index multi-phase patterns, so a second phase means subtracting the solved one first |
| `INDEX_BRAVAIS_AMBIGUOUS` | Refine in the higher symmetry because it was reported. The stated system is the conservative one; refine there and *test* the higher one, never the reverse. A disagreement between gemmi and spglib is information, not a bug — their tolerances are different kinds of number (a Le Page obliquity in degrees against a `symprec` in Å) and disagreement is what genuine pseudosymmetry looks like |
| `INDEX_VOLUME_UNPHYSICAL` | Quote the cell. It is outside what these data can support — below a single atom's exclusion volume, or clear of Smith's (1977) envelope for the number of lines observed |
| `INDEX_NOT_VALIDATED` | Read a `medium` as a near-`high`. No pattern was supplied, so nothing tested any candidate against the whole profile, and the figure-of-merit panel is blind to lines beyond the first twenty, to impurity content and to predicted-but-absent reflections. Pass `data=` and `instrument=` |
| `INDEX_VALIDATION_FAILED` | (warning — on the candidate's `lebail.diagnostics`) Read this candidate's Le Bail numbers as a judgement, in either direction. The validation *fit* raised (the message names the exception), so `lebail.rwp` is inf and its `status` is `failed`: nothing was measured, which refutes nothing. It is evidence about the candidate, not about the search — but check the instrument before discarding the candidate, because a mis-declared profile or a wavelength on an absorption edge fails every candidate alike, and a run whose validations all fail this way is telling you about the setup, not the cells |
| `INDEX_BUDGET_EXHAUSTED` | Read the answer as covering the requested search. The ceiling (`quick`'s default, or a declared `total_budget_seconds`) bound, and the result covers what was *reached*: `systems_searched` + `search_complete` distinguish three states — searched (present, `True`), truncated (present, `False`), and not reached (absent; the diagnostic's `where` names them) — and candidates whose validation never ran read `not_validated` (capping), never `validation_failed` (refuting). Units run system-major (WP-1042), so what a binding ceiling cuts is trailing low-symmetry *systems* for every engine equally, never a whole engine — a candidate from a completed system keeps all its finders. The message also distinguishes the slice-only case: the run finished under its ceiling but one or more validation fits exhausted their equal slice of the remaining clock. A user cancellation never writes this code: a stopped run is not a budget statement |
| `INDEX_SINGLE_ENGINE` | (info) Read `low` as "refuted". One engine ran, and agreement between independent searches is what confidence measures — so every candidate of a one-engine run grades `low` *structurally* (fewer than two finders), which means "unconfirmed by construction". It is a diagnostic rather than a caveat because a capping caveat cannot explain a floor `grade()` produces before caveats are consulted. Re-run with the default engine set for a gradeable answer |
| `INDEX_CELL_SYSTEMATIC_UNQUANTIFIED` | Quote a Bragg-Brentano cell to its esd. The esd is a *precision* from the line positions; the goniometer radius alone carries **≈ ±85 ppm** that no esd reports, because the data cannot identify it (Rwp moves 0.029 points across 180–320 mm) |
| `INDEX_CANDIDATES_TRUNCATED` | (info) Read the reported list as everything the search produced. It is the top `max_candidates` of a larger merged set, and the message says how many ranked below it — the cap exists because each reported candidate is priced a Le Bail fit, not because the rest were judged. Its second clause names any (engine × system) unit that returned a **full pool** (five times the reported cap since WP-1046); that clause is a flag rather than a count, because how many distinct lattices sat behind a discarded harvest is not knowable without deduplicating one the search already dropped. Raise `max_candidates` to see further down — it raises the pool with it, and the cost is the validation fits |
| `INDEX_PRIOR_USED` | (info) Read the answer as unsteered. It *was* steered — this diagnostic names each declared prior and its fate (confirmed by engines / entered unconfirmed / refuted / refused at the box) — but steering changed only *when* things were searched and what seeded the stochastic engine, never a range, a system set, or a rank: prior-only candidates are appended **after** the ranked list and never enter the Borda ranking. A candidate whose `found_by` is `["prior"]` alone is stated-and-unconfirmed — the ordinary agreement caveat grades it down, so treat it as your own hypothesis checked against the lines, not as a finding (WP-1045) |

### 7d. The closed loop: from a pattern of an unknown phase to a refinement

Indexing is the step that used to be missing. Before it, this package could
refine a structure against a pattern but could not find the cell, so an unknown
phase was out of reach entirely. `index_pattern` is a peer of `refine` and the
loop between them closes:

**These names are provisional, and the answers they return are versioned.**
Indexing is under active development, so everything under `rietx.indexing` and
every answer type in `rietx.schemas.indexing` may change in any release — the
[compatibility promise](https://yue-here.github.io/rietx/using/compatibility.html#provisional-by-declaration)
declares the subsystem rather than listing names, and every change is in the
release notes. Two things do not move with them:
`capabilities().indexing_thresholds_version`, which is what the gates below are
versioned by, and the `indexing` arm of `refine_json`'s response (§9c). So a
tool loop that *reads* an answer sees any observable change as a version bump;
one that imports these types should pin an exact version.

**How long will this take?** Since WP-1042 the default answers this itself:
`index_pattern` resolves the **`quick` preset** — every engine, every requested
system, and a whole-run ceiling (`SEARCH_PRESETS["quick"]`) covering search,
probe and validation, with each validation fit drawing an equal slice of the
remaining clock. Nothing is narrowed; a run that hits the ceiling says so
(`INDEX_BUDGET_EXHAUSTED`, §7c) rather than having silently searched less, and
what it cuts is the trailing low-symmetry systems — cheapest-first ordering's
documented cost. Progress and a graded shortlist for every *completed* system
stream on the event ladder as the run goes (`events=`), so the useful answer
usually arrives seconds in, long before the run ends. `preset="full"` is the
unbounded pre-1.0 behaviour — reach for it when a quick run reports truncated
or not-reached systems and the answer may live there. For the arithmetic, ask
`rietx.indexing.engines.estimate_ceiling(spec)` (CLI: `rietx index
--ceiling`): `budget_seconds` (default 30) is per **(engine × system)**, the
worst case is that arithmetic plus the probe plus per-fit validation (measured
0.6–44 s each), against measured typicals an order of magnitude lower, because
searches usually finish their systems early. Budgets are runaway guards, not
timers — this package's record has six point measurements where a longer run
never bought a better answer, and one where too little budget reported a wrong
centring, so bound generously and read the three states rather than shrinking
the search.

**State what you know.** You often hold something the search does not: an
isostructural analogue from a database hit, a homologue's cell, a family's
space group. Declare it (WP-1045) — `SearchSpec.prior_cells` /
`prior_spacegroups`, the same fields on the agent request's `search` and in
the GUI's Search controls — and the search runs the prior's crystal system
*first*, seeds the stochastic engine's starting basin with the stated metric,
and checks the cell itself against the lines. Three facts make this safe to
do liberally: a prior **steers, never gates** (no system dropped, no range
changed, prior-only candidates appended after the ranked list — a wrong
prior costs time, not truth, and that sentence is pinned by test); a *real*
prior is then found by the engines themselves, so `found_by` and the grade
keep their meaning; and `INDEX_PRIOR_USED` records what you assumed and what
it changed, so assumed knowledge can never read as measured knowledge. A
worked example — you suspect the specimen is isostructural with calcite
(R -3 c, a = 4.99 Å, c = 17.06 Å):

```python
idx = rietx.index_pattern(
    peaks, data=data, instrument=instrument,
    spec=rietx.indexing.SearchSpec(
        prior_cells=((4.99, 4.99, 17.06, 90.0, 90.0, 120.0),),
        prior_spacegroups=("R -3 c",)))   # trigonal jumps the queue; the
                                          # centring steers the prior's check
# or, as the one JSON call (§9c):
# {"task": "index", "peaks": ..., "search": {
#      "prior_cells": [[4.99, 4.99, 17.06, 90, 90, 120]],
#      "prior_spacegroups": ["R -3 c"]}}
```

If the analogue is right, the truth arrives in the *first* streamed
per-system shortlist instead of after the whole sweep; if it is wrong, the
final list is the one you would have had anyway, plus the record that the
prior was tried.

```python
peaks  = rietx.pick_peaks(data, instrument)           # fitted positions + σ
report = rietx.indexing.assess_peak_list(peaks)       # fit to index at all?
if not report.supports_indexing:
    ...                        # abstention. Do not spend a budget (§6)

idx  = rietx.index_pattern(peaks, data=data, instrument=instrument)
cell = idx.best_or_none()
if cell is None:
    ...                        # read confidence_caveats; do NOT take candidates[0]

phase = rietx.indexing.structure_from_candidate(cell)  # dummy atom, lattice group
result = rietx.refine(data, phase, instrument, mode="lebail",
                        plan="profile_only")

screen = rietx.determine_extinction_symbol(data, cell, instrument)
klass  = screen.best_or_none()          # an extinction *class*, never one group
if klass is not None:
    # any member fits the data equally well — that is what the class means
    phase = rietx.indexing.structure_from_candidate(
        cell, space_group=klass.space_groups[0])
```

Five things about that sequence are load-bearing:

1. **Pass the pattern, not only the peaks.** It is what turns whole-profile
   validation on, and validation is what catches the oversized cell no figure of
   merit sees. Without it every candidate caps at `medium` and the *result*
   abstains.
2. **`best_or_none()` returning `None` is the normal first outcome.** With no
   measured systematic shift it is currently unreachable to get `high` on real
   lab data at all — both engines widen their matching window by an *assumed*
   allowance and say so — and the fix is evidence (an internal standard, a
   calibrated `shift_allowance_deg`), not a bigger constant.
3. **Go through `structure_from_candidate`.** It supplies the mandatory dummy
   atom and, more importantly, defaults the space group to the **absence-free
   lattice group**. A plausible-looking space group would hide exactly the
   reflections whose absence is not yet established — which is also why the
   indexing gate's `predicted_but_absent` test must keep running against the
   lattice group even after the screen has named a class.
4. **The extinction screen answers the next question, and answers it as a
   class.** `determine_extinction_symbol` ranks the classes the lattice admits,
   each listing its space groups; the powder observable *is* the extinction
   symbol, so a returned class with three groups in it is a complete answer, not
   a hedge (§7e).
5. **Choosing inside the class is chemistry, not diffraction.** Any member can be
   handed to `structure_from_candidate` for the Le Bail or Rietveld step that
   follows — they predict the same reflections at the same positions. What
   separates them is what you know about the compound, or which one a structure
   solution works in.

The reverse direction closes too. When a refinement's Layer 2 emits
`reindex_or_recheck_cell` — peak offsets beyond the linearisation radius in most
of the misfitting regions, i.e. the cell is wrong (or the calibration grossly
off) rather than slightly off — that action has something to call: pick peaks
and run `index_pattern` on the same data. Since WP-1054 it survives abstention,
which is where it matters most: the wrong-cell state abstains, and before the
fix it surfaced only a confident `add_impurity_phase` built from its own
displaced peaks. The action carries `refine_zero_shift` /
`refine_sample_displacement` in `alternatives` because the validity-radius
signature cannot choose between a wrong cell and a gross calibration error —
re-indexing is still the safe first move, because `index_pattern` searches
under its own shift allowance.

---

### 7e. The extinction screen (`ExtinctionScreen.diagnostics`, and each class's)

These arrive from `rietx.determine_extinction_symbol`, which runs *after* a cell
is in hand and answers the next question — which systematic absences the pattern
shows. Same split as §7c: a refutation lives on the class it refutes.

| Code | What it means you must not do |
|---|---|
| `EXTINCTION_GROUPS_NOT_SEPARABLE` | (info) Pick one of the listed space groups and call it the answer. They produce **identical** powder patterns by construction — a centre of symmetry, an enantiomorph or a mirror leaves no absence — so this is not weak data and not a tie to be broken by counting longer. Carry the list; `structure_from_candidate(cand, space_group=…)` accepts any member. The arbiters are chemistry (a polar or optically active compound cannot be centrosymmetric) and, eventually, which one a structure solution works in |
| `EXTINCTION_SYMBOL_AMBIGUOUS` | Read the ranked first class as the answer. It fires for three different reasons and says which: a runner-up inside the decisive ΔBIC margin, a leading class none of whose absences is **testable** here (each is outside the range, coincides with a line the class still allows, or sits where the class's own fit already puts a neighbour's tail), or classes a `max_classes` cap never fitted. Only the first is fixed by better data at the same setting |
| `EXTINCTION_FORBIDDEN_INTENSITY` | Keep this class. A position it forbids carries intensity its own Le Bail fit cannot account for, and the hkl and 2θ are named so you can look. Two things it is not: a position under a neighbour's tail, which is no longer testable at all (WP-1077), and necessarily a violated absence — one flagged position can be an impurity line, so check it against the indexing result's `unmatched_observed` before concluding. What it *cannot* be excused by is a good ΔBIC: a class asserts absences, so a testable position carrying intensity refutes it however well it scores |
| `EXTINCTION_CONDITIONS_PARTIAL` | (info) Read `conditions` as the complete condition list for this class. The screen used the absence set itself, which is unaffected; only the human-readable reduction is short. Read `space_groups` |
| `EXTINCTION_SCREEN_FAILED` | (error) Read the empty ranking, or any class's absence from it, as evidence about the symmetry. The *reference* Le Bail fit of the absence-free lattice group raised (the message names the exception), so no class was screened at all — `screen.status` is `failed` and there is nothing to rank. This is about the cell, the instrument or the data, never about one class: every class would fail the same way. Validate the cell first (`index_pattern` with `data=`, §7d's sequence) and check the wavelength is not on an absorption edge |

Three things about the screen that change how you use its answer:

1. **The score is a nested comparison, not Rwp.** A class with fewer absences has
   more reflections and can only fit at least as well, so Rwp ranks the
   least-constrained class first every time. `delta_bic` is BIC(class) −
   BIC(absence-free lattice); **negative favours the class**, and the difference
   between two classes' values is itself a ΔBIC. Measured on a synthetic P 2₁/c
   specimen: the true class and its screw-free partner differ by 1e-5 in Rwp and
   by 24 in ΔBIC.
2. **`n_added` counts only *testable* absences**, so a class whose extra absences
   all hide under allowed neighbours earns nothing for them. Read `n_testable`
   beside `n_absent`: if it is zero the class is a hypothesis these data cannot
   address, whatever its Rwp; if it is `None` the class was never fitted, so the
   question was not asked. The third clause of testable — the class's own fit
   must leave the window below the detection threshold — is what stops a
   badly-modelled peak tail refuting a true class, and it is measured: on
   certified corundum, sham positions 1–3 FWHM below an allowed line, carrying no
   reflection at all, clear the same 3σ test on 40–50 % of probes.
3. **The absence-free class winning is a result, not a failure.** On NAC (I 2₁3)
   it is the *correct* answer: I-centring already extinguishes the very
   reflections the 2₁ screws would, so those screws are invisible in principle.
   It is a *wrong* answer when the shared profile fit is bad, and
   `ExtinctionScreen.profile_rwp` is the field that tells the two apart: on
   certified corundum the screen returns the certified `R - c -` at Rwp 0.149 and
   the absence-free `R - - -` at 0.270, from the same cell and the same pattern.
   Give it a range and a width law its profile fit can match before reading a
   refutation.

**`where` now names the paths on every guard code, `HIGH_CORRELATION` included**
(v1.0, WP-1007). It used to be empty on that one — the paths were recovered from
the message by taking its first word, which for a *pair* is not a path at all —
so a consumer had to parse `"a ~ b (ρ=+0.994)"` to learn which two parameters
were degenerate. Read `d.where`; never split the message.

```python
for d in result.diagnostics:
    if d.code == "HIGH_CORRELATION":
        a, b = d.where          # the degenerate pair, as dot-paths
```

And ask the package what it can do rather than assuming: `rietx.capabilities()`
returns the live registries — backends (with whether each optional dependency is
importable *on this machine*), solvers, plan presets with their `when_to_use`
text, modes, anodes, the pattern formats `read_pattern` opens, and the six
versioned contracts (`schema_version`, `report_thresholds_version`,
`event_schema_version`, `project_format_version`, `textdoc_format_version`,
`indexing_thresholds_version`). Its `features` map is derived
from the tree, so `features["indexing"]` tells you whether *this* build has an
indexer instead of leaving you to try one.

Two of those flags are about **speed rather than capability**, and they are the
ones to read before reporting that a refinement is slow.
`features["compiled_kernels"]` says whether the compiled peak kernels can be
built here (`numba` is a required dependency, but an install may legitimately
omit it), and `features["compiled_kernels_active"]` says whether the next
refinement will use them — `RIETX_COMPILED=0` in the environment switches them
off without a reinstall. Both false on a slow fit is an explanation; both true
is not, and the answer is somewhere in the stage plan. Nothing else changes:
the numbers agree to one or two units in the last place either way, and the
accumulation is bit-for-bit identical.

---

### 7f. Two consumers, one answer: the gate and the evidence (WP-1043)

The gate exists for **unattended** use: a machine that cannot weigh evidence
must never be handed one cell confidently, so `best_or_none()` stays as strict
as it is and nothing in this section loosens it. But the gate's three levels
compress the judgement's *inputs*, and a consumer that can reason — an LLM in
a tool loop, or a human at a screen — wants the inputs, not only the verdict.
The design call this section serves: give them all the information, and let
the judge, human or machine, be the judge.

**What a reasoning consumer reads**: `result.evidence()` — the `evidence` arm
of `refine_json`'s answer. Per candidate: every caveat with its
`refuting`/`capping` **kind** (the split `confidence_caveats` alone withholds);
the panel members that ranked, with values, beside `fom_undefined` — the
figures that could not be computed, each *absent with its reason*, never
silently zero; and the whole-profile numbers together — `lebail_rwp` and both
detector counts, surfaced so a reader can see when a detector has failed (as
it measurably does on magnetite's rival, whose fit buys a negative background
— §7c's row), and never a thing to score on. Result-wide: what the search
covered (`systems_searched` + `search_complete`) against what the list
supports (`systems_supported`). The visual check is part of the answer, not
documentation of it: `rietx.viz.plot_indexing(result, peaks, data=...,
instrument=...)` draws the ranked tick rows and the Le Bail panel from the
result alone.

**Worked example — fluorite, why the two reads differ.** Seventeen usable
lines on certified CaF₂ (Fm-3m, a = 5.4631 Å). The unattended read:
`best_or_none()` is `None` — correct, and exactly as strict as ever, because
the `fom_panel_reduced` caveat (capping) holds every below-twenty-line
candidate at `medium`. The reasoning read: the certified cell at rank 1 at
−18 ppm, found by every engine that ran, Le Bail-validated `converged`, four
systems searched to completion, and the *only* caveat on it is the reduced
panel — M₂₀/F₂₀ absent for cause, the coverage and reversed members all
ranked. A consumer that can weigh that is entitled to adopt the cell with its
eyes open; before WP-1043 the same list was refused outright — the old gate
conflated scoring (twenty lines, where M₂₀/F₂₀ are *defined*) with searching
(`MIN_LINES_PER_DOF` per system: seventeen lines are seventeen-fold
over-determined for a cubic metric), and neither consumer got anything.

**Worked example — bethanechol set F, the truth already at rank 1.** On the
one externally graded benchmark, the published P2₁/n cell comes back ranked
**first** on set F (measured 2026-08-06: `trial_error` under the paper's own
manual-mode conditions, −340/+56/+67 ppm with β out by 0.012°) — and the sets
are bare positions, so there is no profile to validate against and a
single-engine find grades `low`: the gate can never promote it. The evidence
view is where that answer *exists* for a consumer — rank 1, its figures, and
caveats that say precisely what was not checked. An unattended pipeline
correctly gets nothing; a reasoner gets the answer with its qualifications
attached.

One qualifier on everything above, and on any scoreboard number you quote:
nine of ten real-data corpus datasets sit at **≤ 2 free metric parameters**
(0 orthorhombic, 1 monoclinic, 0 triclinic), so every measured claim here is
about high-symmetry lattices until the corpus moves — post-v1 by scope call.

---

## 8. Twenty things that will surprise you, all measured

These are the findings from building the package that change how an agent
should behave. Each one cost a debugging pass.

**8.1 A correction that provably cannot improve Rwp can still be essential.**
The capillary absorption factor factors *exactly* into a constant × exp(c·sin²θ)
— a Debye-Waller shape — so applying it to a model with a free scale and free
Biso leaves the residual unchanged to machine precision. Its entire content is
that a Biso refined without it comes back **low by 0.49 Å² at µR = 1** (Cu Kα),
which is comparable to Biso itself and 19σ against its own esd. `result.absorption`
reports the bias because no fit statistic can. **Corollary for the agent: never
judge a correction by Δ Rwp. Ask which physical quantity it unbiases.**

Measured end to end on a real capillary pattern (11-BM, NIST SRM 660a LaB₆ in
the documented 0.81 mm bore, µR = 0.674): Rwp moved 3 × 10⁻⁸, the lattice
parameter 8 × 10⁻¹² Å, and **both** displacement parameters moved by
+0.0166542 Å² against a predicted 0.0166542. That is what "exact" means here.
It is not a general property of absorption corrections — see 8.12.

**8.2 The opposite also happens: an improvement that passes every statistical
test and is still rejected.** On round-robin brucite, adding anisotropic strain
improves Rwp 18.55 → 17.90 % with ΔBIC +488 — and drives σ²(M) negative on 12
of 43 reflections, so the coefficients are unphysical and unquotable. A
statistical test cannot see a violated positivity cone.

**8.3 Judge a correction at the reflections, not on the fitted grid.** The IUCr
round-robin patterns start at 5° 2θ but their first reflections are at 25–32°.
A grid-based fence cheerfully reported a 27 % low-angle intensity depression
that no modelled peak ever experienced. If you are reasoning about where a
correction has leverage, the relevant coordinate is *where the reflections are*.

**8.4 A multiplicative correction is trivially ~0.96 "scale-like".** Any
correction that rescales intensity projects almost entirely onto the scale
column, so a raw R² against a block containing the scale is a constant that
says nothing. Use the **partial** R² with the scale and background projected
out first — `optimize.statistics.block_projection_r2(..., nuisance=...)`. With
that fix the statistic tracks real identifiability (R² 0.06 → 0.95 as the
low-angle reflections leave the fitted range); without it, it saturates and the
guard is blind.

**8.5 Pairwise correlation is the wrong statistic for a block.** With ~100
spline coefficients, each individual |ρ| against a structural parameter stays
around 0.2 while the block collectively absorbs ~46 % of it. Ask "can this
*group*, acting together, imitate that one?" — that is what
`background_absorption` measures.

**8.6 Some parameters are dead at zero and some explode there.** A
softplus-transformed coefficient (extinction, roughness strength) has
dp/du → 0 at the floor, so it will never move: it needs `Stage.seed`. A
Stephens block has Λ ∝ √Σ with *unbounded* slope at Σ = 0, so it needs
`Stage.strain_seed` to start on the isotropic ray instead. These are opposite
pathologies with opposite fixes; the plans already carry both.

**8.7 A default is a decision, in either direction.** Anisotropic ADPs,
Stephens strain, surface roughness and preferred orientation are opt-in per
atom/phase, because each needs a number about *this* specimen that the file
does not carry. Anomalous dispersion is the exception and is **on by default
since v1.0**: it needs only the species and the wavelength, both already in the
model, so declining it is the choice that has to be justified. Turning any of
them on or off changes every number downstream, including published acceptance
values — if you change one, re-measure; do not carry a comparison across the
change. Note the two knock-on effects WP-1001 measured when dispersion went to
the default: on a specimen sitting inside an absorption-edge interval the
lookup **raises** rather than degrading (that is deliberate — a selective
fallback would leave some species corrected and others not, manufacturing
exactly the unequal cross-phase bias the correction exists to remove; decline
the block or supply `overrides`), and light-atom ADPs come back *less precise*
even as they come back *less biased* (rutile U11/U33 separate at 1.9σ with the
block on against 2.2σ without, because f″ raises the heavy atom's share).

**8.8 Never transfer a literature constant without a numerical check across
*all* its arguments.** A published cylinder-absorption coefficient printed as
"−0·0375" is really −0·3750; the error is invisible against a constant-θ slice
of the paper's own table (which constrains only the other two coefficients) and
is 0.082 wrong at µR = 1. What caught it was a quadrature of the exact integral
the fit approximates — which shares no constant with any published fit. The
general rule: **the strongest anchor is the integral a fit approximates, not
another code's transcription of the same fit.** The same applies to Stephens
S_HKL, where codes fold symmetry multiplicities into their templates and print
values differing by small integer factors.

**8.9 An absurd statistic is more often the linear algebra than the physics.**
JᵀJ here is routinely conditioned at ~10²⁰ — that is what the degeneracy table
in §3 *means* numerically. Until 2026-07-28 the covariance was taken with
`np.linalg.pinv`'s general SVD path, which does not know the matrix is
symmetric and returned correlations as large as |ρ| ≈ 1.6 × 10³ (and +2.75 for
`scale ~ axial_sl` on a real fluorite fit). If a reported correlation, esd or
weight-fraction uncertainty is impossible rather than merely surprising, check
the conditioning before you invent a physical story for it — and remember that
the fix is to compute the covariance properly, not to clip the output, because
clipping 2.75 to 1.0 reports a degeneracy the arithmetic invented rather than
the one the data has.

**8.10 Conventions are documented by physics, never by letter.** GSAS and
FullProf swap the X/Y size/strain labels. Most tabulations print the absorption
*correction* A\* = 1/A where this package multiplies by the *transmission*
A ≤ 1 — and both equal 1 at µR = 0, so an identity test cannot tell them apart;
only the direction of the θ-dependence can. The March coefficient r means
opposite habits in reflection and transmission geometry. **Read the docstring,
not the symbol.**

**8.11 The anode is a physics choice, not a number to look up.** All six
`radiation=` presets come from one column of one evaluation (NIST XRTE
SRD 128), and the shipped `CuKa` pair is bit-identical to it — that is what
makes the others trustworthy, so **never substitute a value from elsewhere**;
Bearden's widely-quoted numbers are a different scale, 24–26 ppm away at Mo/Ag.
Three things then follow from *which* anode, all measured:

* The Kα1/Kα2 gap grows from 20 eV at Cu to 173 eV at Ag, so the one-|F|²-per-
  source assumption gets weaker. A census over Z = 3–98 × six anodes refuses 7
  of 576 combinations, and one is a real specimen: **Ru at Ag Kα**, K edge
  22.14 keV, between the lines. The refusal is correct — split the lines into
  separate histograms or supply a measured override.
* What `DISPERSION_NEGLECTED` is warning about is anode-dependent: hematite is
  a `warning` at Co Kα (180 eV under the Fe K edge, f′ = −3.3 e) and an `info`
  at Mo Ka (f′ = +0.3 e). Same specimen, same code, different severity.
* Contamination checks are per anode. An unrecognised wavelength (synchrotron,
  an untabulated anode) yields `contamination == []` — *not checked*, not
  clean. `background.identify_anode(λ)` returns `None` there and is how you
  tell the two apart.

**8.12 "Infinitely thick" is a modelling claim you make by saying nothing.**
Every flat-plate fit in this package — and by default in every Rietveld code —
assumes the specimen is thicker than the beam penetrates. That is exactly right
for a filled well and badly wrong for a thin layer on a zero-background holder,
which is how small, precious or air-sensitive samples are usually mounted. The
error is much larger than the capillary case and has the opposite sign:
`ΔBiso = −1.5 Å² at µt = 0.2` over a Cu Kα range, because a thin specimen runs
out of material exactly where the beam penetrates deepest, and the missing
high-angle intensity reads as thermal motion.

Four consequences for an agent:

* Declare `Geometry.mu_t` (or `thickness_mm`, and let it be estimated) whenever
  the specimen is a thin mount. Silence means thick.
* The "off" value is **µt = ∞, not 0** — the reverse of every other correction
  here. `mu_t = 0` is a specimen of no thickness and is refused for reflection
  geometry rather than being taken as "no correction". Under
  `flat_plate_transmission` it is the other way round: silence means a
  transparent plate, and the sec θ footprint factor applies regardless, because
  it belongs to the tilt rather than to the absorption.
* **The reported ΔBiso is a lower bound here, not the answer.** For the
  capillary it is exact (seven decimals on real data); for a flat plate the
  bias a fit actually absorbs runs 1.06–1.5× larger, tracking
  `absorption.unabsorbed_fraction` — which is on the record for exactly this
  reason. Quote it as "at least this much", with the residue beside it.
* Unlike the capillary case this one **does** move Rwp, because it is not an
  exact reparameterisation (1–40 % of ln A survives a free scale and Biso). So
  8.1's rule inverts: here a *worse* Rwp after declaring a thickness is
  evidence the specimen was not that thin. Measured on round-robin fluorite —
  a thick back-packed mount — declaring µt = 0.5 takes Rwp 0.1793 → 0.1830 and
  drives one Biso onto its bound. That is the correction correctly refusing to
  fit a specimen that is not there.

**8.13 A stage that takes minutes is telling you it is degenerate.** Measured
on three weighed NaCl/Li₂CO₃ mixtures — identical models, identical parameter
counts, same-sized patterns — wall clock ran **39 s, 858 s and 2 838 s**, a 73×
spread with no corresponding difference in the answer, and the pass reported
`status="converged"` either way. Until v1.1 the budget made that spread far
worse than it needed to be: `max_nfev` was `max_iter × n_par`, pricing a
finite-difference Jacobian the package does not build, so at 46 free parameters
a single `max_iter=100` stage could spend **4 600** evaluations before giving
up. It is now `max_iter ×` a small measured constant (the worst
evaluations-per-iteration ratio over 28 real stages is 3.2), so a stalling
stage says so roughly 30× sooner and a converging one is untouched — every
protocol measured stops an order of magnitude inside the cap. That changes when
you hear about it, not what you should do about it. The
stages that stall are the degenerate groups of §3, so the signal is available
*before* you run them: per-phase size/strain freed against a still-free
instrument U,V,W,X,Y (they model one width curve; the package's own
`lab_sample_refine` only frees them against a **frozen** calibrated instrument),
or preferred orientation whose coefficient has reached a bound. **Corollary:
treat elapsed time as a diagnostic. If a stage runs long, do not wait for it —
look at what you freed.**

**8.14 A bound that exists is not a bound that holds.**
`PreferredOrientation.r` is declared `min=0.0` with a softplus transform, the
idiom that is supposed to keep a parameter strictly positive. The softplus
pre-image runs to −∞, so `r` reaches **exactly 0**, and the March-Dollase factor
then evaluates `(1 − c)/r` and returns inf/NaN. Nothing raises: the residual
becomes garbage and the trust region grinds through its whole budget on it (a
3-second stage that had not returned after ten minutes). Bounding `r` to
0.15–6 fixed the stall *and* the fit, Rwp 30.8 % → 13.2 %. **Corollary: for any
parameter whose model divides by it, set a real floor rather than trusting the
transform — and read `RuntimeWarning: divide by zero` as a fit-stopping error,
not noise.**

**8.15 A coverage score cannot tell a mixture from a low-symmetry single phase,
and this project already published that mistake and withdrew it.** Measured on
third-party data with an engine restricted to two metric parameters: it indexed
47–60 % of the lines of *single-phase* orthorhombic and monoclinic patterns,
82–100 % of genuinely tetragonal or hexagonal ones, and 69 % of a real
two-phase mixture. **The bands overlap.** A "this pattern contains at least two
phases" claim built on the 69 % had to be retracted, because the same number is
what a single-phase pattern of symmetry the engine could not reach produces.
`IndexingResult` therefore carries `systems_searched` beside `search_complete`
and reports failure as *"no cell found in the systems searched"*; no diagnostic
code in the indexing vocabulary asserts a phase count at all, and a test pins
that. **Corollary: partial coverage is a statement about your search, not about
the specimen. Widen the systems before you conclude anything about the sample.**

**8.16 An indexer's tolerance is not its precision, and the gap is 11σ on real
data.** The peak list carries a *fitted* σ(2θ) per line — median 0.0056° on the
bundled corundum pattern, whose cell is certified — and that σ is exactly right
for **weighting** and exactly wrong as a **matching window**: the same pattern's
lines sit a median 0.060° from the certified positions, a cos θ specimen
displacement of −0.065°. At 3σ the true cell indexes *zero* lines and both
engines return nothing, on a pattern whose answer is known. That is why every
indexing program in the literature ships a global ~0.03° tolerance, and why the
engines here add an assumed 0.05° in quadrature and say so with
`INDEX_SHIFT_ALLOWANCE`. **Corollary for the agent: a cell found under a widened
window has absorbed the shift (+1400 ppm measured), so re-fit it with
`shift_template` before quoting it — and the way to earn `high` confidence is to
supply a measured `shift_allowance_deg` — the shift's amplitude, not the
residual scatter a template leaves — from an internal standard, not to widen
further.**

**8.17 "Is there intensity here?" is not one question — it depends on what else
your hypothesis predicts nearby.** Two detectors in this package ask it with the
same window (±½ FWHM) and the same threshold (3σ), and they must use different
null models. WP-1024's `predicted_but_absent` asks it against the fitted
**background**, which is right for an oversized cell's phantom reflection because
a phantom sits in a *gap*. WP-1025's extinction screen asks it at a **forbidden**
position, which sits inside a dense predicted pattern — and measured on the FAP
lab pattern, the 003 that P 6₃/m forbids is 0.89 FWHM from an allowed neighbour
ten times stronger whose tail fills the window to **+27.6 σ**. Against the class's
own `y_calc` — background plus every reflection the class still allows — the same
window reads **−3.9 σ**. **Corollary for the agent: never compute your own
"nothing is here" test from the raw pattern minus a background.** Where nothing
else is predicted nearby the two agree; where something is, the raw test refutes
the true answer.

**8.18 A position correction belongs to a geometry, and the suggestion you get
now says which.** `cos θ` is the *flat-plate* specimen-displacement shape, and
`instrument.geometry.sample_displacement` is force-fixed on anything that is not
`bragg_brentano`. A capillary off the centre of the 2θ circle has its own pair
(McCusker eq 4): `instrument.geometry.capillary_offset_along_beam` carries sin 2θ
and `…_across_beam` carries cos 2θ, they exist only on `debye_scherrer`, and both
need `goniometer_radius_mm`, which eq (4) divides by — a value or a `vary` without
one is refused by name rather than defaulted. Free them for a laboratory capillary
or Guinier camera; at a synchrotron with a crystal analyser the paper says the
displacement error is eliminated, and measured on 11-BM NAC the fit agrees, so
freeing them there measures nothing.

The report's position templates and actions are now chosen by geometry, so the
two `refine_sample_*` actions no longer reach a capillary fit at all (before
WP-1073 they did, naming parameters that could not be freed). On
`flat_plate_transmission` they do not reach either (WP-1003): that geometry
models neither aberration, so a `cos_theta` or `sin_2theta` trend there is
reported as a shape with no action — read it as "a flat specimen off the
axis", evidence with no legal one-click repair. **And this is a
correction whose cause the endpoint hides**: measured on a synthetic capillary
with a 0.30/−0.20 mm offset, refusing the pair puts −290 ppm into `a`, and the
converged report names *no* position cause, because the zero shift and the cell
between them imitate most of eq (4). The `zero` stage's own rung names
`refine_capillary_offset_along_beam` at 0.66. **Corollary for the agent: this is
§9's rule with a concrete case — read the trajectory, not the last state.**

**8.19 A restraint's weight is a per-stage decision, and a fit can converge to
an impossible bond without saying so.** `Stage.restraint_weight_scale` is c_w of
McCusker eq (7), S = S_y + c_w·S_G: high while the structure is incomplete or
approximate, reduced as it improves. It defaults to 1.0 (every restraint exactly
as declared), and 0.0 silences the restraints for a stage while keeping their
rows, so the row count the statistics exclude never changes mid-plan.

Measured on a synthetic case whose data under-determines two oxygen sites,
starting from a Zr–O of 3.73 Å for a 1.87 Å bond: the same three stages run at
c_w = 1 throughout converge with that distance at **4.834 Å**, the restraint
148σ in tension and the coordinates 0.425 rms from truth; run at c_w = 300 then
1, the stiff stage lands the bond at 1.866 Å (0.03σ) and the relaxed stage
converges at 1.872 Å, 0.00107 rms. The plans differ in nothing but c_w.

**Corollary for the agent: this is a case where the fit statistics are the
weaker channel and you must read `result.restraints`.** The failed fit's Rwp is
0.0393 against 0.0327 and its GoF 1.23 against 1.02 — a slightly worse fit, not
an announcement of a 4.8 Å bond; `RESTRAINT_TENSION` is what fires. And a stiff
c_w makes a restraint more authoritative, not more correct: where the assumed
coordination is wrong, §8 of the paper says the refinement "will not progress
satisfactorily", and raising c_w makes that worse rather than better.
`RestraintReport.weight_scale` records which value produced a report, so the
penalty actually minimised is `weight_scale · restraint_chi2`.

**8.20 Intermediate stages are not converged, on purpose, and the last one is.**
A staged plan stops every stage but the last at `ftol = 1e-6` rather than the
solver's `1e-9` (`RefinementPlan.intermediate_ftol`, default since 1.1). The
reason is 8.13's mechanism seen from the other side: those long stages are
walking a near-degenerate direction at ≈0.93 per iteration, and 99.99 % of the
cost decrease is banked by evaluation 55 of 93 — the rest is digits the next
stage refines again anyway, because stages are cumulative and the last one
polishes everything at `1e-9`. Measured over the three lab-shaped benchmark
cases: 1.51×, 1.62× and 1.55× fewer evaluations, every non-degenerate parameter
within 0.03 esd of the fully converged plan, QPA within 0.0014 wt %.
**Corollary for the agent, in three parts.** Do not read a small parameter
difference between a 1.0.x number and a 1.1 number as a physics change; check
`StageResult.ftol` first. Set `intermediate_ftol = None` when a number is going
into a paper, or when you are reproducing an earlier release, and say that you
did. And **measure a series rather than assuming it**: the same chained
ten-pattern comparison came out 1.04× *worse* on one tree and 1.12× *better* on
the next, one commit apart, because each pattern warm-starts from its
predecessor and a different seed changes how many recovery rungs the next one
needs (§9b). The per-fit bound above does not survive a chain in either
direction.

---

## 9. The trajectory, and the history DAG as a search structure

### Read the run, not just its last state

**The first thing to do with a fit is read the report at every stage it passed
through, and that costs you one flag.** `task="refine"` returns `trajectory[]`
when the request sets `"report_trajectory": true` — off by default since
WP-1003, because WP-1064 measured that rungs handed over unasked bought no
better decisions at more calls — and in python:

```python
ref.fit(data, plan="mccusker_default", stage_reports=True)
for rung in ref.stage_reports_:
    print(rung.stage, rung.rwp, [(a.kind, a.confidence) for a in rung.actions])
```

Each rung is the same three-layer report, projected (`FitReport.for_stage`) to
the numbers §4 judges a fit on, the summary sentence, and the **active**
suggestions — those the plan you ran will *not* fix, since the strategy veto is
applied against the whole plan. Two properties make it safe to rely on:

- **It changes no number.** The rungs are read off states the plan already
  passes through; a fit run with the trajectory lands bit-for-bit where the
  same fit runs without it (measured: identical Rwp to full float precision on
  the synthetic fixtures, 0.140249 on 11-BM NAC). Nothing is refined to
  produce a rung.
- **It costs ≈2.5–2.8× the fit's wall clock** (1.06 s → 2.70 s on 59.5k
  channels of real 11-BM data; 0.30 s → 0.82 s on the 4200-channel synthetic
  LaB₆ fixture, re-measured 2026-08-19) and single-digit kB of payload: on
  that LaB₆ fixture, 0.6–0.8 kB a rung, 3.5 kB for the whole five-rung
  trajectory, ~3 % of the 111 kB report it ships beside. Quote that share
  with its fixture — the report's size is dominated by its geometry table
  (89 kB of the 111), which no rung carries, so beside a geometry-light
  report the same trajectory reads as ~26 % (the `StageReport` docstring's
  WP-1058-era episode-fixture measurement). The cost is flat *per stage*, not
  per iteration, so on a hard or diverging fit it disappears into the noise.
  Turn it off for a fit you are not going to read.

What to look for, in order:

1. **A rung that names a cause the final report does not.** That is the
   compensation signature of §5: the plan absorbed a real error. The named
   parameter is the hypothesis; `predict_then_verify` below is how you test
   it rather than believing it.
2. **A confidence that climbs across rungs.** On real 11-BM data with an
   unmodelled CaF₂ impurity, `add_impurity_phase` reads 0.3 → 0.6 → 0.9 as the
   host phase fits: a hypothesis getting *stronger* as the model improves is
   about the specimen, not about the starting values.
3. **`abstained_kind` changing.** `immature` early is ordinary. Ending at
   `resolution_limited` is a legitimate stopping point for a phase-ID
   deliverable (§4b) — not a licence to escalate corrections.
4. **`n_actions_vetoed`.** These are the suggestions your own plan already
   answers; a rung whose actions are *all* vetoed is telling you the plan is
   already the right one.

The rungs deliberately carry no regions, curves or per-region attribution: a
rung is a pointer to a state worth asking about, and `ref.report()` (or the
`report` arm) is where you ask. There is **no `task="diagnose"`** and no
declared bootstrap ladder to invoke, because the states are already there —
every preset opens on a background+scale stage, which is that ladder's first
rung (WP-1058). A hand-rolled one-stage plan is the one case with nothing to
report but its end: the turn-on order is what makes a trajectory informative.

### The DAG: branch, verify, roll back

This is the part of the API that exists because the operator might be a search
process rather than a person. Every stage auto-commits an immutable, restorable
node (~10 kB — state, not curves), so branching is cheap and a rejected
experiment leaves no trace in the working state.

The canonical agent loop:

```python
ref = rx.Refinement(structure, instrument, history="session.jsonl")
ref.fit(data, plan="lab_bragg_brentano")
ref.history.tag(ref.history.head, "baseline")

# try a hypothesis on a branch — rollback is structural, not manual
rival = ref.branch("baseline")
rival.run_stage(data, rx.Stage("aniso_strain", ["phases.*.microstrain.dof.*"],
                               strain_seed=1000.0))

ref.history.compare([n.id for n in ref.history.leaves()])
ref.checkout(ref.history.best("rwp").id)
```

and the machine-checked version of "should I take this suggestion?":

```python
outcome = rx.report.predict_then_verify(ref, data, report.suggested_actions[0])
# runs the action on a branch, keeps it only if χ² actually improves by ≥1 %
print(outcome.accepted, outcome.reason, outcome.predicted_delta_chi2,
      outcome.observed_delta_chi2)
```

Note `expected_delta_chi2` on a suggested action is the *linear model's*
prediction — an optimistic upper bound, not a promise. The gap between
predicted and observed is itself information: a large predicted improvement
that does not materialise means the linearisation was invalid there, which is
usually a peak far enough off that it should have been re-detected rather than
shifted.

This loop is executable, not aspirational: `tests/test_report_loop.py` runs it
closed — report → top surviving suggestion → verify → checkout/rollback →
re-report — from eight planted-cause starts and measures planted-parameter
recovery, stopping behaviour and rollback hygiene against the
`mccusker_default` preset (WP-1052).

The same shape answers the other question the report asks and does not
settle — **which of an exchangeable pair is physical** (§4 step 6):

```python
finding = next(e for e in report.identifiability.exchanges if e.exchangeable)
swap = rx.report.compare_rivals(ref, data, finding)   # two branch fits
for r in swap.rivals:                # [0] frees the held one, [1] the partner
    print(r.freed_path, r.chi2, r.rwp, r.freed_value, r.freed_esd, r.n_free)
print(swap.chi2_ratio)               # < 1 ⇒ the parameter the fit HELD wins
```

Three things about it, and each is deliberate. It runs each rival **alone**
with the other held at its **null** — never both together, which is the ridge
(§3), and never with the rival at its last fitted value, which is neither
rival. The free set is otherwise unchanged, so `n_free` matches across the two
and raw χ² is comparable without an information criterion. And there is **no
`decisive` field**: the package states the reading rule and never applies it,
the same fence `predict_then_verify` respects by reporting
`observed_delta_chi2` beside its own threshold. The reading rule is §4 step
6's band, orientation-neutral because `chi2_ratio` is directional: take **the
winning rival**'s side whichever index it is — the losing χ² over the winning
χ², i.e. max(ratio, 1/ratio) — and compare that against
`RIVAL_DECISIVE_MIN_CHI2_RATIO`. At or above it, the winner's fit is the
answer, quoted without caveat (the 0.86 above is 1/0.86 = 1.17, decisive);
below it the pair has tied and the resolution is protocol. A pair with no
null (a cell edge, a scale) is refused by name — that one is resolved by
protocol, not by measurement.

Two properties worth relying on:

- **Node metrics are as-optimised**, measured on a model frozen at the values
  each stage *started* from. `rx.replay(tree, node_id, data)` recompiles at the
  values the stage *ended* on, so the two can differ marginally. That gap is a
  staleness signal, not a bug.
- **Each node carries the API call that produced it**, so a session doubles as
  a reproducible script, and `cherry_pick` replays another node's stage *action*
  (not its values) on top of the current state.

---

## 9b. Series: refine a ramp as a chain, and check it both ways

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

Three things an operator must know, all measured:

- **Chaining is worth ~3x in iterations, not in accuracy.**  On the eight
  round-robin sample-1 mixtures: 2863 iterations unchained, 904 chained, at
  identical Rwp and identical weight fractions.  Use it to make a long series
  affordable, never to make an individual fit better.
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

`carry` (dot-path globs) restricts what crosses a pattern boundary.  Reach for
it when a parameter must provably not be chained; do **not** reach for it
because a parameter jumps.  That hypothesis was tested on a series whose
composition swings 1 → 94 wt % and it is false: carrying everything is cheaper
there than excluding the scales.

---

## 9c. One JSON call from a tool loop

`rietx.agent.refine_json(dict) → dict` wraps the entry points for a
tool-calling agent, and `rietx.agent.tool_definition()` returns a
ready-to-register tool whose schema quotes the backend/solver/plan/**engine**
vocabularies from the live registries.  Five tasks: `"refine"` (one pattern →
`result`, with the FitReport beside it and — requested, see below — the
per-stage `trajectory`), `"refine_multi"` (one joint residual — its
`node_id`/`tree_id` are null **by design**, a joint fit keeps no history DAG,
and it returns **no report either**: reports are per-histogram and python-only
(`result.for_histogram(h)` + `build_report`), so §4's report ladder does not
run on this task — judge a joint fit from `result.statistics` and §7's
diagnostics), `"refine_sequential"` (a warm-started series → `series`
of per-pattern summaries; history ids live per entry, never per run), `"index"`
(a peak list or a pattern → `indexing`, an `IndexingResult`, with the
`evidence` companion riding beside it — §7f's projection for a consumer that
reasons), and `"suggest"` (a model → `suggestion`, one Jacobian evaluation
ranking the held parameters by
predicted Δχ² — no fit, no mutation, safe between fits).

The whole of §9 arrives on one request field — `"report_trajectory": true`,
without which the response's `trajectory` is `[]` (the default is off since
WP-1003; §9 has the measured reason):

```json
{"task": "refine", "structure": {…}, "instrument": {…}, "pattern": {…},
 "report_trajectory": true}
```

```json
{"ok": true,
 "result": {"statistics": {"rwp": 0.0137, …}, …},
 "report":     {"rwp": 0.0137, "suggested_actions": []},
 "trajectory": [
   {"stage": "scale_bkg", "rwp": 0.0575, "n_actions_vetoed": 3,
    "actions": [{"kind": "refine_sample_displacement", "confidence": 0.997,
                 "rationale": "position error follows the cos_theta template
                               (-0.01003 ± 0.00022 deg, R²=1.00, 69% of χ²,
                               8 regions)",
                 "parameter_paths": ["instrument.geometry.sample_displacement"]}]},
   {"stage": "zero",      "rwp": 0.0150, "actions": [],
    "abstained_kind": "unreadable"},
   {"stage": "cell",      "rwp": 0.0137, "actions": []},
   {"stage": "profile_w", "rwp": 0.0137, "actions": []},
   {"stage": "profile",   "rwp": 0.0137, "actions": []}]}
```

That is the shape to expect from a compensated fit: an empty final action list
over a first rung that names the cause — and the `trajectory` above is there
only because the request asked for it.  `include_report: false` outranks
`report_trajectory: true` and declines **both** — a caller who says it does
not want the report is never handed one a rung at a time.

`"index"` answers in its own arm because its answer is a different *shape*: there
is no cell in it.  Read the `evidence` arm first (WP-1043, §7f) — every
candidate with each caveat's refuting/capping kind, the ranked figures beside
the ones absent for cause, and the whole-profile numbers together — then
`indexing.candidates` for the full record; `best_or_none()` is the only
singleton and it is null far more often than not (§7d).  Its `search` object
mirrors the one option surface every engine reads — set `max_volume` and
`n_unindexed` once and every engine means the same thing, which is what makes
their agreement evidence.

The envelope never raises: `{"ok": true, "result"|"series"|"indexing"|"suggestion": …,
"evidence": …, "report": …, "trajectory": […]}`
on success, else `{"ok": false, "error": {code, message, suggestion,
details}}` with `error.code` one of `INVALID_REQUEST` (per-field dot-paths in
`details[]` — the schemas are strict, unknown keys are errors),
`BACKEND_UNAVAILABLE` (a real backend whose optional dependency is not
importable here — checked before dispatch, so nothing ran; the install command
is the suggestion), or `REFINEMENT_FAILED` (the engine's own message,
preserved — the request was valid *and* runnable here, so read the message).  Everything else in this document applies unchanged: the
`result` inside the envelope is the same `RefinementResult`, and §7's
diagnostics are still the first thing to read.

One namespace note: every code in this document is the **engine's** — a
`Diagnostic.code` or one of the three envelope codes above. The GUI server's
session codes (`NOT_FOUND`, `RUN_IN_FLIGHT`, `STALE_REVISION`, …) share the
same UPPER_SNAKE shape but are a separate vocabulary with no rows here, so a
code met outside `result.diagnostics` or the error envelope is the server's,
not the engine's.

---

## 10. A worked default

If you have a lab pattern, a CIF and no other information, this is the sequence
to run and the checks to make. Adapt, do not skip the checks — adaptation is
the literature's own instruction, because the right order depends on the data
and the starting values (Toby, 2024, the "recipe problem").

```python
import rietx as rx

data       = rx.read_pattern("sample.xy")
structure  = rx.Structure.from_cif("phase.cif")
instrument = rx.Instrument.bragg_brentano(radiation="CuKa",
                                          monochromator_two_theta=26.6)
instrument.background = rx.background.auto_background(data)

ref = rx.Refinement(structure, instrument, history="session.jsonl")

# 1. structure-free first: cell + profile without any structural assumption
ref.fit(data, mode="lebail", plan="profile_only")

# 2. Rietveld from the converged cell/profile
result = ref.fit(data, plan="lab_bragg_brentano")

# 3. guards outrank statistics
for d in result.diagnostics:
    print(d.level, d.code, d.where, d.message)

# 4. numbers, not pixels
report = ref.report(plan="lab_bragg_brentano")
if report.abstained_reason:
    print("Layer 1 abstained:", report.abstained_reason)   # fix the fit first
else:
    for r in report.attribution:
        if r.gates_passed:
            print(r.two_theta_lo, r.two_theta_hi,
                  [(c.kind, c.value, c.stderr, c.share) for c in r.coefficients])

# 5. impurities / missing phases
print([u for u in report.unmatched if u.kind == "unmatched_obs"])

# 6. only now, the statistics
print(result.statistics.rwp, result.statistics.gof,
      result.statistics.durbin_watson, result.statistics.esd_inflation)
```

**Stop conditions.** Stop refining when (a) every diagnostic is understood and
either resolved or reported as a caveat, (b) Layer 1 attributes no remaining
region above the significance gate, and (c) adding the next parameter group
fails a ΔBIC test or trips a guard. Do **not** stop merely because Rwp stopped
falling, and do not continue merely because it is still falling. These are the
*structure-grade* conditions — §4b maps the earlier stopping points a declared
phase-ID or QPA deliverable is entitled to.

**What to report.** The refined values with their (inflated) esds, the
diagnostics you could not resolve named as systematics, the protocol you
actually ran (plan, held parameters, excluded ranges, channel count), and the
package version, backend and solver from `result.provenance`. A number without
its protocol is not a measurement.

---

## See also

- [`README.md`](../README.md) — capability table and worked examples
- [`DESIGN.md`](DESIGN.md) — why the FitReport is shaped this way (the
  "Outputs & fit assessment" section is the agent-native design record)
- [`ROADMAP.md`](ROADMAP.md) — what is implemented, what is fenced
- `tests/data/README.md` — provenance and reference values for every dataset
- `rietx compare` — browser UI comparing refinement settings side by side on
  the bundled standards (`src/rietx/viz/compare.py` is its registry, and a
  usable API on its own: `compare.run("zincite", "dispersion")`). Its
  cumulative-Δχ² panel is the machine-readable form of §8.1's rule — it shows
  *where* a correction acted, not just whether Rwp moved

Papers are cited author-year throughout; each citation resolves in the
manual's bibliography (`docs/manual/references.bib`) or carries its journal
reference inline at first mention.
