"""``read_gsas_prm``: the GSAS-I ``.prm`` instrument-parameter importer.

Every fixture here is **hand-written**, not vendored — the corpus this reader
was built and verified against lives outside the repository (WP campaign
archive), never as a committed file, real sample name or collaborator path.
``_prm`` below reproduces the *shapes* real files take (a plain dominant-case
bank, the same shape with inline coefficient labels, a short counted block,
a synthetic time-of-flight bank mimicking ``BNKPAR``/per-bank ``PRCF``) with
invented numbers, so nothing here proves a real calibration — only that the
parser reads what the manual says and refuses what it does not.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import rietx as rx
from rietx.io.instrument_profile import _PRCF_MAPPED, read_gsas_prm
from rietx.io.projects.gsas import (
    CW_PROFILE_COEFFICIENTS,
    read_icons,
    split_records,
)


def _icons(*, lam1=0.5, lam2=None, zero=None, refine="", damping=None,
           pola=0.990, ipola=0, kratio=0.500) -> str:
    """An ``ICONS`` payload laid out at the columns GSAS writes it at.

    ``3F10.0`` LAM1 LAM2 ZERO, ``2X``, ``3A1`` refine flags, ``4X``, ``I1``
    damping, ``F10.0`` POLA, ``I5`` IPOLA, ``F10.0`` KRATIO.  The widths are
    spelled out here and never imported from the reader: a fixture sharing its
    offsets with the parser can only confirm that the parser agrees with itself
    (``io/CLAUDE.md`` § adding a format, rule 4).

    ``None`` writes a field **blank**, which is the distinction the record
    turns on.  A field GSAS did not write is not a field holding zero, and it
    is precisely the blank ``IREF``/``IDAMP`` of an 11-BM file that let a
    whitespace split look correct for as long as it did.
    """
    def f(value, width):
        return " " * width if value is None else f"{value:{width}g}"

    return (f(lam1, 10) + f(lam2, 10) + f(zero, 10)
            + "  " + f"{refine:<3}" + "    "
            + (" " if damping is None else f"{damping:1d}")
            + f(pola, 10)
            + ("     " if ipola is None else f"{ipola:5d}")
            + f(kratio, 10))


def _prm(*, htype="PXCR", bank=1, icons=None,
         prcf_type=3, ncoef=19, cutoff="0.00100",
         coeffs=(1.0, -0.5, 0.2, 0.0, 0.15, 0.0, 0.0011, 0.0022,
                 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
         labels=None, per_line=4, extra_headers=()) -> str:
    """Build a synthetic ``.prm`` text, one dominant-case bank by default.

    ``coeffs`` are packed across ``PRCF11``..``PRCF1n`` continuation lines,
    ``per_line`` values to a line (the real corpus's own packing) — a
    **counted** layout: the header states ``ncoef`` and that is what a
    correct reader consumes, so a test can freely pass fewer ``coeffs`` than
    the header claims to exercise the short-file refusal, or more to exercise
    truncation.  ``labels`` optionally maps a 1-based coefficient position to
    an inline GSAS label token (``{1: "GU", 2: "GV", ...}``), reproducing the
    2-in-1500 real files that print one.  ``extra_headers`` inserts
    additional ``INS 1PRCF1 ...`` header lines *before* the coefficient lines
    of the (single) block built here, to exercise the "declared twice"
    refusal.
    """
    labels = labels or {}
    lines = [
        "INS   BANK  " + str(bank),
        "INS   HTYPE   " + htype,
        # no space after the key: the payload starts at column 12 and the
        # leading blanks of LAM1's F10.0 field are part of the field
        "INS  1 ICONS" + (_icons() if icons is None else icons),
        "INS  1 IRAD     0",
        "INS  1I HEAD  synthetic test fixture",
        "INS  1I ITYP    0    0.0000  180.0000         1",
    ]
    for h in extra_headers:
        lines.append(h)
    lines.append(f"INS  1PRCF1     {prcf_type}   {ncoef}   {cutoff}")
    for start in range(0, len(coeffs), per_line):
        chunk = coeffs[start:start + per_line]
        toks = []
        for i, v in enumerate(chunk, start=start + 1):
            if i in labels:
                toks.append(f"{labels[i]} {v:.6f}")
            else:
                toks.append(f"{v:.6f}")
        idx = start // per_line + 1
        lines.append(f"INS  1PRCF1{idx}   " + "   ".join(toks))
    return "\n".join(lines) + "\n"


def _synthetic_pntr(path):
    """A synthetic time-of-flight bank, shaped like the two real ``PNTR``
    files (``BNKPAR``, per-bank ``PRCF`` with a space before the coefficient
    index rather than the CW ``PRCF1n`` concatenation) but with invented
    numbers throughout.
    """
    text = (
        "INS   BANK  1\n"
        "INS   HTYPE   PNTR\n"
        "INS  1 ICONS    500.00     -0.10     -1.00\n"
        "INS  1BNKPAR    2.0000      9.00      0.00    .00000     .3000    1    1\n"
        "INS  1PRCF      2   15   0.00100\n"
        "INS  1PRCF 1   0.000000E+00   0.200000E+00   0.300000E+02   0.500000E+02\n"
        "INS  1PRCF 2   0.000000E+00   0.150000E+03   0.000000E+00   0.000000E+00\n"
        "INS  1PRCF 3   0.000000E+00   0.000000E+00   0.000000E+00   0.000000E+00\n"
        "INS  1PRCF 4   0.000000E+00   0.000000E+00   0.000000E+00\n"
    )
    path.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------- dominant case

def test_reads_the_dominant_case(tmp_path):
    """A single-bank PXCR / profile-type-3 file — the case the corpus is
    almost entirely made of (1499/1508 read successfully in the campaign's
    corpus run) — returns an ``Instrument`` with every field this reader maps.
    """
    p = tmp_path / "synthetic.prm"
    p.write_text(_prm(), encoding="utf-8")
    inst = read_gsas_prm(p)

    assert inst.source.primary_wavelength == pytest.approx(0.5)
    assert inst.source.polarization.value == pytest.approx(0.990)
    # GU/GV/GW: centidegrees^2 -> degrees^2 is /1e4; LX/LY: centidegrees -> degrees is /1e2
    assert inst.profile.u.value == pytest.approx(1.0 / 1e4)
    assert inst.profile.v.value == pytest.approx(-0.5 / 1e4)
    assert inst.profile.w.value == pytest.approx(0.2 / 1e4)
    assert inst.profile.x.value == pytest.approx(0.15 / 1e2)
    assert inst.profile.y.value == pytest.approx(0.0)
    assert inst.geometry.axial_sl.value == pytest.approx(0.0011)
    assert inst.geometry.axial_hl.value == pytest.approx(0.0022)
    assert inst.geometry.kind == "debye_scherrer"


def test_every_parameter_comes_back_frozen(tmp_path):
    """A ``.prm`` is a beamline calibration, not a starting guess — the same
    ``vary=False`` contract :func:`load_instrument_profile` gives its native
    JSON profiles.
    """
    p = tmp_path / "synthetic.prm"
    p.write_text(_prm(), encoding="utf-8")
    inst = read_gsas_prm(p)

    assert inst.zero_shift.vary is False
    assert inst.source.polarization.vary is False
    assert inst.profile.u.vary is False
    assert inst.profile.v.vary is False
    assert inst.profile.w.vary is False
    assert inst.profile.x.vary is False
    assert inst.profile.y.vary is False
    assert inst.geometry.axial_sl.vary is False
    assert inst.geometry.axial_hl.vary is False


def test_inline_coefficient_labels_are_prose_not_coefficients(tmp_path):
    """2 of 1500 real files print ``GU``/``GV``/``GW``/``LX``/``S/L``/``H/L``
    beside the numbers on the ``PRCF11``/``PRCF12`` lines.  The header's
    coefficient count is a count of **numbers**, so a label token must be
    skipped rather than consumed as one of them — otherwise every coefficient
    after the first label shifts by one position and the file reads as a
    different (wrong) instrument while raising nothing.
    """
    labelled = _prm(labels={1: "GU", 2: "GV", 3: "GW", 5: "LX",
                            7: "S/L", 8: "H/L"})
    bare = _prm()
    p1, p2 = tmp_path / "labelled.prm", tmp_path / "bare.prm"
    p1.write_text(labelled, encoding="utf-8")
    p2.write_text(bare, encoding="utf-8")

    a, b = read_gsas_prm(p1), read_gsas_prm(p2)
    assert a.profile.u.value == pytest.approx(b.profile.u.value)
    assert a.profile.v.value == pytest.approx(b.profile.v.value)
    assert a.profile.w.value == pytest.approx(b.profile.w.value)
    assert a.profile.x.value == pytest.approx(b.profile.x.value)
    assert a.geometry.axial_sl.value == pytest.approx(b.geometry.axial_sl.value)
    assert a.geometry.axial_hl.value == pytest.approx(b.geometry.axial_hl.value)


def test_short_counted_block_without_a_fifth_continuation_line(tmp_path):
    """The block is a **counted** layout: ``ncoef`` says how many numbers
    follow, not how many ``PRCF1n`` lines are present.  A file whose count
    only needs four continuation lines (no ``PRCF15``) must read exactly as
    well as a five-line one — the count governs, never the line that happens
    to be last.
    """
    coeffs = (1.0, -0.5, 0.2, 0.0, 0.15, 0.0, 0.0011, 0.0022,
              0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)  # 16 values, 4 lines of 4
    p = tmp_path / "short.prm"
    p.write_text(_prm(ncoef=16, coeffs=coeffs), encoding="utf-8")
    inst = read_gsas_prm(p)
    assert inst.profile.w.value == pytest.approx(0.2 / 1e4)
    assert inst.geometry.axial_hl.value == pytest.approx(0.0022)


def test_short_file_missing_declared_coefficients_raises(tmp_path):
    """The header claims more coefficients than the file actually supplies —
    a truncated write, or a hand edit that deleted a continuation line.
    Padding the missing values or reading whatever is present are both a
    plausible wrong instrument; raising is the only answer that is not.
    """
    p = tmp_path / "truncated.prm"
    # the header says 19, only 3 are given
    p.write_text(_prm(ncoef=19, coeffs=(1.0, -0.5, 0.2)), encoding="utf-8")
    with pytest.raises(ValueError, match="declares 19 coefficients but only"):
        read_gsas_prm(p)


# ----------------------------------------------------------------- refusals

def test_pntr_time_of_flight_is_refused_by_name(tmp_path):
    p = _synthetic_pntr(tmp_path / "tof.prm")
    with pytest.raises(ValueError, match="(?i)time-of-flight"):
        read_gsas_prm(p)


@pytest.mark.parametrize("prof_type", [1, 2, 4])
def test_unsupported_prcf_profile_types_are_refused_by_name(tmp_path, prof_type):
    """Types 1, 2 and 4 each have their own, independently-defined Fortran
    coefficient layout in the GSAS manual — none is a truncation or extension
    of type 3's — and no real (non-template) file of any of them was found in
    the corpus this reader was built against, so none is read.
    """
    p = tmp_path / f"type{prof_type}.prm"
    p.write_text(_prm(prcf_type=prof_type, ncoef=6,
                      coeffs=(1.0, -0.5, 0.2, 0.0, 0.15, 0.0)),
                 encoding="utf-8")
    with pytest.raises(ValueError, match=str(prof_type)):
        read_gsas_prm(p)


def test_unrecognised_htype_is_refused_by_name(tmp_path):
    p = tmp_path / "mystery.prm"
    p.write_text(_prm(htype="QSTEP"), encoding="utf-8")
    with pytest.raises(ValueError, match="QSTEP"):
        read_gsas_prm(p)


def test_a_file_with_no_bank_or_htype_record_raises(tmp_path):
    """Junk that merely carries a ``.prm`` suffix (5 of the 1508 real
    filenames scanned in the campaign's corpus run turned out to be unrelated
    tab-separated data, one a raw resource-fork attachment) must not be
    silently accepted as an empty or default instrument."""
    p = tmp_path / "not_really_a_prm.prm"
    p.write_text("just some\ntext\tfile\t1\t2\t3\n" * 5, encoding="utf-8")
    with pytest.raises(ValueError, match="not a GSAS-I instrument-parameter file"):
        read_gsas_prm(p)


def test_multi_bank_pxcr_is_refused(tmp_path):
    """Every real ``PXCR`` file in the corpus declares exactly one bank; a
    declared bank count of anything else has no real fixture behind it, so
    reading only the first bank (silently dropping the rest) is refused."""
    p = tmp_path / "multibank.prm"
    p.write_text(_prm(bank=2), encoding="utf-8")
    with pytest.raises(ValueError, match="BANK 2"):
        read_gsas_prm(p)


def test_duplicate_prcf1_header_for_one_bank_is_refused(tmp_path):
    """The one real file that declares its profile function twice under one
    bank (a stock GSAS example stacking types 2/3/4 with placeholder values)
    is ambiguous about which applies — refused rather than picking the first
    or the last silently."""
    p = tmp_path / "duplicate.prm"
    p.write_text(_prm(extra_headers=("INS  1PRCF1     3   19   0.00100",
                                     "INS  1PRCF11   0.0   0.0   0.0   0.0",
                                     "INS  1PRCF12   0.0   0.0   0.0   0.0",
                                     "INS  1PRCF13   0.0   0.0   0.0   0.0",
                                     "INS  1PRCF14   0.0   0.0   0.0   0.0",
                                     "INS  1PRCF15   0.0   0.0   0.0")),
                 encoding="utf-8")
    with pytest.raises(ValueError, match="more than once"):
        read_gsas_prm(p)


def test_a_written_idamp_does_not_move_the_fields_after_it(tmp_path):
    """The bug this reader's record layer was rewritten for (WP-1118).

    ``ICONS`` is fixed-format and its ``IREF``/``IDAMP`` fields are optional.
    Every 11-BM file in ``tests/data`` leaves them blank, so the record splits
    into six tokens that happen to land on the right meanings; ``INST_XRY.PRM``
    writes ``IDAMP`` and splits into seven that do not, and the old reader
    refused it for the count.  Read by column the two records give the *same*
    instrument, which is the property a token count cannot have.
    """
    plain = tmp_path / "blank_idamp.prm"
    written = tmp_path / "written_idamp.prm"
    plain.write_text(_prm(icons=_icons(pola=0.7, kratio=0.5)), encoding="utf-8")
    written.write_text(_prm(icons=_icons(pola=0.7, kratio=0.5, damping=0)),
                       encoding="utf-8")

    assert read_gsas_prm(plain) == read_gsas_prm(written)
    assert read_gsas_prm(written).source.polarization.value == pytest.approx(0.7)


def test_a_doublet_is_read_with_kratio_as_the_second_lines_weight(tmp_path):
    """A second wavelength used to be refused for want of a convention, and
    that want was an artefact of not knowing which field ``KRATIO`` was.

    Located by column it is unambiguous: ``EmissionLine.weight`` is the
    intensity of a line relative to the first, which is exactly the Kα2/Kα1
    ratio GSAS writes there.  The polarization two fields earlier is also
    conventionally 0.5, so this fixture states 0.7 and 0.5 to tell them apart —
    the same separation ``INST_XRY.PRM`` gives against ``FAP.EXP``.
    """
    p = tmp_path / "doublet.prm"
    p.write_text(_prm(icons=_icons(lam1=1.5405, lam2=1.5443, damping=0,
                                   pola=0.7, kratio=0.5)),
                 encoding="utf-8")
    inst = read_gsas_prm(p)

    lines = inst.source.lines
    assert [ln.wavelength.value for ln in lines] == pytest.approx([1.5405, 1.5443])
    assert lines[0].weight.value == 1.0, "line 0's weight is pinned by convention"
    assert lines[1].weight.value == pytest.approx(0.5)
    assert inst.source.polarization.value == pytest.approx(0.7)
    assert all(not ln.weight.vary for ln in lines), (
        "a .prm is a calibration, so every parameter comes back frozen")


def test_a_doublet_without_a_ratio_to_weight_it_by_is_refused(tmp_path):
    """``FAP.EXP`` states a doublet and leaves ``KRATIO`` blank, so a file of
    that shape states a line whose intensity it never gives.  Supplying the
    conventional 0.5 would be this reader's number rather than the file's.
    """
    p = tmp_path / "unweighted.prm"
    p.write_text(_prm(icons=_icons(lam1=1.5405, lam2=1.5443, kratio=None)),
                 encoding="utf-8")
    with pytest.raises(ValueError, match="KRATIO"):
        read_gsas_prm(p)


def test_a_ratio_outside_the_weight_range_is_refused(tmp_path):
    p = tmp_path / "wild_ratio.prm"
    p.write_text(_prm(icons=_icons(lam1=1.5405, lam2=1.5443, kratio=17.0)),
                 encoding="utf-8")
    with pytest.raises(ValueError, match="KRATIO"):
        read_gsas_prm(p)


def test_nonzero_zero_point_is_refused(tmp_path):
    """ICONS ``ZERO`` has a disputed unit convention (``io/recipe.py``'s
    ``_read_zero_shift``) and no real file in the corpus has a non-zero value
    to settle it against — refused rather than mapped on either guess."""
    p = tmp_path / "nonzero_zero.prm"
    p.write_text(_prm(icons=_icons(zero=0.0123)), encoding="utf-8")
    with pytest.raises(ValueError, match="ZERO"):
        read_gsas_prm(p)


def test_nonzero_polarization_type_is_refused(tmp_path):
    """``IPOLA`` selects which polarization convention ``POLA`` is stated in.
    Reading POLA under a type this reader cannot name would apply the right
    number the wrong way, so a non-zero one is refused rather than ignored."""
    p = tmp_path / "ipola.prm"
    p.write_text(_prm(icons=_icons(ipola=7)), encoding="utf-8")
    with pytest.raises(ValueError, match="IPOLA"):
        read_gsas_prm(p)


def test_a_blank_primary_wavelength_is_refused(tmp_path):
    p = tmp_path / "no_lam1.prm"
    p.write_text(_prm(icons=_icons(lam1=None)), encoding="utf-8")
    with pytest.raises(ValueError, match="no primary wavelength"):
        read_gsas_prm(p)


def test_a_blank_polarization_is_refused_rather_than_defaulted(tmp_path):
    """Reading by column makes a blank field reachable where a six-token split
    refused the whole record, so each one needs its own answer.

    ``Instrument.debye_scherrer`` has a ``polarization`` default of 0.99 and it
    is exactly what the corpus states, which is what would make falling back on
    it invisible: the caller would read this package's number as the file's.
    """
    p = tmp_path / "no_pola.prm"
    p.write_text(_prm(icons=_icons(pola=None)), encoding="utf-8")
    with pytest.raises(ValueError, match="no polarization"):
        read_gsas_prm(p)


def test_a_blank_profile_function_type_is_refused(tmp_path):
    """Same reachability, one record along.  A ``PRCF1`` header with no type
    names none of its coefficients, and the types disagree about position 4.
    """
    p = tmp_path / "no_type.prm"
    text = _prm().replace("INS  1PRCF1     3", "INS  1PRCF1      ")
    p.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="no profile function type"):
        read_gsas_prm(p)


def test_nonzero_gp_coefficient_is_refused(tmp_path):
    """PRCF position 4 (GSAS ``GP``) is always 0 in every real file this
    reader was built against and has no mapping onto ``ProfileTCHZ`` — a
    non-zero value is refused rather than silently dropped."""
    coeffs = (1.0, -0.5, 0.2, 0.9, 0.15, 0.0, 0.0011, 0.0022,
              0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    p = tmp_path / "nonzero_gp.prm"
    p.write_text(_prm(coeffs=coeffs), encoding="utf-8")
    with pytest.raises(ValueError, match="'GP'"):
        read_gsas_prm(p)


def test_nonzero_reserved_prcf_term_is_refused(tmp_path):
    """Every coefficient past position 8 (``trns``/``shft``/``sfec`` and
    further reserved slots) is 0 in every real type-3 file this reader was
    checked against (1499/1499 in the campaign's corpus scan) — a non-zero
    one here is unidentified, not dropped."""
    coeffs = (1.0, -0.5, 0.2, 0.0, 0.15, 0.0, 0.0011, 0.0022,
              0.0, 0.0, 0.4, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    p = tmp_path / "nonzero_reserved.prm"
    p.write_text(_prm(coeffs=coeffs), encoding="utf-8")
    with pytest.raises(ValueError, match="coefficient 11 of 19"):
        read_gsas_prm(p)


@pytest.mark.parametrize("what, kwargs", [
    # a .prm states GW signed and ProfileTCHZ.w is non-negative
    ("negative GW", {"coeffs": (1.0, -0.5, -0.4, 0.0, 0.15, 0.0, 0.0011,
                                0.0022) + (0.0,) * 11}),
    # a GU wide enough to leave ProfileTCHZ.u's [-0.05, 1.0]
    ("a GU past its range", {"coeffs": (2e4, -0.5, 0.2, 0.0, 0.15, 0.0, 0.0011,
                                        0.0022) + (0.0,) * 11}),
    # POLA on some other convention's 0-100 scale, where Source.polarization
    # holds a fraction
    ("a POLA past 1", {"icons": _icons(pola=99.0)}),
    ("a negative LAM1", {"icons": _icons(lam1=-0.5)}),
    ("a negative LAM2", {"icons": _icons(lam2=-1.5443, kratio=0.5)}),
])
def test_a_value_outside_the_schemas_range_is_refused_naming_the_file(
        tmp_path, what, kwargs):
    """``io/CLAUDE.md`` § Refusals: a reader raises naming the file, never its
    parser's exception.

    ``Base`` validates on assignment, so every one of these used to escape as
    pydantic's report on a ``Parameter`` — no file name in it, and, worse, the
    ``diagnostics`` list already carrying rows about a file the caller never
    received, which is exactly what the emission site's comment promises
    cannot happen.
    """
    p = tmp_path / "out_of_range.prm"
    p.write_text(_prm(**kwargs), encoding="utf-8")
    notes: list = []
    with pytest.raises(ValueError, match=r"out_of_range\.prm") as caught:
        read_gsas_prm(p, diagnostics=notes)
    assert type(caught.value) is ValueError, (
        f"{what}: a schema error is converted at the reader's boundary, not "
        f"handed on")
    assert notes == [], (
        f"{what}: a file about to be refused leaves no half-list behind")


def test_read_gsas_prm_is_exported_at_top_level():
    assert rx.read_gsas_prm is read_gsas_prm


def test_a_label_belonging_to_another_profile_function_is_refused(tmp_path):
    """A label token is skipped because it is prose beside its own number.

    ``asym`` is function 1's fourth coefficient and no name of function 3, so
    a type-3 record printing it is a file this reader has misunderstood —
    skipping it would silently shorten the list and rename every coefficient
    after it, which is the whole hazard the counted layout exists to stop.
    """
    p = tmp_path / "wrong_label.prm"
    p.write_text(_prm(labels={1: "asym"}), encoding="utf-8")
    with pytest.raises(ValueError, match="unrecognised token"):
        read_gsas_prm(p)


def test_the_mapped_coefficients_are_the_one_tables_own_names():
    """The eight this reader maps are named from ``CW_PROFILE_COEFFICIENTS``.

    The names are asserted literally here and the reader derives them, which is
    the way round that makes a rename visible: two readers unpacking one
    coefficient order from two lists is how they come to disagree, and a
    structural check (``the slice equals the slice``) would pass however the
    table changed.
    """
    assert _PRCF_MAPPED == ("GU", "GV", "GW", "GP", "LX", "LY", "S/L", "H/L")
    assert CW_PROFILE_COEFFICIENTS[3][:len(_PRCF_MAPPED)] == _PRCF_MAPPED

# -- the diagnostics channel, and the committed files nothing was reading ----

DATA = Path(__file__).parent / "data"


def test_the_two_gsas_readers_read_one_icons_record_the_same_way():
    """``ICONS`` is a GSAS record, not a ``.prm`` one or a ``.EXP`` one.

    ``INST_XRY.PRM`` and ``FAP.EXP`` state the same Cu doublet and differ in
    exactly the field that used to be unreadable.  The ``.EXP`` leaves
    ``KRATIO`` blank, so its 0.5 is the *polarization*; the ``.prm`` states
    ``POLA`` 0.7 **and** ``KRATIO`` 0.5 in the same two slots.  Both
    quantities are conventionally 0.5, which is how a reader taking the wrong
    field agrees with the right one on one of these files and disagrees on the
    other — so both go through the one record reader (WP-1118).
    """
    payload = next(
        pay for key, pay in
        split_records((DATA / "INST_XRY.PRM").read_bytes().decode("latin-1"))
        if key[6:].strip().upper() == "ICONS")
    prm = read_icons(payload)
    exp = rx.read_gsas_exp(DATA / "FAP.EXP").histograms[0]

    assert exp.wavelengths == pytest.approx(prm.wavelengths)
    assert exp.polarization == pytest.approx(0.5)
    assert exp.ka2_ratio is None, "FAP.EXP leaves KRATIO blank"
    assert prm.polarization == pytest.approx(0.7)
    assert prm.ka2_ratio == pytest.approx(0.5)


def test_the_file_that_writes_idamp_gets_past_its_record():
    """``INST_XRY.PRM`` is refused for what is wrong with it, not for a count.

    It was refused for a seven-token ``ICONS``; read by column that record is
    fine, and the refusal is now its ``GP`` of 0.1 — one of the stock GSAS
    placeholder profile values (``GU`` 2, ``GV`` −2, ``GW`` 5) this file
    carries, which is a real reason not to return it as a calibration.
    """
    with pytest.raises(ValueError, match="'GP'"):
        read_gsas_prm(DATA / "INST_XRY.PRM")


def test_the_channel_reports_what_the_instrument_does_not_carry():
    """``io/CLAUDE.md``: a value at the model's identity is dropped **with a
    diagnostic**, a non-zero one raises.  The reader had only the refusal half,
    so a caller could not learn that the file said something the ``Instrument``
    does not carry — including ``KRATIO``, which weights a second emission line
    and so has nothing to do on a file stating one wavelength.
    """
    diagnostics: list = []
    ins = read_gsas_prm(DATA / "mg090.prm", diagnostics=diagnostics)

    dropped = [d for d in diagnostics if d.code == "GSAS_PRM_FIELD_DROPPED"]
    assert {tuple(d.where) for d in dropped} == {("ICONS",), ("PRCF",),
                                                 ("IRAD/ITYP",)}
    assert all(d.level == "info" for d in dropped), (
        "a field at the model's identity is reported, not warned about — the "
        "file agreed with the model")
    icons = next(d for d in dropped if d.where == ["ICONS"])
    assert "KRATIO" in icons.message and "not applied" in icons.message
    assert "IPOLA" in icons.message and "IDAMP" in icons.message, (
        "the row names every ICONS field the Instrument does not carry, and "
        "reading the record by column is what made IDAMP one of them")

    # …and the same read with no list passed returns the same instrument in
    # silence, which is what makes the channel opt-in rather than a behaviour
    # change (`io/CLAUDE.md`'s own contract for every other reader here).
    assert read_gsas_prm(DATA / "mg090.prm") == ins


def test_a_drop_is_only_reported_for_a_record_the_file_carried(tmp_path):
    """Round two, item 1.  The three rows were built unconditionally, so two
    of them described files that said no such thing: a ``.prm`` with no
    ``IRAD``/``ITYP`` still got the "ignored by design" row, and a ``PRCF``
    declaring exactly eight coefficients still got "0 coefficient(s) past
    position 8".  The rule the channel implements is about a value **the file
    carried** being dropped at the model's identity; a row about a record that
    is absent is a defaulted field answering a question nobody asked
    (WP-1076), and it is ``info``, so the corpus would keep it invisible.
    """
    # a file carrying neither record: no IRAD/ITYP row at all
    text = _prm()
    without = "\n".join(ln for ln in text.splitlines()
                        if "IRAD" not in ln and "ITYP" not in ln) + "\n"
    assert "IRAD" not in without and "ITYP" not in without
    path = tmp_path / "no_irad.prm"
    path.write_text(without, encoding="utf-8")
    diagnostics: list = []
    read_gsas_prm(path, diagnostics=diagnostics)
    where = {tuple(d.where) for d in diagnostics
             if d.code == "GSAS_PRM_FIELD_DROPPED"}
    assert ("IRAD/ITYP",) not in where
    assert ("ICONS",) in where and ("PRCF",) in where   # the two real ones

    # …and the row is still there for a file that does carry one
    both = tmp_path / "with_irad.prm"
    both.write_text(_prm(), encoding="utf-8")
    diagnostics = []
    read_gsas_prm(both, diagnostics=diagnostics)
    assert ("IRAD/ITYP",) in {tuple(d.where) for d in diagnostics
                              if d.code == "GSAS_PRM_FIELD_DROPPED"}


def test_no_coefficients_past_eight_is_not_reported_as_a_drop(tmp_path):
    """The other half of round two's item 1: a ``PRCF`` declaring exactly
    eight coefficients has nothing past position 8, and the message said
    "0 coefficient(s) past position 8 = 0" — a drop that did not happen.
    ``GP`` at position 4 is genuinely read and dropped either way, so the row
    itself stays."""
    eight = _prm(ncoef=8, coeffs=(1.0, -0.5, 0.2, 0.0, 0.15, 0.0, 0.0011,
                                  0.0022))
    p8 = tmp_path / "eight.prm"
    p8.write_text(eight, encoding="utf-8")
    diagnostics: list = []
    read_gsas_prm(p8, diagnostics=diagnostics)
    prcf = next(d for d in diagnostics
                if d.code == "GSAS_PRM_FIELD_DROPPED" and d.where == ["PRCF"])
    assert "past position 8" not in prcf.message
    assert "GP (position 4)" in prcf.message

    p19 = tmp_path / "nineteen.prm"
    p19.write_text(_prm(), encoding="utf-8")
    nineteen: list = []
    read_gsas_prm(p19, diagnostics=nineteen)
    prcf = next(d for d in nineteen
                if d.code == "GSAS_PRM_FIELD_DROPPED" and d.where == ["PRCF"])
    assert "11 coefficient(s) past position 8" in prcf.message


def test_the_geometry_is_chosen_rather_than_read_and_says_so():
    """A ``.prm`` states no geometry at all, and ``HTYPE PXCR`` spans
    Bragg-Brentano and Debye-Scherrer.  The reader picks the capillary its
    corpus is and must say so, because ``Geometry.kind`` selects the position
    correction and the two geometries' absorption corrections have different
    *off* states (``mu_r = 0`` against ``mu_t = inf``) — so a flat-plate
    calibration read in silence arrives with the wrong half of that machinery
    armed.
    """
    diagnostics: list = []
    ins = read_gsas_prm(DATA / "mg090.prm", diagnostics=diagnostics)
    assert ins.geometry.kind == "debye_scherrer"

    assumed = [d for d in diagnostics if d.code == "GSAS_PRM_GEOMETRY_ASSUMED"]
    assert len(assumed) == 1, "fires on every read, not only on a suspect file"
    assert assumed[0].level == "warning"
    assert assumed[0].where == ["instrument.geometry.kind"]
    assert "not read from the file" in assumed[0].message
    assert "flat-plate" in (assumed[0].suggestion or "")


def test_a_refusal_leaves_no_half_list_on_the_callers_list():
    """Every diagnostic is emitted past the last refusal, so a file that is
    about to raise does not also leave findings behind."""
    diagnostics: list = []
    with pytest.raises(ValueError):
        read_gsas_prm(DATA / "mg090.Cu311.inst", diagnostics=diagnostics)
    assert diagnostics == []


def test_the_one_real_non_pxcr_file_in_the_repo_is_refused_for_the_true_reason():
    """``tests/data/mg090.Cu311.inst`` is ``HTYPE PNCR`` — powder neutron,
    **constant wavelength** — and ``tests/data/README.md`` documents it as the
    ndruo pair's neutron instrument file, which
    ``test_acceptance_wavelength.py`` transcribes by hand today.

    Its meaning is established, so the catch-all "what this file's HTYPE means
    is not established at all" was false of it: ``ProfileTCHZ`` is exactly
    where ``Instrument.constant_wavelength_neutron`` puts its own resolution
    function.  Refusing is still right, for the reason used everywhere else in
    this reader — its ``PRCF`` is type 1 and no real file pins that layout
    down.  The refusal has to say *that*.
    """
    with pytest.raises(ValueError, match="PNCR") as exc:
        read_gsas_prm(DATA / "mg090.Cu311.inst")
    message = str(exc.value)
    assert "constant-wavelength" in message
    assert "type 1" in message, "the refusal must name the missing fixture"
    assert "not established at all" not in message, (
        "PNCR is recognised by name; the catch-all branch is for values the "
        "manual does not define")


def test_a_non_numeric_icons_field_names_the_file(tmp_path):
    """``io/CLAUDE.md``: a reader raises ``ValueError``/``OSError`` **naming
    the file**, never its parser's own exception.  ``_read_icons`` ended in a
    bare ``float()`` generator, so a text token in the wavelength field gave
    ``could not convert string to float: 'ABCDEFGHI'`` — no file, no format,
    nothing a caller could act on."""
    p = tmp_path / "bad_icons.prm"
    p.write_text(_prm(icons="ABCDEFGHI    0.0000    0.0000"
                            "               0.990    0     0.500"),
                 encoding="utf-8")
    with pytest.raises(ValueError, match="bad_icons.prm") as exc:
        read_gsas_prm(p)
    assert "not a number" in str(exc.value)
    assert "could not convert string to float" not in str(exc.value)


def test_the_unit_conversion_agrees_with_the_hand_transcription():
    """The one thing a synthetic fixture cannot check.

    Every other test here builds its own ``.prm`` text, so fixture and
    conversion come from the same assumption: flip ``/1e4`` to ``/1e2`` and
    ``test_reads_the_dominant_case`` would simply be edited to stay green.
    This compares the reader against a transcription made independently of it
    — ``test_acceptance_wavelength._xray_instrument``, which was typed from
    ``mg090.prm``'s own ``PRCF`` record before this reader existed — so the two
    have to agree or one of them is wrong.  WP-1118's task for this reader,
    one file over: take the protocol from the reader instead of from
    transcribed constants.
    """
    from tests.test_acceptance_wavelength import LAM_XRAY, _xray_instrument

    read = read_gsas_prm(DATA / "mg090.prm")
    hand = _xray_instrument()

    assert read.source.lines[0].wavelength.value == pytest.approx(LAM_XRAY)
    for term in ("u", "v", "w", "x", "y"):
        assert getattr(read.profile, term).value == pytest.approx(
            getattr(hand.profile, term).value), (
            f"profile.{term}: reader and hand transcription disagree")
    # The axial pair is where the two *stop* agreeing, and the reader is the
    # one that is right: mg090.prm states S/L = H/L = 0.0011 at PRCF positions
    # 7 and 8, and the hand transcription sets neither, so it models an
    # instrument with no axial divergence at all.  Asserted as the asymmetry
    # rather than as equality, because equality is false and the direction of
    # the difference is the point — it is the argument for that suite taking
    # its profile from this reader.
    assert read.geometry.axial_sl.value == pytest.approx(0.0011)
    assert read.geometry.axial_hl.value == pytest.approx(0.0011)
    assert hand.geometry.axial_sl.value == 0.0
    assert hand.geometry.axial_hl.value == 0.0


def test_a_short_type_3_prcf_is_refused_by_name_not_by_its_unpack(tmp_path):
    """Round three's item 1: the same defect as round one's item 3, one
    function up from where that was fixed.

    ``_read_prcf`` returns exactly ``ncoef`` coefficients and guarantees
    nothing about how many that is, so a type-3 header declaring six passes
    the type gate and reaches ``gu, gv, gw, gp, lx, ly, sl, hl, *rest =
    coeffs``.  On the parent commit that escapes as ``ValueError: not enough
    values to unpack (expected at least 8, got 6)`` — no file name, no
    format, nothing a caller can act on, against ``io/CLAUDE.md``'s rule that
    a reader raises naming the file and never its parser's exception.
    Reported by @yue-here, who measured it on the merged tree.

    ``_read_icons`` twelve lines down is the model answer: check the length
    **before** the unpack and refuse naming the file and the layout.
    """
    short = tmp_path / "short.prm"
    short.write_text(_prm(ncoef=6, coeffs=(1.0, -0.5, 0.2, 0.0, 0.15, 0.0)),
                     encoding="utf-8")
    with pytest.raises(ValueError) as excinfo:
        read_gsas_prm(short)
    message = str(excinfo.value)

    assert "not enough values to unpack" not in message
    assert "short.prm" in message
    assert "6 coefficient(s)" in message
    assert "GU GV GW GP LX LY S/L H/L" in message

    # The positive arm: a header declaring exactly the eight the mapping
    # needs is not caught by the guard, so this refuses a short *header*
    # rather than refusing type 3.
    eight = tmp_path / "eight.prm"
    eight.write_text(_prm(ncoef=8, coeffs=(1.0, -0.5, 0.2, 0.0, 0.15, 0.0,
                                           0.0011, 0.0022)), encoding="utf-8")
    ins = read_gsas_prm(eight)
    assert ins.geometry.axial_sl.value == pytest.approx(0.0011)

    # …and the guard is above the short-*file* refusal it resembles, which is
    # a different question: a header declaring 19 with only 6 present is
    # still refused for the count it declared, not for the mapping.
    truncated = tmp_path / "truncated.prm"
    truncated.write_text(_prm(ncoef=19, coeffs=(1.0, -0.5, 0.2, 0.0, 0.15,
                                                0.0)), encoding="utf-8")
    with pytest.raises(ValueError, match="declares 19 coefficients but only"):
        read_gsas_prm(truncated)


def test_the_geometry_warning_says_to_carry_the_axial_terms_over():
    """Round three's item 2.  Two of the eight coefficients land on the
    object the reader admits it invented, and the diagnostic's own remedy
    silently discarded them.

    ``S/L``/``H/L`` (PRCF positions 7-8) are written to
    ``geometry.axial_sl``/``axial_hl``, not to the profile.  So
    ``GSAS_PRM_GEOMETRY_ASSUMED`` warns that the geometry was not read from
    the file while that same geometry carries two values that were, and its
    suggestion said "set the geometry yourself" — which costs a caller the
    file's axial divergence, giving the instrument with **none at all** that
    ``test_the_unit_conversion_agrees_with_the_hand_transcription`` ends by
    asserting against.  Measured and reported by @yue-here.
    """
    diagnostics: list = []
    ins = read_gsas_prm(DATA / "mg090.prm", diagnostics=diagnostics)
    assumed = next(d for d in diagnostics
                   if d.code == "GSAS_PRM_GEOMETRY_ASSUMED")

    # what is actually at stake, from the file
    assert ins.geometry.axial_sl.value == pytest.approx(0.0011)
    assert ins.geometry.axial_hl.value == pytest.approx(0.0011)

    # a fresh geometry of the kind the suggestion sends you to has neither
    flat = rx.Instrument.bragg_brentano()
    assert flat.geometry.axial_sl.value == 0.0
    assert flat.geometry.axial_hl.value == 0.0

    # …so the suggestion has to name them, and say they came from the file
    assert "axial_sl" in assumed.suggestion
    assert "axial_hl" in assumed.suggestion
    assert "no axial divergence" in assumed.suggestion

    # `where` still names only what was assumed.  The axial terms were read,
    # not assumed, so listing them there would be the opposite error.
    assert assumed.where == ["instrument.geometry.kind"]


def test_the_prcf_drop_row_names_both_objects_the_eight_land_on():
    """The docstring said "the eight coefficients this package's *profile*
    has room for", and the emitted ``PRCF`` row said "this reader maps
    positions 1-8 onto ProfileTCHZ".  Neither is true of positions 7-8, which
    are the two that reach ``Geometry`` — and that was the only clue in the
    tree about where they land, which is what made round three's item 2
    invisible.  The agent skill's own row (``diagnostics-projects.md``) had it
    right all along: "what ``ProfileTCHZ`` and ``Geometry`` have room for"."""
    diagnostics: list = []
    read_gsas_prm(DATA / "mg090.prm", diagnostics=diagnostics)
    prcf = next(d for d in diagnostics
                if d.code == "GSAS_PRM_FIELD_DROPPED" and d.where == ["PRCF"])
    assert "onto ProfileTCHZ and 7-8 (S/L, H/L) onto Geometry" in prcf.message
    assert "positions 1-8 onto ProfileTCHZ" not in prcf.message
def test_the_bank_count_is_read_at_its_column(tmp_path):
    """``BANK`` is ``I5``, so anything after the count is not part of it.

    Read by stripping the whole payload, a record carrying a comment after its
    number is not a digit string, and the refusal then says "no BANK/HTYPE
    record found" about a file that has one. Found by the review pass on
    WP-1118's `.gpx` branch: it is the one record in this module that was not
    read by column, in a module whose whole thesis is that they are.
    """
    text = _prm().replace("INS   BANK  1", "INS   BANK  1    ID 11-BM-B")
    path = tmp_path / "commented.prm"
    path.write_text(text, encoding="latin-1")
    instrument = read_gsas_prm(path)
    assert instrument.source.lines[0].wavelength.value > 0
