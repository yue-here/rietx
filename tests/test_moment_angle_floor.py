"""Exact moment-angle columns against the forward difference, on the fits that
decided where they may be used (issue #1404).

``_make_jacobian`` builds every moment-angle column analytically and gives a
column the forward difference only at a build where it is at most
``MOMENT_DIRECTION_SUPPORT`` of its sites' largest modulus column
(``least_squares._moment_angle_on_floor``).  The column-level evidence is in
``test_moment_jacobian`` and the frame fixture's in
``test_magnetic_moment_frame``.  This file holds the rule to the fits on
``test_stationary_moment_angle``'s Pnma sets, where an angle starts on **a**,
the direction the site symmetry fixes, and asks of each that it lands where
the forward-difference fit lands (``moment_grad_supported`` forced off, every
moment column by the peak chain, as ``test_moment_jacobian._fit_arm`` does):

* the two-site cell with Mn2 tilted 0.08 rad and Mn2's modulus profile, whose
  refits hold the modulus and still need the floor's reference;
* the on-axis cell (both moments along **a**), forty noise seeds;
* WP-2068's six deep starts, a one-site moment tilted or turned off **a**.

Measured 2026-11-20 on darwin/arm64 (Python 3.12, compiled tier); the
numbers are in each test's docstring.  Linux/x86-64 (numpy 2.5.3) gave the
same outcome on every row: the same zeroed sets, profile widths within 1.1e-4
relative of the forward difference's, coverage 20 of 20 and 33 of 40 in both
arms, the same four on-axis stops at the same Δχ², and the six deep starts
within 1e-10 on the solve's full plan (they now stop before its last stage).
The fits run with the closing stage the fixture declares.
"""
from __future__ import annotations

import os
import platform
from contextlib import contextmanager

import pytest

import rietx as rx
import rietx.optimize.least_squares as LS
from rietx.model.forward import CompiledModel
from rietx.optimize.least_squares import STATIONARY_ANGLE_LEVEL
from rietx.optimize.statistics import chi_bar_squared_quantile
from rietx.schemas.structure import Moment
from tests import test_stationary_moment_angle as S

MOD2 = f"{S.MN2}.dof0"
TRUE_MOD2 = 0.7


@contextmanager
def _arm(exact: bool, floor: list | None = None):
    """``exact=False`` is the forward-difference arm: the moment branch off.

    ``floor``, when given, collects the floor test's answer at each angle
    column it is asked about, so a row can say how many columns took the
    forward difference."""
    real = CompiledModel.moment_grad_supported
    real_floor = LS._moment_angle_on_floor
    if not exact:
        CompiledModel.moment_grad_supported = lambda self, ip: False
    if floor is not None:
        def spy(column_norm, modulus_norm):
            on = real_floor(column_norm, modulus_norm)
            floor.append(on)
            return on
        LS._moment_angle_on_floor = spy
    try:
        yield
    finally:
        CompiledModel.moment_grad_supported = real
        LS._moment_angle_on_floor = real_floor


def _fit(seed: int, *, exact: bool, tilt2: float | None, truth1=(3.5, 0.0, 0.0),
         profile: bool = False, plan: rx.RefinementPlan | None = None) -> dict:
    """Mn1 at ``truth1`` (``_vec`` arguments), Mn2 at 0.7 μ_B tilted ``tilt2``
    from **a** (``None``: one site); the start on **a** exactly.  ``plan``
    defaults to the solve's (``S._plan()``)."""
    T, mag = S._solve(), S._magnetic()
    instrument = T.neutron()
    m2 = None if tilt2 is None else Moment.from_values(S._vec(TRUE_MOD2, tilt2), "Mn3+")
    data = T.simulate(T.two_site(m1=Moment.from_values(S._vec(*truth1), "Mn3+"),
                                 m2=m2, magnetic=mag), instrument, seed=seed)
    start = T.two_site(
        m1=Moment.from_values((3.3, 0.0, 0.0), "Mn3+", vary=True),
        m2=(None if tilt2 is None
            else Moment.from_values((0.75, 0.0, 0.0), "Mn3+", vary=True)),
        magnetic=mag)
    floor: list[bool] = []
    with _arm(exact, floor):
        ref = rx.Refinement(rx.Structure(phases=[start]), instrument)
        ref._auto_intervals = False
        result = ref.fit(data, plan=S._plan() if plan is None else plan,
                         telemetry=False)
        interval = ref.profile_interval(data, MOD2) if profile else None
    rows = {p.path: p for p in result.parameters}
    st = result.statistics
    out = {"chi2r": st.chi2, "dof": st.n_points - st.n_free_parameters,
           "zeroed": frozenset(q for t in (result.stages[-1].moment_angle_tests or [])
                               if t.zeroed for q in t.paths),
           "interval": interval,
           "floor": (sum(floor), len(floor)),
           "stages": [f"{s.name} {s.status}/{s.termination} nfev {s.n_iterations}"
                      for s in result.stages]}
    if tilt2 is not None:
        out["m2"], out["s2"] = rows[MOD2].value, rows[MOD2].stderr
    return out


