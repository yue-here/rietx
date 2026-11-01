"""``write_topas_inp(instrument=, pattern=)``: a whole TOPAS input (#732 item 1).

Two kinds of evidence. What the file states is checked against the model it
came from (each keyword, each number). What TOPAS **computes** from it is
checked against TOPAS-64 v6's own Y_calc at zero cycles for the same cases
(``tests/data/topas_export_*_ycalc.txt``, program output for inputs of ours,
``tests/topas_export_cases.py``): rietx's ``predict()`` must reproduce it, and a
positive arm with one term changed must not, so the comparison can see the
term it is about.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.background.models import pspline_penalty_scale, second_difference_matrix
from rietx.io.projects.topas_input import _bspline_pieces
from rietx.model.forward import WINDOW_AREA_TOL, compile_model
from rietx.params.vector import ParameterTable
from tests.topas_export_cases import case_nacl_neutron, case_nacl_pspline, case_nacl_xray

DATA = Path(__file__).parent / "data"
#: TOPAS against rietx at zero cycles, largest |ΔY| over the largest Y. Measured
#: 2.2e-3 (neutron), 2.4e-3 (X-ray), 3.3e-3 (P-spline and FCJ axial) at
#: predict()'s closing windows, which hold 99.9 % of each peak's area
#: (schemas.plan.CLOSING_WINDOW_TOL). At the declared stages' 98 % the three
#: are within 1 % of those, so the window tails are not what is left. TOPAS
#: also averages Y_calc over the data step.
ORACLE_TOL = 1e-2


def _oracle(name, ref):
    x, y_topas = np.loadtxt(DATA / f"topas_export_{name}_ycalc.txt", unpack=True)
    y = np.asarray(ref.predict(x))
    return x, y_topas, float(np.abs(y_topas - y).max() / y.max())


def _write(case, tmp_path, **kw):
    ref, pattern = case()
    path = tmp_path / "case.inp"
    rx.write_topas_inp(ref.fitted_structure, path, free=ref,
                       instrument=ref.fitted_instrument, pattern=pattern,
                       scale="topas", **kw)
    return ref, pattern, path.read_text(encoding="utf-8"), path


def test_the_whole_input_states_the_instrument_and_the_data(tmp_path):
    ref, pattern, text, path = _write(case_nacl_neutron, tmp_path)
    assert 'xdd "case.xye" xye_format' in text
    assert "weighting = 1 / SigmaYobs^2;" in text
    assert "neutron_data" in text and "LP_Factor(90)" in text
    assert "la 1.0 lo 1.594 lh 1e-06" in text
    assert "th2_offset ! 0.02" in text
    assert "bkg ! 300.0 -40.0 15.0 -5.0" in text
    assert "peak_type pv" in text and "pv_fwhm = " in text and "pv_lor = " in text
    assert re.search(r"convolution_step \d+", text)
    data = np.loadtxt(path.with_name("case.xye"))
    assert np.allclose(data[:, 0], pattern.tt()) and np.allclose(data[:, 2], pattern.sig())


def test_the_neutron_case_is_what_topas_computes():
    ref, _ = case_nacl_neutron()
    _, _, err = _oracle("nacl_neutron", ref)
    assert err < ORACLE_TOL
    # positive arm: without the extinction the file states, TOPAS is not matched
    s = ref.fitted_structure.model_copy(deep=True)
    s.phases[0].extinction.value = 0.0
    _, _, arm = _oracle("nacl_neutron", rx.Refinement(s, ref.fitted_instrument,
                                                      history=False))
    assert arm > 4 * err          # measured 1.07e-2 against 2.2e-3


def test_the_xray_case_is_what_topas_computes():
    """LP_Factor(0) for K = 0.5, the scale × K, a Kα doublet, and a specimen
    displacement written as rietx's own law in a th2_offset equation."""
    ref, _ = case_nacl_xray()
    _, _, err = _oracle("nacl_xray", ref)
    assert err < ORACLE_TOL
    inst = ref.fitted_instrument.model_copy(deep=True)
    inst.geometry.sample_displacement.value = -0.05      # the sign, reversed
    _, _, arm = _oracle("nacl_xray", rx.Refinement(ref.fitted_structure, inst,
                                                   history=False))
    assert arm > 2 * ORACLE_TOL
    # the dispersion the case declares is the setting TOPAS's Y_calc carries
    assert ref.fitted_instrument.source.dispersion is not None
    inst = ref.fitted_instrument.model_copy(deep=True)
    inst.source.dispersion = None
    _, _, off = _oracle("nacl_xray", rx.Refinement(ref.fitted_structure, inst,
                                                   history=False))
    assert off > 4 * err          # measured 4.4e-2 against 2.4e-3


