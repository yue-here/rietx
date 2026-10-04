"""WP-1902: the solve cost is the whole-profile χ² at frozen profile.

Public data only: NAC (``tests/data/11BM_NAC.fxye``, ``cod_1000236.cif``,
single line), the GSAS-II tutorial's lab Cu Kα₁/Kα₂ pattern (``FAP.XRA``,
``FAP.EXP``; ``tests/data/README.md``), and a synthetic Cu Kα₁,₂ two-phase
pattern built here from textbook rutile and CaF₂.

**The row that can fail is Ω·F against ``evaluate``.**  At ten random structure
moves, Ω built from a dummy-atom compile times the moved structure's |F|²
reproduces Rietveld-mode ``evaluate`` to ≤ 3.6e-16 of max|y| on both NAC and
FAP (bar 1e-14).  Two wrong Ω fail it: Lp dropped (the Le Bail reading) on
both, and Kα₂ at Kα₁'s Lp on FAP alone, by 2.6e-3, which NAC's single line
cannot see.  An identity of χ² − χ²_min against the same quadratic form passes
for any Ω, so it is not a test of Ω and is not here.

**The bar, and why it is relative to c.**  χ²(F) = c − (bᵀF)²/(FᵀMF) is a
difference of two terms of size c, so its rounding error scales with c, not
with χ²: at NAC's unrefined starting profile (c/χ² ≈ 1.1) the identity holds
to 1.8e-16·χ² (background held) and 8.3e-15·χ² (projected), and on a Le Bail
profile (c/χ² ≈ 36) to 3.6e-14·χ² and 2.2e-13·χ².  All four are ≤ 7.6e-15·c.
The bar is 1e-13·c, 13× above the worst of them.  Each test here was
revert-checked: a dropped projection term, a missed emission line, a wrong
low-rank factor or a removed gate makes the test aimed at it fail.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.model.forward import compile_model, d_spacings
from rietx.params.vector import ParameterTable
from rietx.schemas.pattern import PatternData
from rietx.solve import cost as solve_cost
from rietx.solve.cost import ExtractionRefused, SolveCost

sys.path.insert(0, str(Path(__file__).parent))
from test_acceptance_fap import build_fap_inputs  # noqa: E402
from test_acceptance_nac import build_nac_inputs  # noqa: E402

pytestmark = pytest.mark.xdist_group("solve-cost")

_KEYS = ("a", "b", "c", "alpha", "beta", "gamma")
LIMITS = (2.0, 24.0)
#: |χ²_QF − χ²_profile| ≤ IDENTITY_BAR · c (module docstring)
IDENTITY_BAR = 1e-13
#: max|Ω·F + rest − evaluate| ≤ OMEGA_BAR · max|evaluate|, the WP's 1e-14
OMEGA_BAR = 1e-14


def _values(structure, instrument):
    table = ParameterTable(structure, instrument)
    return table.decode(table.x0())


def _f2(model, values, ip=0):
    cp = model.phases[ip]
    cell = tuple(values[f"phases.{ip}.cell.{k}"] for k in _KEYS)
    return np.asarray(model._total_f2(ip, d_spacings(cp.reflections.index, *cell), values, cell))


def _profile_chi2(model, values, s, *, project, extra_columns=()):
    """Σw(y − y_calc)² at phase-0 scale ``scale·s``, the background held or
    refitted by plain least squares beside ``extra_columns``."""
    v = dict(values)
    v["phases.0.scale"] = values["phases.0.scale"] * s
    w = 1.0 / np.asarray(model.sigma) ** 2
    y = np.asarray(model.y_obs)
    if not project and not extra_columns:
        return float(np.sum(w * (y - np.asarray(model.evaluate(v))) ** 2))
    bragg = np.asarray(model.phase_component(0, v))
    cols = list(extra_columns) + ([*model.bkg_design] if project else [])
    if not project:
        y = y - np.asarray(model.background(v))
    X = np.column_stack(cols)
    coef = np.linalg.lstsq(X * np.sqrt(w)[:, None], (y - bragg) * np.sqrt(w), rcond=None)[0]
    return float(np.sum(w * (y - bragg - X @ coef) ** 2))


# -- NAC -------------------------------------------------------------------------

@pytest.fixture(scope="module")
def nac():
    return build_nac_inputs()


@pytest.fixture(scope="module")
def nac_scaled(nac):
    """NAC's COD structure with only scale and background refined,
    profile at its starting values, and the Rietveld compile at that state."""
    data, st, ins = nac
    ref = rx.Refinement(st, ins, history=False)
    ref.fit(data, plan=rx.RefinementPlan(stages=[rx.Stage(
        "sb", ["phases.*.scale", "instrument.background.*"])]),
        two_theta_limits=LIMITS, telemetry=False)
    S, inst = ref.fitted_structure, ref.fitted_instrument
    model = compile_model(S, inst, data, mode="rietveld", two_theta_limits=LIMITS)
    return model, _values(S, inst)


@pytest.fixture(scope="module")
def nac_lebail(nac):
    data, st, ins = nac
    ref = rx.Refinement(st, ins, history=False)
    result = ref.fit(data, mode="lebail", two_theta_limits=LIMITS, telemetry=False)
    assert result.status == "converged"
    return ref, data


@pytest.mark.parametrize("background", ["held", "projected"])
def test_identity_at_an_unrefined_profile(nac_scaled, background):
    """χ²_QF(F_true) = χ²_profile at its own closed-form scale, built
    straight from the true structure's Rietveld compile."""
    model, v = nac_scaled
    cost = SolveCost.from_model(model, v, background=background)
    chi, s = cost.chi2(_f2(model, v))
    prof = _profile_chi2(model, v, s, project=background == "projected")
    assert s > 0
    assert abs(chi - prof) <= IDENTITY_BAR * cost.c


