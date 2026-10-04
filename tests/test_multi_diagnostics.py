"""Which diagnostics a joint fit owes each histogram (WP-1344).

``multi.DIAGNOSTIC_SCOPES`` places every ``_*_diagnostics`` helper: once per
histogram, once for the shared structure, once for the joint solve, or not at
all with a reason.  Two halves here.  The meta-tests keep the table complete
and keep ``multi.py`` honouring it, read off the source rather than off a fit,
so a helper called only under a condition no fixture meets is still placed.
The arms then show each radiation-keyed code on the histogram that owns it and
nowhere else, and silent where the condition does not hold — the zero the
joint path returned for all three before this WP (PR #281's control, PR
#530's pins).

Synthetic throughout: corundum, and one-site vehicles for the two species
codes, none of them a claim about a specimen.
"""
from __future__ import annotations

import ast
import importlib
import inspect
import re
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.strategy.staged import GuardFinding, GuardReport, RefinementPlan, Stage
from tests.test_joint_xray_neutron import _flat, _neutron, _xray, _y_calc, corundum

multi = importlib.import_module("rietx.multi")
refine_mod = importlib.import_module("rietx.refine")

SCOPES = {multi.HISTOGRAM, multi.SPECIMEN, multi.FIT, multi.ABSENT}


def _helpers(module) -> set[str]:
    return {name for name, obj in vars(module).items()
            if name.startswith("_") and name.endswith("_diagnostics")
            and inspect.isfunction(obj) and obj.__module__ == module.__name__}


# ------------------------------------------------------------ the census ---
def test_every_diagnostic_helper_has_a_scope_and_every_scope_a_helper():
    """Both ways, so a new helper and a renamed one each fail here."""
    helpers = _helpers(refine_mod) | _helpers(multi)
    declared = set(multi.DIAGNOSTIC_SCOPES)
    assert helpers - declared == set(), (
        "diagnostic helpers with no row in multi.DIAGNOSTIC_SCOPES — say "
        "whether a joint fit owes each one per histogram, once, or not at all")
    assert declared - helpers == set(), "rows naming no helper"


@pytest.mark.parametrize("name", sorted(multi.DIAGNOSTIC_SCOPES))
def test_every_row_uses_the_vocabulary_and_states_its_reason(name):
    scopes, reason = multi.DIAGNOSTIC_SCOPES[name]
    assert scopes and set(scopes) <= SCOPES, scopes
    assert len(set(scopes)) == len(scopes)
    if multi.ABSENT in scopes:
        assert scopes == (multi.ABSENT,), "absent is not combinable"
    assert reason.strip(), "a row's reason is where a deliberate omission lives"


def _called_names(node: ast.AST) -> set[str]:
    return {n.func.id for n in ast.walk(node)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}


def _refine_call_graph() -> dict[str, set[str]]:
    tree = ast.parse(Path(inspect.getsourcefile(refine_mod)).read_text(encoding="utf-8"))
    return {fn.name: _called_names(fn) for fn in tree.body
            if isinstance(fn, ast.FunctionDef)}


def _reach(direct: set[str], graph: dict[str, set[str]]) -> set[str]:
    """``direct`` and every ``refine`` function reached through it."""
    seen, todo = set(), list(direct)
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        todo.extend(graph.get(name, ()))
    return seen


def _joint_call_sites() -> tuple[set[str], set[str]]:
    """(reached inside the per-histogram loop, reached anywhere else)."""
    tree = ast.parse(Path(inspect.getsourcefile(multi)).read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == "MultiHistogramRefinement")
    build = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                 and n.name == "_build_result")
    loops = [n for n in ast.walk(build) if isinstance(n, ast.For)
             and isinstance(n.target, ast.Name) and n.target.id == "h"
             and isinstance(n.iter, ast.Call)
             and getattr(n.iter.func, "id", None) == "range"]
    assert len(loops) == 1, "the per-histogram loop is no longer one `for h in range(n)`"
    (loop,) = loops
    loop_ids = {id(n) for n in ast.walk(loop)}
    # the roots are the class's own calls; a module-level function — this
    # module's or refine's — is reached from wherever *it* is called
    outside = {n.func.id for n in ast.walk(cls)
               if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
               and id(n) not in loop_ids}
    graph = _refine_call_graph() | {fn.name: _called_names(fn) for fn in tree.body
                                    if isinstance(fn, ast.FunctionDef)}
    return _reach(_called_names(loop), graph), _reach(outside, graph)


