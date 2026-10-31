"""WP-1534 — a scale and a B the fitted range cannot separate.

A phase's intensity is ``scale · exp(−2B·s²)`` times terms neither parameter
touches.  Where every reflection of the phase in the fitted range sits at one
d-spacing, ln(scale) − 2B·s² is one coordinate, and the two columns are one
direction.  Issue #204 walked bcc Fe's B to −165 Å² that way on a 25–50° Cu Kα
scan, and two staging orders returned it at 0.0 and 80.9 wt% at one Rwp.
WP-1534's task 1 measured the covariance *not* saying so: the pinv cut
discards the combined direction, and Fe came back 0.000 ± 0.000 wt%.

The fixture is task 1's: corundum, zincite, fluorite and bcc Fe at equal
scales, 25–50° in 0.01° steps, Poisson noise at seed 3, fitted from scales of
1e-4 with B at the truth and ``biso`` unbounded, in two staging orders.  Fe has
one reflection in range, (110); fluorite is the nearest phase that *is*
separable, and keeps its honest, huge esd.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx import PatternData
from rietx.model.forward import compile_model
from rietx.optimize.qpa import compute_qpa
from rietx.optimize.statistics import PINV_RCOND, _psd_pinv
from rietx.params.vector import ParameterTable
from rietx.refine import SCALE_B_SEPARATION_FLOOR, _scale_b_separation
from rietx.schemas.instrument import BackgroundChebyshev, Dispersion
from rietx.schemas.results import RefinementResult, StageResult
from rietx.strategy.staged import RefinementPlan, Stage

pytestmark = pytest.mark.xdist_group("scale-b-ridge")

OUT = Path(__file__).parent / "output"

TT = np.arange(25.0, 50.0, 0.01)
TRUE_SCALES = [2.0e-4, 2.0e-4, 2.0e-4, 2.0e-4]
START_SCALES = [1.0e-4, 1.0e-4, 1.0e-4, 1.0e-4]
TRUE_B = {"corundum": 0.30, "zincite": 0.55, "fluorite": (0.55, 0.75),
          "iron": 0.35}
FLUORITE, FE = 2, 3
FE_B = "phases.3.atoms.0.biso"

BIG = ["phases.*.scale", "instrument.background.*"]
CELL = ["phases.*.cell.*", "instrument.zero_shift"]
BISO = ["phases.*.atoms.*.biso"]
WIDTH = ["phases.*.lor_size", "instrument.profile.w"]
ORDERS = {
    "cell_then_B": [Stage("s", BIG), Stage("c", BIG + CELL),
                    Stage("b", BIG + CELL + BISO),
                    Stage("w", BIG + CELL + BISO + WIDTH)],
    "B_then_cell": [Stage("s", BIG), Stage("b", BIG + BISO),
                    Stage("c", BIG + BISO + CELL),
                    Stage("w", BIG + CELL + BISO + WIDTH)],
}


def _p(v, **kw):
    return rx.Parameter(value=v, **kw)


def _phase(name, sg, cell, atoms, scale, unbounded):
    a, b, c, al, be, ga = cell
    # #204's shape: the caller's Parameter carries no bounds on B
    bk = dict(min=-math.inf, max=math.inf) if unbounded else {}
    return rx.Phase(
        name=name, space_group=sg,
        cell=rx.Cell(a=_p(a), b=_p(b), c=_p(c), alpha=_p(al), beta=_p(be),
                     gamma=_p(ga)),
        atoms=[rx.Atom(label=lab, species=sp, x=_p(x), y=_p(y), z=_p(z),
                       biso=_p(biso, **bk))
               for lab, sp, x, y, z, biso in atoms],
        scale=_p(scale, min=0.0, transform="softplus"),
        lor_size=_p(0.02, min=0.0, transform="softplus"),
        lor_strain=_p(0.0, min=0.0, transform="softplus"))


def _models(scales, *, unbounded=True):
    def b(name, k=0):
        v = TRUE_B[name]
        return v[k] if isinstance(v, tuple) else v
    phases = [
        _phase("corundum", "R -3 c", (4.7593, 4.7593, 12.9917, 90, 90, 120),
               [("Al", "Al", 0.0, 0.0, 0.35216, b("corundum")),
                ("O", "O", 0.30624, 0.0, 0.25, b("corundum"))],
               scales[0], unbounded),
        _phase("zincite", "P 63 m c", (3.2499, 3.2499, 5.2066, 90, 90, 120),
               [("Zn", "Zn", 1 / 3, 2 / 3, 0.0, b("zincite")),
                ("O", "O", 1 / 3, 2 / 3, 0.3826, b("zincite"))],
               scales[1], unbounded),
        _phase("fluorite", "F m -3 m", (5.4631,) * 3 + (90, 90, 90),
               [("Ca", "Ca", 0.0, 0.0, 0.0, b("fluorite", 0)),
                ("F", "F", 0.25, 0.25, 0.25, b("fluorite", 1))],
               scales[2], unbounded),
        _phase("iron", "I m -3 m", (2.8665,) * 3 + (90, 90, 90),
               [("Fe", "Fe", 0.0, 0.0, 0.0, b("iron"))], scales[3], unbounded),
    ]
    instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
    # declared rather than inherited (root CLAUDE.md): the default, task 1's
    instrument.source.dispersion = Dispersion()
    instrument.background = BackgroundChebyshev(
        coefficients=[_p(v) for v in (150.0, -20.0, 5.0)])
    return rx.Structure(phases=phases), instrument


def _fit(data, stages, *, unbounded=True, ref=None, **plan):
    ref = ref or rx.Refinement(*_models(START_SCALES, unbounded=unbounded))
    res = ref.fit(data, plan=RefinementPlan(stages=stages, **plan), telemetry=False)
    return ref, res


def _fraction(res, name):
    (row,) = [q for q in res.qpa.phases if q.name == name]
    return row.weight_fraction


def _findings(res, code="SCALE_B_INSEPARABLE"):
    return [d for d in res.diagnostics if d.code == code]


@pytest.fixture(scope="module")
def pattern() -> PatternData:
    structure, instrument = _models(TRUE_SCALES, unbounded=False)
    blank = PatternData(two_theta=TT.tolist(), intensity=np.zeros_like(TT).tolist())
    model = compile_model(structure, instrument, blank, mode="rietveld")
    table = ParameterTable(structure, instrument)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(3).poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=np.asarray(model.tt).tolist(), intensity=y.tolist())


@pytest.fixture(scope="module")
def true_fraction() -> dict[str, float]:
    structure, instrument = _models(TRUE_SCALES, unbounded=False)
    table = ParameterTable(structure, instrument)
    q = compute_qpa(structure, table.decode(table.x0()))
    return {p.name: p.weight_fraction for p in q.phases}


@pytest.fixture(scope="module")
def ridge_fits(pattern) -> dict[str, tuple]:
    """Both staging orders, ``biso`` unbounded — #204's two answers."""
    return {order: _fit(pattern, stages) for order, stages in ORDERS.items()}


