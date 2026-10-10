"""WP-1202 — the help corpus against the live vocabularies it describes.

Every arm of ``rietx.help`` is keyed by a member of a vocabulary the package
already owns, and each test here crosses one arm against its own authority in
*both* directions: a member with no entry fails, and an entry describing
nothing fails too.  That second direction is the one a hand-written corpus
loses first, because a renamed member leaves its old entry sitting there
describing a name that no longer exists.

The rule is the root CLAUDE.md's, one rank over from ``_SURFACE_FLAGS``: a
description is a claim about a name, and a claim nothing checks rots silently.
``features["indexing"]`` spent its whole life ``False`` for exactly this reason.

Two fields are checked against the schemas rather than read: ``unit`` and
``default``.  A third check reaches into ``description``, which is authored
prose and has no authority in general — but where a sentence quotes a
*threshold* the code owns, that number does
(:func:`test_quoted_thresholds_are_the_codes_own`, WP-1437).  ``typical``
deliberately has none.
"""

from __future__ import annotations

import ast
import dataclasses
import json
import re
from pathlib import Path
from typing import get_args

import pytest
from pydantic import BaseModel

import rietx as rx
from rietx import _about
from rietx.gui.imports import INSTRUMENT_PRESETS
from rietx.help import (
    INSTRUMENT_FIELD_HELP,
    PARAMETER_HELP,
    PEAK_DIAGNOSTIC_HELP,
    PEAK_FLAG_HELP,
    PEAK_ORIGIN_HELP,
    READER_OPTION_HELP,
    SEARCH_FIELD_HELP,
    STAGE_FIELD_HELP,
    UNIT_DISPLAY,
    HelpEntry,
    help_key_for,
    help_registry,
    plan_help,
)
from rietx.io.formats.base import READER_OPTIONS
from rietx.params.vector import SIZE_CAP_MIN_SIZE_A, ParameterTable
from rietx.refine import SIZE_FLAG_SIZE_A, STRAIN_FLAG_WIDTH
from rietx.schemas.common import Parameter
from rietx.schemas.indexing import IndexingControls, ObservedPeak, PeakFlag
from rietx.schemas.instrument import (
    BackgroundFixedPlusChebyshev,
    BackgroundPSpline,
    EmissionLine,
    Geometry,
    HumpComponent,
    Instrument,
    PeakComponent,
    RoughnessPitschke,
    RoughnessSuortti,
    Source,
)
from rietx.schemas.plan import StageSpec
from rietx.schemas.structure import (
    Atom,
    Cell,
    MagneticSymmetry,
    Moment,
    Phase,
    PreferredOrientation,
    StephensStrain,
    Structure,
)
from rietx.strategy.staged import PLAN_INFO
from tests.test_manual import built_manual  # noqa: F401  (fixture, shared build)

ROOT = Path(__file__).resolve().parents[1]
INDEXING = ROOT / "src" / "rietx" / "indexing"


# ------------------------------------------------------------------ vocabulary
def _default_models() -> tuple[Structure, Instrument]:
    """A phase and an instrument whose every ``Parameter`` sits at its default.

    Both halves matter.  The paths are what a real ``ParameterTable`` produces,
    so the family globs are checked against the strings they will actually meet;
    and because nothing here overrides a ``Parameter``, each entry's ``value``
    *is* the schema default, which is what lets :func:`test_defaults_are_the_schemas_own`
    read the defaults off a table instead of restating them.

    Every optional block that *this* model can carry is present on purpose.
    ``tests/data/gui/fnmatch_cases.json`` is built from two models that carry no
    preferred-orientation block, so its path list has a hole exactly where a
    family would go unchecked; this is the coverage authority, and it closes it.
    The blocks one instrument cannot hold at once — the two roughness models are
    alternatives and a background is one of three — are :func:`_variant_models`,
    and everything here reads both.
    """
    def p(value: float) -> Parameter:
        return Parameter(value=value)

    cell = Cell(a=p(3.15), b=p(3.15), c=p(4.77),
                alpha=p(90.0), beta=p(90.0), gamma=p(120.0))
    phase = Phase(
        name="brucite", space_group="P -3 m 1", cell=cell,
        atoms=[
            Atom(label="Mg", species="Mg", x=p(0.0), y=p(0.0), z=p(0.0),
                 aniso=rx.AnisoU.isotropic(0.01, cell)),
            Atom(label="O", species="O", x=p(1 / 3), y=p(2 / 3), z=p(0.22)),
        ],
        preferred_orientation=PreferredOrientation(axis=(0, 0, 1)),
        # bare, not `isotropic()`: the coefficients have to sit at their
        # schema defaults for `test_defaults_are_the_schemas_own` to read
        # them off this table.  An all-zero block still produces the same
        # `dof.k` paths, since the subspace is derived from the operators.
        microstrain=StephensStrain(),
    )
    instrument = Instrument(source=Source(lines=[
        EmissionLine(wavelength=1.540598), EmissionLine(wavelength=1.544426)]))
    return Structure(phases=[phase]), instrument


