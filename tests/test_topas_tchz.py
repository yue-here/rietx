"""A TOPAS ``TCHZ_Peak_Type(…)`` profile and radius read into an ``Instrument``
(WP-1455, issue #732): ``topas.read_topas_inp`` then ``topas.to_instrument``.

Two kinds of evidence. What TOPAS **computes** from a TCHZ call is checked
against TOPAS-64 v6's own Y_calc at zero cycles for two inputs of ours
(``tests/data/topas_tchz_nacl_xray_run1[01]*``, the case of
``tests/topas_export_cases.py::case_nacl_xray`` with the profile written as a
TCHZ call): the profile this reader builds must reproduce it, and the reading
that follows the Technical Reference's printed signature must not. The slot-4
fold into U and W is algebra, so it is checked as an identity across the 2θ
axis, to 1e-12.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.io.projects import topas
from rietx.model.profiles.caglioti import gaussian_fwhm, lorentzian_fwhm
from tests.topas_export_cases import case_nacl_xray

DATA = Path(__file__).parent / "data"
#: As ``test_topas_whole_input.ORACLE_TOL``: TOPAS against rietx at zero
#: cycles, the largest |ΔY| over the largest Y. Measured 2.1e-3 (run 10) and
#: 2.5e-3 (run 11), the case's own floor (2.4e-3 with the pv equations).
ORACLE_TOL = 1e-2
RUN10 = (DATA / "topas_tchz_nacl_xray_run10.inp").read_text(encoding="utf-8")
TCHZ_LINE = re.compile(r"TCHZ_Peak_Type\([^)]*\)")


def _inp(tmp_path, text, name="case.inp"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return topas.read_topas_inp(path)


def _with_call(tmp_path, call, extra=""):
    """Run 10's input with its TCHZ call replaced, and ``extra`` cards added to
    the dataset."""
    text = TCHZ_LINE.sub(call, RUN10)
    if extra:
        text = text.replace("  convolution_step 3\n", f"  convolution_step 3\n{extra}\n")
    return _inp(tmp_path, text)


def _oracle(run, instrument):
    ref, _ = case_nacl_xray()
    x, y_topas = np.loadtxt(DATA / f"topas_tchz_nacl_xray_run{run}_ycalc.txt",
                            unpack=True)
    y = np.asarray(rx.Refinement(ref.fitted_structure, instrument,
                                 history=False).predict(x))
    return float(np.abs(y_topas - y).max() / y.max())


def _read(run):
    ref, _ = case_nacl_xray()
    model = topas.read_topas_inp(DATA / f"topas_tchz_nacl_xray_run{run}.inp")
    return model, topas.to_instrument(model, ref.fitted_instrument)


def _signature_reading(instrument, values):
    """The Technical Reference's printed ``(u, v, w, x, y, z)`` taken by
    position, with its formula's letters: slot 4 the tanθ Lorentzian, slot 5
    the 1/cosθ one, slot 6 the Z/cos²θ Gaussian. TOPAS 6 does not do this."""
    out = instrument.model_copy(deep=True)
    s1, s2, s3, s4, s5, s6 = values
    for name, value in dict(u=s1 + s6, v=s2, w=s3 + s6, y=s4, x=s5).items():
        param = getattr(out.profile, name)
        param.max = max(param.max, value + 1.0)
        param.value = value
    return out


@pytest.mark.parametrize("run", [10, 11])
def test_the_tchz_profile_is_what_topas_computes(run):
    """Slots 1-3 → U, V, W; slot 4 (Z/cos²θ) → U and W; slot 5 → Y (tanθ);
    slot 6 → X (1/cosθ), measured against TOPAS 6's own Y_calc. Run 11 swaps
    slots 4 and 5, so a reading that mixed them up passes at most one run."""
    model, inst = _read(run)
    err = _oracle(run, inst)
    assert err < ORACLE_TOL
    # positive arm: the printed signature's order is not what TOPAS computes
    arm = _oracle(run, _signature_reading(inst, model.tchz[0].values))
    assert arm > 4 * err          # measured 0.41 and 0.087 against 2.1e-3, 2.5e-3


def test_the_swap_arm_moves_the_answer():
    """Each run's own slots match its own Y_calc; run 10's slots do not match
    run 11's, so the comparison can see slots 4 and 5."""
    _, inst10 = _read(10)
    _, inst11 = _read(11)
    own = _oracle(11, inst11)
    assert _oracle(11, inst10) > 4 * own


