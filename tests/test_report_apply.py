"""WP-1012 — from a typed suggestion to the verbs that carry it out.

Two halves, and the split is the point.  The **mapping** is pure: which of the
eighteen ``ActionKind`` members is a button, what stage a button runs, and why a
non-button is not one — all answerable without a fit, so they are asserted
against hand-built :class:`SuggestedAction` objects rather than waiting for a
state that emits each kind (since WP-1106 every member has a demonstrated
emitter, but which fixture produces which kind is the emission suites' concern,
not the mapping's).

The **apply** half is driven over real HTTP against one real refinement, because
the claims are about what happens to the project: one history node, χ² actually
measured against the prediction, and undo being a ``checkout`` rather than an
inverse verb.  The fixture deliberately fits a *narrow* plan (scale, background,
two profile widths) on a model whose cell is 0.0005 Å off — small enough to stay
inside the linearisation radius so Layer 1 does not abstain, and outside the
plan so the strategy veto does not cover it.  Everything the report says about
that project is a measurement, not a construction: ``refine_scale`` comes back
vetoed because the plan already refines it, and the two geometry actions come
back *unreachable* — this instrument is a capillary that declares no
goniometer radius, and McCusker eq (4) divides by one, so the pair it would
free is structurally fixed (WP-1073; before it, the unreachable pair here was
the Bragg-Brentano one, suggested on a Debye-Scherrer instrument because the
templates were geometry-blind).
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

import rietx as rx
from rietx.gui import ROUTES, GuiSession, build_server
from rietx.gui.session import RESERVED_ROUTES
from rietx.report.apply import (
    RECIPES,
    api_call,
    describe_action,
    missing_kinds,
    recipe,
    refusal,
    stage_for,
    unreachable,
)
from rietx.report.schemas import ActionKind, SuggestedAction
from rietx.schemas.instrument import BackgroundChebyshev
from tests.test_project import _write_xye
from tests.test_refine_synthetic import (
    TRUE_A,
    TRUE_BKG,
    TRUE_SCALE,
    TRUE_W,
    TRUE_ZERO,
    WAVELENGTH,
    synthesize,
)
from tests.test_schemas import make_lab6

pytestmark = pytest.mark.xdist_group("report-apply")

OUT = Path(__file__).parent / "output"

#: A narrow plan: everything the fit is allowed to touch.  What it leaves out is
#: what the report gets to suggest, and the veto's whole job is to mark what it
#: covers — so this list is the test's independent variable.
NARROW = [
    {"name": "scale+bkg", "turn_on": ["phases.*.scale", "instrument.background.*"]},
    {"name": "profile", "turn_on": ["instrument.profile.w", "instrument.profile.u"]},
]


def _action(kind: ActionKind, paths: list[str] | None = None,
            **kw) -> SuggestedAction:
    return SuggestedAction(kind=kind, confidence=0.5, rationale="because",
                           parameter_paths=paths or [], **kw)


# ----------------------------------------------------------------------
# the mapping (no fit needed)
# ----------------------------------------------------------------------
def test_every_action_kind_is_classified_and_the_split_is_declared():
    """A closed vocabulary, a complete table, and each half saying which it is.

    The count is asserted so that adding an ``ActionKind`` cannot quietly land on
    the advice side by default — which is how a vocabulary grows a member nothing
    can act on and nobody notices.
    """
    assert missing_kinds() == []
    how = {}
    for kind, rule in RECIPES.items():
        assert rule.kind == kind
        how.setdefault(rule.how, []).append(kind)
    assert len(how["stage"]) == 13
    assert how["index"] == ["reindex_or_recheck_cell"]
    assert sorted(how["advice"]) == [
        "add_impurity_phase", "collect_better_data",
        "decrease_background_flexibility", "increase_background_flexibility"]

    # a note is the substitute for a button, so it exists exactly where there is
    # no button — and a `stage` kind's explanation is the suggestion's own
    # rationale, not a second sentence here
    for rule in RECIPES.values():
        assert bool(rule.note) is (rule.how != "stage"), rule.kind
    with pytest.raises(KeyError, match="unknown action kind"):
        recipe("refine_everything")


def test_an_applicable_action_is_one_stage_named_after_its_kind():
    """No new mechanism: the mapping's output is a ``StageSpec``.

    Which is what makes an applied suggestion travel the path the "Run this stage"
    button already travels — and makes the line echoed before the click identical
    to the one the history node prints after it, because both come from
    ``NodeAction.api_call``.
    """
    action = _action("refine_cell", ["phases.*.cell.*"])
    stage = stage_for(action)
    assert stage.name == "apply:refine_cell"
    assert stage.turn_on == ["phases.*.cell.*"]
    # no seeds: a suggestion never proposes a softplus-floored or Stephens block
    assert stage.seed == 0.0 and stage.strain_seed == 0.0

    line = api_call(stage)
    assert line.startswith("ref.run_stage(data, rx.Stage('apply:refine_cell'")
    from rietx.schemas.history import NodeAction
    from rietx.schemas.plan import CLOSING_WINDOW_TOL

    # the node an applied stage writes: run_stage records the closing fraction
    assert line == NodeAction(kind="stage", name=stage.name, turn_on=stage.turn_on,
                              window_area_tol=CLOSING_WINDOW_TOL).api_call()

    with pytest.raises(ValueError, match="not carried out by a stage"):
        stage_for(_action("collect_better_data"))


def test_the_echoed_line_carries_the_plan_settings_the_stage_will_run_at():
    """A project whose stored plan switches the absent-phase hold off runs an
    applied stage with it off (``Project.run_stage``), and the node then
    renders that keyword, so the line echoed before the click names it too
    (WP-2002, B1).  A default plan echoes the line it always did."""
    from rietx.schemas.history import NodeAction
    from rietx.schemas.plan import CLOSING_WINDOW_TOL, PlanSpec

    stage = stage_for(_action("refine_cell", ["phases.*.cell.*"]))
    assert api_call(stage, plan=PlanSpec()) == api_call(stage)
    plan = PlanSpec(phase_support_sigma=None, correlation_guard=0.9)
    line = api_call(stage, plan=plan)
    assert line.endswith("correlation_guard=0.9, phase_support_sigma=None)")
    assert line == NodeAction(kind="stage", name=stage.name, turn_on=stage.turn_on,
                              phase_support_sigma=None, correlation_guard=0.9,
                              window_area_tol=CLOSING_WINDOW_TOL).api_call()


def test_advice_kinds_refuse_in_their_own_words_rather_than_silently():
    """"Unapplicable" is a statement with content, not an absent button."""
    free = {"phases.0.scale": "", "instrument.background.0": ""}
    for kind in ("add_impurity_phase", "collect_better_data",
                 "increase_background_flexibility",
                 "decrease_background_flexibility"):
        why = refusal(_action(kind, ["phases.*.scale"]), held=free)
        assert why.startswith("not a one-click action")
        assert RECIPES[kind].note in why

    # Both background kinds stay advice for a structural reason, not for want
    # of evidence: a Chebyshev term is a property of the model, not a member of
    # turn_on, so no stage can carry it.  Since WP-1055 the measurement they
    # name *is* in the report, and both notes point at it — the note that used
    # to say "which is not in this report" would now be a lie.
    for kind in ("increase_background_flexibility",
                 "decrease_background_flexibility"):
        assert "report.background.worst_absorption" in RECIPES[kind].note
        assert "not in this report" not in RECIPES[kind].note
    assert "biasing ADPs" in RECIPES["increase_background_flexibility"].note
    assert "BACKGROUND_ABSORPTION" in RECIPES["increase_background_flexibility"].note


def test_indexing_is_applicable_now_that_the_engine_exists():
    """The refusal a client could watch expire — expired (WP-1024, via WP-1037).

    This test's first version was a sentinel: it asserted the live flag
    ``is False`` so it would fail the day the engine landed and demand the
    applicable branch.  It slept through the event it was set for — the flag's
    ``hasattr`` name was wrong (``index`` against an export named
    ``index_pattern``), so the flag stayed ``False`` with the engine present.
    ``test_capabilities.py`` now meta-tests the name against ``__all__``; what
    is left to assert here is both sides of the gate on the live flag.
    """
    action = _action("reindex_or_recheck_cell", ["phases.*.cell.*"])
    held = {"phases.0.cell.a": ""}
    # a build that reports no engine still gets the refusal, with the reason…
    why = refusal(action, held=held, indexing=False)
    assert "features['indexing']" in why
    # …and the live flag now takes the applicable branch
    assert rx.capabilities().features["indexing"] is True
    assert refusal(action, held=held,
                   indexing=rx.capabilities().features["indexing"]) == ""


def test_the_veto_outranks_every_other_reason():
    """The strategy engine holds the veto, so it is the reason that is reported.

    A vetoed action that is *also* unreachable must still read as vetoed: the
    engine's judgement is the one a user has to argue with, and burying it under a
    plumbing complaint would hide the reasoning the report exists to show.
    """
    action = _action("refine_cell", ["phases.*.cell.*"],
                     vetoed_by="already refined by the staged plan (phases.*.cell.*)")
    why = refusal(action, held={})
    assert why == ("vetoed: already refined by the staged plan (phases.*.cell.*)")
    assert describe_action(action, held={})["stage"] is None


def test_unreachable_globs_separate_absent_from_held():
    """Two failure modes a panel must not merge, each quoting the table.

    ``preferred_orientation.r`` is *absent* until the phase declares the block —
    Layer 2 emits the action anyway, on purpose, with the axis in its rationale.
    A Le Bail project's ``biso`` is *present and held*, and the reason is
    ``held_because`` verbatim rather than a guess between three possibilities.
    """
    held = {"phases.0.atoms.0.biso":
            "force-fixed by the intensity mode (lebail/pawley)",
            "phases.0.cell.a": ""}

    absent = unreachable(_action("refine_preferred_orientation",
                                 ["phases.0.preferred_orientation.r"]), held)
    assert "not declared on the phase yet" in absent["phases.0.preferred_orientation.r"]

    blocked = unreachable(_action("refine_biso", ["phases.*.atoms.*.biso"]), held)
    assert blocked["phases.*.atoms.*.biso"] == (
        "every match is held (force-fixed by the intensity mode (lebail/pawley))")

    # a glob with one refinable match is reachable, however many held ones it hits
    assert unreachable(_action("refine_cell", ["phases.*.cell.*"]), held) == {}
    assert refusal(_action("refine_cell", []), held=held) == (
        "action carries no refinable parameter paths")


# ----------------------------------------------------------------------
# applying one, over HTTP, against a real fit
# ----------------------------------------------------------------------
def _models(delta_a: float = 0.0005):
    """The truth, with the cell moved by ``delta_a`` and nothing else wrong.

    0.0005 Å on a = 4.1566 is Δ2θ ≈ 0.0024° at 20° 2θ, about 0.15 FWHM here —
    inside the 0.4·FWHM linearisation radius, so Layer 1 does not abstain, and
    large enough that the position trend carries most of the misfit.  At 0.001 Å
    the fit is immature (measured Rwp 0.41) and the report correctly refuses to
    attribute anything, which is the wrong fixture for testing *apply*.
    """
    structure = make_lab6()
    for axis in ("a", "b", "c"):
        getattr(structure.phases[0].cell, axis).value = TRUE_A + delta_a
    structure.phases[0].scale.value = TRUE_SCALE * 1.3
    ins = rx.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.zero_shift.value = TRUE_ZERO
    ins.profile.w.value = TRUE_W * 1.4
    ins.background = BackgroundChebyshev(
        coefficients=[rx.Parameter(value=v) for v in TRUE_BKG])
    return structure, ins


class Client:
    """The same tiny client ``test_gui_server`` uses; kept local, not shared."""

    def __init__(self, port: int) -> None:
        self.port = port

    def request(self, method: str, path: str, body: dict | None = None):
        from http.client import HTTPConnection

        conn = HTTPConnection("127.0.0.1", self.port, timeout=120)
        payload = None if body is None else json.dumps(body).encode()
        head = {"Host": f"127.0.0.1:{self.port}"}
        if payload is not None:
            head["Content-Type"] = "application/json"
        try:
            conn.request(method, path, body=payload, headers=head)
            response = conn.getresponse()
            raw = response.read()
            try:
                return response.status, json.loads(raw)
            except ValueError:
                return response.status, {"raw": raw.decode("utf-8", "replace")}
        finally:
            conn.close()

    def get(self, path):
        return self.request("GET", path)

    def post(self, path, body=None):
        return self.request("POST", path, body or {})


def _wait_idle(client: Client, timeout: float = 120.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = client.get("/api/run/state")[1]
        if state["state"] == "idle":
            return state
        time.sleep(0.02)
    raise AssertionError("run did not finish")


def _serve(root: Path, state_dir: Path, plot: str = ""):
    """Create the project, fit the narrow plan, and serve it on a free port."""
    pattern = _write_xye(root.parent / "synth.xye", synthesize())
    structure, ins = _models()
    project = rx.Project.create(root, pattern=pattern, structure=structure,
                                instrument=ins,
                                plan=rx.PlanSpec.model_validate(
                                    {"stages": NARROW}).to_plan())
    session = GuiSession(project, state_dir=state_dir)
    httpd = build_server(session, port=0)
    threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.02},
                     daemon=True).start()
    client = Client(httpd.server_address[1])
    assert client.post("/api/run", {"kind": "fit"})[0] == 200
    state = _wait_idle(client)
    assert state["run"]["status"] == "converged", state
    if plot:
        OUT.mkdir(exist_ok=True)
        project.refinement.result_.plot(path=str(OUT / plot))
    return session, client, project, httpd


@pytest.fixture(scope="module")
def narrow(tmp_path_factory):
    """The fitted project the *reading* tests share — nothing here mutates it."""
    root = tmp_path_factory.mktemp("apply") / "narrow.rex"
    session, client, project, httpd = _serve(
        root, tmp_path_factory.mktemp("apply-state"), plot="report_apply_narrow.png")
    try:
        yield session, client, project
    finally:
        session.close()
        httpd.shutdown()
        httpd.server_close()


@pytest.fixture
def fresh(tmp_path):
    """A private copy for the test that applies an action.

    Its own project on purpose, and the fit is only ~0.4 s: applying a suggestion
    frees the cell and then *checks out* an earlier node, which moves the head and
    discards the result — so sharing the module fixture would make every reading
    test downstream of it depend on running second.
    """
    session, client, project, httpd = _serve(tmp_path / "fresh.rex",
                                             tmp_path / "state")
    try:
        yield session, client, project
    finally:
        session.close()
        httpd.shutdown()
        httpd.server_close()


def test_the_route_left_the_reserved_table_when_it_landed(narrow):
    """A path is live or reserved, never both — WP-1008's rule, one row later."""
    assert ("POST", "/api/report/apply") in ROUTES
    assert ("POST", "/api/report/apply") not in RESERVED_ROUTES
    assert not set(ROUTES) & set(RESERVED_ROUTES)


