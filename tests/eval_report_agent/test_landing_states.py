"""Round-3 landing states: every expected answer is a measurement.

PROTOCOL.md 2.0 § Episodes registers each row's verifying measurement and its
decision band; this suite pins them at the states the episodes' default paths
land on — the measure → register → run ordering rule, as tests.  A row that
stops clearing its band is a fixture to redesign and re-register, never a
truth file to edit on sight (tests/CLAUDE.md § "An eval's expected answer is
a measurement").  All numbers quoted in docstrings were measured 2026-08-13,
``[dev]`` venv, darwin/arm64.

Everything here runs real fits, so the module is slow; each dataset gets its
own xdist group — none shares a pytest fixture with the acceptance suites,
so separate groups are free (tests/CLAUDE.md § Shared fixtures).
"""

from pathlib import Path

import pytest

import rietx as rx
from rietx.report import compare_rivals
from rietx.schemas.plan import PlanSpec
from rietx.strategy.staged import PLAN_PRESETS
from tests.eval_report_agent import build_fixtures as bf

pytestmark = pytest.mark.slow

OUT = Path(__file__).resolve().parents[1] / "output"

#: the registered decision bands (PROTOCOL.md 2.0 § Decision bands)
TIE_BAND = (0.99, 1.01)
DECISIVE_MIN = 1.10

DISP = "instrument.geometry.sample_displacement"
ZERO = "instrument.zero_shift"


def _models(core):
    """The episode core, back through the schemas — the same JSON round-trip
    the agent's shim performs, so a core that stopped validating fails here
    first."""
    return (rx.Structure.model_validate(core["structure"]),
            rx.Instrument.model_validate(core["instrument"]),
            rx.PatternData.model_validate(core["pattern"]))


def _fit_default(core, **kw):
    """The lazy path: the episode start under ``mccusker_default``, honouring
    a protocol-level limits key where the core carries one (W1).

    The preset runs as an object, the path these rows were registered on: by
    name, a Bragg-Brentano instrument also frees the displacement beside the
    zero (WP-2015), which is the plant N1, C1 and E8p hold."""
    structure, ins, data = _models(core)
    if "two_theta_limits" in core:
        kw.setdefault("two_theta_limits", tuple(core["two_theta_limits"]))
    ref = rx.Refinement(structure, ins)
    return ref, ref.fit(data, plan=PLAN_PRESETS["mccusker_default"](), **kw), data


def _plot(result, stem):
    OUT.mkdir(exist_ok=True)
    result.plot(path=str(OUT / f"{stem}.png"))
    import matplotlib.pyplot as plt

    plt.close("all")


def _rival_state(ref, data, freed, held):
    """One side of the swap: ``freed`` alone, ``held`` at its null — the
    experiment the 0.8 clause names, as a branch whose report can be read."""
    trial = ref.branch()
    trial.set_vary([held], False)
    trial.set_values({held: 0.0})
    trial.set_vary([freed], True)
    trial.run_stage(data, rx.Stage(f"swap:{freed}", [freed]))
    return trial


# ----------------------------------------------------------------------
# the SRM 660c trio: N1, C1 (R2 rides the same baseline)
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def srm_trio():
    try:
        return bf.build_real_episodes()
    except FileNotFoundError as exc:
        pytest.skip(str(exc))