@pytest.fixture(params=list(ORDERS))
def ridge_fit(request, ridge_fits):
    return (request.param, *ridge_fits[request.param])


# ----------------------------------------------------------------------
# the floor and the probe
# ----------------------------------------------------------------------
def test_the_floor_is_where_the_covariance_cut_falls():
    """Two unit columns ``r`` apart lose their difference direction to pinv's
    cut below the floor and keep it above — the derivation, checked against
    the call the covariance makes rather than restated."""
    assert SCALE_B_SEPARATION_FLOOR == pytest.approx(2.0 * math.sqrt(PINV_RCOND))
    diff = np.array([1.0, -1.0]) / math.sqrt(2.0)

    def variance_of_the_difference(r):
        c = math.sqrt(1.0 - r * r)
        k = _psd_pinv(np.array([[1.0, c], [c, 1.0]]), PINV_RCOND)
        return float(diff @ k @ diff)

    # the true value is 1/(1 − c) ≈ 2/r²: 2e15 at half the floor, 1e14 at twice
    assert variance_of_the_difference(0.5 * SCALE_B_SEPARATION_FLOOR) < 1.0
    assert variance_of_the_difference(2.0 * SCALE_B_SEPARATION_FLOOR) > 1e13


def test_the_probe_separates_one_d_spacing_from_several(pattern):
    """Fe's one reflection reads at the probe's rounding floor, every other
    phase several decades above the cut — at the values a B stage starts from."""
    structure, instrument = _models(START_SCALES)
    table = ParameterTable(structure, instrument)
    table.set_vary(BIG + BISO, True)
    model = compile_model(structure, instrument, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    r = _scale_b_separation(model, table)
    print(f"\nseparation at stage start: "
          f"{ {ip: f'{v:.3g}' for ip, v in r.items()} }")
    assert sorted(r) == [0, 1, 2, FE]
    assert r[FE] < SCALE_B_SEPARATION_FLOOR * 1e-3
    assert min(v for ip, v in r.items() if ip != FE) > SCALE_B_SEPARATION_FLOOR * 1e3


# ----------------------------------------------------------------------
# the hold, the record and the finding
# ----------------------------------------------------------------------
def test_fe_b_is_held_in_every_stage_that_frees_it(ridge_fit):
    order, _, res = ridge_fit
    for stage, sr in zip(ORDERS[order], res.stages):
        if BISO[0] in stage.turn_on:
            assert FE_B in sr.held and FE_B not in sr.freed, (order, sr.name)
            assert list(sr.scale_b_held) == [FE], (order, sr.name)
            assert sr.scale_b_held[FE] < SCALE_B_SEPARATION_FLOOR
        else:
            # looked, and nothing to hold: the written empty, never None
            assert sr.scale_b_held == {} and FE_B not in sr.held
        # fluorite is separable, so its B refines and keeps its honest esd
        assert not any(p.startswith(f"phases.{FLUORITE}.") for p in sr.held)
        assert sr.released == []
    params = {p.path: p for p in res.parameters}
    assert FE_B not in params, "a held value is the caller's, not a result"
    assert params[f"phases.{FLUORITE}.atoms.0.biso"].stderr is not None


def test_fe_b_stays_at_the_value_handed_in(ridge_fit):
    """Unbounded, the walk is gone: task 1 measured −150 Å² in both orders."""
    _, ref, _ = ridge_fit
    assert ref.structure.phases[FE].atoms[0].biso.value == TRUE_B["iron"]


def test_the_finding_names_iron_and_only_iron(ridge_fit):
    order, ref, res = ridge_fit
    (finding,) = _findings(res)
    assert finding.level == "warning"
    assert finding.where == [FE_B]
    assert finding.value == min(sr.scale_b_held.get(FE, math.inf)
                                for sr in res.stages)
    assert "phase 3 (iron)" in finding.message
    held_in = [s.name for s in ORDERS[order] if BISO[0] in s.turn_on]
    assert f"stages {', '.join(held_in)}" in finding.message
    # the fraction's sensitivity, from Fe (110)'s own s² = 1/(4d²)
    s2 = 0.25 / (2.8665 / math.sqrt(2.0)) ** 2
    assert f"about {100.0 * math.expm1(2.0 * s2):.2g} %" in finding.message
    assert "1 scale-B inseparable (WP-1534)" in ref.summary()


def test_fe_fraction_lands_near_the_truth_and_both_orders_agree(
        ridge_fits, true_fraction):
    """The acceptance: never two different confident fractions at one Rwp.

    The tolerance is the fit's own: three of Fe's scale esds, relative — the
    one direction this fixture's Fe fraction is measured along once B is held.
    Its QPA esd is no tolerance here: fluorite's near-ridge carries thousands
    of wt% through the normalisation into every fraction (task 1).
    """
    fractions, rwps, tolerances = {}, {}, {}
    for order, (_, res) in ridge_fits.items():
        scale = {p.path: p for p in res.parameters}[f"phases.{FE}.scale"]
        fractions[order] = _fraction(res, "iron")
        rwps[order] = res.statistics.rwp
        tolerances[order] = 3.0 * scale.stderr / scale.value
    truth = true_fraction["iron"]
    print(f"\nFe wt%: truth {truth * 100:.4f}; "
          + "; ".join(f"{o} {w * 100:.6f} (tol ±{tolerances[o] * truth * 100:.4f}, "
                      f"Rwp {rwps[o]:.10f})" for o, w in fractions.items()))
    for order, w in fractions.items():
        assert abs(w - truth) < tolerances[order] * truth, order
    a, b = fractions.values()
    # measured 1.284265 and 1.284271 wt%, against 0.000 ± 0.000 in both
    # orders before the hold (task 1); the truth is 1.2111, 1.1 scale esds away
    assert abs(a - b) < 1e-4 * truth


def test_the_record_round_trips(ridge_fit):
    _, _, res = ridge_fit
    held = [sr for sr in res.stages if sr.scale_b_held]
    assert held
    for sr in res.stages:
        back = StageResult.model_validate_json(sr.model_dump_json())
        assert back == sr
        assert all(isinstance(ip, int) for ip in back.scale_b_held)
    whole = RefinementResult.model_validate_json(res.model_dump_json())
    assert [s.scale_b_held for s in whole.stages] == [s.scale_b_held
                                                      for s in res.stages]
    # a record written before the field: nobody looked, never "nothing held"
    old = held[0].model_dump(mode="json")
    old.pop("scale_b_held")
    assert StageResult.model_validate(old).scale_b_held is None


# ----------------------------------------------------------------------
# where the test does not apply
# ----------------------------------------------------------------------
def test_a_plan_that_never_frees_b_holds_nothing(pattern):
    _, res = _fit(pattern, ORDERS["cell_then_B"][:2])
    assert all(sr.scale_b_held == {} and sr.held == [] for sr in res.stages)
    assert _findings(res) == []


def test_a_held_scale_leaves_b_to_measure_the_intensity(pattern):
    """The ridge is a *pair* of columns: with the scale fixed, B is what the
    one intensity determines, and holding it would freeze a measured value."""
    # the declared stage's probe; the closing stage is tests/test_closing_stage.py's
    _, res = _fit(pattern, [Stage("b", ["instrument.background.*"] + BISO)],
                  closing_window_tol=None)
    (sr,) = res.stages
    assert sr.scale_b_held == {} and FE_B in sr.freed
    assert _findings(res) == []


def test_a_phase_released_inside_the_stage_is_asked_before_its_second_solve(
        pattern):
    """Fe starts under the noise, so the support hold takes its B before the
    probe can see it; the solve raises its scale and the release frees B.  The
    probe is asked then, or the second solve runs on the ridge unflagged."""
    ref = rx.Refinement(*_models(START_SCALES[:FE] + [1e-9]))
    # the declared stage's probe; the closing stage is tests/test_closing_stage.py's
    _, res = _fit(pattern, [Stage("b", BIG + BISO)], ref=ref, closing_window_tol=None)
    (sr,) = res.stages
    assert FE_B in sr.held and FE_B not in sr.released + sr.freed
    assert list(sr.scale_b_held) == [FE]
    assert sr.scale_b_held[FE] < SCALE_B_SEPARATION_FLOOR
    (finding,) = _findings(res)
    assert finding.where == [FE_B]
    assert _findings(res, "PHASE_UNCONSTRAINED") == []


def test_a_variable_driving_b_is_held_as_its_column(pattern):
    """Columns, never names (WP-1342): the free name is the variable's."""
    ref = rx.Refinement(*_models(START_SCALES))
    ref.add_variable("B_fe", TRUE_B["iron"])
    ref.tie(FE_B, "vars.B_fe")
    _, res = _fit(pattern, [Stage("s", BIG), Stage("b", BIG + BISO + ["vars.*"])],
                  ref=ref)
    sr = res.stages[-1]
    assert sr.held == ["vars.B_fe"]
    assert sr.held_reach == {"vars.B_fe": [FE_B]}
    assert list(sr.scale_b_held) == [FE]
    (finding,) = _findings(res)
    assert finding.where == ["vars.B_fe"]


def test_a_variable_shared_with_a_separable_phase_is_not_held(pattern):
    """All, never any: fluorite's B gives the shared column a direction Fe's
    scale cannot imitate, so the pair is not a ridge and nothing is held."""
    ref = rx.Refinement(*_models(START_SCALES))
    ref.add_variable("B", TRUE_B["iron"])
    ref.tie_equal([FE_B, f"phases.{FLUORITE}.atoms.0.biso"], source="vars.B")
    _, res = _fit(pattern, [Stage("s", BIG), Stage("b", BIG + BISO + ["vars.*"])],
                  ref=ref)
    sr = res.stages[-1]
    assert "vars.B" in sr.freed and sr.held == []
    assert sr.scale_b_held == {}
    assert _findings(res) == []


# ----------------------------------------------------------------------
# the block: more displacement columns than the reflections leave room for
# ----------------------------------------------------------------------
#: 25–33° Cu Kα: fluorite keeps (111) and (200), two reflections for its
#: scale, B(Ca) and B(F).  The uniform B is separable there, the block is not.
#: Iron is left out of the block tests: it has no reflection there, and its
#: scale is WP-1958's, tested below.
TT_NARROW = np.arange(25.0, 33.0, 0.01)
ADP = ["phases.*.atoms.*.adp.*"]


def _narrow_models(scales):
    structure, instrument = _models(scales)
    structure.phases = structure.phases[:FE]
    return structure, instrument


@pytest.fixture(scope="module")
def narrow_pattern() -> PatternData:
    structure, instrument = _narrow_models(TRUE_SCALES)
    blank = PatternData(two_theta=TT_NARROW.tolist(),
                        intensity=np.zeros_like(TT_NARROW).tolist())
    model = compile_model(structure, instrument, blank, mode="rietveld")
    table = ParameterTable(structure, instrument)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(3).poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=np.asarray(model.tt).tolist(), intensity=y.tolist())