@pytest.mark.parametrize("background", ["held", "projected"])
def test_identity_from_a_lebail_extraction(nac_lebail, background):
    """The S0 path: Le Bail → blind compile (one dummy atom) → the cost, then
    the true structure's |F|² against the true structure's own profile χ² at
    the extraction's cell, profile and background."""
    ref, data = nac_lebail
    cost = SolveCost.from_pawley(ref, data, background=background)
    S, inst = ref.fitted_structure, ref.fitted_instrument
    model = compile_model(S, inst, data, mode="rietveld", two_theta_limits=LIMITS)
    v = _values(S, inst)
    assert np.array_equal(cost.hkl, model.phases[0].reflections.index)
    chi, s = cost.chi2(_f2(model, v))
    prof = _profile_chi2(model, v, s / v["phases.0.scale"],
                         project=background == "projected")
    assert abs(chi - prof) <= IDENTITY_BAR * cost.c
    assert cost.chi2_floor < chi
    assert cost.records["extraction"] == {
        "mode": "lebail", "status": "converged", "rwp": ref.result_.statistics.rwp}


def test_floor_is_the_cost_s_own_unconstrained_solve(nac_lebail):
    """χ²_min = c − bᵀM⁺b equals a direct, unbounded least squares over free
    intensities and background coefficients on the same Ω.  It checks the
    projection algebra, not Ω (that is the ``evaluate`` row below)."""
    ref, data = nac_lebail
    cost = SolveCost.from_pawley(ref, data)
    S = solve_cost.blind_structure(ref.fitted_structure, 0, "pawley")
    model = compile_model(S, ref.fitted_instrument, data, mode="rietveld",
                          two_theta_limits=LIMITS)
    y, w, om, X = solve_cost._design(model, _values(S, ref.fitted_instrument), 0,
                                     "projected", "pawley")
    A = np.hstack([om.toarray(), X]) * np.sqrt(w)[:, None]
    coef = np.linalg.lstsq(A, y * np.sqrt(w), rcond=None)[0]
    direct = float(np.sum((y * np.sqrt(w) - A @ coef) ** 2))
    assert abs(cost.chi2_floor - direct) <= IDENTITY_BAR * cost.c
    assert np.allclose(cost.intensities, coef[:len(cost.b)], rtol=0,
                       atol=1e-9 * np.abs(coef[:len(cost.b)]).max())


def test_a_pawley_fit_sits_on_or_above_its_own_floor(nac):
    """From a Pawley fit: the free-intensity minimum at the fit's own profile can
    only be at or below the fit's Σw(y − y_calc)², which carries the Pawley
    restraint rows and the ridge the floor does not."""
    data, st, ins = nac
    ref = rx.Refinement(st, ins, history=False)
    result = ref.fit(data, mode="pawley", two_theta_limits=(2.0, 12.0), telemetry=False)
    cost = SolveCost.from_pawley(ref, data)
    assert cost.records["extraction"]["mode"] == "pawley"
    r = (np.asarray(result.y_obs) - np.asarray(result.y_calc)) / np.asarray(result.sigma)
    assert cost.n_points == len(r)
    assert cost.chi2_floor <= float(r @ r)
    assert cost.chi2_floor > 0.99 * float(r @ r)


