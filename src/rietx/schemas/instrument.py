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
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from pydantic import Field, field_validator, model_validator

from ..model.profiles.caglioti import _MIN_GAMMA_G2
from .common import Base, Parameter, _InheritsDeclaredDefaults

if TYPE_CHECKING:  # the blank a measured background is built from
    from .pattern import PatternData

#: Å.  Strictly positive floor for a wavelength :class:`Parameter`.  λ reaches
#: the model only through sin θ = λ/2d, so λ ≤ 0 puts every reflection at
#: 2θ = 0 (or off the sphere) and the profile derivatives go with it — the
#: "``min=0`` where the physics divides" trap of the root ``CLAUDE.md``,
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


class EmissionLine(_InheritsDeclaredDefaults):
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
    #: Bounded at 0 and nowhere above (WP-2002, the B9 ruling of 2026-10-19):
    #: an intensity ratio cannot be negative, and how strong a second line is
    #: relative to the first is the data's to say.  The ceiling of 2 it carried
    #: before 1.10 had no stated source.  TOPAS's default for an emission line's
    #: ``la`` is 1e-5 to 2·Val + 0.1, recomputed every iteration, so it limits
    #: a step and never the answer (Tech Ref Version 9 § 2.17, Table 2-1).
    weight: Parameter = Field(
        default_factory=lambda: Parameter(value=1.0, min=0.0)
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


#: Seed for a harmonic's relative weight.  Deliberately small and deliberately
#: *not* any of the numbers the literature reports for a real beamline (see
#: :class:`Harmonic`): a seed at the expected answer is how a correction comes
#: back confirming its own prior.  1 % is far enough below every reported value
#: that the refinement has to travel to reach one.
HARMONIC_WEIGHT_SEED = 0.01


class Harmonic(_InheritsDeclaredDefaults):
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
    #: n ≤ 0 is not a diffraction order at all.  No default (WP-2002, the
    #: eighth round's item 4): which orders pass is a fact about the
    #: monochromator's crystal (the extinction route above), so a default of 2
    #: was the package choosing for a Ge(733) or Si(111) beam, which passes no
    #: λ/2.  Every saved harmonic carries its order, so old files still read.
    order: int = Field(ge=2)
    # Every attribute stated, ``unit`` and the infinite ``max`` included: the
    # derived emission line takes this object by reference
    # (:attr:`NeutronSource.lines`) so a refined weight writes back here, and a
    # Parameter leaving any attribute unset is copied on the way into a class
    # that inherits declared ranges (``_InheritsDeclaredDefaults``), which
    # would cut that link.
    #
    # **No ceiling** (WP-2002, the B9 ruling of 2026-10-19).  The 0.5 it
    # carried before 1.10 was a chosen limit on a quantity that stays physical:
    # a weight is an intensity ratio, and only below 0 is it not one.  A large
    # value is still the finding the old ceiling was meant to make, and
    # ``HARMONIC_FRACTION`` says so at ``warning`` past
    # :data:`~rietx.refine.HARMONIC_IMPLAUSIBLE_FRAC`.
    weight: Parameter = Field(
        default_factory=lambda: Parameter(
            value=HARMONIC_WEIGHT_SEED, min=0.0, max=math.inf, unit=None)
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


#: µs/Å.  Floor for :attr:`TOFSource.difc`, and a fence rather than a claim.
#: DIFC = (m_N/h)·(L₁ + L₂)·2 sin θ is a *geometry*: a positive flight path and
#: a positive Bragg angle, so it is strictly positive on every instrument that
#: exists, and d = TOF/DIFC at the leading order divides by it.  1.0 µs/Å is
#: nearly three orders below the smallest real bank found (GEM bank 1,
#: DIFC ≈ 740 µs/Å at 2θ = 8.67°).
_DIFC_MIN = 1.0

#: :class:`TOFSource`'s four calibration constants, in the order the four-term
#: relation writes them.  One authority for the names, the ``CAPILLARY_OFFSETS``
#: idiom: the field validator below coerces them and ``params.vector``
#: registers them as ``instrument.source.<name>`` and writes them back — so a
#: fifth term (or a rename) is one edit rather than several that can drift.
TOF_CONSTANTS: tuple[str, ...] = ("difc", "difa", "tzero", "difb")


def _as_parameter(v, **defaults):
    """Coerce a bare number into a :class:`Parameter`, the ``_as_wavelength`` way.

    A calibration constant arrives from an instrument-parameter file as a plain
    float far more often than as a refinement declaration, and typing
    ``Parameter(value=..., vary=False)`` four times at every construction site
    is the kind of ceremony that gets skipped.  Fixed by default, because a
    DIFC read from a `.iparm` is a *calibration*: it was refined against a
    standard, and freeing it against an unknown re-opens the flat direction
    between the constants and the cell.
    """
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return Parameter(value=float(v), vary=False, **defaults)
    return v


class ProfileTOF(_InheritsDeclaredDefaults):
    """GSAS **type-3** time-of-flight profile coefficients.

    Two back-to-back exponentials convoluted with a pseudo-Voigt (Von Dreele,
    Jorgensen & Windsor, 1982, *J. Appl. Cryst.* **15**, 581; the
    moderator-pulse form is Ikeda & Carpenter, 1985, *Nucl. Instrum. Methods A*
    **239**, 536), with every coefficient a polynomial in the reflection's
    **d-spacing** rather than in an angle — which is the whole structural
    difference from :class:`ProfileTCHZ` and the reason this is a separate
    container rather than five more fields on that one:

        α(d) = α₀ + α₁/d
        β(d) = β₀ + β₁/d⁴
        σ²(d) = σ₀² + σ₁²·d² + σ₂²·d⁴
        γ(d)  = γ₀ + γ₁·d + γ₂·d²

    The names are GSAS's own (``alp-0``, ``bet-1``, ``sig-2``, …) with the
    punctuation dropped, so an ``.iparm`` or ``.instprm`` maps onto them without
    a translation table anyone has to remember.  GSAS-II spells the first term
    of α as a lone ``alpha`` and adds ``beta-q``/``sig-q`` terms this container
    does not carry; the readers in :mod:`rietx.io.instrument_tof` record what
    they dropped rather than dropping it silently.

    **A container, and in this build nothing evaluates it.**  Reading a
    calibration losslessly is what it is for: ``params.vector`` registers all
    ten as ``instrument.source.profile_tof.*`` — fixed by default, like the
    calibration constants beside them — so a bank's table lists them, and no
    forward model reads them until the time-of-flight profile lands
    (yue-here/rietx issue #193).  They are the rows a stage freeing a bank's
    widths will address, which is why the constant-wavelength
    ``instrument.profile.*`` rows are not registered on a bank at all
    (:meth:`rietx.params.vector.ParameterTable._collect_instrument`).
    """

    #: µs⁻¹.  The d-independent part of the rise constant α.  A *rate*, like
    #: every α and β term here.
    alpha0: Parameter = Field(default_factory=lambda: Parameter(value=0.0, unit="1/us"))
    #: µs⁻¹·Å.  The 1/d term of α — GSAS-II's lone ``alpha``.
    alpha1: Parameter = Field(default_factory=lambda: Parameter(value=0.0, unit="A/us"))
    #: µs⁻¹.  The d-independent part of the decay constant β.
    beta0: Parameter = Field(default_factory=lambda: Parameter(value=0.0, unit="1/us"))
    #: The 1/d⁴ term of β.
    beta1: Parameter = Field(default_factory=lambda: Parameter(value=0.0, unit="A^4/us"))
    #: µs².  Gaussian **variance** terms, in d⁰, d² and d⁴ — variances, not
    #: FWHMs, which is why they are squares in the law above and why a value
    #: read from a file is used as written.
    #:
    #: **Floored at zero.**  ``sig-*`` are variance coefficients (GSAS
    #: Technical Manual p. 144), so each is floored at zero rather than only
    #: their sum at a given d; σ²(d) ≥ 0 is a *cone* coupling all three, which
    #: a box cannot express, so the whole polynomial is checked where it is
    #: evaluated.  The floor is each row's lower bound, which the driver holds
    #: as a box since every parameter is refined in its own units (WP-1938), and
    #: a free row starting on it is what ``Stage(seed=…)`` lifts.  Zero stays
    #: the default: it is a physical statement (no Gaussian broadening), and a
    #: negative value read from a file is refused by name at read.
    sig0: Parameter = Field(default_factory=lambda: Parameter(
        value=0.0, min=0.0, unit="us^2"))
    sig1: Parameter = Field(default_factory=lambda: Parameter(
        value=0.0, min=0.0, unit="us^2/A^2"))
    sig2: Parameter = Field(default_factory=lambda: Parameter(
        value=0.0, min=0.0, unit="us^2/A^4"))
    #: µs.  Lorentzian FWHM terms, in d⁰, d¹ and d² (GSAS's ``gam-0``…``gam-2``,
    #: profile function 3).  GSAS-II's ``.instprm`` names Lorentzian terms
    #: ``X``, ``Y``, ``Z`` for a TOF bank without publishing their d-laws, so
    #: that reader accepts them only at zero rather than map them here.
    gam0: Parameter = Field(default_factory=lambda: Parameter(value=0.0, unit="us"))
    gam1: Parameter = Field(default_factory=lambda: Parameter(value=0.0, unit="us/A"))
    gam2: Parameter = Field(default_factory=lambda: Parameter(value=0.0, unit="us/A^2"))

    @field_validator("*", mode="before")
    @classmethod
    def _coerce_coefficients(cls, v, info):
        """A bare number is a fixed :class:`Parameter`, as on :class:`TOFSource`.

        The same coercion the calibration constants beside these get, and for
        the same reason one rank up (:func:`_as_parameter`): a profile
        coefficient arrives from a ``.iparm`` ``PRCF`` block or from a
        seed table as a plain float far more often than as a refinement
        declaration, and ``ProfileTOF(alpha1=0.45)`` reading as a validation
        error is a papercut every harness on this track has hit.

        The **unit and bounds come from the field's own default**
        rather than from a table retyped here: a second spelling of ten units
        is a second thing to keep in step, and this way
        ``ProfileTOF(alpha1=0.45).alpha1.unit`` cannot disagree with
        ``ProfileTOF().alpha1.unit``.  Carrying the *bounds* is what makes
        the σ floor above real: a bare
        ``ProfileTOF(sig1=300.0)`` is how every harness on this track builds
        one, and coercing it to a plain unbounded parameter would
        have left the floor reachable only by callers who typed the whole
        ``Parameter`` out.  A ``Parameter`` passed in explicitly is left
        exactly as written — including a ``unit`` of ``None`` and bounds of
        its own — which is what :meth:`TOFSource._coerce_constants` does too:
        the caller who built one has said what they meant.
        """
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            return v
        default = cls.model_fields[info.field_name].get_default(
            call_default_factory=True)
        return _as_parameter(v, unit=default.unit, min=default.min,
                             max=default.max)


class IncidentSpectrum(_InheritsDeclaredDefaults):
    """The moderator spectrum a time-of-flight bank still carries, or none.

    A white beam delivers a different number of neutrons at every flight time,
    so a histogram that has **not** been divided by a vanadium measurement
    carries the source's own output as a smooth envelope over its Bragg peaks.
    GSAS measures that envelope, fits it with one of five functions and writes
    the choice into an instrument-parameter file's ``ITYP`` record with the
    coefficients in ``ICOFF``; this container is that record.

    **Whether a file carries one is a fact about the file, not an assumption**,
    and real TOF ``.iparm`` files disagree: ISIS GEM writes ``ITYP 0`` on all
    six banks and no ``ICOFF`` at all, while the LANSCE files in the legacy
    layout (:mod:`rietx.io.legacy`) write ``ITYP 1`` with a full ``ICOFF``
    block beside it.  The default
    here is :attr:`itype` 0 — no spectrum, no coefficients, the identity — so a
    bank constructed by hand, and every reduction that already normalised
    (GEM, NOMAD, POWGEN), carries the identity.

    Fixed by default, for :func:`_as_parameter`'s reason one class up: these
    are a *calibration*, refined by GSAS against a vanadium run, and freeing
    them against an unknown structure re-opens a flat direction — a smooth
    envelope in λ and an isotropic displacement parameter are degenerate, which
    is the whole reason the correction has to be right rather than merely
    flexible.  Freeing them anyway is legitimate on a standard, and is how the
    transcription gets checked.

    The functions and their millisecond argument are tabulated in
    :mod:`rietx.model.tof_spectrum`; nothing in this build evaluates them.
    Larson & Von Dreele (2004), *GSAS — General Structure Analysis System*,
    LAUR 86-748, GSAS Technical Manual p. 127-129.
    """

    #: Which of the manual's functions, 0 for none.  Validated against
    #: :data:`rietx.model.tof_spectrum.SPECTRUM_TYPES`, so an ``ITYP`` the
    #: manual does not define is refused **by number** at construction rather
    #: than read as 0 — "a function this build cannot evaluate" and "no
    #: spectrum at all" differ by two orders of magnitude across a bank.
    itype: int = 0
    #: P₁…P_N in the file's order, exactly as many as the type uses (11 for
    #: types 1-2, 12 for types 3-5, none for type 0).  A count that disagrees
    #: with the type is refused, not padded.
    coefficients: list[Parameter] = Field(default_factory=list)
    #: µs.  The flight-time window the spectrum was fitted over, from the
    #: ``ITYP`` record's second and third fields — which are in **milli**
    #: seconds in the file (manual p. 223) and are converted on the way in.
    #: Metadata: nothing clips to it, because a fit window is the caller's
    #: choice and a spectrum evaluated a little outside its fitted range is an
    #: extrapolation the Rwp will report.  Carried so a caller can ask.
    tof_min_us: float | None = None
    tof_max_us: float | None = None

    @model_validator(mode="after")
    def _type_and_count_agree(self) -> "IncidentSpectrum":
        # imported here rather than at module scope: ``model.tof_spectrum``
        # imports ``crystallography.neutron``, and the schemas are what the
        # model layer imports, not the other way round.
        from ..model.tof_spectrum import (
            SPECTRUM_TYPES,
            _coefficient_count,
            _type_zero_message,
        )

        want = _coefficient_count(self.itype)
        if want == 0 and self.coefficients:
            raise ValueError(_type_zero_message(len(self.coefficients)))
        if len(self.coefficients) != want:
            raise ValueError(
                f"IncidentSpectrum: ITYP {self.itype} "
                f"({SPECTRUM_TYPES[self.itype]}) uses {want} coefficients "
                f"and {len(self.coefficients)} were given. GSAS writes ICOFF as "
                f"three records of four numbers whatever the type, so a file "
                f"using fewer writes zeros into the rest; a list of the wrong "
                f"length is refused rather than padded, because which end the "
                f"missing ones belong to is not stated anywhere.")
        lo, hi = self.tof_min_us, self.tof_max_us
        if lo is not None and hi is not None and not lo < hi:
            raise ValueError(
                f"IncidentSpectrum: the fitted window is "
                f"({lo}, {hi}) µs, which is not increasing")
        for name in ("tof_min_us", "tof_max_us"):
            v = getattr(self, name)
            if v is not None and v <= 0.0:
                raise ValueError(f"{name} is a flight time in microseconds and "
                                 f"must be positive, got {v}")
        return self


class TOFSource(_InheritsDeclaredDefaults):
    """Neutron **time-of-flight** bank: a white beam, a fixed detector angle.

    A third arm of the :class:`Instrument` source union, and a separate class
    for the reason :class:`NeutronSource` is one — almost nothing it would
    share is meaningful here.  What differs from both constant-wavelength arms:

    * **There is no wavelength.**  The bank sees the whole moderator spectrum
      and separates reflections by arrival time, so ``λ`` is a property of the
      *channel*, not of the source.  Every reflection's position comes from its
      d-spacing through the bank's calibration instead:

          TOF = DIFC·d + DIFA·d² + TZERO + DIFB/d

      (Larson & Von Dreele, 2004, LAUR 86-748, GSAS Technical Manual p. 141,
      which gives the first three terms and spells the third ``ZERO``; the
      fourth is the ``difB``/d term GSAS-II's published documentation gives
      beside them.)  All four are
      carried, and DIFB defaults to 0 so a project that does not use it is
      bit-identical to a three-term one — but a project that *does* set it is
      never silently truncated, which is what a three-term reader would do.
    * **The scattering angle is a constant of the bank, not a coordinate.**
      ``two_theta_bank_deg`` is a plain float and deliberately not a
      :class:`Parameter`: it is the detector's placement, it is already folded
      into the refined DIFC, and freeing both would be a flat direction.
    * **The Lorentz factor is d⁴·sin θ**, not 1/(sin²θ·cos θ) (manual p. 140),
      and the absorption varies *within* one histogram because λ does.

    **This build reads such a bank and refines none.**  The readers
    (:mod:`rietx.io.instrument_tof`, :mod:`rietx.io.legacy`) return one
    ``Instrument`` per bank carrying this source, and
    :class:`rietx.params.vector.ParameterTable` lists its calibration and
    profile rows; no time-of-flight forward model exists here yet, so
    :meth:`rietx.Refinement.fit` and every other entry that would compute a
    pattern refuse a ``neutron_tof`` source by name
    (:func:`rietx.schemas.pattern.require_two_theta`).  Widening them is
    tracked on yue-here/rietx issue #193.
    """

    kind: Literal["neutron_tof"] = "neutron_tof"

    #: µs/Å.  The linear term, and the one every instrument has.  **Fixed by
    #: default**: it is a calibration refined against a standard (the manual,
    #: p. 141-142: *"Precise values for constants DIFC, DIFA and ZERO must be
    #: obtained by fitting to a powder diffraction pattern of a standard
    #: material"*), and freeing it beside a free cell is the TOF spelling of
    #: the λ-vs-cell degeneracy :class:`EmissionLine` describes.
    difc: Parameter
    #: µs/Å².  The quadratic term, usually small and often negative.  Zero is
    #: a legitimate value and the common one on a well-behaved bank.
    difa: Parameter = Field(default_factory=lambda: Parameter(value=0.0, unit="us/A^2"))
    #: µs.  The constant offset.  **Three spellings, one quantity**: the GSAS
    #: manual writes ``ZERO``, GSAS-II writes ``Zero``, Mantid writes
    #: ``TZERO``.  The field is Mantid's, because it is the only one of the
    #: three that cannot be confused with :attr:`Instrument.zero_shift` (a 2θ
    #: offset in degrees, a different quantity in a different unit); the
    #: readers map all three.
    tzero: Parameter = Field(default_factory=lambda: Parameter(value=0.0, unit="us"))
    #: µs·Å.  GSAS-II's fourth term, ``DIFB/d``.  Neither the GSAS manual nor
    #: Mantid's documented relation carries it, and it is 0 in most projects —
    #: it is here because a reader built to the three-term relation would drop
    #: a non-zero one **silently**, turning a GSAS-II project into a pattern
    #: whose peaks are in the wrong place with nothing said.
    difb: Parameter = Field(default_factory=lambda: Parameter(value=0.0, unit="us*A"))

    #: Degrees.  The bank's fixed scattering angle — a float, not a
    #: :class:`Parameter`: see the class docstring.
    two_theta_bank_deg: float
    #: m.  Primary flight path (moderator to sample).  Metadata: DIFC is the
    #: refined authority on the geometry, and these two are what the file said.
    l1_m: float | None = None
    #: m.  Secondary flight path (sample to detector centre).
    l2_m: float | None = None

    #: The GSAS type-3 coefficients (:class:`ProfileTOF`).  Always present, all
    #: zero by default — a bank whose profile was never calibrated is a real
    #: thing, and an empty container says that more plainly than ``None``.
    profile_tof: ProfileTOF = Field(default_factory=ProfileTOF)

    #: The moderator spectrum this bank's data still carries
    #: (:class:`IncidentSpectrum`).  Always present, ``ITYP 0`` by default —
    #: i.e. **no** spectrum, which is what a reduction that already divided by
    #: a vanadium measurement leaves behind and what ISIS GEM, SNS NOMAD and
    #: POWGEN all write.  Present rather than ``None`` for ``profile_tof``'s
    #: reason: "this file says there is none" is an answer, and it is the one
    #: an ``ITYP 0`` record actually gives.
    incident_spectrum: IncidentSpectrum = Field(default_factory=IncidentSpectrum)

    #: A white beam is a *continuum*, not a line list.  Read by
    #: ``capabilities._radiation`` so the arm does not report
    #: ``max_emission_lines = 1`` — which would be the one wrong statement a
    #: derived-predicate table could make about this source.
    continuous_spectrum: ClassVar[bool] = True

    #: No monochromator, so no λ/n order to declare: the harmonic question does
    #: not arise here rather than being answered "no".
    harmonics_supported: ClassVar[bool] = False

    @field_validator(*TOF_CONSTANTS, mode="before")
    @classmethod
    def _coerce_constants(cls, v, info):
        units = {"difc": "us/A", "difa": "us/A^2", "tzero": "us", "difb": "us*A"}
        extra = {"min": _DIFC_MIN} if info.field_name == "difc" else {}
        return _as_parameter(v, unit=units[info.field_name], **extra)

    @model_validator(mode="after")
    def _bank_is_a_real_bank(self) -> "TOFSource":
        if self.difc.value <= 0.0:
            raise ValueError(
                f"difc must be positive, got {self.difc.value}: DIFC = "
                f"(m_N/h)(L1 + L2)·2 sin(theta) is a flight path times an "
                f"angle, and d = TOF/DIFC divides by it")
        if not 0.0 < self.two_theta_bank_deg < 180.0:
            raise ValueError(
                f"two_theta_bank_deg is the detector bank's fixed scattering "
                f"angle in degrees and must lie in (0, 180); got "
                f"{self.two_theta_bank_deg}")
        for name in ("l1_m", "l2_m"):
            v = getattr(self, name)
            if v is not None and v <= 0.0:
                raise ValueError(f"{name} is a flight path in metres and must "
                                 f"be positive, got {v}")
        return self

    @property
    def polarization(self) -> Parameter:
        """K = 1, force-fixed — neutrons, exactly as :class:`NeutronSource`."""
        return Parameter(value=1.0, vary=False, min=1.0, max=1.0)

    @property
    def dispersion(self) -> None:
        """Always ``None``; the X-ray path tests this to decide f′/f″."""
        return None

    def tof_from_d(self, d):
        """Flight time in µs for a d-spacing in Å — the four-term relation.

        The one place the relation is written, so the readers, the tests and
        (later) the forward model cannot each carry their own version of it.
        Accepts a scalar or an array.

        References: Larson, A. C. & Von Dreele, R. B. (2004), *General
        Structure Analysis System (GSAS)*, Los Alamos National Laboratory
        Report LAUR 86-748, p. 141 (``DIFC``, ``DIFA`` and the constant term);
        the ``DIFB``/d term is the ``difB`` key of GSAS-II's instrument
        parameter file, Toby, B. H. & Von Dreele, R. B. (2013), J. Appl.
        Cryst. 46, 544-549, whose documentation (not the paper) states it.
        """
        import numpy as _np

        dd = _np.asarray(d, dtype=_np.float64)
        return (self.difc.value * dd + self.difa.value * dd ** 2
                + self.tzero.value + self.difb.value / dd)

    def d_from_tof(self, tof, *, tol: float = 1e-10, max_iter: int = 50):
        """d-spacing in Å for a flight time in µs — by successive substitution.

        With DIFA or DIFB non-zero the relation is a cubic in d and has no
        useful closed form, so it is inverted by fixed-point iteration,
        d ← (TOF − DIFA·d² − TZERO − DIFB/d)/DIFC from d₀ = TOF/DIFC.  Converged to ``tol`` in Å rather than to a fixed
        iteration count, and it **raises** rather than returning the last
        iterate if it has not: a silently unconverged d is a peak in the wrong
        place.  On real calibrations (a small DIFA against a DIFC of
        thousands) the iteration contracts by |2·DIFA·d/DIFC| ≪ 1 a step and
        converges in a handful of iterations.

        The relation inverted is the one of :meth:`tof_from_d` (Larson & Von
        Dreele, 2004, LAUR 86-748, p. 141; ``DIFB`` term: Toby & Von Dreele,
        2013, J. Appl. Cryst. 46, 544-549, via GSAS-II's documentation).
        """
        import numpy as _np

        t = _np.asarray(tof, dtype=_np.float64)
        d = (t - self.tzero.value) / self.difc.value
        if self.difa.value == 0.0 and self.difb.value == 0.0:
            return d
        for _ in range(max_iter):
            nxt = (t - self.difa.value * d ** 2 - self.tzero.value
                   - self.difb.value / d) / self.difc.value
            if _np.all(_np.abs(nxt - d) < tol):
                return nxt
            d = nxt
        raise ValueError(
            f"d_from_tof did not converge in {max_iter} iterations for "
            f"difc={self.difc.value}, difa={self.difa.value}, "
            f"tzero={self.tzero.value}, difb={self.difb.value}: the four-term "
            f"relation is not invertible over this range, which usually means "
            f"a sign or a unit is wrong in the calibration rather than that "
            f"the solver needs more iterations")


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


class Source(_InheritsDeclaredDefaults):
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
    #: What stands between the tube and the detector as far as Kβ goes (WP-1445).
    #: ``None`` is **undeclared**, never "no filter": most files say nothing, and
    #: the contamination screen runs unchanged on it.  ``"monochromator"`` makes
    #: the screen skip both searches.  ``"filter"`` and ``"mirror"`` are
    #: recorded and change nothing: a filtered or mirrored beam still shows an
    #: injected leak down to 2 % of Kα, and there is no measured ceiling to
    #: narrow to.  See ``background.diagnostics.ghost_searches``.
    kbeta: Literal["filter", "monochromator", "mirror"] | None = None
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


class RoughnessSuortti(_InheritsDeclaredDefaults):
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
    region rather than at its floor of 0, and the ``ROUGHNESS_UNCONSTRAINED``
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
        default_factory=lambda: Parameter(value=0.0, min=0.0, max=5.0)
    )


class RoughnessPitschke(_InheritsDeclaredDefaults):
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
        default_factory=lambda: Parameter(value=0.0, min=0.0, max=4.0)
    )
    tau: Parameter = Field(
        default_factory=lambda: Parameter(value=0.05, min=0.0, max=0.3)
    )


