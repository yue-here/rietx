import contextlib
import copy
import dataclasses
import inspect
import json
import math
import pickle
import re
import types
import typing

import pytest
from pydantic import ValidationError

import rietx as rx

# Force every module that defines a Base subclass to be imported, so
# ``Base.__subclasses__()`` below sees the whole family regardless of what
# else this file happens to import — this test must find the same set
# whether it runs alone or as part of the suite.
import rietx.report.schemas  # noqa: F401
import rietx.schemas.history  # noqa: F401
import rietx.schemas.indexing  # noqa: F401
import rietx.schemas.instrument  # noqa: F401
import rietx.schemas.params  # noqa: F401
import rietx.schemas.pattern  # noqa: F401
import rietx.schemas.plan  # noqa: F401
import rietx.schemas.project  # noqa: F401
import rietx.schemas.results  # noqa: F401
import rietx.schemas.sequential  # noqa: F401
import rietx.schemas.structure  # noqa: F401
import rietx.schemas.suggest  # noqa: F401
from rietx import Instrument, Parameter, PatternData, Structure
from rietx.schemas import Atom, Cell, Phase
from rietx.schemas.common import Base


def make_lab6() -> Structure:
    return Structure(phases=[Phase(
        name="LaB6",
        space_group="P m -3 m",
        cell=Cell.cubic(4.1566, vary=True),
        atoms=[
            Atom(label="La", species="La", x=Parameter(value=0.0),
                 y=Parameter(value=0.0), z=Parameter(value=0.0)),
            Atom(label="B", species="B", x=Parameter(value=0.1993),
                 y=Parameter(value=0.5), z=Parameter(value=0.5)),
        ],
    )])


def test_parameter_bounds_validated():
    with pytest.raises(ValidationError):
        Parameter(value=2.0, min=0.0, max=1.0)
    with pytest.raises(ValidationError):
        Parameter(value=0.5, min=1.0, max=0.0)


def test_parameter_expr_reserved():
    with pytest.raises(ValidationError):
        Parameter(value=1.0, expr="2*a")


def test_unknown_field_rejected():
    with pytest.raises(ValidationError) as err:
        Parameter(value=1.0, vry=True)  # typo
    assert "vry" in str(err.value)


def _atom(**kw) -> Atom:
    """An otherwise-minimal Atom, so each bound-inheritance test only names
    the field it is exercising."""
    kw.setdefault("label", "X")
    kw.setdefault("species", "H")
    kw.setdefault("x", Parameter(value=0.0))
    kw.setdefault("y", Parameter(value=0.0))
    kw.setdefault("z", Parameter(value=0.0))
    return Atom(**kw)


def test_atom_bare_biso_parameter_inherits_declared_bounds():
    """Issue #204: a caller's own bare ``Parameter`` for ``biso`` — the
    natural way to set a starting value or hold one — used to silently lose
    the field's declared (0, 25, "A^2") range to Parameter's own bare
    defaults. Fails on the parent commit (a4eec1db), where ``a.biso.min``
    reads ``-inf``."""
    a = _atom(biso=Parameter(value=1.0, vary=False))
    assert (a.biso.min, a.biso.max, a.biso.unit) == (0.0, 25.0, "A^2")


def test_atom_bare_occ_parameter_inherits_declared_bounds():
    """Same mechanism as biso, on occ's declared (0, 1.5) range. Fails on
    the parent commit, where ``a.occ.max`` reads ``inf``."""
    a = _atom(occ=Parameter(value=0.8))
    assert (a.occ.min, a.occ.max) == (0.0, 1.5)


def test_atom_omitted_biso_still_gets_declared_bounds():
    """Not a regression by itself (the parent commit already got this right
    for the omitted-field case), but pinned here so the inheritance path and
    the omitted-field path are asserted to agree on the same numbers."""
    a = _atom()
    assert (a.biso.min, a.biso.max, a.biso.unit) == (0.0, 25.0, "A^2")


def test_atom_xyz_have_no_declared_bounds_to_lose():
    """x/y/z are required with no default_factory, so the inheritance loop
    (which only fires for fields carrying one) never touches them — pinned
    per the issue's own claim that they "lose nothing"."""
    a = _atom()
    assert (a.x.min, a.x.max) == (float("-inf"), float("inf"))


def test_atom_biso_out_of_declared_bounds_now_raises():
    """The issue's measured consequence, reproduced directly: a bare
    ``Parameter(value=-165.0)`` for biso used to be accepted silently
    (refined Biso of -165 A^2 at unchanged Rwp). With the declared bound
    inherited, -165 lies outside [0, 25] and construction raises. Fails on
    the parent commit, where this construction succeeds."""
    with pytest.raises(ValidationError, match=r"outside bounds"):
        _atom(biso=Parameter(value=-165.0, vary=True))


