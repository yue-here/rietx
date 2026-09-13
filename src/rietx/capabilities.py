"""What this build of rietx can do, as data (WP-1007).

One call a client makes once, so it never has to guess: which backends exist and
which are *installed*, which solvers and plan presets are registered, which
intensity modes and anodes are known, what ``read_pattern`` actually opens, and
which of the six versioned contracts it is talking to.

**Every arm is quoted from the live registry, never restated.** The lesson is
measured rather than stylistic: the fourth backend name arrived two days after
the third (WP-0408), and a hand-written list would have been wrong for those two
days while looking authoritative. ``tests/test_capabilities.py`` fails if a
member of ``BACKEND_NAMES``, ``SOLVERS``, ``PLAN_PRESETS``, ``Mode``, the anode
table or ``PATTERN_FORMATS`` is missing from its arm — the registry-membership
meta-test WP-0602 wrote for the JSON tool schema, which outlived it (that
schema and its module went in WP-1303; this call is what a client asks now).

The same rule shapes :attr:`Capabilities.features`: each flag is a **derived
predicate** — a schema field's presence, a top-level export's existence — and not
a literal ``True``. A literal is a claim that cannot rot loudly; a derivation
either keeps telling the truth or stops importing.  **But a derived flag rots
too, and it rots silently** (WP-1037): ``features["indexing"]`` asked
``hasattr(rx, "index")`` from the day it was written, while the export that
landed (WP-1024) is ``index_pattern`` — so the flag read ``False`` for the whole
life of the feature, and its test asserted the same ``hasattr`` and could never
fail.  The repair is to make the *name* data: :data:`_SURFACE_FLAGS` pairs each
flag with the export it claims, ``_features()`` derives the flags from that one
table, and the meta-test checks every name in it against ``rietx.__all__`` —
an authority the predicate itself never consults, which is what a tautology
lacks.
"""

from __future__ import annotations

import importlib.util
from typing import get_args

from pydantic import Field

from .backend.api import (
    BACKEND_NAMES,
    BACKEND_REQUIRES,
    EXPERIMENTAL_BACKENDS,
    backend_dtype_note,
)

# The anode and Kβ tables are module-private by history (several tests import
# them the same way), and are quoted rather than copied: the registry meta-test
# fails loudly if either name moves, which is the property that matters — see the
# module docstring on derivation over restatement.
from .background.diagnostics import _KBETA
from .history.events import EVENT_SCHEMA_VERSION

# The plans arm iterates PLAN_INFO, not PLAN_PRESETS: the two are held in
# bijection by tests/test_params_surface.py, so quoting the one that carries the
# four facts a chooser needs keeps the arm complete without a second assertion
# about the same pair (WP-1007's inherited note from WP-1004).  The search
# presets follow the identical pattern one registry over (WP-1042, bijection
# held by tests/test_indexing_scheduler.py).
from .indexing.engines import (
    CENTRINGS,
    DEFAULT_SEARCH_PRESET,
    SEARCH_PRESET_INFO,
    SEARCH_PRESETS,
    SYSTEM_ORDER,
    engine_descriptions,
)
from .io.readers import PATTERN_FORMATS, READER_OPTIONS
from .optimize.least_squares import SOLVERS
from .refine import _VERSION
from .report.schemas import THRESHOLDS_VERSION
from .schemas.common import SCHEMA_VERSION, Base, Mode
from .schemas.indexing import INDEXING_THRESHOLDS_VERSION, SHIFT_TEMPLATES
from .schemas.instrument import _KA_DOUBLETS, _RADIATIONS
from .schemas.project import PROJECT_FORMAT_VERSION
from .strategy.staged import PLAN_INFO


class BackendCapability(Base):
    """A Jacobian backend, and whether this machine can actually run it."""

    name: str
    #: is its optional dependency importable *here* — the question a GUI's
    #: backend menu needs answered, which the registry alone cannot answer
    available: bool
    #: kept for validation and future work, not for production refinements
    #: (torch is an order of magnitude slower than the analytic numpy path and
    #: MPS two — see docs/milestones/v0.4.md)
    experimental: bool
    #: the distribution to install, or ``None`` when always available
    requires: str | None
    #: precision this backend computes at, for ``Provenance.dtype``
    dtype: str


