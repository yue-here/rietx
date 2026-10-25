"""The peak windows over the domain they claim (WP-2002, batch item B10).

B10 (ruled 2026-10-19): a numerical setting is tier 1 once a test bounds its
error over the domain it claims.  This file holds the window constants of
``rietx.model.forward`` that only a fit can exercise:

* ``WINDOW_AREA_TOL`` (2e-2), the area a window may drop from each peak.
* ``WINDOW_MIN_DEG`` (0.3°), the slack added to every half-width as movement
  headroom, and ``StageSpec.window_slack_deg``, whose default ``None`` is it.
* ``REFLECTION_MARGIN_DEG`` (0.5°), how far past the fitted range a
  reflection is still generated.

Each is measured on four families: NIST SRM 660c (LaB6, lab Cu Kα), the
GSAS-II fluorapatite tutorial (lab), the CPD round robin's cpd-1a (lab, three
phases) and 11-BM NAC (synchrotron), each under its acceptance protocol.

**Two bars, both a tenth of the noise.**

1. *The model at fixed parameters.*  At a protocol answer, y_calc under the
   shipped constant against y_calc under a converged one, point by point, in
   units of that point's own σ from the file.  A window drops a peak's tail,
   where σ is set by the background's counting noise rather than by the
   peak, so the dropped intensity is compared with the σ of the point it
   falls on.  The bar is max |Δy|/σ ≤ 0.1, which adds at most 1 % to that
   point's expected χ².  It is the bar the FCJ domain tests
   (``tests/test_lab_instrument.py``) set at the peak maximum.
2. *The answer.*  Both arms polished to a fixed point of "compile, then
   solve one all-free stage", up to five rounds, until no row moves by 0.01
   of its esd.  The bar is 0.1 plain esd (``stderr_uncorrected``) on every
   row that is not a background coefficient, the larger of the two arms'
   esds as the yardstick.  The background coefficients absorb the dropped
   tails, so they move most.  Their shift is reported, not asserted.

Both arms start from one answer: the protocol's, run with the reference
constant.  Comparing single polishes would compare where each compile put its
windows.  On LaB6 the first polish moves U by 0.9-1.2 esd under every window
setting, the second by 0.003-0.013.  The start matters as much: LaB6's
protocol lands in a different minimum under each tolerance (axial H/L 10 esd
apart at χ² 46 higher), and polishing from each keeps it there.  So the start
must not move with the constant under test, or changing the constant would
change the comparison.

Measured on 2026-10-21 (macOS arm64, worktree venv ``[dev]``, compiled tier
on, dispersion declined by every fixture):

=================================  ======  =====  ======  =====
WINDOW_AREA_TOL 2e-2, vs 5e-5      LaB6    FAP    cpd-1a  NAC
=================================  ======  =====  ======  =====
max |Δy|/σ at fixed parameters     1.13    2.04   2.15    0.71
largest non-background shift, esd  0.26    0.91   0.97    0.17
largest background shift, esd      2.1     5.1    4.0     3.7
=================================  ======  =====  ======  =====

The non-background rows that move are ``instrument.profile.x`` (LaB6, NAC),
the fluorapatite ``lor_size`` and the zincite scale.  At 1e-3 the same
columns read 0.058, 0.026, 0.022 and 0.091 σ, and 0.003, 0.008, 0.020 and
0.018 esd, with the background at 0.17-0.95 esd: both bars met.  At 2e-4 they
read under 0.009 σ and 0.012 esd.  The whole protocol fit takes 1.3×, 3.5×,
2.1× and 1.2× the shipped time at 1e-3, and 2.1×, 6.8×, 3.2× and 1.9× at
2e-4 (two runs each on a quiet machine; shipped LaB6 0.30-0.33 s, FAP
0.50-0.52 s, cpd-1a 0.98-1.03 s, NAC 0.34 s).  The converged-window model
does not always fit better: from the shipped answer its χ² is 110 higher than
the truncated one's on FAP and 37-1730 lower on the other three.

``WINDOW_MIN_DEG`` claims movement headroom only.  At the converged tolerance
the slack moves nothing: slack 0 and slack 1° give the slack-0.3° answer to
within 0.001 σ and 0.001 esd on all four families.  What it must cover is how
far a peak moves inside one stage.  The largest movement in any stage was
0.21° (cpd-1a, ``profile_w``, from the fixture's start and from a cold start
with the zero 0.1° off, the comment's "instrument-scale" error).  So the
slack holds with 1.4× to spare.  NAC is not started cold: 0.1° is about ten
of its FWHM, not an instrument-scale error at 11-BM, and its Le Bail pass
then diverges.

The frozen windows do not cover a peak that **widens** during a stage, and no
constant claims to.  In the ``profile`` stage of LaB6 (widths ×1.5) and
cpd-1a (×2.8), and cpd-1a's ``sample_broadening`` (×1.18), the end-state
peaks lose 6.5 %, 5.8 % and 3.0 % of their area against the 2 % bound.  The
next stage recompiles, so every final stage holds the bound (at most 1.96 %).

``REFLECTION_MARGIN_DEG``: a strong reflection just past the high-angle end
puts its tail into the range.  At 0.5° that tail is 0.124 σ (FAP, 129.98°)
and 0.119 σ (cpd-1a, 149.9°) at the last points, and moves the fluorite
``lor_strain`` by 0.103 esd.  LaB6 and NAC have nothing there.  Against 20°,
2° still leaves 0.114 σ and 0.11 esd on cpd-1a, whose high-angle windows are
about 4° wide.  5° is identical to 20° on both.  The margin needed grows with
the window, so a tighter ``WINDOW_AREA_TOL`` needs a wider margin: at 5e-5
the 0.5° margin leaves 0.169 σ on FAP.  At the closing stage's 1e-3 windows it
leaves 0.186 σ on FAP and 0.124 σ on cpd-1a at the last points, and moves the
closing answer 0.026 and 0.043 esd (measured 2026-10-21; the margin test below
still runs the declared stages' 2 %).

Each assertion was made to fail once, on 2026-10-21.  The real-data ones were
rerun with the module constant patched in-process (``rietx.model.forward``)
and the test selected by node id.  ``WINDOW_AREA_TOL`` at 1e-3 turned
``test_window_area_tol_meets_the_bar`` XPASS(strict) on all four families.
``REFLECTION_MARGIN_DEG`` at 5.0 did the same to the margin test on FAP and
cpd-1a.  ``WINDOW_MIN_DEG`` at 0.1 failed the movement test on cpd-1a and on
the cold FAP and cpd-1a starts, a peak moving 0.147° in a stage.
"""