def _xray_extinction(value):
    ref, pattern = case_nacl_xray()
    s = ref.fitted_structure.model_copy(deep=True)
    s.phases[0].extinction.value = value
    return rx.Refinement(s, ref.fitted_instrument, history=False), pattern


def test_an_xray_extinction_is_written_in_electrons_squared(tmp_path):
    """TOPAS's X-ray ``A01^2 + B01^2 + A11^2 + B11^2`` is rietx's |F|² (factor
    1, where the neutron term has 100), measured against TOPAS 6's zero-cycle
    Y_calc of this case at extinction 20 (``topas_export_nacl_xray_ext20``)."""
    ref, pattern = _xray_extinction(20.0)
    rx.write_topas_inp(ref.fitted_structure, tmp_path / "x.inp", free=ref,
                       instrument=ref.fitted_instrument, pattern=pattern,
                       scale="topas")
    text = (tmp_path / "x.inp").read_text(encoding="utf-8")
    (line,) = [ln for ln in text.splitlines() if "scale_pks" in ln]
    assert "*(A01^2 + B01^2 + A11^2 + B11^2)*(1.5405929/Get(cell_volume))^2" in line
    assert "100*" not in line
    _, _, err = _oracle("nacl_xray_ext20", ref)
    assert err < ORACLE_TOL          # measured 2.6e-3, the case's own floor
    # positive arms: no extinction, and the neutron factor 100, both miss
    for value in (0.0, 20.0 * 100):
        arm_ref, _ = _xray_extinction(value)
        _, _, arm = _oracle("nacl_xray_ext20", arm_ref)
        assert arm > 4 * err         # measured 2.4e-1 and 3.7


def test_the_written_laue_factor_is_within_its_stated_bound(tmp_path):
    """TOPAS has no Bessel function, so the file spells e^(−x)·[I₀ + I₁] as
    Abramowitz & Stegun 9.8.1-9.8.4 (WP-2044). The Laue factor is cut out of
    the written ``scale_pks`` line, mapped to python and evaluated against
    scipy over x in (0, 10⁴], and the file's head says what was written."""
    from scipy.special import i0e, i1e

    from rietx.io.projects.topas_input import _LAUE_SPELLING_REL

    ref, pattern = _xray_extinction(20.0)
    rx.write_topas_inp(ref.fitted_structure, tmp_path / "x.inp", free=ref,
                       instrument=ref.fitted_instrument, pattern=pattern,
                       scale="topas")
    text = (tmp_path / "x.inp").read_text(encoding="utf-8")
    assert "Abramowitz & Stegun" in text.split("scale_pks")[0]
    (line,) = [ln for ln in text.splitlines() if "scale_pks" in ln]
    rhs = line.split("=", 1)[1].rstrip(";").strip()
    # the Laue arm sits between the x <= 0 guard and the closing '*Cos(Th)^2'
    xv = rhs[rhs.index("If(") + 3:rhs.index(" <= 0, 1, ")]
    laue = rhs[rhs.index("If("):rhs.rindex("*Cos(Th)^2")].replace(xv, "X")
    expr = (laue.replace("^", "**").replace("Exp", "np.exp")
            .replace("Sqrt", "np.sqrt"))
    expr = re.sub(r"If\(", "_if(", expr)

    def _if(c, a, b):
        return np.where(c, a, b)

    x = np.concatenate([np.geomspace(1e-6, 10, 20001), np.geomspace(10, 1e4, 2001)])
    with np.errstate(all="ignore"):
        got = eval(compile(expr, "<laue>", "eval"),  # noqa: S307 - our own file
                   {"np": np, "_if": _if, "X": x})
    exact = i0e(x) + i1e(x)
    assert np.max(np.abs(got - exact) / exact) <= _LAUE_SPELLING_REL  # 3.59e-8