# ============================================== the two-site cell, profiled

def _profiled_pair(seed: int):
    return [_fit(seed, exact=exact, tilt2=0.08, profile=True) for exact in (True, False)]


def _width(fit):
    iv = fit["interval"]
    return None if iv.lower is None or iv.upper is None else iv.upper - iv.lower


def _check_profiled(seed, exact, fd):
    assert exact["zeroed"] != frozenset(S.ANGLES), (seed, "all four angles zeroed")
    assert exact["zeroed"] == fd["zeroed"], (seed, exact["zeroed"], fd["zeroed"])
    w_ex, w_fd = _width(exact), _width(fd)
    print(f"seed {seed}: {len(exact['zeroed'])} angles zeroed, Mn2 interval width "
          f"{w_ex} vs {w_fd}")
    assert (w_ex is None) == (w_fd is None), (seed, w_ex, w_fd)
    if w_ex is not None:
        assert abs(w_ex / w_fd - 1.0) <= 0.25, (seed, w_ex, w_fd)


def _covers(fit) -> bool:
    """An open side covers; seed 15 profiles to no bound on either side, in
    both arms."""
    iv = fit["interval"]
    return ((iv.lower is None or iv.lower <= TRUE_MOD2)
            and (iv.upper is None or TRUE_MOD2 <= iv.upper))


@pytest.mark.parametrize("seed", [4, 5, 6])
def test_a_profiled_two_site_fit_lands_where_the_forward_difference_does(seed):
    """The 4 Nov two-site cell: Mn1 3.5 μ_B on **a**, Mn2 0.7 μ_B tilted
    0.08 rad, the start on **a** for both, then Mn2's modulus profile, whose
    refits hold the modulus (so the floor's reference is the modulus column
    built from ``moment_f2_grads``, not one in J).  No fit has all four angles
    zeroed, the zeroed set is the forward difference's, and the profile
    interval's width is within 25 % of its width.  Three seeds here, ~10 s
    each for both arms, and fast because this is the solve the ruling was
    for: seeds 4-6 send the profile's refits to the floor most often among the
    first seven (95, 83 and 29 forward-difference columns, against 0-6 on
    seeds 0-3).  Twenty
    seeds, with coverage, in the slow test below; measured 2026-11-20
    (darwin/arm64) the widths agree to 1.1e-4 relative on every seed and 20 of
    20 cover in both arms."""
    exact, fd = _profiled_pair(seed)
    _check_profiled(seed, exact, fd)


@pytest.mark.slow
def test_twenty_profiled_two_site_fits_cover_as_the_forward_difference_does():
    """Twenty seeds of the cell above: the per-seed checks, and the profile
    intervals covering the true 0.7 μ_B in as many fits as the forward
    difference's, within one."""
    covered = {True: 0, False: 0}
    for seed in range(20):
        exact, fd = _profiled_pair(seed)
        _check_profiled(seed, exact, fd)
        covered[True] += _covers(exact)
        covered[False] += _covers(fd)
    print(f"coverage of 0.7 μ_B: exact {covered[True]}/20, forward difference "
          f"{covered[False]}/20")
    assert abs(covered[True] - covered[False]) <= 1, covered


# ============================================== the on-axis cell

