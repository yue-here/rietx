"""Curves for a browser chart, as a JSON header and typed arrays (WP-1461, D4).

A chart that zooms in the browser needs every channel once. As JSON that costs
the server 52-57 ms of ``json.dumps`` and the browser 4-9 ms of parse on the
11-BM NAC pattern, and both fall to under 2 ms as raw float64 at 57 % of the
bytes (the WP's § The payload behind a client zoom). Float64 rather than
float32, because a Σχ² re-based at a zoom as ``cum[j] − cum[i−1]`` loses 1.2e-3
of itself in float32 over a narrow window.

The body is a little-endian uint32 header length, the JSON header padded with
spaces to an 8-byte boundary, then each array padded to 8 bytes. The header's
``arrays`` lists each one's ``name``, ``dtype``, ``offset`` (from the first
array) and ``length``, so a reader makes a typed-array view with no copy.
``rxplot.mjs``'s ``unpack`` is the browser's reader and :func:`unpack` is
Python's.
"""

from __future__ import annotations

import json
import struct
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

#: What a route serves a packed body as.
MEDIA_TYPE = "application/octet-stream"

#: About the most channels a packed payload carries (D4 and D5). The chart
#: paints each pixel column's lowest and highest point, and the pilot measured
#: that at 132 992 channels, the largest pattern the repository reads, with no
#: long frame. The spike's 200 000 had one, so a pattern past this is
#: decimated by ``viz.compare.decimation_index`` first, whose count is a
#: budget: a bucket's minimum and maximum can bring it a channel over. The GUI's
#: curves routes, ``rietx compare`` and the file ``write_html`` writes all send
#: under it.
CURVES_CEILING = 150_000

#: The two dtypes a browser reads as a typed array with no conversion.
_FLOAT, _INT = "<f8", "<i4"


class OffPattern(ValueError):
    """A result whose channels are not the pattern's, so its curves cannot go over it."""


@dataclass(frozen=True)
class Packed:
    """A header and named arrays, packed only when a transport asks.

    A session verb returns one, so the verb knows nothing of the wire. The GUI
    server calls :meth:`to_bytes` where it would call ``json.dumps``.
    """

    header: dict[str, Any]
    arrays: dict[str, np.ndarray]

    def to_bytes(self, dumps: Callable[[Any], str] = json.dumps) -> bytes:
        return pack(self.header, self.arrays, dumps)


def _typed(name: str, values) -> np.ndarray:
    a = np.asarray(values)
    if a.dtype.kind == "f":
        return a.astype(_FLOAT, copy=False)
    if a.dtype.kind in "iub":
        if a.size and (a.min() < -2**31 or a.max() >= 2**31):
            raise ValueError(f"{name}: an index past int32 has no typed array to read it")
        return a.astype(_INT, copy=False)
    raise ValueError(f"{name}: dtype {a.dtype} is neither a float nor an integer")


def pack(header: dict[str, Any], arrays: dict[str, Any],
         dumps: Callable[[Any], str] = json.dumps) -> bytes:
    """The body for ``header`` and ``arrays``. Floats go as float64, integers as int32."""
    if "arrays" in header:
        raise ValueError("'arrays' is the packed format's own header key")
    specs, blobs, offset = [], [], 0
    for name, values in arrays.items():
        a = _typed(name, values)
        raw = np.ascontiguousarray(a).tobytes()
        specs.append({"name": name, "dtype": a.dtype.str, "offset": offset,
                      "length": int(a.size)})
        pad = -len(raw) % 8
        blobs.append(raw + b"\0" * pad)
        offset += len(raw) + pad
    head = dumps({**header, "arrays": specs}).encode("utf-8")
    head += b" " * (-(4 + len(head)) % 8)
    return struct.pack("<I", len(head)) + head + b"".join(blobs)


def unpack(body: bytes) -> Packed:
    """The header and arrays of a packed body, the arrays copied out of it."""
    (n,) = struct.unpack_from("<I", body, 0)
    header = json.loads(body[4:4 + n])
    base, arrays = 4 + n, {}
    for spec in header.pop("arrays"):
        start = base + spec["offset"]
        arrays[spec["name"]] = np.frombuffer(
            body, dtype=spec["dtype"], count=spec["length"], offset=start).copy()
    return Packed(header, arrays)


