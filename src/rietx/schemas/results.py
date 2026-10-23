"""Refinement result schemas."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

import numpy as np
from pydantic import Field, model_validator

from .._about import DIST_NAME
from .common import Base, Diagnostic, Mode, Provenance
from .interval import ParameterInterval
from .parametric import (
    ParametricCoefficient,
    ParametricFormReading,
    ParametricFormTest,
    ParametricValue,
    RefinedParametricEquation,
)
from .pattern import POISSON_FLOOR_COUNTS, _floor_sigma


class RefinedParameter(Base):
    """One row of :attr:`RefinementResult.parameters`.

    The membership filter **is the contract** (WP-1003, ratifying 1053): a row
    appears iff the entry varied or was tied — a fixed parameter is *absent*,
    not present with ``vary=False``.  The full table, held rows and their
    reasons included, is :meth:`rietx.Refinement.parameters`, which also
    merges these esds back in.

    **``at_bound`` has three states, and one of them is "nobody looked"**
    (WP-1076).  ``True``/``False`` are answers about a *measured* row;
    ``None`` says the question was not asked of this row, which happens two
    ways: the result was assembled without a guard report (``refine.replay``,
    which is evaluate-only, and any hand-built result), and a **tied** row,
    which is not in the free vector and so is never tested — its value
    follows its sources, and it can sit on its own declared bound while every
    source is interior.  A free scale or width on its floor of 0 is tested
    like any other bound (WP-1938), so an absent phase's scale reads ``True``
    when the data push it onto that floor.  Before WP-1076 the field was
    ``bool = False`` and nothing wrote it, so every row of every result
    asserted "not at a bound" about a parameter no code had looked at.

    **``True`` says the limit carried load, not that the value is near one**
    (WP-1434).  Under the default ``lm`` driver the row is in the driver's
    exact active set: it sits on the limit and the gradient there points out
    of the allowed range (WP-1929).  Under ``trf``, or a system too large for
    an exact step, it must sit within a hundredth of its own esd of the limit
    *and* the residual must still push it outward.  Either way a value resting
    on a limit the fit is not pressing reads ``False`` and there is nothing
    there to widen.  The diagnostic's ``Diagnostic.value`` carries the
    evidence, signed; this flag is the bit.

    **The source is the guard, never a local recomputation.**  The one place
    the bound test happens is :func:`rietx.strategy.staged.bound_findings`,
    whose findings become the ``BOUND_HIT`` and ``FLOOR_HIT`` diagnostics
    (``FLOOR_HIT`` on a floor no wider bound can lower, WP-1929); this flag is
    a projection of that same list onto the rows, so it is ``True`` under
    either code and the two can never disagree.  The diagnostics stay the
    reported channel — the flag exists so that an agent iterating
    ``parameters`` does not have to cross-reference ``diagnostics`` by path.

    **``equations`` names the parametric declarations that set the row** (WP-1325),
    in declaration order, and is empty where none does.  A row is set by an equation
    when one of its coefficients moves it, read off **C** as every hold reads
    it (WP-1342), so a held coefficient still counts.  Three kinds of row are:
    the target in each pattern of the subset, what follows the target there (a
    cubic cell's b and c), and the coefficient's own ``vars.<name>_<j>`` row.
    On a target row the value and esd are the equation's at that pattern's
    coordinates, which can be far tighter than the pattern measures alone, and
    where the pattern cannot see the target they are the equation's alone
    (``PARAMETRIC_TARGET_UNSEEN``).  On a coefficient row they are in the
    table's units, per unit of the *scaled* coordinate, and
    :attr:`RefinementResult.parametric` holds the same coefficient in the
    caller's units.  Two writers: ``MultiHistogramRefinement._parameters``,
    and ``refine._build_result``, which writes it empty because a single fit
    declares no equation (a chain's rows are its fits').  ``None`` says nobody
    recorded it: a hand-built row, or a result written before schema 0.57,
    when 1.9.0's parametric fits already carried equation-set rows that an empty
    list would have called measured.

    **``interval`` is the profile interval of a moment angle the fit left out
    of its covariance** (WP-2002, B2).  The stationary-angle test
    (``StageResult.moment_angle_tests``, WP-1929) takes such an angle's column
    out, so its ``stderr`` stays ``None``.  The data still determine the angle
    through curvature, so the fit computes its 95 % profile interval
    (:class:`~rietx.schemas.interval.ParameterInterval`, the answer
    ``Refinement.profile_interval`` returns) and stores it here.  One writer:
    ``parameter_interval.attach_stationary_intervals``, which ``fit`` and
    ``run_stage`` call for every angle the answer-producing stage left out.
    ``None`` says no interval was computed: any other row, a joint fit (which
    has no profile verb), a package-internal trial, a fit cancelled while its
    intervals ran, or a result stored before the field.

    **``stderr_uncorrected`` is the esd other programs print** (WP-2002, B4).
    ``stderr`` carries the Bérar-Lelann factor f for serially correlated
    residuals (``optimize.statistics.berar_lelann_factor``); this is the same
    esd without it, √(χ²_red·(JᵀJ)⁻¹) carried to the row, which is what
    GSAS-II and FullProf report.  It is ``stderr`` divided by the f the solve
    multiplied it by (``LSQOutcome.esd_inflation``), so one fit's rows share
    one ratio and the identity is exact to rounding.  That f is measured on
    the solve's own last residual, and :attr:`Statistics.esd_inflation`
    re-measures it at the result's compile: on 11-BM NAC the two differ by
    0.07 % (Rietveld) and 0.75 % (Le Bail), and by 4 % on a joint fit
    weighted 1:4.  So ``stderr / Statistics.esd_inflation`` is close to this
    and not equal to it.  Two writers, each beside ``stderr``:
    ``refine._build_result`` and ``MultiHistogramRefinement._parameters``; a
    series copies its fits' rows.  ``None`` wherever ``stderr`` is, and on a
    result stored before the field.
    """

    path: str
    value: float
    stderr: float | None = None
    stderr_uncorrected: float | None = None
    vary: bool = True
    at_bound: bool | None = None
    equations: list[str] | None = None
    interval: ParameterInterval | None = None

    def __str__(self) -> str:
        """``path  value(esd)  state`` on one line, so a list of rows reads as
        a table (WP-1545)."""
        from .._display import refined_parameter_text
        return refined_parameter_text(self)


class Statistics(Base):
    """Agreement indices, defined per Toby (2006), Powder Diffraction 21, 67.

    Per-fit only: ``n_iterations`` is on :class:`~rietx.schemas.sequential.SeriesEntry`
    (a series has one count per pattern, not one pooled figure here), and an
    unmatched-peak count is the report's — ``FitReport.unmatched`` (rows) or
    ``StageReport.n_unmatched_obs``/``n_unmatched_calc`` (counts), never here.

    ``rwp_background_subtracted`` re-evaluates Rwp with the background removed
    from both y_obs and y_calc, which Toby recommends as the more meaningful
    number when the background is a large fraction of the signal.

    ``esd_inflation`` is the Bérar-Lelann serial-correlation factor, their
    homogeneous correction (Bérar & Lelann, 1991, J. Appl. Cryst. 24, 1,
    § IV) — reported parameter esds have already been multiplied by it.
    Perfectly white residuals still land at ≈1.13, from chance same-sign
    neighbours (``optimize.statistics.berar_lelann_factor``), so a value near
    that is no evidence of correlation; lab data with unmodelled profile
    detail lands near 2-3 (1.93 on the FAP tutorial fit, 2.82 on SRM 660c).
    It is measured on the residual at the values this result reports, while
    the esds carry the factor the solve measured on its own last residual,
    so the two can differ slightly (WP-2002, B4, measured on 11-BM NAC:
    0.07 % on a Rietveld fit, 0.75 % on a Le Bail fit, 4 % on a joint fit
    weighted 1:4).  The raw χ²·(JᵀJ)⁻¹ esd of a row is
    :attr:`RefinedParameter.stderr_uncorrected`.

    ``max_shift_over_esd`` is McCusker et al. (1999) §7's convergence
    quantity: the largest |Δθᵢ|/esd(θᵢ) over the final accepted step of the
    answer-producing solve, both sides in external parameter units.
    The paper's band — converged when ≤ 0.1
    (``optimize.statistics.MAX_SHIFT_CONVERGED``) — is quoted, never tuned,
    and gates nothing; a TRF solve at ftol 1e-9 satisfies it a fortiori, so
    the information is on the other branch: a stage that stopped on
    ``STAGE_MAX_ITER`` reports how far it was still moving, in esd units.
    ``run_least_squares`` computes it, ``refine`` copies it, nothing else
    derives it (WP-1076).  ``None`` wherever it cannot be measured: no
    accepted step, no esds, or an evaluate-only ``replay``.  A joint
    multi-histogram fit has it too (WP-1341): one shift per column of the
    joint θ against the esd the joint covariance gives that column, so the
    histogram weights change the number and leave its meaning alone
    (``run_multi_least_squares`` computes it).  It is whole-fit, so a
    :class:`HistogramResult`'s own statistics leave it ``None`` and
    :meth:`RefinementResult.for_histogram` carries the joint figure onto
    its view, beside the joint stages it prints.

    ``identifiability_clause`` is the report's identifiability sentence,
    verbatim — the same string ``build_report`` appends to
    ``FitReport.summary``, rendered once by
    :func:`~rietx.report.identifiability.identifiability_clause` and written
    to both places in the same build (the pair is pinned bit-identical by
    test).  ``build_report`` is its **only** writer — a declared
    cross-document write (WP-1108): the sentence is report contract
    (``report_thresholds_version``), so no fit-time code writes it and a fit
    alone leaves it ``None``.  ``None`` covers both "no report was built"
    and "nothing crossed a comment threshold" — the honest empty state,
    never a verdict — and per-histogram statistics have no writer (the
    clause is whole-fit).  It is delivered here, beside the numbers, because
    measured agent consumers pipe the JSON response to a file and grep the
    statistics block back, and the summary string is what those greps drop
    (WP-1065's 2-of-12; the placement round, WP-1107).
    """

    rwp: float
    rp: float
    rexp: float
    chi2: float
    gof: float
    rwp_background_subtracted: float | None = None
    durbin_watson: float | None = None
    esd_inflation: float | None = None
    n_points: int
    n_free_parameters: int
    max_shift_over_esd: float | None = None
    identifiability_clause: str | None = None


class DataSupport(Base):
    """How many observations the pattern actually holds (WP-1071).

    ``n_points`` on :class:`Statistics` is what the least-squares algorithm
    calls N, and it is not what the data can support.  McCusker, Von Dreele,
    Cox, Louër & Scardi (1999), *J. Appl. Cryst.* **32**, 36-50, §9 is blunt
    about the consequence: "the Rietveld algorithm will allow many more
    parameters to be refined than the data can actually support (because
    mathematically the number of observations is the number of steps in the
    profile), so the user has to intervene with common sense."  Only the
    integrated intensities of individual reflections are unique observations,
    and the paper's band on the ratio is "at least three and preferably five".

    **Evidence, gating nothing.**  Both counts are reported and neither
    refuses anything: this is the coarse number a reader checks first, and
    the sharp per-parameter question is
    :class:`Identifiability`'s — the Gram-condition soft modes and the
    exchangeability scan answer *which* parameter is unsupported, where this
    answers *how many* the pattern can carry at all.  Neither claims the
    other's job.

    ``n_unique_reflections`` counts orbit representatives (so a Laue orbit is
    one reflection, and the Kα2 companion of a line is not a second one),
    summed over every phase, restricted to those actually measured — a fitted
    channel within half the reflection's own FWHM of its position, on **any**
    emission line.  Half a FWHM rather than the range ends because that is the
    criterion the excluded regions and the two edges both answer at once: a
    reflection whose top falls in an excluded gap was not observed, however
    far inside ``two_theta`` it sits (WP-1033's fitted-mask rule one rank
    down), and a reflection just past the top edge whose peak is half measured
    was.  It is the **raw** count, and it over-counts by construction: two
    reflections at one 2θ are one observation.

    ``n_structural_parameters`` counts the free parameters §9 is about — the
    atomic ones (coordinate DOFs, occupancies, Biso, ADP DOFs), matched as
    ``phases.*.atoms.*``.  Cell, zero, profile, background, scale, preferred
    orientation and extinction are excluded: they are determined by peak
    positions and shape rather than by the integrated intensities being
    counted here.  The complement is
    ``Statistics.n_free_parameters − n_structural_parameters`` — not repeated
    as a field, because that count already has an authority.

    ``n_effective_observations`` is that count corrected for overlap —
    Altomare, Cascarano, Giacovazzo, Guagliardi, Moliterni, Burla & Polidori
    (1995), *J. Appl. Cryst.* **28**, 738-744, which McCusker §9 names as the
    way to make the estimate.  Each reflection contributes the fraction of its
    own area on which no overlapping reflection stands higher, so an isolated
    line counts 1 and an exactly coincident pair counts 1 between them.  The
    method and its three caveats — including the paper's own "may not have a
    rigorous basis", which McCusker quotes — are in
    :func:`~rietx.optimize.statistics.effective_observations`.  It is a
    **float**, because a partly resolved pair is worth more than one
    observation and less than two, and that is the whole content of the number.

    ``observations_per_parameter`` and
    ``effective_observations_per_parameter`` are the two ratios, both
    ``None`` when no structural parameter is free (a Le Bail or Pawley fit,
    or a profile-only stage), where the ratio is not undefined so much as not
    about anything.  **The effective ratio is the one the paper's band is
    about**; the raw one is its upper bound, and the two are reported together
    because their *gap* is the pattern's overlap.
    """

    n_unique_reflections: int
    n_effective_observations: float | None = None
    n_structural_parameters: int
    observations_per_parameter: float | None = None
    effective_observations_per_parameter: float | None = None


class CorrelationPair(Base):
    """One entry of the worst-|ρ| list (WP-1056).

    ``rho`` is the signed correlation from the solver's final undamped
    Jacobian (the same matrix the ``HIGH_CORRELATION`` guard read, so the
    two can never disagree); the list is ordered worst first.
    """

    path_a: str
    path_b: str
    rho: float


class SoftMode(Base):
    """One near-null direction of the scale-normalised normal matrix.

    WP-1056.  Watkin, 2008, J. Appl. Cryst. 41, 491 §3.8 — the informative
    object is the *combination*, not the pair; Prince, *Mathematical
    Techniques* 3rd ed. ch. 8 — remedies are "linear combinations of
    parameters that are approximately eigenvectors of the Hessian matrix".

    ``eigenvalue`` is of ĴᵀĴ with every column normalised to unit length, so
    it is dimensionless and transform-independent: for a single pair with
    correlation ρ it equals 1 − |ρ| (Prince's "worthwhile at |ρ| > 0.95" is
    eigenvalue < 0.05), and 0 is exact degeneracy.  ``loadings`` are the
    components of the unit eigenvector with |v| ≥ 0.1, keyed by path, sign
    canonicalised so the largest component is positive.  The softest modes
    are carried whatever their eigenvalues — the number is the evidence; the
    report decides where comment starts.
    """

    eigenvalue: float
    loadings: dict[str, float] = Field(default_factory=dict)


class ExchangeRow(Base):
    """How well the fitted parameters can imitate one held parameter.

    WP-1056.  ``r2`` is the block projection R² of the held parameter's Jacobian
    column — evaluated at the converged values with the candidate freed on a
    copy of the vary set, never refined — onto the span of the free columns:
    R² → 1 means the data cannot distinguish freeing it from what was
    fitted (Prince ch. 8: dropping a correlated variable leaves the fit
    unchanged and the survivors' apparent precision illusory).  **R² alone
    is a design-matrix property of the sampled range and fires on clean fits
    too** (measured 0.999945 on the E2 fixture *and* its clean reference);
    the discriminating half — is anything significant riding the exchange —
    is the report's, from the fitted partners' values and esds.

    ``partners`` are the scale-free loadings of the held column's
    least-squares reconstruction in the free span (|loading| ≥ 0.05 kept,
    signed): the paths whose fitted values absorb the held parameter's
    signature, magnitudes read as the share of the held column's norm each
    partner supplies.
    """

    held: str
    r2: float
    partners: dict[str, float] = Field(default_factory=dict)


class Identifiability(Base):
    """Degeneracy evidence measured on the **final Jacobian** (WP-1055/-1056).

    This carrier exists because these statistics cannot be recovered from a
    stored result.  J is an N×P array that is never serialized (a history node
    stores state, not curves), so anything read off it has to be screened at
    fit time or lost — unlike Rwp or a residual, which any consumer can
    recompute from the arrays already here.

    It arrived **additive and defaulted**, which under the rule of the day left
    ``SCHEMA_VERSION`` where it was — the events rule of WP-1043 one rank over,
    a new field on an existing shape not being a new shape.  **That is no
    longer the rule.**  Since WP-1117 the only question is whether a consumer
    could *notice*, and a new field on a result is noticeable, so an addition
    of this shape now bumps the version like any other: the comment beside
    :data:`~rietx.schemas.common.SCHEMA_VERSION` is the changelog, and three of
    its entries are additive defaulted fields.  Corrected here rather than
    deleted because this is the sentence that talked a later reader out of a
    bump it owed.

    ``background_absorption`` maps each screened structural path to the block
    projection R² of its Jacobian column onto the background column span
    (:func:`~rietx.optimize.statistics.background_absorption`).  **Every**
    screened pair is here, not only those over
    ``BACKGROUND_ABSORPTION_GUARD``: a fired/not-fired bit is a verdict, while
    0.46-against-0.08 is evidence, and the guard's diagnostic already carries
    the verdict.  The numbers are the *same measurement* the guard decided on,
    not a second one — so the report's background section and the
    ``BACKGROUND_ABSORPTION`` diagnostic can never quote different numbers.

    ``top_correlations``, ``soft_modes`` and ``exchangeability`` (WP-1056) are
    the parameter-space evidence measured at the same point, by
    :mod:`~rietx.optimize.identifiability`: the worst pairwise correlations
    with their paths, the softest modes of the scale-normalised normal matrix
    as named combinations, and the held-parameter exchangeability scan.  All
    three are carried as evidence on the same terms as the absorption table —
    numbers, not verdicts; thresholds live in the report.

    This answers **which** parameter the data cannot support;
    :class:`DataSupport` answers **how many** the pattern can carry at all,
    from the reflection count rather than from the Jacobian.  Neither claims
    the other's job, and the coarse number is the one a reader checks first.

    Empty ⇔ nothing was measurable: fewer than two free parameters, no
    Jacobian retained by the solver, or no pair/candidate to project
    (``exchangeability`` is additionally empty in Pawley mode, where the
    residual's θ carries the intensity block and the fitted span the scan
    projects onto is not the table's — see the scan's docstring).  Absent
    (``None`` on the result) ⇔ nothing measured it — a ``replay`` of a
    history node (evaluate-only, no solve).  Read ``None`` as "not measured
    here", never as "no degeneracy".

    A joint multi-histogram fit (WP-1341) screens each histogram's own rows,
    so its ``background_absorption`` keys are ``hist.<h>.``-scoped, shared
    paths included, and :meth:`RefinementResult.for_histogram` hands one
    histogram's view its own rows, unscoped.  The joint path runs neither
    the declared-peak screen nor the parameter-space screens, so
    ``extra_peak_absorption`` and the three tables below it stay empty there,
    a declared and freed peak included: not measured, the same reading as
    ``None``.
    """

    background_absorption: dict[str, float] = Field(default_factory=dict)
    #: The same statistic asked of the component seam's *other* member
    #: (WP-1103): R² of each screened structural column on the span of the
    #: **declared sharp peaks**.  Evidence only — no threshold fires on it,
    #: because the 0.25 above was measured for background blocks and nothing
    #: has measured what separates a healthy declared peak from a parasitic
    #: one.  ``EXTRA_PEAK_ON_REFLECTION`` carries the verdict this number is
    #: evidence beside, and it is a *positional* test rather than a
    #: correlational one.
    #:
    #: The two tables **partition** the declared components: a component is in
    #: one block or the other, never both, by its declared aggregate.  Empty
    #: when no peak component is declared or freed.
    extra_peak_absorption: dict[str, float] = Field(default_factory=dict)
    top_correlations: list[CorrelationPair] = Field(default_factory=list)
    soft_modes: list[SoftMode] = Field(default_factory=list)
    exchangeability: list[ExchangeRow] = Field(default_factory=list)


class PhaseQuantity(Base):
    """One phase's quantitative-analysis row (Hill & Howard, 1987).

    ``cell_mass`` (= Z·M) and ``cell_volume`` are the unambiguous quantities;
    ``z`` and ``molar_mass`` are the best-effort integer-formula-unit split
    (``z = 1``, ``molar_mass = cell_mass`` when the composition does not reduce
    to integers under refined occupancies).  ``weight_fraction`` never depends
    on that split.

    The microabsorption fields are filled only when the Brindley correction
    ran (every phase carried a ``particle_radius_um``).  ``weight_fraction``
    always stays the *uncorrected* Hill-Howard number — the correction is
    reported alongside, never silently substituted.  ``weight_fraction_stderr``
    belongs to the uncorrected fraction; the corrected one inherits the
    systematic uncertainty of the user-supplied radii, which dominates and is
    not statistical.  ``mu_r`` is the phase's µ·R (dimensionless, R = particle
    radius): Brindley's spherical-particle treatment is derived for the
    fine/medium powder regime µ·D ≤ 0.1 (D = 2R), i.e. µ·R ≤ 0.05 — beyond
    that the number travels with the answer so the fence diagnostic can point
    at it.
    """

    name: str                                       # matches Phase.name / ticks key
    weight_fraction: float                          # W, renormalised to sum to 1
    weight_fraction_stderr: float | None = None     # σ(W); None if scale esds absent
    scale: float                                    # S (refined phases.{i}.scale)
    z: int | None = None                            # formula units per cell (display)
    molar_mass: float | None = None                 # M, g/mol per formula unit
    cell_mass: float                                # Z·M, g/mol per unit cell
    cell_volume: float                              # V, Å³
    zmv: float                                       # cell_mass · V

    # -- Brindley microabsorption (WP-0305); None unless the correction ran --
    weight_fraction_corrected: float | None = None  # W/τ, renormalised
    brindley_tau: float | None = None               # τ((µ_p − µ̄)·R_p)
    mu_cm: float | None = None                      # µ_p at the primary λ, 1/cm
    mu_r: float | None = None                       # µ_p·R_p (fence: ≤ 0.05)
    particle_radius_um: float | None = None         # R_p as supplied, µm


class MicroabsorptionCorrection(Base):
    """Mixture-level record of the Brindley correction (Brindley, 1945).

    ``mu_mean_cm`` is the volume-weighted mean attenuation of the *solid*
    crystalline mixture at the correction's fixed point (porosity is not
    modelled; the solid average is the conservative choice).  ``wavelength``
    is the primary emission line the attenuation was evaluated at — µ ∝ λ³
    makes the Kα₂ difference sub-percent in µ and smaller still in τ.
    """

    method: Literal["brindley_sphere"] = "brindley_sphere"
    wavelength: float                               # Å, primary emission line
    mu_mean_cm: float                               # µ̄ of the solid mixture, 1/cm


class AbsorptionCorrection(Base):
    """Record of the specimen absorption applied (cylinder or flat plate).

    WP-0501 added the cylinder and WP-0508 the flat plate.  Present only for Rietveld fits that actually carried a specimen dimension.
    ``method`` says which geometry's expression ran; ``mu_r`` carries the
    dimensionless µ·(length) in every case — the capillary radius for
    ``rouse_cylinder``, the specimen thickness for the two flat-plate cases —
    and ``mu_r_source`` says whether it was given or estimated from
    composition × packing × that length.

    ``equivalent_delta_biso`` is the point of the whole correction, and for the
    cylinder it is the *only* point: the Rouse transmission factor is exactly a
    constant times exp(c·sin²θ), so applying it is an exact reparameterisation
    of the phase scale and the displacement parameters and Rwp does not change.
    What changes is that a Biso refined *without* it comes back low by this
    much (Å²) — positive means "add this to recover the unbiased value".

    The flat-plate cases are **not** exactly reparameterisable, and that makes
    their ``equivalent_delta_biso`` a **lower bound** rather than the answer: the
    projection behind it is unweighted while a refinement finds a weighted
    compromise, and measured against synthetic refits the bias a fit really
    absorbs runs 1.06-1.5x the predicted one, tracking ``unabsorbed_fraction``.
    Two more fields carry what the cylinder does not need:
    ``unabsorbed_fraction`` is the share of ln A that a free scale and a free
    Biso cannot reproduce (0 for the cylinder to rounding, a few per cent to
    tens of per cent for a flat plate) — and hence how far to trust the ΔBiso
    above.  ``identifiable_fraction`` is the same measure applied to ∂lnA/∂µt,
    the number behind the decision not to make the thickness refinable.  Both
    are measured at the *reflection* positions rather than on the fitted grid
    (WP-0502's lesson).

    ``intensity_fraction_of_optimal`` is filled for transmission only.  The
    intensity-maximising plate has µt = 1 exactly, so µt *is* the thickness in
    units of the optimum and this is µt·exp(1 − µt) — the counts this specimen
    delivered as a fraction of the best it could have.  A specimen-preparation
    number no fit statistic can express, since a badly chosen thickness costs
    counting statistics and not accuracy.
    """

    method: Literal["rouse_cylinder", "flat_plate_reflection",
                    "flat_plate_transmission"] = "rouse_cylinder"
    mu_r: float
    mu_r_source: Literal["given", "estimated"]
    wavelength: float                    # Å, primary emission line
    equivalent_delta_biso: float         # Å², bias incurred by omitting this
    #: set when the dimensionless product was requested but could not be
    #: estimated (absorption edge in the tabulation interval, element outside
    #: the compilation, energy outside 2-120 keV) — the correction was then not
    #: applied
    skipped: str | None = None
    #: set when µR exceeds the Rouse fit's stated range; the value was still
    #: used, since refusing outright would silently drop real absorption.
    #: Never set for the flat-plate cases, which are exact integrals with no
    #: fitted range to leave
    out_of_range: bool = False
    #: flat plate only — the share of ln A not reproducible by {scale, Biso}
    unabsorbed_fraction: float | None = None
    #: flat plate only — the share of ∂lnA/∂(µt) not reproducible by them
    identifiable_fraction: float | None = None
    #: transmission only — counts delivered as a fraction of the µt = 1 optimum
    intensity_fraction_of_optimal: float | None = None


class QuantitativePhaseAnalysis(Base):
    """Per-phase weight fractions from the refined Rietveld scales.

    Hill & Howard (1987), J. Appl. Cryst. 20, 467: W_p ∝ S_p·(Z·M·V)_p,
    renormalised across phases.  ``weight_fraction_stderr`` is propagated from
    the *correlated* scale block of the covariance (not σ(S) treated as
    independent), carrying the same conditioning as every other reported esd.

    Scope (``crystalline_only``): these are fractions of the modelled
    **crystalline** content.  An unmodelled amorphous fraction or a missing
    phase still makes them sum to 1.  Internal-standard / amorphous
    quantification is fenced to v2.
    """

    phases: list[PhaseQuantity]
    method: Literal["zmv"] = "zmv"
    crystalline_only: bool = True

    # Brindley microabsorption: the mixture-level record when the correction
    # ran, or the reason it was skipped when radii were supplied but the
    # correction could not run (partial radii, µ unavailable at this λ, …).
    # Both None ⇔ no phase asked for a correction.
    microabsorption: MicroabsorptionCorrection | None = None
    microabsorption_skipped: str | None = None


class PhaseAgreement(Base):
    """One phase's structure-sensitive agreement indices (WP-1069).

    R_Bragg and R_F, McCusker et al. (1999) eqs (14) and (13), from the
    observed-intensity partition described in
    :func:`~rietx.optimize.statistics.structure_r_factors` — which also carries
    the definitions, the CIF tags and the bias warning.  Every published
    Rietveld refinement is expected to quote at least one of them (Young,
    Prince & Sparks, 1982, *J. Appl. Cryst.* **15**, 357).

    **Per phase, and beside the QPA rather than inside it.**  Other codes quote
    R_B per phase and readers of a multi-phase fit compare them, so a single
    whole-fit number would be the wrong shape.  It is not a field of
    :class:`PhaseQuantity` because QPA needs Z and a molar mass and is absent
    without them, while a structure R exists for any Rietveld fit — a
    single-phase refinement with no QPA at all still has one.

    **Absent for cause outside Rietveld mode.**  In Le Bail mode the partition
    *is* the fit and in Pawley mode the intensities are refined parameters, so
    I(obs) would be compared against itself: circular, not merely
    uninformative.  ``refine`` leaves ``RefinementResult.phase_agreement``
    empty there — the ``lebail_gap`` precedent, one rank down.

    ``r_bragg`` and ``r_f`` are ``None`` only for a phase with no partitionable
    scattering power at all (see the function above); ``n_reflections`` is how
    many reflections entered the sums, which is smaller than the phase's
    reflection list whenever one falls off the Ewald sphere.
    """

    name: str                          # matches Phase.name / the ticks key
    r_bragg: float | None = None       # eq (14), _refine_ls_R_I_factor
    r_f: float | None = None           # eq (13), _refine_ls_R_factor_all
    n_reflections: int = 0


class PhaseTexture(Base):
    """One phase's spherical-harmonics texture at the answer (WP-1960).

    These are the correction's evidence, because Rwp is not (root CLAUDE.md).
    ``texture_index`` is J = 1 + Σ C²/(2l+1), 1 for a random powder, a lower
    bound on the specimen's because the odd orders and those past the
    declared order are not measured.  ``min_p_reflections`` is the lowest
    multiplier over the phase's fitted reflections, and ``min_p_sphere`` the
    lowest over directions sampled on the whole sphere, the reflections
    included.  A negative ``min_p_sphere`` is what ``TEXTURE_NOT_POSITIVE``
    reports.

    Written by ``refine._phase_texture``, one row per phase that carries a
    texture block in Rietveld mode.  Empty otherwise, and empty for a joint
    fit, whose shared coefficients meet each histogram at its own ψ.
    """

    name: str                         # matches Phase.name
    texture_index: float
    min_p_reflections: float
    min_p_sphere: float


class RestraintRow(Base):
    """One soft restraint's computed-vs-target deviation (WP-0406).

    ``deviation_over_sigma`` is the headline: a restraint fighting the data
    shows up as |deviation/σ| ≫ 1 (and, past a threshold, a ``RESTRAINT_TENSION``
    diagnostic).  ``atoms`` (bond/angle) or ``path`` (value) names the target;
    exactly one is set.  A planarity restraint gives one row per atom: its
    signed distance to the plane (target 0), ``atoms`` listing that atom first
    and then the rest of the plane in restraint order.
    """

    phase_index: int | None = None
    kind: Literal["bond", "angle", "value", "tether", "anti_bump", "planarity"]
    atoms: list[int] | None = None                  # bond (2) / angle (3) indices
    path: str | None = None                         # value-restraint dot-path
    computed: float                                 # Å (bond), deg (angle), or value
    target: float
    sigma: float
    weight: float = 1.0
    deviation: float                                # computed − target
    deviation_over_sigma: float


class RestraintReport(Base):
    """Per-restraint deviations and the pooled restraint χ² (WP-0406).

    ``restraint_chi2`` = Σ weight·(deviation/σ)² is S_G of McCusker eq (7) —
    the sum of the squared restraint rows at unit c_w.  It is *not* part of the
    data-row Rwp/χ²/GoF (those see data rows only), by design: restraints are
    soft observations, not measured intensities.

    ``weight_scale`` is the c_w the stage that produced this ran at (WP-1074),
    so the penalty actually added to the minimised S is
    ``weight_scale · restraint_chi2``.  The deviations themselves are reported
    unscaled because "is this restraint satisfied?" is a question about the
    geometry, and c_w is a choice about how hard to insist on the answer.
    """

    rows: list[RestraintRow]
    restraint_chi2: float
    n_restraints: int
    weight_scale: float = 1.0


class GeometryDistance(Base):
    """One interatomic distance, bonding or nonbonding (WP-1072).

    ``atom_1`` sits at its published coordinates (``symmetry_1`` is always
    ``"."``); ``atom_2`` is the image reached by ``symmetry_2``, a CIF
    ``n_klm`` code against the operation order
    :func:`~rietx.model.geometry.symmetry_operations` lists and the exported
    CIF carries.  ``None`` there means the image needs a lattice shift outside
    the one-digit code, which changes nothing about the distance.

    The rows are **every** asymmetric-unit atom's whole environment, so a bond
    between two sites appears once from each end and the count of rows naming
    an atom is its coordination number (see :mod:`rietx.model.geometry` for
    why that beats the CIF's one-direction convention here, and where the
    convention is restored).  ``atom_index_*`` index
    ``structure.phases[phase_index].atoms``, the way ``RestraintRow.atoms``
    does, so a consumer never has to match on a label.

    ``stderr`` is McCusker §10's number — J·Cov·Jᵀ through the **whole**
    covariance, ties and cell included.  ``stderr_diagonal`` is the same
    propagation with the off-diagonal covariance zeroed, i.e. what a reader
    combining the printed parameter esds in quadrature would get.  It is
    carried so the difference §10 warns about is visible rather than asserted
    (the ``qpa.weight_fractions`` precedent), and it is never the answer.
    Both are ``None`` when no covariance was estimated, and also when nothing
    the row depends on was refined — an all-zero block is absence of
    information, not σ = 0.  The two causes deliberately share one ``None``
    (WP-1003): a consumer never needs σ's *reason* to use the number, and if
    one ever does, a per-row cause field is the additive fix — never a
    reinterpreted zero.
    """

    phase_index: int
    atom_1: str                       # _atom_site_label of the reference atom
    atom_2: str
    atom_index_1: int
    atom_index_2: int
    distance: float                   # Å
    stderr: float | None = None       # full covariance
    stderr_diagonal: float | None = None
    symmetry_1: str = "."
    symmetry_2: str | None = "."
    bonded: bool = True               # covalent-radius criterion (BOND_SLACK_ANG)

    def __str__(self) -> str:
        """The pair, the distance with its esd, and the image's symmetry code
        on one line, so a list of bonds reads as a table (WP-1545)."""
        from .._display import distance_text
        return distance_text(self)


class GeometryAngle(Base):
    """One interatomic angle at ``atom_2``, in degrees (WP-1072).

    The vertex is at its published coordinates; the two arms carry their own
    symmetry codes.  Only bonded arms are used, so a listed angle is one
    between two members of the vertex's coordination sphere.  esd conventions
    are :class:`GeometryDistance`'s exactly.
    """

    phase_index: int
    atom_1: str
    atom_2: str                       # the vertex
    atom_3: str
    atom_index_1: int
    atom_index_2: int
    atom_index_3: int
    angle: float                      # degrees
    stderr: float | None = None
    stderr_diagonal: float | None = None
    symmetry_1: str | None = "."
    symmetry_2: str = "."
    symmetry_3: str | None = "."


class CellVolume(Base):
    """One phase's unit-cell volume in Å³, with its esd (WP-1933).

    The esd goes through the whole covariance of the six cell entries
    (:func:`~rietx.model.geometry.cell_volumes`), so a crystal-system tie and
    the correlation between, say, a and c in a hexagonal cell both reach it.
    esd conventions are :class:`GeometryDistance`'s exactly: ``None`` where
    nothing the volume depends on was refined, or where a source measured
    nothing, and ``stderr_diagonal`` the number with the refined parameters'
    correlations dropped.
    """

    phase_index: int
    volume: float                     # Å³
    stderr: float | None = None
    stderr_diagonal: float | None = None


class GeometryTable(Base):
    """Bonding geometry of the converged model, with propagated esds (WP-1072).

    The second of McCusker §11's two "most important criteria" — the chemical
    sense of the structure — as evidence rather than as a verdict: this module
    computes distances and angles and says nothing about whether they are
    reasonable.  It is a **carrier** for the same reason
    :class:`Identifiability` is: the covariance the esds come from is read off
    the final Jacobian and never serialized, so a stored result carries what
    was measured at fit close or ``None``.

    Present for Rietveld fits with atoms; ``None`` in Le Bail and Pawley mode,
    where the dummy atom the mode requires is not a structure.  ``notes``
    records every place coverage was bounded — a per-atom contact cap, a phase
    too large to search — because a table that silently stopped early reads
    exactly like one that found nothing more.
    """

    distances: list[GeometryDistance] = Field(default_factory=list)
    angles: list[GeometryAngle] = Field(default_factory=list)
    #: the listing criteria actually used, so a row can be read without
    #: knowing which version of the module produced it
    bond_slack: float = 0.0           # Å, added to the covalent-radius sum
    contact_max: float = 0.0          # Å, the nonbonding listing radius; bonds are not bounded by it
    notes: list[str] = Field(default_factory=list)

    @property
    def bonds(self) -> list[GeometryDistance]:
        """The bonded subset of :attr:`distances`."""
        return [d for d in self.distances if d.bonded]

    @property
    def contacts(self) -> list[GeometryDistance]:
        """The nonbonded subset of :attr:`distances`."""
        return [d for d in self.distances if not d.bonded]


class MicrostructureTerm(Base):
    """One profile coefficient read as the physical quantity behind it.

    ``kind`` is ``"size"`` — a **coherent domain size** in Å, the length over
    which the lattice diffracts in phase — or ``"strain"``, the dimensionless
    Δd/d.  ``path`` names the coefficient it came from, ``coefficient`` is that
    coefficient in its stored units (deg for the Lorentzian pair, deg² for the
    Gaussian variances), and ``value``/``esd`` are the reading.

    **A coherent domain size is not a particle size** and must never be
    reported as one: ``Phase.particle_radius_um`` is Brindley's absorption
    path, a *particle*, and profile broadening measures the domain inside it,
    which is smaller than the particle and unrelated to it.  Nor is it a
    two-figure number: the Scherrer constant moves 10-20 % with crystallite
    shape (:data:`~rietx.model.profiles.caglioti.SCHERRER_K`), so this is an
    order-of-magnitude statement about the specimen.

    ``value`` and ``esd`` are ``None`` **for cause**, and ``unavailable`` says
    which cause (WP-1072's rule: a quantity that cannot be measured is absent
    rather than zero):

    * ``"at_zero"`` — the coefficient is at its off state, where a size is
      infinite and a strain is a perfect lattice.  True, and not a number;
    * ``"no_wavelength"`` — a size needs a λ and the source declares none
      (never reaches a strain, which has no λ in it);
    * ``"not_measured"`` — the coefficient carries no esd, so ``value`` stands
      and ``esd`` does not.  Three ways that happens and they are one answer
      here: the parameter was never freed, its column measured nothing
      (``ParameterTable.unmeasured_rows``), or the result came from ``replay``.

    The propagation is exact and needs no covariance beyond one variance,
    because each reading is a function of exactly **one** parameter:
    ``L = (180/π)·K·λ/x`` gives ``σ_L = L·σ_x/x``, and ``Δd/d = (π/360)·y``
    is linear, so ``σ`` scales by the same constant.  A *combined*
    Gaussian-plus-Lorentzian size would need the cross-term and is not reported
    — the two are read separately and compared instead
    (:attr:`PhaseMicrostructure.size_agreement`).
    """

    path: str
    kind: Literal["size", "strain"]
    coefficient: float
    #: Å for ``kind="size"``, dimensionless Δd/d for ``kind="strain"``
    value: float | None = None
    esd: float | None = None
    unavailable: str | None = None


class PhaseMicrostructure(Base):
    """A phase's size and strain as physical numbers, with esds (WP-1131).

    Four coefficients, four readings: ``lor_size`` and ``gauss_size`` each
    imply a coherent domain size, ``lor_strain`` and ``gauss_strain`` each a
    Δd/d.  They are four *independent* columns in this package — unlike
    GSAS-II, which refines one magnitude per mechanism plus a Gaussian/Lorentzian
    mixing coefficient — so nothing makes them agree and
    :attr:`size_agreement` / :attr:`strain_agreement` report whether they do.

    ``separable`` is the caveat, carried **beside the number** rather than left
    to a reader: over a narrow 2θ range the 1/cosθ and tanθ templates are
    collinear (the Williamson-Hall problem) and a size quoted without saying so
    is the confident wrong singleton the FitReport exists to refuse.  It is the
    width ``TrendAnalysis``'s own ``separable``, attached when the report ran
    Layer 1 and ``None`` — *no claim made* — otherwise; never recomputed here,
    because a second opinion on one statistic is two statistics.
    """

    phase_index: int
    phase_name: str = ""
    #: the λ the sizes were read at — the source's longest declared line, the
    #: selector every size surface in the package shares
    wavelength: float | None = None
    #: the Scherrer constant used, so a row can be rescaled without knowing
    #: which build produced it.  **Required, not defaulted** (WP-1076, and
    #: WP-1305's ``delta_bic`` precedent): a 0.0 here would read as an *answer*
    #: about a constant nothing set, and a size scales linearly in it, so a
    #: document written without one must fail to load rather than load with a
    #: K nobody chose
    scherrer_k: float
    terms: list[MicrostructureTerm] = Field(default_factory=list)
    #: Gaussian-implied size ÷ Lorentzian-implied size, when both are readable.
    #: 1 means the two independent columns describe one specimen; far from 1
    #: means they do not, and neither is quotable alone
    size_agreement: float | None = None
    #: the same ratio for the two strains
    strain_agreement: float | None = None
    #: the width trend's own separability verdict, or None for "not assessed"
    separable: bool | None = None
    #: |correlation| between the 1/cosθ and tanθ templates over the sampled
    #: range, carried with ``separable`` so a reader sees how close it came
    size_strain_collinearity: float | None = None

    def term(self, name: str) -> MicrostructureTerm | None:
        """The term for a coefficient name (``"lor_size"``, …), or None."""
        for t in self.terms:
            if t.path.rsplit(".", 1)[-1] == name:
                return t
        return None

    def __str__(self) -> str:
        """One row a term, each reading with its esd or its reason, then the
        agreement and separability fields (WP-1545). The generic tree spent
        five lines on a term and printed a size as an unrounded float."""
        from .._display import MICROSTRUCTURE_HEADER, microstructure_sections, table_text
        head, rows, tail = microstructure_sections(self)
        body = table_text(MICROSTRUCTURE_HEADER, rows, "  ") if rows else []
        return "\n".join([head, *body, *("  " + line for line in tail)])

    def _repr_html_(self) -> str:
        """The terms as a table between the head line and the verdict lines."""
        from .._display import (
            MICROSTRUCTURE_HEADER,
            microstructure_sections,
            pre_html,
            table_html,
        )
        head, rows, tail = microstructure_sections(self)
        table = table_html(MICROSTRUCTURE_HEADER, rows) if rows else ""
        return pre_html(head) + table + pre_html("\n".join(tail))


class MomentAngleTest(Base):
    """One round of the stationary-angle test on a stage's covariance (WP-1929).

    A moment's polar angle and azimuth have Jacobian columns that vanish at a
    direction the symmetry fixes, because the pattern is even in the angle
    there.  The covariance equilibrates every column to unit norm, so near such
    a direction a column's direction is set by where the solver stopped, and
    so were the other esds.  The test moves ``paths`` together,
    everything else fixed, until every column is below
    ``MOMENT_DIRECTION_SUPPORT`` of the largest of its sites' modulus columns.
    The test then refits the other columns by one linear step at the stop and
    at that point.  ``statistic`` is the difference in data χ² over
    χ²_red·f².  The angles pass when it is at most ``cut``, the 95 % point of
    the χ̄² mixture for ``len(paths)`` one-sided directions (Self & Liang,
    1987; Shapiro, 1985).  Their columns then leave the covariance, so each
    has no esd, and their values stand.  On a single fit each such angle's
    row carries its profile interval instead (``RefinedParameter.interval``,
    WP-2002).

    ``paths`` are free columns.  A caller's ``vars.X`` driving only moment
    angles is one of them.  The angles it drives share its verdict.

    A set that fails and has more than one angle drops one and is tested
    again.  The dropped angle contributes most to the second-order change, or
    has the largest column where the Newton step did not reach the floor.
    ``reached`` is ``False`` for a set whose Newton step did not reach it, and
    ``statistic`` is then ``None``.

    ``half_widths`` is filled on a round that passed.  Per angle, it is the
    distance either side of the stationary direction at which the data χ²,
    every other parameter held, rises by χ²_red·f².  It is no esd.  It is the
    step ``Refinement.profile_interval`` starts from for such an angle.
    """

    paths: list[str]
    reached: bool
    statistic: float | None = None
    cut: float
    zeroed: bool
    #: each angle's value where the Newton step drove the columns to the
    #: floor, filled when ``reached``.  The distance from the fitted value is
    #: what the statistic was read across.
    stationary_at: dict[str, float] = Field(default_factory=dict)
    half_widths: dict[str, float] = Field(default_factory=dict)


class StageResult(Base):
    """One stage's outcome.

    ``status`` is the solver's, and the vocabulary is **exactly the three
    terminations the solver produces** — ``optimize/least_squares.py`` builds
    its outcome three ways and there is no fourth.  It admitted a
    ``"skipped"`` until WP-1076; nothing anywhere set it, so a consumer writing
    an exhaustive match handled a branch that could not occur and a reader of
    the type inferred a skip mechanism the package does not have.  A stage a
    plan does not run produces no ``StageResult`` at all, which is the honest
    way to say the same thing.
    """

    name: str
    status: Literal["converged", "max_iter", "diverged"]
    #: residual evaluations the solve made, the start included: scipy's
    #: ``nfev`` on both drivers, and the unit ``Stage.max_iter`` × 4 caps
    #: (``NFEV_PER_ITERATION``, WP-1937)
    n_iterations: int
    cost_initial: float
    cost_final: float
    freed: list[str] = Field(default_factory=list)
    #: the relative cost-decrease tolerance this stage actually stopped at, or
    #: ``None`` for the solver default (1e-9) — which is what the answer-
    #: producing last stage takes, and what every stage of every fit before
    #: WP-1123 took.  Recorded because it is otherwise unrecoverable from a
    #: result: the plan's schedule (``RefinementPlan.intermediate_ftol``) and a
    #: stage's own ``Stage.ftol`` both land here, and a consumer comparing two
    #: fits' parameter shifts needs to know whether they were converged the
    #: same way.
    ftol: float | None = None
    #: the fraction of each peak's area this stage's windows dropped, or
    #: ``None`` for ``forward.WINDOW_AREA_TOL`` — what every declared stage
    #: takes.  A plan's closing stage runs at ``closing_window_tol`` (WP-2002,
    #: the sixth round's Q1 and Q2), a stage run by hand at the fraction it
    #: ran at, and the result's curves and statistics are measured at the last
    #: stage's.  So a reader rebuilding the model from
    #: ``RefinementResult.parameters`` passes
    #: ``forward.recorded_window_tol(this)`` to ``compile_model`` to reproduce
    #: them, ``compile_model``'s own default being the closing stage's
    #: fraction: the 2 % and 0.1 % windows of one answer differ by up to 0.6 %
    #: in χ².
    window_area_tol: float | None = None
    #: steps the bounded-LM driver held on a linear-inequality constraint (the
    #: Stephens strain cone, or the Γ_G² floor of WP-1938 D7) during this
    #: stage: the step for the box alone crossed a row, and the step solved
    #: over the box and the rows replaced it (WP-1938 D8; the name is from
    #: before D8, when such a step was truncated).  Always 0 under
    #: TRF, which has no such vocabulary.  Nonzero in the *final* stage means
    #: the answer sits on or near a constraint face and additionally raises a
    #: ``CONSTRAINT_ACTIVE`` diagnostic — the only signal that a declared
    #: constraint was active rather than merely present (WP-0601).
    n_constraint_truncations: int = 0
    #: trial cells this stage's residual refused as degenerate (zero or
    #: negative volume, ``crystallography.lattice.DegenerateCellError``)
    #: rather than warning about and returning NaN — issue #283.  ``Cell``'s
    #: six parameters declare no bounds of their own (deliberately; see
    #: ``schemas.structure.Cell``'s docstring), so an underdetermined cell
    #: stage can reach a degenerate metric often, not rarely — this is the
    #: count of every trial pushed back out rather than crashing the stage,
    #: and 0 only means this particular stage never reached one.
    #: Additive field, defaulted to 0 (the honest "never happened" state);
    #: bumped with this change, ``SCHEMA_VERSION`` 0.19 → 0.20 (see the
    #: changelog entry in ``schemas/common.py``).
    n_degenerate_cell_probes: int = 0
    #: decompositions this stage's solve and esds repeated with LAPACK's
    #: QR-iteration driver because the divide-and-conquer driver stopped
    #: without converging (``optimize.lapack``): the same decomposition by
    #: another route, so the answer is the one a converging build computes.
    #: Met on macOS's system LAPACK, whose ``gesdd`` failed on a TRF step on
    #: CPD brucite that OpenBLAS's decomposed (WP-2002).  0 means no
    #: decomposition needed it.
    n_lapack_fallbacks: int = 0
    #: paths this stage **held** although the plan had freed them: the
    #: structural parameters of a phase the data could not see at stage start
    #: (the screen ``CompiledModel.phase_support`` below
    #: ``PHASE_SUPPORT_SIGMA``), or whose scale was not that significant
    #: against the counting noise at the stage's answer (WP-1523), which
    #: reach the pattern only through ``scale × |F|² × profile`` and are
    #: therefore a flat direction the solver would spend its budget walking
    #: (WP-1301).  Disjoint from :attr:`freed` by construction — a held path is
    #: dropped from it — so the two together say exactly what refined.  Empty
    #: on every fit with no unsupported phase, which is every fit that is
    #: working; the phase's own ``scale`` is never held, because that is how a
    #: phase legitimately climbs out of the noise.
    #: Since WP-1342 these are **columns**, not names: a caller's ``vars.X``
    #: driving that cell is what stopped moving, and a path under
    #: ``phases.{ip}.`` need not appear here at all.  What each held column
    #: also stopped is :attr:`held_reach`.
    held: list[str] = Field(default_factory=list)
    #: per held column, the tied entries it also stopped — the other half of
    #: :attr:`held`, and what lets a reader of this record find the *phase*
    #: a held ``vars.X`` was about (WP-1342).  Carried beside ``held`` rather
    #: than folded into it because the two are asked for by different
    #: consumers: ``held`` is the set the verb passed to ``set_vary`` and the
    #: set :attr:`freed` is made disjoint from, while this is the account
    #: ``PHASE_UNCONSTRAINED`` is built from.
    #:
    #: **Only the columns that drove something else**, and every tie counts,
    #: not only a caller's: holding a cubic ``a`` stops ``b`` and ``c`` with
    #: it, and a reader should not have to know the crystal system to learn
    #: that.  A column that moved nothing else is absent rather than mapped to
    #: an empty list, so ``held`` and the values here together are every value
    #: the stage froze.
    held_reach: dict[str, list[str]] = Field(default_factory=dict)
    #: per phase whose displacement parameters this stage **held** because the
    #: fitted range cannot separate them from the phase's scale (WP-1534), the
    #: separation measured at stage start (or, for a phase the support hold
    #: released inside the stage, before its second solve): the sine of the
    #: angle between the
    #: phase's scale column and its uniform-B column
    #: (``refine._scale_b_separation``), under
    #: ``refine.SCALE_B_SEPARATION_FLOOR``.  Keyed by phase index.  The held
    #: columns themselves are in :attr:`held`, beside WP-1301's and WP-1327's;
    #: this is what says which of them were held on this test and why.
    #:
    #: A hold on the frozen reflection list, so — unlike WP-1301's — never
    #: released inside the stage: a phase with one d-spacing in range keeps it
    #: whatever the solve does.  It feeds ``SCALE_B_INSEPARABLE``.
    #:
    #: **``None`` means nobody looked**: a result stored before this field, and
    #: every stage of a joint fit, whose runner does not ask the question.
    #: Both single-histogram runners write a mapping on every stage, so an
    #: empty one is a stage that looked and held nothing on this test.
    scale_b_held: dict[int, float] | None = None
    #: per instrument width column this stage **held** because free specimen
    #: widths have its angular dependence (WP-2002), the specimen columns it
    #: pairs with: U with ``gauss_strain`` and ``gauss_size`` (tan²θ in Γ_G²;
    #: the size's 1/cos²θ is 1 + tan²θ, so it is flat with U and W together,
    #: and W, the constant width, is never held), X with ``lor_size`` (1/cosθ in
    #: Γ_L), Y with ``lor_strain`` (tanθ in Γ_L).  The data see each
    #: angular term only as a total, so with both sides free it walks along a
    #: flat direction.  The instrument side is held at the value the stage
    #: started from, which is how every program that separates the two does
    #: it, by fixing the instrument from a standard (``docs/practice.md``), and
    #: the specimen value is then the width the instrument does not account
    #: for.  Where the instrument value was fitted on this specimen instead,
    #: it carries that stage's split.  The held columns are in :attr:`held` too.
    #:
    #: Held where the null space of the totals is not empty
    #: (``refine._width_twin_flats``): one seen phase whose specimen width is
    #: held pins the instrument term for every phase, and nothing is held.
    #: One pair is held by rule instead: a free Stephens block locks
    #: ``lor_strain`` and takes its place as Y's twin, flat exactly at its
    #: isotropic seed and near it after, so Y is listed here with the block's
    #: columns; a held block pins Y like a held ``lor_strain``.  The test reads
    #: no bound, so a specimen width that ends on its floor of 0 stays paired
    #: with a held instrument term.  Asked at stage start and again before a
    #: second solve, never released inside the stage.
    #:
    #: ``None`` means a result stored before the field.  Every runner writes a
    #: mapping, and an empty one is a stage that held nothing on this test.
    width_twins_held: dict[str, list[str]] | None = None
    #: paths held at stage start and **released within the same stage**: the
    #: phase rose above support while the stage solved, so the hold was lifted
    #: and the stage solved a second time (once — never a third) with them
    #: free.  They refined in this stage, which is why they are not in
    #: :attr:`held`; the cost of both solves is in :attr:`n_iterations`, and
    #: :attr:`cost_initial` is still the cost the stage started at.
    released: list[str] = Field(default_factory=list)
    #: per three-DOF moment site whose azimuth this stage held as part of a
    #: flat **combination** of its two angles (issue #599) — a uniaxial powder
    #: on axes whose frame pole is not the unique axis, R-3m:R about [111] —
    #: the flat rotation axis, as crystal-axis components of a unit vector in
    #: the magCIF unit-vector metric.  Keyed by site (``phases.i.atoms.j``).
    #: A site whose azimuth is flat on its own (the P4/mmm case) is not here.
    #: Empty on every fit where no such site was held.
    moment_flat_axes: dict[str, list[float]] = Field(default_factory=dict)
    #: the sites of :attr:`moment_flat_axes` whose moment the stage **turned**
    #: about that axis, onto the meridian through it, before holding the
    #: azimuth — a move the data cannot see, checked against the
    #: flat-direction floor before it was written, and the one correction
    #: here that changes the direction a fit reports.  A site in
    #: :attr:`moment_flat_axes` and not here was held where it was, because
    #: the turned moment did not reproduce the pattern to that floor.
    moment_turned: list[str] = Field(default_factory=list)
    #: paths this stage's ``turn_on`` matched and did **not** free, because
    #: the caller had declared a hold on them (WP-1435,
    #: ``Refinement.hold``).  The record of which declaration won: a plan's
    #: glob loses to a hold, and before this the glob won in silence while
    #: the model still read ``vary=False``.
    #:
    #: Disjoint from :attr:`freed` (a blocked path never entered it) and from
    #: :attr:`held`, which is WP-1301's separate thing — a *stage's* reading
    #: of what the data can see, decided per stage and lifted at the next.
    #: This one is the caller's, and it persists until ``unhold``.
    #:
    #: Empty on every fit where no hold was declared, which is every fit that
    #: predates this field.  It feeds ``HOLD_BLOCKED_PLAN``.
    blocked_by_hold: list[str] = Field(default_factory=list)
    #: the **literal** paths, and the retired spellings, in this stage's
    #: ``turn_on`` that name no parameter of the model, in plan order
    #: (WP-1414, issue #265).  A literal is a ``turn_on`` entry with no
    #: ``*``, ``?`` or ``[``: it names one parameter,
    #: so missing it is a typo or a renamed path, and whatever the stage was
    #: meant to refine was not.  A *pattern* that matched nothing is not here,
    #: because that is how the shipped plans reach components a model may not
    #: declare, unless it is written under a spelling a release retired
    #: (``instrument.background_peaks.*``, WP-1102), which can only be a
    #: rename the plan missed; nor is a row that exists and was declined (locked, tied or
    #: held), which :attr:`freed` omits and ``ParameterRow.held_because``
    #: explains.  On a joint fit, known means a bare path of some histogram or
    #: a scoped ``hist.h.…`` one.  It feeds ``STAGE_PATH_UNKNOWN``.
    #:
    #: **``None`` means nobody looked**, and every runner writes a list, so an
    #: empty one is a stage that was checked and named nothing missing.  The
    #: default is for a result stored before this field: a typo'd literal
    #: freed nothing in silence then too, so ``[]`` there would claim a check
    #: that never ran (WP-1076's rule; ``RefinedParameter.at_bound`` is the
    #: precedent).  Writers: the three runners that build a ``StageResult``.
    unknown_paths: list[str] | None = None
    #: joint fits only: per histogram this stage's globs **reached elsewhere
    #: and not there**, the globs that did (WP-1414, issue #265's comment).
    #: Keyed by histogram index.  Histogram ``h`` is here when no glob
    #: addressing it matched any of its rows while one of those globs matched
    #: another histogram's — ``instrument.profile.*`` freeing the
    #: constant-wavelength histogram and nothing on a bank.  A glob scoped to
    #: another histogram (``hist.0.…``) does not address ``h``, and a row that
    #: exists but is locked, tied or held counts as reached, so a deliberate
    #: plan stays out of it.  Written ``{}`` by a single-histogram fit, where
    #: there is no elsewhere to have reached, and ``None`` — nobody looked —
    #: only on a result stored before the field, for :attr:`unknown_paths`'
    #: reason.  It feeds ``STAGE_FREED_NOTHING``.
    unreached_histograms: dict[int, list[str]] | None = None
    #: each row this stage lifted before solving, and the value it started at
    #: in column units (WP-1930).  Two writers put a row here.  The stage's own
    #: :attr:`~rietx.strategy.staged.Stage.seed`, through
    #: :meth:`~rietx.params.vector.ParameterTable.seed_floored`, starts a
    #: freed row sitting exactly on a floor of 0 or above at the seed.  Its
    #: :attr:`~rietx.strategy.staged.Stage.strain_seed`, through
    #: :meth:`~rietx.params.vector.ParameterTable.seed_stephens`, puts a freed
    #: all-zero Stephens block on the isotropic ray, and every DOF of that block
    #: is here at the value the seed wrote, a zero coefficient of the ray
    #: included (WP-2002, B14).  Those rows sit at zero rather than on a floor,
    #: since a Stephens DOF is unbounded below.  The joint fit's runner seeds
    #: no Stephens block, so its stages carry the first writer's rows alone.
    #: WP-1930's floor seed sized by unit went with WP-1938: it existed because
    #: a softplus column at its floor was twelve orders below its neighbours,
    #: and a row refined in its own units has its physical column there.
    #: ``None`` means a result stored before the field; all three runners write
    #: a mapping, and an empty one is a stage that lifted nothing.  A result
    #: stored before B14 lacks the Stephens rows of a stage that seeded them.
    seeded: dict[str, float] | None = None
    #: the stationary-angle test the stage's covariance ran (WP-1929), one
    #: :class:`MomentAngleTest` per round in the order they ran.  A round with
    #: ``zeroed`` set names the angles whose columns left the covariance: they
    #: stayed free, kept their values and carry no esd.  Its writer is the
    #: solve (``LSQOutcome.moment_angle_tests``), copied here unchanged by all
    #: three runners.  ``None`` means no test ran: no moment angle was free
    #: beside its free modulus, the stage computed no covariance, or the result
    #: was stored before the field.  It feeds ``MOMENT_ANGLE_STATIONARY``.
    moment_angle_tests: list[MomentAngleTest] | None = None
    #: the free cell parameters this stage **put back** at the values it
    #: started from, because a cell parameter of their phase left the safety
    #: window while the stage solved (±15 % on a length, ±6° on an angle:
    #: ``params.vector.CELL_SAFETY_FRACTION``; WP-2002, B8).  The phase's whole
    #: free cell goes back, a parameter that stayed inside the window included.
    #: Found after the stage's first solve, the cell is held and the stage
    #: solves once more without it, the collapse's path (WP-1301), and the next
    #: stage frees it again.  Found after that second solve, there is no third:
    #: the value goes back, the column stays free in the answer, and its esd is
    #: withheld.  ``CELL_RUNAWAY`` names the paths and says which happened.
    #:
    #: Disjoint from :attr:`freed` and from :attr:`held`: a path the collapse
    #: also holds is in ``held``.  Writers: the three runners that build a
    #: ``StageResult``, ``Refinement.fit`` and ``Refinement.run_stage`` from
    #: ``Refinement._run_stage``'s record, and ``MultiHistogramRefinement.fit``
    #: from its own stage loop.  ``None`` means a result stored before the
    #: field; every runner writes a list, and an empty one is a stage that put
    #: nothing back, which is every stage of an ordinary fit.
    cell_reset: list[str] | None = None
    #: the free parameters this stage **restored** to the values it started
    #: from and held, because the answer of its first solve found them flat
    #: (WP-1301, B1; recorded since WP-2002, B14).  Two readings of the answer
    #: put a column here, and both take the same restore, hold and one second
    #: solve.  A column moving only phases whose scale is under the plan's
    #: ``phase_support_sigma`` there collapsed with its phase.  A moment
    #: direction whose turn no longer moves the pattern went flat while the
    #: stage ran.  The first solve's values for them were the walk, not a
    #: measurement, and are gone.
    #:
    #: A subset of :attr:`held`, which also carries the columns held at stage
    #: start, so a column in ``held`` and not here was held before anything
    #: solved.  Disjoint from :attr:`released`, from :attr:`freed` and from
    #: :attr:`cell_reset`: a cell the runaway reset and the collapse both reach
    #: is here.  Writers: the three runners that build a ``StageResult``,
    #: ``Refinement.fit`` and ``Refinement.run_stage`` from
    #: ``Refinement._run_stage``'s record, and ``MultiHistogramRefinement.fit``
    #: from its own stage loop.  ``None`` means a result stored before the
    #: field; every runner writes a list, and an empty one is a stage whose
    #: answer restored nothing, which is every stage of an ordinary fit.
    collapsed: list[str] | None = None

    @model_validator(mode="before")
    @classmethod
    def _drop_floor_unseeded(cls, value: Any) -> Any:
        """Open a result stored while the floor seed existed (WP-1930 to 1938).

        ``floor_unseeded`` named the freed softplus rows that seed could not
        size, and fed ``SOFTPLUS_FREED_AT_FLOOR``.  Both went with the seed
        (WP-1938), so nothing writes the field and nothing could read it.  A
        stored value is dropped rather than refused under ``extra="forbid"``,
        because old documents open.
        """
        if isinstance(value, dict) and "floor_unseeded" in value:
            value = dict(value)
            value.pop("floor_unseeded")
        return value


class HistogramResult(Base):
    """One pattern's slice of a multi-histogram joint refinement.

    A joint fit stacks several patterns into one residual (Von Dreele, 1997,
    J. Appl. Cryst. 30, 517), so a *single* pooled Rwp would hide a
    badly-fitting histogram — the failure mode this package's reporting exists
    to prevent.  Each histogram therefore reports its **own** agreement indices
    and curves here; ``RefinementResult.statistics`` stays the pooled number,
    never quoted alone.  Empty ``RefinementResult.histograms`` ⇒ an ordinary
    single-histogram fit (backward compatible).

    ``weight`` is the inter-histogram relative weight applied to this
    histogram's residual block (1.0 = unit weight, each point's own esd
    governs); it is also recorded in ``Provenance.notes`` so a non-unit
    weighting is never silent.
    """

    label: str = ""
    weight: float = 1.0
    statistics: Statistics
    two_theta: list[float] = Field(default_factory=list)
    y_obs: list[float] = Field(default_factory=list)
    y_calc: list[float] = Field(default_factory=list)
    y_background: list[float] = Field(default_factory=list)
    sigma: list[float] = Field(default_factory=list)
    ticks: dict[str, list[float]] = Field(default_factory=dict)
    #: Which reflection each of those ticks is, index for index, as the orbit
    #: representative ``h k l`` (WP-1438).  A **companion**, not a change of
    #: shape: :attr:`ticks` has four readers that want a list of positions and
    #: none of them wants this, so the pairing is by index and
    #: ``tests/test_ticks.py`` pins the two lengths equal per phase.
    #:
    #: Absent for a phase's key rather than empty when there is nothing to
    #: say, which is the case the reserved declared-peaks key is in: a peak
    #: somebody declared by centre has no Miller index, and ``[]`` there would
    #: claim it had none *of its own*.
    #:
    #: Every emission line's tick is here, so one representative appears once
    #: per line — the same reflection, imaged twice, which is what the reader
    #: hovering a Kα2 tick wants to be told.
    #:
    #: A satellite (WP-1326) is ``[h, k, l, m]`` — its parent H and its order —
    #: because H alone does not identify it; a nuclear row keeps three.
    tick_hkl: dict[str, list[list[int]]] = Field(default_factory=dict)
    qpa: "QuantitativePhaseAnalysis | None" = None
    restraints: "RestraintReport | None" = None
    #: this histogram's own R_Bragg/R_F — the partition is of *these* counts
    phase_agreement: list[PhaseAgreement] = Field(default_factory=list)
    diagnostics: list[Diagnostic] = Field(default_factory=list)


# ----------------------------------------------------------------------
# The termination view (WP-1302) — shared projections, never a re-derivation.
# ``Refinement.summary()`` (refine.py) reuses these three for the rows a bare
# result already carries, and adds the rows that need the compiled model
# (Layer 1, suggest, a deliverable) around them.
# ----------------------------------------------------------------------
def _stage_lines(stages: list[StageResult], max_shift_over_esd: float | None) -> list[str]:
    """Section 1: per-stage status, and the last stage's convergence number.

    ``max_shift_over_esd`` (McCusker et al. 1999 §7) is the answer-producing
    solve's own number, not one per stage — ``Statistics`` carries it exactly
    once, on the fit as a whole.
    """
    lines = []
    for i, s in enumerate(stages):
        ftol = f"{s.ftol:.0e}" if s.ftol is not None else "solver default"
        line = f"  stage {s.name}: {s.status} ({s.n_iterations} evals, ftol={ftol})"
        if i == len(stages) - 1 and max_shift_over_esd is not None:
            line += f", max|Δθ|/esd={max_shift_over_esd:.3f}"
        lines.append(line)
    return lines


#: Above this many *distinct* pairs, a printed diagnostics list stops growing
#: and names the rest as one count instead (WP-1302). Display-only: it caps
#: what `_diagnostic_lines` renders, never `RefinementResult.diagnostics`
#: itself — `sequential._persistent_diagnostics` counts `HIGH_CORRELATION`
#: occurrences across a whole series from that stored list, and a pair
#: ranked just outside the top ten in every pattern must still be countable
#: as "N of M" there even though no single pattern's *printed* view shows it.
#: 10 is not tuned: it is "more than a reader scans, fewer than a reader
#: ignores".
HIGH_CORRELATION_MAX = 10


#: The pair-keyed codes :func:`_cap_high_correlation` bounds, each as
#: ``(code, its omitted-count code, what one row is called)``.
#:
#: **Each gets its own budget of** :data:`HIGH_CORRELATION_MAX`, never a shared
#: one.  A flat direction emits a ``FLAT_DIRECTION`` *and* the
#: ``HIGH_CORRELATION`` it sharpens (WP-1311), and both carry |ρ| ≈ 1, so one
#: budget would make them compete for the same ten slots on a key that cannot
#: separate them — which of the two survives would then be decided by sort
#: stability rather than by anything about the fit.
_CAPPED_PAIR_CODES = (
    ("HIGH_CORRELATION", "HIGH_CORRELATION_OMITTED", "correlated pair"),
    ("FLAT_DIRECTION", "FLAT_DIRECTION_OMITTED", "flat direction"),
)


def _cap_one_code(diagnostics: list[Diagnostic], code: str, omitted_code: str,
                  noun: str) -> list[Diagnostic]:
    """One code's rows bounded at :data:`HIGH_CORRELATION_MAX`, worst |ρ| first."""
    is_hit = [d.code == code for d in diagnostics]
    if sum(is_hit) <= HIGH_CORRELATION_MAX:
        return diagnostics
    hits = sorted((d for d, hit in zip(diagnostics, is_hit) if hit),
                  key=lambda d: abs(d.value) if d.value is not None else 0.0,
                  reverse=True)
    kept, omitted = hits[:HIGH_CORRELATION_MAX], hits[HIGH_CORRELATION_MAX:]
    out = [d for d, hit in zip(diagnostics, is_hit) if not hit]
    last_hit = max(i for i, hit in enumerate(is_hit) if hit)
    insert_at = sum(not hit for hit in is_hit[:last_hit + 1])
    out[insert_at:insert_at] = [*kept, Diagnostic(
        level="info", code=omitted_code, where=[],
        value=float(len(omitted)),
        message=f"{len(omitted)} more {noun}(s) below the "
                f"{HIGH_CORRELATION_MAX} shown here, weaker than all of them.",
        suggestion="Read result.identifiability for the full correlation "
                   "matrix and top_correlations list.",
    )]
    return out


def _cap_high_correlation(diagnostics: list[Diagnostic]) -> list[Diagnostic]:
    """Bound each pair-keyed code at :data:`HIGH_CORRELATION_MAX`, worst first,
    for **rendering only** — see that constant's docstring for why this must
    never be applied to a stored diagnostics list.

    Every other code passes through untouched and in place; a bounded code's
    entries are pulled out, ordered by |ρ|, truncated, and the survivors
    appended where the last one used to sit.  Which codes, and why each has its
    own budget: :data:`_CAPPED_PAIR_CODES`.
    """
    for code, omitted_code, noun in _CAPPED_PAIR_CODES:
        diagnostics = _cap_one_code(diagnostics, code, omitted_code, noun)
    return diagnostics


#: What ``summary(deliverable=…)`` accepts, on a result and on a series alike
#: (the agent skill §4b's four purposes).  Data rather than two literal lists:
#: :meth:`rietx.refine.Refinement.summary` implements the first three and
#: :meth:`rietx.schemas.sequential.SeriesResult.summary` the fourth, and each
#: refuses the other's by naming where it lives — a vocabulary neither owns.
DELIVERABLES = ("phase_id", "qpa", "structure", "series")


def _diagnostic_lines(diagnostics: list[Diagnostic]) -> list[str]:
    """Section 2a: the first stop condition — every diagnostic, resolved or not.

    Present even at zero (WP-1302's acceptance: the stop-condition lines are
    on *every* fit, including one with nothing to report), so a caller never
    has to distinguish "no diagnostics" from "this section did not run".

    The header count is the *stored* list's — accurate, uncapped; only the
    rows actually printed below are bounded (:func:`_cap_high_correlation`),
    so "23 unresolved" can be followed by fewer than 23 lines without lying
    about how many there are.
    """
    if not diagnostics:
        return ["  diagnostics: none"]
    lines = [f"  diagnostics: {len(diagnostics)} unresolved"]
    for d in _cap_high_correlation(diagnostics):
        lines += [f"    {line}" for line in str(d).splitlines()]
    return lines


def _parametric_lines(coefficients: list[ParametricCoefficient] | None,
                      form: list[ParametricFormTest] | None = None,
                      joint: ParametricFormReading | None = None) -> list[str]:
    """The coefficients of a joint fit's parametric declarations (WP-1325).

    Nothing for ``None``, which is "no declaration": the block is the answer
    of a parametric fit, so it is absent where none was asked for rather than
    printed empty.  One line per declaration names its target and reference,
    then one line per term in the caller's units, so the intercept reads as
    the target *at the reference* and never as an extrapolation to zero.  A
    term with no esd says which of the two reasons holds.  The declaration's
    form test closes it, when ``form`` has one, and the joint reading of
    every tested declaration closes the block.
    """
    if coefficients is None:
        return []
    from .._display import _number

    tests = {t.equation: t for t in form or []}
    lines = ["  parametric coefficients (user units, at each reference):"]
    names = list(dict.fromkeys(c.equation for c in coefficients))
    for equation in names:
        terms = [c for c in coefficients if c.equation == equation]
        ref = ("" if not terms[0].reference else " at " + ", ".join(
            f"{k}={v:g}" for k, v in terms[0].reference.items()))
        lines.append(f"    {equation}: {terms[0].target}{ref}")
        for c in terms:
            if not c.vary:
                value = f"{_number(c.value)} (not free at the answer)"
            elif c.esd is None:
                value = f"{_number(c.value)} (no esd: unmeasured)"
            else:
                value = _number(c.value, c.esd)
            unit = f" {c.unit}" if c.unit else ""
            lines.append(f"      [{c.term}] {value}{unit}")
        if equation in tests:
            lines.append(_form_line(tests[equation]))
    if joint is not None:
        n = sum(t.others_freed is not None for t in form or [])
        lines.append(f"    the {n} tested equations together: form {_verdict(joint)}")
    return lines


def _form_line(t: ParametricFormTest) -> str:
    """One declaration's form test, as :func:`_parametric_lines` closes it."""
    over = f"over {t.n_patterns} of {t.n_subset} patterns"
    tied, freed = t.tied, t.others_freed
    if tied is None:
        return "      form not tested: a coefficient was not free at the answer"
    if freed is None:
        if tied.statistic is None and tied.dof == 0:
            return (f"      form not tested: the {t.n_patterns} of its {t.n_subset} "
                    "patterns that see the target add no direction beyond the "
                    "coefficients")
        if tied.statistic is None:
            return ("      form not tested: the answer's χ²_red is not a "
                    "positive finite number")
        return f"      form {_verdict(tied)} {over}"
    # the freed reading is the verdict, so it reads first
    verdict = {True: "REJECTED", False: "not rejected", None: "not tested"}[t.rejected]
    line = (f"      form {verdict} {over}:"
            f"\n        with the other equations freed, {_verdict(freed)}"
            f"\n        with the other equations tied, {_verdict(tied)}")
    if t.provisional_on:
        names = ", ".join(repr(n) for n in t.provisional_on)
        line += (f"\n        provisional: {names} rejected too, and moved the answer this "
                 "reading steps from; read it again after fixing and refitting")
    return line


def _verdict(r: ParametricFormReading) -> str:
    """One reading's verdict, statistic, cut, p-value and directions."""
    if r.statistic is None:
        # the schema's two reasons, as the one-reading line above tells them
        return ("not tested: no direction to test" if r.dof == 0 else
                "not tested: the answer's χ²_red is not a positive finite number")
    verdict = "REJECTED" if r.rejected else "not rejected"
    side = "past" if r.rejected else "within"
    # a tail under 1e-300 is 0.0 in a double, and "p = 0" claims certainty
    p = "p < 0.001" if r.p_value < 1e-3 else f"p = {r.p_value:.2g}"
    return (f"{verdict}: {r.statistic:.1f} {side} the cut {r.cut:.1f} ({p}) "
            f"for {r.dof} directions")


def _provenance_line(provenance: Provenance) -> str:
    """The provenance clause of section 4 — the only part of it a bare
    result can answer (the rest needs the compiled model: held paths, the
    plan, N reflections)."""
    return (f"  provenance: rietx {provenance.package_version}, "
            f"backend={provenance.backend}, solver={provenance.solver}")


def _agreement_line(stats: Statistics) -> str:
    """Section 5: agreement indices last, Rwp beside Rexp — their ratio is GoF."""
    line = (f"  Rwp {stats.rwp:.4f} / Rexp {stats.rexp:.4f} (GoF {stats.gof:.2f}), "
            f"Rp {stats.rp:.4f}, χ² {stats.chi2:.1f}")
    if stats.durbin_watson is not None:
        line += f", DW {stats.durbin_watson:.2f}"
    return line


#: What :attr:`RefinementResult.n_extra_components` was called in v1.2, kept as
#: the one spelling of the legacy name the way
#: ``schemas.instrument._LEGACY_COMPONENT_FIELD`` is for the field it renames.
_LEGACY_COUNT_FIELD = "n_background_peaks"


class RefinementResult(Base):
    """What a fit returns: the answer, its statistics, and what the engine
    found wrong with it.

    **``status`` is the optimiser's exit and nothing else.**  ``"converged"``
    says the solver met its stopping test; it makes **no claim that the fit is
    any good**, and a model that matches nothing can converge — driving a
    phase scale to zero *is* a minimum (issue #243: ``converged`` at Rwp
    84–235 % beside ``MODEL_FAR_FROM_DATA``).  The vocabulary is
    :class:`StageResult`'s three solver terminations, for the reason its
    docstring gives, which is why a fourth member such as
    ``"converged_with_findings"`` is not how this is said.

    **Quality is** :attr:`diagnostics`' **channel.**  Branch on the codes; a
    ``"warning"`` is a finding to answer before quoting what it names, and an
    ``"error"`` means the parameter values and esds are not a refinement of
    this model.  :attr:`usable` is the one-line reading of both channels a
    batch driver wants: ``status == "converged"`` and no diagnostic at level
    ``"error"``.  It is a gate against the unusable, not a certificate of the
    rest — a ``True`` fit still owes an answer to each of its warnings.
    """

    #: ``result.rwp`` is the single most expensive miss in WP-1110's evidence,
    #: because of *when* it fires: the ``AttributeError`` arrived after a
    #: 105 s refinement had completed, and took it with it — see
    #: ``Base.__getattr__``. This is the class calls it commonly bind to.
    _attr_hint_name: ClassVar[str | None] = "result"

    status: Literal["converged", "max_iter", "diverged"]
    mode: Mode
    parameters: list[RefinedParameter]
    statistics: Statistics
    stages: list[StageResult] = Field(default_factory=list)
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    provenance: Provenance

    # Where this result sits in the refinement history DAG (None when the
    # refinement was run with history disabled).
    node_id: str | None = None
    tree_id: str | None = None

    # Arrays for plotting/export (kept as lists for JSON round-trip; use
    # the exporters for column files).
    two_theta: list[float] = Field(default_factory=list)
    y_obs: list[float] = Field(default_factory=list)
    y_calc: list[float] = Field(default_factory=list)
    y_background: list[float] = Field(default_factory=list)
    # per-point σ actually used in the fit (file esds when present, Poisson
    # fallback otherwise) — the FitReport weights with these, never re-derives
    sigma: list[float] = Field(default_factory=list)
    # per-phase reflection tick positions (deg 2θ), where the model draws each
    # peak: Bragg angle plus zero and the geometry's shift (WP-1908)
    ticks: dict[str, list[float]] = Field(default_factory=dict)
    #: Which reflection each of those ticks is, index for index, as the orbit
    #: representative ``h k l`` (WP-1438).  A **companion**, not a change of
    #: shape: :attr:`ticks` has four readers that want a list of positions and
    #: none of them wants this, so the pairing is by index and
    #: ``tests/test_ticks.py`` pins the two lengths equal per phase.
    #:
    #: Absent for a phase's key rather than empty when there is nothing to
    #: say, which is the case the reserved declared-peaks key is in: a peak
    #: somebody declared by centre has no Miller index, and ``[]`` there would
    #: claim it had none *of its own*.
    #:
    #: Every emission line's tick is here, so one representative appears once
    #: per line — the same reflection, imaged twice, which is what the reader
    #: hovering a Kα2 tick wants to be told.
    #:
    #: A satellite (WP-1326) is ``[h, k, l, m]`` — its parent H and its order —
    #: because H alone does not identify it; a nuclear row keeps three.
    tick_hkl: dict[str, list[list[int]]] = Field(default_factory=dict)

    # Quantitative phase analysis (weight fractions); computed for Rietveld
    # fits, None for Le Bail (its scales are degenerate).
    qpa: QuantitativePhaseAnalysis | None = None

    # Structure-sensitive agreement indices, one row per phase (WP-1069) —
    # see :class:`PhaseAgreement`.  Empty outside Rietveld mode, where the
    # partition would be circular, and empty for a result not built by a fit.
    phase_agreement: list[PhaseAgreement] = Field(default_factory=list)

    # The spherical-harmonics texture's evidence, one row per textured phase
    # (WP-1960) — see :class:`PhaseTexture`.
    texture: list[PhaseTexture] = Field(default_factory=list)

    # Observation/parameter evidence (WP-1071) — see :class:`DataSupport`.
    # Present for anything with a compiled model behind it, ``replay``
    # included.  None for a joint multi-histogram fit, which would need one
    # count per histogram, and for a result recorded before v1.0 — the
    # ``identifiability`` convention: read None as "not measured here".
    data_support: DataSupport | None = None

    # Cylindrical absorption (WP-0501); None unless a capillary µR was given or
    # estimable.  Carries the equivalent Biso bias, because that — not Rwp — is
    # what the correction buys.
    absorption: AbsorptionCorrection | None = None

    # Soft-restraint summary (bond/angle/value deviations, pooled restraint χ²);
    # present only when a phase declared restraints (Rietveld-only), None
    # otherwise.  Deviations in units of σ surface an over-tight restraint
    # fighting the data even while Rwp looks good.
    restraints: RestraintReport | None = None

    # Bonding geometry with esds propagated through the full covariance
    # (WP-1072) — see :class:`GeometryTable`.  Rietveld-only, and None when the
    # result did not come from a fit that had a compiled model to search.
    geometry: GeometryTable | None = None

    # Each phase's cell volume with its esd through the cell covariance
    # (WP-1933), in every mode, since a Le Bail cell is a measurement too —
    # see :class:`CellVolume`.  None when the result did not come from a fit.
    cell_volumes: list[CellVolume] | None = None

    # Coherent domain size and microstrain as physical numbers (WP-1131) — see
    # :class:`PhaseMicrostructure`.  A carrier for the same reason ``geometry``
    # is: the esds come from the covariance read off the final Jacobian, which
    # is never serialized.  Empty when the fit had no compiled model to read a
    # wavelength and phase names from.
    microstructure: list[PhaseMicrostructure] = Field(default_factory=list)

    # Degeneracy evidence measured on the final Jacobian, which is never
    # serialized — see :class:`Identifiability`.  None when the result did not
    # come from a fit that ran the guards.  It follows that a *stored* result
    # can carry this but never recompute it (WP-1003, recording 1055): a
    # report built from a deserialized result quotes what fit time measured
    # or shows the section absent, and nothing re-derives it from the curves.
    identifiability: Identifiability | None = None

    #: The coefficients of every parametric declaration a joint fit refined
    #: (WP-1325, :class:`~rietx.schemas.parametric.ParametricEquation`), each in the
    #: caller's units at the declaration's reference, with its esd from the
    #: joint covariance or ``None`` where that gives it none.  ``None`` means
    #: no parametric equation was declared — never "declared, and nothing to say",
    #: which a declaration cannot be.  One writer:
    #: ``MultiHistogramRefinement._build_result``.
    parametric: list[ParametricCoefficient] | None = None

    #: Whether each parametric declaration's form survives the data, one
    #: :class:`~rietx.schemas.parametric.ParametricFormTest` per declaration,
    #: in declaration order (WP-1325).  ``None`` exactly when
    #: :attr:`parametric` is.  One writer:
    #: ``MultiHistogramRefinement._build_result``.
    parametric_form: list[ParametricFormTest] | None = None

    #: The form test of every tested parametric declaration at once
    #: (WP-1325): the χ² freeing each tested equation's target in every pattern
    #: would remove, as one
    #: :class:`~rietx.schemas.parametric.ParametricFormReading`.  Two equations
    #: whose targets move the pattern alike can each pass with the other freed
    #: while both are wrong; this reading sees that, and names no equation.
    #: ``None`` unless two or more declarations were tested.  One writer:
    #: ``MultiHistogramRefinement._build_result``.
    parametric_form_joint: ParametricFormReading | None = None

    #: Each parametric declaration as the fit resolved it, with its
    #: coefficients' covariance in the caller's units, one
    #: :class:`~rietx.schemas.parametric.RefinedParametricEquation` per declaration in
    #: declaration order (WP-1325).  :meth:`parametric_value` evaluates one at
    #: any coordinate.  ``None`` exactly when :attr:`parametric` is, and on a
    #: result written before schema 0.57.  One writer:
    #: ``MultiHistogramRefinement._build_result``.
    parametric_equations: list[RefinedParametricEquation] | None = None

    # How many explicit :class:`~rietx.schemas.instrument.HumpComponent` terms
    # this fit declared — the other half of "how flexible was the background":
    # :class:`Identifiability`'s absorption table says what the background could
    # imitate, this says with how many free peaks it was allowed to do it (N
    # peaks are 3N parameters with unconstrained positions), and a reader
    # comparing two Rwp values has to be able to see them.
    #
    # It sits **here and not on** :class:`Identifiability`, whose members are
    # read off the final Jacobian and therefore exist only where a solve
    # measured them.  This is not a measurement: it is
    # ``len(CompiledModel.component_paths)``, a count of what the instrument
    # *declared*, available wherever a compiled model is.  Behind that carrier's
    # guard it read 0 — "none declared" — on every ``replay``, which is a
    # different claim from the true one and the reason it moved.  Read off the
    # frozen compile state rather than counted from ``parameters``: a peak
    # declared and never freed is still freedom the caller granted, and it would
    # not appear there.
    #
    # ``0`` therefore means none was declared, exactly off; ``None`` means
    # nothing here counted — the ``data_support`` convention, and for the same
    # reason, a joint multi-histogram fit (one count per histogram, reported
    # through each histogram) or a result recorded before the feature existed.
    n_extra_components: int | None = None
    #: How many of those are **background-landing** — humps, in v1.4's
    #: vocabulary (WP-1103).  Equal to :attr:`n_extra_components` until the seam
    #: gained a second member, and a separate number now because the two answer
    #: different questions: that one is "what did I declare", this one is "how
    #: much *background* flexibility was granted", which is what a reader
    #: comparing two Rwp values needs and what
    #: :attr:`Identifiability.background_absorption` screens.  A declared sharp
    #: peak is in the first and not the second.
    #:
    #: Written from ``len(CompiledModel.component_paths)``, the frozen compile
    #: state, on the same terms as the count above — declared, not measured, so
    #: a ``replay`` carries it.  ``None`` means nothing counted, never "none
    #: declared", which is ``0``.
    n_background_components: int | None = None

    @model_validator(mode="before")
    @classmethod
    def _migrate_v1_2_n_background_peaks(cls, value: Any) -> Any:
        """Read a 1.2-era ``n_background_peaks`` count under its new name.

        The second half of WP-1102's rename, and the half the textual repair in
        :mod:`rietx.schemas.migrate` cannot reach: ``n_background_peaks`` has no
        word boundary before ``background_peaks``, and a saved result is read at
        a fourth point (``rietx html <result.json>``) that is not one of that
        module's :data:`~rietx.schemas.migrate.READ_POINTS`.  Without this, a
        result JSON written by v1.2 raises ``extra_forbidden`` on open, which is
        the direction the repo does **not** break in: old documents open.

        A count, not a path, so it is repaired at the schema exactly the way
        ``Instrument._migrate_v1_2_background_peaks`` repairs the field: an
        explicit new-name value wins, the legacy key being a leftover then.
        """
        if isinstance(value, dict) and _LEGACY_COUNT_FIELD in value:
            value = dict(value)
            legacy = value.pop(_LEGACY_COUNT_FIELD)
            value.setdefault("n_extra_components", legacy)
        # ``n_background_components`` landed in v1.4 beside a second union
        # member.  Before it, every declared component *was* background, so a
        # document that counted one and not the other is telling us both — and
        # without this the count silently disappears from
        # ``report.background.n_peaks`` the moment an older result is reopened,
        # which is the ``None``-means-nothing-counted lie one field over.  A
        # v1.4 writer always states both (0 included), so this never overrides
        # a real answer.
        if (isinstance(value, dict)
                and value.get("n_extra_components") is not None
                and value.get("n_background_components") is None):
            value = dict(value)
            value["n_background_components"] = value["n_extra_components"]
        return value

    # Per-histogram slices of a multi-histogram joint refinement (WP-0308);
    # empty for an ordinary single-histogram fit.  ``statistics`` above is then
    # the pooled combined number and ``two_theta``/``y_*`` mirror histogram 0.
    histograms: list[HistogramResult] = Field(default_factory=list)

    @property
    def usable(self) -> bool:
        """Whether this fit can be read at all (WP-1336): the solver converged
        **and** no diagnostic carries level ``"error"``.

        An expression over :attr:`Diagnostic.level`, never a list of codes
        (WP-1037's rule for a derived flag): an error-level code added later is
        counted the day it is written, with nothing here to edit.  ``False``
        means do not read the values; ``True`` is not a pass — the warnings
        still name what each number may not be quoted as (class docstring).
        """
        return (self.status == "converged"
                and not any(d.level == "error" for d in self.diagnostics))

    # -- numpy views -------------------------------------------------------
    def sig(self) -> np.ndarray:
        """Per-point σ for this result — **the one authority** (WP-1029 (s)).

        Every weighted residual in the package divides by this: the matplotlib
        panel, the ``write_html`` page, the VLM montage, Layer 0 and the GUI's
        curves routes.  They each open-coded it once, with three
        different policies, and agreed only because the disagreement lived in
        branches a modern result never takes.

        Normally this is a plain lookup rather than a computation, and that is
        the point: ``CompiledModel.sigma`` is what the stage weighted by, and
        ``refine`` stores it here verbatim, so the esd-column/Poisson choice was
        already made once at stage compile.  That is :meth:`PatternData.sig` for
        every model but one — a background holding a measured curve with
        ``fixed_sigma`` adds the curve's own counting statistics at compile
        (σ² = σ_y² + s²·σ_f², WP-1309), so σ here is wider than the pattern's
        own and is still the one a caller must divide by.  Two conditioning
        steps remain, both for callers that are about to divide:

        * results recorded before v0.2 carry no σ at all, and get the same
          Poisson ``√max(y,1)`` fallback the fit itself would have used
          (CLAUDE.md, Weights);
        * non-positive entries are floored by :meth:`PatternData.sig`'s own
          rule, so a zero esd is a small σ rather than an ``inf`` that loses
          the whole trace.

        Note this says nothing about *where* σ came from: by the time a result
        exists, a file esd column and a Poisson estimate are the same array of
        floats.  ``DataRef.has_sigma`` is the fact that survives, and it is what
        the GUI and the text document both label the residual from.
        """
        if self.sigma:
            s = np.asarray(self.sigma, dtype=np.float64)
        else:
            s = np.sqrt(np.maximum(np.asarray(self.y_obs, dtype=np.float64),
                                   POISSON_FLOOR_COUNTS))
        return _floor_sigma(s)

    def for_histogram(self, h: int) -> "RefinementResult":
        """A single-histogram-shaped view of histogram ``h`` for reporting/plots.

        Swaps the top-level curves and statistics for histogram ``h``'s own and
        clears ``histograms``, so ``build_report(result.for_histogram(h))`` and
        ``result.for_histogram(h).plot()`` operate per pattern (reports are
        per-histogram — see :class:`HistogramResult`).

        Paths are spelled as a single fit spells them (WP-1341).  The joint
        result scopes a per-histogram row ``hist.<h>.``; the view keeps
        histogram ``h``'s rows, unscoped, and drops every other histogram's,
        in ``parameters`` and in the background screen alike.  A shared row
        keeps the joint result's value, which for a WP-1131 size term is the
        coefficient at histogram 0's wavelength.  A negative ``h`` counts from
        the end, as list indexing does.
        """
        if not self.histograms:
            if h == 0:
                return self
            raise IndexError("this result has no per-histogram slices")
        n = len(self.histograms)
        if not -n <= h < n:
            raise IndexError(f"histogram {h} of a {n}-histogram result")
        h %= n
        hr = self.histograms[h]
        prefix = f"hist.{h}."
        view = self.model_copy(deep=True)
        view.parameters = [
            p.model_copy(update={"path": p.path[len(prefix):]})
            if p.path.startswith(prefix) else p
            for p in view.parameters
            if p.path.startswith(prefix) or not p.path.startswith("hist.")]
        view.statistics = hr.statistics.model_copy(deep=True)
        # the joint solve's convergence figure belongs to the stages the view
        # keeps, so it travels with them (WP-1341)
        view.statistics.max_shift_over_esd = self.statistics.max_shift_over_esd
        view.two_theta = list(hr.two_theta)
        view.y_obs = list(hr.y_obs)
        view.y_calc = list(hr.y_calc)
        view.y_background = list(hr.y_background)
        view.sigma = list(hr.sigma)
        view.ticks = dict(hr.ticks)
        view.qpa = hr.qpa.model_copy(deep=True) if hr.qpa is not None else None
        view.restraints = (hr.restraints.model_copy(deep=True)
                           if hr.restraints is not None else None)
        view.diagnostics = list(hr.diagnostics)
        if view.identifiability is not None:
            # this histogram's background screen, as a single fit spells it
            # (WP-1341): the joint result scopes every row ``hist.<h>.``
            mine = {k[len(prefix):]: v for k, v in
                    view.identifiability.background_absorption.items()
                    if k.startswith(prefix)}
            view.identifiability = view.identifiability.model_copy(
                update={"background_absorption": mine})
        view.histograms = []
        return view

    def plot(self, path: str | None = None, **kw):
        from ..viz.plots import plot_result

        return plot_result(self, path=path, **kw)

    def parameter(self, path: str) -> RefinedParameter:
        for p in self.parameters:
            if p.path == path:
                return p
        raise KeyError(path)

    def parametric_value(self, equation: str, coordinates: dict[str, float] | None = None,
                         *, row: list[float] | None = None) -> ParametricValue:
        """A parametric equation's target at any coordinate, with its esd (WP-1325).

        ``equation`` names the declaration; ``coordinates`` maps each coordinate
        its polynomial uses to a value, in the coordinate table's units, and a
        ``design`` equation takes a ``row`` instead.  Reads the stored coefficients
        (:attr:`parametric`), their covariance and the resolved reference
        (:attr:`parametric_equations`), and the form test (:attr:`parametric_form`
        and :attr:`parametric_form_joint`), whose verdicts ride beside the value
        because the esd assumes the form.  At a pattern's own coordinates this is that pattern's
        ``hist.<h>.`` target row, value and esd.
        """
        if self.parametric_equations is None:
            raise ValueError(
                "this result carries no parametric equation to evaluate: it declared "
                f"none, or was written before {DIST_NAME} 1.10")
        declared = {r.equation.name: r for r in self.parametric_equations}
        if equation not in declared:
            raise KeyError(f"no parametric equation named {equation!r}; this result has "
                           f"{sorted(declared)}")
        coefficients = [c for c in self.parametric or [] if c.equation == equation]
        form = next((t for t in self.parametric_form or [] if t.equation == equation), None)
        return declared[equation].evaluate(coefficients, form, coordinates, row,
                                           joint=self.parametric_form_joint)

    def _repr_html_(self) -> str:
        """The termination view, then the refined parameters as a table
        (WP-1544). The text is what ``print`` gives; the table is the same
        numbers as ``parameters``."""
        from .._display import _number, diagnostics_html, pre_html, table_html
        rows = [(p.path, _number(p.value, p.stderr),
                 "" if p.at_bound is None else str(p.at_bound).lower())
                for p in self.parameters]
        header = ("path", "value", "at_bound")
        # an equation's column only where an equation set a row (WP-1325), so a fit that
        # declared none keeps its three columns
        if any(p.equations for p in self.parameters):
            header += ("equations",)
            rows = [(*row, ", ".join(p.equations or ()))
                    for row, p in zip(rows, self.parameters, strict=True)]
        table = table_html(header, rows) if rows else ""
        before, after = self._text_parts()
        before.append(_diagnostic_lines(self.diagnostics)[0])
        return (pre_html("\n".join(before))
                + diagnostics_html(_cap_high_correlation(self.diagnostics))
                + pre_html("\n".join(after)) + table)

    def __str__(self) -> str:
        """The termination view a bare result can answer (WP-1302): per-stage
        status, every diagnostic, provenance, agreement indices last.

        Not the full view — ``Refinement.summary()`` adds the rows that need
        the compiled model (Layer 1's summary sentence, the next suggestion,
        a deliverable's rows, the plan and held paths) around this one, in
        the order the agent skill §10's stop conditions declare.  This
        is what a caller holding only the result — the return value of
        ``fit()``, or one read back from a project — can print without it.
        """
        before, after = self._text_parts()
        return "\n".join(before + _diagnostic_lines(self.diagnostics) + after)

    def _text_parts(self) -> tuple[list[str], list[str]]:
        """The lines before the diagnostics and the lines after them, so the
        HTML view can fold each diagnostic between the two."""
        before = [f"RefinementResult: {self.status} ({self.mode})"]
        before += _stage_lines(self.stages, self.statistics.max_shift_over_esd)
        after = _parametric_lines(self.parametric, self.parametric_form,
                                  self.parametric_form_joint)
        after.append(_provenance_line(self.provenance))
        after.append(_agreement_line(self.statistics))
        return before, after
