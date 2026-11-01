"""Bruker/Siemens ``.raw`` — the binary DIFFRAC formats, v1 to v4.

Spec: written down as a table of offsets *before* any parser was opened, and the
parser written with the sources closed.  ``ATTRIBUTION.md`` § Format
specifications records which fact came from which; the rule is that a byte
offset is an interface fact, so it may be read from a source whose licence would
bar a port.

Four magic numbers, one reader, **one of them refused**::

    RAW      v1 — refused: no description of it exists
    RAW2     v2   single-range only (WP-2059)
    RAW1.01  v3   (the version numbering is the vendor's, not a typo)
    RAW4.00  v4

**v2 is read from two descriptions and one real file that agree** (WP-2059,
issue #1164).  It was refused while GSAS-II's was the only description and no
file existed to check it against.  A hand decode of a public v2 file (the PbSO₄
round-robin X-ray pattern of Hill 1992, as converted to v2 in 1997 for the
Durham TOPAS tutorials) matches GSAS-II's description field for field, and
TOPAS, run as a black box on the same file, returns the same 6001 counts.  The
layout is a table of offsets: a block count at 4, then one block whose header
starts at 0x100 and declares its own length, then ``n`` float32 counts.  The
data offset is read from that length, never assumed, and the one gate a
mis-parse cannot pass is arithmetic: ``0x100 + header length + 4n`` must be
the file's size.  A block count other than 1 is refused by name until a
multi-range v2 file is seen.  No count is altered: GSAS-II raises every count
below 1 to 1, and this reader does not.  The header's other fields
(wavelengths, anode, date) are not read, because no second description
corroborates them.

**v4 is a walk, not a table of offsets.**  After a fixed 61-byte preamble the
file is a chain of ``(uint32 type, uint32 length)`` segments; a type of 0 or 160
is not a segment but the marker that a *range* follows, and a range is a header
(itself ending in a nested chain of segments, of declared total size
``hdrSize``) followed by ``nSteps`` records of ``datumSize`` bytes each, of
which the leading float32 is the intensity.  Then the chain resumes.  Two bugs
in the other two readers are what make the walk worth stating:

* **stride by ``datumSize``.**  GSAS-II reads the field and then reads ``nSteps``
  *consecutive* float32s anyway; FAIRmat hard-codes an 8-byte stride it
  describes as "interleaved float32 pairs".  Both are right on a file with
  ``datumSize == 8`` and wrong on one with 4.  The real fixture has 8, and the
  trailing four bytes of each of its 7134 records are ``int32 == 1`` — a field
  whose meaning is unknown, so it is stepped over rather than guessed at.
* **walk to EOF; never count.**  GSAS-II counts occurrences of ``b'2Theta'`` in
  the whole file to decide how many banks there are.  ``2Theta`` occurs
  **twice** in the single-range real fixture — once as a drive record and once
  as the scan-axis record — so that count reports two ranges where there is one.

**Which drive was scanned is read, not assumed.**  The range header's nested
chain carries one type-50 record per drive, each with a name, a flag and the
position it sat at.  The scanned one is the record whose flag is non-zero *and*
whose position equals the range's own start angle — two independent statements
that must agree, because one real file is not enough to trust the flag alone.
Where they do not, the ``ScanType`` string decides, and where that is unfamiliar
too the axis is assumed and said so.  This is the same three-way policy the
other four formats use (:func:`base.check_axis`); the vocabulary is this
format's own.

**σ has to be measured, because v4 declares no intensity unit at all.**  The
range header does give the counting time — ``stepTime``, in **milliseconds**:
the fixture's 310.003 over 7134 steps is a 37-minute scan, where seconds would
make it 25 days.  So :func:`base.sigma_by_arithmetic` decides, exactly as for
the two Rigaku formats: integral values are counts and the Poisson fallback is
correct, an integral ``y·t`` is a rate whose σ is derived, and anything else
withholds σ and says the scale could not be verified.

**v3 is a chain of fixed-size headers, and the ambiguity in it is not one.**
GSAS-II adds a literal 40 bytes to a range header's declared length when the
file holds one range and an ``int32`` from offset +256 when it holds several,
then carries a bare ``except`` that retries the whole data read 40 bytes
earlier; a second reader ignores both and re-anchors a single-range file to
``filesize − 4·n``.  Both are patches over the same two fields neither reads:
**data_record_length** at +252 is v3's datum size, and
**total_size_of_extra_records** at +256 is the length of a chain of optional
records sitting between the header and the data.  With those the data offset is
arithmetic — and the datum is a float32 count followed by one float64 per
*varying* parameter, which is why assuming four bytes per point is what forced
the patches.  ``data_record_length == 4 + 8·popcount(varying_parameters)`` is
the self-consistency gate that says the header was parsed at all.

**The real fixture proves structure and metadata, never values.**  See
``tests/data/README.md``: its header is intact and its intensities are not the
measurement.  It is a v4 file; **v3 has no fixture at all**, so its gates are
deliberately strict — the declared ranges must consume the file exactly — on
the grounds that a visible refusal is recoverable and a silent mis-parse is not.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ...schemas.common import Diagnostic
from ...schemas.pattern import PatternData
from .base import (
    PatternFormat,
    ScanInfo,
    ascending,
    check_axis,
    head,
    multiscan_default,
    pattern_data,
    sigma_by_arithmetic,
)

#: The four magic strings, longest first so ``RAW1.01`` is not read as ``RAW ``
#: would be if the test were four bytes for every version.  The value is the
#: version number this package uses in its own messages.
_MAGIC: tuple[tuple[bytes, int], ...] = (
    (b"RAW1.01", 3),
    (b"RAW4.00", 4),
    (b"RAW2", 2),
    (b"RAW ", 1),
)

#: Where the v4 segment chain begins — the only fixed offset in the format past
#: the preamble's date and time strings.
_V4_SEGMENTS = 61

#: Segment "types" that are not segments: each marks the start of a range.
_RANGE_MARKERS = frozenset({0, 160})

#: Segment payload layouts, as offsets from the segment's own start.
_SEG_KEYVALUE = 10          # uint32 skip, char[24] key, char[len-36] value
_SEG_SOURCE = 30            # 64 skip, then Kα-mean/Kα1/Kα2/Kβ/ratio, then anode
_SEG_DRIVE = 50             # uint32 flag, char[24] name, 20 skip, float64 position

#: A datum is at least one float32; anything smaller cannot hold an intensity.
_MIN_DATUM = 4

#: Runaway guards on numbers a corrupt or misread header can make enormous.
#: Neither is a format limit — they are the difference between a refusal that
#: names the file and an allocation that does not.
_MAX_RANGES = 4096
_MAX_HEADER = 1 << 20

#: Drive names whose stepped axis is the diffraction angle 2θ.
_TWO_THETA_DRIVES = frozenset({"2theta", "twotheta"})

#: Drive names that are recognisably **not** 2θ, with what each one measures.
#: The vocabulary is the set of drive names these files carry (``Theta``,
#: ``2Theta``, ``Chi``, ``Phi``, ``BeamTranslation``, ``Z-Drive``, ``Divergence
#: Slit``), classified by what the goniometer does when each is the scanned one.
_OTHER_DRIVES: dict[str, str] = {
    "theta": "a rocking curve about θ with the detector fixed",
    "omega": "a rocking curve about ω with the detector fixed",
    "phi": "a φ rotation — one ring of a pole figure",
    "chi": "a χ tilt — one arc of a pole figure",
    "khi": "a χ tilt — one arc of a pole figure",
    "psi": "a ψ tilt, as measured for residual stress",
    "zdrive": "a specimen height scan, used to set the sample surface",
    "z": "a specimen height scan, used to set the sample surface",
    "beamtranslation": "a translation of the beam across the specimen",
    "divergenceslit": "a divergence-slit opening scan, not a diffraction scan",
}

#: The scan types the two versions name — **one table**, because they name the
#: same things: v4 writes the words, v3 writes an enumerated code for them.  Each
#: entry is (the abscissa is 2θ, what it is instead).  A name or code **absent**
#: here is unknown, which reads as 2θ with the assumption reported rather than
#: refused: v4's string vocabulary comes from three examples and v3's enum from a
#: single source, so an unfamiliar one is this reader's ignorance, not the file's
#: fault.  ``Detector Scan`` moves the detector alone and ``Locked``/``Unlocked
#: Coupled`` move θ and 2θ together; all three step 2θ.
_SCAN_TYPES: dict[str, tuple[bool, str | None]] = {
    "locked coupled": (True, None),
    "unlocked coupled": (True, None),
    "unlocked coupled hr xrd": (True, None),
    "detector scan": (True, None),
    "rocking curve": (False, "a rocking curve about θ with the detector fixed"),
    "chi scan": (False, "a χ tilt — one arc of a pole figure"),
    "phi scan": (False, "a φ rotation — one ring of a pole figure"),
    "x scan": (False, "a specimen translation in x, used to position the sample"),
    "y scan": (False, "a specimen translation in y, used to position the sample"),
    "z scan": (False, "a specimen height scan, used to set the sample surface"),
    "psi scan": (False, "a ψ tilt, as measured for residual stress"),
    "hkl scan": (False, "a scan along one hkl direction in reciprocal space"),
    "reciprocal-space scan": (False, "a reciprocal-space map, which is a surface "
                                     "and not a profile"),
}

#: v3's numeric spelling of the names above.
_V3_SCAN_CODES: dict[int, str] = {
    0: "locked coupled", 1: "unlocked coupled", 2: "detector scan",
    3: "rocking curve", 4: "chi scan", 5: "phi scan", 6: "x scan", 7: "y scan",
    8: "z scan", 12: "psi scan", 13: "hkl scan", 14: "reciprocal-space scan",
    20: "unlocked coupled hr xrd",
}


def _scan_type_axis(name: str, *, field: str, note: str) -> _Axis:
    """The axis a *named* scan type implies — shared by both versions."""
    two_theta, other = _SCAN_TYPES.get(name.strip().lower(), (False, None))
    return _Axis(stated=name, field=field, two_theta=two_theta, other=other,
                 remedy="Export the coupled θ–2θ range instead.",
                 note="" if two_theta else note)


def _key(name: str) -> str:
    return name.lower().replace(" ", "").replace("-", "").replace("_", "")


@dataclass(frozen=True)
class _Drive:
    """One goniometer axis as a v4 range header records it."""

    name: str
    #: non-zero on exactly one record in the real fixture — the scanned drive.
    #: Not trusted alone: see :func:`_v4_axis`
    flag: int
    position: float


@dataclass(frozen=True)
class _Axis:
    """The scanned-axis question as one version's vocabulary answers it.

    The two versions state the axis in inputs of different shapes — v4 in a
    drive record's name, v3 in an enumerated scan-type code — so each classifies
    for itself and hands the verdict to :func:`base.check_axis`, which is the
    same split every other format in this package uses.
    """

    stated: str
    field: str
    two_theta: bool
    other: str | None = None
    remedy: str = ""
    note: str = ""


@dataclass(frozen=True)
class _Range:
    """One measurement inside a ``.raw`` file, located but not yet decoded."""

    axis: _Axis
    start: float
    step: float
    n_points: int
    #: seconds per step, or ``None`` where the file's own number is unusable
    count_time_s: float | None
    #: the stride, which both versions declare and neither of the two consulted
    #: readers uses: v4 calls it ``datumSize``, v3 ``data_record_length``
    datum_size: int
    #: where the intensity records begin, and where the range as a whole ends
    data_at: int
    end: int
    #: byte offset **within a datum** of a measured 2θ (float64), where the file
    #: stores one per point rather than implying it from start and step.  Only
    #: v3 does, and only when its ``varying_parameters`` says so
    two_theta_at: int | None = None
    label: str = ""
    generator_kv: float | None = None
    generator_ma: float | None = None
    wavelength: float | None = None
    temperature_k: float | None = None

    @property
    def implied_two_theta(self) -> np.ndarray:
        return self.start + self.step * np.arange(self.n_points, dtype=np.float64)


def _unpack(fmt: str, buf: bytes, at: int, *, path: Path, what: str) -> tuple:
    """``struct.unpack_from`` that refuses by naming the file, never ``struct.error``."""
    try:
        return struct.unpack_from(fmt, buf, at)
    except struct.error:
        raise ValueError(
            f"{path.name}: the file ends inside {what} — it wants "
            f"{struct.calcsize(fmt)} bytes at offset {at} and holds "
            f"{len(buf)}. The file is truncated or is not the format its magic "
            "bytes claim") from None


def _text(buf: bytes, at: int, length: int) -> str:
    """A fixed-width NUL-padded field, decoded permissively.

    ``latin-1`` rather than UTF-8 because these are Windows-written operator
    strings — a sample name with a degree sign in it must not make the file
    unreadable — and ``errors`` cannot help a codec that would reject nothing.
    """
    return buf[at:at + length].split(b"\0")[0].decode("latin-1").strip()


def _segment(buf: bytes, at: int, *, path: Path) -> tuple[int, int]:
    """The ``(type, length)`` at ``at``, with length clamped and bounds checked."""
    kind, declared = _unpack("<II", buf, at, path=path, what="a segment header")
    length = max(declared, 8)
    if at + length > len(buf):
        raise ValueError(
            f"{path.name}: a segment of type {kind} at offset {at} declares "
            f"{length} bytes but only {len(buf) - at} remain. The file is "
            "truncated")
    return kind, length


def _drives(buf: bytes, at: int, size: int, *, path: Path) -> tuple[_Drive, ...]:
    """Every drive record in a range header's nested chain of ``size`` bytes.

    The chain must land **exactly** on the declared end.  That is the
    self-consistency gate this format needs most: a mis-parsed length walks off
    into the intensity records and finds plausible-looking segments there, so
    "ended where it said it would" is the difference between a parse and a
    coincidence.
    """
    out: list[_Drive] = []
    cursor, end = at, at + size
    if end > len(buf):
        raise ValueError(f"{path.name}: the range header declares {size} bytes of "
                         f"drive records at offset {at}, past the end of a "
                         f"{len(buf)}-byte file")
    while cursor < end:
        kind, length = _segment(buf, cursor, path=path)
        if kind == _SEG_DRIVE:
            flag, = _unpack("<I", buf, cursor + 8, path=path, what="a drive flag")
            position, = _unpack("<d", buf, cursor + 56, path=path,
                                what="a drive position")
            out.append(_Drive(name=_text(buf, cursor + 12, 24), flag=flag,
                              position=position))
        cursor += length
    if cursor != end:
        raise ValueError(
            f"{path.name}: the range header's segments overrun the {size} bytes "
            f"it declares — they end at offset {cursor}, {cursor - end} byte(s) "
            "past. The header is not the layout this reader knows")
    return tuple(out)


def _v4_axis(scan_type: str, drives: tuple[_Drive, ...], start: float) -> _Axis:
    """Which drive was stepped, from two statements that have to agree.

    A drive record's flag is non-zero on exactly one record in the only real
    file, and that record's stored position is also the range's start angle.
    One file is not enough to trust either statement alone, so the scanned drive
    is the one both pick out.  A ``Locked Coupled`` scan moves θ and 2θ together
    and the flagged record is ``2Theta``, whose 10.0° is the start angle while
    ``Theta`` sits at 5.0 — so the position test is what separates the abscissa
    from the drives that merely moved.
    """
    candidates = [d for d in drives
                  if d.flag and np.isclose(d.position, start, atol=1e-6)]
    if len(candidates) != 1:
        # fall back to what the file calls the *kind* of scan.  Less specific —
        # it names the coupling rather than the axis — but it is a statement the
        # file makes about the same thing, and it is what GSAS-II validates on.
        # A recognisably non-2θ type is **refused** here rather than assumed: a
        # file saying "Rocking Curve" has told us the abscissa is not 2θ, and
        # nothing about its drive records makes that less true
        return _scan_type_axis(
            scan_type, field="ScanType",
            note=(" No single drive record is flagged as the scanned one at the "
                  "range's start angle, so the scan type had to answer instead."))
    scanned = candidates[0].name
    return _Axis(stated=scanned, field="the scanned drive",
                 two_theta=_key(scanned) in _TWO_THETA_DRIVES,
                 other=_OTHER_DRIVES.get(_key(scanned)),
                 remedy="Export the coupled θ–2θ range instead.",
                 note=f" The file calls this scan a {scan_type!r}.")


def _read_v4_range(buf: bytes, marker: int, *, path: Path) -> _Range:
    """One v4 range, located from its marker at ``marker`` — the field table.

    Offsets are relative to ``p``, the start angle, which sits 72 bytes past the
    marker: 4 for the marker word itself, 28 unread, 24 of ``ScanType`` and 16
    more unread.
    """
    scan_type = _text(buf, marker + 32, 24)
    p = marker + 72
    start, step = _unpack("<dd", buf, p, path=path, what="a range's start and step")
    n_points, = _unpack("<I", buf, p + 16, path=path, what="a range's point count")
    step_time_ms, = _unpack("<f", buf, p + 20, path=path, what="a range's step time")
    kv, ma = _unpack("<ff", buf, p + 28, path=path, what="the generator settings")
    wavelength, = _unpack("<d", buf, p + 40, path=path, what="the wavelength")
    datum_size, hdr_size = _unpack("<II", buf, p + 64, path=path,
                                   what="the datum and header sizes")

    if n_points < 1:
        raise ValueError(f"{path.name}: a range declares {n_points} points")
    if datum_size < _MIN_DATUM or datum_size % 4:
        raise ValueError(
            f"{path.name}: a range declares a datum of {datum_size} bytes; an "
            f"intensity is a float32, so a datum is a multiple of 4 and at "
            f"least {_MIN_DATUM}")
    if step == 0.0 or not np.isfinite(step) or not np.isfinite(start):
        raise ValueError(f"{path.name}: a range steps by {step!r} from {start!r}, "
                         "which is not a scan this reader can put on an axis")

    drives = _drives(buf, p + 88, hdr_size, path=path)
    data_at = p + 88 + hdr_size
    end = data_at + datum_size * n_points
    if end > len(buf):
        raise ValueError(
            f"{path.name}: a range declares {n_points} points of {datum_size} "
            f"bytes from offset {data_at}, which needs {end} bytes and the file "
            f"holds {len(buf)}. The file is truncated")

    # milliseconds, and a scan whose step time is zero or absurd tells us nothing
    # about its counting statistics — so no counting time rather than a wrong one
    time_s = step_time_ms / 1000.0 if 0.0 < step_time_ms < 1e9 else None
    return _Range(axis=_v4_axis(scan_type, drives, start), label=scan_type,
                  start=start, step=step, n_points=n_points, count_time_s=time_s,
                  generator_kv=kv, generator_ma=ma, wavelength=wavelength,
                  datum_size=datum_size, data_at=data_at, end=end)


@dataclass(frozen=True)
class _File:
    """A ``.raw`` file's file-level header and every range in it, located."""

    version: int
    ranges: tuple[_Range, ...]
    keys: dict[str, str] = field(default_factory=dict)
    anode: str | None = None
    wavelengths: tuple[float, ...] = ()
    goniometer_radius_mm: float | None = None