class PlanCapability(Base):
    """A staged-plan preset with the four facts a chooser needs (``PLAN_INFO``)."""

    name: str
    title: str
    description: str
    modes: list[Mode]
    when_to_use: str


class SearchPresetCapability(Base):
    """An indexing search preset (WP-1042): the ceiling and the measured cost.

    ``total_budget_seconds`` is the whole-run ceiling the preset fills in
    (``None`` = unbounded — ``estimate_ceiling`` is then the worst-case
    arithmetic); ``typical_seconds`` is the **measured** range over the
    known-cell corpus, which is a different kind of number and says so by
    being a range.
    """

    name: str
    title: str
    description: str
    when_to_use: str
    default: bool
    total_budget_seconds: float | None
    typical_seconds: tuple[float, float]


class EngineCapability(Base):
    """An indexing search engine, with the one-line description registration
    carries (WP-1045) — quoted so a client's engine checkboxes and the agent
    schema cannot name different sets."""

    name: str
    description: str


class AnodeCapability(Base):
    """A laboratory anode this package knows the emission wavelengths of."""

    name: str
    wavelengths: list[float]
    #: ``True`` for the ``"CuKa1"``-style entries: an incident-side
    #: monochromator has removed Kα2, so there is one line rather than two
    kalpha1_only: bool
    #: Kβ1,3 for the contamination check, or ``None`` when untabulated.  Not a
    #: modelled emission line — one |F|² cannot serve Kβ and Kα together.
    kbeta: float | None


class RadiationCapability(Base):
    """One kind of source this build can refine against, and what differs.

    Not a feature flag, because "neutron: true" answers no question a caller
    has.  What a caller needs is which discriminator value to write and what
    changes underneath it, since the *shape* of a source differs between the
    two: an X-ray source carries an emission-line list and a dispersion
    channel, a neutron source carries one wavelength and neither.
    """

    #: the ``kind`` discriminator, written verbatim into ``Instrument.source``
    kind: str
    title: str
    #: what does the scattering, and therefore whether the amplitude falls off
    #: with Q — the single physical difference the rest follows from
    scatterer: str
    #: ``True`` where the source carries a ``Dispersion`` channel.  Derived
    #: from the class, never asserted: f′/f″ is an X-ray core-level effect, and
    #: a neutron source has no field for it to be set on
    anomalous_dispersion: bool
    #: how many emission lines the source can carry.  ``None`` is unbounded —
    #: an anode with a Kα doublet declares its own list, and a source that can
    #: declare λ/n harmonics grows its spectrum the same way, so this stopped
    #: being 1 for neutrons the moment harmonics landed.  1 means the spectrum
    #: is one wavelength and can be nothing else.
    max_emission_lines: int | None
    #: ``True`` where the Lorentz-polarisation K is refinable.  For neutrons it
    #: is pinned at 1, which collapses the factor to the bare Lorentz factor
    polarization_refinable: bool
    #: ``True`` where the source accepts declared λ/n monochromator harmonics.
    #: Read off ``Source.harmonics_supported`` — the same attribute the schema's
    #: own refusal reads — so this cannot claim a support the validator denies.
    #: False for X-rays, where one shared f′/f″ cannot serve λ and λ/n.
    harmonic_contamination: bool


class ReaderCapability(Base):
    """A pattern format, how it is recognised, and where its σ comes from."""

    name: str
    title: str
    extensions: list[str]
    sniff: str
    sigma: str
    #: reader keywords a caller may need to supply *and* record — ``block`` for
    #: pdCIF, because the same file reads as a different pattern without it.
    #: Names only; what each one *means* is :class:`ReaderOptionCapability`,
    #: which is build-wide rather than per format
    options: list[str]
    #: set when this entry is a format the build **recognises in order to
    #: decline** — a ``.dif`` peak list is not a profile — carrying why.  A
    #: client reads it to tell "we can open this" from "we know what this is
    #: and it is the wrong kind of file", which are different answers
    refuses: str | None = None


class ReaderOptionCapability(Base):
    """One reader keyword in the build's vocabulary, and what it does.

    Separate from :class:`ReaderCapability` because the vocabulary is shared:
    ``scan`` means the same thing in five formats, and a client rendering a
    control for it should not have to pick which format's copy of the prose to
    quote.  ``ReaderCapability.options`` names the subset each format honours.
    """

    name: str
    #: ``"str"`` or ``"int"`` — a form needs to know which control to draw, and
    #: a project records every option as a string, so someone must coerce
    kind: str
    help: str


