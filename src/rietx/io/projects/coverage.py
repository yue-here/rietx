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

    ``keywords`` are the format's own identifiers. ``what`` is one line in this
    package's words, written to be read *in a diagnostic message* — it says what
    the file states, not what TOPAS does with it. ``why`` is present only where
    the stance needs an argument: a ``REFUSED`` row has to say what building
    without it would misrepresent, and a ``REPORTED`` one what the caller is
    losing.
    """

    name: str
    keywords: tuple[str, ...]
    stance: Stance
    what: str
    why: str = ""

    def __str__(self) -> str:
        return f"{self.name} ({', '.join(self.keywords)})"


def _f(name, stance, what, *keywords, why=""):
    return Feature(name, tuple(keywords), stance, what, why)


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
           "keyword is not droppable with a diagnostic either"),

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
           "convolution stacks do not correspond term for term"),
    _f("specimen corrections", Stance.REPORTED,
       "a specimen or geometry correction",
       "capillary_diameter_mm", "capillary_parallel_beam",
       "capillary_divergent_beam", "capillary_u_cm_inv",
       "brindley_spherical_r_cm", "aberration_range_change_allowed",
       why="the correction's parameters are the author's model of the "
           "specimen, and they are not transferable term for term"),
    _f("preferred orientation", Stance.REPORTED,
       "a texture model", "spherical_harmonics_hkl", "normals_plot",
       "normals_plot_min_d",
       why="rietx carries March-Dollase and spherical harmonics are a v2 "
           "fence, so the texture is dropped and the intensities it explained "
           "are not"),
    _f("restraints and penalties", Stance.REPORTED,
       "a restraint, penalty or interatomic interaction",
       "penalty", "phase_penalties", "only_penalties", "atomic_interaction",
       "ai_anti_bump", "ai_sites_1", "ai_sites_2", "ai_no_self_interation",
       "ai_closest_N", "ai_radius", "ai_exclude_eq_0", "ai_only_eq_0",
       "box_interaction", "grs_interaction", "no_self_interaction",
       "from_N", "to_N", "qi", "qj", "sites_flatten", "sites_flatten_tol",
       why="rietx has soft restraints, but a penalty is an arbitrary equation "
           "over the file's own parameter names and does not translate"),
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


def stance(keyword: str) -> Stance | None:
    """This reader's declared stance on ``keyword``, or ``None`` if the keyword
    is not in the phase scope this table covers."""
    feat = _BY_KEYWORD.get(keyword)
    return feat.stance if feat else None


def feature(keyword: str) -> Feature | None:
    """The :class:`Feature` ``keyword`` belongs to, or ``None``."""
    return _BY_KEYWORD.get(keyword)


@dataclass(frozen=True)
class Hit:
    """One feature a file states, and the keywords it stated it with.

    The keywords are the ones actually **found**, not the feature's whole list:
    a message naming every convolution keyword TOPAS has, when the file wrote
    two of them, is a message a reader stops reading.
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

    @property
    def partial(self) -> bool:
        """True where the file states something about the model this import does
        not carry."""
        return bool(self.reported or self.refused)

    def summary(self) -> str:
        """One line naming what was not imported, for a diagnostic message."""
        return self.summary_of(self.reported + self.refused)

    @staticmethod
    def summary_of(hits) -> str:
        """The same line for one stance's hits, so the two arms of a report read
        the same way without either restating the other's."""
        return "; ".join(str(h) for h in hits)


def classify(found: dict[str, set[str]]) -> Coverage:
    """Sort keywords into stances. ``found`` maps a keyword to the phase names
    that stated it.

    The token scan itself belongs to the reader, which owns the mask that makes
    one safe (a ``site`` inside a quoted path is not a keyword). This function
    only decides what the stances mean, so it stays testable without a file.
    """
    reported: list[Hit] = []
    refused: list[Hit] = []
    for feat in FEATURES:
        hits = sorted(kw for kw in feat.keywords if kw in found)
        if not hits:
            continue
        phases = sorted({p for kw in hits for p in found[kw] if p})
        bucket = (reported if feat.stance is Stance.REPORTED
                  else refused if feat.stance is Stance.REFUSED else None)
        if bucket is not None:
            bucket.append(Hit(feat, tuple(hits), tuple(phases)))
    return Coverage(tuple(reported), tuple(refused))