def _read_v4(buf: bytes, *, path: Path) -> _File:
    """Walk the whole file: segments until a range marker, a range, repeat.

    To EOF rather than to a count, because there is no count to read — and the
    one other reader that invents one gets it wrong on the only real file.
    """
    keys: dict[str, str] = {}
    anode: str | None = None
    waves: tuple[float, ...] = ()
    ranges: list[_Range] = []

    cursor = _V4_SEGMENTS
    while cursor + 4 <= len(buf):
        kind, = _unpack("<I", buf, cursor, path=path, what="a segment type")
        if kind in _RANGE_MARKERS:
            found = _read_v4_range(buf, cursor, path=path)
            ranges.append(found)
            cursor = found.end
            continue
        kind, length = _segment(buf, cursor, path=path)
        if kind == _SEG_KEYVALUE:
            keys[_text(buf, cursor + 12, 24).upper()] = _text(buf, cursor + 36,
                                                              length - 36)
        elif kind == _SEG_SOURCE:
            base = cursor + 72
            waves = _unpack("<5d", buf, base, path=path, what="the tube wavelengths")
            anode = _text(buf, base + 44, 4) or None
        cursor += length

    if not ranges:
        raise ValueError(
            f"{path.name}: the header parses as Bruker RAW4 but the file holds "
            "no measurement range. It is either truncated before its data or is "
            "a settings file rather than a scan")
    return _File(version=4, ranges=tuple(ranges), keys=keys, anode=anode,
                 wavelengths=waves)