@pytest.mark.xdist_group("eval-srm660c")
def test_srm_trio_reads_truth_off_the_baseline(srm_trio):
    """Truth values are read off the baseline fit, never hard-coded: N1 and
    C1 share the knocked instrument and differ only in the pattern (N1's is
    the truncated subset — nothing to widen into), R2 moves only the scale.
    C1 is the row with the restored tolerance; N1's planted value is
    recorded, never graded."""
    n1 = srm_trio["N1"]["truth"]
    c1 = srm_trio["C1"]["truth"]
    r2 = srm_trio["R2"]["truth"]
    assert n1["planted"]["truth"] == c1["planted"]["truth"]
    # -0.0801 until WP-1938.  The SRM 660c baseline now holds Γ_G² ≥ 1e-8 deg²
    # at every reflection, where the TRF answer's Caglioti quadratic went
    # negative above 2θ ≈ 134°, and the displacement moved to -0.0791.
    assert c1["planted"]["truth"] == pytest.approx(-0.0791, abs=5e-4)
    assert n1["planted"]["tol"] is None
    assert c1["planted"]["tol"] == {"abs": bf.C1_DISP_TOL}
    assert r2["planted"]["start"] == pytest.approx(
        0.90 * r2["planted"]["truth"], rel=1e-12)
    assert (srm_trio["C1"]["core"]["pattern"]
            == srm_trio["R2"]["core"]["pattern"])
    n1_tt = srm_trio["N1"]["core"]["pattern"]["two_theta"]
    assert len(n1_tt) < len(srm_trio["C1"]["core"]["pattern"]["two_theta"])
    assert n1_tt[-1] <= bf.N1_MAX_TWO_THETA
    assert (srm_trio["N1"]["core"]["instrument"]["geometry"]
            ["sample_displacement"]["value"] == -0.02)


@pytest.mark.xdist_group("eval-srm660c")
def test_n1_window_ties_and_no_reachable_state_is_quiet(srm_trio):
    """N1's registration: on the ≤56° window the zero/displacement rivals tie
    within [0.99, 1.01] (measured 1.0075) and the exchange clause fires at
    the default-plan landing state (measured Rwp 0.10106, zero +0.0251) and
    at both single-rival states — no reachable state is correctly quiet, and
    the aberration is in the *data*, so E8's failure mode (a default stage
    freeing the plant and landing quiet) cannot recur."""
    ref, result, data = _fit_default(srm_trio["N1"]["core"])
    assert result.status == "converged"
    assert "held at its null" in ref.report().summary
    _plot(result, "eval_n1_landing")

    comp = compare_rivals(ref, data, (DISP, ZERO))
    ratio = comp.rivals[1].chi2 / comp.rivals[0].chi2
    assert TIE_BAND[0] <= ratio <= TIE_BAND[1], ratio

    for freed, held in ((DISP, ZERO), (ZERO, DISP)):
        trial = _rival_state(ref, data, freed, held)
        assert "held at its null" in trial.report().summary, freed


@pytest.mark.xdist_group("eval-srm660c")
def test_c1_data_chooses_and_the_tolerance_discriminates(srm_trio):
    """C1's registration: the full window is decisive (≥ 1.10; measured
    1.1679, zero-only 4.0753 against disp-only 3.4894) and the registered
    {abs: 0.005} tolerance passes the swap (measured recovery 1.4e-07) while
    failing the ridge (disp −0.1202, off by 0.0401) — which lands at a
    *better* Rwp, the trap — and the zero-absorber state (the path never
    freed).  Verdict-only scoring would recreate round 2's tension in
    mirror; the tolerance is what makes the row honest."""
    truth = srm_trio["C1"]["truth"]
    tol = truth["planted"]["tol"]["abs"]
    disp_truth = truth["planted"]["truth"]

    ref, result, data = _fit_default(srm_trio["C1"]["core"])
    assert result.status == "converged"
    assert ref.fitted_instrument.geometry.sample_displacement.value == -0.02
    assert abs(ref.fitted_instrument.zero_shift.value) > 0.02  # absorbed
    assert "held at its null" in ref.report().summary
    _plot(result, "eval_c1_lazy_landing")

    comp = compare_rivals(ref, data, (DISP, ZERO))
    disp_fit, zero_fit = comp.rivals
    assert zero_fit.chi2 / disp_fit.chi2 >= DECISIVE_MIN
    assert abs(disp_fit.freed_value - disp_truth) <= tol  # the swap passes

    ridge = ref.branch()
    ridge_res = ridge.run_stage(data, rx.Stage("ridge", [DISP, ZERO]))
    ridge_disp = ridge.fitted_instrument.geometry.sample_displacement.value
    assert abs(ridge_disp - disp_truth) > tol             # the ridge fails
    assert ridge_res.statistics.rwp < disp_fit.rwp        # at a better Rwp


