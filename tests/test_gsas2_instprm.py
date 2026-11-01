"""``read_gsas2_instprm``/``write_gsas2_instprm``: GSAS-II's text instrument file.

Two fixtures are **vendored**, unlike the GSAS-I ``.prm`` pair's: the GSAS-II
tutorials carry a redistribution grant where this WP's other corpora are
private (``tests/data/README.md`` § GSAS-II).  They are the two ends of what
the corpus holds — a constant-wavelength neutron calibration that reads end to
end, and an X-ray one that is **refused** for a negative ``X``, which 2 of the
corpus's 4 constant-wavelength files carry.

What no real file here covers is written by hand, which is the same split
``test_projects_gsas2.py`` makes: no ``.instprm`` in the corpus states a Kα
doublet, a ``Diff-type`` or a goniometer radius, and the doublet key names are
corroborated instead by ``gsas2_pbso4.gpx``, whose two histograms carry
``INSTPRM_CW_SINGLE`` and ``INSTPRM_CW_DOUBLET`` exactly.
"""

from __future__ import annotations

import csv
import math
import re
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.io.instrument_profile import (
    INSTPRM_SHL_FLOOR,
    from_instrument_gsas2,
    read_gsas2_instprm,
)
from rietx.io.projects.gsas2 import (
    INSTPRM_CW_DOUBLET,
    INSTPRM_CW_SINGLE,
    read_instprm,
)
from rietx.model.profiles.pseudovoigt import pseudo_voigt, tch_gamma_eta

DATA = Path(__file__).parent / "data"
BNL = DATA / "gsas2_bnl.instprm"
HB2A = DATA / "gsas2_hb2a.instprm"
EIGHT_LN2 = 8.0 * math.log(2.0)


def _calibrated() -> rx.Instrument:
    """An instrument shaped like a converged ``lab_calibrate``, doublet and all.

    The same shape ``test_gsas_prm.py`` writes for the ``.prm`` writer, so the
    two formats' round trips are comparable.
    """
    inst = rx.Instrument.debye_scherrer(wavelength=1.5405929, polarization=0.99)
    inst.source.lines.append(rx.EmissionLine(
        wavelength=1.5444274, weight=rx.Parameter(value=0.5, min=0.0, max=2.0)))
    inst.profile.u.value = 1.163e-4
    inst.profile.v.value = -0.126e-4
    inst.profile.w.value = 0.063e-4
    inst.profile.x.value = 0.173e-2
    inst.profile.y.value = 0.0
    inst.geometry.axial_sl.value = 0.0015
    inst.geometry.axial_hl.value = 0.0015
    inst.zero_shift.value = -0.0043
    return inst


# ----------------------------------------------------------------- the grammar


def test_the_grammar_reads_the_items_gsas_ii_writes():
    """One bank, keys and values as strings, spaces stripped from both."""
    (bank,) = read_instprm(HB2A.read_text(encoding="utf-8"))
    assert bank.number is None
    assert bank.items["Type"] == "PNC"
    assert bank.items["Lam"] == "2.4062686168735197"


def test_several_items_may_share_a_line_and_spaces_are_stripped():
    """``;`` separates items on one line and every space goes, which is what
    makes GSAS-II's own ``Gonio. radius`` arrive as ``Gonio.radius``."""
    text = ("#GSAS-II instrument parameter file; do not add/delete items!\n"
            "Type:PXC; Lam:1.5405\n"
            "Gonio. radius:217.5\n")
    (bank,) = read_instprm(text)
    assert bank.items == {"Type": "PXC", "Lam": "1.5405",
                          "Gonio.radius": "217.5"}


def test_a_triple_quoted_value_runs_to_its_delimiter():
    """GSAS-II writes a multi-line value that way, and a reader that split it
    on ``:`` would take its second line for an item."""
    text = ("#GSAS-II instrument parameter file; do not add/delete items!\n"
            "InstrName:'''a beamline\nwith a note: two lines'''\n"
            "Type:PXC\n")
    (bank,) = read_instprm(text)
    assert bank.items["Type"] == "PXC"
    assert "two lines" in bank.items["InstrName"]


