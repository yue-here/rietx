"""WP-2224: a second ``fit`` on a model its last fit converged runs one stage.

A first fit runs the plan.  A re-fit (the working state is an accepted fit's
answer on the same pattern, mode and channels, with no value written since)
runs the plan collapsed into one stage, ``warm_refit``, and falls back to the
plan when that one stage is rejected.  ``refit="stages"`` is the fit as it was.

The reference for "keeps the answer" is the **first fit's** answer, never a
staged re-fit's: a staged re-fit moves zincite's profile V about 2 esd to a
lower Rwp (WP-2224 § Measured), which is the staged plan's own behaviour.
Every fit here declares its ``refit`` when it pins a number through a second
``fit``.
"""

from __future__ import annotations

import importlib
import json
import warnings
from pathlib import Path

import numpy as np
import pytest

from rietx.history.tree import RefinementTree
from rietx.refine import REFIT_KEY_NOTE, Refinement
from rietx.strategy.staged import CLOSING_STAGE_NAME, Stage
from rietx.viz import compare

# the module, never ``rietx.refine``, which the package rebinds to the function
refine_mod = importlib.import_module("rietx.refine")
DATA_DIR = compare.default_data_dir()
FAMILIES = ("zincite", "fluorite", "corundum")


def _standard(key):
    std = next(s for s in compare.STANDARDS if s.key == key)
    if not std.available(DATA_DIR):
        pytest.skip(f"{key} data not present")
    return std


def _declared(result):
    """The stages a result's plan declared, the closing stage left out."""
    return [s.name for s in result.stages if s.name != CLOSING_STAGE_NAME]


def _evaluations(result):
    return sum(s.n_iterations for s in result.stages)


def _plot(result, stem):
    from rietx.viz.plots import plot_result
    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    plot_result(result, path=str(out / f"refit_single_{stem}.png"))


class _Fitted:
    """One standard, first-fitted once; each test checks out its answer."""

    def __init__(self, key):
        self.std = _standard(key)
        self.inputs = self.std.build(DATA_DIR)
        self.kw = dict(two_theta_limits=self.inputs.two_theta_limits)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.ref = Refinement(self.inputs.structure, self.inputs.instrument)
            self.first = self.ref.fit(self.inputs.data, plan=self.plan(), **self.kw)

    def plan(self):
        return self.std.build(DATA_DIR).plan

    def fit(self, **kw):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return self.ref.fit(self.inputs.data, plan=self.plan(), **self.kw, **kw)

    def at_answer(self):
        """The working state back at the first fit's answer node."""
        self.ref.checkout(self.first.node_id)
        return self


_CACHE: dict[str, _Fitted] = {}


def _at(key):
    """The standard's first fit, shared within its xdist group, at its answer."""
    if key not in _CACHE:
        _CACHE[key] = _Fitted(key)
    return _CACHE[key].at_answer()


#: one group per standard, so the three first fits run on three workers
_GROUPED = [pytest.param(k, marks=pytest.mark.xdist_group(f"refit-{k}"))
            for k in FAMILIES]
_ZINCITE = pytest.mark.xdist_group("refit-zincite")


@pytest.fixture(params=_GROUPED)
def fitted(request):
    return _at(request.param)


@pytest.fixture
def zincite():
    return _at("zincite")


def test_a_first_fit_runs_the_plan(fitted):
    assert _declared(fitted.first) == [s.name for s in fitted.plan().stages]
    assert fitted.first.status == "converged"


def test_a_refit_is_one_stage_and_keeps_the_first_answer(fitted):
    one = fitted.fit()
    assert _declared(one) == ["warm_refit"]
    assert one.status == "converged"
    first = {p.path: p for p in fitted.first.parameters}
    gaps = {p.path: abs(p.value - first[p.path].value) / first[p.path].stderr
            for p in one.parameters
            if p.path in first and first[p.path].stderr}
    assert gaps and max(gaps.values()) < 0.5, max(gaps.items(), key=lambda kv: kv[1])
    _plot(one, fitted.std.key)

    # the staged re-fit from the same converged state, for its cost alone
    staged = fitted.at_answer().fit(refit="stages")
    assert _declared(staged) == _declared(fitted.first)
    assert _evaluations(one) < 0.6 * _evaluations(staged), (
        _evaluations(one), _evaluations(staged))


@_ZINCITE
def test_refit_stages_is_the_fit_without_a_refit_bit_for_bit(zincite):
    """``"stages"`` is the path a start that is not a re-fit takes."""
    asked = zincite.fit(refit="stages")
    zincite.at_answer()
    zincite.ref._refit_key = None          # the state the package had before WP-2224
    plain = zincite.fit()
    assert _declared(asked) == _declared(plain) == _declared(zincite.first)
    np.testing.assert_array_equal(asked.y_calc, plain.y_calc)
    assert ([(p.path, p.value, p.stderr) for p in asked.parameters]
            == [(p.path, p.value, p.stderr) for p in plain.parameters])


