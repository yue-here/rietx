"""A plain ``.zip`` of patterns is N scans (WP-1315, issue #134).

Every fixture here is synthetic and built inline: the real archive that
motivated the reader is not redistributable, and what it established is in
``tests/data/README.md`` § Zip collections.  The fixture the WP names is
:func:`write_zip_collection`'s default: two readable members written out of
name order, a directory entry, an office lock file and a binary member no
reader claims.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.io.formats import zip_collection
from rietx.io.readers import identify_format, list_scans


def xye_text(start: float, n: int = 40) -> str:
    """Three columns, 2θ from ``start`` in 0.02° steps, with an esd column."""
    return "".join(f"{start + 0.02 * i:.2f} {500 + i % 7} {22 + i % 3}\n"
                   for i in range(n))


def fxye_text(n: int = 12) -> str:
    """One GSAS ``FXYE`` bank: 2θ in centidegrees, intensity and esd per row."""
    rows = "".join(f"  {(10.0 + 0.02 * i) * 100:.1f}  {500 + i % 7}  {22 + i % 3}\n"
                   for i in range(n))
    return (f"a synthetic FXYE bank\nBANK 1 {n} {n} CONST 1000.0 2.0 0 0 FXYE\n"
            + rows)


def write_zip_collection(path: Path, members: list[tuple[str, str | bytes]] | None = None,
                         *, compression: int = zipfile.ZIP_DEFLATED) -> Path:
    """A zip of ``(name, content)`` in the order given; the WP's fixture by default."""
    if members is None:
        members = [
            ("z/second.xye", xye_text(30.0)),       # written first, sorts last
            ("dir/", ""),                            # a directory entry
            (".~lock.first.xye#", "a lock file\n"),  # a dotfile, as the real one
            ("image.bin", b"\x00\x01\x02" * 100),    # binary, claimed by no reader
            ("first.xye", xye_text(10.0)),
        ]
    with zipfile.ZipFile(path, "w", compression) as archive:
        for name, content in members:
            archive.writestr(name, content)
    return path


@pytest.fixture
def two(tmp_path):
    return write_zip_collection(tmp_path / "two.zip")


def read_member_directly(tmp_path: Path, name: str, content: str, **options):
    member = tmp_path / "direct" / Path(name).name
    member.parent.mkdir(exist_ok=True)
    member.write_text(content, encoding="utf-8")
    found: list = []
    return rx.read_pattern(member, diagnostics=found, **options), found


# ------------------------------------------------------------- enumeration
def test_the_archive_is_claimed_as_a_zip_collection(two):
    assert identify_format(two).name == "zip_collection"


def test_the_patterns_enumerate_in_name_order_and_nothing_else_does(two):
    scans = list_scans(two)
    # the directory, the lock file and the binary member are skipped, never
    # counted, and the member written first comes last
    assert [s.label for s in scans] == ["first.xye", "z/second.xye"]
    assert [s.index for s in scans] == [0, 1]
    assert [s.n_points for s in scans] == [40, 40]
    assert scans[0].two_theta_range == pytest.approx((10.0, 10.78))
    assert scans[1].two_theta_range == pytest.approx((30.0, 30.78))


def test_scan_selects_the_kth_pattern_and_says_how_many_there_are(two):
    data = rx.read_pattern(two, scan=1)
    assert data.tt()[0] == pytest.approx(30.0)
    assert data.metadata["scan"] == "1"
    assert data.metadata["scan_count"] == "2"
    # the member's full name inside the archive, never the staging file's
    assert data.metadata["source_file"] == "z/second.xye"


def test_reading_member_zero_by_default_is_loud(two):
    found: list = []
    data = rx.read_pattern(two, diagnostics=found)
    assert data.tt()[0] == pytest.approx(10.0)
    (d,) = [d for d in found if d.code == "PATTERN_MULTISCAN_DEFAULTED"]
    assert "two.zip holds 2 scans" in d.message
    # and a choice made is silent
    found.clear()
    rx.read_pattern(two, scan=0, diagnostics=found)
    assert "PATTERN_MULTISCAN_DEFAULTED" not in {d.code for d in found}


