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

from pathlib import Path

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
SYNTHETIC_FIXTURES = ["uxd", "rasx", "brml", "raw4", "raw3", "gsas_esd", "udf",
                      "philips_v5"]


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
            "  100  110  120  130  140  150  160  170\n",
}
_AT_OR_BELOW_0 = {
    "xy": "-2.0 100.0\n-1.0 110.0\n0.0 120.0\n1.0 130.0\n",
    "gsas": "through zero\nBANK 1 4 1 CONST -200.0 100.0 0 0 STD\n"
            "  100  110  120  130\n",
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
