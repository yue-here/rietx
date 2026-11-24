"""WP-2056: ``LOW_ANGLE_ASYMMETRY_UNCALIBRATED`` — the lowest lines are magnetic.

Issue #1090's point 2.  On a constant-wavelength neutron pattern whose lowest
seen lines are all magnetic-only, no nuclear line in the sample checks the
axial asymmetry where it is largest.  The finding reports each such line's
position shift and decides nothing.

The arms, on the synthetic CrSBr k = (0, 0, 1/2) pattern of
``tests/_synthetic_crsbr.py`` (λ 2.449 Å; the magnetic (0 0 1) of the a,b,2c
child at 8.9°, the first nuclear line, (0 0 2), at 17.8°):

- **positive**: the truth is drawn with S/L = H/L = 0.03 and fitted with the
  asymmetry at 0.  The lowest line's shift is negative (the observed line
  sits low) by many esds.
- **null, same geometry**: no asymmetry in the truth or the model.  The finding
  still fires, because what fires it is the geometry, and the shift is inside
  three esds of zero.  This is the arm that fails if the shift were biased.
- **silent**: the same pattern fitted from 12°, above the magnetic line, so
  the lowest seen line is nuclear; and the paramagnetic pattern fitted with no
  magnetic component at all.
- **zero moments, Le Bail and Pawley** (Yue's review of #1493, before-merge
  item 1): the positive arm's truth fitted with every moment at 0.  The
  intensity is extracted anyway, so the magnetic (0 0 1) is still seen, and
  it must still read as magnetic-only and fire.
- **apertures refined** (the same review's item 3, finished): S/L and H/L
  freed in a second stage, and a tied pair freed on a truth with none, which
  ends on the bound at 0.

The real-data case (Ba₂FeSbSe₅ on G4.1 at 1.5 K) is asserted beside its
fixture, in ``tests/test_magnetic_series.py``.  PNGs of the lowest lines go to
``tests/output/`` (gitignored), stems ``low_angle_asymmetry_*``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
import rietx.report.magnetic as M
from rietx.report.magnetic import _line_shifts
from rietx.strategy.staged import PLAN_PRESETS
from tests import _synthetic_crsbr as G

pytestmark = pytest.mark.xdist_group("low-angle-asymmetry")

CODE = "LOW_ANGLE_ASYMMETRY_UNCALIBRATED"
SEED = 2056
ASYMMETRY = 0.03


def _truth(asymmetry: float) -> rx.PatternData:
    ins = G.instrument()
    ins.geometry.axial_sl.value = ins.geometry.axial_hl.value = asymmetry
    ref = rx.Refinement(rx.Structure(phases=[G.child_phase()]), ins)
    mean = np.asarray(ref.predict(G.blank()), dtype=float)
    counts = np.random.default_rng(SEED).poisson(mean).astype(float)
    return rx.PatternData(two_theta=G.TWO_THETA.tolist(), intensity=counts.tolist(),
                          sigma=np.sqrt(np.maximum(counts, 1.0)).tolist())


def _fit(data, limits=None, aperture=0.0, free_apertures=None):
    """``free_apertures``: ``"both"`` frees S/L and H/L in a second stage,
    ``"tied"`` ties H/L to S/L and frees S/L alone."""
    ins = G.instrument()
    ins.geometry.axial_sl.value = ins.geometry.axial_hl.value = aperture
    ref = rx.Refinement(G.start_structure(), ins)
    G.apply_ties(ref)
    first = PLAN_PRESETS["magnetic_width"]().stages[0]
    stages = [first]
    if free_apertures is not None:
        extra = ["instrument.geometry.axial_sl"]
        if free_apertures == "tied":
            ref.tie("instrument.geometry.axial_hl", "instrument.geometry.axial_sl")
        else:
            extra.append("instrument.geometry.axial_hl")
        stages.append(rx.Stage("asymmetry", list(first.turn_on) + extra))
    res = ref.fit(data, plan=rx.RefinementPlan(stages=stages),
                  two_theta_limits=limits)
    return ref, res


def _fit_zero_moments(data, mode):
    """Every moment at 0, fitted in ``mode`` with background, U and W free."""
    st = G.start_structure()
    for atom in st.phases[0].atoms:
        if atom.moment is not None:
            for ax in ("crystalaxis_x", "crystalaxis_y", "crystalaxis_z"):
                getattr(atom.moment, ax).value = 0.0
    ref = rx.Refinement(st, G.instrument())
    G.apply_ties(ref)
    res = ref.fit(data, mode=mode, plan=rx.RefinementPlan(stages=[rx.Stage(
        mode, ["instrument.background.c*", "instrument.profile.u",
               "instrument.profile.w"])]))
    return ref, res


def _lowest(ref):
    """The lowest seen line's (position, shift, esd), read the way the finding reads it."""
    model, values = ref._model, ref._answer["values"]
    r = np.asarray(model.y_obs) - np.asarray(model.evaluate(values))
    _, pos, _, frac, shift, esd, _ = _line_shifts(model, values, r,
                                                 np.asarray(model.sigma))[0]
    return pos, frac, shift, esd