def _variant_models() -> list[tuple[Structure, Instrument]]:
    """The optional blocks :func:`_default_models` structurally cannot carry.

    A ``Geometry`` holds at most one surface-roughness model and an
    ``Instrument`` one background, and roughness is refused outside
    ``bragg_brentano``, so "every optional block present" needs more than one
    instrument.  Without these the coverage tests are blind to live parameter
    families — the four roughness fields, the P-spline's air term and the three
    background-peak fields — which is the same hole the preferred-orientation
    block was in.  A single defaulted :class:`HumpComponent` declares the
    ``instrument.extra_components.*.{position,height,fwhm}`` families and a
    :class:`PeakComponent` the ``{center,area,eta}`` ones; without them the
    corpus could describe a component field the coverage tests never meet.  Both
    members are present rather than either, because ``fwhm`` is the one field
    name they share and its entry has to answer for both.

    The third instrument is the ``fixed_plus_chebyshev`` member, which is here
    for one path: its ``scale`` (WP-1309).  The other two members' coefficients
    spell ``c*`` the same way, so before the scale existed this member declared
    no family of its own and the corpus could not lose anything by omitting it.

    Every ``Parameter`` here sits at its schema default **except** the peak's
    ``center``, which has no usable default: finite bounds are what size its
    frozen window, so :class:`PeakComponent` refuses one without them.  The
    numbers below are arbitrary and only have to be finite.  The P-spline's
    air term is the other exception, having no default but absence.
    """
    structure, _ = _default_models()
    # The air term is absent by default (WP-1454), so the family is declared
    # here the way ``auto_background`` declares it, or the corpus could
    # describe it unmet.
    spline = BackgroundPSpline(
        breakpoints=[10.0, 20.0, 30.0, 40.0],
        coefficients=[Parameter(value=0.0) for _ in range(6)],
        air_scatter=Parameter(value=1e-3, min=0.0, transform="softplus"))
    return [
        (structure, Instrument(
            source=Source(lines=[EmissionLine(wavelength=1.540598)]),
            geometry=Geometry(kind="bragg_brentano",
                              goniometer_radius_mm=217.5,
                              surface_roughness=RoughnessSuortti()),
            background=spline,
            extra_components=[
                HumpComponent(),
                PeakComponent(center=Parameter(value=30.0, min=29.0, max=31.0,
                                               unit="deg")),
            ])),
        (structure, Instrument(
            source=Source(lines=[EmissionLine(wavelength=1.540598)]),
            geometry=Geometry(kind="bragg_brentano",
                              goniometer_radius_mm=217.5,
                              surface_roughness=RoughnessPitschke()))),
        (structure, Instrument(
            source=Source(lines=[EmissionLine(wavelength=1.540598)]),
            background=BackgroundFixedPlusChebyshev(
                fixed_two_theta=[10.0, 20.0, 30.0],
                fixed_intensity=[120.0, 100.0, 95.0]))),
        # A moment block: it needs its own phase, because the default model's
        # Mg carries an ``aniso`` and a site may not have both, and because a
        # moment needs a magnetic space group on the phase beside it.  Every
        # ``Parameter`` here sits at its schema default — the components are
        # the default zeros and the block is not free, which is a legal state
        # (a record, not a dead parameter) and the one that keeps
        # ``test_defaults_are_the_schemas_own`` reading defaults off this
        # table like every other model here.  The instrument is the X-ray one
        # every other model here uses: the moment DOFs come off the
        # *structure*, and a neutron source renames ``instrument.source.*``
        # paths this file's coverage tests enumerate separately.
        (Structure(phases=[Phase(
            name="MnF2", space_group="P 42/m n m",
            cell=Cell(a=Parameter(value=4.8734), b=Parameter(value=4.8734),
                      c=Parameter(value=3.3099), alpha=Parameter(value=90.0),
                      beta=Parameter(value=90.0), gamma=Parameter(value=90.0)),
            atoms=[
                Atom(label="Mn", species="Mn", x=Parameter(value=0.0),
                     y=Parameter(value=0.0), z=Parameter(value=0.0),
                     moment=Moment(ion="Mn2+")),
                Atom(label="F", species="F", x=Parameter(value=0.305),
                     y=Parameter(value=0.305), z=Parameter(value=0.0)),
            ],
            magnetic_symmetry=MagneticSymmetry.model_validate("136.499"),
        )]),
         Instrument(source=Source(lines=[EmissionLine(wavelength=1.540598)]))),
        # A rigid body (WP-1805): its origin, origin DOFs and rotation
        # increment are families no other model declares.  Two atoms placed
        # by ``body_from_atoms`` in a P1 cell, so the body decodes them back.
        (Structure(phases=[_body_phase()]),
         Instrument(source=Source(lines=[EmissionLine(wavelength=1.540598)]))),
    ]