def test_sparse_low_rank_equals_the_dense_projection(nac_lebail):
    """M₀ − VVᵀ, b and c against the dense P = W − WX(XᵀWX)⁺XᵀW built directly.

    The oracle's (XᵀWX)⁺ is equilibrated, as the code's is: an unequilibrated
    ``pinv`` cuts what an unequilibrated eigensolve cuts and would agree with
    a wrong cutoff (``test_chi2_does_not_depend_on_the_impurity_s_stored_scale``
    measures the cutoff itself)."""
    ref, data = nac_lebail
    cost = SolveCost.from_pawley(ref, data)
    assert cost.V.shape[1] == cost.n_nuisance > 0
    assert cost.M0.nnz < 0.25 * len(cost.b) ** 2     # banded, not dense
    S = solve_cost.blind_structure(ref.fitted_structure, 0, "pawley")
    model = compile_model(S, ref.fitted_instrument, data, mode="rietveld",
                          two_theta_limits=LIMITS)
    y, w, om, X = solve_cost._design(model, _values(S, ref.fitted_instrument), 0,
                                     "projected", "pawley")
    Om = om.toarray()
    WX = w[:, None] * X
    G = X.T @ WX
    dg = 1.0 / np.sqrt(np.diag(G))
    Gp = dg[:, None] * np.linalg.pinv(G * np.outer(dg, dg), rcond=1e-12,
                                      hermitian=True) * dg   # D(DGD)⁺D, not eigh
    OX, YX = Om.T @ WX, WX.T @ y
    M = Om.T @ (w[:, None] * Om) - OX @ Gp @ OX.T
    b = Om.T @ (w * y) - OX @ (Gp @ YX)
    c = float(y @ (w * y) - YX @ (Gp @ YX))
    F = np.random.default_rng(0).random((6, len(b))) * np.abs(cost.intensities).max()
    assert np.max(np.abs(cost.matvec(F) - F @ M)) <= 1e-13 * np.max(np.abs(F @ M))
    assert np.max(np.abs(cost.b - b)) <= 1e-13 * np.max(np.abs(b))
    assert abs(cost.c - c) <= 1e-13 * c
    batch = cost.chi2_batch(F)
    assert np.allclose(batch, [cost.chi2(f)[0] for f in F], rtol=1e-13, atol=0)


# -- Ω·F against Rietveld-mode evaluate (the WP's row) ----------------------------

def _moved(values, structure, rng):
    """``values`` with every coordinate, site degree of freedom and Biso of
    phase 0 moved at random: the atoms change, the frozen profile does not."""
    w = dict(values)
    for ia in range(len(structure.phases[0].atoms)):
        for q in ("x", "y", "z", "dof.0", "dof.1", "dof.2"):
            key = f"phases.0.atoms.{ia}.{q}"
            if key in w:
                w[key] += rng.normal(scale=0.02)
        key = f"phases.0.atoms.{ia}.biso"
        if key in w:
            w[key] = abs(w[key] + rng.normal(scale=0.3))
    return w


def _lp_by_line(model, values):
    """Per line, Lp at each reflection's position, from the compile's own
    Lp function (the wrong arms need it; the cost never reads it)."""
    from rietx.model.forward import lorentz_polarization
    pol = values["instrument.polarization"]
    return [np.asarray(lorentz_polarization(np.asarray(p[0]), pol))
            for p in model.phase_peaks(0, values)]


def _wrong_no_lp(lines, lp):
    """Ω with Lp divided out of every line: what a Le Bail compile carries."""
    return sum((om @ _diag(1.0 / lpl) for om, lpl in zip(lines, lp)), 0 * lines[0])


def _wrong_ka2_at_ka1_lp(lines, lp):
    """Ω with Kα₂ at Kα₁'s Lp: one I across the doublet, no per-line Lp."""
    return lines[0] + sum((om @ _diag(lp[0] / lpl) for om, lpl in zip(lines[1:], lp[1:])),
                          0 * lines[0])


def _diag(v):
    from scipy.sparse import diags
    return diags(np.where(np.isfinite(v), v, 0.0))


@pytest.fixture(scope="module", params=["NAC", "FAP"])
def moved_case(request):
    """(model of the true structure, Ω lines from its dummy-atom compile,
    values, ten moves).  No fit: the frozen profile is the input's."""
    if request.param == "NAC":
        (data, st, ins), limits = build_nac_inputs(), LIMITS
    else:
        (data, st, ins), limits = build_fap_inputs(), (15.0, 130.0)
    model = compile_model(st, ins, data, mode="rietveld", two_theta_limits=limits)
    blind = solve_cost.blind_structure(st, 0, "pawley")
    bmodel = compile_model(blind, ins, data, mode="rietveld", two_theta_limits=limits)
    assert np.array_equal(bmodel.phases[0].reflections.index,
                          model.phases[0].reflections.index)
    v = _values(st, ins)
    lines = solve_cost.omega_lines(bmodel, 0, _values(blind, ins))
    rng = np.random.default_rng(1902)
    return request.param, model, lines, v, [_moved(v, st, rng) for _ in range(10)]


def _omega_residual(model, omega, v, moves):
    """max over the moves of max|Ω·(s·F) + rest − evaluate| / max|evaluate|;
    the dummy compile's scale is 1, so the true scale multiplies F."""
    worst = 0.0
    for w in moves:
        y = np.asarray(model.evaluate(w))
        rest = y - np.asarray(model.phase_component(0, w))
        yq = omega @ (w["phases.0.scale"] * _f2(model, w)) + rest
        worst = max(worst, float(np.max(np.abs(yq - y)) / np.max(np.abs(y))))
    return worst