# ---------------------------------------------------------------- a fit's curves
def curve_arrays(tt_all, y_all, keep, res, *, weighted: bool | None,
                 header: dict | None = None,
                 ceiling: int | None = None) -> Packed:
    """A pattern's every channel, and a fit's curves on the channels it kept.

    WP-1461, D4. Taking the result explicitly, because its three callers'
    results are different: ``GuiSession.result_curves`` draws the project's,
    ``GuiSession.series_curves`` one member of a series, and
    :func:`rietx.viz.html.page` a result alone, over its own channels. One
    function means no two pictures draw residuals under two policies: the σ is
    ``RefinementResult.sig()``, never a re-derivation.

    ``weighted`` is the caller's fact, not this function's: it is whether the σ
    was **measured** (``DataRef.has_sigma``) rather than whether ``delta`` is
    divided by something, which it always is. ``GuiSession.result_curves``'s
    docstring says what happens when that distinction is lost. ``None`` is a
    caller that cannot know, as a result alone cannot.

    The arrays:

    - ``two_theta`` and ``y_obs``: the pattern over every channel, ascending in
      2θ, as ``PatternData`` refuses any other order and uPlot draws no other.
    - ``kept``: the channels the protocol fits now, as indices into those two.
      The client draws the rest as masked.
    - With a fit, ``fitted``: the channels the fit kept, the same way. Then
      ``y_calc``, ``y_background`` when there is one, ``delta``, ``delta_raw``
      and ``cumulative_chi2``, one value per fitted channel.

    ``fitted`` and ``kept`` differ only when ``stale``: an exclusion persists
    on the verb and the curves move only on a run. Two facts carry the index,
    both checked on the NAC example and a series member bit for bit: a result's
    2θ is the pattern's own under the mask it was fitted with, and so is its
    ``y_obs``. A result not on this pattern's channels is refused.

    Past ``ceiling`` channels, :data:`CURVES_CEILING` unless the caller names
    another, the pattern is decimated, and every index follows: ``n_channels`` is then the pattern's count and ``decimated``
    says so. **Three residuals, and one of them cannot be derived from the
    others** (WP-1029): the Σχ² is accumulated over every fitted channel before
    any decimation, so each value sent is still exact, where summing the
    channels that survive would understate it by whatever the dropped ones
    contributed.
    """
    grid = np.asarray(tt_all, dtype=float)
    head = {"weighted": weighted, "n_channels": len(grid), **(header or {})}
    arrays = {"two_theta": grid, "y_obs": np.asarray(y_all, dtype=float),
              "kept": np.flatnonzero(keep)}
    if res is None or not res.two_theta:
        return _under_ceiling(Packed({**head, "fit": False}, arrays), ceiling)

    tt_fit = np.asarray(res.two_theta, dtype=float)
    at = np.minimum(np.searchsorted(grid, tt_fit), len(grid) - 1)
    if not np.array_equal(grid[at], tt_fit):
        raise OffPattern("the fit's channels are not this pattern's, so its curves "
                         "cannot be drawn over it — run again")
    y_obs, y_calc = np.asarray(res.y_obs), np.asarray(res.y_calc)
    raw = y_obs - y_calc
    delta = raw / res.sig()
    arrays.update({"fitted": at, "y_calc": y_calc})
    if res.y_background:
        arrays["y_background"] = np.asarray(res.y_background)
    arrays.update({"delta": delta, "delta_raw": raw,
                   # accumulated over every fitted channel; a client re-bases it
                   # at a zoom as cum[j] − cum[i−1]
                   "cumulative_chi2": np.cumsum(delta**2)})
    head.update({
        "fit": True, "n_fitted": len(tt_fit),
        "stale": not np.array_equal(grid[keep], tt_fit),
        **_tick_rows(res),
    })
    return _under_ceiling(Packed(head, arrays), ceiling)


def _under_ceiling(packed: Packed, ceiling: int | None = None) -> Packed:
    """``packed`` decimated to ``ceiling`` channels, :data:`CURVES_CEILING` by default.

    The channels kept are ``decimation_index``'s over the observed and
    calculated curves and both differences, Δ/σ and the raw one, so a misfit
    spike survives as a peak top does in whichever residual is drawn. The raw
    difference joined in WP-1461's task 10: the file ``write_html`` writes
    draws it by default, and the extremes of Δ/σ are not its extremes, so on
    the synthetic fixture decimated to 600 channels its deepest misfit went
    from −391 to −363. The budget is split between the curves, since each adds
    its own bucket extrema. ``kept`` and ``fitted`` are re-indexed onto the
    channels that stay, and a fitted channel that went takes its model values
    with it.
    """
    # here and not at the top: viz.compare imports this module
    from .compare import decimation_index

    arrays = packed.arrays
    n = len(arrays["two_theta"])
    ceiling = CURVES_CEILING if ceiling is None else ceiling
    if n <= ceiling:
        return packed
    curves = [arrays["y_obs"]]
    if "fitted" in arrays:
        # off the fit's channels the model is the data and the residual zero,
        # so neither adds an extremum there
        for key, off in (("y_calc", arrays["y_obs"]), ("delta", np.zeros(n)),
                         ("delta_raw", np.zeros(n))):
            on_grid = np.array(off, dtype=float)
            on_grid[arrays["fitted"]] = arrays[key]
            curves.append(on_grid)
    sel = decimation_index(arrays["two_theta"], curves, ceiling // len(curves))
    where = np.full(n, -1)
    where[sel] = np.arange(len(sel))
    out = {"two_theta": arrays["two_theta"][sel], "y_obs": arrays["y_obs"][sel]}
    kept = where[arrays["kept"]]
    out["kept"] = kept[kept >= 0]
    if "fitted" in arrays:
        fitted = where[arrays["fitted"]]
        on = fitted >= 0
        out["fitted"] = fitted[on]
        for key, values in arrays.items():
            if key not in out and key != "fitted":
                out[key] = values[on]
    return Packed({**packed.header, "decimated": True}, out)


def _tick_rows(res) -> dict:
    """``ticks`` and ``tick_hkl``, the Miller indices only where they pair.

    ``tick_hkl`` is a companion pinned by index (``RefinementResult``), so a
    row's indices are sent only when they are as many as its positions. A
    result built before WP-1438 — one reopened from a project's history —
    carries positions and no indices, and then the row is simply absent rather
    than a list of blanks: the page falls back to the 2θ it always showed.
    """
    ticks = {phase: list(row) for phase, row in res.ticks.items()}
    hkl = {phase: list(res.tick_hkl[phase]) for phase, row in res.ticks.items()
           if phase in res.tick_hkl and len(res.tick_hkl[phase]) == len(row)}
    return {"ticks": ticks, "tick_hkl": hkl}
