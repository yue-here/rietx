"""M1: a public call refuses a choice it cannot honour before any work (WP-2302).

DESIGN § Rules, 4: "a literal the call cannot honour raises before any work,
naming the argument and the fix."  A misspelt ``mode`` used to run 2.8 s of a
4.1 s fit and then raise a pydantic error about ``RefinementResult``, an
internal schema; ``Refinement.parameters(mode=...)`` answered without a word.

**Which arguments are choices is derived, not listed.**  The public surface is
:mod:`tests.api_surface`'s.  An argument is a choice when its annotation holds a
``Literal``, or when its name is in :data:`CHOICE_NAMES` and its annotation
admits a ``str``.  Every such argument needs a row in :data:`CASES` (a cheap
call passing a bad value) or in :data:`NOT_CHOICES` (a reason).  A new choice
argument with neither fails :func:`test_every_choice_argument_has_a_row`,
naming the callable.

**"Before any work" is checked**: ``compile_model`` is replaced, in every
module that imported it, by a function that raises :class:`CompileReached`.
A refusal that comes after the model is built fails the test by that name.

**The valid members come from the live registries** the code checks against
(``get_args(Mode)``, ``SOLVERS``, ``BACKEND_NAMES``), never a copy here: a row
naming a registry asserts that every member is quoted in the message.
"""

from __future__ import annotations

import sys
import typing
from types import SimpleNamespace

import pytest

import rietx as rx
from rietx.backend.api import BACKEND_NAMES
from rietx.model import forward
from rietx.optimize.least_squares import SOLVERS
from rietx.schemas.common import Mode
from rietx.schemas.plan import PlanSpec
from rietx.strategy.refit import REFIT_MODES
from rietx.strategy.staged import PLAN_PRESETS
from tests import api_surface
from tests.test_refine_synthetic import perturbed_models, synthesize

#: argument names that take a choice from a fixed set wherever they appear
CHOICE_NAMES = frozenset({
    "mode", "solver", "backend", "refit", "direction", "on_error",
    "nuclear_group", "prefer", "metric", "kind", "preset", "engines",
    "deliverable", "radiation", "plan", "shape", "width", "p1_expand",
})

#: (callable, argument) the derivation finds that is not a choice, with why
NOT_CHOICES: dict[tuple[str, str], str] = {
    ("FitReport.action", "kind"):
        "a lookup by an action's kind in this report; a missing one raises "
        "KeyError naming it",
}

BAD = "zzbad"


class CompileReached(AssertionError):
    """A call reached ``compile_model`` before refusing a bad choice."""


def _choice_arguments() -> set[tuple[str, str]]:
    found = set()
    for name, obj in _callables():
        import inspect

        for p in inspect.signature(obj).parameters.values():
            ann = _resolved(obj, p.annotation)
            if "Literal" in str(ann) or (p.name in CHOICE_NAMES and _admits_str(ann)):
                found.add((name, p.name))
    return found


def _resolved(func, annotation):
    """One parameter's annotation, evaluated where ``func`` was written.

    Per parameter, because ``typing.get_type_hints`` gives up on the whole
    signature when one name (a return type, say) resolves only later."""
    if not isinstance(annotation, str):
        return annotation
    try:
        return eval(annotation, getattr(func, "__globals__", {}))  # noqa: S307
    except Exception:
        return annotation


def _admits_str(annotation) -> bool:
    """Whether ``annotation`` takes a ``str``, alone or inside a union or a
    sequence (``str | None``, ``RefinementPlan | str``, ``Sequence[str]``)."""
    if isinstance(annotation, str):
        return "str" in annotation.replace("|", " ").replace("[", " ").replace(
            "]", " ").split()
    return annotation is str or any(
        _admits_str(arg) for arg in typing.get_args(annotation))


def _callables():
    import inspect

    surface = api_surface.derive_surface()
    types_ = api_surface.reachable_types()
    for name, entry in sorted(surface.items()):
        if entry.kind not in ("function", "member"):
            continue
        parts = name.split(".")
        if entry.kind == "function":
            obj = rx
            for part in parts:
                obj = getattr(obj, part, None)
        else:
            cls = types_.get(parts[0])
            obj = inspect.getattr_static(cls, parts[1], None) if cls else None
            if isinstance(obj, (staticmethod, classmethod)):
                obj = obj.__func__
        if not callable(obj) or isinstance(obj, (property, type)):
            continue
        try:
            inspect.signature(obj)
        except (TypeError, ValueError):
            continue
        yield name, obj