class Capabilities(Base):
    """The whole answer.  JSON-serialisable; WP-1008 serves it verbatim."""

    package_version: str
    #: the six versioned contracts a client can be talking to, all live values.
    #: The count moved from four to five when WP-1009 added the text document,
    #: which is the argument for putting them here rather than in prose: a client
    #: reads the arm, not a paragraph that has to be remembered — and from five
    #: to six when WP-1003's review found the indexing thresholds riding on
    #: every ``IndexingResult`` without being quoted here.
    schema_version: str
    report_thresholds_version: str
    event_schema_version: str
    project_format_version: str
    #: ``rxt N`` — the line-oriented project document (WP-1009).  A client that
    #: offers a text pane needs it *before* fetching a document
    textdoc_format_version: str
    #: gates/vocabulary contract of the indexing answer (caveat and grade
    #: vocabularies, gate thresholds) — ``schemas.indexing``'s peer of
    #: ``report_thresholds_version``, stamped on every ``IndexingResult``
    indexing_thresholds_version: str

    backends: list[BackendCapability] = Field(default_factory=list)
    solvers: list[str] = Field(default_factory=list)
    plans: list[PlanCapability] = Field(default_factory=list)
    search_presets: list[SearchPresetCapability] = Field(default_factory=list)
    #: the indexing control vocabularies (WP-1045), quoted from the live
    #: registries so the GUI form, the agent schema and ``SearchSpec`` cannot
    #: disagree about what may be asked for
    indexing_engines: list[EngineCapability] = Field(default_factory=list)
    #: ``SYSTEM_ORDER`` verbatim — the order *is* information (cheapest first)
    crystal_systems: list[str] = Field(default_factory=list)
    #: Bravais centrings each system admits, ``engines.CENTRINGS`` verbatim
    centrings: dict[str, list[str]] = Field(default_factory=dict)
    shift_templates: list[str] = Field(default_factory=list)
    modes: list[Mode] = Field(default_factory=list)
    #: the source kinds ``Instrument.source`` discriminates on, derived from the
    #: union itself.  ``anodes`` below is a *sub*-vocabulary of the X-ray entry
    #: and says nothing about the others, which is why both arms are here
    radiations: list[RadiationCapability] = Field(default_factory=list)
    anodes: list[AnodeCapability] = Field(default_factory=list)
    reader_formats: list[ReaderCapability] = Field(default_factory=list)
    #: every keyword ``read_pattern`` accepts, across all formats — the
    #: allowlist itself, so a client renders a control per option rather than
    #: keeping a second copy of the vocabulary
    reader_options: list[ReaderOptionCapability] = Field(default_factory=list)
    features: dict[str, bool] = Field(default_factory=dict)
    #: Absolute path of the agent skill this build carries (WP-1304), or
    #: ``None`` where neither the wheel's copy nor a repository tree is present.
    #: A *path* rather than the text: the skill is ~156 kB across nine files and
    #: a harness wants to point at the directory, not to be handed it — and this
    #: call is the one place a client already asks "what does this build have?".
    skill_path: str | None = None


