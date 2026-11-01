"""The Γ_G² clamp, kept out of LM's reach two ways (WP-1938 D7, D8).

``gaussian_fwhm`` clamps Γ_G² at ``caglioti._MIN_GAMMA_G2`` = 1e-8 deg², and
under the clamp every Gaussian width column is exactly zero.  LM's bounded
step lands W exactly on its floor, so with the floor at 0 and U = V = 0 a
stage freeing W put Γ_G² under the clamp at every point and stopped there.  A
synthetic LaB₆ pattern with NAC's widths reproduces it in a fraction of a
second.  Two things now keep the clamp out of reach, and each is tested here
alone.  W's floor is the clamp itself.  And Γ_G² ≥ ε at every reflection is
a row of LM's linear inequalities
(``least_squares.gaussian_width_inequalities``), held inside the step since
D8, which also covers a negative U or V.

obs/calc/diff PNGs of the LM fits go to ``tests/output/``.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

import rietx as rx
import rietx.optimize.least_squares as ls
from rietx import Instrument, PatternData, Refinement
from rietx.io.instrument_profile import read_gsas2_instprm, read_gsas_prm
from rietx.model.forward import compile_model
from rietx.model.profiles.caglioti import _MIN_GAMMA_G2, gaussian_fwhm
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import (
    TCHZ_BOUNDS,
    BackgroundChebyshev,
    ProfileTCHZ,
)
from tests.test_schemas import make_lab6

OUT = Path(__file__).parent / "output"
DATA = Path(__file__).parent / "data"
WAVELENGTH = 0.4139
#: NAC's widths under TRF (11-BM), x rounded: a narrow Gaussian beside a
#: Lorentzian, so the start's W = 1e-3 is far too broad
TRUE = {"u": 9e-4, "v": -2e-4, "w": 2.5e-5, "x": 2e-3}
_B = ["phases.0.scale", "instrument.background.*"]
PLAN = rx.RefinementPlan(stages=[
    rx.Stage(name="scale", turn_on=_B),
    rx.Stage(name="profile_w", turn_on=_B + ["instrument.profile.w"]),
    rx.Stage(name="profile", turn_on=_B + ["instrument.profile.u",
                                           "instrument.profile.v",
                                           "instrument.profile.w",
                                           "instrument.profile.x"]),
])


def _models(true: bool):
    structure = make_lab6()
    structure.phases[0].scale.value = 5e-4
    ins = Instrument.debye_scherrer(wavelength=WAVELENGTH)
    if true:
        for name, value in TRUE.items():
            getattr(ins.profile, name).value = value
        ins.background = BackgroundChebyshev(coefficients=[Parameter(value=40.0)])
    else:
        ins.background = BackgroundChebyshev.with_terms(1)
    return structure, ins


@pytest.fixture(scope="module")
def pattern() -> PatternData:
    structure, ins = _models(true=True)
    tt = np.arange(3.0, 24.0, 0.005)
    blank = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, blank, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(7).poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


def _fit(pattern, solver, *, w_min=None):
    structure, ins = _models(true=False)
    if w_min is not None:
        # written on the Parameter itself, which ProfileTCHZ's validator does
        # not see: the only way left to put W's floor back at 0
        ins.profile.w.min = w_min
    ref = Refinement(structure, ins, solver=solver, history=False)
    return ref, ref.fit(pattern, plan=PLAN)


def _g2_at_reflections(ref, result) -> np.ndarray:
    """The raw Γ_G² at every tick, before ``gaussian_fwhm``'s clamp."""
    p = ref.instrument.profile
    t = np.tan(np.radians(0.5 * np.asarray(
        [x for ticks in result.ticks.values() for x in ticks])))
    return p.u.value * t * t + p.v.value * t + p.w.value


def _draw(result, stem: str) -> None:
    from rietx.viz.plots import plot_result

    OUT.mkdir(exist_ok=True)
    plot_result(result, path=str(OUT / f"{stem}.png"))
    plot_result(result, path=str(OUT / f"{stem}_zoom.png"), two_theta_range=(9.5, 12.5))


@pytest.fixture(scope="module")
def trf(pattern):
    return _fit(pattern, "trf")


