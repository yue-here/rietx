"""Writers for the **binary** vendor formats, which have no vendorable fixture.

The text formats' writers live inline in ``test_readers.py``: writing a
``.uxd`` or a ``.ras`` is writing lines, and a line is self-describing.  A
binary format is not, and packing one raises a circularity the text ones never
face — a fixture built from the reader's own understanding agrees with the
reader by construction and proves nothing about the format.  Three rules keep
that from being what these writers are:

1. **The offsets here are written literally, and are not shared with the
   reader.**  Not an import, not a constant, not a helper: if
   ``bruker_raw.py``'s field table drifts, these functions keep packing the old
   one and the tests fail.  A writer that consulted the reader could only ever
   confirm that the reader agrees with itself.
2. **The offsets were cross-checked against a second, independent
   description.**  For Bruker RAW v4 the two that agree are (a) the real file
   ``tests/data/bruker_raw4_scrambled.raw``, walked byte by byte and reported in
   ``tests/data/README.md``, and (b) GSAS-II's ``G2pwd_BrukerRAW.py``, read as a
   specification only.  Where a third description exists — FAIRmat's
   ``bruker_raw_parser.py`` — it is not independent: it hard-codes absolute
   offsets taken from that same file.  For **v3** there are three that agree —
   GSAS-II, ``bracerino/xrd-file-converter`` (MIT) and ``reductus/reductus``
   (Unlicense), the last a field-by-field transcription of Bruker's own header
   definition — and **no** file at all, which is why v3's gates in the reader
   are the strict ones.  For **v2** the two are a hand decode of a real public
   file (Durham's ``Pbso4.raw``, never vendored: ``tests/local_data.py``) and
   GSAS-II's description, with TOPAS's reading of the same file as a black-box
   third (issue #1164, WP-2059).
3. **The reader carries a self-consistency gate**, so a wrong parse raises
   rather than returning plausible garbage: a range header's nested segment
   chain must end *exactly* on the declared ``hdrSize``, and
   ``data + datumSize·nSteps`` must land on the next range or on EOF.  These
   writers exist partly to violate those gates on purpose.

So what a synthesized file exercises is the reader's **failure paths and its
options** — a second range, a narrower datum, a drive that is not 2θ, a header
that overruns — never the format itself.  The real fixture is the only evidence
about the format, and it is evidence about structure alone (its intensities are
scrambled; ``tests/data/README.md`` has the measurement).
"""

from __future__ import annotations

import math
import struct
from pathlib import Path

#: Bruker RAW v4, packed from the literal field table — see rule 1 above.
_V4_MAGIC = b"RAW4.00\x00"
_V4_SEGMENT_START = 61


def _fixed(text: str, width: int) -> bytes:
    """A NUL-padded fixed-width field, refusing text that would not fit."""
    raw = text.encode("latin-1")
    if len(raw) >= width:
        raise ValueError(f"{text!r} does not fit a {width}-byte field")
    return raw + b"\x00" * (width - len(raw))


def _keyvalue(key: str, value: str) -> bytes:
    """A type-10 segment: uint32 type, uint32 length, 4 unused, key[24], value."""
    body = value.encode("latin-1") + b"\x00"
    return (struct.pack("<III", 10, 36 + len(body), 0) + _fixed(key, 24) + body)


def _source(anode: str, waves: tuple[float, float, float, float, float]) -> bytes:
    """A type-30 segment: 64 unused, then Kα-mean/Kα1/Kα2/Kβ/ratio, 4, anode[4]."""
    body = (b"\x00" * 64 + struct.pack("<5d", *waves) + b"\x00" * 4
            + _fixed(anode, 4))
    return struct.pack("<II", 30, 8 + len(body) + 12) + body + b"\x00" * 12


