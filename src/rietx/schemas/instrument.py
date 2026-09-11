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
from typing import ClassVar, Literal

from pydantic import Field, field_validator, model_validator

from .common import Base, Parameter

#: Å.  Strictly positive floor for a wavelength :class:`Parameter`.  λ reaches
#: the model only through sin θ = λ/2d, so λ ≤ 0 puts every reflection at
#: 2θ = 0 (or off the sphere) and the profile derivatives go with it — the
#: "softplus min=0 where the physics divides" trap of the root ``CLAUDE.md``,
#: one rank over.  1e-3 Å is three orders below any diffraction wavelength, so
#: the bound is a fence and not a claim about the instrument.
_WAVELENGTH_MIN_A = 1e-3

#: The two halves of McCusker eq (4), in order (sin 2θ, cos 2θ).  One
#: authority for the pair of names: the schema validator, ``ParameterTable``,
#: ``CompiledModel._position_shift_deg`` and the Layer-2 action map all read
#: it, so adding a third axis (or renaming one) is a single edit rather than
#: four that can drift.  See :class:`Geometry`.
CAPILLARY_OFFSETS: tuple[str, str] = ("capillary_offset_along_beam",
                                      "capillary_offset_across_beam")


def _as_wavelength(v):
    """Coerce a bare number into a wavelength :class:`Parameter`.

    ``wavelength`` was a plain ``float`` through v1.1, so every construction
    site — and every persisted instrument — spells it as a number.  Accepting
    one here keeps all of them working and makes the field's own history the
    migration: a document written before this change validates unchanged, at
    ``vary=False``, which is what it meant.
    """
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return Parameter(value=float(v), vary=False,
                         min=_WAVELENGTH_MIN_A, unit="A")
    return v


class EmissionLine(Base):
    """One wavelength component of the incident spectrum.

    ``wavelength`` is in Å and **defaults to fixed**, because for a *single*
    histogram it is exactly degenerate with the cell: d = λ/(2 sin θ) fixes
    only the product, so a free λ beside a free cell is a flat direction and
    the parameter table refuses it (:func:`rietx.params.multi.check_wavelength_freedom`).
    Across several histograms of **one specimen sharing one cell** the
    degeneracy breaks — holding one λ pins the cell's scale and the remaining
    N − 1 are over-determined by that shared cell — so a joint fit may free all
    but one of them.  A bare number is still accepted and becomes a fixed
    parameter, so nothing that spelled ``wavelength=1.5406`` has to change.

    ``weight`` is the intensity of this line *relative to the first line of the
    source*, which is pinned at 1 by convention — refining the first line's
    weight would be degenerate with the phase scale factors, so the parameter
    table always holds line 0 fixed.  A Kα1/Kα2 doublet therefore carries one
    refinable number: the Kα2/Kα1 intensity ratio (≈0.5 for a sealed Cu tube;
    lower after a crystal monochromator's passband clips Kα2).

    **The wavelength rule is that same convention one rank up**, and
    deliberately so: one member of a set is pinned to fix a scale the data
    cannot set and the rest are free.  What differs is only *where the set
    lives* — the line weights are a set inside one source, so line 0 can be
    locked here; the wavelengths are a set across *instruments*, which no
    single instrument can count, so the pinning is enforced where the joint
    problem is assembled.
    """

    wavelength: Parameter
    weight: Parameter = Field(
        default_factory=lambda: Parameter(value=1.0, min=0.0, max=2.0)
    )

    @field_validator("wavelength", mode="before")
    @classmethod
    def _coerce_wavelength(cls, v):
        return _as_wavelength(v)

    @model_validator(mode="after")
    def _positive_wavelength(self) -> "EmissionLine":
        if self.wavelength.value <= 0.0:
            raise ValueError(
                f"wavelength must be positive, got {self.wavelength.value}")
        return self


#: The harmonic order a bare ``Harmonic()`` declares.  A monochromator set for
#: λ reflects *every* order its planes admit, but the second is the only one
#: that normally carries measurable intensity: the higher orders' structure
#: factors and their Bragg-reflectivity widths both fall away, and the λ/3
#: component of a Ge or Cu monochromator is typically an order below the λ/2
#: one.  So this is a **default, not a limit** — :class:`Harmonic` is general
#: in ``order`` and a beamline that knows it has a third order declares it.
DEFAULT_HARMONIC_ORDER = 2

#: Seed for a harmonic's relative weight.  Deliberately small and deliberately
#: *not* any of the numbers the literature reports for a real beamline (see
#: :class:`Harmonic`): a seed at the expected answer is how a correction comes
#: back confirming its own prior.  1 % is far enough below every reported value
#: that the refinement has to travel to reach one.
HARMONIC_WEIGHT_SEED = 0.01

#: Ceiling on a harmonic's relative weight.  Not a tuning: a component that is
#: more than half the fundamental is not a contaminant of it, and a refinement
#: that pushes the weight here is telling you the peaks it is filling are not
#: harmonic peaks.  The bound is therefore *informative* — ``BOUND_HIT`` on
#: this path is the finding, not a nuisance.
HARMONIC_WEIGHT_MAX = 0.5