def _version(p: Path) -> int:
    """Which of the four RAW formats ``p`` is, by magic bytes."""
    raw = head(p, 8).raw
    for magic, version in _MAGIC:
        if raw.startswith(magic):
            return version
    raise ValueError(f"{p.name}: not a Bruker RAW file — its first bytes are "
                     f"{raw[:8]!r}")


#: v2 (``RAW2``), WP-2059.  The block count is a file-level uint32; the block
#: header starts at a fixed 0x100 and the offsets after it are relative to it.
#: Its first field is the header's own length, which is what places the data.
_V2_BLOCK_COUNT = 4
_V2_BLOCK = 0x100
_V2_POINTS = 2
_V2_STEP = 12
_V2_START = 16


def _read_v2(buf: bytes, *, path: Path) -> _File:
    """v2's one block: a header that states its own length, then ``n`` float32s.

    Every gate is one the file can fail.  The block count must be 1, ``n`` must
    be positive, and the header length and ``n`` together must account for the
    file to the byte: a header length or a point count read from the wrong
    offset lands the data's end anywhere but on the file's.
    """
    blocks, = _unpack("<I", buf, _V2_BLOCK_COUNT, path=path,
                      what="the block count")
    if blocks != 1:
        what = (f"{blocks} blocks, a multi-range v2 file, which this reader "
                "refuses until one has been seen to check the layout against"
                if blocks > 1 else
                f"{blocks} blocks, so it holds no measurement")
        raise ValueError(f"{path.name}: the Bruker RAW version 2 header "
                         f"declares {what}")
    header_len, = _unpack("<H", buf, _V2_BLOCK, path=path,
                          what="the block header's length")
    n_points, = _unpack("<H", buf, _V2_BLOCK + _V2_POINTS, path=path,
                        what="the block's point count")
    step, = _unpack("<f", buf, _V2_BLOCK + _V2_STEP, path=path,
                    what="the block's step")
    start, = _unpack("<f", buf, _V2_BLOCK + _V2_START, path=path,
                     what="the block's start angle")
    if n_points < 1:
        raise ValueError(f"{path.name}: the Bruker RAW version 2 block declares "
                         f"{n_points} points")
    if step == 0.0 or not np.isfinite(step) or not np.isfinite(start):
        raise ValueError(f"{path.name}: the block steps by {step!r} from "
                         f"{start!r}, which is not a scan this reader can put "
                         "on an axis")
    data_at = _V2_BLOCK + header_len
    end = data_at + 4 * n_points
    if end != len(buf):
        raise ValueError(
            f"{path.name}: the Bruker RAW version 2 block header declares a "
            f"length of {header_len} bytes and {n_points} points, so its counts "
            f"would end at offset {end}, and the file is {len(buf)} bytes. The "
            "header was not read at the offsets this reader knows, or the file "
            "is not a single-range v2 file")
    # the description names these two fields as 2θ, so the axis is stated by the
    # layout rather than assumed; there is no scan-type field to classify
    return _File(version=2, ranges=(_Range(
        axis=_Axis(stated="", field="the scan axis", two_theta=True),
        label="2θ", start=start, step=step, n_points=n_points,
        count_time_s=None, datum_size=4, data_at=data_at, end=end),))