def test_an_out_of_range_scan_is_refused_naming_the_archive_and_its_count(two):
    with pytest.raises(ValueError) as exc:
        rx.read_pattern(two, scan=2)
    assert "two.zip holds 2 pattern(s)" in str(exc.value)
    assert "scan=2" in str(exc.value)


def test_a_single_pattern_archive_reads_without_a_default_warning(tmp_path):
    path = write_zip_collection(tmp_path / "one.zip", [("a.xye", xye_text(10.0))])
    found: list = []
    data = rx.read_pattern(path, diagnostics=found)
    assert found == []
    assert data.metadata["scan_count"] == "1"


# ------------------------------------------ the stored-zip mis-dispatch (#134)
def test_a_stored_zip_of_gsas_text_is_a_zip_not_a_gsas_file(tmp_path):
    """On main the first member's ``BANK`` record sat inside the 4 kB head
    sniff, ``gsas`` claimed the archive, and ``read_gsas`` failed on its
    ``PK\\x03\\x04`` bytes with no file named."""
    path = write_zip_collection(tmp_path / "stored.zip",
                                [("a/11bm.fxye", fxye_text())],
                                compression=zipfile.ZIP_STORED)
    assert b"BANK 1" in path.read_bytes()[:4096]      # the trap is armed
    assert identify_format(path).name == "zip_collection"
    data = rx.read_pattern(path)
    assert len(data.intensity) == 12


# ------------------------------------ σ and the axis are the inner reader's
def test_every_sigma_and_axis_decision_is_the_member_readers(tmp_path):
    """The archive adds nothing: a GSAS member comes back exactly as ``gsas``
    reads the same bytes, centidegree fold and esd column included."""
    text = fxye_text()
    path = write_zip_collection(tmp_path / "g.zip", [("a/11bm.fxye", text)])
    found: list = []
    from_zip = rx.read_pattern(path, diagnostics=found)
    direct, direct_found = read_member_directly(tmp_path, "11bm.fxye", text)
    assert from_zip.two_theta == direct.two_theta
    assert from_zip.intensity == direct.intensity
    assert from_zip.sigma == direct.sigma
    assert from_zip.axis == direct.axis == "two_theta"
    assert from_zip.metadata["format"] == direct.metadata["format"] == "gsas-fxye"
    assert [d.code for d in found] == [d.code for d in direct_found]


def test_a_repair_the_member_reader_makes_is_reported_as_it_would_be(tmp_path):
    rows = "".join(f"{30.0 - 0.02 * i:.2f} {500 + i % 7}\n" for i in range(20))
    path = write_zip_collection(tmp_path / "down.zip", [("down.xy", rows)])
    found: list = []
    data = rx.read_pattern(path, diagnostics=found)
    assert np.all(np.diff(data.tt()) > 0)
    assert [d.code for d in found] == ["PATTERN_SCAN_REVERSED"]


def test_the_other_reader_options_reach_the_member_reader(tmp_path):
    path = write_zip_collection(tmp_path / "t.zip",
                                [("bank.xy", xye_text(1000.0))])
    data = rx.read_pattern(path, axis="tof")
    assert data.axis == "tof"
    assert data.metadata["declared_axis"] == "tof"


def test_an_option_the_member_reader_does_not_take_is_reported_there(tmp_path):
    path = write_zip_collection(tmp_path / "x.zip", [("a.xye", xye_text(10.0))])
    found: list = []
    rx.read_pattern(path, block="_meas", diagnostics=found)
    (d,) = [d for d in found if d.code == "READER_OPTION_IGNORED"]
    assert "block=" in d.message


def test_the_nonpositive_sigma_rule_applies_to_a_member(tmp_path):
    rows = "".join(f"{10.0 + 0.02 * i:.2f} {500 + i % 7} {0.0 if i == 5 else 22.0}\n"
                   for i in range(12))
    path = write_zip_collection(tmp_path / "s.zip", [("a.xye", rows)])
    assert not rx.read_pattern(path).in_range_mask()[5]
    assert rx.read_pattern(path, nonpositive_sigma="poisson").in_range_mask()[5]