def test_with_w_bounded_at_zero_and_no_rows_lm_stops_under_the_clamp(
        pattern, trf, monkeypatch):
    """The trap both remedies exist for: it must still be reachable, or the
    tests below prove nothing."""
    monkeypatch.setattr(ls, "gaussian_width_inequalities", lambda m, t, x: [])
    ref, result = _fit(pattern, "lm", w_min=0.0)
    _draw(result, "gaussian_width_floor_off_lm")
    assert ref.instrument.profile.w.min == 0.0
    assert np.all(_g2_at_reflections(ref, result) < _MIN_GAMMA_G2)
    assert all(s.n_constraint_truncations == 0 for s in result.stages)
    assert result.statistics.chi2 > 10.0 * trf[1].statistics.chi2


def test_with_w_bounded_at_zero_the_rows_hold_and_lm_reaches_trfs_minimum(pattern, trf):
    """The rows alone, W's floor put back at 0: the ``profile_w`` stage
    presses Γ_G² onto ε at every reflection, and the step holds it there
    rather than truncating short of it (WP-1938 D8)."""
    ref, result = _fit(pattern, "lm", w_min=0.0)
    _draw(result, "gaussian_width_rows_lm")
    assert np.all(_g2_at_reflections(ref, result) >= _MIN_GAMMA_G2 * (1.0 - 1e-9))
    profile_w = next(s for s in result.stages if s.name == "profile_w")
    assert profile_w.n_constraint_truncations >= 1
    ref_trf, result_trf = trf
    assert result.statistics.chi2 == pytest.approx(result_trf.statistics.chi2, rel=1e-8)
    for name in "uvwx":
        assert getattr(ref.instrument.profile, name).value == pytest.approx(
            getattr(ref_trf.instrument.profile, name).value, rel=1e-4), name
    # the answer is interior, so the final stage pressed nothing
    assert not any(d.code == "CONSTRAINT_ACTIVE" for d in result.diagnostics)


@pytest.mark.parametrize("rows", [False, True], ids=["floor_alone", "default"])
def test_on_the_floor_lm_reaches_trfs_minimum(pattern, trf, monkeypatch, rows):
    if not rows:
        monkeypatch.setattr(ls, "gaussian_width_inequalities", lambda m, t, x: [])
    ref, result = _fit(pattern, "lm")
    _draw(result, "gaussian_width_floor_lm" if rows else "gaussian_width_floor_alone_lm")
    assert ref.instrument.profile.w.min == _MIN_GAMMA_G2
    assert np.all(_g2_at_reflections(ref, result) >= _MIN_GAMMA_G2)
    ref_trf, result_trf = trf
    assert result.statistics.chi2 == pytest.approx(result_trf.statistics.chi2, rel=1e-8)
    for name in "uvwx":
        assert getattr(ref.instrument.profile, name).value == pytest.approx(
            getattr(ref_trf.instrument.profile, name).value, rel=1e-4), name


def test_the_declared_boxes_start_at_the_clamp():
    assert TCHZ_BOUNDS["w"][0] == _MIN_GAMMA_G2
    assert ProfileTCHZ().w.min == _MIN_GAMMA_G2
    assert ProfileTCHZ.coarse().w.min == _MIN_GAMMA_G2


def test_a_stored_min_of_zero_opens_with_the_floor():
    """The ``MARCH_R_MIN`` precedent: the broken bound outlives the default.

    A project or history node written before the floor stores ``min: 0.0``,
    and W itself may sit on that 0, which is where the trap leaves it.
    """
    doc = Instrument.debye_scherrer(wavelength=WAVELENGTH).model_dump(mode="json")
    doc["profile"]["w"].update(value=0.0, min=0.0)
    w = Instrument.model_validate(doc).profile.w
    assert (w.value, w.min, w.max) == (_MIN_GAMMA_G2, _MIN_GAMMA_G2, TCHZ_BOUNDS["w"][1])

    # a value above the floor is kept, and only the bound moves
    doc["profile"]["w"].update(value=2.5e-5, min=0.0)
    w = Instrument.model_validate(doc).profile.w
    assert (w.value, w.min) == (2.5e-5, _MIN_GAMMA_G2)


def test_a_callers_bound_under_the_floor_is_raised():
    profile = ProfileTCHZ(w=Parameter(value=-0.01, min=-1.0, max=1.0))
    assert (profile.w.value, profile.w.min) == (_MIN_GAMMA_G2, _MIN_GAMMA_G2)
    # an assignment re-runs the model's validators
    profile.w = Parameter(value=0.0, min=0.0, max=1.0)
    assert (profile.w.value, profile.w.min) == (_MIN_GAMMA_G2, _MIN_GAMMA_G2)


