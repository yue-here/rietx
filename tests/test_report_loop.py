"""Closed-loop FitReport usefulness eval (WP-1052): does *following* the report
converge anything?

The misfit-injection suite (``test_fitreport_layers.py``) measures whether the
report tells the truth about a planted cause.  This module measures the next
question: starting from a planted-cause state, repeatedly follow the report's
top surviving suggestion through the history DAG (``predict_then_verify``:
branch → verify stage → keep on >1 % χ² improvement → checkout winner /
structural rollback) and check that the planted *parameter* is recovered — Rwp
alone is never the criterion — that the loop stops when nothing actionable
remains, and that every rejection leaves the DAG clean.  It is the first
executable version of the agent skill's §9 (`references/history.md`)
canonical agent loop.

``_run_report_loop`` is a measurement instrument, not product: WP-1050's fence
holds verbatim — *"No automatic stage insertion: the staged runner stays
preset; suggest() informs a caller (human, GUI, or the agent loop), it does
not drive."*  Nothing importable from ``rietx`` may become an autopilot.

Honest framing for every baseline comparison here: on a synthetic single-cause
start every other parameter is already at truth, so "the loop freed fewer
parameters than ``mccusker_default``" means **the report localised the
cause**, never "report-driven refinement is cheaper".

Placement: fast suite, deliberately **no** ``xdist_group`` — the shared
``_truth()`` is cheap synthesis, not a fitted fixture, so grouping the
episodes would create a serial group rivalling the whole fast-suite wall.
The two real-data SRM 660c episodes are the exception: slow-marked and in
the ``srm660c`` group, because they consume the shared session fixture.
"""

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.report import predict_then_verify
from rietx.report.apply import recipe
from rietx.report.schemas import FitReport, VerificationOutcome
from rietx.strategy.staged import PLAN_PRESETS, RefinementPlan, Stage
from tests.test_fitreport_layers import _result_for, _truth

_OUT = Path(__file__).parent / "output"

#: hard stop on loop rounds — a runaway guard (tests/CLAUDE.md), never a timer
ROUND_CAP = 4
#: strict > over the collinearity cap (``confidence = min(confidence, 0.3)`` on
#: non-separable trends, layer2.py) — the loop never acts on an attribution the
#: report itself flagged non-separable
CONFIDENCE_FLOOR = 0.3
#: two consecutive rejections mean the report has nothing left worth trying
REJECTION_STOP = 2

#: mutually-substitutable cause families, as in the layers suite's
#: calibration-ensemble test — "the top suggestion is in the planted family"
#: is the success criterion, never "is exactly the planted kind"
POSITION_FAMILY = {"refine_zero_shift", "refine_sample_displacement",
                   "refine_sample_transparency", "refine_cell"}
WIDTH_FAMILY = {"refine_profile_widths", "refine_sample_size_broadening",
                "refine_sample_strain_broadening"}
SCALE_FAMILY = {"refine_scale", "refine_biso"}


# ----------------------------------------------------------------------
# the driver — a measurement instrument, private to this module
# ----------------------------------------------------------------------
@dataclass
class RoundRecord:
    """One report → select → verify round."""

    report: FitReport
    #: kind selected this round, None when nothing survived selection
    selected: str | None
    #: (kind, why) for every action ranked above the selection that was
    #: passed over; at a stopping round this covers the whole report
    blocked: list[tuple[str, str]]
    outcome: VerificationOutcome | None
    #: id of the accepted verify node (None on rejection/stop)
    verify_node: str | None
    #: working-state χ² after the round
    chi2: float


@dataclass
class EpisodeResult:
    ref: rx.Refinement
    rounds: list[RoundRecord] = field(default_factory=list)
    stop_reason: str = ""
    bootstrap_chi2: float = 0.0

    @property
    def accepted(self) -> list[str]:
        return [r.selected for r in self.rounds
                if r.outcome is not None and r.outcome.accepted]

    @property
    def rejected(self) -> list[str]:
        return [r.selected for r in self.rounds
                if r.outcome is not None and not r.outcome.accepted]

    @property
    def first_accepted(self) -> VerificationOutcome | None:
        for r in self.rounds:
            if r.outcome is not None and r.outcome.accepted:
                return r.outcome
        return None

    @property
    def final_chi2(self) -> float:
        return self.rounds[-1].chi2 if self.rounds else self.bootstrap_chi2

    @property
    def final_report(self) -> FitReport:
        return self.rounds[-1].report

    def blocked_kinds(self) -> list[str]:
        """Kinds passed over at the stopping round, report order."""
        return [k for k, _ in self.rounds[-1].blocked]

    def top_blocked_nonstage(self) -> str | None:
        """Highest-ranked action refused at the stopping round for not being
        a stage (the advice/index kinds) — what the loop points a human at
        when it stops itself."""
        for kind, why in self.rounds[-1].blocked:
            if why.startswith("how="):
                return kind
        return None