def test_atom_explicit_parameter_bound_is_not_overwritten():
    """An explicit bound must win over the declared default — the whole
    point of inheriting only what model_fields_set says was omitted, rather
    than always overwriting from the field's default_factory."""
    a = _atom(biso=Parameter(value=1.0, min=-5.0, max=5.0, unit="foo"))
    assert (a.biso.min, a.biso.max, a.biso.unit) == (-5.0, 5.0, "foo")


def test_the_always_overwrite_design_would_clobber_an_explicit_bound():
    """Guards against over-firing. A parent-commit check can't demonstrate
    why the model_fields_set discriminator matters — the parent applies no
    inheritance at all, so it would pass a "the explicit bound survived"
    comparison trivially, for the wrong reason. Demonstrate instead against
    the design this PR rejected: unconditionally overwrite min/max/unit from
    the field's declared default, without consulting model_fields_set. Run
    on the very Parameter the test above proves the real validator leaves
    alone, so the two tests are directly comparable."""
    a = _atom(biso=Parameter(value=1.0, min=-5.0, max=5.0, unit="foo"))
    default = Atom.model_fields["biso"].default_factory()
    rejected = a.biso.model_copy()
    for attr in ("min", "max", "unit"):  # the rejected design has no gate here
        setattr(rejected, attr, getattr(default, attr))
    assert (rejected.min, rejected.max, rejected.unit) == (0.0, 25.0, "A^2")
    assert (rejected.min, rejected.max, rejected.unit) != (a.biso.min, a.biso.max, a.biso.unit)


def test_every_bounds_carrying_atom_field_is_inherited():
    """The generalisation guard the issue asked for most: rather than
    trusting that ``occ`` and ``biso`` are the only two fields shaped this
    way, discover every ``Parameter`` field on ``Atom`` whose
    ``default_factory`` declares a min/max/unit beyond Parameter's own bare
    defaults, and check each one inherits. A field added later the same way
    is exercised here automatically, with no edit to this test; if
    ``Atom._inherit_declared_bounds`` ever regresses to naming fields
    explicitly and misses one, this fails. Fails on the parent commit for
    both fields it currently finds (occ, biso)."""
    bare = Parameter(value=0.0)
    checked = []
    for name, info in Atom.model_fields.items():
        if info.annotation is not Parameter or info.default_factory is None:
            continue
        default = info.default_factory()
        declared = {attr: getattr(default, attr) for attr in ("min", "max", "unit")
                    if getattr(default, attr) != getattr(bare, attr)}
        if not declared:
            continue
        checked.append(name)
        got = getattr(_atom(**{name: Parameter(value=default.value)}), name)
        for attr, want in declared.items():
            assert getattr(got, attr) == want, (name, attr, got)
    # Guards against a no-op loop (e.g. the annotation check silently
    # matching nothing) rather than pinning the exact set, so a future field
    # shaped like occ/biso is exercised above without needing this line
    # touched.
    assert {"occ", "biso"} <= set(checked)


def test_atom_construction_does_not_mutate_the_callers_parameter():
    """Review item 1 on PR #206: an earlier ``mode="after"`` version of this
    validator filled the missing attributes by ``getattr``/``setattr`` on
    ``self``'s own field — but pydantic stores a passed-in ``Parameter`` by
    reference, so that object *was* the caller's, and ``Base``'s
    ``validate_assignment=True`` meant the ``setattr`` calls both wrote to it
    and added the names to *its own* ``model_fields_set``. Fixed by filling
    the raw input in a ``mode="before"`` validator, before any ``Parameter``
    exists to mutate. Pin the caller's object exactly as handed in."""
    p = Parameter(value=1.0)
    before = (p.min, p.max, p.unit, frozenset(p.model_fields_set))
    _atom(biso=p)
    after = (p.min, p.max, p.unit, frozenset(p.model_fields_set))
    assert after == before


def test_atom_reusing_one_parameter_for_occ_and_biso_gets_each_fields_own_range():
    """The mutation in the previous test's defect wasn't only visible on the
    caller's own object — it leaked *across fields* the moment the same
    ``Parameter`` was reused: filling ``biso``'s bounds onto the shared
    object also added them to its ``model_fields_set``, so a second ``Atom``
    built from the same object for ``occ`` saw them as "already present" and
    inherited nothing of its own. An occupancy silently carrying Biso's
    range *and unit* is the defect class PR #206 exists to close, reopened
    through this door. Each field must get its own declared range from one
    shared, untouched source object."""
    p = Parameter(value=1.0)
    _atom(biso=p)
    a = _atom(occ=p)
    assert (a.occ.min, a.occ.max, a.occ.unit) == (0.0, 1.5, None)