def test_omega_times_f2_is_rietveld_evaluate_at_ten_moves(moved_case):
    name, model, lines, v, moves = moved_case
    assert len(lines) == (2 if name == "FAP" else 1)       # the doublet is exercised
    F0 = _f2(model, v)
    assert all(np.max(np.abs(_f2(model, w) - F0)) > 0.05 * np.max(F0) for w in moves)
    assert _omega_residual(model, sum(lines[1:], lines[0]), v, moves) <= OMEGA_BAR


def test_a_wrong_omega_fails_the_evaluate_row(moved_case):
    """The negative arm: Lp dropped fails on both; Kα₂ at Kα₁'s Lp fails on
    the doublet by orders of magnitude and is invisible on a single line."""
    name, model, lines, v, moves = moved_case
    lp = _lp_by_line(model, v)
    assert _omega_residual(model, _wrong_no_lp(lines, lp), v, moves) > 1e3 * OMEGA_BAR
    ka2 = _omega_residual(model, _wrong_ka2_at_ka1_lp(lines, lp), v, moves)
    if name == "FAP":
        assert ka2 > 1e9 * OMEGA_BAR
    else:
        assert ka2 <= OMEGA_BAR


# -- refusals --------------------------------------------------------------------

def test_refuses_an_unconverged_extraction(nac):
    data, st, ins = nac
    ref = rx.Refinement(st, ins, history=False)
    result = ref.fit(data, mode="lebail", two_theta_limits=(2.0, 12.0), telemetry=False,
                     plan=rx.RefinementPlan(stages=[rx.Stage(
                         "cell", ["phases.*.cell.*", "instrument.background.*"],
                         max_iter=1)]))
    assert result.status == "max_iter"
    with pytest.raises(ExtractionRefused, match="'max_iter'") as err:
        SolveCost.from_pawley(ref, data)
    assert err.value.reason == "unconverged"


def test_refuses_a_converged_fit_far_from_the_data(nac):
    """A 3 % cell error: the solver reports ``converged`` at Rwp ≈ 29."""
    data, st, ins = nac
    wrong = st.model_copy(deep=True)
    for k in ("a", "b", "c"):
        getattr(wrong.phases[0].cell, k).value *= 1.03
    ref = rx.Refinement(wrong, ins, history=False)
    result = ref.fit(data, mode="lebail", two_theta_limits=(2.0, 12.0), telemetry=False,
                     plan=rx.RefinementPlan(stages=[rx.Stage("b", ["instrument.background.*"])]))
    assert result.status == "converged"
    with pytest.raises(ExtractionRefused, match="carries MODEL_FAR_FROM_DATA") as err:
        SolveCost.from_pawley(ref, data)
    assert err.value.reason == "poor"


def test_refuses_a_converged_extraction_carrying_any_error_level_code(nac_lebail,
                                                                       monkeypatch):
    """The "poor" bar is ``RefinementResult.usable``, not a copy of one code's
    threshold: an error-level code it has never heard of refuses too (WP-1902)."""
    ref, data = nac_lebail
    error = rx.Diagnostic(level="error", code="SOME_FUTURE_ERROR", message="x")
    unusable = ref.result_.model_copy(
        update={"diagnostics": [*ref.result_.diagnostics, error]})
    assert unusable.status == "converged" and not unusable.usable
    monkeypatch.setattr(ref, "result_", unusable)
    with pytest.raises(ExtractionRefused, match="carries SOME_FUTURE_ERROR") as err:
        SolveCost.from_pawley(ref, data)
    assert err.value.reason == "poor"


def test_refuses_a_rietveld_fit_and_no_fit(nac, nac_lebail):
    data, st, ins = nac
    ref = rx.Refinement(st, ins, history=False)
    with pytest.raises(ExtractionRefused, match="no fit") as err:
        SolveCost.from_pawley(ref, data)
    assert err.value.reason == "not_an_extraction"
    ref.fit(data, plan=rx.RefinementPlan(stages=[rx.Stage(
        "sb", ["phases.*.scale", "instrument.background.*"])]),
        two_theta_limits=(2.0, 12.0), telemetry=False)
    with pytest.raises(ExtractionRefused, match="'rietveld'") as err:
        SolveCost.from_pawley(ref, data)
    assert err.value.reason == "rietveld"


def test_refuses_data_other_than_the_fitted_pattern(nac_lebail):
    """An excluded region the fit did not have changes the fitted points."""
    ref, data = nac_lebail
    cut = data.model_copy(update={"excluded_regions": [(10.0, 11.0)]})
    with pytest.raises(ValueError, match="fitted points where the extraction fitted"):
        SolveCost.from_pawley(ref, cut)