def _body_phase() -> Phase:
    from rietx.crystallography.bodies import body_from_atoms

    phase = Phase(
        name="body", space_group="P1",
        cell=Cell(a=Parameter(value=6.0), b=Parameter(value=7.0),
                  c=Parameter(value=8.0), alpha=Parameter(value=90.0),
                  beta=Parameter(value=90.0), gamma=Parameter(value=90.0)),
        atoms=[Atom(label="C1", species="C", x=Parameter(value=0.1),
                    y=Parameter(value=0.2), z=Parameter(value=0.3)),
               Atom(label="O1", species="O", x=Parameter(value=0.3),
                    y=Parameter(value=0.2), z=Parameter(value=0.3))])
    from rietx.schemas.structure import BodyTorsion

    phase = phase.model_copy(update={"atoms": [*phase.atoms, Atom(
        label="H1", species="H", x=Parameter(value=0.35), y=Parameter(value=0.3),
        z=Parameter(value=0.3))]})
    body = body_from_atoms(phase, ["C1", "O1", "H1"], "coh")
    body = body.model_copy(update={"torsions": [
        BodyTorsion(name="t", axis=("C1", "O1"), moves=["H1"])]})
    return phase.model_copy(update={"rigid_bodies": [body]})


def _all_models() -> list[tuple[Structure, Instrument]]:
    return [_default_models(), *_variant_models()]


def _vocabulary() -> list[str]:
    """Every parameter path the models above produce, in table order."""
    seen: dict[str, None] = {}
    for structure, instrument in _all_models():
        for e in ParameterTable(structure, instrument).entries:
            seen.setdefault(e.path, None)
    return list(seen)