# ----------------------------------------------------------------------
# W1: wrong assumption — phase list (real 11-BM NAC, model NAC only)
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def w1_landing():
    try:
        ep = bf.build_nac_episode()["W1"]
    except FileNotFoundError as exc:
        pytest.skip(str(exc))
    structure, ins, data = _models(ep["core"])
    ref = rx.Refinement(structure, ins)
    result = ref.fit(data, plan="mccusker_default",
                     two_theta_limits=tuple(ep["core"]["two_theta_limits"]),
                     stage_reports=True)
    return ep, ref, result, data


def _caf2_lines(lo, hi):
    """Strong fluorite line positions on the 11-BM wavelength — computed, not
    quoted, so a wavelength change moves them with the episode."""
    import numpy as np

    from tests.test_acceptance_nac import WAVELENGTH

    a = 5.4631
    out = []
    for hkl in [(1, 1, 1), (2, 2, 0), (3, 1, 1), (4, 0, 0), (3, 3, 1),
                (4, 2, 2)]:
        d = a / np.sqrt(sum(i * i for i in hkl))
        tt = 2 * np.degrees(np.arcsin(WAVELENGTH / (2 * d)))
        if lo <= tt <= hi:
            out.append(float(tt))
    return out


@pytest.mark.xdist_group("eval-nac")
def test_w1_landing_names_the_impurity_and_the_trajectory_climbs(w1_landing):
    """W1's registration, three measurements at one landing state (measured
    Rwp 0.14025): the converged report carries a non-empty action list with
    ``add_impurity_phase`` leading at 0.9 — the Layer-2 decidability
    precondition, which round 2's converged reports all failed; strong
    ``unmatched_obs`` at the CaF₂ lines (measured 5 of 6, three at ~110σ);
    and the WP-1058 climbing-confidence trajectory (measured
    0.3 → 0.6 → 0.9) — the one real signal the ``report_trajectory`` default
    is decided on."""
    ep, ref, result, data = w1_landing
    assert result.status == "converged"
    report = ref.report()
    _plot(result, "eval_w1_landing")

    active = {a.kind: a.confidence
              for a in report.suggested_actions if a.active}
    assert active.get("add_impurity_phase", 0.0) >= 0.8

    unmatched = [u for u in report.unmatched if u.kind == "unmatched_obs"]
    lines = _caf2_lines(*ep["core"]["two_theta_limits"])
    hits = {t: [u.height_over_sigma for u in unmatched
                if abs(u.two_theta - t) <= 0.05]
            for t in lines}
    hit_lines = [t for t, sigmas in hits.items() if sigmas]
    assert len(hit_lines) >= 4, hits
    assert max(s for sigmas in hits.values() for s in sigmas or [0]) > 50

    climb = [next((a.confidence for a in rung.actions
                   if a.kind == "add_impurity_phase"), 0.0)
             for rung in ref.stage_reports_]
    assert climb == sorted(climb), climb        # never falls back
    assert climb[0] <= 0.5 and climb[-1] >= 0.8, climb


@pytest.mark.xdist_group("eval-nac")
def test_w1_modelling_the_impurity_is_decisive(w1_landing):
    """The with/without comparison behind the ``impurity_suspected`` +
    ``add_phase`` registration: appending the CaF₂ phase moves χ² decisively
    (measured 28.28 → 12.46, ratio 2.2702 against the ≥ 1.10 band)."""
    ep, _ref, nac_only, data = w1_landing
    from tests.test_acceptance_nac import _caf2_phase
    from tests.test_acceptance_qpa_roundrobin import seed_scales

    s2, i2, _ = _models(ep["core"])
    s2.phases.append(_caf2_phase())
    seed_scales(s2, i2, data)
    plan = rx.RefinementPlan.mccusker_default()
    plan.stages.append(rx.Stage("biso", ["phases.*.atoms.*.biso"]))
    ref2 = rx.Refinement(s2, i2)
    both = ref2.fit(data, plan=plan,
                    two_theta_limits=tuple(ep["core"]["two_theta_limits"]))
    assert both.status == "converged"
    assert nac_only.statistics.chi2 / both.statistics.chi2 >= DECISIVE_MIN
    _plot(both, "eval_w1_with_caf2")


