"""Write the three planted known-bad patterns of the D1B Co₃O₄ quench series.

Each is derived from one real file in this directory by a fixed byte-level
transformation, and none replaces a real file.  They exist so that a series'
quarantine and ``on_error`` have a case whose right answer is plain to a human
(issue #1150, WP-2003); what rietx does with them is for the tiering session to
measure, and this script asserts nothing about it.  ``tests/data/README.md``
§ "WP-2003 family D" describes each one.

Every planted file states what it is on its first line, where the ``XYDATA``
title was: the FullProf heading's title is free text, and the reader takes only
``TEMP`` and ``INTER`` from the heading.  Data rows are 39 bytes (2θ in
``[0:9]``, counts in ``[9:27]``, σ in ``[27:39]``) and CRLF-terminated; the
transformations keep both, so a planted file has the shape of the real ones.

Run from anywhere: ``python tests/data/d1b_co3o4_quench/make_planted.py``
rewrites the three files; ``test_d1b_co3o4_quench.py`` checks that what this
module builds is byte-identical to what is committed.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent

#: The seed of the only random step (the shuffle).  Fixed, so the files are
#: reproducible on every platform: ``Generator.permutation`` on PCG64 is
#: specified bit-for-bit by NumPy for a given seed.
SEED = 2003

#: Lines of the ``XYDATA`` heading, the keyword line included.
HEADING = 6

#: The 60 data rows written as NaN in the NaN-block file: 2θ 30.79–36.69°,
#: which holds the (111) reflection (about 31.4° at λ = 2.52 Å).
NAN_ROWS = slice(300, 360)


def _split(name: str) -> tuple[list[bytes], list[bytes], bytes]:
    """Heading lines, data rows and whatever follows the last CRLF."""
    lines = (HERE / name).read_bytes().split(b"\r\n")
    head, body = lines[:HEADING], lines[HEADING:]
    tail = body.pop()          # bytes after the final CRLF (may be empty)
    if any(len(row) != 39 for row in body):
        raise ValueError(f"{name}: a data row is not 39 bytes")
    return head, body, tail


def _join(head: list[bytes], body: list[bytes], tail: bytes) -> bytes:
    return b"\r\n".join([*head, *body, tail])


def _title(text: str) -> bytes:
    return b"XYDATA " + text.encode("ascii")


def shuffled_counts() -> bytes:
    """873q-1p5K_1.dat with its (counts, σ) pairs permuted across channels.

    The 2θ column and the heading's numbers are untouched, so the file has the
    same points, total counts and noise as the real pattern; every Bragg peak
    is gone, which is what corrupted intensities look like.
    """
    head, body, tail = _split("873q-1p5K_1.dat")
    order = np.random.default_rng(SEED).permutation(len(body))
    body = [body[i][:9] + body[j][9:] for i, j in enumerate(order)]
    head[0] = _title("PLANTED shuffled counts from 873q-1p5K_1.dat, "
                     "not a measurement")
    return _join(head, body, tail)


def nan_block() -> bytes:
    """1023q_1p5K.dat with 60 channels' counts and σ written as NaN.

    The shape a normalisation by a zero monitor or efficiency leaves; the
    rows keep their 2θ and their field widths.
    """
    head, body, tail = _split("1023q_1p5K.dat")
    for i in range(*NAN_ROWS.indices(len(body))):
        body[i] = body[i][:9] + b"NaN".rjust(18) + b"NaN".rjust(12)
    head[0] = _title("PLANTED NaN block in 1023q_1p5K.dat, not a measurement")
    return _join(head, body, tail)


def wrong_sample() -> bytes:
    """The garnet standard's pattern, titled as a Co₃O₄ quench pattern.

    Every number is the real standard's (a garnet measured at 300 K in the
    same experiment); only the title changes, as when a file is put in the
    wrong slot of a series.
    """
    head, body, tail = _split("standard_garnet_300K_1.dat")
    head[0] = _title("PLANTED wrong sample: the garnet standard "
                     "standard_garnet_300K_1.dat titled as Co3O4-quenched_300K")
    return _join(head, body, tail)


#: File name → builder.  The ``PLANTED_`` prefix is what keeps a glob for real
#: patterns (``*q*1p5K*``) from collecting them.
PLANTED = {
    "PLANTED_shuffled_counts_from_873q-1p5K_1.dat": shuffled_counts,
    "PLANTED_nan_block_from_1023q_1p5K.dat": nan_block,
    "PLANTED_wrong_sample_garnet_titled_co3o4.dat": wrong_sample,
}


def build() -> dict[str, bytes]:
    return {name: make() for name, make in PLANTED.items()}


if __name__ == "__main__":
    for name, data in build().items():
        (HERE / name).write_bytes(data)
        print(name, len(data))