@_ZINCITE
def test_a_written_value_runs_the_plan(zincite):
    zero = zincite.ref.instrument.zero_shift.value
    zincite.ref.set_values({"instrument.zero_shift": zero + 1e-3})
    assert _declared(zincite.fit()) == _declared(zincite.first)


@_ZINCITE
def test_a_free_set_change_keeps_it_a_refit(zincite):
    zincite.ref.set_vary("instrument.zero_shift", True)
    assert _declared(zincite.fit()) == ["warm_refit"]


@_ZINCITE
@pytest.mark.parametrize("change", ["pattern", "limits", "mode"])
def test_another_pattern_channels_or_mode_runs_the_plan(change, zincite):
    f = zincite
    data, kw = f.inputs.data, dict(f.kw)
    mode = "rietveld"
    if change == "pattern":
        data = data.model_copy(update={"intensity": np.asarray(data.intensity) * 1.01})
    elif change == "limits":
        lo, hi = f.inputs.two_theta_limits or (float(data.x()[0]), float(data.x()[-1]))
        kw["two_theta_limits"] = (lo + 0.5, hi)
    else:
        mode = "lebail"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = f.ref.fit(data, plan=f.plan(), mode=mode, **kw)
    assert "warm_refit" not in _declared(res)


def test_a_fit_that_did_not_converge_leaves_no_refit():
    f = _Fitted.__new__(_Fitted)
    f.std = _standard("zincite")
    f.inputs = f.std.build(DATA_DIR)
    f.kw = dict(two_theta_limits=f.inputs.two_theta_limits)
    plan = f.std.build(DATA_DIR).plan
    for stage in plan.stages:
        stage.max_iter = 1
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        f.ref = Refinement(f.inputs.structure, f.inputs.instrument)
        short = f.ref.fit(f.inputs.data, plan=plan, **f.kw)
        assert short.status != "converged"
        assert f.ref._refit_key is None
        assert _declared(f.ref.fit(f.inputs.data, plan=f.std.build(DATA_DIR).plan,
                                   **f.kw)) == [s.name for s in plan.stages]


