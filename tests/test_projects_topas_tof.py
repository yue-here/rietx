"""Time-of-flight datasets in a TOPAS ``.inp`` (``io/projects/topas_tof.py``).

Every fixture is written inline from the Technical Reference's grammar and the
laws measured against TOPAS v6 (``tests/data/README.md`` § TOPAS time of
flight); no archive file and no archive number is used. Each law test states
the measurement it pins, so a change that breaks one names which.
"""

import math
import re
from pathlib import Path

import numpy as np
import pytest

from rietx.io.projects import topas_tof as TT
from rietx.io.projects.topas import TopasInpError, read_topas_inp, to_structure
from rietx.model.profiles.pseudovoigt import tch_gamma_eta
from rietx.schemas import Parameter
from rietx.schemas.instrument import (
    BackgroundChebyshev,
    IncidentSpectrum,
    Instrument,
    ProfileTOF,
)
from rietx.schemas.structure import Atom, Cell, Phase, Structure

LN1000 = math.log(1000.0)


def _inp(directory: Path, text: str, name: str = "tof.inp") -> Path:
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return path


#: One phase, written the way `str` blocks are; its profile lines are added
#: per test, so what reads is attributable to the line that was added.
_PHASE = ('  str\n    phase_name "P"\n    space_group "P m -3 m"\n'
          '    a 4.0 b 4.0 c 4.0 al 90 be 90 ga 90\n    scale @ 0.001\n'
          '    site A1 x 0 y 0 z 0 occ Ni 1 beq 0.5\n')
_HEAD = ('xdd "bank.xye"\n  neutron_data\n  TOF_LAM(0.001)\n'
         '  start_X 5000 finish_X 30000\n'
         '  TOF_x_axis_calibration(!t0, 7.5, t1, 10000, !t2, -3.25)\n'
         '  scale_pks = D_spacing^4;\n')
#: A whole representable shape: TOF_PV for the widths, one TOF_Exponential
#: per side in the two laws rietx's α and β follow.
_SHAPE = ('    TOF_PV(@, 50, @, 0.3, t1)\n'
          '    TOF_Exponential(!a0, 20, !a1, 4, 1, t1, -)\n'
          '    TOF_Exponential(!b0, 2, !b1, 0.5, 4, t1, +)\n')


def _bank(tmp_path, head=_HEAD, phase=_PHASE + _SHAPE):
    model = read_topas_inp(_inp(tmp_path, head + phase))
    return model, model.tof_banks[0]


# ------------------------------------------------------------ the equations

@pytest.mark.parametrize("expr, value", [
    ("6 / 2 3", 9.0),            # juxtaposition is `*`, same rank, left to right
    ("8 / 2 Sqrt(4)", 8.0),
    ("2 ^ 3 2", 16.0),           # `^` binds tighter than juxtaposition
    ("2 3 ^ 2", 18.0),
    ("-2^2", -4.0),              # unary minus below `^`
    ("2^3^2", 512.0),            # `^` is right-associative
    ("12 / 2 / 3", 2.0),
    ("2 (3 + 1)", 8.0),
    ("-Ln(0.001) / 2", LN1000 / 2),
])
def test_an_equation_evaluates_as_topas_evaluates_it(expr, value):
    """Each value is TOPAS v6's own `: value` write-back for the same text."""
    law, why = TT._law(expr, {})
    assert why is None and law(1.0) == pytest.approx(value, rel=1e-14)


def test_an_unknown_name_is_unreadable_rather_than_zero():
    law, why = TT._law("a + D_spacing", {})
    assert law is None and "`a`" in why


# ----------------------------------------------------------- what is mapped

def test_tof_x_axis_calibration_is_tzero_difc_difa_with_its_flags(tmp_path):
    """Measured: `Xo = t0 + t1·d + t2·d²` exactly. A name is a refine flag."""
    _, bank = _bank(tmp_path)
    cal = {k: (p.value, p.vary) for k, p in bank.calibration.items()}
    assert cal == {"tzero": (7.5, False), "difc": (10000.0, True),
                   "difa": (-3.25, False), "difb": (0.0, False)}