SurfaceRoughness = RoughnessSuortti | RoughnessPitschke

#: The fraction of a capillary bore or a flat slab occupied by solid, read only
#: to estimate µR or µt from the composition: 0.3-0.6 is typical for a tapped
#: powder and 0.64 is random close packing of spheres.  An assumption about the
#: caller's specimen; GSAS-II's absorption calculator starts at 0.50.
PACKING_FRACTION = 0.6


class Geometry(_InheritsDeclaredDefaults):
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
    #: How far the specimen sits off the goniometer axis (mm).
    #:
    #: **No position correction carries a default bound; the axial ratios and
    #: the transparency keep their floor of 0.**  WP-2002's B9 ruling
    #: (2026-10-19) removed chosen limits on quantities that stay physical.
    #: The FCJ quadrature is defined for any S/L, H/L ≥ 0 (``fcj._xi_max``
    #: clips at |tan 2θ|; ``fcj.fcj_live`` reads a negative ratio as the
    #: aberration off), and a transparency is 1/(2µR) ≥ 0.  The displacement,
    #: the two capillary offsets and ``Instrument.zero_shift`` lost their
    #: ±1 mm and ±0.5° on 2026-10-20.  The fit reports the degeneracy with or
    #: without them: on 11-BM NAC over 2-24° 2θ with zero and both offsets
    #: free, bounded, the cell lands 1097 ppm from its reference with an esd
    #: of 2610 ppm; unbounded, the offsets slide to +4.86 and +2.12 mm and
    #: the cell to 5111 ppm with an esd of 2544 ppm, and both fits carry the
    #: same two ``FLAT_DIRECTION`` findings naming the cell and an offset
    #: (``tests/test_capillary_displacement.py``).  The bound acted as a
    #: prior that the mount is aligned, true on 11-BM and so nearer the
    #: reference there, without narrowing the esd.  A prior about the mount
    #: is the caller's: the bounds had one family behind them and a named
    #: dissenter (a recessed holder), and neither GSAS-II nor FullProf sets
    #: one.  A caller who knows the mount states a bound; ``BOUND_HIT``
    #: reports one that carries load.
    sample_displacement: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, unit="mm")
    )
    sample_transparency: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, min=0.0)
    )
    #: capillary displacement along the incident beam (mm, positive
    #: downstream) — the sin 2θ half of eq (4).  ``debye_scherrer`` only.
    capillary_offset_along_beam: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, unit="mm")
    )
    #: capillary displacement perpendicular to the beam in the diffraction
    #: plane (mm, positive toward increasing 2θ) — the cos 2θ half of eq (4).
    capillary_offset_across_beam: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, unit="mm")
    )
    axial_sl: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, min=0.0)
    )
    axial_hl: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, min=0.0)
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
    packing_fraction: float = Field(default=PACKING_FRACTION, gt=0.0, le=1.0)

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