def test_two_sites_on_two_reflections_are_one_ridge(narrow_pattern):
    """Stepping both of fluorite's B together finds a direction the scale
    cannot imitate; the two sites apart do not.  The round robin's cpd-1c
    walked them to +99 and −111 Å² this way (WP-1534, 2026-10-04)."""
    from rietx.refine import SCALE_B_STEP, _column_separation

    structure, instrument = _narrow_models(START_SCALES)
    table = ParameterTable(structure, instrument)
    table.set_vary(BIG + BISO, True)
    model = compile_model(structure, instrument, narrow_pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    r = _scale_b_separation(model, table)
    assert r[FLUORITE] < SCALE_B_SEPARATION_FLOOR * 1e-3
    values = table.decode(table.x0())
    sigma = np.asarray(model.sigma)
    a = np.asarray(model.phase_component(FLUORITE, values)) / sigma
    both = dict(values)
    for j in (0, 1):
        both[f"phases.{FLUORITE}.atoms.{j}.biso"] += SCALE_B_STEP
    uniform = np.asarray(model.phase_component(FLUORITE, both)) / sigma - a
    assert _column_separation([a], [uniform]) > SCALE_B_SEPARATION_FLOOR * 1e3


def test_the_block_hold_keeps_fluorite_off_the_walk(narrow_pattern):
    truth = _narrow_models(TRUE_SCALES)
    table = ParameterTable(*truth)
    w = {p.name: p.weight_fraction
         for p in compute_qpa(truth[0], table.decode(table.x0())).phases}
    ref = rx.Refinement(*_narrow_models(START_SCALES))
    _, res = _fit(narrow_pattern, [Stage("s", BIG), Stage("b", BIG + BISO)], ref=ref)
    sr = res.stages[-1]
    flu = [f"phases.{FLUORITE}.atoms.{j}.biso" for j in (0, 1)]
    assert set(flu) <= set(sr.held)
    assert FLUORITE in sr.scale_b_held
    (finding,) = [f for f in _findings(res) if flu[0] in f.where]
    assert finding.where == flu
    assert [a.biso.value for a in ref.structure.phases[FLUORITE].atoms] == list(
        TRUE_B["fluorite"])
    got = _fraction(res, "fluorite")
    scale = {p.path: p for p in res.parameters}[f"phases.{FLUORITE}.scale"]
    tol = 3.0 * scale.stderr / scale.value
    print(f"\nfluorite wt% on 25–33°: {100 * got:.3f} (truth {100 * w['fluorite']:.3f}, "
          f"tol ±{100 * tol * w['fluorite']:.3f})")
    # measured 23.884 against 23.730
    assert abs(got - w["fluorite"]) < tol * w["fluorite"]


def test_an_anisotropic_site_is_probed(pattern):
    """An ADP DOF is a displacement column like a ``biso``; the probe once
    skipped a phase with no isotropic site (WP-1534's declined finding)."""
    structure, instrument = _models(START_SCALES)
    fe = structure.phases[FE].atoms[0]
    u = TRUE_B["iron"] / (8.0 * math.pi ** 2)
    fe.aniso = rx.AnisoU(u11=_p(u, vary=True), u22=_p(u, vary=True),
                         u33=_p(u, vary=True))
    fe.biso.vary = False
    table = ParameterTable(structure, instrument)
    table.set_vary(BIG + BISO + ADP, True)
    model = compile_model(structure, instrument, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    r = _scale_b_separation(model, table)
    assert r[FE] < SCALE_B_SEPARATION_FLOOR * 1e-3
    _, res = _fit(pattern, [Stage("s", BIG), Stage("b", BIG + BISO + ADP)],
                  ref=rx.Refinement(structure, instrument))
    sr = res.stages[-1]
    assert list(sr.scale_b_held) == [FE]
    assert all(p.startswith(f"phases.{FE}.atoms.0.adp.") for p in sr.held)


# ----------------------------------------------------------------------
# WP-1958 (#954): a phase with no reflection in the fitted range
# ----------------------------------------------------------------------
SCALES_ONLY = [Stage("s", BIG), Stage("s2", BIG)]
FE_SCALE = f"phases.{FE}.scale"


@pytest.fixture(scope="module")
def four_phase_narrow_pattern() -> PatternData:
    """All four phases over 25–33°, where bcc Fe has no reflection."""
    structure, instrument = _models(TRUE_SCALES, unbounded=False)
    blank = PatternData(two_theta=TT_NARROW.tolist(),
                        intensity=np.zeros_like(TT_NARROW).tolist())
    model = compile_model(structure, instrument, blank, mode="rietveld")
    assert int(model.phase_line_counts()[FE]) == 0
    assert all(int(n) > 0 for n in model.phase_line_counts()[:FE])
    table = ParameterTable(structure, instrument)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(3).poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=np.asarray(model.tt).tolist(), intensity=y.tolist())


@pytest.mark.parametrize("solver", ["lm", "trf"])
def test_a_phase_with_no_reflection_keeps_its_scale_and_has_no_fraction(
        four_phase_narrow_pattern, solver):
    """The acceptance of WP-1958, as decided on #954: under both solvers the
    scale is unchanged and the QPA carries no fraction for the phase.

    Measured on ``main`` before it (the WP's repro, this fit): LM left the
    scale at 1e-4 and read iron at 0.61 wt%, the start value; TRF walked it to
    164.7 and read iron at 99.99 wt%.  Both now hold the scale at the 1e-4
    handed in, and iron has no fraction.
    """
    ref = rx.Refinement(*_models(START_SCALES), solver=solver)
    res = ref.fit(four_phase_narrow_pattern,
                  plan=RefinementPlan(stages=SCALES_ONLY), telemetry=False)
    # on the Refinement's own copy, the one the fit could move
    assert ref.structure.phases[FE].scale.value == START_SCALES[FE]
    assert all(FE_SCALE in sr.held and FE_SCALE not in sr.freed
               for sr in res.stages)
    assert FE_SCALE not in {p.path for p in res.parameters}
    (iron,) = [q for q in res.qpa.phases if q.name == "iron"]
    assert iron.weight_fraction is None and iron.weight_fraction_stderr is None
    assert res.qpa.unmeasured_phases == ["iron"]
    (finding,) = _findings(res, "PHASE_UNCONSTRAINED")
    assert finding.where == [FE_SCALE]
    assert "relative to the phases seen in range" in finding.message
    # the unmeasured scale withholds no other esd: it left the sum
    assert _findings(res, "QPA_ESD_UNAVAILABLE") == []


@pytest.mark.parametrize("solver", ["lm", "trf"])
def test_the_phases_seen_in_range_still_refine_and_are_quantified(
        four_phase_narrow_pattern, solver):
    """The positive arm: the three phases with reflections in range refine
    their scales off the 1e-4 start towards the 2e-4 truth and carry fractions
    with esds, which sum to 1 over the phases seen and match the three-phase
    truth, the fixture's fluorite tolerance applied to each."""
    ref = rx.Refinement(*_models(START_SCALES), solver=solver)
    res = ref.fit(four_phase_narrow_pattern,
                  plan=RefinementPlan(stages=SCALES_ONLY), telemetry=False)
    truth = _narrow_models(TRUE_SCALES)
    table = ParameterTable(*truth)
    w = {p.name: p.weight_fraction
         for p in compute_qpa(truth[0], table.decode(table.x0())).phases}
    rows = {p.path: p for p in res.parameters}
    seen = [q for q in res.qpa.phases if q.name != "iron"]
    assert math.isclose(sum(q.weight_fraction for q in seen), 1.0, rel_tol=1e-12)
    for ip, q in enumerate(seen):
        scale = rows[f"phases.{ip}.scale"]
        assert abs(scale.value - TRUE_SCALES[ip]) < 0.1 * TRUE_SCALES[ip]
        assert all(f"phases.{ip}.scale" in sr.freed for sr in res.stages)
        assert q.weight_fraction_stderr is not None
        tol = 3.0 * scale.stderr / scale.value
        assert abs(q.weight_fraction - w[q.name]) < tol * w[q.name]


def test_iron_with_a_reflection_in_range_refines_its_scale_under_trf(pattern):
    """The same phase and solver on 25–50°, where (110) is in range: nothing
    of WP-1958's hold applies, iron's scale refines and it has a fraction."""
    ref = rx.Refinement(*_models(START_SCALES), solver="trf")
    res = ref.fit(pattern, plan=RefinementPlan(stages=SCALES_ONLY), telemetry=False)
    assert all(FE_SCALE in sr.freed and FE_SCALE not in sr.held
               for sr in res.stages)
    assert ref.structure.phases[FE].scale.value != START_SCALES[FE]
    (iron,) = [q for q in res.qpa.phases if q.name == "iron"]
    assert iron.weight_fraction is not None and iron.weight_fraction > 0.0
    assert res.qpa.unmeasured_phases == []


def test_the_lineless_hold_does_not_wait_on_the_support_threshold(
        four_phase_narrow_pattern):
    """``phase_support_sigma=None`` switches the significance hold off, and a
    phase with no line in range is held all the same: "no line" is a count."""
    ref = rx.Refinement(*_models(START_SCALES), solver="trf")
    res = ref.fit(four_phase_narrow_pattern,
                  plan=RefinementPlan(stages=SCALES_ONLY, phase_support_sigma=None),
                  telemetry=False)
    assert all(FE_SCALE in sr.held for sr in res.stages)
    assert ref.structure.phases[FE].scale.value == START_SCALES[FE]
    assert [q.weight_fraction for q in res.qpa.phases if q.name == "iron"] == [None]


def test_a_restrained_lineless_scale_is_left_to_its_restraint(
        four_phase_narrow_pattern):
    """A ``ValueRestraint`` on the scale gives it a column the data do not, so
    the hold leaves it free and it goes to the target; its fraction stays
    absent, the value being the caller's and not the data's."""
    structure, instrument = _models(START_SCALES)
    structure.phases[FE].restraints = [
        rx.ValueRestraint(path=FE_SCALE, target=3.0e-4, sigma=1.0e-6)]
    ref = rx.Refinement(structure, instrument, solver="trf")
    res = ref.fit(four_phase_narrow_pattern,
                  plan=RefinementPlan(stages=SCALES_ONLY), telemetry=False)
    assert all(FE_SCALE not in sr.held for sr in res.stages)
    assert math.isclose(ref.structure.phases[FE].scale.value, 3.0e-4, rel_tol=1e-3)
    assert res.qpa.unmeasured_phases == ["iron"]


def test_a_magnetic_window_in_range_counts_as_a_line(four_phase_narrow_pattern):
    """A phase drawing its magnetic component on its own wider windows has a
    column wherever either window reaches the range (WP-1343's ``win_mag``)."""
    structure, instrument = _models(START_SCALES)
    model = compile_model(structure, instrument, four_phase_narrow_pattern,
                          mode="rietveld")
    cp = model.phases[FE]
    assert int(model.phase_line_counts()[FE]) == 0
    # one reflection whose nuclear window is empty and whose wider magnetic
    # one covers five points, in the frozen layout (n_lines, N, 2)
    cp.win = np.zeros((cp.win.shape[0], 1, 2), dtype=np.int64)
    cp.win_mag = cp.win.copy()
    assert int(model.phase_line_counts()[FE]) == 0
    cp.win_mag[0, 0] = (0, 5)
    assert int(model.phase_line_counts()[FE]) == 1


@pytest.mark.parametrize("solver", ["lm", "trf"])
def test_a_joint_fit_holds_each_histograms_unseen_scale(
        four_phase_narrow_pattern, solver):
    """The joint runner's half: each histogram's own Fe scale is held where
    that histogram has no line of it.  Measured before the hold, TRF walked
    the two to 214.1 and 2.3 on two copies of the 25–33° scan."""
    from rietx.multi import MultiHistogramRefinement

    structure, instrument = _models(START_SCALES)
    multi = MultiHistogramRefinement(
        structure, [instrument.model_copy(deep=True) for _ in range(2)],
        solver=solver)
    res = multi.fit([four_phase_narrow_pattern] * 2,
                    plan=RefinementPlan(stages=SCALES_ONLY))
    held = {f"hist.{h}.{FE_SCALE}" for h in range(2)}
    assert all(held <= set(sr.held) for sr in res.stages)
    assert [s.phases[FE].scale.value for s in multi.fitted_structures] == [
        START_SCALES[FE]] * 2


# ----------------------------------------------------------------------
# a joint fit: scales per histogram, displacement parameters shared
# ----------------------------------------------------------------------
def _joint_fit(patterns, stages):
    from rietx.multi import MultiHistogramRefinement

    structure, instrument = _models(START_SCALES)
    ins = [instrument.model_copy(deep=True) for _ in patterns]
    multi = MultiHistogramRefinement(structure, ins)
    return multi, multi.fit(patterns, plan=RefinementPlan(stages=stages))


def _wide_pattern(tt) -> PatternData:
    structure, instrument = _models(TRUE_SCALES, unbounded=False)
    blank = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, instrument, blank, mode="rietveld")
    table = ParameterTable(structure, instrument)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(4).poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=np.asarray(model.tt).tolist(), intensity=y.tolist())


