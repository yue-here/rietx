"""Bruker/Siemens ``.uxd`` — the DIFFRAC-AT ASCII export.

Spec: the format is line-oriented ASCII and its structure was read off five real
files (see ``tests/data/README.md`` for which, and why none could be vendored).
Keys and markers are interface facts, so they are written down here and the
parser is this package's own::

    ; a comment, anywhere
    _FILEVERSION=2                    required first non-comment line
    _ANODE='Cu'                       … file-level header
    _WL1=1.540600
    _GONIOMETER_RADIUS=250.000000
    ; (Data for Range number 1)
    _DRIVE='COUPLED'                  … per-range header, overriding the above
    _STEPTIME=1.000000                seconds per step, directly
    _STEPSIZE=0.020000
    _START=5.000000
    _2THETACOUNTS                     the block marker — see below
       5.0000      1234
       5.0200      1250

**The block marker declares two orthogonal things**, and its name is read as
those two rather than looked up in a table of four:

* the ``_2THETA`` prefix means **the first column is present**; without it the
  positions are reconstructed from ``_START`` and ``_STEPSIZE``;
* the ``COUNTS``/``CPS`` suffix is the **intensity unit**.

So ``σ`` needs no arithmetic detective work here, unlike ``.ras`` one module
over: that format declares its unit in a free-text header field which real files
get *wrong*, whereas this one declares it structurally, in the token that opens
the block, where it cannot disagree with itself.  Measured on the real files:
every ``COUNTS`` block is integral to the last of 3774 points.

**The prefix is nonetheless a misnomer, and trusting it is the trap.**  The
first column is the position of whatever ``_DRIVE`` names — and a rocking curve
(``_DRIVE='THETA'``) and a pole figure (``_DRIVE='PHI'``) are both stored under
a marker called ``_2THETACOUNTS``.  Of the five real files read, **four** are
not 2θ scans at all.  So ``_DRIVE`` is the authority, classified against the
vocabulary below and decided by :func:`base.check_axis`.

**Ranges are scans, and this format is why the rule is not academic.**  One
153-range file carries ``_STEPTIME`` of both 2 s and 20 s; concatenating its
ranges would put measurements a factor of ten apart in counting statistics into
one weighting regime under one Poisson assumption.  ``scan=`` selects; nothing
joins.
"""

from __future__ import annotations

import re
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
    sigma_from_cps,
)

#: The key the format requires first, ignoring comments — the sniff.
_MAGIC = "_FILEVERSION"

_KEY_LINE = re.compile(r"^_(\w+)\s*=\s*(.*)$")

#: A block marker: an optional ``2THETA`` prefix and a unit suffix, nothing else.
#: Written as one pattern rather than a set of four names because the two halves
#: are independent facts and a table would imply they are not.
_MARKER = re.compile(r"^_(?P<x>2THETA)?(?P<unit>COUNTS|CPS)$")

#: ``_DRIVE`` values whose stepped axis is the diffraction angle 2θ.
#: ``2THETA`` is a detector scan (verified on a real file); ``COUPLED`` is the
#: format's name for the θ–2θ scan a powder pattern is measured with, accepted
#: on the format's vocabulary rather than on a fixture — no obtainable ``.uxd``
#: is a powder scan, which is itself the finding.
_TWO_THETA_DRIVES = frozenset({"coupled", "2theta", "twotheta", "theta2theta"})

#: ``_DRIVE`` values that are recognisably **not** 2θ, with what each measures.
#: Every one of these was found in a real file except ``omega`` and ``psi``.
_OTHER_DRIVES: dict[str, str] = {
    "theta": "a rocking curve about θ with the detector fixed",
    "omega": "a rocking curve about ω with the detector fixed",
    "phi": "a φ rotation — one ring of a pole figure",
    "khi": "a χ tilt — one arc of a pole figure",
    "chi": "a χ tilt — one arc of a pole figure",
    "psi": "a ψ tilt, as measured for residual stress",
    "x": "a specimen translation in x, used to position the sample",
    "y": "a specimen translation in y, used to position the sample",
    "z": "a specimen height scan, used to set the sample surface",
}