def test_pk_xo_in_an_argument_free_macro_is_the_calibration(tmp_path):
    """The archive's form: `pk_xo` written inside a user macro the bank
    invokes. The values come from the declarations, as do the flags."""
    head = ('macro tof_axis { pk_xo = zero + difc D_spacing + difa D_spacing^2; }\n'
            'xdd "bank.xye"\n  neutron_data\n  TOF_LAM(0.001)\n'
            '  local !zero 3 local difc 9000 local !difa 1.5\n'
            '  tof_axis\n  scale_pks = D_spacing^4;\n')
    _, bank = _bank(tmp_path, head=head, phase=_PHASE + _SHAPE.replace("t1", "difc"))
    cal = {k: (p.value, p.vary) for k, p in bank.calibration.items()}
    assert cal == {"tzero": (3.0, False), "difc": (9000.0, True),
                   "difa": (1.5, False), "difb": (0.0, False)}


def test_tof_pv_is_a_tch_pair_that_reproduces_its_fwhm_and_eta(tmp_path):
    """Measured: TOF_PV(fw, F, lor, η, t1) is a pseudo-Voigt of FWHM
    10⁻⁵·F·t1·d and fraction η. The imported σ² and γ must give exactly that
    back through rietx's own TCH blend, at every d."""
    _, bank = _bank(tmp_path)
    p = {k: v.value for k, v in bank.profile.items()}
    for d in (0.4, 1.0, 2.5, 6.0):
        sig2 = p["sig0"] + p["sig1"] * d ** 2 + p["sig2"] * d ** 4
        gam = p["gam0"] + p["gam1"] * d + p["gam2"] * d ** 2
        fwhm, eta = tch_gamma_eta(np.array(math.sqrt(8 * math.log(2) * sig2)),
                                  np.array(gam))
        assert float(fwhm) == pytest.approx(1e-5 * 50 * 10000 * d, rel=1e-9)
        assert float(eta) == pytest.approx(0.3, rel=1e-9)


def test_tof_exponential_is_alpha_on_the_early_side_and_beta_on_the_late(tmp_path):
    """Measured: rate = ln(1000)·(a0 + a1/d^w)/t1, `−` early, `+` late. So
    w = 1 on `−` is α₀ + α₁/d and w = 4 on `+` is β₀ + β₁/d⁴."""
    _, bank = _bank(tmp_path)
    p = {k: v.value for k, v in bank.profile.items()}
    assert p["alpha0"] == pytest.approx(LN1000 * 20 / 10000, rel=1e-12)
    assert p["alpha1"] == pytest.approx(LN1000 * 4 / 10000, rel=1e-12)
    assert p["beta0"] == pytest.approx(LN1000 * 2 / 10000, rel=1e-12)
    assert p["beta1"] == pytest.approx(LN1000 * 0.5 / 10000, rel=1e-12)
    assert not bank.refused


def test_exp_conv_const_is_a_rate_by_its_sign(tmp_path):
    """Measured: `exp_conv_const c` decays at −ln(0.001)/c, late for c > 0."""
    shape = ('    peak_type pv pv_lor 0 pv_fwhm = 3 D_spacing;\n'
             '    exp_conv_const = Ln(0.001) / (0.1 + 0.4 / D_spacing);\n'
             '    exp_conv_const = -Ln(0.001) / (0.03 + 0.002 / D_spacing^4);\n')
    _, bank = _bank(tmp_path, phase=_PHASE + shape)
    p = {k: v.value for k, v in bank.profile.items()}
    assert (p["alpha0"], p["alpha1"]) == pytest.approx((0.1, 0.4), rel=1e-12)
    assert (p["beta0"], p["beta1"]) == pytest.approx((0.03, 0.002), rel=1e-12)
    assert p["sig1"] == pytest.approx(9 / (8 * math.log(2)), rel=1e-12)
    assert p["gam1"] == 0.0


def test_the_range_the_background_and_tof_lam_are_read(tmp_path):
    head = _HEAD + "  bkg @ 10 -2 0.5\n  extra_X_left 40\n"
    _, bank = _bank(tmp_path, head=head)
    assert (bank.start_x, bank.finish_x, bank.tof_lam) == (5000.0, 30000.0, 0.001)
    assert [(c.value, c.vary) for c in bank.background] == [
        (10.0, True), (-2.0, True), (0.5, True)]
    assert bank.extra_x == (40.0, 0.5)


# ----------------------------------------------------- what is refused, why