def test_schema_version_bumped_and_pre_fix_documents_still_load():
    """Review item 2 on PR #206: ``SCHEMA_VERSION`` must move, since the set
    of legal ``Atom`` constructions shrank — the constant's own changelog
    names this exact bump. Also pins the claim the comment makes and issue
    #209 depends on: a document written *before* this fix, carrying the
    unbounded ``biso`` the bug allowed (explicit ``-Infinity``/``Infinity``,
    the shape ``model_dump_json`` actually wrote), still loads unaffected —
    the break is to construction, not to persisted documents, because
    ``model_fields_set``/dict-keys are already complete on load and nothing
    is inherited.

    The version is pinned against the changelog block rather than a
    literal.  A literal ``== "0.16"`` goes red on the next WP that bumps
    the constant, under a name whose subject is ``Atom`` bounds, and reads
    as though this fix broke (review round 4 on PR #206).  What this test
    is entitled to assert is that the bump for *this* change is recorded
    and has been reached — not that nothing has happened since."""
    import rietx.schemas.common as common
    from rietx.schemas.common import SCHEMA_VERSION

    entry = re.search(
        r"^#: (\d+\.\d+) \u2192 (\d+\.\d+) \(issue #204\)",
        inspect.getsource(common),
        re.M,
    )
    assert entry is not None, (
        "the SCHEMA_VERSION changelog no longer records the issue #204 "
        "bump; this test's whole claim is that the shrunken set of legal "
        "Atom constructions is a documented version change")

    def as_key(v):
        return tuple(int(part) for part in v.split("."))

    assert as_key(entry.group(2)) > as_key(entry.group(1))
    assert as_key(SCHEMA_VERSION) >= as_key(entry.group(2))

    pre_fix_doc = (
        '{"label": "Fe1", "species": "Fe",'
        ' "x": {"value": 0.0}, "y": {"value": 0.0}, "z": {"value": 0.0},'
        ' "occ": {"value": 1.0, "min": 0.0, "max": 1.5},'
        ' "biso": {"value": -165.0, "min": "-Infinity", "max": "Infinity",'
        ' "unit": null}}'
    )
    a = Atom.model_validate_json(pre_fix_doc)
    assert (a.biso.value, a.biso.min, a.biso.max, a.biso.unit) == (
        -165.0, float("-inf"), float("inf"), None)


def test_structure_json_round_trip():
    s = make_lab6()
    s2 = Structure.model_validate_json(s.model_dump_json())
    assert s2 == s


def test_instrument_json_round_trip():
    ins = Instrument.debye_scherrer(wavelength=0.4139)
    ins2 = Instrument.model_validate_json(ins.model_dump_json())
    assert ins2 == ins
    assert math.isclose(ins2.source.primary_wavelength, 0.4139)


def test_pattern_validation():
    with pytest.raises(ValidationError):
        PatternData(two_theta=[1.0, 0.5], intensity=[1.0, 2.0])  # not increasing
    with pytest.raises(ValidationError):
        PatternData(two_theta=[1.0, 2.0], intensity=[1.0])  # length mismatch
    p = PatternData(two_theta=[1.0, 2.0, 3.0], intensity=[4.0, 9.0, 16.0])
    assert p.sig().tolist() == [2.0, 3.0, 4.0]  # Poisson fallback


# ------------------------------------------------------- the one plan schema
def test_stage_spec_mirrors_every_stage_field():
    """StageSpec must carry every field of the dataclass it mirrors.

    The mirror lost data before WP-1004: ``strain_seed`` existed on ``Stage``
    and on the agent surface's copy of this schema but not on the history one,
    so a Stephens stage round-tripped through a history tree with its seed
    reset to 0.  A field-set assertion is the guard that makes the next added
    ``Stage`` field fail loudly instead of silently failing to serialize.
    """
    import dataclasses

    from rietx.schemas.plan import StageSpec

    assert set(StageSpec.model_fields) == {f.name for f in dataclasses.fields(rx.Stage)}


def test_stage_spec_round_trips_strain_seed():
    from rietx.schemas.plan import StageSpec

    stage = rx.Stage("sample_broadening", ["phases.*.microstrain.dof.*"],
                     seed=1e-3, strain_seed=1000.0)
    back = StageSpec.model_validate_json(
        StageSpec.from_stage(stage).model_dump_json()).to_stage()
    assert back == stage


def test_the_mirror_is_crossed_in_both_directions():
    """A plan and its mirror are interchangeable at every surface (WP-1110 item 15).

    ``PLAN_PRESETS`` hands back the dataclass; a request, a project file and a
    history header hold the pydantic mirror.  Before this the crossing existed
    nowhere, so a caller had to know which of two same-shaped types each
    surface wanted — two agents on the trigger dataset took a preset, were
    answered ``INVALID_REQUEST``, and rebuilt it field by field.
    """
    from rietx.schemas.plan import PlanSpec, StageSpec
    from rietx.strategy.staged import resolve_plan

    plan = rx.PLAN_PRESETS["mccusker_default"]()
    spec = PlanSpec.from_plan(plan)

    # inbound: the dataclass validates as its mirror, at both ranks
    assert PlanSpec.model_validate(plan) == spec
    assert StageSpec.model_validate(plan.stages[0]) == spec.stages[0]
    # outbound: the mirror resolves to the dataclass
    assert resolve_plan(spec, "rietveld") == plan
    # and a name still resolves through the mode mapping it always did
    assert resolve_plan("mccusker_default", "lebail") == rx.RefinementPlan.profile_only()