#: The v3 file header, before the first range header.
_V3_HEADER = 712

#: v3 range-header field offsets that this reader reads, relative to its start.
_V3_POINTS = 4
_V3_TWO_THETA_START = 16
_V3_STEP = 176
_V3_STEP_TIME = 192
_V3_SCAN_TYPE = 196
_V3_TEMPERATURE = 212
_V3_WAVELENGTH = 240
_V3_VARYING = 248
_V3_RECORD_LENGTH = 252
_V3_EXTRA_RECORDS = 256
#: the last field read above ends here, so a header shorter than this is not one
_V3_MIN_HEADER = _V3_EXTRA_RECORDS + 4

#: v3's ``varying_parameters`` bits, in the order their float64 columns follow
#: the float32 count inside a datum.  Only the first matters to this reader —
#: when it is set, the file stores a *measured* 2θ per point and the implied
#: ``start + i·step`` is not used.
_V3_VARYING_BITS = ("two_theta", "theta", "chi", "phi", "x", "y", "z",
                    "aux1", "aux2", "aux3", "time", "temp")

def _v3_axis(code: int) -> _Axis:
    """v3 states its axis as a number, which is the sixth shape this package
    classifies — hence :data:`_V3_SCAN_CODES` here and the shared verdict in
    ``check_axis``."""
    return _scan_type_axis(
        _V3_SCAN_CODES.get(code, f"scan type {code}"), field="the scan type",
        note=(" The scan-type code is one this reader has no name for, and its "
              "table has a single source."))