def _select(report: FitReport, rejected: set[str]):
    """First surviving action in report order (= confidence desc), with the
    reasons everything ranked above it was passed over.

    The four rules, in order: (i) active — ``Refinement.report()`` passes the
    working free set, so every previously-accepted action is auto-vetoed
    "already free", the built-in anti-thrash; (ii) a stage recipe — the index
    and advice kinds inform, they are not one ``run_stage``; (iii) strictly
    above the collinearity cap; (iv) not already rejected this episode
    (loop-local memory; correct for single-cause episodes only).
    """
    blocked: list[tuple[str, str]] = []
    for action in report.suggested_actions:
        if not action.active:
            blocked.append((action.kind, f"vetoed: {action.vetoed_by}"))
        elif recipe(action.kind).how != "stage":
            blocked.append((action.kind, f"how={recipe(action.kind).how}"))
        elif not action.confidence > CONFIDENCE_FLOOR:
            blocked.append((action.kind,
                            f"confidence {action.confidence} <= {CONFIDENCE_FLOOR}"))
        elif action.kind in rejected:
            blocked.append((action.kind, "rejected earlier this episode"))
        else:
            return action, blocked
    return None, blocked


def _run_report_loop(structure, instrument, data, *,
                     round_cap: int = ROUND_CAP) -> EpisodeResult:
    """Bootstrap fit, then follow the report until it stops itself.

    Bootstrap is a background-only stage: ``predict_then_verify`` needs a
    prior fit, and a zero-free-parameter solve won't run.  Each accepted
    action is followed by ``checkout`` of the verify node and one
    empty-``turn_on`` refit stage — ``checkout`` nulls ``_model``/``result_``
    and the refit re-establishes them without freeing anything
    (``set_vary([], True)`` frees nothing; ``_prepare_table(restore=True)``
    restores the node's free set).
    """
    ref = rx.Refinement(structure, instrument)
    ref.fit(data, plan=RefinementPlan(stages=[
        Stage("bootstrap", ["instrument.background.*"])]))
    episode = EpisodeResult(ref=ref, bootstrap_chi2=ref.result_.statistics.chi2)

    rejected: set[str] = set()
    consecutive_rejections = 0
    for _ in range(round_cap):
        report = ref.report()
        action, blocked = _select(report, rejected)
        if action is None:
            episode.rounds.append(RoundRecord(
                report=report, selected=None, blocked=blocked, outcome=None,
                verify_node=None, chi2=ref.result_.statistics.chi2))
            episode.stop_reason = "no_action"
            return episode

        parent_id = ref._head_id
        parent_chi2 = ref.result_.statistics.chi2
        outcome = predict_then_verify(ref, data, action)
        verify_node = None
        if outcome.accepted:
            # after an accepted trial the shared tree's HEAD *is* the verify
            # node (RefinementTree.add advances it; the parent's private head
            # stays put); VerificationOutcome carries no node id, so navigate
            # by HEAD and sanity-check the node is the one the action ran
            verify_node = ref.history.head
            node = ref.history[verify_node]
            assert node.action.kind == "stage", node.action
            assert node.action.name == f"verify:{action.kind}", node.action
            assert node.parents == [parent_id], (node.parents, parent_id)
            ref.checkout(verify_node)
            ref.run_stage(data, Stage(f"refit:{action.kind}", []))
            consecutive_rejections = 0
        else:
            # structural rollback: the parent working state is untouched, bit
            # for bit, and the trial is at most a dead leaf in the DAG
            assert ref._head_id == parent_id
            assert ref.result_.statistics.chi2 == parent_chi2
            rejected.add(action.kind)
            consecutive_rejections += 1
        episode.rounds.append(RoundRecord(
            report=report, selected=action.kind, blocked=blocked,
            outcome=outcome, verify_node=verify_node,
            chi2=ref.result_.statistics.chi2))
        if consecutive_rejections >= REJECTION_STOP:
            episode.stop_reason = "two_rejections"
            return episode
    episode.stop_reason = "round_cap"
    return episode


# ----------------------------------------------------------------------
# shared assertions and helpers
# ----------------------------------------------------------------------
def _truth_chi2(structure, instrument, data) -> float:
    """χ² of a model state evaluated (not refined) against ``data`` — the
    noise floor when called with the truth models."""
    result, _, _ = _result_for(structure, instrument, data)
    return result.statistics.chi2


def _dead_verify_leaves(tree) -> list:
    """Rejected trials: verify nodes nothing ever built on."""
    return [n for n in tree.leaves()
            if n.action.kind == "stage"
            and (n.action.name or "").startswith("verify:")]