class ProfileTCHZ(_InheritsDeclaredDefaults):
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

    **The widths have a floor, and U, V and Y have none of their own.**  What
    must stay non-negative is a width: Γ_G² above and Γ_L, each with every
    phase's own terms added.  A coefficient can be negative while both
    widths stay positive.  So U and V are bounded at −180² deg² and Y at
    −180°, the ceilings' mirror images, which no width reaches (the
    maintainer's ruling of 2026-10-23, WP-2002).  GSAS-II and FullProf bound
    none of the five.  The default LM driver holds Γ_G² ≥ ε and Γ_L ≥ 0 at
    every reflection inside the step
    (:func:`~rietx.optimize.least_squares.gaussian_width_inequalities`,
    :func:`~rietx.optimize.least_squares.lorentzian_width_inequalities`).
    ``solver="trf"`` holds no inequality, and ``RESOLUTION_NOT_POSITIVE``
    reports an instrument width that goes negative in the fitted range.
    Two floors stay.  W's is the Γ_G² clamp (below).  X's is 0: at θ → 0
    the tanθ term vanishes, so the instrument's Γ_L is X itself there.
    Every preset builds this one box (:data:`TCHZ_BOUNDS`), and an explicit
    ``Parameter(value, min, max)`` carries the caller's own.  The chosen
    floors went on 2026-10-23: U ≥ −0.05 and V ≥ −0.5 on the X-ray presets,
    U ≥ −0.5 and V ≥ −4 on the neutron one, Y ≥ 0 on both.  A solution
    read from another program can still sit under a floor: one with W < 0
    starts from W's floor rather than from its value.

    **The ceiling is the width of the 2θ axis** (:data:`TCHZ_CEILING_DEG`),
    which no peak can reach.  The chosen ceilings (1 for U, W, X and Y, 0.5
    for V) went on 2026-10-21 (WP-2002, the fifth round's Q5): X ≤ 1° capped
    the Lorentzian size near 8 nm at Cu Kα, and none of GSAS-II, FullProf,
    TOPAS, RIETAN-FP, MAUD or EasyDiffraction bounds these coefficients by
    default (BGMN has none to bound).  A finite ceiling stays because
    ``solver="trf"`` scales each step by the distance to a finite bound and
    by 1 for an infinite one, so an infinite ceiling changes TRF's path where
    no width comes near it.  Without one, TRF stopped the CPD brucite
    Stephens fit at Rwp 0.17891 with one S_HKL esd collapsing to 66 (t = −203).
    With these ceilings it stops at 0.17878 with the pre-removal t values, as
    it did with every ceiling at 10 or at 1000 (the sixth round's Q7).  LM,
    the default driver, gives the same answer either way.  The floors at
    −180² and −180 are finite for the same reason.

    **W's floor is the Γ_G² clamp, not zero** (WP-1938 D7).
    :func:`~rietx.model.profiles.caglioti.gaussian_fwhm` takes
    Γ_G = √max(Γ_G², ε) with ε = ``_MIN_GAMMA_G2`` = 1e-8 deg², and under the
    clamp every Gaussian width column is exactly zero.  The LM driver puts a
    parameter exactly on its bound, so with W bounded at 0 a stage freeing W
    while U and V sat near 0 put Γ_G² under the clamp at every point and
    stopped there: on the manual's minimal NAC call, Rwp 0.18028 under LM
    against TRF's 0.13375 (macOS arm64, ``[dev]``).  A bound at ε keeps W's
    own column live on its floor.  It does not hold the sum, which a negative
    U or V can still take under the clamp; ``RESOLUTION_NOT_POSITIVE`` stays
    the check for that.  A stored or passed ``min`` under ε is raised to it
    (:meth:`_w_floor_is_reachable`).
    """

    shape: Literal["tchz_pv", "voigt"] = "tchz_pv"
    u: Parameter = Field(default_factory=lambda: _tchz_width("u"))
    v: Parameter = Field(default_factory=lambda: _tchz_width("v"))
    w: Parameter = Field(default_factory=lambda: _tchz_width("w"))
    x: Parameter = Field(default_factory=lambda: _tchz_width("x"))
    y: Parameter = Field(default_factory=lambda: _tchz_width("y"))

    @model_validator(mode="before")
    @classmethod
    def _refuse_bare_widths(cls, data):
        """A bare number is refused by name.

        A width is a :class:`Parameter` carrying its own box; a bare number
        never was one, and pydantic's type error said so without saying what
        to do (WP-1312's 2026-09-11 ruling: the constructor refuses by name).
        So a bare width, such as a neutron instrument's Caglioti ``U = 1.576``
        (issue #276), is refused naming the width, the value, the box and the
        two ways to build it: :meth:`ProfileTCHZ.coarse`, which builds all
        five widths from bare values, or an explicit
        ``Parameter(value, min, max)``.  A :class:`Parameter` or a dict passes
        through untouched *here*; one leaving its bounds unset inherits
        :data:`TCHZ_BOUNDS` from
        :class:`~rietx.schemas.common._InheritsDeclaredDefaults` (WP-1321), and
        a value outside it is refused there.
        """
        if not isinstance(data, dict):
            return data
        bare = {name: v for name, v in data.items()
                if name in TCHZ_DEFAULTS and isinstance(v, (int, float))
                and not isinstance(v, bool)}
        if bare:
            said = ", ".join(f"{n}={float(v)!r} (box [{TCHZ_BOUNDS[n][0]}, "
                             f"{TCHZ_BOUNDS[n][1]}])"
                             for n, v in bare.items())
            raise ValueError(
                f"ProfileTCHZ: {said} is a bare number, and a width is a "
                f"Parameter carrying its box. Build all five widths from values "
                f"with ProfileTCHZ.coarse(...), or state the width as an "
                f"explicit Parameter(value, min, max) with its own bounds")
        return data

    @model_validator(mode="after")
    def _w_floor_is_reachable(self) -> "ProfileTCHZ":
        """Raise a W bound under the Γ_G² clamp to the clamp, and the value with it.

        The ``PreferredOrientation._r_bound_is_reachable`` pattern, and for its
        reason: the broken bound **outlives the default**.  A project or a
        history node written before the floor carries ``min: 0.0`` and
        deserializes straight back into the trap, and no ``default_factory``
        runs on that path.  So does a caller's own ``Parameter`` stating
        ``min=0.0``, or a negative one.  A value under the floor is raised with
        it.  Silent, like the precedent: a schema has no diagnostics channel.
        Lifting a stored W of 0 widens a line by at most √ε = 1e-4° of FWHM.
        """
        w = self.w
        if w.min < _MIN_GAMMA_G2:
            # max, then value, then min: ``Base`` validates on assignment, so
            # each write must leave a legal Parameter behind it
            w.max = max(w.max, _MIN_GAMMA_G2)
            w.value = max(w.value, _MIN_GAMMA_G2)
            w.min = _MIN_GAMMA_G2
        return self

    @classmethod
    def coarse(cls, *, shape: Literal["tchz_pv", "voigt"] = "tchz_pv",
               **widths: float) -> "ProfileTCHZ":
        """The five widths built from bare values, in :data:`TCHZ_BOUNDS`.

        What :meth:`Instrument.constant_wavelength_neutron` builds.  The name
        survives from WP-1312, when a CW neutron line needed a wider box than
        the X-ray presets; since 2026-10-23 every preset builds the same box.
        ``widths`` are values (``u=1.576``), each kept in that box.
        """
        unknown = set(widths) - set(TCHZ_DEFAULTS)
        if unknown:
            raise TypeError(f"ProfileTCHZ.coarse: no width named "
                            f"{sorted(unknown)}; the widths are "
                            f"{sorted(TCHZ_DEFAULTS)}")
        return cls(shape=shape, **{
            name: _tchz_width(name, widths.get(name))
            for name in TCHZ_DEFAULTS})


#: The default :class:`ProfileTCHZ` seed per width coefficient.
TCHZ_DEFAULTS: dict[str, float] = {"u": 0.0, "v": 0.0, "w": 1e-3, "x": 1e-3,
                                   "y": 0.0}

#: The ceiling on every TCHZ width: the whole 2θ axis, 180° for X and Y and
#: 180² deg² for U, V and W.  It bounds nothing a peak can reach and gives
#: ``solver="trf"`` a finite bound to scale its steps by (:class:`ProfileTCHZ`
#: says why; WP-2002, the sixth round's Q7).
TCHZ_CEILING_DEG = 180.0
_TCHZ_CEILING = {"u": TCHZ_CEILING_DEG ** 2, "v": TCHZ_CEILING_DEG ** 2,
                 "w": TCHZ_CEILING_DEG ** 2, "x": TCHZ_CEILING_DEG,
                 "y": TCHZ_CEILING_DEG}

#: The refinement box per width coefficient, which every preset builds.  U, V
#: and Y have no floor of their own: each stops at the ceiling's mirror image,
#: which no width reaches and which stays finite for ``solver="trf"``'s step
#: scaling (:class:`ProfileTCHZ`; the maintainer's ruling of 2026-10-23,
#: WP-2002).  W's floor is the Γ_G² clamp since WP-1938, and X's is 0.  The
#: chosen ceilings (1 for U, W, X and Y, 0.5 for V) were removed on 2026-10-21
#: (the fifth round's Q5).  The chosen floors went on 2026-10-23, and with them
#: the neutron preset's own box, ``TCHZ_BOUNDS_COARSE`` (U ≥ −0.5, V ≥ −4).
#: That box was measured on the public APDW Co3O4 set (ILL D1B, λ = 2.52 Å;
#: issue #276), whose FullProf model has V = −0.501, under the X-ray floor.
TCHZ_BOUNDS: dict[str, tuple[float, float]] = {
    "u": (-_TCHZ_CEILING["u"], _TCHZ_CEILING["u"]),
    "v": (-_TCHZ_CEILING["v"], _TCHZ_CEILING["v"]),
    "w": (_MIN_GAMMA_G2, _TCHZ_CEILING["w"]), "x": (0.0, _TCHZ_CEILING["x"]),
    "y": (-_TCHZ_CEILING["y"], _TCHZ_CEILING["y"])}

_TCHZ_UNITS = {"u": "deg^2", "v": "deg^2", "w": "deg^2", "x": "deg", "y": "deg"}


def _tchz_width(name: str, value: float | None = None) -> Parameter:
    lo, hi = TCHZ_BOUNDS[name]
    return Parameter(value=TCHZ_DEFAULTS[name] if value is None else value,
                     min=lo, max=hi, unit=_TCHZ_UNITS[name])


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


#: The P-spline's default stiffness, in :attr:`BackgroundPSpline.lambda_units`'
#: dimensionless units: λ = 1 suppresses features narrower than a knot spacing,
#: and Rwp and Biso stay flat from 0.1 to 100 on IUCr CPD sample 2 and 11-BM
#: NAC (WP-1454).  ``auto_background`` builds every P-spline at it.
PSPLINE_LAMBDA_SMOOTH = 1.0


class BackgroundPSpline(Base):
    """Penalised cubic P-spline background, co-refined with the structure.

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
    air-scatter rise.  It is **absent** (``None``) unless something declares
    it, and :func:`rietx.background.auto_background` declares it only when
    the pattern diagnostics flag the rise (``rietx.background.diagnose``).
    Absent means no design row and no parameter path, which is what keeps it
    off: every preset frees ``instrument.background.*`` and a plan replaces
    the vary flags (WP-1208), so a term held at 0 with ``vary=False`` was
    freed on every fit anyway.  Inside the span of a fine spline its column
    was a flat direction, reported once per pair of background columns
    (WP-1454).  Declare one with ``Parameter(value=1e-3, min=0.0)``.
    """

    kind: Literal["pspline"] = "pspline"
    breakpoints: list[float]
    coefficients: list[Parameter]
    lambda_smooth: float = Field(default=PSPLINE_LAMBDA_SMOOTH, ge=0.0)
    #: What ``lambda_smooth`` is measured against.  ``"dimensionless"``: the
    #: rows are √(λ·m)·D₂c/σ̄, with σ̄ the median σ over the fitted channels
    #: and m the fitted channels per coefficient, both frozen at compile
    #: (:func:`rietx.background.models.pspline_penalty_scale`).  One λ then
    #: means the same stiffness in any intensity unit, at any count level and
    #: any step size.  ``"intensity"``: the pre-WP-1454 rows √λ·D₂c, whose λ
    #: carries inverse intensity squared, so a unit change alone took one
    #: background from unpenalised to a straight line.  Kept as the
    #: bit-identical way back, which is what a golden declares.
    lambda_units: Literal["dimensionless", "intensity"] = "dimensionless"
    air_scatter: Parameter | None = None

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
                  lambda_smooth: float = PSPLINE_LAMBDA_SMOOTH,
                  vary: bool = True) -> "BackgroundPSpline":
        """Uniform knots covering [lo, hi] at ~``knot_step_deg`` spacing."""
        n = max(int(round((hi - lo) / knot_step_deg)) + 1, 2)
        breaks = [lo + (hi - lo) * i / (n - 1) for i in range(n)]
        return cls(
            breakpoints=breaks,
            coefficients=[Parameter(value=0.0, vary=vary) for _ in range(n + 2)],
            lambda_smooth=lambda_smooth,
        )


class BackgroundFixedPlusChebyshev(_InheritsDeclaredDefaults):
    """A fixed curve held in the model, a small refinable Chebyshev correction
    on top, and a scale on the curve itself.

    The curve is either an estimate — :func:`rietx.background.estimate`, arPLS
    or SNIP — or a **measurement**: an empty vanadium can, a blank capillary, a
    matrix-only scan, an empty furnace.  Holding it inside the model keeps the
    Poisson weights correct where subtracting it would not.

    ``scale`` is the multiplier the measured case needs, and it is TOPAS's
    ``bkg_file("f.xy", @, s)`` against its ``bkg_file("f.xy")`` (Coelho,
    *TOPAS-Academic Technical Reference*, v8).  The default is 1.0 held, which
    is the second form, and it is what every project did before WP-1309.  A
    blank is never on the specimen's scale: the two scans differ in monitor
    normalisation and counting time, and the specimen attenuates the
    container's own scattering.  The Chebyshev riding on top cannot absorb
    that, because it is **additive** and the error is multiplicative — it can
    move the level and never rescale the shape.  Quantitative phase analysis is
    the workflow least tolerant of the difference, since what a wrong
    background level biases is the phase scales and hence the weight fractions,
    while Rwp improves.

    The scale multiplies the curve **as stored**, so it reads as a physical
    multiplier of :attr:`fixed_intensity` and is comparable to a TOPAS
    ``bkg_file`` scale digit for digit.

    ``fixed_sigma`` is the curve's own counting statistics, and what it buys is
    that a short blank scan is honestly worse than a long one: the channel
    weight becomes σ² + s²·σ_f² rather than σ² alone
    (:func:`rietx.model.forward.compile_model`).  Two caveats, neither of them
    solved by the field.  Interpolating a noisy curve onto the pattern grid
    correlates neighbouring channels' errors, so the propagated σ is a lower
    bound unless the curve is smoothed first, and smoothing is a modelling
    choice that belongs in the record rather than in a sampler.  And one blank
    reused across a series has fully correlated error rather than error that
    averages down, so a refined scale that *trends* along a ramp is partly an
    artefact of the single measurement.

    **The physics a scalar cannot carry.**  The container's scattering reaches
    the detector *through* the specimen in the sample run and through nothing
    in the blank run, so the exact multiplier is angle-dependent — of the order
    of the specimen transmission :mod:`rietx.model.absorption` already computes
    for cylinders.  A constant scale is the leading-order correction, and it is
    correct per pattern rather than as one constant across a temperature or
    atmosphere series.

    ``fixed_source`` names where the curve came from, and is what separates a
    measurement from an estimate for anything reading the model back: the CIF
    export says "measured" only when it is set.
    """

    kind: Literal["fixed_plus_chebyshev"] = "fixed_plus_chebyshev"
    fixed_two_theta: list[float]
    fixed_intensity: list[float]
    #: The curve's own esds, channel for channel, or ``None`` for a curve with
    #: no statistics to propagate (every estimator's output, and a blank whose
    #: file carried no esd column).  ``None`` is no claim made rather than a
    #: claim of no error, which is why it is not a list of zeros.
    fixed_sigma: list[float] | None = None
    #: Where the curve came from, free text — a file name, a run number, an
    #: estimator and its λ.  Provenance is a claim, and a background asserting
    #: it is a measurement without naming the measurement is worse than a
    #: polynomial, which at least does not pretend to be evidence.
    fixed_source: str | None = None
    #: The multiplier on the stored curve.  Fixed at 1.0 by default, so a model
    #: that declares nothing behaves exactly as it did before this field
    #: existed.  ``min=0.0`` is safe here because zero **is** the off state —
    #: the model is linear in this parameter and divides by nothing (root
    #: CLAUDE.md § Invariants, the ``MARCH_R_MIN`` rule read the other way).
    #: It keeps the curve from being subtracted by a solver that found a
    #: negative multiplier cheaper than the physics.  Since WP-1938 it is an
    #: ordinary bound, so a scale driven to zero can come back as a
    #: ``FLOOR_HIT`` (WP-1929).  What makes a double-counted curve visible is the refined
    #: scale itself, which lands a whole unit from where the caller declared
    #: it.
    scale: Parameter = Field(
        default_factory=lambda: Parameter(value=1.0, min=0.0)
    )
    chebyshev: BackgroundChebyshev = Field(default_factory=lambda: BackgroundChebyshev())

    @model_validator(mode="after")
    def _lengths(self) -> "BackgroundFixedPlusChebyshev":
        if len(self.fixed_two_theta) != len(self.fixed_intensity):
            raise ValueError("fixed background arrays differ in length")
        if self.fixed_sigma is not None:
            if len(self.fixed_sigma) != len(self.fixed_intensity):
                raise ValueError(
                    f"fixed_sigma has {len(self.fixed_sigma)} points and the "
                    f"curve has {len(self.fixed_intensity)}")
            if any(s < 0.0 for s in self.fixed_sigma):
                raise ValueError("fixed_sigma must be non-negative")
        return self

    @classmethod
    def from_pattern(cls, blank: "PatternData", *, n_terms: int = 4,
                     vary_scale: bool = False, scale: float = 1.0,
                     source: str | None = None
                     ) -> "BackgroundFixedPlusChebyshev":
        """Build the model from a measured blank, esds and all.

        ``read_pattern`` is therefore the route in, and every format it opens
        is a background format for free.  The blank's own esds are carried when
        it has them — ``PatternData.sig()`` is not used, because its Poisson
        fallback would invent statistics for a curve that has none, and that is
        the difference this field exists to record.

        ``vary_scale`` is the caller's declared act.  It is ``False`` by
        default for the reason the field is: a declared measured background
        starts where the code stood before it could refine one.

        The blank's own ``excluded_regions`` are honoured, so a channel
        somebody marked bad in the blank does not become background: the curve
        skips it and the interpolation bridges the gap.  A region at either end
        shortens the curve, which is then a fit range it no longer covers and a
        refusal rather than a flat extrapolation.
        """
        keep = blank.in_range_mask()
        return cls(
            fixed_two_theta=[float(v) for v in blank.tt()[keep]],
            fixed_intensity=[float(v) for v in blank.y()[keep]],
            fixed_sigma=(None if blank.sigma is None else
                         [float(v) for v, k in zip(blank.sigma, keep, strict=True)
                          if k]),
            fixed_source=source,
            scale=Parameter(value=scale, vary=vary_scale, min=0.0),
            chebyshev=BackgroundChebyshev.with_terms(n_terms, vary=True),
        )


Background = BackgroundChebyshev | BackgroundFixedPlusChebyshev | BackgroundPSpline


#: :class:`HumpComponent`'s refinable fields, in path order.  One authority for
#: the three names: ``params.vector.extra_component_parameters`` registers them,
#: ``ParameterTable.apply_to_models`` writes them back, ``compile_model`` freezes
#: the paths and ``strategy.staged`` reads them — so adding a fourth (an η, say)
#: is one edit rather than five that can drift.  The sub-path *is* the field
#: name, which is what makes ``instrument.extra_components.0.fwhm`` legible.
HUMP_FIELDS: tuple[str, ...] = ("position", "height", "fwhm")

#: Lower bound on :attr:`HumpComponent.fwhm`, in °2θ.  The Gaussian divides by
#: Γ, so this is the :data:`~rietx.schemas.structure.MARCH_R_MIN` situation and
#: not a `min=0.0` one: a zero width is a pole (root CLAUDE.md § Invariants).
#:
#: The number comes from the sampling rule the rest of the package already
#: quotes: :data:`rietx.background.diagnostics.STEPS_PER_FWHM_MIN` = 5 steps
#: across a feature is the minimum at which anything can be refined from it, and
#: 0.02 °2θ is the finest step a routine powder scan uses — 5 × 0.02 = 0.1.
#: Below that a "background feature" is narrower than a handful of channels,
#: which is a Bragg peak or a spike, not diffuse scattering.  It is a floor on
#: the *parameterisation*, deliberately far below any real hump (whole degrees):
#: it exists to make the pole unreachable, not to encode a physical width.
HUMP_FWHM_MIN = 0.1

#: :class:`PeakComponent`'s refinable fields, in path order — the
#: :data:`HUMP_FIELDS` role for the second member.  ``center`` and not
#: ``position`` because it is the *apparent* centre of a peak this package does
#: not place from a cell, and ``area`` and not ``scale`` because
#: :func:`rietx.refine.mode_fixed_path` force-fixes every ``*.scale`` path under
#: Le Bail and Pawley, where a declared sharp peak must stay refinable.
PEAK_FIELDS: tuple[str, ...] = ("center", "area", "fwhm", "eta")

#: Which fields each :data:`ExtraComponent` member refines, keyed by its
#: ``kind`` discriminator.  One authority, so
#: :func:`rietx.params.vector.extra_component_parameters` stays member-agnostic
#: instead of growing an ``isinstance`` ladder that ``apply_to_models`` would
#: have to grow in step — exactly the drift clause 4 of the member contract
#: exists to prevent.  A new member adds its row here, and
#: ``tests/test_extra_components.py`` fails on a member whose row is missing.
COMPONENT_FIELDS: dict[str, tuple[str, ...]] = {
    "hump": HUMP_FIELDS,
    "peak": PEAK_FIELDS,
}

#: Lower bound on :attr:`PeakComponent.fwhm`, in °2θ.  The same pole the
#: :data:`HUMP_FWHM_MIN` comment describes, since the pseudo-Voigt divides by
#: Γ, derived by the same rule at the other end of the instrument range.
#:
#: :data:`rietx.background.diagnostics.STEPS_PER_FWHM_MIN` = 5 channels across a
#: feature is the minimum anything can be refined from; 0.001 °2θ is the step of
#: the finest scan this package is tested against (APS 11-BM,
#: ``tests/data/11BM_Si640c.xy``, stated in that file's own header), so
#: 5 × 0.001 = 0.005.  :data:`HUMP_FWHM_MIN` takes 0.02° — the finest step a
#: *routine* powder scan uses — and is 20× larger for that reason alone.
#:
#: It is a floor on the *parameterisation*, not a claim about how sharp a real
#: peak is.  Unlike the hump's floor, which sits whole degrees below any real
#: hump, this one has no comfortable margin beneath a legitimate width: sharp is
#: the point of this member.  It exists to make the pole unreachable, and a
#: caller whose peak is genuinely narrower than five channels has a spike, not a
#: peak this profile describes.
EXTRA_PEAK_FWHM_MIN = 0.005

#: Default upper bound on :attr:`PeakComponent.fwhm`, in °2θ — a *default*, not
#: a limit, and a caller who needs a broader peak simply says so.
#:
#: It is a default at all because this bound is not only a claim about the peak,
#: it is the **window's size**: the frozen half-width is
#: ``window_fwhm_mult(eta.max)·fwhm.max + WINDOW_MIN_DEG``, and ``k(η)`` reaches
#: about 16 at η = 1.  Left at the width bound a `Parameter` would otherwise
#: carry, the window swallows the whole pattern and the member costs what it was
#: windowed to avoid.  0.5° is several times the FWHM of a laboratory
#: diffractometer at any angle, so it is generous for something described as a
#: *sharp* peak while keeping the default window near ±8°.
#:
#: The trade is the one the whole sized-from-bounds design makes, and it is
#: worth stating plainly: a bound is what makes a free centre provably stay
#: inside a frozen window, and the price of a loose bound is a wide window.
#: Tight bounds are the caller's to set and are worth setting.
EXTRA_PEAK_FWHM_MAX = 0.5

#: A lower bound at or under this is a bound at zero to the width repairs
#: below — the same 1e-12 `schemas/structure.py` uses, restated here rather
#: than imported so `schemas/instrument.py` keeps importing nothing from its
#: sibling.  It is the value under which a stored ``min`` meant no bound at
#: all before schema 0.46, so no stored document repairs differently.
_ZERO_BOUND = 1e-12

#: What :attr:`Instrument.extra_components` was called in v1.2, kept here as the
#: one spelling of the legacy name so the field migration and the path migration
#: (:mod:`rietx.schemas.migrate`) cannot drift apart.
_LEGACY_COMPONENT_FIELD = "background_peaks"


class HumpComponent(_InheritsDeclaredDefaults):
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
    background, so it lives on :attr:`Instrument.extra_components` and the
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
    Chebyshev, 3 terms                   3  0.120051  0.413(64)                    0
    that **+ one peak**              3 + 3  0.082134  0.421(10)                    0
    Chebyshev, 6 terms                   6  0.088232  0.422(25)                    0
    that **+ one peak**              6 + 3  0.076711  0.4234(64)                   0
    ==============================  ======  ========  ============  ================

    **Three parameters beat three polynomial terms.**  Rows one and two differ by
    three numbers and so do rows one and three — the peak takes Rwp down 32 %
    relative, three more Chebyshev coefficients only 27 %.  Biso(Si) barely moves
    (well inside one esd) but its **esd falls 6.4×**, and so do those of λ, the
    scale and the zero shift: an undescribed background blurs this fit rather
    than biasing it.

    **The feature is identified from outside the fit.**  The refined peak is
    5.61(22)° wide against an instrumental Gaussian FWHM of 0.00347° at that
    angle — 1 618×.  11-BM's published blank (run 4736, ``empty Kapton
    capillary``, same February 2010 beamtime), fitted independently of this
    package, puts the same feature at 4.2417(111)° with FWHM 6.153(23)°, and the
    beamline's published air-scatter scan shows no localised feature anywhere.
    The blank's envelope maximum, d = 4.74 Å (Q = 1.33 Å⁻¹), is the polyimide
    halo.  That — not the Rwp — is what makes the term quotable.

    **A peak needs a low-order background to mean anything.**  Between the
    3-term and 6-term arms the peak moves 1.08° and narrows from 5.61(22)° to
    1.92(8)° while Rwp moves by 0.005: the peak and the polynomial describe
    overlapping freedom, so the more flexible the polynomial the less the peak's
    own parameters mean.  Declare a peak *instead of* extra polynomial terms,
    never on top of them.

    **The refined centre is not the halo position.**  A symmetric Gaussian
    spanning 2-50° also absorbs the residual direct-beam rise a 3-term Chebyshev
    cannot reach, which pulls the fitted centre to 4.18(9)° below the envelope's
    4.98°; at six terms it relaxes onto the envelope at 5.245(32)°.  Quote the
    envelope for where the halo is and the fit for the model that describes it.
    ``docs/docs/concepts/parameters.md`` § Humps carries the long form and
    ``tests/data/README.md`` the provenance of every file named here.

    Fields, and the reason each bound is the bound it is:

    * ``position`` — °2θ, **unbounded by default**.  It is
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
    * ``height`` — ``min=0.0``, default 0.0.  ``min=0.0`` is safe here for
      exactly one reason: **zero is the off state.**  h = 0 makes the whole
      term identically zero and the peak contributes nothing anywhere, so the
      bound lands on the identity, not on a pole (contrast
      ``PreferredOrientation.r``, whose identity is interior at r = 1 with
      the pole *at* zero).
    * ``fwhm`` — °2θ, floored at :data:`HUMP_FWHM_MIN` with a reachability
      validator, because this one *does* divide.
    * shape — **Gaussian only, and the fence is deliberate.**  No mixing
      parameter: a broad feature is described by a few tens of channels of
      curvature sitting on a polynomial that can already absorb the difference
      between a Gaussian and a pseudo-Voigt, so η would be a third number the
      data cannot separate from the terms underneath it.  It is also what the
      practice being matched does — TOPAS's ``gauss_fwhm``.  If a mixing
      parameter is ever added, its identity is interior (η = 0 and η = 1 are
      both legitimate ends, so the ``PreferredOrientation.r`` trap does not
      apply) and it needs the box [0, 1], not a floor.

    All three default to ``vary=False``: a declared peak is inert until a stage
    frees it, and ``height = 0`` means a declared-but-never-freed peak is
    bit-identical to no peak at all.
    """

    #: apparent position of the hump in °2θ.  Required — there is no default
    #: place for a background feature, and a defaulted one would be a claim.
    position: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, unit="deg"))
    height: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, min=0.0, unit="counts"))
    fwhm: Parameter = Field(
        default_factory=lambda: Parameter(value=5.0,
                                         min=HUMP_FWHM_MIN,
                                         unit="deg"))
    #: Discriminator.  Its one legal value names this member of
    #: :data:`ExtraComponent`; the union dispatches on it, never on shape.
    kind: Literal["hump"] = "hump"
    #: free-text tag, e.g. ``"cryostat tail"``.  Not a parameter and not part of
    #: any dot-path — the paths index the list, so a relabelled peak keeps its
    #: refined values.
    label: str | None = None

    @model_validator(mode="after")
    def _fwhm_floor_is_reachable(self) -> "HumpComponent":
        """Repair a width bound at zero, where the Gaussian's pole is.

        The ``PreferredOrientation._r_bound_is_reachable`` pattern, and for the
        same reason: the broken bound **outlives the default**.  A JSON project
        or a history node written with ``min: 0.0`` deserializes straight back
        into the pole, and no default_factory ever runs on that path.  Only a
        bound at or under :data:`_ZERO_BOUND` is touched; any positive bound a
        caller chose is left alone.
        """
        if self.fwhm.min <= _ZERO_BOUND:
            # value **before** min: ``Base`` validates on assignment, so raising
            # the floor under a value that is still below it would trip
            # ``Parameter._check_bounds`` mid-repair.  Lifting the value first is
            # always legal — the old bound was ≤ 1e-12.
            self.fwhm.value = max(self.fwhm.value, HUMP_FWHM_MIN)
            self.fwhm.min = HUMP_FWHM_MIN
        return self