def _read_v3(buf: bytes, *, path: Path) -> _File:
    """Walk v3's chain: a 712-byte file header, then one block per range.

    Each block is a header whose own length it declares, then
    ``total_size_of_extra_records`` bytes of optional records, then the data —
    and the datum is ``data_record_length`` bytes, not four.  Reading those two
    fields is the whole difference between this and the two readers that patch
    around them; ``data_record_length == 4 + 8·popcount(varying_parameters)`` is
    asserted, because a header parsed at the wrong offset will not satisfy it.
    """
    n_ranges, = _unpack("<i", buf, 12, path=path, what="the range count")
    if not 1 <= n_ranges <= _MAX_RANGES:
        raise ValueError(f"{path.name}: the header declares {n_ranges} ranges, "
                         f"which is not a number of measurements (1 to "
                         f"{_MAX_RANGES})")
    radius, = _unpack("<f", buf, 564, path=path, what="the goniometer radius")

    ranges: list[_Range] = []
    cursor = _V3_HEADER
    for _ in range(n_ranges):
        header_len, = _unpack("<i", buf, cursor, path=path,
                              what="a range header length")
        if not _V3_MIN_HEADER <= header_len <= _MAX_HEADER:
            raise ValueError(
                f"{path.name}: a range header at offset {cursor} declares a "
                f"length of {header_len} bytes, which cannot hold the fields "
                f"this format puts in the first {_V3_MIN_HEADER}")
        n_points, = _unpack("<i", buf, cursor + _V3_POINTS, path=path,
                            what="a range's point count")
        start, = _unpack("<d", buf, cursor + _V3_TWO_THETA_START, path=path,
                         what="a range's 2θ start")
        step, = _unpack("<d", buf, cursor + _V3_STEP, path=path,
                        what="a range's step")
        step_time, = _unpack("<f", buf, cursor + _V3_STEP_TIME, path=path,
                             what="a range's step time")
        code, = _unpack("<i", buf, cursor + _V3_SCAN_TYPE, path=path,
                        what="a range's scan type")
        temperature, = _unpack("<f", buf, cursor + _V3_TEMPERATURE, path=path,
                               what="a range's temperature")
        wavelength, = _unpack("<d", buf, cursor + _V3_WAVELENGTH, path=path,
                              what="a range's wavelength")
        varying, record_len, extra = _unpack(
            "<iii", buf, cursor + _V3_VARYING, path=path,
            what="a range's varying parameters, record length and extra records")

        if n_points < 1:
            raise ValueError(f"{path.name}: a range declares {n_points} points")
        if step == 0.0 or not np.isfinite(step) or not np.isfinite(start):
            raise ValueError(f"{path.name}: a range steps by {step!r} from "
                             f"{start!r}, which is not a scan this reader can "
                             "put on an axis")
        columns = int(varying).bit_count() if 0 <= varying < 2 ** 31 else -1
        if record_len != 4 + 8 * columns:
            raise ValueError(
                f"{path.name}: a range declares a data record of {record_len} "
                f"bytes and varying parameters {varying:#x}, which wants "
                f"{4 + 8 * columns}. The two disagree, so the header was not "
                "read at the offset this format puts it")
        if extra < 0 or extra > _MAX_HEADER:
            raise ValueError(f"{path.name}: a range declares {extra} bytes of "
                             "extra records, which is not a length")

        data_at = cursor + header_len + extra
        end = data_at + record_len * n_points
        if end > len(buf):
            raise ValueError(
                f"{path.name}: a range declares {n_points} points of "
                f"{record_len} bytes from offset {data_at}, which needs {end} "
                f"bytes and the file holds {len(buf)}. The file is truncated")

        ranges.append(_Range(
            axis=_v3_axis(code), label=_V3_SCAN_CODES.get(code, "?"),
            start=start, step=step, n_points=n_points,
            count_time_s=step_time if 0.0 < step_time < 1e6 else None,
            datum_size=record_len, data_at=data_at, end=end,
            two_theta_at=4 if varying & 1 else None,
            wavelength=wavelength,
            temperature_k=temperature if temperature > 0.0 else None))
        cursor = end

    # the global gate, and the reason v3 can be shipped without a fixture: the
    # ranges it declares must account for the file.  Alignment padding is real,
    # a whole misread range is not, so the tolerance is one datum's worth of
    # slack -- and, past that, the leftover's *content* rather than its length.
    # A range read at the wrong offset leaves counts behind, and counts are not
    # zeros; a real DIFFRAC file zero-pads its tail (measured: 3280 zero bytes
    # past 82 ranges of a VT reel, which the length-only gate refused).
    tail = buf[cursor:]
    if len(tail) >= 8 and any(tail):
        raise ValueError(
            f"{path.name}: the {n_ranges} range(s) it declares end at offset "
            f"{cursor} and the file is {len(buf)} bytes, leaving "
            f"{len(tail)} unaccounted for, the first non-zero byte of them at "
            f"offset {cursor + next(i for i, b in enumerate(tail) if b)}. The "
            "layout is not the one this reader knows, and a pattern read from "
            "it would be wrong rather than short")
    return _File(version=3, ranges=tuple(ranges), anode=_text(buf, 608, 4) or None,
                 keys={"SAMPLEID": _text(buf, 326, 60)},
                 goniometer_radius_mm=radius if 0.0 < radius < 1e4 else None)