def _assert_dag_hygiene(episode: EpisodeResult) -> None:
    """The DAG as audit trail, not scenery.

    Every rejection that got as far as a solve leaves exactly one dead leaf
    whose ``history.compare`` row shows it improved < 1 % over its parent —
    the acceptance criterion, read back out of the record.  (A trial that
    *failed* to solve is a rejection with no node, so the leaf count is the
    count of "rolled back" rejections, not of all rejections.)
    """
    tree = episode.ref.history
    leaves = _dead_verify_leaves(tree)
    rolled_back = [r for r in episode.rounds
                   if r.outcome is not None and not r.outcome.accepted
                   and "rolled back" in r.outcome.reason]
    assert len(leaves) == len(rolled_back), (
        f"{len(rolled_back)} rolled-back rejections but {len(leaves)} dead "
        f"verify leaves: {[n.id for n in leaves]}")
    for leaf in leaves:
        assert len(leaf.parents) == 1, leaf.parents
        parent_row, leaf_row = tree.compare([leaf.parents[0], leaf.id])
        improvement = parent_row["chi2"] - leaf_row["chi2"]
        assert improvement <= 0.01 * abs(parent_row["chi2"]), (
            f"dead leaf {leaf.id} improved {improvement:.4g} over its parent "
            f"({parent_row['chi2']:.4g}) — that should have been accepted")


#: measured pred/obs Δχ² ratios on the first accepted action of E1–E4:
#: 0.79, 0.85, 1.16, 0.79 (2026-08-11, this fixture).  The estimate covers
#: only the gated regions and assumes the linear model exact, so a broad band
#: is the honest pin — the assertion is "the prediction is an estimate, not a
#: fabrication", not "the estimate is accurate".
PREDICTION_BAND = (0.3, 3.0)


def _assert_prediction_band(episode: EpisodeResult) -> None:
    """predicted/observed Δχ² on the **first** accepted action only —
    ``expected_delta_chi2`` is one number per report, stamped on every
    Layer-1 action, so later rounds' predictions describe misfit the earlier
    accepted action already removed.  Skipped when the report carried no
    prediction (texture actions; abstained reports)."""
    outcome = episode.first_accepted
    if outcome is None or outcome.predicted_delta_chi2 is None:
        return
    ratio = outcome.predicted_delta_chi2 / outcome.observed_delta_chi2
    lo, hi = PREDICTION_BAND
    assert lo <= ratio <= hi, (
        f"predicted {outcome.predicted_delta_chi2:.4g} vs observed "
        f"{outcome.observed_delta_chi2:.4g} (ratio {ratio:.2f})")


def _plot(episode: EpisodeResult, stem: str) -> None:
    """obs/calc/diff PNGs to tests/output/ (gitignored), full range + a
    low-angle zoom — Rwp hides locally-bad fits (house convention)."""
    from rietx.viz.plots import plot_result

    _OUT.mkdir(exist_ok=True)
    result = episode.ref.result_
    plot_result(result, path=str(_OUT / f"{stem}.png"))
    plot_result(result, path=str(_OUT / f"{stem}_zoom.png"),
                two_theta_range=(18.0, 45.0))


def _actions_in_order(report: FitReport) -> list[str]:
    return [a.kind for a in report.suggested_actions]


# ----------------------------------------------------------------------
# fixtures
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def truth():
    return _truth()


# ----------------------------------------------------------------------
# E1 — zero shift: the loop's canonical accepted round
# ----------------------------------------------------------------------
def test_e1_zero_shift_loop(truth):
    """A 0.008° zero error: one accepted ``refine_zero_shift`` round, the
    planted parameter recovered, nothing wrong kept, and the final state at
    least as good as every other leaf in the DAG."""
    structure, ins, data = truth
    start = ins.model_copy(deep=True)
    start.zero_shift.value = 0.008

    episode = _run_report_loop(structure, start, data)

    # pre-loop calibration transfer: the bootstrap's background stage can
    # absorb part of the planted misfit, so the loop's starting report is not
    # the layers suite's unrefined state — establish, don't assume, that the
    # planted family is still top-ranked after the bootstrap
    report0 = episode.rounds[0].report
    assert report0.layer1_available, report0.abstained_reason
    assert _actions_in_order(report0)[0] in POSITION_FAMILY, (
        _actions_in_order(report0))

    assert episode.accepted == ["refine_zero_shift"], (
        episode.accepted, episode.rejected, episode.stop_reason)

    # recovery is the planted *parameter* at truth, never Rwp alone
    zero = episode.ref.fitted_instrument.zero_shift.value
    assert zero == pytest.approx(0.0, abs=0.002), zero

    # nothing else on the instrument moved off its start
    disp = episode.ref.fitted_instrument.geometry.sample_displacement.value
    assert disp == 0.0, disp

    # the accepted branch is the best leaf (within the keep threshold), and it
    # sits at the noise floor — the χ² of the *truth* model on this noise
    assert episode.final_chi2 <= 1.05 * _truth_chi2(structure, ins, data)
    stats_leaves = [n.metrics.statistics.chi2
                    for n in episode.ref.history.leaves()
                    if n.metrics.statistics is not None]
    assert episode.final_chi2 <= 1.01 * min(stats_leaves), (
        episode.final_chi2, min(stats_leaves))

    _assert_dag_hygiene(episode)
    _assert_prediction_band(episode)
    _plot(episode, "report_loop_e1")