def test_a_file_without_the_marker_is_refused():
    """GSAS-II's own file test is ``'GSAS-II' in the first line`` and nothing
    else, so this reader makes the same one."""
    with pytest.raises(ValueError, match="GSAS-II"):
        read_instprm("#some other program's parameters\nType:PXC\n")


def test_banks_are_split_on_their_headers():
    text = ("#Bank 1: GSAS-II instrument parameter file; do not add/delete items!\n"
            "  Type:PXC\n  Lam:1.0\n"
            "#Bank 2: GSAS-II instrument parameter file; do not add/delete items!\n"
            "  Type:PXC\n  Lam:2.0\n")
    banks = read_instprm(text)
    assert [b.number for b in banks] == [1, 2]
    assert banks[1].items["Lam"] == "2.0"


# ------------------------------------------------------------------ the reader


def test_a_real_neutron_calibration_reads_end_to_end():
    """``gsas2_hb2a.instprm``, HFIR's HB-2A: the corpus file that reads.

    Its numbers are the file's own: U, V and W are a Gaussian variance in
    centidegrees squared (so ``profile.u/v/w`` = value / 1e4 / 8 ln 2, the FWHM²
    in degrees²) and X, Y centidegrees, while ``Zero`` is already degrees.
    """
    instrument = read_gsas2_instprm(HB2A)
    assert instrument.source.kind == "neutron_cw"
    assert instrument.source.wavelength.value == pytest.approx(
        2.4062686168735197, rel=1e-15)
    assert instrument.profile.u.value == pytest.approx(
        798.889 / 1e4 * EIGHT_LN2, rel=1e-15)
    assert instrument.profile.v.value == pytest.approx(
        -444.367 / 1e4 * EIGHT_LN2, rel=1e-15)
    assert instrument.profile.w.value == pytest.approx(
        242.406 / 1e4 * EIGHT_LN2, rel=1e-15)
    assert instrument.zero_shift.value == pytest.approx(
        -0.009602591470493875, rel=1e-15)
    # SH/L = 0.09 is GSAS-II's combined (S+H)/L
    assert instrument.geometry.axial_sl.value == pytest.approx(0.045, rel=1e-15)
    assert instrument.geometry.axial_hl.value == pytest.approx(0.045, rel=1e-15)


def test_everything_comes_back_frozen():
    """A calibration is not a starting guess — :func:`load_instrument_profile`'s
    contract, which both foreign importers here keep."""
    instrument = read_gsas2_instprm(HB2A)
    assert not instrument.profile.u.vary
    assert not instrument.profile.w.vary
    assert not instrument.zero_shift.vary
    assert not instrument.geometry.axial_sl.vary


def test_the_neutron_read_says_what_it_assumed_and_what_it_dropped():
    diagnostics: list = []
    read_gsas2_instprm(HB2A, diagnostics=diagnostics)
    codes = {d.code for d in diagnostics}
    assert codes == {"GSAS2_INSTPRM_CONVENTION_ASSUMED",
                     "GSAS2_INSTPRM_GEOMETRY_ASSUMED",
                     "GSAS2_INSTPRM_FIELD_NOT_READ"}
    (dropped,) = [d for d in diagnostics
                  if d.code == "GSAS2_INSTPRM_FIELD_NOT_READ"]
    # inert in GSAS-II too: it applies the factor to an XC or XB type only
    assert "Polariz." in dropped.message
    assert "K = 1" in dropped.message


def test_a_real_x_ray_calibration_is_refused_for_its_negative_x():
    """``gsas2_bnl.instprm``: a converged GSAS-II fit with ``X`` = −0.0978.

    GSAS-II bounds none of U V W X Y Z and this package's Lorentzian terms are
    bounded below at zero, so reading it would answer from a model the file
    does not describe.  Two of the corpus's four constant-wavelength files
    carry one, so this is the ordinary case rather than a corner.
    """
    with pytest.raises(ValueError, match="bounded below at zero"):
        read_gsas2_instprm(BNL)