def test_the_report_says_what_applies_beside_what_it_suggests(narrow):
    """One authority: the button's enabled-ness is the route's own judgement.

    And three of the arms are measurements of this fixture rather than
    constructions — the narrow plan's veto, the geometry's locked aberrations, and
    a suggestion the plan leaves alone.
    """
    _, client, _ = narrow
    status, payload = client.get("/api/report")
    assert status == 200, payload
    report, arms = payload["report"], payload["apply"]
    assert report["layer1_available"] is True, report["abstained_reason"]
    # parallel to the actions, in the same order — a kind is not a unique key
    assert len(arms) == len(report["suggested_actions"])
    assert [a["kind"] for a in arms] == [a["kind"] for a in report["suggested_actions"]]
    by_kind = {a["kind"]: a for a in arms}

    # the cell is what the narrow plan left wrong, and it is applicable
    cell = by_kind["refine_cell"]
    assert cell["can_apply"] is True and cell["how"] == "stage"
    assert cell["stage"]["turn_on"] == ["phases.*.cell.*"]
    assert cell["api_call"].startswith("ref.run_stage(data, rx.Stage('apply:refine_cell'")

    # the plan refines the scale, so the engine vetoes the suggestion to
    assert by_kind["refine_scale"]["can_apply"] is False
    assert "already refined by the staged plan" in by_kind["refine_scale"]["refusal"]

    # …and Layer 2's position templates name this geometry's own aberrations —
    # eq (4)'s two capillary offsets — which are locked here because the
    # instrument declares no goniometer radius for eq (4) to divide by.  So the
    # suggestion is unreachable rather than a button that frees nothing
    for kind in ("refine_capillary_offset_along_beam",
                 "refine_capillary_offset_across_beam"):
        arm = by_kind[kind]
        assert arm["can_apply"] is False, kind
        assert "every match is held" in arm["refusal"], arm
        assert "structurally fixed" in arm["refusal"], arm