# ------------------------------------------------------------------ fixtures


@pytest.fixture(scope="module")
def ctx(tmp_path_factory):
    """One fitted refinement and the cheap objects the rows call into."""
    data = synthesize()
    fitted = rx.Refinement(*perturbed_models())
    fitted.fit(data, plan=rx.RefinementPlan(
        [rx.Stage("scale", turn_on=["phases.*.scale"])]))
    root = tmp_path_factory.mktemp("choices")
    xy = root / "pattern.xy"
    xy.write_text("\n".join(f"{t:.4f} {y:.3f}" for t, y in zip(
        data.two_theta, data.intensity, strict=True)), encoding="utf-8")
    structure, instrument = perturbed_models()
    project = rx.Project.create(root / "p.rex", pattern=xy,
                                structure=structure, instrument=instrument)
    joint = _joint_ref(SimpleNamespace(data=data))
    joint.fit([data, data], plan=rx.RefinementPlan(
        [rx.Stage("scale", turn_on=["phases.*.scale"])]))
    return SimpleNamespace(data=data, fitted=fitted, joint=joint, xy=xy, root=root,
                           project_path=project.path)


@pytest.fixture
def no_compile(monkeypatch):
    real = forward.compile_model

    def refuse(*args, **kwargs):
        raise CompileReached("compile_model was reached before the refusal")

    for module in list(sys.modules.values()):
        if (getattr(module, "__name__", "").startswith("rietx")
                and getattr(module, "compile_model", None) is real):
            monkeypatch.setattr(module, "compile_model", refuse)


def _fresh():
    return rx.Refinement(*perturbed_models())


def _seq():
    return rx.SequentialRefinement(*perturbed_models())


def _joint(c, **kw):
    structure, instrument = perturbed_models()
    return rx.refine_multi([c.data, c.data], structure,
                           [instrument, instrument.model_copy(deep=True)], **kw)


def _joint_ref(c, **kw):
    structure, instrument = perturbed_models()
    return rx.MultiHistogramRefinement(
        structure, [instrument, instrument.model_copy(deep=True)], **kw)


MODES = typing.get_args(Mode)

