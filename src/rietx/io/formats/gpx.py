"""GSAS-II ``.gpx`` projects read as **patterns**: each powder histogram a scan.

A ``.gpx`` is a whole refinement, and :mod:`rietx.io.projects.gsas2` reads it as
one — phases, instrument coefficients, refine flags.  This entry reads the other
half of it: the observed data each ``PWDR`` histogram stores, so a ``.rex``
project can point at a ``.gpx`` pattern (its ``DataRef`` records which entry of
:data:`~rietx.io.formats.PATTERN_FORMATS` claimed the file, and with which
``scan``).  Decided on issue #875 (2026-10-13), WP-1943 task 1: a registry entry
rather than a method on the project reader, because only a registry entry can be
the reader a project records.

**The histograms are scans, selected by ``scan=``, never concatenated.**  A
project commonly holds several — the PbSO₄ round robin's neutron and X-ray
patterns sit in one file — and they are separate measurements on separate
instruments, so the root ``CLAUDE.md`` rule for a multi-range file applies
unchanged.  ``scan`` counts the ``PWDR`` items from 0 in file order, which is
GSAS-II's own tree order.

**σ is the file's: σ = 1/√w** from the stored least-squares weight, which the
data-tree specification defines as w = 1/σ² (``objvarorg.rst`` § Powder
Diffraction Tree Items).  The scale is **measured, not adopted**
(``io/CLAUDE.md`` § Adding a format): on ``tests/data/gsas2_pbso4.gpx`` the
weighted residual over GSAS-II's own calculated pattern, inside each
histogram's limits, reproduces the project's stored Rwp, 6.1707 % over 8 739
channels, to the digits GSAS-II wrote (``tests/test_projects_gsas2.py``).  On
that file w·y is a whole number on every neutron point (1 to 10, the number of
D1A counters averaged into the point) and exactly 1 on every X-ray point, so σ
is √(y/N) and √y — the file's statement, which the Poisson fallback would get
wrong by √N on the neutron pattern.

A **zero weight** is GSAS-II's mark of a point that contributes nothing (a
channel that counted zero); it is excluded, exactly as pdCIF's zero
``_pd_proc_ls_weight`` is (``PATTERN_ZERO_WEIGHT_EXCLUDED``), and the point
keeps the Poisson σ only so the pattern stays valid.  A negative weight states
no σ at all, so the whole column is set aside for the Poisson fallback and
``PATTERN_WEIGHT_UNUSABLE`` says so — pdCIF's rule again.  A non-finite weight
drops its own row, as every reader's non-finite value does (WP-2079).

**The project's protocol is not the pattern.**  The limits, the excluded
regions and any ``numpy.ma`` mask GSAS-II stored with the arrays are its
refinement settings, not the measurement, and are left on
:class:`~rietx.io.projects.gsas2.Gsas2Histogram` for a caller who is adopting
GSAS-II's protocol to read (root ``CLAUDE.md``: comparing against another code
means adopting its protocol, deliberately).

**Constant-wavelength histograms only.**  A time-of-flight histogram (``PNT``)
or any other type is refused by name: the data tree stores a flight-time
abscissa, but this entry has measured no file's TOF unit against its own
output, and adopting it from prose is the one thing the format rule forbids.

**Dispatch position.**  The file is a sequence of pickles, so it goes with the
binary-claiming entries, because the stream is binary (a protocol-1 or -2
pickle, the two ``looks_gpx`` accepts; a protocol-0 one, which is ASCII, is not
claimed).  The sniff is the project reader's own,
:func:`~rietx.io.projects.gsas2.looks_gpx` (a pickle opcode *and* a GSAS-II tree
label), which no other entry's evidence overlaps.  Reading goes through the same
allow-listed unpickler (:data:`~rietx.io.projects.gsas2.ALLOWED_GLOBALS`), so a
``.gpx`` opened as a pattern crosses the same trust boundary as one opened as a
project.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from ...schemas.common import Diagnostic
from ...schemas.pattern import PatternData
from ..projects import gsas2
from .base import (
    PatternFormat,
    ScanInfo,
    ascending,
    head,
    multiscan_default,
    pattern_data,
)
from .pdcif import _runs


def _items(p: Path) -> list[tuple[str, Any, dict[str, Any]]]:
    try:
        items = gsas2.powder_items(p)
    except gsas2.Gsas2GpxError as exc:
        raise ValueError(str(exc)) from None
    if not items:
        raise ValueError(f"{p.name}: is a GSAS-II project holding no powder "
                         f"(PWDR) histogram, so there is no pattern to read")
    return items


def _kind(children: dict[str, Any]) -> str:
    instrument = children.get("Instrument Parameters", [{}])
    values = instrument[0] if isinstance(instrument, (list, tuple)) and instrument else {}
    if isinstance(values, dict) and isinstance(values.get("Type"), (list, tuple)):
        return str(values["Type"][0]).strip()
    return ""


def _instrument_value(children: dict[str, Any], name: str) -> float | None:
    instrument = children.get("Instrument Parameters", [{}])
    values = instrument[0] if isinstance(instrument, (list, tuple)) and instrument else {}
    entry = values.get(name) if isinstance(values, dict) else None
    try:
        return float(entry[1] if len(entry) > 1 else entry[0])  # type: ignore[index]
    except (TypeError, ValueError, IndexError):
        return None


def _sigma(p: Path, label: str, w: np.ndarray,
           diagnostics: list[Diagnostic] | None) -> np.ndarray | None:
    """σ = 1/√w, +∞ marking a zero weight; ``None`` for an unusable column.

    The decision reads the **finite** weights only, and a non-finite one
    becomes a NaN σ, so :func:`~.base.ascending` drops that row and names it
    rather than this function setting the whole column aside (WP-2079's rule:
    a reader's decisions skip non-finite values and drop none of their rows).
    """
    w = w + 0.0                    # −0.0 is a zero weight, not a √ of a negative
    finite = np.isfinite(w)
    if not np.any(w[finite] < 0) and np.any(w[finite] > 0):
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(finite, 1.0 / np.sqrt(np.where(finite, w, 1.0)), np.nan)
    if diagnostics is not None:
        n_neg = int((w[finite] < 0).sum())
        found = f"{n_neg} negative weight(s)" if n_neg else "no positive weight"
        diagnostics.append(Diagnostic(
            level="info", code="PATTERN_WEIGHT_UNUSABLE",
            message=(f"{p.name}: histogram {label!r} stores {found} in "
                     f"{w.size} points, so its weights are not read. The "
                     f"Poisson σ = √max(y, 1) is used instead."),
            value=float(n_neg), where=["w"]))
    return None


def read_gpx_pattern(path: str | Path, *, scan: int | None = None,
                     diagnostics: list[Diagnostic] | None = None) -> PatternData:
    """One powder histogram of a GSAS-II ``.gpx``, as a pattern.

    ``scan`` counts the project's ``PWDR`` histograms from 0 in file order
    (:func:`list_gpx_scans` names them).  σ is 1/√w from the histogram's own
    weights; see the module docstring for how that scale was measured.
    """
    p = Path(path)
    items = _items(p)
    multiscan_default(len(items), scan, path=p, diagnostics=diagnostics)
    index = 0 if scan is None else scan
    if not 0 <= index < len(items):
        raise ValueError(f"{p.name} holds {len(items)} powder histogram(s), "
                         f"numbered 0 to {len(items) - 1}; scan={index} is not "
                         f"one of them")
    label, payload, children = items[index]
    kind = _kind(children)
    if kind not in gsas2.CW_TYPES:
        stated = gsas2.HISTOGRAM_TYPES.get(kind, "a type this reader cannot name")
        raise ValueError(
            f"{p.name}: histogram {label!r} states the type {kind!r} "
            f"({stated}). This reader reads constant-wavelength histograms "
            f"({', '.join(gsas2.CW_TYPES)}) only; the abscissa unit of any other "
            f"type has not been measured against GSAS-II's own output")
    arrays = gsas2.histogram_arrays(payload)
    if arrays is None:
        raise ValueError(f"{p.name}: histogram {label!r} does not store three "
                         f"equal-length arrays of 2θ, intensity and weight")

    sigma = _sigma(p, label, arrays.w, diagnostics)
    tt, y, sig = ascending(arrays.x, arrays.y, sigma, path=p, fmt=GPX,
                           keep_infinite_sigma=True, diagnostics=diagnostics)
    excluded: list[tuple[float, float]] = []
    if sig is not None and np.isinf(sig).all():
        raise ValueError(f"{p.name}: histogram {label!r} has no point of non-zero "
                         f"weight left once its non-finite rows are dropped, so "
                         f"no point of it would be fitted")
    if sig is not None and np.isinf(sig).any():
        unused = np.isinf(sig)
        sig = np.where(unused, np.sqrt(np.maximum(y, 1.0)), sig)
        excluded = _runs(tt, unused)
        if diagnostics is not None:
            diagnostics.append(Diagnostic(
                level="info", code="PATTERN_ZERO_WEIGHT_EXCLUDED",
                message=(f"{p.name}: {int(unused.sum())} of {tt.size} points of "
                         f"histogram {label!r} carry a zero weight, which "
                         f"contributes nothing to GSAS-II's sums. They became "
                         f"{len(excluded)} excluded region(s); every other "
                         f"point keeps σ = 1/√w."),
                value=float(unused.sum()), where=["w"]))

    data0 = payload[0] if isinstance(payload, (list, tuple)) and payload else {}
    title = data0.get("histTitle") if isinstance(data0, dict) else None
    sample = children.get("Sample Parameters", {})
    radius = sample.get("Gonio. radius") if isinstance(sample, dict) else None
    primary = _instrument_value(children, "Lam")
    alpha2 = None
    if primary is None:
        primary = _instrument_value(children, "Lam1")
        alpha2 = _instrument_value(children, "Lam2")
    data = pattern_data(
        p, tt, y, sig,
        source_file=p.name, format=GPX.name, scan=index, scan_count=len(items),
        title=(str(title).strip() or None) if title is not None else label,
        wavelength=primary, wavelength_alpha2=alpha2,
        goniometer_radius_mm=(float(radius) if isinstance(radius, (int, float))
                              else None))
    if excluded:
        data.excluded_regions = excluded
    return data


def list_gpx_scans(path: str | Path) -> list[ScanInfo]:
    """The project's powder histograms, labelled by their own tree names."""
    p = Path(path)
    out = []
    for i, (label, payload, children) in enumerate(_items(p)):
        arrays = gsas2.histogram_arrays(payload)
        kind = _kind(children)
        named = gsas2.HISTOGRAM_TYPES.get(kind, kind or "untyped")
        n = 0 if arrays is None else int(arrays.x.size)
        # a non-CW histogram's abscissa is not 2θ, and it cannot be read here
        span = ((float(np.nanmin(arrays.x)), float(np.nanmax(arrays.x)))
                if arrays is not None and kind in gsas2.CW_TYPES else (0.0, 0.0))
        out.append(ScanInfo(index=i, label=f"{label} ({named})", n_points=n,
                            two_theta_range=span))
    return out


def looks_gpx_file(p: Path) -> bool:
    """The project reader's own two-clause sniff, on the bounded head."""
    return gsas2.looks_gpx(head(p).raw)


GPX = PatternFormat(
    name="gsas2_gpx",
    title="GSAS-II project histogram (.gpx)",
    extensions=(".gpx",),
    sniff=("a pickle stream (protocol-2 header or a list opcode) whose head "
           "names a GSAS-II tree item — the project reader's own test"),
    sigma=("σ = 1/√w from the histogram's stored least-squares weight "
           "(w = 1/σ²), its scale checked against the project's stored Rwp; a "
           "zero weight is excluded, an unusable column falls back to Poisson "
           "with PATTERN_WEIGHT_UNUSABLE"),
    matches=looks_gpx_file,
    read=read_gpx_pattern,
    options=("scan",),
    scans=list_gpx_scans,
)