@_ZINCITE
def test_a_plan_that_fixes_runs_staged(zincite):
    plan = zincite.plan()
    plan.stages[-1].turn_off = ["instrument.zero_shift"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = zincite.ref.fit(zincite.inputs.data, plan=plan, **zincite.kw)
    assert _declared(res) == [s.name for s in plan.stages]


@_ZINCITE
def test_a_rejected_one_stage_fit_falls_back_to_the_plan(monkeypatch, tmp_path, zincite):
    """Rejected → discarded, models restored, the plan run from the same start.

    The fallback's answer is the staged re-fit's from that start, bit for bit,
    which is what "the models go back to where the fit started" has to mean.
    """
    f = zincite
    start = f.ref._head_id
    real = refine_mod._rejected
    monkeypatch.setattr(refine_mod, "_rejected",
                        lambda fit: (any(s.name == "warm_refit" for s in fit.stages)
                                     or real(fit)))
    runs_root = tmp_path / "runs"
    monkeypatch.delenv("RIETX_TELEMETRY", raising=False)
    fell = f.fit(telemetry=runs_root)
    monkeypatch.undo()

    assert _declared(fell) == _declared(f.first)
    codes = [d for d in fell.diagnostics if d.code == "WARM_REFIT_REJECTED"]
    assert len(codes) == 1 and codes[0].level == "info"
    assert codes[0].message.startswith("The one-stage re-fit ")
    assert "so it was discarded and the plan was run in stages" in codes[0].message
    assert _summary_plan_line(f.ref).endswith(
        "in stages, after the one-stage re-fit was discarded.")
    tree = f.ref.history
    discarded = [i for i in tree.order if tree.nodes[i].notes.get("refit_discarded")]
    assert discarded
    assert all(tree.nodes[i].action.name in ("warm_refit", CLOSING_STAGE_NAME)
               for i in discarded)
    # the staged pass grew from the start node, never from the discarded one
    node = tree.nodes[fell.node_id]
    while node.id != start:
        assert not node.notes.get("refit_discarded")
        node = tree.nodes[node.parent]
    # one job, one run directory, ending done
    run_dirs = [d for d in runs_root.iterdir() if d.is_dir()]
    assert len(run_dirs) == 1
    status = json.loads((run_dirs[0] / "status.json").read_text(encoding="utf-8"))
    assert status["state"] == "done"

    staged = f.at_answer().fit(refit="stages")
    np.testing.assert_array_equal(fell.y_calc, staged.y_calc)
    assert ([(p.path, p.value) for p in fell.parameters]
            == [(p.path, p.value) for p in staged.parameters])


def test_a_reopened_tree_at_a_converged_answer_is_a_refit(tmp_path):
    """Design 5: the history head is the working state, so the key rides on it."""
    std = _standard("zincite")
    inputs = std.build(DATA_DIR)
    log = tmp_path / "history.jsonl"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ref = Refinement(inputs.structure, inputs.instrument, history=log)
        first = ref.fit(inputs.data, plan=std.build(DATA_DIR).plan,
                        two_theta_limits=inputs.two_theta_limits)
        tree = RefinementTree.load(log)
        assert tree.nodes[tree.head].notes.get(REFIT_KEY_NOTE)
        reopened = Refinement.from_node(tree, "head")
        again = reopened.fit(inputs.data, plan=std.build(DATA_DIR).plan,
                             two_theta_limits=inputs.two_theta_limits)
    assert first.status == "converged"
    assert _declared(again) == ["warm_refit"]


@_ZINCITE
def test_refit_rejects_an_unknown_mode(zincite):
    with pytest.raises(ValueError, match="refit must be one of"):
        zincite.fit(refit="once")


def test_the_one_stage_keeps_the_last_stages_objective_and_windows():
    """A restraint weight, an ftol or a window slack on the plan's last stage
    is what its answer converged under, so the one stage keeps it, as the
    closing stage does (``RefinementPlan.closing_stage``)."""
    from rietx.strategy.refit import _collapse
    from rietx.strategy.staged import RefinementPlan, Stage

    plan = RefinementPlan(stages=[
        Stage("a", ["phases.*.scale"], restraint_weight_scale=10.0),
        Stage("b", ["phases.*.cell.*"], ftol=1e-11, restraint_weight_scale=0.1,
              window_slack_deg=0.5)])
    (one,) = _collapse(plan).stages
    assert (one.ftol, one.restraint_weight_scale, one.window_slack_deg) == (
        1e-11, 0.1, 0.5)
    assert one.turn_on == ["phases.*.scale", "phases.*.cell.*"]


@_ZINCITE
def test_an_empty_plan_is_refused_on_a_refit_too(zincite):
    """A re-fit does not collapse an empty plan into one stage freeing nothing."""
    from rietx.strategy.staged import RefinementPlan

    with pytest.raises(ValueError, match="a plan with no stages refines nothing"):
        zincite.ref.fit(zincite.inputs.data, plan=RefinementPlan(stages=[]),
                        **zincite.kw)


def _summary_plan_line(ref):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        text = ref.summary()
    return next(line for line in text.splitlines()
                if line.strip().startswith("plan:"))


@_ZINCITE
def test_a_plan_freeing_what_the_converged_fit_held_runs_staged(zincite):
    """Yue's ruling of 2026-11-19: a released parameter starts cold, so the
    plan runs in stages and the summary says which parameter made it."""
    plan = zincite.plan()
    plan.stages.append(Stage("xyz", ["phases.*.atoms.*.dof.*"]))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = zincite.ref.fit(zincite.inputs.data, plan=plan, **zincite.kw)
    assert _declared(res) == [s.name for s in plan.stages]
    line = _summary_plan_line(zincite.ref)
    assert "in stages, because this fit frees phases.0.atoms.0.dof.0" in line, line
    assert "which the last fit held" in line

    # that answer freed the coordinates, so fitting it again is a re-fit
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        again = zincite.ref.fit(zincite.inputs.data, plan=plan, **zincite.kw)
    assert _declared(again) == ["warm_refit"]


@_ZINCITE
def test_a_plan_freeing_less_stays_a_refit(zincite):
    plan = zincite.plan()
    plan.stages.pop()                       # biso stays where the fit left it
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = zincite.ref.fit(zincite.inputs.data, plan=plan, **zincite.kw)
    assert _declared(res) == ["warm_refit"]
    line = _summary_plan_line(zincite.ref)
    assert line.strip().startswith("plan: one stage (warm_refit), because the "
                                   "model had already converged"), line


@_ZINCITE
def test_an_unhold_releases_a_parameter_and_runs_staged(zincite):
    zincite.ref.hold("instrument.zero_shift")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        held = zincite.fit()
    # holding narrows the free set: a re-fit
    assert _declared(held) == ["warm_refit"]
    zincite.ref.unhold("instrument.zero_shift")
    assert _declared(zincite.fit()) == _declared(zincite.first)