def capabilities() -> Capabilities:
    """Everything this build can do — see the module docstring."""
    # Local, and not for cost: ``rietx.gui`` imports the session, which imports
    # this module, so a top-level import here would be a cycle.  By call time the
    # package is initialised and the constant is reachable — still quoted from
    # where it is defined, never copied.
    from .gui.textdoc import FORMAT_VERSION as TEXTDOC_FORMAT_VERSION
    from .skill import skill_path

    _skill = skill_path()

    return Capabilities(
        skill_path=str(_skill) if _skill is not None else None,
        package_version=_VERSION,
        schema_version=SCHEMA_VERSION,
        report_thresholds_version=THRESHOLDS_VERSION,
        event_schema_version=EVENT_SCHEMA_VERSION,
        project_format_version=PROJECT_FORMAT_VERSION,
        textdoc_format_version=TEXTDOC_FORMAT_VERSION,
        indexing_thresholds_version=INDEXING_THRESHOLDS_VERSION,
        backends=[_backend(name) for name in BACKEND_NAMES],
        solvers=list(SOLVERS),
        plans=[PlanCapability(name=name, title=info.title,
                              description=info.description,
                              modes=list(info.modes),
                              when_to_use=info.when_to_use)
               for name, info in sorted(PLAN_INFO.items())],
        search_presets=[
            SearchPresetCapability(
                name=name, title=info.title, description=info.description,
                when_to_use=info.when_to_use,
                default=name == DEFAULT_SEARCH_PRESET,
                total_budget_seconds=SEARCH_PRESETS[name],
                typical_seconds=info.typical_seconds)
            for name, info in sorted(SEARCH_PRESET_INFO.items())],
        indexing_engines=[
            EngineCapability(name=name, description=desc)
            for name, desc in sorted(engine_descriptions().items())],
        crystal_systems=list(SYSTEM_ORDER),
        centrings={system: list(letters)
                   for system, letters in CENTRINGS.items()},
        shift_templates=list(SHIFT_TEMPLATES),
        modes=list(get_args(Mode)),
        radiations=[_radiation(cls) for cls in _source_classes()],
        anodes=[_anode(name) for name in sorted(_RADIATIONS)],
        reader_formats=[
            ReaderCapability(name=f.name, title=f.title,
                             extensions=list(f.extensions), sniff=f.sniff,
                             sigma=f.sigma, options=list(f.options),
                             refuses=f.refuses)
            for f in PATTERN_FORMATS],
        reader_options=[
            ReaderOptionCapability(name=o.name, kind=o.kind, help=o.help)
            for _, o in sorted(READER_OPTIONS.items())],
        features=_features(),
    )


def _backend(name: str) -> BackendCapability:
    requires = BACKEND_REQUIRES.get(name)
    return BackendCapability(
        name=name,
        available=requires is None or importlib.util.find_spec(requires) is not None,
        experimental=name in EXPERIMENTAL_BACKENDS,
        requires=requires,
        dtype=backend_dtype_note(name),
    )


#: What is physically different about each radiation, one line each.  Prose
#: only — every *derivable* field of :class:`RadiationCapability` is read off
#: the class below, so a new source kind with no entry here still appears in the
#: arm (titled by its own discriminator) rather than being silently absent.
_RADIATION_NOTES: dict[str, tuple[str, str]] = {
    "xray_cw": ("Constant-wavelength X-ray",
                "the electron density, so f falls off with Q"),
    "neutron_cw": ("Constant-wavelength neutron",
                   "the nucleus, a point scatterer, so b is independent of Q"),
}


def _source_classes() -> list[type]:
    """The ``Instrument.source`` union, in declaration order.

    Read off the annotation rather than listed, so a source kind added to the
    union cannot be missing from the arm — the ``_SURFACE_FLAGS`` lesson
    (WP-1037) applied to a vocabulary instead of a flag.  A single class, before
    a second radiation existed, is not a union and is handled as one member.
    """
    from .schemas.instrument import Instrument

    annotation = Instrument.model_fields["source"].annotation
    members = get_args(annotation)
    return list(members) if members else [annotation]


def _radiation(cls: type) -> RadiationCapability:
    kind = get_args(cls.model_fields["kind"].annotation)[0]
    title, scatterer = _RADIATION_NOTES.get(kind, (kind, "undocumented"))
    lines_field = cls.model_fields.get("lines")
    # Not "does the class have a harmonics field" — both source classes do, so
    # that predicate would report X-ray support the validator refuses.  The
    # class attribute is the one authority for the answer and
    # ``check_harmonics`` reads the same one.
    harmonics = bool(getattr(cls, "harmonics_supported", False))
    return RadiationCapability(
        kind=kind,
        title=title,
        scatterer=scatterer,
        # all derived predicates, never literals: a source that grows a
        # dispersion channel flips its own flag
        anomalous_dispersion="dispersion" in cls.model_fields,
        # a declared spectrum *or* a harmonic declaration lifts the cap: a
        # single-wavelength source that can carry λ/n is not a one-line source
        max_emission_lines=None if (lines_field is not None or harmonics) else 1,
        polarization_refinable="polarization" in cls.model_fields,
        harmonic_contamination=harmonics,
    )