def _ranges(path: Path) -> list[tuple[str, dict[str, str], np.ndarray]]:
    """Every ``(marker, header, rows)`` in file order, header inherited downwards.

    A range's own keys override the file-level ones and *persist* into the next
    range, which is what the real files rely on: only the keys that change are
    rewritten between ranges.
    """
    p = Path(path)
    text = p.read_text(encoding=head(p).encoding, errors="replace")

    out: list[tuple[str, dict[str, str], np.ndarray]] = []
    header: dict[str, str] = {}
    marker: str | None = None
    #: the header **as it stood when the marker opened this block**.  Snapshotted
    #: there rather than at close, because keys persist across ranges: by the
    #: time a block ends, the *next* range's ``_STEPTIME`` has already replaced
    #: it, and the σ of a 2 s range would be derived from a 20 s one.
    opened: dict[str, str] = {}
    rows: list[list[float]] = []

    def close() -> None:
        if marker is not None:
            # narrowest row wins: a file truncated mid-row is otherwise a ragged
            # list, and numpy's "inhomogeneous shape" complaint names no file
            width = min((len(r) for r in rows), default=1)
            out.append((marker, opened,
                        np.array([r[:width] for r in rows], dtype=np.float64)
                        if rows else np.empty((0, 1))))

    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        if (found := _MARKER.match(line)) is not None:
            close()
            marker, opened, rows = found.group(0), dict(header), []
            continue
        if (key := _KEY_LINE.match(line)) is not None:
            header[key.group(1).upper()] = key.group(2).strip().strip("'\"")
            continue
        if line.startswith("_"):
            raise ValueError(
                f"{p.name}: line {number} is {line.split('=')[0]!r}, which opens "
                "no block of counts this reader knows and carries no value "
                "either. Known block markers are _COUNTS, _CPS, _2THETACOUNTS "
                "and _2THETACPS")
        if marker is None:
            raise ValueError(f"{p.name}: line {number} is a row of data before "
                             "any block marker opened one: {line!r}".format(
                                 line=line))
        try:
            rows.append([float(v) for v in line.split()])
        except ValueError:
            raise ValueError(f"{p.name}: line {number} is inside a block of "
                             f"counts but is not numeric: {line!r}") from None
    close()

    if not out:
        raise ValueError(f"{p.name}: {_MAGIC} is present but the file holds no "
                         "block of counts (_COUNTS, _CPS, _2THETACOUNTS or "
                         "_2THETACPS)")
    return out


def _float(header: dict[str, str], key: str) -> float | None:
    try:
        return float(header[key])
    except (KeyError, ValueError):
        return None


def _positions(marker: str, header: dict[str, str], rows: np.ndarray, *,
               path: Path) -> tuple[np.ndarray, np.ndarray]:
    """The stepped positions and the intensities, whichever form the block took."""
    if rows.size == 0:
        raise ValueError(f"{path.name}: a {marker} block holds no counts")
    has_x = _MARKER.match(marker).group("x") is not None
    if has_x:
        if rows.shape[1] < 2:
            raise ValueError(f"{path.name}: {marker} declares a position column "
                             "and an intensity, but its rows have one number")
        return rows[:, 0], rows[:, 1]

    # no position column: the format says start + i·step, and without both there
    # is no x axis at all — which is a refusal, never an assumed step of 1
    start, step = _float(header, "START"), _float(header, "STEPSIZE")
    y = rows.reshape(-1)
    if start is None or step is None or step <= 0:
        raise ValueError(
            f"{path.name}: {marker} carries counts with no position column, so "
            "the positions come from _START and _STEPSIZE — and this range gives "
            f"_START={header.get('START', '(absent)')}, "
            f"_STEPSIZE={header.get('STEPSIZE', '(absent)')}. Without both there "
            "is no 2θ axis to read")
    return start + step * np.arange(y.size, dtype=np.float64), y


def _sigma(marker: str, y: np.ndarray, header: dict[str, str], *, path: Path,
           diagnostics: list[Diagnostic] | None,
           ) -> tuple[np.ndarray | None, float | None]:
    """σ from the marker's declared unit and ``_STEPTIME``.

    Trusted here, unlike ``.ras``, because the declaration is *structural*: the
    unit is the token that opens the block, not a free-text field beside it.
    """
    t = _float(header, "STEPTIME")
    if _MARKER.match(marker).group("unit") == "COUNTS":
        return None, t                      # the Poisson fallback is correct
    if t is not None and t > 0:
        return sigma_from_cps(y, t), t
    if diagnostics is not None:
        diagnostics.append(Diagnostic(
            level="warning", code="PATTERN_INTENSITY_SCALED",
            message=(f"{path.name} stores this range as {marker} (counts per "
                     "second) but gives no usable _STEPTIME to undo the "
                     f"division (_STEPTIME={header.get('STEPTIME', '(absent)')}). "
                     "No σ was supplied, so the Poisson fallback applies to "
                     "a rate."),
            where=["sigma"],
            suggestion=("Re-export the file in counts, or supply the esds.")))
    return None, t