class PeakComponent(_InheritsDeclaredDefaults):
    """One declared sharp pseudo-Voigt peak the phases cannot account for.

    A sample holder reflecting at its own specimen distance, a mount, a window,
    an unidentified sharp impurity — something that diffracts, sits where no
    phase in the model puts a line, and **overlaps peaks that matter**.  That
    overlap is the whole reason this member exists: ``excluded_regions`` is the
    alternative, and it masks the sample peak underneath along with the
    intruder.

        y(2θ) = A · pV(2θ − 2θ_c; Γ, η)

    with pV the unit-area pseudo-Voigt already used for every Bragg reflection
    (:func:`rietx.model.profiles.pseudovoigt.pseudo_voigt`): η·L + (1−η)·G, both
    components unit-area at one FWHM Γ.  The intensity therefore enters as an
    **area**, which is what a reflection intensity is, and A is in counts·deg.

    **This is a declaration, never a detection.**  The package does not look for
    extra peaks and does not decide whether yours is real; it fits what you
    declare and reports evidence about it.  What it will not do is refuse.

    **Why it is not a phase.**  TOPAS spells the same capability as a cell-less
    "peaks phase" (``xo_Is``; Coelho, 2018, *J. Appl. Cryst.* **51**, 210).
    Here a :class:`~rietx.Phase` is crystallographic through and through — cell
    ties, Wyckoff sites, QPA weight fractions — and a cell-less one breaks every
    consumer of it.  The component seam gives the same power without the schema
    violence, which is the argument :data:`ExtraComponent` is built on.

    **What it is not corrected for, and why that is the point.**  The centre is
    the **apparent** position of the *primary* emission line: no ``zero_shift``,
    no sample-displacement or transparency shift, no FCJ asymmetry.  A holder
    sits at its own distance from the focusing circle and its aberrations are
    its own, so correcting it with the specimen's would be worse than not
    correcting it at all.  All of it is absorbed into a free centre, which is
    also why the centre carries no crystallographic meaning: see the non-goal in
    WP-1103 about reading a d-spacing off it.

    **Emission lines: all of them, by default.**  The holder diffracts the same
    source, so its Kα2 is physically there.  ``all_lines=True`` places each line
    at the Bragg image of the apparent centre and scales it by the line's weight
    **times the two lines' Lorentz-polarisation ratio** — not the bare weight,
    which is a measured bias and not a simplification: holding it biased the
    fitted Kα1 by −2e-4° and −0.26 mean σ pull on lab Cu Kα LaB6 (WP-1018, and
    :mod:`rietx.indexing.peakfit` states the same arithmetic for the same
    reason).  Set ``all_lines=False`` for something that does not diffract at
    all — a fluorescence line, a detector artefact — where a Kα2 image would be
    a claim about physics that is not happening.

    Fields, and the reason each bound is the bound it is:

    * ``center`` — °2θ, and **finite ``min``/``max`` are
      required**.  This is the one place this member disagrees with
      :class:`HumpComponent`, whose ``position`` is deliberately unbounded, and
      the difference is not taste: a hump is evaluated on the whole grid, so its
      position has no window to leave, while this peak is evaluated in a window
      frozen at stage compile.  That window is sized from ``center``'s *bounds*,
      which is what lets a free centre move during a stage without ever leaving
      it — the frozen-per-stage invariant held by construction instead of by
      plumbing ``free_paths`` into the compile.  With no bound there is no
      window to size, so the refusal is a real one and it suggests a range.
    * ``area`` — counts·deg, ``min=0.0``, default 0.0.  ``min=0.0`` is safe
      for the one reason it is ever safe: **zero is the off state.**  A = 0
      makes the term identically zero everywhere, so the bound lands on the
      identity and not on a pole (root CLAUDE.md § Invariants; contrast
      ``PreferredOrientation.r``).  A declared peak is therefore bit-identical
      to no peak until something frees it.
    * ``fwhm`` — °2θ, floored at :data:`EXTRA_PEAK_FWHM_MIN` with the
      same reachability repair :class:`HumpComponent` carries, because this one
      divides.  **Finite ``min``/``max`` are required** for the window reason
      above: the half-width is ``k(η)·fwhm.max``, so an unbounded width is an
      unbounded window.
    * ``eta`` — the Gaussian/Lorentzian mixing, bounded to [0, 1], default
      0.5.  Both ends are legitimate (η = 0 is a pure Gaussian, η = 1 a pure
      Lorentzian) and neither is a pole, so unlike a width this needs no floor
      — but it does need the upper bound, which is what
      :class:`HumpComponent`'s own docstring predicted for the η it declined to
      have.  **η's upper bound sizes the window too**: ``k(η)`` is the
      half-width in FWHM units at which the discarded area of the profile stays
      under ``forward.WINDOW_AREA_TOL``, and it is a steep function of η
      (k(0) ≈ 1.05, k(0.6) ≈ 9.5, k(1) ≈ 16), so the window is built at ``k`` of
      η's *upper bound* and never of its value.  A caller who knows the peak is
      near-Gaussian can say so with ``eta.max`` and buy a much smaller window.

    All four default to ``vary=False``.  **One** preset frees them —
    ``mccusker_structural``'s ``extra_components`` stage, whose glob
    ``instrument.extra_components.*`` is member-blind because the dot-path
    carries the list index and never the ``kind`` — and every other preset
    stops short of the prefix.  Nothing ever *adds* a component, which is the
    safety property that matters: a sharp peak with a free area improves any
    Rwp, so one exists only because the caller declared it.
    """

    #: apparent °2θ centre of the **primary** emission line.  Required, and
    #: required to carry finite bounds: they size the frozen window.
    center: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, unit="deg"))
    area: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, min=0.0, unit="counts*deg"))
    fwhm: Parameter = Field(
        default_factory=lambda: Parameter(value=0.1,
                                          min=EXTRA_PEAK_FWHM_MIN,
                                          max=EXTRA_PEAK_FWHM_MAX,
                                          unit="deg"))
    eta: Parameter = Field(
        default_factory=lambda: Parameter(value=0.5, min=0.0, max=1.0))
    #: Place an image of this peak at every emission line, weighted by the
    #: line's weight × its Lorentz-polarisation ratio.  ``False`` for something
    #: that does not diffract (fluorescence, a detector artefact).
    all_lines: bool = True
    #: Discriminator.  Its one legal value names this member of
    #: :data:`ExtraComponent`; the union dispatches on it, never on shape.
    kind: Literal["peak"] = "peak"
    #: free-text tag, e.g. ``"steel holder 110"``.  Rendered in diagnostics so a
    #: finding can name the peak a human declared.  Not a parameter and not part
    #: of any dot-path — the paths index the list, so a relabelled peak keeps its
    #: refined values.
    label: str | None = None

    @model_validator(mode="after")
    def _window_bounds_are_finite(self) -> "PeakComponent":
        """Refuse a peak whose window cannot be sized, and say what to write.

        ``center`` and ``fwhm`` bound the frozen evaluation window, so an
        infinite bound is not a loose claim but an unbuildable one.  This is a
        refusal rather than a repair because the range is a fact about the
        caller's pattern that the schema cannot see — the
        :meth:`HumpComponent._fwhm_floor_is_reachable` situation inverted, where
        the repair was possible precisely because the floor was a property of
        the profile's pole and not of anyone's data.
        """
        for name, hint in (("center", "min=28.0, max=28.8"),
                           ("fwhm", f"min={EXTRA_PEAK_FWHM_MIN}, max=0.5")):
            par = getattr(self, name)
            if not (math.isfinite(par.min) and math.isfinite(par.max)):
                raise ValueError(
                    f"PeakComponent.{name} needs finite min and max: they size "
                    "the evaluation window, which is frozen at stage compile and "
                    "cannot follow a parameter that has no bound. Give it the "
                    f"range you expect — e.g. Parameter(value={par.value!r}, "
                    f"{hint}, unit='deg').")
        return self

    @model_validator(mode="after")
    def _fwhm_floor_is_reachable(self) -> "PeakComponent":
        """Repair a width bound at zero, where the pseudo-Voigt's pole is.

        :meth:`HumpComponent._fwhm_floor_is_reachable` byte for byte, at this
        member's floor, and for the reason stated there: the broken bound
        **outlives the default**, so a stored ``min: 0.0`` deserializes straight
        back into the pole and no ``default_factory`` ever runs on that path.
        """
        if self.fwhm.min <= _ZERO_BOUND:
            # value **before** min, as in the hump: ``Base`` validates on
            # assignment, so raising the floor under a value still below it
            # would trip ``Parameter._check_bounds`` mid-repair.
            self.fwhm.value = max(self.fwhm.value, EXTRA_PEAK_FWHM_MIN)
            self.fwhm.min = EXTRA_PEAK_FWHM_MIN
        return self