def test_a_joint_fit_of_two_narrow_scans_holds_fe(pattern):
    """Before WP-1534's port the joint runner ran no probe, and the 0–25 Å²
    default on ``Atom.biso`` was all that stood between it and #204's walk."""
    multi, res = _joint_fit([pattern, pattern],
                            [Stage("s", BIG), Stage("b", BIG + BISO)])
    sr = res.stages[-1]
    assert list(sr.scale_b_held) == [FE]
    assert sr.scale_b_held[FE] < SCALE_B_SEPARATION_FLOOR
    assert FE_B in sr.held and FE_B not in sr.freed
    assert multi.fitted_structures[0].phases[FE].atoms[0].biso.value == TRUE_B["iron"]
    (finding,) = _findings(res)
    assert finding.where == [FE_B]
    assert res.stages[0].scale_b_held == {}


def test_a_second_histogram_reaching_more_reflections_separates_fe(pattern):
    """Fe's (200) and (211) in a 25–90° scan give the shared B a direction no
    combination of the two scales imitates, so nothing is held."""
    wide = _wide_pattern(np.arange(25.0, 90.0, 0.02))
    _, res = _joint_fit([pattern, wide], [Stage("s", BIG), Stage("b", BIG + BISO)])
    assert all(sr.scale_b_held == {} for sr in res.stages)
    assert FE_B in res.stages[-1].freed
    assert _findings(res) == []