def test_e1_zero_shift_baseline(truth):
    """``mccusker_default`` recovers the same start too (its ``zero`` stage
    frees exactly the planted parameter) — the contrast with the loop is
    localisation, not capability: the preset also frees scale, cell and the
    whole profile block on a state where those were already at truth.

    The preset is passed as an object: by name, a Bragg-Brentano instrument
    also frees the displacement beside the zero (WP-2015), and this baseline
    is about the preset's own ``zero`` stage."""
    structure, ins, data = truth
    start = ins.model_copy(deep=True)
    start.zero_shift.value = 0.008

    ref = rx.Refinement(structure, start)
    ref.fit(data, plan=PLAN_PRESETS["mccusker_default"]())
    assert ref.fitted_instrument.zero_shift.value == pytest.approx(0.0, abs=0.002)


# ----------------------------------------------------------------------
# E2 — sample displacement: the cause the baseline cannot reach
# ----------------------------------------------------------------------
def test_e2_sample_displacement_loop(truth):
    """A −0.02 mm displacement (cosθ signature, separable from a constant
    zero over 18–125° 2θ): the report names ``refine_sample_displacement``
    and the loop frees exactly that."""
    structure, ins, data = truth
    start = ins.model_copy(deep=True)
    start.geometry.sample_displacement.value = -0.02

    episode = _run_report_loop(structure, start, data)

    report0 = episode.rounds[0].report
    assert report0.layer1_available, report0.abstained_reason
    assert _actions_in_order(report0)[0] in POSITION_FAMILY, (
        _actions_in_order(report0))

    assert episode.accepted == ["refine_sample_displacement"], (
        episode.accepted, episode.rejected, episode.stop_reason)
    disp = episode.ref.fitted_instrument.geometry.sample_displacement.value
    assert disp == pytest.approx(0.0, abs=0.005), disp
    # the collinear rival was never touched, and the fit is at the noise floor
    assert episode.ref.fitted_instrument.zero_shift.value == 0.0
    assert episode.final_chi2 <= 1.05 * _truth_chi2(structure, ins, data)

    _assert_dag_hygiene(episode)
    _assert_prediction_band(episode)
    _plot(episode, "report_loop_e2")


def test_e2_sample_displacement_baseline(truth):
    """The structural miss: no ``mccusker_default`` stage frees
    ``instrument.geometry.sample_displacement`` (only the ``lab_*`` plans
    do), so the planted cause survives the whole preset untouched.

    Measured contrast, which is the point of this episode: the preset still
    lands at χ²_red ≈ 1.01 — its ``zero`` stage absorbs the cosθ shift with a
    compensating zero_shift ≈ −0.011° (truth 0) while the displacement stays
    wrong — so the fit *looks* as good as the loop's while carrying two wrong
    parameters.  Rwp alone cannot distinguish them; the parameter values do.

    Since WP-2015 the *name* ``"mccusker_default"`` on a Bragg-Brentano
    instrument frees the displacement with the zero, which closes this miss;
    the preset object, which runs as given, is what is measured here.
    """
    structure, ins, data = truth
    start = ins.model_copy(deep=True)
    start.geometry.sample_displacement.value = -0.02

    ref = rx.Refinement(structure, start)
    ref.fit(data, plan=PLAN_PRESETS["mccusker_default"]())
    assert ref.fitted_instrument.geometry.sample_displacement.value == -0.02
    # the compensation is real: zero was dragged off truth to cover for it
    assert abs(ref.fitted_instrument.zero_shift.value) > 0.005