def _parse(p: Path) -> tuple[bytes, _File]:
    """The file's bytes and its ranges, or a refusal naming the version."""
    version = _version(p)
    if version == 1:
        raise ValueError(
            f"{p.name} is Bruker RAW version 1, which this build does not read: "
            "no description of it exists, so a reader would be guessing at your "
            "intensities. Re-export it from DIFFRAC as RAW4, or convert it to "
            ".uxd, .xy or GSAS .fxye, all of which this build reads")
    buf = p.read_bytes()
    read = {2: _read_v2, 3: _read_v3, 4: _read_v4}[version]
    return buf, read(buf, path=p)


def _decode(buf: bytes, found: _Range, *, path: Path) -> tuple[np.ndarray,
                                                               np.ndarray]:
    """A range's 2θ and intensity, strided by the datum size the file declares.

    The leading float32 of each datum is the intensity in both versions.  What
    follows it differs — v4's real file carries four bytes nobody has explained,
    v3 carries one float64 per varying parameter — so the rest is stepped over
    except for the one column that is *2θ measured per point*, which a v3 file
    stores when its scan varies 2θ and which beats ``start + i·step``.
    """
    records = np.frombuffer(buf, dtype=np.uint8, offset=found.data_at,
                            count=found.datum_size * found.n_points,
                            ).reshape(found.n_points, found.datum_size)
    y = np.ascontiguousarray(records[:, :4]).view("<f4").reshape(-1)
    y = np.asarray(y, dtype=np.float64)
    if not np.all(np.isfinite(y)):
        raise ValueError(f"{path.name}: {int((~np.isfinite(y)).sum())} of "
                         f"{y.size} intensities are not finite numbers, so the "
                         "data block is not float32 at the stride the header "
                         "declares")
    if found.two_theta_at is None:
        return found.implied_two_theta, y
    at = found.two_theta_at
    tt = np.ascontiguousarray(records[:, at:at + 8]).view("<f8").reshape(-1)
    tt = np.asarray(tt, dtype=np.float64)
    if not np.all(np.isfinite(tt)):
        raise ValueError(f"{path.name}: the range stores a measured 2θ per point "
                         "and some of them are not finite numbers")
    return tt, y


