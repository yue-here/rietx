"""Indexing schemas — the fitted peak list an indexer consumes, and the answer
it is allowed to give.

The contract this module exists to establish is **per-line σ instead of a
global tolerance knob**.  Every indexing program in the literature takes a
single "position tolerance" and applies it to every line; a fitted peak list
carries σ(2θ) per line, propagated into σ(Q), so a strong sharp reflection and
a weak shoulder are weighted by what they actually determine.  That is the same
move the refinement side made with the file's esd column (CLAUDE.md, Weights).

Thresholds are pinned here and versioned by
:data:`INDEXING_THRESHOLDS_VERSION`, following ``report/schemas.py``: an agent
reading a peak list can reproduce the decisions that produced it.

**The answer's shape is a rule, not a convenience** (WP-1024).
:class:`IndexingResult` has no ``.cell`` and no ``.best``; the only way to a
singleton is :meth:`IndexingResult.best_or_none`, gated on
:data:`Confidence` reaching ``"high"``.  The FitReport's
never-a-confident-wrong-singleton rule, one rank up — and here the type enforces
it rather than a docstring asking for it.

**Q, not d, and not 2θ.**  ``Q = 1/d²`` is linear in the reciprocal metric
(:func:`rietx.crystallography.inv_d_squared`), which is what makes cell
refinement a linear least-squares problem downstream, so Q is propagated here
once rather than re-derived by each engine.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from pydantic import Field, field_validator, model_validator

from .common import Base, Diagnostic, Provenance

#: Any change a consumer could observe bumps the last component by one, and
#: the comment says what changed — no classification, no digest (WP-1117).
#: 1.0 (WP-1018): first release of the peak-list contract.
#: 1.1 (WP-1038): ``ShiftScreen.source`` gains ``"reflection_pairs"`` and the
#: screen gains ``allowance_deg`` — a vocabulary member is a contract change even
#: when every prior value still means what it did.
#: 1.2 (WP-1039): the lines a search is *driven* by are now the strongest
#: ``n_search_lines`` rather than the first N in 2θ order
#: 1.3 (WP-1110 item 14): ``PeakFlag`` gains ``no_intensity`` and
#: ``PEAK_UNUSABLE_FLAGS`` gains it too — a component that refined onto its zero
#: intensity bound, which nothing could see before the covariance was
#: equilibrated
#: (:func:`rietx.indexing.engines.search_line_order`).  No field changed and no
#: threshold here moved — this is bumped because ``workflow._spec_notes`` records
#: this string beside the spec as the stamp a run is reproducible from, and two
#: runs with identical spec notes now answer differently.  A position-only list is
#: unaffected: with no measured intensities the rule is exactly the old one.
INDEXING_THRESHOLDS_VERSION = "1.3"

# ----------------------------------------------------------------------
# Detection
# ----------------------------------------------------------------------
#: Net height a candidate must reach, in units of the channel's own σ.  It is
#: **σ-normalised and never relative to the global maximum**: the prototype
#: indexer used ``prominence = net.max()·0.01``, which on a pattern that is one
#: enormous reflection plus a dozen weak lines (measured on
#: ``KD1-2_5_NaCoO2``, tag ``guillemot-study``) suppresses everything but the
#: giant.  A σ-normalised threshold has no coupling between unrelated parts of
#: the pattern.  5.0 matches the existing pattern-diagnostics census.
PEAK_MIN_HEIGHT_SIGMA = 5.0
#: Topographic prominence a candidate must reach, in units of the local σ.
#: Lower than the height floor because prominence is measured against the
#: neighbouring saddle rather than the baseline, and a genuine shoulder on a
#: strong line has small prominence by construction.
PEAK_MIN_PROMINENCE_SIGMA = 3.0
#: Significance a *curvature* (shoulder) seed must reach, in units of the
#: propagated noise of the second-derivative filter.  Higher than the prominence
#: floor for a multiple-comparison reason, not a physical one: the curvature test
#: is applied at every local dip in the pattern, i.e. of order (2θ range)/FWHM ≈
#: several hundred independent trials, so a 3σ per-trial threshold yields about
#: one false shoulder per pattern *by construction* — measured, one at 31.56° on
#: a three-peak synthetic.  At 5σ the expected count is ~1e-4.  A false line is
#: far worse here than a missed shoulder: it is the "confident wrong singleton"
#: the FitReport gates exist to prevent, one rank down.
PEAK_SHOULDER_MIN_SIGMA = 5.0
#: Detection separation floor as a fraction of the *narrowest* predicted FWHM
#: in range.  Deliberately smaller than
#: ``model.forward.PAWLEY_OVERLAP_FWHM_FRAC`` (0.5, the point past which least
#: squares cannot apportion intensity): detection should *offer* a shoulder at
#: 0.3 FWHM as a seed and let grouping plus the ΔBIC test decide whether the
#: component survives, rather than never seeing it.
PEAK_DETECT_SEPARATION_FWHM_FRAC = 0.25
#: A candidate is an **Kα2 alias** — the same reflection's second emission line,
#: not a line of its own — if it sits within this fraction of a FWHM of the
#: Bragg-predicted Kα2 position of a stronger candidate.  Why this filter has to
#: exist: once a doublet resolves (Δ2θ = 2·tanθ·Δλ/λ exceeds half a FWHM) the Kα2
#: maximum is a separate detection, lands in its own group, and — because each
#: group is fitted independently, with its own full doublet — comes back as a
#: real line with real intensity.  Measured on a synthetic Cu Kα pattern: one
#: spurious line per resolved doublet.  Stripping is not the alternative (see
#: :mod:`rietx.indexing.peakfit`); recognising the alias is.
PEAK_ALIAS_TOL_FWHM_FRAC = 0.3
#: Observed height ratio, as multiples of the emission line's own ``weight``,
#: inside which an alias is accepted as such.  Wide on purpose: the ratio equals
#: the weight only for a fully resolved pair, and at partial overlap the apparent
#: height at the Kα2 maximum is inflated by the Kα1 tail.  A *genuine* line that
#: happens to sit at a stronger line's Kα2 position is indistinguishable from an
#: alias in one pattern, so the drop is reported (``PEAK_KALPHA2_ALIAS``) rather
#: than made silently.
PEAK_ALIAS_RATIO_RANGE = (0.25, 4.0)
#: How many of the most prominent detections the width census averages over.
#: **Rank first, then measure** (WP-1028, measured on third-party lab data): a
#: median FWHM over *all* detections above a prominence floor read 0.071° on a
#: noisy 0.01°-step pattern whose real lines are 0.389°, because smoothing
#: ripples survive the floor as weak maxima and drag the median down by a factor
#: of five.  The median of the twelve most prominent detections recovers 0.389°.
PEAK_WIDTH_CENSUS_N = 12

# ----------------------------------------------------------------------
# Per-group profile fitting
# ----------------------------------------------------------------------
#: A component's position is bounded to ±this fraction of its seed FWHM.  The
#: analogue of Layer 1's ``VALIDITY_RADIUS_FWHM = 0.4``, and the reasoning is
#: the same one rank down: a fit that wants to move a component further than
#: half a FWHM is reporting a *detection* failure, not a small offset, and
#: should come back at its bound with a flag rather than converge somewhere
#: unrelated.
PEAK_POSITION_BOUND_FWHM = 0.5
#: Bounds on each fitted **component** FWHM (Γ_G, Γ_L separately), as multiples
#: of the group's seed combined Γ.  The lower one is a *positivity floor*, not a
#: physical constraint, and it is tiny on purpose: a genuinely Lorentzian line
#: has Γ_G → 0 and a genuinely Gaussian one has Γ_L → 0, so a floor at a
#: fraction like 0.2 would forbid both limits.  All it has to do is keep Γ
#: strictly positive, since the profile is (1/Γ)·f(x/Γ) — which is the only thing
#: a softplus reparameterisation was ever buying here, and native trust-region
#: bounds keep the analytic Jacobian in physical units with no chain factor.
PEAK_WIDTH_BOUND_FACTORS = (1e-4, 5.0)
#: Half-width of a group's fitting window, in seed FWHM beyond the outermost
#: seed.  Far narrower than the refinement's area-criterion windows
#: (``forward.WINDOW_AREA_TOL``; up to tens of FWHM at high η), and for
#: a different reason: there the whole pattern is modelled and a truncated tail
#: shows up as missing intensity under its neighbours, whereas here each window
#: is fitted alone against a frozen background, so a wide window only buys more
#: baseline error.  Truncation does not bias the reported area — the profile is
#: unit-area and *not* renormalised over the window — it costs precision on the
#: Lorentzian fraction, which is why the window is not narrower still.
PEAK_WINDOW_FWHM_MULT = 4.0
#: Bounds on the global broadening factor that calibrates the instrument width
#: law to the measured width census.  A factor above 1 is ordinary sample
#: broadening; below 1 means the declared instrument is broader than the data,
#: which is a mis-declared instrument rather than physics — allowed, but not
#: without limit, and the range is what stops a pathological census (all
#: shoulders, or one saturated line) from setting every window.
PEAK_WIDTH_SCALE_BOUNDS = (0.5, 50.0)
#: Re-seeding (adding a component to a group whose residual demands one) is an
#: explicit extra pass, capped at this many.  The component count per group is
#: frozen *before* each fit and never changes inside it: a fitter that adds or
#: drops a component mid-solve has a discontinuous residual, which is the
#: frozen-per-stage invariant (CLAUDE.md) one level down.
PEAK_MAX_RESEED_PASSES = 2
#: ΔBIC an added component must clear to be kept (``report.layer2.delta_bic``,
#: which already charges ``n_added·ln N``).  6.0 rather than 0 is "strong"
#: evidence on the Kass & Raftery (1995) scale: peak fitting is unusually prone
#: to spending a component on noise, and a spurious component does not merely
#: add a line — it displaces the position of the real one it splits.
PEAK_KEEP_COMPONENT_MIN_DELTA_BIC = 6.0
#: |t| of the residual's odd-cubic projection above which a peak is flagged
#: asymmetric-beyond-the-model.  The *odd-cubic* direction, not the odd-linear
#: one, because a free position already absorbs the first odd moment exactly —
#: after fitting, the leading detectable signature of unmodelled axial
#: asymmetry is the next odd term.
PEAK_ASYMMETRY_MIN_SIGMA = 4.0

# ----------------------------------------------------------------------
# List level
# ----------------------------------------------------------------------
#: Usable lines below which the list cannot be **scored** — the bar for the
#: figures of merit only, never for the search (WP-1043).  Twenty is not a round
#: number: de Wolff's M₂₀ and Smith & Snyder's F₂₀ are both defined on the first
#: twenty lines, and Smith's (1977) volume envelope is quoted at N = 20.  It is
#: **not** a precondition for searching — a search needs enough lines to
#: over-determine the metric, which is :data:`MIN_LINES_PER_DOF`'s per-system
#: question (18 lines against cubic's one free parameter is eighteen-fold
#: over-determined).  Conflating the two was measured to refuse a question the
#: package answers perfectly: fluorite's 18 clean lines, which all three engines
#: index at −5 ppm.  Below this bar the panel shrinks by the same members for
#: every candidate (``fom.panel_undefined``), each absent figure is reported
#: with its reason on ``DataQualityReport.fom_undefined``, and the
#: ``fom_panel_reduced`` caveat caps confidence at ``"medium"``.
PEAK_MIN_USABLE_LINES = 20
# ----------------------------------------------------------------------
# Data quality (WP-1019)
# ----------------------------------------------------------------------
#: Metric degrees of freedom of the quadratic form Q(hkl) per crystal system —
#: the number of independent entries of {A..F} in
#: ``Q = Ah² + Bk² + Cl² + Dkl + Ehl + Fhk``.  A search cannot be better
#: determined than this: with fewer *usable* lines than DOF the cell is not
#: over-determined at all, and any figure of merit computed on it is fitting
#: noise exactly.  The names are the seven ``sg.crystal_system_str()`` values
#: ``params.vector`` already ties cells by, so the vocabulary is not new.
METRIC_DOF: dict[str, int] = {
    "cubic": 1, "tetragonal": 2, "hexagonal": 2, "trigonal": 2,
    "orthorhombic": 3, "monoclinic": 4, "triclinic": 6,
}
#: Usable lines per metric degree of freedom below which the data are reported
#: as unable to support a search *in that system*.  Five is not a statistical
#: threshold; it is the smallest ratio at which a wrong cell is unlikely to
#: match every line by accident, and it is what makes the abstention system-
#: dependent: 20 lines is 20× over-determined for cubic and 3.3× for triclinic,
#: which is why "enough lines" is not a single number.
MIN_LINES_PER_DOF = 5.0
#: Median σ(Q)/Q above which the position precision is reported as too poor to
#: separate candidate cells.  Read it as a *resolving power*: at 1e-3 two cells
#: differing by 0.1 % in a lattice parameter are indistinguishable, which is the
#: scale at which derivative-lattice ambiguity (Mighell & Santoro 1975) lives.
MAX_RELATIVE_SIGMA_Q = 1e-3
#: The three physical causes of a systematic 2θ shift, in the *same* names
#: ``report/layer2.py``'s ``_POSITION_ACTIONS`` uses, so one physical cause has
#: one name package-wide.  ``tan_theta`` is deliberately **absent**: a tanθ
#: deviation is a *cell* error, not an instrument shift, and offering it here
#: would let the screen "explain" a shift by changing the very answer indexing
#: is about to produce.  WP-1020 refines the cell and the chosen shift together,
#: where the tanθ direction belongs to the cell by construction.
SHIFT_TEMPLATES: tuple[str, ...] = ("constant", "cos_theta", "sin_2theta")
#: Shift sources a downstream tolerance may **trust** as measured.  Kept separate
#: from ``ShiftScreen.source`` so the label never has to lie: a shift fitted
#: against supplied references and one recovered from harmonic reflection pairs
#: are different measurements with different failure modes — a wrong reference
#: versus accidental agreement — and an agent's next action differs, so they get
#: different names.  Trust is the thing they share, and it lives here.
TRUSTED_SHIFT_SOURCES: frozenset[str] = frozenset({"measured", "reflection_pairs"})

# ----------------------------------------------------------------------
# The reflection-pair shift screen (WP-1038)
# ----------------------------------------------------------------------
#: Largest harmonic order ``m`` a reflection pair may have.  ``m·sin θ ≤ 1``
#: confines the low member of an m = 3 pair below ~39° 2θ and an m = 8 pair below
#: ~14°, so the supply above this is dominated by accidental sine ratios rather
#: than by harmonics of a real plane.
PAIR_MAX_M = 8
#: Implied shift (° 2θ) beyond which a candidate triple is not admitted as a pair.
#: Dong (1999) §3's own window, used there to find 11 pairs in a pattern carrying
#: −0.182°.  It is deliberately *wider* than any shift this package expects to
#: measure: narrowing it would bias the estimate toward zero by truncating the
#: very tail that says the shift is large.
PAIR_WINDOW_DEG = 0.20
#: Half-width (° 2θ) of the window the concentration statistic slides over the
#: implied shifts.  Measured (WP-1038 task 0): real clusters have σ 0.0033-0.0071°
#: across the corpus, so 0.010 holds a real cluster whole while spanning 1/20 of
#: the admission window.
PAIR_CLUSTER_HALF_WIDTH_DEG = 0.010
#: Structureless replicates the concentration is tested against.  200 puts the
#: empirical p floor at 1/201, which is below the bar and cheap: the whole screen
#: costs well under a second on every list in the corpus.
PAIR_NULL_REPLICATES = 200
#: Concentration z below which the pair method declines to report a shift.
#: **Measured, not asserted**: over 3600 null replicates (18 line lists × 200),
#: z ≥ 3.0 fires on 0.83 % and z ≥ 3.5 on 0.03 % — one replicate — while every
#: fitted list in the corpus scores z ≥ 4.2 and every bare position list scores
#: z ≈ 0.  So 4 admits all seven real lists at a measured false-positive rate of
#: 1 in 3600, and the gap on either side of it is wide rather than tuned.
PAIR_MIN_Z = 4.0
#: Empirical p a concentration must also clear, and the **only** gate used when
#: judging a *losing* template.  z and p say the same thing while the null counts
#: are many and spread; they part company when the counts are few and discrete,
#: where the null's own σ can collapse to a fraction of a count and make z an
#: artefact of the draw rather than a measurement.  That is not hypothetical: it
#: let ``sin_2theta`` escape refutation on SRM 660c at k = 3 against a null mean of
#: 1.2, on one rng sequence and not another.  So detection requires **both** bars
#: — z carries the measured false-positive rate, p carries the robustness — and
#: refutation, which lives entirely in the small-count regime, uses p alone.
PAIR_MAX_P = 0.01
#: Pairs that must agree before an amplitude is quoted at all, independent of the
#: null.  Dong (1999) §3: "at least three reflection pairs should be used and the
#: calculated zero shifts ... should be close to one another."
PAIR_MIN_CLUSTERED = 3
#: A template is **refuted** only if its concentration is both insignificant
#: (below :data:`PAIR_MIN_Z`) *and* this far below the winner's.  The second half
#: is what stops a one-pair difference reading as evidence: on zircon
#: ``constant`` reaches k = 7 against ``cos_theta``'s 8, which straddles the z bar
#: and would report the zero-point cause refuted on the strength of a single
#: accidental pair.  Measured across the corpus the real separation is not
#: marginal — ``sin_2theta`` sits at 0.30-0.50 of the winner wherever a shift
#: exists — so a bar at 0.6 refutes transparency everywhere it should and never
#: separates the two collinear templates.
PAIR_REFUTE_K_FRACTION = 0.6
#: Standard errors of the fitted amplitude carried into
#: :attr:`ShiftScreen.allowance_deg` on top of the amplitude itself.  **One
#: formula for both roads** — a shift fitted against supplied references and one
#: recovered from harmonic pairs produce the same kind of number, so they open
#: the same kind of window, and ``lab6_calibrated`` no longer computes it by hand.
#:
#: **The headroom term is the dangerous one, and its size was measured against
#: the answer rather than argued.**  A window must span the shift, because
#: matching happens against uncorrected positions; every degree beyond that is
#: one more coincidence a wrong lattice is allowed to have.  Swept on the two
#: certified datasets (WP-1038): corundum keeps the certified trigonal *R*
#: lattice at σ_sys = 0, 0.05, 0.0639 (its own amplitude) and 0.070, and flips to
#: a wrong **hexagonal P** at 0.0767; SRM 660c keeps cubic *P* at 0.0345 and
#: 0.05, flips to tetragonal *P* at 0.0532, and at 0.060 returns a 35.9 Å³ cell
#: **293 000 ppm** from the certificate *at ``high`` confidence* — the
#: confident-wrong-singleton this package exists to prevent, manufactured by
#: window width alone.  Cost moves the same way: corundum takes 50 s at 0.05 and
#: 169 s at 0.085.
#:
#: So the amplitude is safe and the headroom must be small.  It is scaled by the
#: standard error of the cluster **mean**, not by the pair-to-pair **scatter**:
#: the scatter is dominated by each pair's own σ amplified through
#: :func:`~rietx.indexing.pairs.pair_shift_sensitivity`, and using it put
#: corundum at 0.0767 — past its own breaking point — while the standard error
#: puts it at 0.0681, inside it.
SHIFT_ALLOWANCE_K_ESD = 3.0
#: Smith (1977) volume envelope, ``V ≈ 0.6·d_N³/(1/N − 0.0052)``, evaluated for
#: **triclinic** at N = 20: 13.39·d₂₀³.  Kept as the two published constants
#: rather than the product, because the formula is used at other N.
SMITH_VOLUME_C1, SMITH_VOLUME_C2 = 0.6, 0.0052

# ----------------------------------------------------------------------
# Consensus and the confidence gate (WP-1024)
# ----------------------------------------------------------------------
#: Share of the **whole usable line list** a candidate must index before it can
#: be called ``"high"`` confidence.  Note the denominator: the search is driven
#: by the first :data:`~rietx.indexing.engines.DEFAULT_SEARCH_LINES` lines and
#: may leave ``n_unindexed`` of *those* unexplained, so a cell can pass the
#: search having said nothing at all about lines 21 onwards — the first of the
#: three blind spots Le Bail validation exists for.  This bar is what makes the
#: whole list count.
#:
#: 0.9 rather than a count derived from ``n_unindexed``, and the difference is
#: the point: on a 75-line list ``n_unindexed = 2`` would demand 97 %, which no
#: real pattern with an impurity or an undetected weak line can meet, while on a
#: 20-line list it would demand only 90 % anyway.  A fixed fraction lets a couple
#: of foreign lines through on a long list and still refuses a cell that explains
#: only the low-angle half.
INDEX_MIN_INDEXED_FRACTION = 0.9
#: Confidence in one candidate cell.  Three levels, and the top one is
#: **agreement between independent engines** rather than any statistic: the same
#: device as ``sequential.py``'s ``direction="both"`` and the cross-backend
#: Jacobian matrix.  Two agreeing engines is the ceiling (the whole-profile Monte
#: Carlo is a measured no-go, WP-1023), not a shortfall.
Confidence = Literal["high", "medium", "low"]
#: Closed vocabulary of the reasons a candidate is *not* ``"high"``.  Closed for
#: the same reason ``report/schemas.py``'s ``ActionKind`` is: a consumer branches
#: on these, and a free-text reason cannot be branched on.  The human detail
#: belongs in the accompanying ``INDEX_*`` diagnostic, not here.
#:
#: ``engines_disagree`` — fewer than every engine run found this lattice.
#: ``geometric_ambiguity`` — a distinct lattice fits the positions as well
#: (Mighell & Santoro 1975); the partner carries the reflections that would
#: break the tie.  ``fom_panel_disagrees`` — the panel's members put different
#: candidates first, so at least one blind spot is active.  ``not_validated`` —
#: this candidate has no Le Bail fit behind it, either because no pattern was
#: supplied at all (``IndexingResult.validated`` is then False) or because the
#: run's ceiling expired part-way down the shortlist, which
#: ``INDEX_BUDGET_EXHAUSTED`` counts: the run-level flag and this caveat are
#: therefore not each other's negation.  ``predicted_but_absent`` — the Le Bail fit found reflections where
#: the pattern has no intensity, the classic oversized-cell false positive M₂₀
#: cannot see.  ``indexed_fraction_low`` — below
#: :data:`INDEX_MIN_INDEXED_FRACTION` of the usable lines.  ``search_incomplete``
#: — a budget expired, so a *negative* result elsewhere in the domain means
#: nothing.  ``shift_allowance_assumed`` — the matching window was widened by an
#: *assumed* systematic (``INDEX_SHIFT_ALLOWANCE``), and a cell found inside a
#: widened window absorbs the shift.  ``bravais_ambiguous`` — the lattice
#: symmetry appears only at a loose tolerance, or the two methods disagree.
#: ``volume_unphysical`` — outside the volume the data can support.
#: ``validation_failed`` — the Le Bail fit raised or diverged, which is evidence
#: about the candidate and is kept distinct from ``not_validated`` (no fit was
#: attempted): absence of a test and a failed test are not the same statement.
#: ``fom_panel_reduced`` — the list is below :data:`PEAK_MIN_USABLE_LINES`, so
#: the panel that ranked this candidate lacks the classical figures
#: (``DataQualityReport.fom_undefined`` names them with reasons); the ranking
#: stands, the scoring does not, and ``"high"`` stays exactly as unreachable as
#: the pre-WP-1043 abstention made it — capping, not refuting, because a short
#: list is not evidence *against* a cell.
IndexCaveat = Literal[
    "engines_disagree",
    "geometric_ambiguity",
    "fom_panel_disagrees",
    "fom_panel_reduced",
    "not_validated",
    "validation_failed",
    "predicted_but_absent",
    "indexed_fraction_low",
    "search_incomplete",
    "shift_allowance_assumed",
    "bravais_ambiguous",
    "volume_unphysical",
]
#: Caveats that **refute** a candidate rather than merely qualifying it: each is
#: positive evidence against the cell, or evidence that the data cannot choose,
#: so any one of them puts the candidate at ``"low"``.  The others cap it at
#: ``"medium"``.  The split is the whole content of the gate, so it is one
#: constant read by :func:`rietx.indexing.consensus.confidence_for` rather than
#: a chain of conditions.
INDEX_REFUTING_CAVEATS: frozenset[str] = frozenset({
    "geometric_ambiguity", "fom_panel_disagrees", "predicted_but_absent",
    "indexed_fraction_low", "volume_unphysical", "validation_failed"})

#: σ(2θ) in degrees assumed by :meth:`PeakList.from_positions`, which receives
#: bare positions from a publication or another program.  A typical
#: well-aligned laboratory position precision — but the number is not the point:
#: the point is that it is *assumed*, so every such line carries
#: ``"sigma_assumed"`` and downstream gates must treat the precision as
#: unmeasured rather than quote it.
PEAK_ASSUMED_ESD_DEG = 0.02

#: Flags on a line.  ``ghost_kbeta`` / ``ghost_tungsten`` — a contamination
#: line, flagged and **excluded, never subtracted** (Rachinger stripping
#: redistributes the noise and biases what is left; see
#: :mod:`rietx.indexing.peakfit`).  ``excluded`` — the caller removed it.
#: ``fit_failed`` — the group solve did not converge, so position and σ are the
#: seed, not a measurement.  ``sigma_assumed`` — σ(2θ) was supplied, not fitted.
#: ``unresolved_shoulder`` — a component kept in a group where it never
#: separated from its neighbour by half a FWHM.  ``position_at_bound`` — the fit
#: pushed to :data:`PEAK_POSITION_BOUND_FWHM`, i.e. detection put the seed in
#: the wrong place.  ``asymmetry_unmodelled`` — see
#: :data:`PEAK_ASYMMETRY_MIN_SIGMA`.  ``background_extrapolated`` — the line
#: stands where the background envelope was extrapolated rather than measured
#: (WP-1028 §(i)): its prominence is over a level nobody observed, so it is
#: real intensity that may not be a line.  Report, do not refuse — the
#: consumer that can weigh that should be given the chance — so it is
#: deliberately **not** in :data:`PEAK_UNUSABLE_FLAGS`, and it is a flag of its
#: own rather than a reuse of ``position_at_bound``, which means something
#: else and caught only two of the five cases that motivated this.
#: ``no_intensity`` — the component refined onto its zero intensity bound, so it
#: contributes nothing to the window and its own position stops being
#: identifiable (a peak reaches the data only through ``intensity × profile``).
#: It **is** unusable: unlike the report-do-not-refuse flags above, there is no
#: judgement left for a consumer to make.  It stays in ``peaks`` for the same
#: reason ``not_separable`` does — a report must be able to say why a line went,
#: and a component a *human* placed is theirs to see and remove.
#: ``unnamed_neighbour`` — only :func:`~rietx.indexing.fit_peaks` can raise it
#: (WP-1101): detection saw a component inside this window that the caller's
#: position list did not name, so the fit apportioned that intensity among the
#: named components and biased their positions.  The only other numeric trace
#: is χ²_red.  **Reported, not refused**: naming a subset is a legitimate
#: request — one line of a cluster is all a d-spacing lookup wants — and the
#: esd inflation by √max(χ²_red, 1) already carries the cost.  It is absent
#: from :data:`PEAK_UNUSABLE_FLAGS` for that reason, and it does not move
#: :data:`INDEXING_THRESHOLDS_VERSION`: no ``pick_peaks`` answer changes, and a
#: list that can carry the flag comes from a call that did not exist at 1.3.
PeakFlag = Literal[
    "ghost_kbeta",
    "ghost_tungsten",
    "excluded",
    "fit_failed",
    "sigma_assumed",
    "unresolved_shoulder",
    "position_at_bound",
    "asymmetry_unmodelled",
    "not_separable",
    "background_extrapolated",
    "axial_tail",
    "kalpha2_residual",
    "no_intensity",
    "unnamed_neighbour",
]

#: FWHM multiple within which a weak component may be read as a stronger
#: group-mate's **axial-divergence tail** (WP-1043, acting on WP-1028's
#: census).  3.5 spans the measured census — the farthest SRM 660c tail sits
#: 2.99 fitted FWHM out — with margin.  This is nevertheless not the distance
#: knob the census ruled out (widening ``PEAK_SATELLITE_NEAR_FWHM`` reaches
#: four of six): the screen is **one-sided**, requiring the offset's sign to
#: match the aberration's 90° flip — tails point to low 2θ below 90° and to
#: high 2θ above it, and nothing else in a powder pattern flips there — which
#: is a physics signature ``PEAK_SATELLITE_NEAR_FWHM`` could never express.
#: Both flags this screen family writes are deliberately absent from
#: :data:`PEAK_UNUSABLE_FLAGS`: measured across the six real lab patterns the
#: screens hit 11 further usable components nobody has verified, so refusing
#: them blind risks losing real lines — the flag reports the evidence and the
#: consumer judges, the same rule as ``background_extrapolated`` and the
#: WP-1043 gate itself.
PEAK_AXIAL_TAIL_MAX_FWHM = 3.5

#: Flags that take a line out of :meth:`PeakList.usable`.  ``sigma_assumed``
#: and ``unresolved_shoulder`` are deliberately absent: those lines are still
#: evidence, just less precise evidence, and their σ already says so.  Dropping
#: them would discard the input the bethanechol benchmark arrives as.
#:
#: ``not_separable`` **is** here, and it is the one flag that marks a component
#: the fitter believes in as a *shape* and disbelieves as a *line* — see
#: :data:`PEAK_SEPARABLE_MAX_CHI2`.  It stays in ``peaks`` (a report must be able
#: to say why a line went, and the component genuinely improves the group's fit,
#: so removing it from the *model* would bias the position of the line it sits
#: on) while never being offered as evidence of a lattice.
PEAK_UNUSABLE_FLAGS: frozenset[str] = frozenset(
    {"ghost_kbeta", "ghost_tungsten", "excluded", "fit_failed", "not_separable",
     "no_intensity"})

#: Standard deviations above χ²_red = 1 at which a group's fit is **refuted**, and
#: therefore above which a ΔBIC verdict on adding one more component to it cannot
#: be read as evidence of a line.
#:
#: Not a flat χ²_red bar, because the groups differ in size by 5× across one
#: pattern and χ²_red's own scatter is ν-dependent: for ν degrees of freedom
#: σ(χ²_red) = √(2/ν), so the bar is ``1 + 3·√(2/ν)`` — 1.48 on an 83-point
#: window, 1.27 on a 300-point one.  Three σ, the same 99.7 % convention
#: :data:`~rietx.indexing.fom.MATCH_SIGMA` uses on positions, so one number
#: means one thing across the package.
#:
#: This is the constant that closes WP-1026's real-data obstruction, and the
#: reason it is needed is a limit of ΔBIC rather than a bad threshold in it.
#: :data:`PEAK_KEEP_COMPONENT_MIN_DELTA_BIC` asks "does the data prefer n+1
#: components to n?", which is only the same question as "is there a line here?"
#: when the n-component model is *capable of fitting*.  Measured on the bundled
#: qarr corundum pattern (Cu Kα, lab Bragg-Brentano): the strong 104 line at
#: 35.09° fits with χ²_red = **17.4** at n = 1 and **4.6** at n = 2, so both
#: models are refuted, the ΔBIC gain is enormous, and the component bought sits
#: 0.17° (≈ 1 FWHM) below the real line at 10 % of its area — carrying a small
#: esd, so it reads downstream as a well-measured line.  Detection never proposed
#: it: ``detect_peaks`` returned 41 groups with **one seed each**, and the fitter
#: returned 63 components.
#:
#: **The consequence was total, not marginal.**  With those satellites in the
#: list neither engine could index a pattern whose cell is certified; with them
#: out, both do (a = 4.7583/4.7626 Å against the certified 4.759355).  That is
#: also why the earlier diagnosis of the same failure — that the matching
#: tolerance was too tight — was wrong; see
#: :data:`rietx.indexing.engines.DEFAULT_UNKNOWN_SHIFT_DEG`.
#:
#: **It is a "the model is refuted" bar, not a goodness bar**, and its failure
#: mode is stated rather than eliminated: on a *well*-fitted group a weak close
#: neighbour is kept, and on a badly-fitted one a genuine weak neighbour is
#: demoted to ``not_separable``.  The second is the deliberate direction — a line
#: the fitter cannot separate from its neighbour's shape is not evidence, and the
#: flag says exactly that rather than deleting the component.
PEAK_REFUTED_SIGMA = 3.0
#: Distance, in the group's fitted FWHM, within which a component lies *inside* a
#: neighbour's own profile rather than beside it.  Paired with
#: :data:`PEAK_SATELLITE_MAX_RATIO`: both must hold, plus the component must have
#: come from a re-seed pass rather than from a detected maximum.
PEAK_SATELLITE_NEAR_FWHM = 1.5
#: Area ratio below which a component is a *satellite* of a group-mate — small
#: enough that the stronger line's shape error can account for it.  Measured
#: satellite ratios on the qarr lab patterns are 0.08-0.14.
PEAK_SATELLITE_MAX_RATIO = 0.25


def q_of_two_theta(two_theta_deg: np.ndarray, wavelength: float) -> np.ndarray:
    """Q = 1/d² = 4·sin²θ/λ² (Å⁻²) from 2θ in degrees."""
    tt = np.asarray(two_theta_deg, dtype=np.float64)
    return 4.0 * np.sin(np.radians(0.5 * tt)) ** 2 / wavelength ** 2


def q_esd_of_two_theta(two_theta_deg: np.ndarray, two_theta_esd: np.ndarray,
                       wavelength: float) -> np.ndarray:
    """σ(Q) from σ(2θ), by the exact derivative of :func:`q_of_two_theta`.

        dQ/d(2θ°) = (π/90)·sin(2θ)/λ²

    Note the constant: differentiating 4sin²θ/λ² with respect to 2θ *in degrees*
    gives 2·(π/180)·sin(2θ)/λ², i.e. π/90 — half of it is the θ = (2θ)/2 chain
    and the other half is the degree conversion, and it is easy to apply only
    one of the two.  Checked against a central difference in
    ``tests/test_peak_picking.py``.
    """
    tt = np.asarray(two_theta_deg, dtype=np.float64)
    esd = np.asarray(two_theta_esd, dtype=np.float64)
    return (np.pi / 90.0) * np.abs(np.sin(np.radians(tt))) / wavelength ** 2 * esd


class ObservedPeak(Base):
    """One measured line: a fitted position with its esd, width, shape, area.

    ``q``/``q_esd`` are derived from ``two_theta`` and the owning
    :class:`PeakList`'s wavelength; the list validates that they agree, so a
    consumer may use either without checking which is authoritative.

    ``fwhm`` and ``eta`` are the *group's* shared shape, not per-component
    values: within a group (a fraction of a degree) the widths are not
    separately identifiable, and pretending otherwise is what lets a doublet fit
    absorb an unresolved neighbour.
    """

    two_theta: float               # ° 2θ of the **Kα1** (primary-line) component
    two_theta_esd: float           # ° 2θ, carrying the √max(χ²_red,1) inflation
    intensity: float               # integrated area of the primary line
    intensity_esd: float
    q: float                       # Å⁻², = 1/d²
    q_esd: float
    fwhm: float                    # ° 2θ, the group's combined Γ
    eta: float                     # pseudo-Voigt mixing (0 = Gaussian)
    group: int                     # index of the fitted group this came from
    n_in_group: int                # components fitted simultaneously with it
    chi2_red: float                # reduced χ² of that group's fit
    flags: list[PeakFlag] = Field(default_factory=list)
    #: Provenance, not a judgement: ``"fitted"`` — detection proposed it;
    #: ``"manual"`` — a human placed it (its position was still *fitted*, but a
    #: human decided a line exists here); ``"edited"`` — a human moved a fitted
    #: line and its group was refitted.  A reader weighs these differently
    #: (WP-1027's panel shows which is which); no gate in this package branches
    #: on it, because a human's decision is input, not evidence to discount.
    origin: Literal["fitted", "manual", "edited"] = "fitted"

    @property
    def d(self) -> float:
        """d-spacing (Å)."""
        return float(self.q ** -0.5)

    @property
    def usable(self) -> bool:
        return not (set(self.flags) & PEAK_UNUSABLE_FLAGS)


class PeakList(Base):
    """Every resolvable line in one pattern, with per-line σ.

    ``source`` distinguishes a list this package *measured* from one it was
    *handed*: ``"fitted"`` means every σ came out of a profile fit,
    ``"positions"`` means positions were supplied and σ was assumed (see
    :data:`PEAK_ASSUMED_ESD_DEG`).  Downstream gates read it rather than
    inferring precision from the numbers.
    """

    peaks: list[ObservedPeak]
    wavelength: float                        # primary emission line, Å
    two_theta_min: float
    two_theta_max: float
    source: Literal["fitted", "positions"] = "fitted"
    thresholds_version: str = INDEXING_THRESHOLDS_VERSION
    diagnostics: list[Diagnostic] = Field(default_factory=list)

    @model_validator(mode="after")
    def _q_matches_two_theta(self) -> "PeakList":
        """Q is derived, so it cannot be allowed to drift from 2θ.

        Cheap (one vectorised pass) and it makes the derived field
        self-guarding: a caller that builds a peak by hand and forgets Q gets an
        error here rather than a silently mis-indexed pattern later.
        """
        if not self.peaks:
            return self
        tt = np.array([p.two_theta for p in self.peaks])
        want = q_of_two_theta(tt, self.wavelength)
        got = np.array([p.q for p in self.peaks])
        bad = np.abs(got - want) > 1e-9 * np.maximum(np.abs(want), 1.0)
        if bad.any():
            k = int(np.flatnonzero(bad)[0])
            raise ValueError(
                f"peak {k} at 2θ = {tt[k]:.4f}° carries q = {float(got[k])!r} "
                f"but 1/d² at λ = {self.wavelength} Å is {float(want[k])!r}; "
                "build peaks with PeakList.from_positions or "
                "indexing.pick_peaks rather than setting q by hand")
        return self

    def usable(self) -> list[ObservedPeak]:
        """Lines fit to index: ghosts, failed fits and caller exclusions out.

        Every screen and every engine runs on this, not on ``peaks`` — the
        excluded lines are kept in the list so a report can say *why* a line was
        dropped, which a filtered-at-source list cannot.
        """
        return [p for p in self.peaks if p.usable]

    def two_theta(self) -> np.ndarray:
        return np.array([p.two_theta for p in self.usable()], dtype=np.float64)

    def two_theta_esd(self) -> np.ndarray:
        return np.array([p.two_theta_esd for p in self.usable()], dtype=np.float64)

    def q(self) -> np.ndarray:
        return np.array([p.q for p in self.usable()], dtype=np.float64)

    def q_esd(self) -> np.ndarray:
        return np.array([p.q_esd for p in self.usable()], dtype=np.float64)

    def intensity(self) -> np.ndarray:
        return np.array([p.intensity for p in self.usable()], dtype=np.float64)

    @classmethod
    def from_positions(cls, two_theta: np.ndarray, wavelength: float, *,
                       intensity: np.ndarray | None = None,
                       two_theta_esd: float | np.ndarray = PEAK_ASSUMED_ESD_DEG,
                       fwhm: float = 0.1,
                       ) -> "PeakList":
        """A peak list from bare positions — a publication, or another program.

        Every line is flagged ``"sigma_assumed"`` and ``source`` is
        ``"positions"``, because an assumed σ is *unmeasured*: it must not be
        quoted as a precision, and a gate that weights lines by 1/σ² is being
        handed a constant rather than information.  Intensities default to equal
        weight, which is what a position-only list actually says.
        """
        tt = np.asarray(two_theta, dtype=np.float64)
        if tt.ndim != 1 or not len(tt):
            raise ValueError("two_theta must be a non-empty 1-D array")
        esd = np.broadcast_to(np.asarray(two_theta_esd, dtype=np.float64), tt.shape)
        inten = (np.ones_like(tt) if intensity is None
                 else np.asarray(intensity, dtype=np.float64))
        q = q_of_two_theta(tt, wavelength)
        q_esd = q_esd_of_two_theta(tt, esd, wavelength)
        order = np.argsort(tt)
        peaks = [
            ObservedPeak(
                two_theta=float(tt[i]), two_theta_esd=float(esd[i]),
                intensity=float(inten[i]), intensity_esd=float("inf"),
                q=float(q[i]), q_esd=float(q_esd[i]),
                fwhm=fwhm, eta=0.5, group=int(k), n_in_group=1,
                chi2_red=float("nan"), flags=["sigma_assumed"])
            for k, i in enumerate(order)
        ]
        return cls(peaks=peaks, wavelength=wavelength,
                   two_theta_min=float(tt.min()), two_theta_max=float(tt.max()),
                   source="positions")


class FigureOfMerit(Base):
    """One figure of merit, and **what it cannot see**.

    ``blind_spot`` is not documentation, it is a field: the panel exists because
    every published figure of merit has a failure mode, and a consumer that reads
    a value without its blind spot is one step from the confident wrong singleton
    the FitReport gates exist to prevent.  ``k_sigma`` records the matching window
    the value was computed at, in units of each line's own σ — so a number is
    reproducible from the peak list that produced it.
    """

    name: str
    value: float
    n_lines: int
    n_possible: int
    k_sigma: float
    #: mean |Δ| of the matched lines, in the FoM's own units (Å⁻² for M₂₀, ° for
    #: F_N); −1 when nothing matched, which is *not* zero discrepancy
    mean_discrepancy: float = -1.0
    blind_spot: str = ""


class AmbiguityPartner(Base):
    """A distinct lattice whose calculated line *positions* match this one's.

    Mighell & Santoro (1975): a powder pattern carries only the **length** of the
    reciprocal vector, so distinct lattices can be indistinguishable in it.  This
    is reported, never resolved — and ``discriminating_reflections`` is what makes
    it actionable rather than merely honest: the hkl that would break the tie, with
    the 2θ where a line would have to appear (or be absent) to do so.  The
    structural twin of Layer 2's "extend the fit range".
    """

    cell: tuple[float, float, float, float, float, float]
    #: integer transformation from this candidate's basis to the partner's
    transformation: list[list[int]]
    index: int                      # |det| of the transformation
    system: str
    volume: float
    #: hkl of the partner (or of this cell) whose position differs, and where
    discriminating_reflections: list[tuple[int, int, int]] = Field(
        default_factory=list)
    discriminating_two_theta: list[float] = Field(default_factory=list)


class BravaisOpinion(Base):
    """What gemmi and spglib each say about a candidate's lattice symmetry.

    The serialisable face of :class:`rietx.indexing.reduce.BravaisScreen`, and
    it keeps the two opinions **apart** on purpose: gemmi's tolerance is a Le Page
    obliquity in *degrees* and spglib's is a ``symprec`` in *Å*, so a
    disagreement between them is information about the cell rather than a bug in
    either — it is what genuine pseudosymmetry looks like.  ``system`` is the
    symmetry that survives the whole tolerance sweep; ``system_loosest`` is the
    highest any tolerance reported, and the two differing is
    ``INDEX_BRAVAIS_AMBIGUOUS``.
    """

    system: str
    system_loosest: str
    system_gemmi: str
    system_spglib: str
    ambiguous: bool = False
    methods_disagree: bool = False
    #: the Niggli-reduced cell the screen was run on, so a consumer can see which
    #: setting the symbols refer to
    reduced_cell: tuple[float, float, float, float, float, float] = (0.0,) * 6


class LeBailValidation(Base):
    """A candidate cell tested against the **whole pattern** by a Le Bail fit.

    Why this is mandatory rather than optional: the figure-of-merit panel is
    computed on ≤20 lines and is structurally blind to three things the whole
    profile sees — lines beyond the panel, reflections *predicted where there is
    no intensity*, and impurity content.  The middle one is the classic
    doubled-cell false positive and M₂₀ cannot see it at all (Oishi-Tomiyasu
    2013): its ``N_poss`` denominator penalises an oversized cell only weakly.
    Layer 0's strong-negative-residual detector sees it directly, and
    :attr:`predicted_but_absent` is that count.

    ``rwp`` is the figure the literature calls **lebail_rwp**.  It is
    deliberately *not* a member of the ranking panel: the panel ranks every
    candidate and this costs a refinement, so it is computed for the shortlist
    only and used to *validate* rather than to order.  Reading it as a rank would
    also reintroduce the blind spot it exists to close — a bigger cell fits
    better.

    The fit is **single-phase**, and that is a measured constraint rather than a
    simplification (WP-1028): ``CompiledModel.lebail_update`` partitions
    ``max(y_obs − y_bkg, 0)`` per phase with nothing to arbitrate two phases
    claiming the same channel, so two phases inflate one another without bound
    (measured Rwp 742–9 281 % against 7.5–24.8 % for one).  A candidate is
    therefore never validated against a multi-phase hypothesis.
    """

    rwp: float
    gof: float
    #: the **absence-free lattice** group the fit used — not a space group, which
    #: is not known yet (WP-1025).  An absence-carrying group would hide exactly
    #: the reflections whose absence is not yet established.
    space_group: str
    n_reflections: int
    #: reflections the lattice predicts where the pattern has no intensity, from
    #: Layer 0's ``unmatched_calc``
    predicted_but_absent: int = 0
    #: observed peaks with no calculated reflection nearby — impurity content, or
    #: a wrong cell.  Layer 0's ``unmatched_obs``
    unmatched_observed: int = 0
    #: ° 2θ of each, so the report is actionable rather than a count
    predicted_but_absent_two_theta: list[float] = Field(default_factory=list)
    unmatched_observed_two_theta: list[float] = Field(default_factory=list)
    #: the underlying refinement's status; ``"failed"`` when the Le Bail fit
    #: raised, which is itself evidence against the candidate but is reported as
    #: a failure rather than converted into a score
    status: str = "converged"
    n_stages: int = 0
    diagnostics: list[Diagnostic] = Field(default_factory=list)


class CellCandidate(Base):
    """One candidate lattice, with everything needed to rank or reject it.

    Deliberately *not* named "solution" and deliberately carrying no "is correct"
    field.  ``found_by`` is the engines that produced it — agreement between
    independent engines is the confidence, the same device as the cross-backend
    Jacobian matrix and ``direction="both"`` — and ``ambiguity`` is populated
    whenever a geometrically indistinguishable partner exists.
    """

    cell: tuple[float, float, float, float, float, float]
    cell_esd: tuple[float, float, float, float, float, float]
    system: str
    centring: str = "P"
    #: absence-free space-group symbol of the *lattice* (holohedry + centring) —
    #: what the FoM denominators count, and the starting point for WP-1025's
    #: extinction-symbol screen.  Not a space group: that is not known yet.
    lattice_group: str = ""
    volume: float = 0.0
    volume_esd: float = 0.0
    #: (A..F), the quadratic-form parameters actually fitted
    af: tuple[float, float, float, float, float, float] = (0.0,) * 6
    n_indexed: int = 0
    n_lines: int = 0
    chi2_red: float = 0.0
    shift_template: str | None = None
    shift_coefficient: float = 0.0
    shift_esd: float = 0.0
    fom: list[FigureOfMerit] = Field(default_factory=list)
    found_by: list[str] = Field(default_factory=list)
    ambiguity: list[AmbiguityPartner] = Field(default_factory=list)
    #: the two independent opinions on the lattice symmetry (WP-1020's screen)
    bravais: BravaisOpinion | None = None
    #: the whole-profile test; ``None`` means no pattern was supplied, which caps
    #: every candidate at ``"medium"`` rather than being silently ignored
    lebail: LeBailValidation | None = None
    #: filled by the consensus gate.  Still deliberately **not** an "is correct"
    #: field: ``"high"`` means the engines agreed and nothing refuted it, which is
    #: a statement about the evidence and not about the crystal.
    confidence: Confidence = "low"
    #: every reason this candidate is not ``"high"``, from the closed
    #: :data:`IndexCaveat` vocabulary
    confidence_caveats: list[IndexCaveat] = Field(default_factory=list)
    diagnostics: list[Diagnostic] = Field(default_factory=list)

    def fom_value(self, name: str) -> float | None:
        """One panel member by name, or None — never a KeyError, because which
        members exist depends on what could be computed."""
        for f in self.fom:
            if f.name == name:
                return f.value
        return None


class ShiftTemplateFit(Base):
    """One systematic-shift template fitted **alone** to the deviations.

    ``coefficient`` is in degrees 2θ and means the template's own amplitude:
    δ(θ) = z (``constant``), s·cos θ (``cos_theta``), t·sin 2θ
    (``sin_2theta``).  ``residual_ss`` is the weighted residual sum of squares,
    which is what the separability ratio is computed on — not R², because every
    template scores R² ≈ 0.99 against a clean trend
    (``report/schemas.py``'s ``SEPARABILITY_MIN_SS_RATIO``).
    """

    name: str
    coefficient: float
    stderr: float
    r2: float
    residual_ss: float


class ReflectionPairScreen(Base):
    """Evidence behind a shift measured from harmonic reflection pairs.

    Reported in full rather than summarised because the method's failure mode is
    *accidental agreement*, and the only way a reader can judge that is to see how
    much agreement there was against how much a structureless list of the same
    size produces.  ``z`` is that comparison; everything else is what it was
    computed from.
    """

    #: pairs admitted inside :data:`PAIR_WINDOW_DEG`, of the candidate triples
    #: (any line pair whose sine ratio rounds to an integer 2 ≤ m ≤
    #: :data:`PAIR_MAX_M`) that were examined
    n_pairs: int
    n_candidate_triples: int
    #: pairs inside the densest ±:data:`PAIR_CLUSTER_HALF_WIDTH_DEG` window — the
    #: statistic, and the members the amplitude is averaged over
    n_clustered: int
    #: the same statistic on ``null_replicates`` structureless line lists drawn
    #: uniformly in sin²θ over the same range, and the standardised gap
    null_k_mean: float
    null_k_std: float
    z: float
    p_value: float
    null_replicates: int
    seed: int
    #: scatter (° 2θ) of the clustered pairs about the reported amplitude
    scatter_deg: float
    #: templates the pair evidence **refutes** — those whose own concentration is
    #: not significant.  The method may refute (``sin_2theta`` collapses from
    #: k = 10 to 3 on corundum) and may **not** choose between ``constant`` and
    #: ``cos_theta``, which tie to within one pair on every dataset measured.
    refuted_templates: list[str] = Field(default_factory=list)
    #: why no shift was reported, when none was
    declined_reason: str | None = None


class ShiftScreen(Base):
    """Which physical cause a systematic 2θ shift has — or that it has no
    nameable one over the range measured.

    ``best`` always names the template that fits best; ``separable`` says
    whether that name means anything.  The asymmetry is the point: when the
    templates are collinear over the sampled angles the *magnitude* is still
    well determined (all three remove the same amount at those angles, so a cell
    refined against any of them lands in the same place) while the *cause* is
    not, and reporting the cause anyway is the confident-wrong-singleton failure
    one rank up from the FitReport's.
    """

    n_lines: int
    templates: list[ShiftTemplateFit] = Field(default_factory=list)
    best: str | None = None
    separable: bool = False
    separability_ratio: float = 0.0
    max_collinearity: float = 0.0
    #: residual scatter (°2θ) after removing the best template — the σ_sys floor
    #: WP-1020's tolerance model adds in quadrature to each line's own σ
    sigma_sys_deg: float = 0.0
    #: largest disagreement (°2θ), over the angles actually sampled, between the
    #: corrections the **competitive** templates predict — competitive meaning
    #: within ``SEPARABILITY_MIN_SS_RATIO`` of the best residual sum of squares.
    #: It is the cost of choosing the wrong cause, reported rather than argued,
    #: and the qualifier is load-bearing.  Measured (WP-1019) on a 0.10° cos θ
    #: displacement sampled over 10-25° 2θ, where the screen correctly refuses to
    #: name a cause: over **all three** templates the predictions differ by
    #: 0.046°, nearly half the shift — but ``sin_2theta`` is not competitive
    #: there (it fits worse by more than the ratio bar), and over the two that
    #: are, the spread is **0.0011°**, about 1 % of the shift.  So the plan's
    #: conclusion holds — the *cell* stands while the *cause* does not — but only
    #: with "competitive" in it: a template the data rejects is not a candidate
    #: cause, and averaging it in overstates the risk forty-fold.  Read this field
    #: rather than inferring the risk from ``separable``.
    prediction_spread_deg: float = 0.0
    #: **What a search window must span** (° 2θ), which is *not* ``sigma_sys_deg``
    #: and the difference is the whole reason this field exists.  ``sigma_sys_deg``
    #: is the scatter the winning template *leaves*; the window has to span the
    #: shift's own **amplitude**, because a candidate's positions are matched
    #: against uncorrected lines — ``refine_with_shift`` fits the template only
    #: after a candidate survives.  Measured on SRM 660c the two are 0.0078° and
    #: 0.037°, a factor 4.3, and declaring the smaller one makes the search find
    #: **nothing** while declaring the larger one recovers the certificate.  The
    #: cluster scatter is carried in quadrature so a list whose shift is
    #: consistent with zero (11-BM NAC: 0.0003°) still opens a window wide enough
    #: for the precision behind that zero.
    allowance_deg: float = 0.0
    #: ``"measured"`` when reference positions were supplied and the templates
    #: were fitted; ``"reflection_pairs"`` when
    #: :mod:`rietx.indexing.pairs` recovered it from harmonic pairs with no
    #: reference at all; ``"unavailable"`` when neither was possible — see
    #: :func:`rietx.indexing.quality.assess_peak_list`.  Which of the first two
    #: produced a number matters because their failure modes differ (a wrong
    #: reference versus accidental agreement); what they share is trust, and that
    #: is :data:`TRUSTED_SHIFT_SOURCES` rather than a widened label.
    source: Literal["measured", "reflection_pairs", "unavailable"] = "unavailable"
    #: the pair screen's own evidence, when ``source == "reflection_pairs"``
    pairs: "ReflectionPairScreen | None" = None


class DataQualityReport(Base):
    """Is this peak list fit to index, and what does it already say?

    ``supports_indexing`` answers "can this list be **searched**" — the
    per-system :data:`MIN_LINES_PER_DOF` question plus the precision floor —
    and is read by ``index_pattern`` before any budget is spent.  **Abstention
    is a result**: a list that cannot support a search in any system comes back
    with ``supports_indexing = False`` and a reason, never as an exception and
    never as a ranked list of cells with nothing behind it.  "Can it be
    **scored**" is a separate, weaker precondition (WP-1043): a list short of
    :data:`PEAK_MIN_USABLE_LINES` is still searched over
    ``systems_supported``, with the undefined figures named in
    ``fom_undefined`` and confidence capped by the ``fom_panel_reduced``
    caveat.

    Every threshold this verdict rests on is a module constant in
    ``schemas/indexing.py`` with its reasoning, and ``thresholds_version``
    records which set produced it.
    """

    n_usable: int
    n_total: int
    two_theta_min: float
    two_theta_max: float
    source: Literal["fitted", "positions"]
    #: median and worst σ(2θ) over the usable lines, ° 2θ
    sigma_two_theta_median: float
    sigma_two_theta_worst: float
    #: median σ(Q)/Q — a dimensionless resolving power, see
    #: :data:`MAX_RELATIVE_SIGMA_Q`
    relative_sigma_q_median: float
    #: median σ(Q) over the mean spacing between neighbouring Q values.  Above
    #: ~1 the lines are not individually resolved in Q and no tolerance can
    #: separate a right cell from a wrong one.
    sigma_over_spacing: float
    #: usable lines ÷ metric DOF, per system — the system-dependent half of
    #: "enough lines" (:data:`MIN_LINES_PER_DOF`)
    lines_per_dof: dict[str, float] = Field(default_factory=dict)
    #: systems this list can support a search in at all
    systems_supported: list[str] = Field(default_factory=list)
    #: figures of merit undefined on this list, name → reason (WP-1043).  A
    #: property of the *peak list* — its line count — not of any candidate, so
    #: the panel shrinks by exactly these members for every candidate alike and
    #: Borda ranks over what remains.  Filled from ``fom.panel_undefined``, the
    #: one authority; empty at or above :data:`PEAK_MIN_USABLE_LINES`.
    fom_undefined: dict[str, str] = Field(default_factory=dict)
    #: Smith (1977) envelope on the unit-cell volume, Å³, from d at the N-th
    #: line — the default ``max_volume`` for a search, **per system** because the
    #: bound differs by up to 96× across them (a cubic F lattice shows ~96× fewer
    #: distinct lines than a primitive triclinic one of the same volume, so the
    #: same N lines admit a correspondingly larger cell).  One number would
    #: therefore either exclude the true cubic cell or be useless for triclinic.
    volume_envelope: dict[str, float] = Field(default_factory=dict)
    shift: ShiftScreen | None = None
    supports_indexing: bool = True
    abstained_reason: str | None = None
    thresholds_version: str = INDEXING_THRESHOLDS_VERSION
    diagnostics: list[Diagnostic] = Field(default_factory=list)


# ----------------------------------------------------------------------
# the search controls — one spec behind every chair (WP-1045)
# ----------------------------------------------------------------------
class SearchSpecSpec(Base):
    """Mirrors ``indexing.engines.SearchSpec``; every engine reads the same one.

    Flat and complete rather than a handful of convenience knobs, because the
    engines' **agreement** is the confidence and that only means something if
    they were given identical bounds: a per-engine option would make ``high``
    a statement about two different searches.

    **This is the one control surface** (WP-1045).  It lived in ``agent.py``
    (WP-1024) until the GUI needed the same fields; now the agent re-exports
    it (the ``StageSpec``/``PlanSpec`` precedent), the project document embeds
    it (``ProjectDoc.indexing``), and the GUI form renders it — held
    field-for-field against the frozen dataclass by
    ``tests/test_search_controls.py``, so a control added to one chair fails
    a test until every chair has it.  Vocabulary validators import the live
    registries lazily (engines register on package import, and
    ``engines.py`` imports this module); the neutral descriptions here are
    deliberate — the live-quoted ones belong to the surface that *exports* a
    schema (``agent.py``'s field descriptions), never to the shared model.
    """

    systems: list[str] | None = Field(None, description=(
        "crystal systems to search; None = all seven, run in decreasing "
        "symmetry order because a cubic answer costs seconds and a triclinic "
        "search costs minutes, so whoever gets the cubic answer first can "
        "stop"))
    centrings: dict[str, list[str]] | None = Field(None, description=(
        "Bravais centrings to try, per system (e.g. {'cubic': ['P', 'I']}); "
        "None or an absent system = every centring that system admits. An "
        "empty list is refused — omitting the key is how a system keeps its "
        "full set, and skipping a system entirely is `systems`' job"))
    min_d_axis: float = Field(2.0, gt=0.0, description=(
        "shortest principal d-spacing (Å) to consider — a bound on d(100), which "
        "for an oblique cell is slightly stronger than a bound on a"))
    max_d_axis: float = Field(25.0, gt=0.0, description=(
        "longest principal d-spacing (Å); raising it costs exponentially, since "
        "domain size is what an exhaustive search pays for"))
    min_volume: float = Field(15.0, gt=0.0)
    max_volume: float | None = Field(None, description=(
        "cell-volume ceiling (Å³), taken verbatim — explicit narrowing is the "
        "caller's own act. None takes Smith's (1977) per-system envelope from "
        "the data-quality report (which differs by up to 96x across systems), "
        "with the calibration slack the engines apply to a mean line"))
    n_unindexed: int = Field(2, ge=0, description=(
        "search lines a cell may leave unindexed and still be accepted. Raising "
        "it MANUFACTURES cells — every tolerated line is one more coincidence a "
        "wrong metric is allowed — so 2 is a default and 4 is a statement about "
        "the specimen"))
    n_search_lines: int = Field(20, ge=2, description=(
        "observed lines the search is DRIVEN by — the strongest N, scored "
        "afterwards against every usable line. Raising it is not free and not "
        "safe: a cell must index all but n_unindexed of THESE, an absolute "
        "budget, so every extra foreign line admitted can refute the true cell "
        "rather than merely rank it lower (measured: a 68-line list loses its "
        "certified lattice entirely at 32)"))
    k_sigma: float = Field(3.0, gt=0.0, description=(
        "matching window in units of each line's own sigma; 3 is a calibrated "
        "99.7 % window, not a knob"))
    shift_allowance_deg: float = Field(0.0, ge=0.0, description=(
        "systematic 2theta allowance (deg) you have MEASURED, e.g. from an "
        "internal standard — the shift's AMPLITUDE the matching window must "
        "span (ShiftScreen.allowance_deg), never the residual scatter a "
        "template leaves (ShiftScreen.sigma_sys_deg): the two differ 4.3x on "
        "a certified pattern and declaring the scatter finds no cell at all. "
        "Leave 0 and the engines assume 0.05 deg and say so with "
        "INDEX_SHIFT_ALLOWANCE — which caps confidence, because a cell found "
        "inside a widened window absorbs the shift (+1400 ppm measured)"))
    shift_template: str | None = Field(None, description=(
        "'constant' | 'cos_theta' | 'sin_2theta' — re-fit a surviving candidate "
        "with this shift column, which is the fix for the allowance above; a "
        "shift is only identifiable against reference positions and a candidate "
        "cell is what supplies them"))
    budget_seconds: float = Field(30.0, gt=0.0, description=(
        "wall clock per (engine x crystal system) SLICE of the search, not per "
        "run: a default two-engine, seven-system call is up to 2x7x30 s of "
        "search before the probe and validation. An engine stopped by it "
        "reports search_complete[system] = false, and a negative result there "
        "is not evidence. total_budget_seconds is the whole-run bound"))
    total_budget_seconds: float | None = Field(None, gt=0.0, description=(
        "wall-clock ceiling for the WHOLE run — search, probe and validation "
        "together. The run still returns a complete IndexingResult over what "
        "was reached; systems_searched/search_complete distinguish searched, "
        "truncated and not reached, and INDEX_BUDGET_EXHAUSTED names them. "
        "None (default) leaves the ceiling to `preset`; setting it overrides "
        "the preset's and the result records preset='custom'"))
    preset: str | None = Field(None, description=(
        "search preset governing the whole-run ceiling, from the live "
        "SEARCH_PRESETS registry. None resolves to the default ('quick', a "
        "measured ceiling with truncation reported loudly); 'full' is the "
        "unbounded pre-1.0 behaviour, one rerun away"))
    max_candidates: int = Field(12, ge=1)
    seed: int = 0
    prior_cells: list[tuple[float, float, float, float, float, float]] | None = \
        Field(None, description=(
            "structural-analogue cells (a, b, c in Å; alpha, beta, gamma in "
            "deg) to try FIRST — each one's crystal system jumps the search "
            "queue, its metric seeds the stochastic engine's starting basin, "
            "and the cell itself is checked against the peak list, entering "
            "the answer as finder 'prior' only if it indexes the search "
            "lines. A prior STEERS, never gates: no system dropped, no range "
            "changed, prior-only candidates appended after the ranked list — "
            "a wrong prior costs time, not truth — and INDEX_PRIOR_USED "
            "records what was supplied and what it changed"))
    prior_spacegroups: list[str] | None = Field(None, description=(
        "space-group symbols from a structural analogue (e.g. 'R -3 c'): "
        "each contributes its crystal system to the queue jump and, beside a "
        "matching prior cell, its centring. What a powder measures is the "
        "extinction symbol, so the symbol steers the search rather than "
        "labelling the answer"))

    @field_validator("prior_cells")
    @classmethod
    def _sane_prior_cells(cls, v):
        for cell in v or ():
            a, b, c, al, be, ga = cell
            if min(a, b, c) <= 0.0:
                raise ValueError(f"prior cell {cell} has a non-positive axis")
            if not all(0.0 < x < 180.0 for x in (al, be, ga)):
                raise ValueError(f"prior cell {cell} has an angle outside "
                                 "(0, 180) degrees")
        return v

    @field_validator("prior_spacegroups")
    @classmethod
    def _known_prior_spacegroups(cls, v):
        for symbol in v or ():
            from ..indexing.priors import spacegroup_prior

            spacegroup_prior(symbol)  # raises naming the symbol
        return v

    @field_validator("systems")
    @classmethod
    def _known_systems(cls, v):
        from ..indexing.engines import SYSTEM_ORDER

        for name in v or ():
            if name not in SYSTEM_ORDER:
                raise ValueError(f"unknown crystal system {name!r}; "
                                 f"available: {', '.join(SYSTEM_ORDER)}")
        return v

    @field_validator("centrings")
    @classmethod
    def _known_centrings(cls, v):
        from ..indexing.engines import CENTRINGS, SYSTEM_ORDER

        for system, letters in (v or {}).items():
            if system not in SYSTEM_ORDER:
                raise ValueError(f"unknown crystal system {system!r}; "
                                 f"available: {', '.join(SYSTEM_ORDER)}")
            allowed = CENTRINGS.get(system, ("P",))
            if not letters:
                raise ValueError(
                    f"empty centring list for {system!r} — a system with no "
                    "centrings would be silently skipped; omit the key to "
                    "keep its full set, or drop the system from `systems`")
            for c in letters:
                if c not in allowed:
                    raise ValueError(
                        f"centring {c!r} is not admitted by {system} "
                        f"(available: {', '.join(allowed)})")
        return v

    @field_validator("shift_template")
    @classmethod
    def _known_template(cls, v):
        if v is not None and v not in SHIFT_TEMPLATES:
            raise ValueError(f"unknown shift template {v!r}; "
                             f"available: {', '.join(SHIFT_TEMPLATES)}")
        return v

    @field_validator("preset")
    @classmethod
    def _known_preset(cls, v):
        from ..indexing.engines import SEARCH_PRESETS

        if v is not None and v not in SEARCH_PRESETS:
            raise ValueError(f"unknown search preset {v!r}; "
                             f"available: {', '.join(SEARCH_PRESETS)}")
        return v

    def to_spec(self):
        from ..indexing.engines import SYSTEM_ORDER, SearchSpec

        return SearchSpec(
            systems=tuple(self.systems) if self.systems else SYSTEM_ORDER,
            centrings=({k: tuple(v) for k, v in self.centrings.items()}
                       if self.centrings else None),
            min_d_axis=self.min_d_axis, max_d_axis=self.max_d_axis,
            min_volume=self.min_volume, max_volume=self.max_volume,
            n_unindexed=self.n_unindexed, n_search_lines=self.n_search_lines,
            k_sigma=self.k_sigma, shift_allowance_deg=self.shift_allowance_deg,
            shift_template=self.shift_template,
            budget_seconds=self.budget_seconds,
            total_budget_seconds=self.total_budget_seconds,
            max_candidates=self.max_candidates, seed=self.seed,
            prior_cells=tuple(tuple(c) for c in self.prior_cells or ()),
            prior_spacegroups=tuple(self.prior_spacegroups or ()))


class IndexingControls(Base):
    """Everything an indexing *run* is asked with that is not the data itself.

    ``SearchSpecSpec`` plus the ``index_pattern`` call options that are not
    ``SearchSpec`` fields.  The project document embeds this (control state is
    a project setting, persisted on the verb), the agent request carries the
    same fields, and ``tests/test_search_controls.py`` holds all three to
    ``index_pattern``'s own signature.  ``two_theta_limits`` is deliberately
    absent: the project document already owns it (one authority per fact).
    """

    search: SearchSpecSpec = Field(default_factory=SearchSpecSpec)
    engines: list[str] | None = Field(None, description=(
        "indexing engines to run; None = all registered, and keep it — "
        "'high' confidence MEANS every engine that ran found the same "
        "lattice, so naming a subset narrows what the answer can say"))
    validate_candidates: bool = Field(True, description=(
        "run the whole-profile Le Bail validation when a pattern is "
        "available; turning it off caps every candidate at medium, so do it "
        "only to save time on a first look"))
    check_top: int | None = Field(None, ge=1, description=(
        "candidates given the expensive per-candidate checks (geometrical "
        "ambiguity + Le Bail validation); None = the package default plus "
        "every candidate the gate could promote, which never removes a "
        "candidate that might grade high"))

    @field_validator("engines")
    @classmethod
    def _known_engines(cls, v):
        from ..indexing.engines import engine_names

        for name in v or ():
            if name not in engine_names():
                raise ValueError(f"unknown indexing engine {name!r}; "
                                 f"available: {', '.join(engine_names())}")
        return v


class CaveatEvidence(Base):
    """One caveat, carrying the half the gate never serialized: its **kind**.

    ``confidence_caveats`` is a bare name list, and whether a member *refutes*
    the cell or merely *caps* its grade lives in
    :data:`INDEX_REFUTING_CAVEATS` — a package constant a JSON consumer cannot
    see.  An agent told ``predicted_but_absent`` and ``not_validated`` in the
    same breath needs to know the first argues against the cell and the second
    only says a question was never asked; that distinction is what this model
    puts in the answer (WP-1043).
    """

    name: IndexCaveat
    kind: Literal["refuting", "capping"]


class CandidateEvidence(Base):
    """One candidate's evidence, collected for a consumer that can reason.

    **No new physics** — every field is a projection of
    :class:`CellCandidate`, assembled so the inputs to the gate's judgement
    arrive together instead of scattered (WP-1043).  The magnetite pair is the
    argument for the three whole-profile figures sitting side by side: on the
    correct cell ``predicted_but_absent`` reads 2 and on its wrong rival **0**
    — the detector is backwards there — while Rwp reads 0.2545 against 0.7884.
    A reasoner given both can see the detector has failed; the gate, reading
    one number, cannot.  That is an argument for *surfacing* Rwp, never for
    scoring on it: WP-1020 kept ``lebail_rwp`` off the ranking panel because
    it rewards flexibility, and the retraction recorded in WP-1043 is what
    reading it as evidence cost once already.
    """

    #: position in ``IndexingResult.candidates`` — candidates arrive ranked,
    #: so 0 is the panel's first choice, and this index is what
    #: adopt/extinction calls address
    index: int
    cell: tuple[float, float, float, float, float, float]
    cell_esd: tuple[float, float, float, float, float, float]
    system: str
    centring: str
    volume: float
    confidence: Confidence
    #: every caveat with its refuting/capping kind — the field
    #: ``confidence_caveats`` withholds
    caveats: list[CaveatEvidence] = Field(default_factory=list)
    found_by: list[str] = Field(default_factory=list)
    n_indexed: int = 0
    n_lines: int = 0
    #: the panel members that ranked this candidate, name → value.  Which
    #: members exist is a property of the peak list, not of the candidate —
    #: ``IndexingEvidence.fom_undefined`` names the absent ones with reasons
    fom: dict[str, float] = Field(default_factory=dict)
    #: ``True`` when a Le Bail fit ran on *this* candidate — distinct from
    #: ``IndexingResult.validated`` (a pattern was supplied at all): under a
    #: budget the shortlist can be validated only partway down
    validated: bool = False
    lebail_status: str | None = None
    lebail_rwp: float | None = None
    predicted_but_absent: int | None = None
    unmatched_observed: int | None = None
    ambiguity_partners: int = 0


def candidate_evidence(index: int, c: CellCandidate) -> CandidateEvidence:
    """One candidate's evidence-view row — the **one** projection (WP-1042/43).

    Shared by :meth:`IndexingResult.evidence` and the per-system streaming
    snapshot the scheduler emits, so the shape a candidate takes mid-run can
    never fork from the shape the answer reports — the two WPs deliberately
    share this schema rather than each writing its own dict.
    """
    return CandidateEvidence(
        index=index, cell=c.cell, cell_esd=c.cell_esd,
        system=c.system, centring=c.centring, volume=c.volume,
        confidence=c.confidence,
        caveats=[CaveatEvidence(
            name=v, kind=("refuting" if v in INDEX_REFUTING_CAVEATS
                          else "capping"))
                 for v in c.confidence_caveats],
        found_by=list(c.found_by),
        n_indexed=c.n_indexed, n_lines=c.n_lines,
        fom={f.name: f.value for f in c.fom},
        validated=c.lebail is not None,
        lebail_status=None if c.lebail is None else c.lebail.status,
        lebail_rwp=None if c.lebail is None else c.lebail.rwp,
        predicted_but_absent=(None if c.lebail is None
                              else c.lebail.predicted_but_absent),
        unmatched_observed=(None if c.lebail is None
                            else c.lebail.unmatched_observed),
        ambiguity_partners=len(c.ambiguity))


class IndexingEvidence(Base):
    """The reasoning consumer's view of an :class:`IndexingResult` (WP-1043).

    The gate returns three levels and ``best_or_none()``; a consumer that can
    reason wants the *inputs* to that judgement.  This is those inputs in one
    machine-readable place: per candidate the caveats with kinds, the ranked
    figures beside the names of the ones that could not be computed, and the
    three whole-profile numbers together; result-wide, what the search
    covered and what the list supports.  Everything here is a projection —
    built by :meth:`IndexingResult.evidence` from the fields the result
    already carries, so the two can never disagree.
    """

    candidates: list[CandidateEvidence] = Field(default_factory=list)
    #: what the search covered — tried, and per system whether the domain was
    #: exhausted (the two answer different questions; see ``IndexingResult``)
    systems_searched: list[str] = Field(default_factory=list)
    search_complete: dict[str, bool] = Field(default_factory=dict)
    #: what the peak list supports at all (``MIN_LINES_PER_DOF``)
    systems_supported: list[str] = Field(default_factory=list)
    n_usable_lines: int = 0
    #: panel members that ranked every candidate — uniform by construction
    fom_ranked: list[str] = Field(default_factory=list)
    #: members undefined on this list, name → reason — absent for cause is a
    #: different statement from silently zero (WP-1043)
    fom_undefined: dict[str, str] = Field(default_factory=dict)
    #: was a pattern supplied, i.e. could Le Bail validation run at all
    validated: bool = False


class IndexingResult(Base):
    """What :func:`rietx.index_pattern` returns — and what it *cannot* return.

    **The founding rule is enforced by the type.**  There is no ``.cell``, no
    ``.best`` and no ``.solution`` attribute; :attr:`candidates` is always a list,
    and the only singleton accessor is :meth:`best_or_none`, which returns a cell
    only when the confidence gate is fully satisfied.  That is the same species of
    guard as ``Geometry.mu_r`` being a plain ``float`` so the type forbids
    refining it: the *shape* of the API holds the rule, not a caller's discipline.
    An indexer that hands back one cell confidently is the failure this whole
    milestone exists to prevent, and this repo has already met it on its own data
    (the withdrawn multiphase claim recorded at the tag ``guillemot-study``).

    **A restricted search is not a verdict.**  :attr:`systems_searched` is beside
    :attr:`search_complete` because the two answer different questions: the first
    is what was *tried*, the second whether the domain was *exhausted*.  Failure
    is reported as "no cell found in the systems searched"
    (``INDEX_SYSTEMS_NOT_COVERED``), never as "this pattern is multiphase" —
    measured, a restricted engine's coverage bands overlap between single-phase
    low-symmetry patterns and genuine mixtures, and a claim built on that
    ambiguity was withdrawn.
    """

    candidates: list[CellCandidate] = Field(default_factory=list)
    #: engines that actually ran, from the live registry.  This is the
    #: denominator of the agreement gate, so it must be what ran and not what was
    #: requested.
    engines_run: list[str] = Field(default_factory=list)
    #: systems any engine covered, merged across engines
    systems_searched: list[str] = Field(default_factory=list)
    #: per system: did *every* engine that searched it exhaust its domain?  An
    #: exhaustive engine that finished and found nothing has said "no such cell
    #: within these bounds"; the same engine stopped by its budget has said
    #: nothing, and the two must not be one field.
    search_complete: dict[str, bool] = Field(default_factory=dict)
    #: per-engine counters, prefixed ``<engine>.`` so two engines' numbers never
    #: collide
    engine_stats: dict[str, float] = Field(default_factory=dict)
    #: do the panel's members put different candidates first?  A *result*-level
    #: fact (it is a statement about the comparison, not about one cell) that caps
    #: every candidate's confidence
    fom_panel_disagrees: bool = False
    quality: DataQualityReport | None = None
    #: was a pattern supplied, i.e. did Le Bail validation run at all?  ``False``
    #: caps every candidate at ``"medium"`` and fires ``INDEX_NOT_VALIDATED`` —
    #: the *result* abstains rather than one field being quietly downgraded
    validated: bool = False
    wavelength: float = 0.0
    n_usable_lines: int = 0
    provenance: Provenance
    #: which search preset governed the run's ceiling (WP-1042):
    #: ``engines.SEARCH_PRESETS`` names, or ``"custom"`` when the caller's own
    #: ``total_budget_seconds`` did, or ``None`` on a result recorded before
    #: presets existed.  The ceiling itself is in ``provenance.notes``.
    preset: str | None = None
    thresholds_version: str = INDEXING_THRESHOLDS_VERSION
    diagnostics: list[Diagnostic] = Field(default_factory=list)

    def best_or_none(self) -> CellCandidate | None:
        """The single candidate, or None.

        Returns a cell only when exactly one candidate has
        ``confidence == "high"`` and no ambiguity partners.  Every other
        situation — nothing found, two cells that both explain the pattern, a
        geometrically ambiguous winner, an unvalidated search, an assumed
        tolerance — returns ``None``, and the reason is in
        :attr:`diagnostics` and in each candidate's ``confidence_caveats``.

        The ambiguity re-check is redundant with the gate (which already refuses
        ``"high"`` to a candidate with partners) and is kept anyway: this method
        is the single place the rule is *guaranteed*, so it does not delegate the
        guarantee to whoever filled the field.
        """
        high = [c for c in self.candidates if c.confidence == "high"]
        if len(high) != 1:
            return None
        return None if high[0].ambiguity else high[0]

    def evidence(self) -> IndexingEvidence:
        """The machine-readable evidence view (WP-1043).

        A projection, never a second copy that could disagree: every field is
        computed from this result on each call.  ``fom_ranked`` is read from
        the first candidate carrying a panel — membership is uniform by
        construction (a property of the peak list), and a candidate with an
        *empty* panel hit the reflection ceiling, which its
        ``indexed_fraction_low`` caveat already reports.
        """
        ranked: list[str] = []
        for c in self.candidates:
            if c.fom:
                ranked = [f.name for f in c.fom]
                break
        q = self.quality
        return IndexingEvidence(
            candidates=[candidate_evidence(i, c)
                        for i, c in enumerate(self.candidates)],
            systems_searched=list(self.systems_searched),
            search_complete=dict(self.search_complete),
            systems_supported=([] if q is None
                               else list(q.systems_supported)),
            n_usable_lines=self.n_usable_lines,
            fom_ranked=ranked,
            fom_undefined={} if q is None else dict(q.fom_undefined),
            validated=self.validated)


class ExtinctionCandidate(Base):
    """One **extinction class**: the space groups that share an absence set.

    The observable is the extinction symbol, never the space group.  Groups in
    one class differ only by symmetry elements a powder pattern cannot see —
    centrosymmetric/non-centrosymmetric pairs, enantiomorphs, the mirror that
    turns ``P 63`` into ``P 63/m`` — so they produce **identical** patterns by
    construction, not for want of counting time.  That is why
    :attr:`space_groups` is a list and why
    ``EXTINCTION_GROUPS_NOT_SEPARABLE`` fires whenever it holds more than one:
    the cleanest instance in the package of "never a confident wrong singleton",
    since here the singleton is not merely unsupported but *unmeasurable*.

    Two counts carry the evidence and they answer different questions.
    :attr:`n_absent` is how many lines of the absence-free lattice this class
    forbids; :attr:`n_testable` is how many of those the data could actually
    check — the rest fall outside the fitted range, coincide with a line the
    class still allows, or sit in a window this class's own fit already fills
    with a neighbour's tail, and none of the three is an observation.
    :attr:`n_present` is the refutation: a forbidden position that carries
    intensity.
    """

    #: IT-style extinction symbol, **derived** from the class members rather than
    #: transcribed (see :func:`rietx.indexing.extinction.extinction_symbol`).
    #: A label, not a key: two classes can in principle carry the same string,
    #: and :attr:`representative` is what identifies the class.
    symbol: str
    #: the H-M symbol whose reflections were generated for this class
    representative: str
    #: **every** space group in the class, in IT number order.  A list because
    #: the data cannot choose between them — see the class docstring.
    space_groups: list[str] = Field(default_factory=list)
    #: derived reflection conditions ("0kl: k = 2n"), for a human to check
    conditions: list[str] = Field(default_factory=list)
    #: False when the derivation left some absences unnamed; the absence set
    #: itself is authoritative either way (measured: 1 of 550 gemmi settings)
    conditions_complete: bool = True
    #: distinct lines (not orbits) this class predicts in the fitted range
    n_lines: int = 0
    #: lattice lines this class forbids
    n_absent: int = 0
    #: of those, the ones the data can test — inside the range, separable from
    #: every line the class still allows, and left **quiet by this class's own
    #: fitted pattern**.  This is ``n_added`` in the nested comparison: a
    #: forbidden line coinciding with an allowed one never was an independently
    #: determined intensity, so removing it costs no parameter.
    #:
    #: ``None`` until :attr:`screened`, and that is not bookkeeping.  The third
    #: clause is a question about the class's *fit* — a window filled by a
    #: neighbour's tail measures the profile model rather than the absence
    #: (WP-1077) — so before the fit the count is unknown rather than zero, and
    #: a geometric count published in the meantime would be an over-estimate
    #: reading as a measurement.
    n_testable: int | None = None
    #: testable forbidden positions carrying net intensity above the fitted
    #: background — each one refutes the class
    n_present: int = 0
    #: the refuting reflections, so the refutation can be checked in the pattern
    forbidden_hkl: list[tuple[int, int, int]] = Field(default_factory=list)
    forbidden_two_theta: list[float] = Field(default_factory=list)
    #: whole-pattern Le Bail fit of this class; ``rwp`` is ``inf`` when the class
    #: was refuted before it was fitted (:attr:`screened`)
    rwp: float = float("inf")
    gof: float = float("inf")
    chi2: float = float("inf")
    #: BIC(this class) − BIC(the absence-free lattice), from
    #: ``report.layer2.delta_bic``: **negative favours this class**.  Differences
    #: between two classes' values are themselves a ΔBIC, because both are taken
    #: against the same reference.
    delta_bic: float = 0.0
    #: Hamilton's (1965) R-factor ratio test in the same direction: True when
    #: restoring the forbidden reflections is *justified*, i.e. the class's
    #: absences are contradicted by the fit
    absences_rejected: bool = False
    #: was the Le Bail screen actually run for this class?  False when direct
    #: absence evidence already refuted it (no fit can rescue a forbidden
    #: position that carries intensity) or when ``max_classes`` truncated
    screened: bool = False
    #: **One-sided by construction.** A class asserts *absences*, so intensity at
    #: a position it forbids contradicts it — while a class claiming too *few*
    #: absences asserts nothing the data can falsify and is outranked rather than
    #: refuted.  The one other way in is a Le Bail fit that raised, which
    #: :attr:`refuted_reason` names as such: with no χ² it cannot be the answer.
    refuted: bool = False
    refuted_reason: str | None = None
    diagnostics: list[Diagnostic] = Field(default_factory=list)


class ExtinctionScreen(Base):
    """What :func:`rietx.determine_extinction_symbol` returns.

    Same shape rule as :class:`IndexingResult` one rank down: no ``.symbol`` and
    no ``.space_group`` on the screen itself, only a ranked :attr:`candidates`
    list and :meth:`best_or_none`.  And even ``best_or_none()`` returns a *class*
    — which lists its space groups — so the API cannot express "the space group
    is P2₁/c" where the powder can only say "the extinction symbol is P 1 21/c 1".

    The ranking is by :attr:`ExtinctionCandidate.delta_bic` with refuted classes
    last, and ties broken toward **fewer** absences: an absence you cannot see is
    not an absence you may claim.
    """

    candidates: list[ExtinctionCandidate] = Field(default_factory=list)
    #: the absence-free lattice group every class is compared against
    lattice_group: str = ""
    cell: tuple[float, float, float, float, float, float] = (0.0,) * 6
    system: str = ""
    centring: str = "P"
    wavelength: float = 0.0
    #: fitted 2θ range the classes were enumerated and judged over.  It is part
    #: of the answer: two classes differing only outside it are one class here.
    two_theta_range: tuple[float, float] = (0.0, 0.0)
    #: classes enumerated / classes whose Le Bail fit was run
    n_classes: int = 0
    n_screened: int = 0
    #: the absence-free class's own screen fit — the reference model
    reference_rwp: float = float("inf")
    reference_chi2: float = float("inf")
    reference_lines: int = 0
    n_points: int = 0
    #: Rwp of the shared profile fit that produced the frozen instrument every
    #: class is then fitted with
    profile_rwp: float = float("inf")
    status: str = "converged"
    thresholds_version: str = INDEXING_THRESHOLDS_VERSION
    diagnostics: list[Diagnostic] = Field(default_factory=list)

    def best_or_none(self) -> ExtinctionCandidate | None:
        """The one extinction class, or None.

        Returns a class only when it was fitted, is not refuted, rests on at
        least one absence the data could **test** (or is the absence-free class
        itself, whose claim is that there is nothing to see), is separated from
        the next surviving class by a decisive ΔBIC margin, and **no unrefuted
        class was left unfitted** — a ``max_classes`` cap or a cancelled run
        leaves an unasked question, which must not read as a clean answer.  Every
        other situation returns None with the reason in :attr:`diagnostics`.

        A returned class still lists every space group it contains.  There is no
        accessor anywhere in this module that yields one space group.
        """
        from ..indexing.extinction import DECISIVE_DELTA_BIC

        if any(not c.refuted and not c.screened for c in self.candidates):
            return None                 # an unasked question, not a clean answer
        alive = [c for c in self.candidates if not c.refuted]
        if not alive:
            return None
        top = alive[0]
        if top.n_absent and top.n_testable == 0:
            return None
        if len(alive) > 1 and alive[1].delta_bic - top.delta_bic < DECISIVE_DELTA_BIC:
            return None
        return top