def _peak_diagnostic_codes() -> set[str]:
    """Every ``PEAK_*`` diagnostic code constructed under ``indexing/``.

    Derived by walking the source rather than listed, for the reason
    ``tests/test_docs_consistency.py`` walks it too: a code added to a screen is
    a message a person will read, and a curated list is what stops noticing.
    All twelve live in ``indexing/diagnostics.py`` today; the walk covers the
    package so one written elsewhere is still caught.
    """
    codes: set[str] = set()
    for py in sorted(INDEXING.rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if (kw.arg == "code" and isinstance(kw.value, ast.Constant)
                        and isinstance(kw.value.value, str)
                        and kw.value.value.startswith("PEAK_")):
                    codes.add(kw.value.value)
    return codes


def _preset_fields() -> set[str]:
    return {f for fields in INSTRUMENT_PRESETS.values() for f in fields}


def _search_fields() -> set[str]:
    """Every control ``ProjectDoc.indexing`` carries, flattened one level.

    Derived from the document's own model rather than named, so a field added
    to either half reaches this set: the three beside ``search`` and the
    eighteen inside it are one form to a person and two models to pydantic.
    """
    top = set(IndexingControls.model_fields) - {"search"}
    nested = IndexingControls.model_fields["search"].annotation.model_fields
    return top | set(nested)


def _arms() -> dict[str, dict[str, HelpEntry]]:
    """Every named arm, so a test can sweep all of them at once."""
    return {
        "peak_flags": PEAK_FLAG_HELP,
        "peak_diagnostics": PEAK_DIAGNOSTIC_HELP,
        "peak_origins": PEAK_ORIGIN_HELP,
        "stage_fields": STAGE_FIELD_HELP,
        "reader_options": READER_OPTION_HELP,
        "instrument_fields": INSTRUMENT_FIELD_HELP,
        "search_fields": SEARCH_FIELD_HELP,
        "plans": plan_help(),
    }


def _every_entry() -> list[tuple[str, HelpEntry]]:
    out = [(g, e) for g, e in PARAMETER_HELP.items()]
    for arm, entries in _arms().items():
        out += [(f"{arm}:{k}", e) for k, e in entries.items()]
    return out


# ------------------------------------------------------- the parameter families
def test_every_parameter_path_matches_exactly_one_family():
    """No path is undescribed, and none is described twice.

    Exactly-one is what lets :func:`rietx.help.help_key_for` return the first
    match without ranking by specificity.  Two families claiming one path would
    make its description depend on declaration order, which is not a property
    anybody should have to know about.
    """
    from fnmatch import fnmatchcase

    unclaimed, contested = [], []
    for path in _vocabulary():
        hits = [g for g in PARAMETER_HELP if fnmatchcase(path, g)]
        if not hits:
            unclaimed.append(path)
        elif len(hits) > 1:
            contested.append((path, hits))
    assert not unclaimed, (
        f"parameter paths no family describes: {unclaimed} — add a family to "
        "rietx.help.PARAMETER_HELP")
    assert not contested, (
        f"parameter paths claimed by more than one family: {contested} — "
        "help_key_for returns the first match, so this would make a "
        "description depend on declaration order")


def test_every_family_glob_describes_a_real_path():
    """The other direction: a family matching nothing describes a dead name.

    This is the half a corpus loses to a rename.  The glob keeps matching
    nothing and the entry keeps rendering into the glossary, so a reader is
    told about a parameter the package does not have.
    """
    from fnmatch import fnmatchcase

    paths = _vocabulary()
    dead = [g for g in PARAMETER_HELP
            if not any(fnmatchcase(p, g) for p in paths)]
    assert not dead, (
        f"family globs matching no live parameter path: {dead} — the "
        "parameter was renamed or removed, and its entry outlived it")


# --------------------------------------------------------------- the named arms
def test_every_peak_flag_has_an_entry():
    flags = set(get_args(PeakFlag))
    assert len(flags) >= 13, "PeakFlag import broke — the Literal moved?"
    assert set(PEAK_FLAG_HELP) == flags, (
        f"missing: {sorted(flags - set(PEAK_FLAG_HELP))}; "
        f"describing nothing: {sorted(set(PEAK_FLAG_HELP) - flags)}")


def test_every_peak_origin_has_an_entry():
    origins = set(get_args(ObservedPeak.model_fields["origin"].annotation))
    assert len(origins) == 3, "ObservedPeak.origin's Literal moved?"
    assert set(PEAK_ORIGIN_HELP) == origins, (
        f"missing: {sorted(origins - set(PEAK_ORIGIN_HELP))}; "
        f"describing nothing: {sorted(set(PEAK_ORIGIN_HELP) - origins)}")


#: The arms whose members are drawn as chips (WP-1209): every entry carries a
#: ``label``, which is what the chip says.  A chip reads at a glance or not at
#: all, so a label is one to three words and no two in an arm are the same.
LABELLED_ARMS = ("peak_flags", "peak_origins")


def test_every_chip_arm_entry_carries_a_short_unique_label():
    arms = _arms()
    for arm in LABELLED_ARMS:
        entries = arms[arm]
        missing = [k for k, e in entries.items() if not e.label]
        assert not missing, f"{arm}: no label on {missing}"
        long = [k for k, e in entries.items() if len(e.label.split()) > 3]
        assert not long, f"{arm}: labels over three words on {long}"
        labels = [e.label for e in entries.values()]
        assert len(set(labels)) == len(labels), (
            f"{arm}: two chips would read the same: {labels}")
    # …and nothing else has one: a label is a chip's, and an arm that grows
    # one has to be named here so its shortness is held too
    stray = [f"{arm}:{k}" for arm, entries in arms.items()
             if arm not in LABELLED_ARMS
             for k, e in entries.items() if e.label]
    assert not stray, f"labels outside the chip arms: {stray}"
    assert not [g for g, e in PARAMETER_HELP.items() if e.label]


def test_every_peak_diagnostic_code_has_an_entry():
    codes = _peak_diagnostic_codes()
    assert len(codes) >= 12, (
        f"only {len(codes)} PEAK_* codes collected — the AST walk broke, it "
        "does not mean the screens got quieter")
    assert set(PEAK_DIAGNOSTIC_HELP) == codes, (
        f"missing: {sorted(codes - set(PEAK_DIAGNOSTIC_HELP))}; "
        f"describing nothing: {sorted(set(PEAK_DIAGNOSTIC_HELP) - codes)}")


def test_every_stage_field_has_an_entry():
    fields = set(StageSpec.model_fields)
    assert set(STAGE_FIELD_HELP) == fields, (
        f"missing: {sorted(fields - set(STAGE_FIELD_HELP))}; "
        f"describing nothing: {sorted(set(STAGE_FIELD_HELP) - fields)}")


def test_every_reader_option_has_an_entry():
    assert set(READER_OPTION_HELP) == set(READER_OPTIONS), (
        f"missing: {sorted(set(READER_OPTIONS) - set(READER_OPTION_HELP))}; "
        f"describing nothing: "
        f"{sorted(set(READER_OPTION_HELP) - set(READER_OPTIONS))}")


def test_every_instrument_preset_field_has_an_entry():
    """A field the wizard offers with no description is a control with no label.

    ``INSTRUMENT_PRESETS`` is the constructors' own signature list, which is
    what ``gui/src/lib/wizard.ts`` is already held to across the language
    boundary; this holds the prose to the same set.
    """
    fields = _preset_fields()
    assert set(INSTRUMENT_FIELD_HELP) == fields, (
        f"missing: {sorted(fields - set(INSTRUMENT_FIELD_HELP))}; "
        f"describing nothing: {sorted(set(INSTRUMENT_FIELD_HELP) - fields)}")


def test_every_indexing_search_control_has_an_entry():
    """The form's own fields, held to the document that stores them (WP-1203).

    The prose here *is* the Peaks form's, moved out of
    ``gui/src/lib/controls.ts`` so the popover and the glossary read the same
    sentence.  ``controls.ts`` is already held to the same vocabulary from the
    other side by ``tests/test_search_controls.py``, so the form, the document
    and the corpus are three views of one field list.
    """
    fields = _search_fields()
    assert len(fields) == 21, f"the indexing control set moved: {sorted(fields)}"
    assert set(SEARCH_FIELD_HELP) == fields, (
        f"missing: {sorted(fields - set(SEARCH_FIELD_HELP))}; "
        f"describing nothing: {sorted(set(SEARCH_FIELD_HELP) - fields)}")


def test_search_control_defaults_are_the_schemas_own():
    """A search entry quotes its schema default, or says nothing.

    The hole WP-1202 left open and named: every other arm's ``default`` is
    prose restating a live value, so retuning one leaves a stale number in
    print.  These are plain pydantic fields with real defaults, so the crossing
    costs nothing.  JSON is the rendering, which is what makes ``null`` and
    ``true`` unambiguous where a Python repr would print ``None`` and ``True``
    at a reader who is looking at a browser.
    """
    top = IndexingControls.model_fields
    nested = top["search"].annotation.model_fields
    wrong = []
    for name, entry in SEARCH_FIELD_HELP.items():
        field = nested.get(name) or top[name]
        quoted = None if field.default is None else json.dumps(field.default)
        if entry.default != quoted:
            wrong.append((name, entry.default, quoted))
    assert not wrong, (
        "search entries whose default disagrees with the schema "
        f"(field, entry, schema): {wrong} — a retuned default leaves a stale "
        "number in the popover and in the glossary")


def test_the_plan_arm_is_plan_info_projected_not_restated():
    """``PLAN_INFO`` is the authority, so the arm must quote it byte for byte.

    A paraphrase here would be a second description of the same preset, kept in
    a second place, and the two would answer differently the first time one was
    edited.
    """
    plans = plan_help()
    assert set(plans) == set(PLAN_INFO)
    for name, info in PLAN_INFO.items():
        assert plans[name].title == info.title
        assert plans[name].description == info.description
        assert plans[name].typical == info.when_to_use


# ------------------------------------------------------ the schema-backed fields
#: The three places a table path is not the schema's own field path: the source
#: block's polarization flattens onto the instrument, a background coefficient
#: is indexed as ``cN`` — from ``coefficients`` or from the fixed member's
#: nested ``chebyshev.coefficients``, which is one design row either way — and
#: an ADP component loses its ``aniso`` block.  Named
#: rather than skipped, and :func:`_schema_parameters` asserts the map is
#: exhaustive, so a fourth renaming fails here instead of quietly dropping a
#: parameter out of the unit and default checks.  That guard has already earned
#: itself: the ADP rule was found by it, not by reading the table.
_PATH_RENAMES = {
    "instrument.source.polarization": "instrument.polarization",
    "instrument.background.air_scatter": "instrument.background.air",
}
_COEFFICIENT = re.compile(r"^instrument\.background\.(?:chebyshev\.)?coefficients\.(\d+)$")
_ANISO = re.compile(r"^(phases\.\d+\.atoms\.\d+)\.aniso\.(u\d\d)$")


def _schema_parameters() -> dict[str, Parameter]:
    """Every ``Parameter`` the models hold, keyed by its table path."""
    walked: dict[str, Parameter] = {}

    def walk(obj: BaseModel, prefix: str) -> None:
        for name in type(obj).model_fields:
            value = getattr(obj, name)
            path = f"{prefix}.{name}"
            if isinstance(value, Parameter):
                walked[path] = value
            elif isinstance(value, BaseModel):
                walk(value, path)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, Parameter):
                        walked[f"{path}.{i}"] = item
                    elif isinstance(item, BaseModel):
                        walk(item, f"{path}.{i}")

    for structure, instrument in _all_models():
        walk(instrument, "instrument")
        walk(structure.phases[0], "phases.0")

    out: dict[str, Parameter] = {}
    for path, param in walked.items():
        coefficient = _COEFFICIENT.match(path)
        if coefficient:
            path = f"instrument.background.c{coefficient.group(1)}"
        aniso = _ANISO.match(path)
        if aniso:
            path = f"{aniso.group(1)}.{aniso.group(2)}"
        out[_PATH_RENAMES.get(path, path)] = param

    live = set(_vocabulary())
    strayed = sorted(set(out) - live)
    assert not strayed, (
        f"schema field paths the parameter table does not produce: {strayed} — "
        "the table renamed a path and _PATH_RENAMES has not been told, so "
        "these parameters are silently outside the unit and default checks")
    return out