def test_a_files_w_of_zero_reads_onto_the_floor(tmp_path):
    """A reader writes W onto a built profile, which the validator does not
    see, so each lifts a W in [0, floor) itself.  A negative W stays refused."""
    text = (DATA / "gsas2_hb2a.instprm").read_text(encoding="utf-8")
    path = tmp_path / "w0.instprm"
    path.write_text(re.sub(r"^W:.*$", "W:0.0", text, flags=re.M), encoding="utf-8")
    w = read_gsas2_instprm(path).profile.w
    assert (w.value, w.min) == (_MIN_GAMMA_G2, _MIN_GAMMA_G2)

    text = (DATA / "11bm_gsas.prm").read_text(encoding="utf-8")
    # PRCF11's GV and GW fields, at their fixed columns
    gw = "      -0.126000       0.063000"
    assert gw in text
    for new, name in (("      -0.126000       0.000000", "w0.prm"),
                      ("      -0.126000      -0.063000", "wneg.prm")):
        (tmp_path / name).write_text(text.replace(gw, new, 1), encoding="utf-8")
    w = read_gsas_prm(tmp_path / "w0.prm").profile.w
    assert (w.value, w.min) == (_MIN_GAMMA_G2, _MIN_GAMMA_G2)
    with pytest.raises(ValueError, match="wneg.prm"):
        read_gsas_prm(tmp_path / "wneg.prm")


# ----------------------------------------------------------------------
# the rows (WP-1938 D7, held inside the step since D8)
# ----------------------------------------------------------------------
def test_a_pawley_fit_pads_the_rows_past_its_intensity_block(pattern):
    """The rows read the table, and a Pawley solve's vector also carries one
    intensity per reflection.  Unpadded, ``T·θ`` raised a shape error on
    every Pawley stage freeing a width."""
    structure, ins = _models(true=False)
    ins.profile.w.min = 0.0               # so the rows, not the floor, bind
    ref = Refinement(structure, ins, solver="lm", history=False)
    result = ref.fit(pattern, plan=PLAN, mode="pawley")
    _draw(result, "gaussian_width_rows_pawley_lm")
    assert result.status == "converged"
    assert np.all(_g2_at_reflections(ref, result) >= _MIN_GAMMA_G2 * (1.0 - 1e-9))


def _stage_table(pattern, free: list[str], **widths):
    structure, ins = _models(true=False)
    for name, value in widths.items():
        getattr(ins.profile, name).value = value
    structure.phases[0].gauss_size.value = 2e-5
    structure.phases[0].gauss_strain.value = 3e-5
    model = compile_model(structure, ins, pattern, mode="rietveld")
    table = ParameterTable(structure, ins)
    table.set_vary(free, True)
    return model, table


def test_a_row_is_the_clamped_quantity_at_a_reflection(pattern):
    """T·θ + c is Γ_G² − ε, the quantity ``gaussian_fwhm`` clamps, with the
    phase's Gaussian size and strain in it."""
    model, table = _stage_table(
        pattern, ["instrument.profile.u", "instrument.profile.v",
                  "instrument.profile.w", "phases.0.gauss_size",
                  "phases.0.gauss_strain"], u=1e-4, v=-3e-5, w=4e-5)
    x0 = table.x0()
    (block,) = ls.gaussian_width_inequalities(model, table, x0)
    assert block.label == "instrument.profile (phases.0)"
    v = table.decode(x0)
    tt = np.asarray(model._cell_block(
        model.phases[0], tuple(v[f"phases.0.cell.{k}"] for k in
                               ("a", "b", "c", "alpha", "beta", "gamma")),
        model.line_lambdas(v))[1][0])
    on_data = model.phases[0].win[0][:, 1] > model.phases[0].win[0][:, 0]
    g = gaussian_fwhm(0.5 * tt[on_data], v["instrument.profile.u"],
                      v["instrument.profile.v"], v["instrument.profile.w"],
                      v["phases.0.gauss_size"], v["phases.0.gauss_strain"])
    expected = np.unique(np.round(np.asarray(g) ** 2 - _MIN_GAMMA_G2, 18))
    got = np.unique(np.round(block.slack(x0), 18))
    np.testing.assert_allclose(np.sort(got), np.sort(expected), rtol=1e-12)