@pytest.mark.parametrize("change, construct", [
    # a stack that is not push/one/bring/one/add-pop is another shape
    (lambda s: s.replace("    TOF_Exponential(!b0", "    push_peak\n    TOF_Exponential(!b0"),
     "peak stack"),
    (lambda s: s + "    user_defined_convolution = X; min 0 max 1\n", "user_defined_convolution"),
    (lambda s: s + "    hat = 2;\n", "hat"),
    (lambda s: s + "    TOF_Exponential(!c0, 9, !c1, 0, 4, t1, +)\n", "late-side exponential"),
    (lambda s: s.replace("    TOF_Exponential(!a0, 20, !a1, 4, 1, t1, -)\n", ""),
     "early-side exponential"),
    (lambda s: s.replace("4, 1, t1, -)", "4, 4, t1, -)"), "early-side exponential"),
    (lambda s: s + "    peak_type fp\n", "peak_type fp"),
    (lambda s: s + "    more_accurate_Voigt\n", "more_accurate_Voigt"),
    (lambda s: s + "    TOF_CS_L(@, 100, t1)\n", "TOF_CS_L"),
    (lambda s: s.replace("site A1 x 0 y 0 z 0 occ Ni 1 beq 0.5",
                         "site A1 x 0 y 0 z 0 occ Ni 1 beq 0.5 mlx 1"), "mlx"),
])
def test_what_rietx_cannot_carry_is_refused_by_name(tmp_path, change, construct):
    """Each is a different function, not a nearby one, so it is refused rather
    than approximated — and named, so the caller knows which."""
    model, bank = _bank(tmp_path, phase=change(_PHASE + _SHAPE))
    assert construct in [c for c, _ in bank.refused]
    with pytest.raises(TopasInpError, match=re.escape(construct)):
        TT.to_tof_refinement(model, dataset=0, two_theta_bank_deg=90.0)


#: The beamline ``GSAS_btb`` form of the same two exponentials: a peak stack,
#: one per member, nothing weighted.
_STACK = ('    TOF_PV(@, 50, @, 0.3, t1)\n'
          '    push_peak\n'
          '    TOF_Exponential(!a0, 20, !a1, 4, 1, t1, -)\n'
          '    bring_2nd_peak_to_top\n'
          '    TOF_Exponential(!b0, 2, !b1, 0.5, 4, t1, +)\n'
          '    add_pop_1st_2nd_peak\n')


def test_the_unweighted_peak_stack_is_the_back_to_back_pair(tmp_path):
    """Measured against TOPAS v6 (``tests/data/tof/topas_stack/``): the
    un-weighted stack is the same pulse as the two exponentials in series, so
    it reads to the same profile and builds, refusing nothing."""
    model, stack = _bank(tmp_path, phase=_PHASE + _STACK)
    (tmp_path / "series").mkdir()
    _, series = _bank(tmp_path / "series")
    assert stack.refused == []
    assert {k: v.value for k, v in stack.profile.items()} == pytest.approx(
        {k: v.value for k, v in series.profile.items()}, rel=1e-15)
    assert stack.sources["peak stack"].startswith("push_peak")
    TT.to_tof_refinement(model, dataset=0, two_theta_bank_deg=90.0)


@pytest.mark.parametrize("weight", ["    scale_top_peak 3\n",
                                    "    set_top_peak_area 0.5\n"])
def test_a_weighted_peak_stack_is_refused_as_a_different_kind(tmp_path, weight):
    """The positive arm: the same stack with one member weighted is a pair with
    a step at the junction (TOPAS's ``scale_top_peak 3`` moves the peak 0.14 of
    its maximum off the pulse, measured), so it is refused by name."""
    phase = _PHASE + _STACK.replace("    add_pop_1st_2nd_peak\n",
                                    weight + "    add_pop_1st_2nd_peak\n")
    model, bank = _bank(tmp_path, phase=phase)
    kw = weight.split()[0]
    assert [c for c, _ in bank.refused] == [kw]
    assert "different kind" in dict(bank.refused)[kw]
    with pytest.raises(TopasInpError, match=kw):
        TT.to_tof_refinement(model, dataset=0, two_theta_bank_deg=90.0)


def test_no_refusal_says_a_stack_is_a_sum_of_two_pulses(tmp_path):
    """The old refusal's reason was wrong (Von Dreele, Jorgensen & Windsor 1982
    eq. 10 *is* the weighted sum) and is gone from the module."""
    import inspect

    assert "sum of two" not in inspect.getsource(TT)


