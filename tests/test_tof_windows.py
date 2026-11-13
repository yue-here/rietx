"""Frozen evaluation windows on a flight-time bank, sized by the tail.

The back-to-back-exponential peak is **asymmetric**, and its asymmetry is a
function of α and β — the very coefficients a stage refines.  So a window that
discards a fixed fraction of the *area* discards a fraction that moves between
candidate solutions, and a window frozen for the stage turns that into a term
in χ² that depends on where the model was compiled rather than on where it is.
Measured on a real bank at 2 %
it was worth 42 χ² units in 1941 — enough to move the χ² minimum by eleven of
its own σ and to score an uphill step as downhill.

The rule here is a **per-side, per-component** discarded fraction,
``TOF_WINDOW_AREA_TOL``, with the exponential wings sized as −ln(tol)
e-foldings and the resolution function to the same fraction on each side.  The
two extents are *added*, which is a bound rather than an approximation: the
profile is a convolution, so ``P(E + R > h_E + h_R) ≤ P(E > h_E) + P(R > h_R)``.

**Every fixture here is synthetic.**  No real bank's numbers are in it.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

import rietx as rx
from rietx.model import forward_tof as ftof
from rietx.model.forward import WINDOW_AREA_TOL, window_fwhm_mult
from rietx.model.forward_tof import (
    TAIL_EFOLDS,
    TOF_WINDOW_AREA_TOL,
    compile_tof_model,
)
from rietx.model.profiles.tof import back_to_back_gaussian
from rietx.params.vector import ParameterTable
from rietx.schemas.pattern import PatternData
from rietx.schemas.structure import Atom, Cell, Phase, Structure

P = rx.Parameter

TOF_LO, TOF_HI, TOF_STEP = 8000.0, 45000.0, 10.0
#: β well below α, which is the normal case: the pulse rises fast and decays
#: slowly, so the long-flight-time wing is several times the short one and a
#: symmetric window either truncates the tail or pays for it twice.
PROFILE = dict(alpha1=0.45, beta0=0.055, beta1=0.003, sig1=300.0)


def silicon(a: float = 5.4311946, biso: float = 0.5) -> Structure:
    cell = Cell(a=P(value=a), b=P(value=a), c=P(value=a), alpha=P(value=90.0),
                beta=P(value=90.0), gamma=P(value=90.0))
    return Structure(phases=[Phase(
        name="Si", space_group="F d -3 m :2", cell=cell, scale=P(value=1.0),
        atoms=[Atom(label="Si", species="Si", x=P(value=0.125),
                    y=P(value=0.125), z=P(value=0.125), biso=P(value=biso))])])


def bank(**profile):
    prof = dict(PROFILE)
    prof.update(profile)
    return rx.Instrument.tof_neutron_bank(
        difc=12000.0, tzero=-5.0, two_theta_bank_deg=90.0,
        profile=rx.ProfileTOF(**{k: P(value=v) for k, v in prof.items()}))


def grid() -> np.ndarray:
    return np.arange(TOF_LO, TOF_HI + 0.5 * TOF_STEP, TOF_STEP)


def blank() -> PatternData:
    g = grid()
    return PatternData(tof=g.tolist(), intensity=[1.0] * len(g))


def values_of(structure, instrument) -> dict[str, float]:
    return {e.path: e.value for e in ParameterTable(structure, instrument).entries}


# ------------------------------------------------------------------ the rule
def test_the_two_halves_of_one_window_state_one_tolerance():
    """``TAIL_EFOLDS`` is **derived** and not chosen beside the tolerance.

    The mass of a normalised exponential beyond ``k`` e-foldings is exactly
    ``e^{-k}``, so ``-ln(tol)`` is the sizing that leaves ``tol`` outside.  A
    constant chosen independently could disagree with the other half of the
    same window, which is what the shipped rule did: 12 e-foldings (6e-6) on
    the wings against 2 % on the resolution, i.e. the resolution alone decided
    the truncation and nothing said so.
    """
    assert TAIL_EFOLDS == pytest.approx(-math.log(TOF_WINDOW_AREA_TOL))
    assert math.exp(-TAIL_EFOLDS) == pytest.approx(TOF_WINDOW_AREA_TOL)
    assert TOF_WINDOW_AREA_TOL < WINDOW_AREA_TOL / 100.0


def test_the_constant_wavelength_tolerance_is_untouched_and_is_the_default():
    """``window_fwhm_mult`` grew an argument, not a new default."""
    eta = np.array([0.0, 0.3, 0.6, 1.0])
    assert np.array_equal(window_fwhm_mult(eta),
                          window_fwhm_mult(eta, tol=WINDOW_AREA_TOL))
    # …and the argument does something: a tighter tolerance is a wider window,
    # monotonically, at every η
    tight = window_fwhm_mult(eta, tol=2.0 * TOF_WINDOW_AREA_TOL)
    assert np.all(tight > window_fwhm_mult(eta))


def _worst_discard(profile, tol, efolds):
    """``(worst rise-side fraction, worst decay-side fraction, peaks checked)``.

    For each reflection the compiled window's two half-widths are recovered
    from the frozen indices and the unit-area profile is integrated outside
    each of them, on a grid 200× finer than the pattern's and out to 40
    e-foldings, so the quadrature is not the limit.
    """
    old = ftof.TOF_WINDOW_AREA_TOL, ftof.TAIL_EFOLDS
    ftof.TOF_WINDOW_AREA_TOL, ftof.TAIL_EFOLDS = tol, efolds
    try:
        st, ins = silicon(), bank(**profile)
        m = compile_tof_model(st, ins, blank())
        (pos, alpha, beta, sigma, _g, _i), = m.phase_peaks(
            0, values_of(st, ins))
        g, win = grid(), m.phases[0].win[0]
        worst_lo = worst_hi = 0.0
        checked = 0
        for k in range(len(pos)):
            i0, i1 = int(win[k, 0]), int(win[k, 1])
            if i1 - i0 < 10 or i0 == 0 or i1 >= len(g):
                continue       # a window the pattern's own ends clipped
            lo = float(pos[k]) - g[i0]
            hi = g[i1 - 1] - float(pos[k])
            far = max(lo, hi) * 6.0 + 40.0 / float(min(alpha[k], beta[k]))
            dt = np.linspace(-far, far, 400001)
            omega = np.asarray(back_to_back_gaussian(
                dt, float(alpha[k]), float(beta[k]), float(sigma[k])))
            total = np.trapezoid(omega, dt)
            worst_lo = max(worst_lo,
                           np.trapezoid(omega[dt < -lo], dt[dt < -lo]) / total)
            worst_hi = max(worst_hi,
                           np.trapezoid(omega[dt > hi], dt[dt > hi]) / total)
            checked += 1
        return worst_lo, worst_hi, checked
    finally:
        ftof.TOF_WINDOW_AREA_TOL, ftof.TAIL_EFOLDS = old


def test_the_discarded_area_is_the_stated_bound_on_each_side_separately():
    """The rule's own claim, integrated rather than argued — with the arm that
    says the claim is not free.

    The bound is ``2·TOF_WINDOW_AREA_TOL`` per side (the union bound over the
    exponential and the resolution), and every peak must sit under it on
    **both** sides.  The shipped rule on the *same* peaks does not: measured
    3.8e-4 on the rise side, nearly twice the bound and ten times its own
    decay side — the shape dependence, in the currency the rule is written in.

    Measured in the ``FAST`` regime, which is where the resolution half of the
    window binds and is the regime the real banks are in; with a slow decay
    the shipped rule's 12 e-foldings covered the tail on their own and its
    2 %-of-area resolution never bit.  A fixture has to state its regime
    rather than be "a bank".
    """
    bound = 2.0 * TOF_WINDOW_AREA_TOL
    lo, hi, checked = _worst_discard(FAST, TOF_WINDOW_AREA_TOL, TAIL_EFOLDS)
    assert checked > 10, "the arm checked too few peaks to mean anything"
    assert lo < bound and hi < bound

    was_lo, was_hi, _ = _worst_discard(FAST, *SHIPPED)
    assert was_lo > bound                # the shipped rule was not a bound
    assert was_lo > 5.0 * was_hi         # and it was not symmetric either


def test_the_window_is_asymmetric_the_way_the_pulse_is():
    """β < α puts the tail at long flight time, so the decay side of every
    window must be the longer one — the whole reason the two wings are sized
    separately rather than from one FWHM."""
    st, ins = silicon(), bank()
    m = compile_tof_model(st, ins, blank())
    v = values_of(st, ins)
    (pos, alpha, beta, _s, _g, _i), = m.phase_peaks(0, v)
    g, win = grid(), m.phases[0].win[0]
    seen = 0
    for k in range(len(pos)):
        i0, i1 = int(win[k, 0]), int(win[k, 1])
        if i1 - i0 < 10 or i0 == 0 or i1 >= len(g):
            continue
        assert beta[k] < alpha[k]                     # the premise
        assert g[i1 - 1] - pos[k] > pos[k] - g[i0]    # the consequence
        seen += 1
    assert seen > 10


# --------------------------------------------- what the tolerance is worth
#: The regime the real banks are in and the one this rung is about: a rise and
#: a decay fast against the Gaussian resolution, so it is the **resolution**
#: half of the window that binds and the exponential wings are cheap (a real
#: high-resolution bank has 1/α far below σ).  With
#: a slow decay instead, the 12-e-folding wings of the shipped rule ran to 4σ
#: on their own and the 2 %-of-area resolution never bit — which is why a
#: fixture has to state its regime rather than be "a bank".
FAST = dict(alpha1=8.0, beta0=0.6, beta1=0.0, sig1=300.0)
#: The same bank with a threefold slower rise and decay: a *different profile
#: shape*, which is what a stage refining α and β walks between and what a
#: fixed-fraction-of-area window truncates by a different amount.
SLOW = dict(alpha1=1.2, beta0=0.12, beta1=0.0, sig1=300.0)
#: Counting statistics strong enough that the truncation is visible above the
#: Poisson noise rather than mixed into it — at a tenth of this the penalty is
#: dominated by the cross term with the noise and changes sign between seeds,
#: which would make the arm measure a seed.
SCALE, BACKGROUND = 500.0, 200.0


def state(a, profile):
    st, ins = silicon(a), bank(**profile)
    st.phases[0].scale.value = SCALE
    ins.background.coefficients[0].value = BACKGROUND
    return st, ins


def _chi2_at(st, ins, data, **kw):
    """χ² with the model compiled **at** this state — never ``result.y_calc``,
    which carries the window of the state the stage started from."""
    m = compile_tof_model(st, ins, data, **kw)
    r = (m.y_obs - np.asarray(m.evaluate(values_of(st, ins)))) / m.sigma
    return float(r @ r)


def observed(seed: int = 20260906) -> PatternData:
    """Poisson counts around the ``FAST`` state, generated with 500 µs of
    window slack so the *data* carries no truncation of its own."""
    st, ins = state(5.4311946, FAST)
    m = compile_tof_model(st, ins, blank(), window_slack_us=500.0)
    y = np.asarray(m.evaluate(values_of(st, ins)), dtype=np.float64)
    rng = np.random.default_rng(seed)
    return PatternData(tof=grid().tolist(),
                       intensity=rng.poisson(np.maximum(y, 0.0)
                                             ).astype(np.float64).tolist())


def penalty(tol, efolds, st, ins, data):
    """χ²(frozen window) − χ²(the same state with 500 µs of extra slack).

    500 µs is the untruncated reference: it swamps every tail here, and on the
    real bank 200 / 500 / 1000 / 3000 / 8000 µs all agree to four decimals.
    """
    old = ftof.TOF_WINDOW_AREA_TOL, ftof.TAIL_EFOLDS
    ftof.TOF_WINDOW_AREA_TOL, ftof.TAIL_EFOLDS = tol, efolds
    try:
        return (_chi2_at(st, ins, data)
                - _chi2_at(st, ins, data, window_slack_us=500.0))
    finally:
        ftof.TOF_WINDOW_AREA_TOL, ftof.TAIL_EFOLDS = old


#: The rule an earlier draft of this model shipped: 12 e-foldings on the wings against a
#: **two-sided** 2 % of area on the resolution, i.e. two halves of one window
#: sized to bars four orders apart, so the resolution alone decided the
#: truncation and nothing said so.
SHIPPED = (1e-2, 12.0)
NOW = (TOF_WINDOW_AREA_TOL, TAIL_EFOLDS)


def test_the_frozen_window_no_longer_charges_the_shape_it_was_compiled_at():
    """The measurement this rung exists for, on a synthetic bank.

    One observed pattern and two candidate states of it, differing in the cell
    *and* in the pulse asymmetry — the pair a solver walks between, and the
    pair a shape-dependent truncation cannot cancel over.  Under the shipped
    rule the truncation penalty is large and, worse, **different** between the
    two, so the frozen χ² is not the χ² of the state it describes.

    The bar is that difference, not the penalty: a penalty equal at both
    states would cancel out of every comparison a solver makes.
    """
    data = observed()
    left = state(5.4311946, FAST)
    right = state(5.4311946 * 1.00005, SLOW)

    shipped = [penalty(*SHIPPED, st, ins, data) for st, ins in (left, right)]
    now = [penalty(*NOW, st, ins, data) for st, ins in (left, right)]

    assert abs(shipped[0] - shipped[1]) > 20.0     # the defect, reproduced
    assert abs(now[0] - now[1]) < 2.0              # the bar
    assert max(abs(p) for p in now) < 2.0
    # and it is a real improvement, not a rescaled one
    assert abs(now[0] - now[1]) < 0.01 * abs(shipped[0] - shipped[1])


def test_the_generating_state_reaches_its_own_noise_floor():
    """The consequence in the units a reader quotes.

    The data is Poisson noise around the ``FAST`` state, so χ² evaluated *at*
    that state is a draw from χ²(n) and χ²_red must be ≈ 1.  Under the shipped
    window rule it is not: the truncated intensity is a systematic deficit at
    every peak, and the state the data was generated from cannot reach its own
    noise floor.  Nothing about the model is wrong there — only the window.
    """
    data = observed()
    st, ins = state(5.4311946, FAST)
    n = len(grid())

    old = ftof.TOF_WINDOW_AREA_TOL, ftof.TAIL_EFOLDS
    try:
        ftof.TOF_WINDOW_AREA_TOL, ftof.TAIL_EFOLDS = SHIPPED
        shipped = _chi2_at(st, ins, data) / n
        ftof.TOF_WINDOW_AREA_TOL, ftof.TAIL_EFOLDS = NOW
        now = _chi2_at(st, ins, data) / n
    finally:
        ftof.TOF_WINDOW_AREA_TOL, ftof.TAIL_EFOLDS = old

    assert abs(now - 1.0) < 0.05
    assert shipped > now + 0.1


def test_a_step_between_the_two_states_is_scored_the_same_way_twice():
    """The consequence that reaches a user: under a shape-dependent
    truncation, a χ² difference computed on one frozen window disagrees with
    the same difference computed at each state — which is how an uphill step
    scores as downhill.  Here the two ways of asking must agree."""
    data = observed()
    left = state(5.4311946, FAST)
    right = state(5.4311946 * 1.00005, SLOW)

    def gap(**kw):
        return (_chi2_at(*left, data, **kw) - _chi2_at(*right, data, **kw))

    frozen = gap()
    untruncated = gap(window_slack_us=500.0)
    assert abs(frozen - untruncated) < 2.0
    assert np.sign(frozen) == np.sign(untruncated)


def test_a_result_reproduces_from_its_own_parameters():
    """``result.y_calc`` against a model recompiled at ``result.parameters``:
    the same state, so the same curve, and the difference is a χ² of zero."""
    data = observed()
    st0, ins0 = state(5.4311946 * 1.0002, FAST)
    st0.phases[0].atoms[0].biso.value = 1.0
    ref = rx.Refinement(st0, ins0, history=False)
    plan = rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.c*"]),
        rx.Stage("late", ["phases.*.cell.a", "phases.*.atoms.*.biso"]),
    ])
    plan.intermediate_ftol = None
    res = ref.fit(data, plan=plan)
    st, ins = ref.fitted_structure, ref.fitted_instrument
    m = compile_tof_model(st, ins, data)
    reported = np.asarray(res.y_calc, dtype=np.float64)
    fresh = np.asarray(m.evaluate(values_of(st, ins)), dtype=np.float64)
    d = (reported - fresh) / m.sigma
    assert float(d @ d) < 1.0