#: (callable, argument) -> (call with a bad value, the registry the message
#: quotes in full, or None)
CASES: dict[tuple[str, str], tuple] = {
    ("refine", "mode"): (lambda c, v: rx.refine(c.data, *perturbed_models(), mode=v), MODES),
    ("refine", "plan"): (lambda c, v: rx.refine(c.data, *perturbed_models(), plan=v), None),
    ("refine", "backend"): (lambda c, v: rx.refine(c.data, *perturbed_models(), backend=v),
                            BACKEND_NAMES),
    ("refine", "solver"): (lambda c, v: rx.refine(c.data, *perturbed_models(), solver=v),
                           SOLVERS),
    ("refine", "refit"): (lambda c, v: rx.refine(c.data, *perturbed_models(), refit=v),
                          REFIT_MODES),
    ("Refinement.fit", "mode"): (lambda c, v: _fresh().fit(c.data, mode=v), MODES),
    ("PlanSpec.preset_name", "mode"): (
        lambda c, v: PlanSpec.from_plan(PLAN_PRESETS["mccusker_default"]()).preset_name(v),
        MODES),
    ("Refinement.fit", "plan"): (lambda c, v: _fresh().fit(c.data, plan=v), None),
    ("Refinement.fit", "refit"): (lambda c, v: _fresh().fit(c.data, refit=v), REFIT_MODES),
    ("Refinement.run_stage", "mode"): (
        lambda c, v: _fresh().run_stage(c.data, rx.Stage("s", turn_on=["phases.*.scale"]),
                                        mode=v), MODES),
    ("Refinement.parameters", "mode"): (lambda c, v: _fresh().parameters(mode=v), MODES),
    ("Refinement.suggest", "mode"): (lambda c, v: c.fitted.suggest(c.data, mode=v), MODES),
    ("Refinement.report", "plan"): (lambda c, v: c.fitted.report(plan=v), None),
    ("Refinement.summary", "plan"): (lambda c, v: c.fitted.summary(plan=v), None),
    ("Refinement.summary", "deliverable"): (
        lambda c, v: c.fitted.summary(deliverable=v), None),
    ("Refinement.merge", "prefer"): (lambda c, v: c.fitted.merge("head", prefer=v),
                                     ("ours", "theirs")),
    ("Refinement.from_node", "backend"): (
        lambda c, v: rx.Refinement.from_node(c.fitted.history, c.fitted.history.head,
                                             backend=v), BACKEND_NAMES),
    ("Refinement.from_node", "solver"): (
        lambda c, v: rx.Refinement.from_node(c.fitted.history, c.fitted.history.head,
                                             solver=v), SOLVERS),
    ("RefinementTree.best", "metric"): (lambda c, v: c.fitted.history.best(metric=v), None),
    ("RefinementResult.summary", "deliverable"): (
        lambda c, v: c.fitted.result_.summary(deliverable=v), None),
    ("diagnostics_summary", "deliverable"): (
        lambda c, v: rx.diagnostics_summary([c.fitted.result_], deliverable=v), None),
    ("SequentialRefinement.fit", "mode"): (lambda c, v: _seq().fit([c.data], mode=v), MODES),
    ("SequentialRefinement.fit", "plan"): (lambda c, v: _seq().fit([c.data], plan=v), None),
    ("SequentialRefinement.fit", "refit"): (lambda c, v: _seq().fit([c.data], refit=v),
                                            REFIT_MODES),
    ("SequentialRefinement.fit", "direction"): (
        lambda c, v: _seq().fit([c.data], direction=v), None),
    ("SequentialRefinement.fit", "on_error"): (
        lambda c, v: _seq().fit([c.data], on_error=v), None),
    ("refine_sequential", "backend"): (
        lambda c, v: rx.refine_sequential([c.data], *perturbed_models(), backend=v),
        BACKEND_NAMES),
    ("refine_sequential", "solver"): (
        lambda c, v: rx.refine_sequential([c.data], *perturbed_models(), solver=v), SOLVERS),
    ("SeriesResult.agreement_trajectory", "metric"): (
        lambda c, v: rx.SeriesResult.model_construct().agreement_trajectory("p", metric=v),
        ("r_bragg", "r_f")),
    ("SeriesResult.summary", "deliverable"): (
        lambda c, v: rx.SeriesResult.model_construct().summary(deliverable=v), None),
    ("refine_multi", "mode"): (lambda c, v: _joint(c, mode=v), None),
    ("refine_multi", "plan"): (lambda c, v: _joint(c, plan=v), None),
    ("refine_multi", "backend"): (lambda c, v: _joint(c, backend=v), BACKEND_NAMES),
    ("refine_multi", "solver"): (lambda c, v: _joint(c, solver=v), SOLVERS),
    ("MultiHistogramRefinement.fit", "mode"): (
        lambda c, v: _joint_ref(c).fit([c.data, c.data], mode=v), None),
    ("MultiHistogramRefinement.fit", "plan"): (
        lambda c, v: _joint_ref(c).fit([c.data, c.data], plan=v), None),
    ("MultiHistogramRefinement.parameters", "mode"): (
        lambda c, v: _joint_ref(c).parameters(mode=v), MODES),
    ("MultiHistogramRefinement.report", "plan"): (
        lambda c, v: c.joint.report(0, plan=v), None),
    ("Project.create", "mode"): (
        lambda c, v: rx.Project.create(c.root / f"m{v}.rex", pattern=c.xy,
                                       structure=perturbed_models()[0],
                                       instrument=perturbed_models()[1], mode=v), MODES),
    ("Project.create", "backend"): (
        lambda c, v: rx.Project.create(c.root / f"b{v}.rex", pattern=c.xy,
                                       structure=perturbed_models()[0],
                                       instrument=perturbed_models()[1], backend=v),
        BACKEND_NAMES),
    ("Project.create", "solver"): (
        lambda c, v: rx.Project.create(c.root / f"s{v}.rex", pattern=c.xy,
                                       structure=perturbed_models()[0],
                                       instrument=perturbed_models()[1], solver=v), SOLVERS),
    ("Project.open", "backend"): (lambda c, v: rx.Project.open(c.project_path, backend=v),
                                  BACKEND_NAMES),
    ("Project.open", "solver"): (lambda c, v: rx.Project.open(c.project_path, solver=v),
                                 SOLVERS),
    ("Structure.from_cif", "nuclear_group"): (
        lambda c, v: rx.Structure.from_cif("tests/data/cod_1000236.cif", nuclear_group=v),
        None),
    ("solve_magnetic", "nuclear_group"): (
        lambda c, v: rx.solve_magnetic(c.fitted, c.data, nuclear_group=v), None),
    ("auto_background", "kind"): (lambda c, v: rx.auto_background(c.data, kind=v), None),
    ("index_pattern", "preset"): (
        lambda c, v: rx.index_pattern(data=c.data, instrument=perturbed_models()[1],
                                      preset=v), None),
    ("index_pattern", "engines"): (
        lambda c, v: rx.index_pattern(data=c.data, instrument=perturbed_models()[1],
                                      engines=[v]), None),
    ("Instrument.bragg_brentano", "radiation"): (
        lambda c, v: rx.Instrument.bragg_brentano(radiation=v), None),
    ("Instrument.flat_plate_transmission", "radiation"): (
        lambda c, v: rx.Instrument.flat_plate_transmission(radiation=v), None),
    ("ProfileTCHZ.coarse", "shape"): (lambda c, v: rx.ProfileTCHZ.coarse(shape=v), None),
    ("GuardFinding.nonpositive_resolution", "width"): (
        lambda c, v: rx.GuardFinding.nonpositive_resolution(1, 2, -1.0, 10.0, width=v),
        None),
    ("write_topas_inp", "p1_expand"): (
        lambda c, v: rx.write_topas_inp(perturbed_models()[0], c.root / "x.inp",
                                        p1_expand=v), None),
}