class Harmonic(Base):
    """An nth-order contribution at λ/n from a monochromator that passes order.

    Named for the mechanism rather than the symptom: it is the **nth-order
    reflection from the same monochromator planes**, which is why it is general
    in n and why no monochromator setting removes it.  Published experimental
    sections use exactly this vocabulary — "a Cu(311) monochromator was used,
    with a constant wavelength of λ = 1.5402(2) Å and a second-order
    contribution at λ/2" (Gaultois *et al.*, *J. Phys.: Condens. Matter*,
    2013), describing the NIST BT-1 diffractometer this correction is validated
    against.

    A crystal monochromator set to pass λ by Bragg reflection from planes of
    spacing d_M satisfies λ = 2 d_M sin θ_M.  At that *same* setting the
    condition λ/n = 2 (d_M/n) sin θ_M also holds, and d_M/n is the spacing of
    the nth-order reflection of the same planes — so the beam carries λ/n for
    every n ≥ 2 whose reflection n·(hkl) is not extinct.  The order is a
    property of the reflection, not of the geometry, so no adjustment of the
    monochromator angle removes it; only something that discriminates by energy
    does — a filter, a second crystal detuned off the harmonic's rocking curve,
    or an extinct nth order.

    **The extinction route is the one that decides a real beamline**, and it is
    arithmetic rather than a measurement.  A germanium monochromator (diamond
    structure) cut on all-odd indices has |F| = 0 for its own second order: the
    doubled indices are all even, and the diamond structure factor
    1 + exp[2πi(h+k+l)/4] vanishes unless h+k+l ≡ 0 (mod 4).  Ge(733) doubles
    to (14,6,6) with h+k+l = 26 ≡ 2, so **Ge(733) passes no λ/2 at all**.  Cu
    is face-centred cubic with one atom per lattice point and no such
    cancellation: Cu(311) doubles to (622), all even, fully allowed — so
    **Cu(311) does pass λ/2**.  Two histograms of one specimen taken on those
    two monochromators are therefore a controlled pair by construction, which
    is what this correction is validated against (``tests/test_harmonics.py``).

    **Why this is an emission line and not a phase.**  At a fixed detector
    angle 2θ the λ/n beam satisfies λ/n = 2 d sin θ, so it is diffracting from
    planes of spacing d = λ/(2n sin θ) — the harmonic's peak from a given
    *hkl* therefore sits at **lower** 2θ than the fundamental's peak from the
    same *hkl*.  A phase with a doubled cell reproduces those positions (cell
    2a has d′ = 2d, and λ at d′ lands where λ/2 at d does) and is the usual
    workaround, but its structure factors are those of a fictitious doubled
    cell, so the *intensities* are wrong.  An emission line at λ/n diffracts
    the **same** *hkl* list with the **same** |F|², which gets positions and
    intensities right together, and costs one refinable number instead of a
    whole phase.  This is also what the published Nd₂Ru₂O₇ pyrochlore
    refinement did: two wavelengths, λ and exactly λ/2, on one histogram, each
    with its own scale.

    ``weight`` follows the package's existing convention — relative to line 0
    of the source, which is structurally locked at 1 — so a declared harmonic
    is exactly one refinable parameter.  What that number *is* depends on the
    monochromator and is not predictable from the cut: reported values for
    real beamlines span a factor of ten, so it is refined, never assumed, and
    :data:`HARMONIC_WEIGHT_SEED` is set low on purpose.

    Refine it **only after the profile and the scale are settled**.  It is a
    small fraction that correlates with the background, and a fitted value far
    from a few per cent is evidence the model is absorbing something else
    through it — an unmodelled impurity, a bad background — rather than a
    measurement of the beam.
    """

    #: n in λ/n.  ``ge=2`` because n = 1 *is* the fundamental (declaring it
    #: would be a second copy of line 0, degenerate with the phase scales) and
    #: n ≤ 0 is not a diffraction order at all.
    order: int = Field(default=DEFAULT_HARMONIC_ORDER, ge=2)
    weight: Parameter = Field(
        default_factory=lambda: Parameter(
            value=HARMONIC_WEIGHT_SEED, min=0.0, max=HARMONIC_WEIGHT_MAX)
    )

    @property
    def wavelength_factor(self) -> float:
        """1/n — what the fundamental wavelength is multiplied by."""
        return 1.0 / float(self.order)


def check_harmonics(harmonics: list[Harmonic], *, kind: str,
                    supported: bool) -> None:
    """Refuse a harmonic declaration that cannot mean anything.

    One authority for every source class, so the refusals cannot drift.  An
    empty list returns immediately and touches nothing, which is what makes
    "off" exact rather than merely cheap.

    ``order`` itself is fenced on :class:`Harmonic` (``ge=2``: n = 1 is the
    fundamental, n ≤ 0 is not a diffraction order).  Two things only a
    *source* can see are checked here.  **Duplicate orders** would put two
    emission lines at one wavelength carrying two weights for one physical
    component — a flat direction, not a richer model.  And **whether this
    radiation's spectrum can carry a harmonic at all**, which is
    ``Source.harmonics_supported`` — see that attribute for why the X-ray
    answer is no.
    """
    if not harmonics:
        return
    if not supported:
        orders = ", ".join(f"n = {h.order}" for h in harmonics)
        raise ValueError(
            f"a {kind} source cannot carry declared harmonics ({orders}): one "
            f"f' + i*f'' is frozen per phase and shared across every emission "
            f"line, which is exact only while f is real. lambda and "
            f"lambda/{harmonics[0].order} differ by 100 %, with absorption "
            f"edges between them in general, so "
            f"crystallography.dispersion.resolve refuses the pair anyway (its "
            f"limit is 1 % of Z) -- and smearing one f' across a "
            f"factor-of-two wavelength gap is the one thing that must not "
            f"happen silently. Two routes are open. Use a neutron source, "
            f"where there is no dispersion channel to disagree with and "
            f"harmonics are supported. Or, on an X-ray source, declare the "
            f"lambda/n component as a plain EmissionLine in source.lines with "
            f"source.dispersion = None: with f = f0 the structure factor "
            f"depends on the reflection (through sin(theta)/lambda = 1/2d) "
            f"and not on which wavelength diffracts it, so one |F|^2 serves "
            f"both lines exactly. That forgoes the order declaration and so "
            f"the HARMONIC_FRACTION diagnostic, which is the whole difference")
    seen: set[int] = set()
    for h in harmonics:
        if h.order in seen:
            raise ValueError(
                f"duplicate harmonic order n = {h.order} on a {kind} source: "
                f"two declarations of the same order put two emission lines at "
                f"the same wavelength with two weights on one physical "
                f"component, which is a flat direction rather than a richer "
                f"model -- declare each order once")
        seen.add(h.order)