def _drive(name: str, position: float, flag: int) -> bytes:
    """A type-50 segment, 92 bytes: flag, name[24], 20 unused, position."""
    body = (struct.pack("<I", flag) + _fixed(name, 24) + b"\x00" * 20
            + struct.pack("<d", position))
    return struct.pack("<II", 50, 92) + body + b"\x00" * (92 - 8 - len(body))


def write_raw4(path: Path, ranges, *, sample="Synthesized", comment="",
               anode="Cu", waves=(1.5418, 1.5406, 1.5444, 1.3922, 0.5),
               marker=0, header_overrun=0) -> Path:
    """A Bruker RAW v4 file holding ``ranges``.

    Each range is a dict: ``start``, ``step``, ``intensity`` (the values, in
    order), and optionally ``scan_type``, ``drives`` (``(name, position, flag)``
    triples, defaulting to a locked-coupled θ/2θ pair with 2Theta flagged),
    ``datum_size`` (4 or more, a multiple of 4) and ``step_time_ms``.

    ``header_overrun`` mis-states ``hdrSize`` by that many bytes without moving
    the data, which is what the reader's "the chain must end exactly here" gate
    is for; ``marker`` picks which of the two range markers to write.
    """
    out = bytearray(_V4_MAGIC + struct.pack("<I", 0xFFEF)
                    + _fixed("04/07/2025", 12) + _fixed("20:48:56", 10))
    out += b"\x00" * (_V4_SEGMENT_START - len(out))
    out += _keyvalue("USER", "Administrator")
    out += _keyvalue("SAMPLEID", sample)
    out += _keyvalue("COMMENT", comment)
    out += _source(anode, waves)

    for spec in ranges:
        drives = spec.get("drives", (("2Theta", spec["start"], 0),
                                     ("Theta", spec["start"] / 2, 0),
                                     ("2Theta", spec["start"], 2)))
        datum = spec.get("datum_size", 8)
        header = b"".join(_drive(*d) for d in drives)
        y = list(spec["intensity"])

        out += struct.pack("<I", marker)
        out += b"\x00" * 28
        out += _fixed(spec.get("scan_type", "Locked Coupled"), 24)
        out += b"\x00" * 16
        out += struct.pack("<dd", spec["start"], spec["step"])
        out += struct.pack("<I", len(y))
        out += struct.pack("<f", spec.get("step_time_ms", 310.0))
        out += b"\x00" * 4
        out += struct.pack("<ff", 40.0, 40.0)
        out += b"\x00" * 4
        out += struct.pack("<d", waves[1])
        out += b"\x00" * 16
        out += struct.pack("<II", datum, len(header) + header_overrun)
        out += b"\x00" * 16
        out += header
        for value in y:
            out += struct.pack("<f", value) + b"\x00" * (datum - 4)

    path.write_bytes(bytes(out))
    return path


#: Bruker RAW v3 (`RAW1.01`), packed from its own literal field table.
_V3_MAGIC = b"RAW1.01\x00"
_V3_HEADER = 712
#: the range header's own declared length here.  The format lets it vary — the
#: reader reads the declared value — so the writer picks a size that is not the
#: minimum, which is what makes "data starts at header + extras" testable.
_V3_RANGE_HEADER = 304


def _v3_extra(record_type: int, length: int) -> bytes:
    """One optional record between a range header and its data.

    These are what `total_size_of_extra_records` counts, and what GSAS-II's
    literal `+40` is standing in for. Content is irrelevant to a pattern reader;
    only the `(type, length)` pair and the total are.
    """
    return struct.pack("<ii", record_type, length) + b"\x00" * (length - 8)