from __future__ import annotations

import importlib
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest
from scipy.special import erf

import rietx as rx
import rietx.model.forward as fwd
from rietx.model import compiled
from rietx.model.profiles.fcj import fcj_live, fcj_offsets_weights
from rietx.params.vector import ParameterTable
from rietx.schemas.plan import CLOSING_WINDOW_TOL, StageSpec

refine_mod = importlib.import_module("rietx.refine")

pytestmark = pytest.mark.xdist_group("window-domain")

OUT = Path(__file__).parent / "output"
FAMILIES = ("lab6", "fap", "cpd1a", "nac")
#: the converged references: every row of every family within 0.009 σ at
#: 2e-4 of its value at 5e-5, and 5° bit-identical to 20°
TOL_CONVERGED = 5e-5
MARGIN_CONVERGED = 20.0
#: a tenth of the point's σ, and a tenth of a plain esd
NOISE_BAR = 0.1
ESD_BAR = 0.1
#: a fixed point: no row moves by more than this many esds between polishes
FIXED_POINT_ESD = 0.01
_C = 2.0 * np.sqrt(np.log(2.0))


def _build(family):
    """(data, structure, instrument, plan, fit kwargs) of the family's protocol,
    with no closing stage: the constants under test are the declared stages'."""
    data, st, ins, plan, kw = _protocol(family)
    plan.closing_window_tol = None
    return data, st, ins, plan, kw


