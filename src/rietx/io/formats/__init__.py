"""The pattern-format registry — one module per format, ordered for dispatch.

:data:`PATTERN_FORMATS` is the single ordered list every consumer reads: the
dispatch in :func:`rietx.io.readers.identify_format`, ``capabilities()``
(WP-1007, which must say what this build can actually open), and a project's
``DataRef`` (WP-1005, which records *which reader claimed the file*).

**The order is behaviour, not presentation** — the first format whose ``matches``
returns True reads the file — and it runs strongest evidence first:

1. **magic bytes** and container manifests, which no other format can imitate;
2. a **required first line** or XML root element, which the format's own spec
   mandates;
3. **suffix**, where the format has no in-band marker (pdCIF);
4. a **loose text sniff** (GSAS's ``BANK`` record anywhere in the first 4 kB);
5. the two/three-column ASCII catch-all, last **of the readers**;
6. one entry below even that: ``RAW_UNKNOWN``, which claims a binary ``.raw``
   only once every reader has already declined it.  It is a refusal rather than
   a reader, and its position is what makes it safe — reached last, it cannot
   shadow anything, so no ordering mistake can route a real Bruker or Philips
   file into a message that names six vendors and picks none.

Binary-claiming formats go first so nothing tries to decode their bytes as text.
"""

from __future__ import annotations

from .base import (
    HEAD_BYTES,
    METADATA_KEYS,
    READER_OPTIONS,
    Head,
    PatternFormat,
    ReaderOption,
    ScanInfo,
    ascending,
    check_axis,
    decode,
    head,
    looks_binary,
    metadata,
    multiscan_default,
    pattern_data,
    reader_options_for,
    sigma_by_arithmetic,
    sigma_from_cps,
    sigma_from_scaled,
)
from .brml import BRML, read_brml
from .bruker_raw import BRUKER_RAW, read_bruker_raw
from .chi import CHI, read_chi
from .dif import DIF, read_dif
from .gsas import GSAS, GSASBank, gsas_banks, read_gsas
from .pdcif import PDCIF, read_pdcif
from .peaklist import PEAK_LIST, read_peaklist
from .philips_rd import PHILIPS_RD, read_philips_rd
from .ras import RAS, read_ras
from .rasx import RASX, read_rasx
from .raw_unknown import RAW_UNKNOWN, read_unknown_raw
from .total_scattering import (
    TOTAL_SCATTERING,
    TotalScatteringRefused,
    read_total_scattering,
)
from .udf import UDF, read_udf
from .uxd import UXD, read_uxd
from .xrdml import XRDML, read_xrdml
from .xy import XY, read_xy

#: Every format ``read_pattern`` accepts, **in dispatch order** (see above).
#: ``BRUKER_RAW`` is first: its magic bytes name the format *and* its version at
#: offset 0, which no other entry can imitate and which no other entry needs to
#: be told apart from.  ``PHILIPS_RD`` is second on the same grounds, and the
#: pair is disjoint by construction — ``RAW…`` against ``V3RD``/``V5RD`` — which
#: matters more here than usual, since ``.raw`` is written by six unrelated
#: vendors and ``.rd`` by two, so neither reader may trust a suffix.
#: ``RASX`` and ``BRML`` follow, sharing a zip's magic and
#: separated by their manifests rather than by it; then ``RAS``, ``UXD``,
#: ``XRDML`` and ``UDF``, each recognised by a first line, a root element or a
#: required pair of header keys its own spec mandates, which is stronger
#: evidence than the suffix and loose-text sniffs below them.  ``UDF`` sits with
#: that group and not lower: its two required keys are what the *parser* needs
#: to build an abscissa at all, so a file matching them is a ``.udf`` or is
#: nothing, and putting it below ``PDCIF``/``GSAS`` would only let a weaker
#: sniff answer first.  ``PEAK_LIST`` sits beside ``DIF``, the refusal it
#: copies; ``TOTAL_SCATTERING`` (issue #1240) beside both and directly above
#: ``XY``, the one entry its files fell to, so it can shadow no reader;
#: ``RAW_UNKNOWN`` sits below ``XY``, for the reason in the module docstring.
PATTERN_FORMATS: tuple[PatternFormat, ...] = (BRUKER_RAW, PHILIPS_RD, RASX, BRML,
                                              RAS, UXD, XRDML, UDF, PDCIF, GSAS,
                                              CHI, DIF, PEAK_LIST,
                                              TOTAL_SCATTERING, XY,
                                              RAW_UNKNOWN)

__all__ = [
    "HEAD_BYTES",
    "METADATA_KEYS",
    "PATTERN_FORMATS",
    "READER_OPTIONS",
    "GSASBank",
    "Head",
    "PatternFormat",
    "ReaderOption",
    "ScanInfo",
    "TotalScatteringRefused",
    "ascending",
    "check_axis",
    "decode",
    "gsas_banks",
    "head",
    "looks_binary",
    "metadata",
    "multiscan_default",
    "pattern_data",
    "read_brml",
    "read_bruker_raw",
    "read_chi",
    "read_dif",
    "read_gsas",
    "read_pdcif",
    "read_peaklist",
    "read_philips_rd",
    "read_ras",
    "read_rasx",
    "read_total_scattering",
    "read_udf",
    "read_unknown_raw",
    "read_uxd",
    "read_xrdml",
    "read_xy",
    "reader_options_for",
    "sigma_by_arithmetic",
    "sigma_from_cps",
    "sigma_from_scaled",
]