def _draw(res, stem):
    from rietx.viz.plots import plot_result

    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    plot_result(res, path=str(out / f"low_angle_asymmetry_{stem}.png"),
                two_theta_range=(6.0, 20.0))


@pytest.fixture(scope="module")
def arms():
    out = {"positive": _fit(_truth(ASYMMETRY)), "null": _fit(_truth(0.0))}
    out["set"] = _fit(_truth(ASYMMETRY), aperture=ASYMMETRY)
    out["above"] = _fit(_truth(ASYMMETRY), limits=(12.0, 130.0))
    out["refined"] = _fit(_truth(ASYMMETRY), aperture=0.01, free_apertures="both")
    out["refined_to_zero"] = _fit(_truth(0.0), aperture=0.01, free_apertures="tied")
    for mode in ("lebail", "pawley"):
        out[f"{mode}_zero_moments"] = _fit_zero_moments(_truth(ASYMMETRY), mode)
    nuc = rx.Refinement(rx.Structure(phases=[G.nuclear_phase()]), G.instrument())
    out["paramagnetic"] = (nuc, nuc.fit(G.pattern("paramagnetic"), plan=rx.RefinementPlan(
        stages=[rx.Stage("nuclear", ["phases.*.scale", "instrument.background.c*"])])))
    for stem in ("positive", "null"):
        _draw(out[stem][1], stem)
    return out


def _findings(res):
    return [d for d in res.diagnostics if d.code == CODE]


def test_an_asymmetry_the_model_lacks_shows_as_a_negative_shift_at_the_magnetic_line(arms):
    ref, res = arms["positive"]
    pos, frac, shift, esd = _lowest(ref)
    assert pos == pytest.approx(8.9, abs=0.1) and frac == pytest.approx(1.0)
    assert shift < -3.0 * esd, (shift, esd)
    (d,) = _findings(res)
    assert d.level == "info"
    assert d.value == pytest.approx(shift)
    assert d.where == ["instrument.geometry.axial_sl", "instrument.geometry.axial_hl"]
    assert "(0 0 1) " in d.message and "1 magnetic-only line of phase 0 does" in d.message
    assert "not determinable from this sample's nuclear lines" in d.message
    assert "held at 0" in d.message and "predicts" in d.message


def test_the_message_names_a_position_shift_and_not_a_centroid(arms):
    """Yue's review of #1493: the number is the best-fit rigid shift of the drawn
    profile, which on an asymmetric line is not the obs - calc centroid."""
    (d,) = _findings(arms["positive"][1])
    assert "position shift" in d.message
    assert "centroid" not in d.message.lower()


