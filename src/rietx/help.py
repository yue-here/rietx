"""WP-1202 — one authority for what a name in this package *means*.

A parameter path, a peak flag, a stage field, a reader option, an instrument
preset field and an indexing search setting are all things a person has to be
told about, and before this module each was told about in a different place or
nowhere at all: 169 ``title=`` strings in the frontend, two hand-written
TypeScript corpora, and no description of ``instrument.profile.w`` anywhere in
the tree.  The corpus lives here so the GUI, the CLI and the manual read the
same sentence.

Two rules govern what may be written down here, both of them the root CLAUDE.md's
"a derived flag rots silently" one rank over.

**A fact the package already computes is never restated.**  ``unit`` and
``default`` are pinned to the live :class:`~rietx.schemas.common.Parameter` by
``tests/test_help.py``, through :data:`UNIT_DISPLAY` for the spelling difference
between a schema (``deg^2``) and a page (``deg² 2θ``); the plan arm is
:data:`~rietx.strategy.staged.PLAN_INFO` projected, not paraphrased.  A retuned
default or a renamed unit fails a test rather than leaving a stale number in
print.

**Every arm is meta-tested against its live registry.**  The vocabularies are
closed and derivable (``PeakFlag``, the ``PEAK_*`` diagnostic codes,
``StageSpec``'s fields, ``READER_OPTIONS``, ``INSTRUMENT_PRESETS``,
``IndexingControls`` flattened one level), so a member added without an entry
fails coverage the day it lands.  That is why the arms are
keyed by name and the parameter families by glob rather than being one flat dict:
each key set has a different authority to be checked against.

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
    "PEAK_DIAGNOSTIC_HELP",
    "PEAK_FLAG_HELP",
    "PEAK_ORIGIN_HELP",
    "READER_OPTION_HELP",
    "SEARCH_FIELD_HELP",
    "INSTRUMENT_FIELD_HELP",
    "STAGE_FIELD_HELP",
    "UNIT_DISPLAY",
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
    relative to the manual's root — so a consumer builds a link by joining it to
    :data:`rietx._about.DOCS_URL` and nothing has to know the manual's layout a
    second time.  It carried the id alone until WP-1203 needed to *render* the
    link and found that an id names no page; every one of the thirty was on
    exactly one page of the built manual, which is what made the change
    mechanical.  ``tests/test_help.py`` checks it against the built HTML rather
    than the sources — a heading that fails to render still has an id in the
    Markdown — and now checks the page as well as the id, which the bare form
    could not.

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
    "1e-12 A^-4": "10⁻¹² Å⁻⁴",
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
    title="Cell edge",
    description=(
        "A unit-cell edge length. Sets every reflection position through the "
        "lattice metric, so it is the parameter a powder pattern determines "
        "best and the one a systematic position error corrupts first. Edges "
        "the space-group setting ties to another (b to a in a tetragonal cell) "
        "are held and follow their source."
    ),
    unit="Å", default=None,
    typical="3-40 Å for an inorganic phase; refined shifts are 10-1000 ppm",
    anchor="peak-positions.html#lattice-metric-and-bragg-s-law",
)
_CELL_ANGLE = HelpEntry(
    title="Cell angle",
    description=(
        "A unit-cell angle. An angle the space-group setting fixes at 90° or "
        "120° is locked and cannot be freed; a monoclinic cell frees only its "
        "unique-axis angle."
    ),
    unit="deg", default=None,
    typical="90° or 120° when symmetry fixes it; 80-100° for a monoclinic β",
    anchor="peak-positions.html#lattice-metric-and-bragg-s-law",
)
_ATOM_COORD = HelpEntry(
    title="Fractional coordinate",
    description=(
        "An atom's position along a cell axis, in fractions of the edge. It is "
        "not refined directly: `ParameterTable` ties x, y and z to the site's "
        "symmetry degrees of freedom, so editing it means editing the "
        "`dof.k` entries it follows. An atom on a fully fixed special position "
        "has no free direction and its coordinates are locked."
    ),
    unit=None, default=None,
    typical="0 to 1",
    anchor="parameterisation.html#site-symmetry-degrees-of-freedom",
)
_ATOM_ANISO_U = HelpEntry(
    title="Anisotropic displacement component",
    description=(
        "One component of the stored CIF U^ij displacement tensor, in Å². Like "
        "the coordinates it is tied rather than free: the refined quantities "
        "are the `adp.k` entries of the site-symmetry-allowed subspace, and a "
        "tensor outside that subspace is refused rather than symmetrised."
    ),
    unit="Å²", default=None,
    typical="0.005-0.05 Å² on the diagonal; off-diagonal components are smaller",
    anchor="intensities.html#debye-waller-factors-and-adp-representations",
)
_STEPHENS_S = HelpEntry(
    title="Stephens strain coefficient",
    description=(
        "One S_HKL coefficient of the Stephens (1999) anisotropic strain "
        "model, multiplying the literal monomial h^H k^K l^L. Coefficients are "
        "in 10⁻¹² Å⁻⁴ because the physical Å⁻⁴ values near 10⁻⁸ would be "
        "finite-differenced with a step 100 times their own size. Like the "
        "ADP components these are tied: the refined quantities are the "
        "`microstrain.dof.k` entries of the Laue-allowed subspace."
    ),
    unit="10⁻¹² Å⁻⁴", default="0.0",
    typical="0-500 for a sample with measurable anisotropic strain",
    anchor="microstructure.html#stephens-anisotropic-strain",
)

PARAMETER_HELP: dict[str, HelpEntry] = {
    # -- instrument --------------------------------------------------
    "instrument.zero_shift": HelpEntry(
        title="Zero-point shift",
        description=(
            "A constant offset added to every calculated 2θ, absorbing the "
            "goniometer's zero-point misalignment. It is a property of the "
            "diffractometer, not of the specimen, so calibrate it on a "
            "standard with a certified cell and hold it afterwards. Freed "
            "alongside a free cell and a free sample displacement it is close "
            "to degenerate with both, which is what makes calibration on a "
            "held cell the step that separates the three."
        ),
        unit="deg 2θ", default="0.0",
        typical="|Δ| < 0.05 deg on an aligned diffractometer",
        anchor="peak-positions.html#aberration-shifts",
    ),
    "instrument.polarization": HelpEntry(
        title="Polarization factor",
        description=(
            "The K of the Lorentz-polarisation correction, "
            "(1 + K·cos²2θ)/(1 + K). Fixed by the beam optics, so it is "
            "declared and not refined: 0.5 for an unpolarised laboratory "
            "source, cos²2θ_M for a monochromated one, and 0.99 in the APS "
            "11-BM instrument-parameter files."
        ),
        unit=None, default="0.5",
        typical="0.5 unmonochromated lab; 0.9-1.0 synchrotron",
        anchor="corrections.html#lorentz-polarisation",
    ),
    "instrument.source.lines.*.wavelength": HelpEntry(
        title="Emission wavelength",
        description=(
            "One emission line's wavelength. Bragg's law fixes only the "
            "product of λ and the cell scale, so a free wavelength and a free "
            "cell are an exactly flat direction: the row reports "
            "`needs_held_cell` and `set_vary` refuses it while any cell is "
            "free. Refine it against a standard whose cell is certified, or "
            "leave it at the tabulated value."
        ),
        unit="Å", default=None,
        typical="1.540598 Å Cu Kα1, 0.7093 Å Mo Kα1, 0.3-1.0 Å synchrotron",
        anchor="peak-positions.html#the-wavelengthcell-degeneracy",
    ),
    "instrument.source.lines.*.weight": HelpEntry(
        title="Emission line weight",
        description=(
            "One emission line's intensity relative to line 0. Line 0 is "
            "structurally locked at 1 because it is degenerate with the phase "
            "scales, so only a second or later line carries a refinable "
            "weight. For a Kα doublet the value is the 2j+1 degeneracy ratio "
            "and needs refining only when a monochromator or a filter has "
            "changed it."
        ),
        unit=None, default="1.0",
        typical="0.5 for Kα2 against Kα1",
        anchor="peak-positions.html#wavelength-scales",
    ),
    "instrument.geometry.sample_displacement": HelpEntry(
        title="Specimen displacement",
        description=(
            "How far the specimen surface sits off the goniometer axis, "
            "positive toward the source and detector side of the focusing "
            "circle. On a Bragg-Brentano mount it shifts every "
            "line by −2s·cosθ/R (McCusker eq 3), which is the largest "
            "systematic position error a laboratory pattern usually carries. "
            "The cosθ shape is close to the constant shape of `zero_shift`, "
            "so freeing both on one pattern usually reports a correlation."
        ),
        unit="mm", default="0.0",
        typical="|s| < 0.05 mm on a carefully packed flat plate",
        anchor="peak-positions.html#aberration-shifts",
    ),
    "instrument.geometry.sample_transparency": HelpEntry(
        title="Specimen transparency",
        description=(
            "The coefficient of the sin 2θ position shift a beam penetrating "
            "into the specimen produces (McCusker eq 4). On a flat plate it is "
            "the transparency aberration; on a capillary the same sin 2θ shape "
            "is the along-beam offset instead, so this parameter belongs to a "
            "flat-plate geometry and the report suggests it only there."
        ),
        unit=None, default="0.0",
        typical="0-0.01 for a dense oxide; larger for a low-absorbing organic",
        anchor="peak-positions.html#aberration-shifts",
    ),
    "instrument.geometry.axial_sl": HelpEntry(
        title="Axial divergence: specimen length",
        description=(
            "The Finger-Cox-Jephcoat S/L, the illuminated specimen length "
            "divided by the goniometer radius. It sets how strongly low-angle "
            "peaks lean towards low 2θ. Fit it on a standard together with "
            "`axial_hl`; the two are strongly correlated and are usually "
            "reported as a pair."
        ),
        unit=None, default="0.0",
        typical="0.01-0.05",
        anchor="profiles.html#finger-cox-jephcoat-axial-divergence",
    ),
    "instrument.geometry.axial_hl": HelpEntry(
        title="Axial divergence: detector slit",
        description=(
            "The Finger-Cox-Jephcoat H/L, the receiving slit height divided by "
            "the goniometer radius. It is the second half of the axial "
            "asymmetry and is correlated with `axial_sl` closely enough that "
            "refining one while holding the other is a common protocol."
        ),
        unit=None, default="0.0",
        typical="0.01-0.05",
        anchor="profiles.html#finger-cox-jephcoat-axial-divergence",
    ),
    "instrument.geometry.capillary_offset_along_beam": HelpEntry(
        title="Capillary offset along the beam",
        description=(
            "How far the capillary axis sits from the rotation centre in the "
            "beam direction. It shifts positions as sin 2θ, the same shape "
            "flat-plate transparency has, and this is the parameter the report "
            "suggests for a Debye-Scherrer geometry."
        ),
        unit="mm", default="0.0",
        typical="|d| < 0.05 mm on an aligned spinner",
        anchor="peak-positions.html#aberration-shifts",
    ),
    "instrument.geometry.capillary_offset_across_beam": HelpEntry(
        title="Capillary offset across the beam",
        description=(
            "How far the capillary axis sits from the rotation centre "
            "perpendicular to the beam. It shifts positions as cos 2θ, so it "
            "is separable from the along-beam offset by shape, unlike the "
            "flat-plate pair."
        ),
        unit="mm", default="0.0",
        typical="|d| < 0.05 mm on an aligned spinner",
        anchor="peak-positions.html#aberration-shifts",
    ),
    # Surface roughness is an opt-in Bragg-Brentano block and the two models
    # are alternatives, so each field is its own family: one entry over
    # `surface_roughness.*` would have to quote four different schema defaults.
    "instrument.geometry.surface_roughness.a": HelpEntry(
        title="Suortti roughness: surviving fraction",
        description=(
            "The a of the Suortti (1972) surface-roughness correction, "
            "R = [a + (1 − a)·exp(−b/sinθ)] / [a + (1 − a)·exp(−b)]. It is the "
            "intensity fraction that survives even at grazing incidence, so "
            "1 − a bounds how deep the low-angle depression can go. Refine it "
            "with `b` and never alone: b = 0 is exactly the identity whatever "
            "a is."
        ),
        unit=None, default="0.5",
        typical="0.5-1; the default is interior because at a = 1 the gradient "
                "of b vanishes identically and it could never lift off",
        anchor="corrections.html#surface-roughness",
    ),
    "instrument.geometry.surface_roughness.b": HelpEntry(
        title="Suortti roughness: layer depth",
        description=(
            "The dimensionless optical depth of the depleted surface layer in "
            "the Suortti (1972) correction. It sets where in angle the "
            "depression falls, not how deep it goes. Both limits return the "
            "identity, so any one depression is reproducible by two values of "
            "b, and `ROUGHNESS_UNCONSTRAINED` measures the modelled depression "
            "rather than b itself. b = 0 is a dead gradient, so a stage that "
            "frees it seeds it."
        ),
        unit=None, default="0.0",
        typical="0.1-0.5; past about 3 the correction is dead and its gradient flat",
        anchor="corrections.html#surface-roughness",
    ),
    "instrument.geometry.surface_roughness.c": HelpEntry(
        title="Pitschke roughness: strength",
        description=(
            "The strength of the Pitschke et al. (1993) surface-roughness "
            "correction, R = 1 − c·u·(1 − u) with u = τ/sinθ. c = 0 is exactly "
            "no correction. The paper's angle-independent porosity term is "
            "deliberately absent here, because a constant prefactor is exactly "
            "degenerate with the phase scale."
        ),
        unit=None, default="0.0",
        typical="0-4; beyond 4 R can go negative inside the valid range",
        anchor="corrections.html#surface-roughness",
    ),
    "instrument.geometry.surface_roughness.tau": HelpEntry(
        title="Pitschke roughness: τ",
        description=(
            "The dimensionless surface-roughness parameter τ = t₀/β of the "
            "Pitschke et al. (1993) correction, refined directly rather than "
            "through a particle size the diffraction data cannot constrain. "
            "The correction is monotone only while sinθ ≥ 2τ and would amplify "
            "beyond sinθ = τ, which `ROUGHNESS_OUTSIDE_REGIME` reports: a box "
            "bound cannot express a fence that depends on the fitted range."
        ),
        unit=None, default="0.05",
        typical="0.005-0.12, the span of the paper's own four specimens",
        anchor="corrections.html#surface-roughness",
    ),
    "instrument.profile.u": HelpEntry(
        title="Caglioti U",
        description=(
            "The tan²θ term of the Gaussian variance, "
            "Γ_G² = U·tan²θ + V·tanθ + W. It is where instrumental strain-like "
            "broadening lives, and a phase's `gauss_strain` adds to it: "
            "variances add under convolution, so instrument and specimen stack "
            "here rather than replacing each other. Refining U on a specimen "
            "whose `gauss_strain` is also free fits one quantity twice."
        ),
        unit="deg² 2θ", default="0.0",
        typical="0-0.05 on a laboratory diffractometer",
        anchor="profiles.html#thompson-cox-hastings-pseudo-voigt",
    ),
    "instrument.profile.v": HelpEntry(
        title="Caglioti V",
        description=(
            "The tanθ term of the Gaussian variance. It is the only Caglioti "
            "term allowed to be negative, and the minimum of the width curve "
            "sits where it cancels against U. Nothing in the specimen "
            "contributes to it, so it is purely instrumental."
        ),
        unit="deg² 2θ", default="0.0",
        typical="−0.05 to 0",
        anchor="profiles.html#thompson-cox-hastings-pseudo-voigt",
    ),
    "instrument.profile.w": HelpEntry(
        title="Caglioti W",
        description=(
            "The constant term of the Gaussian variance, so it sets the width "
            "the pattern would have at zero angle. It is bounded positive: a "
            "negative W is a negative variance. Freeing W together with a "
            "free `gauss_size` fits the same constant twice at low angle."
        ),
        unit="deg² 2θ", default="0.001",
        typical="0.001-0.02 on a laboratory diffractometer",
        anchor="profiles.html#thompson-cox-hastings-pseudo-voigt",
    ),
    "instrument.profile.x": HelpEntry(
        title="Lorentzian X",
        description=(
            "The 1/cosθ term of the Lorentzian FWHM, Γ_L = X/cosθ + Y·tanθ. "
            "The 1/cosθ shape is Scherrer size broadening, and a phase's "
            "`lor_size` adds to it, since Lorentzian FWHMs add under "
            "convolution. Document the physics rather than the letter: GSAS "
            "and FullProf swap the X and Y assignment."
        ),
        unit="deg 2θ", default="0.001",
        typical="0.001-0.05 on a laboratory diffractometer",
        anchor="profiles.html#thompson-cox-hastings-pseudo-voigt",
    ),
    "instrument.profile.y": HelpEntry(
        title="Lorentzian Y",
        description=(
            "The tanθ term of the Lorentzian FWHM. The tanθ shape is "
            "microstrain broadening, and a phase's `lor_strain` adds to it. "
            "An anisotropic strain block replaces the specimen half of this "
            "term with an hkl-dependent width and locks `lor_strain`, but "
            "leaves the instrumental Y alone."
        ),
        unit="deg 2θ", default="0.0",
        typical="0-0.05 on a laboratory diffractometer",
        anchor="profiles.html#thompson-cox-hastings-pseudo-voigt",
    ),
    "instrument.background.c*": HelpEntry(
        title="Background coefficient",
        description=(
            "One coefficient of the shifted-Chebyshev background, "
            "y_bkg = Σ c_n T_n(x) over the fitted 2θ range normalised to "
            "[−1, 1]. The model is linear in these, so their Jacobian columns "
            "are the basis functions themselves and they can be freed from the "
            "first stage. Adding terms until Rwp stops falling is the wrong "
            "test: a background flexible enough to imitate the peaks biases "
            "displacement parameters up and scales down while Rwp improves. "
            "Read `FitReport.background` instead."
        ),
        unit=None, default="0.0",
        typical="4-8 terms for a flat laboratory background; c0 is of the "
                "order of the observed background counts",
        anchor="background.html#choosing-the-flexibility",
    ),
    "instrument.background.air": HelpEntry(
        title="Air-scatter term",
        description=(
            "Scales an additive 1/(2θ) term for the low-angle air-scatter "
            "rise, carried by the P-spline background beside its spline "
            "coefficients. 0 is exactly no term, and that is where it belongs "
            "unless `rietx.background.diagnose` reports the rise: the shape is "
            "broad, so freeing it without cause gives the background one more "
            "way to imitate a peak."
        ),
        unit=None, default="0.0",
        typical="0 unless the pattern diagnostics report a low-angle rise",
        anchor="background.html#additive-models-never-subtraction",
    ),
    "instrument.background_peaks.*.position": HelpEntry(
        title="Background-peak position",
        description=(
            "The centre, in °2θ, of an explicit Gaussian background term — a "
            "diffuse or amorphous hump, a cryostat or sample-container "
            "contribution. Unbounded by default: it is not a Bragg position, so "
            "nothing constrains it but the data, and a caller who knows the "
            "fitted range may set min/max. A declared peak is inert (vary=False, "
            "height 0) until a stage frees it — nothing in the package adds one "
            "on its own. Freeing position, height and width together *is* a "
            "reflection with no cell behind it, which is why the fitted width is "
            "held to the resolution (`BACKGROUND_PEAK_TOO_NARROW`)."
        ),
        unit="deg 2θ", default="0.0",
        typical="wherever the diffuse feature sits, e.g. 14.4 on NIST BT-1",
        anchor="background.html#localised-flexibility-explicit-background-peaks",
    ),
    "instrument.background_peaks.*.height": HelpEntry(
        title="Background-peak height",
        description=(
            "The peak intensity of an explicit Gaussian background term, in the "
            "pattern's own count units. Softplus with min 0 because zero is the "
            "off state: h = 0 makes the whole term identically zero, so a "
            "declared-but-never-freed peak is bit-identical to no peak at all."
        ),
        unit="counts", default="0.0",
        typical="of the order of the hump's rise above the smooth background",
        anchor="background.html#localised-flexibility-explicit-background-peaks",
    ),
    "instrument.background_peaks.*.fwhm": HelpEntry(
        title="Background-peak width",
        description=(
            "The full width at half maximum, in °2θ, of an explicit Gaussian "
            "background term. What makes the term a *background* term is that "
            "this width comes from disorder rather than the goniometer, so it is "
            "many times the instrumental resolution; a fitted width approaching "
            "the resolution is a reflection being eaten, reported as "
            "`BACKGROUND_PEAK_TOO_NARROW`. Softplus, floored at a small positive "
            "value because the Gaussian divides by it."
        ),
        unit="deg 2θ", default="5.0",
        typical="several times the instrumental FWHM at that angle; ~6 on the "
                "BT-1 case this feature was measured on",
        anchor="background.html#localised-flexibility-explicit-background-peaks",
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
            "The multiplier on this phase's calculated intensity, and the only "
            "route by which the phase reaches the pattern at all. Quantitative "
            "phase analysis is computed from it through the Hill-Howard ZMV "
            "relation, so it carries the weight fractions. A scale that "
            "refines onto its lower bound means the data does not see the "
            "phase: the fit still reports convergence while the phase's cell "
            "drifts unconstrained, which is what `PHASE_UNCONSTRAINED` names."
        ),
        unit=None, default="1.0",
        typical="positive, spanning several orders of magnitude between phases",
        anchor="corrections.html#quantitative-phase-analysis-and-microabsorption",
    ),
    "phases.*.extinction": HelpEntry(
        title="Secondary extinction",
        description=(
            "The Sabine secondary-extinction coefficient, attenuating the "
            "strong low-angle reflections of a well-crystallised specimen. "
            "0 is exactly no correction, so a phase that does not free it is "
            "unaffected. The gradient at 0 is dead, which is why the staged "
            "plans seed it off zero with `Stage.seed` when they free it."
        ),
        unit=None, default="0.0",
        typical="0 for a ground powder; up to 1e-4 for large crystallites",
        anchor="corrections.html#secondary-extinction",
    ),
    "phases.*.lor_size": HelpEntry(
        title="Lorentzian size broadening",
        description=(
            "The specimen's 1/cosθ contribution to the Lorentzian FWHM, which "
            "is Scherrer broadening from finite crystallite size. It adds to "
            "the instrumental X. Calibrate the instrument on a standard, hold "
            "U V W X Y, then refine this and its three companions. "
            "It carries a default upper bound — a floor on the crystallite at "
            "2 nm, deliberately permissive so genuinely nanocrystalline "
            "specimens refine freely — which reports BOUND_HIT if reached. "
            "Setting max to any finite value is your own claim and switches "
            "that default off. A refined size below 5 nm raises "
            "SIZE_UNUSUALLY_SMALL, which flags rather than bounds."
        ),
        unit="deg 2θ", default="0.0",
        typical="0-0.3 deg; 0.1 deg is roughly a 100 nm domain at Cu Kα",
        anchor="microstructure.html#isotropic-size-and-strain",
    ),
    "phases.*.lor_strain": HelpEntry(
        title="Lorentzian strain broadening",
        description=(
            "The specimen's tanθ contribution to the Lorentzian FWHM, which is "
            "isotropic microstrain. It adds to the instrumental Y. Declaring a "
            "Stephens anisotropic strain block locks this parameter, because "
            "the isotropic direction of that block is identically this column. "
            "It carries a default upper bound derived from the fitted 2θ range "
            "— a line cannot be wider than the interval it was measured over — "
            "which sits two orders of magnitude above any specimen and reports "
            "BOUND_HIT if reached. Setting max to any finite value, however "
            "large, is your own claim and switches that default off. A width "
            "past 1.5 deg raises STRAIN_UNUSUALLY_LARGE, which flags rather "
            "than bounds."
        ),
        unit="deg 2θ", default="0.0",
        typical="0-0.3 deg",
        anchor="microstructure.html#isotropic-size-and-strain",
    ),
    "phases.*.gauss_size": HelpEntry(
        title="Gaussian size broadening",
        description=(
            "The specimen's 1/cos²θ contribution to the Gaussian variance. "
            "Gaussian variances add, so it stacks on the instrumental W and "
            "U rather than replacing them. Most specimens are better described "
            "by the Lorentzian pair; free this one when the peak shape is "
            "measurably more Gaussian than the standard's. "
            "It carries the same default 2 nm floor as lor_size, squared: this "
            "is a variance, so the cap on the width it contributes applies to "
            "its square root."
        ),
        unit="deg² 2θ", default="0.0",
        typical="0-0.05 deg²",
        anchor="microstructure.html#isotropic-size-and-strain",
    ),
    "phases.*.gauss_strain": HelpEntry(
        title="Gaussian strain broadening",
        description=(
            "The specimen's tan²θ contribution to the Gaussian variance, "
            "stacking on the instrumental U. Freeing it while U is also free "
            "fits one quantity twice, and the guard reports the correlation. "
            "It carries the same default upper bound as lor_strain, squared: "
            "this is a variance, so the cap on the width it contributes "
            "applies to its square root."
        ),
        unit="deg² 2θ", default="0.0",
        typical="0-0.05 deg²",
        anchor="microstructure.html#isotropic-size-and-strain",
    ),
    "phases.*.preferred_orientation.r": HelpEntry(
        title="March coefficient",
        description=(
            "The March-Dollase coefficient for preferred orientation along the "
            "declared hkl axis. r = 1 is exactly no correction. Which side of "
            "1 means platy and which means needle-like flips between "
            "reflection and transmission geometry, so read it against the "
            "mount rather than from the number alone. The bound is 0.15 "
            "rather than 0 because the March factor divides by r."
        ),
        unit=None, default="1.0",
        typical="0.6-1.4; a value outside 0.5-2 describes a texture few powder "
                "mounts produce",
        anchor="corrections.html#preferred-orientation-march-dollase",
    ),
    "phases.*.atoms.*.x": _ATOM_COORD,
    "phases.*.atoms.*.y": _ATOM_COORD,
    "phases.*.atoms.*.z": _ATOM_COORD,
    "phases.*.atoms.*.dof.*": HelpEntry(
        title="Site-symmetry coordinate degree of freedom",
        description=(
            "One allowed direction of motion for an atom on its Wyckoff site. "
            "This is the quantity that refines: x, y and z are affine-tied to "
            "the site's degrees of freedom, so the site symmetry holds exactly "
            "rather than approximately. A site with no allowed direction "
            "produces no `dof` entry and its coordinates are locked. Free them "
            "with the `phases.*.atoms.*.dof.*` glob."
        ),
        unit=None, default=None,
        typical="0 to 1, in the same units as the coordinate it drives",
        anchor="parameterisation.html#site-symmetry-degrees-of-freedom",
    ),
    "phases.*.atoms.*.occ": HelpEntry(
        title="Site occupancy",
        description=(
            "The fraction of the site occupied by this species. It is close to "
            "degenerate with the site's displacement parameter, since both "
            "reduce scattered intensity, and X-rays separate the two poorly. "
            "Refine one or the other unless the data reaches high Q, and "
            "constrain occupancies that must sum to 1 with a user tie."
        ),
        unit=None, default="1.0",
        typical="0 to 1; the bound allows 1.5 so a shared site can be modelled",
        anchor="intensities.html#the-structure-factor",
    ),
    "phases.*.atoms.*.biso": HelpEntry(
        title="Isotropic displacement parameter",
        description=(
            "The atom's isotropic B, related to the mean-square displacement "
            "by B = 8π²·Uiso. It damps intensity as exp(−B·sin²θ/λ²), so it is "
            "determined by the high-angle data and is the parameter a "
            "too-flexible background biases first. A negative B is "
            "unphysical and the bound is at 0; a refined B above about 5 Å² "
            "for a heavy atom usually means an absorption or background error "
            "rather than a real displacement."
        ),
        unit="Å²", default="0.5",
        typical="0.2-2 Å² for an inorganic framework at room temperature",
        anchor="intensities.html#debye-waller-factors-and-adp-representations",
    ),
    "phases.*.atoms.*.u11": _ATOM_ANISO_U,
    "phases.*.atoms.*.u22": _ATOM_ANISO_U,
    "phases.*.atoms.*.u33": _ATOM_ANISO_U,
    "phases.*.atoms.*.u12": _ATOM_ANISO_U,
    "phases.*.atoms.*.u13": _ATOM_ANISO_U,
    "phases.*.atoms.*.u23": _ATOM_ANISO_U,
    "phases.*.atoms.*.adp.*": HelpEntry(
        title="Site-symmetry ADP degree of freedom",
        description=(
            "One allowed component of the anisotropic displacement tensor on "
            "this Wyckoff site. Unlike a coordinate degree of freedom these "
            "are absolute rather than incremental: U is the sum of θ_k times "
            "the basis tensors, which enforces the site symmetry exactly. "
            "Positive-definiteness couples all six components and so is not a "
            "bound; a tensor that loses it raises "
            "`ADP_NOT_POSITIVE_DEFINITE`, because the Debye-Waller factor "
            "then diverges at high Q. Free them with the "
            "`phases.*.atoms.*.adp.*` glob, alongside the `biso` glob every "
            "displacement stage carries."
        ),
        unit="Å²", default=None,
        typical="0.005-0.05 Å²",
        anchor="intensities.html#debye-waller-factors-and-adp-representations",
    ),
    "phases.*.microstrain.s*": _STEPHENS_S,
    "phases.*.microstrain.dof.*": HelpEntry(
        title="Stephens strain degree of freedom",
        description=(
            "One allowed direction of the Laue-permitted S_HKL subspace, "
            "derived from the space-group operators rather than tabulated. "
            "These are what refine; the fifteen `s` coefficients are tied to "
            "them. Seed an all-zero block onto the isotropic ray with "
            "`Stage.strain_seed`: at S = 0 the square root in the width has "
            "unbounded slope. Positivity of σ²(M) is a cone coupling all "
            "fifteen coefficients, so under the default solver it is reported "
            "by `STEPHENS_STRAIN_NOT_POSITIVE` rather than bounded. Read that "
            "flag as 'these coefficients are not quotable', not as evidence of "
            "anisotropy."
        ),
        unit=None, default=None,
        typical="the isotropic seed is ε²·[M²] for a strain ε of 1e-4 to 1e-3",
        anchor="microstructure.html#the-positivity-cone-the-seed-and-how-to-read-the-guard",
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
    "ghost_kbeta": HelpEntry(
        title="Kβ contamination line",
        label="Kβ ghost",
        description=(
            "The line sits where the Kβ partner of a stronger reflection "
            "would be. It is excluded rather than stripped: Rachinger "
            "stripping redistributes the counting noise and biases what is "
            "left. The line is unusable as evidence of a lattice."
        ),
        anchor="peak-positions.html#wavelength-scales",
    ),
    "ghost_tungsten": HelpEntry(
        title="Tungsten contamination line",
        label="W ghost",
        description=(
            "The line sits at a tungsten L emission position, which an aged "
            "tube with a contaminated anode produces. Excluded for the same "
            "reason as a Kβ ghost, and unusable."
        ),
        anchor="peak-positions.html#wavelength-scales",
    ),
    "excluded": HelpEntry(
        title="Excluded by the caller",
        label="excluded",
        description=(
            "Someone removed this line by hand. It stays in the list so a "
            "report can say the line was seen and dropped, and it is not "
            "offered as evidence."
        ),
    ),
    "fit_failed": HelpEntry(
        title="Group fit did not converge",
        label="fit failed",
        description=(
            "The solve over this line's group did not converge, so the "
            "position and σ on the row are the detection seed rather than a "
            "measurement. Unusable."
        ),
    ),
    "sigma_assumed": HelpEntry(
        title="σ assumed, not fitted",
        label="σ assumed",
        description=(
            "The position uncertainty was supplied rather than measured, "
            "which is what happens to a list read from a publication or "
            "another program. The line is still evidence, and its σ already "
            "says how good it is, so it stays usable. Treat the precision as "
            "unknown rather than quoting it."
        ),
    ),
    "unresolved_shoulder": HelpEntry(
        title="Never separated from its neighbour",
        label="shoulder",
        description=(
            "The component was kept in a group where it never moved half a "
            "FWHM away from its neighbour. It is less precise evidence rather "
            "than none, so it stays usable."
        ),
    ),
    "position_at_bound": HelpEntry(
        title="Position refined to its bound",
        label="at bound",
        description=(
            "The fitted position reached the limit it was allowed to move "
            "from its seed, which means detection put the seed in the wrong "
            "place. The position is a bound, not a minimum."
        ),
    ),
    "asymmetry_unmodelled": HelpEntry(
        title="Asymmetry the shape does not carry",
        label="asymmetric",
        description=(
            "The residual over this line is asymmetric beyond what the fitted "
            "shape allows, so the position is biased towards the tail. Axial "
            "divergence at low 2θ is the usual cause."
        ),
        anchor="profiles.html#finger-cox-jephcoat-axial-divergence",
    ),
    "not_separable": HelpEntry(
        title="Improves the group as a shape, not as a line",
        label="not separable",
        description=(
            "The component makes the group fit measurably better, but a "
            "nested fit without it is not refuted, so it is not evidence of a "
            "distinct reflection. It stays in the model, because removing it "
            "would bias the position of the line it sits on, and it is never "
            "offered to an indexing engine."
        ),
    ),
    "background_extrapolated": HelpEntry(
        title="Standing on extrapolated background",
        label="bkg extrapolated",
        description=(
            "The line's prominence is measured against a background level "
            "that was extrapolated rather than observed. That is real "
            "intensity which may not be a line. It is reported and not "
            "refused, because a consumer that can weigh the evidence should "
            "be given the chance."
        ),
        anchor="background.html#model-free-estimation",
    ),
    "axial_tail": HelpEntry(
        title="Possibly a stronger line's axial tail",
        label="axial tail",
        description=(
            "A weak component within 3.5 fitted FWHM of a stronger group-mate, "
            "on the side axial divergence points: towards low 2θ below 90° and "
            "towards high 2θ above it. The screen is one-sided, because "
            "nothing else in a powder pattern flips sign at 90°. Reported and "
            "not refused, since a real line can coincide with a tail."
        ),
        anchor="profiles.html#finger-cox-jephcoat-axial-divergence",
    ),
    "kalpha2_residual": HelpEntry(
        title="Sitting on a modelled Kα2 maximum",
        label="Kα2 residual",
        description=(
            "The component sits at the Kα2 position of a stronger group-mate, "
            "predicted from the declared doublet splitting as "
            "δ(2θ) = 2·(λ₂/λ₁ − 1)·tanθ rather than found by a distance "
            "threshold. It is the residual of a doublet the model already "
            "carries. Reported and not refused, since a real line can "
            "coincide with it."
        ),
        anchor="peak-positions.html#wavelength-scales",
    ),
    "unnamed_neighbour": HelpEntry(
        title="An unnamed component shares this window",
        label="unnamed neighbour",
        description=(
            "You named the components in this window, and detection found "
            "another one you did not name. Its intensity had nowhere to go but "
            "into the components that were fitted, so their positions are "
            "biased towards it and χ²_red is the only other sign. Reported and "
            "not refused: naming a subset is a legitimate request, and the esd "
            "inflation by the square root of χ²_red already carries the cost. "
            "Name the neighbour too, or narrow the range, if the position "
            "matters."
        ),
    ),
    "no_intensity": HelpEntry(
        title="Refined to zero intensity",
        label="no intensity",
        description=(
            "The component reached its zero-intensity bound, so it "
            "contributes nothing to the window and its own position is no "
            "longer identifiable: a peak reaches the data only through "
            "intensity times profile. Unusable, and unlike the reported flags "
            "there is no judgement left to make."
        ),
    ),
}

#: One entry per value of :attr:`~rietx.schemas.indexing.ObservedPeak.origin`
#: (WP-1209).  Provenance, not a judgement — the schema's own words — and the
#: GUI draws a chip for the two that mean a person acted, so each carries a
#: ``label``.
PEAK_ORIGIN_HELP: dict[str, HelpEntry] = {
    "fitted": HelpEntry(
        title="Proposed by detection",
        label="fitted",
        description=(
            "Detection found a maximum or a shoulder here and the group fit "
            "kept it. Nobody has touched the line: its position, width and "
            "area are the fitter's, and so are its flags."
        ),
    ),
    "manual": HelpEntry(
        title="Placed by a person",
        label="manual",
        description=(
            "Someone added this line by clicking the plot or typing a 2θ. Its "
            "position was still fitted, within the group it landed in, but "
            "the decision that a line exists here is a person's, so the "
            "picker's own screens never remove it."
        ),
    ),
    "edited": HelpEntry(
        title="Moved by a person",
        label="moved",
        description=(
            "Detection proposed this line and a person dragged it or typed a "
            "new 2θ; the group was refitted from the new seed. The position "
            "shown is the refit's, not the pointer's."
        ),
    ),
}

#: One entry per ``PEAK_*`` diagnostic code the peak-picking route emits.  These
#: are messages about the *list*, where a ``PeakFlag`` is a fact about one line;
#: several codes are the list-level summary of a flag, and say how many lines
#: carry it.
PEAK_DIAGNOSTIC_HELP: dict[str, HelpEntry] = {
    "PEAK_LIST_TOO_SHORT": HelpEntry(
        title="Too few usable lines to index",
        description=(
            "The list has fewer usable lines than an indexing search needs. "
            "The classical figures of merit are also undefined below that "
            "count, which caps confidence rather than refuting any cell. "
            "Widen the 2θ range, count for longer, or lower the detection "
            "threshold and check what arrives."
        ),
        anchor="using/indexing.html#the-confidence-gate",
    ),
    "PEAK_SIGMA_ASSUMED": HelpEntry(
        title="Position uncertainties were assumed",
        description=(
            "Some or all lines carry an assumed σ(2θ) rather than a fitted "
            "one, which is what a list of bare positions produces. Downstream "
            "gates treat the precision as unmeasured."
        ),
    ),
    "PEAK_UNRESOLVED_SHOULDER": HelpEntry(
        title="Components that never separated",
        description=(
            "Lines were kept in groups where they stayed within half a FWHM of "
            "a neighbour. Their positions are correlated with their "
            "neighbours' and are less precise than their σ alone suggests."
        ),
    ),
    "PEAK_NOT_SEPARABLE": HelpEntry(
        title="Components refuted as distinct lines",
        description=(
            "Components improved their group's fit but did not survive the "
            "nested comparison against a fit without them. They stay in the "
            "model and are withheld from indexing."
        ),
    ),
    "PEAK_ASYMMETRY_UNMODELLED": HelpEntry(
        title="Asymmetry the peak shape does not carry",
        description=(
            "Lines show asymmetric residuals beyond the fitted shape, so "
            "their positions are pulled towards the tail. Declaring the axial "
            "divergence terms is the usual fix."
        ),
        anchor="profiles.html#finger-cox-jephcoat-axial-divergence",
    ),
    "PEAK_AXIAL_TAIL": HelpEntry(
        title="Weak lines that may be axial tails",
        description=(
            "Weak components lie within 3.5 FWHM of a stronger group-mate on "
            "the side axial divergence points. They may be real lines and are "
            "reported rather than removed."
        ),
        anchor="profiles.html#finger-cox-jephcoat-axial-divergence",
    ),
    "PEAK_KALPHA2_RESIDUAL": HelpEntry(
        title="Components on a modelled Kα2 maximum",
        description=(
            "Components sit where the Kα2 partner of a stronger line is "
            "already modelled, so they are that doublet's residual rather "
            "than new lines. Reported rather than removed."
        ),
        anchor="peak-positions.html#wavelength-scales",
    ),
    "PEAK_KALPHA2_ALIAS": HelpEntry(
        title="Kα2 candidates dropped before fitting",
        description=(
            "Detection found candidates at the Kα2 positions of stronger "
            "lines and dropped them before any fit. The drop is reported "
            "because a genuine weak line can alias onto one."
        ),
        anchor="peak-positions.html#wavelength-scales",
    ),
    "PEAK_CONTAMINATION_LINE": HelpEntry(
        title="Contamination lines excluded",
        description=(
            "Lines were identified as Kβ or tungsten emission and excluded. "
            "They are excluded and never stripped, because stripping "
            "redistributes the counting noise."
        ),
        anchor="peak-positions.html#wavelength-scales",
    ),
    "PEAK_SHOULDER_SEEDED": HelpEntry(
        title="Extra components seeded from the residual",
        description=(
            "The width census found groups wider than the instrument's own "
            "law allows, so extra components were seeded into them from the "
            "residual. Check that the added lines are real before indexing on "
            "them."
        ),
    ),
    "PEAK_WIDTH_LAW_MISMATCH": HelpEntry(
        title="Fitted widths disagree with the instrument",
        description=(
            "The fitted widths do not follow the declared instrumental width "
            "law. Either the specimen is broadened, which is a finding, or "
            "the declared instrument is wrong, which is a setup error. The "
            "message carries the ratio so the two can be told apart."
        ),
        anchor="profiles.html#the-instrument-sample-width-split",
    ),
    "PEAK_POSITION_PRECISION": HelpEntry(
        title="Position precision relative to the line spacing",
        description=(
            "States the measured position precision against what an indexing "
            "search needs. A cell search matches within an assumed systematic "
            "allowance rather than within σ, so this is context for reading a "
            "search result, not a refusal."
        ),
        anchor="using/indexing.html#the-confidence-gate",
    ),
}


#: One entry per field of :class:`~rietx.schemas.plan.StageSpec`.  These are
#: settings for one stage of a plan, not refined quantities, so ``default`` is
#: the schema's default and ``typical`` says what a preset actually uses.
STAGE_FIELD_HELP: dict[str, HelpEntry] = {
    "name": HelpEntry(
        title="Stage name",
        description=(
            "A label for the stage. It appears in the stage table, in the "
            "history node this stage commits, and in any diagnostic that has "
            "to say where a finding came from."
        ),
    ),
    "turn_on": HelpEntry(
        title="Parameters freed this stage",
        description=(
            "Dot-path globs freed when the stage starts, matched with "
            "`fnmatch`: `phases.*.cell.*` frees every cell parameter of every "
            "phase. Staging is cumulative, so a parameter freed here keeps "
            "refining in every later stage. Paths never contain brackets, "
            "because `fnmatch` reads them as a character class."
        ),
        default="[]",
        typical="one or two globs per stage",
        anchor="parameterisation.html#from-tree-to-vector",
    ),
    "max_iter": HelpEntry(
        title="Iteration budget",
        description=(
            "Approximate solver iterations for this stage. The trust-region "
            "solver caps function evaluations rather than iterations, so the "
            "number is scaled by a measured worst-case rejection rate before "
            "it reaches the solver."
        ),
        default="100",
        typical="20-100",
        anchor="estimation.html#convergence",
    ),
    "ftol": HelpEntry(
        title="Stage termination tolerance",
        description=(
            "This stage's own relative cost-decrease tolerance, overriding "
            "the plan's schedule. Null takes it from the plan, which runs "
            "every stage but the last at `intermediate_ftol` and the last at "
            "the solver's 1e-9. The record says what a stage ran at, never "
            "what it declared, so a cherry-pick replays what happened."
        ),
        default="null",
        typical="leave null unless reproducing a specific run",
        anchor="estimation.html#convergence",
    ),
    "lebail_cycles": HelpEntry(
        title="Le Bail cycles per evaluation",
        description=(
            "How many intensity-partitioning cycles run before each solve in "
            "`lebail` mode. Ignored in `rietveld` and `pawley` modes, where "
            "intensities come from the structure or from the parameter vector."
        ),
        default="3",
        typical="3",
        anchor="forward-model.html#three-intensity-models",
    ),
    "seed": HelpEntry(
        title="Softplus seed value",
        description=(
            "Lifts any softplus-floored parameter this stage frees to this "
            "value. A parameter sitting exactly at its floor has no gradient, "
            "so a stage that frees extinction without seeding it refines "
            "nothing. Use `strain_seed` for a Stephens block: that one has "
            "the opposite problem."
        ),
        default="0.0",
        typical="1e-4 to 1e-3 where a stage frees extinction",
    ),
    "strain_seed": HelpEntry(
        title="Stephens strain seed",
        description=(
            "Microstrain in ppm used to seed an all-zero Stephens block onto "
            "the isotropic ray. At S = 0 the square root in the width law has "
            "unbounded slope, which is the opposite pathology to a dead "
            "gradient and needs its own setting: `seed` reaches softplus "
            "entries only, and these coefficients are not softplus."
        ),
        unit="ppm", default="0.0",
        typical="100-1000 ppm where a stage frees an anisotropic strain block",
        anchor="microstructure.html#the-positivity-cone-the-seed-and-how-to-read-the-guard",
    ),
    "restraint_weight_scale": HelpEntry(
        title="Restraint weight",
        description=(
            "The c_w of S = S_y + c_w·S_G (McCusker eq 7), weighting the "
            "geometric restraints against the diffraction data for this stage. "
            "Hold it high early and reduce it as the model improves. 1.0 is "
            "the identity and is bit-identical to no scaling; 0.0 silences the "
            "rows without removing them, so the restraint count the statistics "
            "rest on cannot move mid-plan."
        ),
        default="1.0",
        typical="1-100 early, falling to 1 in the last stage",
        anchor="parameterisation.html#weighting-the-restraints",
    ),
    "window_slack_deg": HelpEntry(
        title="Window capture slack",
        description=(
            "Extra 2θ on each side of a reflection's integration window, "
            "replacing the default. Declared by fits whose starting model may "
            "sit far from the data, such as the Le Bail validation an "
            "indexing candidate goes through. Null takes the default."
        ),
        unit="deg 2θ", default="null",
        typical="leave null outside indexing validation",
    ),
}

#: One entry per ``io.formats.base.READER_OPTIONS`` key.  ``ReaderOption.help``
#: stays as it is: it is a ``capabilities()`` contract written for a client
#: enumerating what a reader accepts.  These entries are the text a person
#: reads beside the control.
READER_OPTION_HELP: dict[str, HelpEntry] = {
    "block": HelpEntry(
        title="Data block",
        description=(
            "Which block of a multi-block file to read, matched by substring "
            "on the block name. A pdCIF carrying both a `_meas` and a `_calc` "
            "block is a different pattern depending on this, which is why the "
            "project records the option beside the file rather than only the "
            "file name."
        ),
        typical="`_meas` for measured data in a pdCIF",
    ),
    "scan": HelpEntry(
        title="Scan index",
        description=(
            "Which measurement to read from a file holding several, counting "
            "from 0. A vendor file commonly stores a whole session. Scans are "
            "selected and never concatenated: a multi-range file holds "
            "separate measurements, and joining them mixes two weighting "
            "regimes."
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
            "Which tube anode the pattern was measured with. It selects the "
            "Kα1 and Kα2 wavelengths from the package's NIST-scale table and "
            "the doublet weight, so it is the one entry a cell error of about "
            "100 ppm hides behind. Read it off the instrument rather than "
            "guessing from the peak positions."
        ),
        typical="`CuKa`, `MoKa`, `CoKa`, `CrKa`, `FeKa`, `AgKa`, or the "
                "`…Ka1` variant of any of them for a Kα1-only beam",
        anchor="peak-positions.html#wavelength-scales",
    ),
    "wavelength": HelpEntry(
        title="Wavelength",
        description=(
            "The incident wavelength, asked for by the Debye-Scherrer preset "
            "because it is the one geometry with no anode to read it from. A "
            "synchrotron or neutron beamline states it in the data file or "
            "the beamline record."
        ),
        unit="Å",
        typical="0.3-1.0 Å synchrotron, 1.0-2.5 Å constant-wavelength neutron",
        anchor="peak-positions.html#wavelength-scales",
    ),
    "polarization": HelpEntry(
        title="Polarization",
        description=(
            "The K of the Lorentz-polarisation correction. Only the "
            "Debye-Scherrer preset takes it, and leaving it empty there gives "
            "0.99, the APS 11-BM instrument-parameter value, not the 0.5 of an "
            "unpolarised laboratory beam. Neither flat-plate preset has the "
            "field: Bragg-Brentano derives K from `monochromator_two_theta` "
            "and transmission is unpolarised, K = 0.5."
        ),
        typical="0.99 is the preset default; 0.5 is an unpolarised lab beam",
        anchor="corrections.html#lorentz-polarisation",
    ),
    "goniometer_radius_mm": HelpEntry(
        title="Goniometer radius",
        description=(
            "The radius of the 2θ circle. The specimen-displacement shift "
            "divides by it (McCusker eq 3), so declaring it is what turns a "
            "refined displacement into millimetres instead of an arbitrary "
            "coefficient."
        ),
        unit="mm",
        typical="217.5 mm is a common benchtop value and the default",
        anchor="peak-positions.html#aberration-shifts",
    ),
    "monochromator_two_theta": HelpEntry(
        title="Monochromator 2θ",
        description=(
            "The take-off angle of a diffracted-beam monochromator crystal, "
            "which fixes the polarisation factor as cos²2θ_M. Leave it empty "
            "if there is no monochromator."
        ),
        unit="deg",
        typical="26.6° for graphite (002) at Cu Kα",
        anchor="corrections.html#lorentz-polarisation",
    ),
    "ka2_ratio": HelpEntry(
        title="Kα2 to Kα1 ratio",
        description=(
            "The intensity of the Kα2 line relative to Kα1. 0.5 is the 2j+1 "
            "degeneracy ratio and is the right starting value for every "
            "anode. Change it only when a monochromator or a filter has "
            "altered the doublet."
        ),
        default="0.5",
        typical="0.5",
        anchor="peak-positions.html#wavelength-scales",
    ),
    "capillary_radius_mm": HelpEntry(
        title="Capillary radius",
        description=(
            "The internal radius of the capillary bore, not its outside "
            "diameter. It is an input to estimating µR and never a refined "
            "quantity."
        ),
        unit="mm",
        typical="0.1-0.5 mm",
        anchor="corrections.html#capillary-cylindrical-absorption",
    ),
    "packing_fraction": HelpEntry(
        title="Packing fraction",
        description=(
            "The fraction of the bore or the specimen slab occupied by solid. "
            "An input to estimating µR and µt, never refinable. 0.3-0.6 covers "
            "a tapped powder and 0.64 is random close packing of spheres."
        ),
        default="0.6",
        typical="0.3-0.6",
        anchor="corrections.html#attenuation-coefficients",
    ),
    "mu_r": HelpEntry(
        title="µR",
        description=(
            "The capillary absorption parameter, the linear attenuation "
            "coefficient times the bore radius. Leave it empty for no "
            "correction: µR = 0 is the off state. It is not refinable, "
            "because it is exactly a reparameterisation of the phase scale "
            "and the displacement parameters, so the fit statistic cannot "
            "move. Its entire content is a shift of every B by "
            "c(µR)·λ²/2."
        ),
        typical="0-1 for a typical capillary mount",
        anchor="corrections.html#capillary-cylindrical-absorption",
    ),
    "mu_t": HelpEntry(
        title="µt",
        description=(
            "The flat-plate absorption parameter, the linear attenuation "
            "coefficient times the specimen thickness. The off state belongs "
            "to the geometry. On a Bragg-Brentano mount leaving it empty is "
            "the thick specimen, and µt = 0 there is a specimen of no "
            "thickness and is refused. In transmission µt = 0 is legal and is "
            "what empty means: a non-absorbing plate, still carrying the sec θ "
            "footprint factor. Declaring a thickness wrongly on a genuinely "
            "thick specimen makes the fit worse and biases every B downwards."
        ),
        typical="empty for a thick reflection specimen; 1-5 for a thin "
                "transmission mount",
        anchor="corrections.html#flat-plate-absorption",
    ),
    "thickness_mm": HelpEntry(
        title="Specimen thickness",
        description=(
            "For a reflection mount, the depth of the powder layer and not "
            "the depth of the holder. An input to estimating µt only. Leave "
            "it empty for a thick specimen."
        ),
        unit="mm",
        typical="0.1-2 mm for a transmission mount",
        anchor="corrections.html#flat-plate-absorption",
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
            "Which crystal systems the search covers, run in decreasing "
            "symmetry so a cubic answer arrives in seconds and a triclinic "
            "one in minutes. Restricting them is not a verdict about the "
            "specimen: the result reports the systems it searched, and says "
            "nothing about the ones it did not."
        ),
        typical="all seven; narrow only when a prior tells you the system",
        anchor="using/indexing.html#the-search-specification",
    ),
    "centrings": HelpEntry(
        title="Bravais centrings",
        description=(
            "Which lattice centrings to try within each system. Unticking one "
            "narrows the search and is recorded in the result's spec notes. "
            "At least one must stay in every system being searched."
        ),
        typical="all of them; a wrongly excluded centring costs the true cell",
        anchor="using/indexing.html#the-search-specification",
    ),
    "preset": HelpEntry(
        title="Search preset",
        description=(
            "The name of the whole-run ceiling. `quick`, the default, runs "
            "every engine and system under a measured ceiling and reports "
            "truncation loudly. `full` is unbounded. A typed whole-run budget "
            "overrides the preset and the result records `custom`."
        ),
        typical="`quick` for a first look, `full` when the answer matters",
        anchor="using/indexing.html#presets-budgets-and-the-three-states-of-a-system",
    ),
    "total_budget_seconds": HelpEntry(
        title="Whole-run budget",
        description=(
            "Wall-clock ceiling for the whole run: search, probe and "
            "validation together. Empty leaves it to the preset. Setting it "
            "overrides the preset's ceiling and the result records the preset "
            "as `custom`."
        ),
        unit="s",
        typical="empty; a few minutes if you are bounding an interactive click",
        anchor="using/indexing.html#presets-budgets-and-the-three-states-of-a-system",
    ),
    "budget_seconds": HelpEntry(
        title="Budget per search slice",
        description=(
            "Wall clock for one engine on one crystal system, not for the "
            "run. An engine stopped by it reports that system as incomplete, "
            "and a negative result from an incomplete search is not evidence "
            "against a cell."
        ),
        unit="s",
        default="30.0",
        typical="30 s; raise it for a triclinic search you intend to trust",
        anchor="using/indexing.html#presets-budgets-and-the-three-states-of-a-system",
    ),
    "min_d_axis": HelpEntry(
        title="Shortest principal d-spacing",
        description=(
            "The shortest principal d-spacing a candidate cell may have. It "
            "bounds d(100) rather than the axis a, which is slightly stronger "
            "for an oblique cell."
        ),
        unit="Å",
        default="2.0",
        typical="2 Å for an inorganic phase",
        anchor="using/indexing.html#the-search-specification",
    ),
    "max_d_axis": HelpEntry(
        title="Longest principal d-spacing",
        description=(
            "The longest principal d-spacing a candidate cell may have. "
            "Raising it costs exponentially, because the size of the domain "
            "is what an exhaustive search pays for."
        ),
        unit="Å",
        default="25.0",
        typical="25 Å; raise it only for a genuinely large cell",
        anchor="using/indexing.html#the-search-specification",
    ),
    "min_volume": HelpEntry(
        title="Smallest cell volume",
        description=(
            "The smallest cell volume a candidate may have. It removes the "
            "degenerate small cells that index a few lines by coincidence."
        ),
        unit="Å³",
        default="15.0",
        typical="15 Å³",
        anchor="using/indexing.html#the-search-specification",
    ),
    "max_volume": HelpEntry(
        title="Cell-volume ceiling",
        description=(
            "The largest cell volume a candidate may have, taken verbatim. "
            "Empty takes Smith's per-system envelope from the data-quality "
            "report, with the calibration slack the engines apply to a mean "
            "line."
        ),
        unit="Å³",
        typical="empty; state it only when you know the volume",
        anchor="using/indexing.html#the-search-specification",
    ),
    "n_unindexed": HelpEntry(
        title="Unindexed lines allowed",
        description=(
            "How many search lines a cell may leave unindexed and still be "
            "accepted. Raising it manufactures cells: every tolerated line is "
            "one more coincidence a wrong metric is allowed. Two is a "
            "default; four is a statement about the specimen."
        ),
        default="2",
        typical="2, or up to 4 on a pattern with a known impurity",
        anchor="using/indexing.html#the-search-specification",
    ),
    "n_search_lines": HelpEntry(
        title="Lines the search is driven by",
        description=(
            "How many of the strongest observed lines drive the search. It is "
            "not free to raise: a cell must index all but the allowance of "
            "these, so every extra foreign line can refute the true cell. "
            "Measured on a 68-line list, the certified lattice is lost at 32."
        ),
        default="20",
        typical="20; the tail of a list is where foreign lines live",
        anchor="using/indexing.html#the-search-specification",
    ),
    "k_sigma": HelpEntry(
        title="Matching window in σ",
        description=(
            "The matching window, in units of each line's own σ. Three is a "
            "99.7 % window and a calibrated figure rather than a knob. The "
            "systematic allowance below is the other half of the window, and "
            "it is the half a displaced pattern needs."
        ),
        default="3.0",
        typical="3",
        anchor="using/indexing.html#the-systematic-shift-and-the-window-it-opens",
    ),
    "shift_allowance_deg": HelpEntry(
        title="Systematic 2θ allowance",
        description=(
            "A systematic 2θ allowance you have measured: the amplitude a "
            "matching window has to span, never the residual scatter a "
            "template leaves after fitting. The two differ by 4.3× on a "
            "certified pattern, and declaring the scatter finds no cell at "
            "all. Zero lets the engines assume their own allowance and caps "
            "the confidence they may report."
        ),
        unit="deg 2θ",
        default="0.0",
        typical="0 unless an internal standard measured the shift",
        anchor="using/indexing.html#the-systematic-shift-and-the-window-it-opens",
    ),
    "shift_template": HelpEntry(
        title="Shift template",
        description=(
            "The physical cause of the 2θ shift, if you know it. A candidate "
            "that survives the search is re-fitted with this column, which is "
            "what stops a widened search reporting a biased cell."
        ),
        typical="`cos_theta` for specimen displacement, `constant` for a zero error",
        anchor="using/indexing.html#the-systematic-shift-and-the-window-it-opens",
    ),
    "max_candidates": HelpEntry(
        title="Candidates reported",
        description=(
            "How many candidates the reported list holds once the engines are "
            "merged and ranked. It also prices validation, since every "
            "reported candidate costs a Le Bail fit. Each engine hands the "
            "merge five times this many, so the cap never decides a rank."
        ),
        default="12",
        typical="12",
        anchor="using/indexing.html#the-result-object",
    ),
    "seed": HelpEntry(
        title="Random seed",
        description=(
            "The stochastic engine's RNG seed. It is recorded in every "
            "result, so a run is reproducible from what it reports."
        ),
        default="0",
        typical="0",
        anchor="using/indexing.html#the-search-specification",
    ),
    "prior_cells": HelpEntry(
        title="Analogue cells",
        description=(
            "Cells from a structural analogue, each as a b c α β γ. The "
            "system jumps the queue, the metric seeds the stochastic engine, "
            "and the cell itself is checked against the lines. A prior "
            "steers and never gates: a wrong one costs time rather than "
            "truth, and the result records what it changed."
        ),
        typical="empty; one analogue cell when the chemistry suggests one",
        anchor="using/indexing.html#the-search-specification",
    ),
    "prior_spacegroups": HelpEntry(
        title="Analogue space groups",
        description=(
            "Space-group symbols from a structural analogue, such as `R -3 c`. "
            "Each contributes its crystal system to the queue jump and, "
            "beside a matching prior cell, its centring."
        ),
        typical="empty",
        anchor="using/indexing.html#the-search-specification",
    ),
    "engines": HelpEntry(
        title="Engines to run",
        description=(
            "Which searches run. All of them is the default to keep, because "
            "high confidence means every engine that ran found the same "
            "lattice: a subset narrows what the answer is able to say."
        ),
        typical="all of them",
        anchor="using/indexing.html#three-engines-and-why-the-default-is-all-of-them",
    ),
    "validate_candidates": HelpEntry(
        title="Le Bail validation",
        description=(
            "Whole-profile validation of the top candidates. Turning it off "
            "caps every candidate at medium confidence, because the "
            "figure-of-merit panel cannot see a reflection predicted where "
            "the pattern has no intensity. Do it only to save time on a "
            "first look."
        ),
        default="true",
        typical="on",
        anchor="using/indexing.html#the-whole-profile-test",
    ),
    "check_top": HelpEntry(
        title="Candidates given the expensive checks",
        description=(
            "How many candidates get the per-candidate checks, which are the "
            "ambiguity search and the Le Bail fit. Empty takes the package "
            "default plus every candidate the confidence gate could promote."
        ),
        typical="empty",
        anchor="using/indexing.html#the-whole-profile-test",
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
            anchor="estimation.html#staged-strategy-and-series",
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
    70.0 kB), against 40.7 kB for the whole registry fetched once.  The server
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
        "peak_diagnostics": {k: asdict(v) for k, v in PEAK_DIAGNOSTIC_HELP.items()},
        "peak_origins": {k: asdict(v) for k, v in PEAK_ORIGIN_HELP.items()},
        "stage_fields": {k: asdict(v) for k, v in STAGE_FIELD_HELP.items()},
        "reader_options": {k: asdict(v) for k, v in READER_OPTION_HELP.items()},
        "instrument_fields": {k: asdict(v) for k, v in INSTRUMENT_FIELD_HELP.items()},
        "search_fields": {k: asdict(v) for k, v in SEARCH_FIELD_HELP.items()},
        "plans": {k: {**asdict(v), "modes": list(PLAN_INFO[k].modes)}
                  for k, v in plans.items()},
    }
