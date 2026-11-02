"""What a project reader does with each construct of the format it reads.

**Why this exists.** A `.inp` states far more than a structure, this reader
imports a structure, and every construct in between has to go somewhere. Before
this table it went nowhere in particular: a keyword nobody had written a branch
for was invisible, so "the reader handles it" and "the reader has never seen it"
were the same observable, and each new file shape arrived as a defect rather
than as a row. Nine review rounds on WP-1118 each found one more of them, all of
the same shape — a construct dropped in silence — which is a property of the
reader's *structure*, not of the nine constructs.

So the stance is **declared per construct** and the default is never silence.
Four of them, and the distinction that matters is what a caller loses:

* :attr:`Stance.READ` — the reader builds it into the model. Nothing lost.
* :attr:`Stance.IGNORED` — the construct is about the *run*, not the model:
  where output goes, what gets appended to the ``.OUT``, what the GUI shows.
  Dropping it changes nothing about the structure that was built, so it is
  dropped in silence and this table is the argument for the silence.
* :attr:`Stance.REPORTED` — the construct is about the model and is **not**
  carried. This is a partial import: the structure built is right as far as it
  goes, and one ``TOPAS_FEATURES_NOT_IMPORTED`` says how far that is.
* :attr:`Stance.REFUSED` — carrying the phase *without* the construct would
  misrepresent the file, so :func:`~rietx.io.projects.topas.to_structure`
  refuses by name. A rigid body generates the coordinates that the ``site``
  lines report, so importing those numbers as free atoms says the refinement
  moved eleven independent atoms when it moved one body's six degrees of
  freedom; ``occ_merge`` couples occupancies across sites; a stacking-fault
  phase does not diffract from the cell it states. In every case the *numbers*
  read back fine, which is what makes the silence dangerous rather than
  obvious.

**The mechanism for a feature this reader does not have yet**, which is the
point of the table rather than a side effect of it: support arrives by moving a
row from ``REPORTED``/``REFUSED`` to ``READ`` and teaching the reader the
keyword. Until someone does, the construct is *named* in every import that
meets it. Nothing is silently dropped in the meantime and nothing has to be
guessed at review time, because :data:`PHASE_SCOPE` is the completeness oracle:
``tests/test_projects_topas.py`` asserts every keyword the format allows inside
a phase has exactly one stance, so a keyword added to the scope without a stance
fails, and a stance naming a keyword the scope does not contain fails too.

**Scope decides the default.** The reference's §5.1 tree bounds a phase
(``Tstr_details`` and the ``Tphase_*``/``Tcomm_*`` groups reachable under
``str``), and inside that boundary every keyword is model-relevant until shown
otherwise — so the phase scope is enumerated here in full. Outside it a keyword
is about the run, and this reader's answer is a
:class:`~rietx.schemas.Structure`, which carries no run: those are ignored as a
class, stated once here rather than keyword by keyword. The two constructs
outside a phase that *do* change what the phases mean are already refused at
read time by :mod:`~rietx.io.projects.topas` itself, and for a different reason
— ``for``/``load``/``move_to`` move where a card attaches and the
``#``-directives change what text there is, so with either of them present the
text in hand is not the text TOPAS parsed. That refusal is about the *file*;
this table is about the *model*.

**A library macro is a construct too** (#649). A file often writes a peak
shape not as ``peak_type``/``lor_fwhm`` but as ``TCHZ_Peak_Type(…)``, a size
as ``CS_L(…)``, a displacement as ``Specimen_Displacement(…)`` — and the mask
that makes the keyword scan safe blanks every ``name(…)`` call, name included,
so a registry of keywords alone met none of them and the import said nothing.
A row therefore also lists the :attr:`Feature.macros` that state it, scanned by
the reader as *invocations* (``Name(``) anywhere in the active text, not only
inside a phase: the reference lists these macros under its instrument, 2θ and
intensity-correction and microstructure headings (§19.3.4-19.3.10, §17.9.5.2),
so wherever one is written it is about the model. The names and signatures
are the reference's section text; no macro body is reproduced. A *keyword*
outside a phase is still out of scope as above — that boundary is the
module's, and moving it is a separate decision.

Keyword names are the format's own identifiers, treated as specification facts
the way ``io/CLAUDE.md`` § Adding a format already treats a byte offset or a
tag name; every description here is this package's own. See ``ATTRIBUTION.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

#: Which edition of the format this table was written against. A keyword from a
#: later one is not in :data:`PHASE_SCOPE`, and this reader would not report it
#: — so the version is stated rather than implied, and extending the table to a
#: new edition is a declared piece of work rather than a discovery.
SPEC = "TOPAS Academic Technical Reference, version 8 (2026-08-12), §5.1-5.2"


class Stance(str, Enum):
    """What this reader does with one construct. See the module docstring."""

    READ = "read"
    IGNORED = "ignored"
    REPORTED = "reported"
    REFUSED = "refused"


@dataclass(frozen=True)
class Feature:
    """One construct of the format, and this reader's declared stance on it.

    ``keywords`` are the format's own identifiers, and ``macros`` the library
    macros that state the same construct (see the module docstring). ``what``
    is one line in this package's words, written to be read *in a diagnostic
    message* — it says what the file states, not what TOPAS does with it.
    ``why`` is present only where the stance needs an argument: a ``REFUSED``
    row has to say what building without it would misrepresent, and a
    ``REPORTED`` one what the caller is losing.
    """

    name: str
    keywords: tuple[str, ...]
    stance: Stance
    what: str
    why: str = ""
    macros: tuple[str, ...] = ()

    def __str__(self) -> str:
        return f"{self.name} ({', '.join(self.keywords + self.macros)})"


def _f(name, stance, what, *keywords, why="", macros=()):
    return Feature(name, tuple(keywords), stance, what, why, tuple(macros))


#: The registry. One row per construct, ordered by stance so the table reads as
#: an argument rather than as an alphabetical list.
FEATURES: tuple[Feature, ...] = (
    # ------------------------------------------------------------------ read
    _f("phase", Stance.READ, "a crystalline phase",
       "str", "hkl_Is", "xo_Is", "d_Is", "dummy_str", "phase_name", "scale",
       "weight_percent"),
    _f("symmetry", Stance.READ, "the space group", "space_group"),
    _f("cell", Stance.READ, "the lattice parameters",
       "a", "b", "c", "al", "be", "ga", "min", "max"),
    _f("sites", Stance.READ, "the atom sites and their occupancies",
       "site", "occ", "beq", "x", "y", "z"),
    _f("anisotropic displacement", Stance.READ,
       "the anisotropic displacement tensor (to_structure(aniso=True))",
       "adps", "u11", "u22", "u33", "u12", "u13", "u23"),
    _f("parameter declarations", Stance.READ,
       "a named parameter an equation may reference", "prm", "local"),
    _f("magnetic moments", Stance.READ,
       "the site magnetic moments and the Landé g "
       "(to_structure(magnetic_symmetry=...))",
       "mlx", "mly", "mlz", "mg"),
    _f("magnetic space group", Stance.READ,
       "the magnetic space group: a BNS or OG number is the group, and a "
       "`str` stating no `space_group` takes its nuclear group from it; a "
       "Shubnikov symbol is carried as metadata and the build refuses a "
       "moment-bearing phase by name until to_structure(magnetic_symmetry=...) "
       "supplies the operators",
       "mag_space_group"),

    # --------------------------------------------------------------- refused
    _f("rigid body", Stance.REFUSED,
       "a rigid body generating this phase's coordinates",
       "rigid", "z_matrix", "point_for_site", "rotate", "translate",
       "operate_on_points", "start_values_from_site", "in_cartesian",
       why="the `site` lines of a rigid-body phase report coordinates the body "
           "generated, so importing them as independent atoms states a "
           "refinement of one atom per site where the file refined one body's "
           "translations and rotations. The numbers are right and the model "
           "around them is not, which no later reading of the structure could "
           "recover"),
    _f("merged occupancies", Stance.REFUSED,
       "occupancies coupled across sites", "occ_merge", "occ_merge_radius",
       why="the coupling is what keeps a shared site's occupancies summing, and "
           "it does not survive into a Structure — the imported occupancies "
           "would be free to move apart, which is a composition the file never "
           "states"),
    _f("scaled occupancy", Stance.REFUSED,
       "an occupancy multiplier", "scale_occ",
       why="the site's occupancy in the file is the stated `occ` times this, so "
           "importing `occ` alone imports a number the file does not state"),
    _f("stacking faults", Stance.REFUSED,
       "a stacking-fault model",
       "generate_stack_sequences", "number_of_sequences",
       "number_of_stacks_per_sequence", "save_sequences",
       "save_sequences_as_strs", "match_transition_matrix_stats",
       "use_layer", "user_defined_starting_transition", "layers_tol",
       why="such a phase does not diffract from the cell it states — the "
           "pattern comes from the stacking sequence — so a Structure built "
           "from the cell and sites is a different specimen"),
    _f("magnetic-only phase", Stance.REFUSED,
       "a phase, or a site, contributing magnetic intensity only",
       "mag_only", "mag_only_for_mag_sites",
       why="such a phase has no nuclear structure factor at all — its "
           "intensity is |F_m|² alone — and rietx's magnetic model is a moment "
           "on a site of a nuclear phase sharing one scale (WP-1327), so there "
           "is no shape here for a phase whose nuclear half is declared "
           "absent. Importing the sites as an ordinary phase would add the "
           "nuclear intensity the file says is not there — and the idiom that "
           "uses it (a nuclear `str` beside a `mag_only_for_mag_sites` one "
           "restating the magnetic sites, as the Durham LaMnO3 tutorial does) "
           "would then count those sites' nuclear scattering twice, so the "
           "keyword is not droppable with a diagnostic either. One form is "
           "read, and the lift is made when the file is read, by the one "
           "predicate `to_structure`'s merge uses: a "
           "`\"<name> magnetic part\"` str of `mag_only` sites that carry a "
           "moment, merged into `<name>` only where its scale, cell, space "
           "group and sites equal the nuclear str's (`mag_only_for_mag_sites` "
           "and any other use stay refused)"),

    # -------------------------------------------------------------- reported
    _f("peak profile", Stance.REPORTED,
       "the peak shape and the instrument convolutions",
       "peak_type", "pv_lor", "pv_fwhm", "h1", "h2", "m1", "m2",
       "spv_h1", "spv_h2", "spv_l1", "spv_l2", "numerical_area",
       "axial_conv", "circles_conv", "exp_conv_const", "exp_limit",
       "ft_conv", "gauss_fwhm", "lor_fwhm", "one_on_x_conv", "hat",
       "num_hats", "stacked_hats_conv", "whole_hat", "half_hat",
       "hat_height", "user_defined_convolution", "push_peak", "modify_peak",
       "modify_peak_eqn", "modify_peak_apply_before_convolutions",
       "more_accurate_Voigt", "numerical_lor_gauss_conv",
       "numerical_lor_ymin_on_ymax", "pk_xo", "th2_offset",
       "lpsd_th2_angular_range_degrees", "WPPM_ft_conv",
       why="rietx's own profile is fitted from the pattern, and the two codes' "
           "convolution stacks do not correspond term for term",
       # §19.3.5 (the phase peak types) and §19.3.4 (the instrument and its
       # convolutions).
       macros=("PV_Peak_Type", "PVII_Peak_Type", "TCHZ_Peak_Type",
               "Simple_Axial_Model", "Full_Axial_Model", "Finger_et_al",
               "Tube_Tails", "UVW", "Slit_Width", "SW", "Specimen_Tilt",
               "Sample_Thickness", "Divergence", "Variable_Divergence",
               "Variable_Divergence_Shape")),
    _f("size and strain broadening", Stance.REPORTED,
       "a crystallite-size or microstrain broadening",
       why="rietx refines its own size and strain widths on the phase, added "
           "to the instrument's, and the file's are a term of a convolution "
           "stack the import does not carry, so the widths they explained are "
           "not reproduced",
       # §19.3.10's size and strain macros, with their documented short forms,
       # and §17.9.5.2's.
       macros=("CS_L", "CS_G", "CS", "Crystallite_Size", "Strain_L",
               "Strain_G", "Microstrain", "MS", "LVol_FWHM_CS_G_L",
               "e0_from_Strain")),
    _f("2θ corrections", Stance.REPORTED,
       "a zero-point or specimen-displacement correction",
       why="each moves every peak, and rietx refines its own zero and "
           "displacement against the pattern, so the file's correction is not "
           "carried and the positions it explained are not",
       # §19.3.7, with the documented short forms.
       macros=("Zero_Error", "ZE", "Specimen_Displacement", "SD")),
    _f("specimen corrections", Stance.REPORTED,
       "a specimen or geometry correction",
       "capillary_diameter_mm", "capillary_parallel_beam",
       "capillary_divergent_beam", "capillary_u_cm_inv",
       "brindley_spherical_r_cm", "aberration_range_change_allowed",
       why="the correction's parameters are the author's model of the "
           "specimen, and they are not transferable term for term",
       # §19.3.8 (intensity corrections), §19.3.6's Brindley macro and
       # §19.3.10's thickness-dependent absorption; `Absorption` from §5.2.
       # The two cylindrical corrections are named beside their functions
       # `AB_Cyl_Corr`/`AL_Cyl_Corr` in version 9's Table 3-1 (WP-1530).
       macros=("Absorption", "Absorption_With_Sample_Thickness_mm",
               "Absorption_With_Sample_Thickness_mm_Intensity",
               "Absorption_With_Sample_Thickness_mm_Shape_Intensity",
               "Surface_Roughness_Pitschke_et_al", "Surface_Roughness_Suortti",
               "Variable_Divergence_Intensity",
               "Apply_Brindley_Spherical_R_PD", "Cylindrical_I_Correction",
               "Cylindrical_2Th_Correction")),
    _f("preferred orientation", Stance.REPORTED,
       "a texture model", "normals_plot", "normals_plot_min_d",
       why="this reader translates neither a March-Dollase correction nor a "
           "spherical-harmonics one into rietx's.  The Technical Reference "
           "cites Järvinen (1993) for its harmonics but states neither their "
           "normalisation nor their frame, and no TOPAS output has measured "
           "them, so the texture is dropped and the intensities it explained "
           "are not",
       # §19.3.8, with the documented short form.
       macros=("Preferred_Orientation", "PO", "PO_Two_Directions",
               "PO_Spherical_Harmonics")),
    _f("spherical-harmonics series", Stance.REPORTED,
       "a spherical-harmonics function of hkl", "spherical_harmonics_hkl",
       why="an equation uses its value, for a texture through scale_pks or "
           "for hkl-dependent broadening, and this reader translates neither "
           "use, so what that equation explained is dropped"),
    _f("restraints and penalties", Stance.REPORTED,
       "a restraint, penalty or interatomic interaction",
       "penalty", "phase_penalties", "only_penalties", "atomic_interaction",
       "ai_anti_bump", "ai_sites_1", "ai_sites_2", "ai_no_self_interation",
       "ai_closest_N", "ai_radius", "ai_exclude_eq_0", "ai_only_eq_0",
       "box_interaction", "grs_interaction", "no_self_interaction",
       "from_N", "to_N", "qi", "qj", "sites_flatten", "sites_flatten_tol",
       why="rietx has soft restraints, but a penalty is an arbitrary equation "
           "over the file's own parameter names and does not translate",
       # The bond-length penalty macros, §22.1.9 in version 9 (WP-1530).
       macros=("Anti_Bump", "AI_Anti_Bump", "Parabola_N", "Grs_Interaction",
               "Grs_No_Repulsion", "Grs_BornMayer", "Distance_Restrain",
               "Angle_Restrain", "Flatten", "Distance_Restrain_Keep_Within",
               "Distance_Restrain_Keep_Out", "Keep_Atom_Within_Box")),
    _f("reflection controls", Stance.REPORTED,
       "a per-reflection control",
       "omit_hkls", "hkl_plane", "hkl_Re_Im", "str_hkl_angle",
       "i_on_error_ratio_tolerance", "num_highest_I_values_to_keep",
       "default_I_attributes", "siv_s1_s2",
       why="these select or weight individual reflections, which changes what "
           "the refinement fitted"),
    _f("scattering factors", Stance.REPORTED,
       "a scattering-factor override",
       "f0_f1_f11_atom", "no_f11", "normalize_FCs", "Flack",
       "d_spacing_to_energy_in_eV_for_f1_f11",
       why="rietx resolves f0 and the anomalous terms from its own tables, so "
           "an override in the file does not reach the built model"),
    _f("site multiplicity", Stance.REPORTED,
       "an explicit site multiplicity or position count",
       "num_posns", "rand_xyz", "inter", "adps_scale", "min_r", "max_r",
       "co", "track",
       why="rietx takes multiplicity from the space group and the site's own "
           "Wyckoff position, so a stated count is not read"),
    _f("phase scaling", Stance.REPORTED,
       "a scale modifier or a conditional phase",
       "scale_pks", "scale_phase_X", "auto_scale", "remove_phase",
       "amorphous_phase", "degree_of_crystallinity", "del_approx",
       why="each changes what the phase contributes to the pattern, so the "
           "imported scale is the file's number without the modifier that "
           "acted on it"),
    _f("emission profile", Stance.REPORTED,
       "an emission profile this reader does not read",
       why="`emission_macro`, `anode` and `emission_lines` are read from the "
           "`CuKa5`-style macros and from `la`/`lo` lines, so a profile stated "
           "through this macro leaves all three empty and the wavelength has to "
           "come from the caller",
       # §22.1.3 in version 9, less the ones the reader reads (an element, `Ka`
       # and a digit, `topas._EMISSION_MACRO`) (WP-1530).
       macros=("CuK1sharp", "CuKa2_analyt", "CuKa4_Holzer", "CuKa5_Berger",
               "CoKa7_Holzer", "CrKa7_Holzer", "FeKa7_Holzer", "MnKa7_Holzer",
               "NiKa5_Holzer", "CuKb4_Holzer", "CoKb6_Holzer", "CrKb5_Holzer",
               "FeKb4_Holzer", "MnKb5_Holzer", "NiKb4_Holzer")),
    _f("cell mass, volume and weight percent", Stance.REPORTED,
       "a phase's cell mass, cell volume and weight percent stated through MVW",
       why="this reader reads `weight_percent` as a keyword only, so a weight "
           "percent stated as the macro's third argument does not reach the "
           "phase's `weight_percent`",
       # §22.1.6 in version 9 (WP-1530).
       macros=("MVW",)),
    _f("parameter attribute edits", Stance.REPORTED,
       "an edit to a parameter declared elsewhere", "existing_prm",
       why="it changes a parameter after its declaration, so a value read at "
           "the declaration is not necessarily the one the refinement used"),

    # --------------------------------------------------------------- ignored
    _f("structure output", Stance.IGNORED,
       "where the run writes its results and what it reports",
       "append_cartesian", "append_fractional", "append_bond_lengths",
       "in_str_format", "consider_lattice_parameters", "p1_fractional_to_file",
       "out", "out_record", "phase_out", "phase_out_X", "atom_out",
       # `mag_atom_out` is `atom_out`'s magnetic twin and belongs beside it:
       # it appends the site moments to the `.OUT`, so it says where output
       # goes and nothing about the model.  WP-1328's task list puts it in the
       # *read* group; there is nothing in it to read — a stance of READ would
       # claim the reader builds something from a directive that carries no
       # value — so it is IGNORED here and the deviation is in the report.
       "mag_atom_out",
       "xdd_out", "report_on_str", "report_on", "view_structure",
       "fourier_map", "sites_distance", "sites_angle", "sites_geometry"),
    _f("figures of merit", Stance.IGNORED,
       "the converged figures of merit of a fit this package has not run",
       "r_bragg"),
    _f("performance controls", Stance.IGNORED,
       "how the run spends its memory and time", "peak_buffer_step"),
)

_BY_KEYWORD: dict[str, Feature] = {
    kw: feat for feat in FEATURES for kw in feat.keywords}

#: The library macros the registry names, each to its row. Not part of
#: :data:`PHASE_SCOPE`: a macro is not a keyword of the §5.1 tree, and the
#: reader scans for it on a different view of the text (an invocation, where
#: the keyword mask blanks every call) and over the whole file.
_BY_MACRO: dict[str, Feature] = {
    m: feat for feat in FEATURES for m in feat.macros}

#: Every macro name the registry gives a stance.
MACROS: frozenset[str] = frozenset(_BY_MACRO)

#: The edition the two lists below were transcribed from (WP-1530). It is
#: newer than :data:`SPEC`, whose section numbers are version 8's: the
#: standard macros are §22.1 here and were §19.3 there.
INDEX_SPEC = ("TOPAS Academic Technical Reference, version 9 "
              "(topas-academic.com/technical_reference, read 2026-11-02), "
              "Table 3-1 and §22.1")

#: The equation functions of Table 3-1, which states them case-sensitive. A
#: call to one computes a value inside an equation, so it is never an unread
#: call: what the equation states is the keyword's, and the keyword has a
#: stance of its own.
EQUATION_FUNCTIONS: frozenset[str] = frozenset({
    "And", "Or", "ArcCos", "ArcSin", "ArcTan", "ArcTan2", "Cos", "Cosh",
    "Erf_Approx", "Erfc_Approx", "Exp", "Gamma_Approx", "Gamma_Ln_Approx",
    "Gamma_P", "Gamma_Q", "Ln", "Sin", "Sinh", "Sqrt", "Tan", "Tanh", "For",
    "Get", "If", "Sum", "Abs", "Concat", "Error", "Load_Eval", "Max", "Min",
    "Mod", "Obj_There", "Prm_There", "Rand", "Rand_Normal", "Round", "To_Prm",
    "To_String", "Sign", "AB_Cyl_Corr", "AL_Cyl_Corr", "Bkg_at", "Constant",
    "Ln_Normal_x_at_CD", "PV_Lor_from_GL", "Sites_Geometry_Distance",
    "Sites_Geometry_Angle", "Sites_Geometry_Dihedral_Angle", "Value_at_X",
    "Voigt_FWHM_GL", "Voigt_Integral_Breadth_GL", "Ycalc_at", "Yobs_Avg",
    "Yobs_at", "Yobs_dx_at", "Yobs_Min"})

#: Every standard macro §22.1 lists with an argument list, so that a file can
#: call it. The completeness oracle for :attr:`Coverage.unread_calls`: a test
#: holds that each one has a disposition — a row here, a read in
#: :mod:`~rietx.io.projects.topas`, or :data:`MODEL_FREE_MACROS` — so a
#: library macro is never reported as "called and not read". The macros listed
#: without arguments (``No_Th_Dependence``, ``Lorentz_Factor``,
#: ``ADPs_Keep_PD``, ``Temperature_Regime``, ``Exclude``) cannot be a call and
#: are not here. ``Out_*`` and ``Create_*`` (§22.1.10) are matched by prefix in
#: the reader. A macro the reference does not list (``Rp_Peak``) is still
#: reported as unread: nothing here says what it states.
STANDARD_MACROS: frozenset[str] = frozenset({
    # §22.1.1, the xdd macros
    "RAW", "DAT", "XDD", "XY", "XYE", "SCR", "SHELX_HKL4",
    # §22.1.2
    "Cubic", "Tetragonal", "Hexagonal", "Rhombohedral",
    # §22.1.3
    "CuKa1", "CuK1sharp", "CuKa2_analyt", "CuKa2", "CuKa4_Holzer", "CuKa5",
    "CuKa5_Berger", "CoKa3", "CoKa7_Holzer", "CrKa7_Holzer", "FeKa7_Holzer",
    "MnKa7_Holzer", "NiKa5_Holzer", "MoKa2", "CuKb4_Holzer", "CoKb6_Holzer",
    "CrKb5_Holzer", "FeKb4_Holzer", "MnKb5_Holzer", "NiKb4_Holzer",
    # §22.1.4
    "Radius", "Specimen_Tilt", "Slit_Width", "SW", "Sample_Thickness",
    "Divergence", "Variable_Divergence", "Variable_Divergence_Shape",
    "Simple_Axial_Model", "Full_Axial_Model", "Finger_et_al", "Tube_Tails",
    "UVW",
    # §22.1.5-22.1.8
    "PV_Peak_Type", "TCHZ_Peak_Type", "PVII_Peak_Type",
    "Apply_Brindley_Spherical_R_PD", "MVW", "Zero_Error", "ZE",
    "Specimen_Displacement", "SD", "LP_Factor",
    "Surface_Roughness_Pitschke_et_al", "Surface_Roughness_Suortti",
    "Preferred_Orientation", "PO", "PO_Two_Directions",
    "PO_Spherical_Harmonics",
    # §22.1.9
    "Anti_Bump", "AI_Anti_Bump", "Parabola_N", "Grs_Interaction",
    "Grs_No_Repulsion", "Grs_BornMayer", "Distance_Restrain", "Angle_Restrain",
    "Flatten", "Distance_Restrain_Keep_Within", "Distance_Restrain_Keep_Out",
    "Keep_Atom_Within_Box",
    # §22.1.10, less the Out_*/Create_* reporting macros
    "Absorption_With_Sample_Thickness_mm_Shape_Intensity", "CS_L",
    "Crystallite_Size", "CS", "CS_G", "Strain_L", "Microstrain", "MS",
    "Strain_G", "LVol_FWHM_CS_G_L",
    # §22.1.11
    "TOF_XYE", "TOF_GSAS", "TOF_LAM", "TOF_x_axis_calibration",
    "TOF_Exponential", "TOF_CS_L", "TOF_CS_G", "TOF_PV",
    # §22.1.12
    "STR", "Decompose", "Mixture_LAC_1_on_cm", "Phase_Density_g_on_cm3",
    "Phase_LAC_1_on_cm", "Gauss", "Lorentzian"})

#: The standard macros that state nothing about the model, so a call to one
#: owes the caller no word: the three absorption and density macros of §22.1.12
#: define a quantity the run reports, ``Gauss``/``Lorentzian`` are functions an
#: equation evaluates, and ``Decompose`` selects which data points the run fits,
#: the run-level class the module docstring ignores. Drawn from
#: :data:`STANDARD_MACROS` only, which a test holds.
MODEL_FREE_MACROS: frozenset[str] = frozenset({
    "Decompose", "Mixture_LAC_1_on_cm", "Phase_Density_g_on_cm3",
    "Phase_LAC_1_on_cm", "Gauss", "Lorentzian"})

#: Every keyword the format allows inside a phase, from the reference's §5.1
#: tree (``Tstr_details`` plus the ``Tphase_*``/``Tcomm_*`` groups reachable
#: under ``str``, and the ``site``/``occ`` children one level down). This is the
#: **completeness oracle**, not a convenience: a meta-test partitions it against
#: :data:`FEATURES` both ways, so a keyword here without a stance fails and a
#: stance naming a keyword absent here fails. Adding a keyword to this set is
#: therefore how a new construct is declared, and the test says what it costs.
PHASE_SCOPE: frozenset[str] = frozenset(_BY_KEYWORD)


#: The keywords worth scanning a phase for: the ones whose stance produces an
#: outcome. A ``READ`` keyword is already read and an ``IGNORED`` one is
#: declared irrelevant, so finding either changes nothing — and several of them
#: are one or two characters (``a``, ``x``, ``min``), where a token scan is all
#: cost and no answer. The registry still carries them, because the
#: completeness oracle is the whole scope and not the interesting part of it.
SCANNED: frozenset[str] = frozenset(
    kw for kw, f in _BY_KEYWORD.items()
    if f.stance in (Stance.REPORTED, Stance.REFUSED))


#: The **file-level** constructs: the macro and pre-processor forms that decide
#: what text there is, outside the phase scope :data:`FEATURES` partitions.
#: Declared here so the reach is a table too (WP-1433), with one difference
#: from the phase rows: a ``REFUSED`` row here refuses at **read**
#: (:func:`~rietx.io.projects.topas.read_topas_inp` raises naming it), since
#: with it present the text in hand is not the text TOPAS parsed — there is no
#: model to build without it. Written against :data:`PREPROCESSOR_SPEC`.
PREPROCESSOR_SPEC = ("TOPAS Academic Technical Reference, version 8 "
                     "(2026-08-12), §19.1.2 and §19.3.12")

PREPROCESSOR: tuple[Feature, ...] = (
    _f("STR macro", Stance.READ,
       "a phase opened by `STR(sg)` or `STR(sg, name)`, read as a `str` "
       "stating that space group (and that phase_name)", "STR",
       why="§19.3.12 says what `STR(sg)` does, so the reader writes the `str` "
           "it opens; the body is a macro library's and is not reproduced"),
    _f("name conditionals", Stance.READ,
       "text selected by whether a name was `#define`d",
       "#define", "#ifdef", "#ifndef", "#else", "#endif"),
    _f("hash conditionals", Stance.READ,
       "text selected by a condition over `#prm` hash parameters: numbers, "
       "+ - * / and `^` (left-binding, as Table 3-1 states it), the "
       "comparisons and `And`; `#out` inside a condition; "
       "`Run_Number` as the first run's 0, reported as TOPAS_FIRST_RUN_READ "
       "where `num_runs` states more",
       "#prm", "#if", "#elseif", "#out", "Run_Number",
       why="`#out` outside a condition is left in the text, so a value read "
           "through one refuses as stated-but-unreadable"),
    _f("undecidable hash condition", Stance.REFUSED,
       "a condition reaching `Rand`, a string, a function other than `And`, "
       "a character that is no operator here (`%`, a lone `=`), or a `^` "
       "Table 3-1 does not order (`-x^y`, `x*y^z`)",
       "Rand", "Mod", "%",
       why="§19.1.2's own `#prm ran = Constant(Rand(0,1)); #if ran < 0.5;` has "
           "no answer a reader can give, and neither does a function this "
           "reader does not evaluate"),
    _f("STR template or own STR", Stance.REFUSED,
       "`STR(######, ...)`, a template slot no script has filled, or a file "
       "defining its own `macro STR`, whose body is what TOPAS would expand",
       "STR(######", "macro STR",
       why="the first is not a space group; the second is a body this reader "
           "does not expand"),
    _f("negated name test", Stance.REFUSED,
       "`#ifdef !name`, which the reference does not describe", "#ifdef !",
       why="read as a negation the branch is live, as a name it is dead"),
    _f("text from elsewhere", Stance.REFUSED,
       "text pulled in from another file",
       "#include", "#ingest", "#external_INP"),
    _f("un-definition", Stance.REFUSED,
       "a directive un-defining names already collected",
       "#undef", "#delete_macros"),
    _f("macro-expansion directives", Stance.REFUSED,
       "a `#m_*` directive outside any macro body", "#m_if", "#m_ifarg"),
)


def stance(keyword: str) -> Stance | None:
    """This reader's declared stance on ``keyword`` (or a macro name), or
    ``None`` if the table does not cover it."""
    feat = feature(keyword)
    return feat.stance if feat else None


def feature(keyword: str) -> Feature | None:
    """The :class:`Feature` ``keyword`` (or a macro name) belongs to, or
    ``None``."""
    return _BY_KEYWORD.get(keyword) or _BY_MACRO.get(keyword)


@dataclass(frozen=True)
class Hit:
    """One feature a file states, and the keywords it stated it with.

    The keywords (and macro names) are the ones actually **found**, not the
    feature's whole list: a message naming every convolution keyword TOPAS
    has, when the file wrote two of them, is a message a reader stops reading.
    """

    feature: Feature
    keywords: tuple[str, ...]
    #: Which phases stated it, by name, so a multi-phase file says *where*.
    phases: tuple[str, ...] = ()

    def __str__(self) -> str:
        where = f" [{', '.join(self.phases)}]" if self.phases else ""
        return f"{self.feature.name} ({', '.join(self.keywords)}){where}"


@dataclass(frozen=True)
class Coverage:
    """What one import met, and what it did with it.

    Carried on :class:`~rietx.io.projects.topas.TopasModel` so that "this import
    is partial" is a **fact on the answer** rather than only a message on a
    channel a caller may not have passed — the same reason
    ``skipped_blocks`` is on the model whether or not a ``diagnostics`` list was
    given. A caller that wants the whole story reads ``reported``/``refused``;
    one that wants a yes/no reads :attr:`partial`.
    """

    #: Features the file states that this import does not carry, in registry
    #: order. A partial import, named.
    reported: tuple[Hit, ...] = ()
    #: Features whose absence would misrepresent the file.
    #: :func:`~rietx.io.projects.topas.read_topas_inp` records them and does not
    #: raise — the model is still an honest account of the text, and reading it
    #: is how a caller finds out what the file states.
    #: :func:`~rietx.io.projects.topas.to_structure` is what refuses.
    refused: tuple[Hit, ...] = ()
    #: Names the file **calls** as ``name(…)`` that it does not define, that
    #: carry no row here and that the reader does not read (WP-1530, #651).
    #: A user's own include and a misspelt macro look the same from outside,
    #: which is why the wording is "called and not read" and nothing stronger.
    #: A bare identifier in keyword position (``lor_fwhmm 0.1``) is **not**
    #: covered: telling a keyword from a parameter name in value position needs
    #: the grammar, and TOPAS itself stops on such a line.
    unread_calls: tuple[str, ...] = ()

    @property
    def partial(self) -> bool:
        """True where the file states something about the model this import does
        not carry."""
        return bool(self.reported or self.refused or self.unread_calls)

    def summary(self) -> str:
        """One line naming what was not imported, for a diagnostic message."""
        return self.summary_of(self.reported + self.refused)

    @staticmethod
    def summary_of(hits) -> str:
        """The same line for one stance's hits, so the two arms of a report read
        the same way without either restating the other's."""
        return "; ".join(str(h) for h in hits)


def classify(found: dict[str, set[str]],
             unread_calls: tuple[str, ...] = ()) -> Coverage:
    """Sort keywords into stances. ``found`` maps a keyword or a macro name to
    the phase names that stated it, ``""`` for one stated outside any phase.

    The token scan itself belongs to the reader, which owns the mask that makes
    one safe (a ``site`` inside a quoted path is not a keyword). This function
    only decides what the stances mean, so it stays testable without a file.
    """
    reported: list[Hit] = []
    refused: list[Hit] = []
    for feat in FEATURES:
        hits = sorted(kw for kw in feat.keywords + feat.macros if kw in found)
        if not hits:
            continue
        phases = sorted({p for kw in hits for p in found[kw] if p})
        bucket = (reported if feat.stance is Stance.REPORTED
                  else refused if feat.stance is Stance.REFUSED else None)
        if bucket is not None:
            bucket.append(Hit(feat, tuple(hits), tuple(phases)))
    return Coverage(tuple(reported), tuple(refused), tuple(unread_calls))
