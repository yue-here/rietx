"""Primary extinction (WP-0506, Sabine model).

The reference is a faithful scalar transcription of GSAS-II ``GetPwdrExt`` /
``GetPwdrExtDerv`` (behavioural reference only; no code is ported, see
ATTRIBUTION.md).  Since WP-2044 rietx evaluates the Laue factor in closed form,
e^(−x)·[I₀(x) + I₁(x)], where GSAS-II truncates a series below x = 1 and an
asymptote above it.  So the transcription pins the Bragg half, the Xpol
constant and the blend to ~1e-10, and the Laue half to the measured band
between the two forms.  The closed form itself is pinned to a quadrature of
the Laue integral it is derived from.
"""

from __future__ import annotations

import math
import warnings

import numpy as np
import pytest

from rietx.model.extinction import (
    _laue_and_deriv,
    sabine_extinction,
    sabine_extinction_and_dx,
)

# a spread of |F|², 2θ and ext chosen so both Laue branches (x ≤ 1 and x > 1)
# are exercised across the reflection list (the strong low-angle rows cross
# x = 1, the weak high-angle rows stay well below it)
WAVE = 1.5406
VOL = 20.0
TT = np.array([8.0, 17.0, 25.0, 44.0, 63.0, 92.0, 121.0, 158.0])
F2 = np.array([9.0e4, 4.2e4, 2.1e4, 8.0e3, 3.0e3, 1.1e3, 4.0e2, 1.2e2])


# -- an independent GSAS-II GetPwdrExt / GetPwdrExtDerv reference -------

_COEF = [-0.5, 0.25, -0.10416667, 0.036458333, -0.0109375, 2.8497409e-3]


def _gsas_laue(x: float) -> tuple[float, float]:
    """GSAS-II's Laue factor and its slope: the six-term series on 0 < x ≤ 1,
    the two-term asymptote above, 1 and 0 at x ≤ 0."""
    if x <= 0.0:
        return 1.0, 0.0
    if x <= 1.0:
        return (1.0 + sum(_COEF[i] * x ** (i + 1) for i in range(6)),
                sum((i + 1) * _COEF[i] * x ** i for i in range(6)))
    pi2 = math.sqrt(2.0 / math.pi)
    return (pi2 * (1.0 - 0.125 / x) / math.sqrt(x),
            pi2 / math.sqrt(x) * (-0.5 / x + 0.1875 / x ** 2))


#: the band between the closed-form Laue factor and GSAS-II's two branches,
#: measured on a dense grid (WP-2044).  Each row is (lo, hi, value, slope):
#: on the interval, |ΔE_L|/E_L stays under ``value`` and |ΔdE_L/dx| under
#: ``slope``.  The difference grows towards x = 1 from both sides, so each bar
#: is the difference at the end of its interval nearer 1, rounded up.
_GSAS_BAND = (
    (0.0, 0.1, 5.0e-11, 3.6e-9),
    (0.1, 0.25, 4.0e-8, 1.0e-6),
    (0.25, 0.5, 5.6e-6, 6.3e-5),
    (0.5, 1.0, 8.0e-4, 3.7e-3),
    (1.0, 2.0, 3.7e-2, 4.2e-2),
    (2.0, 5.0, 9.9e-3, 7.0e-3),
    (5.0, np.inf, 1.2e-3, 2.2e-4),
)


def _band(x: float) -> tuple[float, float]:
    """The (value, slope) bar at x: intervals are (lo, hi] up to x = 1, where
    GSAS-II's series holds, and (lo, hi] above it too, x = 1 itself excluded."""
    for lo, hi, value, slope in _GSAS_BAND:
        if lo < x <= hi:
            return value, slope
    raise AssertionError(f"x = {x} outside the band table")


def _gsas_ext(f2: float, tt_deg: float, ext: float) -> float:
    sth2 = math.sin(math.radians(tt_deg / 2.0)) ** 2
    c2th = 1.0 - 2.0 * sth2
    flv2 = f2 * (WAVE / VOL) ** 2 * 0.079411 * (1.0 + c2th ** 2) / 2.0
    xfac = flv2 * ext
    exb = 1.0 / math.sqrt(1.0 + xfac) if xfac > -1.0 else 1.0
    exl = 1.0
    if 0 < xfac <= 1.0:
        exl += sum(_COEF[i] * xfac ** (i + 1) for i in range(6))
    elif xfac > 1.0:
        exl = math.sqrt(2.0 / math.pi) * (1.0 - 0.125 / xfac) / math.sqrt(xfac)
    return exb * sth2 + exl * (1.0 - sth2)


def _gsas_ext_derv(f2: float, tt_deg: float, ext: float) -> float:
    """dE/d(ext) — the GSAS-II derivative reference."""
    sth2 = math.sin(math.radians(tt_deg / 2.0)) ** 2
    c2th = 1.0 - 2.0 * sth2
    flv2 = f2 * (WAVE / VOL) ** 2 * 0.079411 * (1.0 + c2th ** 2) / 2.0
    xfac = flv2 * ext
    dbde = -0.5 * flv2 / math.sqrt(1.0 + xfac) ** 3 if xfac > -1.0 else -500.0 * flv2
    dlde = 0.0
    if 0 < xfac <= 1.0:
        dlde = sum(i * flv2 * xfac ** i * _COEF[i - 1] for i in range(1, 7)) / xfac
    elif xfac > 1.0:
        xfac2 = 1.0 / math.sqrt(xfac)
        dlde = 0.5 * flv2 * math.sqrt(2.0 / math.pi) * xfac2 * (-1.0 / xfac + 0.375 / xfac ** 2)
    return dbde * sth2 + dlde * (1.0 - sth2)


def _x_of(ext: float) -> np.ndarray:
    _, _, x = sabine_extinction_and_dx(F2, WAVE, VOL, TT, ext)
    return x


# -- schema ------------------------------------------------------------


def test_phase_extinction_defaults_off_and_round_trips():
    from rietx.schemas.structure import Phase
    from tests.test_schemas import make_lab6

    phase = make_lab6().phases[0]
    # off by default: value 0, not varying, bounded at zero
    assert phase.extinction.value == 0.0
    assert phase.extinction.vary is False
    assert phase.extinction.min == 0.0

    phase.extinction.value = 0.004
    phase.extinction.vary = True
    back = Phase.model_validate_json(phase.model_dump_json())
    assert back.extinction.value == pytest.approx(0.004)
    assert back.extinction.vary is True
    assert back.extinction.min == 0.0