def test_does_not_refuse_the_converged_extraction(nac_lebail):
    ref, data = nac_lebail
    assert ref.result_.status == "converged"
    assert ref.result_.statistics.rwp < 0.2
    SolveCost.from_pawley(ref, data)


def test_refuses_extinction_on_the_solved_phase(nac_lebail):
    ref, data = nac_lebail
    S = solve_cost.blind_structure(ref.fitted_structure, 0, "pawley")
    S.phases[0].extinction.value = 50.0
    model = compile_model(S, ref.fitted_instrument, data, mode="rietveld",
                          two_theta_limits=LIMITS)
    with pytest.raises(ExtractionRefused, match="extinction") as err:
        SolveCost.from_model(model, _values(S, ref.fitted_instrument))
    assert err.value.reason == "nonlinear"


def _magnetic_structure():
    P = rx.Parameter
    return rx.Structure(phases=[rx.Phase(
        name="MnF2", space_group="P 42/m n m",
        cell=_cell(4.8734, 4.8734, 3.3099, 90, 90, 90),
        atoms=[_atom("Mn", "Mn", 0, 0, 0, 0.4), _atom("F", "F", 0.305, 0.305, 0, 0.4)],
        scale=P(value=1.0))])


def test_refuses_a_magnetic_phase():
    from rietx.schemas.structure import Moment
    st = _magnetic_structure()
    st.phases[0].atoms[0].moment = Moment.from_values((0.0, 0.0, 4.6), "Mn2+")
    st.phases[0].magnetic_symmetry = "136.499"
    ins = rx.Instrument.constant_wavelength_neutron(2.41, fwhm_deg=0.3)
    tt = np.arange(20.0, 80.0, 0.02)
    flat = PatternData(two_theta=list(tt), intensity=list(np.ones_like(tt)))
    with pytest.raises(ExtractionRefused, match="magnetic") as err:
        SolveCost.from_pawley(rx.Refinement(st, ins, history=False), flat)
    assert err.value.reason == "magnetic"     # before the no-fit check
    model = compile_model(st, ins, flat, mode="rietveld")
    with pytest.raises(ExtractionRefused, match="magnetic") as err:
        SolveCost.from_model(model, _values(st, ins))
    assert err.value.reason == "magnetic"
    # the moment scatters no X-rays, and the same phase without it is accepted
    xray = rx.Instrument.debye_scherrer(1.54)
    SolveCost.from_model(compile_model(st, xray, flat, mode="rietveld"), _values(st, xray))
    plain = _magnetic_structure()
    SolveCost.from_model(compile_model(plain, ins, flat, mode="rietveld"),
                         _values(plain, ins))


def test_refuses_a_projected_p_spline_background():
    """Its coefficients are penalised, not free, so projecting them as free
    columns is not the extraction's objective; held, it is accepted."""
    from rietx.schemas.instrument import BackgroundPSpline
    st = _magnetic_structure()
    ins = rx.Instrument.debye_scherrer(1.54)
    ins.background = BackgroundPSpline.for_range(20.0, 80.0, knot_step_deg=10.0)
    tt = np.arange(20.0, 80.0, 0.02)
    flat = PatternData(two_theta=list(tt), intensity=list(np.ones_like(tt)))
    model = compile_model(st, ins, flat, mode="rietveld")
    with pytest.raises(ExtractionRefused, match="P-spline") as err:
        SolveCost.from_model(model, _values(st, ins))
    assert err.value.reason == "nonlinear"
    SolveCost.from_model(model, _values(st, ins), background="held")


# -- a synthetic two-phase pattern: the nuisance modes ---------------------------

def _cell(*v):
    return rx.Cell(**{k: rx.Parameter(value=float(x)) for k, x in zip(_KEYS, v)})


def _atom(label, sp, x, y, z, b):
    return rx.Atom(label=label, species=sp, x=rx.Parameter(value=x), y=rx.Parameter(value=y),
                   z=rx.Parameter(value=z), biso=rx.Parameter(value=b))