@pytest.mark.parametrize("name", sorted(multi.DIAGNOSTIC_SCOPES))
def test_the_joint_path_honours_the_scope(name):
    """A HISTOGRAM row is called in the loop, a SPECIMEN/FIT row outside it,
    an ABSENT row nowhere — the part that stops the gap reopening."""
    scopes, _ = multi.DIAGNOSTIC_SCOPES[name]
    inside, outside = _joint_call_sites()
    assert (name in inside) == (multi.HISTOGRAM in scopes), (
        f"{name}: declared {scopes}, "
        f"{'called' if name in inside else 'not called'} per histogram")
    once = multi.SPECIMEN in scopes or multi.FIT in scopes
    assert (name in outside) == once, (
        f"{name}: declared {scopes}, "
        f"{'called' if name in outside else 'not called'} once for the fit")


def _finding_fields() -> set[str]:
    import dataclasses

    from rietx.strategy.staged import GuardReport
    return {f.name for f in dataclasses.fields(GuardReport)
            if str(f.type) == "list[GuardFinding]"}


def test_every_guard_list_has_a_scope():
    """The rule one rank down: which of a ``GuardReport``'s finding lists a
    joint fit fills, and where — both ways, so a new guard fails here."""
    fields = _finding_fields()
    assert len(fields) >= 11
    assert set(multi.GUARD_SCOPES) == fields


def _guard_fills() -> tuple[set[str], set[str]]:
    """(fields filled inside the per-histogram loop, fields filled elsewhere):
    a ``GuardReport(field=…)`` keyword, or ``<report>.field`` written."""
    fields = _finding_fields()
    tree = ast.parse(Path(inspect.getsourcefile(multi)).read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == "MultiHistogramRefinement")
    build = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                 and n.name == "_build_result")
    loop = next(n for n in ast.walk(build) if isinstance(n, ast.For)
                and getattr(n.target, "id", None) == "h")

    def fills(node, skip=frozenset()):
        out = set()
        for n in ast.walk(node):
            if id(n) in skip:
                continue
            if (isinstance(n, ast.Call) and getattr(n.func, "id", None) == "GuardReport"):
                out |= {k.arg for k in n.keywords} & fields
            if isinstance(n, ast.Attribute) and n.attr in fields:
                out.add(n.attr)
        return out

    return fills(loop), fills(cls, {id(n) for n in ast.walk(loop)})


@pytest.mark.parametrize("field", sorted(multi.GUARD_SCOPES))
def test_the_joint_path_fills_each_guard_where_its_scope_says(field):
    scopes, reason = multi.GUARD_SCOPES[field]
    assert set(scopes) <= SCOPES - {multi.ABSENT} and reason.strip()
    inside, outside = _guard_fills()
    assert (field in inside) == (multi.HISTOGRAM in scopes), field
    assert (field in outside) == bool(set(scopes) & {multi.SPECIMEN, multi.FIT}), field


#: A finding for each guard placed on a histogram's list *and* at the top
#: level: the one exception to the written rule, which the prose must name.
_ON_BOTH_LISTS = {
    "background_correlations":
        lambda: GuardFinding.background_absorption("hist.0.phases.0.scale", 0.99),
}


def test_a_guard_on_both_lists_is_named_as_the_exception_in_the_prose():
    """The manual and skill §8.30 say a pattern's finding goes on its
    histogram's list and a fit's goes at the top level; a guard scoped to
    both is the exception, so its code must be named in both texts — and a
    new such row fails here until it is."""
    both = {f for f, (scopes, _) in multi.GUARD_SCOPES.items()
            if multi.HISTOGRAM in scopes
            and set(scopes) & {multi.SPECIMEN, multi.FIT}}
    assert both == set(_ON_BOTH_LISTS)
    root = Path(__file__).resolve().parents[1]
    manual = (root / "docs/manual/using/series.md").read_text(encoding="utf-8")
    skill = (root / "docs/skill/rietx/references/surprises.md").read_text(
        encoding="utf-8")
    s830 = skill[skill.index("**8.30 "):].split("\n**8.", 1)[0]
    for field, finding in _ON_BOTH_LISTS.items():
        (diag,) = multi._guard_diagnostics(
            GuardReport(**{field: [finding()]}))
        for text in (manual, s830):
            assert _names_as_exception(text, diag.code), (field, diag.code)
        # anchored on the paragraph, not on the code's first mention: an
        # earlier passing mention elsewhere in the file must not hide the
        # exception's own paragraph, and a paragraph without it still fails
        decoy = f"`{diag.code}` is also mentioned here, in passing.\n\n"
        assert _names_as_exception(decoy + manual, diag.code)
        assert not _names_as_exception(
            manual.replace("both lists", "two lists"), diag.code)