def _axis(header: dict[str, str], *, path: Path,
          diagnostics: list[Diagnostic] | None) -> str | None:
    """``_DRIVE`` decides, because the block marker's ``2THETA`` prefix lies."""
    drive = header.get("DRIVE", "").strip()
    key = drive.lower().replace(" ", "").replace("-", "").replace("_", "")
    return check_axis(drive, path=path, field="_DRIVE",
                      two_theta=key in _TWO_THETA_DRIVES,
                      other=_OTHER_DRIVES.get(key),
                      remedy="Export the coupled θ–2θ range instead.",
                      note=(" The block marker does not settle it. A rocking "
                            "curve is also stored under _2THETACOUNTS."),
                      diagnostics=diagnostics)


def read_uxd(path: str | Path, *, scan: int | None = None,
             diagnostics: list[Diagnostic] | None = None) -> PatternData:
    p = Path(path)
    ranges = _ranges(p)
    multiscan_default(len(ranges), scan, path=p, diagnostics=diagnostics)

    index = 0 if scan is None else scan
    if not 0 <= index < len(ranges):
        raise ValueError(f"{p.name} holds {len(ranges)} range(s), numbered 0 to "
                         f"{len(ranges) - 1}; scan={index} is not one of them")
    marker, header, rows = ranges[index]

    axis = _axis(header, path=p, diagnostics=diagnostics)
    x, y = _positions(marker, header, rows, path=p)
    sigma, count_time = _sigma(marker, y, header, path=p, diagnostics=diagnostics)
    tt, y, sig = ascending(x, y, sigma, path=p, fmt=UXD, diagnostics=diagnostics)
    return pattern_data(
        p, tt, y, sig,
        source_file=p.name, format="uxd", scan=index, scan_count=len(ranges),
        scan_axis=axis, anode=header.get("ANODE") or None,
        wavelength=_float(header, "WL1"),
        wavelength_alpha2=_float(header, "WL2"),
        intensity_unit=_MARKER.match(marker).group("unit").lower(),
        count_time_s=count_time,
        goniometer_radius_mm=_float(header, "GONIOMETER_RADIUS"))


def list_uxd_scans(path: str | Path) -> list[ScanInfo]:
    out: list[ScanInfo] = []
    for i, (marker, header, rows) in enumerate(_ranges(Path(path))):
        try:
            x, _ = _positions(marker, header, rows, path=Path(path))
        except ValueError:
            x = np.array([0.0])
        drive = header.get("DRIVE", "?")
        fixed = _float(header, "2THETA")
        # the fixed detector angle is what identifies which reflection a pole
        # figure ring belongs to, so it goes in the label where the file has one
        at = (f" at 2θ {fixed:.4g}°"
              if fixed is not None and drive.lower() != "2theta" else "")
        out.append(ScanInfo(
            index=i, label=f"{drive} {np.nanmin(x):.4g}–{np.nanmax(x):.4g}°{at}",
            n_points=int(x.size),
            two_theta_range=(float(np.nanmin(x)), float(np.nanmax(x)))))
    return out


def looks_uxd(p: Path) -> bool:
    """The required first key, past any leading comment block, within the head."""
    for line in head(p).text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(";"):
            continue
        return stripped.startswith(_MAGIC)
    return False


UXD = PatternFormat(
    name="uxd",
    title="Bruker/Siemens DIFFRAC-AT export (.uxd)",
    extensions=(".uxd",),
    sniff=f"the first line that is neither blank nor a ; comment begins {_MAGIC}",
    sigma=("the Poisson fallback for a _COUNTS block; √(y·t)/t from _STEPTIME "
           "for a _CPS one — the unit is the block marker itself, so it is "
           "structural rather than a header field that could disagree"),
    matches=looks_uxd,
    read=read_uxd,
    options=("scan",),
    scans=list_uxd_scans,
)