def test_a_time_of_flight_bank_dispatches_on_its_type(tmp_path):
    """One reader on ``Type``: a ``PNT`` bank comes back as a ``neutron_tof``
    source, and one stating no bank angle is refused naming the key it lacks."""
    head = "#GSAS-II instrument parameter file; do not add/delete items!\n"
    path = tmp_path / "tof.instprm"
    path.write_text(head + "Type:PNT\ndifC:22583.9\n2-theta:90.0\n",
                    encoding="utf-8")
    source = read_gsas2_instprm(path).source
    assert source.kind == "neutron_tof"
    assert source.difc.value == 22583.9 and not source.difc.vary
    path.write_text(head + "Type:PNT\ndifC:22583.9\n", encoding="utf-8")
    with pytest.raises(ValueError, match="'2-theta'"):
        read_gsas2_instprm(path)


def test_an_energy_dispersive_bank_is_refused_by_name(tmp_path):
    path = tmp_path / "ed.instprm"
    path.write_text("#GSAS-II instrument parameter file; do not add/delete items!\n"
                    "Type:PXE\n", encoding="utf-8")
    with pytest.raises(ValueError, match="energy-dispersive"):
        read_gsas2_instprm(path)


def test_a_non_zero_z_is_refused(tmp_path):
    """``ProfileTCHZ`` is u, v, w, x, y exactly, and ``Z`` is zero in all 95
    constant-wavelength histograms of the ``.gpx`` corpus."""
    path = tmp_path / "z.instprm"
    path.write_text("#GSAS-II instrument parameter file; do not add/delete items!\n"
                    "Type:PXC\nLam:1.5405\nZ:0.4\n", encoding="utf-8")
    with pytest.raises(ValueError, match="constant Lorentzian"):
        read_gsas2_instprm(path)