def _names_as_exception(text: str, code: str) -> bool:
    """Some one paragraph of ``text`` names ``code`` and says "both lists"."""
    return any(code in para and "both lists" in para
               for para in re.split(r"\n[ \t]*\n", text))


# -------------------------------------------------------- the three codes ---
def _short_plan():
    """One three-iteration stage: enough to compile and report every histogram."""
    return RefinementPlan(stages=[Stage("scale", ["phases.*.scale"], max_iter=3)])


def _xray_without_dispersion() -> rx.Instrument:
    xray = _xray()
    return xray.model_copy(update={
        "source": xray.source.model_copy(update={"dispersion": None})})


def _rock_salt(species: str) -> rx.Phase:
    """A rock-salt ``XO``: a vehicle for one site of ``species``, not a phase."""
    P = rx.Parameter
    a = 4.88
    return rx.Phase(
        name=f"{species}O", space_group="F m -3 m",
        cell=rx.Cell(a=P(value=a), b=P(value=a), c=P(value=a),
                     alpha=P(value=90.0), beta=P(value=90.0), gamma=P(value=90.0)),
        scale=P(value=1.0, min=0.0, transform="softplus"),
        atoms=[rx.Atom(label=species, species=species, x=P(value=0.0),
                       y=P(value=0.0), z=P(value=0.0), biso=P(value=0.3)),
               rx.Atom(label="O", species="O", x=P(value=0.5),
                       y=P(value=0.5), z=P(value=0.5), biso=P(value=0.3))])


def _as3plus_corundum() -> rx.Phase:
    """Corundum with its Al site labelled ``As3+``, an ion the X-ray table lacks."""
    phase = corundum()
    phase.atoms[0].species = "As3+"
    return phase


# (code, phase, X-ray instrument, expected count per [X-ray, neutron] histogram)
ARMS = [
    pytest.param("DISPERSION_NEGLECTED", corundum, _xray_without_dispersion,
                 [1, 0], id="dispersion-declined"),
    pytest.param("DISPERSION_NEGLECTED", corundum, _xray, [0, 0],
                 id="dispersion-on"),
    pytest.param("NEUTRON_RESONANT_ABSORBER", lambda: _rock_salt("Gd"), _xray,
                 [0, 1], id="resonant-Gd"),
    pytest.param("NEUTRON_RESONANT_ABSORBER", corundum, _xray, [0, 0],
                 id="resonant-none"),
    pytest.param("SPECIES_FALLBACK_NEUTRAL", _as3plus_corundum, _xray, [1, 0],
                 id="fallback-As3+"),
    pytest.param("SPECIES_FALLBACK_NEUTRAL", corundum, _xray, [0, 0],
                 id="fallback-none"),
]


@pytest.mark.parametrize("code, phase, xray, expected", ARMS)
def test_a_radiation_keyed_code_lands_on_the_histogram_that_owns_it(
        code, phase, xray, expected):
    """One count on the owning histogram, none on the other, none at top level
    — and, where it fires, the single fit's own message, so the joint path
    asks the question the single one does rather than a copy of it."""
    structure = rx.Structure(phases=[phase()])
    instruments = [xray(), _neutron()]
    joint = rx.refine_multi([_flat(20.0, 80.0), _flat(20.0, 80.0)], structure,
                            instruments, plan=_short_plan())
    per_hist = [[d for d in h.diagnostics if d.code == code]
                for h in joint.histograms]
    assert [len(f) for f in per_hist] == expected
    assert not [d for d in joint.diagnostics if d.code == code], (
        "a radiation-keyed code is the histogram's, never the fit's")

    for h, fired in enumerate(per_hist):
        if not fired:
            continue
        alone = rx.Refinement(structure.model_copy(deep=True), instruments[h],
                              history=False).fit(_flat(20.0, 80.0),
                                                 plan=_short_plan())
        single = [d for d in alone.diagnostics if d.code == code]
        assert [d.message for d in fired] == [d.message for d in single]