class NeutronSource(Base):
    """Constant-wavelength **neutron** source: one wavelength, nuclear scattering.

    A separate class rather than a flag on :class:`Source`, because almost every
    field of an X-ray source is meaningless here and a class that has to explain
    which of its own fields are inert is worse than two classes.  What differs:

    * **One wavelength, no emission-line list.**  A monochromator or chopper
      selects a single λ; there is no Kα1/Kα2 doublet and no line-weight ratio
      to refine.
    * **No anomalous dispersion.**  f′/f″ is an X-ray core-level effect.  The
      neutron analogue — a complex, wavelength-dependent b near a nuclear
      resonance — is a property of a handful of nuclides rather than a
      correction applied to all of them, and is fenced out of this class (see
      :mod:`rietx.crystallography.neutron`).
    * **The polarisation term is identically 1.**  Neutrons are not polarised
      by the monochromator the way the Thomson cross-section polarises X-rays,
      so the Lorentz-polarisation factor reduces to the bare Lorentz factor
      1/(sin²θ·cosθ), which is geometry and radiation-independent.  In the
      existing form Lp = [K + (1 − K)·cos²2θ]/(sin²θ·cosθ) that is exactly
      K = 1, so this class needs **no new correction code** — it pins K.

    ``polarization`` is therefore force-fixed at 1.0 and refusing to be
    anything else: a parameter the forward branch cannot use must be
    force-fixed rather than merely left unfree, or a free entry becomes a dead
    column in the Jacobian.
    """

    kind: Literal["neutron_cw"] = "neutron_cw"
    #: Å.  **Fixed by default** — for one histogram a powder pattern cannot
    #: separate λ from the cell (they enter d = λ/(2 sin θ) as a product),
    #: which is why a certified standard is refined with its cell held to
    #: calibrate λ rather than the other way round.  In a *joint* fit of
    #: several histograms of one specimen the product splits: see
    #: :class:`EmissionLine` and
    #: :func:`rietx.params.multi.check_wavelength_freedom`.  A bare number is
    #: accepted and becomes a fixed parameter.
    wavelength: Parameter

    @field_validator("wavelength", mode="before")
    @classmethod
    def _coerce_wavelength(cls, v):
        return _as_wavelength(v)

    @model_validator(mode="after")
    def _positive_wavelength(self) -> "NeutronSource":
        if self.wavelength.value <= 0.0:
            raise ValueError(
                f"wavelength must be positive, got {self.wavelength.value}")
        return self

    #: λ/n components the monochromator does not filter (:class:`Harmonic`).
    #: **Empty is off and off is exact**: with no harmonic declared
    #: :attr:`lines` is the single line it has always been, so every number
    #: measured before this field existed is reproduced bit for bit.  This is
    #: where a harmonic normally belongs — a CW neutron monochromator is the
    #: usual offender, and unlike :class:`Source` there is no anomalous
    #: dispersion here for the λ/n line to disagree with.
    harmonics: list[Harmonic] = Field(default_factory=list)

    #: True here — the counterpart of :attr:`Source.harmonics_supported`, and
    #: for the reason that attribute gives: there is no dispersion channel on
    #: this radiation, so one |F|² serves λ and λ/n exactly.
    harmonics_supported: ClassVar[bool] = True

    @model_validator(mode="after")
    def _harmonics_are_admissible(self) -> "NeutronSource":
        check_harmonics(self.harmonics, kind="constant-wavelength neutron",
                        supported=self.harmonics_supported)
        return self

    @property
    def lines(self) -> list[EmissionLine]:
        """The fundamental, then one line per declared harmonic at λ/n.

        The fundamental's weight is structurally 1: with one line there is
        nothing for a relative weight to be relative to, and it would be
        degenerate with the phase scales in any case.  A harmonic's weight is
        the *stored* :class:`Parameter` off :attr:`harmonics`, passed by
        reference rather than copied, which is what makes a refined value
        survive the write-back (``params.vector.ParameterTable.write_back``
        reaches it as ``instrument.source.lines.i.weight``).

        Building the list here rather than materialising the extra lines into a
        field is what keeps the *declaration* and the *spectrum* one fact: an
        order can never be listed twice under two weights, the wavelength is
        never stored as a number that could drift from λ/n, and nothing
        downstream needs to know a line is a harmonic — it is an emission line,
        so the reflection generator, the per-line Lorentz factor, the frozen
        windows and ``RefinementResult.ticks`` all serve it already.

        **A fresh object every access**, so this is a read-only view: the
        wavelength a table writes back to lives at ``self.wavelength``, and the
        one authority for reaching it either way is
        :attr:`wavelength_parameters`.

        **A harmonic's λ is derived and therefore never free**, even when the
        fundamental is.  It is λ/n by construction, so a second free handle on
        it would be a second name for one number — the degeneracy this whole
        class is written to avoid.  Deriving it here rather than storing it is
        also what makes a *refined* fundamental propagate: the table writes
        λ back to ``self.wavelength``, and the next access rebuilds every λ/n
        from the new value.  A stored harmonic wavelength would silently keep
        the old one.
        """
        out = [EmissionLine(wavelength=self.wavelength.model_copy(),
                            weight=Parameter(value=1.0, vary=False))]
        out += [EmissionLine(
                    wavelength=Parameter(
                        value=self.wavelength.value * h.wavelength_factor,
                        vary=False, unit=self.wavelength.unit),
                    weight=h.weight)
                for h in self.harmonics]
        return out

    @property
    def wavelength_parameters(self) -> list[Parameter]:
        """The live, *independently refinable* wavelengths, in line order.

        The one authority for *writing* a refined wavelength back, and the
        reason it exists: :attr:`lines` is a property here and a stored field
        on :class:`Source`, so a write through ``source.lines[i].wavelength``
        lands on a throwaway object for a neutron source and on the model for
        an X-ray one.  ``params/vector.py`` reads and writes through this
        instead, which is what keeps a refined λ from silently vanishing at the
        next recompile.

        **Shorter than** :attr:`lines` **whenever a harmonic is declared, and
        that is the point.**  A λ/n line has no independent wavelength to write
        back to — it is derived in :attr:`lines` from this one — so listing it
        here would offer a handle whose writes go nowhere.  Anything pairing
        the two must key by the fundamental rather than zip them.
        """
        return [self.wavelength]

    @property
    def primary_wavelength(self) -> float:
        return self.wavelength.value

    @property
    def polarization(self) -> Parameter:
        """K = 1, force-fixed — the docstring above says why."""
        return Parameter(value=1.0, vary=False, min=1.0, max=1.0)

    @property
    def dispersion(self) -> None:
        """Always ``None``; the X-ray path tests this to decide f′/f″."""
        return None