def write_raw3(path: Path, ranges, *, sample="Synthesized", anode="Cu",
               radius=250.0, trailing=b"") -> Path:
    """A Bruker RAW v3 file holding `ranges`.

    Each range is a dict: `start`, `step`, `intensity`, and optionally
    `scan_type` (the enumerated code, default 0 = locked coupled), `step_time`,
    `wavelength`, `extras` (a list of `(type, length)` optional records) and
    `two_theta` (measured positions, which set the varying-2θ bit and put a
    float64 column in every datum).

    `trailing` appends bytes past the last range, which the reader's
    "the declared ranges must account for the file" gate is for.
    """
    header = bytearray(b"\x00" * _V3_HEADER)
    header[0:8] = _V3_MAGIC
    header[12:16] = struct.pack("<i", len(ranges))
    header[16:26] = _fixed("04/07/25", 10)
    header[26:36] = _fixed("20:48:56", 10)
    header[326:386] = _fixed(sample, 60)
    header[564:568] = struct.pack("<f", radius)
    header[608:612] = _fixed(anode, 4)
    out = bytearray(header)

    for spec in ranges:
        y = list(spec["intensity"])
        measured = spec.get("two_theta")
        columns = 1 if measured is not None else 0
        varying = 1 if measured is not None else 0
        record_length = 4 + 8 * columns
        extras = b"".join(_v3_extra(t, ln) for t, ln in spec.get("extras", ()))

        block = bytearray(b"\x00" * _V3_RANGE_HEADER)
        block[0:4] = struct.pack("<i", _V3_RANGE_HEADER)
        block[4:8] = struct.pack("<i", len(y))
        block[8:16] = struct.pack("<d", spec["start"] / 2)          # θ start
        block[16:24] = struct.pack("<d", spec["start"])             # 2θ start
        block[176:184] = struct.pack("<d", spec["step"])
        block[192:196] = struct.pack("<f", spec.get("step_time", 1.0))
        block[196:200] = struct.pack("<i", spec.get("scan_type", 0))
        block[212:216] = struct.pack("<f", spec.get("temperature", 0.0))
        block[240:248] = struct.pack("<d", spec.get("wavelength", 1.5406))
        block[248:252] = struct.pack("<i", spec.get("varying", varying))
        block[252:256] = struct.pack("<i", spec.get("record_length",
                                                    record_length))
        block[256:260] = struct.pack("<i", len(extras))
        out += block + extras

        for i, value in enumerate(y):
            out += struct.pack("<f", value)
            if measured is not None:
                out += struct.pack("<d", measured[i])

    out += trailing
    path.write_bytes(bytes(out))
    return path


#: Bruker RAW v2 (`RAW2`), packed from its own literal field table (WP-2059).
_V2_MAGIC = b"RAW2"
#: the real file's block-header length.  The reader reads the declared value,
#: so a test that moves it moves the data with it.
_V2_HEADER = 68
#: what the bytes this table does not name are filled with: not zero, so a
#: reader that took a field from one of them reads nonsense and fails a gate
_V2_FILL = 0xA5


def write_raw2(path: Path, counts, *, start=10.0, step=0.025, blocks=1,
               header_length=_V2_HEADER, points=None, trailing=b"") -> Path:
    """A single-block Bruker RAW v2 file holding `counts` as float32.

    `blocks` is the uint32 at 4, `header_length` the uint16 at 0x100 (the
    block header is padded to it, so the counts start at 0x100 + it), and
    `points` overrides the uint16 point count at 0x102.  `trailing` appends
    bytes past the counts, which the reader's size gate is for.
    """
    y = list(counts)
    if header_length < 20:
        raise ValueError("a v2 block header holds its start angle at +16")
    out = bytearray([_V2_FILL]) * (0x100 + header_length)
    out[0:4] = _V2_MAGIC
    out[4:8] = struct.pack("<I", blocks)
    out[0x100:0x102] = struct.pack("<H", header_length)
    out[0x102:0x104] = struct.pack("<H", len(y) if points is None else points)
    out[0x10C:0x110] = struct.pack("<f", step)
    out[0x110:0x114] = struct.pack("<f", start)
    for value in y:
        out += struct.pack("<f", value)
    out += trailing
    path.write_bytes(bytes(out))
    return path