def test_a_reflection_only_its_magnetic_window_reaches_still_gets_a_row(pattern):
    """A magnetic component is drawn over its own, wider window (``win_mag``),
    and its Γ_G² is the nuclear one.  So a reflection whose nuclear window
    holds no data, beside an excluded region or the range's edge, can still
    put a magnetic peak on the data, and its row is built."""
    model, table = _stage_table(
        pattern, ["instrument.profile.u", "instrument.profile.v",
                  "instrument.profile.w"], u=1e-4, v=-3e-5, w=4e-5)
    cp = model.phases[0]

    def n_rows():
        (block,) = ls.gaussian_width_inequalities(model, table, table.x0())
        return len(block.c)

    every = n_rows()
    cp.win_mag = cp.win.copy()
    cp.win = cp.win.copy()
    cp.win[0][3, 1] = cp.win[0][3, 0]          # reflection 3's nuclear window, emptied
    assert n_rows() == every
    cp.win_mag = None
    assert n_rows() == every - 1


def test_no_row_without_a_free_width_and_none_the_start_violates(pattern):
    model, table = _stage_table(pattern, ["instrument.profile.x"])
    assert ls.gaussian_width_inequalities(model, table, table.x0()) == []

    def rows_at(v: float):
        structure, ins = _models(true=False)
        ins.profile.w.value = _MIN_GAMMA_G2
        ins.profile.v.value = v
        model = compile_model(structure, ins, pattern, mode="rietveld")
        table = ParameterTable(structure, ins)
        table.set_vary(["instrument.profile.w"], True)
        return ls.gaussian_width_inequalities(model, table, table.x0()), table.x0()

    # U = V = 0 with W on its floor sits exactly on every row, and is held
    (block,), x0 = rows_at(0.0)
    assert np.all(block.slack(x0) == 0.0)
    # a negative V and no sample term: Γ_G² < ε at every reflection, so every
    # row is violated at the start and none is built (feasibility is kept,
    # never restored)
    assert rows_at(-1e-4)[0] == []


# ------------------------------------------------ _MIN_GAMMA_G2 over its domain (B10)
#: a tenth of σ/peak at the strongest peak: what a profile error may reach and
#: add at most 1 % to that point's expected χ² (lab FAP.XRA, 11-BM NAC)
NOISE_BAR = {"lab": 0.1 * 7.2e-3, "synchrotron": 0.1 * 1.75e-3}


def _floor_profile_change(gamma_l: float) -> float:
    """The largest change, in units of the peak height, that clamping Γ_G at
    √``_MIN_GAMMA_G2`` makes to a TCHZ peak whose true Γ_G lies under it."""
    from rietx.model.profiles.pseudovoigt import pseudo_voigt, tch_gamma_eta

    floor = np.sqrt(_MIN_GAMMA_G2)
    x = np.linspace(-20.0 * gamma_l, 20.0 * gamma_l, 40001)
    g1, e1 = tch_gamma_eta(np.array(floor), np.array(gamma_l))
    clamped = pseudo_voigt(x, g1, e1)
    worst = 0.0
    for true in (0.0, 0.5 * floor, 0.9 * floor):
        g0, e0 = tch_gamma_eta(np.array(max(true, 1e-300)), np.array(gamma_l))
        exact = pseudo_voigt(x, g0, e0)
        worst = max(worst, float(np.max(np.abs(clamped - exact)) / np.max(exact)))
    return worst


@pytest.mark.parametrize("noise, gamma_l", [
    ("lab", 5e-3),
    ("synchrotron", 1e-2),
    pytest.param("synchrotron", 3e-3, marks=pytest.mark.xfail(strict=True, reason=(
        "a peak whose Gaussian part is under the floor and whose Lorentzian FWHM "
        "is 0.003 deg moves by 9.9e-4 of its height, 0.56 sigma/peak at 11-BM "
        "(measured 2026-10-21); NAC's narrowest Lorentzian is 0.0026 deg, but its "
        "Gaussian part there is 1180x the floor, so the clamp does not act")))])
def test_where_the_floor_binds_it_moves_a_peak_less_than_the_noise(noise, gamma_l):
    """``_MIN_GAMMA_G2`` = 1e-8 deg² (Γ_G ≥ 1e-4°), at fixed parameters.

    The floor changes the model only at a reflection whose Caglioti Γ_G²
    falls under it.  There the peak is a TCHZ with Γ_G = 1e-4° in place of
    something narrower, and the change is largest when the Lorentzian is
    narrow.  Measured as a fraction of the peak height: 6.9e-3 at
    Γ_L = 0.001°, 9.9e-4 at 0.003°, 4.4e-4 at 0.005°, 1.6e-4 at 0.01°,
    1.1e-5 at 0.1° and 6.4e-6 at 0.164° (SRM 660c's high-angle Γ_L).  So the
    floor meets the lab bar wherever Γ_L ≥ 0.005° and the 11-BM bar wherever
    Γ_L ≥ 0.01°.

    Made to fail on 2026-10-21: ``_MIN_GAMMA_G2`` patched to 1e-6 deg²
    (Γ_G ≥ 1e-3°) moved the two passing rows by 2.6e-2 and 6.9e-3.
    """
    change = _floor_profile_change(gamma_l)
    assert change <= NOISE_BAR[noise], (
        f"Gamma_L {gamma_l} deg: the floor moves the peak by {change:.2e} of its "
        f"height (bar {NOISE_BAR[noise]:.2e}, {noise})")