def test_a_scale_shared_across_histograms_is_one_column(pattern):
    """Fe's (110) on one scan and (200) on another each sit at one d-spacing,
    so per-histogram scales and the shared B are one ridge.  Sharing the scale
    leaves one scale column for two s², which the shared B can no longer
    imitate, so nothing is held.  Counted once per histogram, the shared scale
    read as two columns and held B anyway."""
    from rietx.multi import MultiHistogramRefinement
    from rietx.params.multi import SharingMap

    other = _wide_pattern(np.arange(55.0, 75.0, 0.02))
    stages = [Stage("s", BIG), Stage("b", BIG + BISO)]
    _, own = _joint_fit([pattern, other], stages)
    assert list(own.stages[-1].scale_b_held) == [FE]
    structure, instrument = _models(START_SCALES)
    multi = MultiHistogramRefinement(
        structure, [instrument.model_copy(deep=True) for _ in range(2)],
        sharing=SharingMap(shared=[f"phases.{FE}.scale"]))
    shared = multi.fit([pattern, other], plan=RefinementPlan(stages=stages))
    assert all(sr.scale_b_held == {} for sr in shared.stages)
    assert FE_B in shared.stages[-1].freed


def test_the_held_fit_is_drawn_for_inspection(ridge_fit):
    """Rwp hides locally-bad fits; the picture is the check that does not."""
    from rietx.viz.plots import plot_result

    order, _, res = ridge_fit
    OUT.mkdir(exist_ok=True)
    path = OUT / f"scale_b_ridge_{order}.png"
    plot_result(res, path=str(path))
    import matplotlib.pyplot as plt

    plt.close("all")
    assert path.exists()