def test_the_crossing_is_by_type_not_by_shape():
    """`.stages` is not evidence: the two types share every field name.

    Which is exactly what let a ``PlanSpec`` run through ``fit(plan=...)``
    undeclared before WP-1110 — it fitted, bit-identically, because a plan is
    only ever read.  A duck-typed crossing would certify that accident, so
    both validators test ``isinstance`` against the real class.
    """
    from rietx.schemas.plan import PlanSpec

    assert {f.name for f in dataclasses.fields(rx.RefinementPlan)} == set(
        PlanSpec.model_fields)

    class LooksLikeAPlan:
        stages = []
        correlation_guard = 0.98

    with pytest.raises(ValidationError):
        PlanSpec.model_validate(LooksLikeAPlan())


def test_a_preset_is_the_builder_and_says_so():
    """``PLAN_PRESETS[name]`` builds a plan; asking it for one names the call.

    The registry stores builders on purpose — a plan is a mutable dataclass, so
    a shared instance would carry one caller's edit to the next — and the cost
    was ``'function' object has no attribute 'stages'`` (WP-1110 item 4), which
    names neither the registry nor the call.
    """
    factory = rx.PLAN_PRESETS["mccusker_default"]

    with pytest.raises(AttributeError, match=r"PLAN_PRESETS\['mccusker_default'\]\(\)"):
        factory.stages
    assert factory() is not factory(), "a preset must not hand out a shared plan"

    # every preset, not one: the wrapper is what stands between the registry
    # and the plan that every fit in the package runs, so the claim it builds
    # exactly what the classmethod builds is checked across the whole registry
    for name in rx.PLAN_PRESETS:
        assert rx.PLAN_PRESETS[name]() == getattr(rx.RefinementPlan, name)()
    # ``functools.update_wrapper``: an agent reading help() must reach the
    # builder, not the wrapper — the round measured one leave for the source
    # over exactly this.
    assert factory.__name__ == "mccusker_default"
    assert inspect.getdoc(factory) == inspect.getdoc(rx.RefinementPlan.mccusker_default)


def test_a_wrong_stage_or_plan_field_gets_the_closest_match():
    """``Stage``/``RefinementPlan`` are dataclasses, not ``Base`` subclasses,
    so they carry their own hand-written version of the same idea (WP-1302).

    ``free`` is a real historical miss (agents reading a *declared* stage for
    what it *did*), and it is nobody's typo of a field name, so it exercises
    the field-listing branch plus the one named cross-class hint.
    """
    stage = rx.Stage("cell", ["phases.*.cell.*"])
    with pytest.raises(AttributeError, match=r"its fields are .*'turn_on'.*"
                                               r"what a stage freed is StageResult\.freed"):
        stage.free
    with pytest.raises(AttributeError, match=r"did you mean 'turn_on'"):
        stage.turnon  # a close typo, not the historical miss above

    plan = rx.RefinementPlan.mccusker_default()
    with pytest.raises(AttributeError, match=r"did you mean 'stages'"):
        plan.stagess


def test_every_public_schema_class_is_a_top_level_export():
    """WP-1302: no `Source`/`EmissionLine`/`BackgroundChebyshev`-shaped gap.

    Derived, not typed — walks every ``rietx.schemas`` submodule the same way
    ``rietx/__init__.py`` does, rather than re-listing the classes by hand,
    so a schema added tomorrow is covered the day it lands.
    """
    import pkgutil

    schema_names = set()
    for info in pkgutil.iter_modules(rx.schemas.__path__):
        module = __import__(f"rietx.schemas.{info.name}", fromlist=["_"])
        for name, obj in vars(module).items():
            if (not name.startswith("_") and inspect.isclass(obj)
                    and obj.__module__ == module.__name__ and issubclass(obj, Base)):
                schema_names.add(name)

    # Base itself is excluded from the public surface (tests/api_surface.py)
    # rather than from this export list — see that file for the reason.
    missing = {n for n in schema_names if n != "Base"} - set(rx.__all__)
    assert not missing


def test_package_getattr_lazily_imports_a_submodule():
    """``rx.viz`` works without an explicit ``import rietx.viz`` first
    (WP-1302) — a real historical miss (`module 'rietx' has no attribute
    'viz'`), fixed rather than merely explained.
    """
    import sys
    import types

    sys.modules.pop("rietx.viz", None)
    if hasattr(rx, "viz"):
        del rx.__dict__["viz"]

    assert isinstance(rx.viz, types.ModuleType)
    assert rx.viz is sys.modules["rietx.viz"]