def test_units_are_the_schemas_own():
    """No entry may invent a unit, or disagree with the one the schema declares.

    The two spellings differ on purpose: a schema says ``deg^2`` because it is
    a machine-readable field, and a page says ``deg² 2θ``.  :data:`UNIT_DISPLAY`
    is the crossing, so a schema unit with no display spelling fails here rather
    than reaching a reader as ``A^-4``.
    """
    schema = _schema_parameters()
    unknown, wrong = [], []
    for path, param in schema.items():
        entry = rx.help_for(path)
        assert entry is not None, f"{path} has no entry"
        if param.unit is None:
            continue
        if param.unit not in UNIT_DISPLAY:
            unknown.append((path, param.unit))
            continue
        if entry.unit != UNIT_DISPLAY[param.unit]:
            wrong.append((path, entry.unit, UNIT_DISPLAY[param.unit]))
    assert not unknown, (
        f"schema units with no display spelling: {unknown} — add them to "
        "rietx.help.UNIT_DISPLAY")
    assert not wrong, (
        "entries whose unit disagrees with the schema "
        f"(path, entry, expected): {wrong}")

    reached = {p.unit for p in schema.values() if p.unit}
    assert set(UNIT_DISPLAY) == reached, (
        f"display spellings for units no schema declares: "
        f"{sorted(set(UNIT_DISPLAY) - reached)} — a table nothing reads is a "
        "spelling nobody has checked")