def _protocol(family):
    """(data, structure, instrument, plan, fit kwargs) as the acceptance suite fits them."""
    if family == "lab6":
        from tests.test_acceptance_srm660c import _nist_calibrated_plan, build_srm_inputs
        data, st, ins = build_srm_inputs()
        return data, st, ins, _nist_calibrated_plan(), {}
    if family == "fap":
        from tests.test_acceptance_fap import _gsas_protocol_plan, build_fap_inputs
        data, st, ins = build_fap_inputs()
        return data, st, ins, _gsas_protocol_plan(), {}
    if family == "cpd1a":
        from tests.test_acceptance_qpa_roundrobin import (
            DATA,
            corundum_phase,
            fluorite_phase,
            qarr_instrument,
            qpa_plan,
            seed_scales,
            zincite_phase,
        )
        if not DATA.exists():
            pytest.skip("IUCr QPA round-robin dataset not present")
        data = rx.read_pattern(DATA / "cpd-1a.prn")
        st = rx.Structure(phases=[corundum_phase(), zincite_phase(), fluorite_phase()])
        ins = qarr_instrument()
        seed_scales(st, ins, data)
        return data, st, ins, qpa_plan(), {}
    from tests.test_acceptance_nac import LIMITS, _caf2_phase, build_nac_inputs
    data, st, ins = build_nac_inputs()
    kw = {"two_theta_limits": LIMITS}
    lb = rx.Refinement(st, ins, history=False)
    lebail = rx.RefinementPlan.mccusker_default()
    # the Le Bail pass seeds the Rietveld plan and stays as it was measured
    lebail.closing_window_tol = None
    lb.fit(data, mode="lebail", plan=lebail, **kw)
    st = lb.fitted_structure.model_copy(deep=True)
    ins = lb.fitted_instrument.model_copy(deep=True)
    st.phases[0].scale.value = 1e-6
    st.phases.append(_caf2_phase())
    plan = rx.RefinementPlan.mccusker_default()
    plan.stages.append(rx.Stage("biso", ["phases.*.atoms.*.biso"]))
    return data, st, ins, plan, kw


def _kept(c, gam, eta, a, b):
    """Area of the unit pseudo-Voigt (centre c, FWHM gam, mix eta) on [a, b]."""
    ua, ub = (a - c) / gam, (b - c) / gam
    lor = (np.arctan(2.0 * ub) - np.arctan(2.0 * ua)) / np.pi
    return eta * lor + (1.0 - eta) * 0.5 * (erf(_C * ub) - erf(_C * ua))