def test_e2_one_json_call_names_the_cause(truth):
    """WP-1058's acceptance: one fit on the E2 model, asking for the
    trajectory, comes back naming the displacement family.
    (``report_trajectory`` defaulted on when this landed; WP-1003 flipped it
    on WP-1064's measured criterion, so the one call now asks explicitly —
    what is asserted here is the *content*, which the flip does not touch.)

    The call was ``refine_json`` until WP-1303 and the answer is read here the
    way that retirement prescribes: run the fit, ask for the report, and dump
    both with ``model_dump(mode="json")``.  Every assertion below is on the
    JSON, unchanged — which is the point, since the envelope only ever wrapped
    these same dumps.

    The two halves are what the answer is made of, and neither is the other:

    * the **converged** report's action list is empty, and the fitted
      parameter that carries the error is not even in ``result.parameters``
      (the vary-or-tie filter: ``sample_displacement`` was never freed).  What
      it *does* say is WP-1056's: ``zero_shift`` stands ~128σ from zero and is
      exchangeable with the held displacement — a stated ambiguity, not a
      cause;
    * the **first rung** of the same call's trajectory resolves it: over
      18–125° the cosθ template fits at R² ≈ 1.00 and ``refine_sample_``
      ``displacement`` comes back at ~0.997, because at that state the two are
      still separable.

    In the pilot the second half existed and reached nobody — no agent ever
    generated a state where the report could say it.  One call that asks
    carries it.

    The preset runs as an object, as in the baseline above: by name, a
    Bragg-Brentano instrument frees the displacement too (WP-2015).
    """
    structure, ins, data = truth
    start = ins.model_copy(deep=True)
    start.geometry.sample_displacement.value = -0.02

    ref = rx.Refinement(structure, start)
    plan = PLAN_PRESETS["mccusker_default"]()
    result = ref.fit(data, plan=plan, stage_reports=True)
    out = {
        "result": result.model_dump(mode="json"),
        "report": ref.report(plan=plan).model_dump(mode="json"),
        "trajectory": [rung.model_dump(mode="json")
                       for rung in ref.stage_reports_],
    }

    # half one: converged-looking, no action, and the culprit not even listed
    assert out["result"]["statistics"]["rwp"] < 0.02
    assert out["report"]["suggested_actions"] == []
    assert "instrument.geometry.sample_displacement" not in [
        p["path"] for p in out["result"]["parameters"]]
    exchange = next(e for e in out["report"]["identifiability"]["exchanges"]
                    if e["held"] == "instrument.geometry.sample_displacement")
    assert exchange["exchangeable"] is True
    assert exchange["partner"] == "instrument.zero_shift"
    assert exchange["partner_significance"] > 100.0

    # half two: the same call's first rung, where the two are still separable
    rung = out["trajectory"][0]
    assert rung["stage"] == "scale_bkg"
    kinds = [a["kind"] for a in rung["actions"]]
    assert kinds[0] in POSITION_FAMILY, kinds
    assert "refine_sample_displacement" in kinds, kinds
    top = rung["actions"][0]
    assert top["confidence"] > CONFIDENCE_FLOOR, top
    assert top["parameter_paths"] == ["instrument.geometry.sample_displacement"]

    # the answer is still an ordinary result: it round-trips and it plots
    _OUT.mkdir(exist_ok=True)
    from rietx.schemas.results import RefinementResult
    from rietx.viz.plots import plot_result

    plot_result(RefinementResult.model_validate(out["result"]),
                path=str(_OUT / "report_loop_e2_json_call.png"))


# ----------------------------------------------------------------------
# E3 — profile.w halved: Voigt compensation, and the emitter gap
# ----------------------------------------------------------------------
def test_e3_width_error_loop(truth):
    """Peaks too narrow (w = 2e-3, truth 4e-3): the loop recovers the planted
    instrument Gaussian — the WP-1106 emitter closing the gap this test used
    to document.  The two rounds are the design working in sequence.  Round
    one accepts the sample-side reading (``refine_sample_size_broadening``,
    the Voigt proxy): Lorentzian sample broadening absorbs most of the FWHM
    deficit, χ²_red ≈15.1 → ≈4.3, and stalls there because a Lorentzian FWHM
    cannot reproduce a Gaussian variance deficit.  Round two takes the
    instrument-side peer the same width trend now carries
    (``refine_profile_widths`` over the Gaussian U/V/W — emitted at half the
    sample action's confidence, the calibrate-on-a-standard protocol
    discount), frees the planted parameter, and lands the noise floor:
    measured 4.30 → 1.0105 against a truth floor of 1.0099, with w back at
    3.95e-3 and the proxy's ``lor_size`` collapsed to ~1.4e-4.  Before the
    emitter the loop stopped at 4.3 with the width trend still standing at
    7σ and nothing left to name it.
    """
    structure, ins, data = truth
    start = ins.model_copy(deep=True)
    start.profile.w.value = 2.0e-3

    episode = _run_report_loop(structure, start, data)

    report0 = episode.rounds[0].report
    assert report0.layer1_available, report0.abstained_reason
    assert _actions_in_order(report0)[0] in WIDTH_FAMILY, (
        _actions_in_order(report0))

    # the sample proxy first (protocol order), then the instrument side
    assert episode.accepted == ["refine_sample_size_broadening",
                                "refine_profile_widths"], (
        episode.accepted, episode.rejected, episode.stop_reason)
    # the planted parameter is freed and recovered (same bar as the
    # mccusker_default baseline below)
    w = episode.ref.fitted_instrument.profile.w.value
    assert w == pytest.approx(4.0e-3, rel=0.20), w
    # …and the loop now reaches the noise floor the proxy alone missed by 4×
    # (measured ratio 1.0006; the 1.05 factor is E4's, margin ~80×)
    assert episode.final_chi2 <= 1.05 * _truth_chi2(structure, ins, data), (
        episode.final_chi2)

    _assert_dag_hygiene(episode)
    _assert_prediction_band(episode)
    _plot(episode, "report_loop_e3")


def test_e3_width_error_baseline(truth):
    """The reference arm the loop is measured against: ``mccusker_default``'s
    ``profile_w`` stage frees the planted parameter directly and lands w back
    at truth in one plan.  Until WP-1106 this arm *beat* the loop — the
    report localised the misfit to the width family but had no emitter naming
    the instrument Gaussian, so the loop's proxy correction stalled at
    χ²_red ≈4.3.  Both routes now recover w; this arm keeps the recovery bar
    itself independent of the emitter under test."""
    structure, ins, data = truth
    start = ins.model_copy(deep=True)
    start.profile.w.value = 2.0e-3

    ref = rx.Refinement(structure, start)
    ref.fit(data, plan="mccusker_default")
    w = ref.fitted_instrument.profile.w.value
    assert w == pytest.approx(4.0e-3, rel=0.20), w