class Dispersion(Base):
    """Anomalous scattering corrections f′, f″ at the source wavelengths.

    **On by default since v1.0** (it was opt-in through v0.5-v0.6, so every
    number in ``docs/milestones/`` up to and including v0.6 was measured with
    it off).  It is *not* a refinement — f′ and f″ are fixed constants of
    (element, wavelength), looked up once at stage compile from
    ``crystallography.dispersion``.

    What makes it a default rather than an opt-in is that it is the only
    correction here needing **no information the caller does not already
    have**: capillary absorption wants µR, roughness wants a specimen surface,
    Stephens wants a strain model, March-Dollase wants a habit — dispersion
    wants the species and the wavelength, both of which are already in the
    model.  Neglecting it is not a neutral simplification: it mis-scales every
    reflection of a species by ((Z + f′)² + f″²)/Z² − 1, which is −16 % for
    ZnO at Cu Kα and +7 % for CaF₂, and unequal effects across phases bias QPA
    weight fractions directly (measured: RMS error 2.26 → 0.69 wt % on the
    IUCr round robin).

    Set ``source.dispersion = None`` to decline it and reproduce the ≤ v0.6
    behaviour exactly — that is also the escape hatch when the table cannot
    answer, since a wavelength inside an absorption-edge interval raises
    rather than interpolating across the edge (WP-1001 census: 12 of 1176
    element × shipped-anode combinations, including Eu and Ho at Cu Kα).

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
    #: The *declared* lines.  Harmonics are appended by :attr:`spectrum`, not
    #: stored here — see :attr:`harmonics`.
    lines: list[EmissionLine]
    polarization: Parameter = Field(
        default_factory=lambda: Parameter(value=0.5, min=0.0, max=1.0)
    )
    #: anomalous scattering, **on by default since v1.0**; None ⇒ f = f₀,
    #: bit-identical to the non-anomalous model and to every number recorded
    #: in ``docs/milestones/`` through v0.6 (see :class:`Dispersion`)
    dispersion: Dispersion | None = Field(default_factory=Dispersion)
    #: Declared λ/n harmonics — **refused on this radiation**, and the field
    #: exists so that the refusal can name the reason instead of arriving as
    #: pydantic's "extra inputs are not permitted".  See
    #: :attr:`harmonics_supported` and :func:`check_harmonics`.
    harmonics: list[Harmonic] = Field(default_factory=list)

    #: One authority, two consumers: :func:`check_harmonics` refuses a declared
    #: harmonic when this is False, and ``capabilities()`` reports it — so the
    #: flag and the behaviour cannot disagree, and X-ray support would land as
    #: one edit here rather than as a capability that lies.
    #:
    #: False for X-rays because ``f_anom`` is resolved once per phase and
    #: shared across the emission lines, which the λ/n line breaks: f′/f″ are
    #: functions of λ alone and λ against λ/2 is a 100 % change.  Supporting it
    #: honestly means a per-line ``PhaseSites`` and a per-line |F|², i.e.
    #: giving up the sharing this correction otherwise depends on — a different
    #: change, not a flag.  The route that needs no new code is in
    #: :func:`check_harmonics`'s message.
    harmonics_supported: ClassVar[bool] = False

    @model_validator(mode="after")
    def _nonempty(self) -> "Source":
        if not self.lines:
            raise ValueError("source has no emission lines")
        return self

    @model_validator(mode="after")
    def _harmonics_are_admissible(self) -> "Source":
        check_harmonics(self.harmonics, kind="constant-wavelength X-ray",
                        supported=self.harmonics_supported)
        return self

    @property
    def wavelength_parameters(self) -> list[Parameter]:
        """The live wavelength :class:`Parameter` of each line, in line order.

        The peer of :attr:`NeutronSource.wavelength_parameters` — that
        docstring says why both exist.
        """
        return [line.wavelength for line in self.lines]

    @property
    def primary_wavelength(self) -> float:
        return self.lines[0].wavelength.value


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

    ``debye_scherrer``: spinning capillary (synchrotron or lab).  Two things
    move its peaks: ``zero_shift``, and the capillary sitting off the centre of
    the 2θ circle (McCusker, Von Dreele, Cox, Louër & Scardi, 1999,
    *J. Appl. Cryst.* **32**, 36-50, §5 eq 4),

        Δ2θ = (−a·sin2θ + b·cos2θ)/R   [radians],  R = goniometer radius (mm)

    where ``capillary_offset_along_beam`` (a) is the displacement along the
    incident beam, positive downstream, and ``capillary_offset_across_beam``
    (b) is the displacement perpendicular to it in the diffraction plane,
    positive toward increasing 2θ.  Physics, not letters — the paper writes
    (x·sin2θ − y·cos2θ)/R and other codes pair the letter x with the *other*
    term, so only the signatures travel; the derivation that fixes both signs
    is in :func:`rietx.model.corrections.capillary_displacement_shift_deg`.
    Both default to 0 with ``vary=False``: a laboratory capillary or Guinier
    camera is where the aberration bites, and at a synchrotron with a crystal
    analyser the paper says displacement error is eliminated, so freeing them
    is a deliberate act.  Both need ``goniometer_radius_mm``, which eq (4)
    divides by; setting a value or freeing one without it is refused rather
    than defaulted.  ``zero_shift`` + a + b is three positional corrections
    over {1, sin2θ, cos2θ} — separable over a wide range and badly collinear
    over a short low-angle one, which is what ``analyse_trends`` and the
    identifiability layer report.

    Cylindrical **absorption** is applied as an
    intensity factor when µR > 0 (Rouse, Cooper, York & Chakera, 1970, *Acta
    Cryst.* A26, 682; see :mod:`rietx.model.absorption`), µR coming either
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
    nothing else**: only ``zero_shift`` moves its peaks.  A transmission
    goniometer has its own displacement aberration, and this package does not
    model it rather than inventing one; if a specimen is badly enough off-axis
    for that to matter, the peak positions are not trustworthy anyway.  That
    argument is about *this* geometry only — for a capillary the published
    correction exists (eq 4 above), so the same sentence stopped applying
    there once the paper was read (WP-1073).

    ``mu_t`` — dimensionless µ times **specimen thickness** — turns on the
    flat-plate absorption factors for both flat geometries
    (:mod:`rietx.model.absorption`, *International Tables* Vol. C
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
    #: capillary displacement along the incident beam (mm, positive
    #: downstream) — the sin 2θ half of eq (4).  ``debye_scherrer`` only.
    capillary_offset_along_beam: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, min=-1.0, max=1.0, unit="mm")
    )
    #: capillary displacement perpendicular to the beam in the diffraction
    #: plane (mm, positive toward increasing 2θ) — the cos 2θ half of eq (4).
    capillary_offset_across_beam: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, min=-1.0, max=1.0, unit="mm")
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
    def _capillary_offsets_need_a_radius(self) -> "Geometry":
        # eq (4) divides by R.  A default radius would be an invented
        # instrument, and a silently-ignored offset would be a value the user
        # set and the model did not use, so both are refused here — naming the
        # field that is missing.  ``ParameterTable`` repeats the check for
        # ``vary`` because a mutation after construction re-runs no validator.
        for name in CAPILLARY_OFFSETS:
            offset = getattr(self, name)
            if offset.value == 0.0 and not offset.vary:
                continue
            if self.kind != "debye_scherrer":
                raise ValueError(
                    f"{name} is a capillary (debye_scherrer) correction, "
                    f"McCusker et al. (1999) eq (4); this geometry is "
                    f"{self.kind!r}")
            if not self.goniometer_radius_mm:
                raise ValueError(
                    f"{name} needs goniometer_radius_mm: eq (4) is "
                    f"Δ2θ = (−a·sin2θ + b·cos2θ)/R and R is unset")
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
    flag it (``rietx.background.diagnose``).
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

    The fixed curve typically comes from :func:`rietx.background.estimate`
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


#: :class:`BackgroundPeak`'s refinable fields, in path order.  One authority for
#: the three names: ``params.vector.background_peak_parameters`` registers them,
#: ``ParameterTable.apply_to_models`` writes them back, ``compile_model`` freezes
#: the paths and ``strategy.staged`` reads them — so adding a fourth (an η, say)
#: is one edit rather than five that can drift.  The sub-path *is* the field
#: name, which is what makes ``instrument.background_peaks.0.fwhm`` legible.
BACKGROUND_PEAK_FIELDS: tuple[str, ...] = ("position", "height", "fwhm")

#: Lower bound on :attr:`BackgroundPeak.fwhm`, in °2θ.  The Gaussian divides by
#: Γ, so this is the :data:`~rietx.schemas.structure.MARCH_R_MIN` situation and
#: not a `min=0.0` one: ``internal_bounds`` maps any lower bound ≤ 1e-12 to −∞
#: and ``log(1+e^u)`` underflows to *exactly* 0.0, so a softplus "strictly
#: positive" width is a promise the transform does not keep and a zero width is
#: a pole (root CLAUDE.md § Invariants).
#:
#: The number comes from the sampling rule the rest of the package already
#: quotes: :data:`rietx.background.diagnostics.STEPS_PER_FWHM_MIN` = 5 steps
#: across a feature is the minimum at which anything can be refined from it, and
#: 0.02 °2θ is the finest step a routine powder scan uses — 5 × 0.02 = 0.1.
#: Below that a "background feature" is narrower than a handful of channels,
#: which is a Bragg peak or a spike, not diffuse scattering.  It is a floor on
#: the *parameterisation*, deliberately far below any real hump (whole degrees):
#: it exists to make the pole unreachable, not to encode a physical width.
BACKGROUND_PEAK_FWHM_MIN = 0.1

#: Softplus lower bound at or under which `internal_bounds` gives up on the
#: bound entirely — the same 1e-12 `schemas/structure.py` uses, restated here
#: rather than imported so `schemas/instrument.py` keeps importing nothing from
#: its sibling.
_SOFTPLUS_FLOOR = 1e-12


class BackgroundPeak(Base):
    """One explicit broad Gaussian added on top of whatever background is in use.

    A localised background feature — a diffuse/amorphous hump, an unmodelled
    scattering contribution from the sample environment, a cryostat or container
    artefact — described by three numbers instead of by making the polynomial or
    the spline flexible enough to contort into it:

        y_peak(2θ) = h · exp[ −4 ln2 · ((2θ − 2θ₀)/Γ)² ]

    **This is an empirical basis function, not a diffraction profile.**  A
    Gaussian in 2θ has no derivation behind it here and does not pretend to
    one — genuinely amorphous scattering is a Debye/RDF term in Q, not a
    Gaussian in angle.  What is cited is the *practice*: an explicit broad peak
    added to the background is what GSAS-II exposes as a background peak
    (position, intensity, width; Toby & Von Dreele, 2013, *J. Appl. Cryst.*
    **46**, 544) and what TOPAS exposes as a cell-less "peaks phase"
    (``xo_Is`` + ``gauss_fwhm``; Coelho, 2018, *J. Appl. Cryst.* **51**, 210).
    The :class:`Background` docstrings cite Chebyshev and P-spline practice the
    same way, and this sits in that register.

    **Why it is not a fourth** :data:`Background` **member.** It composes with
    all three rather than replacing any — it is an additive term beside the
    background, so it lives on :attr:`Instrument.background_peaks` and the
    design matrix is untouched.  It is also not a :class:`~rietx.Phase`: a phase
    here is crystallographic through and through (cell ties, Wyckoff sites,
    QPA) and a cell-less one breaks every consumer of it.

    **Why the flexibility has to be local, measured.**  APS 11-BM run 4918, NIST
    SRM 640c silicon in a **Kapton capillary** (``tests/data/11BM_Si640c.xy``,
    47 999 channels over 1.997-49.996 °2θ, σ from file), refined by
    ``tests/test_acceptance_si640c.py``'s protocol with the background swapped
    from its P-spline to a low-order Chebyshev.  One phase, cell held at the NIST
    certificate:

    ==============================  ======  ========  ============  ================
    background                       terms  Rwp       Biso(Si)/Å²   HIGH_CORRELATION
    ==============================  ======  ========  ============  ================
    Chebyshev, 3 terms                   3  0.119977  0.414(75)                    0
    that **+ one peak**              3 + 3  0.082503  0.421(12)                    0
    Chebyshev, 6 terms                   6  0.088597  0.422(29)                    0
    that **+ one peak**              6 + 3  0.077152  0.4235(85)                   0
    ==============================  ======  ========  ============  ================

    **Three parameters beat three polynomial terms.**  Rows one and two differ by
    three numbers and so do rows one and three — the peak takes Rwp down 31 %
    relative, three more Chebyshev coefficients only 26 %.  Biso(Si) barely moves
    (well inside one esd) but its **esd falls 6×**, and so do those of λ, the
    scale and the zero shift: an undescribed background blurs this fit rather
    than biasing it.

    **The feature is identified from outside the fit.**  The refined peak is
    5.57(27)° wide against an instrumental Gaussian FWHM of 0.00346° at that
    angle — 1 608×.  11-BM's published blank (run 4736, ``empty Kapton
    capillary``, same February 2010 beamtime), fitted independently of this
    package, puts the same feature at 4.2417(111)° with FWHM 6.153(23)°, and the
    beamline's published air-scatter scan shows no localised feature anywhere.
    The blank's envelope maximum, d = 4.74 Å (Q = 1.33 Å⁻¹), is the polyimide
    halo.  That — not the Rwp — is what makes the term quotable.

    **A peak needs a low-order background to mean anything.**  Between the
    3-term and 6-term arms the peak moves 1.07° and narrows from 5.57(27)° to
    1.94(11)° while Rwp moves by 0.005: the peak and the polynomial describe
    overlapping freedom, so the more flexible the polynomial the less the peak's
    own parameters mean.  Declare a peak *instead of* extra polynomial terms,
    never on top of them.

    **The refined centre is not the halo position.**  A symmetric Gaussian
    spanning 2-50° also absorbs the residual direct-beam rise a 3-term Chebyshev
    cannot reach, which pulls the fitted centre to 4.18(11)° below the envelope's
    4.98°; at six terms it relaxes onto the envelope at 5.245(41)°.  Quote the
    envelope for where the halo is and the fit for the model that describes it.
    ``docs/manual/using/data.md`` carries the long form and
    ``tests/data/README.md`` the provenance of every file named here.

    Fields, and the reason each bound is the bound it is:

    * ``position`` — °2θ, identity transform, **unbounded by default**.  It is
      not a Bragg position, so nothing constrains it but the data; and the
      bound one would want — the fitted range — is not a fact this schema can
      see, since it depends on the pattern and on the excluded regions.  That
      makes it the solver's per-stage window rather than a property of the
      stored parameter, which is the ``cell_window`` rule
      (:mod:`rietx.params.vector`), and a window is worth building only where
      the failure it prevents is fatal.  Here it is merely uninformative: a
      position that walks off the measured range stops moving Rwp, and comes
      back as an unmeasured row with **no** esd rather than a small one, which
      ``ParameterTable.unmeasured_rows`` already names.  A caller who knows the
      range may set ``min``/``max``, and a finite stored bound is the caller's
      claim, as everywhere else.
    * ``height`` — softplus, ``min=0.0``, default 0.0.  ``min=0.0`` under
      softplus is safe here for exactly one reason: **zero is the off state.**
      h = 0 makes the whole term identically zero and the peak contributes
      nothing anywhere, so the underflow softplus permits lands on the
      identity, not on a pole (contrast ``PreferredOrientation.r``, whose
      identity is interior at r = 1 with the pole *at* the bound).
    * ``fwhm`` — °2θ, softplus, floored at :data:`BACKGROUND_PEAK_FWHM_MIN`
      with a reachability validator, because this one *does* divide.
    * shape — **Gaussian only, and the fence is deliberate.**  No mixing
      parameter: a broad feature is described by a few tens of channels of
      curvature sitting on a polynomial that can already absorb the difference
      between a Gaussian and a pseudo-Voigt, so η would be a third number the
      data cannot separate from the terms underneath it.  It is also what the
      practice being matched does — TOPAS's ``gauss_fwhm``.  If a mixing
      parameter is ever added, its identity is interior (η = 0 and η = 1 are
      both legitimate ends, so the ``PreferredOrientation.r`` trap applies) and
      it needs a logit transform, not a softplus.

    All three default to ``vary=False``: a declared peak is inert until a stage
    frees it, and ``height = 0`` means a declared-but-never-freed peak is
    bit-identical to no peak at all.
    """

    #: apparent position of the hump in °2θ.  Required — there is no default
    #: place for a background feature, and a defaulted one would be a claim.
    position: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, unit="deg"))
    height: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, min=0.0, unit="counts",
                                          transform="softplus"))
    fwhm: Parameter = Field(
        default_factory=lambda: Parameter(value=5.0,
                                         min=BACKGROUND_PEAK_FWHM_MIN,
                                         unit="deg", transform="softplus"))
    #: free-text tag, e.g. ``"cryostat tail"``.  Not a parameter and not part of
    #: any dot-path — the paths index the list, so a relabelled peak keeps its
    #: refined values.
    label: str | None = None

    @model_validator(mode="after")
    def _fwhm_floor_is_reachable(self) -> "BackgroundPeak":
        """Repair a width bound softplus cannot actually enforce.

        The ``PreferredOrientation._r_bound_is_reachable`` pattern, and for the
        same reason: the broken bound **outlives the default**.  A JSON project
        or a history node written with ``min: 0.0`` deserializes straight back
        into the pole, and no default_factory ever runs on that path.  Only a
        bound at or under the softplus floor is touched; any positive bound a
        caller chose already maps to a finite internal one and is left alone.
        """
        if self.fwhm.min <= _SOFTPLUS_FLOOR:
            # value **before** min: ``Base`` validates on assignment, so raising
            # the floor under a value that is still below it would trip
            # ``Parameter._check_bounds`` mid-repair.  Lifting the value first is
            # always legal — the old bound was ≤ 1e-12.
            self.fwhm.value = max(self.fwhm.value, BACKGROUND_PEAK_FWHM_MIN)
            self.fwhm.min = BACKGROUND_PEAK_FWHM_MIN
        return self


class Instrument(Base):
    """Everything about the measurement except the sample.

    A declaration, not an output: the number an agent usually wants first is
    ``instrument.source.primary_wavelength`` (a plain float, the first line's
    wavelength); a fitted value comes back on the *result*, never here.
    """

    #: Discriminated on ``kind``: ``"xray_cw"`` is :class:`Source`,
    #: ``"neutron_cw"`` is :class:`NeutronSource`.  A union rather than one
    #: class with inert fields — see :class:`NeutronSource`.
    source: Source | NeutronSource = Field(discriminator="kind")
    geometry: Geometry = Field(default_factory=Geometry)
    zero_shift: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, min=-0.5, max=0.5, unit="deg")
    )
    profile: ProfileTCHZ = Field(default_factory=ProfileTCHZ)
    background: Background = Field(
        default_factory=lambda: BackgroundChebyshev(), discriminator=None
    )
    #: Explicit broad peaks **added on top of** ``background``, not a kind of
    #: it (:class:`BackgroundPeak`).  The empty default is **exactly off**: no
    #: path is registered, no term is evaluated, and the serialized instrument
    #: differs from a pre-``background_peaks`` one only by ``[]`` — the idiom
    #: ``Structure.restraints``, ``Phase.microstrain`` and
    #: ``Geometry.surface_roughness`` already use, pinned by a bit-identity
    #: test rather than asserted here.
    #:
    #: The field name is ``background_peaks`` and **not** ``background.peaks``
    #: on purpose: fnmatch's ``*`` crosses dots, so a nested spelling would be
    #: matched by the ``instrument.background.*`` glob every preset's first
    #: stage carries, and every declared peak would be freed at stage 1 — a
    #: free position over a pattern whose peaks have not been placed yet.  The
    #: underscore puts the paths outside that glob by construction instead of
    #: by retightening seven presets.
    background_peaks: list[BackgroundPeak] = Field(default_factory=list)

    @model_validator(mode="after")
    def _radiation_admits_its_corrections(self) -> "Instrument":
        """Refuse a correction whose derivation assumes the other radiation.

        ``Geometry`` already refuses ``surface_roughness`` outside
        ``bragg_brentano`` — that is a *geometry* fence, and this is the
        radiation one beside it.  Both roughness models depress the low-angle
        intensity because the beam samples less material where an irregular
        surface turns away from it, which needs the penetration depth to be
        comparable to the surface relief: microns for X-rays.  A thermal neutron
        beam penetrates centimetres of the same specimen, so the correction has
        no regime here rather than merely a small coefficient, and fitting it
        would buy Rwp from a parameter with nothing behind it.

        Refused rather than diagnosed because there is no legitimate reason to
        set it — unlike ``dispersion = None``, which has two — and because a
        stored roughness block is a claim, not a default.
        """
        if (self.source.kind != "xray_cw"
                and self.geometry.surface_roughness is not None):
            raise ValueError(
                f"surface_roughness is an X-ray correction and this source is "
                f"{self.source.kind!r}: both models (Suortti 1972, Pitschke "
                f"1993) depress the low-angle intensity of a beam that "
                f"penetrates microns, while a thermal neutron beam penetrates "
                f"centimetres — set geometry.surface_roughness = None")
        return self

    @classmethod
    def constant_wavelength_neutron(
            cls, wavelength: float, *,
            goniometer_radius_mm: float | None = None,
            capillary_radius_mm: float | None = None,
            mu_r: float | None = None,
            fwhm_deg: float | None = None,
            harmonics: bool | list[int] = False) -> "Instrument":
        """Constant-wavelength neutron powder diffractometer.

        Debye-Scherrer geometry, because that is what a CW neutron
        diffractometer is — a can of powder in a beam with detectors on a
        circle — so the cylindrical absorption correction and the eq (4)
        capillary offsets apply unchanged.

        ``fwhm_deg`` seeds the Caglioti terms from an observed peak width, which
        matters more here than on a lab X-ray: a neutron instrument's lines are
        typically 0.2-0.5° where the ``ProfileTCHZ`` default is a *synchrotron*
        line of ~0.03°, and the frozen per-stage evaluation windows are sized
        from the seed.  Left ``None``, the default stands and a 0.3° line will
        not be found.

        It seeds ``w`` **only**, so the seeded profile is a flat Gaussian of
        exactly ``fwhm_deg`` at every angle -- the width you observed is the
        width you get, which is what makes the argument checkable.

        Note the profile itself needs no neutron-specific code: the Caglioti
        law U·tan²θ + V·tanθ + W *is* the neutron resolution function (Caglioti,
        Paoletti & Ricci, 1958, *Nucl. Instrum.* **3**, 223), and the X-ray path
        is the borrower.

        ``harmonics`` declares the λ/n components a monochromator that does not
        filter its own orders lets through (:class:`Harmonic`).  ``True`` is the
        second order alone, which is the one that normally carries measurable
        intensity; a list of orders is the general form (``harmonics=[2, 3]``).
        ``False``, the default, leaves the source with the single line it has
        always had, so every number measured before this argument existed is
        reproduced bit for bit.  The declared weights arrive **fixed** — free
        them with the ``instrument.source.lines.*.weight`` glob once the profile
        and the scale are settled, never in the opening stage.
        """
        orders: list[int] = []
        if harmonics is True:
            orders = [DEFAULT_HARMONIC_ORDER]
        elif harmonics is not False:
            orders = list(harmonics)
        inst = cls(source=NeutronSource(
                       wavelength=wavelength,
                       harmonics=[Harmonic(order=n) for n in orders]),
                   geometry=Geometry(kind="debye_scherrer",
                                     goniometer_radius_mm=goniometer_radius_mm,
                                     capillary_radius_mm=capillary_radius_mm,
                                     mu_r=mu_r))
        if fwhm_deg is not None:
            # Seed the Gaussian constant term alone, at the *full* observed
            # width: with U = V = 0 the Caglioti law gives Gamma_G = sqrt(W),
            # so W = fwhm^2 reproduces `fwhm_deg` exactly and at every angle
            # (issue #124).  `x` is deliberately left at its default.  It is
            # the Lorentzian Scherrer term, Gamma_L = X/cos(theta), so seeding
            # it from an observed width both double-counts the width and makes
            # the seed climb with angle -- 3.93x the stated FWHM at 150 deg,
            # over exactly the high-angle peaks a CW neutron cell refinement
            # leans on hardest.  A real CW resolution function is narrowest
            # near the focusing angle and widens either side (Caglioti,
            # Paoletti & Ricci 1958), so a monotonically climbing seed is not
            # a coarse version of that curve; a flat one is the honest
            # zeroth-order stand-in, and U/V/X/Y refine away from it.
            inst.profile.w.value = fwhm_deg ** 2
        return inst

    @classmethod
    def debye_scherrer(cls, wavelength: float, *, polarization: float = 0.99,
                       goniometer_radius_mm: float | None = None,
                       capillary_radius_mm: float | None = None,
                       packing_fraction: float = 0.6,
                       mu_r: float | None = None) -> "Instrument":
        """Synchrotron/capillary preset with a single wavelength.

        ``polarization`` follows the GSAS POLA convention (see :class:`Source`);
        0.99 matches APS 11-BM instrument-parameter files.

        Cylindrical absorption stays **off** unless a capillary radius or an
        explicit ``mu_r`` is given, and the eq (4) displacement offsets stay at
        zero and fixed whether or not ``goniometer_radius_mm`` is given — so
        the preset's historical meaning ("no aberrations") is unchanged for a
        caller that passes none of the three.  R is what eq (4) divides by:
        declare it to make the offsets refinable, which is the laboratory
        capillary case (:class:`Geometry`).
        """
        return cls(
            source=Source(
                lines=[EmissionLine(wavelength=wavelength)],
                polarization=Parameter(value=polarization, min=0.0, max=1.0),
            ),
            geometry=Geometry(kind="debye_scherrer", mu_r=mu_r,
                              goniometer_radius_mm=goniometer_radius_mm,
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
#: contamination check live in ``rietx.background.diagnostics``.
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