# ------------------------------------------------------------- membership
def test_a_refused_member_is_not_a_pattern(tmp_path):
    """``total_scattering`` claims a ``.gr`` in order to refuse it, so it is
    skipped like an unclaimed member and never counted."""
    gr = "".join(f"{0.01 * i:.2f} {0.1 * (i % 5)}\n" for i in range(1, 30))
    path = write_zip_collection(tmp_path / "m.zip", [("a.gr", gr),
                                                     ("b.xye", xye_text(10.0))])
    assert [s.label for s in list_scans(path)] == ["b.xye"]


def test_a_zip_inside_is_skipped(tmp_path):
    inner = write_zip_collection(tmp_path / "inner.zip",
                                 [("a/11bm.fxye", fxye_text())],
                                 compression=zipfile.ZIP_STORED)
    path = write_zip_collection(tmp_path / "outer.zip",
                                [("inner.zip", inner.read_bytes()),
                                 ("b.xye", xye_text(10.0))],
                                compression=zipfile.ZIP_STORED)
    assert [s.label for s in list_scans(path)] == ["b.xye"]


def test_a_vendor_container_inside_is_a_pattern(tmp_path):
    from tests.test_readers import write_rasx

    rasx = write_rasx(tmp_path / "scan.rasx",
                      [dict(rows=[(10.0 + 0.02 * i, 500 + i % 7) for i in range(50)])])
    path = write_zip_collection(tmp_path / "v.zip", [("scan.rasx", rasx.read_bytes())])
    data = rx.read_pattern(path)
    assert data.metadata["format"] == "rasx"
    assert len(data.intensity) == 50


def test_a_member_past_the_cap_is_skipped(tmp_path, monkeypatch):
    path = write_zip_collection(tmp_path / "big.zip",
                                [("a.xye", xye_text(10.0, n=400)),
                                 ("b.xye", xye_text(30.0, n=10))])
    monkeypatch.setattr(zip_collection, "MAX_MEMBER_BYTES", 2000)
    assert [s.label for s in list_scans(path)] == ["b.xye"]


def test_an_archive_with_no_pattern_is_not_claimed(tmp_path):
    path = write_zip_collection(tmp_path / "none.zip",
                                [("image.bin", b"\x00\x01" * 100), ("dir/", "")])
    assert not zip_collection.looks_zip_collection(path)
    with pytest.raises(ValueError) as exc:
        rx.read_pattern(path)
    assert "none.zip" in str(exc.value)


def test_an_archive_carrying_a_vendor_manifest_is_not_enumerated(tmp_path):
    path = write_zip_collection(tmp_path / "r.zip",
                                [("root.xml", "<Root/>"), ("a.xye", xye_text(10.0))])
    assert not zip_collection.looks_zip_collection(path)


# ---------------------------------------------------------------- refusals
def test_a_member_that_cannot_be_read_is_refused_naming_archive_and_member(tmp_path):
    path = write_zip_collection(tmp_path / "bad.zip",
                                [("notes.txt", "a log, not a pattern\n"),
                                 ("z.xye", xye_text(10.0))])
    # the ASCII reader claims any text, so the log counts and refuses on read
    with pytest.raises(ValueError, match="bad.zip holds 2 pattern"):
        rx.read_pattern(path, scan=5)
    with pytest.raises(ValueError) as exc:
        rx.read_pattern(path, scan=0)
    message = str(exc.value)
    assert message.startswith("bad.zip: member 'notes.txt'")
    assert "pattern 0 of the 2" in message