def test_a_non_zero_azimuth_is_refused(tmp_path):
    """At a non-zero azimuth GSAS-II mixes the two polarization components, so
    ``Polariz.`` no longer means this package's K."""
    path = tmp_path / "azm.instprm"
    path.write_text("#GSAS-II instrument parameter file; do not add/delete items!\n"
                    "Type:PXC\nLam:1.5405\nAzimuth:90.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="azimuth"):
        read_gsas2_instprm(path)


def test_a_doublet_without_its_ratio_is_refused(tmp_path):
    path = tmp_path / "pair.instprm"
    path.write_text("#GSAS-II instrument parameter file; do not add/delete items!\n"
                    "Type:PXC\nLam1:1.5405\nLam2:1.5444\n", encoding="utf-8")
    with pytest.raises(ValueError, match="I\\(L2\\)/I\\(L1\\)"):
        read_gsas2_instprm(path)


def test_a_neutron_bank_stating_a_doublet_is_refused(tmp_path):
    """A monochromator selects one wavelength, so ``NeutronSource`` holds one
    and picking between the pair would be this reader's guess."""
    path = tmp_path / "npair.instprm"
    path.write_text("#GSAS-II instrument parameter file; do not add/delete items!\n"
                    "Type:PNC\nLam1:1.5405\nLam2:1.5444\nI(L2)/I(L1):0.5\n", encoding="utf-8")
    with pytest.raises(ValueError, match="NeutronSource holds"):
        read_gsas2_instprm(path)


def _two_banks() -> str:
    return ("#Bank 1: GSAS-II instrument parameter file; do not add/delete items!\n"
            "  Type:PXC\n  Lam:1.5405\n  W:1.0\n"
            "#Bank 2: GSAS-II instrument parameter file; do not add/delete items!\n"
            "  Type:PXC\n  Lam:0.4139\n  W:4.0\n")


def test_a_multi_bank_file_needs_a_bank(tmp_path):
    """The selection rule ``read_pattern``'s ``scan=`` makes: reading the first
    of several would pick a detector rather than read one.  Three of the
    corpus's twelve files are multi-bank."""
    path = tmp_path / "gem.instprm"
    path.write_text(_two_banks(), encoding="utf-8")
    with pytest.raises(ValueError, match="bank=N"):
        read_gsas2_instprm(path)

    chosen = read_gsas2_instprm(path, bank=2)
    assert chosen.source.lines[0].wavelength.value == pytest.approx(0.4139)
    assert chosen.profile.w.value == pytest.approx(4.0 / 1e4 * EIGHT_LN2, rel=1e-15)


def test_a_bank_the_file_does_not_state_is_refused(tmp_path):
    path = tmp_path / "gem.instprm"
    path.write_text(_two_banks(), encoding="utf-8")
    with pytest.raises(ValueError, match="states 1, 2"):
        read_gsas2_instprm(path, bank=7)


def test_a_repeated_bank_number_is_refused(tmp_path):
    """Three of the corpus's twelve files write ``#Bank 6`` twice, so a number
    can name two calibrations in one file."""
    path = tmp_path / "twice.instprm"
    path.write_text(_two_banks().replace("#Bank 2:", "#Bank 1:"),
                    encoding="utf-8")
    with pytest.raises(ValueError, match="names two calibrations"):
        read_gsas2_instprm(path, bank=1)


def test_a_stated_geometry_is_read_rather_than_assumed(tmp_path):
    path = tmp_path / "bb.instprm"
    path.write_text("#GSAS-II instrument parameter file; do not add/delete items!\n"
                    "Type:PXC\nLam:1.5405\nDiff-type:Bragg-Brentano\n"
                    "Gonio. radius:217.5\n", encoding="utf-8")
    diagnostics: list = []
    instrument = read_gsas2_instprm(path, diagnostics=diagnostics)
    assert instrument.geometry.kind == "bragg_brentano"
    assert instrument.geometry.goniometer_radius_mm == pytest.approx(217.5)
    assert not [d for d in diagnostics
                if d.code == "GSAS2_INSTPRM_GEOMETRY_ASSUMED"]


# ------------------------------------------------------------------ the writer


def test_the_writer_round_trips_a_doublet_calibration(tmp_path):
    """Every number the reader maps comes back, through the one centidegree
    conversion rather than a second copy of it."""
    inst = _calibrated()
    out = tmp_path / "written.instprm"
    rx.write_gsas2_instprm(inst, out)
    back = read_gsas2_instprm(out)

    assert len(back.source.lines) == 2
    assert back.source.lines[0].wavelength.value == pytest.approx(1.5405929, rel=1e-15)
    assert back.source.lines[1].wavelength.value == pytest.approx(1.5444274, rel=1e-15)
    assert back.source.lines[1].weight.value == pytest.approx(0.5, rel=1e-15)
    assert back.source.polarization.value == pytest.approx(0.99, rel=1e-15)
    for key in ("u", "v", "w", "x", "y"):
        assert getattr(back.profile, key).value == pytest.approx(
            getattr(inst.profile, key).value, rel=1e-12)
    assert back.geometry.axial_sl.value == pytest.approx(0.0015, rel=1e-15)
    assert back.geometry.axial_hl.value == pytest.approx(0.0015, rel=1e-15)
    assert back.zero_shift.value == pytest.approx(-0.0043, rel=1e-15)
    assert back.geometry.kind == "debye_scherrer"


def test_a_single_line_source_writes_lam_and_not_the_pair(tmp_path):
    inst = rx.Instrument.debye_scherrer(wavelength=0.4139090, polarization=0.99)
    out = tmp_path / "mono.instprm"
    rx.write_gsas2_instprm(inst, out)
    assert "\nLam:" in out.read_text(encoding="utf-8")
    back = read_gsas2_instprm(out)
    assert len(back.source.lines) == 1
    assert back.source.primary_wavelength == pytest.approx(0.4139090, rel=1e-15)


def test_a_neutron_instrument_round_trips(tmp_path):
    """The one radiation the ``.prm`` pair refuses outright: GSAS-II states it
    as ``PNC`` and this package has held a ``NeutronSource`` since v1.4."""
    inst = rx.Instrument.constant_wavelength_neutron(wavelength=1.5401)
    inst.profile.w.value = 0.02
    out = tmp_path / "neutron.instprm"
    rx.write_gsas2_instprm(inst, out)
    assert "\nType:PNC\n" in out.read_text(encoding="utf-8")
    back = read_gsas2_instprm(out)
    assert back.source.kind == "neutron_cw"
    assert back.source.wavelength.value == pytest.approx(1.5401, rel=1e-15)
    assert back.profile.w.value == pytest.approx(0.02, rel=1e-15)


def test_the_written_keys_are_the_formats_own_list(tmp_path):
    """The two key tuples are the specification's order, and the writer is the
    one caller that depends on it."""
    doublet = read_instprm(from_instrument_gsas2(_calibrated()))[0]
    assert tuple(doublet.items)[:len(INSTPRM_CW_DOUBLET)] == INSTPRM_CW_DOUBLET

    mono = rx.Instrument.debye_scherrer(wavelength=1.0)
    single = read_instprm(from_instrument_gsas2(mono))[0]
    assert tuple(single.items)[:len(INSTPRM_CW_SINGLE)] == INSTPRM_CW_SINGLE
    # GSAS-II's own file test, made on a file this package wrote
    assert from_instrument_gsas2(mono).splitlines()[0].startswith("#GSAS-II")


def test_an_uneven_axial_pair_is_merged_and_the_merge_is_named(tmp_path):
    """``io/CLAUDE.md`` § Project writers' narrower-field rule, met on a value:
    GSAS-II models one ``(S+H)/L``, so the sum crosses and the split does not."""
    inst = _calibrated()
    inst.geometry.axial_sl.value = 0.0010
    inst.geometry.axial_hl.value = 0.0020
    diagnostics: list = []
    out = tmp_path / "uneven.instprm"
    rx.write_gsas2_instprm(inst, out, diagnostics=diagnostics)

    (row,) = [d for d in diagnostics if d.code == "GSAS2_INSTPRM_VALUE_MERGED"]
    assert row.value == pytest.approx(0.0030, rel=1e-12)
    back = read_gsas2_instprm(out)
    assert back.geometry.axial_sl.value == pytest.approx(0.0015, rel=1e-12)
    assert back.geometry.axial_hl.value == pytest.approx(0.0015, rel=1e-12)


def test_an_axial_sum_below_gsas_ii_own_floor_is_named(tmp_path):
    """The one class this round trip cannot catch: GSAS-II floors ``SH/L`` at
    0.002 when it evaluates a profile, so a smaller one is written faithfully
    and modelled as the floor by the program the file is for."""
    inst = _calibrated()
    inst.geometry.axial_sl.value = 0.0005
    inst.geometry.axial_hl.value = 0.0005
    diagnostics: list = []
    rx.write_gsas2_instprm(inst, tmp_path / "small.instprm",
                           diagnostics=diagnostics)
    (row,) = [d for d in diagnostics if d.code == "GSAS2_INSTPRM_VALUE_FLOORED"]
    assert row.value == pytest.approx(0.001, rel=1e-12)
    assert str(INSTPRM_SHL_FLOOR) in row.message


def test_the_written_file_says_what_it_could_not_state(tmp_path):
    inst = _calibrated()
    inst.profile.u.vary = True
    diagnostics: list = []
    rx.write_gsas2_instprm(inst, tmp_path / "said.instprm",
                           diagnostics=diagnostics)
    (row,) = [d for d in diagnostics
              if d.code == "GSAS2_INSTPRM_FIELD_NOT_WRITTEN"]
    assert row.level == "warning"
    assert "the background" in row.message
    assert "every refine flag" in row.message


def test_the_writer_refuses_a_geometry_gsas_ii_cannot_state():
    """``Diff-type`` names two sample kinds and transmission is not one of
    them; writing either would hand over a different experiment."""
    inst = rx.Instrument.flat_plate_transmission()
    with pytest.raises(ValueError, match="Diff-type"):
        from_instrument_gsas2(inst)


def test_the_writer_refuses_more_lines_than_a_bank_holds():
    inst = _calibrated()
    inst.source.lines.append(rx.EmissionLine(
        wavelength=1.39222, weight=rx.Parameter(value=0.1, min=0.0, max=2.0)))
    with pytest.raises(ValueError, match="emission lines"):
        from_instrument_gsas2(inst)


def test_the_writer_refuses_a_declared_harmonic():
    """A λ/n component changes the spectrum and a constant-wavelength bank has
    no term for one."""
    inst = rx.Instrument.constant_wavelength_neutron(wavelength=1.5,
                                                    harmonics=[2])
    with pytest.raises(ValueError, match="harmonic"):
        from_instrument_gsas2(inst)


def test_the_writer_refuses_a_non_finite_value():
    """``repr`` spells it ``inf`` and no real program parses that — the same
    refusal all five writers here make."""
    inst = _calibrated()
    inst.profile.y.max = float("inf")
    inst.profile.y.value = float("inf")
    with pytest.raises(ValueError, match="inf"):
        from_instrument_gsas2(inst)


def test_the_written_values_are_the_real_files_own_spelling(tmp_path):
    """The check a round trip cannot make, made against a real file.

    ``float()`` here would read a value GSAS-II spells differently, so the
    ``.EXP`` writer had to compare its cards against ``FAP.EXP``'s own
    spelling (``io/CLAUDE.md`` § Project writers).  A token format lets that be
    exact: reading ``gsas2_hb2a.instprm`` and writing it back reproduces every
    item it states, character for character.
    """
    out = tmp_path / "again.instprm"
    rx.write_gsas2_instprm(read_gsas2_instprm(HB2A), out)
    (original,) = read_instprm(HB2A.read_text(encoding="utf-8"))
    (written,) = read_instprm(out.read_text(encoding="utf-8"))
    assert original.items == {k: v for k, v in written.items.items()
                              if k in original.items}
    assert len(original.items) == 13


def test_an_item_the_format_declares_and_a_file_omits_is_named(tmp_path):
    """GSAS-II writes every item and its header says not to delete any, so a
    missing one is a hand-edited file — and the value used is this package's
    default rather than the file's."""
    path = tmp_path / "thin.instprm"
    path.write_text("#GSAS-II instrument parameter file; do not add/delete items!\n"
                    "Type:PXC\nLam:1.5405\n", encoding="utf-8")
    diagnostics: list = []
    read_gsas2_instprm(path, diagnostics=diagnostics)
    (row,) = [d for d in diagnostics
              if d.code == "GSAS2_INSTPRM_VALUE_DEFAULTED"]
    assert "SH/L" in row.message and "Polariz." in row.message


# ------------------------------------- what the review pass measured (WP-1118)


def test_an_empty_file_is_refused_by_name(tmp_path):
    """A zero-byte file has no first line, and indexing one raised
    ``IndexError`` out of a reader whose contract is a `ValueError` naming the
    file. A truncated download is the ordinary way to get one."""
    path = tmp_path / "empty.instprm"
    path.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="GSAS-II"):
        read_gsas2_instprm(path)