def test_package_getattr_names_where_a_miss_actually_lives():
    with pytest.raises(AttributeError, match=r"did you mean 'Instrument'"):
        rx.Insrument
    with pytest.raises(AttributeError, match=r"io\.readers\.PATTERN_FORMATS"):
        rx.identify_format
    with pytest.raises(AttributeError, match=r"no attribute 'not_a_real_export'"):
        rx.not_a_real_export


def test_package_getattr_reports_a_broken_submodule_as_attributeerror():
    """A submodule that fails on its *own* missing dependency (``viz``/``gui``
    pull in matplotlib/plotly, absent on a minimal install) must raise
    ``AttributeError``, not let the underlying ``ModuleNotFoundError``
    escape — only ``AttributeError`` is what ``hasattr``/``getattr(default=)``
    catch, so a caller checking "is this built with plotting support" must
    get ``False``, not a crash (found by code review).
    """
    import importlib
    import sys
    from unittest.mock import patch

    sys.modules.pop("rietx.viz", None)
    if hasattr(rx, "viz"):
        del rx.__dict__["viz"]

    real_import = importlib.import_module

    def fake_import(name, *a, **kw):
        if name == "rietx.viz":
            raise ModuleNotFoundError("No module named 'matplotlib'",
                                      name="matplotlib")
        return real_import(name, *a, **kw)

    with patch("rietx.importlib.import_module", side_effect=fake_import):
        with pytest.raises(AttributeError, match=r"rietx\.viz exists but "
                           r"failed to import.*matplotlib") as excinfo:
            rx.viz
        assert isinstance(excinfo.value.__cause__, ModuleNotFoundError)
        assert hasattr(rx, "viz") is False


@pytest.mark.parametrize("obj, mirror", [
    (rx.RefinementPlan.mccusker_default(), "PlanSpec.from_plan"),
    (rx.Stage("cell", ["phases.*.cell.*"]), "StageSpec.from_stage"),
])
def test_asking_a_plan_dataclass_for_pydantic_names_the_mirror(obj, mirror):
    """These two are the package's only schema-shaped non-pydantic objects.

    A plan is a record of fields sitting beside a ``PlanSpec`` that mirrors it
    one for one, unlike ``Refinement`` or ``Project``, which are plainly
    machines.  So ``.model_dump()`` is the natural next keystroke, and the bare
    ``'Stage' object has no attribute 'model_dump'`` says nothing about where
    serialization lives.  An error message is the documentation an agent reads.
    """
    with pytest.raises(AttributeError, match=mirror):
        obj.model_dump()
    # everything else still raises the ordinary way, so hasattr and copy are
    # unchanged
    with pytest.raises(AttributeError):
        obj.no_such_attribute
    assert copy.deepcopy(obj) == obj


def _bare_result():
    """A RefinementResult with nothing but its required fields."""
    from rietx.schemas.common import Provenance
    from rietx.schemas.results import RefinementResult, Statistics

    return RefinementResult(
        status="converged", mode="rietveld", parameters=[],
        statistics=Statistics(rwp=0.1, rp=0.08, rexp=0.05, chi2=4.0, gof=2.0,
                              n_points=100, n_free_parameters=5),
        provenance=Provenance(package_version="0.0.0+test"))


@pytest.mark.parametrize("name, path", [
    ("rwp", "result.statistics.rwp"),
    ("gof", "result.statistics.gof"),
    ("chi2", "result.statistics.chi2"),
    ("esd_inflation", "result.statistics.esd_inflation"),
    ("backend", "result.provenance.backend"),
    ("mu_r", "result.absorption.mu_r"),
    ("soft_modes", "result.identifiability.soft_modes"),
])
def test_a_nested_number_is_answered_with_its_path(name, path):
    """``result.rwp`` is WP-1110's most expensive miss, because of *when*.

    The ``AttributeError`` arrived after a 105 s refinement had completed and
    took it with it, and the bare ``'RefinementResult' object has no attribute
    'rwp'`` does not say where the number is.  Parametrised past ``rwp``
    because the message is **derived** from the live annotations, not from a
    list of misses already seen: the optional blocks are searched too, so a
    field added to one of them is covered on the day it lands.
    """
    with pytest.raises(AttributeError, match=re.escape(path)):
        getattr(_bare_result(), name)


def test_the_hint_is_a_pointer_and_not_an_alias():
    """Nothing new is reachable, and nothing new is frozen.

    Forwarding the value would give two spellings of one fact and promote a
    dozen nested names to public API under the v1.0 freeze.  So the top level
    still has no ``rwp``: ``hasattr`` is False, ``model_fields`` is unchanged,
    and the JSON is unchanged.
    """
    result = _bare_result()

    assert not hasattr(result, "rwp")
    assert "rwp" not in type(result).model_fields
    assert "rwp" not in json.loads(result.model_dump_json())
    assert result.statistics.rwp == 0.1

    # a name that is nowhere still raises the ordinary way, and the machinery
    # pydantic and the stdlib probe with is untouched
    with pytest.raises(AttributeError, match="no attribute 'not_a_field'"):
        result.not_a_field
    assert copy.deepcopy(result) == result
    assert pickle.loads(pickle.dumps(result)) == result
    assert type(result).model_validate_json(result.model_dump_json()) == result


