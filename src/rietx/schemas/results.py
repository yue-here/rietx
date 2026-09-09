"""Refinement result schemas."""

from __future__ import annotations

from typing import ClassVar, Literal

import numpy as np
from pydantic import Field

from .common import Base, Diagnostic, Mode, Provenance


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
    source is interior.  Before WP-1076 the field was ``bool = False`` and
    nothing wrote it, so every row of every result asserted "not at a bound"
    about a parameter no code had looked at.

    **The source is the guard, never a local recomputation.**  The one place
    the bound test happens is :func:`rietx.strategy.staged.bound_findings`,
    whose findings become the ``BOUND_HIT`` diagnostics; this flag is a
    projection of that same list onto the rows, so the two can never
    disagree.  ``BOUND_HIT`` stays the reported channel — the flag exists so
    that an agent iterating ``parameters`` does not have to cross-reference
    ``diagnostics`` by path.
    """

    path: str
    value: float
    stderr: float | None = None
    vary: bool = True
    at_bound: bool | None = None


class Statistics(Base):
    """Agreement indices, defined per Toby (2006), Powder Diffraction 21, 67.

    Per-fit only: ``n_iterations`` is on :class:`~rietx.schemas.sequential.SeriesEntry`
    (a series has one count per pattern, not one pooled figure here), and an
    unmatched-peak count is the report's — ``FitReport.unmatched`` (rows) or
    ``StageReport.n_unmatched_obs``/``n_unmatched_calc`` (counts), never here.

    ``rwp_background_subtracted`` re-evaluates Rwp with the background removed
    from both y_obs and y_calc, which Toby recommends as the more meaningful
    number when the background is a large fraction of the signal.

    ``esd_inflation`` is the Bérar-Lelann serial-correlation factor
    (Bérar & Lelann, 1991, J. Appl. Cryst. 24, 1) — reported parameter esds
    have already been multiplied by it.  The estimator is conservative: even
    perfectly white residuals land at ≈1.51 (chance same-sign runs — see
    ``optimize.statistics.berar_lelann_factor``); lab data with unmodelled
    profile detail typically lands at 2-4.  Divide it out for raw
    χ²·(JᵀJ)⁻¹ esds.

    ``max_shift_over_esd`` is McCusker et al. (1999) §7's convergence
    quantity: the largest |Δθᵢ|/esd(θᵢ) over the final accepted step of the
    answer-producing solve, both sides in external parameter units (the
    transform chain makes internal-space ratios meaningless at finite step).
    The paper's band — converged when ≤ 0.1
    (``optimize.statistics.MAX_SHIFT_CONVERGED``) — is quoted, never tuned,
    and gates nothing; a TRF solve at ftol 1e-9 satisfies it a fortiori, so
    the information is on the other branch: a stage that stopped on
    ``STAGE_MAX_ITER`` reports how far it was still moving, in esd units.
    ``run_least_squares`` computes it, ``refine`` copies it, nothing else
    derives it (WP-1076).  ``None`` wherever it cannot be measured: no
    accepted step, no esds, an evaluate-only ``replay``, or the joint
    multi-pattern residual, which carries no writer yet.

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
    """One near-null direction of the scale-normalised normal matrix
    (WP-1056; Watkin, 2008, J. Appl. Cryst. 41, 491 §3.8 — the informative
    object is the *combination*, not the pair; Prince, *Mathematical
    Techniques* 3rd ed. ch. 8 — remedies are "linear combinations of
    parameters that are approximately eigenvectors of the Hessian matrix").

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
    """One held parameter's exchangeability with the fitted span (WP-1056).

    ``r2`` is the block projection R² of the held parameter's Jacobian
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
    history node (evaluate-only, no solve) or a joint multi-histogram fit,
    which screens per histogram and reports through each histogram's own
    diagnostics.  Read ``None`` as "not measured here", never as "no
    degeneracy".
    """

    background_absorption: dict[str, float] = Field(default_factory=dict)
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
    """Record of the specimen absorption applied — WP-0501 (cylinder), WP-0508
    (flat plate).

    Present only for Rietveld fits that actually carried a specimen dimension.
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


