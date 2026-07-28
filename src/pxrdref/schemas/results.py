"""Refinement result schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import Base, Diagnostic, Mode, Provenance


class RefinedParameter(Base):
    path: str
    value: float
    stderr: float | None = None
    initial: float | None = None
    vary: bool = True
    at_bound: bool = False


class Statistics(Base):
    """Agreement indices, defined per Toby (2006), Powder Diffraction 21, 67.

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
    """Record of the cylindrical (capillary) absorption applied, WP-0501.

    Present only for ``debye_scherrer`` Rietveld fits that actually carried a
    µR.  ``mu_r`` is the value used (from ``Geometry.mu_r``, or estimated from
    composition × packing × capillary radius when that was left unset), and
    ``mu_r_source`` says which.

    ``equivalent_delta_biso`` is the point of the whole correction.  The Rouse
    transmission factor is exactly a constant times exp(c·sin²θ), so applying
    it is an exact reparameterisation of the phase scale and the displacement
    parameters: Rwp does not change.  What changes is that a Biso refined
    *without* it comes back low by this much (Å²), which is why the correction
    is worth applying and why an Rwp comparison would show nothing.
    """

    method: Literal["rouse_cylinder"] = "rouse_cylinder"
    mu_r: float
    mu_r_source: Literal["given", "estimated"]
    wavelength: float                    # Å, primary emission line
    equivalent_delta_biso: float         # Å², bias incurred by omitting this
    #: set when µR was requested but could not be estimated (absorption edge in
    #: the tabulation interval, element outside the compilation, energy outside
    #: 2-120 keV) — the correction was then not applied
    skipped: str | None = None
    #: set when µR exceeds the Rouse fit's stated range; the value was still
    #: used, since refusing outright would silently drop real absorption
    out_of_range: bool = False


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

    ``restraint_chi2`` = Σ weight·(deviation/σ)² is the sum of the squared
    restraint residual rows — the penalty the restraints add to the cost.  It
    is *not* part of the data-row Rwp/χ²/GoF (those see data rows only), by
    design: restraints are soft observations, not measured intensities.
    """

    rows: list[RestraintRow]
    restraint_chi2: float
    n_restraints: int


class IterationRecord(Base):
    stage: str
    iteration: int
    cost: float
    grad_norm: float | None = None
    step_norm: float | None = None


class StageResult(Base):
    name: str
    status: Literal["converged", "max_iter", "diverged", "skipped"]
    n_iterations: int
    cost_initial: float
    cost_final: float
    freed: list[str] = Field(default_factory=list)


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
    diagnostics: list[Diagnostic] = Field(default_factory=list)


class RefinementResult(Base):
    status: Literal["converged", "max_iter", "diverged"]
    mode: Mode
    parameters: list[RefinedParameter]
    statistics: Statistics
    correlation_warnings: list[str] = Field(default_factory=list)
    stages: list[StageResult] = Field(default_factory=list)
    history: list[IterationRecord] = Field(default_factory=list)
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

    # Cylindrical absorption (WP-0501); None unless a capillary µR was given or
    # estimable.  Carries the equivalent Biso bias, because that — not Rwp — is
    # what the correction buys.
    absorption: AbsorptionCorrection | None = None

    # Soft-restraint summary (bond/angle/value deviations, pooled restraint χ²);
    # present only when a phase declared restraints (Rietveld-only), None
    # otherwise.  Deviations in units of σ surface an over-tight restraint
    # fighting the data even while Rwp looks good.
    restraints: RestraintReport | None = None

    # Per-histogram slices of a multi-histogram joint refinement (WP-0308);
    # empty for an ordinary single-histogram fit.  ``statistics`` above is then
    # the pooled combined number and ``two_theta``/``y_*`` mirror histogram 0.
    histograms: list[HistogramResult] = Field(default_factory=list)

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