@pytest.mark.parametrize("stem", ['a"b', "a\nb", "a\rb"])
def test_a_data_file_name_the_xdd_line_cannot_hold_is_refused(tmp_path, stem):
    ref, pattern = case_nacl_neutron()
    out = tmp_path / f"{stem}.inp"
    with pytest.raises(ValueError, match="xdd"):
        rx.write_topas_inp(ref.fitted_structure, out, free=ref,
                           instrument=ref.fitted_instrument, pattern=pattern,
                           scale="topas")
    assert list(tmp_path.iterdir()) == []


def test_the_xray_file_states_lp_and_the_doublet(tmp_path):
    _, _, text, _ = _write(case_nacl_xray, tmp_path)
    assert "LP_Factor(0)" in text and "neutron_data" not in text
    assert "la 0.5 lo 1.5444274" in text
    assert "th2_offset = -2*Rad*(0.05)*Cos(Th)/217.5;" in text
    assert "rietx Phase.scale x 0.5" in text


def test_a_pspline_is_written_as_its_own_pieces_and_penalty(tmp_path):
    ref, pattern, text, _ = _write(case_nacl_pspline, tmp_path)
    bkg = ref.fitted_instrument.background
    assert text.count("fit_obj = ") == len(bkg.coefficients)
    assert text.count("penalty = ") == len(bkg.coefficients) - 2
    assert "pen_weight = 1;" in text
    w = np.sqrt(bkg.lambda_smooth) * pspline_penalty_scale(
        pattern.sig()[pattern.in_range_mask()], len(bkg.coefficients))
    first = re.search(r"penalty = \(([-\d.e+]+)\*", text)
    assert float(first.group(1)) == pytest.approx(w, rel=1e-12)
    assert second_difference_matrix(len(bkg.coefficients)).shape[0] == text.count("penalty = ")


def test_the_pspline_case_is_what_topas_computes():
    """rietx's P-spline and FCJ axial divergence, as TOPAS fit_obj pieces, penalty
    terms and Finger_et_al: TOPAS's Y_calc, and its own penalty sum at zero
    cycles, printed as P = 32.039846 against rietx's Σr² (TOPAS-64 v6, same
    run as the Y_calc file)."""
    ref, pattern = case_nacl_pspline()
    _, _, err = _oracle("nacl_pspline", ref)
    assert err < ORACLE_TOL
    inst = ref.fitted_instrument.model_copy(deep=True)
    inst.geometry.axial_sl.value = 0.0
    inst.geometry.axial_hl.value = 0.0
    _, _, arm = _oracle("nacl_pspline", rx.Refinement(ref.fitted_structure, inst,
                                                      history=False))
    assert arm > 3 * err          # measured 1.07e-2 against 3.3e-3
    # The penalty's σ̄ is the data file's.  TOPAS read the file written on
    # 2026-10-06, when predict() drew the case at the declared stages'
    # windows, so its σ is rebuilt at that setting by name: drawn at today's
    # closing windows, σ̄ moves and Σr² misses TOPAS's in its fifth figure (WP-2002).
    tt = pattern.tt()
    table = ParameterTable(ref.structure, ref.instrument)
    grid = rx.PatternData(two_theta=list(tt), intensity=[0.0] * len(tt))
    y = compile_model(ref.structure, ref.instrument, grid, mode="rietveld",
                      moving_paths=set(table.moving_paths),
                      window_area_tol=WINDOW_AREA_TOL).evaluate(table.decode(table.x0()))
    sig = np.sqrt(np.maximum(y, 1.0))[pattern.in_range_mask()]
    bkg = ref.fitted_instrument.background
    c = np.array([p.value for p in bkg.coefficients])
    w = np.sqrt(bkg.lambda_smooth) * pspline_penalty_scale(sig, len(c))
    r = w * (second_difference_matrix(len(c)) @ c)
    assert float(r @ r) == pytest.approx(32.039846, abs=5e-7)


