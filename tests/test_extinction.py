"""Secondary extinction (WP-0506, Sabine model).

The golden is a faithful scalar transcription of GSAS-II ``GetPwdrExt`` /
``GetPwdrExtDerv`` (behavioral reference only — no code is ported; see
ATTRIBUTION.md), used to pin our vectorised/branchless implementation and the
exact numeric constants (Xpol = 0.079411, the six Laue coefficients, the two
Laue branches) to ~1e-10.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from pxrdref.model.extinction import (
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
    from pxrdref.schemas.structure import Phase
    from tests.test_schemas import make_lab6

    phase = make_lab6().phases[0]
    # off by default: value 0, not varying, softplus-bounded positive
    assert phase.extinction.value == 0.0
    assert phase.extinction.vary is False
    assert phase.extinction.min == 0.0
    assert phase.extinction.transform == "softplus"

    phase.extinction.value = 0.004
    phase.extinction.vary = True
    back = Phase.model_validate_json(phase.model_dump_json())
    assert back.extinction.value == pytest.approx(0.004)
    assert back.extinction.vary is True
    assert back.extinction.transform == "softplus"


def test_extinction_param_wiring_and_routing():
    """It enters θ under the ``phases.*.extinction`` glob, decodes back, and is
    *not* matched by the structural (dof/adp) analytic-column regex — so it
    rides the ordinary peak-chain FD column, not the structural one."""
    from pxrdref import Instrument
    from pxrdref.optimize.least_squares import _STRUCTURAL_PATH
    from pxrdref.params.vector import ParameterTable
    from tests.test_schemas import make_lab6

    structure = make_lab6()
    structure.phases[0].extinction.value = 0.004
    table = ParameterTable(structure, Instrument.debye_scherrer(wavelength=1.5406))
    table.set_vary(["*"], False)
    assert table.set_vary(["phases.*.extinction"], True) == ["phases.0.extinction"]
    assert table.decode(table.x0())["phases.0.extinction"] == pytest.approx(0.004)
    # the structural analytic path (dof/adp) must not claim this column
    assert _STRUCTURAL_PATH.match("phases.0.extinction") is None


# -- forward model integration -----------------------------------------


def _lab6_model(ext: float):
    """A compiled LaB6 model (heavy La ⇒ strong |F|², detectable extinction)."""
    from pxrdref import Instrument, PatternData
    from pxrdref.model.forward import compile_model
    from pxrdref.params.vector import ParameterTable
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
    from pxrdref.crystallography.lattice import d_spacings, two_theta_deg
    from pxrdref.crystallography.structure_factor import structure_factors_squared
    from pxrdref.model.corrections import lorentz_polarization

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
    from pxrdref import Instrument, PatternData
    from pxrdref.crystallography.lattice import cell_volume, d_spacings
    from pxrdref.crystallography.structure_factor import structure_factors_squared
    from pxrdref.model.forward import compile_model
    from pxrdref.optimize.least_squares import _make_jacobian, _make_residual
    from pxrdref.params.vector import ParameterTable
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
                          free_paths=set(table.free_paths))
    values = table.decode(table.x0())

    # G must genuinely differ from 1 (so the test discriminates) but no
    # reflection may cross the x=1 branch discontinuity (FD breaks there)
    cp = model.phases[0]
    cell = tuple(values[f"phases.0.cell.{k}"] for k in ("a", "b", "c", "alpha", "beta", "gamma"))
    d = d_spacings(cp.reflections.hkl, *cell)
    xyz, occ, biso, uaniso, astar = model._site_values(0, values, cell)
    f2 = structure_factors_squared(cp.reflections.hkl, d, cp.sites, xyz, occ, biso, uaniso, astar)
    lam0 = model.line_wavelengths[0]
    tt0 = cp.reflections.two_theta(cell, lam0)
    E, _, x = sabine_extinction_and_dx(f2, lam0, cell_volume(*cell), tt0,
                                       values["phases.0.extinction"])
    assert x.max() < 0.9, "extinction too strong — a reflection crosses x=1"
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


# -- GSAS-II golden ----------------------------------------------------


def test_golden_matches_gsas_getpwdrext_both_branches():
    ext = 0.03  # large enough that the strong low-angle reflections cross x = 1
    x = _x_of(ext)
    assert (x <= 1.0).any() and (x > 1.0).any(), "test must span both Laue branches"

    E = sabine_extinction(F2, WAVE, VOL, TT, ext)
    ref = np.array([_gsas_ext(f, t, ext) for f, t in zip(F2, TT, strict=True)])
    assert E == pytest.approx(ref, abs=1e-10, rel=1e-10)


def test_golden_matches_gsas_derivative_both_branches():
    ext = 0.03
    _, dEdx, x = sabine_extinction_and_dx(F2, WAVE, VOL, TT, ext)
    assert (x <= 1.0).any() and (x > 1.0).any()
    # dE/d(ext) = dE/dx · ∂x/∂ext = dEdx · (x/ext)
    dE_dext = dEdx * (x / ext)
    ref = np.array([_gsas_ext_derv(f, t, ext) for f, t in zip(F2, TT, strict=True)])
    assert dE_dext == pytest.approx(ref, abs=1e-10, rel=1e-8)


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
    """E ≤ 1 for all ext, and the within-branch slope dE/dx ≤ 0 everywhere.

    The reported slope is ≤ 0 on both Laue branches, so extinction only ever
    attenuates.  (E is *not* globally monotone in ext: GSAS-II's two-term x>1
    asymptote does not join the six-term x≤1 series continuously — see
    ``test_series_and_asymptote_jump_at_x_equals_one`` — so a reflection whose
    x sweeps through 1 sees a ~2% step.  That is the model as GSAS-II ships it,
    and it is out of reach for lab data where x ≪ 1.)
    """
    for ext in np.linspace(0.0, 0.4, 30):
        E = sabine_extinction(F2, WAVE, VOL, TT, ext)
        assert np.all(E <= 1.0 + 1e-12)
        _, dEdx, _ = sabine_extinction_and_dx(F2, WAVE, VOL, TT, ext)
        assert np.all(dEdx <= 0.0), f"positive slope at ext={ext}"


def test_extinction_is_monotone_in_the_lab_regime():
    """Where x stays ≤ 1 (the six-term series branch), E decreases with ext.

    This is the only regime lab or synchrotron powder data reach; the
    discontinuity above lives at x > 1 (E_L ≈ 0.6, a 40% intensity loss).
    """
    ext_grid = np.linspace(0.0, 0.02, 20)  # x_max stays < 1 here
    assert _x_of(ext_grid[-1]).max() < 1.0
    prev = np.ones_like(F2)
    for ext in ext_grid:
        E = sabine_extinction(F2, WAVE, VOL, TT, ext)
        assert np.all(E <= prev + 1e-12), f"E increased at ext={ext}"
        prev = E


def test_series_and_asymptote_jump_at_x_equals_one():
    """Pin the known GSAS-II discontinuity so a future 'fix' is a deliberate one."""
    el_below, _ = _laue_and_deriv(np.array([1.0]))       # six-term series at x=1
    el_above, _ = _laue_and_deriv(np.array([1.0 + 1e-9]))  # asymptote just above
    assert el_below[0] == pytest.approx(0.6742039, abs=1e-6)
    assert el_above[0] == pytest.approx(0.6981490, abs=1e-6)


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
