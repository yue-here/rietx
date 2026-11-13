"""What the readers do to files that are *wrong*, not merely unfamiliar.

Every reader in this package is handed bytes somebody else wrote — increasingly
so, since the vendor formats are containers (zip members, XML trees, binary TLV
segments) written by instrument software this project does not own.  A container
parser's natural failure mode is its *library's* exception: ``struct.error``,
``zipfile.BadZipFile``, ``ET.ParseError``.  None of those is a
``ValueError``/``OSError``, and ``ET.ParseError`` subclasses ``SyntaxError``, so
one escaping a reader is a traceback on an API caller and a 500 on the GUI's
upload route rather than "this file could not be read".

So there is one cross-cutting invariant, asserted here rather than trusted:

    **a reader raises ``ValueError`` or ``OSError``, and names the file.**

The harness that earns its keep is truncation — the cheapest way to produce a
file that is *structurally* broken at an arbitrary depth rather than merely
odd, which is what a half-finished copy, an interrupted download and a
network-mounted instrument share drive all produce for real.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.io.readers import identify_format

DATA = Path(__file__).parent / "data"

#: Every *real* fixture a pattern reader claims, with the reader that claims it.
#: One per reader rather than one per file: the point is to exercise each
#: parser's failure paths, and thirty round-robin ``.prn`` files share one.
REAL_FIXTURES = [
    ("11BM_NAC.fxye", "gsas"),            # GSAS FXYE, 2.5 MB, esd column
    ("FAP.XRA", "gsas"),                  # GSAS STD, fixed-format, Poisson
    ("mg090.Cu311.gsas", "gsas"),         # GSAS ESD, 8-char positional fields
    ("nist_srm660c_100a.cif", "pdcif"),   # pdCIF through gemmi, two blocks
    ("cod_2242872.cif", "pdcif"),         # pdCIF, a net column + weights, 173 kB
    ("qarr/corundum.prn", "xy"),          # two-column ASCII
    ("rigaku_nims.ras", "ras"),           # Rigaku text, marked sections
    ("panalytical_powder.xrdml", "xrdml"),      # XRDML 1.6, one scan, counts
    ("panalytical_mesh.xrdml", "xrdml"),        # XRDML 2.1, 101 scans, listPositions
    ("rigaku_powder.rasx", "rasx"),             # a zip container: BOM'd members
    ("bruker_absorber.brml", "brml"),           # a zip of XML, 4.5 MB unread
    ("bruker_raw4_scrambled.raw", "bruker_raw"),  # binary TLV, one range, 7134 pts
    ("qarr/corundum.rd", "philips_rd"),    # Philips V3, 250-byte header, packed
    ("gsas2_pbso4.gpx", "gsas2_gpx"),      # GSAS-II pickle stream, two histograms
]

#: Formats with **no vendorable real file**, built here instead.  Kept apart from
#: the list above rather than mixed into it, because a synthesized file exercises
#: the parser's failure paths and says nothing about the format: it is written
#: from the same understanding the reader was, so the two agree by construction.
#: ``.uxd`` is here because every obtainable real one is GPL or carries no
#: licence at all; ``.rasx`` for a different reason — a real one is vendored and
#: truncated above, but the only real *multi-scan* archive is 2.3 MB, so the
#: several-groups failure paths are reached synthetically
#: (``tests/data/README.md`` names both).  ``raw4`` is here for a third reason
#: again — a real one *is* vendored and truncated above, but it holds one range,
#: and a cut through the second range of a two-range file is a different depth
#: to fail at: the first range has already parsed and returned by then.
#: ``raw3`` is the plainest case: **no** real file exists, from any source, so
#: this arm is the only truncation coverage that format has.
#: ``gsas_esd`` is a fifth reason: a real ESD bank *is* vendored and truncated
#: above (``mg090.Cu311.gsas``), but the ESD field's failure mode only appears
#: once a value **fills** all eight of its characters, and no vendored bank has
#: one — ``mg090.Cu311.gsas`` peaks at 14 476 written without decimals
#: (``14476.``, six characters).  The APS 11-BM patterns that do reach the edge
#: are not redistributable (``tests/data/README.md`` § GSAS ESD), so the layout
#: is packed here instead.
#: ``udf`` is a sixth reason: a vendorable fixture *does* exist (PyXRD's inline
#: one, BSD-2) but it is 33 points and five keys, so cutting it reaches almost
#: none of the header; all 56 real files are unlicensed, so the full 19-key
#: header is synthesized here from the table in ``tests/data/README.md``.
#: ``philips_v5`` is the ``raw3`` case exactly: a real **V3** ``.rd`` is
#: vendored and truncated above, but **no V5 file exists anywhere**, and V5's
#: header is 810 bytes against V3's 250 — so a cut lands at depths the V3 file
#: cannot reach, and this arm is the only truncation coverage that version has.
SYNTHETIC_FIXTURES = ["uxd", "rasx", "brml", "raw4", "raw3", "raw2", "gsas_esd",
                      "udf", "philips_v5"]


def _synthesize(kind: str, path: Path) -> Path:
    from tests.test_readers import (
        write_brml,
        write_gsas_esd,
        write_rasx,
        write_udf,
        write_uxd,
    )
    from tests.writers_xrd import (
        CORUNDUM_HEAD,
        write_philips_rd,
        write_raw2,
        write_raw3,
        write_raw4,
    )

    if kind == "udf":
        return write_udf(path, [500 + i % 7 for i in range(400)])
    if kind == "philips_v5":
        # 400 points of real counts, so the 810-byte header and a long data
        # block are both deep enough for a cut to land inside either
        return write_philips_rd(path, CORUNDUM_HEAD * 34, version=b"V5RD")

    if kind == "gsas_esd":
        # every fifth channel fills its 8-character field, so a cut lands
        # inside a fused pair as well as inside an ordinary one
        return write_gsas_esd(
            path,
            [101641.3 if i % 5 == 4 else 500.0 + i % 7 for i in range(200)],
            [318.8 if i % 5 == 4 else 22.0 + i % 3 for i in range(200)])
    if kind == "raw3":
        # extra records in the second range, so a cut can land between a header
        # and the data it declares rather than only inside one of them
        return write_raw3(path, [
            dict(start=10.0, step=0.02,
                 intensity=[500.0 + i % 7 for i in range(200)]),
            dict(start=40.0, step=0.02, extras=[(100, 40), (110, 32)],
                 intensity=[300.0 + i % 5 for i in range(200)])])
    if kind == "raw2":
        # the real file is local-only, so this arm is v2's truncation coverage
        return write_raw2(path, [500.0 + i % 7 for i in range(200)])
    if kind == "raw4":
        return write_raw4(path, [
            dict(start=10.0, step=0.02,
                 intensity=[500.0 + i % 7 for i in range(200)]),
            dict(start=40.0, step=0.02,
                 intensity=[300.0 + i % 5 for i in range(200)])])
    if kind == "uxd":
        return write_uxd(path, [dict(drive="COUPLED", marker="_2THETACOUNTS",
                                     steptime=1.0,
                                     rows=[(10.0 + 0.02 * i, 500 + i % 7)
                                           for i in range(400)])])
    # two groups each, so a cut lands inside a manifest, a member and the
    # central directory at different depths
    if kind == "rasx":
        return write_rasx(path, [dict(rows=[(10.0 + 0.02 * i, 500 + i % 7)
                                            for i in range(200)]),
                                 dict(rows=[(40.0 + 0.02 * i, 300 + i % 5)
                                            for i in range(200)])])
    assert kind == "brml"
    return write_brml(path, [dict(rows=[(1, 1, 10.0 + 0.02 * i, 5.0, 500 + i % 7)
                                        for i in range(200)]),
                             dict(rows=[(1, 1, 40.0 + 0.02 * i, 20.0, 300 + i % 5)
                                        for i in range(200)])])


#: Where to cut.  Fractions rather than byte counts so the same set of offsets
#: means the same thing on a 3 kB file and a 5 MB one, and deliberately dense
#: near the start, where a header is still being consumed and a parser is most
#: likely to index into something it has not read.
CUTS = (0.0, 0.0005, 0.001, 0.002, 0.004, 0.008, 0.015, 0.03, 0.05, 0.08,
        0.12, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.999)


def test_the_offsets_are_the_twenty_the_docstring_claims():
    assert len(CUTS) == 20 and CUTS == tuple(sorted(set(CUTS)))


@pytest.mark.parametrize("fixture,reader", REAL_FIXTURES)
def test_the_fixture_reads_whole_and_is_claimed_by_the_reader_named(fixture, reader):
    """The control: without this, a harness that truncates a file nothing reads
    would pass by asserting nothing."""
    path = DATA / fixture
    assert identify_format(path).name == reader
    assert len(rx.read_pattern(path).two_theta) > 100


@pytest.mark.parametrize("fixture,reader", REAL_FIXTURES)
def test_every_truncation_fails_as_a_value_or_os_error_naming_the_file(
        fixture, reader, tmp_path):
    """Twenty depths per fixture; each one may parse, but may not *crash*.

    A truncation that still parses is a legitimate outcome — half an ``.xy`` is
    a shorter ``.xy`` — so the assertion is on the *kind* of failure, never on
    there being one.
    """
    raw = (DATA / fixture).read_bytes()
    name = Path(fixture).name
    for cut in CUTS:
        stub = tmp_path / f"{int(cut * 1e6):07d}_{name}"
        stub.write_bytes(raw[:int(len(raw) * cut)])
        try:
            rx.read_pattern(stub)
        except (ValueError, OSError) as exc:
            assert stub.name in str(exc) or name in str(exc), (
                f"{fixture} cut at {cut}: refusal does not name the file: {exc}")
        except Exception as exc:                       # noqa: BLE001 - the point
            raise AssertionError(
                f"{fixture} cut at {cut} raised {type(exc).__module__}."
                f"{type(exc).__name__}, which is neither ValueError nor OSError "
                f"— a reader must convert its parser's exception at its own "
                f"boundary: {exc}") from exc


@pytest.mark.parametrize("fixture,_reader", REAL_FIXTURES)
def test_a_fixture_with_a_nul_spliced_in_is_refused_rather_than_decoded(
        fixture, _reader, tmp_path):
    """The other half of "not merely odd": bytes that are *not* text at all.

    A NUL early in the file is what a binary vendor format looks like to the
    dispatch, and the answer must be the refusal that names the readable
    formats — not a decoder error from whichever reader claimed it anyway.
    """
    raw = bytearray((DATA / fixture).read_bytes()[:8192])
    raw[100:110] = b"\x00" * 10
    stub = tmp_path / Path(fixture).name
    stub.write_bytes(bytes(raw))
    try:
        rx.read_pattern(stub)
    except (ValueError, OSError) as exc:
        assert stub.name in str(exc)
    except Exception as exc:                           # noqa: BLE001 - the point
        raise AssertionError(
            f"{fixture} with a NUL spliced in raised {type(exc).__name__}") from exc


def test_a_directory_is_an_os_error_not_a_confusing_parse(tmp_path):
    """``read_pattern`` is handed paths from a CLI and a project document, and
    a directory is the commonest wrong one — a ``.rex`` project passed where
    its pattern was meant."""
    (tmp_path / "project.rex").mkdir()
    with pytest.raises(OSError):
        rx.read_pattern(tmp_path / "project.rex")


def test_a_missing_file_says_so_before_any_reader_sees_it(tmp_path):
    with pytest.raises(OSError):
        rx.read_pattern(tmp_path / "nope.xy")


def test_an_empty_file_is_refused_by_name(tmp_path):
    """Zero bytes claims nothing and parses as nothing; the refusal has to come
    from the dispatch or the reader, never from numpy reshaping an empty array."""
    p = tmp_path / "empty.xy"
    p.write_bytes(b"")
    with pytest.raises(ValueError) as exc:
        rx.read_pattern(p)
    assert "empty.xy" in str(exc.value)


@pytest.mark.parametrize("kind", SYNTHETIC_FIXTURES)
def test_every_truncation_of_a_synthesized_fixture_fails_the_same_way(kind, tmp_path):
    """The same invariant for a format that has no real fixture to truncate.

    Weaker evidence and deliberately labelled as such — the file agrees with the
    reader by construction — but a truncation still cuts mid-number, mid-marker
    and mid-header, which is where an ASCII parser indexes into what it has not
    read.
    """
    raw = _synthesize(kind, tmp_path / f"whole.{kind}").read_bytes()
    for cut in CUTS:
        stub = tmp_path / f"{int(cut * 1e6):07d}.{kind}"
        stub.write_bytes(raw[:int(len(raw) * cut)])
        try:
            rx.read_pattern(stub)
        except (ValueError, OSError) as exc:
            assert stub.name in str(exc), (
                f"{kind} cut at {cut}: refusal does not name the file: {exc}")
        except Exception as exc:                       # noqa: BLE001 - the point
            raise AssertionError(
                f"synthesized {kind} cut at {cut} raised "
                f"{type(exc).__module__}.{type(exc).__name__}: {exc}") from exc


# ---------------------------------------------------------------------------
# the *structure* readers, and the magnetic constructs they carry (WP-1328)
#
# Until this rung the harness above covered the **pattern** readers only, so a
# `.cif` or a `.inp` had never been handed to `structure_from_cif` /
# `read_topas_inp` cut mid-token.  It found one defect immediately and it was
# pre-existing on the nuclear path: an empty or truncated CIF raised a bare
# `IndexError('vector')` out of gemmi's C++ side — neither ValueError nor
# OSError, naming no file, which is a traceback on an API caller and a 500 on
# the GUI's upload route.  `crystallography.cif._gemmi_or_value_error` is the
# conversion; this arm is what keeps it.
# ---------------------------------------------------------------------------

#: The magnetic structure fixtures to truncate, taken from ``test_magcif``'s
#: own typed set rather than re-typed here: one writer per fixture, and a
#: fixture that changes there changes here.  Four published structures spanning
#: orthorhombic, tetragonal and (twice) hexagonal — the last because M-5
#: measured that a wrong symmetry action is invisible outside space groups
#: 149-194, so a magnetic arm without a hexagonal file is not a control.
MAGNETIC_STRUCTURE_FIXTURES = ("LaMnO3", "Cr2WO6", "YMnO3", "ScMnO3")


@pytest.mark.parametrize("key", MAGNETIC_STRUCTURE_FIXTURES)
def test_every_truncation_of_a_magcif_fails_as_a_named_value_error(key, tmp_path):
    """Twenty depths through a magCIF: each may read, none may crash.

    The depths that matter are the ones that cut inside a construct rather than
    between two: mid-operator (``-x+1/2,y+1/2,-z``), mid-su (``3.7(1`` — an
    unclosed parenthesis), mid-bracket (``[0 0`` in the propagation vector,
    which gemmi cannot tokenise even whole), and between a loop header and its
    rows.  A truncation that still reads is a legitimate outcome — a magCIF
    with the moment loop cut off is a nuclear CIF — so the assertion is on the
    *kind* of failure and never on there being one.
    """
    from rietx.crystallography.cif import structure_from_cif
    from tests.test_magcif import _fixture

    raw = _fixture(tmp_path, key).read_bytes()
    for cut in CUTS:
        stub = tmp_path / f"{int(cut * 1e6):07d}_{key}.mcif"
        stub.write_bytes(raw[:int(len(raw) * cut)])
        try:
            structure_from_cif(str(stub))
        except (ValueError, OSError) as exc:
            assert stub.name in str(exc), (
                f"{key} cut at {cut}: refusal does not name the file: {exc}")
        except Exception as exc:                       # noqa: BLE001 - the point
            raise AssertionError(
                f"magCIF {key} cut at {cut} raised "
                f"{type(exc).__module__}.{type(exc).__name__}, which is "
                f"neither ValueError nor OSError: {exc}") from exc


@pytest.mark.parametrize("key", MAGNETIC_STRUCTURE_FIXTURES)
def test_a_magcif_with_a_nul_spliced_in_is_refused_rather_than_decoded(
        key, tmp_path):
    """Bytes that are not text at all, on the structure reader's own path."""
    from rietx.crystallography.cif import structure_from_cif
    from tests.test_magcif import _fixture

    raw = bytearray(_fixture(tmp_path, key).read_bytes())
    raw[100:110] = b"\x00" * 10
    stub = tmp_path / f"nul_{key}.mcif"
    stub.write_bytes(bytes(raw))
    try:
        structure_from_cif(str(stub))
    except (ValueError, OSError) as exc:
        assert stub.name in str(exc)
    except Exception as exc:                           # noqa: BLE001 - the point
        raise AssertionError(
            f"magCIF {key} with a NUL spliced in raised "
            f"{type(exc).__module__}.{type(exc).__name__}: {exc}") from exc


def test_every_truncation_of_a_magnetic_inp_fails_as_a_named_value_error(tmp_path):
    """The same invariant for the TOPAS reader's new magnetic keywords.

    A cut inside ``mlx 0 mly @ 2.35`` leaves a site stating a moment component
    with no value, which the reader must refuse naming the line rather than
    default to 0 — a moment pointing somewhere else, with |F_m|² quadratic in
    it, is not an error that announces itself.
    """
    from rietx.io.projects.topas import read_topas_inp, to_structure
    from tests.test_magcif import _TOPAS_MAG

    raw = _TOPAS_MAG.encode()
    for cut in CUTS:
        stub = tmp_path / f"{int(cut * 1e6):07d}_mag.inp"
        stub.write_bytes(raw[:int(len(raw) * cut)])
        try:
            model = read_topas_inp(stub)
            to_structure(model, magnetic_symmetry="58.395")
        except (ValueError, OSError) as exc:
            assert stub.name in str(exc), (
                f"mag.inp cut at {cut}: refusal does not name the file: {exc}")
        except Exception as exc:                       # noqa: BLE001 - the point
            raise AssertionError(
                f"magnetic .inp cut at {cut} raised "
                f"{type(exc).__module__}.{type(exc).__name__}, which is "
                f"neither ValueError nor OSError: {exc}") from exc


# ---------------------------------------------------------------------------
# what a reader hands back: the axis, the rows, the σ column (WP-1332)
#
# The files above are *broken*.  These parse perfectly and came back wrong: a
# GSAS file whose bank record lost its line to a comment, a header row read as
# a data point, a constant column read as σ.  Every one was silent, so each
# test asserts the code as well as the numbers.
# ---------------------------------------------------------------------------

#: Issue #236's pair, verbatim: two files differing by the ``#`` some tool
#: prepended to the bank line (issue #230 met it as two archive copies of one
#: measurement).  Missed by the sniff, the bad one fell to ``xy`` and read its
#: centidegrees as degrees.
_GOOD_FXYE = ("ZnCr2O4 test\n"
              "BANK 1 4 4 CONST 5000.0 1000.0 0 0 FXYE\n"
              "    5000.0     1000.0       31.6\n"
              "    6000.0     1010.0       31.8\n"
              "    7000.0      990.0       31.5\n"
              "    8000.0     1005.0       31.7\n")
_BAD_FXYE = _GOOD_FXYE.replace("BANK 1", "# BANK 1")


def _read(path, text):
    path.write_text(text, encoding="utf-8")
    found = []
    return rx.read_pattern(path, diagnostics=found), [d.code for d in found]


def test_a_commented_bank_record_reads_the_same_axis_and_says_so(tmp_path):
    good, good_codes = _read(tmp_path / "good.fxye", _GOOD_FXYE)
    bad, bad_codes = _read(tmp_path / "bad.fxye", _BAD_FXYE)
    assert good.two_theta == bad.two_theta == [50.0, 60.0, 70.0, 80.0]
    assert bad.sigma == good.sigma
    assert good_codes == []
    assert bad_codes == ["GSAS_BANK_COMMENTED"]
    assert identify_format(tmp_path / "bad.fxye").name == "gsas"


def test_a_live_bank_outranks_a_commented_one(tmp_path):
    """Commenting a bank out is also how a person disables it, so a file with
    both reads the live one and reports nothing.  A commented bank on either
    side of it is not read into its rows."""
    text = ("two banks\n"
            "# BANK 1 2 2 CONST 1000.0 1000.0 0 0 FXYE\n"
            "    1000.0      500.0       22.4\n"
            "    2000.0      510.0       22.6\n"
            + _GOOD_FXYE.split("\n", 1)[1]
            + "# BANK 3 2 2 CONST 9000.0 1000.0 0 0 FXYE\n"
            "    9000.0      700.0       26.5\n"
            "   10000.0      710.0       26.6\n")
    pat, codes = _read(tmp_path / "two.fxye", text)
    assert pat.two_theta == [50.0, 60.0, 70.0, 80.0]
    assert codes == []


def test_a_comment_that_mentions_a_bank_does_not_claim_an_ascii_file(tmp_path):
    """The commented form must carry the whole loose header.  A passing mention
    claimed as GSAS would turn a readable ``.xy`` into a refusal."""
    path = tmp_path / "detector.xy"
    path.write_text("# BANK 1 of the detector\n10.0 100.0\n10.1 110.0\n",
                    encoding="utf-8")
    assert identify_format(path).name == "xy"
    assert rx.read_pattern(path).two_theta == [10.0, 10.1]


#: One axis per band, each written for two readers, because the check belongs
#: to the answer and not to one reader.  The ``xy`` file past 180° is the #230
#: file's failure without the sniff fix: centidegrees read as degrees.
_PAST_180 = {
    "xy": "5000.0 1000.0\n6000.0 1010.0\n7000.0 990.0\n8000.0 1005.0\n",
    "gsas": "past\nBANK 1 8 1 CONST 17000.0 200.0 0 0 STD\n"
            "     100     110     120     130     140     150     160     170\n",
}
_AT_OR_BELOW_0 = {
    "xy": "-2.0 100.0\n-1.0 110.0\n0.0 120.0\n1.0 130.0\n",
    "gsas": "through zero\nBANK 1 4 1 CONST -200.0 100.0 0 0 STD\n"
            "     100     110     120     130\n",
}
_SUFFIX = {"xy": ".xy", "gsas": ".gsas"}


@pytest.mark.parametrize("reader", sorted(_PAST_180))
def test_an_axis_past_180_degrees_is_refused_naming_the_file_and_reader(
        reader, tmp_path):
    path = tmp_path / f"past{_SUFFIX[reader]}"
    path.write_text(_PAST_180[reader], encoding="utf-8")
    assert identify_format(path).name == reader
    with pytest.raises(ValueError, match="No scattering angle exceeds 180") as exc:
        rx.read_pattern(path)
    assert path.name in str(exc.value)
    assert identify_format(path).title in str(exc.value)


def test_the_centidegree_hint_is_offered_only_where_division_lands_in_range(
        tmp_path):
    """The hint is evidence only where division by 100 puts the axis inside
    (0, 180].  A time-of-flight axis in µs does not, and gets no hint."""
    cdeg = tmp_path / "cdeg.xy"
    cdeg.write_text(_PAST_180["xy"], encoding="utf-8")
    with pytest.raises(ValueError, match="Divided by 100 it would run 50° to 80°"):
        rx.read_pattern(cdeg)
    tof = tmp_path / "tof.xy"
    tof.write_text("5000.0 1.0\n19000.0 2.0\n", encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        rx.read_pattern(tof)
    assert "Divided by 100" not in str(exc.value)
    # a GSAS reader has already divided by 100, so the lead would be wrong
    gsas = tmp_path / "past.gsas"
    gsas.write_text(_PAST_180["gsas"], encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        rx.read_pattern(gsas)
    assert "Divided by 100" not in str(exc.value)


@pytest.mark.parametrize("reader", sorted(_AT_OR_BELOW_0))
def test_an_axis_reaching_zero_is_read_and_reported(reader, tmp_path):
    path = tmp_path / f"zero{_SUFFIX[reader]}"
    path.write_text(_AT_OR_BELOW_0[reader], encoding="utf-8")
    found = []
    pat = rx.read_pattern(path, diagnostics=found)
    axis = [d for d in found if d.code == "PATTERN_X_AXIS_IMPLAUSIBLE"]
    assert pat.two_theta == [-2.0, -1.0, 0.0, 1.0]
    assert len(axis) == 1
    assert axis[0].where == ["-2.000-0.000"]
    assert axis[0].value == -2.0
    assert "3 of its 4 points" in axis[0].message


def test_a_lone_point_at_zero_names_an_interval_a_project_accepts(tmp_path):
    """Printed to nearest, one point at exactly 0° named (0.000, 0.000), an
    interval ``check_interval`` refuses as empty."""
    from rietx.schemas.project import check_interval

    path = tmp_path / "zero_point.xy"
    path.write_text("0.0 5.0\n10.0 100.0\n10.1 110.0\n", encoding="utf-8")
    found = []
    rx.read_pattern(path, diagnostics=found)
    axis = [d for d in found if d.code == "PATTERN_X_AXIS_IMPLAUSIBLE"]
    assert axis[0].where == ["0.000-0.001"]
    check_interval("excluded_regions", 0.0, 0.001)


#: Issue #266's first file, verbatim: a six-token numeric header row above four
#: two-token data rows.  Read on its first three tokens it was a point at (0, 1).
_HEADER_ROW_XY = ("title=my pattern\n"
                  "det#  used  xcol detcol  xmin  xmax\n"
                  "  0    1    0    1    5.0   50.0\n"
                  "10.0  100.0\n"
                  "10.1  110.0\n"
                  "10.2  120.0\n"
                  "10.3  130.0\n")


def test_a_numeric_header_row_is_dropped_and_reported_by_line(tmp_path):
    path = tmp_path / "header_row.xy"
    path.write_text(_HEADER_ROW_XY, encoding="utf-8")
    found = []
    pat = rx.read_pattern(path, diagnostics=found)
    assert pat.two_theta == [10.0, 10.1, 10.2, 10.3]
    assert pat.intensity == [100.0, 110.0, 120.0, 130.0]
    assert [d.code for d in found] == ["PATTERN_ROWS_DROPPED"]
    assert found[0].where == ["line 3"]
    assert "'0 1 0 1 5.0 50.0'" in found[0].message


def test_a_row_cut_short_is_dropped_and_the_file_keeps_its_sigma(tmp_path):
    """The column count used to be the *minimum* over rows, so one row that
    lost its σ took σ away from every other row."""
    path = tmp_path / "cut.xye"
    path.write_text("10.0 100.0 10.0\n10.1 110.0 10.5\n10.2 120.0 11.0\n"
                    "10.3 130.0\n", encoding="utf-8")
    found = []
    pat = rx.read_pattern(path, diagnostics=found)
    assert pat.sigma == [10.0, 10.5, 11.0]
    assert [d.where for d in found] == [["line 4"]]


def test_a_tied_column_count_goes_to_the_last_row(tmp_path):
    """A header sits above its data, so on a tie the data's count wins."""
    path = tmp_path / "tie.xy"
    path.write_text("1 2 3 4 5 6\n1 2 3 4 5 6\n10.0 100.0\n10.1 110.0\n",
                    encoding="utf-8")
    assert rx.read_pattern(path).two_theta == [10.0, 10.1]


# --- WP-1952: what the xy reader skips inside the data, and what it refuses

def _read_xy(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    found = []
    return rx.read_pattern(path, diagnostics=found), found


def test_a_text_line_inside_the_data_is_reported_by_line(tmp_path):
    """``10.2 n/a`` between data rows was a lost point with no word (#897)."""
    pat, found = _read_xy(tmp_path, "na.xy", "# 2theta counts\n10.0 100\n"
                          "10.1 110\n10.2 n/a\n10.3 130 spike\n10.4 140\n")
    assert pat.two_theta == [10.0, 10.1, 10.4]
    assert [d.code for d in found] == ["PATTERN_ROWS_DROPPED"]
    assert found[0].where == ["line 4", "line 5"]
    assert found[0].value == 2.0
    assert "'10.2 n/a'" in found[0].message and "(lines 2-6)" in found[0].message
    assert "do not read as a row of numbers" in found[0].message


def test_a_header_and_a_footer_around_the_data_are_skipped_without_a_word(tmp_path):
    """22 repository files open with text; reporting it would fire on all.  A
    footer below the last row cannot be a point lost between two."""
    pat, found = _read_xy(tmp_path, "head.xy", "Sample: quartz\n2theta intensity\n"
                          "10.0 100\n10.1 110\n10.2 120\nEnd of data\n")
    assert pat.two_theta == [10.0, 10.1, 10.2]
    assert found == []


def test_a_semicolon_comment_line_is_a_comment_and_not_a_row(tmp_path):
    """``;`` separates columns now, so a ``;``-led line would read as a row."""
    pat, found = _read_xy(tmp_path, "semi_comment.xy",
                          "; 10 80\n10.0 100\n10.1 110\n")
    assert pat.two_theta == [10.0, 10.1]
    assert found == []


def test_a_nan_row_is_reported_by_its_angle_and_not_as_text(tmp_path):
    """``nan`` parses as a number, so the finite-row drop (WP-2079) names it."""
    _, found = _read_xy(tmp_path, "nan.xy", "10.0 100\n10.1 nan\n10.2 120\n")
    assert [d.code for d in found] == ["PATTERN_ROWS_DROPPED"]
    assert "10.1°" in found[0].message
    assert "line" not in found[0].where[0]


@pytest.mark.parametrize("step", [1.0, 0.02])
def test_a_decimal_comma_file_is_refused_naming_the_separator(step, tmp_path):
    """At 1° the file read as 2θ = 10, 11… with y = 0 and σ the counts; at 0.02°
    the duplicate-2θ refusal fired and named the wrong cause."""
    rows = "".join(f"{10 + step * i:.2f}".replace(".", ",") + f"\t{100 + 10 * i}\n"
                   for i in range(30))
    path = tmp_path / "comma.xy"
    path.write_text("2Theta\tCounts\n" + rows, encoding="utf-8")
    with pytest.raises(ValueError, match=r"comma\.xy: 30 of the file's 30 rows "
                                         r".*comma inside a number.*decimal "
                                         r"separator \(10,02\)"):
        rx.read_pattern(path)


def test_a_decimal_comma_under_semicolons_is_refused_too(tmp_path):
    path = tmp_path / "euro.csv"
    path.write_text("".join(f"{10 + 0.02 * i:.2f};{100 + i}.5\n".replace(".", ",")
                            for i in range(10)), encoding="utf-8")
    with pytest.raises(ValueError, match="comma inside a number"):
        rx.read_pattern(path)


def test_a_decimal_comma_in_a_minority_of_rows_is_refused(tmp_path):
    """An exporter that drops trailing zeros writes ``10`` beside ``10,5``: at a
    0.5° step and an odd row count the comma rows are one short of half, lost
    the column-count vote and were dropped under the wrong cause."""
    rows = "".join((f"{10 + i // 2}" if i % 2 == 0 else f"{10 + i // 2},5")
                   + f"\t{100 + i}\n" for i in range(21))
    path = tmp_path / "half.xy"
    path.write_text(rows, encoding="utf-8")
    with pytest.raises(ValueError, match=r"half\.xy: 10 of the file's 21 rows"):
        rx.read_pattern(path)


def test_a_thousands_separator_is_refused_rather_than_split(tmp_path):
    """``10.00 1,234`` on every row read as y = 1, σ = 234, with no word."""
    rows = "".join(f"{10 + 0.02 * i:.2f} 1,{200 + i}\n" for i in range(10))
    path = tmp_path / "thousands.xy"
    path.write_text(rows, encoding="utf-8")
    with pytest.raises(ValueError, match=r"the field '1,200'.*thousands separator"):
        rx.read_pattern(path)


@pytest.mark.parametrize("text", [
    "10.0,100\n10.1,110\n10.2,120\n",            # comma-separated, decimal point
    "10.0, 100\n10.1, 110\n10.2, 120\n",         # with a space after the comma
    "10, 100\n11, 110\n12, 120\n",               # integers
])
def test_a_comma_separated_file_is_not_taken_for_a_decimal_comma(text, tmp_path):
    pat, found = _read_xy(tmp_path, "csv.xy", text)
    assert len(pat.two_theta) == 3 and pat.intensity[0] == 100.0
    assert found == []


def test_a_trailing_comment_is_dropped_and_its_row_kept(tmp_path):
    """JulesOpp's file (#897): one ``# spike`` row was dropped in silence."""
    rows = "".join(f"{10 + 0.01 * i:.2f} {150 + i}" + ("  # spike" if i == 6 else "")
                   + "\n" for i in range(10))
    pat, found = _read_xy(tmp_path, "spike.xy", rows)
    assert len(pat.two_theta) == 10 and pat.intensity[6] == 156.0
    assert found == []


def test_a_trailing_comment_on_every_row_reads(tmp_path):
    pat, found = _read_xy(tmp_path, "every.xy", "10.0 100 ! a\n10.1 110 ! b\n"
                          "10.2 120 # c\n")
    assert pat.intensity == [100.0, 110.0, 120.0]
    assert found == []


def test_semicolon_separated_columns_read_as_commas_do(tmp_path):
    pat, found = _read_xy(tmp_path, "semi.xy",
                          "10.0;100;10\n10.1;110;10.5\n10.2;120;11\n")
    assert pat.sigma == [10.0, 10.5, 11.0]
    assert found == []


def test_quoted_fields_are_refused_by_name(tmp_path):
    path = tmp_path / "quoted.csv"
    path.write_text('"2theta","counts"\n"10.0","100"\n"10.1","110"\n',
                    encoding="utf-8")
    with pytest.raises(ValueError, match=r"quoted\.csv: its fields are quoted "
                                         r"\(line 2"):
        rx.read_pattern(path)


def test_prose_with_quotes_is_not_called_quoted_fields(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text('A file "about" nothing\nno numbers here\n', encoding="utf-8")
    with pytest.raises(ValueError, match=r"no line reads as a row of numbers; the "
                                         r"first line that is not a comment is line 1"):
        rx.read_pattern(path)


def test_a_file_of_comments_says_so(tmp_path):
    path = tmp_path / "comments.xy"
    path.write_text("# one\n! two\n' three\n", encoding="utf-8")
    with pytest.raises(ValueError, match="every non-blank line starts with a "
                                         "comment marker"):
        rx.read_pattern(path)


def test_an_xydata_heading_with_no_rows_names_the_heading(tmp_path):
    path = tmp_path / "empty.dat"
    path.write_text("XYDATA\nINTER 1 1 0 0\nTEMP 300\nx\nx\nx\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no line of text below its XYDATA heading"):
        rx.read_pattern(path)


#: Issue #266's second file, and the same constant σ under a reader whose
#: format *declares* the column.  The check is on the hook, so both say it.
_CONSTANT_SIGMA = {
    "xy": ("constant_third.xy",
           "10.0  100.0  1.0\n10.1  110.0  1.0\n"
           "10.2  120.0  1.0\n10.3  130.0  1.0\n"),
    "gsas": ("constant.fxye",
             "flat esd\nBANK 1 4 4 CONST 1000.0 10.0 0 0 FXYE\n"
             "  1000.0  100.0  1.0\n  1010.0  110.0  1.0\n"
             "  1020.0  120.0  1.0\n  1030.0  130.0  1.0\n"),
}


@pytest.mark.parametrize("reader", sorted(_CONSTANT_SIGMA))
def test_a_constant_sigma_is_kept_and_reported(reader, tmp_path):
    name, text = _CONSTANT_SIGMA[reader]
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    assert identify_format(path).name == reader
    found = []
    pat = rx.read_pattern(path, diagnostics=found)
    assert pat.sigma == [1.0, 1.0, 1.0, 1.0]
    assert [d.code for d in found] == ["PATTERN_SIGMA_CONSTANT"]
    assert found[0].value == 1.0
    assert "every one of its 4 points" in found[0].message


#: Every code WP-1332 added.  A real fixture raising any of them is a false
#: alarm on a file somebody measured.
_WP1332_CODES = {"GSAS_BANK_COMMENTED", "PATTERN_X_AXIS_IMPLAUSIBLE",
                 "PATTERN_ROWS_DROPPED", "PATTERN_SIGMA_CONSTANT"}


@pytest.mark.parametrize("fixture,_reader", REAL_FIXTURES)
def test_no_real_fixture_trips_a_check_on_what_its_reader_hands_back(
        fixture, _reader):
    found = []
    rx.read_pattern(DATA / fixture, diagnostics=found)
    assert not {d.code for d in found} & _WP1332_CODES


# ------------------------------------------------- non-finite rows (WP-2079)
#: Twelve points, and the bad value goes at index 5.
_NF_N, _NF_AT = 12, 5
_NF_TT = [10.0 + 0.02 * i for i in range(_NF_N)]
_NF_Y = [500.0 + i % 7 for i in range(_NF_N)]
_NF_S = [22.0 + i % 3 for i in range(_NF_N)]
_NF_BAD = (float("nan"), float("inf"), float("-inf"))

#: Each reader that can carry a float, with the columns its file can hold one
#: in: ``x`` the 2θ, ``y`` the count, ``s`` the σ.  A reader whose 2θ is built
#: from a start and a step has no ``x``.
_NF_COLUMNS = {"xy": "xys", "chi": "xy", "gsas_fxye": "xys", "gsas_esd": "ys",
               "ras": "xy", "uxd": "xy", "xrdml": "y", "udf": "y", "rasx": "xy",
               "brml": "xy", "pdcif": "xys", "gsas2_gpx": "xy"}
#: Bruker RAW stores float32 counts, and a non-finite one is its evidence that
#: the stride is wrong: the reader refuses the file, and that refusal stays.
_NF_REFUSED = {"raw4": "y", "raw3": "x"}
#: Philips ``.rd`` stores √-packed uint16 counts, which cannot be NaN or ±inf.
_NF_CANNOT_CARRY = {"philips_rd"}


def _nonfinite_file(kind: str, column: str, bad: float, d: Path) -> Path:
    from tests.test_readers import (
        _write_pdcif,
        write_brml,
        write_chi,
        write_gsas,
        write_gsas_esd,
        write_ras,
        write_rasx,
        write_udf,
        write_uxd,
        write_xrdml,
        write_xy,
    )
    from tests.writers_xrd import write_gpx, write_raw3, write_raw4

    def put(seq, col):
        return [bad if (i == _NF_AT and col == column) else v
                for i, v in enumerate(seq)]

    tt, y, s = put(_NF_TT, "x"), put(_NF_Y, "y"), put(_NF_S, "s")
    if kind == "xy":
        return write_xy(d / "a.xye", tt, y, s)
    if kind == "chi":
        return write_chi(d / "a.chi", "2-Theta Angle (Degrees)", tt, y)
    if kind == "gsas_fxye":
        body = "".join(f"  {a * 100}  {b}  {c}\n" for a, b, c in zip(tt, y, s))
        return write_gsas(d / "a.fxye", bintype="CONST", flag="FXYE", body=body,
                          nchan=_NF_N, nrec=_NF_N, coeffs=(1000.0, 2.0, 0, 0))
    if kind == "gsas_esd":
        return write_gsas_esd(d / "a.gsas", y, s, start=1000.0, step=2.0)
    if kind == "ras":
        return write_ras(d / "a.ras", [(a, b, 1.0) for a, b in zip(tt, y)])
    if kind == "uxd":
        return write_uxd(d / "a.uxd", [dict(drive="COUPLED", marker="_2THETACOUNTS",
                                           steptime=1.0, rows=list(zip(tt, y)))])
    if kind == "xrdml":
        return write_xrdml(d / "a.xrdml", start=_NF_TT[0], end=_NF_TT[-1], counts=y)
    if kind == "udf":
        return write_udf(d / "a.udf", y, lo=_NF_TT[0], step=0.02)
    if kind == "rasx":
        return write_rasx(d / "a.rasx", [dict(rows=[(a, b, 1.0)
                                                    for a, b in zip(tt, y)])])
    if kind == "brml":
        return write_brml(d / "a.brml", [dict(rows=[(1, 1, a, 5.0, b)
                                                    for a, b in zip(tt, y)])])
    if kind == "pdcif":
        return _write_pdcif(d / "a.cif", {"_pd_meas_2theta_scan": tt,
                                          "_pd_meas_counts_total": y,
                                          "_pd_meas_counts_total_su": s})
    if kind == "gsas2_gpx":
        # the weight column is w = 1/σ²; a non-finite *weight* is its own test
        # (test_projects_gsas2.py), since σ is derived from it, not stored
        return write_gpx(d / "a.gpx", [dict(x=tt, y=y, w=[1.0 / v ** 2 for v in _NF_S])])
    if kind == "raw4":
        return write_raw4(d / "a.raw", [dict(start=10.0, step=0.02, intensity=y)])
    assert kind == "raw3"
    return write_raw3(d / "a.raw", [dict(start=10.0, step=0.02, intensity=y,
                                         two_theta=tt)])


@pytest.mark.parametrize("kind,column,bad", [
    (k, c, b) for k, cols in _NF_COLUMNS.items() for c in cols for b in _NF_BAD])
def test_a_non_finite_value_drops_its_row_and_says_where(kind, column, bad,
                                                         tmp_path):
    path = _nonfinite_file(kind, column, bad, tmp_path)
    found = []
    pat = rx.read_pattern(path, diagnostics=found)
    assert len(pat.intensity) == _NF_N - 1
    assert all(map(math.isfinite, pat.tt()))
    assert all(map(math.isfinite, pat.intensity))
    assert pat.sigma is None or all(map(math.isfinite, pat.sigma))
    # nothing else moves: a NaN count once withheld σ from the whole scan
    assert [d.code for d in found] == ["PATTERN_ROWS_DROPPED"]
    (d,) = found
    assert d.value == 1.0 and d.level == "warning"
    # CIF has no infinity, and gemmi reads ``inf`` as a null, which is NaN
    what = "a NaN" if math.isnan(bad) or kind == "pdcif" else "an infinite"
    name = {"x": "2θ", "y": "count", "s": "σ"}[column]
    assert f"1 of {_NF_N} points has {what} {name} " in d.message
    if column == "x":
        # a row with no finite 2θ has no position to name
        assert d.where == ["two_theta"]
        assert d.message.endswith(f"{name} and was not read as data.")
    else:
        assert d.where == [f"{_NF_TT[_NF_AT]:.3f}-{_NF_TT[_NF_AT]:.3f}"]
        assert d.message.endswith(f"was not read as data, at 2θ {_NF_TT[_NF_AT]:g}°.")


def test_a_row_with_no_finite_2theta_is_counted_beside_the_named_ones(tmp_path):
    from tests.test_readers import write_xy

    nan = float("nan")
    found = []
    pat = rx.read_pattern(write_xy(tmp_path / "mixed.xy",
                                   [10.0, 10.1, nan, 10.3, 10.4],
                                   [1.0, nan, 3.0, 4.0, 5.0]),
                          diagnostics=found)
    assert pat.two_theta == [10.0, 10.3, 10.4]
    (d,) = found
    assert d.where == ["10.100-10.100"]
    assert d.message == (
        "mixed.xy: 2 of 5 points have a NaN 2θ or count and were not read as "
        "data, at 2θ 10.1°, and 1 with no finite 2θ.")


@pytest.mark.parametrize("kind", sorted(_NF_REFUSED))
def test_bruker_raw_refuses_a_non_finite_value_as_a_wrong_stride(kind, tmp_path):
    path = _nonfinite_file(kind, _NF_REFUSED[kind], float("nan"), tmp_path)
    assert identify_format(path).name == "bruker_raw"
    with pytest.raises(ValueError, match="not finite numbers") as exc:
        rx.read_pattern(path)
    assert path.name in str(exc.value)


def test_every_reader_is_classified_for_non_finite_values():
    """A new reader fails here until it is tested for NaN rows or says why not."""
    from rietx.io.readers import PATTERN_FORMATS

    readers = {f.name for f in PATTERN_FORMATS if f.refuses is None}
    covered = ({k.removesuffix("_fxye").removesuffix("_esd") for k in _NF_COLUMNS}
               | {"bruker_raw"} | _NF_CANNOT_CARRY)
    assert covered == readers


def test_separate_runs_are_named_three_at_a_time(tmp_path):
    from tests.test_readers import write_xy

    tt = [10.0 + 0.1 * i for i in range(20)]
    y = [float("nan") if i in (2, 3, 7, 11, 15, 18) else 100.0
         for i in range(20)]
    found = []
    pat = rx.read_pattern(write_xy(tmp_path / "runs.xy", tt, y),
                          diagnostics=found)
    assert len(pat.intensity) == 14
    (d,) = found
    assert d.where == ["10.200-10.300", "10.700-10.700", "11.100-11.100",
                       "11.500-11.500", "11.800-11.800"]
    assert d.message.endswith(
        "at 2θ 10.2-10.3°, 10.7°, 11.1°, and 2 more range(s).")


def test_a_descending_scan_drops_its_nan_row_before_it_is_reversed(tmp_path):
    from tests.test_readers import write_xy

    tt = [12.0 - 0.5 * i for i in range(5)]
    found = []
    pat = rx.read_pattern(write_xy(tmp_path / "down.xy", tt,
                                   [1.0, 2.0, float("nan"), 4.0, 5.0]),
                          diagnostics=found)
    assert pat.two_theta == [10.0, 10.5, 11.5, 12.0]
    assert [d.code for d in found] == ["PATTERN_ROWS_DROPPED",
                                       "PATTERN_SCAN_REVERSED"]
    assert found[0].where == ["11.000-11.000"]


def test_an_xydata_file_under_multipliers_drops_its_nan_row_and_scales_the_rest(
        tmp_path):
    """The ``XYDATA`` heading's ``INTER`` multipliers (#1064) are applied before
    the order checks, so the NaN row they leave NaN is dropped there and the
    finite rows carry the product.  Issue #1187's file is this format."""
    rows = [f"{10 + 0.1 * i:.3f} {'nan' if i == 3 else f'{100.0 + i:.1f}'} "
            f"{10.0 + 0.1 * i:.1f}"
            for i in range(8)]
    path = tmp_path / "d1b.xys"
    path.write_text("\n".join(["XYDATA", "TITLE synthetic", "COND: neutrons",
                               "FILE: d1b.xys", "TEMP 4.25", "INTER 1.0 2.0 0 0.05",
                               *rows]) + "\n", encoding="utf-8")
    found = []
    pat = rx.read_pattern(path, diagnostics=found)
    assert len(pat.intensity) == 7
    assert pat.intensity[0] == 200.0 and pat.sigma[0] == 20.0
    assert sorted(d.code for d in found) == ["PATTERN_ROWS_DROPPED",
                                             "XYDATA_INTER_APPLIED"]
    (d,) = [d for d in found if d.code == "PATTERN_ROWS_DROPPED"]
    assert d.message.endswith("was not read as data, at 2θ 10.3°.")


def test_a_declared_flight_time_bank_names_its_dropped_row_in_microseconds(
        tmp_path):
    """``axis="tof"`` (#1064) reaches the drop, which names the row by its
    flight time rather than calling it a 2θ."""
    rows = [f"{2000.0 + 16.0 * i:.1f} {'nan' if i == 4 else '100.0'} "
            f"{10.0 + 0.1 * i:.1f}"
            for i in range(10)]
    path = tmp_path / "bank.dat"
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    found = []
    pat = rx.read_pattern(path, axis="tof", diagnostics=found)
    assert pat.axis == "tof" and len(pat.tof) == 9
    (d,) = found
    assert d.code == "PATTERN_ROWS_DROPPED"
    assert d.message.endswith("was not read as data, at flight time 2064 µs.")


def test_a_file_with_no_finite_row_is_refused_by_name(tmp_path):
    from tests.test_readers import write_xy

    path = write_xy(tmp_path / "void.xy", [10.0, 10.1, 10.2], [float("nan")] * 3)
    with pytest.raises(ValueError, match="every one of its 3 points") as exc:
        rx.read_pattern(path)
    assert "void.xy" in str(exc.value)


def test_a_reader_that_skips_the_check_is_refused_at_the_schema(tmp_path):
    """``pattern_data`` is the backstop for a reader that never called
    ``ascending``: it refuses rather than hand the fit a NaN."""
    from rietx.io.formats.base import pattern_data

    with pytest.raises(ValueError, match="skipped.cif: a NaN or infinite"):
        pattern_data(tmp_path / "skipped.cif", [10.0, 10.1, 10.2],
                     [1.0, float("nan"), 3.0])


def test_a_non_finite_absorber_drops_its_row_rather_than_the_file(tmp_path):
    """A NaN in a column a reader reads *before* ``ascending`` (here the
    ``.brml`` absorber that σ is derived through) drops its row like any other."""
    from tests.test_readers import write_brml

    rows = [(1, float("nan") if i == 2 else 1.0, a, 5.0, b)
            for i, (a, b) in enumerate(zip(_NF_TT[:6], _NF_Y[:6]))]
    found = []
    pat = rx.read_pattern(write_brml(tmp_path / "a.brml", [dict(rows=rows)]),
                          diagnostics=found)
    assert len(pat.intensity) == 5
    assert [d.code for d in found] == ["PATTERN_ROWS_DROPPED"]


def test_a_finite_count_on_a_dropped_row_still_votes_on_the_unit(tmp_path):
    """Only a non-finite *value* is left out of the counts test.  A finite
    count is evidence about its column's unit whatever its 2θ, and 84.3047 is
    the rate a real ``.ras`` stored under a "counts" label."""
    from tests.test_readers import write_ras

    y = [100.0, 101.0, 84.3047, 103.0, 104.0, 105.0]
    tt = [float("nan") if i == 2 else a for i, a in enumerate(_NF_TT[:6])]
    found = []
    rx.read_pattern(write_ras(tmp_path / "a.ras",
                              [(a, b, 1.0) for a, b in zip(tt, y)]),
                    diagnostics=found)
    assert [d.code for d in found] == ["PATTERN_INTENSITY_SCALED",
                                       "PATTERN_ROWS_DROPPED"]


# --------------------------------------------- a σ of zero or below (WP-1952)
def _sigma_file(kind: str, s: list[float], d: Path) -> Path:
    """A twelve-point file of ``kind`` whose σ column is ``s``."""
    from tests.test_readers import _write_pdcif, write_gsas, write_gsas_esd, write_xy

    if kind == "xy":
        return write_xy(d / "a.xye", _NF_TT, _NF_Y, s)
    if kind == "gsas_fxye":
        body = "".join(f"  {a * 100}  {b}  {c}\n" for a, b, c in zip(_NF_TT, _NF_Y, s))
        return write_gsas(d / "a.fxye", bintype="CONST", flag="FXYE", body=body,
                          nchan=_NF_N, nrec=_NF_N, coeffs=(1000.0, 2.0, 0, 0))
    if kind == "gsas_esd":
        return write_gsas_esd(d / "a.gsas", _NF_Y, s, start=1000.0, step=2.0)
    assert kind == "pdcif"
    return _write_pdcif(d / "a.cif", {"_pd_meas_2theta_scan": _NF_TT,
                                      "_pd_meas_counts_total": _NF_Y,
                                      "_pd_meas_counts_total_su": s})


#: σ = 0 at index 5 and σ = -1 at index 7, on every reader whose σ is a column.
_NONPOS_S = [-1.0 if i == 7 else (0.0 if i == 5 else v) for i, v in enumerate(_NF_S)]


@pytest.mark.parametrize("kind", ["xy", "gsas_fxye", "gsas_esd", "pdcif"])
def test_a_nonpositive_sigma_leaves_the_fit_and_is_reported(kind, tmp_path):
    """#897's file gave one σ = 0 a weight about 10⁶ times its neighbours',
    in silence. Now the point takes no weight, and the reader says which."""
    found = []
    pat = rx.read_pattern(_sigma_file(kind, _NONPOS_S, tmp_path), diagnostics=found)
    assert pat.sigma == _NONPOS_S                    # the file's numbers kept
    assert pat.nonpositive_sigma == "exclude"
    mask = pat.in_range_mask()
    assert np.flatnonzero(~mask).tolist() == [5, 7]
    (d,) = [d for d in found if d.code == "PATTERN_SIGMA_NONPOSITIVE"]
    assert d.level == "warning" and d.value == 2.0
    assert ("2 of 12 points have a σ of zero or below (1 zero and 1 negative)"
            in d.message)
    assert "at 2θ 10.1°, 10.14°" in d.message
    # the number the suggestion's condition turns on: none of the two counted 0
    assert "0 of them record an intensity of zero" in d.message
    assert d.where == ["10.100-10.100", "10.140-10.140"]
    # the placeholder σ is finite and never a weight the fit reads
    assert np.all(pat.sig() > 0)


@pytest.mark.parametrize("kind", ["xy", "pdcif"])
def test_the_poisson_option_keeps_such_points_at_one_count(kind, tmp_path):
    found = []
    pat = rx.read_pattern(_sigma_file(kind, _NONPOS_S, tmp_path), diagnostics=found,
                          nonpositive_sigma="poisson")
    assert pat.nonpositive_sigma == "poisson"
    assert pat.in_range_mask().all()
    assert pat.sig()[5] == pytest.approx(np.sqrt(_NF_Y[5]))
    assert "PATTERN_SIGMA_NONPOSITIVE" not in {d.code for d in found}
    rule = pat.sigma_rule()
    assert (rule.n_file_sigma, rule.n_poisson_sigma,
            rule.n_nonpositive_excluded) == (10, 2, 0)


def test_an_unknown_nonpositive_sigma_value_is_refused_by_name(tmp_path):
    with pytest.raises(ValueError, match="nonpositive_sigma= takes one of"):
        rx.read_pattern(_sigma_file("xy", _NONPOS_S, tmp_path),
                        nonpositive_sigma="floor")


def test_a_format_with_a_derived_sigma_reports_the_option_unused(tmp_path):
    from tests.test_readers import write_udf

    found = []
    rx.read_pattern(write_udf(tmp_path / "a.udf", _NF_Y, lo=10.0, step=0.02),
                    diagnostics=found, nonpositive_sigma="poisson")
    assert "READER_OPTION_IGNORED" in {d.code for d in found}


@pytest.mark.parametrize("kind", ["xy", "chi", "gsas_esd"])
def test_a_column_with_no_positive_sigma_is_not_read(kind, tmp_path):
    """Every σ ≤ 0 states no weight anywhere: excluding every point would leave
    nothing to fit, so the column is declined, and said to be. The xy and chi
    readers declined one in silence until WP-1952."""
    if kind == "chi":
        from tests.test_readers import write_chi

        path = write_chi(tmp_path / "a.chi", "2-Theta Angle (Degrees)", _NF_TT, _NF_Y)
        text = path.read_text(encoding="utf-8").splitlines()
        n_head = len(text) - _NF_N
        text[n_head:] = [f"{line}  0.0" for line in text[n_head:]]
        path.write_text("\n".join(text) + "\n", encoding="utf-8")
    else:
        path = _sigma_file(kind, [0.0] * _NF_N, tmp_path)
    found = []
    pat = rx.read_pattern(path, diagnostics=found)
    assert pat.sigma is None
    (d,) = [d for d in found if d.code == "PATTERN_SIGMA_NONPOSITIVE"]
    assert ("every one of its 12 σ values is zero or negative (12 zero)"
            in d.message)
    # and the constant-σ report does not fire on a column that was not read
    assert "PATTERN_SIGMA_CONSTANT" not in {d.code for d in found}


@pytest.mark.parametrize("fixture,_reader", REAL_FIXTURES)
def test_no_real_fixture_carries_a_nonpositive_sigma(fixture, _reader):
    found = []
    rx.read_pattern(DATA / fixture, diagnostics=found)
    assert "PATTERN_SIGMA_NONPOSITIVE" not in {d.code for d in found}