def test_defaults_are_the_schemas_own():
    """An entry's ``default`` is the schema's value, or absent.

    Absent is the honest state for a cell edge or a coordinate, which arrive
    with the structure and have no default to quote.  What this catches is the
    other case: a retuned schema default leaving a stale number in print, which
    is the failure the fenced constants in ``docs/manual/conf.py`` exist for.
    """
    wrong = []
    for path, param in _schema_parameters().items():
        entry = rx.help_for(path)
        if entry.default is None:
            continue
        try:
            quoted = float(entry.default)
        except ValueError:  # a prose default such as "null" or "[]"
            continue
        if quoted != pytest.approx(param.value, rel=0, abs=0):
            wrong.append((path, entry.default, param.value))
    assert not wrong, (
        "entries whose default disagrees with the schema "
        f"(path, entry, schema): {wrong}")


#: Thresholds a ``description`` quotes in words, each beside the live constant
#: the sentence is a copy of: ``(help path, constant, value the sentence must
#: spell, the spelling)``.  WP-1437 found the polarisation *formula* in this
#: corpus disagreeing with the code by up to 2x, undetected because prose has no
#: authority; a formula cannot be pinned this way and is a review rule in
#: ``help.py``'s module docstring instead, but a number can be and is.
#:
#: The converters are the units the sentence chose, not the code's: a crystallite
#: floor is stored in Å and read by people in nm.  Retuning a constant therefore
#: fails here until the sentence is rewritten, which is the whole point.
_QUOTED_THRESHOLDS = (
    ("phases.0.lor_size", "SIZE_CAP_MIN_SIZE_A", SIZE_CAP_MIN_SIZE_A / 10.0, "2 nm"),
    ("phases.0.gauss_size", "SIZE_CAP_MIN_SIZE_A", SIZE_CAP_MIN_SIZE_A / 10.0, "2 nm"),
    ("phases.0.lor_size", "SIZE_FLAG_SIZE_A", SIZE_FLAG_SIZE_A / 10.0, "5 nm"),
    ("phases.0.lor_strain", "STRAIN_FLAG_WIDTH", STRAIN_FLAG_WIDTH, "1.5 deg"),
)