# ----------------------------------------------------------------------
# E4 — scale ×0.90: the intensity-family accepted round
# ----------------------------------------------------------------------
def test_e4_scale_error_loop(truth):
    """A 10 % scale deficit: ``refine_scale`` accepted, scale recovered to
    truth, nothing wrong kept."""
    structure, ins, data = truth
    start = structure.model_copy(deep=True)
    start.phases[0].scale.value = 4e-4 * 0.90

    episode = _run_report_loop(start, ins, data)

    report0 = episode.rounds[0].report
    assert report0.layer1_available, report0.abstained_reason
    assert _actions_in_order(report0)[0] in SCALE_FAMILY, (
        _actions_in_order(report0))

    assert episode.accepted == ["refine_scale"], (
        episode.accepted, episode.rejected, episode.stop_reason)
    scale = episode.ref.fitted_structure.phases[0].scale.value
    assert scale == pytest.approx(4e-4, rel=0.02), scale
    assert episode.final_chi2 <= 1.05 * _truth_chi2(structure, ins, data)

    _assert_dag_hygiene(episode)
    _assert_prediction_band(episode)
    _plot(episode, "report_loop_e4")


def test_e4_scale_error_baseline(truth):
    """The preset's ``scale_bkg`` stage recovers it too — localisation
    framing only, as for E1."""
    structure, ins, data = truth
    start = structure.model_copy(deep=True)
    start.phases[0].scale.value = 4e-4 * 0.90

    ref = rx.Refinement(start, ins)
    ref.fit(data, plan="mccusker_default")
    assert ref.fitted_structure.phases[0].scale.value == pytest.approx(
        4e-4, rel=0.02)


# ----------------------------------------------------------------------
# E5 — impurity spike: the loop must stop and point at the advice
# ----------------------------------------------------------------------
def test_e5_impurity_stops_the_loop(truth):
    """A Gaussian spike no reflection accounts for: nothing to refine, so the
    loop keeps nothing and stops with ``add_impurity_phase`` as the top
    refused non-stage kind — the hand-back to a caller who can name a phase.

    Rejections are budgeted, not forbidden: measured here, the spike's
    intensity misfit reads as a March-Dollase texture false-positive
    (``refine_preferred_orientation`` at confidence ≈0.76), which
    ``predict_then_verify`` rejects at +0.00 % — the verify machinery doing
    exactly its job on an incidental sub-cause.
    """
    structure, ins, data = truth
    tt = np.asarray(data.two_theta)
    y = np.asarray(data.intensity, dtype=float)
    y = y + 900.0 * np.exp(-0.5 * ((tt - 29.35) / 0.06) ** 2)
    doped = rx.PatternData(two_theta=tt.tolist(), intensity=y.tolist(),
                           sigma=data.sigma)

    episode = _run_report_loop(structure, ins, doped)

    # pre-loop: the model-free evidence survives the bootstrap
    report0 = episode.rounds[0].report
    assert "add_impurity_phase" in _actions_in_order(report0)

    assert episode.accepted == [], (episode.accepted, episode.stop_reason)
    assert episode.stop_reason == "no_action", episode.stop_reason
    assert episode.top_blocked_nonstage() == "add_impurity_phase", (
        episode.rounds[-1].blocked)
    # the peak is still in the final report — stopping did not bury it
    assert any(u.kind == "unmatched_obs" and abs(u.two_theta - 29.35) < 0.15
               for u in episode.final_report.unmatched)

    _assert_dag_hygiene(episode)
    _plot(episode, "report_loop_e5")