def test_extinction_param_wiring_and_routing():
    """It enters θ under the ``phases.*.extinction`` glob, decodes back, and is
    *not* matched by the structural (dof/adp) analytic-column regex — so it
    rides the ordinary peak-chain FD column, not the structural one."""
    from rietx import Instrument
    from rietx.optimize.least_squares import _STRUCTURAL_PATH
    from rietx.params.vector import ParameterTable
    from tests.test_schemas import make_lab6

    structure = make_lab6()
    structure.phases[0].extinction.value = 0.004
    table = ParameterTable(structure, Instrument.debye_scherrer(wavelength=1.5406))
    table.set_vary(["*"], False)
    assert table.set_vary(["phases.*.extinction"], True) == ["phases.0.extinction"]
    assert table.decode(table.x0())["phases.0.extinction"] == pytest.approx(0.004)
    # the structural analytic path (dof/adp) must not claim this column
    assert _STRUCTURAL_PATH.match("phases.0.extinction") is None


# -- staged plan + seed ------------------------------------------------


def test_mccusker_structural_frees_extinction_after_displacement():
    from rietx.strategy.staged import RefinementPlan

    plan = RefinementPlan.mccusker_structural()
    names = [s.name for s in plan.stages]
    # extinction used to be the last stage; since WP-0502 surface roughness
    # follows it, being *more* degenerate with Biso/ADPs still (a low-angle
    # intensity depression with no |F|² handle to distinguish it).  The
    # load-bearing assertion was always the ordering, not the last position.
    assert names.index("biso") < names.index("extinction")  # displacement first
    assert names.index("extinction") < names.index("roughness")
    ext = plan.stages[names.index("extinction")]
    assert ext.turn_on == ["phases.*.extinction"]
    # no seed since WP-1938: the coefficient's column at 0 is the physical
    # one, and dropping the 1e-3 seed moved no BT-1 answer beyond 3.4e-8 esd
    assert ext.seed == 0.0


def test_the_stage_seed_lifts_a_zero_coefficient_off_its_floor():
    """A caller's ``Stage.seed`` reaches the coefficient through its bounds
    (WP-1938): it is free, bounded below at 0, and on that floor."""
    from rietx import Instrument
    from rietx.params.vector import ParameterTable
    from tests.test_schemas import make_lab6

    table = ParameterTable(make_lab6(), Instrument.debye_scherrer(wavelength=1.5406))
    table.set_vary(["*"], False)
    freed = table.set_vary(["phases.*.extinction"], True)
    e = next(x for x in table.entries if x.path == "phases.0.extinction")
    assert e.value == 0.0 and e.lo == 0.0

    seeded = table.seed_floored(freed, 1e-3)
    assert seeded == ["phases.0.extinction"]
    assert e.value == 1e-3
    # seeding is idempotent-ish: a value already at the seed is left alone
    assert table.seed_floored(freed, 1e-3) == []


def test_stagespec_round_trips_the_seed():
    from rietx.schemas.plan import StageSpec
    from rietx.strategy.staged import Stage

    spec = StageSpec.from_stage(Stage("extinction", ["phases.*.extinction"], seed=1e-3))
    assert spec.seed == 1e-3
    back = StageSpec.model_validate_json(spec.model_dump_json()).to_stage()
    assert back.seed == 1e-3


# -- forward model integration -----------------------------------------


def _lab6_model(ext: float):
    """A compiled LaB6 model (heavy La ⇒ strong |F|², detectable extinction)."""
    from rietx import Instrument, PatternData
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable
    from tests.test_schemas import make_lab6

    structure = make_lab6()
    structure.phases[0].scale.value = 5e-3
    structure.phases[0].extinction.value = ext
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 1e-2
    tt = np.arange(12.0, 120.0, 0.02)
    pattern = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, pattern, mode="rietveld")
    table = ParameterTable(structure, ins)
    return model, table.decode(table.x0())


def test_forward_ext_zero_is_the_extinction_free_formula():
    """ext = 0 skips the multiply: the intensity is exactly scale·m·|F|²·w·Lp,
    bit-identical to the pre-extinction model."""
    from rietx.crystallography.lattice import d_spacings, two_theta_deg
    from rietx.crystallography.structure_factor import structure_factors_squared
    from rietx.model.corrections import lorentz_polarization

    model, values = _lab6_model(ext=0.0)
    cp = model.phases[0]
    cell = tuple(values[f"phases.0.cell.{k}"] for k in ("a", "b", "c", "alpha", "beta", "gamma"))
    d = d_spacings(cp.reflections.hkl, *cell)
    xyz, occ, biso, uaniso, astar = model._site_values(0, values, cell)
    f2 = structure_factors_squared(cp.reflections.hkl, d, cp.sites, xyz, occ, biso, uaniso, astar)
    base = values["phases.0.scale"] * cp.reflections.multiplicity * f2

    peaks = model.phase_peaks(0, values)
    for il, lam in enumerate(model.line_wavelengths):
        w = values[f"instrument.source.lines.{il}.weight"]
        tt = two_theta_deg(d, lam)
        expected = base * w * lorentz_polarization(tt, values["instrument.polarization"])
        assert np.array_equal(peaks[il][3], expected)  # bit-identical, no tolerance


def test_forward_ext_attenuates_strong_reflections_only():
    """Extinction removes intensity from the strong lines and leaves the weak
    high-angle ones essentially untouched (x ∝ |F|²)."""
    model0, v0 = _lab6_model(ext=0.0)
    modelE, vE = _lab6_model(ext=1.0)  # large ⇒ clearly visible on the strong lines
    i0 = model0.phase_peaks(0, v0)[0][3]
    iE = modelE.phase_peaks(0, vE)[0][3]

    ratio = iE / np.where(i0 > 0, i0, 1.0)
    assert np.all(ratio <= 1.0 + 1e-12), "extinction must not amplify"
    strong = i0 > 0.5 * i0.max()
    weak = i0 < 1e-3 * i0.max()
    assert ratio[strong].min() < 0.97, "a strong reflection should be attenuated"
    if weak.any():
        assert ratio[weak].min() > 0.995, "weak reflections barely change"