def test_the_slots_map_by_position():
    model, inst = _read(10)
    (call,) = model.tchz
    assert call.phase == "NaCl"
    assert call.values == (0.004, -0.002, 0.003, 0.03, 0.008, 0.0015)
    assert call.vary == (False,) * 6
    got = {k: getattr(inst.profile, k).value for k in "uvwxy"}
    assert got == pytest.approx(dict(u=0.034, v=-0.002, w=0.033, x=0.0015, y=0.008),
                                rel=0, abs=1e-15)
    assert not any(getattr(inst.profile, k).vary for k in "uvwxy")
    # the names are user labels: renaming the pairs moves nothing
    assert topas.tchz_widths(call.values) == pytest.approx(got, abs=1e-15)


def test_names_are_labels_and_flags_are_read(tmp_path):
    model = _with_call(tmp_path, "TCHZ_Peak_Type(pkz, 0.004, @, -0.002, !pkw, 0.003, "
                                 "pkx, 0.03, pky, 0.008`_0.0001, pku, 0.0015)")
    (call,) = model.tchz
    assert call.values == (0.004, -0.002, 0.003, 0.03, 0.008, 0.0015)
    assert call.vary == (True, True, False, True, True, True)
    ref, _ = case_nacl_xray()
    inst = topas.to_instrument(model, ref.fitted_instrument)
    assert inst.profile.u.value == pytest.approx(0.034)
    assert inst.profile.x.value == pytest.approx(0.0015)
    assert not inst.profile.u.vary     # a calibration reads frozen


def test_a_slot_may_name_a_declared_parameter(tmp_path):
    text = TCHZ_LINE.sub("TCHZ_Peak_Type(!pku, u0, !pkv, -0.002, !pkw, 0.003, "
                         "!pkx, 0.03, !pky, 0.008, !pkz, 0.0015)", RUN10)
    text = text.replace("iters 0\n", "iters 0\nprm !u0 0.004\n")
    model = _inp(tmp_path, text)
    assert model.tchz[0].values[0] == pytest.approx(0.004)


def test_the_z_fold_is_exact(tmp_path):
    """Z/cos²θ = Z·tan²θ + Z: Γ_G and Γ_L by TOPAS's TCHZ formula and by
    rietx's Caglioti and Lorentzian laws agree across 5-150° 2θ."""
    s = (0.012, -0.007, 0.004, 0.0021, 0.013, 0.0042)
    model = _with_call(tmp_path, "TCHZ_Peak_Type(!a, {}, !b, {}, !c, {}, !d, {}, "
                                 "!e, {}, !f, {})".format(*s))
    ref, _ = case_nacl_xray()
    inst = topas.to_instrument(model, ref.fitted_instrument)
    p = inst.profile
    theta = np.linspace(5.0, 150.0, 2901) / 2.0
    t, c = np.tan(np.radians(theta)), np.cos(np.radians(theta))
    topas_g = np.sqrt(s[0] * t * t + s[1] * t + s[2] + s[3] / (c * c))
    topas_l = s[4] * t + s[5] / c
    rietx_g = gaussian_fwhm(theta, p.u.value, p.v.value, p.w.value)
    rietx_l = lorentzian_fwhm(theta, p.x.value, p.y.value)
    assert np.max(np.abs(rietx_g / topas_g - 1.0)) < 1e-12
    assert np.max(np.abs(rietx_l / topas_l - 1.0)) < 1e-12
    # positive arm: the same values with Z dropped are not the same widths
    dropped = gaussian_fwhm(theta, s[0], s[1], s[2])
    assert np.max(np.abs(dropped / topas_g - 1.0)) > 1e-3


def test_the_secondary_radius_is_read(tmp_path):
    ref, _ = case_nacl_xray()
    model = _inp(tmp_path, RUN10.replace("Rp 217.5 Rs 217.5", "Rp 217.5 Rs 200"))
    assert model.secondary_radii == [200.0]
    inst = topas.to_instrument(model, ref.fitted_instrument)
    assert inst.geometry.goniometer_radius_mm == 200.0
    model = _inp(tmp_path, RUN10.replace("Rp 217.5 Rs 217.5", "Radius(240)"))
    assert model.goniometer_radius_mm == 240.0
    # an equation using Rs is not a statement of it
    assert "/217.5;" in RUN10
    model = _inp(tmp_path, RUN10.replace("Rp 217.5 Rs 217.5", "").replace(
        "/217.5;", "/Rs;"))
    assert model.secondary_radii == [] and model.goniometer_radius_mm is None
    inst = topas.to_instrument(model, ref.fitted_instrument)
    assert (inst.geometry.goniometer_radius_mm
            == ref.fitted_instrument.geometry.goniometer_radius_mm)