# ----------------------------------------------------------------------
# W2: wrong assumption — instrument (real qarr corundum, single-line lie)
# ----------------------------------------------------------------------
def _ka2_predictions(result, lam1, lam2):
    """Predicted Kα2 positions off a single-line fit's own ticks."""
    import numpy as np

    out = []
    for positions in result.ticks.values():
        for tt1 in positions:
            s = (lam2 / lam1) * np.sin(np.radians(tt1 / 2))
            if s < 1:
                out.append(float(2 * np.degrees(np.arcsin(s))))
    return out


def _unmatched_near(report, predictions, tol=0.08):
    return [u.two_theta for u in report.unmatched
            if u.kind == "unmatched_obs"
            and any(abs(u.two_theta - p) <= tol for p in predictions)]


@pytest.mark.xdist_group("eval-qarr")
def test_w2_satellites_vanish_when_the_source_is_fixed():
    """W2's registration: under the single-line declaration the Kα2
    satellites read impurity-shaped — measured 31 ``unmatched_obs`` at
    predicted Kα2 positions, with the designed Layer-0 trap live
    (``add_impurity_phase`` served at 0.9) — and declaring the doublet is
    decisive (measured ratio 2.5450 against the ≥ 1.10 band) **and** empties
    those positions (measured 0 — the vanishing criterion).  An impurity's
    peaks would survive a source fix; that is the discriminator between
    ``assumption_wrong`` and ``impurity_suspected``."""
    try:
        ep = bf.build_qarr_episode()["W2"]
    except FileNotFoundError as exc:
        pytest.skip(str(exc))
    from tests.test_acceptance_qpa_roundrobin import (
        corundum_phase,
        qarr_instrument,
        seed_scales,
    )

    structure, ins_single, data = _models(ep["core"])
    assert len(ins_single.source.lines) == 1      # the wrong declaration
    ref1 = rx.Refinement(structure, ins_single)
    r1 = ref1.fit(data, plan="mccusker_default")
    rep1 = ref1.report()
    assert r1.status == "converged"
    _plot(r1, "eval_w2_single_line_landing")

    doublet = qarr_instrument()
    # ``.value``: EmissionLine.wavelength is a Parameter, not a float
    lam1 = doublet.source.lines[0].wavelength.value
    lam2 = doublet.source.lines[1].wavelength.value
    preds = _ka2_predictions(r1, lam1, lam2)
    assert len(_unmatched_near(rep1, preds)) >= 10       # measured 31
    active = {a.kind: a.confidence
              for a in rep1.suggested_actions if a.active}
    assert active.get("add_impurity_phase", 0.0) >= 0.8  # the trap, live

    s2 = rx.Structure(phases=[corundum_phase()])
    seed_scales(s2, doublet, data)
    ref2 = rx.Refinement(s2, doublet)
    r2 = ref2.fit(data, plan="mccusker_default")
    assert r2.status == "converged"
    assert r1.statistics.chi2 / r2.statistics.chi2 >= DECISIVE_MIN
    assert _unmatched_near(ref2.report(), preds) == []   # vanished
    _plot(r2, "eval_w2_doublet_refit")