# -- analytic Jacobian (the hidden-Jacobian guard) ---------------------


def test_jacobian_dof_adp_extinction_columns_match_fd_with_extinction_on():
    """With ext ≠ 0 the analytic coordinate/ADP columns must carry the
    G = E + x·dE/dx chain factor; the extinction column itself rides the
    peak-chain FD path.  All are checked against a full-model finite
    difference.  ext is large here so G departs from 1 by ~10-30% — without
    the factor the dof/adp columns would miss by far more than the tolerance
    (that is the hidden-Jacobian bug this test exists to catch)."""
    from rietx import Instrument, PatternData
    from rietx.crystallography.lattice import cell_volume, d_spacings
    from rietx.crystallography.structure_factor import structure_factors_squared
    from rietx.model.forward import compile_model
    from rietx.optimize.least_squares import _make_jacobian, _make_residual
    from rietx.params.vector import ParameterTable
    from tests.test_aniso_adp import make_aniso_rutile

    structure = make_aniso_rutile()
    structure.phases[0].scale.value = 1e-3
    structure.phases[0].extinction.value = 2.0  # large ⇒ |G − 1| ≫ tolerance
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 1e-2
    grid = np.arange(10.0, 90.0, 0.02)
    pattern = PatternData(two_theta=grid.tolist(), intensity=np.zeros_like(grid).tolist())

    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    free = ["phases.0.extinction", "phases.0.atoms.1.dof.0",
            "phases.0.atoms.0.adp.0", "phases.0.atoms.0.adp.1",
            "phases.0.atoms.1.adp.0", "phases.0.scale", "phases.0.cell.a"]
    for p in free:
        assert table.set_vary([p], True), p
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    values = table.decode(table.x0())

    # G must genuinely differ from 1 (so the test discriminates).  Before
    # WP-2044 no reflection could cross x = 1 either, where GSAS-II's two
    # branches stepped and FD broke.  The closed form is smooth there, and
    # tests/test_cross_backend.py's ``extinction_strong`` row crosses it.
    cp = model.phases[0]
    cell = tuple(values[f"phases.0.cell.{k}"] for k in ("a", "b", "c", "alpha", "beta", "gamma"))
    d = d_spacings(cp.reflections.hkl, *cell)
    xyz, occ, biso, uaniso, astar = model._site_values(0, values, cell)
    f2 = structure_factors_squared(cp.reflections.hkl, d, cp.sites, xyz, occ, biso, uaniso, astar)
    lam0 = model.line_wavelengths[0]
    tt0 = cp.reflections.two_theta(cell, lam0)
    E, _, _ = sabine_extinction_and_dx(f2, lam0, cell_volume(*cell), tt0,
                                       values["phases.0.extinction"])
    assert (1.0 - E).max() > 0.02, "extinction too weak — test would not discriminate"

    theta = table.x0()
    J = _make_jacobian(model, table)(theta)
    residual = _make_residual(model, table)
    r0 = residual(theta)
    for c, path in enumerate(table.free_paths):
        h = 1e-6 * max(1.0, abs(theta[c]))
        tp = theta.copy()
        tp[c] += h
        col_fd = (residual(tp) - r0) / h
        col_an = J[:, c]
        scale = np.linalg.norm(col_fd)
        assert scale > 0, f"{path}: dead FD column"
        err = np.linalg.norm(col_an - col_fd) / scale
        assert err < 5e-3, f"{path}: analytic vs FD mismatch ({err:.2e})"


# -- identity when off -------------------------------------------------


def test_extinction_is_identity_at_zero():
    """ext = 0 ⇒ E ≡ 1 to machine precision, every reflection and line."""
    E = sabine_extinction(F2, WAVE, VOL, TT, 0.0)
    assert np.array_equal(E, np.ones_like(F2))
    E2, dEdx, x = sabine_extinction_and_dx(F2, WAVE, VOL, TT, 0.0)
    assert np.array_equal(E2, np.ones_like(F2))
    assert np.array_equal(x, np.zeros_like(F2))


# -- GSAS-II reference, within the measured band -----------------------


def test_extinction_matches_gsas_getpwdrext_within_the_band():
    """E per reflection against GSAS-II, both Laue branches.

    The Bragg half and the blend are GSAS-II's to 1e-10.  The Laue half differs
    by the band, scaled by the cos²θ weight it enters E with.
    """
    ext = 0.03  # large enough that the strong low-angle reflections cross x = 1
    x = _x_of(ext)
    assert (x <= 1.0).any() and (x > 1.0).any(), "test must span both Laue branches"

    E = sabine_extinction(F2, WAVE, VOL, TT, ext)
    ref = np.array([_gsas_ext(f, t, ext) for f, t in zip(F2, TT, strict=True)])
    cos2 = np.cos(np.radians(TT / 2.0)) ** 2
    el, _ = _laue_and_deriv(x)
    bar = np.array([_band(v)[0] for v in x]) * el * cos2 + 1e-10
    assert np.all(np.abs(E - ref) <= bar), np.abs(E - ref) / bar

    # dE/d(ext) = dE/dx · ∂x/∂ext = dEdx · (x/ext); the Laue slope's band is
    # absolute in dE_L/dx, so it scales by the same two factors
    _, dEdx, _ = sabine_extinction_and_dx(F2, WAVE, VOL, TT, ext)
    ref_d = np.array([_gsas_ext_derv(f, t, ext) for f, t in zip(F2, TT, strict=True)])
    bar_d = np.array([_band(v)[1] for v in x]) * cos2 * (x / ext) + 1e-8
    assert np.all(np.abs(dEdx * (x / ext) - ref_d) <= bar_d)