def read_bruker_raw(path: str | Path, *, scan: int | None = None,
                    diagnostics: list[Diagnostic] | None = None) -> PatternData:
    p = Path(path)
    buf, parsed = _parse(p)
    multiscan_default(len(parsed.ranges), scan, path=p, diagnostics=diagnostics)

    index = 0 if scan is None else scan
    if not 0 <= index < len(parsed.ranges):
        raise ValueError(f"{p.name} holds {len(parsed.ranges)} range(s), numbered "
                         f"0 to {len(parsed.ranges) - 1}; scan={index} is not one "
                         "of them")
    found = parsed.ranges[index]

    axis = check_axis(found.axis.stated, path=p, field=found.axis.field,
                      two_theta=found.axis.two_theta, other=found.axis.other,
                      remedy=found.axis.remedy, note=found.axis.note,
                      diagnostics=diagnostics)
    tt, y = _decode(buf, found, path=p)
    sigma = sigma_by_arithmetic(y, found.count_time_s, "", path=p,
                                diagnostics=diagnostics)
    tt, y, sig = ascending(tt, y, sigma, path=p, fmt=BRUKER_RAW,
                           diagnostics=diagnostics)
    # recorded verbatim, **zero included**: a v4 source segment writing Kα2 = 0
    # with its Kα-mean equal to Kα1 is the file saying the doublet was not used,
    # which is what lets the import wizard suggest the Kα1-only radiation on
    # evidence rather than on a guess.  A format that records no such field says
    # nothing, and ``metadata()`` drops the None
    alpha2 = parsed.wavelengths[2] if len(parsed.wavelengths) > 2 else None
    return pattern_data(
        p, tt, y, sig,
        source_file=p.name, format="bruker_raw", scan=index,
        scan_count=len(parsed.ranges), scan_axis=axis,
        sample=parsed.keys.get("SAMPLEID") or None,
        title=parsed.keys.get("COMMENT") or None,
        anode=parsed.anode,
        wavelength=found.wavelength or None,
        wavelength_alpha2=alpha2,
        goniometer_radius_mm=parsed.goniometer_radius_mm,
        count_time_s=found.count_time_s,
        # v3 only: v4 range headers carry no such field.  It was parsed and
        # dropped until WP-1110, so an agent on a 68-pattern in-situ reel read
        # ``_Range.temperature_k`` off this module's private ``_parse`` to
        # recover its own series coordinate.
        temperature_k=found.temperature_k)