def _stage_summary(model, v0, v1):
    """For one solve: the largest peak movement, and the largest area an
    end-state peak inside the fitted range loses to the window frozen at the
    stage start (FCJ smear at 512 nodes where the aberration acts)."""
    tt = np.asarray(model.tt)
    step = np.diff(tt)
    sl = v1.get("instrument.geometry.axial_sl", 0.0)
    hl = v1.get("instrument.geometry.axial_hl", 0.0)
    live = fcj_live(sl, hl)
    move, worst = 0.0, (0.0, None)
    for ip, cp in enumerate(model.phases):
        for comp, win in ((0, cp.win), (1, cp.win_mag)):
            if win is None:
                continue
            p0 = model.phase_peaks(ip, v0, component=comp)
            p1 = model.phase_peaks(ip, v1, component=comp)
            for il in range(win.shape[0]):
                pos0 = np.asarray(p0[il][0], dtype=float)
                pos1, gam, eta = (np.asarray(x, dtype=float) for x in p1[il][:3])
                ok = np.isfinite(pos0) & np.isfinite(pos1)
                if ok.any():
                    move = max(move, float(np.abs(pos1[ok] - pos0[ok]).max()))
                for k in np.flatnonzero(ok & (pos1 >= tt[0]) & (pos1 <= tt[-1])):
                    lo, hi = int(win[il, k, 0]), int(win[il, k, 1])
                    if hi <= lo:
                        lost = 1.0
                    else:
                        # a window ending at the range edge is the margin's
                        # business, not the window's
                        a = -np.inf if lo == 0 else tt[lo] - 0.5 * step[lo - 1]
                        b = np.inf if hi >= len(tt) else tt[hi - 1] + 0.5 * step[hi - 1]
                        if live:
                            phi, om = fcj_offsets_weights(float(pos1[k]), sl, hl, 512)
                            kept = float(np.asarray(om) @ _kept(np.asarray(phi), gam[k],
                                                                eta[k], a, b))
                        else:
                            kept = float(_kept(pos1[k], gam[k], eta[k], a, b))
                        lost = 1.0 - kept
                    if lost > worst[0]:
                        worst = (lost, f"phase {ip} reflection {k} at {pos1[k]:.2f} deg")
    return move, worst


@lru_cache(maxsize=None)
def _family(family, cold=False):
    """The protocol fit, every solve summarised as it ran, and the answer."""
    was = compiled.set_enabled(True)
    try:
        data, st, ins, plan, kw = _build(family)
        assert ins.source.dispersion is None, "every fixture here declines dispersion"
        if cold:
            ins.zero_shift.value += 0.1
        stages = []
        orig = refine_mod.run_least_squares

        def recording(model, table, *, stage="", **k):
            v0 = dict(table.decode(table.x0()))
            out = orig(model, table, stage=stage, **k)
            stages.append((stage, *_stage_summary(model, v0, dict(table.decode(out.theta)))))
            return out

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(refine_mod, "run_least_squares", recording)
            ref = rx.Refinement(st, ins, history=False)
            res = ref.fit(data, plan=plan, **kw)
        OUT.mkdir(exist_ok=True)
        res.plot(path=str(OUT / f"window_domain_{family}{'_cold' if cold else ''}.png"))
        import matplotlib.pyplot as plt
        plt.close("all")
        return {"data": data, "plan": plan, "kw": kw, "stages": stages,
                "window_loss": [(s.window_loss, s.window_area_tol) for s in res.stages],
                "codes": {d.code for d in res.diagnostics},
                "structure": ref.fitted_structure.model_copy(deep=True),
                "instrument": ref.fitted_instrument.model_copy(deep=True)}
    finally:
        compiled.set_enabled(was)


def _patched(consts):
    mp = pytest.MonkeyPatch()
    for name, value in dict(consts).items():
        mp.setattr(fwd, name, value)
    return mp


@lru_cache(maxsize=None)
def _answer(family, consts):
    """The protocol's answer with the window constants at ``consts``: the
    common start both arms of a comparison polish from."""
    was = compiled.set_enabled(True)
    mp = _patched(consts)
    try:
        data, st, ins, plan, kw = _build(family)
        assert ins.source.dispersion is None
        ref = rx.Refinement(st, ins, history=False)
        ref.fit(data, plan=plan, **kw)
        return {"data": data, "plan": plan, "kw": kw,
                "structure": ref.fitted_structure.model_copy(deep=True),
                "instrument": ref.fitted_instrument.model_copy(deep=True)}
    finally:
        mp.undo()
        compiled.set_enabled(was)


def _y(family, start, consts):
    """y_calc and σ at the answer reached under ``start``, drawn under ``consts``."""
    f = _answer(family, start)
    mp = _patched(consts)
    try:
        st, ins = f["structure"], f["instrument"]
        # a declared stage's windows, read after the patch: compile_model's own
        # default is the closing stage's fraction (the seventh round's Q1)
        model = fwd.compile_model(st, ins, f["data"],
                                  two_theta_limits=f["kw"].get("two_theta_limits"),
                                  window_area_tol=fwd.WINDOW_AREA_TOL)
        table = ParameterTable(st, ins)
        y = np.asarray(model.evaluate(table.decode(table.x0())), dtype=float)
        return np.asarray(model.tt), y, np.asarray(model.sigma, dtype=float)
    finally:
        mp.undo()