@pytest.mark.parametrize("scale, construct", [
    ("  scale_pks = D_spacing^pow;\n", "scale_pks = D_spacing^pow"),
    ("  scale_pks = Exp(-0.1 D_spacing);\n", "scale_pks = Exp(-0.1 D_spacing)"),
    ("", "scale_pks = D_spacing^4"),        # absent: TOPAS's intensity then has no d⁴
])
def test_a_scale_other_than_d4_is_refused(tmp_path, scale, construct):
    head = _HEAD.replace("  scale_pks = D_spacing^4;\n", scale)
    _, bank = _bank(tmp_path, head=head)
    assert construct in [c for c, _ in bank.refused]


def test_a_calibration_that_is_not_the_four_term_relation_is_refused(tmp_path):
    head = _HEAD.replace("  TOF_x_axis_calibration(!t0, 7.5, t1, 10000, !t2, -3.25)\n",
                         "  local t1 10000\n  pk_xo = t1 D_spacing + 2 D_spacing^3;\n")
    _, bank = _bank(tmp_path, head=head)
    assert "pk_xo" in [c for c, _ in bank.refused]


def test_a_macro_with_arguments_stating_the_shape_is_refused(tmp_path):
    head = ("macro shape(c, v) { prm c v exp_conv_const = c; }\n" + _HEAD)
    phase = _PHASE + _SHAPE + "    shape(!s0, 5)\n"
    _, bank = _bank(tmp_path, head=head, phase=phase)
    assert "macro shape(…)" in [c for c, _ in bank.refused]


def test_phases_of_one_bank_stating_different_shapes_are_refused(tmp_path):
    other = (_PHASE.replace('"P"', '"Q"')
             + _SHAPE.replace("TOF_PV(@, 50", "TOF_PV(@, 60"))
    _, bank = _bank(tmp_path, phase=_PHASE + _SHAPE + other)
    assert "per-phase profile" in [c for c, _ in bank.refused]


def test_to_structure_still_refuses_a_time_of_flight_dataset(tmp_path):
    """The structure of a bank is built through `to_tof_refinement`, which
    converts its scale; `to_structure` says so instead of building it."""
    model, _ = _bank(tmp_path)
    with pytest.raises(TopasInpError, match="to_tof_refinement"):
        to_structure(model)


# ---------------------------------------------------------------- building

def test_the_scale_is_converted_by_the_measured_factor(tmp_path):
    """Measured: TOPAS's reflection intensity is rietx's × 0.01/sin θ_bank at
    one scale, so S_rietx = S_TOPAS · 0.01 / sin θ_bank."""
    model, _ = _bank(tmp_path)
    st, ins = TT.to_tof_refinement(model, dataset=0, two_theta_bank_deg=60.0)
    assert st.phases[0].scale.value == pytest.approx(
        0.001 * 0.01 / math.sin(math.radians(30.0)), rel=1e-15)
    assert ins.source.two_theta_bank_deg == 60.0
    assert ins.source.difc.vary and not ins.source.tzero.vary


def test_a_bank_with_refusals_does_not_build(tmp_path):
    model, _ = _bank(tmp_path, phase=_PHASE + _SHAPE + "    hat = 2;\n")
    with pytest.raises(TopasInpError, match="refused rather than approximated"):
        TT.to_tof_refinement(model, dataset=0, two_theta_bank_deg=90.0)


# ----------------------------------------------------------------- writing

def _model(gam=(0.5, 1.2, 0.3), difb=0.0, vary=False):
    P = lambda v, free=False: Parameter(value=float(v), vary=free)  # noqa: E731
    st = Structure(phases=[Phase(
        name="NiO", space_group="Fm-3m",
        cell=Cell(a=P(4.177, True), b=P(4.177), c=P(4.177), alpha=P(90),
                  beta=P(90), gamma=P(90)),
        atoms=[Atom(label="Ni1", species="Ni", x=P(0), y=P(0), z=P(0), occ=P(1),
                    biso=P(0.5, True)),
               Atom(label="O1", species="O", x=P(0.5), y=P(0.5), z=P(0.5),
                    occ=P(1), biso=P(0.7))],
        scale=P(2.5, True))])
    prof = ProfileTOF(alpha0=P(0.1, vary), alpha1=0.45, beta0=0.03,
                      beta1=P(0.004, vary), sig0=2.0, sig1=40.0, sig2=1.5,
                      gam0=gam[0], gam1=gam[1], gam2=gam[2])
    ins = Instrument.tof_neutron_bank(10000.0, two_theta_bank_deg=90.0,
                                      difa=-3.25, tzero=7.5, difb=difb,
                                      profile=prof)
    return st, ins.model_copy(update={"background": BackgroundChebyshev(
        coefficients=[P(10.0), P(-2.0), P(0.5)])})