# ----------------------------------------------------------------------
# #1103's review: what the answer quotes, and what a restraint exempts
# ----------------------------------------------------------------------
def _restraint_fit(pattern, *, weight=1.0, via_variable=False, solver="trf"):
    """The narrow fit with a restraint of ``weight`` on iron's scale, named
    directly or through a variable driving it."""
    structure, instrument = _models(START_SCALES)
    path = "vars.S_fe" if via_variable else FE_SCALE
    structure.phases[FE].restraints = [
        rx.ValueRestraint(path=path, target=3.0e-4, sigma=1.0e-6, weight=weight)]
    ref = rx.Refinement(structure, instrument, solver=solver)
    stages = SCALES_ONLY
    if via_variable:
        ref.add_variable("S_fe", START_SCALES[FE])
        ref.tie(FE_SCALE, "vars.S_fe")
        stages = [Stage(s.name, [*s.turn_on, "vars.*"]) for s in SCALES_ONLY]
    res = ref.fit(pattern, plan=RefinementPlan(stages=stages), telemetry=False)
    return ref, res


def test_a_weightless_restraint_does_not_exempt_the_scale(
        four_phase_narrow_pattern):
    """A restraint of weight 0 gives the column nothing, so the hold stays on
    and the scale keeps the value handed in (TRF walked it to 64.9 when the
    restraint's mere presence exempted it)."""
    ref, res = _restraint_fit(four_phase_narrow_pattern, weight=0.0)
    assert all(FE_SCALE in sr.held for sr in res.stages)
    assert ref.structure.phases[FE].scale.value == START_SCALES[FE]
    assert res.qpa.unmeasured_phases == ["iron"]


def test_a_restraint_through_a_variable_exempts_the_scale_it_drives(
        four_phase_narrow_pattern):
    """The positive arm: a weighted restraint on ``vars.S_fe``, which drives
    iron's scale, gives that scale a column, so the hold leaves it to the
    restraint instead of overriding it (and ``RESTRAINT_TENSION`` firing at
    -200σ)."""
    ref, res = _restraint_fit(four_phase_narrow_pattern, via_variable=True)
    assert all(FE_SCALE not in sr.held and "vars.S_fe" not in sr.held
               for sr in res.stages)
    assert math.isclose(ref.structure.phases[FE].scale.value, 3.0e-4, rel_tol=1e-3)
    assert _findings(res, "RESTRAINT_TENSION") == []
    assert res.qpa.unmeasured_phases == ["iron"]


def test_the_unmeasured_set_is_what_the_last_stage_held(pattern):
    """A scale the last stage held is unmeasured though the answer's count
    finds a line (a refined zero shift moved one over the range edge): the
    wide pattern has iron's (110), and the record says it was held."""
    from rietx.refine import _unmeasured_phases

    structure, instrument = _models(START_SCALES)
    model = compile_model(structure, instrument, pattern, mode="rietveld")
    assert int(model.phase_line_counts()[FE]) > 0

    def stage(held, reach=None):
        return StageResult(name="z", status="converged", n_iterations=1, cost_initial=1.0, cost_final=1.0, held=held,
                           held_reach=reach or {})

    assert _unmeasured_phases(model, [stage([FE_SCALE])]) == {FE}
    assert _unmeasured_phases(model, [stage([FE_SCALE]), stage([])]) == set()
    assert _unmeasured_phases(model, [stage(["vars.S"])]) == set()
    assert _unmeasured_phases(
        model, [stage(["vars.S"], {"vars.S": [FE_SCALE]})]) == {FE}
    assert _unmeasured_phases(model, None) == set()


def test_a_shared_scale_another_histogram_measures_is_quoted_everywhere():
    """A scale shared by a histogram without a line of iron and one with
    several: its value is the wide scan's measurement, so the narrow
    histogram's QPA counts iron too (it left iron out before)."""
    from rietx.multi import MultiHistogramRefinement
    from rietx.params.multi import SharingMap

    structure, instrument = _models(START_SCALES)
    narrow = _wide_pattern(np.arange(25.0, 33.0, 0.01))
    wide = _wide_pattern(np.arange(25.0, 90.0, 0.02))
    plan = RefinementPlan(stages=SCALES_ONLY)
    multi = MultiHistogramRefinement(
        structure, [instrument.model_copy(deep=True) for _ in range(2)],
        sharing=SharingMap(shared=["phases.*.scale"]))
    res = multi.fit([narrow, wide], plan=plan)
    assert all(FE_SCALE not in sr.held for sr in res.stages)
    for hist in res.histograms:
        assert hist.qpa.unmeasured_phases == []
        (iron,) = [q for q in hist.qpa.phases if q.name == "iron"]
        assert iron.weight_fraction is not None
    # per-histogram scales stay as before: the narrow scan has no iron fraction
    own = MultiHistogramRefinement(
        structure, [instrument.model_copy(deep=True) for _ in range(2)]
    ).fit([narrow, wide], plan=plan)
    assert own.histograms[0].qpa.unmeasured_phases == ["iron"]
    assert own.histograms[1].qpa.unmeasured_phases == []


def test_the_message_says_where_the_closing_stage_refined_the_scale():
    """The scale held in an early stage and refined in the last: the message
    names the stages that held it and says the answer is a measurement."""
    from rietx.refine import _phase_support_diagnostics

    structure, _ = _models(START_SCALES)
    held = StageResult(name="s", status="converged", n_iterations=1, cost_initial=1.0, cost_final=1.0, held=[FE_SCALE])
    closing = StageResult(name="close", status="converged", n_iterations=1, cost_initial=1.0, cost_final=1.0, held=[])
    args = (np.full(4, 0.5), np.array([5, 5, 5, 1]), (25.0, 44.0), [FE_SCALE],
            structure)
    (finding,) = _phase_support_diagnostics(*args, [held, closing])
    assert "held at the value handed in for stage s" in finding.message
    assert "refined in the last stage (close)" in finding.message
    (finding,) = _phase_support_diagnostics(*args, [held, held])
    assert "refined in the last stage" not in finding.message