def _rows(res):
    return {p.path: (p.value, p.stderr_uncorrected) for p in res.parameters}


def _shift(cur, ref, *, background):
    """Largest |cur − ref| over the larger of the two plain esds, among the
    background rows or among the rest.  The larger esd is B9's yardstick
    (``tests/test_seed_invariance.py``): a row on a nearly flat direction
    reads an esd of 7e-4 at one fixed point and 276 at the next (cpd-1a's
    fluorite ``lor_size``), and the smaller one would call its walk 22 esd."""
    worst = (0.0, None)
    for path, (value, e1) in cur.items():
        if path.startswith("instrument.background.") != background or path not in ref:
            continue
        v0, e0 = ref[path]
        esds = [e for e in (e0, e1) if e is not None and np.isfinite(e) and e > 0.0]
        if not esds:
            continue
        worst = max(worst, (abs(value - v0) / max(esds), path), key=lambda t: t[0])
    return worst


@lru_cache(maxsize=None)
def _fixed_point(family, start, consts):
    """Polish from the answer reached under ``start``, under ``consts``, until
    no row moves by ``FIXED_POINT_ESD``: the rows, and the obs/calc/diff figure."""
    f = _answer(family, start)
    globs = sorted({g for s in f["plan"].stages for g in s.turn_on})
    st, ins = f["structure"], f["instrument"]
    was = compiled.set_enabled(True)
    mp = _patched(consts)
    try:
        prev, settled = None, False
        for _ in range(5):
            ref = rx.Refinement(st.model_copy(deep=True), ins.model_copy(deep=True),
                                history=False)
            res = ref.fit(f["data"], plan=rx.RefinementPlan(
                stages=[rx.Stage("polish", globs)], closing_window_tol=None), **f["kw"])
            cur = _rows(res)
            st, ins = ref.fitted_structure, ref.fitted_instrument
            if prev is not None and max(_shift(cur, prev, background=False)[0],
                                        _shift(cur, prev, background=True)[0]) < FIXED_POINT_ESD:
                settled = True
                break
            prev = cur
        assert settled, (f"{family}: the polish under {consts or 'the shipped constants'} "
                         f"still moved a row by {FIXED_POINT_ESD} esd after five rounds, so "
                         f"the comparison is not between fixed points")
        tag = ("_".join(f"{k}{v}" for k, v in consts) or "shipped") + "_from_" + (
            "_".join(f"{k}{v}" for k, v in start) or "shipped")
        OUT.mkdir(exist_ok=True)
        res.plot(path=str(OUT / f"window_domain_{family}_{tag}.png"))
        import matplotlib.pyplot as plt
        plt.close("all")
        return cur
    finally:
        mp.undo()
        compiled.set_enabled(was)


def _assert_both_bars(family, ref, what):
    """Both bars, with both arms starting from the answer the protocol
    reaches under the reference ``ref``, so the start does not move with
    the constant under test."""
    tt, y, sig = _y(family, ref, ())
    _, y_ref, _ = _y(family, ref, ref)
    d = np.abs(y_ref - y) / sig
    j = int(np.argmax(d))
    shipped = _fixed_point(family, ref, ())
    converged = _fixed_point(family, ref, ref)
    model = _shift(shipped, converged, background=False)
    bkg = _shift(shipped, converged, background=True)
    msg = (f"{family}, {what}: max |dy|/sigma {d[j]:.3f} at {tt[j]:.2f} deg (bar {NOISE_BAR}); "
           f"answer moves {model[0]:.3f} esd on {model[1]} (bar {ESD_BAR}), "
           f"{bkg[0]:.2f} esd on {bkg[1]}")
    assert d[j] <= NOISE_BAR and model[0] <= ESD_BAR, msg