@pytest.fixture(scope="module")
def two_phase():
    """Rutile (x_O = 0.3048) with a CaF₂ impurity, Cu Kα₁,₂,
    Poisson noise, then a Le Bail extraction of both phases from the truth."""
    rutile = rx.Phase(name="TiO2", space_group="P 42/m n m",
                      cell=_cell(4.5937, 4.5937, 2.9587, 90, 90, 90),
                      atoms=[_atom("Ti", "Ti4+", 0, 0, 0, 0.4),
                             _atom("O", "O2-", 0.3048, 0.3048, 0, 0.6)],
                      scale=rx.Parameter(value=1e-3))
    caf2 = rx.Phase(name="CaF2", space_group="F m -3 m",
                    cell=_cell(5.4631, 5.4631, 5.4631, 90, 90, 90),
                    atoms=[_atom("Ca", "Ca2+", 0, 0, 0, 0.6),
                           _atom("F", "F1-", 0.25, 0.25, 0.25, 0.9)],
                    scale=rx.Parameter(value=4e-4))
    ins = rx.Instrument.bragg_brentano(radiation="CuKa")
    ins.source.dispersion = None
    st = rx.Structure(phases=[rutile, caf2])
    tt = np.arange(15, 120, 0.02)
    flat = PatternData(two_theta=list(tt), intensity=list(np.ones_like(tt)))
    y = np.asarray(compile_model(st, ins, flat, mode="rietveld").evaluate(_values(st, ins)))
    yo = np.random.default_rng(4).poisson(y * 1e3 + 50.0).astype(float)
    data = PatternData(two_theta=list(tt), intensity=list(yo),
                       sigma=list(np.sqrt(np.maximum(yo, 1))))
    ref = rx.Refinement(st, ins, history=False)
    result = ref.fit(data, mode="lebail", telemetry=False, plan=rx.RefinementPlan(
        stages=[rx.Stage("b", ["instrument.background.*"])]))
    assert result.status == "converged"
    return ref, data


def test_scale_nuisance_is_the_profile_chi2_with_one_free_impurity_scale(two_phase):
    ref, data = two_phase
    cost = SolveCost.from_pawley(ref, data, nuisance="scale")
    S, inst = ref.fitted_structure, ref.fitted_instrument
    model = compile_model(S, inst, data, mode="rietveld")
    v = _values(S, inst)
    assert sum(k.startswith("instrument.source.lines.") and k.endswith(".weight")
               for k in v) == 2    # Kα₁,₂: the per-line factors are exercised
    assert cost.n_nuisance == model.bkg_design.shape[0] + 1
    chi, s = cost.chi2(_f2(model, v))
    impurity = np.asarray(model.phase_component(1, v))
    prof = _profile_chi2(model, v, s / v["phases.0.scale"], project=True,
                         extra_columns=[impurity])
    assert abs(chi - prof) <= IDENTITY_BAR * cost.c


def test_scale_nuisance_keeps_what_free_impurity_intensities_discard(two_phase):
    """The impurity's own profile lies in the span of its free-intensity columns,
    so for every |F|² vector χ²_scale ≥ χ²_pawley; and ``"pawley"`` spends one
    column per live impurity reflection where ``"scale"`` spends one."""
    ref, data = two_phase
    scale = SolveCost.from_pawley(ref, data, nuisance="scale")
    pawley = SolveCost.from_pawley(ref, data, nuisance="pawley")
    n_bkg = scale.n_nuisance - 1
    assert pawley.n_nuisance - n_bkg > 10
    F = np.abs(np.random.default_rng(1).normal(size=(8, len(scale.b))))
    F = np.vstack([F, np.abs(scale.intensities)])
    gap = scale.chi2_batch(F) - pawley.chi2_batch(F)
    assert np.all(gap >= -IDENTITY_BAR * scale.c)
    assert np.all(gap > 0)
    assert scale.chi2_floor >= pawley.chi2_floor


def _blind_cost(ref, data, structure, nuisance="scale"):
    S = solve_cost.blind_structure(structure, 0, nuisance)
    model = compile_model(S, ref.fitted_instrument, data, mode="rietveld")
    return model, SolveCost.from_model(model, _values(S, ref.fitted_instrument),
                                       nuisance=nuisance)


def test_chi2_does_not_depend_on_the_impurity_s_stored_scale(two_phase):
    """The stored impurity scale is a free nuisance coefficient, so χ² cannot
    depend on it.  Swept over eight decades (1e-4 is near the fixture's; 1 is
    the schema default, which Le Bail and Pawley leave as declared) against a
    direct least squares over unit-norm columns √W·[Ω·F, impurity, background],
    an SVD of the design that never forms XᵀWX.  Unequilibrated, the cut at
    1e-12·λmax let the impurity column set the background's cutoff: −4e-4 at
    1e2 and ×37 at 1e4 (#580 review)."""
    ref, data = two_phase
    S0 = ref.fitted_structure
    truth = compile_model(S0, ref.fitted_instrument, data, mode="rietveld")
    f2 = _f2(truth, _values(S0, ref.fitted_instrument))
    got = []
    for scale in 10.0 ** np.arange(-4, 5):
        st = S0.model_copy(deep=True)
        st.phases[1].scale.value = float(scale)
        model, cost = _blind_cost(ref, data, st)
        y, w, om, X = solve_cost._design(model, _values(
            solve_cost.blind_structure(st, 0, "scale"), ref.fitted_instrument),
            0, "projected", "scale")
        A = np.column_stack([om @ f2, X]) * np.sqrt(w)[:, None]
        A = A / np.linalg.norm(A, axis=0)
        coef = np.linalg.lstsq(A, y * np.sqrt(w), rcond=None)[0]
        assert coef[0] > 0
        r = y * np.sqrt(w) - A @ coef
        chi, _ = cost.chi2(f2)
        assert abs(chi - float(r @ r)) <= IDENTITY_BAR * cost.c, scale
        got.append(chi)
    assert np.ptp(got) <= IDENTITY_BAR * cost.c