def test_quoted_thresholds_are_the_codes_own():
    """A number a description states in words is the live constant's, in words.

    The fourth member of the ``*_are_the_…_own`` family, and the one that
    reaches into authored prose — named for the *code* rather than the schemas
    because a threshold is a module constant and not a field.
    ``unit`` and ``default`` are pinned because they *are* the
    schema's; these are pinned because a reader acts on them exactly as if they
    were, and nothing else would notice a retune.

    Two directions, as everywhere in this file.  The sentence must spell the
    constant, so retuning ``SIZE_CAP_MIN_SIZE_A`` to 30 Å fails until the
    description says 3 nm.  And the spelling must be *derived* from the constant
    rather than asserted flat, so a row whose converter is wrong fails here
    rather than certifying its own arithmetic.
    """
    stale = []
    for path, const_name, value, spelling in _QUOTED_THRESHOLDS:
        assert spelling == _spell(value, spelling), (
            f"{const_name} is {value:g} in the sentence's units, which spells "
            f"{_spell(value, spelling)!r}, but the row claims {spelling!r}")
        entry = rx.help_for(path)
        assert entry is not None, f"{path} has no entry"
        # Anchored, not ``in``: a sentence drifting from "5 nm" to "15 nm" still
        # *contains* "5 nm", so a bare substring test passes on exactly the
        # drift this guard exists to catch.
        if not re.search(rf"(?<![\d.]){re.escape(spelling)}", entry.description):
            stale.append((path, const_name, spelling))
    assert not stale, (
        "descriptions that no longer quote the constant they describe "
        f"(path, constant, expected spelling): {stale}. Either the sentence was "
        "rewritten away from the constant, or the constant was retuned and this "
        "row's converter followed it while the sentence did not")


def _spell(value: float, like: str) -> str:
    """``value`` in the spelling ``like`` uses, so a row cannot assert itself."""
    return f"{value:g} {like.split(' ', 1)[1]}"


def test_a_parameter_with_no_default_says_so_rather_than_guessing():
    """A cell edge and a coordinate carry ``default=None``, not a made-up value.

    The WP-1076 shape: a defaulted number would read as an answer about a
    parameter that has none.
    """
    for path in ("phases.0.cell.a", "phases.0.cell.beta", "phases.0.atoms.0.x"):
        assert rx.help_for(path).default is None, path


# ---------------------------------------------------------------- the row's key
def test_every_row_of_a_real_model_carries_its_family_key():
    """``ParameterRow.help_key`` is filled by ``Refinement.parameters``.

    Filled there rather than by the GUI, so ``None`` means "no family claims
    this path" for every caller.  A row whose key is missing would report the
    same ``None`` and mean something else entirely.
    """
    for structure, instrument in _all_models():
        rows = rx.Refinement(structure, instrument).parameters()
        assert rows
        missing = [r.path for r in rows if r.help_key is None]
        assert not missing, f"rows with no help_key: {missing}"
        for row in rows:
            assert row.help_key == help_key_for(row.path)
            assert row.help_key in PARAMETER_HELP