def _cells(failing):
    return [pytest.param(f, id=f, marks=([pytest.mark.xfail(strict=True, reason=failing[f])]
                                         if f in failing else []))
            for f in FAMILIES]


#: measured where WINDOW_AREA_TOL 2e-2 fails (module docstring's table)
_TOL_FAILS = {
    "lab6": "1.13 sigma at 29.29 deg; 0.26 esd on profile.x, 2.1 esd on background c0",
    "fap": "2.04 sigma at 30.8 deg; 0.91 esd on lor_size, 5.1 esd on background c0",
    "cpd1a": "2.15 sigma at 45.6 deg; 0.97 esd on the zincite scale, 4.0 on background c2",
    "nac": "0.71 sigma at 7.67 deg; 0.17 esd on profile.x, 3.7 esd on background c0",
}


@pytest.mark.slow
@pytest.mark.parametrize("family", _cells(_TOL_FAILS))
def test_window_area_tol_meets_the_bar(family):
    """``WINDOW_AREA_TOL`` against 5e-5, where every window spans the pattern
    to within 0.009 σ of its limit."""
    _assert_both_bars(family, (("WINDOW_AREA_TOL", TOL_CONVERGED),),
                      f"WINDOW_AREA_TOL {fwd.WINDOW_AREA_TOL} vs {TOL_CONVERGED}")


@pytest.mark.slow
@pytest.mark.parametrize("family", FAMILIES)
def test_the_converged_window_reference_is_converged(family):
    """The reference the area test reads: 2e-4 and 5e-5 agree to a fifth of
    the noise bar at every point (measured at most 0.009 σ, NAC)."""
    ref = (("WINDOW_AREA_TOL", TOL_CONVERGED),)
    tt, y_a, sig = _y(family, ref, (("WINDOW_AREA_TOL", 2e-4),))
    _, y_b, _ = _y(family, ref, ref)
    d = np.abs(y_b - y_a) / sig
    assert d.max() <= NOISE_BAR / 5, f"{family}: {d.max():.4f} sigma at {tt[np.argmax(d)]:.2f}"


@pytest.mark.slow
@pytest.mark.parametrize("family, cold", [
    *((f, False) for f in FAMILIES),
    # NAC is not started cold: 0.1 deg is ten of its FWHM (module docstring)
    *((f, True) for f in ("lab6", "fap", "cpd1a"))])
def test_window_min_deg_covers_every_stages_movement(family, cold):
    """Movement headroom: no peak moves further within one stage than the
    slack every window carries, nor than the reflection margin.  Measured at
    most 0.21 deg (cpd-1a ``profile_w``, warm and cold)."""
    stages = _family(family, cold)["stages"]
    stage, move, _ = max(stages, key=lambda s: s[1])
    assert StageSpec(name="x", turn_on=[]).window_slack_deg is None
    assert move <= fwd.WINDOW_MIN_DEG, (
        f"{family}{' cold' if cold else ''}: a peak moved {move:.3f} deg in {stage!r}, past "
        f"the {fwd.WINDOW_MIN_DEG} deg slack")
    assert move <= fwd.REFLECTION_MARGIN_DEG


_GROWTH_FAILS = {
    "lab6": "'profile' widens peaks 1.5x: 6.5 % of a peak's area lost (bound 2 %)",
    "cpd1a": "'profile' widens peaks 2.8x: 5.8 % lost; 'sample_broadening' 3.0 %",
}