def test_a_triple_quoted_value_may_open_and_close_on_one_line():
    """Scanning on for a closing delimiter that is already there swallowed
    every item after it — `Type` and the wavelength included — into one
    value, and the bank was then refused for stating no type it does state."""
    text = ("#GSAS-II instrument parameter file; do not add/delete items!\n"
            "InstrName:'''My Lab'''\n"
            "Type:PXC\n"
            "Lam:1.5406\n")
    (bank,) = read_instprm(text)
    assert bank.items["InstrName"] == "My Lab"
    assert bank.items["Type"] == "PXC"
    assert bank.items["Lam"] == "1.5406"


def test_a_file_stating_lam1_is_not_reported_as_missing_lam(tmp_path):
    """``Lam`` and ``Lam1`` are two spellings of one item, so a file stating
    either is not a file missing the other."""
    path = tmp_path / "one.instprm"
    path.write_text("#GSAS-II instrument parameter file; do not add/delete items!\n"
                    "Type:PXC\nLam1:1.5405\n", encoding="utf-8")
    diagnostics: list = []
    read_gsas2_instprm(path, diagnostics=diagnostics)
    (row,) = [d for d in diagnostics
              if d.code == "GSAS2_INSTPRM_VALUE_DEFAULTED"]
    # `\bLam\b` does not match `Lam1`, which is the point: the row may name
    # the items this file really does omit, and must not name the wavelength
    assert not re.search(r"\bLam\b", row.message)
    assert "SH/L" in row.message