def test_an_archive_that_stops_early_is_refused_by_name(tmp_path):
    raw = write_zip_collection(tmp_path / "whole.zip",
                               [("a/11bm.fxye", fxye_text())],
                               compression=zipfile.ZIP_STORED).read_bytes()
    cut = tmp_path / "cut.zip"
    cut.write_bytes(raw[:len(raw) // 2])
    assert identify_format(cut).name == "zip_collection"
    with pytest.raises(ValueError, match="cut.zip begins like a zip archive"):
        rx.read_pattern(cut)


def test_nothing_is_left_on_disk(two, tmp_path, monkeypatch):
    import tempfile

    staging = tmp_path / "tmp"
    staging.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(staging))
    rx.read_pattern(two, scan=1)
    list_scans(two)
    identify_format(two)
    assert list(staging.iterdir()) == []


def test_the_capabilities_arm_names_the_format_and_its_options():
    caps = rx.capabilities()
    by_name = {r.name: r for r in caps.reader_formats}
    zipped = by_name["zip_collection"]
    assert zipped.extensions == [".zip"]
    assert zipped.options == ["axis", "bank", "block", "nonpositive_sigma", "scan"]
    assert zipped.refuses is None


# ------------------------------------------- from the branch's review pass
def test_two_members_of_one_name_are_two_patterns(tmp_path):
    """``getinfo(name)`` answers with the last of them, so each member is
    carried as its own entry from the listing to the read."""
    path = write_zip_collection(tmp_path / "dup.zip", [("a.xye", xye_text(10.0)),
                                                       ("a.xye", xye_text(30.0))])
    starts = [rx.read_pattern(path, scan=k).tt()[0] for k in (0, 1)]
    assert starts == pytest.approx([10.0, 30.0])


@pytest.mark.parametrize("method", [zipfile.ZIP_DEFLATED, zipfile.ZIP_BZIP2,
                                    zipfile.ZIP_LZMA])
def test_a_member_that_cannot_be_decompressed_is_refused_by_name(method, tmp_path):
    """Its bytes cannot say whether it is a pattern, so the archive is claimed
    and the read refuses naming it, never with ``lzma``'s own exception."""
    path = write_zip_collection(tmp_path / "bad.zip",
                                [("a.xye", xye_text(10.0, n=400))],
                                compression=method)
    raw = bytearray(path.read_bytes())
    start = 30 + len("a.xye")                  # the local header, then the data
    for i in range(start + 20, start + 60):
        raw[i] ^= 0xFF
    path.write_bytes(bytes(raw))
    assert identify_format(path).name == "zip_collection"
    with pytest.raises(ValueError) as exc:
        rx.read_pattern(path)
    assert "bad.zip" in str(exc.value)


def test_a_member_holding_several_scans_is_refused_naming_it(tmp_path):
    from tests.test_readers import write_rasx

    rasx = write_rasx(tmp_path / "two.rasx",
                      [dict(rows=[(10.0 + 0.02 * i, 500 + i % 7) for i in range(50)]),
                       dict(rows=[(40.0 + 0.02 * i, 300 + i % 5) for i in range(50)])])
    path = write_zip_collection(tmp_path / "m.zip", [("two.rasx", rasx.read_bytes())])
    found: list = []
    with pytest.raises(ValueError, match="member 'two.rasx' is itself a .* holding 2"):
        rx.read_pattern(path, diagnostics=found)
    # the member's own "pass scan=" advice would select an archive member
    assert "PATTERN_MULTISCAN_DEFAULTED" not in {d.code for d in found}


def test_what_the_member_reader_says_names_the_member_and_the_archive(tmp_path):
    rows = "".join(f"{30.0 - 0.02 * i:.2f} {500 + i % 7}\n" for i in range(20))
    path = write_zip_collection(tmp_path / "w.zip",
                                [("données/scan 1 (A).xy", rows),
                                 ("notes.txt", "a log, not a pattern\n")])
    found: list = []
    rx.read_pattern(path, scan=0, diagnostics=found)
    (d,) = [d for d in found if d.code == "PATTERN_SCAN_REVERSED"]
    assert "données/scan 1 (A).xy in w.zip" in d.message
    with pytest.raises(ValueError) as exc:
        rx.read_pattern(path, scan=1)
    assert "rietx-zip-" not in str(exc.value)      # no staging path escapes


def test_the_post_read_checks_quote_the_member_reader(tmp_path):
    """A GSAS member whose ``BANK`` record is gone reads as columns in
    centidegrees; the hint read from the ASCII reader still reaches it."""
    rows = "".join(f"{1000.0 + 2.0 * i} {500 + i % 7}\n" for i in range(20))
    path = write_zip_collection(tmp_path / "c.zip", [("a.dat", rows)])
    with pytest.raises(ValueError, match="Divided by 100"):
        rx.read_pattern(path)


def test_empty_members_and_windows_directory_entries_are_not_patterns(tmp_path):
    path = write_zip_collection(tmp_path / "e.zip", [("empty.xy", ""),
                                                     ("folder\\", ""),
                                                     ("b.xye", xye_text(10.0))])
    assert [s.label for s in list_scans(path)] == ["b.xye"]