def _anode(name: str) -> AnodeCapability:
    lines = _RADIATIONS[name]
    doublet = name if name in _KA_DOUBLETS else name[:-1]
    return AnodeCapability(
        name=name,
        wavelengths=list(lines),
        kalpha1_only=name not in _KA_DOUBLETS,
        kbeta=_KBETA.get(doublet),
    )


#: Entry-point-shaped feature flags: flag → the top-level export whose existence
#: it reports.  One table, two consumers — ``_features()`` derives the flags from
#: it, and ``tests/test_capabilities.py`` checks every name in it against
#: ``rietx.__all__`` — because the two halves of a derived predicate (the name
#: asked about and the name that exists) can otherwise drift with the guarding
#: test asserting the same ``hasattr``, which is how ``indexing`` stayed
#: ``False`` from the day the feature shipped (see the module docstring).
_SURFACE_FLAGS: dict[str, str] = {
    "multi_histogram": "refine_multi",
    "sequential_series": "refine_sequential",
    "project_container": "Project",
    "background_estimation": "auto_background",
    "pattern_diagnostics": "diagnose",
    "peak_picking": "pick_peaks",
    "peak_fitting": "fit_peaks",
    "indexing": "index_pattern",
    # run control (WP-1006): a client that cannot cancel must not offer to
    "cancellation": "CancelToken",
    # the PowderLine interchange format (WP-1306).  Deliberately here and not
    # in ``reader_formats``: that arm answers "what can ``read_pattern``
    # open", and a recipe is a whole refinement rather than a pattern, so it
    # is a *feature* of the build and not a pattern format.
    "powderline_recipe": "read_recipe",
}


def _features() -> dict[str, bool]:
    """Feature flags, every one of them derived (see the module docstring).

    The schema-shaped ones ask the model whether it has the field, so a
    correction that is removed or renamed cannot leave a flag behind claiming
    it; the surface-shaped ones ask the package for the export
    :data:`_SURFACE_FLAGS` names, so a flag flips on its own when its entry
    point lands — provided the name is right, which is the meta-test's job.
    """
    import inspect

    import rietx as rx

    from .model import compiled
    from .refine import Refinement
    from .schemas.instrument import Geometry, Source
    from .schemas.structure import Atom, Phase

    return {
        # corrections and model extensions, asked of the schemas
        "anisotropic_adp": "aniso" in Atom.model_fields,
        "preferred_orientation": "preferred_orientation" in Phase.model_fields,
        "stephens_strain": "microstrain" in Phase.model_fields,
        "secondary_extinction": "extinction" in Phase.model_fields,
        "restraints": "restraints" in Phase.model_fields,
        "surface_roughness": "surface_roughness" in Geometry.model_fields,
        "capillary_absorption": "mu_r" in Geometry.model_fields,
        "flat_plate_absorption": "mu_t" in Geometry.model_fields,
        "anomalous_dispersion": "dispersion" in Source.model_fields,
        # …and whether dispersion is ON unless declined, which moved in WP-1001
        # and is the one default whose position changes published numbers.  Read
        # off the field rather than by constructing a Source, which would need
        # arguments and could run validators — a capability query must not.
        "anomalous_dispersion_default_on": Source.model_fields["dispersion"]
        .get_default(call_default_factory=True) is not None,
        # execution, asked of the tier itself (WP-1115).  Two flags because
        # they answer different questions and can disagree: *can* the compiled
        # kernels be built here — numba is a required dependency, but a
        # ``--no-deps`` or distro install legitimately has none — and *will*
        # the next residual use them, which ``RIETX_COMPILED=0`` decides.  A
        # client reporting "why is this build slow" needs the second.
        "compiled_kernels": compiled.available(),
        "compiled_kernels_active": compiled.enabled(),
        # delivery (WP-1058): whether a fit can hand back the report at every
        # stage boundary as well as at the end.  Asked of the keyword that
        # turns it on, because the envelope whose field this used to read was
        # deleted in WP-1303 and ``Refinement.fit`` is where the feature now
        # lives — a signature is as derived as a ``model_fields`` lookup and
        # stops importing the same way if the keyword is renamed
        "report_trajectory": "stage_reports" in inspect.signature(
            Refinement.fit).parameters,
        # entry points, asked of the package through the one table the
        # meta-test also reads
        **{flag: hasattr(rx, name) for flag, name in _SURFACE_FLAGS.items()},
    }