# ------------------------------------------------- the Gaussian convention (D1)


def _written_items(inst, tmp_path):
    out = tmp_path / "w.instprm"
    rx.write_gsas2_instprm(inst, out)
    return {k: float(v) for k, v in
            read_instprm(out.read_text(encoding="utf-8"))[0].items.items()
            if k in ("U", "V", "W", "X", "Y")}


def test_the_written_gaussian_width_is_gsas2s_variance_not_a_fwhm_squared(tmp_path):
    """GSAS-II states σ² = U tan²θ + V tanθ + W (centideg²) and draws a Gaussian
    of FWHM √(8 ln 2 · σ²).  Evaluating *that* law on the written numbers must
    give the FWHM rietx's own ``Γ_G² = u tan²θ + v tanθ + w`` states.

    Written without the 8 ln 2, the same file makes GSAS-II's Gaussian
    √(8 ln 2) = 2.35 times wider than the one rietx fitted.
    """
    inst = _calibrated()
    items = _written_items(inst, tmp_path)
    pr = inst.profile
    for two_theta in (20.0, 60.0, 120.0):
        t = math.tan(math.radians(two_theta / 2.0))
        rietx_fwhm = math.sqrt(pr.u.value * t * t + pr.v.value * t + pr.w.value)
        sigma2_centideg2 = items["U"] * t * t + items["V"] * t + items["W"]
        gsas2_fwhm = math.sqrt(EIGHT_LN2 * sigma2_centideg2) / 100.0
        assert gsas2_fwhm == pytest.approx(rietx_fwhm, rel=1e-12), two_theta