def test_the_suggestion_follows_whether_an_asymmetry_is_already_drawn(arms):
    """Held at 0, nothing was set and the first advice is to take it from a
    standard; with the apertures set the finding cannot know where they came
    from, so it must not call them uncalibrated or tell the reader to take
    them from a standard as if none were.  Fails on the one-text suggestion."""
    (held,) = _findings(arms["positive"][1])
    (given,) = _findings(arms["set"][1])
    assert "held at 0" in held.message
    assert held.suggestion.startswith("Take the axial asymmetry from a standard")
    assert "held at S/L 0.03, H/L 0.03" in given.message
    assert not given.suggestion.startswith("Take the axial asymmetry")
    assert "already drawn" in given.suggestion
    # the numbers are the same finding's: with the asymmetry set, the lowest
    # line sits within three esds of the drawn one
    assert abs(given.value) < 3.0 * _lowest(arms["set"][0])[3]


def _derivative_error(arms, step):
    """Largest relative gap between the position derivative at ``step`` and at a
    10x smaller one, over every line of the fit with the axial apertures live."""
    ref, _ = arms["set"]
    model, values = ref._model, ref._answer["values"]
    sigma = np.asarray(model.sigma, dtype=float)
    old = M._SHIFT_STEP_FWHM
    try:
        M._SHIFT_STEP_FWHM = step / 10.0
        fine = M._phase_lines(model, values, 0, sigma)
        M._SHIFT_STEP_FWHM = step
        coarse = M._phase_lines(model, values, 0, sigma)
    finally:
        M._SHIFT_STEP_FWHM = old
    assert len(fine) == len(coarse) > 10
    return max(float(np.max(np.abs(a["dy"] - b["dy"])) / np.max(np.abs(b["dy"])))
               for a, b in zip(coarse, fine))


def test_the_derivative_step_is_converged_to_a_millionth_with_the_asymmetry_live(arms):
    """Yue's review of #1493: ``_SHIFT_STEP_FWHM`` earns tier 1 by a stated bar.
    With S/L = H/L = 0.03 (the Finger-Cox-Jephcoat tail live) the column at the
    shipped 1e-4 differs from the one at 1e-5 by less than 1e-6 of its peak on
    every line (measured about 6e-8).  The positive arm: a step of 1e-3 misses the
    same bar (about 2e-6), so the test can fail."""
    assert ASYMMETRY > 0.0
    assert _derivative_error(arms, M._SHIFT_STEP_FWHM) < 1e-6
    assert _derivative_error(arms, 1e-3) > 1e-6


def test_with_no_asymmetry_anywhere_the_geometry_still_fires_and_the_shift_is_noise(arms):
    ref, res = arms["null"]
    pos, _, shift, esd = _lowest(ref)
    assert pos == pytest.approx(8.9, abs=0.1)
    assert abs(shift) < 3.0 * esd, (shift, esd)
    (d,) = _findings(res)
    assert d.value == pytest.approx(shift)


def test_a_nuclear_lowest_line_and_a_pattern_with_no_moment_are_silent(arms):
    ref, res = arms["above"]
    pos, frac, _, _ = _lowest(ref)
    assert pos > 12.0 and frac < 0.05
    assert not _findings(res)
    assert not _findings(arms["paramagnetic"][1])