class RestraintRow(Base):
    """One soft restraint's computed-vs-target deviation (WP-0406).

    ``deviation_over_sigma`` is the headline: a restraint fighting the data
    shows up as |deviation/σ| ≫ 1 (and, past a threshold, a ``RESTRAINT_TENSION``
    diagnostic).  ``atoms`` (bond/angle) or ``path`` (value) names the target;
    exactly one is set.
    """

    phase_index: int | None = None
    kind: Literal["bond", "angle", "value"]
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
    contact_max: float = 0.0          # Å, the nonbonding search radius
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
    #: steps the bounded-LM driver shortened against a linear-inequality
    #: constraint (the Stephens strain cone) during this stage.  Always 0 under
    #: TRF, which has no such vocabulary.  Nonzero in the *final* stage means
    #: the answer sits on or near a constraint face and additionally raises a
    #: ``CONSTRAINT_ACTIVE`` diagnostic — the only signal that a declared
    #: constraint was active rather than merely present (WP-0601).
    n_constraint_truncations: int = 0
    #: trial cells this stage's residual refused as degenerate (zero or
    #: negative volume, ``crystallography.lattice.DegenerateCellError``)
    #: rather than warning about and returning NaN — issue #283.  ``Cell``'s
    #: own parameter bounds keep an ordinary bounded search almost entirely
    #: away from this, so 0 is the overwhelmingly common value; nonzero means
    #: the search still reached a degenerate combination *inside* those
    #: per-parameter bounds (a=b=c with the three angles all past ~120 deg,
    #: say -- well inside the 170 deg per-angle ceiling) and was pushed back
    #: out rather than crashing the stage.
    #: Additive field, defaulted to 0 (the honest "never happened" state);
    #: pending SCHEMA_VERSION renumbering rather than bumped with this change
    #: (see ``schemas/common.py``).
    n_degenerate_cell_probes: int = 0
    #: paths this stage **held** although the plan had freed them: the
    #: structural parameters of a phase the data could not see at stage start
    #: (``CompiledModel.phase_support`` below ``PHASE_SUPPORT_SIGMA``), which
    #: reach the pattern only through ``scale × |F|² × profile`` and are
    #: therefore a flat direction the solver would spend its budget walking
    #: (WP-1301).  Disjoint from :attr:`freed` by construction — a held path is
    #: dropped from it — so the two together say exactly what refined.  Empty
    #: on every fit with no unsupported phase, which is every fit that is
    #: working; the phase's own ``scale`` is never held, because that is how a
    #: phase legitimately climbs out of the noise.
    held: list[str] = Field(default_factory=list)
    #: paths held at stage start and **released within the same stage**: the
    #: phase rose above support while the stage solved, so the hold was lifted
    #: and the stage solved a second time (once — never a third) with them
    #: free.  They refined in this stage, which is why they are not in
    #: :attr:`held`; the cost of both solves is in :attr:`n_iterations`, and
    #: :attr:`cost_initial` is still the cost the stage started at.
    released: list[str] = Field(default_factory=list)


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
        line = f"  stage {s.name}: {s.status} ({s.n_iterations} it, ftol={ftol})"
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


def _cap_high_correlation(diagnostics: list[Diagnostic]) -> list[Diagnostic]:
    """Bound ``HIGH_CORRELATION`` at :data:`HIGH_CORRELATION_MAX`, worst first,
    for **rendering only** — see that constant's docstring for why this must
    never be applied to a stored diagnostics list.

    Every other code passes through untouched and in place; the correlation
    entries are pulled out, ordered by |ρ|, truncated, and the survivors
    appended where the last one used to sit.
    """
    is_hc = [d.code == "HIGH_CORRELATION" for d in diagnostics]
    if sum(is_hc) <= HIGH_CORRELATION_MAX:
        return diagnostics
    correlated = sorted((d for d, hc in zip(diagnostics, is_hc) if hc),
                        key=lambda d: abs(d.value) if d.value is not None else 0.0,
                        reverse=True)
    kept, omitted = correlated[:HIGH_CORRELATION_MAX], correlated[HIGH_CORRELATION_MAX:]
    out = [d for d, hc in zip(diagnostics, is_hc) if not hc]
    last_hc = max(i for i, hc in enumerate(is_hc) if hc)
    insert_at = sum(not hc for hc in is_hc[:last_hc + 1])
    out[insert_at:insert_at] = [*kept, Diagnostic(
        level="info", code="HIGH_CORRELATION_OMITTED", where=[],
        value=float(len(omitted)),
        message=f"{len(omitted)} more correlated pair(s) below the "
                f"{HIGH_CORRELATION_MAX} shown here, weaker than all of them",
        suggestion="result.identifiability carries the full correlation "
                   "matrix and top_correlations list — nothing here was "
                   "dropped from the fit, only from this message",
    )]
    return out


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
        line = f"    {d.level.upper()} {d.code}: {d.message}"
        if d.suggestion:
            line += f" — {d.suggestion}"
        lines.append(line)
    return lines


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