def test_every_emitted_action_carries_its_execution_class(narrow):
    """WP-1106: the recipe table's ``how``, typed on the action itself.

    Serialized, an advice kind arrives with ``parameter_paths: []`` *by
    design*, and before this field nothing in the JSON separated that from a
    bug — the sentence saying so reached agent context in 2 of 12 measured
    cells (WP-1065), because agents pipe the answer to a file and grep the
    statistics back.  So the classification is stamped on every emitted
    action, from the same table the GUI's apply arms quote; the two surfaces
    must agree because neither restates the mapping.
    """
    _, client, _ = narrow
    payload = client.get("/api/report")[1]
    report, arms = payload["report"], payload["apply"]
    assert report["suggested_actions"], "fixture must suggest something"
    for action, arm in zip(report["suggested_actions"], arms):
        assert action["execution"] == RECIPES[action["kind"]].how, action["kind"]
        assert action["execution"] == arm["how"]
    # the pin survives the typed contract's round-trip
    from rietx.report import FitReport

    parsed = FitReport.model_validate(report)
    assert all(a.execution is not None for a in parsed.suggested_actions)
    # and a hand-built action has honestly not been classified
    assert _action("refine_cell").execution is None


def test_the_predicted_delta_chi2_is_one_number_for_the_whole_report(narrow):
    """It is not per suggestion, and it is not a bound. Both are measured here.

    ``build_report`` computes ``estimate_delta_chi2`` once and stamps it on *every*
    Layer-1-derived action, so eight mutually-exclusive suggestions carry the
    identical figure — it cannot rank them, and a strip that printed it per row
    would imply a per-action prediction that does not exist.  Measured on this
    fixture: 16.19 on all eight, against a total χ² of 16.96, because the fifteen
    region entries happen to contain almost the whole misfit of a synthetic
    fifteen-peak pattern.

    The texture actions carry ``None`` on purpose (their evidence is
    per-reflection, not the gated region attribution the estimate covers), which
    is the other half of "one number per report".
    """
    _, client, _ = narrow
    report = client.get("/api/report")[1]["report"]
    predicted = {a["kind"]: a["expected_delta_chi2"]
                 for a in report["suggested_actions"]}
    stamped = {v for v in predicted.values() if v is not None}
    assert len(stamped) == 1, predicted
    assert len(predicted) > 3, "too few suggestions for this to mean anything"
    # …and the one number is most of the whole χ², which is what makes reading it
    # as "what this particular suggestion will buy" so misleading
    chi2 = client.get("/api/result")[1]["result"]["statistics"]["chi2"]
    assert stamped.pop() > 0.5 * chi2