def test_a_phase_with_restraints_is_blinded_without_them(two_phase):
    """The dummy swap leaves one atom, so a restraint naming atom 1 would fail
    the Phase validator on assignment; the cost reads no restraint row, so a
    blinded phase carries none.  A ``"scale"`` impurity keeps its atoms and
    its restraints."""
    ref, data = two_phase
    st = ref.fitted_structure.model_copy(deep=True)
    for ph in st.phases:
        ph.restraints = [rx.BondRestraint(atom_i=0, atom_j=1, target=1.95, sigma=0.01)]
    blind = solve_cost.blind_structure(st, 0, "scale")
    assert blind.phases[0].restraints == [] and len(blind.phases[0].atoms) == 1
    assert len(blind.phases[1].restraints) == 1 and len(blind.phases[1].atoms) == 2
    blind = solve_cost.blind_structure(st, 0, "pawley")
    assert all(ph.restraints == [] for ph in blind.phases)
    _, cost = _blind_cost(ref, data, st, nuisance="pawley")
    _, plain = _blind_cost(ref, data, ref.fitted_structure, nuisance="pawley")
    assert cost.chi2_floor == plain.chi2_floor


# -- refused by name: what the form would leave out in silence (#580 item 5) -----

def _rutile(k=None):
    return rx.Phase(name="TiO2", space_group="P 42/m n m",
                    cell=_cell(4.5937, 4.5937, 2.9587, 90, 90, 90),
                    atoms=[_atom("Ti", "Ti", 0, 0, 0, 0.4), _atom("O", "O", 0.3048, 0.3048, 0, 0.6)],
                    scale=rx.Parameter(value=1e-3), propagation_vector=k)


def _caf2(k=None):
    return rx.Phase(name="CaF2", space_group="F m -3 m",
                    cell=_cell(5.4631, 5.4631, 5.4631, 90, 90, 90),
                    atoms=[_atom("Ca", "Ca", 0, 0, 0, 0.6), _atom("F", "F", 0.25, 0.25, 0.25, 0.9)],
                    scale=rx.Parameter(value=4e-4), propagation_vector=k)


def _flat(lo, hi):
    tt = np.arange(lo, hi, 0.02)
    return PatternData(two_theta=list(tt), intensity=list(np.full_like(tt, 10.0)))


def _in_range(cp):
    """The oracle's own reading of the frozen windows: any line, nonempty."""
    return np.any(cp.win[:, :, 1] > cp.win[:, :, 0], axis=0)


def _xray():
    ins = rx.Instrument.debye_scherrer(1.54)
    ins.source.dispersion = None
    return ins


@pytest.mark.parametrize("nuisance", ["pawley", "scale"])
def test_refuses_satellites_on_the_solved_phase(nuisance):
    """On main the cost was built with an empty Ω column for every satellite in
    range (37 here): the Rietveld compile gives a satellite factor 0, while the
    data carries the peak.  The count is checked against the windows."""
    st, ins = rx.Structure(phases=[_rutile(("0", "0", "1/2")), _caf2()]), _xray()
    model = compile_model(st, ins, _flat(15, 120), mode="rietveld")
    cp = model.phases[0]
    n = int(np.sum(cp.reflections.is_satellite & _in_range(cp)))
    assert n > 10
    with pytest.raises(ExtractionRefused, match=rf"the solved phase has {n} satellite") as err:
        SolveCost.from_model(model, _values(st, ins), nuisance=nuisance)
    assert err.value.reason == "satellite"
    assert "(0, 0, 1)+k" in str(err.value)


def test_refuses_satellites_through_from_pawley():
    """The extraction path: a Le Bail fit with k declared extracts the
    satellites, and the blind compile keeps k, so the refusal is reached."""
    st, ins = rx.Structure(phases=[_rutile(("0", "0", "1/2"))]), _xray()
    tt = np.arange(20.0, 70.0, 0.02)
    flat = PatternData(two_theta=list(tt), intensity=list(np.ones_like(tt)))
    y = np.asarray(compile_model(st, ins, flat, mode="rietveld").evaluate(_values(st, ins)))
    yo = np.random.default_rng(5).poisson(y * 1e3 + 50.0).astype(float)
    data = PatternData(two_theta=list(tt), intensity=list(yo),
                       sigma=list(np.sqrt(np.maximum(yo, 1))))
    ref = rx.Refinement(st, ins, history=False)
    assert ref.fit(data, mode="lebail", telemetry=False, plan=rx.RefinementPlan(
        stages=[rx.Stage("b", ["instrument.background.*"])])).status == "converged"
    with pytest.raises(ExtractionRefused, match="satellite reflection") as err:
        SolveCost.from_pawley(ref, data)
    assert err.value.reason == "satellite"