def _all_base_subclasses() -> list[type]:
    """Every ``Base`` subclass currently defined, recursively.

    Depends on the explicit import block above: a subclass ``__subclasses__``
    has not seen does not exist yet, so this walk is only as complete as that
    list.
    """
    seen: set[type] = set()
    frontier = [Base]
    while frontier:
        for sub in frontier.pop().__subclasses__():
            if sub not in seen:
                seen.add(sub)
                frontier.append(sub)
    return sorted(seen, key=lambda c: f"{c.__module__}.{c.__qualname__}")


def _dummy_scalar(annotation: object, depth: int) -> object:
    """A type-shaped placeholder, never a validated value.

    Only used for *required* fields, so a model-level validator reading a
    sibling mid-``validate_assignment`` finds something of the right shape
    (a nonzero tuple, a populated nested model) instead of the "declared but
    never given a value" case one rank up — that case is real and tested on
    its own; here it would just be noise from this helper's own construction.
    Business-rule rejection of the placeholder (a ``ValidationError``) is the
    caller's to accept, not this function's to avoid.
    """
    if depth > 8:
        return None
    origin = typing.get_origin(annotation)
    if origin is typing.Literal:
        return typing.get_args(annotation)[0]
    if origin in (types.UnionType, typing.Union):
        args = [a for a in typing.get_args(annotation) if a is not type(None)]
        return _dummy_scalar(args[0], depth + 1) if args else None
    if origin is list:
        args = typing.get_args(annotation) or (typing.Any,)
        return [_dummy_scalar(args[0], depth + 1)]
    if origin is dict:
        args = typing.get_args(annotation)
        if len(args) == 2:
            return {_dummy_scalar(args[0], depth + 1): _dummy_scalar(args[1], depth + 1)}
        return {}
    if origin is tuple:
        args = typing.get_args(annotation)
        if len(args) == 2 and args[1] is Ellipsis:
            return ()
        return tuple(_dummy_scalar(a, depth + 1) for a in args)
    if isinstance(annotation, type) and issubclass(annotation, Base):
        return _dummy_instance(annotation, depth + 1)
    return {bool: False, int: 1, float: 1.0, str: "x"}.get(annotation)


def _dummy_instance(cls: type, depth: int = 0):
    """``model_construct`` with every *required* field filled, recursively.

    Optional fields are left to ``model_construct``'s own default/
    ``default_factory`` handling — only a required field can leave a model
    validator looking at something unset.
    """
    required = {f: _dummy_scalar(info.annotation, depth)
                for f, info in cls.model_fields.items() if info.is_required()}
    return cls.model_construct(**required)


@pytest.mark.parametrize(
    "cls", _all_base_subclasses(), ids=lambda c: f"{c.__module__}.{c.__qualname__}")
def test_every_base_subclass_survives_the_new_getattr(cls):
    """``Base.__getattr__`` must not break pydantic's own machinery.

    Required fields carry a type-shaped dummy (see ``_dummy_instance``) so a
    model validator touching a sibling field during ``validate_assignment``
    finds a value rather than exercising the *other*, already-tested "declared
    but never given a value" branch; a business-rule rejection of that dummy
    (``ValidationError``) is not this test's concern, only an ``AttributeError``
    escaping from ``Base.__getattr__`` itself is.
    """
    obj = _dummy_instance(cls)
    assert copy.deepcopy(obj) == obj
    assert pickle.loads(pickle.dumps(obj)) == obj
    assert obj.model_copy() == obj
    obj.model_dump(mode="json")
    defaulted = next(
        (f for f, info in cls.model_fields.items() if not info.is_required()), None)
    if defaulted is not None:
        with contextlib.suppress(ValidationError):
            setattr(obj, defaulted, getattr(obj, defaulted))  # validate_assignment path


def test_plan_spec_is_one_class_everywhere():
    """History must not re-acquire a private copy.

    The compat re-exports went pre-freeze (WP-1003): ``StageSpec`` is spelled
    only ``schemas.plan.StageSpec``, and its *absence* from the old home is
    the guard — a re-acquired private copy would make the attribute exist.
    ``PlanSpec`` stays imported there because it is used, and it must be the
    one class.  The agent envelope was the second consumer this test watched
    until WP-1303 deleted it; the rule is unchanged, it just has one importer
    fewer to police.
    """
    from rietx.schemas import history, plan

    assert history.PlanSpec is plan.PlanSpec
    assert not hasattr(history, "StageSpec")