#: A declared parametric term added to the calculated pattern, discriminated on
#: ``kind``.  One member today, :class:`HumpComponent`; WP-1103 adds a sharp
#: peak.  The union is a *bare* PEP-604 alias with ``kind`` ``Literal``\ s, the
#: :data:`Background` precedent, and :attr:`Instrument.extra_components` is the
#: list of them.
#:
#: **Why a union and not a second list per shape.**  Every code that has been
#: asked this carries several kinds of additive non-Bragg term at once: GSAS-II
#: a background function *plus* Debye diffuse terms *plus* background peaks
#: (Toby & Von Dreele, 2013, *J. Appl. Cryst.* **46**, 544); FullProf's ``Nba``
#: selects polynomial, Debye-like *plus* polynomial, Fourier filtering or a
#: table (manual eq. 3.4); TOPAS a peaks phase beside ``fit_obj`` (Coelho, 2018,
#: *J. Appl. Cryst.* **51**, 210).  A list of one concrete type is the shape
#: none of them chose.
#:
#: **The member contract.**  Every member owes all six, and a new member that
#: cannot pay one of them is the wrong shape for this seam:
#:
#: 1. **An evaluator in ``xp`` ops**, whole-grid or frozen-window, so every
#:    backend differentiates it through the traced twin and no member needs an
#:    analytic Jacobian branch of its own.  The arithmetic lives where it
#:    belongs — a hump's in :mod:`rietx.background.models`, a peak's in the
#:    unit-area pseudo-Voigt every reflection already uses — and
#:    :mod:`rietx.model.forward` calls it directly.  This clause once said the
#:    evaluators were *registered* in :mod:`rietx.model.components`; that module
#:    did not exist when the sentence was written, and when WP-1103 built it the
#:    evaluator table had no reader, so it was deleted.  What the clause
#:    requires is a property of the evaluator, not a place to list it.
#: 2. **A declared aggregate membership**, held as *data* rather than implied by
#:    the class: which reported aggregate the member's curve joins — the
#:    reported background (``result.y_background``, ``BackgroundEvidence``, the
#:    absorption span) for a hump, the tick list for a peak.  It is the axis on
#:    which members differ most, and reading it off the class name is how a
#:    member ends up counted twice or not at all.  The declaration is
#:    :data:`rietx.model.components.COMPONENT_AGGREGATE`, and it is read, never
#:    inferred.
#: 3. **Its curve is subtracted from the Le Bail/Pawley partition net**, or
#:    phases are handed shares of counts that are not theirs.  For a
#:    background-landing member this is free, because
#:    :meth:`~rietx.model.forward.CompiledModel.background` is the one authority
#:    the partition already calls.
#: 4. **Its refinable fields are declared once** and registered through one
#:    helper feeding *both* ``_collect_instrument`` and ``apply_to_models``; a
#:    field registered in one and forgotten in the other loses its refined value
#:    at the next stage's recompile, silently.
#: 5. **A new member is a closed-vocabulary schema event** — a
#:    ``SCHEMA_VERSION`` bump — and ships with a cross-backend ``CONFIGS`` row,
#:    a manual equation carrying its ``*Source:*`` line, and :mod:`rietx.help`
#:    entries.
#: 6. **A member is state, never code.**
#:
#: **What clause 6 admits, and what it fences.**  An *expression* member —
#: serializable text over this package's own dot-paths, evaluated and
#: differentiated like any other term — is admissible under this contract, and
#: is what TOPAS's arbitrary functions actually are: its computer-algebra layer
#: writes one node in terms of others as text in the INP file, tracks the
#: dependencies, and gets the derivatives from them (Coelho, 2018, §2).  A
#: **Python callable** is not admissible, and the three grounds are the ones
#: that do *not* apply to an expression:
#:
#: * history stores state, and an expression string **is** state, serializing
#:   and restoring like any other field — a callable is not;
#: * the traced twin must differentiate the same term on jax and torch, and an
#:   expression tree is the *easy* case for both — a Python callable closed over
#:   arbitrary objects is not traceable at all;
#: * the agent surface is JSON schemas under ``extra="forbid"``, and a ``str``
#:   field is legal there — a callable has no JSON form.
#:
#: This package already has both halves TOPAS pairs: a typed tree addressed by
#: dot-paths, and a tie layer writing one entry in terms of others (affine, so
#: far — WP-1070).  Building an expression member is neither this WP's work nor
#: WP-1103's; the contract is written so that it would be a member rather than a
#: redesign.
#:
#: **What this union has proved, and what it has not.**  The contract has two
#: axes — an evaluator's *shape*, and *where the member lands* — and they are no
#: longer in the same state.  :class:`HumpComponent` is a local bump in 2θ
#: reported as background; :class:`PeakComponent` is the same evaluator shape
#: landing somewhere else entirely, on the tick list, which is what turned
#: clause 2 from a design intention into a tested one (WP-1103).  Read the
#: membership from :data:`rietx.model.components.COMPONENT_AGGREGATE`; a member
#: that infers it from the class name passes no test here.
#:
#: The *first* axis is still untested.  Both members are a local feature in 2θ
#: evaluated over a window; a Debye term ``Σⱼ Bⱼ·sin(Q rⱼ)/(Q rⱼ)`` — a
#: whole-pattern oscillation in Q, which GSAS-II and FullProf both ship and this
#: package does not — would be its proving case.  Until one lands, a claim that
#: this seam admits *any* evaluator shape is an intention.
ExtraComponent = HumpComponent | PeakComponent