@pytest.mark.slow
@pytest.mark.parametrize("family", FAMILIES)
def test_no_protocol_stage_ends_on_stale_windows(family):
    """WP-2047: every stage of the four protocols ends with its frozen windows
    dropping less than its own tolerance at its answer (1.61 % at most, LaB6's
    ``profile`` stage, against 2 %), so ``STAGE_WINDOWS_STALE`` stays silent
    on every fit the acceptance suites run."""
    f = _family(family)
    for loss, tol in f["window_loss"]:
        assert loss is not None and loss < fwd.recorded_window_tol(tol), f["window_loss"]
    assert "STAGE_WINDOWS_STALE" not in f["codes"]


@pytest.mark.slow
@pytest.mark.parametrize("family", _cells(_GROWTH_FAILS))
def test_frozen_windows_hold_the_area_bound_through_each_stage(family):
    """Every end-state peak inside the range keeps all but
    ``WINDOW_AREA_TOL`` of its area within the window frozen at its stage's
    start.  Fails where a stage widens the peaks, which no constant claims
    to cover; every final stage holds it (at most 1.96 %)."""
    # cold passed positionally, as the movement test does: lru_cache keys
    # _family(f) and _family(f, False) apart, which would refit the protocol
    stages = _family(family, False)["stages"]
    stage, _, (lost, where) = max(stages, key=lambda s: s[2][0])
    assert lost <= fwd.WINDOW_AREA_TOL, (
        f"{family}: {lost:.4f} of the area of {where} lost in {stage!r}")
    assert stages[-1][2][0] <= fwd.WINDOW_AREA_TOL


#: measured where REFLECTION_MARGIN_DEG 0.5 fails (module docstring)
_MARGIN_FAILS = {
    "fap": "0.124 sigma at 129.98 deg; 0.016 esd (Biso), 0.08 esd on background c5",
    "cpd1a": "0.119 sigma at 149.9 deg; 0.103 esd on fluorite lor_strain",
}


@pytest.mark.slow
@pytest.mark.parametrize("family", _cells(_MARGIN_FAILS))
def test_reflection_margin_meets_the_bar(family):
    """``REFLECTION_MARGIN_DEG`` against 20 deg, at the shipped tolerance."""
    _assert_both_bars(family, (("REFLECTION_MARGIN_DEG", MARGIN_CONVERGED),),
                      f"REFLECTION_MARGIN_DEG {fwd.REFLECTION_MARGIN_DEG} vs {MARGIN_CONVERGED}")


def test_a_stage_without_window_slack_compiles_the_window_min_deg_windows():
    """``StageSpec.window_slack_deg = None`` is ``WINDOW_MIN_DEG``, to the
    bit: the same frozen windows and the same pattern.  Made to fail once by
    passing ``WINDOW_MIN_DEG + 1e-3`` as the explicit slack."""
    from tests.test_schemas import make_lab6
    st = make_lab6()
    ins = rx.Instrument.bragg_brentano(radiation="CuKa", goniometer_radius_mm=173.0)
    ins.geometry.axial_sl.value = ins.geometry.axial_hl.value = 0.025
    grid = np.arange(15.0, 120.0, 0.02)
    pat = rx.PatternData(two_theta=grid.tolist(), intensity=np.ones_like(grid).tolist())
    assert StageSpec(name="x", turn_on=[]).window_slack_deg is None
    m_none = fwd.compile_model(st, ins, pat, window_slack_deg=None)
    m_min = fwd.compile_model(st, ins, pat, window_slack_deg=fwd.WINDOW_MIN_DEG)
    table = ParameterTable(st, ins)
    v = table.decode(table.x0())
    for a, b in zip(m_none.phases, m_min.phases, strict=True):
        assert np.array_equal(a.win, b.win)
    assert np.array_equal(np.asarray(m_none.evaluate(v)), np.asarray(m_min.evaluate(v)))