# ----------------------------------------------------------------------
# the synthetic rows: E8p, J1
# ----------------------------------------------------------------------
@pytest.mark.xdist_group("eval-synth")
def test_e8p_lazy_path_fires_the_clause_and_the_rivals_tie():
    """E8's replacement (PROTOCOL.md 2.0 § Episode validity): displacement —
    which no ``mccusker_default`` stage frees, pinned here — planted on the
    short window.  The lazy path absorbs it into zero (measured −0.0112,
    Rwp 0.01265) and the clause fires at that converged state; the plant
    lives in the start, so the rivals tie exactly (measured 1.0001) — this
    row can only ever answer "tie", which is its job.  The wrong-family
    state's clause firing is pinned one suite over, in
    ``test_fitreport_layers`` (the E8-short block)."""
    plan = rx.RefinementPlan.mccusker_default()
    assert not any("displacement" in g
                   for st in plan.stages for g in st.turn_on)

    ep = bf.build_episodes()["E8p"]
    ref, result, data = _fit_default(ep["core"])
    assert result.status == "converged"
    assert ref.fitted_instrument.geometry.sample_displacement.value == -0.02
    assert abs(ref.fitted_instrument.zero_shift.value) > 0.005  # absorbed
    assert "held at its null" in ref.report().summary
    _plot(result, "eval_e8p_lazy_landing")

    comp = compare_rivals(ref, data, (DISP, ZERO))
    ratio = comp.rivals[1].chi2 / comp.rivals[0].chi2
    assert TIE_BAND[0] <= ratio <= TIE_BAND[1], ratio


@pytest.mark.xdist_group("eval-synth")
def test_e8p_through_the_agent_surface_carries_the_clause():
    """The end-to-end pin at synthetic cost: the episode core through the
    shim's own request runner — the surface the agent drives — converges with
    the planted path never freed (the vary-or-tie serialisation) and the
    clause in the delivered report's summary.

    It ran through the package's ``refine_json`` until WP-1303; the request is
    the same dict and the runner is the same two package calls.
    """
    from tests.eval_report_agent.run_refine import run_request

    # the preset as a spec, which runs as given: the request's default name
    # frees the displacement on Bragg-Brentano since WP-2015 (``_fit_default``)
    plan = PlanSpec.model_validate(PLAN_PRESETS["mccusker_default"]())
    core = bf.build_episodes()["E8p"]["core"]
    response = run_request(dict(core, include_report=True,
                                plan=plan.model_dump(mode="json")))
    assert response["ok"], response.get("error")
    values = {p["path"] for p in response["result"]["parameters"]}
    assert DISP not in values
    assert "held at its null" in response["report"]["summary"]


@pytest.mark.xdist_group("eval-synth")
def test_j1_one_state_supports_both_registered_answers():
    """J1P/J1S share one core; the landing state supports both registered
    answers at once, decided by the declared deliverable (§4b as an
    episode): a good fit with an empty action list (phase identification →
    ``converged`` + none) whose intensity model demonstrably carries the
    misfit (structure quality → ``ambiguous`` + chemistry_or_contents).
    Re-measured pins of WP-1057's 2026-08-12 numbers — Rwp 0.04048,
    GoF 2.970, gap ratio 2.381; the report-level sibling is
    ``test_fitreport_layers.test_pore_proxy_gap_and_contents_clause``."""
    eps = bf.build_episodes()
    assert eps["J1P"]["core"] == eps["J1S"]["core"]
    assert eps["J1P"]["truth"]["deliverable"] == "phase_id"
    assert eps["J1S"]["truth"]["deliverable"] == "structure"

    ref, result, _data = _fit_default(eps["J1P"]["core"])
    assert result.status == "converged"
    assert result.statistics.rwp < 0.05          # measured 0.04048
    assert 2.5 < result.statistics.gof < 3.5     # measured 2.970
    report = ref.report()
    assert report.lebail_gap is not None and report.lebail_gap.ratio > 2.0
    assert "alternate in sign" in report.summary
    assert "un-modelled scattering contents" in report.summary
    assert not [a for a in report.suggested_actions if a.active]
    _plot(result, "eval_j1_landing")