def test_laue_factor_stays_within_the_band_of_gsas_branches():
    """The closed form against GSAS-II's series and asymptote, value and slope,
    on a grid crossing x = 1, and at the recorded points to two digits."""
    x = np.concatenate([np.linspace(1e-4, 1.0, 2001),
                        np.linspace(1.0 + 1e-9, 60.0, 4001)])
    el, dl = _laue_and_deriv(x)
    for v, e, d in zip(x, el, dl, strict=True):
        ref_e, ref_d = _gsas_laue(v)
        bar_e, bar_d = _band(v)
        assert abs(e - ref_e) / e <= bar_e, f"value at x = {v}"
        assert abs(d - ref_d) <= bar_d, f"slope at x = {v}"
    # the recorded differences (relative to E_L), so the band cannot loosen
    # into a bar that would hide a change of form
    recorded = {0.25: 3.9e-8, 0.5: 5.6e-6, 1.0: 7.9e-4, 1.0 + 1e-12: 3.6e-2,
                2.0: 9.8e-3, 5.0: 1.13e-3}
    for v, want in recorded.items():
        e = float(_laue_and_deriv(np.array([v]))[0][0])
        got = abs(e - _gsas_laue(v)[0]) / e
        assert got == pytest.approx(want, rel=0.02), f"x = {v}: {got:.3e}"


# -- the closed form: the Laue integral, continuous at x = 1 -----------


def _laue_integral(x: float) -> float:
    """(1/πx)·∫ ½[1 − exp(−2x/(1 + u²))] du over the real line, by quadrature.

    ITC Vol. C (2006) §6.4.5's construction of Sabine's Laue factor: the
    Laue-case fraction of eq. 6.4.4.3 with a Lorentzian coupling, divided by
    the kinematic intensity.  ``expm1`` keeps small x free of cancellation.
    """
    from scipy.integrate import quad

    half, _ = quad(lambda u: -0.5 * math.expm1(-2.0 * x / (1.0 + u * u)),
                   0.0, np.inf, epsabs=0.0, epsrel=1e-13, limit=500)
    return 2.0 * half / (math.pi * x)


@pytest.mark.parametrize("x", [1e-3, 0.01, 0.3, 1.0, 2.5, 6.49, 40.0])
def test_laue_factor_is_the_laue_integral(x):
    """E_L = e^(−x)·[I₀ + I₁] is the integral Sabine's expansions truncate.

    Measured 1e-16 to 4e-16 relative.  6.49 is the largest x of CaF₂ on the QPA
    guide's fit (WP-2044).
    """
    el, _ = _laue_and_deriv(np.array([x]))
    assert el[0] == pytest.approx(_laue_integral(x), rel=1e-12)


def test_laue_factor_is_continuous_at_x_equals_one():
    """No step at x = 1, in value or slope (GSAS-II's pair stepped 3.6 %)."""
    el, dl = _laue_and_deriv(np.array([1.0 - 1e-9, 1.0, 1.0 + 1e-9]))
    assert el[1] == pytest.approx(0.673670022943349, rel=1e-15)
    # the value moves by its slope times the 2e-9 gap, and no more
    assert abs(el[2] - el[0]) < 1e-9
    assert abs(el[2] - el[0] - 2e-9 * dl[1]) < 1e-15
    assert abs(dl[2] - dl[0]) < 1e-9


def test_laue_slope_matches_a_central_difference():
    """dE_L/dx = −i1e(x)/x against a central difference of E_L, across x = 1
    and down to the floor, where the slope is −1/2."""
    x = np.array([1e-6, 0.05, 0.4, 0.999, 1.0, 1.001, 1.7, 6.49, 30.0])
    h = 1e-5 * np.maximum(x, 0.1)
    _, dl = _laue_and_deriv(x)
    fd = (_laue_and_deriv(x + h)[0] - _laue_and_deriv(x - h)[0]) / (2.0 * h)
    assert dl == pytest.approx(fd, rel=1e-8, abs=1e-9)
    assert _laue_and_deriv(np.array([0.0]))[1][0] == pytest.approx(-0.5, rel=1e-15)


def test_dEdx_matches_finite_difference():
    """dEdx (∂E/∂x) agrees with a central difference of E(x) via ext."""
    ext = 0.015
    E0, dEdx, x0 = sabine_extinction_and_dx(F2, WAVE, VOL, TT, ext)
    h = 1e-7
    Ep = sabine_extinction(F2, WAVE, VOL, TT, ext + h)
    Em = sabine_extinction(F2, WAVE, VOL, TT, ext - h)
    # dE/dext by FD, converted to dE/dx by dividing ∂x/∂ext = x/ext
    dE_dext_fd = (Ep - Em) / (2 * h)
    assert dEdx * (x0 / ext) == pytest.approx(dE_dext_fd, rel=1e-5, abs=1e-9)


# -- monotonicity ------------------------------------------------------


def test_extinction_never_amplifies_and_slope_is_non_positive():
    """E ≤ 1 for all ext, and the slope dE/dx ≤ 0 everywhere, so extinction
    only ever attenuates."""
    for ext in np.linspace(0.0, 0.4, 30):
        E = sabine_extinction(F2, WAVE, VOL, TT, ext)
        assert np.all(E <= 1.0 + 1e-12)
        _, dEdx, _ = sabine_extinction_and_dx(F2, WAVE, VOL, TT, ext)
        assert np.all(dEdx <= 0.0), f"positive slope at ext={ext}"


def test_extinction_is_monotone_in_ext_across_x_equals_one():
    """E decreases with ext on every reflection, including the ones whose x
    sweeps through 1.  GSAS-II's branches stepped up by 3.6 % there, and real
    powder data reach it: CaF₂ on the QPA guide's fit has five of 11
    reflections above x = 1 (WP-2044)."""
    ext_grid = np.linspace(0.0, 0.1, 400)
    assert _x_of(ext_grid[-1]).max() > 1.0, "the grid must carry x through 1"
    prev = np.ones_like(F2)
    for ext in ext_grid:
        E = sabine_extinction(F2, WAVE, VOL, TT, ext)
        assert np.all(E <= prev + 1e-12), f"E increased at ext={ext}"
        prev = E


# -- the branchless select computes every arm, so each must stay finite ---
#
# ``_laue_and_deriv`` evaluates the Bessel arm at every x and throws it away on
# x < 0.  Before WP-2044 it evaluated GSAS-II's series *and* asymptote, neither
# finite over the whole line, and the discarded arm raised numpy
# RuntimeWarnings out of a converged refinement: the bug these tests pin.  The
# Bessel arm is finite for every x ≥ 0, and its argument is clamped at 0 and
# shifted by 2⁻¹²⁶, so i1e(x)/x never divides 0 by 0.