#: :meth:`Instrument.debye_scherrer`'s polarisation K, in the GSAS POLA
#: convention: 0.99, as APS 11-BM's instrument-parameter files state it.  An
#: assumption about the caller's beam, which a lab capillary does not share.
DEBYE_SCHERRER_POLARIZATION = 0.99
#: :meth:`Instrument.bragg_brentano`'s goniometer radius, mm: the radius a lab
#: diffractometer commonly has, there because the geometry refuses a missing one.
BRAGG_BRENTANO_RADIUS_MM = 217.5
#: The Kα2/Kα1 intensity ratio the lab presets seed: 0.5 is the 2j+1 degeneracy
#: ratio (4:2).  Measured integrated ratios run a few percent above it and a
#: diffracted-beam monochromator clips it (Hölzer et al. 1997, Phys. Rev. A 56,
#: 4554); ``lab_bragg_brentano`` refines it and ``mccusker_default`` holds it.
KA2_RATIO = 0.5


class Instrument(_InheritsDeclaredDefaults):
    """Everything about the measurement except the sample.

    A declaration, not an output: the number an agent usually wants first is
    ``instrument.source.primary_wavelength`` (a plain float, the first line's
    wavelength); a fitted value comes back on the *result*, never here.
    """

    #: Discriminated on ``kind``: ``"xray_cw"`` is :class:`Source`,
    #: ``"neutron_cw"`` is :class:`NeutronSource`, ``"neutron_tof"`` is
    #: :class:`TOFSource`.  A union rather than one class with inert fields —
    #: see :class:`NeutronSource`.  A ``neutron_tof`` source puts a flight time
    #: on the pattern's abscissa and is **read, never refined**, in this build:
    #: every entry that would compute a pattern refuses it by name through
    #: :func:`rietx.schemas.pattern.require_two_theta`.
    source: Source | NeutronSource | TOFSource = Field(discriminator="kind")
    geometry: Geometry = Field(default_factory=Geometry)
    #: unbounded with the other position corrections since 2026-10-20: see
    #: ``Geometry``'s comment above ``sample_displacement`` for why (WP-2002)
    zero_shift: Parameter = Field(
        default_factory=lambda: Parameter(value=0.0, unit="deg")
    )
    profile: ProfileTCHZ = Field(default_factory=ProfileTCHZ)
    background: Background = Field(
        default_factory=lambda: BackgroundChebyshev(), discriminator=None
    )
    #: Explicit broad peaks **added on top of** ``background``, not a kind of
    #: it (:class:`HumpComponent`).  The empty default is **exactly off**: no
    #: path is registered, no term is evaluated, and the serialized instrument
    #: differs from a pre-``extra_components`` one only by ``[]`` — the idiom
    #: ``Structure.restraints``, ``Phase.microstrain`` and
    #: ``Geometry.surface_roughness`` already use, pinned by a bit-identity
    #: test rather than asserted here.
    #:
    #: The field name is ``extra_components`` and **not** ``background.peaks``
    #: on purpose: fnmatch's ``*`` crosses dots, so a nested spelling would be
    #: matched by the ``instrument.background.*`` glob every preset's first
    #: stage carries, and every declared peak would be freed at stage 1 — a
    #: free position over a pattern whose peaks have not been placed yet.  The
    #: underscore puts the paths outside that glob by construction instead of
    #: by retightening seven presets.
    extra_components: list[ExtraComponent] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _migrate_v1_2_background_peaks(cls, value: Any) -> Any:
        """Read a 1.2-era ``background_peaks`` block as ``extra_components``.

        The field shipped in v1.2 under the old name, so a project, a history
        node or an ``.rxt`` written by that release carries it.  **Old files
        open; old code does not**: this reads the legacy key on the way in, and
        assigning ``instrument.background_peaks`` still raises under
        ``extra="forbid"``, which is the direction the repo breaks in.

        Only the *field* is repaired here.  The stored **paths** — a history
        node's ``free_paths``, a saved plan's globs — are the other half and are
        migrated in :mod:`rietx.schemas.migrate`, because they are the half that
        fails in silence: a missing field raises, while a glob that no longer
        matches anything simply stops refining a declared hump and returns a
        plausible answer.
        """
        if isinstance(value, dict) and _LEGACY_COMPONENT_FIELD in value:
            value = dict(value)
            legacy = value.pop(_LEGACY_COMPONENT_FIELD)
            # an explicit new-name block wins: a document carrying both was
            # written by something that already knew the new name, and the
            # legacy key is then a leftover rather than the payload
            value.setdefault("extra_components", legacy)
        return value

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
            harmonics: list[int] | bool = False) -> "Instrument":
        """Constant-wavelength neutron powder diffractometer.

        Debye-Scherrer geometry, because that is what a CW neutron
        diffractometer is — a can of powder in a beam with detectors on a
        circle — so the cylindrical absorption correction and the eq (4)
        capillary offsets apply unchanged.

        ``fwhm_deg`` seeds ``w`` alone, at the observed peak width squared,
        which matters more here than on a lab X-ray: a neutron instrument's
        lines are typically 0.2-0.5° where the ``ProfileTCHZ`` default is a
        *synchrotron* line of ~0.03°, and the frozen per-stage evaluation
        windows are sized from the seed.  Left ``None``, the default stands and
        a 0.3° line will not be found.

        The seeded profile is a flat Gaussian of ``fwhm_deg`` at every angle,
        with ``x`` left at its negligible default: the width you observed is
        the width you get.

        The profile is built by :meth:`ProfileTCHZ.coarse`, in the box every
        preset builds (:data:`TCHZ_BOUNDS`).  U and V have no floor of their
        own, so a long-wavelength CW neutron model fits in it (issue #276:
        V = −0.501 on D1B at λ = 2.52 Å).  Every width's ceiling is the 2θ
        axis (:data:`TCHZ_CEILING_DEG`), so any ``fwhm_deg`` up to 180° seeds
        ``w`` at its square.  A *bare* width still
        refuses: ``ProfileTCHZ(u=1.576)`` raises, naming
        ``ProfileTCHZ.coarse`` and an explicit ``Parameter`` as the ways out.

        Note the profile itself needs no neutron-specific code: the Caglioti
        law U·tan²θ + V·tanθ + W *is* the neutron resolution function (Caglioti,
        Paoletti & Ricci, 1958, *Nucl. Instrum.* **3**, 223), and the X-ray path
        is the borrower.

        ``harmonics`` declares the λ/n components a monochromator that does not
        filter its own orders lets through (:class:`Harmonic`), as the list of
        orders n it passes: ``[2]`` for Cu(311) or pyrolytic graphite,
        ``[3]`` for Si(111) or Ge(311), whose second order is extinct,
        ``[2, 3]`` for both.  ``True`` is refused, since which orders pass
        depends on the crystal.  ``False``, the default, leaves the source with
        the single line it has always had, so every number measured before this
        argument existed is reproduced bit for bit.  The declared weights arrive **fixed** — free
        them with the ``instrument.source.lines.*.weight`` glob once the profile
        and the scale are settled, never in the opening stage.
        """
        if harmonics is True:
            raise ValueError(
                "harmonics=True does not say which orders the monochromator passes, "
                "and that depends on its crystal: name them, e.g. harmonics=[2] for "
                "Cu(311) or pyrolytic graphite, harmonics=[3] for Si(111) or Ge(311), "
                "whose second order is extinct")
        orders = [] if harmonics is False else list(harmonics)
        inst = cls(source=NeutronSource(
                       wavelength=wavelength,
                       harmonics=[Harmonic(order=n) for n in orders]),
                   geometry=Geometry(kind="debye_scherrer",
                                     goniometer_radius_mm=goniometer_radius_mm,
                                     capillary_radius_mm=capillary_radius_mm,
                                     mu_r=mu_r),
                   profile=ProfileTCHZ.coarse())
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
    def tof_neutron_bank(cls, difc: float, *, two_theta_bank_deg: float,
                         difa: float = 0.0, tzero: float = 0.0,
                         difb: float = 0.0,
                         l1_m: float | None = None, l2_m: float | None = None,
                         capillary_radius_mm: float | None = None,
                         mu_r: float | None = None,
                         profile: ProfileTOF | None = None) -> "Instrument":
        """One detector bank of a neutron time-of-flight diffractometer.

        Beside :meth:`constant_wavelength_neutron`, and the same shape of
        preset: Debye-Scherrer geometry, because that is what a TOF
        diffractometer is — a can of powder in a white beam with banks of
        detectors at fixed angles.  ``difc`` is the only required constant; a
        bank with no measured DIFA or TZERO is the ordinary starting point and
        the three-term relation with two zeros is exactly the two-term one.

        **A multi-bank experiment is several instruments, not one.**  DIFC,
        DIFA, TZERO and the whole profile differ per bank — that is what a bank
        *is* — so each bank gets its own ``Instrument`` and they meet in a
        multi-histogram fit once a time-of-flight forward model exists, the
        way several wavelengths meet today
        (:class:`rietx.multi.MultiHistogramRefinement`).

        This build builds and reads such a bank and refines none; see
        :class:`TOFSource`.
        """
        source = TOFSource(difc=difc, difa=difa, tzero=tzero, difb=difb,
                           two_theta_bank_deg=two_theta_bank_deg,
                           l1_m=l1_m, l2_m=l2_m,
                           profile_tof=profile or ProfileTOF())
        return cls(source=source,
                   geometry=Geometry(kind="debye_scherrer",
                                     capillary_radius_mm=capillary_radius_mm,
                                     mu_r=mu_r))

    @classmethod
    def debye_scherrer(cls, wavelength: float, *,
                       polarization: float = DEBYE_SCHERRER_POLARIZATION,
                       goniometer_radius_mm: float | None = None,
                       capillary_radius_mm: float | None = None,
                       packing_fraction: float = PACKING_FRACTION,
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
                       goniometer_radius_mm: float = BRAGG_BRENTANO_RADIUS_MM,
                       monochromator_two_theta: float | None = None,
                       ka2_ratio: float = KA2_RATIO,
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
        ``None`` → unpolarized beam, K = 0.5.  A monochromator also removes Kβ,
        so it sets ``Source.kbeta = "monochromator"`` and the contamination
        screen skips its Kβ and W Lα searches; one declaration says both.

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
        kbeta = None
        if monochromator_two_theta is not None:
            c2 = math.cos(math.radians(monochromator_two_theta)) ** 2
            k = 1.0 / (1.0 + c2)
            kbeta = "monochromator"
        emission = [EmissionLine(wavelength=lines[0],
                                 weight=Parameter(value=1.0, min=0.0))]
        for wl in lines[1:]:
            emission.append(EmissionLine(
                wavelength=wl,
                weight=Parameter(value=ka2_ratio, min=0.0)))
        return cls(
            source=Source(
                lines=emission,
                polarization=Parameter(value=k, min=0.0, max=1.0),
                kbeta=kbeta,
            ),
            geometry=Geometry(kind="bragg_brentano",
                              goniometer_radius_mm=goniometer_radius_mm,
                              mu_t=mu_t, thickness_mm=thickness_mm),
        )


    @classmethod
    def flat_plate_transmission(cls, *, radiation: str = "CuKa1",
                                mu_t: float | None = None,
                                thickness_mm: float | None = None,
                                packing_fraction: float = PACKING_FRACTION,
                                ka2_ratio: float = KA2_RATIO) -> "Instrument":
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
                                 weight=Parameter(value=1.0, min=0.0))]
        for wl in lines[1:]:
            emission.append(EmissionLine(
                wavelength=wl, weight=Parameter(value=ka2_ratio, min=0.0)))
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