def test_plan_spec_reads_a_pre_v1_history_header():
    """A tree written before ``strain_seed`` existed still validates.

    Vendored header line from a v0.6 history JSONL (schema_version 0.1), whose
    stage specs have no ``strain_seed`` key at all.
    """
    from rietx.schemas.history import HistoryRecord

    line = (
        '{"record":"header","header":{"tree_id":"t0","created_utc":'
        '"2026-07-28T10:00:00Z","data_fingerprint":"abc","data_source":"",'
        '"n_points":100,"plan":{"stages":[{"name":"scale_bkg","turn_on":'
        '["phases.*.scale"],"max_iter":100,"lebail_cycles":3,"seed":0.0},'
        '{"name":"cell","turn_on":["phases.*.cell.*"],"max_iter":100,'
        '"lebail_cycles":3,"seed":0.0}],"correlation_guard":0.98},'
        '"package_version":"0.6.0.dev0","schema_version":"0.1"}}'
    )
    rec = HistoryRecord.model_validate_json(line)
    assert rec.header is not None
    assert [s.name for s in rec.header.plan.stages] == ["scale_bkg", "cell"]
    assert all(s.strain_seed == 0.0 for s in rec.header.plan.stages)


# -- WP-1206: the Le Bail scaffold, shared by Adopt and a typed cell -------


def test_lebail_scaffold_carries_a_cell_and_one_inert_atom():
    """The scaffold is the cell plus the atom ``Phase._nonempty`` demands.

    The atom is what makes a structure-free phase representable at all; that it
    contributes nothing is a *mode* property (lebail/pawley force-fix every
    ``.atoms.`` path), which is why the check here is that the atom exists and
    carries a species with a form factor — not that it is invisible.
    """
    from rietx.schemas.structure import DUMMY_SPECIES, lebail_scaffold

    structure = lebail_scaffold("R -3 c", (4.7607, 4.7607, 12.9947, 90, 90, 120),
                                name="corundum")
    phase = structure.phases[0]
    assert phase.name == "corundum"
    assert phase.space_group == "R -3 c"
    assert [phase.cell.a.value, phase.cell.c.value] == [4.7607, 12.9947]
    assert phase.cell.gamma.value == 120.0
    assert [a.species for a in phase.atoms] == [DUMMY_SPECIES]
    assert not any(p.vary for p in (phase.cell.a, phase.cell.c, phase.scale))


def test_lebail_scaffold_does_not_validate_the_symbol():
    """A ``Phase`` never has, and the two callers refuse against their own field.

    Stated as a test because the alternative reads like an oversight: resolving
    the symbol here would put the refusal a layer below the form field it
    belongs to, and ``structure_from_candidate`` would then re-raise it anyway.
    """
    from rietx.schemas.structure import lebail_scaffold

    structure = lebail_scaffold("not a symbol", (1, 2, 3, 90, 90, 90))
    assert structure.phases[0].space_group == "not a symbol"


def test_structure_from_candidate_is_the_scaffold_plus_the_symbol_default():
    """The indexing wrapper adds the absence-free lattice group and nothing else.

    Bit-identity, not equivalence: the candidate's six numbers reach the phase
    exactly as it refined them (WP-1206 deliberately does not route them through
    ``complete_cell``, which would move every stored cell in the indexing
    acceptance suite at the 1e-14 level for no gain).
    """
    from rietx.indexing.workflow import structure_from_candidate
    from rietx.schemas.indexing import CellCandidate
    from rietx.schemas.structure import lebail_scaffold

    cell = (4.15682, 4.15680, 4.15681, 90.0, 90.0, 90.0)
    candidate = CellCandidate(cell=list(cell), cell_esd=[0.0] * 6, volume=71.83,
                              system="cubic", centring="P",
                              lattice_group="P m -3 m")
    got = structure_from_candidate(candidate, name="candidate")
    want = lebail_scaffold("P m -3 m", cell, name="candidate")
    assert got.model_dump() == want.model_dump()


# ------------------------------------------ the shared form-factor grammar ---
# The *where* of a bad species — the refusal naming the phase, the atom and the
# label — is tested at the compile boundary, in test_robustness_external.py,
# because that is where the lookups fire and ``docs/manual/using/data.md``
# § Atom promises the check lives ("validated when the model compiles rather
# than when the object is built").  What stays here is the property one rank
# below: the two **X-ray** lookups parse the *same* grammar, which
# ``cif._CANONICAL_SPECIES`` claims they "share deliberately" — an agreement
# nothing asserted before, and the divergence class the first attempt fell into
# (widening one lookup while the other still refused, invisibly).
#
# The guard is scoped to the X-ray pair on purpose: the compile boundary reaches
# a *third* table on a neutron source (``neutron.normalize_species`` → ``b_coh``,
# keyed by nuclide), and it parses the grammar more leniently — it keeps a
# nuclide the X-ray table has no row for and *accepts* the sign-first charge the
# X-ray pair refuses.  That is a property to pin, not a contradiction to
# resolve: the neutron table discards the charge it is handed, so a spelling the
# X-ray guard calls malformed is well-formed there.  The divergence is asserted
# just below, so the X-ray guard cannot be misread as a claim about all three.