def test_the_bspline_pieces_are_the_basis():
    from rietx.background.models import bspline_design_matrix

    knots = np.linspace(5.0, 95.0, 10)
    x = np.linspace(5.0, 94.99, 333)
    design = bspline_design_matrix(x, knots)
    for k in range(design.shape[0]):
        pieces = _bspline_pieces(knots, k)
        y = np.zeros_like(x)
        for lo, hi, a in pieces:
            m = (x >= lo) & (x < hi)
            u = x[m] - lo
            y[m] = sum(an * u ** n for n, an in enumerate(a))
        assert np.allclose(y, design[k], atol=1e-12)


def test_the_finger_lengths_are_twice_the_ratios_times_the_radius(tmp_path):
    _, _, text, _ = _write(case_nacl_pspline, tmp_path)
    assert "prm rx_fcj_s2 = 435.0*(0.01);" in text
    assert "prm rx_fcj_h2 = 435.0*(geom_axial_hl);" in text      # free: by name
    assert "Finger_et_al(=rx_fcj_s2;, =rx_fcj_h2;)" in text


def test_pattern_needs_the_instrument(tmp_path):
    ref, pattern = case_nacl_neutron()
    with pytest.raises(ValueError, match="needs instrument="):
        rx.write_topas_inp(ref.fitted_structure, tmp_path / "x.inp", pattern=pattern)


def test_an_absorption_correction_is_refused_by_name(tmp_path):
    ref, pattern = case_nacl_neutron()
    inst = ref.fitted_instrument.model_copy(update={
        "geometry": ref.fitted_instrument.geometry.model_copy(update={"mu_r": 0.3})})
    with pytest.raises(ValueError, match="mu_r"):
        rx.write_topas_inp(ref.fitted_structure, tmp_path / "x.inp", instrument=inst,
                           pattern=pattern)


def _broadened():
    """The neutron case with a Lorentzian size and a Gaussian strain width."""
    ref, pattern = case_nacl_neutron()
    s = ref.fitted_structure.model_copy(deep=True)
    s.phases[0].lor_size.value = 0.03
    s.phases[0].gauss_strain.value = 0.02
    return rx.Refinement(s, ref.fitted_instrument, history=False), pattern


def _width_lines(text):
    return [ln for ln in text.splitlines()
            if ln.startswith("  lor_fwhm") or ln.startswith("  gauss_fwhm")]


def test_the_widths_are_stated_once(tmp_path):
    """A whole input folds the sample widths into ``pv_fwhm``/``pv_lor`` and
    writes no ``str``-level width line beside them (TOPAS would convolve the
    widths in twice); a ``free=``-only file has no profile, so it states them
    as the structure-only writer's lines, a free width over its name."""
    ref, pattern = _broadened()
    s = ref.fitted_structure
    rx.write_topas_inp(s, tmp_path / "whole.inp", free=ref,
                       instrument=ref.fitted_instrument, pattern=pattern)
    whole = (tmp_path / "whole.inp").read_text(encoding="utf-8")
    assert "pv_fwhm = " in whole and _width_lines(whole) == []

    rx.write_topas_inp(s, tmp_path / "free.inp", free=ref)
    rx.write_topas_inp(s, tmp_path / "str.inp")
    free = (tmp_path / "free.inp").read_text(encoding="utf-8")
    assert "peak_type" not in free
    assert _width_lines(free) == _width_lines(
        (tmp_path / "str.inp").read_text(encoding="utf-8")) == [
        "  lor_fwhm = 0.03/Cos(Th);", "  gauss_fwhm = Sqrt(0.02*Tan(Th)^2);"]

    ref.set_vary(["phases.0.lor_size"], True)
    rx.write_topas_inp(s, tmp_path / "freed.inp", free=ref)
    freed = (tmp_path / "freed.inp").read_text(encoding="utf-8")
    assert _width_lines(freed)[0] == "  lor_fwhm = (p0_lor_size)/Cos(Th);"
    assert re.search(r"^prm p0_lor_size 0\.03\b", freed, re.MULTILINE)