# ----------------------------------------------------------------- the registry
def test_the_registry_is_json_and_carries_every_arm():
    registry = help_registry()
    assert set(registry) == {"parameters", "peak_flags", "peak_diagnostics",
                             "peak_origins", "stage_fields", "reader_options",
                             "instrument_fields", "search_fields", "plans"}
    payload = json.dumps(registry)  # raises on anything unserialisable
    assert len(payload) > 10_000

    reached = {g for entry in registry["parameters"] for g in entry["paths"]}
    assert reached == set(PARAMETER_HELP), (
        "the parameters arm lost a glob in the grouping — a help_key would "
        "then index nothing")
    for entry in registry["parameters"]:
        assert entry["title"] and entry["description"]
    for name, entry in registry["plans"].items():
        assert entry["modes"] == list(PLAN_INFO[name].modes)


def test_the_help_route_serves_the_registry_and_the_manual_s_address():
    """The route is the registry plus the one thing an ``anchor`` needs (WP-1203).

    An anchor is ``page.html#heading-id`` relative to the manual root, so a
    client can only build a link if it is also told where the manual lives.
    ``docs_url`` rides beside the arms rather than in one because it is not a
    name anything looks up, and it is served rather than spelled in TypeScript
    for the reason ``_about`` exists at all.
    """
    from rietx.gui.server import ROUTES
    from rietx.gui.session import GuiSession

    assert ("GET", "/api/help") in ROUTES
    served = GuiSession().help()
    assert {k: v for k, v in served.items() if k != "docs_url"} == help_registry()
    assert served["docs_url"] == _about.DOCS_URL


# -------------------------------------------------------------------- the prose
def test_every_parameter_family_carries_a_range_and_a_chapter():
    """A parameter entry must have both ``typical`` and ``anchor``; an arm need not.

    All 38 families already do, and this is the audit turning that accident
    into a checked claim: a range to compare a refined number against, and the
    chapter with the equation, are the two things a parameter entry is *for*.
    ``None`` on either would read as "nothing covers this" about a family
    nobody had finished — the defaulted-answer shape again.

    The named arms are exempt by nature, not by oversight: a peak flag has no
    typical range, and seven of the thirteen name a state no Part 2 chapter
    has an equation for.
    """
    thin = sorted({g for g, e in PARAMETER_HELP.items()
                   if e.typical is None or e.anchor is None})
    assert not thin, (
        f"parameter families with no typical range or no manual anchor: {thin}")


def test_every_entry_has_a_title_and_a_description():
    thin = [name for name, e in _every_entry()
            if not e.title or len(e.description.split()) < 8]
    assert not thin, (
        f"entries with no title or a description under eight words: {thin} — "
        "a stub reads as an answer the same way a defaulted field does")


@pytest.mark.xdist_group("manual-build")
def test_every_anchor_resolves_in_the_built_manual(built_manual):  # noqa: F811
    """An ``anchor`` is the page and heading the popover links to, so both must exist.

    Checked against the **built** HTML rather than the Markdown sources, for
    the reason ``test_no_unrendered_math_survives_the_build`` is: a heading id
    exists in the source whether or not the page renders, and a slug is
    generated rather than written, so only the output says what a link will
    find.  This is the dead-link guard WP-1017 planned, arriving early because
    the corpus is the first thing in the tree that links into Part 2 by id.

    Since WP-1203 the anchor carries its page (``page.html#id``), which is what
    a rendered link needs, so this checks the pair: an id found on some *other*
    page used to pass, and would now send a reader to a page that does not
    carry the heading.
    """
    out, result = built_manual
    assert result.returncode == 0, "manual did not build — see test_manual.py"
    ids: dict[str, set[str]] = {}
    for page in out.rglob("*.html"):
        rel = page.relative_to(out).as_posix()
        ids[rel] = set(re.findall(r'id="([^"]+)"', page.read_text(encoding="utf-8")))
    assert sum(len(v) for v in ids.values()) > 100, (
        "no ids found — did the build produce HTML?")

    shapeless = sorted({(name, e.anchor) for name, e in _every_entry()
                        if e.anchor and e.anchor.count("#") != 1})
    assert not shapeless, (
        f"anchors that are not `page.html#heading-id`: {shapeless} — a bare id "
        "names no page, so no link can be built from it")

    broken = sorted({(name, e.anchor) for name, e in _every_entry() if e.anchor
                     and e.anchor.split("#")[1] not in ids.get(e.anchor.split("#")[0], ())})
    assert not broken, (
        f"entries whose anchor is not a heading on that page of the built "
        f"manual: {broken} — the heading was renamed, the slug moved with it, "
        "or the chapter did")


def test_entry_is_frozen_so_a_consumer_cannot_edit_the_corpus():
    entry = rx.help_for("phases.0.scale")
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.title = "something else"  # type: ignore[misc]