#: Philips PC-APD, packed from the literal field table — see rule 1 above.  The
#: offsets were derived from **28 real V3 files** before the reader was written
#: (``tests/data/README.md`` § Philips) and agree with both published
#: descriptions; they are repeated here rather than imported so the two cannot
#: drift together.
_PHILIPS_HEADER = {b"V3RD": 250, b"V5RD": 810}

#: The first twelve counts of ``tests/data/qarr/corundum.rd``, as its committed
#: ``.prn`` conversion states them.  Real instrument output, so every one is
#: exactly representable in the format's √ encoding and a synthesized file can
#: round-trip without the writer having to choose values for the caller.
CORUNDUM_HEAD = (182, 176, 176, 174, 158, 139, 151, 174, 196, 187, 161, 169)


def write_philips_rd(path: Path, counts, *, start=5.0, step=0.02,
                     version=b"V3RD", sample="Synthesized", anode=0,
                     end=None, stated_max=None, trailing=b"") -> Path:
    """A Philips ``.rd``/``.sd`` holding ``counts`` — real counts, not packed.

    The √ compression is applied **here**, so a caller writes the counts it
    expects to read back and the round trip exercises the decode instead of
    agreeing with it by construction.

    **A count the format cannot hold is refused, not quietly moved.**  The
    encoding is lossy above ~100 counts: ``v = isqrt(100·c)`` inverts
    ``v²//100`` only for the smallest ``c`` of each ``v``, and by 400 counts one
    step of ``v`` already spans four of them.  Silently writing the nearest
    representable count would make a round-trip test pass while asserting
    something the caller did not write, so this raises instead and the caller
    uses counts a real instrument produced (:data:`CORUNDUM_HEAD` below).

    This writer exists mainly for **V5**, which has no real file anywhere.  A V3
    fixture *is* committed (``tests/data/qarr/corundum.rd``, whose intensities
    are checked against a ``.prn`` conversion of the same scan in the same
    tree), so what this package knows about V3 comes from that file and not from
    here.  The other use is violating the reader's three gates on purpose:
    ``end`` and ``stated_max`` write a range or a maximum that disagrees with
    the data, and ``trailing`` appends bytes past the last point.
    """
    values = []
    for c in counts:
        # the reader truncates, so the v that decodes back to c is the *smallest*
        # whose square over 100 reaches it — ceil(√(100c)), not isqrt(100c)
        v = 0 if int(c) <= 0 else math.isqrt(100 * int(c) - 1) + 1
        if v * v // 100 != int(c):
            raise ValueError(
                f"{c} counts is not representable in the .rd √ encoding — the "
                f"nearest below it is {v * v // 100} and the next is "
                f"{(v + 1) ** 2 // 100}. Writing one of those would make a "
                "round trip assert a number the caller never wrote; use counts "
                "a real instrument produced, e.g. CORUNDUM_HEAD")
        values.append(v)
    last = start + step * (len(values) - 1)
    header = bytearray(b"\x00" * _PHILIPS_HEADER[version])
    header[0:4] = version
    header[4:44] = _fixed("Philips Analytical X-Ray B.V.", 40)
    header[44:84] = _fixed("PC-APD, Diffraction software", 40)
    header[84] = 3                                  # diffractometer: PW3710
    header[85] = anode                              # 0 = Cu
    header[86] = 3                                  # focus: LFF
    header[94:118] = struct.pack("<3d", 1.540562, 1.54439, 0.5)
    header[130:132] = struct.pack("<H", round(start * 200))
    header[132:134] = struct.pack("<H", round(last * 200))
    header[136:138] = struct.pack(
        "<H", max(values) if stated_max is None else stated_max)
    header[138:146] = _fixed(sample[:7], 8)
    header[146:166] = _fixed(sample[:19], 20)
    header[214:238] = struct.pack("<3d", step, start,
                                  last if end is None else end)

    out = bytearray(header)
    for v in values:
        out += struct.pack("<H", v)
    out += trailing
    path.write_bytes(bytes(out))
    return path