@lru_cache(maxsize=None)
def _closed(family):
    """The protocol's declared stages at the shipped constants, then the closing
    stage at ``CLOSING_WINDOW_TOL``: the answer a fit returns."""
    was = compiled.set_enabled(True)
    try:
        data, st, ins, plan, kw = _build(family)
        plan.closing_window_tol = CLOSING_WINDOW_TOL
        ref = rx.Refinement(st, ins, history=False)
        res = ref.fit(data, plan=plan, **kw)
        assert res.stages[-1].name == "closing"
        OUT.mkdir(exist_ok=True)
        res.plot(path=str(OUT / f"window_domain_{family}_closing.png"))
        import matplotlib.pyplot as plt
        plt.close("all")
        return {"data": data, "kw": kw, "rows": _rows(res),
                "structure": ref.fitted_structure.model_copy(deep=True),
                "instrument": ref.fitted_instrument.model_copy(deep=True)}
    finally:
        compiled.set_enabled(was)


#: measured where the closing stage fails (2026-10-21)
_CLOSING_FAILS = {
    "lab6": ("0.908 esd on profile.u, not a window: the closing stage is one polish at 1e-3 to "
             "every printed digit, a second recompile moves u 1 esd and a third 0.002, with the "
             "high-angle Gaussian variance on the clamp floor (WP-1467)"),
}


@pytest.mark.slow
@pytest.mark.parametrize("family", _cells(_CLOSING_FAILS))
def test_the_closing_stage_meets_the_bar(family):
    """The answer a fit returns meets both bars (the sixth round's Q1 and Q2).

    The closing stage starts from the declared stages' answer at the shipped
    2 % windows, so the reference starts there too: the fixed point at
    ``TOL_CONVERGED`` polished from that answer.  Bar 1 draws the closing
    answer at ``CLOSING_WINDOW_TOL`` and at ``TOL_CONVERGED``.  Bar 2 compares
    the closing answer, one solve, with the reference fixed point.

    Measured on 2026-10-21 (macOS arm64, ``[dev]``): bar 1 0.026, 0.022 and
    0.091σ and bar 2 0.008, 0.011 and 0.019 esd on the fluorapatite, cpd-1a
    and NAC (``lor_strain``, zincite's ``scale``, ``profile.x``; re-measured
    after the closing FCJ rule, cpd-1a was 0.018 on ``axial_sl``), the background
    0.23-0.95 esd.  LaB6 meets bar 1 at 0.058σ and misses bar 2 by 0.908 esd
    on ``profile.u``.  That is no window: its answer puts the highest-angle
    reflections' Gaussian variance U·tan²θ + V·tanθ + W under the clamp
    floor, where a polish moves U by an esd at any window (``waiting.md``
    § B10, forwarded to WP-1467), so a second recompile moves it 1 esd and a
    third 0.002.
    """
    f = _closed(family)
    st, ins = f["structure"], f["instrument"]
    lim = f["kw"].get("two_theta_limits")
    table = ParameterTable(st, ins)
    values = table.decode(table.x0())
    draws = []
    for tol in (CLOSING_WINDOW_TOL, TOL_CONVERGED):
        model = fwd.compile_model(st, ins, f["data"], two_theta_limits=lim,
                                  window_area_tol=tol)
        draws.append(np.asarray(model.evaluate(values), dtype=float))
    sig = np.asarray(model.sigma, dtype=float)
    d = np.abs(draws[1] - draws[0]) / sig
    j = int(np.argmax(d))
    converged = _fixed_point(family, (), (("WINDOW_AREA_TOL", TOL_CONVERGED),))
    rows = _shift(f["rows"], converged, background=False)
    bkg = _shift(f["rows"], converged, background=True)
    msg = (f"{family}, closing stage at {CLOSING_WINDOW_TOL}: max |dy|/sigma {d[j]:.3f} at "
           f"{np.asarray(model.tt)[j]:.2f} deg (bar {NOISE_BAR}); answer {rows[0]:.3f} esd "
           f"from the converged fixed point on {rows[1]} (bar {ESD_BAR}), background "
           f"{bkg[0]:.2f} esd on {bkg[1]}")
    print(msg)
    assert d[j] <= NOISE_BAR and rows[0] <= ESD_BAR, msg