def list_bruker_raw_scans(path: str | Path) -> list[ScanInfo]:
    _, parsed = _parse(Path(path))
    out: list[ScanInfo] = []
    for i, found in enumerate(parsed.ranges):
        stepped = found.implied_two_theta
        low, high = float(min(stepped[0], stepped[-1])), float(max(stepped[0],
                                                                  stepped[-1]))
        # the temperature goes in the label as well as the field, because on a
        # VT reel it is the only thing that differs: every range of the trigger
        # dataset's 68 scans the same axis over the same angles, so without it
        # the picker shows 68 identical rows — which is exactly what
        # ``ScanInfo.label`` says it must not do
        at = "" if found.temperature_k is None else f" at {found.temperature_k:.4g} K"
        out.append(ScanInfo(
            index=i,
            label=f"{found.axis.stated or found.label or '?'} "
                  f"{low:.4g}–{high:.4g}°{at}",
            n_points=found.n_points, two_theta_range=(low, high),
            temperature_k=found.temperature_k))
    return out


def looks_bruker_raw(p: Path) -> bool:
    """Magic bytes, and nothing else — the strongest evidence in the registry.

    Disjoint from GSAS raw by construction: that format is claimed by a ``BANK``
    record, so a GSAS file named ``.raw`` still reaches it and a Bruker file
    named ``.gsas`` still reaches this one.
    """
    raw = head(p, 8).raw
    return any(raw.startswith(magic) for magic, _ in _MAGIC)


BRUKER_RAW = PatternFormat(
    name="bruker_raw",
    title="Bruker/Siemens DIFFRAC binary (.raw, v2/v3/v4)",
    extensions=(".raw",),
    sniff="the file begins RAW4.00, RAW1.01 or RAW2 (or 'RAW ', which is "
          "named and refused as the version no description of exists; so is a "
          "v2 file holding more than one range)",
    sigma=("measured per file: integral intensities are counts and take the "
           "Poisson fallback, an integral y·t is a rate whose σ is derived from "
           "the header's step time, and anything else withholds σ — no "
           "version declares an intensity unit anywhere, and v2's step time "
           "is not read"),
    matches=looks_bruker_raw,
    read=read_bruker_raw,
    options=("scan",),
    scans=list_bruker_raw_scans,
)