@pytest.mark.parametrize("cards", ["Rs 200\n  Radius(217.5)", "Radius(217.5, 200)"])
def test_two_secondary_radii_are_refused(tmp_path, cards):
    ref, _ = case_nacl_xray()
    model = _inp(tmp_path, RUN10.replace("Rp 217.5 Rs 217.5", cards))
    assert model.goniometer_radius_mm is None
    with pytest.raises(ValueError, match="secondary radius two ways"):
        topas.to_instrument(model, ref.fitted_instrument)


@pytest.mark.parametrize("call, match", [
    ("TCHZ_Peak_Type(!a, 0.004, !b, -0.002, !c, 0.003, !d, 0.03, !e, 0.008)",
     "10 arguments"),
    ("TCHZ_Peak_Type(!a, 0.004, !b, -0.002, !c, 0.003, !d, -0.01, !e, 0.008, "
     "!f, 0.0015)", "W = slot 3 \\+ slot 4"),
    ("TCHZ_Peak_Type(!a, 0.004, !b, -0.002, !c, 0.003, !d, 0.0, !e, 0.008, "
     "!f, -0.001)", "X = slot 6"),
    ("TCHZ_Peak_Type(!a, 0.004, !b, -0.002, !c, 0.003, !d, 0.0, !e, -0.05, "
     "!f, 0.001)", "negative above 2θ"),
    ("TCHZ_Peak_Type(!a, 0.004, !b, -0.002, !c, 0.003, !d, 0.0, !e, nope, "
     "!f, 0.001)", "slot 5 value 'nope'"),
])
def test_a_profile_this_package_cannot_hold_is_refused(tmp_path, call, match):
    model = _with_call(tmp_path, call)
    # the structure import does not depend on the profile
    assert topas.to_structure(model).phases[0].name == "NaCl"
    ref, _ = case_nacl_xray()
    with pytest.raises(ValueError, match=match) as info:
        topas.to_instrument(model, ref.fitted_instrument)
    assert "case.inp" in str(info.value)


def test_no_call_is_refused(tmp_path):
    model = _with_call(tmp_path, "peak_type pv")
    ref, _ = case_nacl_xray()
    with pytest.raises(ValueError, match="states no TCHZ_Peak_Type"):
        topas.to_instrument(model, ref.fitted_instrument)


def test_two_phases_stating_two_profiles_need_a_choice(tmp_path):
    second = RUN10[RUN10.index("str\n"):].replace('"NaCl"', '"KCl"').replace(
        "!pkx, 0.03", "!pkx, 0.02")
    text = RUN10.replace("Out_X_Ycalc", "' Out_X_Ycalc") + second
    model = _inp(tmp_path, text)
    assert [c.phase for c in model.tchz] == ["NaCl", "KCl"]
    ref, _ = case_nacl_xray()
    with pytest.raises(ValueError, match="2 different profiles .*phase="):
        topas.to_instrument(model, ref.fitted_instrument)
    inst = topas.to_instrument(model, ref.fitted_instrument, phase="KCl")
    assert inst.profile.u.value == pytest.approx(0.004 + 0.02)
    with pytest.raises(ValueError, match="for phase 'LiF'"):
        topas.to_instrument(model, ref.fitted_instrument, phase="LiF")


def test_a_dataset_level_call_applies_to_every_phase(tmp_path):
    call = TCHZ_LINE.search(RUN10).group(0)
    text = RUN10.replace(f"  {call}\n", "").replace(
        "  convolution_step 3\n", f"  convolution_step 3\n  {call}\n")
    model = _inp(tmp_path, text)
    assert [c.phase for c in model.tchz] == [""]
    ref, _ = case_nacl_xray()
    inst = topas.to_instrument(model, ref.fitted_instrument, phase="NaCl")
    assert inst.profile.w.value == pytest.approx(0.033)


def test_each_profile_entry_names_its_topas_and_gsas2_equivalent():
    """The help entries carry the translation a session otherwise reads the
    source for: the TCHZ slot by position, the GSAS-II letter, and on U and W
    how TOPAS's Z folds in."""
    from rietx.help import PARAMETER_HELP

    slots = dict(u="first", v="second", w="third", x="sixth", y="fifth")
    for name, slot in slots.items():
        text = PARAMETER_HELP[f"instrument.profile.{name}"].description
        assert f"{slot} value of `TCHZ_Peak_Type`" in text, name
        assert f"In GSAS-II it is `{name.upper()}`" in text, name
    for name in ("u", "w"):
        assert "Z/cos²θ" in PARAMETER_HELP[f"instrument.profile.{name}"].description
    # the slots the entries name are the ones the reader maps
    for name, slot in slots.items():
        index = ["first", "second", "third", "fourth", "fifth", "sixth"].index(slot)
        assert name in topas.TCHZ_SLOT_TERMS[index]