class RefinementResult(Base):
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
    # per-phase reflection tick positions (deg 2θ)
    ticks: dict[str, list[float]] = Field(default_factory=dict)

    # Quantitative phase analysis (weight fractions); computed for Rietveld
    # fits, None for Le Bail (its scales are degenerate).
    qpa: QuantitativePhaseAnalysis | None = None

    # Structure-sensitive agreement indices, one row per phase (WP-1069) —
    # see :class:`PhaseAgreement`.  Empty outside Rietveld mode, where the
    # partition would be circular, and empty for a result not built by a fit.
    phase_agreement: list[PhaseAgreement] = Field(default_factory=list)

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

    # How many explicit :class:`~rietx.schemas.instrument.BackgroundPeak` terms
    # this fit declared — the other half of "how flexible was the background":
    # :class:`Identifiability`'s absorption table says what the background could
    # imitate, this says with how many free peaks it was allowed to do it (N
    # peaks are 3N parameters with unconstrained positions), and a reader
    # comparing two Rwp values has to be able to see them.
    #
    # It sits **here and not on** :class:`Identifiability`, whose members are
    # read off the final Jacobian and therefore exist only where a solve
    # measured them.  This is not a measurement: it is
    # ``len(CompiledModel.bkg_peak_paths)``, a count of what the instrument
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
    n_background_peaks: int | None = None

    # Per-histogram slices of a multi-histogram joint refinement (WP-0308);
    # empty for an ordinary single-histogram fit.  ``statistics`` above is then
    # the pooled combined number and ``two_theta``/``y_*`` mirror histogram 0.
    histograms: list[HistogramResult] = Field(default_factory=list)

    # -- numpy views -------------------------------------------------------
    def sig(self) -> np.ndarray:
        """Per-point σ for this result — **the one authority** (WP-1029 (s)).

        Every weighted residual in the package divides by this: the matplotlib
        panel, the plotly export, the VLM montage, Layer 0 and the GUI's
        ``/api/result/window``.  They each open-coded it once, with three
        different policies, and agreed only because the disagreement lived in
        branches a modern result never takes.

        Normally this is a plain lookup rather than a computation, and that is
        the point: ``CompiledModel.sigma`` *is* :meth:`PatternData.sig`, and
        ``refine`` stores it here verbatim, so the esd-column/Poisson choice was
        already made once at stage compile.  Two conditioning steps remain, both
        for callers that are about to divide:

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
            s = np.sqrt(np.maximum(np.asarray(self.y_obs, dtype=np.float64), 1.0))
        floor = max(1e-3, float(np.median(s[s > 0])) * 1e-3) if np.any(s > 0) else 1.0
        return np.maximum(s, floor)

    def for_histogram(self, h: int) -> "RefinementResult":
        """A single-histogram-shaped view of histogram ``h`` for reporting/plots.

        Swaps the top-level curves and statistics for histogram ``h``'s own and
        clears ``histograms``, so ``build_report(result.for_histogram(h))`` and
        ``result.for_histogram(h).plot()`` operate per pattern (reports are
        per-histogram — see :class:`HistogramResult`).
        """
        if not self.histograms:
            if h == 0:
                return self
            raise IndexError("this result has no per-histogram slices")
        hr = self.histograms[h]
        view = self.model_copy(deep=True)
        view.statistics = hr.statistics.model_copy(deep=True)
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
        lines = [f"RefinementResult: {self.status} ({self.mode})"]
        lines += _stage_lines(self.stages, self.statistics.max_shift_over_esd)
        lines += _diagnostic_lines(self.diagnostics)
        lines.append(_provenance_line(self.provenance))
        lines.append(_agreement_line(self.statistics))
        return "\n".join(lines)