def test_the_reader_takes_gsas2s_variance_to_rietxs_fwhm_squared(tmp_path):
    """The inverse: U = 100 centideg² of variance is a Gaussian FWHM of
    √(8 ln 2 · 100)/100 = 0.2355° at θ = 45°, and ``u`` is its square."""
    path = tmp_path / "u.instprm"
    path.write_text(
        "#GSAS-II instrument parameter file; do not add/delete items!\n"
        "Type:PXC\nLam:1.5\nPolariz.:0.7\nU:100.0\nV:0.0\nW:0.0\nX:0.0\n"
        "Y:0.0\nZ:0.0\nSH/L:0.002\nZero:0.0\nAzimuth:0.0\nBank:1.0\n",
        encoding="utf-8")
    inst = read_gsas2_instprm(path)
    fwhm = math.sqrt(inst.profile.u.value)       # tan(45°) = 1, V = W = 0
    assert fwhm == pytest.approx(math.sqrt(EIGHT_LN2 * 100.0) / 100.0, rel=1e-12)


def _half_max_width(x: np.ndarray, y: np.ndarray, x0: float) -> float:
    """The FWHM of the peak nearest ``x0`` as drawn on the grid ``x``: a
    parabola through the top three points for the height, linear
    interpolation for each half-maximum crossing."""
    i0 = int(np.searchsorted(x, x0))
    lo, hi = max(i0 - 40, 0), min(i0 + 40, len(x) - 1)
    k = lo + int(np.argmax(y[lo:hi]))
    a, b, c = np.polyfit(x[k - 1:k + 2], y[k - 1:k + 2], 2)
    half = (c - b * b / (4.0 * a)) / 2.0
    j = k
    while y[j] > half:
        j -= 1
    left = x[j] + (half - y[j]) * (x[j + 1] - x[j]) / (y[j + 1] - y[j])
    j = k
    while y[j] > half:
        j += 1
    right = x[j - 1] + (half - y[j - 1]) * (x[j] - x[j - 1]) / (y[j] - y[j - 1])
    return right - left