#: numpy's default error state.  ``under='ignore'`` is deliberate and is
#: numpy's own default: x⁶ → 0 for tiny x is the *correct* answer, not a
#: defect, and the reported bug was over/divide, which are 'warn'.
_NUMPY_DEFAULT_ERRSTATE = dict(divide="warn", over="warn",
                               under="ignore", invalid="warn")


def _warnings_from(fn, *args):
    """Every warning ``fn`` raises under numpy's default error state."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        old = np.seterr(**_NUMPY_DEFAULT_ERRSTATE)
        try:
            fn(*args)
        finally:
            np.seterr(**old)
    return [str(w.message) for w in caught]


def test_laue_branches_are_warning_free_across_the_reachable_domain():
    """No RuntimeWarning for any x a refinement can produce.

    x = ext·|F|²·(λ/V)²·Xpol is ≥ 0 (ext ≥ 0, |F|² ≥ 0, Xpol > 0), so the
    domain is [0, ∞).  The regression lived in the denormal window: GSAS-II's
    asymptote's 1/x² term underflowed to *exactly zero* below x ≈ 1.5e-162 and
    then divided by it.  The window is reached while ``ext`` is driven to the
    exact zero that switches the correction off.  The negative values are the
    clamp's: x < 0 selects 1, and the discarded arm must not warn either.
    """
    rng = np.random.default_rng(0)
    x = np.concatenate([
        # exact zero, the subnormal floor, and both warning thresholds
        np.array([0.0, 5e-324, 1e-320, 1e-300, 1e-206, 1e-162, 1e-100,
                  1e-20, 1e-6, 0.5, 1.0, np.nextafter(1.0, 2.0), 2.0, 1e6,
                  -0.0, -5e-324, -2.0 ** -126, -1.0]),
        10.0 ** rng.uniform(-323.0, 12.0, 20000),
    ])
    assert _warnings_from(_laue_and_deriv, x) == []


def test_laue_shift_never_moves_a_value_that_is_actually_selected():
    """The clamp and the 2⁻¹²⁶ shift are the identity on every fp64 value.

    Guards the shift against being replaced by a *tuned* floor: one large
    enough to bite would silently move converged numbers.  E_L is compared bit
    for bit with the unshifted closed form on x > 0, the subnormals included.
    The slope is compared where −i1e(x)/x is itself accurate, x ≥ 1e-300.
    Below that i1e(x) ≈ x/2 is subnormal, and the unshifted quotient loses
    digits the shifted one keeps.
    """
    from scipy.special import i0e, i1e

    rng = np.random.default_rng(7)
    x = np.concatenate([np.array([5e-324, 1e-320, 2.0 ** -126, 2.0 ** -73,
                                  2.0 ** -72, 1e-17, 1.0]),
                        10.0 ** rng.uniform(-323.0, -10.0, 5000),
                        rng.uniform(0.0, 1.0, 5000),
                        rng.uniform(1.0, 50.0, 5000)])
    x = x[x > 0.0]
    el, dl = _laue_and_deriv(x)

    # bit-identical, not approx: a moved bit here moves every converged fit
    assert np.array_equal(el, i0e(x) + i1e(x))
    accurate = x >= 1e-300
    assert dl[accurate] == pytest.approx(-i1e(x[accurate]) / x[accurate], rel=1e-15)
    exact = x >= 2.0 ** -72
    assert np.array_equal(dl[exact], -i1e(x[exact]) / x[exact])
    # and the floor: E_L is exactly 1 with the one-sided slope
    el0, dl0 = _laue_and_deriv(np.array([0.0, -0.0, -1.0]))
    assert el0.tolist() == [1.0, 1.0, 1.0]
    assert dl0 == pytest.approx([-0.5, -0.5, 0.0], rel=1e-15, abs=0.0)


@pytest.mark.parametrize("name", ["jax", "torch"])
def test_autodiff_takes_the_one_sided_laue_slope_at_the_floor(name):
    """A traced backend differentiates E_L to −i1e(x)/x, and to −1/2 at x = 0.

    The scaled Bessel functions carry e^(−|x|), and jax and torch differentiate
    them through sign(x), with sign(0) = 0.  Unshifted, both return +1/2 at
    x = 0 exactly: an extinction column at its floor of 0 with the wrong sign
    (measured, WP-2044).  The 2⁻¹²⁶ shift in ``_laue_and_deriv`` is the fix.
    """
    from rietx.backend import traced
    from rietx.backend.api import BACKEND_REQUIRES, resolve_backend
    from rietx.backend.linalg64 import to_host_fp64

    pytest.importorskip(BACKEND_REQUIRES[name])
    xp = resolve_backend(name)
    x = np.array([0.0, 1e-300, 0.3, 1.0, 1.0 + 1e-9, 6.49])
    want = _laue_and_deriv(x)[1]
    with traced.active(xp):
        primal, tangent = xp.asarray(x), xp.asarray(np.ones_like(x))
        if name == "jax":
            import jax

            _, out = jax.jvp(lambda v: _laue_and_deriv(v)[0], (primal,), (tangent,))
        else:
            import torch

            _, out = torch.func.jvp(lambda v: _laue_and_deriv(v)[0],
                                    (primal,), (tangent,))
    got = to_host_fp64(out)
    assert got[0] == pytest.approx(-0.5, rel=1e-12)
    assert got == pytest.approx(want, rel=1e-12)


def test_a_negligible_structure_factor_is_not_what_triggers_the_warning():
    """Records a *refuted* diagnosis, so it is not re-derived.

    The diagnosis concerned GSAS-II's asymptote, which rietx evaluated until
    WP-2044.  The closed form has no such term, and the test keeps its point
    about where x can collapse.  The obvious reading — "reflections with zero
    or negligible |F|² overflow the asymptote" — is wrong, in the one detail
    that decides the fix.  An
    exactly-zero |F|² gives x = 0, which the branch guard already catches, and
    a |F|² that is merely negligible floors at the fp64 cancellation limit of a
    systematic absence (~1e-29 for a real structure), some 130 orders of
    magnitude above the ~1.5e-162 the asymptote needs to misbehave.  So no
    reflection list, however long, reaches it at a physical ext: the collapse
    has to be in the *coefficient*.  A test built on zero-|F|² members would
    therefore pass against the unfixed code and pin nothing.
    """
    f2 = np.array([0.0, 0.0, 1.0e-29, 1.0e-20, 1.0e3, 9.0e4])
    tt = np.array([8.0, 44.0, 63.0, 92.0, 121.0, 158.0])

    _, _, x = sabine_extinction_and_dx(f2, WAVE, VOL, tt, 1.0e-3)
    assert np.all(x[f2 == 0.0] == 0.0), "zero |F|² must give exactly x = 0"
    smallest = x[f2 > 0.0].min()
    assert smallest > 1.0e-162, "a negligible |F|² does not reach the window"

    # and the whole list is quiet, which is what made the zero-|F|² framing
    # vacuous as a regression test
    assert _warnings_from(sabine_extinction_and_dx,
                          f2, WAVE, VOL, tt, 1.0e-3) == []


def test_extinction_collapsing_to_its_off_state_is_warning_free():
    """The real trigger: ``ext`` walking down to its floor of zero.

    Measured before WP-1938, when ``Phase.extinction``'s solver coordinate was
    unbounded below and reached exactly 0.0 only past a window of denormal
    values.  That window is a *legitimate* place for a trial step to land —
    the extinction stage is cumulative, so ext stays free alongside the phase
    scale and the emission-line weights, and those three scale intensity
    together — and every ext in it warned before the clamp.
    """
    f2 = np.array([9.0e4, 4.2e4, 2.1e4, 8.0e3, 3.0e3, 1.1e3, 4.0e2, 1.2e2])
    for ext in (1.0e-3, 1.0e-40, 1.0e-100, 1.0e-160, 1.0e-200, 1.0e-300,
                5.0e-324, 0.0):
        assert _warnings_from(sabine_extinction, f2, WAVE, VOL, TT, ext) == [], \
            f"forward path warned at ext={ext!r}"
        assert _warnings_from(sabine_extinction_and_dx,
                              f2, WAVE, VOL, TT, ext) == [], \
            f"derivative path warned at ext={ext!r}"
        E = sabine_extinction(f2, WAVE, VOL, TT, ext)
        assert np.all(np.isfinite(E))
    # the off state is still exactly the identity
    assert np.all(sabine_extinction(f2, WAVE, VOL, TT, 0.0) == 1.0)


# -- angular limits (the sin²θ / cos²θ convention trap) ----------------


def test_angular_limits_bragg_is_sin2_laue_is_cos2():
    """At backscatter E → E_B (Bragg); at forward scatter E → E_L (Laue).

    This is the guard on the convention: if the sin²θ/cos²θ blend were flipped
    the two limits would swap.
    """
    ext = 0.35
    f2 = np.array([1.0e5, 1.0e5])
    tt = np.array([0.4, 179.6])  # near-forward, near-backscatter
    E = sabine_extinction(f2, WAVE, VOL, tt, ext)

    # pure Bragg and Laue components at these two angles, from the same x
    _, _, xv = sabine_extinction_and_dx(f2, WAVE, VOL, tt, ext)
    e_b = 1.0 / np.sqrt(1.0 + xv)
    e_l, _ = _laue_and_deriv(xv)
    assert abs(e_l[0] - e_b[0]) > 1e-2, "x too small — the two limits coincide"

    # forward scatter (cos²θ ≈ 1) selects the Laue component; backscatter
    # (sin²θ ≈ 1) selects the Bragg component — the sin²/cos² convention
    assert E[0] == pytest.approx(e_l[0], abs=1e-3)
    assert E[1] == pytest.approx(e_b[1], abs=1e-3)

# -- end-to-end recovery + correlation ---------------------------------

from pathlib import Path  # noqa: E402

OUT = Path(__file__).parent / "output"


def _synthesize_extinct_lab6(ext_true: float, *, noise_seed: int = 5):
    """A LaB6 pattern carrying a known extinction coefficient + Poisson noise."""
    from rietx import Instrument, PatternData
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable
    from tests.test_schemas import make_lab6

    structure = make_lab6()
    structure.phases[0].scale.value = 5e-3
    structure.phases[0].extinction.value = ext_true
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 8e-3
    tt = np.arange(15.0, 120.0, 0.02)
    pattern = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, pattern, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0())) + 40.0  # flat background floor
    rng = np.random.default_rng(noise_seed)
    return PatternData(two_theta=model.tt.tolist(),
                       intensity=rng.poisson(np.maximum(y, 1.0)).astype(float).tolist())


def test_injected_extinction_is_recovered_within_esds():
    """Inject a known ext into a heavy-atom (LaB6) pattern, start from ext = 0,
    and recover it within a few esds.  Biso is held at its (correct) value so
    the recovery isolates extinction from the Biso it correlates with — the
    does-no-harm side is checked separately against real data."""
    from rietx import Instrument, Refinement
    from rietx.strategy.staged import RefinementPlan, Stage
    from rietx.viz.plots import plot_result
    from tests.test_schemas import make_lab6

    ext_true = 2.5
    pattern = _synthesize_extinct_lab6(ext_true)

    structure = make_lab6()  # extinction starts at 0
    structure.phases[0].scale.value = 4e-3
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 1.1e-2

    plan = RefinementPlan(stages=[
        Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        Stage("cell", ["phases.*.cell.*"]),
        Stage("profile_w", ["instrument.profile.w"]),
        Stage("extinction", ["phases.*.extinction"], seed=1e-3),
    ])
    ref = Refinement(structure, ins, history=False)
    result = ref.fit(pattern, plan=plan)
    assert result.status == "converged"

    ext = result.parameter("phases.0.extinction")
    assert ext.stderr is not None and ext.stderr > 0
    assert ext.value == pytest.approx(ext_true, abs=max(4 * ext.stderr, 0.05 * ext_true)), \
        f"recovered ext={ext.value:.3f}±{ext.stderr:.3f}, truth {ext_true}"
    # and it is resolved, not merely fitted: several esds away from zero
    assert ext.value > 5 * ext.stderr

    OUT.mkdir(exist_ok=True)
    plot_result(result, path=str(OUT / "extinct_lab6_fit.png"))


def test_extinction_correlates_with_scale_and_biso_and_the_guard_fires():
    """Co-freeing extinction, scale and the atom Biso on a *single* powder
    pattern is a genuine degeneracy — all three attenuate the strong low-angle
    lines.  Measured on this LaB6 synthetic the extinction↔scale correlation is
    ρ ≈ +0.97 and extinction↔La-Biso ρ ≈ +0.87: extinction's per-reflection
    x ∝ |F|² sin²θ/cos²θ signature does *not* break the degeneracy against a
    freely-varying scale here.  That is exactly why the staged plan refines
    scale (and Biso) before extinction and holds Biso while extinction is freed
    (test_injected_extinction_is_recovered_within_esds), and it is what the
    high-correlation guard exists to catch.

    This test also pins the guard *live*: before WP-0407 the returned
    correlation matrix was deflated by BL² (the placement bug), so this
    genuinely-collinear pair reported ρ ≈ +0.4 and the guard never fired.  On
    the true Pearson matrix (unit diagonal) it does."""
    from rietx import Instrument
    from rietx.model.forward import compile_model
    from rietx.optimize.least_squares import run_least_squares
    from rietx.params.vector import ParameterTable
    from rietx.strategy.staged import check_guards
    from tests.test_schemas import make_lab6

    pattern = _synthesize_extinct_lab6(2.5)
    structure = make_lab6()
    structure.phases[0].scale.value = 5e-3
    structure.phases[0].extinction.value = 1.0
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 9e-3

    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    table.set_vary(["phases.0.extinction", "phases.0.scale",
                    "phases.0.atoms.*.biso"], True)
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    outcome = run_least_squares(model, table, max_iter=60)

    free = table.free_paths
    ie = free.index("phases.0.extinction")
    isc = free.index("phases.0.scale")
    corr = np.asarray(outcome.correlation)
    # true Pearson matrix: unit diagonal (the placement bug left 1/BL² here)
    assert np.allclose(np.diag(corr), 1.0)
    assert corr[ie, isc] > 0.9, \
        f"ext↔scale should be collinear here, ρ={corr[ie, isc]:+.2f}"

    # the guard fires on the genuinely degenerate ext↔scale pair (ρ ≈ 0.97 sits
    # below the default 0.98 bar; at the lenient 0.8 threshold it is flagged)
    guard = check_guards(table, outcome, threshold=0.8)
    assert any({"phases.0.extinction", "phases.0.scale"} == set(c.paths)
               for c in guard.high_correlations), guard.high_correlations


# -- the off-state gate (WP-1109) -----------------------------------------

def _gate_case(ext_value: float, free: tuple[str, ...], *,
               tie_extinction_to: str | None = None,
               declare_moving: bool = True):
    """A compiled LaB6 model plus its table, for the gate's truth table."""
    from rietx import Instrument, PatternData
    from rietx.model.forward import compile_model
    from rietx.params.vector import AffineTie, ParameterTable
    from tests.test_schemas import make_lab6

    structure = make_lab6()
    structure.phases[0].scale.value = 5e-3
    structure.phases[0].extinction.value = ext_value
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 9e-3
    tt = np.arange(15.0, 120.0, 0.05)
    pattern = PatternData(two_theta=tt.tolist(),
                          intensity=np.full(tt.shape, 100.0).tolist())

    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    for path in free:
        assert table.set_vary([path], True), path
    if tie_extinction_to is not None:
        table.set_tie("phases.0.extinction",
                      AffineTie(terms=((tie_extinction_to, 1.0),)))
    model = compile_model(
        structure, ins, pattern, mode="rietveld",
        moving_paths=set(table.moving_paths) if declare_moving else None)
    return model, table