def _families():
    from tests.test_window_domain import FAMILIES

    return FAMILIES


@pytest.mark.slow
@pytest.mark.parametrize("family", _families())
def test_the_floor_leaves_every_protocol_answer_under_the_noise(family, monkeypatch):
    """The real-data half: at each family's protocol answer, y_calc with the
    shipped floor against y_calc with none, point by point in units of the
    file's σ, bar 0.1 (1 % of that point's expected χ²).

    Raw Γ_G² at the reflections inside the fitted range sits far above the
    floor on three families: 1180× at its lowest on 11-BM NAC (Γ_G 0.0034°
    at 13.5°), 10 252× on cpd-1a and 2.5e5× on FAP.  SRM 660c's answer has
    the instrument's Caglioti quadratic negative at its highest-angle points
    (``RESOLUTION_NOT_POSITIVE``: 75 of 5332, worst at 150.9°), where the
    floor binds.  The Lorentzian there is 0.164°, which bounds the floor's
    effect at about 6e-6 of the peak.  Measured
    max |Δy|/σ on 2026-10-21 (macOS arm64, ``[dev]``, compiled tier on): 0
    on SRM 660c, FAP and NAC, 4.8e-9 on cpd-1a.  SRM 660c reads 0 because
    its answer keeps every reflection at or above the face Γ_G² = 1e-8
    (``CONSTRAINT_ACTIVE``), one of them within 1e-6 deg² of it at 149.7°,
    so the clamp and no clamp agree; a floor of 1e-6 moves that point by
    0.002 σ.

    This bar is at fixed parameters.  The answer is another matter: polished
    under a floor of 1e-10, SRM 660c's and cpd-1a's answers stop 1.2 plain
    esd away on ``profile.u`` (FAP and NAC do not move), and so does a polish
    under an ``FD_STEP`` of 5e-7.  ``tests/test_cross_backend.py``'s
    ``test_fd_columns_hold_at_every_protocol_answer`` records that face.

    Made to fail on 2026-10-21: ``_MIN_GAMMA_G2`` patched to 1e-3 deg²
    (Γ_G ≥ 0.032°) failed NAC at 163 σ.
    """
    import rietx.model.profiles.caglioti as caglioti
    from rietx.model.forward import compile_model
    from tests.test_window_domain import _answer

    f = _answer(family, ())
    st, ins = f["structure"], f["instrument"]
    # two compiles, so the windows are the shipped ones in both and the
    # second model's width memo has never seen the shipped floor
    model, fresh = (compile_model(st, ins, f["data"],
                                  two_theta_limits=f["kw"].get("two_theta_limits"))
                    for _ in range(2))
    table = ParameterTable(st, ins)
    values = table.decode(table.x0())
    shipped = np.asarray(model.evaluate(values), dtype=float)
    monkeypatch.setattr(caglioti, "_MIN_GAMMA_G2", 1e-300)
    unfloored = np.asarray(fresh.evaluate(values), dtype=float)
    d = np.abs(shipped - unfloored) / np.asarray(model.sigma, dtype=float)
    k = int(np.argmax(d))
    assert d[k] <= 0.1, (f"{family}: the floor moves y_calc by {d[k]:.3g} sigma at "
                         f"{np.asarray(model.tt)[k]:.2f} deg")


def test_constraint_active_names_the_block_that_bound():
    from rietx.refine import _constraint_diagnostics

    (d,) = _constraint_diagnostics("profile", SimpleNamespace(
        n_constraint_truncations=2,
        truncated_by={"instrument.profile (phases.0)": 2}))
    assert "instrument.profile (phases.0): 2" in d.message
    assert "Γ_G² floor" in d.suggestion
    assert "STEPHENS" not in d.suggestion
    (d,) = _constraint_diagnostics("strain", SimpleNamespace(
        n_constraint_truncations=1, truncated_by={"phases.0.microstrain": 1}))
    assert "phases.0.microstrain: 1" in d.message
    assert "STEPHENS_STRAIN_NOT_POSITIVE" in d.suggestion
    assert "Γ_G² floor" not in d.suggestion