@pytest.mark.parametrize("nuisance", ["pawley", "scale"])
def test_refuses_a_nuisance_phase_s_satellites(nuisance):
    """``"pawley"`` dropped them with the ``live`` filter (n_nuisance was the
    same as without k); ``"scale"`` projected an impurity profile that is zero
    at them.  Either way the data's satellite peaks had no column."""
    st, ins = rx.Structure(phases=[_rutile(), _caf2(("1/2", "1/2", "1/2"))]), _xray()
    model = compile_model(st, ins, _flat(15, 120), mode="rietveld")
    cp = model.phases[1]
    n = int(np.sum(cp.reflections.is_satellite & _in_range(cp)))
    assert n > 10
    with pytest.raises(ExtractionRefused, match=rf"nuisance phase 1 has {n} satellite") as err:
        SolveCost.from_model(model, _values(st, ins), nuisance=nuisance)
    assert err.value.reason == "satellite"


@pytest.fixture(scope="module")
def harmonic():
    """λ = 2.4 Å with its λ/2 harmonic over 10–150°: every reflection with
    d < 1.2 Å is beyond line 0's sphere and reached by line 1 alone."""
    ins = rx.Instrument.constant_wavelength_neutron(2.4, fwhm_deg=0.3, harmonics=True)
    assert [ln.wavelength.value for ln in ins.source.lines] == [2.4, 1.2]
    return ins, _flat(10, 150)


def test_refuses_a_reflection_only_the_harmonic_reaches_under_pawley(harmonic):
    """The oracle is geometric: d below λ₀/2 and a live window on line 1.
    On main those 26 CaF₂ columns came out empty and were dropped."""
    ins, data = harmonic
    st = rx.Structure(phases=[_rutile(), _caf2()])
    model = compile_model(st, ins, data, mode="rietveld")
    cp = model.phases[1]
    beyond = np.asarray(cp.reflections.d) < 2.4 / 2
    n = int(np.sum(beyond & (cp.win[1, :, 1] > cp.win[1, :, 0])))
    assert n > 10
    with pytest.raises(ExtractionRefused, match=rf"nuisance phase 1 has {n} reflection") as err:
        SolveCost.from_model(model, _values(st, ins), nuisance="pawley")
    assert err.value.reason == "secondary_line_only"
    assert "(4, 2, 2)" in str(err.value)


def test_the_harmonic_is_not_refused_under_scale_or_on_the_solved_phase(harmonic):
    """The negative arms.  ``"scale"`` projects the impurity's whole calculated
    profile, every line drawn; the solved phase reads its factor off |F|², so
    its λ/2-only reflections are carried, and Ω·F reproduces ``evaluate``."""
    ins, data = harmonic
    two = rx.Structure(phases=[_rutile(), _caf2()])
    SolveCost.from_model(compile_model(two, ins, data, mode="rietveld"),
                         _values(two, ins), nuisance="scale")
    one = rx.Structure(phases=[_caf2()])
    v = _values(one, ins)
    # The data carry the phase.  On the flat pattern the background explains
    # everything, so the projected data are rounding noise (|b| ~ 1e-14) and the
    # scale's sign with them: it came out 0.0 on Windows on 2026-10-02 (WP-1541).
    y = np.asarray(compile_model(one, ins, data, mode="rietveld").evaluate(v))
    data = PatternData(two_theta=data.two_theta, intensity=list(y))
    model = compile_model(one, ins, data, mode="rietveld")
    cost = SolveCost.from_model(model, v, nuisance="pawley")
    beyond = np.asarray(model.phases[0].reflections.d) < 2.4 / 2
    assert np.sum(beyond & _in_range(model.phases[0])) > 10
    blind = solve_cost.blind_structure(one, 0, "pawley")
    bmodel = compile_model(blind, ins, data, mode="rietveld")
    omega = sum(solve_cost.omega_lines(bmodel, 0, _values(blind, ins))[1:],
                solve_cost.omega_lines(bmodel, 0, _values(blind, ins))[0])
    assert np.all(omega.getnnz(axis=0)[beyond & _in_range(model.phases[0])] > 0)
    assert _omega_residual(model, omega, v, [v]) <= OMEGA_BAR
    # Scale 1 to rounding means every line's reflections are in the cost: one
    # dropped λ/2-only reflection leaves its peak unexplained and moves it.
    assert cost.chi2(_f2(model, v))[1] == pytest.approx(1.0, rel=1e-9)
