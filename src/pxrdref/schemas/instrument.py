"""Instrument schemas: source, geometry, profile, background.

``Source``/``Geometry``/profile blocks are the pluggable seams for later
neutron/TOF and fundamental-parameters work.  What is implemented today is a
constant-wavelength X-ray source (one or more emission lines, optional
anomalous dispersion) in two geometries: ``debye_scherrer`` (capillary /
synchrotron, e.g. APS 11-BM, with the cylindrical absorption correction),
``bragg_brentano`` (laboratory flat plate, with displacement, transparency,
axial divergence, surface roughness and finite-thickness absorption) and
``flat_plate_transmission`` (a plate the beam passes through, with the
symmetric-transmission absorption factor).
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import Field, model_validator

from .common import Base, Parameter


class EmissionLine(Base):
    """One wavelength component of the incident spectrum.

    ``wavelength`` is in Å and fixed (emission wavelengths are known far more
    accurately than a powder pattern can refine them).  ``weight`` is the
    intensity of this line *relative to the first line of the source*, which is
    pinned at 1 by convention — refining the first line's weight would be
    degenerate with the phase scale factors, so the parameter table always
    holds line 0 fixed.  A Kα1/Kα2 doublet therefore carries one refinable
    number: the Kα2/Kα1 intensity ratio (≈0.5 for a sealed Cu tube; lower
    after a crystal monochromator's passband clips Kα2).
    """

    wavelength: float = Field(gt=0.0)
    weight: Parameter = Field(
        default_factory=lambda: Parameter(value=1.0, min=0.0, max=2.0)
    )


class Dispersion(Base):
    """Anomalous scattering corrections f′, f″ at the source wavelengths.

    Opt-in, and absent by default: switching it on changes every computed
    intensity (by −16 % for ZnO at Cu Kα, +7 % for CaF₂), so it is a modelling
    decision the caller makes rather than one a file read makes for them.  It
    is *not* a refinement — f′ and f″ are fixed constants of (element,
    wavelength), looked up once at stage compile from
    ``crystallography.dispersion``.

    ``overrides`` supplies measured pairs for elements where a table cannot be
    right: within a few tens of eV of an absorption edge the true f″ is the
    near-edge structure of the *compound*, which depends on coordination and
    oxidation state.  Keys are element symbols (``{"Zn": (-3.1, 0.5)}``), and
    an override also disables the edge-interval refusal for that element,
    since supplying the number is exactly how a user says "I measured this".
    """

    table: Literal["cromer_liberman"] = "cromer_liberman"
    overrides: dict[str, tuple[float, float]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _known_elements(self) -> "Dispersion":
        from ..crystallography.dispersion import normalize_element

        for key in self.overrides:
            if normalize_element(key) != key.strip().capitalize():
                raise ValueError(
                    f"dispersion override key {key!r} must be a bare element "
                    "symbol: f' and f'' are core-level effects and are "
                    "tabulated per element, not per ion")
        return self


class Source(Base):
    """Constant-wavelength X-ray source.

    ``polarization`` is the fraction K of the beam polarised *perpendicular*
    to the diffraction plane (σ-polarised).  The polarisation factor is

        P(2θ) = K + (1 − K)·cos²2θ

    so K = 0.5 reproduces the unpolarised-beam (1 + cos²2θ)/2, and a
    synchrotron beam diffracting in the vertical plane (E-vector horizontal,
    i.e. σ) has K ≈ 0.99 → an almost flat correction.  This matches the GSAS
    POLA convention used in APS 11-BM instrument-parameter files (Larson &
    Von Dreele, 2004, GSAS manual).
    """

    kind: Literal["xray_cw"] = "xray_cw"
    lines: list[EmissionLine]
    polarization: Parameter = Field(
        default_factory=lambda: Parameter(value=0.5, min=0.0, max=1.0)
    )
    #: opt-in anomalous scattering; None ⇒ f = f₀, bit-identical to the
    #: non-anomalous model (see :class:`Dispersion`)
    dispersion: Dispersion | None = None

    @model_validator(mode="after")
    def _nonempty(self) -> "Source":
        if not self.lines:
            raise ValueError("source has no emission lines")
        return self

    @property
    def primary_wavelength(self) -> float:
        return self.lines[0].wavelength


class RoughnessSuortti(Base):
    """Surface-roughness intensity correction, Suortti (1972) form.

        R(θ) = [a + (1 − a)·exp(−b/sinθ)] / [a + (1 − a)·exp(−b)]

    normalised so R(90°) = 1.  A rough or loosely-packed flat specimen has a
    packing-density deficit in its top layer; at low θ the beam crosses that
    depleted layer at grazing incidence over a long path, so the diffracted
    intensity is depressed, increasingly so as θ → 0.  Suortti, P. (1972),
    *J. Appl. Cryst.* **5**, 325–331.

    **Document by physics, not letters.**  ``a`` is the intensity fraction that
    survives even at grazing incidence, so **1 − a bounds the depression**
    (measured: with a = 0.9 the depression never exceeds 0.084 anywhere).
    ``b`` is the depleted layer's dimensionless optical depth, and it sets
    **where in angle** the transition falls, *not* how deep it goes.  This is
    GSAS-II's ``SurfaceRough`` parameterisation with a = SRA and b = SRB, which
    is what makes numbers portable between the two codes (behavioral reference
    only — no code ported, see ATTRIBUTION.md).

    **``b`` is bimodal, and that is a refinement hazard worth knowing.**  Both
    limits return the identity: b → 0 leaves the layer transparent, and b → ∞
    makes it opaque at *every* angle, so after the θ=90° normalisation no
    relative angular variation survives.  The correction is therefore strongest
    at intermediate b, and any given depression is reproducible by **two**
    values of b, one on each side of that peak.  Measured depression at the
    lowest fitted angle, a = 0.5:

    ======  ======  ======  ======  ======  ======
    b       0.01    0.1     0.3     1.0     3.0
    ======  ======  ======  ======  ======  ======
    2θ=5°   0.098   0.422   0.425   0.269   0.047
    2θ=20°  0.023   0.177   0.321   0.266   0.047
    ======  ======  ======  ======  ======  ======

    — peaking near b ≈ 0.17 (2θ_min = 5°) and b ≈ 0.46 (2θ_min = 20°), i.e. the
    peak moves out as sinθ_min grows.  Past b ≈ 3 the correction is effectively
    dead and its gradient is flat, so an optimiser that wanders there stalls.
    Two things guard this: the staged plan seeds ``b`` near the sensitive
    region rather than at the softplus floor, and the ``ROUGHNESS_UNCONSTRAINED``
    diagnostic fires on *either* dead branch by measuring the modelled
    depression over the fitted window instead of looking at ``b`` itself.
    ``max = 5`` bounds the excursion without pretending the bound is physics.

    Two properties the rest of the code relies on:

    * ``b = 0 ⇒ R ≡ 1``, and *exactly* so in floating point for any ``a``:
      numerator and denominator reduce to the identical expression
      ``a + (1 − a)*1.0``.  The off state is therefore bit-identical, with no
      branch in the hot path.
    * ``0 < R ≤ 1`` for b ≥ 0, since sinθ ≤ 1 ⇒ exp(−b/sinθ) ≤ exp(−b).  The
      correction can only *depress* intensity, never amplify it.

    ``a`` defaults to 0.5 — strictly interior — rather than to the seemingly
    natural 1.0, because at b = 0 the gradient ∂R/∂b = (1 − a)·(1 − 1/sinθ)
    vanishes identically when a = 1: the parameter could never lift off.
    """

    kind: Literal["suortti"] = "suortti"
    a: Parameter = Field(
        default_factory=lambda: Parameter(value=0.5, min=0.0, max=1.0)
    )
    b: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, min=0.0, max=5.0,
                                          transform="softplus")
    )


class RoughnessPitschke(Base):
    """Surface-roughness intensity correction, Pitschke *et al.* (1993) form.

        R(θ) = 1 − c·u·(1 − u),      u = τ/sinθ

    Pitschke, W., Hermann, H. & Mattern, N. (1993), *Powder Diffr.* **8**,
    74–83, Eqs (13)–(18).  The paper writes the multiplier as (1 − P) with
    P = P₀ + C·u(1 − u); **P₀ is deliberately absent here** because it is the
    angle-*independent* bulk-porosity term, so (1 − P) factorises as
    (1 − P₀)·[1 − c·u(1 − u)] with c = C/(1 − P₀) and the constant prefactor is
    exactly degenerate with the phase scale factor.  (The paper could only
    extract P₀ by fitting I/I₀ curves against a separate free scale, and even
    then reported 0.5–0.7 ± 0.1 for all four of its specimens — unresolved.)

    ``τ = t₀/β`` is the paper's dimensionless surface-roughness parameter,
    refined here **directly** rather than via the particle size β = 2b/3, which
    keeps a length scale the diffraction data cannot constrain out of the
    parameter table.  ``c`` is the strength knob; c = 0 gives R ≡ 1 exactly.

    **Regime (the paper's Eq 18: sinθ ≥ τ).**  u(1 − u) peaks at u = ½ and
    returns to 0 at u = 1, so:

    * R is monotone in θ only while **sinθ ≥ 2τ**;
    * between 2τ and τ the depression turns back over — the model is empirical
      there, with no geometric interpretation (the paper says so itself);
    * beyond sinθ = τ the correction would *amplify* (R > 1), which is
      unphysical.

    ``τ`` is bounded at 0.3, the paper's own estimate of the physical upper
    limit for real powders (its fitted values span 0.005–0.12), and ``c`` at 4,
    beyond which R can go negative inside the valid range.  The refinement
    still raises ``ROUGHNESS_OUTSIDE_REGIME`` when τ exceeds sinθ of the lowest
    fitted angle: bounds cannot express a fence that depends on the data range.

    ``τ`` defaults to 0.05 — mid-range and strictly interior — for the same
    lift-off reason as :class:`RoughnessSuortti`'s ``a``.
    """

    kind: Literal["pitschke"] = "pitschke"
    c: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, min=0.0, max=4.0,
                                          transform="softplus")
    )
    tau: Parameter = Field(
        default_factory=lambda: Parameter(value=0.05, min=0.0, max=0.3)
    )


SurfaceRoughness = RoughnessSuortti | RoughnessPitschke


class Geometry(Base):
    """Diffraction geometry.

    ``debye_scherrer``: spinning capillary (synchrotron or lab); only
    ``zero_shift`` moves the peaks.  Cylindrical **absorption** is applied as an
    intensity factor when µR > 0 (Rouse, Cooper, York & Chakera, 1970, *Acta
    Cryst.* A26, 682; see :mod:`pxrdref.model.absorption`), µR coming either
    from ``mu_r`` directly or from ``capillary_radius_mm`` × ``packing_fraction``
    × the composition's linear attenuation coefficient.

    **µR is deliberately a plain float and not a refinable** :class:`Parameter`.
    The Rouse expression factors exactly into a constant times exp(c·sin²θ) — a
    Debye-Waller shape — so within this model a free µR is *exactly* a linear
    combination of the phase-scale and Biso columns rather than merely a
    correlated one.  Refining it would improve nothing and silently
    re-apportion ADPs.  ``packing_fraction`` is likewise not refinable: it is
    exactly degenerate with µR itself.  What the correction buys is an
    **unbiased Biso** — neglecting it biases Biso low by c(µR)·λ²/2, which is
    0.13 Å² at µR = 0.5 and 0.49 Å² at µR = 1.0 for Cu Kα.

    ``bragg_brentano``: flat-plate para-focusing goniometer (v0.2).  Two
    sample aberrations shift the peaks (Wilson, 1963, *Mathematical Theory of
    X-ray Powder Diffractometry*; Klug & Alexander, 1974, ch. 5):

    * **sample displacement** — a specimen surface off the goniometer axis by
      ``s`` (mm, positive *toward the source/detector side*, i.e. above the
      focusing circle) shifts every peak by

          Δ2θ = −(2·s/R)·cosθ   [radians],  R = goniometer radius (mm)

      the dominant lab-instrument error, distinguishable from ``zero_shift``
      by its cosθ dependence;

    * **sample transparency** — finite penetration moves the effective
      diffracting surface below the physical surface, shifting peaks by

          Δ2θ = −t·sin2θ   [radians],  t = 1/(2·μ_eff·R)

      where μ_eff is the effective linear attenuation coefficient (mm⁻¹).
      ``sample_transparency`` holds the *coefficient* t (dimensionless,
      ≥ 0 for the physical thick-sample case); for strong absorbers such as
      LaB₆ it is negligible and stays fixed at 0.

    Axial (out-of-plane) divergence produces the low-angle peak *asymmetry*
    modelled by the Finger-Cox-Jephcoat profile (Finger, Cox & Jephcoat,
    1994, J. Appl. Cryst. 27, 892): ``axial_sl`` and ``axial_hl`` are the
    FCJ S/L and H/L ratios — sample and receiving-slit axial half-lengths
    over the goniometer radius.  Both zero → symmetric profile (FCJ off).
    S/L and H/L enter the aberration nearly symmetrically and are strongly
    correlated; refining only one (or tying them equal) is common practice.

    ``surface_roughness`` is an **opt-in** block (default ``None``) carrying the
    third Bragg-Brentano sample aberration: unlike displacement and
    transparency it does not move the peaks, it depresses their *intensity* at
    low angle.  See :class:`RoughnessSuortti` / :class:`RoughnessPitschke`.  It
    is opt-in rather than always-present because an uncorrected roughness
    depression is absorbed by Biso/ADPs, so *adding* the freedom must be a
    deliberate act — and because attaching it changes nothing until refined
    (both models are exactly the identity at their default values).

    ``flat_plate_transmission``: a flat specimen the beam passes *through* —
    a Stoe Stadi P, or a laboratory diffractometer run in transmission with the
    powder between two foils (v0.5, WP-0508).  It models **absorption and
    nothing else**: like ``debye_scherrer``, only ``zero_shift`` moves its
    peaks.  A transmission goniometer has its own displacement aberration, and
    this package does not model it rather than inventing one; if a specimen is
    badly enough off-axis for that to matter, the peak positions are not
    trustworthy anyway.

    ``mu_t`` — dimensionless µ times **specimen thickness** — turns on the
    flat-plate absorption factors for both flat geometries
    (:mod:`pxrdref.model.absorption`, *International Tables* Vol. C
    Table 6.3.3.1):

    * ``bragg_brentano`` → case (2), finite-thickness reflection,
      A = 1 − exp(−2µt/sin θ), normalised by the thick-specimen limit;
    * ``flat_plate_transmission`` → case (3a), symmetric transmission,
      A = sec θ·exp(−µt·(sec θ − 1)), normalised at θ = 0.

    **The off state for reflection is µt = ∞, not µt = 0** — the reverse of
    every other correction in this package.  ITC case (1a) says a specimen
    thicker than the penetration depth has A = 1/2µ with *no θ at all*, which is
    what "leave ``mu_t`` unset" means and what this package has always assumed;
    a plate of zero thickness diffracts nothing, so ``mu_t = 0`` is rejected for
    ``bragg_brentano`` rather than being silently treated as "off".  Under
    transmission ``mu_t = 0`` is legal and means a non-absorbing plate, which
    still carries the sec θ growth of the illuminated volume — and so is leaving
    it ``None``: that geometry applies its factor unconditionally, because the
    footprint belongs to the tilt and not to the absorption.

    **µt is a plain float for the same reason µR is, but on weaker evidence,
    and the difference is worth knowing.**  A free µR is *exactly* a linear
    combination of the scale and Biso columns.  A free µt is not: measured
    against the normalised expressions above it keeps a few per cent to tens of
    per cent of its angular signature
    (``absorption.mu_t_identifiable_fraction``).  It is held fixed anyway, on
    three grounds — µt is knowable from the specimen (a thickness and a
    composition), a free one lands in the ill-conditioned {scale, Biso,
    background} corner, and what it would silently re-apportion is the ADPs,
    which is what the correction exists to protect.  What the fit *reports*
    instead is the Biso bias it removed, which for a flat plate is large:
    −1.5 Å² at µt = 0.2 over a Cu Kα range, an order of magnitude past the
    capillary case.
    """

    kind: Literal["debye_scherrer", "bragg_brentano",
                  "flat_plate_transmission"] = "debye_scherrer"
    goniometer_radius_mm: float | None = None
    surface_roughness: SurfaceRoughness | None = None
    sample_displacement: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, min=-1.0, max=1.0, unit="mm")
    )
    sample_transparency: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, min=0.0, max=0.05)
    )
    axial_sl: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, min=0.0, max=0.2)
    )
    axial_hl: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, min=0.0, max=0.2)
    )
    #: dimensionless µ·R of the packed specimen; ``None`` → estimate it from the
    #: composition and ``capillary_radius_mm``.  Never a ``Parameter`` — see the
    #: class docstring.  0.0 disables the correction exactly (A ≡ 1.0).
    mu_r: float | None = None
    #: internal radius of the capillary bore, mm (estimator input only).
    capillary_radius_mm: float | None = None
    #: dimensionless µ·t of the packed flat specimen; ``None`` → estimate it from
    #: the composition and ``thickness_mm``, and failing that leave the specimen
    #: thick (reflection) — the pre-WP-0508 assumption.  Never a ``Parameter``;
    #: see the class docstring.
    mu_t: float | None = None
    #: flat-specimen thickness, mm (estimator input only).  For a reflection
    #: mount this is the depth of the powder layer, not the holder.
    thickness_mm: float | None = None
    #: fraction of the bore (or the specimen slab) occupied by solid.  0.3-0.6 is
    #: typical for a tapped powder; 0.64 is random close packing of spheres.
    #: Estimator input only.
    packing_fraction: float = Field(default=0.6, gt=0.0, le=1.0)

    @model_validator(mode="after")
    def _bb_needs_radius(self) -> "Geometry":
        if self.kind == "bragg_brentano" and not self.goniometer_radius_mm:
            raise ValueError("bragg_brentano geometry requires goniometer_radius_mm")
        if self.surface_roughness is not None and self.kind != "bragg_brentano":
            # Raise rather than silently lock the parameters: the block is
            # opt-in, so its presence is a claim about the specimen, and the
            # correction is derived for a flat reflection specimen only.  A
            # spinning capillary has no illuminated flat surface to roughen.
            raise ValueError(
                f"surface_roughness is a flat-specimen (bragg_brentano) "
                f"correction; this geometry is {self.kind!r}")
        return self

    @model_validator(mode="after")
    def _capillary_fields_need_debye_scherrer(self) -> "Geometry":
        if self.kind != "debye_scherrer":
            for name in ("mu_r", "capillary_radius_mm"):
                if getattr(self, name) is not None:
                    raise ValueError(f"{name} applies only to debye_scherrer geometry")
        if self.mu_r is not None and self.mu_r < 0.0:
            raise ValueError("mu_r must be non-negative")
        if self.capillary_radius_mm is not None and self.capillary_radius_mm <= 0.0:
            raise ValueError("capillary_radius_mm must be positive")
        return self

    @model_validator(mode="after")
    def _flat_plate_fields_need_a_flat_specimen(self) -> "Geometry":
        if self.kind == "debye_scherrer":
            for name in ("mu_t", "thickness_mm"):
                if getattr(self, name) is not None:
                    raise ValueError(
                        f"{name} is a flat-specimen quantity; this geometry is "
                        f"{self.kind!r} (a capillary uses mu_r / "
                        "capillary_radius_mm)")
        if self.thickness_mm is not None and self.thickness_mm <= 0.0:
            raise ValueError("thickness_mm must be positive")
        if self.mu_t is not None:
            if self.mu_t < 0.0:
                raise ValueError("mu_t must be non-negative")
            # 0 is the identity for every other correction here and emphatically
            # not for this one: ITC case (2) reads A = 1 − exp(0) = 0, a
            # specimen of no thickness, which is a modelling mistake worth
            # refusing rather than a way of switching the correction off.
            if self.mu_t == 0.0 and self.kind == "bragg_brentano":
                raise ValueError(
                    "mu_t = 0 is a specimen of zero thickness, not 'no "
                    "correction': leave mu_t unset for the thick-specimen case "
                    "(International Tables C, Table 6.3.3.1 case 1a), which is "
                    "exactly degenerate with the phase scale and needs no "
                    "correction at all")
        return self


class ProfileTCHZ(Base):
    """Thompson-Cox-Hastings pseudo-Voigt width parameters.

    Gaussian variance (in centidegrees², GSAS convention is *not* used —
    everything here is in degrees 2θ):

        Γ_G² = U·tan²θ + V·tanθ + W          (Caglioti et al., 1958)

    Lorentzian FWHM:

        Γ_L = X/cosθ + Y·tanθ

    where the 1/cosθ term is Scherrer (size) broadening and the tanθ term is
    microstrain broadening (document physics, not letters: GSAS and FullProf
    swap the X/Y letter assignment).  Thompson, Cox & Hastings (1987),
    J. Appl. Cryst. 20, 79.

    ``shape`` selects the peak shape these widths feed: the default
    ``"tchz_pv"`` pseudo-Voigt (fast, the usual Rietveld choice) or ``"voigt"``,
    the exact Gaussian⊗Lorentzian convolution via a shared Faddeeva w(z)
    (``model/profiles/voigt.py``).  It is a per-instrument, compile-time choice —
    not a refinable parameter and not per-reflection — and consumes the *same*
    U,V,W,X,Y widths, so switching shapes never touches the parameter table.
    """

    shape: Literal["tchz_pv", "voigt"] = "tchz_pv"
    u: Parameter = Field(default_factory=lambda: Parameter(value=0.0, min=-0.05, max=1.0, unit="deg^2"))
    v: Parameter = Field(default_factory=lambda: Parameter(value=0.0, min=-0.5, max=0.5, unit="deg^2"))
    w: Parameter = Field(
        default_factory=lambda: Parameter(value=1e-3, min=0.0, max=1.0, unit="deg^2", transform="softplus")
    )
    x: Parameter = Field(
        default_factory=lambda: Parameter(value=1e-3, min=0.0, max=1.0, unit="deg", transform="softplus")
    )
    y: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, min=0.0, max=1.0, unit="deg", transform="softplus")
    )


class BackgroundChebyshev(Base):
    """Shifted-Chebyshev background, linear in its coefficients.

    y_bkg(x) = Σ c_n T_n(x), x = 2·(2θ − 2θ_min)/(2θ_max − 2θ_min) − 1.
    Being linear, the Jacobian columns for the coefficients are exact basis
    functions (used by the analytic-Jacobian path).
    """

    kind: Literal["chebyshev"] = "chebyshev"
    coefficients: list[Parameter] = Field(
        default_factory=lambda: [Parameter(value=0.0, vary=False) for _ in range(4)]
    )

    @classmethod
    def with_terms(cls, n: int, *, vary: bool = True) -> "BackgroundChebyshev":
        return cls(coefficients=[Parameter(value=0.0, vary=vary) for _ in range(n)])


class BackgroundPSpline(Base):
    """Penalized cubic P-spline background, co-refined with the structure.

    The background is linear in its B-spline coefficients (exact Jacobian
    columns), and a second-difference smoothness penalty on the coefficients
    rides in the least squares as extra residual rows

        r_pen = √λ · (D₂ c)          (Eilers & Marx, 1996, Stat. Sci. 11, 89)

    which keeps the co-refined curve smooth, propagates esds, and — the
    reason it exists — makes it *physically unable* to absorb broad Bragg
    intensity (the documented nanocrystalline/QPA failure mode of
    subtract-then-refine backgrounds).  ``breakpoints`` are the spline knots
    in 2θ (uniform spacing from :meth:`for_range`; the clamped cubic basis
    has ``len(breakpoints) + 2`` coefficients).

    ``air_scatter`` scales an additive 1/(2θ) term for the low-angle
    air-scatter rise; leave it fixed at 0 unless the pattern diagnostics
    flag it (``pxrdref.background.diagnose``).
    """

    kind: Literal["pspline"] = "pspline"
    breakpoints: list[float]
    coefficients: list[Parameter]
    lambda_smooth: float = Field(default=1.0, ge=0.0)
    air_scatter: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, min=0.0, transform="softplus")
    )

    @model_validator(mode="after")
    def _consistent(self) -> "BackgroundPSpline":
        if len(self.breakpoints) < 2:
            raise ValueError("pspline needs at least 2 breakpoints")
        if any(nxt <= prev for prev, nxt in zip(self.breakpoints, self.breakpoints[1:])):
            raise ValueError("breakpoints must be strictly increasing")
        if len(self.coefficients) != len(self.breakpoints) + 2:
            raise ValueError(
                f"clamped cubic basis over {len(self.breakpoints)} breakpoints has "
                f"{len(self.breakpoints) + 2} functions; got "
                f"{len(self.coefficients)} coefficients")
        return self

    @classmethod
    def for_range(cls, lo: float, hi: float, *, knot_step_deg: float = 5.0,
                  lambda_smooth: float = 1.0, vary: bool = True) -> "BackgroundPSpline":
        """Uniform knots covering [lo, hi] at ~``knot_step_deg`` spacing."""
        n = max(int(round((hi - lo) / knot_step_deg)) + 1, 2)
        breaks = [lo + (hi - lo) * i / (n - 1) for i in range(n)]
        return cls(
            breakpoints=breaks,
            coefficients=[Parameter(value=0.0, vary=vary) for _ in range(n + 2)],
            lambda_smooth=lambda_smooth,
        )


class BackgroundFixedPlusChebyshev(Base):
    """A fixed estimated curve (never subtracted; held additively) plus a
    small refinable Chebyshev correction on top.

    The fixed curve typically comes from :func:`pxrdref.background.estimate`
    (arPLS/SNIP).  Holding it inside the model keeps Poisson weights correct.
    """

    kind: Literal["fixed_plus_chebyshev"] = "fixed_plus_chebyshev"
    fixed_two_theta: list[float]
    fixed_intensity: list[float]
    chebyshev: BackgroundChebyshev = Field(default_factory=lambda: BackgroundChebyshev())

    @model_validator(mode="after")
    def _lengths(self) -> "BackgroundFixedPlusChebyshev":
        if len(self.fixed_two_theta) != len(self.fixed_intensity):
            raise ValueError("fixed background arrays differ in length")
        return self


Background = BackgroundChebyshev | BackgroundFixedPlusChebyshev | BackgroundPSpline


class Instrument(Base):
    """Everything about the measurement except the sample."""

    source: Source
    geometry: Geometry = Field(default_factory=Geometry)
    zero_shift: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, min=-0.5, max=0.5, unit="deg")
    )
    profile: ProfileTCHZ = Field(default_factory=ProfileTCHZ)
    background: Background = Field(
        default_factory=lambda: BackgroundChebyshev(), discriminator=None
    )

    @classmethod
    def debye_scherrer(cls, wavelength: float, *, polarization: float = 0.99,
                       capillary_radius_mm: float | None = None,
                       packing_fraction: float = 0.6,
                       mu_r: float | None = None) -> "Instrument":
        """Synchrotron/capillary preset with a single wavelength.

        ``polarization`` follows the GSAS POLA convention (see :class:`Source`);
        0.99 matches APS 11-BM instrument-parameter files.

        Cylindrical absorption stays **off** unless a capillary radius or an
        explicit ``mu_r`` is given, so the preset's historical meaning ("no
        position aberrations") is unchanged for callers that pass neither.
        """
        return cls(
            source=Source(
                lines=[EmissionLine(wavelength=wavelength)],
                polarization=Parameter(value=polarization, min=0.0, max=1.0),
            ),
            geometry=Geometry(kind="debye_scherrer", mu_r=mu_r,
                              capillary_radius_mm=capillary_radius_mm,
                              packing_fraction=packing_fraction),
        )

    @classmethod
    def bragg_brentano(cls, *, radiation: str = "CuKa",
                       goniometer_radius_mm: float = 217.5,
                       monochromator_two_theta: float | None = None,
                       ka2_ratio: float = 0.5,
                       mu_t: float | None = None,
                       thickness_mm: float | None = None) -> "Instrument":
        """Lab flat-plate diffractometer preset with a Kα1/Kα2 doublet.

        ``radiation`` names an anode in :data:`_RADIATIONS` — ``"CrKa"``,
        ``"FeKa"``, ``"CoKa"``, ``"CuKa"``, ``"MoKa"``, ``"AgKa"``, or the
        ``…Ka1`` variant of any of them for an incident-side-monochromated beam
        with Kα2 removed (``ka2_ratio`` then has no line to act on).

        Each emission line diffracts at its own Bragg angle, so the doublet
        splitting *grows with tanθ* (differentiate Bragg's law:
        Δ2θ = 2·tanθ·Δλ/λ) — never a fixed 2θ offset.  ``ka2_ratio`` seeds the
        refinable Kα2/Kα1 intensity ratio.  0.5 is the 2j+1 degeneracy ratio
        (4:2) and is the right seed for every anode; measured integrated ratios
        run a few percent above it and rise slowly with Z, and a
        diffracted-beam monochromator passband typically clips it a little.

        ``monochromator_two_theta``: 2θ_m of a diffracted-beam (post-sample)
        crystal monochromator, e.g. ≈26.6° for pyrolytic graphite (002) with
        Cu Kα.  For an ideally-mosaic crystal the polarization factor becomes
        (1 + cos²2θ_m·cos²2θ)/(1 + cos²2θ_m), i.e. our K-convention with
        K = 1/(1 + cos²2θ_m)  (International Tables C, §6.2; Azároff, 1955).
        ``None`` → unpolarized beam, K = 0.5.

        That 26.6° is a *Cu* number, not a property of the crystal: 2θ_m =
        2·asin(λ/2d) with d₍₀₀₂₎ ≈ 3.354 Å, so the same graphite sits at ≈12.1°
        at Mo Kα, where K = 0.511 rather than 0.500.  Off Cu, compute it for
        the anode in use rather than copying the example.

        ``mu_t`` / ``thickness_mm`` declare a **finite-thickness** specimen
        (ITC case 2, WP-0508) — a thin layer on a zero-background holder rather
        than a filled well.  Both absent is the thick-specimen default, which
        needs no correction because it is exactly degenerate with the scale.
        """
        try:
            lines = _RADIATIONS[radiation]
        except KeyError:
            raise ValueError(
                f"unknown radiation {radiation!r}; available: {sorted(_RADIATIONS)}"
            ) from None
        k = 0.5
        if monochromator_two_theta is not None:
            c2 = math.cos(math.radians(monochromator_two_theta)) ** 2
            k = 1.0 / (1.0 + c2)
        emission = [EmissionLine(wavelength=lines[0],
                                 weight=Parameter(value=1.0, min=0.0, max=2.0))]
        for wl in lines[1:]:
            emission.append(EmissionLine(
                wavelength=wl,
                weight=Parameter(value=ka2_ratio, min=0.0, max=1.0)))
        return cls(
            source=Source(
                lines=emission,
                polarization=Parameter(value=k, min=0.0, max=1.0),
            ),
            geometry=Geometry(kind="bragg_brentano",
                              goniometer_radius_mm=goniometer_radius_mm,
                              mu_t=mu_t, thickness_mm=thickness_mm),
        )


    @classmethod
    def flat_plate_transmission(cls, *, radiation: str = "CuKa1",
                                mu_t: float | None = None,
                                thickness_mm: float | None = None,
                                packing_fraction: float = 0.6,
                                ka2_ratio: float = 0.5) -> "Instrument":
        """Flat-specimen **transmission** preset (WP-0508).

        The powder sits between two foils and the beam passes through it —
        a Stoe Stadi P, or a Bragg-Brentano instrument reconfigured for
        transmission.  Only ``zero_shift`` moves the peaks (see
        :class:`Geometry`); what this geometry adds over a bare source is ITC
        case (3a) absorption, which is on as soon as the geometry is chosen
        because its sec θ volume factor survives at µt = 0.

        ``radiation`` defaults to the **Kα1-only** ``"CuKa1"``, unlike
        :meth:`bragg_brentano`: a transmission instrument of this kind is
        normally built around an incident-beam focusing monochromator, which is
        what makes the geometry practical in the first place.  Pass a doublet
        name explicitly for an unmonochromated transmission setup.

        Give ``mu_t`` directly, or ``thickness_mm`` and let the refinement
        estimate µt from the composition.  With neither, the geometry still
        applies the sec θ footprint factor at µt = 0 — a transparent plate is
        still a tilted one — and the result's ``absorption`` record reports
        ``mu_r = 0`` so that choice is visible rather than implied.
        """
        try:
            lines = _RADIATIONS[radiation]
        except KeyError:
            raise ValueError(
                f"unknown radiation {radiation!r}; available: {sorted(_RADIATIONS)}"
            ) from None
        emission = [EmissionLine(wavelength=lines[0],
                                 weight=Parameter(value=1.0, min=0.0, max=2.0))]
        for wl in lines[1:]:
            emission.append(EmissionLine(
                wavelength=wl, weight=Parameter(value=ka2_ratio, min=0.0, max=1.0)))
        return cls(
            source=Source(lines=emission,
                          polarization=Parameter(value=0.5, min=0.0, max=1.0)),
            geometry=Geometry(kind="flat_plate_transmission", mu_t=mu_t,
                              thickness_mm=thickness_mm,
                              packing_fraction=packing_fraction),
        )


#: Kα1/Kα2 **peak** wavelengths (Å) — not the centroid Kᾱ, which is what the
#: doublet model would double-count.
#:
#: Every value is the *direct experimental* wavelength of the KL3 (Kα1) and
#: KL2 (Kα2) transition in the NIST X-ray Transition Energies Database
#: (SRD 128, https://physics.nist.gov/PhysRefData/XrayTrans/), whose evaluation
#: is Deslattes, Kessler, Indelicato, de Billy, Lindroth & Anton (2003),
#: Rev. Mod. Phys. 75, 35.  Reproduce any row with
#:
#:     curl "https://physics.nist.gov/cgi-bin/XrayTrans/search.pl?\
#: download=tab&element=Mo&trans=KL2&trans=KL3&lower=&upper=&units=A"
#:
#: **One column of one evaluation for all anodes** is the load-bearing part,
#: not the individual digits: mixing wavelength scales is the classic ~100 ppm
#: cell error.  Within that column the anodes trace to two measurements —
#: ref 7d = Hölzer, Fritsch, Deutsch, Härtwig & Förster (1997), Phys. Rev. A
#: 56, 4554 for the 3d metals, ref 5d = Deslattes & Kessler, in *Atomic
#: Inner-Shell Physics* (Plenum, 1985), 181 for Mo/Ag — so "same column" is
#: the claim, not "same paper".  What makes it checkable: the Cu pair below is
#: byte-for-byte the Hölzer peak values this package has shipped since v0.2,
#: on the scale of the NIST SRM 660c certificate.  It is unchanged here, and
#: `test_lab_instrument` asserts that, because it is what pins the rest.
#:
#: Bearden (1967), Rev. Mod. Phys. 39, 78 — the values most textbooks quote —
#: is a *different* scale (Mo Kα2 0.713590 vs 0.713607 here, 24 ppm; Ag Kα1
#: 0.5594075 vs 0.55942178, 26 ppm).  Do not "correct" a row toward it.
#:
#: Kβ is deliberately absent: it is filtered or monochromated away in
#: essentially every lab setup, and one |F|² cannot serve it and Kα together
#: (``dispersion.LINE_DISPERSION_TOL``).  The Kβ wavelengths used for the
#: contamination check live in ``pxrdref.background.diagnostics``.
_KA_DOUBLETS: dict[str, tuple[float, float]] = {
    "CrKa": (2.2897260, 2.2936510),    # ref 7d
    "FeKa": (1.9360410, 1.9399730),    # ref 7d
    "CoKa": (1.7889960, 1.7928350),    # ref 7d
    "CuKa": (1.5405929, 1.5444274),    # ref 7d — 1.54059290 / 1.54442740
    "MoKa": (0.70931715, 0.713607),    # ref 5d
    "AgKa": (0.55942178, 0.5638131),   # ref 5d
}

#: The doublets, plus a Kα1-only entry per anode (``"CuKa1"``, ``"MoKa1"``, …)
#: for beams monochromated on the incident side — a Ge(111) or Johansson
#: crystal removes Kα2, and that is a flat-plate geometry the single-wavelength
#: :meth:`Instrument.debye_scherrer` preset cannot express.  Derived from the
#: same tuples so there is one source of truth per wavelength.  ``ka2_ratio``
#: has no line to act on for those entries and is ignored.
_RADIATIONS: dict[str, tuple[float, ...]] = {
    **_KA_DOUBLETS,
    **{f"{name}1": (lines[0],) for name, lines in _KA_DOUBLETS.items()},
}