@pytest.mark.slow
def test_on_axis_fits_stop_no_further_above_the_forward_difference_than_the_cut():
    """WP-2060 § 7's on-axis cell: both moments along **a** in truth and at the
    start, forty seeds, no profile.  The ruling's known limit: a few fits stop
    above the forward difference's stop, and none further above it than the
    stationary-angle test's cut for the angles it zeroed, c_k·χ²_red (k the
    number zeroed, at least one) -- the bound that test enforces when it
    zeroes them.  Coverage of the true Mn2 modulus by its ±1.96 esd interval
    is within one fit of the forward difference's.

    Measured 2026-11-20 (darwin/arm64): four of forty stop above by more than
    1e-6 of χ², seeds 3, 6, 9 and 34, at Δχ² 1.5, 2.3, 1.0 and 1.2 with all
    four angles zeroed (c₄·χ²_red ≈ 6.7, and even c₁·χ²_red ≈ 2.8 holds);
    coverage 33 of 40 in both arms."""
    covered = {True: 0, False: 0}
    above = []
    for seed in range(40):
        exact = _fit(seed, exact=True, tilt2=0.0)
        fd = _fit(seed, exact=False, tilt2=0.0)
        for arm, fit in ((True, exact), (False, fd)):
            if fit["s2"] is not None:
                covered[arm] += abs(fit["m2"] - TRUE_MOD2) <= 1.96 * fit["s2"]
        d_chi2 = (exact["chi2r"] - fd["chi2r"]) * fd["dof"]
        cut = chi_bar_squared_quantile(STATIONARY_ANGLE_LEVEL,
                                       max(1, len(exact["zeroed"]))) * fd["chi2r"]
        if d_chi2 > 1e-6 * fd["chi2r"] * fd["dof"]:
            above.append((seed, round(d_chi2, 2), len(exact["zeroed"])))
        assert d_chi2 < cut, (seed, d_chi2, cut)
    print(f"stops above the forward difference's (seed, Δχ², angles zeroed): "
          f"{above}; coverage exact {covered[True]}/40, forward difference "
          f"{covered[False]}/40")
    assert abs(covered[True] - covered[False]) <= 1, covered


# ============================================== WP-2068's deep starts

def _deep_plan() -> rx.RefinementPlan:
    """The solve's plan through its first two stages (the moduli, then the
    moment stage with scale and background), closing stage kept."""
    full = S._plan()
    return rx.RefinementPlan(stages=full.stages[:2],
                             closing_window_tol=full.closing_window_tol)


def _machine() -> str:
    """The CPU model, the core count and the xdist worker, for a row whose
    reference arm has moved on one CI job and not on a repeat."""
    model = platform.processor() or platform.machine()
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as fh:
            model = next((line.split(":", 1)[1].strip() for line in fh
                          if line.startswith("model name")), model)
    except OSError:
        pass
    return (f"cpu {model!r}, nproc {os.cpu_count()}, "
            f"PYTEST_XDIST_WORKER {os.environ.get('PYTEST_XDIST_WORKER')}")


def _deep_line(name: str, fit: dict) -> str:
    hits, checks = fit["floor"]
    columns = (f"{hits} of {checks} angle-column builds by forward difference"
               if checks else "every moment column by forward difference")
    return (f"{name}: χ²_red {fit['chi2r']:.12f}; {columns}; "
            f"stages {fit['stages']}; zeroed {sorted(fit['zeroed'])}")


@pytest.mark.parametrize("kind", ["tilt", "azimuth"])
@pytest.mark.parametrize("angle", [0.05, 0.2, 0.8])
def test_a_deep_start_reaches_the_forward_difference_s_chi2(kind, angle):
    """WP-2068's six starts: one site, truth 3.5 μ_B tilted towards **c** or
    turned towards **b** by ``angle``, noise seed 2, the start on **a**, where
    the direction is a deep maximum along the angle.  Every one reaches the
    forward-difference fit's χ² to 1e-6 relative.

    The deep starts stop before the plan's last stage, which frees the cell,
    zero, Biso and profile: there the reference arm's stop moved on one CI
    job (py3.14, 2026-11-20) and not on a run of the same tree on
    2026-11-24, and this row tests the angle rule, not that stage.

    Measured 2026-11-24 (darwin/arm64): the six agree to 8.1e-11 relative,
    the azimuth starts taking 3-12 of 30-46 angle-column builds by forward
    difference and the tilt starts 2.  With that fallback removed, the 0.2 rad
    tilt stops at χ²_red 1.0302671 against 1.0302484 (1.8e-5 relative, 18
    times the bar), so the bar separates the rule from the exact columns
    alone.  On the full plan (2026-11-20) the six agreed to 2e-10 and that
    tilt missed by 2.5e-4.
    """
    truth = (3.5, angle) if kind == "tilt" else (3.5, 0.0, angle)
    exact = _fit(2, exact=True, tilt2=None, truth1=truth, plan=_deep_plan())
    fd = _fit(2, exact=False, tilt2=None, truth1=truth, plan=_deep_plan())
    rel = abs(exact["chi2r"] - fd["chi2r"]) / fd["chi2r"]
    message = "\n".join([
        f"{kind} {angle}: relative difference {rel:.1e} (bar 1e-6)",
        _deep_line("rule", exact), _deep_line("forward difference", fd),
        _machine()])
    print(message)
    assert rel < 1e-6, message