def test_applying_a_suggestion_runs_one_stage_and_undo_is_a_checkout(fresh):
    """The whole loop: predict, apply, measure, undo.

    ``expected_delta_chi2`` is documented as an optimistic upper bound, and on
    this fit it is **not one**: predicted 16.19 against 16.33 observed, 0.8 % low.
    It bounds the misfit the linear model attributes *inside the gated regions*,
    while applying the action also moves regions that failed a gate and stretches
    of pattern no region entry covers.  So what is asserted is that the two agree
    in size and sign — which is the honest claim, and the reason the panel prints
    the observed value beside the predicted one instead of the prediction alone.
    """
    session, client, project = fresh
    before_nodes = len(project.history)
    chi2_before = project.refinement.result_.statistics.chi2
    rwp_before = project.refinement.result_.statistics.rwp

    status, payload = client.post("/api/report/apply", {"kind": "refine_cell"})
    assert status == 200, payload
    assert payload["state"] == "running"
    assert payload["applied"]["stage"]["name"] == "apply:refine_cell"
    assert payload["chi2_before"] == pytest.approx(chi2_before)
    undo = payload["undo"]
    assert undo == project.refinement._head_id or undo

    state = _wait_idle(client)
    assert state["run"]["status"] in ("converged", "max_iter"), state
    result = project.refinement.result_
    observed = chi2_before - result.statistics.chi2
    predicted = payload["applied"]["expected_delta_chi2"]
    assert observed > 0, "applying the cell suggestion did not improve the fit"
    assert result.statistics.rwp < rwp_before
    assert 0.3 < predicted / observed < 3.0, (predicted, observed)

    # one node, of kind `stage`, and its api_call is the line the route echoed
    assert len(project.history) == before_nodes + 1
    node = project.history[state["run"]["node_id"]]
    assert node.action.kind == "stage" and node.action.name == "apply:refine_cell"
    assert node.action.api_call() == payload["api_call"]

    # undo needs no inverse verb: the head before the apply is a node
    status, back = client.post("/api/history/checkout", {"node_id": undo})
    assert status == 200 and back["head"] == undo
    a = [r for r in back["parameters"] if r["path"] == "phases.0.cell.a"][0]
    assert a["value"] == pytest.approx(TRUE_A + 0.0005)

    # …and the applied node is still there to go back to
    client.post("/api/history/checkout", {"node_id": node.id})
    assert client.get("/api/params")[1]["head"] == node.id