def test_the_answer_quotes_no_fraction_for_a_scale_the_last_stage_held(
        four_phase_narrow_pattern, monkeypatch):
    """#1103's item 1 end to end: the stages held iron's scale, and the
    answer's own recount then finds a line (a zero shift moved one over the
    edge, simulated by emptying the recount once the result is being built).
    The scale is still the value handed in, so no fraction is quoted."""
    import importlib

    refine = importlib.import_module("rietx.refine")

    building = {"on": False}
    real_lineless, real_build = refine._lineless_phases, refine._build_result

    def lineless(model):
        return set() if building["on"] else real_lineless(model)

    def build(*args, **kw):
        building["on"] = True
        try:
            return real_build(*args, **kw)
        finally:
            building["on"] = False

    monkeypatch.setattr(refine, "_lineless_phases", lineless)
    monkeypatch.setattr(refine, "_build_result", build)
    ref = rx.Refinement(*_models(START_SCALES), solver="trf")
    res = ref.fit(four_phase_narrow_pattern,
                  plan=RefinementPlan(stages=SCALES_ONLY), telemetry=False)
    assert all(FE_SCALE in sr.held for sr in res.stages)
    assert res.qpa.unmeasured_phases == ["iron"]
    (iron,) = [q for q in res.qpa.phases if q.name == "iron"]
    assert iron.weight_fraction is None and iron.weight_fraction_stderr is None


def _simulate_a_line_entering_after_the_stages(monkeypatch):
    """Empty the line recount whenever a result is being built, so the stages
    hold iron's scale and the answer's own count then finds it a line (the
    crossing a refined zero shift makes, #1103)."""
    import importlib

    refine = importlib.import_module("rietx.refine")
    building = {"on": False}
    real_lineless, real_build = refine._lineless_phases, refine._build_result

    def lineless(model):
        return set() if building["on"] else real_lineless(model)

    def build(*args, **kw):
        building["on"] = True
        try:
            return real_build(*args, **kw)
        finally:
            building["on"] = False

    monkeypatch.setattr(refine, "_lineless_phases", lineless)
    monkeypatch.setattr(refine, "_build_result", build)


@pytest.fixture
def crossed_fit(four_phase_narrow_pattern, monkeypatch):
    _simulate_a_line_entering_after_the_stages(monkeypatch)
    structure, instrument = _models(START_SCALES)
    for phase in structure.phases:
        phase.particle_radius_um = 0.4
    ref = rx.Refinement(structure, instrument, solver="trf")
    res = ref.fit(four_phase_narrow_pattern,
                  plan=RefinementPlan(stages=SCALES_ONLY), telemetry=False)
    return ref, res, four_phase_narrow_pattern


def test_replay_quotes_no_fraction_for_a_scale_every_stage_held(crossed_fit):
    """#1103 round 2, item 1: a node records the scales its stage held, so a
    replay (which has no stage record) quotes iron no fraction either."""
    ref, res, pattern = crossed_fit
    assert res.qpa.unmeasured_phases == ["iron"]
    assert ref.history[res.node_id].metrics.held_scale_phases == [FE]
    replayed = rx.replay(ref.history, res.node_id, pattern)
    assert replayed.qpa.unmeasured_phases == ["iron"]
    assert replayed.qpa.unmeasured_held == ["iron"]
    (iron,) = [q for q in replayed.qpa.phases if q.name == "iron"]
    assert iron.weight_fraction is None


def test_every_text_gives_a_held_scales_cause_not_a_missing_line(crossed_fit):
    """Item 2: iron has a reflection at the answer, so no text says it has
    none; each says the scale was held, and the advice is not to widen."""
    from rietx.io.exporters import _qpa_caveats

    ref, res, _ = crossed_fit
    assert res.qpa.unmeasured_held == ["iron"]
    texts = {
        "caveat": " ".join(_qpa_caveats(res.qpa)),
        "skipped": res.qpa.microabsorption_skipped or "",
        "summary": ref.summary(deliverable="qpa"),
    }
    for name, text in texts.items():
        assert "no reflection in the fitted range" not in text, name
    assert "scale was held" in texts["caveat"]
    assert "scale was held" in texts["skipped"]
    (skipped,) = [d for d in res.diagnostics
                  if d.code == "MICROABSORPTION_SKIPPED"]
    assert "Widen the fitted range" not in skipped.suggestion
    assert "scale was held" in skipped.suggestion
    (finding,) = [d for d in res.diagnostics if d.code == "PHASE_UNCONSTRAINED"]
    assert "no weight fraction" in finding.message
    assert "scale was held" in finding.message
    assert "seed its scale" not in finding.suggestion


def test_a_restraint_freed_scale_is_not_called_a_measurement():
    """Item 3: no line in range, held in s0 and left free in the last stage
    by a weighted restraint: the message says so, never that a reflection
    reached the range."""
    from rietx.refine import _phase_support_diagnostics

    structure, _ = _models(START_SCALES)
    held = StageResult(name="s0", status="converged", n_iterations=1,
                       cost_initial=1.0, cost_final=1.0, held=[FE_SCALE])
    free = StageResult(name="s1", status="converged", n_iterations=1,
                       cost_initial=1.0, cost_final=1.0, held=[])
    args = (np.full(4, 0.0), np.array([5, 5, 5, 0]), (25.0, 44.0), [FE_SCALE],
            structure, [held, free])
    (finding,) = _phase_support_diagnostics(*args)
    assert "where a reflection reached the range" not in finding.message
    assert "weighted restraint" in finding.message
    assert "is a measurement" not in finding.message


def test_a_joint_message_names_the_histograms_that_held_the_scale():
    """Item 4: only histogram 0's iron scale was held."""
    from rietx.refine import _phase_support_diagnostics

    structure, _ = _models(START_SCALES)
    held = StageResult(name="s", status="converged", n_iterations=1,
                       cost_initial=1.0, cost_final=1.0,
                       held=[f"hist.0.{FE_SCALE}"])
    (finding,) = _phase_support_diagnostics(
        np.full(4, 0.5), np.array([5, 5, 5, 0]), (25.0, 44.0), [FE_SCALE],
        structure, [held, held])
    assert "in histogram 0" in finding.message