def test_gsas2s_own_lab6_peaks_have_the_width_the_read_instprm_draws(tmp_path):
    """GSAS-II's computed pattern is the oracle, not its formula.

    The PowderLine LaB6 output (``tests/data/powderline/example_LaB6``) is a
    GSAS-II refinement: its ``refined_parameters.csv`` states the refined
    ``U V W`` and its ``fit_profile.txt`` the pattern GSAS-II drew from them.
    Those ``U V W`` written as an ``.instprm`` and read here give rietx's
    Gaussian FWHM.  Combined with GSAS-II's own Lorentzian (the peak list's
    ``gamma``) into rietx's pseudo-Voigt and drawn on GSAS-II's grid, each
    isolated line's FWHM lands within 0.21 % of GSAS-II's drawn
    ``y_calc − y_bkg`` (24 reflections, 2.3-14.9° 2θ at 0.1665 Å).  Read as
    a FWHM² (÷ 1e4 alone, the reading before #705) the same lines are drawn
    0.42-0.53 times as wide, and 1/√(8 ln 2) = 0.425 exactly where GSAS-II
    floors the Lorentzian.  The same half-maximum finder measures both
    curves, so the grid's interpolation error cancels.
    """
    lab6 = DATA / "powderline" / "example_LaB6"
    refined = {r["descriptive_name"]: float(r["value"]) for r in csv.DictReader(
        (lab6 / "output/refined_parameters.csv").read_text(
            encoding="utf-8").splitlines())}
    U, V, W = (refined[f"instrument_broadening_{k}"] for k in "UVW")
    path = tmp_path / "lab6.instprm"
    path.write_text(
        "#GSAS-II instrument parameter file; do not add/delete items!\n"
        f"Type:PXC\nLam:0.1665\nZero:0.0\nPolariz.:0.99\nAzimuth:0.0\n"
        f"U:{U!r}\nV:{V!r}\nW:{W!r}\nX:0.0\nY:0.0\nZ:0.0\nSH/L:0.0005\n",
        encoding="utf-8")
    pr = read_gsas2_instprm(path).profile

    profile = np.loadtxt(lab6 / "output/fit_profile.txt", skiprows=1)
    two_theta, net = profile[:, 0], profile[:, 3] - profile[:, 5]
    peaks = list(csv.DictReader((lab6 / "output/LaB6_peak_list_report.csv")
                                .read_text(encoding="utf-8").splitlines()))
    positions = np.array([float(r["2theta"]) for r in peaks])

    checked = 0
    for i, row in enumerate(peaks):
        t2 = positions[i]
        drawn = _half_max_width(two_theta, net, t2)
        if np.min(np.abs(np.delete(positions, i) - t2)) < 4.0 * drawn:
            continue                                 # an overlapped line
        t = math.tan(math.radians(t2 / 2.0))
        gamma_l = float(row["gamma"]) / 100.0        # GSAS-II's, centideg
        gamma_g = math.sqrt(pr.u.value * t * t + pr.v.value * t + pr.w.value)
        gamma, eta = tch_gamma_eta(np.array([gamma_g]), np.array([gamma_l]))
        ours = _half_max_width(
            two_theta, pseudo_voigt(two_theta - t2, gamma[0], eta[0]), t2)
        assert ours == pytest.approx(drawn, rel=5e-3), t2

        fwhm_squared_reading = math.sqrt((U * t * t + V * t + W) / 1e4)
        old, _ = tch_gamma_eta(np.array([fwhm_squared_reading]),
                               np.array([gamma_l]))
        assert old[0] / drawn < 0.55, t2
        checked += 1
    assert checked >= 20


def test_the_lorentzian_terms_keep_their_centidegree_factor(tmp_path):
    """X and Y are FWHMs, not variances: no 8 ln 2 belongs on them."""
    items = _written_items(_calibrated(), tmp_path)
    assert items["X"] == pytest.approx(0.173e-2 * 100.0, rel=1e-12)