# ----------------------------------------------------------------------
# E6 — cell +0.4 %: shift-based corrections must never be applied
# ----------------------------------------------------------------------
def test_e6_wrong_cell_applies_no_position_action(truth):
    """A 0.4 % cell error moves peaks many FWHM: the loop must never apply a
    shift-based position correction to a wrong cell, and it doesn't.

    Measured (2026-08-11): after the background bootstrap the whole report
    **abstains** (Rwp 0.716 > 0.35) — 11 of 15 regions trip the validity
    radius, and abstention outranks per-region gating.  WP-1052 recorded a
    finding here: ``reindex_or_recheck_cell`` was emitted only by the mature
    branch (``far and rwp > 0.2``), so the abstained report surfaced
    ``add_impurity_phase`` at 0.9 alone — the phantom-phase invitation a real
    model consumed in WP-1053's pilot.  **WP-1054 is the fix of that
    finding**, and this test now pins the fixed behaviour: the shared emitter
    (``layer2.reindex_action``, on widespread validity failure — measured
    here 11 of 15 misfitting regions, count fraction 0.73) emits the reindex
    pointer on the abstained branch, top-ranked at 0.4, carrying the whole
    position family in ``alternatives``; the impurity call is capped at 0.3
    because every strong unmatched peak pairs with a missing calculated line
    (32 displaced pairs measured at 0.12–0.82°).  Both are non-stage kinds
    (``index``/``advice``), so the loop still selects nothing and stops — but
    the hand-back now points a caller at re-indexing, not at a phantom phase.

    Baseline (recorded, not asserted — the contrast is the point): the blunt
    ``mccusker_default`` cell stage *rescues* this start — a → 4.156604
    (23 ppm from truth), Rwp 0.0137, zero ≈ 1.4e-4° — where the report-driven
    loop refuses to touch it.  A preset that happens to free the right
    parameter beats a report that correctly refuses to linearise; that is a
    statement about this start being inside the cell stage's basin, not about
    the refusal being wrong.
    """
    from rietx.report.schemas import IMPURITY_SHIFT_CAP

    structure, ins, data = truth
    start = structure.model_copy(deep=True)
    start.phases[0].cell = rx.Cell.cubic(4.1568 * 1.004)

    episode = _run_report_loop(start, ins, data)

    report0 = episode.rounds[0].report
    assert not report0.layer1_available, "expected abstention on a wrong cell"
    tripped = [a for a in report0.attribution
               if any(f.code == "outside_validity_radius"
                      for f in a.gate_failures)]
    assert tripped, "gross peak offsets did not trip the validity radius"

    assert episode.accepted == [], (episode.accepted, episode.stop_reason)
    for r in episode.rounds:
        assert r.selected not in POSITION_FAMILY, r.selected
        assert not (set(_actions_in_order(r.report)) & POSITION_FAMILY), (
            "an abstained report emitted a position action")
    assert episode.stop_reason == "no_action", episode.stop_reason

    # the WP-1052 finding, fixed by WP-1054: the abstained report leads with
    # the reindex pointer, and the loop's hand-back names it
    final = episode.final_report
    assert _actions_in_order(final)[0] == "reindex_or_recheck_cell", (
        _actions_in_order(final))
    assert episode.top_blocked_nonstage() == "reindex_or_recheck_cell", (
        episode.rounds[-1].blocked)
    impurity = final.action("add_impurity_phase")
    assert impurity.confidence <= IMPURITY_SHIFT_CAP, impurity
    assert impurity.alternatives[0] == "reindex_or_recheck_cell", impurity

    _assert_dag_hygiene(episode)
    _plot(episode, "report_loop_e6")


# ----------------------------------------------------------------------
# E7 — hopeless start: abstain and do nothing
# ----------------------------------------------------------------------
def test_e7_hopeless_start_abstains_and_stops(truth):
    """Cell at 4.60 Å (nowhere near) and scale ÷10: the report must abstain
    and the loop must apply nothing — not even a trial.  Measured: the
    abstention fires the explained-fraction gate here (only 26 % of the
    misfitting χ² sits in gate-passing regions) rather than the Rwp gate the
    layers suite's un-bootstrapped state trips; either way
    ``abstained_reason`` is set, which is what the loop keys off."""
    structure, ins, data = truth
    start = structure.model_copy(deep=True)
    start.phases[0].cell = rx.Cell.cubic(4.60)
    start.phases[0].scale.value = 4e-5

    episode = _run_report_loop(start, ins, data)

    report0 = episode.rounds[0].report
    assert report0.abstained_reason, "a hopeless start must abstain"

    assert episode.accepted == [], episode.accepted
    assert len(episode.rounds) == 1 and episode.rounds[0].selected is None, (
        "zero stages — not even a trial — after bootstrap")
    assert episode.stop_reason == "no_action", episode.stop_reason

    _assert_dag_hygiene(episode)
    _plot(episode, "report_loop_e7")


# ----------------------------------------------------------------------
# E8 — collinear window: the confidence cap holds the line
# ----------------------------------------------------------------------
def test_e8_collinear_window_applies_no_position_action():
    """Over 20–56° 2θ the position templates are collinear (measured
    |r| ≈ 0.9995 in the layers suite): every position action is capped at
    exactly 0.3, the strict ``>`` floor refuses them all, and no position
    kind is ever applied — never-a-confident-wrong-singleton, closed-loop.

    The measured incidental (allowed by design, worth knowing): the axial-
    divergence shape term absorbs much of a constant 0.02° shift over this
    short window — ``refine_axial_asymmetry`` (fixed confidence 0.5, a
    different observable from the position trend, so the collinearity cap
    never sees it) is accepted at χ²_red 170.8 → 51.3.  The keep-threshold
    is doing its job on a genuinely-improving proxy; the line the episode
    holds is that no *position* attribution the report itself called
    non-separable is ever acted on.
    """
    structure, ins, data = _truth(lo=20.0, hi=56.0, seed=23)
    start = ins.model_copy(deep=True)
    start.zero_shift.value = 0.02

    episode = _run_report_loop(structure, start, data)

    # pre-loop: the cap held at the bootstrap state (the layers suite skips
    # when this state abstains; measured here it does not — assert, so a
    # future abstention is a visible change rather than a silent skip)
    report0 = episode.rounds[0].report
    assert report0.layer1_available, report0.abstained_reason
    for action in report0.suggested_actions:
        if action.kind in POSITION_FAMILY:
            assert action.confidence <= CONFIDENCE_FLOOR, action

    for r in episode.rounds:
        assert r.selected not in POSITION_FAMILY, r.selected
    assert not (set(episode.accepted) & POSITION_FAMILY), episode.accepted
    assert episode.stop_reason, "stop reason must be recorded"
    # the planted zero was never touched: still exactly the injection
    assert episode.ref.fitted_instrument.zero_shift.value == 0.02

    _assert_dag_hygiene(episode)
    _assert_prediction_band(episode)
    _plot(episode, "report_loop_e8")