def test_a_free_width_at_zero_is_still_written(tmp_path):
    """A free term TOPAS must be able to move is written though it is zero."""
    ref, _ = case_nacl_neutron()
    ref.set_vary(["phases.0.gauss_size"], True)
    rx.write_topas_inp(ref.fitted_structure, tmp_path / "z.inp", free=ref)
    text = (tmp_path / "z.inp").read_text(encoding="utf-8")
    assert _width_lines(text) == ["  gauss_fwhm = Sqrt((p0_gauss_size)/Cos(Th)^2);"]


def test_what_each_path_does_not_state_is_named(tmp_path):
    """``TOPAS_FIELD_NOT_WRITTEN``: a whole input writes the extinction, so it
    names the texture alone; a ``free=``-only file names both."""
    from rietx.schemas.structure import PreferredOrientation

    ref, pattern = case_nacl_neutron()
    s = ref.fitted_structure.model_copy(deep=True)
    s.phases[0].preferred_orientation = PreferredOrientation(
        axis=(0, 0, 1), r=rx.Parameter(value=0.8, min=0.1, max=3.0))
    assert s.phases[0].extinction.value != 0.0
    whole, free = [], []
    rx.write_topas_inp(s, tmp_path / "w.inp", free=ref, diagnostics=whole,
                       instrument=ref.fitted_instrument, pattern=pattern)
    rx.write_topas_inp(s, tmp_path / "f.inp", free=ref, diagnostics=free)
    [named] = [d for d in whole if d.code == "TOPAS_FIELD_NOT_WRITTEN"]
    assert named.where == ["phases.0.preferred_orientation.r"]
    assert "texture" in named.message and "extinction" not in named.message
    [named] = [d for d in free if d.code == "TOPAS_FIELD_NOT_WRITTEN"]
    assert sorted(named.where) == ["phases.0.extinction",
                                   "phases.0.preferred_orientation.r"]


def test_a_site_near_a_special_position_is_written_on_it(tmp_path):
    """The refined writer writes ZnO's rounded ``x 0.3333 y 0.6667`` on its 2b
    position, as the structure-only writer does: TOPAS reads the rounded
    number as a general position and generates 12 atoms where rietx has 2."""
    from rietx.crystallography.symmetry import get_spacegroup

    def p(v):
        return rx.Parameter(value=v)

    sg = get_spacegroup("P 63 m c")
    structure = rx.Structure(phases=[rx.Phase(
        name="zno", space_group="P 63 m c",
        cell=rx.Cell(a=p(3.25), b=p(3.25), c=p(5.2), alpha=p(90.0), beta=p(90.0),
                     gamma=p(120.0)),
        atoms=[rx.Atom(label="Zn1", species="Zn", x=p(0.3333), y=p(0.6667), z=p(0.0)),
               rx.Atom(label="O1", species="O", x=p(0.3333), y=p(0.6667), z=p(0.382))])])
    rx.write_topas_inp(structure, tmp_path / "zno.inp", free=[])
    sites = [ln for ln in (tmp_path / "zno.inp").read_text(encoding="utf-8").splitlines()
             if ln.startswith("  site ")]
    assert len(sites) == 2
    for ln in sites:
        tokens = ln.split()
        x, y, z = (float(tokens[tokens.index(k) + 2]) for k in "xyz")
        positions = {tuple(np.round((np.array(op.apply_to_xyz([x, y, z])) % 1.0
                                     + 1e-12) % 1.0, 9)) for op in sg.operations()}
        assert len(positions) == 2, ln
    assert structure.phases[0].atoms[0].x.value == 0.3333