def test_moving_paths_is_free_paths_plus_its_ties():
    """``free_paths`` is the θ columns; ``moving_paths`` is what those columns
    can change.  The two differ by exactly the tied rows, which is the whole
    reason a structural gate must not ask the first question."""
    _model, table = _gate_case(0.0, ("phases.0.scale",),
                               tie_extinction_to="phases.0.scale")
    free, moving = set(table.free_paths), set(table.moving_paths)
    assert free <= moving
    assert "phases.0.extinction" in moving and "phases.0.extinction" not in free
    # a genuinely held parameter is in neither: it lives entirely in d
    assert "instrument.zero_shift" not in moving


@pytest.mark.parametrize("ext_value,free,tie,declare,expected", [
    # the gate's one true case: at its identity, and unreachable this stage
    (0.0, ("phases.0.scale",), None, True, True),
    # free ⇒ the column exists and must not be identically zero
    (0.0, ("phases.0.extinction", "phases.0.scale"), None, True, False),
    # non-zero ⇒ E is not the identity, whoever refines it
    (2.0, ("phases.0.scale",), None, True, False),
    # tied to a free parameter: not a θ column, still moves off zero
    (0.0, ("phases.0.scale",), "phases.0.scale", True, False),
    # no claim made about what moves ⇒ nothing is gated
    (0.0, ("phases.0.scale",), None, False, False),
])
def test_extinction_gate_fires_only_when_ext_cannot_move(
        ext_value, free, tie, declare, expected):
    model, _table = _gate_case(ext_value, free, tie_extinction_to=tie,
                               declare_moving=declare)
    assert model.phases[0].skip_extinction is expected