def test_every_choice_argument_has_a_row():
    """A choice argument with no row fails here, naming its callable."""
    found = _choice_arguments()
    missing = sorted(found - set(CASES) - set(NOT_CHOICES))
    assert not missing, (
        "a public argument takes a choice and no row in CASES calls it with a "
        f"bad value: {missing}. Check it on entry (rietx._nearmiss.check_choice) "
        "and add a row; or, if it is not a choice, a NOT_CHOICES reason")
    stale = sorted((set(CASES) | set(NOT_CHOICES)) - found)
    assert not stale, f"rows naming no live choice argument: {stale}"


@pytest.mark.parametrize("key", sorted(CASES), ids=".".join)
def test_a_bad_choice_is_refused_before_any_work(key, ctx, no_compile):
    call, registry = CASES[key]
    _, argument = key
    with pytest.raises(ValueError) as info:
        call(ctx, BAD)
    message = str(info.value)
    assert argument in message, f"the refusal does not name {argument!r}: {message}"
    for member in registry or ():
        assert repr(member) in message or member in message, (
            f"the refusal does not quote the valid choice {member!r}: {message}")


def test_a_near_miss_names_the_choice_it_was_close_to(ctx, no_compile):
    with pytest.raises(ValueError, match=r"did you mean 'lebail'\?"):
        _fresh().parameters(mode="lebial")
    with pytest.raises(ValueError, match=r"unknown mode 'rietvled'; mode takes "
                                         r"'rietveld', 'lebail' or 'pawley'"):
        rx.refine(ctx.data, *perturbed_models(), mode="rietvled")


#: callables whose ``path`` is a parameter dot-path and whose docstring is not
#: the place to say so, with why
PATH_DOC_EXEMPT = {
    "GuardFinding": "factories the package's own guards call; a finding's "
                    "``paths`` field documents the dot-paths it carries",
}


def test_every_path_argument_says_which_path_it_is():
    """``path`` names a file in the writers and a parameter dot-path in the
    verbs (settled 2026-11-23).  A file is typed with ``Path``; a dot-path is
    a bare ``str`` whose docstring says "dot-path"."""
    import inspect

    unclear = []
    for name, obj in _callables():
        parameter = inspect.signature(obj).parameters.get("path")
        if parameter is None or name.split(".")[0] in PATH_DOC_EXEMPT:
            continue
        annotation = _resolved(obj, parameter.annotation)
        if "Path" in str(annotation):
            continue
        if annotation is str and "dot-path" in (inspect.getdoc(obj) or ""):
            continue
        unclear.append(f"{name} ({annotation})")
    assert not unclear, (
        "a `path` argument that does not say which path it is: type a file "
        "`str | Path`, or name a dot-path in the docstring: " + ", ".join(unclear))