def test_two_histograms_of_one_radiation_answer_for_themselves():
    """Per histogram, not per radiation kind: of two X-ray histograms, only the
    one that declined dispersion is told so."""
    joint = rx.refine_multi(
        [_flat(20.0, 80.0), _flat(20.0, 80.0)], rx.Structure(phases=[corundum()]),
        [_xray_without_dispersion(), _xray()], plan=_short_plan())
    assert [[d.code for d in h.diagnostics].count("DISPERSION_NEGLECTED")
            for h in joint.histograms] == [1, 0]


# ----------------------------------------------- the other rows it wired ---
def test_the_specimen_and_the_fit_are_told_once():
    """SPECIMEN and FIT rows land at top level, once, never per histogram."""
    phase = corundum()
    phase.space_group = "R -3 c"  # bare: gemmi picks a setting and says so
    joint = rx.refine_multi([_flat(20.0, 80.0), _flat(20.0, 80.0)],
                            rx.Structure(phases=[phase]), [_xray(), _neutron()],
                            plan=_short_plan())
    top = [d.code for d in joint.diagnostics]
    assert top.count("SPACE_GROUP_SETTING_ASSUMED") == 1
    assert top.count("STAGE_MAX_ITER") == 1
    for h in joint.histograms:
        codes = {d.code for d in h.diagnostics}
        assert not codes & {"SPACE_GROUP_SETTING_ASSUMED", "STAGE_MAX_ITER"}


def test_the_low_angle_region_is_judged_per_histogram_by_the_single_fits_rule():
    """``LOW_ANGLE_UNMODELLED`` needs each tick's support, which only the
    single fit's tick builder had; both now read one rule
    (``refine._reflection_tick_support``), so the two paths quote the same
    boundary.  An impurity-like bump below corundum's first X-ray line fires
    on the X-ray histogram alone."""
    structure = rx.Structure(phases=[corundum()])
    structure.phases[0].scale.value = 1e-4
    rng = np.random.default_rng(1)

    def synth(instrument, step, bump):
        tt = np.arange(10.0, 80.0, step)
        y = (_y_calc(structure, instrument, _flat(10.0, 80.0, step)) + 50.0
             + bump * np.exp(-0.5 * ((tt - 13.0) / 0.4) ** 2))
        return rx.PatternData(two_theta=tt.tolist(),
                              intensity=rng.poisson(y).astype(float).tolist())

    xd, nd = synth(_xray(), 0.02, 300.0), synth(_neutron(), 0.05, 0.0)
    plan = RefinementPlan(stages=[Stage(
        "scale", ["phases.*.scale", "instrument.background.*"], max_iter=20)])
    joint = rx.refine_multi([xd, nd], structure, [_xray(), _neutron()], plan=plan)
    fired = [[d for d in h.diagnostics if d.code == "LOW_ANGLE_UNMODELLED"]
             for h in joint.histograms]
    assert [len(f) for f in fired] == [1, 0]

    alone = rx.Refinement(structure.model_copy(deep=True), _xray(),
                          history=False).fit(xd, plan=plan)
    single = [d for d in alone.diagnostics if d.code == "LOW_ANGLE_UNMODELLED"]
    assert [d.message for d in fired[0]] == [d.message for d in single]


def test_a_resolution_guard_is_the_instruments():
    """``RESOLUTION_NOT_POSITIVE`` (a GUARD_SCOPES HISTOGRAM row, never filled
    on this path before WP-1344): an X-ray Γ_G² below zero everywhere is named
    on the X-ray histogram, and not on the neutron one or the fit."""
    xray = _xray()
    xray.profile.w.min, xray.profile.w.value = -1.0, -0.05
    joint = rx.refine_multi([_flat(20.0, 80.0), _flat(20.0, 80.0)],
                            rx.Structure(phases=[corundum()]), [xray, _neutron()],
                            plan=_short_plan())
    assert [[d.code for d in h.diagnostics].count("RESOLUTION_NOT_POSITIVE")
            for h in joint.histograms] == [1, 0]
    assert "RESOLUTION_NOT_POSITIVE" not in {d.code for d in joint.diagnostics}