def test_gating_extinction_off_is_bit_identical():
    """The gate's whole claim: skipping a multiply by ones changes no bit of
    the residual *or* of any analytic Jacobian column.  Compared with
    ``array_equal`` rather than ``allclose`` — an approximate check would pass
    for a gate that quietly dropped a real correction."""
    from rietx.optimize.least_squares import _make_jacobian, _make_residual

    free = ("phases.0.scale", "phases.0.cell.a", "phases.0.atoms.*.biso",
            "instrument.profile.w")
    gated, table = _gate_case(0.0, free)
    ungated, _ = _gate_case(0.0, free, declare_moving=False)
    assert gated.phases[0].skip_extinction
    assert not ungated.phases[0].skip_extinction

    theta = table.x0()
    r_gated = _make_residual(gated, table)(theta)
    r_ungated = _make_residual(ungated, table)(theta)
    assert np.array_equal(r_gated, r_ungated)

    j_gated = _make_jacobian(gated, table)(theta)
    j_ungated = _make_jacobian(ungated, table)(theta)
    assert np.array_equal(j_gated, j_ungated)


def test_gating_leaves_the_structural_and_po_columns_bit_identical():
    """The other two sites that fold E in by hand — the coordinate/ADP chain
    factor G = E + x·dE/dx and the March-Dollase r column.  Both are exactly 1
    and exactly E at ext = 0, so both gate; a gate applied to ``phase_peaks``
    alone would leave these columns disagreeing with finite differences, which
    is the failure mode ``_absorption``'s docstring is written about."""
    from rietx import Instrument, PatternData
    from rietx.model.forward import compile_model
    from rietx.optimize.least_squares import _make_jacobian
    from rietx.params.vector import ParameterTable
    from rietx.schemas.structure import PreferredOrientation
    from tests.test_aniso_adp import make_aniso_rutile

    structure = make_aniso_rutile()
    structure.phases[0].scale.value = 1e-3
    structure.phases[0].preferred_orientation = PreferredOrientation(axis=(0, 0, 1))
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 1e-2
    tt = np.arange(10.0, 90.0, 0.05)
    pattern = PatternData(two_theta=tt.tolist(),
                          intensity=np.full(tt.shape, 100.0).tolist())

    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    for path in ("phases.0.atoms.1.dof.0", "phases.0.atoms.0.adp.0",
                 "phases.0.preferred_orientation.r"):
        assert table.set_vary([path], True), path

    gated = compile_model(structure, ins, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    ungated = compile_model(structure, ins, pattern, mode="rietveld")
    assert gated.phases[0].skip_extinction
    theta = table.x0()
    assert np.array_equal(_make_jacobian(gated, table)(theta),
                          _make_jacobian(ungated, table)(theta))


# -- the column on a real fit whose reflections cross x = 1 (WP-2044) --------


def _nac_and_fluorite():
    """The QPA guide's first model (``examples/guides/qpa.py``), restated: the
    guide runs on import, so it cannot be imported."""
    import rietx as rx
    from rietx.examples import examples_dir

    def site(label, species, xyz, biso):
        x, y, z = (rx.Parameter(value=v) for v in xyz)
        return rx.Atom(label=label, species=species, x=x, y=y, z=z,
                       biso=rx.Parameter(value=biso, min=0.0, max=25.0))

    structure = rx.Structure.from_cif(examples_dir() / "cod_1000236.cif")
    structure.phases.append(rx.Phase(
        name="CaF2", space_group="F m -3 m", cell=rx.Cell.cubic(5.4631),
        atoms=[site("Ca", "Ca2+", (0, 0, 0), 0.6),
               site("F", "F1-", (0.25, 0.25, 0.25), 0.9)]))
    instrument = rx.Instrument.debye_scherrer(wavelength=0.4139090)
    instrument.profile.w.value = 2e-5
    instrument.profile.x.value = 2e-3
    instrument.background = rx.BackgroundChebyshev.with_terms(6)
    return rx.Refinement(structure, instrument)


@pytest.mark.slow
def test_the_extinction_column_agrees_with_central_differences_on_the_qpa_fit():
    """At the QPA guide's answer CaF₂'s reflections run past x = 1, where
    GSAS-II's two Laue branches stepped by 3.6 %. A central difference at a
    1e-4 relative step then straddled the step (column norm 22.47 against
    0.1957, cosine −0.19, WP-2043), and the esd depended on whether the
    solver's last Jacobian did. With the closed form the solver's
    forward-difference column agrees with a central difference at every step
    to its own truncation error (measured 6.7e-7 of the norm at 1e-4 and 1e-6),
    so it needs no analytic replacement."""
    import rietx as rx
    from rietx import PatternData
    from rietx.crystallography.lattice import cell_volume, d_spacings
    from rietx.crystallography.structure_factor import structure_factors_squared
    from rietx.examples import examples_dir
    from rietx.model.forward import compile_model
    from rietx.optimize.least_squares import _make_jacobian, _make_residual
    from rietx.params.vector import ParameterTable

    data = rx.read_pattern(examples_dir() / "11BM_NAC.fxye")
    ref = _nac_and_fluorite()
    ref.fit(data, plan="mccusker_structural", two_theta_limits=(2, 24))

    tt = np.asarray(data.two_theta)
    keep = (tt >= 2) & (tt <= 24)
    pattern = PatternData(two_theta=tt[keep].tolist(),
                          intensity=np.asarray(data.intensity)[keep].tolist(),
                          sigma=np.asarray(data.sigma)[keep].tolist())
    table = ParameterTable(ref.structure, ref.instrument)
    table.set_vary(["*"], False)
    assert table.set_vary(["phases.1.extinction"], True)
    model = compile_model(ref.structure, ref.instrument, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    values = table.decode(table.x0())

    # the answer is only worth testing while CaF₂'s reflections cross x = 1
    cp = model.phases[1]
    cell = tuple(values[f"phases.1.cell.{k}"]
                 for k in ("a", "b", "c", "alpha", "beta", "gamma"))
    d = d_spacings(cp.reflections.hkl, *cell)
    f2 = structure_factors_squared(cp.reflections.hkl, d, cp.sites,
                                   *model._site_values(1, values, cell))
    lam = model.line_wavelengths[0]
    _, _, x = sabine_extinction_and_dx(f2, lam, cell_volume(*cell),
                                       cp.reflections.two_theta(cell, lam),
                                       values["phases.1.extinction"])
    assert (x > 1.0).sum() >= 3, np.sort(x)[-6:]     # measured five of 11

    theta = table.x0()
    column = _make_jacobian(model, table)(theta)[:, 0]
    residual = _make_residual(model, table)
    for rel in (1e-4, 1e-6):
        h = rel * abs(theta[0])
        up, down = theta.copy(), theta.copy()
        up[0] += h
        down[0] -= h
        central = (residual(up) - residual(down)) / (2.0 * h)
        miss = np.linalg.norm(column - central) / np.linalg.norm(central)
        assert miss < 1e-5, (rel, miss)              # measured 6.7e-7 at both