@pytest.mark.parametrize("gam, difb, vary", [
    ((0.5, 1.2, 0.3), 0.0, False),      # profile type 3
    ((0.0, 0.0, 0.0), 0.0, True),       # type 1, two coefficients free
    ((0.5, 1.2, 0.3), 25.0, False),     # DIFB: the hand-written pk_xo path
])
def test_a_written_bank_reads_back_identical(tmp_path, gam, difb, vary):
    """rietx → `.inp` → rietx: every value and flag the writer states comes
    back bit for bit (and TOPAS computes it to its own truncation floor —
    measured, not asserted here)."""
    st, ins = _model(gam, difb, vary)
    text = TT.from_tof(st, ins, data_file="bank.xye", x_range=(5000.0, 30000.0))
    model = read_topas_inp(_inp(tmp_path, text))
    st2, ins2 = TT.to_tof_refinement(model, dataset=0, two_theta_bank_deg=90.0)
    for key in ("difc", "difa", "tzero", "difb"):
        a, b = getattr(ins.source, key), getattr(ins2.source, key)
        assert (a.value, a.vary) == (b.value, b.vary), key
    for key in ProfileTOF.model_fields:
        a, b = getattr(ins.source.profile_tof, key), getattr(ins2.source.profile_tof, key)
        assert (a.value, a.vary) == (b.value, b.vary), key
    assert [c.value for c in ins2.background.coefficients] == [10.0, -2.0, 0.5]
    assert st2.phases[0].scale.value == st.phases[0].scale.value
    assert [(at.x.value, at.biso.value, at.biso.vary) for at in st2.phases[0].atoms] == [
        (at.x.value, at.biso.value, at.biso.vary) for at in st.phases[0].atoms]


def test_the_writer_states_nothing_topas_refuses(tmp_path):
    """Two of TOPAS's own refusals, measured: `+ -c` is "Invalid equation",
    and a parameter declared twice stops the run. And never `fp` or `xo_Is`."""
    st, ins = _model()
    text = TT.from_tof(st, ins, data_file="bank.xye", x_range=(5000.0, 30000.0))
    assert not re.search(r"[-+]\s+-", text)
    names = re.findall(r"\bprm\s+[!@]?(\w+)", text) + re.findall(
        r"[!@](\w+)\s*,", text.split("TOF_x_axis_calibration(")[1].split(")")[0])
    assert len(names) == len(set(names))
    assert "peak_type pv" in text and "fp" not in text.split() and "xo_Is" not in text


def test_the_writer_names_the_extra_range_rietx_keeps(tmp_path):
    """TOPAS generates reflections only within extra_X of the range (default
    0.5); rietx keeps a peak whose window reaches in. Without this a peak just
    below start_X was missing on the TOPAS side (measured, 6e-3 of the max)."""
    st, ins = _model()
    text = TT.from_tof(st, ins, data_file="bank.xye", x_range=(5000.0, 30000.0))
    left = float(re.search(r"extra_X_left (\S+)", text)[1])
    beta = 0.03 + 0.004 / (ins.source.d_from_tof(5000.0)) ** 4
    assert left > -math.log(1e-4) / beta


@pytest.mark.parametrize("update, needle", [
    (lambda st, ins: (st, ins.model_copy(update={"source": ins.source.model_copy(
        update={"incident_spectrum": IncidentSpectrum(itype=1, coefficients=[Parameter(value=1.0)] * 11)})})),
     "incident spectrum"),
    (lambda st, ins: (st, ins.model_copy(update={"source": ins.source.model_copy(
        update={"profile_tof": ProfileTOF(alpha0=0.1, beta0=0.03)})})), "zero-width"),
    (lambda st, ins: (st, ins.model_copy(update={"background": BackgroundChebyshev(
        coefficients=[Parameter(value=1.0, vary=True), Parameter(value=0.0)])})),
     "one refine flag"),
])
def test_the_writer_refuses_what_it_cannot_state(update, needle):
    st, ins = update(*_model())
    with pytest.raises(ValueError, match=needle):
        TT.from_tof(st, ins, data_file="bank.xye", x_range=(5000.0, 30000.0))
