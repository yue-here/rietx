"""The feature registry (WP-2010): what a user switches on or refines, named once.

A feature is what a user switches on or refines, so it is keyed on the help
vocabulary: every :data:`rietx.help.PARAMETER_HELP` family and every
:data:`rietx.help.INSTRUMENT_FIELD_HELP` field belongs to exactly one feature.
An output topic with no parameter family of its own (phase analysis, indexing,
derived geometry, a width read as a size) is keyed on its Theory heading, since
DESIGN.md § Rules, 4 sends a new topic's equation there.  A heading is written
``"<page> § <heading text>"``, the page being a file under
``docs/docs/theory/``.  A feature with no Theory section says why in
``no_theory``.  :data:`NOT_FEATURES` holds the keys that name no feature (solver
machinery, a statistic, group mathematics no refinement uses), each with its
reason.  ``tests/test_validation_matrix.py`` holds both partitions closed both
ways: a new help family or Theory heading that no feature and no exemption
claims fails there by name, and so does a key here that names nothing on the
tree.

The validation record is the developers' (DESIGN.md § Rules, 2): what verifies
each feature and what validates it live in ``tests/validation_matrix.py`` and its
generated page ``docs/VALIDATION.md``, joined to this registry by each claim's
``features``.  No surface an agent reads to choose a feature carries that record
(:func:`rietx.capabilities`, the help entries, the skill).  This module keeps one
bit of it, :attr:`Feature.independently_measured`, because a fit report names the
numbers it reports from a feature with no independent measurement, once
(:attr:`rietx.report.schemas.FitReport.not_independently_measured`), and the
package cannot read ``tests/``.  The same test file holds the bit equal to the
matrix's derivation, so it cannot drift from the record it copies.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Feature:
    """One feature: its help keys, its Theory headings and one validation bit."""

    #: what the feature is, in words
    title: str
    #: the :data:`rietx.help.PARAMETER_HELP` families it owns
    parameters: tuple[str, ...] = ()
    #: the :data:`rietx.help.INSTRUMENT_FIELD_HELP` fields it owns
    instrument_fields: tuple[str, ...] = ()
    #: its Theory headings, ``"<page> § <heading text>"``
    theory: tuple[str, ...] = ()
    #: why it has no Theory heading, when it has none (WP-2010's declared
    #: exception); empty when ``theory`` is not
    no_theory: str = ""
    #: whether a claim in the validation matrix compares it with an
    #: independent measurement (a certificate, a weighed composition), copied
    #: from the matrix and held to it by ``tests/test_validation_matrix.py``.  ``False``
    #: is "not yet validated", which is not "wrong"
    independently_measured: bool = False


FEATURES: dict[str, Feature] = {
    "lattice_metric": Feature(
        "Cell and Bragg's law",
        parameters=(
            "phases.*.cell.a",
            "phases.*.cell.b",
            "phases.*.cell.c",
            "phases.*.cell.alpha",
            "phases.*.cell.beta",
            "phases.*.cell.gamma",
        ),
        theory=(
            "peak-positions § Lattice metric and Bragg's law",
        ),
        independently_measured=True,
    ),
    "wavelength": Feature(
        "Emission lines, wavelength scales, harmonics, wavelength-cell degeneracy",
        parameters=(
            "instrument.source.lines.*.wavelength",
            "instrument.source.lines.*.weight",
        ),
        instrument_fields=(
            "radiation",
            "wavelength",
            "ka2_ratio",
        ),
        theory=(
            "peak-positions § Wavelength scales",
            "peak-positions § The wavelength–cell degeneracy",
            "peak-positions § Monochromator harmonics",
        ),
        independently_measured=True,
    ),
    "position_aberrations": Feature(
        "Zero, specimen displacement and transparency",
        parameters=(
            "instrument.zero_shift",
            "instrument.geometry.sample_displacement",
            "instrument.geometry.sample_transparency",
        ),
        instrument_fields=(
            "goniometer_radius_mm",
        ),
        theory=(
            "peak-positions § Aberration shifts",
            "peak-positions § Zero-point error",
            "peak-positions § Sample displacement",
            "peak-positions § Sample transparency",
            "peak-positions § Decorrelating the flat-plate trio",
        ),
        independently_measured=True,
    ),
    "capillary_offsets": Feature(
        "Capillary offsets along and across the beam",
        parameters=(
            "instrument.geometry.capillary_offset_along_beam",
            "instrument.geometry.capillary_offset_across_beam",
        ),
        theory=(
            "peak-positions § Capillary displacement",
        ),
    ),
    "tof_calibration": Feature(
        "Time-of-flight calibration (DIFC, DIFA, DIFB, TZERO)",
        parameters=(
            "instrument.source.difc",
            "instrument.source.difa",
            "instrument.source.difb",
            "instrument.source.tzero",
        ),
        theory=(
            "peak-positions § Time of flight",
        ),
    ),
    "tof_profile": Feature(
        "Time-of-flight peak shape and incident spectrum",
        parameters=(
            "instrument.source.profile_tof.alpha0",
            "instrument.source.profile_tof.alpha1",
            "instrument.source.profile_tof.beta0",
            "instrument.source.profile_tof.beta1",
            "instrument.source.profile_tof.sig0",
            "instrument.source.profile_tof.sig1",
            "instrument.source.profile_tof.sig2",
            "instrument.source.profile_tof.gam0",
            "instrument.source.profile_tof.gam1",
            "instrument.source.profile_tof.gam2",
            "instrument.source.incident_spectrum.p*",
        ),
        no_theory="read from a GSAS or GSAS-II file and carried, never evaluated: no flight-time forward model ships, and fit refuses a TOF pattern, so there is no equation of rietx's to state",
    ),
    "instrument_profile": Feature(
        "Caglioti/TCH pseudo-Voigt and true Voigt",
        parameters=(
            "instrument.profile.u",
            "instrument.profile.v",
            "instrument.profile.w",
            "instrument.profile.x",
            "instrument.profile.y",
        ),
        theory=(
            "profiles § The instrument ⊕ sample width split",
            "profiles § When $U$, $V$ and $W$ are determined at all",
            "profiles § Thompson-Cox-Hastings pseudo-Voigt",
            "profiles § Origin and accuracy of the coefficients",
            "profiles § The true Voigt, via the Faddeeva function",
        ),
    ),
    "axial_divergence": Feature(
        "Finger-Cox-Jephcoat axial divergence",
        parameters=(
            "instrument.geometry.axial_sl",
            "instrument.geometry.axial_hl",
        ),
        theory=(
            "profiles § Finger-Cox-Jephcoat axial divergence",
            "method § The FCJ corner at $s = h$",
        ),
    ),
    "bragg_intensities": Feature(
        "Bragg intensities: structure factor, X-ray f0, occupancy, Lorentz-polarisation, Rietveld mode",
        parameters=(
            "phases.*.atoms.*.occ",
            "instrument.polarization",
        ),
        instrument_fields=(
            "polarization",
            "monochromator_two_theta",
        ),
        theory=(
            "corrections § Lorentz-polarisation",
            "intensities § The species scattering factor",
            "intensities § The structure factor",
            "forward-model § Three intensity models",
            "forward-model § Rietveld mode",
        ),
        independently_measured=True,
    ),
    "neutron_scattering": Feature(
        "Neutron scattering lengths",
        theory=(
            "intensities § The neutron scattering length",
        ),
    ),
    "anomalous_dispersion": Feature(
        "Anomalous scattering f′ and f″ (Source.dispersion)",
        theory=(
            "intensities § Anomalous scattering and the powder average",
        ),
        independently_measured=True,
    ),
    "displacement_parameters": Feature(
        "Isotropic and anisotropic displacement parameters",
        parameters=(
            "phases.*.atoms.*.biso",
            "phases.*.atoms.*.u11",
            "phases.*.atoms.*.u22",
            "phases.*.atoms.*.u33",
            "phases.*.atoms.*.u12",
            "phases.*.atoms.*.u13",
            "phases.*.atoms.*.u23",
            "phases.*.atoms.*.adp.*",
        ),
        theory=(
            "intensities § Debye-Waller factors and ADP representations",
            "intensities § How large a $B$ can be",
        ),
    ),
    "atomic_coordinates": Feature(
        "Fractional coordinates and site-symmetry DOFs",
        parameters=(
            "phases.*.atoms.*.x",
            "phases.*.atoms.*.y",
            "phases.*.atoms.*.z",
            "phases.*.atoms.*.dof.*",
        ),
        theory=(
            "parameterisation § Site-symmetry degrees of freedom",
        ),
    ),
    "rigid_bodies": Feature(
        "Rigid bodies (origin, rotation, torsions; riding H)",
        parameters=(
            "phases.*.rigid_bodies.*.origin.x",
            "phases.*.rigid_bodies.*.origin.y",
            "phases.*.rigid_bodies.*.origin.z",
            "phases.*.rigid_bodies.*.origin.dof.*",
            "phases.*.rigid_bodies.*.rotation.*",
            "phases.*.rigid_bodies.*.torsions.*.twist",
        ),
        theory=(
            "parameterisation § Rigid bodies",
        ),
    ),
    "restraints": Feature(
        "Soft restraints and their weighting (Phase.restraints)",
        theory=(
            "parameterisation § Soft restraints",
            "parameterisation § Weighting the restraints",
        ),
    ),
    "primary_extinction": Feature(
        "Primary extinction (Sabine)",
        parameters=(
            "phases.*.extinction",
        ),
        theory=(
            "corrections § Primary extinction",
        ),
    ),
    "march_dollase": Feature(
        "Preferred orientation, March-Dollase",
        parameters=(
            "phases.*.preferred_orientation.r",
        ),
        theory=(
            "corrections § Preferred orientation (March-Dollase)",
        ),
        independently_measured=True,
    ),
    "spherical_harmonics_texture": Feature(
        "Preferred orientation, spherical harmonics",
        parameters=(
            "phases.*.texture.*",
        ),
        theory=(
            "corrections § Preferred orientation (spherical harmonics)",
        ),
        independently_measured=True,
    ),
    "qpa": Feature(
        "Quantitative phase analysis and microabsorption",
        parameters=(
            "phases.*.scale",
        ),
        theory=(
            "corrections § Quantitative phase analysis and microabsorption",
        ),
        independently_measured=True,
    ),
    "attenuation_estimate": Feature(
        "Attenuation coefficients from composition",
        instrument_fields=(
            "packing_fraction",
        ),
        theory=(
            "corrections § Attenuation coefficients",
        ),
    ),
    "capillary_absorption": Feature(
        "Capillary absorption (Rouse)",
        instrument_fields=(
            "capillary_radius_mm",
            "mu_r",
        ),
        theory=(
            "corrections § Capillary (cylindrical) absorption",
            "method § Rouse b₂: validate against the integral",
        ),
    ),
    "flat_plate_absorption": Feature(
        "Flat-plate absorption (thin specimen)",
        instrument_fields=(
            "mu_t",
            "thickness_mm",
        ),
        theory=(
            "corrections § Flat-plate absorption",
            "method § µR, µt, and what $\\Delta R_{wp}$ judges",
        ),
    ),
    "surface_roughness": Feature(
        "Surface roughness (Suortti, Pitschke)",
        parameters=(
            "instrument.geometry.surface_roughness.a",
            "instrument.geometry.surface_roughness.b",
            "instrument.geometry.surface_roughness.c",
            "instrument.geometry.surface_roughness.tau",
        ),
        theory=(
            "corrections § Surface roughness",
        ),
    ),
    "size_strain": Feature(
        "Isotropic size and strain widths",
        parameters=(
            "phases.*.lor_size",
            "phases.*.lor_strain",
            "phases.*.gauss_size",
            "phases.*.gauss_strain",
        ),
        theory=(
            "microstructure § Isotropic size and strain",
            "profiles § The strain width bound",
            "profiles § The size coefficient bound",
        ),
    ),
    "microstructure_readings": Feature(
        "A width read as a domain size or a strain",
        theory=(
            "microstructure § Reading a width as a size",
            "microstructure § Reading a width as a strain",
        ),
    ),
    "stephens_strain": Feature(
        "Stephens anisotropic strain",
        parameters=(
            "phases.*.microstrain.s*",
            "phases.*.microstrain.dof.*",
        ),
        theory=(
            "microstructure § Stephens anisotropic strain",
            "microstructure § Symmetry and the allowed coefficients",
            "microstructure § The positivity cone, the seed and the guard",
        ),
    ),
    "magnetic_structure": Feature(
        "Magnetic moments, magnetic form factor, magnetic widths",
        parameters=(
            "phases.*.atoms.*.moment.crystalaxis_*",
            "phases.*.atoms.*.moment.dof*",
            "phases.*.magnetic_lor_size",
            "phases.*.magnetic_lor_strain",
        ),
        theory=(
            "intensities § The magnetic structure factor",
            "intensities § The magnetic component's own width",
            "intensities § The dipole approximation",
            "parameterisation § Magnetic moment constraints",
            "parameterisation § Moment degrees of freedom",
            "estimation § A moment angle at a direction the symmetry fixes",
        ),
    ),
    "magnetic_determination": Feature(
        "Representation analysis and magnetic candidates (solve_magnetic)",
        theory=(
            "representation-analysis § The little group and its small irreps",
            "representation-analysis § The projection operator and its basis vectors",
            "representation-analysis § The lattice return-vector phase",
            "representation-analysis § Isotropy subgroups and the candidate models",
            "representation-analysis § The powder-equivalence criterion",
        ),
    ),
    "satellites": Feature(
        "Satellites of a propagation vector (Phase.propagation_vector)",
        theory=(
            "peak-positions § Satellites of a propagation vector",
        ),
    ),
    "background_curve": Feature(
        "Chebyshev / P-spline background and air scatter",
        parameters=(
            "instrument.background.c*",
            "instrument.background.air",
        ),
        theory=(
            "background § Additive background models",
            "background § What the pure number leaves to the counts",
            "background § Choosing the flexibility",
            "background § Background flexibility and bias",
        ),
    ),
    "measured_background": Feature(
        "A measured (blank) background and its scale",
        parameters=(
            "instrument.background.scale",
        ),
        theory=(
            "background § A measured background",
        ),
    ),
    "background_estimation": Feature(
        "Model-free background estimate (auto_background)",
        theory=(
            "background § Model-free estimation",
        ),
    ),
    "extra_components": Feature(
        "Humps and declared extra peaks",
        parameters=(
            "instrument.extra_components.*.position",
            "instrument.extra_components.*.height",
            "instrument.extra_components.*.fwhm",
            "instrument.extra_components.*.center",
            "instrument.extra_components.*.area",
            "instrument.extra_components.*.eta",
        ),
        theory=(
            "background § Explicit humps",
            "profiles § Declared extra peaks",
        ),
    ),
    "lebail_pawley": Feature(
        "Le Bail and Pawley intensity extraction (modes)",
        theory=(
            "forward-model § Le Bail mode",
            "forward-model § Pawley mode",
        ),
    ),
    "indexing": Feature(
        "Indexing: engines, figures of merit, lattice ambiguity, supercells",
        theory=(
            "indexing § The quadratic form",
            "indexing § The symmetry-allowed subspace",
            "indexing § What a peak list supports",
            "indexing § Which lines drive the search",
            "indexing § Volume from one line",
            "indexing § Volume from a formula",
            "indexing § Figures of merit, in both directions",
            "indexing § Lattice ambiguity",
            "indexing § A supercell and the lattice inside it",
            "engines § Searching in the metric components",
            "engines § Successive dichotomy",
            "engines § The metric cone and the volume window",
            "engines § Line matching and Hall's condition",
            "engines § One grid pass per system",
            "engines § Index-heuristic trial and error",
            "engines § Zone indexing, assessed and declined",
            "engines § The obliquity bound",
            "engines § The reflection ceiling",
        ),
        independently_measured=True,
    ),
    "peak_shift_screen": Feature(
        "A systematic 2theta shift measured before the cell",
        theory=(
            "indexing § Measuring the shift before the cell",
        ),
        independently_measured=True,
    ),
    "peak_picking_and_fitting": Feature(
        "pick_peaks, fit_peaks and their flags",
        no_theory="a search over the observed pattern, whose fitted peak is the profile of profiles § Thompson-Cox-Hastings pseudo-Voigt; no model of its own",
    ),
    "extinction_symbols": Feature(
        "Extinction symbols (determine_extinction_symbol)",
        no_theory="a ranking of International Tables' reflection conditions against the observed absences; the conditions are the tables', so rietx has no equation of its own to state",
    ),
    "derived_geometry": Feature(
        "Bond lengths and angles with esds",
        theory=(
            "estimation § Esds of derived quantities",
        ),
    ),
    "esds": Feature(
        "Esds: Berar-Lelann inflation, intervals at a bound, scale-B separation",
        theory=(
            "estimation § Esds and the Bérar-Lelann inflation",
            "estimation § A derived esd describes one basin",
            "estimation § An interval for a parameter on its bound",
            "estimation § A scale and a B the range cannot separate",
            "estimation § A combination of three or more",
            "estimation § Why the uncorrected esd is too small",
            "estimation § The factor",
            "estimation § What other programs report",
        ),
    ),
    "sequential_series": Feature(
        "Sequential (chained) series",
        theory=(
            "estimation § Staged strategy and series",
        ),
        independently_measured=True,
    ),
    "joint_refinement": Feature(
        "Joint multi-histogram refinement (refine_multi)",
        no_theory="one objective summed over histograms, each term estimation § Objective and weights; the sharing of a size across wavelengths is the invariant in CLAUDE.md, not a new equation",
    ),
    "parametric_refinement": Feature(
        "A parameter as a function of each pattern's coordinates",
        theory=(
            "parameterisation § A parameter as a function of each pattern's coordinates",
        ),
    ),
    "distortion_modes": Feature(
        "Distortion-mode amplitudes in a stated child",
        parameters=(
            "phases.*.distortion_modes.modes.*.amplitude",
        ),
        theory=(
            "parameterisation § Distortion-mode amplitudes",
        ),
    ),
    "subgroup_enumeration": Feature(
        "Subgroups: t- and k-subgroups, conjugacy classes, standard settings",
        theory=(
            "subgroups § Two kinds, and nothing else",
            "subgroups § The k-subgroups over a prime field",
            "subgroups § Conjugacy classes",
            "subgroups § The transformation to a standard setting",
            "subgroups § What the generator is checked against",
        ),
    ),
}

NOT_FEATURES: dict[str, str] = {
    "vars.*": "a name the caller defines; it carries whichever feature its paths do",
    "estimation § Objective and weights": "estimation machinery",
    "estimation § Agreement statistics": "a statistic",
    "estimation § Structure agreement indices": "a statistic",
    "estimation § The effective observation count": "a statistic",
    "estimation § Solvers": "solver",
    "estimation § Convergence": "solver",
    "estimation § The fp64 floor": "arithmetic",
    "estimation § From fit to report": "report decisions, audited by 2004",
    "estimation § Which parameter to free next": "a suggestion, audited by 2004",
    "forward-model § The residual row layout": "machinery",
    "forward-model § Discreteness frozen per stage": "machinery",
    "parameterisation § From tree to vector": "machinery (cell ties)",
    "method § Two Coelho papers vs. their own tables": "method note",
    "method § Coelho (2005), equation (1)": "solver method note",
    "method § Coelho (2018), equation (9)": "solver method note",
    "superspace § The operators": "group mathematics; no modulated refinement ships",
    "superspace § Generating the groups": "group mathematics",
    "superspace § Symbols": "group mathematics",
    "superspace § Commensurate sections": "group mathematics",
    "superspace § Magnetic superspace groups": "group mathematics",
    "superspace § The group of an irrep at an incommensurate k": "group mathematics",
}


def feature_of(path: str) -> str | None:
    """The feature that owns a parameter dot-path, or ``None``.

    Read through the path's help family (:func:`rietx.help.help_key_for`, the
    match ``ParameterRow.help_key`` carries); a path no family claims, or one
    whose family is in :data:`NOT_FEATURES` (``vars.*``), has no feature.
    """
    from rietx.help import help_key_for

    key = help_key_for(path)
    if key is None:
        return None
    for name, feature in FEATURES.items():
        if key in feature.parameters:
            return name
    return None


def parameters_without_independent_measurement(paths) -> dict[str, list[str]]:
    """``{feature: [path, ...]}`` for the paths whose feature has none.

    In the order the paths came, each path once.  The fit report's one
    sentence is built from this (WP-2010); a path with no feature is left out,
    since nothing is known about it either way.
    """
    out: dict[str, list[str]] = {}
    for path in paths:
        name = feature_of(path)
        if name is None or FEATURES[name].independently_measured:
            continue
        if path not in out.setdefault(name, []):
            out[name].append(path)
    return out