# ----------------------------------------------------------------------
# stretch: the loop off synthetic — two real-data episodes, one honest pair
# ----------------------------------------------------------------------
@pytest.mark.slow
@pytest.mark.xdist_group("srm660c")
def test_srm660c_degraded_zero_is_refused(srm660c_baseline):
    """Real data, and the cap holds where the true cause is *in* the capped
    set: the NIST SRM 660c converged state (CuKα doublet, measured esd
    column) with its zero knocked to +0.01° — and the loop refuses to act.

    Measured (2026-08-11): every position action comes back at or under the
    0.3 collinearity cap (displacement at exactly 0.3, zero at 0.254) — on
    this pattern a constant shift is genuinely not separable from the
    protocol's fitted −0.08 mm displacement, unlike the synthetic 18–125°
    fixture where the same injection separates cleanly.  So the loop stops at
    round 0 and χ²_red stays at the degraded 16.1: **safe, not complete**.  A
    preset's zero/displacement stage would fix this start; the loop's refusal
    is the never-act-on-a-non-separable-attribution rule paying its real
    price, and the report hands the capped pair (with alternatives) to a
    caller who can hold one of the two — the skill's §6
    (`references/abstention.md`), closed-loop.

    (``add_impurity_phase`` at 0.4 outranks the capped family — the shift's
    derivative-shaped residuals read as unindexed lines — but it is advice,
    so selection skips it; on synthetic starts the same false positive never
    outranks the planted family.)
    """
    data, baseline_ref, _ = srm660c_baseline
    structure = baseline_ref.structure.model_copy(deep=True)
    start = baseline_ref.instrument.model_copy(deep=True)
    start.zero_shift.value = 0.01

    episode = _run_report_loop(structure, start, data)

    report0 = episode.rounds[0].report
    assert report0.layer1_available, report0.abstained_reason
    position = [a for a in report0.suggested_actions
                if a.kind in POSITION_FAMILY]
    assert position, "the position family must at least be suggested"
    for action in position:
        assert action.confidence <= CONFIDENCE_FLOOR, action

    assert episode.accepted == [] and episode.rejected == [], (
        episode.accepted, episode.rejected)
    assert episode.stop_reason == "no_action", episode.stop_reason
    # nothing moved: the injection survives, bit for bit
    assert episode.ref.fitted_instrument.zero_shift.value == 0.01
    assert episode.final_chi2 == episode.bootstrap_chi2

    _assert_dag_hygiene(episode)
    _plot(episode, "report_loop_srm660c_zero")


@pytest.mark.slow
@pytest.mark.xdist_group("srm660c")
def test_srm660c_degraded_scale_loop(srm660c_baseline):
    """And the loop *closes* on real data when the cause is separable: the
    same converged state with scale ×0.90 — ``refine_scale`` top-ranked
    (0.85), accepted (χ²_red 6.90 → 3.48, this protocol's own converged
    floor), the scale recovered to ppm of the fixture's converged value, and
    a clean stop.  Together with the zero episode above this is the honest
    real-data pair: refusal where the report cannot separate, recovery where
    it can."""
    data, baseline_ref, _ = srm660c_baseline
    structure = baseline_ref.structure.model_copy(deep=True)
    truth_scale = baseline_ref.structure.phases[0].scale.value
    structure.phases[0].scale.value = truth_scale * 0.90
    start = baseline_ref.instrument.model_copy(deep=True)

    episode = _run_report_loop(structure, start, data)

    report0 = episode.rounds[0].report
    assert report0.layer1_available, report0.abstained_reason
    assert _actions_in_order(report0)[0] in SCALE_FAMILY, (
        _actions_in_order(report0))

    assert episode.accepted == ["refine_scale"], (
        episode.accepted, episode.rejected, episode.stop_reason)
    scale = episode.ref.fitted_structure.phases[0].scale.value
    assert scale == pytest.approx(truth_scale, rel=0.01), (scale, truth_scale)

    _assert_dag_hygiene(episode)
    _assert_prediction_band(episode)
    _plot(episode, "report_loop_srm660c_scale")