# ----------------------------------------------------------------------
# #1103's follow-ups: the trajectory flag (round 1, answer 5) and round 2's
# read-only observations
# ----------------------------------------------------------------------
def test_a_qpa_trajectory_marks_the_points_whose_basis_left_a_phase_out(
        pattern, four_phase_narrow_pattern):
    """Iron's lines leave the range in the middle two patterns, so corundum's
    fraction there is of the three phases seen and steps by 1.4 points with no
    change in the specimen.  Each point names the phases its basis left out."""
    from rietx.sequential import SequentialRefinement

    series = SequentialRefinement(*_models(START_SCALES)).fit(
        [pattern, four_phase_narrow_pattern, four_phase_narrow_pattern, pattern],
        plan=RefinementPlan(stages=SCALES_ONLY), labels=["w0", "n1", "n2", "w3"])
    corundum = series.qpa_trajectory("corundum")
    assert corundum.positions == [0, 1, 2, 3]
    assert corundum.unmeasured == [[], ["iron"], ["iron"], []]
    assert corundum.basis_changes
    assert "n1: relative to the phases seen; iron not measured" in str(corundum)
    assert series.resolve_trajectory("qpa.corundum").unmeasured == corundum.unmeasured
    iron = series.qpa_trajectory("iron")
    assert iron.positions == [0, 3] and not iron.basis_changes
    # the positive arm: every phase in range at every point, one basis
    whole = SequentialRefinement(*_models(START_SCALES)).fit(
        [pattern, pattern], plan=RefinementPlan(stages=SCALES_ONLY))
    corundum = whole.qpa_trajectory("corundum")
    assert corundum.unmeasured == [[], []] and not corundum.basis_changes
    assert "not measured" not in str(corundum)


def test_a_scale_held_through_a_variable_is_named_as_the_scale(
        four_phase_narrow_pattern):
    """The message sorted held columns by name, so a held ``vars.S_fe``
    driving iron's scale read "Its 1 structural parameter was held" and the
    scale clause never fired.  It is the scale, by what the column moves."""
    ref = rx.Refinement(*_models(START_SCALES), solver="trf")
    ref.add_variable("S_fe", START_SCALES[FE])
    ref.tie(FE_SCALE, "vars.S_fe")
    stages = [Stage(s.name, [*s.turn_on, "vars.*"]) for s in SCALES_ONLY]
    res = ref.fit(four_phase_narrow_pattern, plan=RefinementPlan(stages=stages),
                  telemetry=False)
    assert all(sr.held == ["vars.S_fe"] for sr in res.stages)
    (finding,) = _findings(res, "PHASE_UNCONSTRAINED")
    assert finding.where == ["vars.S_fe"]
    assert "Its scale was held at the value handed in" in finding.message
    assert "structural" not in finding.message


def test_a_held_variable_driving_a_cell_is_still_structural():
    """The positive arm: a held ``vars.a`` driving iron's cell edge is a
    structural parameter, and the scale clause stays silent."""
    from rietx.refine import _phase_support_diagnostics

    structure, _ = _models(START_SCALES)
    held = StageResult(name="s", status="converged", n_iterations=1,
                       cost_initial=1.0, cost_final=1.0, held=["vars.a"],
                       held_reach={"vars.a": [f"phases.{FE}.cell.a"]})
    (finding,) = _phase_support_diagnostics(
        np.full(4, 0.5), np.array([5, 5, 5, 0]), (25.0, 33.0), [],
        structure, [held])
    assert "Its 1 structural parameter was held for stage s." in finding.message
    assert "Its scale was held" not in finding.message


def test_per_histogram_scales_tied_to_one_variable_are_quoted_everywhere():
    """A constant ``ParametricEquation`` on iron's scale ties each pattern's
    own scale to ``vars.S_fe_0``, which the wide scan measures, so the narrow
    histogram's scale is the wide scan's measurement as a shared one is.  It
    left iron out under the tie and quoted it under ``SharingMap.shared``."""
    from rietx.multi import MultiHistogramRefinement
    from rietx.schemas.parametric import ParametricEquation

    structure, instrument = _models(START_SCALES)
    narrow = _wide_pattern(TT_NARROW)
    wide = _wide_pattern(np.arange(25.0, 90.0, 0.02))
    stages = [Stage(s.name, [*s.turn_on, "vars.*"]) for s in SCALES_ONLY]
    multi = MultiHistogramRefinement(
        structure, [instrument.model_copy(deep=True) for _ in range(2)],
        parametric=[ParametricEquation(name="S_fe", target=FE_SCALE,
                                       basis="constant")])
    res = multi.fit([narrow, wide], plan=RefinementPlan(stages=stages))
    assert all("vars.S_fe_0" in sr.freed and sr.held == [] for sr in res.stages)
    for hist in res.histograms:
        assert hist.qpa.unmeasured_phases == []
        (iron,) = [q for q in hist.qpa.phases if q.name == "iron"]
        assert iron.weight_fraction is not None


def test_a_variable_no_histogram_with_a_line_reaches_measures_nothing():
    """The negative arm: the same tie over two narrow scans, neither with a
    line of iron.  The stages hold the variable, and neither histogram
    quotes iron."""
    from rietx.multi import MultiHistogramRefinement
    from rietx.schemas.parametric import ParametricEquation

    structure, instrument = _models(START_SCALES)
    narrow = _wide_pattern(TT_NARROW)
    stages = [Stage(s.name, [*s.turn_on, "vars.*"]) for s in SCALES_ONLY]
    multi = MultiHistogramRefinement(
        structure, [instrument.model_copy(deep=True) for _ in range(2)],
        parametric=[ParametricEquation(name="S_fe", target=FE_SCALE,
                                       basis="constant")])
    res = multi.fit([narrow, narrow], plan=RefinementPlan(stages=stages))
    assert all("vars.S_fe_0" in sr.held for sr in res.stages)
    assert [h.qpa.unmeasured_phases for h in res.histograms] == [["iron"]] * 2


def test_a_polynomial_link_on_a_scale_leaves_the_narrow_scan_unmeasured():
    """The a + b·T arm of the tie above (#1176 round 1, question 2).  One wide
    scan sees iron and one narrow scan has no iron line; iron's scale is
    linked by a + b·T.  Two columns face one measured scale, so one direction
    of the pair is flat and the narrow scan's fraction would be the start
    value wearing an esd.  Only a constant link counts as measured, so the
    narrow histogram quotes no iron and the wide one does."""
    from rietx.multi import MultiHistogramRefinement
    from rietx.schemas.parametric import CoordinateTable, ParametricEquation

    structure, instrument = _models(START_SCALES)
    narrow = _wide_pattern(TT_NARROW)
    wide = _wide_pattern(np.arange(25.0, 90.0, 0.02))
    stages = [Stage(s.name, [*s.turn_on, "vars.*"]) for s in SCALES_ONLY]
    multi = MultiHistogramRefinement(
        structure, [instrument.model_copy(deep=True) for _ in range(2)],
        coordinates=CoordinateTable(columns={"T": [300.0, 500.0]}, units={"T": "K"}),
        parametric=[ParametricEquation(name="S_fe", target=FE_SCALE,
                                       basis="polynomial", terms=[[], ["T"]])])
    res = multi.fit([narrow, wide], plan=RefinementPlan(stages=stages))
    narrow_res, wide_res = res.histograms
    assert narrow_res.qpa.unmeasured_phases == ["iron"]
    assert wide_res.qpa.unmeasured_phases == []