def test_a_well_formed_symbol_that_names_no_element_is_the_lookups_business():
    """``Xx`` is spelled correctly and is not an element: two questions, not one.

    A structure can carry it — the schema knows no chemistry and does not gate
    on a periodic table (which would also refuse a neutron nuclide ``2H`` for
    the X-ray table's sake).  The tables are what refuse it, and they refuse it
    at *different depths*, itself worth pinning: ``normalize_element`` validates
    the shape only and hands ``"Xx"`` back, while ``dispersion`` is what has no
    row for it.  Both refusals get named at the compile boundary — that is the
    "well-formed symbol, no table row" half of the population, covered in
    test_robustness_external.py.
    """
    from rietx.crystallography.dispersion import dispersion, normalize_element
    from rietx.crystallography.scattering import normalize_species

    assert normalize_element("Xx") == "Xx"          # shape is all this checks
    with pytest.raises(KeyError, match="Xx"):
        dispersion("Xx", 1.5405929)                 # the table is what refuses
    with pytest.raises(KeyError, match="Xx"):
        normalize_species("Xx")


@pytest.mark.parametrize("spelling", ["Fe", "Fe3+", "Fe2+", "Fe+"])
def test_both_xray_lookups_accept_every_well_formed_spelling(spelling):
    """The shared grammar, checked on a species both tables carry.

    ``cif._CANONICAL_SPECIES`` is declared as the grammar both X-ray lookups
    parse, "which share it deliberately" — so the agreement is a property to
    assert, not a comment to trust.
    """
    from rietx.crystallography.dispersion import normalize_element
    from rietx.crystallography.scattering import normalize_species

    assert normalize_element(spelling) == "Fe"
    assert normalize_species(spelling)          # resolves; ion kept or not


@pytest.mark.parametrize("bad", ["Cu+1", "O-2", "Ni+3", "Cu++", "Cu 1+",
                                 "Cu+1+", "1Cu", ""])
def test_both_xray_lookups_refuse_every_malformed_spelling(bad):
    """The guard that was missing, and the reason this fix moved layers.

    Widening one lookup alone leaves the two disagreeing with nothing asserting
    otherwise, and the divergence is invisible: the second fires two lines after
    the first at the same stage compile and reports a *missing element* for a
    species that is in its table under another spelling. Measured on a
    hand-built ``Cu+1`` structure: the error moved from
    ``dispersion.py`` "cannot read an element symbol" to ``scattering.py``
    "no Waasmaier-Kirfel coefficients for species 'Cu+1'" — same depth, still
    naming neither the atom nor the phase, and now actively misleading, since Cu
    is in that table.
    """
    from rietx.crystallography.dispersion import normalize_element
    from rietx.crystallography.scattering import normalize_species

    with pytest.raises((KeyError, ValueError)):
        normalize_element(bad)
    with pytest.raises((KeyError, ValueError)):
        normalize_species(bad)


@pytest.mark.parametrize("spelling, expected", [
    ("Cu+1", "Cu"), ("Cu1+", "Cu"), ("O-2", "O"),   # sign-first accepted, charge dropped
    ("2H", "2H"), ("D", "2H"), ("157Gd", "157Gd"),   # nuclide kept; alias resolved
])
def test_the_neutron_parser_diverges_from_the_xray_grammar_by_design(
        spelling, expected):
    """The third table the compile boundary reaches, and why the guard is X-ray only.

    ``compile_phase_sites(neutron=True)`` normalises species through
    ``neutron.normalize_species``, keyed by nuclide.  It is *lenient* exactly
    where the X-ray pair above is strict: it accepts both charge spellings
    (``Cu+1`` and ``Cu1+`` alike — the nucleus does not see valence electrons)
    and keeps a mass number (``2H``, ``157Gd``) the Waasmaier-Kirfel table has
    no row for.  So a spelling ``test_both_xray_lookups_refuse_every_malformed``
    calls malformed is well-formed here, and the two guards are about two
    different tables — the reason the locator picks the table by radiation.
    """
    from rietx.crystallography.neutron import normalize_species as neutron_normalize

    assert neutron_normalize(spelling) == expected


def test_a_reader_repairs_the_sign_first_charge_the_compile_boundary_refuses():
    """The division of labour, asserted rather than described.

    A schema has no diagnostics channel and the compile boundary raises; a
    reader has one, so it may repair a sign-first charge and record it
    (``CIF_SPECIES_NORMALISED``). That asymmetry is why the population a
    hand-built structure reaches the compile boundary as is *not* served by the
    reader — it never went through one.
    """
    from rietx.crystallography.cif import normalize_cif_species

    assert normalize_cif_species("Cu+1") == ("Cu1+", "sign-first charge")
    assert normalize_cif_species("O-2") == ("O2-", "sign-first charge")