def test_apply_refuses_what_the_report_refuses_and_says_which(narrow):
    """The route's refusals, with the codes a panel branches on."""
    _, client, _ = narrow
    # a kind this report does not suggest at all
    status, payload = client.post("/api/report/apply",
                                 {"kind": "refine_axial_asymmetry"})
    assert status == 404, payload
    assert payload["error"]["code"] == "NOT_FOUND"

    # an unknown kind is not a 500
    status, payload = client.post("/api/report/apply", {"kind": "make_it_better"})
    assert status in (400, 404) and payload["error"]["code"] == "NOT_FOUND"
    assert client.post("/api/report/apply", {})[0] == 400

    # vetoed and unreachable both answer 409 with the reason, not silence
    for kind in ("refine_scale", "refine_capillary_offset_along_beam"):
        status, payload = client.post("/api/report/apply", {"kind": kind})
        assert status == 409, (kind, payload)
        assert payload["error"]["code"] == "ACTION_NOT_APPLICABLE"
        assert payload["error"]["message"].startswith(f"{kind} cannot be applied")

    # a paths disambiguator that matches nothing is a 404 naming what is there
    status, payload = client.post("/api/report/apply",
                                 {"kind": "refine_cell", "paths": ["nope.*"]})
    assert status == 404 and payload["error"]["where"] == ["paths"]


def test_two_suggestions_of_one_kind_are_not_resolved_by_position(narrow):
    """Two textured phases emit two ``refine_preferred_orientation`` actions.

    ``FitReport.action`` returns the first match, which would free the wrong
    phase's March coefficient — so the route refuses and names the candidates
    instead of picking.  Asserted against the session verb with a hand-built
    report, because making a real two-phase textured fit would test the texture
    diagnostic rather than this rule.
    """
    from rietx.gui.session import GuiError, _pick_action

    report = rx.FitReport(rwp=0.1, gof=1.0, suggested_actions=[
        _action("refine_preferred_orientation", ["phases.0.preferred_orientation.r"]),
        _action("refine_preferred_orientation", ["phases.1.preferred_orientation.r"]),
    ])
    with pytest.raises(GuiError, match="send 'paths' to say which") as caught:
        _pick_action(report, "refine_preferred_orientation")
    assert caught.value.code == "AMBIGUOUS_ACTION"
    assert "phases.1.preferred_orientation.r" in caught.value.message

    picked = _pick_action(report, "refine_preferred_orientation",
                          ["phases.1.preferred_orientation.r"])
    assert picked.parameter_paths == ["phases.1.preferred_orientation.r"]
