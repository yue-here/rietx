"""WP-1202 — one authority for what a name in this package *means*.

A parameter path, a peak flag, a stage field, a reader option, an instrument
preset field and an indexing search setting are all things a person has to be
told about, and before this module each was told about in a different place or
nowhere at all: 169 ``title=`` strings in the frontend, two hand-written
TypeScript corpora, and no description of ``instrument.profile.w`` anywhere in
the tree.  The corpus lives here so the GUI, the CLI and the manual read the
same sentence.

Three rules govern what may be written down here, the first two of them the root
CLAUDE.md's "a derived flag rots silently" one rank over.

**A fact the package already computes is never restated.**  ``unit`` and
``default`` are pinned to the live :class:`~rietx.schemas.common.Parameter` by
``tests/test_help.py``, through :data:`UNIT_DISPLAY` for the spelling difference
between a schema (``deg^2``) and a page (``deg² 2θ``); the plan arm is
:data:`~rietx.strategy.staged.PLAN_INFO` projected, not paraphrased.  A retuned
default or a renamed unit fails a test rather than leaving a stale number in
print.

**Every arm is meta-tested against its live registry.**  The vocabularies are
closed and derivable (``PeakFlag``, the diagnostic codes,
``StageSpec``'s fields, ``READER_OPTIONS``, ``INSTRUMENT_PRESETS``,
``IndexingControls`` flattened one level, the fields of
:data:`RESULT_FIELD_TYPES`), so a member added without an entry
fails coverage the day it lands.  That is why the arms are
keyed by name and the parameter families by glob rather than being one flat dict:
each key set has a different authority to be checked against.

**A description that states a formula or a threshold names where the real one
lives.**  ``description`` is authored, so a formula in one is a *copy* with
nothing holding it to the code, and the copy drifts silently because no test
reads prose.  WP-1437 measured what that costs: this module told users the
Lorentz-polarisation factor was ``(1 + K·cos²2θ)/(1 + K)`` while
:func:`~rietx.model.corrections.lorentz_polarization` computed
``K + (1 − K)·cos²2θ``, which at the K = 0.99 the same entry quoted for 11-BM
is a factor of 0.508 at 2θ = 90° and 0.878 at 30°.  The ratio *varies with
angle*, so no phase scale absorbs it and it biases ADPs and phase fractions.
The naming is the whole guard: a reader who can reach the computing function
can check it, and a session renaming that function finds the entry by grep.
A threshold goes further and is **pinned** — see
``test_quoted_thresholds_are_the_codes_own`` in ``tests/test_help.py`` — because
a number has a live constant to be held against where a sentence does not.

``typical`` is the one field with no live authority.  It is a range a reader can
sanity-check their own number against, sourced from McCusker et al. (1999)
J. Appl. Cryst. 32, 36 and from this repository's own reference datasets, and it
is prose: no code reads it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from fnmatch import fnmatchcase

__all__ = [
    "HelpEntry",
    "PARAMETER_HELP",
    "DIAGNOSTIC_HELP",
    "PEAK_FLAG_HELP",
    "PEAK_ORIGIN_HELP",
    "READER_OPTION_HELP",
    "SEARCH_FIELD_HELP",
    "RESULT_FIELD_HELP",
    "RESULT_FIELD_TYPES",
    "INSTRUMENT_FIELD_HELP",
    "STAGE_FIELD_HELP",
    "UNIT_DISPLAY",
    "explain",
    "help_for",
    "help_key_for",
    "help_registry",
    "plan_help",
]


@dataclass(frozen=True)
class HelpEntry:
    """What one name is, in the fields a reference entry always carries.

    ``unit`` and ``default`` are ``None`` where the quantity has none: a
    fractional coordinate is dimensionless, and a cell edge has no default
    because it arrives with the structure.

    ``anchor`` is where the explanation continues, as ``page.html#heading-id``
    relative to the root of the manual in ``docs/docs/`` — so a consumer builds
    a link by joining it to :func:`rietx._about.docs_base` of the running
    version (``<DOCS_URL>/docs/dev`` or ``…/docs/X.Y``) and nothing has to know
    the manual's layout a second time.  The page carries its tab:
    ``theory/<chapter>.html`` for the equation behind a parameter,
    ``reference/…``, ``guides/…`` or ``concepts/…`` where the fact is about the
    API rather than the physics.  It carried the id alone until WP-1203 needed
    to *render* the link and found that an id names no page; every one of the
    thirty was on exactly one page of the built manual, which is what made the
    change mechanical.  WP-1986 moved every anchor off the old tree's site-root
    pages onto the new tree's, under the versioned base.  ``tests/test_help.py``
    checks it against the new tree's built HTML rather than the sources — a
    heading that fails to render still has an id in the Markdown — and checks
    the page as well as the id, which the bare form could not.

    ``label`` is the short form a chip carries where the name itself would not
    read — ``at bound`` for ``position_at_bound`` (WP-1209).  The GUI's
    ``labelFor`` (``gui/src/lib/help.ts``) draws it on the chip and the popover
    restores the name behind it; the glossary prints it as *Chip*.  It is the
    second authored field after ``typical``: nothing in the package reads it.
    ``tests/test_help.py`` names the arms whose members are chips and holds
    every entry there to a label of one to three words, unique within the arm;
    an arm that draws no chip carries ``None``.
    """

    title: str
    description: str
    unit: str | None = None
    default: str | None = None
    typical: str | None = None
    anchor: str | None = None
    label: str | None = None


#: How a :class:`~rietx.schemas.common.Parameter`'s ``unit`` is spelled for a
#: reader.  Data rather than convention because ``tests/test_help.py`` crosses
#: the two spellings with it: a schema unit absent from this table is a unit
#: nothing has decided how to print.
UNIT_DISPLAY: dict[str, str] = {
    "A": "Å",
    "deg": "deg 2θ",
    "deg^2": "deg² 2θ",
    "mm": "mm",
    "A^2": "Å²",
    "counts": "counts",
    "counts*deg": "counts·deg 2θ",
    "1e-12 A^-4": "10⁻¹² Å⁻⁴",
    "mu_B": "μ_B",
    "um^2": "µm²",
    # The time-of-flight arm.  Ten spellings for fourteen parameters, because
    # a flight time is µs and every coefficient is a polynomial in d, so each
    # power of Å rides along: ``TOFSource``'s four constants and
    # ``ProfileTOF``'s ten coefficients between them use all of these.
    "us": "µs",
    "us/A": "µs/Å",
    "us/A^2": "µs/Å²",
    "us*A": "µs·Å",
    "1/us": "µs⁻¹",
    "A/us": "Å/µs",
    "A^4/us": "Å⁴/µs",
    "us^2": "µs²",
    "us^2/A^2": "µs²/Å²",
    "us^2/A^4": "µs²/Å⁴",
}


# ----------------------------------------------------------------------
# Parameter families
#
# Keyed by the fnmatch glob a plan stage would use, matched with the same
# `fnmatchcase` `ParameterTable.set_vary` calls, so a key here is a string a
# reader can paste into a `turn_on` list.  Several globs may share one entry
# where they share a meaning: a, b and c are one cell edge described once.
# `tests/test_help.py` asserts that every path a live `ParameterTable` produces
# matches exactly one entry, and that every entry matches at least one path.
# ----------------------------------------------------------------------

_CELL_LENGTH = HelpEntry(
    title="Lattice parameter a, b, c",
    description=(
        "A lattice parameter that gives the length of a unit-cell axis. It sets "
        "every reflection position through the lattice metric. A powder pattern "
        "determines it better than any other parameter, and a systematic position "
        "error corrupts it first. An edge that the space-group setting ties to "
        "another (b to a in a tetragonal cell) is held and follows its source."
    ),
    unit="Å", default=None,
    typical="3-40 Å for an inorganic phase; refined shifts are 10-1000 ppm",
    anchor="theory/peak-positions.html#lattice-metric-and-bragg-s-law",
)
_CELL_ANGLE = HelpEntry(
    title="Lattice parameter α, β, γ",
    description=(
        "A lattice parameter that gives the angle between two cell axes. The "
        "space-group setting fixes some angles at 90° or 120°. Those angles are "
        "locked and cannot be freed. A monoclinic cell frees only its unique-axis "
        "angle."
    ),
    unit="deg", default=None,
    typical="90° or 120° when symmetry fixes it; 80-100° for a monoclinic β",
    anchor="theory/peak-positions.html#lattice-metric-and-bragg-s-law",
)
_BODY_ORIGIN = HelpEntry(
    title="Rigid-body origin",
    description=(
        "The position of a rigid body's origin, in fractional coordinates. Like an "
        "atom's x, y and z, it follows the refined origin shifts and is written "
        "back after each stage. Free those shifts with "
        "`phases.*.rigid_bodies.*.origin.dof.*`."
    ),
    unit=None, default=None,
    typical="0 to 1",
    anchor="theory/parameterisation.html#rigid-bodies",
)


_ATOM_COORD = HelpEntry(
    title="Fractional coordinate",
    description=(
        "An atom's position along a cell axis, as a fraction of the lattice "
        "parameter along that axis. You do not refine it directly. rietx ties x, y "
        "and z to the shifts that the site symmetry allows, so editing a position "
        "means editing the `dof.k` entries it follows. An atom on a fully fixed "
        "special position has no free direction, and its coordinates are locked."
    ),
    unit=None, default=None,
    typical="0 to 1",
    anchor="theory/parameterisation.html#site-symmetry-degrees-of-freedom",
)
_ATOM_ANISO_U = HelpEntry(
    title="Anisotropic displacement component",
    description=(
        "One component of the anisotropic displacement tensor `U^ij`, as stored in "
        "the CIF, in Å². Like the coordinates, it is tied to other entries. The "
        "refined quantities are the `adp.k` entries, which span the tensors that "
        "the site symmetry allows. rietx refuses a tensor outside that set."
    ),
    unit="Å²", default=None,
    typical="0.005-0.05 Å² on the diagonal; off-diagonal components are smaller",
    anchor="theory/intensities.html#debye-waller-factors-and-adp-representations",
)
_STEPHENS_S = HelpEntry(
    title="Stephens strain coefficient",
    description=(
        "One `S_HKL` coefficient of the Stephens (1999) anisotropic strain model. "
        "It multiplies the monomial `h^H k^K l^L`, taken literally. The unit is "
        "10⁻¹² Å⁻⁴. In Å⁻⁴ the physical values sit near 10⁻⁸, and a numerical "
        "derivative would step 100 times further than the value itself. Like the "
        "anisotropic displacement components, these coefficients are tied. The "
        "refined quantities are the `microstrain.dof.k` entries of the Laue-allowed "
        "subspace."
    ),
    unit="10⁻¹² Å⁻⁴", default="0.0",
    typical="0-500 for a sample with measurable anisotropic strain",
    anchor="theory/microstructure.html#stephens-anisotropic-strain",
)

PARAMETER_HELP: dict[str, HelpEntry] = {
    # -- instrument --------------------------------------------------
    "instrument.zero_shift": HelpEntry(
        title="Zero-point shift",
        description=(
            "A constant offset added to every calculated 2θ. It absorbs the zero-point "
            "misalignment of the goniometer. It is a property of the diffractometer. "
            "Calibrate it on a standard with a certified cell, then hold it. Freed "
            "together with the lattice parameters and the specimen displacement, it is "
            "close to degenerate with both. Calibrating on a held cell is the step that "
            "separates the three."
        ),
        unit="deg 2θ", default="0.0",
        typical="|Δ| < 0.05 deg on an aligned diffractometer",
        anchor="theory/peak-positions.html#aberration-shifts",
    ),
    "instrument.polarization": HelpEntry(
        title="Polarisation factor",
        description=(
            "The K of the Lorentz-polarisation correction. Its polarisation numerator "
            "is K + (1 − K)·cos²2θ, computed by "
            "`model.corrections.lorentz_polarization`. K is the fraction of the beam "
            "polarised perpendicular to the diffraction plane. The beam optics fix it, "
            "so you declare it and no plan frees it. An unpolarised laboratory source "
            "gives 0.5. A diffracted-beam monochromator gives 1/(1 + cos²2θm), where "
            "2θm is the monochromator angle. That is 0.556 for graphite (002) at Cu Kα "
            "and 0.630 for the same crystal at Cr Kα. The APS 11-BM "
            "instrument-parameter files carry 0.99. A constant-wavelength neutron "
            "source has K = 1. The numerator is then 1, the factor is the bare Lorentz "
            "factor, and rietx force-fixes the entry."
        ),
        unit=None, default="0.5",
        typical="0.5 unmonochromated lab; 0.51-0.63 monochromated lab "
                "(graphite 002, Ag Kα to Cr Kα); 0.9-1.0 synchrotron",
        anchor="theory/corrections.html#lorentz-polarisation",
    ),
    "instrument.source.lines.*.wavelength": HelpEntry(
        title="Emission wavelength",
        description=(
            "The wavelength of one emission line. Bragg's law fixes only the product of "
            "the wavelength and the cell scale, so the two cannot be separated. A free "
            "wavelength with a free lattice parameter is a flat direction. The row "
            "reports `needs_held_cell`, and `set_vary` refuses to free the wavelength "
            "while any cell parameter is free. Refine it against a standard with a "
            "certified cell, or leave it at the tabulated value."
        ),
        unit="Å", default=None,
        typical="1.540598 Å Cu Kα1, 0.7093 Å Mo Kα1, 0.3-1.0 Å synchrotron",
        anchor="theory/peak-positions.html#the-wavelengthcell-degeneracy",
    ),
    "instrument.source.lines.*.weight": HelpEntry(
        title="Emission line weight",
        description=(
            "The intensity of one emission line relative to line 0. Line 0 is locked at "
            "1 because it is degenerate with the phase scales. Only a second or later "
            "line has a refinable weight. For a Kα doublet the starting value is the "
            "2j+1 degeneracy ratio. Refine it only when a monochromator or a filter has "
            "changed that ratio."
        ),
        unit=None, default="1.0",
        typical="0.5 for Kα2 against Kα1",
        anchor="theory/peak-positions.html#wavelength-scales",
    ),
    "instrument.geometry.sample_displacement": HelpEntry(
        title="Specimen displacement",
        description=(
            "How far the specimen surface sits off the goniometer axis. It is positive "
            "toward the source and detector side of the focusing circle. On a "
            "Bragg-Brentano mount it shifts every line by −2s·cosθ/R (McCusker equation "
            "3), where s is the displacement and R the goniometer radius. This is "
            "usually the largest systematic position error in a laboratory pattern. Its "
            "cosθ shape is close to the constant shape of `zero_shift`, so freeing both "
            "on one pattern usually reports a correlation. It has no default bound. "
            "Where the scan cannot separate it from the zero and the cell, the fit "
            "reports `FLAT_DIRECTION` and the cell's esd grows to show it. Set a bound if "
            "you know your mount."
        ),
        unit="mm", default="0.0",
        typical="|s| < 0.05 mm on a carefully packed flat plate",
        anchor="theory/peak-positions.html#sample-displacement",
    ),
    "instrument.geometry.sample_transparency": HelpEntry(
        title="Specimen transparency",
        description=(
            "The coefficient of the sin 2θ position shift that a beam penetrating the "
            "specimen produces (McCusker equation 4). On a flat plate this is the "
            "transparency aberration. On a capillary the same sin 2θ shape is the "
            "along-beam offset instead. The parameter therefore belongs to a flat-plate "
            "geometry, and the report suggests it only there."
        ),
        unit=None, default="0.0",
        typical="0-0.01 for a dense oxide; larger for a low-absorbing organic",
        anchor="theory/peak-positions.html#sample-transparency",
    ),
    "instrument.geometry.axial_sl": HelpEntry(
        title="Axial divergence: specimen length",
        description=(
            "The Finger-Cox-Jephcoat axial-divergence ratio S/L. It is the illuminated "
            "specimen length divided by the goniometer radius. It sets how strongly "
            "low-angle peaks lean toward low 2θ. Fit it on a standard together with "
            "`axial_hl`. The two are strongly correlated and are usually reported as a "
            "pair. With both at zero and either refined, the peaks are computed with "
            "windows and integration points sized for a ratio of 0.02 (see `axial_hl`)."
        ),
        unit=None, default="0.0",
        typical="0.01-0.05",
        anchor="theory/profiles.html#finger-cox-jephcoat-axial-divergence",
    ),
    "instrument.geometry.axial_hl": HelpEntry(
        title="Axial divergence: detector slit",
        description=(
            "The Finger-Cox-Jephcoat axial-divergence ratio H/L. It is the "
            "receiving-slit height divided by the goniometer radius. It is the second "
            "half of the axial asymmetry. It is so strongly correlated with `axial_sl` "
            "that refining one and holding the other is a common protocol. One ratio "
            "alone still smears the peaks. Only both at zero switch the asymmetry off. "
            "With both at zero and either refined, the peaks are computed with windows "
            "and integration points sized for a ratio of 0.02, so the curve differs from the same model with "
            "both held by up to about 5e-5 of the strongest peak."
        ),
        unit=None, default="0.0",
        typical="0.01-0.05",
        anchor="theory/profiles.html#finger-cox-jephcoat-axial-divergence",
    ),
    "instrument.geometry.capillary_offset_along_beam": HelpEntry(
        title="Capillary offset along the beam",
        description=(
            "How far the capillary axis sits from the rotation centre along the beam "
            "direction. It shifts positions as sin 2θ, the same shape that flat-plate "
            "transparency has. The report suggests this parameter for a Debye-Scherrer "
            "geometry."
        ),
        unit="mm", default="0.0",
        typical="|d| < 0.05 mm on an aligned spinner",
        anchor="theory/peak-positions.html#capillary-displacement",
    ),
    "instrument.geometry.capillary_offset_across_beam": HelpEntry(
        title="Capillary offset across the beam",
        description=(
            "How far the capillary axis sits from the rotation centre perpendicular to "
            "the beam. It shifts positions as cos 2θ. Its shape therefore separates it "
            "from the along-beam offset, unlike the flat-plate pair."
        ),
        unit="mm", default="0.0",
        typical="|d| < 0.05 mm on an aligned spinner",
        anchor="theory/peak-positions.html#capillary-displacement",
    ),
    # Surface roughness is an opt-in Bragg-Brentano block and the two models
    # are alternatives, so each field is its own family: one entry over
    # `surface_roughness.*` would have to quote four different schema defaults.
    "instrument.geometry.surface_roughness.a": HelpEntry(
        title="Suortti roughness: surviving fraction",
        description=(
            "The a of the Suortti (1972) surface-roughness correction, R = [a + (1 − "
            "a)·exp(−b/sinθ)] / [a + (1 − a)·exp(−b)]. It is the fraction of intensity "
            "that survives even at grazing incidence, so 1 − a bounds how deep the "
            "low-angle depression can go. Refine it only together with `b`. At b = 0 "
            "the correction is the identity whatever a is."
        ),
        unit=None, default="0.5",
        typical=(
            "0.5-1. The default sits inside the range because at a = 1 the derivative "
            "with respect to b vanishes, and b could never move off its start"
        ),
        anchor="theory/corrections.html#surface-roughness",
    ),
    "instrument.geometry.surface_roughness.b": HelpEntry(
        title="Suortti roughness: layer depth",
        description=(
            "The dimensionless optical depth of the depleted surface layer in the "
            "Suortti (1972) correction. It sets the angle at which the depression "
            "falls. The depth of the depression comes from `a`. The correction is the "
            "identity at b = 0 and again at large b, so two values of b can reproduce "
            "the same depression. `ROUGHNESS_UNCONSTRAINED` therefore measures the "
            "modelled depression and not b itself. A stage that frees b starts it at "
            "0.3, near where the data can see it, because b = 0 is the identity."
        ),
        unit=None, default="0.0",
        typical="0.1-0.5; past about 3 the correction is dead and its gradient flat",
        anchor="theory/corrections.html#surface-roughness",
    ),
    "instrument.geometry.surface_roughness.c": HelpEntry(
        title="Pitschke roughness: strength",
        description=(
            "The strength of the Pitschke et al. (1993) surface-roughness correction, R "
            "= 1 − c·u·(1 − u), with u = τ/sinθ. At c = 0 there is no correction. The "
            "paper's angle-independent porosity term is omitted here, because a "
            "constant prefactor is degenerate with the phase scale."
        ),
        unit=None, default="0.0",
        typical="0-4; beyond 4 R can go negative inside the valid range",
        anchor="theory/corrections.html#surface-roughness",
    ),
    "instrument.geometry.surface_roughness.tau": HelpEntry(
        title="Pitschke roughness: τ",
        description=(
            "The dimensionless roughness parameter τ = t₀/β of the Pitschke et al. "
            "(1993) correction. You refine τ directly, because diffraction data cannot "
            "constrain the particle size behind it. The correction is monotone only "
            "while sinθ ≥ 2τ, and it would amplify intensity beyond sinθ = τ. "
            "`ROUGHNESS_OUTSIDE_REGIME` reports that case, because a bound on τ cannot "
            "express a limit that depends on the fitted range."
        ),
        unit=None, default="0.05",
        typical="0.005-0.12, the span of the paper's own four specimens",
        anchor="theory/corrections.html#surface-roughness",
    ),
    "instrument.profile.u": HelpEntry(
        title="Caglioti U",
        description=(
            "The tan²θ term of the Gaussian variance, `Γ_G² = U·tan²θ + V·tanθ + W`. It "
            "carries the strain-like broadening of the instrument. A phase's "
            "`gauss_strain` adds to it, because variances add under convolution. "
            "Instrument and specimen therefore stack here, and neither replaces the "
            "other. Refining U while the specimen's `gauss_strain` is also free fits "
            "one quantity twice."
        ),
        unit="deg² 2θ", default="0.0",
        typical="0-0.05 on a laboratory diffractometer",
        anchor="theory/profiles.html#thompson-cox-hastings-pseudo-voigt",
    ),
    "instrument.profile.v": HelpEntry(
        title="Caglioti V",
        description=(
            "The tanθ term of the Gaussian variance `Γ_G² = U·tan²θ + V·tanθ + W`, "
            "which `model.profiles.caglioti.gaussian_fwhm` computes. It is the Caglioti "
            "term that usually goes negative. U, V and Y have no floor of their own, "
            "because what must stay positive is the width, and the default solver holds "
            "both widths at every reflection. W and X are bounded below and cannot go "
            "negative. The width curve has its "
            "minimum at tanθ = −V/(2U). No specimen term adds to V, so V belongs to the "
            "instrument. A phase's `gauss_strain` adds to U instead."
        ),
        unit="deg² 2θ", default="0.0",
        typical="−0.05 to 0",
        anchor="theory/profiles.html#thompson-cox-hastings-pseudo-voigt",
    ),
    "instrument.profile.w": HelpEntry(
        title="Caglioti W",
        description=(
            "The constant term of the Gaussian variance. It sets the width that the "
            "pattern would have at zero angle. Its lower bound is a small positive "
            "variance (1e-8 deg²) and is not 0. Below that clamp the width stops "
            "responding to U, V and W, and the fit stalls. Freeing W together with a "
            "free `gauss_size` fits the same constant twice at low angle."
        ),
        unit="deg² 2θ", default="0.001",
        typical="0.001-0.02 on a laboratory diffractometer",
        anchor="theory/profiles.html#thompson-cox-hastings-pseudo-voigt",
    ),
    "instrument.profile.x": HelpEntry(
        title="Lorentzian X",
        description=(
            "The 1/cosθ term of the Lorentzian FWHM, `Γ_L = X/cosθ + Y·tanθ`. The "
            "1/cosθ shape is Scherrer size broadening. A phase's `lor_size` adds to X, "
            "because Lorentzian FWHMs add under convolution. GSAS and FullProf swap the "
            "X and Y labels. Identify the term by its shape: 1/cosθ is size broadening."
        ),
        unit="deg 2θ", default="0.001",
        typical="0.001-0.05 on a laboratory diffractometer",
        anchor="theory/profiles.html#thompson-cox-hastings-pseudo-voigt",
    ),
    "instrument.profile.y": HelpEntry(
        title="Lorentzian Y",
        description=(
            "The tanθ term of the Lorentzian FWHM. The tanθ shape is microstrain "
            "broadening, and a phase's `lor_strain` adds to it. An anisotropic strain "
            "block replaces the specimen part of this term with an hkl-dependent width "
            "and locks `lor_strain`. The instrumental Y stays as it was. Y can go "
            "negative while X keeps the total width at or above zero."
        ),
        unit="deg 2θ", default="0.0",
        typical="0-0.05 on a laboratory diffractometer",
        anchor="theory/profiles.html#thompson-cox-hastings-pseudo-voigt",
    ),
    # ------------------------------------------------------------------
    # The time-of-flight bank.  Fourteen families, one per field, for the
    # reason the five Caglioti terms are five: each carries its own unit —
    # every coefficient is a polynomial in d, so no two powers of Å agree —
    # and `test_units_are_the_schemas_own` compares an entry's unit against
    # the schema's per path.  All fourteen appear on a `neutron_tof` source
    # and on no other; a constant-wavelength table produces none of them.
    # ------------------------------------------------------------------
    "instrument.source.difc": HelpEntry(
        title="TOF calibration DIFC",
        description=(
            "The linear term of the flight-time relation, `TOF = DIFC·d + DIFA·d² + "
            "TZERO + DIFB/d`. It equals `(m_N/h)(L1 + L2)·2 sin θ_bank`, so it holds "
            "the whole flight path and the bank angle. To leading order d = TOF/DIFC. "
            "It is fixed by default because it is a calibration, refined against a "
            "standard. Freeing it beside a free lattice parameter is the time-of-flight "
            "form of the wavelength-cell degeneracy. Free one of the two and hold the "
            "other."
        ),
        unit="µs/Å", default=None,
        typical="740 µs/Å on an 8.7° bank, 5000-13000 µs/Å at 90-150°",
        anchor="theory/peak-positions.html#time-of-flight",
    ),
    "instrument.source.difa": HelpEntry(
        title="TOF calibration DIFA",
        description=(
            "The quadratic term of the flight-time relation. It is small and often "
            "negative, and zero is a legitimate value on a well-behaved bank. Over a "
            "limited d range it imitates a cell scale better than any other term does. "
            "Refining it beside a free lattice parameter opens a flat direction that a "
            "single bank cannot close. Calibrate it on a standard with the certified "
            "cell held."
        ),
        unit="µs/Å²", default="0.0",
        typical="−20 to +2 µs/Å²; 0 on a bank that never needed one",
        anchor="theory/peak-positions.html#time-of-flight",
    ),
    "instrument.source.tzero": HelpEntry(
        title="TOF calibration TZERO",
        description=(
            "The constant offset of the flight-time relation, in microseconds. It is "
            "the emission-time origin of the moderator. It differs from "
            "`instrument.zero_shift`, an offset in degrees 2θ that a bank's table does "
            "not carry. GSAS ZERO, GSAS-II Zero and Mantid TZERO all name this "
            "quantity. The field uses Mantid's name because no one can mistake it for "
            "the angular offset."
        ),
        unit="µs", default="0.0",
        typical="|TZERO| < 100 µs on a calibrated bank",
        anchor="theory/peak-positions.html#time-of-flight",
    ),
    "instrument.source.difb": HelpEntry(
        title="TOF calibration DIFB",
        description=(
            "The 1/d term of the flight-time relation, GSAS-II's `difB`. Neither the "
            "GSAS manual nor Mantid's documented relation carries it, and it is zero in "
            "most projects. It exists so that a reader built to the three-term relation "
            "cannot drop a non-zero value without notice. Dropping one would move every "
            "peak with nothing said."
        ),
        unit="µs·Å", default="0.0",
        typical="0 on almost every bank",
        anchor="theory/peak-positions.html#time-of-flight",
    ),
    "instrument.source.profile_tof.alpha0": HelpEntry(
        title="TOF rise rate α₀",
        description=(
            "The d-independent part of the rate of the leading exponential, α(d) = α₀ + "
            "α₁/d. It describes the rise of the back-to-back pair, which is the "
            "short-flight-time side of the peak. A larger α gives a sharper leading "
            "edge. The shape has amplitude αβ/(α+β), and its width becomes infinite as "
            "either rate goes to zero. An all-zero block is therefore a profile that "
            "nobody calibrated."
        ),
        unit="µs⁻¹", default="0.0",
        typical="0-1 µs⁻¹; often left at 0 with all of α in α₁",
        anchor="reference/instrument.html#time-of-flight-peak-shape",
    ),
    "instrument.source.profile_tof.alpha1": HelpEntry(
        title="TOF rise rate α₁",
        description=(
            "The 1/d term of the rise rate, and usually the whole of it. GSAS-II spells "
            "this one `alpha`. It enters as α₁/d, so the leading edge sharpens toward "
            "short d. That trend is the moderator pulse seen through the flight-time "
            "map. No specimen effect is involved."
        ),
        unit="Å/µs", default="0.0",
        typical="0.1-2 Å/µs",
        anchor="reference/instrument.html#time-of-flight-peak-shape",
    ),
    "instrument.source.profile_tof.beta0": HelpEntry(
        title="TOF decay rate β₀",
        description=(
            "The d-independent part of the rate of the trailing exponential, β(d) = β₀ "
            "+ β₁/d⁴. Normally β < α, and that makes a time-of-flight peak lean toward "
            "long flight times. The asymmetry comes from the moderator, so it has no "
            "angular analogue in an axial-divergence correction."
        ),
        unit="µs⁻¹", default="0.0",
        typical="0.01-0.2 µs⁻¹",
        anchor="reference/instrument.html#time-of-flight-peak-shape",
    ),
    "instrument.source.profile_tof.beta1": HelpEntry(
        title="TOF decay rate β₁",
        description=(
            "The 1/d⁴ term of the decay rate. The fourth power confines it to the "
            "short-d end of a bank. On a range that does not reach there, the data "
            "cannot see it."
        ),
        unit="Å⁴/µs", default="0.0",
        typical="0-0.05 Å⁴/µs",
        anchor="reference/instrument.html#time-of-flight-peak-shape",
    ),
    "instrument.source.profile_tof.sig0": HelpEntry(
        title="TOF Gaussian variance σ₀²",
        description=(
            "The constant term of the Gaussian variance, σ²(d) = σ₀² + σ₁²·d² + σ₂²·d⁴. "
            "It is a variance and is used as written, so do not square a value read "
            "from a `.iparm` file again. It is the flight-time counterpart of Caglioti "
            "W. Like W, it is the width that the bank would show as its own abscissa "
            "goes to zero."
        ),
        unit="µs²", default="0.0",
        typical="0-500 µs²",
        anchor="reference/instrument.html#time-of-flight-peak-shape",
    ),
    "instrument.source.profile_tof.sig1": HelpEntry(
        title="TOF Gaussian variance σ₁²",
        description=(
            "The d² term of the Gaussian variance, and normally the dominant one. Its "
            "square root, √σ₁², reads directly as µs per Å and is a constant Δd/d. The "
            "resolution of a time-of-flight bank improves (√σ₁² falls) as the bank "
            "angle goes back toward 180°."
        ),
        unit="µs²/Å²", default="0.0",
        typical="100-400 µs²/Å² (√σ₁² ≈ 10-20 µs/Å)",
        anchor="reference/instrument.html#time-of-flight-peak-shape",
    ),
    "instrument.source.profile_tof.sig2": HelpEntry(
        title="TOF Gaussian variance σ₂²",
        description=(
            "The d⁴ term of the Gaussian variance, σ²(d) = σ₀² + σ₁²·d² + σ₂²·d⁴. It is "
            "the instrument's share of a variance that grows as d⁴."
        ),
        unit="µs²/Å⁴", default="0.0",
        typical="0-50 µs²/Å⁴",
        anchor="reference/instrument.html#time-of-flight-peak-shape",
    ),
    "instrument.source.profile_tof.gam0": HelpEntry(
        title="TOF Lorentzian FWHM γ₀",
        description=(
            "The constant term of the Lorentzian FWHM, γ(d) = γ₀ + γ₁·d + γ₂·d². It is "
            "a FWHM, unlike the σ terms beside it, which are variances. With all three "
            "γ terms at zero the profile is pure Gaussian (GSAS type 1)."
        ),
        unit="µs", default="0.0",
        typical="0-20 µs; 0 on a type-1 bank",
        anchor="reference/instrument.html#time-of-flight-peak-shape",
    ),
    "instrument.source.profile_tof.gam1": HelpEntry(
        title="TOF Lorentzian FWHM γ₁",
        description=(
            "The d term of the Lorentzian FWHM. It is GSAS-II's `X` for a TOF bank. "
            "GSAS-II's letters differ from GSAS's. A FWHM linear in d is a constant "
            "Δd/d. Lorentzian strain-like broadening takes that shape on a bank."
        ),
        unit="µs/Å", default="0.0",
        typical="0-30 µs/Å",
        anchor="reference/instrument.html#time-of-flight-peak-shape",
    ),
    "instrument.source.profile_tof.gam2": HelpEntry(
        title="TOF Lorentzian FWHM γ₂",
        description=(
            "The d² term of the Lorentzian FWHM. It is GSAS-II's `Y` for a TOF bank. It "
            "carries the extra curvature of the Lorentzian width across d that γ₀ and "
            "γ₁ together do not follow."
        ),
        unit="µs/Å²", default="0.0",
        typical="0-5 µs/Å²",
        anchor="reference/instrument.html#time-of-flight-peak-shape",
    ),
    "instrument.source.incident_spectrum.p*": HelpEntry(
        title="Incident-spectrum coefficient",
        description=(
            "One coefficient of the moderator spectrum that a time-of-flight bank's "
            "data still carries. The coefficients are numbered P1, P2, … as in the GSAS "
            "manual (p. 128-129). The source's `incident_spectrum.itype`, read from the "
            "ITYP record of the file, says which function they belong to. Type 1 is a "
            "sum of exponentials of the flight time in milliseconds. Type 2 replaces "
            "its second term with a Maxwellian. Types 3-5 are Chebyshev polynomials. "
            "The units differ from coefficient to coefficient. P1 is an intensity, and "
            "the odd ones inside the exponentials are reciprocal powers of "
            "milliseconds, so the family declares no unit. The coefficients are held by "
            "default. GSAS refined the file's values against a vanadium run, and a "
            "smooth envelope in wavelength is degenerate with an isotropic displacement "
            "parameter."
        ),
        unit=None, default=None,
        typical=(
            "Whatever the instrument-parameter file states. A bank whose reduction "
            "already divided by vanadium declares ITYP 0 and has no coefficients at all"
        ),
        anchor="reference/instrument.html#incident-spectrum",
    ),
    "instrument.background.c*": HelpEntry(
        title="Background coefficient",
        description=(
            "One coefficient of the shifted-Chebyshev background, `y_bkg = Σ c_n "
            "T_n(x)`, with x the fitted 2θ range normalised to [−1, 1]. The model is "
            "linear in these coefficients, so their derivatives are the basis functions "
            "themselves, and you can free them from the first stage. Adding terms until "
            "Rwp stops falling is a poor test. A background flexible enough to imitate "
            "the peaks biases displacement parameters up and scales down while Rwp "
            "improves. Read `FitReport.background` instead."
        ),
        unit=None, default="0.0",
        typical="4-8 terms for a flat laboratory background; c0 is of the "
                "order of the observed background counts",
        anchor="theory/background.html#choosing-the-flexibility",
    ),
    "instrument.background.scale": HelpEntry(
        title="Measured-background scale",
        description=(
            "Multiplies the fixed curve that the `fixed_plus_chebyshev` background "
            "holds, `y_bkg = Σ c_n T_n(x) + s·f(2θ)`. In TOPAS terms, `bkg_file(\"f.xy\", "
            "@, s)` refines s and `bkg_file(\"f.xy\")` holds it at 1. The number is "
            "comparable to TOPAS's digit for digit because it scales the curve as "
            "stored. Hold it at 1 for an estimated baseline, which has no scale to get "
            "wrong. Free it for a measured blank. A blank is never on the specimen's "
            "scale, because the two scans differ in monitor normalisation and counting "
            "time, and the specimen attenuates the container's own scattering. The "
            "polynomial on top cannot correct this, because it is additive and the "
            "error is multiplicative. Free the scale only against a low-order "
            "polynomial. Expect `HIGH_CORRELATION` against c0 and read it as an "
            "expected report."
        ),
        unit=None, default="1.0",
        typical="1 for an estimated baseline; within 20-40 % "
                "of 1 for a measured blank",
        anchor="theory/background.html#a-measured-background",
    ),
    "instrument.background.air": HelpEntry(
        title="Air-scatter term",
        description=(
            "Scales an additive 1/(2θ) term for the low-angle air-scatter rise. The "
            "P-spline background carries it beside its spline coefficients. It is "
            "absent unless declared, and `auto_background` declares it only when "
            "`rietx.background.diagnose` reports the rise. The shape is broad, so "
            "freeing it without cause gives the background one more way to imitate a "
            "peak. An absent term has no path, so no plan can free it. A fit whose "
            "residual says the term would have cut χ² reports `AIR_SCATTER_UNDECLARED`."
        ),
        unit=None, default="null",
        typical="absent unless the pattern diagnostics report a low-angle "
                "rise; 1e-3 as a seed where they do",
        anchor="theory/background.html#additive-background-models",
    ),
    "instrument.extra_components.*.position": HelpEntry(
        title="Background-peak position",
        description=(
            "The centre, in °2θ, of an explicit Gaussian background term, such as a "
            "diffuse or amorphous hump or a cryostat or sample-container contribution. "
            "It has no default bounds. It is not a Bragg position, so only the data "
            "constrain it. Set min and max if you know the fitted range. A declared "
            "term is inert (`vary=False`, height 0) until a stage frees it, and nothing "
            "in the package adds one on its own. Freeing position, height and width "
            "together amounts to a reflection with no cell behind it. `HUMP_TOO_NARROW` "
            "flags a fitted width near the instrumental resolution."
        ),
        unit="deg 2θ", default="0.0",
        typical="wherever the diffuse feature sits, for example 14.4 on NIST BT-1",
        anchor="theory/background.html#explicit-humps",
    ),
    "instrument.extra_components.*.height": HelpEntry(
        title="Background-peak height",
        description=(
            "The peak intensity of an explicit Gaussian background term, in the "
            "pattern's count units. Its lower bound is 0, the off state. At height 0 "
            "the term is zero everywhere, so a declared peak that no stage frees gives "
            "the same result, bit for bit, as no peak."
        ),
        unit="counts", default="0.0",
        typical="of the order of the hump's rise above the smooth background",
        anchor="theory/background.html#explicit-humps",
    ),
    # One entry for two members, and it has to be: the dot-path carries the
    # list index, never the `kind`, so no glob can tell a hump's width from a
    # peak's. `fwhm` is the only field name the two share (WP-1103).
    "instrument.extra_components.*.fwhm": HelpEntry(
        title="Extra-component width",
        description=(
            "The full width at half maximum, in °2θ, of a declared extra component. The "
            "two kinds treat it differently. A `hump` comes from disorder, so its width "
            "is many times the instrumental resolution, and that breadth makes it a "
            "background term. A fitted width that approaches the resolution is a "
            "reflection being absorbed, and `HUMP_TOO_NARROW` reports it. A `peak` "
            "stands for a real reflection from something that is not one of your "
            "phases, so a sharp width is the point. No width guard fires for a peak. "
            "Its floor exists only because the profile divides by Γ. Each kind has a "
            "small positive floor, 0.1 for a hump and 0.005 for a peak. The floors come "
            "from the coarsest and the finest scan step that anything can be refined "
            "from."
        ),
        unit="deg 2θ", default="5.0 for a hump, 0.1 for a peak",
        typical="a hump: several times the instrumental FWHM at that angle, ~6 "
                "on the BT-1 case it was measured on. A peak: the instrumental "
                "FWHM itself, since it is a reflection",
        anchor="theory/background.html#explicit-humps",
    ),
    "instrument.extra_components.*.center": HelpEntry(
        title="Extra-peak centre",
        description=(
            "The apparent centre, in °2θ, of a declared sharp peak that your phases "
            "cannot explain, such as a sample holder diffracting at its own specimen "
            "distance, a mount or an unidentified impurity line. It is the position of "
            "the primary emission line. The zero-point shift, the displacement and "
            "transparency shifts and the axial asymmetry are not applied to it. A "
            "holder sits at its own distance and has its own aberrations, and this "
            "parameter absorbs all of them. For the same reason you cannot read a "
            "d-spacing from it. Unlike a hump's position, it needs finite min and max. "
            "The evaluation window is frozen when the stage starts and is sized from "
            "those bounds. That freezing lets the centre refine without leaving its "
            "window. A declared peak is inert (`vary=False`, area 0) until a stage "
            "frees it. Of the presets only `mccusker_structural` frees it, in its "
            "`extra_components` stage. Nothing adds a peak that you did not declare."
        ),
        unit="deg 2θ", default=None,
        typical="where you can see the intruding line, bounded a few tenths "
                "either side",
        anchor="theory/profiles.html#declared-extra-peaks",
    ),
    "instrument.extra_components.*.area": HelpEntry(
        title="Extra-peak area",
        description=(
            "The integrated intensity of a declared sharp peak, in the pattern's count "
            "units times °2θ. It is an area because that is what a reflection intensity "
            "is. The parameter is not called `scale` on purpose. Every `*.scale` path "
            "is force-fixed under Le Bail and Pawley, and a declared peak still has to "
            "refine there. Its lower bound is 0, the off state. At area 0 the term is "
            "zero everywhere, so a declared peak that no stage frees gives the same "
            "result, bit for bit, as no peak. An area that refines to its zero bound "
            "means the data do not see the peak. The centre then reports no esd. That "
            "absence is the evidence that the peak was not needed."
        ),
        unit="counts·deg 2θ", default="0.0",
        typical="the intruding line's integrated counts above the background",
        anchor="theory/profiles.html#declared-extra-peaks",
    ),
    "instrument.extra_components.*.eta": HelpEntry(
        title="Extra-peak mixing",
        description=(
            "The Lorentzian fraction of the pseudo-Voigt of a declared sharp peak. 0 is "
            "a pure Gaussian and 1 is a pure Lorentzian. Both ends are legitimate "
            "values, so the bound is [0, 1] with no floor inside it. The upper bound "
            "also sizes the frozen evaluation window. The half-width at which the "
            "discarded area of the profile stays within tolerance depends steeply on η: "
            "about 1 FWHM at η = 0 and about 16 FWHM at η = 1. If you know the peak is "
            "near-Gaussian, set the maximum of `eta` low and the window shrinks a great "
            "deal."
        ),
        unit=None, default="0.5",
        typical="0.3-0.9 for a lab peak; leave it fixed unless the peak is "
                "strong enough to carry a fourth parameter",
        anchor="theory/profiles.html#declared-extra-peaks",
    ),
    # -- phase -------------------------------------------------------
    "phases.*.cell.a": _CELL_LENGTH,
    "phases.*.cell.b": _CELL_LENGTH,
    "phases.*.cell.c": _CELL_LENGTH,
    "phases.*.cell.alpha": _CELL_ANGLE,
    "phases.*.cell.beta": _CELL_ANGLE,
    "phases.*.cell.gamma": _CELL_ANGLE,
    "phases.*.scale": HelpEntry(
        title="Phase scale",
        description=(
            "The multiplier on this phase's calculated intensity. It is the only route "
            "by which the phase reaches the pattern. Quantitative phase analysis is "
            "computed from it through the Hill-Howard ZMV relation, so it carries the "
            "weight fractions. A scale that refines onto its lower bound means the data "
            "do not see the phase. The fit still reports convergence while the cell of "
            "the phase drifts unconstrained, and `PHASE_UNCONSTRAINED` names that case."
        ),
        unit=None, default="1.0",
        typical="positive, spanning several orders of magnitude between phases",
        anchor="theory/corrections.html#quantitative-phase-analysis-and-microabsorption",
    ),
    "phases.*.extinction": HelpEntry(
        title="Primary extinction",
        description=(
            "The Sabine primary-extinction coefficient, a squared mosaic-block size. A "
            "powder has no secondary extinction. The coefficient attenuates the strong "
            "low-angle reflections of a well-crystallised specimen. At 0 there is no "
            "correction, so a phase that does not free it is unaffected. The calculated "
            "pattern still responds to it at 0, so the staged plans free it from 0 "
            "without a seed."
        ),
        unit="µm²", default="0.0",
        typical="0 for a ground powder; 0.1 to 100 (blocks of 0.3 to 10 µm) "
                "where a strong reflection loses a visible share",
        anchor="theory/corrections.html#primary-extinction",
    ),
    "phases.*.lor_size": HelpEntry(
        title="Lorentzian size broadening",
        description=(
            "The specimen's 1/cosθ contribution to the Lorentzian FWHM. It is Scherrer "
            "broadening from finite crystallite size, and it adds to the instrumental "
            "X. Calibrate the instrument on a standard and hold U, V, W, X and Y. Then "
            "refine this parameter with its three companions, `lor_strain`, "
            "`gauss_size` and `gauss_strain`. The default upper bound is derived from "
            "the fitted 2θ range, since a line cannot be wider than the interval it was "
            "measured over. No default bound limits the crystallite size itself. "
            "`BOUND_HIT` reports the range bound if reached. Setting max to any finite "
            "value is your own claim and switches that default off. A refined size "
            "below 5 nm raises `SIZE_UNUSUALLY_SMALL`. That flag marks the value and "
            "does not bound it."
        ),
        unit="deg 2θ", default="0.0",
        typical="0-0.3 deg; 0.1 deg is roughly a 100 nm domain at Cu Kα",
        anchor="theory/microstructure.html#isotropic-size-and-strain",
    ),
    "phases.*.lor_strain": HelpEntry(
        title="Lorentzian strain broadening",
        description=(
            "The specimen's tanθ contribution to the Lorentzian FWHM. It is isotropic "
            "microstrain broadening, and it adds to the instrumental Y. Declaring a "
            "Stephens anisotropic strain block locks this parameter, because the "
            "isotropic direction of that block equals it. The default upper bound is "
            "derived from the fitted 2θ range, since a line cannot be wider than the "
            "interval it was measured over. It sits two orders of magnitude above any "
            "specimen, and `BOUND_HIT` reports it if reached. Setting max to any finite "
            "value, however large, is your own claim and switches that default off. A "
            "width past 1.5 deg raises `STRAIN_UNUSUALLY_LARGE`. That flag marks the "
            "value and does not bound it."
        ),
        unit="deg 2θ", default="0.0",
        typical="0-0.3 deg",
        anchor="theory/microstructure.html#isotropic-size-and-strain",
    ),
    "phases.*.gauss_size": HelpEntry(
        title="Gaussian size broadening",
        description=(
            "The specimen's 1/cos²θ contribution to the Gaussian variance. Gaussian "
            "variances add, so it stacks on the instrumental U and W and does not "
            "replace them. Most specimens are better described by the Lorentzian pair. "
            "Free this parameter when the peak shape is measurably more Gaussian than "
            "the standard's. It has the same default range bound as `lor_size`, "
            "squared. This parameter is a variance, so the limit on the width it "
            "contributes applies to its square root."
        ),
        unit="deg² 2θ", default="0.0",
        typical="0-0.05 deg²",
        anchor="theory/microstructure.html#isotropic-size-and-strain",
    ),
    "phases.*.gauss_strain": HelpEntry(
        title="Gaussian strain broadening",
        description=(
            "The specimen's tan²θ contribution to the Gaussian variance, stacking on "
            "the instrumental U. Freeing it while U is also free fits one quantity "
            "twice, and the guard reports the correlation. It has the same default "
            "upper bound as `lor_strain`, squared. This parameter is a variance, so the "
            "limit on the width it contributes applies to its square root."
        ),
        unit="deg² 2θ", default="0.0",
        typical="0-0.05 deg²",
        anchor="theory/microstructure.html#isotropic-size-and-strain",
    ),
    "phases.*.magnetic_lor_size": HelpEntry(
        title="Magnetic Lorentzian size broadening",
        description=(
            "Extra 1/cosθ Lorentzian FWHM applied to the magnetic part of this phase's "
            "intensity and to nothing else. The magnetic peaks can therefore be broader "
            "than the nuclear ones. It is Scherrer broadening with the magnetic "
            "coherence length in place of the crystallite size. Antiphase and "
            "domain-wall boundaries, an incompletely grown order parameter near the "
            "Néel temperature and disorder that couples to the exchange all cut the "
            "magnetic coherence below the structural one. Zero is off. Refine it after "
            "the moment, and hold the moment while it settles. Both lower the "
            "calculated peak height, so freed together from a cold start they trade "
            "against each other, and `STAGE_FREES_MAGNETIC_WIDTH_WITH_MOMENT` says so. "
            "Read `MAGNETIC_WIDTH_MOVED_MOMENT` before dropping the term. A width whose "
            "esd exceeds its value can still be correlated with the moment. If "
            "releasing it moved the moment by more than the moment's own error bar, "
            "holding it at zero biases the moment and does not simplify the model. The "
            "width is identifiable only where the magnetic-to-nuclear intensity ratio "
            "differs across reflections. A k ≠ 0 structure with magnetic-only "
            "satellites measures it. A k = 0 collinear structure usually cannot, and "
            "the width then comes back with an esd larger than its value. "
            "`MAGNETIC_WIDTH_UNMEASURED` names that case. The parameter exists only on "
            "a phase that declares `magnetic_symmetry`. It is held fixed wherever no "
            "magnetic component is drawn, which means an X-ray histogram and Le Bail or "
            "Pawley."
        ),
        unit="deg 2θ", default="0.0",
        typical="0-0.3 deg; 0.1 deg is roughly a 100 nm magnetic domain at 2.4 Å",
        anchor="theory/microstructure.html#isotropic-size-and-strain",
    ),
    "phases.*.magnetic_lor_strain": HelpEntry(
        title="Magnetic Lorentzian strain broadening",
        description=(
            "Extra tanθ Lorentzian FWHM applied to the magnetic part of this phase's "
            "intensity alone. It is the strain partner of `magnetic_lor_size`, and a "
            "magnetic order parameter that varies across the specimen produces it. Zero "
            "is off. The same turn-on order applies: refine the moment first, then this "
            "term, then both. The same identifiability limits apply too. It is "
            "measurable only where some reflection is more magnetic than another. On a "
            "real k ≠ 0 dataset this term can carry the effect in place of the size "
            "term. The `magnetic_width` plan therefore frees both and lets the report "
            "say which was measured. The parameter exists only on a phase that declares "
            "`magnetic_symmetry`. It is held fixed on an X-ray histogram and under Le "
            "Bail or Pawley."
        ),
        unit="deg 2θ", default="0.0",
        typical="0-0.3 deg",
        anchor="theory/microstructure.html#isotropic-size-and-strain",
    ),
    "phases.*.preferred_orientation.r": HelpEntry(
        title="March-Dollase coefficient",
        description=(
            "The March-Dollase coefficient for preferred orientation along the declared "
            "hkl axis. At r = 1 there is no correction. Whether a value above or below "
            "1 means platy or needle-like crystallites flips between reflection and "
            "transmission geometry, so read r against the mount and not from the number "
            "alone. The March factor divides by r, so r = 0 is a pole. The default lower "
            "bound of 1e-6 keeps r off it, and there is no default upper bound."
        ),
        unit=None, default="1.0",
        typical="0.6-1.4; a value outside 0.5-2 describes a texture few powder "
                "mounts produce",
        anchor="theory/corrections.html#preferred-orientation-march-dollase",
    ),
    "phases.*.texture.*": HelpEntry(
        title="Texture coefficient",
        description=(
            "One coefficient `C_l^n` of the spherical-harmonics preferred-orientation "
            "correction, named `c<l>_<n>` after GSAS-II's C(l,n). With every "
            "coefficient at 0 there is no correction. The Laue class decides which "
            "coefficients exist. The texture index J = 1 + Σ C²/(2l+1) summarises their "
            "size, and J = 1 is a random powder. A Bragg-Brentano coefficient is "
            "GSAS-II's multiplied by `P_l(0)`, because rietx measures the sample angle "
            "from the plate normal. In -3m1 the metric makes hkl and `khl` coincide "
            "although they are inequivalent. A term of opposite sign on that pair is "
            "then measured only through their |F|² difference, and its esd says so."
        ),
        unit=None, default="0.0",
        typical="|C| under 1 at l = 2 for a lightly textured mount; several "
                "for a strongly platy one",
        anchor="theory/corrections.html#preferred-orientation-spherical-harmonics",
    ),
    "phases.*.atoms.*.x": _ATOM_COORD,
    "phases.*.atoms.*.y": _ATOM_COORD,
    "phases.*.atoms.*.z": _ATOM_COORD,
    "phases.*.atoms.*.dof.*": HelpEntry(
        title="Atom position shift",
        description=(
            "One direction in which an atom on its Wyckoff site is free to move. "
            "GSAS-II and FullProf refine x, y and z under constraints that hold an atom "
            "on its special position. rietx refines only the directions that the site "
            "symmetry leaves free, so the site symmetry holds exactly. The coordinates "
            "x, y and z are tied to these directions. Each value is a step from where "
            "the fit began. A site with no free direction produces no `dof` entry, and "
            "its coordinates are locked. Free these parameters with "
            "`phases.*.atoms.*.dof.*`. In a polar space group, `Phase.floating_origin = "
            "\"hold\"` holds, for each direction in which the origin floats, the first "
            "atom shift along it that moves the origin, and the row says so. "
            "`\"centroid\"` holds nothing and restrains a data-weighted centroid of the "
            "sites instead, so every shift keeps an esd."
        ),
        unit=None, default=None,
        typical="0 to 1, in the same units as the coordinate it drives",
        anchor="theory/parameterisation.html#site-symmetry-degrees-of-freedom",
    ),
    "phases.*.rigid_bodies.*.origin.x": _BODY_ORIGIN,
    "phases.*.rigid_bodies.*.origin.y": _BODY_ORIGIN,
    "phases.*.rigid_bodies.*.origin.z": _BODY_ORIGIN,
    "phases.*.rigid_bodies.*.origin.dof.*": HelpEntry(
        title="Rigid-body origin shift",
        description=(
            "One direction in which a rigid body's origin is free to move, as for an "
            "atom on its site. The body translates as one, and the coordinates of every "
            "member atom follow. Each value is a step from where the fit began, as for "
            "an atom's position shift."
        ),
        unit=None, default=None,
        typical="a few hundredths, in the units of the coordinate it drives",
        anchor="theory/parameterisation.html#rigid-bodies",
    ),
    "phases.*.rigid_bodies.*.rotation.*": HelpEntry(
        title="Rigid-body rotation step",
        description=(
            "One component of the rotation vector, in radians, that turns a rigid body "
            "about its origin from the orientation it had at the start of the fit. The "
            "three components together give the rotation Exp(δω), applied to the stored "
            "orientation. All three are zero at the start of every fit. When the fit is "
            "written back, the rotation is composed into the body's stored quaternion. "
            "Each component is bounded to ±π."
        ),
        unit=None, default=None,
        typical="under 0.5 rad from a sensible start",
        anchor="theory/parameterisation.html#rigid-bodies",
    ),
    "phases.*.rigid_bodies.*.torsions.*.twist": HelpEntry(
        title="Rigid-body torsion step",
        description=(
            "The turn, in degrees, of a body's declared moving atoms about the line "
            "through its two axis atoms, measured from the stored angle of the torsion. "
            "A dihedral a–axis[0]–axis[1]–d whose d end is a moved atom changes by the "
            "same amount. One whose a end is moved changes by minus that amount. The "
            "value is zero at the start of every fit. At every stage's commit it is "
            "added into the stored angle of the torsion, wrapped into (−180, 180]."
        ),
        unit=None, default=None,
        typical="a few degrees to a few tens of degrees from a sensible start",
        anchor="theory/parameterisation.html#rigid-bodies",
    ),
    "phases.*.distortion_modes.modes.*.amplitude": HelpEntry(
        title="Distortion-mode amplitude",
        description=(
            "The amplitude, in Å, of one symmetry-adapted displacive mode of a child "
            "stated as its parent plus a distortion (the phase's `distortion_modes` record, "
            "built by "
            "`displacive_statement`). The atoms the mode moves sit at their base "
            "positions plus the sum of amplitude times mode vector over all modes, so the "
            "amplitude is absolute and those atoms have no coordinate parameters of their "
            "own. Unit: AMPLIMODES's, the mode normalised over a primitive cell of the "
            "child in the parent metric before any strain. The sign of the driving mode is a "
            "domain label; relative signs inside a basis are measured (Perez-Mato et al. "
            "2010, § 7). At the parent every amplitude outside the "
            "identity irrep has an exactly zero gradient, so a block freed there is "
            "refused: start from the statement's seed."
        ),
        unit="Å", default=None,
        typical="0 to about 1.5 Å for an octahedral tilt",
        anchor="theory/parameterisation.html#distortion-mode-amplitudes",
    ),
    "phases.*.atoms.*.occ": HelpEntry(
        title="Site occupancy",
        description=(
            "The fraction of the site occupied by this species. It is close to "
            "degenerate with the displacement parameter of the site, because both "
            "reduce the scattered intensity. X-rays have little power to separate the "
            "two. Refine one or the other unless the data reach high Q. Constrain "
            "occupancies that must sum to 1 with a user tie. The default lower bound "
            "is 0, and there is no default upper bound. A refined value above 1 raises "
            "`OCCUPANCY_ABOVE_ONE`."
        ),
        unit=None, default="1.0",
        typical="0 to 1; above 1 when a mixed site declared as its lighter species "
                "refines site scattering",
        anchor="theory/intensities.html#the-structure-factor",
    ),
    "phases.*.atoms.*.biso": HelpEntry(
        title="Isotropic displacement parameter",
        description=(
            "The isotropic B of the atom, related to the mean-square displacement by B "
            "= 8π²·Uiso. It damps intensity as exp(−B·sin²θ/λ²), so the high-angle data "
            "determine it, and a too-flexible background biases it first. A negative B "
            "is unphysical. A refined B above about 5 Å² for a heavy atom usually "
            "points to an absorption or background error and not to a real "
            "displacement. There is no default bound. A negative B reports "
            "`BISO_NEGATIVE`, and one past the melting estimate of the phase reports "
            "`BISO_UNUSUALLY_LARGE`. A stage holds B where the fitted range cannot "
            "separate it from the scale of the phase (`SCALE_B_INSEPARABLE`). Give the "
            "parameter a min or max to bound it yourself."
        ),
        unit="Å²", default="0.5",
        typical="0.2-2 Å² for an inorganic framework at room temperature",
        anchor="theory/intensities.html#debye-waller-factors-and-adp-representations",
    ),
    "phases.*.atoms.*.u11": _ATOM_ANISO_U,
    "phases.*.atoms.*.u22": _ATOM_ANISO_U,
    "phases.*.atoms.*.u33": _ATOM_ANISO_U,
    "phases.*.atoms.*.u12": _ATOM_ANISO_U,
    "phases.*.atoms.*.u13": _ATOM_ANISO_U,
    "phases.*.atoms.*.u23": _ATOM_ANISO_U,
    "phases.*.atoms.*.adp.*": HelpEntry(
        title="Anisotropic displacement parameter",
        description=(
            "One allowed component of the anisotropic displacement tensor on this "
            "Wyckoff site. Unlike an atom's position shift, it is absolute. The tensor "
            "is the sum of the refined values times basis tensors that the site "
            "symmetry allows, so the site symmetry holds exactly. Positive-definiteness "
            "couples all six components, so it cannot be a bound. A tensor that loses "
            "it raises `ADP_NOT_POSITIVE_DEFINITE`, because the Debye-Waller factor "
            "then diverges at high Q. Free these parameters with "
            "`phases.*.atoms.*.adp.*`, alongside the `biso` pattern that every "
            "displacement stage carries."
        ),
        unit="Å²", default=None,
        typical="0.005-0.05 Å²",
        anchor="theory/intensities.html#debye-waller-factors-and-adp-representations",
    ),
    "phases.*.atoms.*.moment.crystalaxis_*": HelpEntry(
        title="Magnetic moment component",
        description=(
            "One crystal-axis component of this site's magnetic moment, in the magCIF "
            "`_atom_site_moment.crystalaxis_*` convention. The basis is right-handed, "
            "with unit vectors along the cell axes. On hexagonal axes the moment (1, 1, "
            "0) is therefore 1 μB and not √2 μB. rietx derives these three components. "
            "The moment enters the fit as `phases.*.atoms.*.moment.dof*`, a modulus and "
            "the angles that the site symmetry leaves free, and the components are "
            "written back from those at the end of a stage. They carry no esd. The esd "
            "of the magnitude is on the modulus entry."
        ),
        unit="μ_B", default=None,
        typical="1-5 μB for a 3d ion, up to 10 μB for a rare earth",
        anchor="theory/intensities.html#the-magnetic-structure-factor",
    ),
    "phases.*.atoms.*.moment.dof*": HelpEntry(
        title="Magnetic moment parameter",
        description=(
            "`dof0` is the modulus of the moment in μB. A fit measures it, and it "
            "carries the esd. Any further entries are angles in radians inside the "
            "subspace that the magnetic symmetry of the site allows. There is one angle "
            "on a two-dimensional subspace and two on a three-dimensional one. A powder "
            "average determines |m| and, on a uniaxial structure, the angle to the "
            "unique axis. It determines no more. The directions it cannot determine are "
            "held and named in `StageResult.held`, and they are not returned as small "
            "numbers. Where the unique axis is not the pole of the frame (rhombohedral "
            "axes, about [111]), the fit first turns the moment about that axis. That "
            "changes the reported direction. The axis and the turn are recorded in "
            "`StageResult.moment_flat_axes` and `StageResult.moment_turned`. Seeding "
            "the modulus at exactly zero is refused, because the magnetic structure "
            "factor squared is proportional to m² and the derivative is zero there."
        ),
        unit=None, default=None,
        typical=(
            "1-5 μB for the modulus. The angles are unbounded while a stage solves. "
            "They are reported with μ ≥ 0, the polar angle in [0, π] and the azimuth in "
            "(−π, π]"
        ),
        anchor="theory/parameterisation.html#moment-degrees-of-freedom",
    ),
    "phases.*.microstrain.s*": _STEPHENS_S,
    "phases.*.microstrain.dof.*": HelpEntry(
        title="Stephens strain parameter",
        description=(
            "One allowed direction of the Laue-permitted `S_HKL` subspace, derived from "
            "the space-group operators. These are the quantities that refine, and the "
            "fifteen `s` coefficients are tied to them. Seed an all-zero block onto the "
            "isotropic limit with `Stage.strain_seed`, because at S = 0 the square root "
            "in the width has unbounded slope. Positivity of σ²(M) couples all fifteen "
            "coefficients as a cone, so it cannot be a bound on each coefficient. The "
            "default Levenberg-Marquardt solver holds it as a linear inequality. Under "
            "`solver=\"trf\"` and in a joint fit, `STEPHENS_STRAIN_NOT_POSITIVE` reports "
            "it instead. Read that flag as 'these coefficients are not quotable'. It is "
            "no evidence of anisotropy."
        ),
        unit=None, default=None,
        typical="the isotropic seed is ε²·[M²] for a strain ε of 1e-4 to 1e-3",
        anchor="theory/microstructure.html#the-positivity-cone-the-seed-and-the-guard",
    ),
    # A caller's own parameter, outside the model tree (WP-1981).
    "vars.*": HelpEntry(
        title="Named variable",
        description=(
            "A parameter of your own, declared with `Refinement.add_variable` and "
            "addressed as `vars.<name>`. It corresponds to the `prm` of TOPAS. Model "
            "parameters follow it through ties, so a constraint can name a shared "
            "quantity and need not pick one parameter as the master. The diffraction "
            "model reads no variable directly. A variable reaches the pattern only "
            "through the parameters tied to it. Its unit and bounds are the ones it was "
            "declared with. Declared with the bounds of the parameter it replaces, it "
            "gives the same answer. Declared without them, it can go where that "
            "parameter could not."
        ),
        unit=None, default=None,
        typical="the range of the parameters it drives",
        anchor="guides/tie.html#tie-to-a-quantity-of-your-own",
    ),
}


# ----------------------------------------------------------------------
# Named arms
#
# Each is keyed by a member of a closed vocabulary the package already owns,
# and `tests/test_help.py` crosses the keys against that vocabulary in both
# directions.  Entries carry no `unit` or `default`: these name states and
# settings, not measured quantities, except where a setting has a schema
# default, which is pinned like a parameter's.
# ----------------------------------------------------------------------

#: One entry per ``schemas.indexing.PeakFlag`` member.  A flag says what is
#: known about a fitted line; whether the line is still evidence for a lattice
#: is ``PEAK_UNUSABLE_FLAGS``, which the peaks route serves beside the
#: vocabulary rather than leaving a client to re-derive.
PEAK_FLAG_HELP: dict[str, HelpEntry] = {
    "position_unmeasured": HelpEntry(
        title="Position never determined",
        label="no position",
        description=(
            "The fit gave this line's position an uncertainty of 180° or more, the "
            "whole span of a 2θ axis. That is no position at all, and any window built "
            "from it matches whatever it is compared with. The line stays in the list "
            "so a report can say why it went. It is excluded from everything that "
            "matches positions."
        ),
        anchor="theory/peak-positions.html#wavelength-scales",
    ),
    "ghost_kbeta": HelpEntry(
        title="Kβ line of a stronger reflection",
        label="Kβ ghost",
        description=(
            "The line sits where the Kβ partner of a stronger reflection would be, and "
            "several other strong reflections carry a partner at the same intensity "
            "ratio. That agreement is the evidence. A single line at a predicted "
            "position is a coincidence and is not flagged. The line is excluded and "
            "Rachinger stripping is not applied, because stripping redistributes the "
            "counting noise and biases what is left. The line is unusable as evidence "
            "of a lattice."
        ),
        anchor="theory/peak-positions.html#wavelength-scales",
    ),
    "ghost_tungsten": HelpEntry(
        title="Tungsten L line from the tube",
        label="W ghost",
        description=(
            "The line sits at a tungsten L emission position, which an aged tube with a "
            "contaminated anode produces. Such lines are flagged jointly, as Kβ lines "
            "are, and excluded for the same reasons. The line is unusable."
        ),
        anchor="theory/peak-positions.html#wavelength-scales",
    ),
    "excluded": HelpEntry(
        title="Removed by hand",
        label="excluded",
        description=(
            "Someone removed this line by hand. It stays in the list so a report can "
            "say the line was seen and dropped. It is not offered as evidence."
        ),
    ),
    "fit_failed": HelpEntry(
        title="Group fit did not converge",
        label="fit failed",
        description=(
            "The fit over this line's group of peaks did not converge. The position and "
            "σ on the row are the starting values from peak detection, so they measure "
            "nothing. The line is unusable."
        ),
    ),
    "sigma_assumed": HelpEntry(
        title="Position uncertainty assumed",
        label="σ assumed",
        description=(
            "The position uncertainty was supplied and not measured. This happens to a "
            "list read from a publication or from another program. The line is still "
            "evidence, and its σ says how good it is, so it stays usable. Treat the "
            "precision as unknown and do not quote it."
        ),
    ),
    "unresolved_shoulder": HelpEntry(
        title="Never separated from its neighbour",
        label="shoulder",
        description=(
            "The component was kept in a group where it never moved half a FWHM away "
            "from its neighbour. It is weaker evidence than a resolved line but still "
            "evidence, so it stays usable."
        ),
    ),
    "position_at_bound": HelpEntry(
        title="Position refined to its limit",
        label="at bound",
        description=(
            "The fitted position reached the limit on how far it could move from its "
            "starting value. That means peak detection put the starting value in the "
            "wrong place. The reported position is the limit itself, and the fit did "
            "not find a minimum there."
        ),
    ),
    "asymmetry_unmodelled": HelpEntry(
        title="Asymmetry the peak shape cannot fit",
        label="asymmetric",
        description=(
            "The residual over this line is asymmetric beyond what the fitted peak "
            "shape allows, so the position is biased towards the tail. Axial divergence "
            "at low 2θ is the usual cause."
        ),
        anchor="theory/profiles.html#finger-cox-jephcoat-axial-divergence",
    ),
    "not_separable": HelpEntry(
        title="Improves the fit as a shape only",
        label="not separable",
        description=(
            "The component improves the fit of its group, but the fit without it cannot "
            "be ruled out, so there is no evidence of a distinct reflection. It stays "
            "in the model because removing it would bias the position of the line it "
            "sits on. It is never offered to an indexing engine."
        ),
    ),
    "background_extrapolated": HelpEntry(
        title="Standing on extrapolated background",
        label="bkg extrapolated",
        description=(
            "The line's prominence is measured against a background level that was "
            "extrapolated and not observed. The intensity is real but may not belong to "
            "a line. The line stays usable, so you can weigh the evidence yourself."
        ),
        anchor="theory/background.html#model-free-estimation",
    ),
    "axial_tail": HelpEntry(
        title="Possibly a stronger line's axial tail",
        label="axial tail",
        description=(
            "A weak component lies within 3.5 fitted FWHM (`PEAK_AXIAL_TAIL_MAX_FWHM`) "
            "of a stronger component in its group, on the side that axial divergence "
            "points to. That side is low 2θ below 90° and high 2θ above it. The screen "
            "looks on one side only, because nothing else in a powder pattern flips "
            "sign at 90°. The line stays usable, since a real line can coincide with a "
            "tail."
        ),
        anchor="theory/profiles.html#finger-cox-jephcoat-axial-divergence",
    ),
    "kalpha2_residual": HelpEntry(
        title="Sitting on a modelled Kα2 maximum",
        label="Kα2 residual",
        description=(
            "The component sits at the Kα2 position of a stronger component in its "
            "group. The position is predicted from the declared doublet splitting as "
            "δ(2θ) = 2·(λ₂/λ₁ − 1)·tanθ and is not found by a distance threshold. It is "
            "the residual of a doublet that the model already carries. The line stays "
            "usable, since a real line can coincide with it."
        ),
        anchor="theory/peak-positions.html#wavelength-scales",
    ),
    "unnamed_neighbour": HelpEntry(
        title="An unnamed component shares this window",
        label="unnamed neighbour",
        description=(
            "You named the components in this window, and peak detection found another "
            "that you did not name. Its intensity went into the components you fitted, "
            "so their positions are biased towards it. Reduced χ² is the only other "
            "sign. The line stays usable, because naming a subset is a legitimate "
            "request and the esd inflation by the square root of reduced χ² already "
            "carries the cost. Name the neighbour too, or narrow the range, if the "
            "position matters."
        ),
    ),
    "no_intensity": HelpEntry(
        title="Refined to zero intensity",
        label="no intensity",
        description=(
            "The component reached its zero-intensity bound, or its fitted intensity is "
            "smaller than its own esd. It contributes nothing measurable to the window, "
            "and its position cannot be identified, because a peak reaches the data "
            "only through intensity times profile. The line is unusable. Unlike the "
            "flags that leave a line usable, there is no judgement left to make."
        ),
    ),
    "duplicate_line": HelpEntry(
        title="Line another group already fitted",
        label="duplicate",
        description=(
            "This component sits on a line that a neighbouring group fitted with a "
            "better-measured component, so it is one physical peak fitted twice. The "
            "copy stays in the list because it let its own group's window fit. It is "
            "unusable, because a list that offers one line twice gives a second line "
            "that no candidate cell explains."
        ),
    ),
    "weak_line": HelpEntry(
        title="Below the false-discovery bar",
        label="weak",
        description=(
            "The component's fitted intensity over its esd is below the bar set by the "
            "pattern's own false-discovery rate (Benjamini-Hochberg at q = 0.01, "
            "`PEAK_FDR_Q`, over the pattern's resolution elements). The list cannot "
            "tell such a line from noise at the rate it promises for every other line. "
            "It stays usable, because on real laboratory data many such lines are weak "
            "reflections that the true cell indexes. The flag is evidence to weigh and "
            "is no verdict. A search is never driven by it, though: the line is scored "
            "like any usable one, but an accepted cell need not index it. A line you "
            "placed by hand is never tested."
        ),
    ),
    "residue_misfit": HelpEntry(
        title="Standing on the subtracted phase",
        label="misfit",
        description=(
            "Written only by `index_residue`. This pick in the residue stands on more of "
            "the subtracted first phase's profile than its own height, so it is as likely "
            "the first cell's misfit as a line of a second phase. It stays usable, so the "
            "second result counts it as a line no candidate explains and grades "
            "accordingly, but it never drives the search. The height rule separates the misfit from true lines on two 11-BM mixtures; on the IUCr CPD lab mixtures it flags about 6 % of true minor-phase lines and misses 15 % of the misfit."
        ),
    ),
    "unresolved_split": HelpEntry(
        title="Split the data cannot resolve",
        label="split",
        description=(
            "This component sits closer to a comparable neighbour in its group than two "
            "lines of the fitted shape can and still show a dip between them. The data "
            "tell the pair apart only through the peak shape, so the pair is reported "
            "as one line. That line is the stronger component, with its position "
            "uncertainty widened to reach this one. This component stays in the list "
            "and is unusable."
        ),
    ),
    "width_capped": HelpEntry(
        title="Width ran into its bound",
        label="too wide",
        description=(
            "The fit tried to make this group broader than the limit of five times the "
            "pattern's own width law at that angle (`PEAK_WIDTH_BOUND_FACTORS`). It is "
            "a hump, such as background that the envelope did not follow, and is not a "
            "line of the phase that set the width law. It stays in the list and is "
            "unusable."
        ),
    ),
}

#: One entry per value of :attr:`~rietx.schemas.indexing.ObservedPeak.origin`
#: (WP-1209).  Provenance, not a judgement — the schema's own words — and the
#: GUI draws a chip for the two that mean a person acted, so each carries a
#: ``label``.
PEAK_ORIGIN_HELP: dict[str, HelpEntry] = {
    "fitted": HelpEntry(
        title="Found by peak detection",
        label="fitted",
        description=(
            "Peak detection found a maximum or a shoulder here and the group fit kept "
            "it. Nobody has touched the line. Its position, width and area come from "
            "the fit, and so do its flags."
        ),
    ),
    "manual": HelpEntry(
        title="Placed by a person",
        label="manual",
        description=(
            "Someone added this line from the plot or by typing a 2θ. Its position was "
            "still fitted, within the group it landed in. A person decided that a line "
            "exists here, so the peak picker's own screens never remove it."
        ),
    ),
    "edited": HelpEntry(
        title="Moved by a person",
        label="moved",
        description=(
            "Peak detection proposed this line, and a person dragged it or typed a new "
            "2θ. The group was refitted from the new starting position. The position "
            "shown comes from the refit and can differ from where you put the line."
        ),
    ),
}

#: One entry per diagnostic code the package raises: what the code means and
#: why it fires, written once per code and never once per finding (WP-1985).
#: A :class:`~rietx.schemas.common.Diagnostic` carries the observation and the
#: action for its own case, and reads this entry as its ``explanation``.
#: ``tests/test_help.py`` holds the keys equal to the codes the source tree
#: raises, read by ``docs/reference_pages.diagnostic_index``.  A ``PEAK_*``
#: code is about the peak *list*, where a ``PeakFlag`` is a fact about one
#: line; several are the list-level summary of a flag.
DIAGNOSTIC_HELP: dict[str, HelpEntry] = {
    "ABSORPTION_ESTIMATE_UNAVAILABLE": HelpEntry(
        title="No absorption correction was applied",
        description=(
            "You gave a specimen radius or thickness, but the package could not estimate "
            "the absorption from it. The fit ran with no absorption correction. "
            "Absorption trades against the scale and the displacement parameters, so "
            "they carry its error. Supply the absorption product yourself, measured or "
            "computed by hand for this specimen."
        ),
    ),
    "ABSORPTION_MU_R_OUT_OF_RANGE": HelpEntry(
        title="Capillary absorption is beyond the fitted range",
        description=(
            "The estimated absorption of the capillary lies beyond the range of the "
            "published fit used to correct it. The correction is then an extrapolation, "
            "so its size is unreliable. Absorption trades against the displacement "
            "parameters, so they carry the error. A more dilute specimen, a narrower "
            "capillary or a shorter wavelength brings the value back into range."
        ),
    ),
    "ABSORPTION_PLATE_THICKNESS": HelpEntry(
        title="Transmission plate far from its best thickness",
        description=(
            "A transmission plate gives the most counts at one thickness, set by its "
            "absorption. This plate is well away from it, so the pattern holds fewer "
            "counts than the specimen could give. The fit is still valid. A plate closer "
            "to the best thickness gives better statistics on the next measurement."
        ),
    ),
    "ABSORPTION_THICKNESS_MATTERS": HelpEntry(
        title="Specimen thickness shifts the displacement parameters",
        description=(
            "For a flat specimen the absorption correction depends on the thickness you "
            "declared. Part of it cannot be absorbed by the scale and the displacement "
            "parameters. An error in the thickness or the packing density therefore "
            "lands in the fit and in those parameters. The thickness is not refined, so "
            "measure it."
        ),
    ),
    "ADP_NOT_POSITIVE_DEFINITE": HelpEntry(
        title="An anisotropic displacement tensor is not an ellipsoid",
        description=(
            "A refined anisotropic displacement tensor has a negative eigenvalue, so it "
            "does not describe an ellipsoid. The Debye-Waller factor then grows without "
            "limit at high angle. The data usually do not support that many displacement "
            "parameters on the site. Return the site to an isotropic value, or check its "
            "occupancy and species, before you quote the tensor."
        ),
    ),
    "AIR_SCATTER_UNDECLARED": HelpEntry(
        title="Background lacks an air-scatter term",
        description=(
            "The spline background declares no term for air scatter. Air scatter adds "
            "intensity that rises towards low angle. A refit with the term would remove "
            "a measurable share of the misfit with the Bragg model held. Without it, the "
            "background can bias the peak intensities at low angle. Declare the term and "
            "refit. If the rise is not air scatter, raise the lower limit of the "
            "pattern."
        ),
    ),
    "BACKGROUND_ABSORPTION": HelpEntry(
        title="The background can imitate a refined parameter",
        description=(
            "The background is flexible enough to reproduce most of the effect of a "
            "structural parameter, such as a scale or a displacement parameter. The fit "
            "can then trade intensity between them, and Rwp still improves. The scales, "
            "displacement parameters and phase fractions come out biased. Stiffen the "
            "background, or hold an estimated curve fixed."
        ),
    ),
    "BACKGROUND_ORDER_AT_CAP": HelpEntry(
        title="Background order stopped at its limit",
        description=(
            "The scan for the Chebyshev order reached its largest allowed order. The "
            "residual in the peak-free channels was still serially correlated, so the "
            "data did not choose the order. Raising the limit does not help, because a "
            "peak-shape misfit leaks into those channels at every order. Check whether "
            "the background absorbs peak intensity, or switch to the penalised spline "
            "background."
        ),
    ),
    "BISO_NEGATIVE": HelpEntry(
        title="A displacement parameter is negative",
        description=(
            "A refined isotropic displacement parameter is below zero. No real vibration "
            "does that, because the Debye-Waller factor would grow with angle instead of "
            "falling. The parameter is absorbing something else. Likely causes are "
            "uncorrected absorption or roughness, a wrong species or occupancy, or a "
            "background that bends at high angle. Correct that cause, or hold the "
            "parameter at a physical value."
        ),
    ),
    "BISO_UNUSUALLY_LARGE": HelpEntry(
        title="A displacement parameter is implausibly large",
        description=(
            "A refined isotropic displacement parameter exceeds the amplitude at which a "
            "solid with this cell would melt. That usually points at the model. A wrong "
            "species or occupancy, a missing absorption correction or a background that "
            "has taken high-angle intensity can all inflate it. A mobile site, such as a "
            "cavity cation, can be genuinely this large. Check the model before you read "
            "the value as motion."
        ),
    ),
    "BOUND_HIT": HelpEntry(
        title="A parameter finished on a limit",
        description=(
            "The refined value finished on its minimum or maximum, and the data were "
            "pushing it further. The number is the limit you set, so it is not a "
            "measurement. Look for a correlated parameter or a tie that drives it there "
            "before you widen the limit."
        ),
    ),
    "BRINDLEY_OUTSIDE_REGIME": HelpEntry(
        title="Particle absorption correction out of range",
        description=(
            "A phase absorbs too strongly for the Brindley correction. The correction is "
            "derived for fine to medium powders. Outside that range the corrected "
            "fractions can sit further from the truth than the uncorrected ones, while "
            "looking more authoritative. Grind the sample finer or use a shorter "
            "wavelength. Otherwise quote the uncorrected fractions and name "
            "microabsorption as a systematic error of unknown size."
        ),
    ),
    "BRML_ABSORBER_ENGAGED": HelpEntry(
        title="An automatic absorber was in the beam",
        description=(
            "The instrument inserted an absorber over some points. The stored "
            "intensities already include the correction, so the reader left them alone. "
            "It did carry the factor into the esds, because the counted quantity is the "
            "intensity before the correction. Nothing needs fixing, but those points "
            "rest on fewer counts than their height suggests."
        ),
    ),
    "CAPILLARY_OFFSET_UNAVAILABLE": HelpEntry(
        title="Capillary offset aberrations are held at zero",
        description=(
            "The capillary geometry has no goniometer radius, so the specimen-offset "
            "aberrations cannot be modelled and are held at zero. Zero here is an "
            "assumption and not a measurement. An unmodelled offset moves every axis of "
            "the cell by the same fraction. A ratio of axes can look accurate while the "
            "axes are not. On a calibrated synchrotron the cost is small. Give the "
            "radius if you know it."
        ),
    ),
    "CELL_DEGENERATE_PROBE": HelpEntry(
        title="The search tried a cell with no volume",
        description=(
            "During the cell search the optimiser tried trial cells with zero or "
            "negative volume. Each trial was rejected and answered with a large "
            "residual, so none entered the reported values. It happens when the data "
            "barely determine a cell stage. The reported values are unaffected. Many "
            "such trials suggest that the data barely constrain the cell."
        ),
    ),
    "CELL_RUNAWAY": HelpEntry(
        title="A cell parameter ran away during the fit",
        description=(
            "A free cell parameter left its safety window around the starting cell while "
            "the solver worked. It is usually degenerate with another free cell or "
            "parameter. The phase's cell was put back to its value at the start of the "
            "stage and held while the stage solved again, so the value is not a "
            "measurement. When this happens in the final stage, that cell and the "
            "parameters tied to it carry no esd. Fix one phase's cell, hold the other "
            "phase, or free the cell in a stage of its own."
        ),
    ),
    "CHILD_GROUP_UNNAMED": HelpEntry(
        title="Child cell group has no standard symbol",
        description=(
            "No Hermann-Mauguin symbol generates the group of the magnetic supercell in "
            "this cell choice. The phase carries its symmetry operations directly, under "
            "a bracketed label that names the closest group type. The statement is "
            "complete. The leading symbol of the label generates a different group, so "
            "check the cell transform before you compare it with a published symbol."
        ),
    ),
    "CIF_CELL_ANGLE_CORRECTED": HelpEntry(
        title="Lattice angle set to its symmetry value",
        description=(
            "The file stores an angle that its space group fixes, and the stored value "
            "differs slightly from the fixed one. The reader used the exact value, "
            "because a cell that contradicts its symmetry cannot be refined. The "
            "deviation may be real. If it is, the symmetry is lower than the symbol "
            "claims, and the phase needs a space group that leaves this angle free."
        ),
    ),
    "CIF_MAGNETIC_CENTERING_ASSUMED": HelpEntry(
        title="Magnetic centring loop missing",
        description=(
            "The file lists no magnetic centring translations, so the group is read as "
            "its operation list with no centring. A forgotten anti-centring (a "
            "translation combined with time reversal) would make this a different and "
            "smaller magnetic group. The moments would then refine under the wrong "
            "symmetry. Add the centring loop if the group has one."
        ),
    ),
    "CIF_MAGNETIC_ION_UNCHARGED": HelpEntry(
        title="Magnetic ion has no charge stated",
        description=(
            "A magnetic CIF has no item for the magnetic ion, and the type symbol of "
            "this site gives no oxidation state. The form factor therefore comes from "
            "the neutral atom. Neutral and ionic form factors differ, so a moment "
            "refined under the wrong one absorbs the difference into its size. State the "
            "ion for the site to use the one your chemistry implies."
        ),
    ),
    "CIF_MAGNETIC_MAGNITUDE_ESD_NOT_STORED": HelpEntry(
        title="Moment uncertainty not carried",
        description=(
            "The file gives a standard uncertainty for the size of a moment. A structure "
            "has no field for it, so the reader does not store it. The uncertainty "
            "belongs to the fit that produced it. A refinement of this structure reports "
            "its own with the magnetic results and writes it back to this item when it "
            "exports a CIF."
        ),
    ),
    "CIF_MAGNETIC_MOMENT_ON_ALLOWED": HelpEntry(
        title="Moment moved onto its symmetry-allowed form",
        description=(
            "The file prints a moment with fewer decimals than the symmetry relation "
            "between its components needs. The printed values then sit slightly off the "
            "form that the site symmetry allows. The reader moved the moment to the "
            "nearest allowed point within the printed precision. The change is no larger "
            "than the rounding in the file. A larger disagreement is refused."
        ),
    ),
    "CIF_MAGNETIC_NUCLEAR_GROUP": HelpEntry(
        title="Positions refine under the parent group",
        description=(
            "The atom positions refine under the parent nuclear group that the file "
            "names. That group contains the file's magnetic operators and gives every "
            "listed site the same orbit. The moments refine under the magnetic group. "
            "Where the parent is larger than the file's own group, the positions carry "
            "constraints that the file's operators do not impose. Check this where a "
            "structural distortion accompanies the magnetic order."
        ),
    ),
    "CIF_MAGNETIC_NUCLEAR_SETTING": HelpEntry(
        title="Positions refine under the file's own group",
        description=(
            "The parent group named by the file cannot carry the file's atoms. The "
            "positions refine instead under the group that the magnetic operators imply "
            "once time reversal is dropped. Common causes are an origin or axis choice "
            "that differs from the tabulated one, and a magnetic group that splits one "
            "parent site into two. The phase may carry its operations directly, so its "
            "symbol can differ from the one in the file."
        ),
    ),
    "CIF_MAGNETIC_NUMBER_MISMATCH": HelpEntry(
        title="Magnetic group number contradicts the operators",
        description=(
            "The group number stated in the file names a different magnetic group from "
            "the one that the file's operator lists make. The operators are what is "
            "refined, so their numbers are stored and the stated name is dropped. Either "
            "side can be wrong. A typing error in the number leaves the operators right. "
            "A missing centring translation makes the operators a smaller group, and the "
            "moments then refine under the wrong symmetry. Check the loops against the "
            "source."
        ),
    ),
    "CIF_MAGNETIC_PARENT_TAG_UNDEFINED": HelpEntry(
        title="Parent space group read from an undefined tag",
        description=(
            "The file names its parent space group under "
            "_parent_space_group.name_H-M, as FullProf writes it. The magnetic CIF "
            "dictionary defines only _parent_space_group.name_H-M_alt, and the "
            "undefined tag can mean nothing else, so the symbol was read from it. The "
            "phase is the one the dictionary's tag would have given. A file that states "
            "both tags with different groups is refused, because nothing in it says "
            "which one is wrong."
        ),
    ),
    "CIF_MAGNETIC_SPHERICAL_ESD_NOT_STORED": HelpEntry(
        title="Spherical moment uncertainties dropped",
        description=(
            "The file gives the moment in spherical form, with standard uncertainties. "
            "Converting to crystal-axis components is nonlinear, so the reader does not "
            "carry the uncertainties over. The components then show no error, and that "
            "does not mean the moment was fixed. Restate the row in crystal-axis or "
            "Cartesian form to keep the uncertainties."
        ),
    ),
    "CIF_MAGNETIC_SYMMFORM": HelpEntry(
        title="File records its own moment constraint",
        description=(
            "The file records the constraint on a moment that its producer applied. The "
            "package derives the allowed moment directions from the operator list and "
            "keeps the recorded form for reference. When both give the same number of "
            "free parameters, the finding is informational. When they differ, the "
            "refinement follows the operators. Check that the operator loop and the "
            "recorded form describe the same site symmetry."
        ),
    ),
    "CIF_MAGNETIC_UNIDENTIFIED": HelpEntry(
        title="Magnetic group not found in the database",
        description=(
            "The operator list does not match any magnetic space group in the tabulated "
            "database, so no UNI number is recorded. The operators are still the model, "
            "and the refinement is unaffected. The number is metadata. A list that is "
            "not closed under composition can cause this, as can a setting that the "
            "database does not recognise."
        ),
    ),
    "CIF_SITE_LISTED_TWICE": HelpEntry(
        title="One site listed twice, second dropped",
        description=(
            "Two sites of the same species lie on one symmetry orbit and share their "
            "occupancy and other properties. The file lists the same atoms twice, and "
            "counting both would double them in the cell. The reader dropped the second. "
            "Nothing needs changing if the two labels are one site. If they are meant as "
            "two sites, their coordinates are closer than any two atoms can be. A pair "
            "that differs in any property is refused instead."
        ),
    ),
    "CIF_SITE_MULTIPLICITY_DISAGREES": HelpEntry(
        title="Stated multiplicity contradicts the coordinates",
        description=(
            "The file states a site multiplicity that differs from the one its "
            "coordinates give under the stated space group. Rounding in the coordinates "
            "does not explain the gap. The atom count follows the coordinates, and so do "
            "the cell contents, the density and every weight fraction. Check the space "
            "group setting and the site against the source."
        ),
    ),
    "CIF_SITE_TWINS_MERGED": HelpEntry(
        title="Near-duplicate atoms merged onto a special position",
        description=(
            "A site sits slightly off a special position, so its symmetry images fall in "
            "tight pairs and would scatter as twice the atoms. The reader moved the site "
            "onto the special position. The usual cause is a relation such as (x, 2x, z) "
            "printed with one coordinate rounded. Check the coordinates against the "
            "source. The occupancy is kept, so the site's atoms per cell change with its "
            "multiplicity, and the message gives both counts. The reader merges only where "
            "the occupancy at the position, summed over the atoms sharing it and each "
            "times the images before over the images after, is above 1; otherwise it "
            "keeps the stated site and says `SITE_TWINS_KEPT`."
        ),
    ),
    "CIF_SPECIES_NORMALISED": HelpEntry(
        title="Atom type symbol rewritten",
        description=(
            "The file writes an atom type in a form that the scattering tables do not "
            "read. Examples are a site label in the type-symbol field and a charge "
            "written before its digit. The reader rewrote the symbol to the standard "
            "form and kept the ion where the file gave one. The meaning is unchanged, "
            "but the species spelling in the model now differs from the file."
        ),
    ),
    "CONSTRAINT_ACTIVE": HelpEntry(
        title="A constraint held the optimum on its edge",
        description=(
            "In the final stage the optimiser held some steps against a built-in "
            "inequality constraint. Examples are the positivity of the strain broadening "
            "and the positive Gaussian instrument width. The optimum therefore sits on "
            "or near the edge of the allowed region. The values are admissible but not "
            "measured. Start from a different seed and quote the values only if they "
            "survive."
        ),
    ),
    "COVARIANCE_DIRECTION_DISCARDED": HelpEntry(
        title="A combination of parameters is not measured",
        description=(
            "The data do not constrain one combination of several parameters. The solver "
            "discards that direction, so each esd in the group comes out too small, by "
            "at least a factor of the square root of two. Do not quote these esds as "
            "measured. Free fewer of the parameters in one stage, hold the ones you know "
            "independently, or widen the fitted range. Esds of other parameters are "
            "unaffected."
        ),
    ),
    "COVARIANCE_UNAVAILABLE": HelpEntry(
        title="The esd calculation failed",
        description=(
            "The solver returned, but the calculation of the esds raised an error "
            "afterwards. The refined values stand. In the final stage every esd, "
            "correlation and derived uncertainty is missing from the result. In an "
            "earlier stage only that stage's correlation checks did not run. Fix or "
            "restrain the most correlated parameters, refit from the returned values, "
            "and quote the esds from that fit."
        ),
    ),
    "DATA_SUPPORT_LOW": HelpEntry(
        title="Too few observations for the parameters",
        description=(
            "The number of independent reflections is low compared with the number of "
            "structural parameters refined. A refinement with too many parameters does "
            "not fail. It reports large esds, while the count of profile points hides "
            "the shortage. Hold the least determined parameters, add restraints, or "
            "extend the 2θ range to add reflections. More points across the same peaks "
            "do not help."
        ),
    ),
    "DECLARED_RANGE_NOT_RESTORED": HelpEntry(
        title="Old parameter left without a range",
        description=(
            "An older release stored this parameter with no limits, because it was set "
            "by hand. The current release gives such a parameter a default range. A "
            "stored value lies outside that range, so the parameter was left as stored "
            "and still refines without limits. No value changed. If the value is right, "
            "set a range that holds it before the next fit. If it is wrong, do not quote "
            "it as a measurement."
        ),
    ),
    "DECLARED_RANGE_RESTORED": HelpEntry(
        title="Old parameter given its default range",
        description=(
            "An older release stored this parameter with no limits, because it was set "
            "by hand. The reopened model gives it the range and unit that the current "
            "release declares for it. No stored value moved. A refinement from the "
            "reopened model can differ from the original run if the new range binds. Set "
            "a range on the parameter to keep a different one."
        ),
    ),
    "DISPERSION_NEGLECTED": HelpEntry(
        title="Anomalous scattering is switched off",
        description=(
            "The model has anomalous scattering turned off, yet at this wavelength it "
            "changes the scattering power of at least one element noticeably. The "
            "correction is a fixed constant and not a refined parameter. Leaving it out "
            "mis-scales every reflection of that element, and unequal effects between "
            "phases bias the weight fractions. Turn it back on. If the wavelength sits "
            "at an absorption edge, supply measured values."
        ),
    ),
    "EXTINCTION_CONDITIONS_PARTIAL": HelpEntry(
        title="Reflection conditions list is incomplete",
        description=(
            "The printed reflection conditions for this extinction class do not name "
            "every absence the class implies. The screen worked from the full set of "
            "absences, so its result is unaffected. Only the readable summary is short. "
            "Take the space groups listed with the class as the reliable statement."
        ),
    ),
    "EXTINCTION_FORBIDDEN_INTENSITY": HelpEntry(
        title="Intensity found where the class forbids it",
        description=(
            "The pattern carries intensity, at positions this extinction class says must "
            "be empty, that the class's own Le Bail fit cannot explain. If the intensity "
            "is real, the class is wrong and its space groups are unsupported. A flagged "
            "position can also be an impurity line, a broad container hump or the result "
            "of a cell held slightly off. Check those before you drop the class."
        ),
    ),
    "EXTINCTION_GROUPS_NOT_SEPARABLE": HelpEntry(
        title="Several space groups share one pattern",
        description=(
            "The leading extinction symbol covers more than one space group. These "
            "groups differ only by symmetry elements that produce no systematic "
            "absences, such as a centre of symmetry, a mirror or a handedness. Their "
            "powder patterns are identical, so longer counting cannot separate them. "
            "Choose between them with chemistry or a structure solution."
        ),
    ),
    "EXTINCTION_PRIOR_APPLIED": HelpEntry(
        title="Declared facts removed space groups from the extinction classes",
        description=(
            "You declared facts about the specimen (chirality, centrosymmetry, "
            "polarity, or the formula units per cell as a Z or a density), and they "
            "removed space groups from some classes. Each removed group is named with "
            "the fact it fails. A declared Z tests whether some element's atoms "
            "per cell can sit on whole orbits of a group (a position with no free parameter "
            "is one orbit, used once), the test of an ordered model. A group that fails "
            "the count is kept and named, since a disordered alloy written with whole counts "
            "fails it on its true group, and is removed only when you declare the model "
            "`ordered`. "
            "Where Z is not a whole multiple of a kept group's general multiplicity "
            "(Z′ below one), the group stays and the message names the special "
            "positions a formula unit then needs, since a molecule there must carry "
            "that symmetry. The declaration only filters the members of each class. "
            "Every class was still fitted, and no ΔBIC moved. It is a warning when the "
            "class the data rank first was emptied: either the chemistry is doing what a "
            "powder cannot, or the declaration is wrong. It is also a warning when a "
            "declared density does not give the declared Z on this cell; nothing is then "
            "filtered by Z. `best_or_none()` abstains in both cases. Check the "
            "declaration before you read the answer."
        ),
    ),
    "EXTINCTION_SCREEN_FAILED": HelpEntry(
        title="The extinction screen could not run",
        description=(
            "The reference Le Bail fit that every extinction class is compared against "
            "failed, or the cell predicts no reflections in the measured range. No class "
            "was screened, so an empty ranking says nothing about the symmetry. Every "
            "class would fail the same way. Validate the cell first, then check the "
            "wavelength and the 2θ range."
        ),
    ),
    "EXTINCTION_SCREEN_UNRELIABLE": HelpEntry(
        title="The extinction screen's reference fit is too poor to read absences against",
        description=(
            "The absence-free reference fit leaves more than half of the pattern's net "
            "signal, taken against its own background, unexplained. It has not modelled "
            "the allowed lines, so every refutation and ΔBIC below it may measure that "
            "misfit. The classes are ranked, but `best_or_none()` abstains. Any of these "
            "can cause it, in no order: the cell (a few tenths of a per cent off at "
            "synchrotron resolution is outside the basin a Le Bail fit can refine it "
            "from; re-index it from a better start), a phase the reference does not "
            "model, weak data (for a perfect fit the quantity is about √(N/(N+S)), N the "
            "channels and S the weighted net Bragg power, so it passes the bound whenever "
            "S < N; counting longer helps and re-indexing does not), the range, the "
            "wavelength and the width law. The bound, 1/√2 (at most half "
            "of the net weighted power unexplained), sits between every right or nearly "
            "right cell (≤ 0.36) and every cell outside the refinable basin (≥ 1.6) on "
            "synthetic Si and P 2₁/c, 11-BM NAC, the GSAS-II fluorapatite and PbSO₄ "
            "patterns and SRM 676a corundum; untested beyond them, and a second phase "
            "carrying half the net weighted power trips it at a right cell. The gate does "
            "not reach a local misfit: on certified SRM 676a corundum "
            "(`R -3 c`) the shared profile fit's `profile_rwp` is 0.149 over 20–90°, where "
            "`R - c -` wins, and 0.227 over 5–150° with declared widths, where `R - - -` "
            "wins, with this code silent in both (measured on that one pattern)."
        ),
    ),
    "EXTINCTION_SYMBOL_AMBIGUOUS": HelpEntry(
        title="The extinction symbol is not settled",
        description=(
            "The data do not pick one extinction symbol. A second class may score within "
            "the decisive margin, the leading class may have no absence that is testable "
            "in this range, some classes may never have been fitted, or no class could "
            "be screened at all. Counting longer at the positions where the leading "
            "classes disagree, or widening the range, helps with the first two. Rwp is "
            "no guide, because it favours the class with more reflections."
        ),
    ),
    "EXTRA_PEAK_NO_INTENSITY": HelpEntry(
        title="A declared peak refined to zero intensity",
        description=(
            "The area of a declared peak finished at zero. A peak reaches the pattern "
            "only through its area, so at zero area nothing fixes its centre. The centre "
            "and its esd are then not measurements. Either the feature is not in the "
            "specimen or the bounds on the centre do not cover it. Drop the peak or move "
            "its centre bounds."
        ),
    ),
    "EXTRA_PEAK_ON_REFLECTION": HelpEntry(
        title="A declared peak sits on a modelled reflection",
        description=(
            "A declared peak lies close enough to a reflection the model already "
            "predicts that the two describe one peak between them. How the intensity "
            "divides between the phase and the peak is a degeneracy and not a "
            "measurement. That is expected when a holder line overlaps a sample peak. If "
            "the peak stands in for a misfitting reflection, fix the phase scale, "
            "profile or preferred orientation instead."
        ),
    ),
    "FLAT_DIRECTION": HelpEntry(
        title="Two parameters the data cannot separate",
        description=(
            "Two parameters are correlated so completely that the data measure only one "
            "combination of them. This is a statement about the rank of the problem and "
            "not about a strong correlation. Each esd is conditional on the other "
            "parameter being right. Fix one at an independently known value and refine "
            "the other, or free them in separate stages. A wider range or a second "
            "histogram can separate them."
        ),
    ),
    "FLAT_DIRECTION_OMITTED": HelpEntry(
        title="Further flat directions not listed",
        description=(
            "The data cannot tell some combinations of parameters apart, and the list "
            "shows only the strongest of these flat directions. This entry counts the "
            "weaker ones left out. Nothing was dropped from the fit. The identifiability "
            "record on the result holds the full set."
        ),
    ),
    "FLOOR_HIT": HelpEntry(
        title="A parameter finished at zero",
        description=(
            "A scale, a width or a similar quantity finished on its lower limit of zero, "
            "because the data push it lower than it can go. The value is a floor and not "
            "a measurement of zero. The other esds are marginal over it. Quote an upper "
            "limit for the parameter. If it belongs to a phase or term the data do not "
            "support, remove it."
        ),
    ),
    "FROZEN_COMPILE_STALE": HelpEntry(
        title="Reported fit statistics differ from the stage's own",
        description=(
            "The final stage fixes its peak windows at the values it started from. At "
            "the returned values, those windows give a chi-squared that differs "
            "noticeably from a fresh calculation. The reported statistics and curves use "
            "the fresh one, and the esds are those of the last solve. The last stage's "
            "record keeps the earlier figure, and so does the history node of a single "
            "fit. A joint fit tests each pattern and names the worst. A large gap means the last stage carried its peaks "
            "past the windows it was solved on, so the solve may have stopped short of the "
            "minimum that windows sized at the answer give. Run one more stage with nothing "
            "new freed and compare. A plan's closing stage does this already."
        ),
    ),
    "FULLPROF_MAGNETIC_PHASE_OMITTED": HelpEntry(
        title="A FullProf magnetic phase was left out",
        description=(
            "The FullProf file holds a magnetic phase, and `nuclear_only=True` asked for "
            "the nuclear phases alone. The built structure has no magnetic scattering. "
            "Its pattern and its fit quality are not comparable with the file's. Leave "
            "the setting off to have the reader map the magnetic phase, or refuse it "
            "with a reason."
        ),
    ),
    "FULLPROF_MAGNETIC_PHASE_READ": HelpEntry(
        title="A FullProf magnetic phase was merged in",
        description=(
            "FullProf describes a magnetic structure as a second phase beside the "
            "nuclear one. The reader checked that the two describe the same crystal and "
            "merged them into one phase with a magnetic group and moments. The magnetic "
            "phase's own scale, positions and displacement parameters are not kept "
            "apart, so refine the merged phase as one. A site that frees only part of "
            "its moment comes in with the whole moment free."
        ),
    ),
    "FULLPROF_OCCUPANCY_UNCHECKED": HelpEntry(
        title="The setting check had nothing to compare",
        description=(
            "FullProf does not write the origin choice or axes of a space group, so the "
            "reader picks one and tests the pick against the site occupancies. A phase "
            "with one site gives that test nothing to compare, because FullProf's "
            "occupancy carries an arbitrary factor for each phase. The setting passed "
            "without being verified, so it may be the wrong one. Check it against the "
            "published structure."
        ),
    ),
    "FULLPROF_ORIGIN_CHOICE": HelpEntry(
        title="A FullProf space group setting was chosen",
        description=(
            "FullProf writes a space group symbol with no origin choice or axes suffix. "
            "The reader added one: origin choice 2 where the bare symbol allows two, and "
            "rhombohedral axes where the cell shows them. A wrong choice moves the "
            "special positions and changes the multiplicities, so the structure would be "
            "a different one. The choice is tested against the site occupancies."
        ),
    ),
    "FULLPROF_RHOMBOHEDRAL_RESTATED": HelpEntry(
        title="A rhombohedral phase was restated for FullProf",
        description=(
            "FullProf reads a rhombohedral space group symbol as hexagonal whatever the "
            "cell says, and it has no suffix to say otherwise. The writer therefore "
            "restated the phase in the hexagonal cell of the same lattice, and rescaled "
            "the scale to match. The crystal and its pattern are unchanged. The ties "
            "between the rhombohedral parameters are not stated, so free the hexagonal "
            "parameters you mean to refine."
        ),
    ),
    "FULLPROF_SPECIES_NORMALISED": HelpEntry(
        title="A FullProf scattering label was respelled",
        description=(
            "FullProf writes the scattering label in the author's case, and it can put "
            "the charge sign first. The reader respelled the label in the standard "
            "element-and-charge form. On a neutron file, an isotope set by a user "
            "scattering length is read as that isotope. The structure holds one "
            "spelling, and the original label stays on the parsed model so you can check "
            "it against the file."
        ),
    ),
    "FULLPROF_SPECIES_WRITTEN_NEUTRAL": HelpEntry(
        title="A FullProf ion was written as neutral",
        description=(
            "The X-ray scattering table has no entry for this ion, so rietx computed the "
            "neutral atom for it. The FullProf file therefore names the neutral element "
            "and the ion's charge is lost. FullProf's pattern differs from rietx's by "
            "the difference between the two form factors. Respell the site in FullProf "
            "if you want the ion."
        ),
    ),
    "FULLPROF_TIE_DROPPED": HelpEntry(
        title="A FullProf constraint was not carried over",
        description=(
            "The FullProf file ties two values together with a shared codeword, and the "
            "built structure does not reproduce that tie. The structure has more free "
            "parameters than the refinement the file records, so the two refinements can "
            "disagree. Re-declare the constraint on the refinement to restore it. The "
            "message names the call."
        ),
    ),
    "GSAS2_CIF_DEUTERIUM_AS_D": HelpEntry(
        title="Deuterium was written as D for GSAS-II",
        description=(
            "GSAS-II's CIF import reads an isotope label such as 2H as hydrogen and says "
            "so only on screen. The one isotope label it accepts is D, so deuterium "
            "sites are written as D. GSAS-II uses its own scattering length for D. It "
            "differs slightly from the value rietx uses. A GSAS-II refinement of this "
            "file starts a little away from the rietx answer on those sites."
        ),
    ),
    "GSAS2_CIF_FIELD_NOT_WRITTEN": HelpEntry(
        title="A phase CIF cannot state the whole model",
        description=(
            "A phase CIF has no tags for refine flags, the phase scale, sample "
            "broadening, or several optional phase corrections. GSAS-II builds its "
            "project from the file with its own defaults for these. The refinement you "
            "start there is not the protocol this model carries. Set these in GSAS-II "
            "before you compare results."
        ),
    ),
    "GSAS2_CIF_RHOMBOHEDRAL_RESTATED": HelpEntry(
        title="A rhombohedral phase was restated for GSAS-II",
        description=(
            "GSAS-II's CIF import gives up on a rhombohedral-axes space group symbol. "
            "The writer restated the phase in the hexagonal cell of the same lattice, "
            "with the scale adjusted to match. The crystal and its pattern are "
            "unchanged. The ties between the rhombohedral parameters are not stated, so "
            "free the hexagonal parameters you mean to refine."
        ),
    ),
    "GSAS2_CIF_SETTING_IN_OPERATORS": HelpEntry(
        title="The setting is stated in the operators",
        description=(
            "GSAS-II and rietx read a bare symbol with two origin choices in opposite "
            "ways. GSAS-II takes choice 2 and rietx takes choice 1. The CIF therefore "
            "states the setting three times: a bare symbol for GSAS-II, a full symbol "
            "for rietx, and the symmetry operators. Both programs can check the "
            "operators. Each program reads the tag it understands."
        ),
    ),
    "GSAS2_CIF_SPECIES_WRITTEN_NEUTRAL": HelpEntry(
        title="A GSAS-II ion was written as neutral",
        description=(
            "The X-ray scattering table has no entry for this ion, so the CIF names the "
            "neutral element that rietx computed with. The ion's charge is not in the "
            "file, and GSAS-II will scatter from the neutral atom. Respell the site in "
            "GSAS-II if you want to refine the ion."
        ),
    ),
    "GSAS2_GPX_BACKGROUND_NOT_CARRIED": HelpEntry(
        title="A GSAS-II background was not converted",
        description=(
            "GSAS-II fits its background with its own functions, including Debye terms "
            "and fitted peaks, and none has an exact counterpart here. The function name "
            "and coefficients stay on the parsed model and nothing is converted. Choose "
            "a background and refine it. An Rwp you compute is not comparable with the "
            "file's until the backgrounds match."
        ),
    ),
    "GSAS2_GPX_CONSTRAINT_NOT_CARRIED": HelpEntry(
        title="GSAS-II constraints were not applied",
        description=(
            "The project holds constraints between parameters, and the built structure "
            "applies none of them. It has more free parameters than the GSAS-II "
            "refinement had. An equivalence can be restored with one tie on the "
            "refinement. A constraint equation or a new variable has no single call that "
            "restores it, so read it and match your free set by hand."
        ),
    ),
    "GSAS2_GPX_COORDINATES_SYMMETRY_FIXED": HelpEntry(
        title="A GSAS-II flag sits on a fixed site",
        description=(
            "The GSAS-II coordinate flag means refine as symmetry permits. These sites "
            "sit on special positions where symmetry permits no movement, so nothing of "
            "them was free in GSAS-II either. The reader holds the coordinates. The "
            "parameter count matches the file's."
        ),
    ),
    "GSAS2_GPX_ITEM_NOT_READ": HelpEntry(
        title="Part of the GSAS-II project was not read",
        description=(
            "A project file holds a whole GSAS-II session, and this reader takes the "
            "powder part. Images, single-crystal histograms, sequential-fit results, "
            "restraints and tree items it has no rule for are named in the message and "
            "carried nowhere. A time-of-flight histogram is kept with its numbers, but "
            "its profile coefficients belong to a different function from the one fitted "
            "here."
        ),
    ),
    "GSAS2_GPX_PHASE_MAGNETIC": HelpEntry(
        title="A magnetic phase appears in the GSAS-II project",
        description=(
            "The project holds a phase that GSAS-II types as magnetic, or a nuclear "
            "phase linked to a magnetic partner. This reader does not read the magnetic "
            "block, so a magnetic phase cannot be built. Its nuclear half alone would "
            "look complete. Other phases build, but where they share a histogram with a "
            "magnetic phase the file's figures include magnetic scattering. A magCIF of "
            "the structure carries the moments."
        ),
    ),
    "GSAS2_GPX_SCALE_NOT_COMPARABLE": HelpEntry(
        title="A GSAS-II scale was not converted",
        description=(
            "GSAS-II keeps a histogram scale and a phase scale, and each folds its own "
            "normalisation into one number. Neither is a rietx scale, so the reader "
            "seeds the scale at a small starting value. Refine it before you trust it. "
            "Phase fractions from the two programs agree only after both have refined."
        ),
    ),
    "GSAS2_GPX_SETTING_FROM_OPERATORS": HelpEntry(
        title="The setting was read from the operators",
        description=(
            "The project names a space group symbol that exists in more than one "
            "setting. GSAS-II also stores the symmetry operators, so the reader takes "
            "the setting from them and assumes nothing. The built phase can carry a "
            "longer symbol than the one the file wrote. The setting is the one the file "
            "states."
        ),
    ),
    "GSAS2_GPX_SPECIES_NORMALISED": HelpEntry(
        title="A GSAS-II atom type was respelled",
        description=(
            "GSAS-II writes the charge sign first and keeps the isotope outside the atom "
            "type. The reader respelled each label in the standard element-and-charge "
            "form, with a mass number in front for an isotope. The structure holds one "
            "spelling, and the original label stays on the parsed model so you can check "
            "it against the file."
        ),
    ),
    "GSAS2_GPX_TEXTURE_CONVERTED": HelpEntry(
        title="A GSAS-II texture was converted",
        description=(
            "GSAS-II places the sample angle of its spherical-harmonics texture "
            "differently from rietx for a Bragg-Brentano histogram, and it normalises "
            "some terms differently. Each coefficient was multiplied by the factor that "
            "maps one onto the other. Compare coefficients with GSAS-II only through "
            "that conversion, and fit under the `bragg_brentano` geometry."
        ),
    ),
    "GSAS2_GPX_TEXTURE_NOT_CARRIED": HelpEntry(
        title="A GSAS-II texture was not carried over",
        description=(
            "The phase has a spherical-harmonics texture that cannot be converted "
            "exactly. The cause is named in the message, such as a different geometry, "
            "histograms that disagree, or terms GSAS-II itself evaluates inconsistently. "
            "The built phase has no texture, so intensities the texture explained are "
            "left unexplained. Declare a texture yourself and refine it from zero."
        ),
    ),
    "GSAS2_INSTPRM_CONVENTION_ASSUMED": HelpEntry(
        title="Axial divergence was split evenly",
        description=(
            "GSAS-II states axial divergence as one combined number, and this package "
            "models it as two. The reader split the number evenly between them. A single "
            "number allows no other split. If you know your slits are unequal, set the "
            "two values yourself."
        ),
    ),
    "GSAS2_INSTPRM_FIELD_DROPPED": HelpEntry(
        title="Some time-of-flight keys were read and not kept",
        description=(
            "The file holds keys that the instrument has no place for. Some are labels. "
            "Others are terms with no published law. The reader accepts these only at "
            "zero, so dropping them changes no calculated pattern. A non-zero value of "
            "such a term stops the read with an error."
        ),
    ),
    "GSAS2_INSTPRM_FIELD_NOT_READ": HelpEntry(
        title="The file states items the instrument cannot hold",
        description=(
            "The file lists items that the instrument has no field for, such as a bank "
            "number, an instrument name or a polarisation on a neutron bank. They were "
            "read and not kept. The message names each one. If one matters to your work, "
            "set the equivalent value yourself."
        ),
    ),
    "GSAS2_INSTPRM_FIELD_NOT_WRITTEN": HelpEntry(
        title="The exported file omits part of the instrument",
        description=(
            "A GSAS-II instrument-parameter file has no items for the background, the "
            "specimen absorption, the specimen displacement or the transparency. "
            "Depending on the instrument, extra components, a Voigt peak shape and "
            "refine flags are lost too. Reading the file back gives a frozen instrument "
            "without them, so keep your own copy of the full one."
        ),
    ),
    "GSAS2_INSTPRM_GEOMETRY_ASSUMED": HelpEntry(
        title="The file states no diffractometer geometry",
        description=(
            "The file has no `Diff-type` item, so the geometry was not read. The reader "
            "applied GSAS-II's own fallback. A stated doublet gives Bragg-Brentano and "
            "anything else gives Debye-Scherrer. The two use different position and "
            "absorption corrections, so set the geometry yourself if you know the "
            "diffractometer."
        ),
    ),
    "GSAS2_INSTPRM_VALUE_DEFAULTED": HelpEntry(
        title="Items missing from the file took default values",
        description=(
            "The file omits items that GSAS-II always writes for a bank, so those values "
            "came from this package's defaults and not from your calibration. GSAS-II's "
            "header tells users not to delete items, so a missing one usually means "
            "someone edited the file by hand. Check the values before you trust the "
            "instrument."
        ),
    ),
    "GSAS2_INSTPRM_VALUE_FLOORED": HelpEntry(
        title="GSAS-II will raise a small axial divergence",
        description=(
            "The combined axial-divergence value is below the smallest one GSAS-II uses "
            "when it evaluates a profile. The file records your value as you gave it. "
            "GSAS-II replaces it with its floor, so it models more axial divergence than "
            "you wrote. Reading the file back here shows no difference, because the "
            "floor belongs to the program that reads it."
        ),
    ),
    "GSAS2_INSTPRM_VALUE_MERGED": HelpEntry(
        title="Two axial-divergence values became one",
        description=(
            "GSAS-II models axial divergence with one number, and this instrument holds "
            "two that differ. The writer saves their sum. Reading the file back splits "
            "the sum evenly, so the original pair does not return. Only the total "
            "survives."
        ),
    ),
    "GSAS_BANK_COMMENTED": HelpEntry(
        title="A commented-out bank record was used",
        description=(
            "The file has no active bank record, so the reader used a commented one. "
            "GSAS bank records give the axis in centidegrees. The same rows read as "
            "plain text put the axis 100 times too high. If the line was commented out "
            "to disable the bank, the file holds no other bank to read."
        ),
    ),
    "GSAS_EXP_BACKGROUND_NOT_CARRIED": HelpEntry(
        title="A GSAS background function was not converted",
        description=(
            "GSAS offers several background functions, including a reciprocal-Q "
            "expansion for air scatter and interpolation between fixed points. None is a "
            "rietx background. The function number and coefficients stay on the parsed "
            "model and nothing is converted. Choose a background and refine it. An Rwp "
            "you compute is not comparable with the file's until the backgrounds match."
        ),
    ),
    "GSAS_EXP_COORDINATES_SYMMETRY_FIXED": HelpEntry(
        title="A GSAS flag sits on a fixed site",
        description=(
            "The GSAS coordinate flag means refine as symmetry permits. These sites sit "
            "on special positions where symmetry permits no movement, so nothing of them "
            "was free in GSAS either. The reader holds the coordinates. The parameter "
            "count matches the file's."
        ),
    ),
    "GSAS_EXP_HISTOGRAM_NOT_READ": HelpEntry(
        title="A GSAS histogram was only partly read",
        description=(
            "The histogram is single-crystal data, time-of-flight or energy-dispersive "
            "data, or it states no radiation type. Its profile functions number their "
            "coefficients differently from the constant-wavelength ones rietx names. The "
            "histogram stays on the parsed model with its ranges, but its profile "
            "coefficients are left unnamed. Naming them under the wrong order would put "
            "every width on the wrong term."
        ),
    ),
    "GSAS_EXP_PHASE_MAGNETIC": HelpEntry(
        title="A magnetic phase appears in the GSAS file",
        description=(
            "GSAS types some phases as magnetic. This reader does not read the magnetic "
            "block of a `.EXP` file, so it refuses to build that phase. Its nuclear half "
            "alone would look complete. The cell and sites stay readable on the parsed "
            "model. A magCIF of the structure carries the moments."
        ),
    ),
    "GSAS_EXP_REFINE_FLAG_MERGED": HelpEntry(
        title="A GSAS flag is wider than the structure",
        description=(
            "GSAS has one refine flag for the whole cell and one for a site's three "
            "coordinates, each meaning refine as symmetry permits. Some members of such "
            "a group are held in your structure and others are free. The writer sets the "
            "flag free where any member varies, so the file frees a parameter you held. "
            "Reading the file back gives every member the same flag. Hold or free the "
            "whole group first."
        ),
    ),
    "GSAS_EXP_SCALE_NOT_COMPARABLE": HelpEntry(
        title="A GSAS scale was not converted",
        description=(
            "The GSAS histogram scale folds its own normalisation and the phase fraction "
            "into one number. It is not a rietx scale, so the reader seeds the scale at "
            "a small starting value. Refine it before you trust it. Phase fractions from "
            "the two programs agree only after both have refined."
        ),
    ),
    "GSAS_EXP_SPECIES_NORMALISED": HelpEntry(
        title="A GSAS atom type was respelled",
        description=(
            "GSAS writes the scattering type in upper case, and it writes an isotope as "
            "the element, the valence and the isotope number after an underscore. The "
            "reader respelled the type in the standard form, with the mass number in "
            "front for an isotope. The structure holds one spelling, and the original "
            "stays on the parsed model."
        ),
    ),
    "GSAS_EXP_SPECIES_WRITTEN_NEUTRAL": HelpEntry(
        title="A GSAS ion was written as neutral",
        description=(
            "The X-ray scattering table has no entry for this ion, so rietx computed the "
            "neutral atom for it. The `.EXP` file therefore names the neutral element "
            "and the ion's charge is lost. GSAS will scatter from the neutral atom. "
            "Respell the type in GSAS if you want the ion."
        ),
    ),
    "GSAS_EXP_VALUE_NARROWED": HelpEntry(
        title="Written values lost trailing digits",
        description=(
            "A `.EXP` file reads each number from a fixed-width field. A value whose "
            "shortest exact decimal is longer than the field was written to the "
            "precision the field holds. The rounding is normally far smaller than the "
            "refined uncertainty. Displacement parameters are the usual case, because "
            "GSAS stores a different form of them. It matters only if you compare "
            "numbers bit for bit."
        ),
    ),
    "GSAS_FIELD_OVERFLOW": HelpEntry(
        title="A GSAS field holds only asterisks",
        description=(
            "Fortran prints asterisks when a number is too wide for its field. GSAS had "
            "a value here and could not write it. The field is optional, so the reader "
            "treats it as absent. A missing value on the model does not mean the file "
            "left it out. Take the value from GSAS's own listing if you need it."
        ),
    ),
    "GSAS_IPARM_FIELD_DROPPED": HelpEntry(
        title="Some instrument records were read and not kept",
        description=(
            "The file holds records or fields with no slot in the instrument model. "
            "Examples are the correlation matrix of the incident-spectrum coefficients, "
            "a checksum with no published algorithm, and labels. The reader names them "
            "once for the whole file. The calibration and the profile that the model "
            "does hold are unaffected."
        ),
    ),
    "GSAS_IPARM_LEGACY_LAYOUT": HelpEntry(
        title="The file used a legacy LANSCE layout",
        description=(
            "The file departs from the layout in the GSAS manual, in a way found in "
            "older instrument files from LANSCE. You called the legacy reader by name, "
            "and it accepted the departure. The standard reader refuses the same file. "
            "Check the values taken against the source of the file, because each finding "
            "names the departure it accepted."
        ),
    ),
    "GSAS_IPARM_PROFILE_DECLINED": HelpEntry(
        title="A peak-shape set was not read",
        description=(
            "A time-of-flight bank can hold several peak-shape sets. Only the default "
            "set is read, so any other set is skipped. A bank with no set at all comes "
            "back with every profile coefficient at zero, and a fit refuses it by name. "
            "Enter the profile yourself, or read it from another file for the same bank."
        ),
    ),
    "GSAS_IPARM_PROFILE_READ": HelpEntry(
        title="Peak-shape coefficients were read in an assumed order",
        description=(
            "The default peak-shape set was read into the instrument. The GSAS manual "
            "names the coefficients but never says that the record holds them in that "
            "order, so the order is an assumption. One cutoff value is read and not "
            "used. Check the values against a known profile before you refine from them."
        ),
    ),
    "GSAS_PRM_FIELD_DROPPED": HelpEntry(
        title="Some parameter-file fields were read and not kept",
        description=(
            "The .prm file holds fields with no place in the instrument model, such as "
            "refine flags, damping controls and profile coefficients beyond the ones "
            "mapped. A frozen calibration has no use for them. They are dropped only "
            "where they sit at a neutral value or are inert for this source, and the "
            "message says what each record held."
        ),
    ),
    "GSAS_PRM_FIELD_NOT_WRITTEN": HelpEntry(
        title="The exported .prm omits part of the instrument",
        description=(
            "A GSAS .prm file has no record for the geometry, the specimen displacement, "
            "the transparency or the specimen absorption. Reading the file back gives a "
            "Debye-Scherrer instrument with every refine flag off. Depending on the "
            "instrument, a Voigt peak shape and extra components are lost too. Keep your "
            "own copy of the full instrument."
        ),
    ),
    "GSAS_PRM_GEOMETRY_ASSUMED": HelpEntry(
        title="The .prm file states no geometry",
        description=(
            "A GSAS .prm file does not say whether the diffractometer is Bragg-Brentano "
            "or Debye-Scherrer. The reader returned a Debye-Scherrer instrument. The "
            "position and absorption corrections differ between the two, so a flat-plate "
            "calibration read this way is modelled wrongly. Set the geometry yourself, "
            "and carry over the axial divergence values that the file did state."
        ),
    ),
    "GSAS_PRM_PROFILE_SET_DEFAULTED": HelpEntry(
        title="The bank offered several profile sets",
        description=(
            "A .prm bank can hold more than one profile set, and you named none, so the "
            "reader took set 1. GSAS-II's importer makes the same choice. Only the "
            "pseudo-Voigt function is read. If another set describes your data, name it "
            "with `profile_set=`."
        ),
    ),
    "GSAS_PRM_VALUE_NARROWED": HelpEntry(
        title="Values were shortened to fit the file",
        description=(
            "A .prm file stores numbers in fixed-width fields. Some of your values need "
            "more characters than a field holds, so the writer saved them to the "
            "precision that fits. A converged calibration does this routinely. The "
            "message names the largest change."
        ),
    ),
    "HARMONIC_ABSENT": HelpEntry(
        title="A declared harmonic refined to nothing",
        description=(
            "A declared wavelength harmonic refined to a fraction indistinguishable from "
            "zero. That is a result and not a failure. The beam carries no measurable "
            "contamination at that order, as a monochromator with that order extinct "
            "should give. Dropping the declaration reproduces the fit with one parameter "
            "fewer."
        ),
    ),
    "HARMONIC_FRACTION": HelpEntry(
        title="Fraction of a wavelength harmonic in the beam",
        description=(
            "A declared wavelength harmonic refined to a measurable fraction of the "
            "fundamental. The value describes this beam on this monochromator in this "
            "measurement. Do not carry it to another histogram or instrument. A large "
            "fraction means the harmonic is absorbing intensity the model puts "
            "elsewhere, such as an unindexed impurity or a stiff background. Check the "
            "tick marks against the unfitted peaks."
        ),
    ),
    "HARMONIC_HELD": HelpEntry(
        title="A harmonic weight was declared but not refined",
        description=(
            "The weight of a declared wavelength harmonic was held, so it did not enter "
            "the fit. The number you see is the value you declared and not a measurement "
            "of the beam. Free the weight in a stage after the profile and the scale "
            "have settled to measure it. Until then, do not quote it as a property of "
            "the beam."
        ),
    ),
    "HIGH_CORRELATION": HelpEntry(
        title="Two parameters are strongly correlated",
        description=(
            "Two refined parameters are strongly correlated, so the data constrain their "
            "combination better than either one alone. Each esd is larger than it would "
            "be if the other were known. You cannot quote the two as independent "
            "measurements. Fixing one at a known value, or freeing them in separate "
            "stages, shows how much each is determined by the data."
        ),
    ),
    "HIGH_CORRELATION_OMITTED": HelpEntry(
        title="Further correlated pairs not listed",
        description=(
            "Some pairs of parameters are correlated so strongly that their separate "
            "values are less reliable. The list shows only the strongest pairs, to stay "
            "readable. This entry counts the weaker pairs left out. The fit used all of "
            "them. The identifiability record on the result holds the full correlation "
            "matrix."
        ),
    ),
    "HOLD_BLOCKED_PLAN": HelpEntry(
        title="A hold overrode part of the plan",
        description=(
            "A stage of the plan asked to refine a parameter that you had held. The hold "
            "won, so the parameter kept the value you gave it and has no esd. The run "
            "did what you declared. The plan therefore did less than its name suggests. "
            "If you meant the plan to refine these parameters, release the hold first."
        ),
    ),
    "HUMP_TOO_NARROW": HelpEntry(
        title="A background peak has become narrow",
        description=(
            "A declared background peak has narrowed towards the instrumental "
            "resolution. At that width it is a reflection with no cell or structure "
            "behind it. A free peak improves Rwp whether or not anything is there. "
            "Background peaks are for diffuse or amorphous scattering, whose width comes "
            "from disorder. A real unindexed line needs a second phase. Do not quote the "
            "peak parameters."
        ),
    ),
    "INDEX_ABSTAINED": HelpEntry(
        title="No cell reached the confidence gate",
        description=(
            "No candidate passed every check needed to name it, or no cell was found in "
            "the systems searched. The best candidates are listed with the reasons they "
            "fell short, so you can see what was considered. The abstention is the "
            "result, and no cell is implied by the ranking. Most reasons are closed by "
            "better data, and a different search seldom helps."
        ),
    ),
    "INDEX_BRAVAIS_AMBIGUOUS": HelpEntry(
        title="Lattice symmetry is not settled",
        description=(
            "The lattice reads as a higher symmetry only at a loose tolerance, or two "
            "symmetry tools disagree about it at their tightest settings. This is what "
            "pseudosymmetry looks like. The reported system is the lower one, which is "
            "the safe reading. Refine in the lower symmetry and test the higher one "
            "against the data."
        ),
    ),
    "INDEX_BUDGET_EXHAUSTED": HelpEntry(
        title="The time limit cut the search short",
        description=(
            "The whole-run time limit ended the search, or the validation fits used up "
            "their share of it. Some systems were searched in part, some were never "
            "reached, and some candidates were not validated. A missing cell or a "
            "missing system is then no evidence of absence. Raise the limit, or narrow "
            "the systems to where the cell can live."
        ),
    ),
    "INDEX_CANDIDATES_TRUNCATED": HelpEntry(
        title="The candidate list was cut to a maximum",
        description=(
            "The search found more distinct lattices than the list reports, so "
            "lower-ranked cells are left out. The limit exists because each reported "
            "candidate costs a validation fit. An engine that returned a full pool may also "
            "have held more. The omitted cells were never judged and rejected. Raise "
            "`max_candidates` to see further down the ranking."
        ),
    ),
    "INDEX_CELL_SYSTEMATIC_UNQUANTIFIED": HelpEntry(
        title="Cell accuracy is worse than its esd",
        description=(
            "The esd on an indexed cell comes from the line positions alone. It measures "
            "precision, not accuracy. Instrument geometry adds a systematic error, such "
            "as the goniometer radius of a Bragg-Brentano diffractometer, that the data "
            "cannot identify and no esd reports. Quote the cell to a coarser level than "
            "its esd, or calibrate against a certified standard."
        ),
    ),
    "INDEX_DATA_INSUFFICIENT": HelpEntry(
        title="Data cannot support an indexing search",
        description=(
            "The peak list cannot constrain a lattice. It has fewer than two usable "
            "lines, too few lines for the free cell parameters of any crystal system, or "
            "line positions too imprecise to tell cells apart. A search would return a "
            "ranking with nothing behind it. Extend the 2θ range, count for longer, or "
            "re-pick the peaks with a lower detection threshold."
        ),
    ),
    "INDEX_DOMINANT_ZONE": HelpEntry(
        title="Lowest lines carry large indices on one axis",
        description=(
            "No cell was found with the standard table of indices, but one appeared when "
            "larger indices were allowed. This happens when one cell axis is much "
            "shorter or longer than the others, so the lowest observed lines have large "
            "indices along it. The lines that would pin that direction lie below the "
            "measured range or are too weak to detect. Measure to lower angle, or use "
            "the dichotomy engine, which assumes no index limit."
        ),
    ),
    "INDEX_GEOMETRIC_AMBIGUITY": HelpEntry(
        title="Different lattices give the same line positions",
        description=(
            "At least one other lattice explains the observed line positions as well as "
            "this one. A powder pattern records only the length of each reciprocal "
            "vector, so the information that separates the lattices is absent from the "
            "measurement. Neither cell can be quoted with confidence. Look for the "
            "reflections that only one of the lattices predicts, at the 2θ positions "
            "listed."
        ),
    ),
    "INDEX_IMPURITY_LINES": HelpEntry(
        title="Observed peaks have no matching reflection",
        description=(
            "After the whole-pattern fit of this cell, some observed peaks sit "
            "where it predicts no reflection. A handful of such lines points to a second "
            "phase. Many of them point to a wrong cell. To look for the second phase, "
            "pass the result to `rietx.indexing.index_residue`, which subtracts the "
            "first cell and indexes the remainder."
        ),
    ),
    "INDEX_INLIER_RETRY": HelpEntry(
        title="The search was run again, accepting a cell that leaves lines unindexed",
        description=(
            "The default run found no lattice that two engines agree on while a cell "
            "could leave at most two search lines unindexed. The search ran again, "
            "accepting a cell that indexes at least 60 % of the search lines and the five "
            "strongest. That is the reading of a list that carries foreign lines: an "
            "impurity, a container halo or unresolved shoulders. The answer rests on the "
            "second rule, so read each candidate's `n_search_unindexed` and "
            "`unindexed_two_theta`. A cell that leaves the weak lines is the phase, and "
            "the residue is a second phase or the picker's junk. Pass `n_unindexed='inliers'` "
            "to search this way from the start, or an integer to forbid the retry."
        ),
    ),
    "INDEX_RESIDUE_PASS": HelpEntry(
        title="This result indexes what another cell left of the pattern",
        description=(
            "`index_residue` fitted the named cell to the pattern with the validation's own "
            "Pawley fit, subtracted "
            "its peaks, picked the remainder at that fit's widths and indexed it. Picks "
            "standing on more of the subtracted profile than their own height are "
            "flagged `residue_misfit` as that fit's misfit, and `where` lists them; they "
            "stay usable lines, so the grade counts them as unindexed, and they never "
            "drive the search. When that fit needed "
            "widths more than three times the list's own, the cell does not describe the "
            "pattern and nothing was picked; the message says so. A candidate here is a "
            "second phase only if it earns a grade of its own. A residue too short to "
            "search abstains, which is the answer on a single-phase pattern (synthetic Si "
            "left no pick, SRM 660c only flagged ones). Measured on real mixtures with "
            "the largest phase subtracted, it found LaB6 first under 11-BM's cBN but no "
            "second phase in the eight IUCr CPD lab mixtures. Refine both phases together "
            "before you quote either cell. The misfit cut, one height of subtracted "
            "profile (`RESIDUE_MISFIT_RATIO`), separates misfit from true lines on two "
            "11-BM mixtures but not on the IUCr CPD lab mixtures, where it flags about 6 % "
            "of true minor-phase lines; a second phase's line under a stronger first-phase "
            "line is flagged with the misfit, scored but not driving."
        ),
    ),
    "INDEX_MULTIPLE_SOLUTIONS": HelpEntry(
        title="More than one cell passes every check",
        description=(
            "Two or more candidate lattices each satisfy the full confidence gate. The "
            "evidence does not choose between them, so no single cell is returned. "
            "Naming one would be a guess with a confidence attached. Compare their "
            "figures of merit, and their validation fits where neither cell predicts "
            "every reflection of the other (a candidate's `supercell_checks` says), since "
            "such a cell fits at least as well. Extend the 2θ range, because one "
            "high-angle reflection often separates them."
        ),
    ),
    "INDEX_NOT_VALIDATED": HelpEntry(
        title="Candidates were not checked against the pattern",
        description=(
            "No pattern was supplied, so no candidate was tested against the whole "
            "profile. The figure-of-merit panel sees only the strongest lines. It is "
            "blind to impurity peaks and to reflections a cell predicts where the "
            "pattern has none. Every candidate is capped below high confidence. Pass the "
            "data and the instrument to validate them."
        ),
    ),
    "INDEX_PANEL_REDUCED": HelpEntry(
        title="Some figures of merit are undefined",
        description=(
            "The peak list has fewer usable lines than the classical figures of merit "
            "are defined on, so some are left out of the ranking. The search still runs "
            "over the crystal systems the line count supports. Every candidate is ranked "
            "on the same remaining figures, so the order stays meaningful. Confidence is "
            "capped, and a longer peak list restores the full panel."
        ),
    ),
    "INDEX_PREDICTED_BUT_ABSENT": HelpEntry(
        title="The cell predicts lines the pattern lacks",
        description=(
            "Inside de Wolff's window (up to the 20th usable line), this lattice "
            "predicts lines that no extinction could remove where the picker's envelope "
            "shows nothing. An oversized cell does this, because it has a translation it "
            "is not using, and M₂₀ cannot see it. The code caps the grade and never "
            "refutes: a correct cell's weak general reflections below detection count "
            "too. Glides and screws are left out of the count, so a correct cell reads "
            "near 0: 0 on synthetic Si, a synthetic tetragonal set and SRM 676a "
            "corundum, 2 on the round-robin magnetite and PbSO₄, against 7 to 79 for "
            "the wrong cells tested (Si's cubic I √2·a₀ 11–12, cubic P 2a₀ 76–79); "
            "measured on those patterns, untested beyond them. Do not check it with "
            "Rwp: a converged fit of a cell that predicts every reflection of another "
            "fits at least as well (0.164 against 0.164 for a doubled cell on rietx's "
            "synthetic LaB6 pattern). Without a peak list the "
            "count is the fitted background's, over the whole range. Absences that "
            "sit only above the window are reported at info level and cap nothing. "
            "Compare the "
            "smaller cell that indexes the same lines, and run the extinction screen "
            "before you reject this one."
        ),
    ),
    "INDEX_PRIOR_USED": HelpEntry(
        title="A declared prior steered the search",
        description=(
            "You supplied a cell, a crystal system or a space group as a prior. A prior "
            "changes the order of the search and seeds one engine. Every search range "
            "stays as declared, and a prior outside the axis box is never checked. A "
            "prior-only cell is listed after the ranked cells with its grade lowered. "
            "Treat it as your hypothesis tested against the lines."
        ),
    ),
    "INDEX_SEARCH_INCOMPLETE": HelpEntry(
        title="A search did not finish its domain",
        description=(
            "An engine stopped before it exhausted its search domain. It ran out of time "
            "for a system, outgrew a size limit on its grid, or was stopped by the "
            "overall time limit. Finding no cell there is then no evidence that none "
            "exists. More time helps only when time was the cause. A size limit is eased "
            "by narrowing the search."
        ),
    ),
    "INDEX_SHIFT_ALLOWANCE": HelpEntry(
        title="Search tolerance widened for a 2θ shift",
        description=(
            "No systematic 2θ shift was measured, so the search assumed one and widened "
            "its matching window. Without that, a zero-point shift or specimen "
            "displacement can leave the true cell unindexed. The cell found in a widened "
            "window absorbs the shift. Refit the winner with a shift template and quote "
            "that cell."
        ),
    ),
    "INDEX_SHIFT_DETECTED": HelpEntry(
        title="A systematic 2θ shift follows one cause",
        description=(
            "The line positions show a systematic 2θ shift, and one physical template "
            "fits it clearly better than the others. The causes differ in how they "
            "change with angle. Folding the shift into the cell biases the cell. Correct "
            "the instrument parameter that matches the template, and carry that template "
            "into the cell refinement."
        ),
    ),
    "INDEX_SHIFT_FROM_PAIRS": HelpEntry(
        title="A 2θ shift was measured from line pairs",
        description=(
            "The size of a systematic 2θ shift was measured from pairs of harmonic "
            "reflections in the peak list, with no reference positions. That size set "
            "the search window. The pair method fixes the amplitude but cannot name the "
            "cause, because a zero-point shift and a specimen displacement look alike "
            "over a short range. A wider 2θ range separates them."
        ),
    ),
    "INDEX_SHIFT_MODEL_AMBIGUOUS": HelpEntry(
        title="A 2θ shift is present, cause unclear",
        description=(
            "The pattern shows a systematic 2θ shift, but the candidate causes fit about "
            "equally well over this range. The size of the shift is measured. Its cause "
            "is unidentified, so do not correct an instrument fault from these data. The "
            "cell is safe to within the spread between the competing templates. Measure "
            "to higher angle, where they separate."
        ),
    ),
    "INDEX_SINGLE_ENGINE": HelpEntry(
        title="Only one indexing engine ran",
        description=(
            "Confidence in an indexed cell comes from independent engines agreeing on "
            "it. With one engine, every candidate grades low by construction. Low here "
            "means unconfirmed and says nothing against the cell. Run the default engine "
            "set to get a graded answer. A single-engine run is a probe."
        ),
    ),
    "INDEX_SUPERCELL_REFUTED": HelpEntry(
        title="A smaller cell explains the same lines",
        description=(
            "This lattice is a superlattice of a higher-ranked candidate. The extra "
            "lines it predicts, which no extinction could remove, are seen no more often "
            "than chance would place them. So it ranks below the smaller cell. A real "
            "superstructure with extra lines too weak to pick escapes this test. Check "
            "the pattern at the listed positions if the chemistry suggests one. "
            "Measured: it refutes Si's cubic I √2·a₀ (0 of 12 extra lines seen) and "
            "kept every truth tested as a child, the lowest at p = 0.0072; on the "
            "finished acceptance searches it put brucite's and 11-BM NAC's truths "
            "first. Untested beyond those patterns. A cell whose own lines are seen more "
            "often than the smaller cell's is never refuted: an oversized cell cannot "
            "do that. On dense low-symmetry patterns chance alone covers most of the "
            "range, and three synthetic truths were refuted before this rule."
        ),
    ),
    "INDEX_SYSTEMS_NOT_COVERED": HelpEntry(
        title="Some crystal systems were not searched",
        description=(
            "The search covered only some crystal systems. A failure to find a cell "
            "means only that none was found in those systems. It says nothing about the "
            "specimen, and it is no evidence of a mixture. Search the missing systems "
            "before you draw a conclusion."
        ),
    ),
    "INDEX_VALIDATION_FAILED": HelpEntry(
        title="The validation fit of a candidate failed",
        description=(
            "The whole-pattern fit that validates this candidate raised an "
            "error, so nothing was measured for it. The candidate is neither supported "
            "nor refuted. A mis-declared instrument profile, or a wavelength on an "
            "absorption edge, fails every candidate alike. Check those first."
        ),
    ),
    "INDEX_VOLUME_UNPHYSICAL": HelpEntry(
        title="Cell volume outside what the data support",
        description=(
            "The cell volume is either below the exclusion volume of a single atom, or "
            "well above the envelope that the number of observed lines can support. The "
            "first is an artefact of the search and describes no lattice. The second is "
            "a cell larger than the lines can justify. Narrow the maximum volume, or "
            "measure more lines."
        ),
    ),
    "INDEX_Z_NOT_INTEGER": HelpEntry(
        title="Cell holds a fractional number of formula units",
        description=(
            "With the formula you gave and typical atomic volumes, the cell holds a "
            "number of formula units far from a whole number. A sub- or supercell of the "
            "true cell does this. So does a formula that misses a solvent or "
            "counter-ion, and so does an ionic specimen, where volumes run large. A "
            "correct cell can fire occasionally. Check the formula first and weigh the "
            "result beside the figures of merit."
        ),
    ),
    "K_VECTOR_UNSEPARATED": HelpEntry(
        title="Two propagation vectors fit equally well",
        description=(
            "The two best candidate propagation vectors differ in fit quality by less "
            "than the gap that counts as a tie. Fit quality is ΔBIC against the nuclear "
            "fit, counting N/f² observations: N fitted points and f the Bérar-Lelann "
            "factor, since neighbouring points of one peak share their misfit. The data "
            "do not choose between them, so the winner is not established. Treat both as "
            "open. Look for reflections that one vector predicts and the other does not."
        ),
    ),
    "LANDE_G_ASSUMED": HelpEntry(
        title="Landé g taken from the free ion",
        description=(
            "The file gives no Landé g, and the assumed magnetic ion needs one. The "
            "package used the Hund's-rule value for the free ion. The magnetic form "
            "factor of a rare-earth or actinide ion depends on g, so a different value "
            "changes the calculated intensities and the refined moment. State g for the "
            "site if you know the value in the compound."
        ),
    ),
    "LAUE_CLASS_NOT_SEPARABLE": HelpEntry(
        title="The leading class spans more than one Laue class",
        description=(
            "The space groups the leading extinction class admits fall in more than one "
            "Laue class. They share every position and absence and differ only in which "
            "reflections are equivalent, which sets the intensity partition inside "
            "overlapped multiplets. A powder pattern does not expose that. Carry one "
            "structure solution per Laue class, not one per group."
        ),
    ),
    "LEBAIL_ALTERNATION_STOPPED": HelpEntry(
        title="The Le Bail passes stopped",
        description=(
            "A Le Bail fit alternates between extracting intensities and refining the "
            "other parameters. The alternation stops at a fixed point when Rwp no longer "
            "falls. If a pass raised Rwp, or the pass limit arrived while Rwp was still "
            "falling, the answer depends on the starting state. The kept pass is the "
            "best one. Check the cell and the background, or allow more passes."
        ),
    ),
    "LOW_ANGLE_UNMODELLED": HelpEntry(
        title="Unexplained signal below the first reflection",
        description=(
            "The region below the first reflection has a larger residual than the rest "
            "of the pattern. No reflection can explain it, so either the background is "
            "wrong there or the data are not usable there. Raise the lower limit of the "
            "pattern to where the residual settles, or add the air-scatter term to the "
            "background. The two remedies answer different causes, so the package does "
            "not choose between them."
        ),
    ),
    "MAGNETIC_ION_ASSUMED": HelpEntry(
        title="Magnetic ion chosen by the package",
        description=(
            "The file states no ion for a site whose element has no neutral-atom "
            "magnetic form factor in the tables. The package took the most common "
            "magnetic oxidation state of that element. The form factor depends on the "
            "ion, so a moment refined under the wrong one absorbs the difference into "
            "its size. State the ion for the site to override the default."
        ),
    ),
    "MAGNETIC_SUBGROUP_PREFERRED": HelpEntry(
        title="A subgroup fits better than the winner",
        description=(
            "After the ranking chose a winner, a maximal magnetic subgroup of it was "
            "refitted from the winner's solution. It fitted better by more than the tie "
            "width, in ΔBIC counting N/f² observations (N fitted points, f the winner's "
            "Bérar-Lelann factor). The ranking had not treated the subgroup as a "
            "competitor, so the "
            "ranked list is unchanged. The data prefer the lower symmetry, and you "
            "choose between the two by hand."
        ),
    ),
    "MAGNETIC_WIDTH_MOVED_MOMENT": HelpEntry(
        title="Magnetic broadening changed the refined moment",
        description=(
            "Freeing the magnetic broadening moved the refined moment by more than its "
            "esd. The width is therefore correlated with the moment, even if its own esd "
            "looks large. Holding it at zero puts the moment back where it was, with the "
            "bias the width removes. Quote the moment from the stage that freed the "
            "width. Give the width as an upper bound and not as a coherence length."
        ),
    ),
    "MAGNETIC_WIDTH_UNMEASURED": HelpEntry(
        title="Magnetic broadening not measured",
        description=(
            "A freed magnetic broadening term came back with too little support to "
            "quote, or with no error estimate. Such a term can be separated only where "
            "the ratio of magnetic to nuclear intensity changes from one reflection to "
            "the next, for example in satellites with no nuclear counterpart. Elsewhere "
            "it is not a coherence length. A correlated width can still move the moment, "
            "so check whether releasing it changed the moment before you drop it."
        ),
    ),
    "MAGNETIC_WIDTH_UNMODELLED": HelpEntry(
        title="Magnetic peaks too narrow, moment lowered",
        description=(
            "The residual under the magnetic reflections is negative at the peak centres "
            "and positive in both tails, and the nuclear-only reflections do not show "
            "it. The calculated magnetic peaks are narrower than the observed ones. The "
            "fit compensates by lowering the moment, so the refined moment is biased "
            "low. Free the magnetic broadening with `plan=\"magnetic_width\"` and refit."
        ),
    ),
    "MICROABSORPTION_SKIPPED": HelpEntry(
        title="Microabsorption correction not applied",
        description=(
            "A particle radius was given for at least one phase, but the correction "
            "could not run. Typical causes are a phase with no radius, no wavelength, or "
            "no attenuation table for the source, or a phase with no weight fraction "
            "(no reflection in range, or a scale a stage held), which the mixture's mean "
            "attenuation needs. Without the correction the fractions of strong and weak "
            "absorbers are biased. Supply a radius for every phase from microscopy or "
            "particle-size analysis, and not from peak broadening; for an unmeasured phase, "
            "reach one of its reflections or remove it."
        ),
    ),
    "MODEL_FAR_FROM_DATA": HelpEntry(
        title="The model does not describe the data",
        description=(
            "Rwp is so high that the model does no better than one that predicts no "
            "intensity. This is a mismatch between model and data. The optimiser can "
            "still report convergence, because a zero phase scale is a minimum once the "
            "peaks sit far from the data. Do not read the parameters or their esds. "
            "Check the cell, the wavelength, the zero shift and the 2θ range. Re-index "
            "if the cell is in doubt."
        ),
    ),
    "MOMENT_ANGLE_STATIONARY": HelpEntry(
        title="Moment direction sits on a symmetry direction",
        description=(
            "A moment angle finished at a direction that the site symmetry fixes. The "
            "pattern is even in that angle there, so its slope is zero and an error "
            "estimate read from it would depend on where the solver stopped. A test "
            "showed that moving the angle onto the symmetry direction costs no more than "
            "noise allows. The angle then leaves the error calculation, so the other "
            "estimates no longer depend on where the solver stopped. In place of an "
            "error estimate, a single-pattern fit computes the angle's profile interval "
            "and stores it in `RefinedParameter.interval`. The message gives the angle's "
            "distance from "
            "the direction and whether the interval includes it. Where it does, quote "
            "the moment as lying along the symmetry direction. Where it does not, quote "
            "the angle with its interval."
        ),
    ),
    "MOMENT_PAIR_DEGENERATE": HelpEntry(
        title="Two moments cannot be told apart",
        description=(
            "A powder pattern cannot always separate the sizes of two moments. These two "
            "are almost fully correlated, so only the quadrature sum of their sizes is "
            "measured. Each size alone is an artefact of the correlation. Quote the "
            "combined value with its error, or add a constraint that the physics "
            "justifies."
        ),
    ),
    "NEUTRON_RESONANT_ABSORBER": HelpEntry(
        title="A neutron resonant absorber is in the structure",
        description=(
            "The structure contains an element whose scattering length is complex and "
            "varies with wavelength near a nuclear resonance. The table carries only the "
            "real thermal value. Away from the resonance that value is right. Near it, "
            "both the amplitude and the phase of the element's contribution are wrong, "
            "and no agreement index shows it. Check your wavelength against the "
            "resonance before you quote an occupancy or displacement parameter on that "
            "site."
        ),
    ),
    "OCCUPANCY_ABOVE_ONE": HelpEntry(
        title="Occupancy refined above a full site",
        description=(
            "A refined site occupancy is above 1, so the model puts more scatterers on "
            "the site than it holds. An occupancy has no default upper bound, so the "
            "fit was free to go there. This is expected when the occupancy stands in "
            "for site scattering: a mixed Fe-Mg site declared as Mg reads about 2.2 at "
            "full Fe. Otherwise it usually means a wrong species, a wrong site "
            "multiplicity, or a displacement parameter pulling the other way, because "
            "the two compete for the same intensity. The fit is not changed."
        ),
    ),
    "ORIGIN_FIXED_ON_POLAR_AXIS": HelpEntry(
        title="A floating origin was fixed",
        description=(
            "The space group has an axis along which shifting every atom changes no "
            "intensity, so the data cannot fix the position along it. The package fixed "
            "it by holding one atom's coordinate or by restraining the weighted centroid "
            "of the sites. The other coordinates along that axis are quoted relative to "
            "that choice. A held coordinate has no esd. Release the hold only if you "
            "accept a flat direction in the fit."
        ),
    ),
    "ORIGIN_NOT_FIXED": HelpEntry(
        title="A floating origin could not be fixed",
        description=(
            "The space group has an axis along which the whole structure can slide "
            "without changing any intensity. The package could not hold an origin there, "
            "because no atom has a free coordinate that a shift along the axis moves. "
            "The fit keeps a flat direction. The coordinates along that axis are not "
            "measurements. Hold what the tied coordinates follow, or tie one of them to "
            "a constant."
        ),
    ),
    "PARAMETRIC_FORM_REJECTED": HelpEntry(
        title="A parametric equation does not fit its target",
        description=(
            "The equation that sets a parameter across the patterns of a joint fit "
            "leaves a misfit that freeing the parameter in each pattern would remove. "
            "Several equations can also be rejected together when none is rejected "
            "alone. The esds of the coefficients assume the form is right, so they are "
            "too small. Add the next term to the basis, or narrow the subset to where "
            "the form holds."
        ),
    ),
    "PARAMETRIC_OUT_OF_RANGE": HelpEntry(
        title="An equation put a parameter outside its bounds",
        description=(
            "A parametric equation sets a parameter, in some patterns, to a value "
            "outside that parameter's own limits. The equation's coefficients are "
            "unbounded, so the limits never constrained the solve. Do not quote the "
            "parameter there as a measurement. Narrow the subset to where the form "
            "holds, lower the order of the polynomial, or use a basis that stays inside "
            "the range."
        ),
    ),
    "PARAMETRIC_TARGET_UNSEEN": HelpEntry(
        title="Equation sets a parameter in unseen patterns",
        description=(
            "In some patterns the phase that a parametric equation controls is too weak "
            "or absent to be seen. There the parameter's value and esd come from the "
            "equation and not from the data. The test of the form cannot check the "
            "equation in those patterns. Quote the equation's coefficients. If the "
            "equation should hold only where it is measured, narrow the subset to the "
            "patterns that see the phase."
        ),
    ),
    "PATTERN_DEAD_CHANNELS": HelpEntry(
        title="A run of channels measured nothing",
        description=(
            "A short run of channels reads far below the local background, and its error "
            "bars shrank with it. This is the signature of a dead or masked detector "
            "cell. Weights go as one over the squared error, so those channels outvote "
            "live ones and pull the background down to meet them. Exclude the interval "
            "before you fit."
        ),
    ),
    "PATTERN_DUPLICATE_POINTS": HelpEntry(
        title="Repeated points were dropped",
        description=(
            "The file lists some positions twice with the same intensity, and the reader "
            "kept one of each pair. This is a file artefact and loses no information. "
            "The point count after the read is lower than the number of lines in the "
            "file. A repeat with a different intensity stops the read instead."
        ),
    ),
    "PATTERN_INTENSITY_NET": HelpEntry(
        title="The intensities are the file's net column",
        description=(
            "The pdCIF held no gross intensity column, so the reader took "
            "`_pd_proc_intensity_net`, which the pdCIF dictionary defines as the values "
            "after background subtraction. The numbers are used as the file states them. "
            "Whether a background still needs refining is your call, and the next "
            "diagnostic says when the column contradicts its label."
        ),
    ),
    "PATTERN_INTENSITY_SCALED": HelpEntry(
        title="The intensity scale could not be established",
        description=(
            "The file does not settle whether its intensities are raw counts or a rate "
            "already divided by a counting time. No esds were supplied, so the weights "
            "fall back to Poisson statistics. Those suit counts and are wrong by the "
            "square root of the counting time for a rate. The fit runs, but quote no "
            "esds or χ² from it unless you re-export in counts or supply the esds."
        ),
    ),
    "PATTERN_MULTISCAN_DEFAULTED": HelpEntry(
        title="Only the first of several scans was read",
        description=(
            "The file holds more than one scan and you chose none, so the reader took "
            "the first. The others are not in the pattern, and a fit to it describes one "
            "measurement of several. Pass `scan=` to choose, or list the scans first to "
            "see what each one is."
        ),
    ),
    "PATTERN_NET_HAS_BACKGROUND": HelpEntry(
        title="A net intensity column still carries background",
        description=(
            "The file's `_pd_proc_intensity_net` column is labelled background-subtracted "
            "but never comes within 5σ of zero. Either a background was left in, or the "
            "fitted range holds no empty baseline; the data cannot say which. The reader "
            "leaves the numbers as they are, and the code's value is the "
            "column's smallest y/σ. Tell the readings apart first: compare y with "
            "y − `_pd_proc_intensity_bkg_calc` where the file states one, and look for an "
            "empty stretch of baseline. If a background was left in, hold that curve "
            "additively (`BackgroundFixedPlusChebyshev`) when y − it reaches zero, "
            "otherwise refine a Chebyshev background, with a hump component for a broad "
            "amorphous or capillary hump. The 5σ "
            "threshold was measured on four unrelated deposits labelled net (a "
            "synchrotron capillary, a laboratory Stoe Stadi-P, a laboratory "
            "PANalytical MPD Pro and a neutron powder pattern), whose smallest y/σ run "
            "from 14 to about 6 000, against a synthetic zero baseline. It misfires "
            "on a subtracted pattern windowed onto a peak cluster with no empty "
            "baseline in range."
        ),
    ),
    "PATTERN_ROWS_DROPPED": HelpEntry(
        title="Some numeric rows were not read as data",
        description=(
            "The reader takes the most common number of values per line as the file's "
            "layout, and it skipped numeric lines with a different count. A header table "
            "or a limits row usually causes this. If a skipped line was a real "
            "measurement, the file mixes layouts. Re-export it with the same number of "
            "values on every row."
        ),
    ),
    "PATTERN_SCAN_REVERSED": HelpEntry(
        title="The scan was stored in descending order",
        description=(
            "The file stores its points from the highest value to the lowest, and the "
            "reader reversed them. This is the same measurement written backwards, so "
            "nothing is lost. A point's position in the file no longer matches its "
            "position in the pattern."
        ),
    ),
    "PATTERN_SIGMA_CONSTANT": HelpEntry(
        title="Every point has the same error estimate",
        description=(
            "The error estimate is identical on every point, so every point gets equal "
            "weight and the fit is unweighted. The reader kept the values, because a "
            "uniform error is legal. Goodness of fit and χ² mean something only if every "
            "point has that error. A placeholder in the error field is the usual cause."
        ),
    ),
    "PATTERN_TOTAL_SCATTERING": HelpEntry(
        title="The file holds a total-scattering function, not a pattern",
        description=(
            "The file holds a reduced total-scattering function: G(r), the pair "
            "distribution function on a real-space axis r in Å, or S(Q) or F(Q) on "
            "a scattering-vector axis Q in Å⁻¹. Neither axis is 2θ. rietx does not "
            "read total-scattering data yet (issue #192), so the file is refused "
            "rather than read as a powder pattern, which would fit a Bragg model to "
            "it and report a plausible Rwp. The file is recognised by its own "
            "column labels (an #L line naming r and G, or Q and S or F), by a "
            "PDFgetX2 or PDFgetX3 header, or, with neither, by a .gr, .sq or .fq "
            "suffix alone; the message says which. Refine the diffraction pattern "
            "the reduction started from instead. A 2θ scan that only carries one of "
            "those suffixes opens under any other name."
        ),
    ),
    "PATTERN_UNDERSAMPLED": HelpEntry(
        title="Too few steps across each peak",
        description=(
            "The typical peak is covered by too few measured points across its width. "
            "The intensities were not sampled finely enough, and nothing done after the "
            "measurement recovers them. Integrated intensities, displacement parameters "
            "and phase fractions can all be affected. The fit still runs. Measure again "
            "with a smaller step."
        ),
    ),
    "PATTERN_WEIGHT_UNUSABLE": HelpEntry(
        title="A pdCIF weight column could not give σ",
        description=(
            "The file's `_pd_proc_ls_weight` column holds a negative entry, a missing "
            "one (`?` or `.`) or no positive entry, so it cannot be read as w = 1/σ². "
            "The reader fell back to the Poisson σ = √max(y, 1), as it does for a file "
            "with no weights, and did not repair the column: it drops the whole column, "
            "not only the bad entries, even where most weights are positive. The message "
            "counts the negative and the missing entries separately; the code's value is "
            "their sum (0 when the column holds no positive weight and no bad entry). "
            "If the file's counting time varies across the scan, the Poisson σ is not "
            "the deposit's; quote χ² and esds accordingly, or supply σ yourself."
        ),
    ),
    "PATTERN_X_AXIS_ASSUMED": HelpEntry(
        title="The scan axis was assumed to be 2θ",
        description=(
            "The file does not state its scan axis in a form the reader recognises, so "
            "the x values were read as 2θ in degrees. Another axis read this way parses "
            "without error and refines to a cell that is wrong by a factor or a "
            "geometry. Check the axis in the file or the instrument software before you "
            "trust the cell."
        ),
    ),
    "PATTERN_X_AXIS_IMPLAUSIBLE": HelpEntry(
        title="The axis reaches 0° or below",
        description=(
            "The x axis starts at or below 0°, where no Bragg reflection lies. Points "
            "there may be the direct beam, the far side of the detector or a header row "
            "read as data. The reader kept them. Check that the axis is 2θ in degrees, "
            "and exclude the interval before you fit."
        ),
    ),
    "PATTERN_ZERO_WEIGHT_EXCLUDED": HelpEntry(
        title="Zero-weight points became excluded regions",
        description=(
            "The pdCIF dictionary defines a `_pd_proc_ls_weight` of zero as a data point "
            "not used for refinement. The reader turned each run of such points into an "
            "excluded region, so the fit leaves out exactly the points the file's author "
            "left out, and every other point keeps σ = 1/√w. The code's value is the "
            "number of points excluded. Their σ is the Poisson value, a placeholder the "
            "fit never reads; remove a region from `excluded_regions` only if you mean "
            "to fit those points."
        ),
    ),
    "PAWLEY_OFF_DATA_RIDGED": HelpEntry(
        title="Pawley intensities taken from the restraint",
        description=(
            "Some reflections have no emission line centred inside the fitted data. They "
            "stay in the list so that a stage can move them onto the data. A restraint "
            "pulls their intensities towards zero, so the value and its esd come from "
            "the restraint and not from the data. Do not export or use these "
            "intensities. Widen the fitted range if you need them."
        ),
    ),
    "PAWLEY_OVERLAP_UNRESOLVED": HelpEntry(
        title="Overlapping Pawley reflections cannot be split",
        description=(
            "Several reflections overlap so strongly that the data fix their summed "
            "intensity but not how it divides among them. At least one individual "
            "intensity has a large relative esd. The split shown comes from the "
            "equal-split restraint. Use the summed intensity of the group as the datum. "
            "Individual values from the group are not measurements."
        ),
    ),
    "PEAK_POSITION_AT_BOUND": HelpEntry(
        title="Positions pressed against their bound",
        description=(
            "Components whose fitted position ran into its bound, half the "
            "group's seed FWHM from where detection or a re-seed put it. "
            "The reported position is the bound's: the fit stopped on its "
            "bound, and its uncertainty is the curvature there, which leaves "
            "out how far past the bound the fit would have moved. Each "
            "entry gives the bound in degrees and the component's intensity "
            "over its esd. The value counts those still usable above the "
            "false-discovery bar."
        ),
    ),
    "PEAK_NO_INTENSITY": HelpEntry(
        title="Components with no intensity",
        description=(
            "Components excluded from usable() and kept in the peak list so a "
            "report can say why. Three causes, and each entry says which: the "
            "fit's intensity is on its zero bound, it is under one esd, or "
            "the caller marked it by hand whatever its intensity. On the "
            "zero bound the position and its esd are not measurements; "
            "whether a position under one esd is worth indexing on is a "
            "reading of PEAK_NO_INTENSITY_SIGMA."
        ),
    ),
    "PEAK_ASYMMETRY_UNMODELLED": HelpEntry(
        title="Asymmetry the peak shape does not carry",
        description=(
            "Lines show asymmetric residuals beyond the fitted shape, so their positions "
            "are pulled towards the tail. Declaring the axial divergence terms is the "
            "usual fix."
        ),
        anchor="theory/profiles.html#finger-cox-jephcoat-axial-divergence",
    ),
    "PEAK_AXIAL_TAIL": HelpEntry(
        title="Weak lines that may be axial tails",
        description=(
            "Weak components lie within 3.5 FWHM of a stronger group-mate on the side "
            "axial divergence points. They may be real lines and are reported rather "
            "than removed."
        ),
        anchor="theory/profiles.html#finger-cox-jephcoat-axial-divergence",
    ),
    "PEAK_CONTAMINATION_LINE": HelpEntry(
        title="Contamination lines excluded",
        description=(
            "Several strong reflections carry a line at their Kβ or tungsten position at "
            "one common ratio, so the beam is leaking that line and those lines were "
            "excluded. The peak list carries the flag and not the size of the leak. For "
            "that, run `background.diagnose(data, wavelength=...)` and read "
            "`ContaminationFlag.leak_ratio`: an unfiltered tube sits near 0.14, and a "
            "filter or monochromator only cuts it. They are excluded and never stripped, "
            "because stripping redistributes the counting noise."
        ),
        anchor="theory/peak-positions.html#wavelength-scales",
    ),
    "PEAK_EXPECTED_FALSE_LINES": HelpEntry(
        title="How many kept lines are expected to be noise",
        description=(
            "The pattern's own false-discovery bar on each component's intensity over "
            "its esd, and the expected number of noise lines among those kept, a lower "
            "bound, since detection selected every component first. Components under the "
            "bar are flagged weak and stay usable. A component that absorbs a shape or "
            "background misfit carries real intensity and is not reached."
        ),
    ),
    "PEAK_KALPHA2_ALIAS": HelpEntry(
        title="Kα2 candidates dropped before fitting",
        description=(
            "Detection found candidates at the Kα2 positions of stronger lines and "
            "dropped them before any fit. The drop is reported because a genuine weak "
            "line can alias onto one."
        ),
        anchor="theory/peak-positions.html#wavelength-scales",
    ),
    "PEAK_KALPHA2_RESIDUAL": HelpEntry(
        title="Components on a modelled Kα2 maximum",
        description=(
            "Components sit where the Kα2 partner of a stronger line is already "
            "modelled, so they are that doublet's residual rather than new lines. "
            "Reported rather than removed."
        ),
        anchor="theory/peak-positions.html#wavelength-scales",
    ),
    "PEAK_LIST_TOO_SHORT": HelpEntry(
        title="Too few usable lines to index",
        description=(
            "The list has fewer usable lines than an indexing search needs. The "
            "classical figures of merit are also undefined below that count, which caps "
            "confidence rather than refuting any cell. Widen the 2θ range, count for "
            "longer, or lower the detection threshold and check what arrives."
        ),
        anchor="reference/peaks.html#enough-lines-and-precise-enough",
    ),
    "PEAK_NOT_SEPARABLE": HelpEntry(
        title="Components refuted as distinct lines",
        description=(
            "Components improved their group's fit but did not survive the nested "
            "comparison against a fit without them. They stay in the model and are "
            "withheld from indexing."
        ),
    ),
    "PEAK_POSITION_PRECISION": HelpEntry(
        title="Position precision relative to the line spacing",
        description=(
            "States the measured position precision against what an indexing search "
            "needs. A cell search matches within an assumed systematic allowance rather "
            "than within σ, so this is context for reading a search result, not a "
            "refusal."
        ),
        anchor="reference/peaks.html#enough-lines-and-precise-enough",
    ),
    "PEAK_SHOULDER_SEEDED": HelpEntry(
        title="Extra components seeded from the residual",
        description=(
            "The width census found groups wider than the instrument's own law allows, "
            "so extra components were seeded into them from the residual. Check that the "
            "added lines are real before indexing on them."
        ),
    ),
    "PEAK_SIGMA_ASSUMED": HelpEntry(
        title="Position uncertainties were assumed",
        description=(
            "Some or all lines carry an assumed σ(2θ) rather than a fitted one, which is "
            "what a list of bare positions produces. Downstream gates treat the "
            "precision as unmeasured."
        ),
    ),
    "PEAK_UNRESOLVED_SHOULDER": HelpEntry(
        title="Components that never separated",
        description=(
            "Lines were kept in groups where they stayed within half a FWHM of a "
            "neighbour. Their positions are correlated with their neighbours' and are "
            "less precise than their σ alone suggests."
        ),
    ),
    "PEAK_UNRESOLVED_SPLIT": HelpEntry(
        title="Splits reported as one line",
        description=(
            "Pairs of comparable components closer than two lines of the fitted shape "
            "can be and still show a dip. Each pair is reported as one line whose "
            "position uncertainty reaches both."
        ),
    ),
    "PEAK_WIDTH_CAPPED": HelpEntry(
        title="Components broader than the width law allows",
        description=(
            "Components whose width ran into five times the pattern's own width law. "
            "They are humps rather than lines and are withheld from indexing."
        ),
    ),
    "PEAK_WIDTH_LAW_MISMATCH": HelpEntry(
        title="Fitted widths disagree with the instrument",
        description=(
            "The fitted widths do not follow the declared instrumental width law. Either "
            "the specimen is broadened, which is a finding, or the declared instrument "
            "is wrong, which is a setup error. The message carries the ratio so the two "
            "can be told apart. On a refinement the census is compared with the fitted "
            "widths, size and strain included, so it fires only when no phase's widths "
            "came within the factor. A phase the data cannot see is left out of that "
            "comparison."
        ),
        anchor="theory/profiles.html#the-instrument-sample-width-split",
    ),
    "PHASE_HELD_IN_PATTERNS": HelpEntry(
        title="A phase was held in some patterns of a joint fit",
        description=(
            "In a joint fit where a phase's structure or scale is per pattern, the "
            "last stage held them in the patterns that cannot see the phase. The "
            "message counts those patterns, and the held rows are named in where. In "
            "those patterns the structure rows keep the values the stage started from "
            "and carry no esd, and a held scale keeps the value handed in, so the "
            "pattern measures no fraction of the phase. The patterns that see the "
            "phase refine their own. This "
            "records what the fit did and asks for nothing. PHASE_UNCONSTRAINED "
            "covers a phase that no pattern sees."
        ),
    ),
    "PHASE_UNCONSTRAINED": HelpEntry(
        title="The data cannot see this phase",
        description=(
            "The scale of a phase is too close to zero for the data to tell it from an "
            "absent phase, or none of its reflections lie in the fitted range. Its other "
            "parameters were then either refined against nothing or held at the values "
            "you supplied. Neither kind of value is a result. Either the phase is not in "
            "the specimen and belongs out of the model, or the range must cover a "
            "reflection of it. With no reflection in range, the scale is held too, the "
            "phase has no weight fraction, and the other fractions are relative to the "
            "phases seen in range."
        ),
    ),
    "QPA_ESD_UNAVAILABLE": HelpEntry(
        title="No weight fraction has an esd",
        description=(
            "A phase scale refined to a value at which its uncertainty could not be "
            "measured, usually zero. Every weight fraction divides by a sum that "
            "includes that scale, so none of them has an esd. A scale at zero usually "
            "means the phase is not in the specimen. Remove the phase to give the other "
            "fractions their esds. A profile interval gives an admissible range for one "
            "fraction."
        ),
    ),
    "QPA_FRACTION_RANGE": HelpEntry(
        title="Weight fractions a width profile admits",
        description=(
            "Pinning the phase's peak width at each width on a grid and refitting "
            "gives the weight fractions the data admit at a statistically acceptable "
            "fit. The value is how far the farthest of them lies from the fit's "
            "fraction, in units of the 95 % interval of the fit's own esd. Below 1, "
            "the profile confirms the esd. Well above 1, the esd describes only the "
            "minimum where the fit stopped: the scale of a weak phase trades against "
            "its width, and the data do not choose. Then quote the range and the "
            "widths that produced it. A width the specimen justifies, a background "
            "that takes the broad hump, or longer counting can narrow the range."
        ),
    ),
    "QPA_UNAVAILABLE": HelpEntry(
        title="Weight fractions cannot be formed",
        description=(
            "The refined scales, weighted by the cell contents, sum to zero or less, so "
            "there is nothing to normalise into weight fractions. An empty result says "
            "nothing about the composition. A phase scale at zero means that phase "
            "contributed no intensity. Check whether the phase belongs in the model, and "
            "whether its starting cell put its peaks where the data have none."
        ),
    ),
    "RAS_ATTENUATOR_PRESENT": HelpEntry(
        title="An attenuator factor was found and not applied",
        description=(
            "The Rigaku file carries an attenuator factor that differs from one over "
            "some points. No specification says whether the stored intensity already "
            "includes it, and applying it twice or not at all are both wrong. The reader "
            "left the intensities alone. Esds are affected too, so check the export "
            "against the instrument software before you trust the relative heights of "
            "those points."
        ),
    ),
    "READER_OPTION_IGNORED": HelpEntry(
        title="A reader option does not apply here",
        description=(
            "You passed an option that the format of this file does not take, so the "
            "file was read as if you had not given it. That is normal when a form "
            "carries a value across a change of file. It matters when you meant to "
            "select a scan or a data block. Check which reader claimed the file."
        ),
    ),
    "RECIPE_BACKGROUND_PEAK_DEGENERATE": HelpEntry(
        title="A background peak spans the whole fit range",
        description=(
            "The recipe declares a background peak whose width reaches the fitted range, "
            "so it never falls to half height inside the window. It then carries no "
            "curvature that the polynomial background lacks. Expect the two to correlate "
            "almost completely, and the stage to spend its budget on that valley. Use a "
            "peak or extra polynomial terms, not both."
        ),
    ),
    "RECIPE_BACKGROUND_RESEEDED": HelpEntry(
        title="Background coefficients restart from zero",
        description=(
            "The recipe's Chebyshev coefficients were not carried over. Only their count "
            "and refine flag were. The two programs scale the polynomial's domain "
            "differently, so the numbers would describe a different curve here. The "
            "coefficients start at zero and refine."
        ),
    ),
    "RECIPE_BOUND_HONOURED": HelpEntry(
        title="A recipe limit was applied",
        description=(
            "The recipe states a minimum or maximum for a parameter. The recipe format's "
            "own documentation says GSAS-II does not apply these, and this refinement "
            "does. A parameter that finishes on one of these limits is a difference from "
            "the reference engine and not a fault in the translation."
        ),
    ),
    "RECIPE_CONVENTION_ASSUMED": HelpEntry(
        title="A combined divergence value was halved",
        description=(
            "The recipe states axial divergence as one combined number, and this package "
            "holds two. The number was halved between them, the symmetric reading. No "
            "recipe available can tell that apart from an uneven split, so treat the two "
            "values as assumed and not measured."
        ),
    ),
    "RECIPE_DISPERSION_DECLINED": HelpEntry(
        title="Anomalous scattering was switched off",
        description=(
            "The recipe's wavelength lies outside the energy range of the bundled "
            "dispersion table, so the correction was turned off and the scattering "
            "factors keep their base values. The absorption edges of the elements "
            "involved sit far below such energies, so the correction would be "
            "negligible. The result is flagged as fitted with dispersion neglected."
        ),
    ),
    "RECIPE_ENGINE_DEFAULT_DECLINED": HelpEntry(
        title="A null broadening value was read as zero",
        description=(
            "The recipe includes a size or strain block but leaves its magnitude empty. "
            "GSAS-II fills that with its own project default, and this package reads it "
            "as no broadening. The instrument terms will differ from the reference "
            "engine's by however much that default contributed. If the block is flagged "
            "for refinement, give it a non-zero start."
        ),
    ),
    "RECIPE_FIELD_DROPPED": HelpEntry(
        title="A recipe field has no counterpart here",
        description=(
            "The recipe holds a field that this package has no place for, so it was left "
            "out. Examples are a constant Lorentzian width term at zero, a refinement "
            "cycle count and the choice of solver. The fit runs without it. Compare "
            "against the reference engine with that difference in mind."
        ),
    ),
    "RECIPE_FIT_RANGE_CHANNELS": HelpEntry(
        title="The fit range became a channel set",
        description=(
            "A recipe states its fit range as two angles, while an engine fits channels, "
            "and the two can disagree by a channel at the edges. The count in the "
            "message is what this package fits, using an inclusive mask at both ends. "
            "Check it against the reference engine's count before you compare any Rwp."
        ),
    ),
    "RECIPE_FLAG_DROPPED": HelpEntry(
        title="A recipe refine flag was not honoured",
        description=(
            "The recipe flags a parameter for refinement that has no counterpart here, "
            "or that would sit at its off state. The flag was not applied, so this fit "
            "has fewer free parameters than the reference engine's, and what the "
            "parameter would have absorbed lands in its neighbours. Keep that in mind "
            "when you compare esds and χ²."
        ),
    ),
    "RECIPE_FLAG_TRANSLATED": HelpEntry(
        title="A mixing parameter became two coefficients",
        description=(
            "GSAS-II describes a broadening effect with a magnitude and a Lorentzian "
            "share. This package has no share, only separate Lorentzian and Gaussian "
            "coefficients, so a freed share became two free coefficients. They hold the "
            "same two free directions under different names. Look for those two in the "
            "result."
        ),
    ),
    "RECIPE_NOTHING_REFINED": HelpEntry(
        title="The recipe flags no parameter for refinement",
        description=(
            "No parameter in the recipe is marked as refinable, so the plan frees "
            "nothing. The run evaluates the model at its declared values. That is a "
            "simulation. Read its agreement statistics as a comparison of the declared "
            "model with the data and not as a fit."
        ),
    ),
    "RECIPE_PLAN_STAGED": HelpEntry(
        title="Flagged parameters are freed in stages",
        description=(
            "A recipe says which parameters refine and gives no order. This package "
            "frees them over several stages in the standard turn-on order, and each "
            "stage keeps what the earlier ones freed. The last stage refines the full "
            "flagged set, as the recipe asks. Freeing everything in one step can send a "
            "cell far from the answer."
        ),
    ),
    "RECIPE_SCALE_RESEEDED": HelpEntry(
        title="Phase scales were re-seeded from the data",
        description=(
            "A scale factor's normalisation belongs to each program, so the recipe's "
            "value cannot be carried across. The scales were set so that the calculated "
            "intensity matches the data in total, and then refined. Do not compare a "
            "scale with the recipe's number or with another engine's."
        ),
    ),
    "RECIPE_SCHEMA_UNTESTED": HelpEntry(
        title="The recipe version has not been tested",
        description=(
            "The recipe declares a schema version that this reader was not checked "
            "against. It was read anyway, because the format allows extra fields. A "
            "field whose meaning changed between versions is read with its old meaning. "
            "Check the values that matter against the program that wrote the recipe."
        ),
    ),
    "RECIPE_ZERO_WEIGHT_EXCLUDED": HelpEntry(
        title="Zero-weight channels became excluded regions",
        description=(
            "A recipe excludes a point by giving it zero weight, and that has no finite "
            "error estimate. The reader turned those channels into excluded regions, so "
            "the same points are left out by a different mechanism. The pattern's "
            "channel count is therefore larger than the number the fit uses."
        ),
    ),
    "RESOLUTION_NOT_POSITIVE": HelpEntry(
        title="The instrument width goes negative",
        description=(
            "An instrument width is negative somewhere in the fitted range. The "
            "Gaussian one is a variance, a quadratic in tan θ, and the model clamps it "
            "to a tiny floor and carries on. That reports a resolution far finer than "
            "any diffractometer. The Lorentzian one, X/cos θ + Y tan θ, is a FWHM, "
            "and a negative one is not a peak shape. Do not quote the widths, or the "
            "size and strain derived from them. Refit the resolution on a standard "
            "with its certified cell held fixed, or load a measured profile."
        ),
    ),
    "RESOLUTION_UNCONSTRAINED": HelpEntry(
        title="Resolution refined on a Lorentzian pattern",
        description=(
            "The Gaussian resolution terms were refined on a pattern whose peaks are "
            "mostly Lorentzian. There the data do not determine them. What they "
            "converged to is an artefact of the fit and not a measurement of the "
            "instrument. Do not quote the widths, or any size or strain read from them. "
            "Measure the instrument on a standard, and hold that profile in this fit."
        ),
    ),
    "RESTRAINT_PAIRS_STALE": HelpEntry(
        title="Some contacts have no anti-bump row",
        description=(
            "At the end of the run, a phase's anti-bump restraints were checked against "
            "the final coordinates, and some contacts closer than their minimum distance "
            "have no row in the pair list. The list is built once, from the starting "
            "coordinates, so a pair that drifted inside its minimum from outside the list "
            "is not restrained. A contact already inside its minimum when the run "
            "started, such as a bond you left out of the list, is not reported. Either rebuild the list with "
            "`anti_bump_restraints` from these coordinates, or with a wider margin, and refit; or, if "
            "the contact is real (a hydrogen bond, say), lower that species pair's minimum distance."
        ),
    ),
    "RESTRAINT_TENSION": HelpEntry(
        title="The data disagree with a restraint",
        description=(
            "A soft restraint, such as a bond length, finished well away from its target "
            "in units of its own uncertainty. The data and your prior knowledge "
            "disagree. The fit averages the two. That costs a slightly worse Rwp and "
            "hides the conflict. Loosen the restraint, correct its target, or accept "
            "that the data should override the prior. A planarity restraint gives one "
            "finding, naming the atoms that sit out of its plane, worst first."
        ),
    ),
    "RIGID_BODY_MISFIT": HelpEntry(
        title="Data reject a rigid body's shape",
        description=(
            "Releasing the body into free atoms, held near the template by restraints, "
            "fits the data significantly better than the body does. Two independent "
            "tests agree. The body still converged with sensible errors, so the wrong "
            "shape went unnoticed. The likeliest cause is the template, such as a wrong "
            "bond length or atom assignment. Correct the template before you quote the "
            "body's geometry."
        ),
    ),
    "RIGID_BODY_UNSUPPORTED": HelpEntry(
        title="A rigid body motion is not measured",
        description=(
            "A free rotation or shift of a rigid body has no effect on the pattern. The "
            "usual cause is a turn that moves only zero-occupancy atoms, or a turn about "
            "an axis the template is symmetric under. The value and the esds of the body "
            "atoms are not measurements. Hold those parameters and refit."
        ),
    ),
    "ROUGHNESS_ABSORPTION": HelpEntry(
        title="Roughness and displacement parameters are entangled",
        description=(
            "Surface roughness cannot be separated from the displacement parameters, the "
            "scale and the background over this range. The others reproduce most of its "
            "effect, or it reproduces theirs. Refining both reports two numbers where "
            "the data support one, and the esds understate that. Uncorrected roughness "
            "drives displacement parameters negative. Extend the fit to lower angle, "
            "where roughness has leverage, or hold roughness at a measured value."
        ),
    ),
    "ROUGHNESS_OUTSIDE_REGIME": HelpEntry(
        title="Roughness model used outside its valid range",
        description=(
            "The Pitschke roughness model holds only above a limiting angle that depends "
            "on its parameter. The lowest fitted angle is at or near that limit. Below "
            "it the model raises intensity where it should lower it, and close above it "
            "the depression turns back. Near the limit the model is empirical, and its "
            "parameter is a fitting parameter and not a measured roughness. Restrict the "
            "fit to higher angle, or use the Suortti model."
        ),
    ),
    "ROUGHNESS_UNCONSTRAINED": HelpEntry(
        title="Roughness has no visible effect",
        description=(
            "The refined roughness correction changes the intensity of every modelled "
            "reflection by almost nothing. The data cannot see it, so its value is "
            "arbitrary. This also happens when the pattern starts too far above the "
            "angles where roughness acts. The Suortti form is inert at both extremes of "
            "its parameter. It is exactly off at b = 0 and at a = 1, and the esds "
            "of the scale and Biso depend on which of the two a fit stops at. Drop the "
            "roughness terms, or measure to lower angle."
        ),
    ),
    "SCALE_B_INSEPARABLE": HelpEntry(
        title="Scale and displacement cannot be separated",
        description=(
            "Over the fitted range the scale of a phase and its displacement parameters "
            "act on the data in the same way. This happens when the phase has few "
            "reflections, for example all at one d-spacing. The package held the "
            "displacement parameters at the values you supplied. The weight fraction is "
            "therefore conditional on those values, and its esd carries none of their "
            "uncertainty. Supply the values from elsewhere, or widen the range to a "
            "second d-spacing."
        ),
    ),
    "SEQUENTIAL_CANCELLED": HelpEntry(
        title="The series stopped before the last pattern",
        description=(
            "The series was cancelled part way. The pattern being fitted was abandoned "
            "and the remaining patterns were never started. The fits that finished are "
            "complete and stand on their own. The trajectory is truncated, so its last "
            "point is not the end of the ramp. Run the series again to extend it."
        ),
    ),
    "SEQUENTIAL_MOMENT_HOLD": HelpEntry(
        title="A magnetic moment is indistinguishable from none",
        description=(
            "In some patterns the refined moment lies within the noise of its own esd. "
            "That reads as a moment the data do not support, and says nothing about a "
            "small moment. Patterns where the modulus has no esd give no verdict at all. "
            "The value shown is the modulus the fit reached. Quote these points as held."
        ),
    ),
    "SEQUENTIAL_MOMENT_ONSET": HelpEntry(
        title="The magnetic onset is only a bracket",
        description=(
            "The series locates where a moment stops being supported by the data. The "
            "result is a bracket between two patterns, set by their spacing. It is no "
            "fitted critical point. The bracket is less reliable when the forward and "
            "backward chains disagree, when the verdicts switch back and forth, or when "
            "the supported side stopped early. Run both directions and compare before "
            "you quote a transition value."
        ),
    ),
    "SEQUENTIAL_PATH_CHECK_INCOMPLETE": HelpEntry(
        title="The forward and backward comparison was partial",
        description=(
            "The check that compares the forward and backward chains either did not run "
            "or covered less than the whole series. Zero path-dependent findings is a "
            "clean result only when the check ran in full. A chain may have stopped, a "
            "pattern may have failed, or a parameter may have had no esd in both chains. "
            "Rerun in both directions to completion before you quote per-pattern esds as "
            "the uncertainty."
        ),
    ),
    "SEQUENTIAL_PATH_DEPENDENT": HelpEntry(
        title="A trajectory depends on the refinement order",
        description=(
            "A parameter takes different values when the series is refined forward and "
            "backward, by more than their esds allow. The data alone do not determine "
            "it, so the path of the chain decides the value. Its per-pattern esd "
            "understates the uncertainty. Hold the parameter, restrain it, or report the "
            "spread between the two directions."
        ),
    ),
    "SEQUENTIAL_PERSISTENT_FINDING": HelpEntry(
        title="A per-pattern finding recurs across the series",
        description=(
            "The same diagnostic fired in most of the patterns. One occurrence says a "
            "pattern has a problem. Most of the series says the model or the plan has "
            "it. Refitting the individual patterns reproduces the finding. Change the "
            "model or the plan instead. The per-pattern diagnostics carry each "
            "occurrence."
        ),
    ),
    "SEQUENTIAL_RESEED": HelpEntry(
        title="A pattern was refitted from the initial model",
        description=(
            "The warm start from the neighbouring pattern failed, so this pattern was "
            "refitted from the initial model. Its starting values did not come from its "
            "neighbour, so it is no evidence that the trajectory is continuous at this "
            "point. Check whether the specimen or the model changed there. If the same "
            "pattern also carries an outlier or a finding the chain did not recover "
            "from, read that first."
        ),
    ),
    "SEQUENTIAL_RWP_OUTLIER": HelpEntry(
        title="A pattern fits much worse than its neighbours",
        description=(
            "Even its best attempt left this pattern's Rwp well above that of the "
            "patterns accepted before it. Compare its GoF and expected Rwp with an "
            "accepted neighbour. A higher GoF means the model has been outgrown, by a "
            "missing phase or a bad frame. A similar GoF with a higher expected Rwp "
            "means fewer counts, and the fit may be sound. If restarts were switched "
            "off, a cold start may still help."
        ),
    ),
    "SEQUENTIAL_UNRECOVERED": HelpEntry(
        title="A pattern failed every restart",
        description=(
            "The fit diverged on this pattern and stayed diverged after every restart "
            "the chain tried. Its values are not a measurement, so do not interpolate "
            "across it. It seeded no later pattern and was left out of the series "
            "median, so its neighbours are unaffected. Fit the pattern on its own to "
            "find out why."
        ),
    ),
    "SEQUENTIAL_WIDTH_GROWTH": HelpEntry(
        title="A phase width grows as the fit worsens",
        description=(
            "A peak-width parameter grew a long way over the series while the goodness "
            "of fit rose. A phase broadened that far usually stands in for something the "
            "model lacks, such as a second phase, a diffuse signal or a background the "
            "function cannot follow. Its width, scale and cell are then unreliable. Fit "
            "the pattern at the onset with the missing component added."
        ),
    ),
    "SERIES_PATTERN_FAILED": HelpEntry(
        title="A pattern could not be fitted",
        description=(
            "Every attempt to fit this pattern raised an error, so it has no entry in "
            "the series. The gap is a missing measurement and is not a zero or a held "
            "value. The last attempt usually started from the initial model, which "
            "points at the pattern itself and clears its neighbour. Fit it on its own "
            "and read the error."
        ),
    ),
    "SITE_SNAPPED_TO_SPECIAL_POSITION": HelpEntry(
        title="Site lies close to a special position",
        description=(
            "A site lies within rounding distance of a special position but not on it. "
            "The package expands the site at the special position, so its multiplicity "
            "is the special one. Where the file states that multiplicity, the "
            "coordinates are moved onto the position as well. The multiplicity sets how "
            "many atoms the site puts in the cell, so it changes the density and every "
            "weight fraction. If it matches the source, the coordinates were only "
            "rounded. A CIF site whose printed digits already round to the position, "
            "within `rietx.crystallography.cif.CIF_PRINTED_ROUNDING` of the last digit, "
            "is read on it and not reported, so this fires on a deviation the file "
            "printed."
        ),
    ),
    "SITE_DOFS_RENUMBERED": HelpEntry(
        title="Coordinate directions of a site renumbered",
        description=(
            "A site's coordinates moved onto or off a special position so that its "
            "coordinate degrees of freedom changed (`dof.1` is y on the general position "
            "and z on a mirror at y = 1/4, in either direction), and a hold, tie or free "
            "path sat on one of them. Each follows its direction to the new number. Where "
            "the position couples coordinates, as (x, 2x, z) does x and y, a hold on x "
            "holds the coupled direction, the one direction that moves x; a free path "
            "follows only where every coordinate that direction moves was free; a tie, "
            "which needs a single direction, is dropped. One on a direction the position "
            "fixes is dropped. The message names every one that followed and every one "
            "that was dropped. Nothing was moved: "
            "this is the bookkeeping of a site whose symmetry changed without a merge, "
            "for instance onto a mirror within 5e-5, after a fit wrote the coordinate "
            "back, or off one by an `edit` or a `checkout`."
        ),
    ),
    "SITE_TWINS_KEPT": HelpEntry(
        title="Near-duplicate atoms left as stored",
        description=(
            "A site lies within 5e-4 (fractional, per coordinate) of a special position, "
            "so its symmetry images fall in tight pairs, and the occupancy at that "
            "position, summed over the atoms sharing it and each times the images before "
            "over the images after, is at most 1. The numbers read two ways: one atom "
            "stated off its special position, or a split pair of part-atoms (#1088). "
            "Nothing was moved, and the model counts the second reading. The message "
            "gives the atoms per cell each reading implies, and the suggestion gives the "
            "occupancy to state on the special position for each. Every boundary applies "
            "the same gate: a project file, a CIF, a stored history and a model edit."
        ),
    ),
    "SITE_TWINS_MERGED": HelpEntry(
        title="Near-duplicate atoms merged onto a special position",
        description=(
            "A site lay within 5e-4 (fractional, per coordinate) of a special position, "
            "so its symmetry images fell in tight pairs, and the occupancy at that "
            "position, summed over the atoms sharing it and each times the images before "
            "over the images after, is above 1: the unchanged site would put more than "
            "one atom at one place. The site was moved onto the special position its "
            "orbit collapses to. Coordinates the position fixes lose `vary`, and an "
            "anisotropic tensor is projected onto the tensors the position allows; the "
            "message says each. This changes the multiplicity, so it changes the density "
            "and every weight fraction. A CIF read says the same thing as "
            "`CIF_SITE_TWINS_MERGED`, and the two never both fire. The occupancy is kept, "
            "so the site's atoms per cell change with its multiplicity, and the message "
            "gives both counts. Check the coordinate against its source, since a special "
            "position stated a few 1e-5 off is the usual cause. To keep a genuinely "
            "displaced atom, state it more than 5e-4 (fractional) from the position. "
            "A hold or tie on a coordinate degree of freedom that the position "
            "renumbers follows it, or is dropped and named in the message."
        ),
    ),
    "SIZE_NORMALISED_ACROSS_WAVELENGTHS": HelpEntry(
        title="Shared size term scaled across wavelengths",
        description=(
            "A size-broadening coefficient scales with wavelength. A joint fit over "
            "several wavelengths therefore shares the crystallite size and gives each "
            "histogram its own coefficient. The shared value is the coefficient at the "
            "first histogram's wavelength. Nothing is wrong. Read the crystallite size, "
            "which is one number for the specimen, instead of the raw coefficient."
        ),
    ),
    "SIZE_UNUSUALLY_SMALL": HelpEntry(
        title="Crystallite size is unusually small",
        description=(
            "A phase's refined size broadening implies a crystallite size below the "
            "range seen in solved refinements. Nanocrystalline material can be this "
            "small, so the fit may be right. A small size also broadens every line and "
            "competes with the background. Check that the broad lines are size "
            "broadening and not an unmodelled peak shape, strain, an amorphous component "
            "or a second phase. If the size is on its limit, the bound set the width and "
            "nothing was measured."
        ),
    ),
    "SOLVE_B_TIED_PER_PARENT_SITE": HelpEntry(
        title="Supercell displacement parameters tied to the parent",
        description=(
            "With `tie_to_parent=True`, a supercell trial holds the cell at the value "
            "derived from the parent. It also ties the displacement parameters of the "
            "child atoms that come from one parent atom. The nuclear reference that each "
            "trial is compared with is treated the same way, so the comparison is fair. "
            "Read the refined cell and displacement parameters as the parent's, and not "
            "as measurements of the supercell."
        ),
    ),
    "SPACE_GROUP_SETTING_ASSUMED": HelpEntry(
        title="Space group setting chosen by default",
        description=(
            "The symbol names a space group that the tables hold in more than one "
            "setting, and it does not name the setting. The package took the first. The "
            "settings put different numbers of atoms on the same coordinates, so the "
            "choice changes the cell contents and every weight fraction while leaving "
            "Rwp alone. If the first is the one you meant, write its setting into the "
            "symbol. Otherwise name the setting your coordinates use."
        ),
    ),
    "SPECIES_FALLBACK_NEUTRAL": HelpEntry(
        title="An ion was scattered as a neutral atom",
        description=(
            "The ion named for a site has no entry in the form-factor table. The model "
            "scattered it as the neutral atom. Its electron count differs. Every "
            "reflection that site contributes to is off by that fraction. Occupancies, "
            "displacement parameters and phase fractions are biased together, with "
            "little change in Rwp. Accept the neutral atom as the model, or substitute a "
            "tabulated ion of the same element with a nearby charge."
        ),
    ),
    "STAGE_FREED_NOTHING": HelpEntry(
        title="A stage freed nothing in one histogram",
        description=(
            "A refinement stage freed parameters in other histograms of a joint fit and "
            "none in this one. The stage's parameter patterns matched only the other "
            "histograms, so this histogram kept its starting values for that stage. "
            "Nothing is wrong if it has no such component. Otherwise its parameters go "
            "by other names, so widen the patterns or scope the stage to one histogram."
        ),
    ),
    "STAGE_FREES_MAGNETIC_WIDTH_WITH_MOMENT": HelpEntry(
        title="Magnetic width and moment freed together",
        description=(
            "A stage frees the magnetic broadening in the same stage that first frees "
            "the moment. Both lower the height of the calculated magnetic peak, so from "
            "a cold start they trade against each other. Neither refined number measures "
            "its own quantity. Refine the moment with the widths at zero, then free the "
            "widths beside the converged moment, then free both together."
        ),
    ),
    "STAGE_MAX_ITER": HelpEntry(
        title="A stage stopped on its iteration limit",
        description=(
            "A stage ran out of iterations before it converged. The result reports the "
            "status of the last stage only, so it can read as converged while an earlier "
            "stage did not. The parameters freed in that stage are probably degenerate. "
            "Free fewer at once, or look for a correlation or a bound hit in the same "
            "stage. More iterations do not find a different minimum."
        ),
    ),
    "STAGE_PATH_NOT_FREE": HelpEntry(
        title="A stage named a fixed parameter",
        description=(
            "A stage asked to refine a parameter that symmetry or the model fixes, or "
            "that follows another parameter. Nothing was freed for it, yet the fit "
            "converged. The parameter kept its value. Free the parameter it follows, or "
            "for a coordinate free the directions that the site symmetry allows. If the "
            "model holds it fixed, there is nothing to refine."
        ),
    ),
    "STAGE_PATH_UNKNOWN": HelpEntry(
        title="A stage named a parameter the model lacks",
        description=(
            "A stage asked to refine a parameter by a name that no parameter of the "
            "model has. The usual cause is a typing slip or a retired spelling. Nothing "
            "was freed, yet the fit converged. A wildcard pattern that matches nothing "
            "stays silent, because some models lack a component. Correct the name, or "
            "use a wildcard if the stage should reach a component that only some models "
            "declare."
        ),
    ),
    "STAGE_WINDOWS_STALE": HelpEntry(
        title="A stage's peaks outgrew the windows it was solved on",
        description=(
            "Each stage computes every peak over a window of points, sized when the "
            "stage starts. A peak that moves or broadens while the stage solves spills "
            "past its window, and the model loses that part of its intensity. The stage "
            "can then fit the loss rather than the data, and still report that it "
            "converged. This fires when the windows drop more of the intensity, at the "
            "stage's answer, than each window is allowed to drop. It reports only the "
            "stages whose answer reaches the result: the last one, and the one before "
            "a plan's closing stage. An earlier stage records its loss too, and every "
            "stage after it refits its answer on fresh windows. Treat the result as "
            "unconfirmed, and refit from starting values nearer the data. On the case "
            "measured, a further stage from the stage's answer ran further away."
        ),
    ),
    "STEPHENS_STRAIN_NOT_POSITIVE": HelpEntry(
        title="Anisotropic strain coefficients are unphysical",
        description=(
            "The refined anisotropic strain coefficients give a negative variance at "
            "some reflections. A variance cannot be negative, so the coefficients lie "
            "outside the physical set. Those reflections receive no strain broadening, "
            "and nothing else says so. A negative value is not evidence of large "
            "anisotropy. Restart from the isotropic limit, refine fewer strain terms, or "
            "extend the fitted range. Do not quote the coefficients."
        ),
    ),
    "STRAIN_UNUSUALLY_LARGE": HelpEntry(
        title="Strain broadening is unusually large",
        description=(
            "A phase's refined strain broadening is far above the range seen in solved "
            "refinements. It is physically possible, so the fit is finished and may be "
            "right. A strain this large reaches across the pattern and competes with the "
            "background and with overlapping phases. Check that the broad lines belong "
            "to this phase and not to an unmodelled peak shape, an amorphous component "
            "or a second phase. If the strain is on its limit, the bound set the width."
        ),
    ),
    "TEXTURE_NOT_POSITIVE": HelpEntry(
        title="Texture series gives a negative pole density",
        description=(
            "The truncated spherical-harmonics series goes below zero somewhere on the "
            "sphere. A pole density cannot be negative, so the coefficients lie outside "
            "the physical set. You cannot quote them as a pole density. The result is no "
            "evidence that the specimen is textured. Lower the order, or hold the "
            "highest terms. The default solver keeps the density positive at the "
            "reflections."
        ),
    ),
    "TOPAS_BLOCK_SKIPPED": HelpEntry(
        title="A TOPAS block is not a phase",
        description=(
            "A `str` block states a cell or sites but no phase name or space group, so "
            "the reader cannot treat it as a phase. It is kept on the parsed model and "
            "not built. Building a structure refuses while other phases build, because "
            "dropping a block that has a cell would leave the phase fractions short. "
            "State the missing name or space group in the file and read it again."
        ),
    ),
    "TOPAS_CELL_COUPLING_DROPPED": HelpEntry(
        title="Tied TOPAS lattice parameters are independent here",
        description=(
            "The file ties one lattice parameter to another, for example by copying one "
            "into the other. The reader copies the value and not the tie. The space "
            "group does not tie the two edges either, so they can refine apart. That is "
            "a different refinement from the one in the file. Tie the edges on the "
            "refinement before you fit."
        ),
    ),
    "TOPAS_FEATURES_NOT_IMPORTED": HelpEntry(
        title="The TOPAS import is partial",
        description=(
            "A TOPAS input states more than a structure, such as peak shapes, "
            "broadening, corrections, restraints and library macros. The import carries "
            "the structure and reports the rest. The cell and coordinates are the file's "
            "values. An Rwp from rietx's own profile model is not comparable with the "
            "file's. A call to a macro the file never defines looks like a spelling "
            "error, and it is reported too."
        ),
    ),
    "TOPAS_FEATURE_REFUSED": HelpEntry(
        title="A TOPAS construct blocks building the structure",
        description=(
            "The file states a construct that would misrepresent the refinement if it "
            "were left out. Examples are a rigid body, a stacking-fault model, a "
            "magnetic structure and time-of-flight data. The reader parses the file and "
            "keeps its numbers, but building a structure refuses. Read the parsed phases "
            "for what the file states."
        ),
    ),
    "TOPAS_FIELD_NOT_WRITTEN": HelpEntry(
        title="A phase term was left out of TOPAS",
        description=(
            "Some phase terms away from their neutral values have no statement in the "
            "TOPAS file. Examples are extinction, magnetic-only widths, texture and a "
            "preferred orientation. TOPAS computes those phases without them, so its "
            "pattern and its fit differ from rietx's. State the terms in TOPAS before "
            "you compare."
        ),
    ),
    "TOPAS_FIRST_RUN_READ": HelpEntry(
        title="Only the first TOPAS run was read",
        description=(
            "A conditional in the input tests the run number, and the file asks for more "
            "than one run. Later runs process the same file into different text. The "
            "reader used the branches the first run takes, so the model is the first "
            "run's. Where the conditional gates only output commands the model is "
            "unaffected. Read the other branches for the run you want."
        ),
    ),
    "TOPAS_MAGNETIC_GROUP_READ": HelpEntry(
        title="A magnetic group was read from its number",
        description=(
            "The file gives a magnetic space group as a BNS or OG number. The reader "
            "resolved it to symmetry operators in the standard setting of that number. "
            "Where the file states no nuclear space group, the reader derived it from "
            "those operators with time reversal dropped. Coordinates and moments are "
            "assumed to be in that setting. Supply your own operators if the file uses "
            "another setting."
        ),
    ),
    "TOPAS_MAGNETIC_PART_MERGED": HelpEntry(
        title="Two TOPAS phases were merged",
        description=(
            "The file writes a magnetic-only part as a second phase beside the nuclear "
            "one. The reader checked that the two share scale, cell, space group and "
            "site positions, then put the moments onto the nuclear phase. The second "
            "phase's own scale is not kept apart, so refine the merged phase as one. A "
            "file whose two phases disagree is refused."
        ),
    ),
    "TOPAS_MOMENT_CONVENTION": HelpEntry(
        title="TOPAS moment components were read as cell fractions",
        description=(
            "TOPAS gives the components of a moment as fractions of the lattice "
            "parameters a, b and c. The reader multiplies each by its lattice parameter "
            "to store crystal-axis components in Bohr magnetons. This follows the TOPAS "
            "reference and agrees with TOPAS's own calculated intensities on a "
            "monoclinic cell. A different reading gives different magnetic intensities "
            "on a non-cubic cell."
        ),
    ),
    "TOPAS_MOMENT_G_HELD": HelpEntry(
        title="A refined Landé factor is held fixed",
        description=(
            "The TOPAS file refines the Landé g factor on a magnetic site. rietx holds g "
            "at a fixed number, so the built model has fewer free parameters than the "
            "file's refinement. The factor sets the weight of the orbital part of the "
            "magnetic form factor. Set another value on the structure to test it, and "
            "remember that g did not move when you compare fits."
        ),
    ),
    "TOPAS_MOMENT_ION_UNCHARGED": HelpEntry(
        title="A magnetic site has no oxidation state",
        description=(
            "The magnetic form factor depends on the oxidation state of the ion. A site "
            "with a moment and an uncharged species gets the form factor of the neutral "
            "atom. That is a different curve. The magnetic intensities then differ from "
            "those of the ion. Write the site with its charge in the TOPAS file so the "
            "ion resolves."
        ),
    ),
    "TOPAS_ORIGIN_TRANSLATED": HelpEntry(
        title="A TOPAS origin suffix was translated",
        description=(
            "TOPAS writes the origin or axes choice of a space group as a trailing "
            "letter. The reader translated that letter into the extension the symmetry "
            "tables use. Dropping the letter would select the other origin without a "
            "warning, because a bare symbol means origin choice 1. The built phase has "
            "the space group the file meant."
        ),
    ),
    "TOPAS_PHASE_RESTATED_IN_P1": HelpEntry(
        title="A magnetic phase was written in P1",
        description=(
            "TOPAS has no magnetic space group number for some phases, such as a "
            "supercell, a family group without a tabulated number, or a non-standard "
            "setting. The writer listed every atom of the cell in P1 and tied each copy "
            "to the parameter it copies. The file is long, and each copy follows its "
            "parent."
        ),
    ),
    "TOPAS_PHASE_TERM_READ": HelpEntry(
        title="A parameter was read as a phase term",
        description=(
            "TOPAS has no keyword for extinction or the magnetic Lorentzian widths of a "
            "phase. The reader takes parameters with the names rietx writes for them as "
            "those terms. A parameter of your own that happens to share one of those "
            "names is read the same way. If the name means something else in your file, "
            "set the phase term back on the built structure."
        ),
    ),
    "TOPAS_SPECIES_NORMALISED": HelpEntry(
        title="A TOPAS atom label was respelled",
        description=(
            "TOPAS writes an ionic charge sign first. The reader reordered it into the "
            "standard form with the digit first, so the scattering tables find the ion. "
            "The atom and its charge are the same as in the file. The structure holds "
            "only this spelling."
        ),
    ),
    "TOPAS_SPECIES_WRITTEN_NEUTRAL": HelpEntry(
        title="A TOPAS ion was written as neutral",
        description=(
            "The X-ray scattering table has no entry for this ion, so rietx computed the "
            "neutral atom for it. The TOPAS file therefore names the neutral element and "
            "the ion's charge is lost. A site that carries a moment keeps its ion. "
            "Respell the site in TOPAS if you want to refine the ion."
        ),
    ),
    "WAVELENGTH_CALIBRATION": HelpEntry(
        title="A refined wavelength moved from its declared value",
        description=(
            "You freed the wavelength, and it moved from its declared value by the "
            "amount shown. The shift measures the calibration error of the monochromator "
            "against the cell that was held. A shift inside its own esd measured "
            "nothing. A shift beyond the beamline's known drift more likely points at a "
            "modelling error, such as an unmodelled harmonic or a zero shift traded "
            "against the wavelength. Compare it with the calibration history before you "
            "quote the cell."
        ),
    ),
    "XRDML_ATTENUATOR_APPLIED": HelpEntry(
        title="A beam attenuator factor was applied",
        description=(
            "An attenuator foil sat in front of the detector over some points. The "
            "stored counts are what the detector saw behind the foil, so the reader "
            "multiplied them by the factor. Esds follow the same factor. The correction "
            "is large and invisible in the file's own numbers. That is why it is "
            "reported."
        ),
    ),
}


#: One entry per field of :class:`~rietx.schemas.plan.StageSpec`.  These are
#: settings for one stage of a plan, not refined quantities, so ``default`` is
#: the schema's default and ``typical`` says what a preset actually uses.
STAGE_FIELD_HELP: dict[str, HelpEntry] = {
    "name": HelpEntry(
        title="Stage name",
        description=(
            "A label for the stage. It appears in the stage table, in the history node "
            "that the stage commits and in any diagnostic that says where a finding "
            "came from."
        ),
    ),
    "turn_on": HelpEntry(
        title="Parameters freed this stage",
        description=(
            "Wildcard patterns for the parameter paths that the stage frees when it "
            "starts. For example, `phases.*.cell.*` frees every lattice parameter of "
            "every phase. Staging is cumulative, so a parameter freed here keeps "
            "refining in every later stage. Paths contain no square brackets, because "
            "the matching reads brackets as a character class."
        ),
        default="[]",
        typical="one or two patterns per stage",
        anchor="theory/parameterisation.html#from-tree-to-vector",
    ),
    "max_iter": HelpEntry(
        title="Iteration budget",
        description=(
            "The approximate number of solver iterations for this stage. Both solvers "
            "cap function evaluations, so the number is scaled by a measured worst-case "
            "rejection rate (`NFEV_PER_ITERATION`) before it reaches the solver."
        ),
        default="100",
        typical="20-100",
        anchor="theory/estimation.html#convergence",
    ),
    "ftol": HelpEntry(
        title="Stage stopping tolerance",
        description=(
            "This stage's own relative tolerance on the decrease in cost. It overrides "
            "the plan's schedule. Empty takes the value from the plan: every declared "
            "stage but the last stops at the plan's `intermediate_ftol`, and the last "
            "declared stage and the closing stage stop at the solver's 1e-9. The history records the tolerance a stage ran at and "
            "not the one it declared, so a cherry-pick replays what happened."
        ),
        default="null",
        typical="leave empty unless reproducing a specific run",
        anchor="theory/estimation.html#convergence",
    ),
    "lebail_cycles": HelpEntry(
        title="Le Bail cycles",
        description=(
            "How many cycles of intensity partitioning run before each solve in "
            "`lebail` mode. In `pawley` mode the same partition seeds the intensities "
            "on a stage that carries none in, and the solve then refines them. The "
            "setting is ignored in `rietveld` mode, where the intensities come from "
            "the structure."
        ),
        default="3",
        typical="3",
        anchor="theory/forward-model.html#three-intensity-models",
    ),
    "seed": HelpEntry(
        title="Starting value for parameters at zero",
        description=(
            "Sets the starting value of every parameter that the stage frees and that "
            "sits exactly on a lower bound of 0 or above. A parameter that can go "
            "negative is never seeded. The Suortti roughness correction is the identity "
            "at b = 0, so the roughness stage uses this to start b near where the data "
            "can see it. That is the only shipped stage that seeds. For a Stephens "
            "strain block use `strain_seed`, which has the opposite problem."
        ),
        default="0.0",
        typical="0.3 where a stage frees surface roughness; 0 elsewhere",
    ),
    "strain_seed": HelpEntry(
        title="Stephens strain seed",
        description=(
            "Microstrain in ppm that starts an all-zero Stephens block on the isotropic "
            "limit. At S = 0 the square root in the width law has unbounded slope, so "
            "the block needs a starting value of its own. `seed` cannot do this, "
            "because it reaches only parameters bounded below at 0 and these "
            "coefficients can go negative."
        ),
        unit="ppm", default="0.0",
        typical="100-1000 ppm where a stage frees an anisotropic strain block",
        anchor="theory/microstructure.html#the-positivity-cone-the-seed-and-the-guard",
    ),
    "restraint_weight_scale": HelpEntry(
        title="Restraint weight",
        description=(
            "The weight `c_w` in `S = S_y + c_w·S_G` (McCusker et al. 1999, equation "
            "7). It sets how strongly the geometric restraints count against the "
            "diffraction data in this stage. Hold it high early and reduce it as the "
            "model improves. A value of 1.0 leaves the restraints unscaled. A value of "
            "0.0 silences them without removing them, so the restraint count behind the "
            "statistics cannot change mid-plan."
        ),
        default="1.0",
        typical="1-100 early, falling to 1 in the last stage",
        anchor="theory/parameterisation.html#weighting-the-restraints",
    ),
    "window_slack_deg": HelpEntry(
        title="Peak window margin",
        description=(
            "Extra 2θ on each side of a reflection's integration window, replacing the "
            "default (`WINDOW_MIN_DEG`). A fit whose starting model may sit far from "
            "the data declares it, such as the whole-pattern validation that an indexing "
            "candidate goes through. Empty takes the default."
        ),
        unit="deg 2θ", default="null",
        typical="leave empty outside indexing validation",
    ),
}

#: One entry per ``io.formats.base.READER_OPTIONS`` key.  ``ReaderOption.help``
#: stays as it is: it is a ``capabilities()`` contract written for a client
#: enumerating what a reader accepts.  These entries are the text a person
#: reads beside the control.
READER_OPTION_HELP: dict[str, HelpEntry] = {
    "bank": HelpEntry(
        title="Detector bank",
        description=(
            "Which detector bank of a GSAS file to read, given as the number in the "
            "file's own `BANK` record. The instrument-parameter file uses the same "
            "number for its per-bank records. A bank is a detector and not a scan. It "
            "has its own scattering angle, its own DIFC, DIFA and zero calibration, and "
            "its own resolution. A time-of-flight diffractometer is several banks (ISIS "
            "GEM writes six). A file with more than one bank is refused until you name "
            "one, because answering with the first would choose for you."
        ),
        typical="unset for a single-bank file; the bank's own number otherwise",
    ),
    "block": HelpEntry(
        title="Data block",
        description=(
            "Which block of a multi-block file to read, matched against part of the "
            "block name. A pdCIF with both a `_meas` block and a `_calc` block gives a "
            "different pattern for each. The project therefore records this option "
            "beside the file name."
        ),
        typical="`_meas` for measured data in a pdCIF",
    ),
    "scan": HelpEntry(
        title="Scan index",
        description=(
            "Which measurement to read from a file that holds several, counting from 0. "
            "A vendor file often stores a whole session. The scans of a multi-range "
            "file are separate measurements, so rietx reads one of them and never joins "
            "them. Joining would mix two weighting regimes."
        ),
        default="0",
        typical="0 unless a preview reports more than one scan",
    ),
}

#: One entry per field any ``gui.imports.INSTRUMENT_PRESETS`` geometry accepts.
#: These are constructor arguments for building an :class:`Instrument`, not
#: parameter paths: the wizard sends a geometry and an anode, and the package
#: owns the physics that follows.
INSTRUMENT_FIELD_HELP: dict[str, HelpEntry] = {
    "radiation": HelpEntry(
        title="Anode",
        description=(
            "The tube anode that the pattern was measured with. It selects the Kα1 and "
            "Kα2 wavelengths from the package's NIST-scale table, and the weight of the "
            "doublet. An error of about 100 ppm in the cell can hide behind this "
            "setting. Read it off the instrument, because the peak positions cannot "
            "tell you."
        ),
        typical="`CuKa`, `MoKa`, `CoKa`, `CrKa`, `FeKa`, `AgKa`, or the "
                "`…Ka1` variant of any of them for a Kα1-only beam",
        anchor="theory/peak-positions.html#wavelength-scales",
    ),
    "wavelength": HelpEntry(
        title="Wavelength",
        description=(
            "The incident wavelength. The Debye-Scherrer preset asks for it because "
            "that geometry has no anode to read it from. A synchrotron or neutron "
            "beamline states it in the data file or the beamline record."
        ),
        unit="Å",
        typical="0.3-1.0 Å synchrotron, 1.0-2.5 Å constant-wavelength neutron",
        anchor="theory/peak-positions.html#wavelength-scales",
    ),
    "polarization": HelpEntry(
        title="Polarisation factor",
        description=(
            "The factor K of the Lorentz-polarisation correction "
            "(`lorentz_polarization`). Only the Debye-Scherrer preset takes it. Left "
            "empty there, it is 0.99, the APS 11-BM instrument-parameter value, and not "
            "the 0.5 of an unpolarised laboratory beam. Neither flat-plate preset has "
            "the field. Bragg-Brentano derives K from `monochromator_two_theta`, and "
            "transmission is unpolarised with K = 0.5."
        ),
        typical="0.99 is the preset default; 0.5 is an unpolarised lab beam",
        anchor="theory/corrections.html#lorentz-polarisation",
    ),
    "goniometer_radius_mm": HelpEntry(
        title="Goniometer radius",
        description=(
            "The radius of the 2θ circle. The specimen-displacement shift divides by it "
            "(McCusker et al. 1999, equation 3). Declaring it turns a refined "
            "displacement into millimetres. Without it the displacement is an arbitrary "
            "coefficient."
        ),
        unit="mm",
        typical="217.5 mm is a common laboratory value and the default",
        anchor="theory/peak-positions.html#sample-displacement",
    ),
    "monochromator_two_theta": HelpEntry(
        title="Monochromator 2θ",
        description=(
            "The take-off angle of a diffracted-beam monochromator crystal. It fixes "
            "the polarisation factor K at 1/(1 + cos²2θm), which is 0.556 for graphite "
            "(002) at Cu Kα. `Instrument.bragg_brentano` does that conversion. Leave it "
            "empty if there is no monochromator, which gives the unpolarised K = 0.5. "
            "The angle 26.6° belongs to Cu Kα. Graphite (002) diffracts other anodes at "
            "other angles, so compute it for your anode."
        ),
        unit="deg",
        typical="26.6° for graphite (002) at Cu Kα; 9.6-39.9° for the same "
                "crystal from Ag Kα to Cr Kα",
        anchor="theory/corrections.html#lorentz-polarisation",
    ),
    "ka2_ratio": HelpEntry(
        title="Kα2 to Kα1 ratio",
        description=(
            "The intensity of the Kα2 line relative to Kα1. 0.5 is the 2j+1 degeneracy "
            "ratio and the right starting value for every anode. Change it only when a "
            "monochromator or a filter has altered the doublet."
        ),
        default="0.5",
        typical="0.5",
        anchor="theory/peak-positions.html#wavelength-scales",
    ),
    "capillary_radius_mm": HelpEntry(
        title="Capillary radius",
        description=(
            "The radius of the capillary bore, measured inside the glass. It is an "
            "input for estimating µR and is never refined."
        ),
        unit="mm",
        typical="0.1-0.5 mm",
        anchor="theory/corrections.html#capillary-cylindrical-absorption",
    ),
    "packing_fraction": HelpEntry(
        title="Packing fraction",
        description=(
            "The fraction of the bore, or of the specimen slab, that solid occupies. It "
            "is an input for estimating µR and µt and is never refined. A tapped powder "
            "falls at 0.3-0.6, and random close packing of spheres is 0.64."
        ),
        default="0.6",
        typical="0.3-0.6",
        anchor="theory/corrections.html#attenuation-coefficients",
    ),
    "mu_r": HelpEntry(
        title="µR",
        description=(
            "The capillary absorption parameter. It is the linear attenuation "
            "coefficient times the bore radius. Leave it empty for no correction, "
            "because µR = 0 is the off state. It cannot be refined. It is exactly a "
            "reparameterisation of the phase scale and the displacement parameters, so "
            "the fit statistic cannot move. Its whole effect is a shift of every B by "
            "c(µR)·λ²/2."
        ),
        typical="0-1 for a typical capillary mount",
        anchor="theory/corrections.html#capillary-cylindrical-absorption",
    ),
    "mu_t": HelpEntry(
        title="µt",
        description=(
            "The flat-plate absorption parameter. It is the linear attenuation "
            "coefficient times the specimen thickness. What an empty value means "
            "depends on the geometry. On a Bragg-Brentano mount, empty is a thick "
            "specimen. There µt = 0 is a specimen of no thickness, and it is refused. "
            "In transmission, µt = 0 is legal and means a non-absorbing plate that "
            "still carries the sec θ footprint factor. Declaring a thickness for a "
            "genuinely thick specimen makes the fit worse and biases every B downwards."
        ),
        typical="empty for a thick reflection specimen; 1-5 for a thin "
                "transmission mount",
        anchor="theory/corrections.html#flat-plate-absorption",
    ),
    "thickness_mm": HelpEntry(
        title="Specimen thickness",
        description=(
            "For a reflection mount, the depth of the powder layer, excluding the "
            "holder. It is an input for estimating µt only. Leave it empty for a thick "
            "specimen."
        ),
        unit="mm",
        typical="0.1-2 mm for a transmission mount",
        anchor="theory/corrections.html#flat-plate-absorption",
    ),
}


#: One entry per control :class:`~rietx.schemas.indexing.IndexingControls`
#: carries, flattened one level: the eighteen fields of its ``search`` block
#: plus the three beside it.  These are search settings, not refined
#: quantities, so ``default`` is the schema's own value rendered as JSON and
#: ``tests/test_help.py`` crosses every one of them.
#:
#: The prose arrived from ``gui/src/lib/controls.ts`` in WP-1203, where it had
#: been the form's ``title=`` strings.  It moved rather than being rewritten:
#: the form was the only place several of these measurements were written down,
#: and a paraphrase here would have been a second account of them.
SEARCH_FIELD_HELP: dict[str, HelpEntry] = {
    "systems": HelpEntry(
        title="Crystal systems to search",
        description=(
            "Which crystal systems the search covers. They run in decreasing symmetry, "
            "so a cubic answer arrives in seconds and a triclinic one in minutes. "
            "Restricting the systems says nothing about the specimen. The result lists "
            "the systems it searched and makes no claim about the others."
        ),
        typical="all seven; narrow only when a prior tells you the system",
        anchor="reference/indexing.html#the-search-specification",
    ),
    "centrings": HelpEntry(
        title="Bravais centrings",
        description=(
            "Which lattice centrings to try within each system. Clearing one tick "
            "narrows the search, and the result records it. At least one must stay "
            "ticked in every system you search."
        ),
        typical="all of them; a wrongly excluded centring costs the true cell",
        anchor="reference/indexing.html#the-search-specification",
    ),
    "preset": HelpEntry(
        title="Search preset",
        description=(
            "The named ceiling on the whole run. `quick`, the default, runs every "
            "engine and system under a measured ceiling and reports any truncation "
            "prominently. `full` has no ceiling. A whole-run budget that you type "
            "overrides the preset, and the result then records `custom`."
        ),
        typical="`quick` for a first look, `full` when the answer matters",
        anchor="reference/indexing.html#presets-budgets-and-the-three-states-of-a-system",
    ),
    "total_budget_seconds": HelpEntry(
        title="Whole-run budget",
        description=(
            "Wall-clock ceiling on the whole run, covering search, probe and validation "
            "together. Empty leaves the ceiling to the preset. A value here overrides "
            "the preset's ceiling, and the result records the preset as `custom`."
        ),
        unit="s",
        typical="empty; a few minutes to bound an interactive run",
        anchor="reference/indexing.html#presets-budgets-and-the-three-states-of-a-system",
    ),
    "budget_seconds": HelpEntry(
        title="Time per engine and system",
        description=(
            "Wall-clock time for one engine on one crystal system. It does not bound "
            "the whole run. An engine that this limit stops reports that system as "
            "incomplete. A negative result from an incomplete search is no evidence "
            "against a cell."
        ),
        unit="s",
        default="30.0",
        typical="30 s; raise it for a triclinic search you intend to trust",
        anchor="reference/indexing.html#presets-budgets-and-the-three-states-of-a-system",
    ),
    "min_d_axis": HelpEntry(
        title="Shortest principal d-spacing",
        description=(
            "The shortest principal d-spacing a candidate cell may have. It bounds "
            "d(100). For an oblique cell that is slightly stronger than a bound on the "
            "axis a."
        ),
        unit="Å",
        default="2.0",
        typical="2 Å for an inorganic phase",
        anchor="reference/indexing.html#the-search-specification",
    ),
    "max_d_axis": HelpEntry(
        title="Longest principal d-spacing",
        description=(
            "The longest principal d-spacing a candidate cell may have. Raising it "
            "costs exponentially, because the domain grows and an exhaustive search "
            "covers all of it."
        ),
        unit="Å",
        default="25.0",
        typical="25 Å; raise it only for a genuinely large cell",
        anchor="reference/indexing.html#the-search-specification",
    ),
    "min_volume": HelpEntry(
        title="Smallest cell volume",
        description=(
            "The smallest cell volume a candidate may have. It removes the tiny cells "
            "that index a few lines by coincidence."
        ),
        unit="Å³",
        default="15.0",
        typical="15 Å³",
        anchor="reference/indexing.html#the-search-specification",
    ),
    "max_volume": HelpEntry(
        title="Largest cell volume",
        description=(
            "The largest cell volume a candidate may have, used exactly as you give it. "
            "Empty takes the per-system envelope of Smith (1977) from the data-quality "
            "report, with the calibration slack that the engines apply to a mean line."
        ),
        unit="Å³",
        typical="empty; state it only when you know the volume",
        anchor="reference/indexing.html#the-search-specification",
    ),
    "n_unindexed": HelpEntry(
        title="Unindexed lines allowed",
        description=(
            "How many search lines a cell may leave unindexed. Empty (the "
            "default) is two. A run where no two engines agree on a lattice "
            "is searched again accepting a cell that indexes 60 % of the "
            "search lines and the five strongest; `'inliers'` searches that "
            "way from the start. A number forbids the retry. Raising it "
            "manufactures cells, because every tolerated line is one more "
            "coincidence that a wrong metric is allowed. Four is a "
            "statement that you know something about the specimen, such as "
            "an impurity."
        ),
        typical="empty; `'inliers'` on a pattern with a known impurity",
        anchor="reference/indexing.html#driven-lines-and-the-inlier-rule",
    ),
    "n_search_lines": HelpEntry(
        title="Lines that drive the search",
        description=(
            "How many of the strongest observed lines drive the search. Raising it is "
            "not free. A cell must index all but the allowance of these lines, so every "
            "extra foreign line can refute the true cell. On a 68-line list the "
            "certified lattice is lost at 32."
        ),
        default="20",
        typical="20; foreign lines live in the tail of a list",
        anchor="reference/indexing.html#driven-lines-and-the-inlier-rule",
    ),
    "k_sigma": HelpEntry(
        title="Matching window in σ",
        description=(
            "The matching window in units of each line's own σ. Three is a calibrated "
            "99.7 % window and needs no tuning. The systematic 2θ allowance is the "
            "other half of the window, and a displaced pattern needs that half."
        ),
        default="3.0",
        typical="3",
        anchor="reference/peaks.html#the-systematic-shift-and-the-window-it-opens",
    ),
    "shift_allowance_deg": HelpEntry(
        title="Systematic 2θ allowance",
        description=(
            "A systematic 2θ allowance that you have measured. It is the amplitude that "
            "the matching window has to span. The residual scatter left after fitting a "
            "template is a different quantity. The two differ by 4.3× on a certified "
            "pattern, and declaring the scatter finds no cell at all. Zero lets the "
            "engines assume their own allowance and caps the confidence they may "
            "report."
        ),
        unit="deg 2θ",
        default="0.0",
        typical="0 unless an internal standard measured the shift",
        anchor="reference/peaks.html#the-systematic-shift-and-the-window-it-opens",
    ),
    "shift_template": HelpEntry(
        title="Shift template",
        description=(
            "The physical cause of the 2θ shift, if you know it. A candidate that "
            "survives the search is refitted with this correction. The refit stops a "
            "widened search from reporting a biased cell."
        ),
        typical="`cos_theta` for specimen displacement, `constant` for a zero-point shift",
        anchor="reference/peaks.html#the-systematic-shift-and-the-window-it-opens",
    ),
    "max_candidates": HelpEntry(
        title="Candidates reported",
        description=(
            "How many candidates the final list holds after the engines are merged and "
            "ranked. It also sets the validation cost, since every reported candidate "
            "needs a validation fit. Each engine hands five times this number to the "
            "merge, so the cap never decides a rank."
        ),
        default="12",
        typical="12",
        anchor="reference/indexing.html#the-result-object",
    ),
    "seed": HelpEntry(
        title="Random seed",
        description=(
            "The seed of the stochastic engine's random number generator. Every result "
            "records it, so you can reproduce a run from what it reports."
        ),
        default="0",
        typical="0",
        anchor="reference/indexing.html#the-search-specification",
    ),
    "prior_cells": HelpEntry(
        title="Analogue cells",
        description=(
            "Cells from a structural analogue, each given as a b c α β γ. The cell's "
            "crystal system moves to the front of the queue, its metric seeds the "
            "stochastic engine, and the cell itself is checked against the lines. A "
            "prior steers the search. A wrong one costs time and cannot rule out the "
            "true cell, and the result records what it changed."
        ),
        typical="empty; one analogue cell when the chemistry suggests one",
        anchor="reference/indexing.html#priors-from-a-structural-analogue",
    ),
    "prior_spacegroups": HelpEntry(
        title="Analogue space groups",
        description=(
            "Space-group symbols from a structural analogue, such as `R -3 c`. Each "
            "moves its crystal system to the front of the queue and, beside a matching "
            "prior cell, supplies its centring."
        ),
        typical="empty",
        anchor="reference/indexing.html#priors-from-a-structural-analogue",
    ),
    "engines": HelpEntry(
        title="Engines to run",
        description=(
            "Which searches run. Keep the default of all of them. High confidence means "
            "that every engine that ran found the same lattice, so a subset narrows "
            "what the answer can say."
        ),
        typical="all of them",
        anchor="reference/indexing.html#three-engines-and-why-the-default-is-all-of-them",
    ),
    "validate_candidates": HelpEntry(
        title="Whole-profile validation",
        description=(
            "Whole-profile validation of the top candidates. Turning it off caps every "
            "candidate at medium confidence, because the figure-of-merit panel cannot "
            "see a reflection predicted where the pattern has no intensity. Turn it off "
            "only to save time on a first look."
        ),
        default="true",
        typical="on",
        anchor="reference/indexing.html#the-whole-profile-test",
    ),
    "check_top": HelpEntry(
        title="Candidates checked in depth",
        description=(
            "How many candidates get the per-candidate checks: the ambiguity search and "
            "the whole-pattern validation fit. Empty takes the package default plus "
            "every candidate that the confidence gate could promote."
        ),
        typical="empty",
        anchor="reference/indexing.html#the-whole-profile-test",
    ),
}


#: The result types whose fields :data:`RESULT_FIELD_HELP` describes, named as
#: data so ``tests/test_help.py`` can resolve each to its class and cross the
#: arm against its ``model_fields``.  These four are the types whose fields
#: record what a fit *did*: ``StageResult``, ``SeriesEntry`` and
#: ``RefinementResult`` are the action-record types the generality record's
#: § Acceptance names, and ``SeriesResult`` is where WP-2003's demoted step
#: statistic lands.  Names rather than classes, because this module imports
#: nothing but the standard library at its top.
RESULT_FIELD_TYPES: tuple[str, ...] = (
    "RefinementResult", "StageResult", "SeriesEntry", "SeriesResult")

#: One entry per field of every type in :data:`RESULT_FIELD_TYPES`, keyed
#: ``"<Type>.<field>"`` (WP-2037).  A number in a result field costs nothing
#: until somebody reads it, where a diagnostic is a message on every run that
#: raises it, so a statistic demoted out of the diagnostics moves into a field
#: and keeps its explanation here.  :func:`explain` answers these keys beside
#: the diagnostic codes.  A field's default is its empty state, so instead of
#: quoting it an entry says what the empty state *means* — ``None`` is "not
#: measured here", never "no" (WP-1076).  ``unit`` is the field's own where it
#: has one.
RESULT_FIELD_HELP: dict[str, HelpEntry] = {
    # ---------------------------------------------------------- RefinementResult
    "RefinementResult.status": HelpEntry(
        title="Solver exit",
        description=(
            "How the solver stopped: `converged`, `max_iter` or `diverged`. It makes "
            "no claim that the fit is good, since a model that matches nothing can "
            "converge. Quality is in `diagnostics`, and `usable` reads both."
        ),
        anchor="theory/estimation.html#convergence",
    ),
    "RefinementResult.mode": HelpEntry(
        title="Intensity mode",
        description=(
            "How the fit treated the peak intensities. `rietveld` computes them from "
            "the structure; `lebail` and `pawley` extract them from the pattern and "
            "refine no structure."
        ),
    ),
    "RefinementResult.parameters": HelpEntry(
        title="Refined parameters",
        description=(
            "Every parameter the fit determined: the free ones and the tied or derived "
            "ones that follow them, each with its value, its esd and whether it sits on "
            "a bound. A parameter no stage freed, or one the fit held because the data "
            "could not see it, is absent."
        ),
    ),
    "RefinementResult.statistics": HelpEntry(
        title="Agreement indices",
        description=(
            "The agreement indices of the answer as Toby (2006) defines them: Rwp, Rp, "
            "Rexp, χ² and the goodness of fit, beside the point and parameter counts "
            "they rest on and the largest shift over esd in the last accepted step."
        ),
    ),
    "RefinementResult.stages": HelpEntry(
        title="Stage records",
        description=(
            "One record per stage the fit ran, in order, ending with the closing stage "
            "where the plan has one. Each says what the stage freed, what it held and "
            "why, and what it cost."
        ),
        anchor="theory/estimation.html#staged-strategy-and-series",
    ),
    "RefinementResult.diagnostics": HelpEntry(
        title="Findings",
        description=(
            "Every finding the fit raised, each with a code, a level, a message, the "
            "paths it is about and a suggested action. A `warning` is to be answered "
            "before quoting what it names; an `error` means the values are not a "
            "refinement of this model. `rietx.help.explain` says what a code means."
        ),
    ),
    "RefinementResult.provenance": HelpEntry(
        title="Provenance",
        description=(
            "What produced the result: the package and schema versions, the backend "
            "and its precision, the solver, the version of the report thresholds and "
            "when it was made."
        ),
    ),
    "RefinementResult.node_id": HelpEntry(
        title="History node",
        description=(
            "The history node this fit committed, which `Refinement.checkout` can "
            "restore. `None` when the refinement ran with history disabled."
        ),
    ),
    "RefinementResult.tree_id": HelpEntry(
        title="History tree",
        description=(
            "The history tree that node belongs to. A tree is pinned to one pattern by "
            "its data fingerprint. `None` when the refinement ran with history disabled."
        ),
    ),
    "RefinementResult.two_theta": HelpEntry(
        title="Fitted channels",
        description=(
            "The 2θ of every channel the fit used, in order. A channel outside the fit "
            "range or inside an excluded region is absent, so this can be shorter than "
            "the pattern file."
        ),
        unit="deg 2θ",
    ),
    "RefinementResult.y_obs": HelpEntry(
        title="Observed intensity",
        description=(
            "The observed intensity at each channel of `two_theta`, in the pattern's "
            "own intensity units. It is what the residual was computed against."
        ),
    ),
    "RefinementResult.y_calc": HelpEntry(
        title="Calculated intensity",
        description=(
            "The calculated intensity at each channel at the refined values, background "
            "included. The weighted difference between `y_obs` and this is what the "
            "fit minimised."
        ),
    ),
    "RefinementResult.y_background": HelpEntry(
        title="Background curve",
        description=(
            "The background part of `y_calc` at each channel: the whole declared "
            "background, any background humps included."
        ),
    ),
    "RefinementResult.sigma": HelpEntry(
        title="Channel weights",
        description=(
            "The σ each channel was weighted by: the file's esd column where it has "
            "one, else the Poisson estimate, widened only where a measured background "
            "adds its own counting statistics. Read it through `RefinementResult.sig`, "
            "which every weighted residual in the package divides by."
        ),
    ),
    "RefinementResult.ticks": HelpEntry(
        title="Reflection positions",
        description=(
            "Where the model puts each reflection, keyed by phase name: the Bragg "
            "angle plus the zero shift and the geometry's own shift. Every emission "
            "line's image is listed, so a Kα2 reflection has a tick of its own."
        ),
        unit="deg 2θ",
    ),
    "RefinementResult.tick_hkl": HelpEntry(
        title="Reflection indices",
        description=(
            "Which reflection each tick in `ticks` is, as Miller indices h k l, paired "
            "with the positions by index. A satellite carries a fourth number, its "
            "order. A key is absent rather than empty where the ticks have no index, as "
            "for peaks declared by their centre."
        ),
    ),
    "RefinementResult.radiation": HelpEntry(
        title="Radiation",
        description=(
            "The source the fit used: its kind and each emission line's wavelength at "
            "the answer, primary first, so a refined wavelength is recorded as "
            "refined. `RefinementResult.plot` names it on the 2θ axis. `None` means "
            "not recorded, as in a result saved before the field existed."
        ),
        anchor="reference/figures.html#the-fit-figure",
    ),
    "RefinementResult.qpa": HelpEntry(
        title="Weight fractions",
        description=(
            "The weight fraction of each modelled phase from the refined scales (Hill "
            "and Howard, 1987), with esds from the correlated scale block. The "
            "fractions are of the crystalline phases in the model, so they sum to one "
            "whatever else the specimen holds. `None` in Le Bail and Pawley fits, and "
            "where the fractions could not be formed, which `QPA_UNAVAILABLE` reports."
        ),
        anchor="theory/corrections.html#quantitative-phase-analysis-and-microabsorption",
    ),
    "RefinementResult.phase_agreement": HelpEntry(
        title="Per-phase R-factors",
        description=(
            "Each phase's Bragg R-factor and structure-factor R-factor, with the number "
            "of reflections behind them (`optimize.statistics.structure_r_factors`). "
            "The observed intensities are partitioned by the model's own prediction, so "
            "a low value is not evidence that a phase is present. Empty outside "
            "Rietveld mode."
        ),
    ),
    "RefinementResult.texture": HelpEntry(
        title="Texture evidence",
        description=(
            "For each phase with a spherical-harmonics texture, the texture index and "
            "the smallest pole-density multiplier over its reflections and over the "
            "whole sphere. A negative minimum is an unphysical texture, which "
            "`TEXTURE_NOT_POSITIVE` reports. Empty when no phase declares one, outside "
            "Rietveld mode and in a joint fit."
        ),
    ),
    "RefinementResult.data_support": HelpEntry(
        title="Observations against parameters",
        description=(
            "How many independent observations the pattern holds: the reflections "
            "measured, the count corrected for overlap, and each per structural "
            "parameter (`optimize.statistics`). It gates nothing. `None` for a joint "
            "fit, and for a result recorded before the field."
        ),
    ),
    "RefinementResult.absorption": HelpEntry(
        title="Absorption correction",
        description=(
            "The specimen absorption correction the fit applied, for a capillary or a "
            "flat plate, with the change in Biso it is equivalent to. That change, not "
            "Rwp, is what the correction buys. `None` when no correction applied, and "
            "outside Rietveld mode."
        ),
    ),
    "RefinementResult.restraints": HelpEntry(
        title="Restraint deviations",
        description=(
            "Each soft restraint's deviation from its target in units of its σ, and "
            "the pooled restraint χ². A large deviation is a restraint fighting the "
            "data, however good Rwp looks. `None` when no phase declared restraints."
        ),
    ),
    "RefinementResult.geometry": HelpEntry(
        title="Bond geometry",
        description=(
            "Bond distances and angles of the refined structure, each with an esd "
            "propagated through the whole covariance beside the diagonal-only one. An "
            "esd that cannot be measured is absent rather than zero. `None` outside "
            "Rietveld mode and when the result did not come from a fit."
        ),
    ),
    "RefinementResult.cell_volumes": HelpEntry(
        title="Cell volumes",
        description=(
            "Each phase's unit-cell volume with its esd through the covariance of the "
            "cell parameters, in every mode, since a Le Bail cell is a measurement too. "
            "`None` when the result did not come from a fit."
        ),
        unit="Å³",
    ),
    "RefinementResult.microstructure": HelpEntry(
        title="Size and strain",
        description=(
            "Each phase's coherent domain size and microstrain as physical numbers, "
            "with the Gaussian and Lorentzian readings given separately, the Scherrer "
            "constant used, and whether size and strain could be told apart. Empty when "
            "the fit had no compiled model to read a wavelength from."
        ),
    ),
    "RefinementResult.identifiability": HelpEntry(
        title="Degeneracy evidence",
        description=(
            "What the final Jacobian says about parameters the data cannot separate: "
            "how much of each structural column the background or an extra peak could "
            "imitate, the strongest correlations, the soft modes and the exchangeable "
            "pairs. A stored result keeps what the fit measured and cannot recompute "
            "it. `None` when the result did not come from a fit that ran the guards."
        ),
    ),
    "RefinementResult.parametric": HelpEntry(
        title="Parametric coefficients",
        description=(
            "The coefficients of every parametric equation a joint fit refined, in the "
            "caller's units at the equation's reference, each with its esd from the "
            "joint covariance or `None` where that gives none. `None` when no "
            "parametric equation was declared."
        ),
    ),
    "RefinementResult.parametric_form": HelpEntry(
        title="Parametric form tests",
        description=(
            "For each parametric equation, in declaration order, whether its form "
            "survives the data. `None` exactly when `parametric` is."
        ),
    ),
    "RefinementResult.parametric_form_joint": HelpEntry(
        title="Joint parametric form test",
        description=(
            "The form test of every tested parametric equation at once: the χ² that "
            "freeing each equation's target in every pattern would remove. It catches "
            "two wrong equations that each pass while the other is freed. `None` "
            "unless two or more equations were tested."
        ),
    ),
    "RefinementResult.parametric_equations": HelpEntry(
        title="Resolved parametric equations",
        description=(
            "Each parametric equation as the fit resolved it, with its coefficients' "
            "covariance in the caller's units, in declaration order. "
            "`RefinementResult.parametric_value` evaluates one at any coordinate. "
            "`None` exactly when `parametric` is, and on a result written before the "
            "field."
        ),
    ),
    "RefinementResult.n_extra_components": HelpEntry(
        title="Declared extra components",
        description=(
            "How many additive non-Bragg components the instrument declared, background "
            "humps and sharp peaks together, whether or not any was freed. `0` means "
            "none was declared; `None` means nothing counted, as in a joint fit or a "
            "result recorded before the field."
        ),
    ),
    "RefinementResult.n_background_components": HelpEntry(
        title="Declared background components",
        description=(
            "How many of the declared extra components land in the background. This is "
            "the background flexibility the caller granted, which a reader comparing "
            "two Rwp values needs to see. `0` means none; `None` means nothing counted."
        ),
    ),
    "RefinementResult.histograms": HelpEntry(
        title="Per-histogram results",
        description=(
            "One slice per pattern of a multi-histogram joint fit, each with its own "
            "curves, statistics and diagnostics, while `statistics` is then the pooled "
            "figure. Empty for an ordinary fit. `RefinementResult.for_histogram` gives "
            "one slice in a single fit's shape."
        ),
    ),
    # --------------------------------------------------------------- StageResult
    "StageResult.name": HelpEntry(
        title="Stage name",
        description=(
            "The stage's name from the plan. The stage a plan appends to converge the "
            "answer is named by `strategy.staged.CLOSING_STAGE_NAME`."
        ),
    ),
    "StageResult.status": HelpEntry(
        title="Stage solver exit",
        description=(
            "How the solver stopped in this stage: `converged`, `max_iter` or "
            "`diverged`. Earlier stages of a plan stop at a looser tolerance on "
            "purpose (`ftol`), so the last stage's exit is the one about the answer."
        ),
        anchor="theory/estimation.html#convergence",
    ),
    "StageResult.n_iterations": HelpEntry(
        title="Residual evaluations",
        description=(
            "The residual evaluations the stage's solve made, the starting one "
            "included, and both solves where the stage solved twice. The name says "
            "iterations but the count is evaluations, the unit a stage's `max_iter` "
            "budget is converted to through `NFEV_PER_ITERATION`."
        ),
    ),
    "StageResult.cost_initial": HelpEntry(
        title="Starting cost",
        description=(
            "The least-squares cost when the stage started: half the sum of squared "
            "weighted residuals over every row, the penalty and restraint rows included "
            "(`model.rows`)."
        ),
    ),
    "StageResult.cost_final": HelpEntry(
        title="Final cost",
        description=(
            "The least-squares cost where the stage stopped, on the same terms as "
            "`cost_initial`. The pair says how much the stage improved the fit."
        ),
    ),
    "StageResult.freed": HelpEntry(
        title="Parameters refined",
        description=(
            "The parameter paths this stage's `turn_on` patterns freed, less any the "
            "stage held. A locked, tied or held path is never here, and "
            "`ParameterRow.held_because` says why."
        ),
    ),
    "StageResult.ftol": HelpEntry(
        title="Tolerance the stage ran at",
        description=(
            "The relative cost-decrease tolerance this stage stopped at. `None` means "
            "the solver's own default, which a plan's last declared stage and its "
            "closing stage take; an earlier stage takes the plan's `intermediate_ftol` "
            "unless it declares its own."
        ),
        anchor="theory/estimation.html#convergence",
    ),
    "StageResult.window_area_tol": HelpEntry(
        title="Profile window fraction",
        description=(
            "The fraction of each peak's area this stage's profile windows dropped. "
            "`None` means `model.forward.WINDOW_AREA_TOL`, which every declared stage "
            "takes, and the closing stage runs at the plan's `closing_window_tol`. "
            "`model.forward.recorded_window_tol` turns this into what `compile_model` "
            "needs to reproduce the result's curves."
        ),
    ),
    "StageResult.window_loss": HelpEntry(
        title="Intensity outside stale windows",
        description=(
            "The share of the Bragg intensity this stage's profile windows dropped at "
            "its answer, against windows sized there. The windows are sized where the "
            "stage starts, so a peak that moved or broadened spills past them. "
            "Negative where the peaks narrowed. Above the stage's window fraction it "
            "feeds `STAGE_WINDOWS_STALE` on the last stage and the one before a closing "
            "stage; an earlier stage records it without a warning, since the stages "
            "after it refit its answer. Magnetic windows and extra peaks are not "
            "measured. `None` means nobody looked. A joint fit records its worst "
            "histogram."
        ),
    ),
    "StageResult.n_constraint_truncations": HelpEntry(
        title="Steps held on a constraint",
        description=(
            "How many solver steps were held on a linear-inequality constraint, such "
            "as the Stephens strain cone, because the step for the bounds alone crossed "
            "it. Always zero under the TRF solver. Nonzero in the last stage means the "
            "answer sits on a constraint face, which `CONSTRAINT_ACTIVE` reports."
        ),
    ),
    "StageResult.n_degenerate_cell_probes": HelpEntry(
        title="Degenerate cells refused",
        description=(
            "How many trial cells this stage's residual refused as degenerate, with "
            "zero or negative volume, pushing the solver back rather than failing. The "
            "cell parameters carry no bounds of their own, so an underdetermined cell "
            "can reach one often. Zero means this stage never did."
        ),
    ),
    "StageResult.n_lapack_fallbacks": HelpEntry(
        title="Decompositions repeated",
        description=(
            "How many matrix decompositions this stage repeated with LAPACK's "
            "QR-iteration driver because the default driver stopped without "
            "converging (`optimize.lapack`). The answer is the one a converging build "
            "computes. Zero means none needed it."
        ),
    ),
    "StageResult.held": HelpEntry(
        title="Held by the stage",
        description=(
            "Parameter columns this stage held fixed although its plan freed them, "
            "because the data could not determine them: the structural parameters of "
            "a phase too weak to see, for example. They are never in `freed`, and the "
            "stage's other fields say which test held which."
        ),
    ),
    "StageResult.held_reach": HelpEntry(
        title="Stopped with a held column",
        description=(
            "For each held column that drives other entries through a tie, the entries "
            "it stopped with it: holding a cubic `a` also stops `b` and `c`. A column "
            "that moved nothing else is absent, so `held` and these values together are "
            "every value the stage froze."
        ),
    ),
    "StageResult.scale_b_held": HelpEntry(
        title="Displacements held against the scale",
        description=(
            "For each phase, by index, whose displacement parameters this stage held "
            "because the fitted range cannot separate them from the phase's scale, the "
            "separation measured (`refine._scale_b_separation`, against "
            "`refine.SCALE_B_SEPARATION_FLOOR`). An empty mapping is a stage that "
            "looked and held nothing; `None` means nobody looked, as in a joint fit."
        ),
    ),
    "StageResult.width_twins_held": HelpEntry(
        title="Instrument widths held",
        description=(
            "For each instrument width term this stage held because a free specimen "
            "width has the same angular dependence, the specimen columns it pairs with "
            "(`refine._width_twin_flats`). The data see only the total width, so the "
            "instrument side is held where the stage found it. An empty mapping held "
            "nothing; `None` means a result stored before the field."
        ),
    ),
    "StageResult.released": HelpEntry(
        title="Released within the stage",
        description=(
            "Paths held at the start of the stage and freed again within it, because "
            "their phase rose above support while the stage solved, which then solved "
            "once more with them free. They refined, so they are not in `held`."
        ),
    ),
    "StageResult.moment_flat_axes": HelpEntry(
        title="Flat moment axes",
        description=(
            "For each magnetic site, keyed `phases.i.atoms.j`, whose moment azimuth "
            "this stage held as part of a flat combination of its two angles, the flat "
            "rotation axis as a unit vector in crystal-axis components. Empty on every "
            "fit where no such site was held."
        ),
    ),
    "StageResult.moment_turned": HelpEntry(
        title="Moments turned",
        description=(
            "The sites of `moment_flat_axes` whose moment the stage turned about the "
            "flat axis before holding it, a move the data cannot see that changes the "
            "direction the fit reports. A site held where it was is in "
            "`moment_flat_axes` alone."
        ),
    ),
    "StageResult.blocked_by_hold": HelpEntry(
        title="Blocked by a hold",
        description=(
            "Paths this stage's `turn_on` matched and did not free, because the caller "
            "declared a hold on them with `Refinement.hold`. A hold outranks a plan's "
            "pattern and lasts until `Refinement.unhold`. It feeds `HOLD_BLOCKED_PLAN`."
        ),
    ),
    "StageResult.unknown_paths": HelpEntry(
        title="Paths naming nothing",
        description=(
            "The literal paths in this stage's `turn_on`, and any retired spellings, "
            "that name no parameter of the model: a typo or a renamed path, so what the "
            "stage meant to refine did not refine. An empty list is a stage that was "
            "checked; `None` means nobody looked. It feeds `STAGE_PATH_UNKNOWN`."
        ),
    ),
    "StageResult.unreached_histograms": HelpEntry(
        title="Histograms a stage missed",
        description=(
            "Joint fits only: for each histogram, by index, the patterns of this stage "
            "that matched rows on another histogram and none on this one. A "
            "single-histogram fit writes an empty mapping; `None` means nobody looked. "
            "It feeds `STAGE_FREED_NOTHING`."
        ),
    ),
    "StageResult.seeded": HelpEntry(
        title="Rows lifted before solving",
        description=(
            "Each row this stage moved before solving, with the value it started at. A "
            "freed row sitting on a floor starts at the stage's `seed`, and an all-zero "
            "Stephens block is put on its isotropic ray by `strain_seed`. An empty "
            "mapping lifted nothing; `None` means a result stored before the field."
        ),
    ),
    "StageResult.moment_angle_tests": HelpEntry(
        title="Stationary-angle tests",
        description=(
            "The stationary-angle test the stage's covariance ran, one round per entry "
            "in order. An angle a round zeroed stayed free and kept its value but "
            "carries no esd. `None` means no test ran, for example because no moment "
            "angle was free beside its modulus. It feeds `MOMENT_ANGLE_STATIONARY`."
        ),
    ),
    "StageResult.cell_reset": HelpEntry(
        title="Cells put back",
        description=(
            "The free cell parameters this stage put back at their starting values, "
            "because a cell parameter of their phase left the safety window while it "
            "solved (`params.vector.CELL_SAFETY_FRACTION`). `CELL_RUNAWAY` names them "
            "and says what followed. An empty list is every stage of an ordinary fit; "
            "`None` means a result stored before the field."
        ),
    ),
    "StageResult.collapsed": HelpEntry(
        title="Restored and held",
        description=(
            "The free parameters this stage restored to their starting values and "
            "held, because its first solve found them flat: a phase whose scale fell "
            "under support, or a moment direction that stopped moving the pattern. "
            "Their first-solve values were a walk, not a measurement. A subset of "
            "`held`; `None` means a result stored before the field."
        ),
    ),
    # --------------------------------------------------------------- SeriesEntry
    "SeriesEntry.index": HelpEntry(
        title="Position in the series",
        description=(
            "The pattern's position in the series as given, counting from zero. It is "
            "the series axis when no coordinate was given."
        ),
    ),
    "SeriesEntry.label": HelpEntry(
        title="Pattern label",
        description=(
            "The pattern's name in the series: the label the run was given, else its "
            "source file's name, made unique because it also names the pattern's "
            "history file."
        ),
    ),
    "SeriesEntry.x": HelpEntry(
        title="Series coordinate",
        description=(
            "The pattern's series coordinate, such as a temperature, time or pressure, "
            "in the caller's units. `None` when the caller gave none, and `index` is "
            "then the axis."
        ),
    ),
    "SeriesEntry.status": HelpEntry(
        title="Pattern solver exit",
        description=(
            "The solver's exit for the attempt kept on this pattern. `diverged` after "
            "the last rung of the ladder means the pattern is quarantined: it seeds no "
            "successor and joins no median, and `SEQUENTIAL_UNRECOVERED` says so."
        ),
    ),
    "SeriesEntry.statistics": HelpEntry(
        title="Pattern agreement indices",
        description=(
            "The agreement indices of the kept attempt, the same table as "
            "`RefinementResult.statistics`. Every entry the chain builds carries one; "
            "`None` means none was recorded."
        ),
    ),
    "SeriesEntry.parameters": HelpEntry(
        title="Pattern parameters",
        description=(
            "The refined parameters of the kept attempt, as "
            "`RefinementResult.parameters` holds them. `SeriesResult.trajectory` reads "
            "one path across every entry."
        ),
    ),
    "SeriesEntry.qpa": HelpEntry(
        title="Pattern weight fractions",
        description=(
            "The weight fractions of the kept attempt, as `RefinementResult.qpa` holds "
            "them. `None` outside Rietveld mode and where the fractions could not be "
            "formed."
        ),
        anchor="theory/corrections.html#quantitative-phase-analysis-and-microabsorption",
    ),
    "SeriesEntry.phase_agreement": HelpEntry(
        title="Pattern R-factors",
        description=(
            "Each phase's Bragg and structure-factor R-factors on this pattern, copied "
            "from its result. A low value on a weak phase is not evidence the phase is "
            "present, because the observed intensity is partitioned by the model's own "
            "prediction. Empty outside Rietveld mode."
        ),
    ),
    "SeriesEntry.magnetic": HelpEntry(
        title="Moment evidence",
        description=(
            "The evidence for each magnetic site's moment on this pattern: whether the "
            "data support it, its esd and what the powder average cannot determine. A "
            "signed moment parameter alone draws an unsupported moment as a small one. "
            "Empty when no phase declares a moment or the pattern carries no magnetic "
            "term, and never because no moment was found."
        ),
    ),
    "SeriesEntry.diagnostics": HelpEntry(
        title="Pattern findings",
        description=(
            "The findings of this pattern's own fit. Findings about the series as a "
            "whole are on `SeriesResult.diagnostics`."
        ),
    ),
    "SeriesEntry.n_iterations": HelpEntry(
        title="Pattern evaluations",
        description=(
            "The residual evaluations spent on this pattern over every attempt, each "
            "rung of the escalation ladder included. It is what a warm start actually "
            "buys, measured rather than assumed."
        ),
    ),
    "SeriesEntry.reseeded": HelpEntry(
        title="Warm start rejected",
        description=(
            "Whether the warm start was rejected and the pattern refitted from the "
            "initial models, the `cold` rung. A reseeded point can be a good fit, but "
            "it is not evidence that the trajectory is continuous there. "
            "`SEQUENTIAL_RESEED` reports it."
        ),
    ),
    "SeriesEntry.rwp_warm": HelpEntry(
        title="Warm attempt's Rwp",
        description=(
            "The Rwp the first, warm attempt reached, recorded whenever the ladder "
            "escalated. With `reseeded` set too, a cold restart rescued the pattern; "
            "alone, the warm attempt stayed the best tried. `None` when the ladder did "
            "not escalate or the first attempt raised."
        ),
    ),
    "SeriesEntry.rung": HelpEntry(
        title="Winning rung",
        description=(
            "Which attempt produced this entry's values: `warm`, a one-stage refit from "
            "the neighbour; `warm_staged`, the full plan from the warm state; or "
            "`cold`, the full plan from the initial models. The first pattern is always "
            "`cold`, having no neighbour to start from."
        ),
    ),
    "SeriesEntry.rungs_tried": HelpEntry(
        title="Rungs tried",
        description=(
            "Every rung attempted on this pattern, in ladder order. One entry means the "
            "pattern fitted first time; `n_iterations` is the cost of these less the "
            "ones in `rungs_raised`."
        ),
    ),
    "SeriesEntry.rungs_raised": HelpEntry(
        title="Rungs that raised",
        description=(
            "The rungs whose fit raised an exception rather than returning, each with "
            "the exception's type and message. The ladder escalates past a raised rung "
            "as past a diverged one. Empty wherever no rung raised."
        ),
    ),
    "SeriesEntry.rwp_fence": HelpEntry(
        title="Rwp fence",
        description=(
            "The Rwp limit the chain set at this pattern, from `reseed_factor` and the "
            "Rwp of the patterns accepted before it (`sequential._rwp_fence`). An "
            "attempt above it climbs the ladder. `None` where no earlier pattern had "
            "been accepted, so no fence judged it."
        ),
    ),
    "SeriesEntry.seeded_from": HelpEntry(
        title="Warm start from",
        description=(
            "The index of the pattern whose fitted state this pattern's warm rungs "
            "started from: the last pattern accepted before it in the walk. A pattern "
            "that stayed diverged after every rung is skipped, so its successor names "
            "the pattern before it. It says where the warm start came from even when "
            "the kept attempt is the cold rung. `None` where there was no warm start."
        ),
    ),
    "SeriesEntry.floored": HelpEntry(
        title="Moments floored",
        description=(
            "The moment modulus paths this pattern's kept attempt received at the "
            "floor, because the pattern it warm-started from did not support them. "
            "Empty when the kept attempt started cold and on a series with no moment. "
            "`SEQUENTIAL_MOMENT_HOLD` names these patterns."
        ),
    ),
    "SeriesEntry.node_id": HelpEntry(
        title="Pattern history node",
        description=(
            "The history node of this pattern's kept fit. Each pattern has a tree of "
            "its own, pinned to it by its data fingerprint. `None` when the series ran "
            "without history."
        ),
    ),
    "SeriesEntry.tree_id": HelpEntry(
        title="Pattern history tree",
        description=(
            "The history tree this pattern's fit is in, one tree per pattern. `None` "
            "when the series ran without history."
        ),
    ),
    # -------------------------------------------------------------- SeriesResult
    "SeriesResult.mode": HelpEntry(
        title="Series intensity mode",
        description=(
            "The intensity mode every pattern of the series was fitted in. One protocol "
            "over every pattern is what makes their trajectories comparable."
        ),
    ),
    "SeriesResult.entries": HelpEntry(
        title="Pattern summaries",
        description=(
            "One summary per pattern that returned a fit, in series order: its refined "
            "values, agreement indices, findings and how the chain reached it. Curves "
            "are not kept; `SequentialRefinement.results_` holds each full result."
        ),
        anchor="theory/estimation.html#staged-strategy-and-series",
    ),
    "SeriesResult.x_label": HelpEntry(
        title="Series axis name",
        description=(
            "The name of the series coordinate, such as temperature or time, for plots "
            "and trajectories. When no coordinate was given the pattern index is the "
            "axis, and this says so."
        ),
    ),
    "SeriesResult.direction": HelpEntry(
        title="Chain direction",
        description=(
            "Which way the chain ran: `forward`, `backward`, or `both`, which runs it "
            "each way and compares the two trajectories. Under `both` the entries are "
            "the forward chain's and the comparison is `SEQUENTIAL_PATH_DEPENDENT`."
        ),
    ),
    "SeriesResult.backward": HelpEntry(
        title="Reverse chain",
        description=(
            "The reverse chain's own series result when `direction` is `both`, so the "
            "trajectory a path-dependence finding is about can be read. `None` for a "
            "one-way run."
        ),
    ),
    "SeriesResult.diagnostics": HelpEntry(
        title="Series findings",
        description=(
            "Findings about the series as a whole, such as path dependence, reseeds "
            "and patterns that failed. Each pattern's own findings stay on its entry, "
            "and the steps between patterns are `steps`, not findings."
        ),
    ),
    "SeriesResult.steps": HelpEntry(
        title="Steps between patterns",
        description=(
            "Every parameter's change between consecutive patterns, in esds of the "
            "later fit, largest first: the path, the two patterns, the signed step and "
            "its size in esds, which is `None` where the later fit measured no esd. A "
            "step may be a phase transition, a sample shift, a beam dump or a wrong "
            "model, and only the sample history can say which; rietx enforces no "
            "threshold on it. A symmetry-mode refinement across the step is what "
            "separates a transition from the rest. `fit(verify_steps=k)` refits the "
            "two patterns of the k largest cold and independently and records "
            "`cold_ratio`: near 1 the step is in the data, near 0 the chain made it. "
            "Steps into or out of a rejected pattern are left out; `None` means a "
            "document written before the field."
        ),
    ),
    "SeriesResult.relative_paths": HelpEntry(
        title="Paths that are steps",
        description=(
            "The paths whose values are steps from where each fit began rather than "
            "positions, such as coordinate DOFs and rigid-body rotations. A comparison "
            "across patterns must not read them as positions. `None` means a document "
            "written before the field."
        ),
    ),
    "SeriesResult.angle_paths": HelpEntry(
        title="Moment angle paths",
        description=(
            "The moment angle DOFs, whose differences across patterns are taken modulo "
            "a full turn. Recorded as `relative_paths` is, and `None` means the same."
        ),
    ),
    "SeriesResult.failures": HelpEntry(
        title="Patterns that failed",
        description=(
            "Every pattern on which every rung of the ladder raised an exception, so "
            "the chain has no entry for it: its index, its label and the last "
            "exception. An empty list means every pattern returned a fit."
        ),
    ),
    "SeriesResult.n_failed": HelpEntry(
        title="Failure count",
        description=(
            "How many patterns failed outright, the length of `failures`, for a caller "
            "that wants a number rather than a list to count."
        ),
    ),
    "SeriesResult.provenance": HelpEntry(
        title="Series provenance",
        description=(
            "What produced the series: the package version, backend, solver, version "
            "of the report thresholds and when it ran. `None` on the reverse chain in "
            "`backward`, which carries none of its own."
        ),
    ),
}


def plan_help() -> dict[str, HelpEntry]:
    """The plan presets as help entries, projected from ``PLAN_INFO``.

    ``PLAN_INFO`` is already the authority for what a preset is for, held in
    bijection with ``PLAN_PRESETS`` by its own meta-test, so this projects it
    rather than restating it: ``when_to_use`` becomes ``typical``, which is the
    field a reader scans to choose.  ``modes`` has no field on
    :class:`HelpEntry` and rides beside the entry in :func:`help_registry`.
    """
    from .strategy.staged import PLAN_INFO

    return {
        name: HelpEntry(
            title=info.title,
            description=info.description,
            typical=info.when_to_use,
            anchor="theory/estimation.html#staged-strategy-and-series",
        )
        for name, info in PLAN_INFO.items()
    }


def help_key_for(path: str) -> str | None:
    """The family glob that claims a parameter dot-path, or ``None``.

    Matching is :func:`fnmatch.fnmatchcase` against the keys of
    :data:`PARAMETER_HELP`, the same call ``ParameterTable.set_vary`` makes.
    ``tests/test_help.py`` asserts that every path a live ``ParameterTable``
    produces matches exactly one family, so the first match is the only match;
    a path from outside that vocabulary may match none, and gets ``None``
    rather than a guess.

    This is what :attr:`~rietx.schemas.params.ParameterRow.help_key` carries.
    A row holds the key rather than the entry because an entry describes a
    *family*, so inlining one repeats a paragraph once per atom: measured at
    3.4x the ``/api/params`` payload on an ordinary two-phase model (20.8 kB to
    70.0 kB), against 40.7 kB for the whole registry fetched once (221 kB
    since every diagnostic code carries its explanation, WP-1985, still one
    fetch: 1.0 ms to build and 0.4 ms to parse).  The server
    still owns the match, so no client re-derives it.
    """
    for glob in PARAMETER_HELP:
        if fnmatchcase(path, glob):
            return glob
    return None


def help_for(path: str) -> HelpEntry | None:
    """The entry for a parameter dot-path, or ``None`` if no family claims it.

    :func:`help_key_for` with the lookup done, for a caller holding one path
    rather than a table of them.
    """
    key = help_key_for(path)
    return None if key is None else PARAMETER_HELP[key]


def explain(name: str) -> HelpEntry | None:
    """What a diagnostic code or a result field means, or ``None`` with no entry.

    ``name`` is a diagnostic code (``"BOUND_HIT"``) or a result field as
    ``"<Type>.<field>"`` (``"RefinementResult.status"``), the keys of
    :data:`DIAGNOSTIC_HELP` and :data:`RESULT_FIELD_HELP`.  One lookup serves
    both because the two key sets cannot collide: a code is UPPER_SNAKE with no
    dot, and every field key has one (``tests/test_help.py`` holds them
    disjoint).

    ``None`` covers a code a newer or older package raised, read from a stored
    file, and a field this build's types do not have: the registry describes
    this build, and an old file must always open.
    """
    entry = DIAGNOSTIC_HELP.get(name)
    return entry if entry is not None else RESULT_FIELD_HELP.get(name)


def help_registry() -> dict[str, object]:
    """The whole corpus as JSON-able data, for ``GET /api/help``.

    The parameter arm is a list rather than a mapping because several globs
    share one entry where they share a meaning, and the grouping is what a
    glossary or a filter wants: one object per entry, carrying every glob that
    reaches it, in the order the registry declares.  A row that already carries
    its own ``help`` needs none of this; the route exists for the arms no row
    carries.
    """
    from .strategy.staged import PLAN_INFO

    grouped: list[dict[str, object]] = []
    index: dict[int, dict[str, object]] = {}
    for glob, entry in PARAMETER_HELP.items():
        got = index.get(id(entry))
        if got is None:
            got = {"paths": [], **asdict(entry)}
            index[id(entry)] = got
            grouped.append(got)
        got["paths"].append(glob)  # type: ignore[union-attr]

    plans = plan_help()
    return {
        "parameters": grouped,
        "peak_flags": {k: asdict(v) for k, v in PEAK_FLAG_HELP.items()},
        "diagnostics": {k: asdict(v) for k, v in DIAGNOSTIC_HELP.items()},
        "peak_origins": {k: asdict(v) for k, v in PEAK_ORIGIN_HELP.items()},
        "stage_fields": {k: asdict(v) for k, v in STAGE_FIELD_HELP.items()},
        "reader_options": {k: asdict(v) for k, v in READER_OPTION_HELP.items()},
        "instrument_fields": {k: asdict(v) for k, v in INSTRUMENT_FIELD_HELP.items()},
        "search_fields": {k: asdict(v) for k, v in SEARCH_FIELD_HELP.items()},
        "plans": {k: {**asdict(v), "modes": list(PLAN_INFO[k].modes)}
                  for k, v in plans.items()},
        "result_fields": {k: asdict(v) for k, v in RESULT_FIELD_HELP.items()},
    }