def test_apertures_refined_in_this_fit_are_named_refined_and_not_held(arms):
    """Our pre-review of #1493: the item-3 branch read the apertures' values,
    not whether the fit moved them.  Freed and refined to the truth's 0.03,
    the suggestion said it "cannot tell whether" they were refined on these
    lines; freed and ended on the bound, the message said "held at 0".  Both
    arms fail on the value-only branch."""
    (refined,) = _findings(arms["refined"][1])
    ref = arms["refined"][0]
    geo = ref.instrument.geometry
    assert geo.axial_sl.value == pytest.approx(ASYMMETRY, abs=0.005)
    assert geo.axial_hl.value == pytest.approx(ASYMMETRY, abs=0.005)
    # the text is checked against the values the fit returned, not a literal:
    # where the solver stops inside the 0.005 band moves with the platform
    # (Yue's review of #1493, before-merge item 1: Linux ended at S/L 0.02841)
    assert f"S/L was refined to {geo.axial_sl.value:.4g}" in refined.message
    assert f"H/L was refined to {geo.axial_hl.value:.4g}" in refined.message
    assert "held" not in refined.message
    assert refined.suggestion.startswith("The axial asymmetry was refined in this fit")
    assert "cannot tell" not in refined.suggestion
    (zero,) = _findings(arms["refined_to_zero"][1])
    geo = arms["refined_to_zero"][0].instrument.geometry
    assert geo.axial_sl.value == 0.0 and geo.axial_hl.value == 0.0
    # H/L is tied to S/L, so it moved with it: refined, not held
    assert "S/L was refined to 0 and H/L was refined to 0" in zero.message
    assert "held at 0" not in zero.message
    assert zero.suggestion.startswith("The axial asymmetry was refined in this fit")


@pytest.mark.parametrize("mode", ["lebail", "pawley"])
def test_a_magnetic_only_line_stays_magnetic_at_zero_moments(arms, mode):
    """Yue's review of #1493, before-merge item 1: with every moment at 0 the
    fraction read at the current moments was 0/0, taken as 0, so in a Le Bail
    fit the magnetic (0 0 1), whose intensity is extracted anyway, passed the
    nuclear-only cut and silenced the finding.  The stated group's
    anti-centring says the row has no nuclear structure factor whatever the
    moments.  Fails on the moment-read fraction (frac 0.000, silent)."""
    ref, res = arms[f"{mode}_zero_moments"]
    assert all(v == 0.0 for k, v in ref._answer["values"].items()
               if ".moment.dof" in k)
    pos, frac, shift, esd = _lowest(ref)
    assert pos == pytest.approx(8.9, abs=0.1)
    assert frac == 1.0
    assert shift < -3.0 * esd, (shift, esd)
    (d,) = _findings(res)
    assert "at 8.88 deg (0 0 1)" in d.message and d.value == pytest.approx(shift)


@pytest.mark.parametrize("mode", ["lebail", "pawley"])
def test_the_tick_rows_agree_with_the_finding_at_zero_moments(arms, mode):
    """Yue's review of #1493, before-merge item 3: the tick builder had its own
    0/0 fraction, so at zero moments the magnetic (0 0 1) drew on the nuclear
    tick row while the finding called it magnetic-only.  Both now read
    ``_magnetic_fraction``.  Fails on the tick builder's own fraction (the
    8.88 deg tick is on the nuclear row)."""
    _, res = arms[f"{mode}_zero_moments"]
    (nuc_key,) = [k for k in res.ticks if not k.endswith("(magnetic)")]
    mag = np.asarray(res.ticks[f"{nuc_key} (magnetic)"], dtype=float)
    nuc = np.asarray(res.ticks[nuc_key], dtype=float)
    assert np.any(np.abs(mag - 8.88) < 0.1), mag[:5]
    assert not np.any(np.abs(nuc - 8.88) < 0.1), nuc[:5]


def test_the_anti_centring_rows_are_the_odd_l_rows_of_the_child():
    """The a,b,2c child's anti-centring {1 | 0 0 1/2}' leaves no nuclear
    structure factor on odd l, and only there: the exact test, no tolerance."""
    from rietx.crystallography.magnetic.scattering import anti_centring_absences

    group = G.child_phase().magnetic_symmetry.group()
    hkl = np.array([[0, 0, 1], [0, 0, 2], [0, 1, 1], [1, 1, 0], [1, 0, 3],
                    [0, 2, 4], [-1, 2, -5]])
    assert anti_centring_absences(group, hkl).tolist() == [
        True, False, True, False, True, False, True]
    # a group with no anti-centring forbids nothing this way
    plain = rx.Structure(phases=[G.parent()]).phases[0]
    assert plain.magnetic_symmetry is None or not anti_centring_absences(
        plain.magnetic_symmetry.group(), hkl).any()
