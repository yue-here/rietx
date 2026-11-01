"""Pattern file readers — the front door.

The parsers themselves live one per module in :mod:`rietx.io.formats`; this
module is the entry point every caller uses (:func:`read_pattern`,
:func:`identify_format`) plus the re-exports that keep ``rietx.io.readers``
the address it has always been for ``PatternFormat``, ``PATTERN_FORMATS`` and
:func:`read_pdcif`.

Which formats, and how each is recognised, is :mod:`rietx.io.formats`'
business — including why the registry's *order* is behaviour rather than
presentation.  When the file carries per-point esds (or least-squares weights,
from which σ = 1/√w) they are stored in ``PatternData.sigma`` — never overridden
by the Poisson fallback (review finding M5).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from ..schemas.common import Diagnostic
from ..schemas.pattern import PatternData
from .formats import (
    PATTERN_FORMATS,
    READER_OPTIONS,
    PatternFormat,
    ReaderOption,
    ScanInfo,
    head,
    looks_binary,
    read_pdcif,
    reader_options_for,
)

__all__ = [
    "PATTERN_FORMATS",
    "READER_OPTIONS",
    "PatternFormat",
    "ReaderOption",
    "ScanInfo",
    "identify_format",
    "list_scans",
    "read_pattern",
    "read_pdcif",
    "reader_options_for",
]


def read_pattern(path: str | Path, *, diagnostics: list[Diagnostic] | None = None,
                 **options: Any) -> PatternData:
    """Read any supported pattern file, dispatching on *content* first.

    GSAS raw files are recognised by their ``BANK`` record rather than by
    suffix — the format is written with a zoo of extensions (``.fxye``,
    ``.gsas``, ``.gda``, ``.xra``, ``.raw``, …) and the record is unambiguous.

    ``options`` are the reader keywords in :data:`READER_OPTIONS` — ``block``
    for a pdCIF's data block, and later the ``scan`` a multi-scan vendor file
    holds several of.  They are named rather than positional precisely so a
    caller (or a project reopening its own pattern) need not know which reader
    will claim the file: an option this format does not take is dropped, while
    an option *no* format takes is a typo and raises.  See
    :func:`~rietx.io.formats.base.reader_options_for` for that distinction.

    ``diagnostics``, when a list is passed, collects what the reader **repaired
    or assumed** — a scan stored high→low and reversed, a duplicated point
    dropped, an option that did not apply.  It is the same channel
    :func:`~rietx.crystallography.cif.structure_from_cif` takes and exists
    for the same reason: a reader is the one layer that may silently correct a
    stranger's file, and it may only do so where it can say that it did.
    Returning a bare :class:`PatternData` was an accident, not a design.

    ``PATTERN_DEAD_CHANNELS`` is the one entry on that channel that is neither
    a repair nor an assumption, and it is here rather than only at compile
    because of *when* it is useful: a dead detector cell reaches the person as
    fourteen parameters at their bounds several minutes later, and none of the
    fourteen is the problem (issue #274).  It is format-agnostic — a dead cell
    is a property of the measurement and not of the file — so it is raised
    once here rather than in each reader, and only when a caller passed the
    list, which keeps it off the path of everyone who did not ask.

    **The axis every reader hands back is checked here**, whatever the format,
    because a wrong one parses perfectly: a GSAS file whose ``BANK`` record is
    missing falls to the ASCII reader and comes back in centidegrees, 100× too
    large (issue #230).  Two bands, split by the rule a reader's repairs
    follow (a contradiction raises, a report says so):

    - **past 180° raises**, naming the file, the reader and the range.  No
      scattering angle exceeds 180°, so the axis contradicts the claim that it
      is 2θ, and no exotic geometry makes it real;
    - **at or below 0° reports** ``PATTERN_X_AXIS_IMPLAUSIBLE`` and reads.  A
      scan through zero is geometrically real on a detector covering both
      sides, but no Bragg reflection lies there, and a header row read as data
      lands there too (issue #266's lands at exactly 0).

    The refusal runs on every call; the report, like the two below, only when
    a caller passed the list.

    ``PATTERN_SIGMA_CONSTANT`` is here for the dead-channel reason: a σ
    identical on every point makes the fit unweighted whichever reader
    produced it, so it is a property of the answer and not of one format.
    Issue #266 met it in ``xy``, which adopts any positive third column; on
    this hook it also reaches a GSAS esd column, a pdCIF weight loop and a
    ``.chi`` third column.  The σ is kept, because a uniform σ is legal.
    """
    p = Path(path)
    fmt = identify_format(p)
    kwargs = reader_options_for(fmt, options, diagnostics=diagnostics)
    data = fmt.read(p, diagnostics=diagnostics, **kwargs)
    axis = _axis_diagnostics(data, fmt, p.name)
    if diagnostics is not None:
        diagnostics.extend(axis)
        diagnostics.extend(_constant_sigma_diagnostics(data, fmt, p.name))
        diagnostics.extend(_dead_channel_diagnostics(data, p.name))
    return data


def _constant_sigma_diagnostics(data: PatternData, fmt: PatternFormat,
                                name: str) -> list[Diagnostic]:
    """``PATTERN_SIGMA_CONSTANT`` — :func:`read_pattern` says why it is here."""
    if data.sigma is None:
        return []
    sigma = np.asarray(data.sigma, dtype=np.float64)
    if not np.all(sigma == sigma[0]):
        return []
    v = float(sigma[0])
    return [Diagnostic(
        level="warning", code="PATTERN_SIGMA_CONSTANT",
        message=(
            f"{name}: σ is {v:g} on every one of its {sigma.size} points, as "
            f"{fmt.title} read it."),
        suggestion=(
            "If the column is a placeholder or a flag, set pattern.sigma = "
            "None to fall back to Poisson weights √max(y, 1). Otherwise "
            "re-export the file with its esd where this reader looks for it."),
        value=v,
    )]


#: No scattering angle exceeds this, so an axis running past it is not 2θ.
TWO_THETA_MAX_DEG = 180.0


def _axis_diagnostics(data: PatternData, fmt: PatternFormat,
                      name: str) -> list[Diagnostic]:
    """Refuse an axis past 180°, report one reaching 0° — :func:`read_pattern`
    says why each band gets which answer.

    A statement about **an angle**, so it abstains on a time-of-flight axis: a
    flight time in µs violates the [0, 180] bound by construction, and the
    reader that put it on ``pattern.tof`` did so off a declaration (a GSAS
    bintype, a Mantid unit line), which is the evidence this range check
    exists to stand in for when a format gives none."""
    if data.axis != "two_theta":
        return []
    tt = data.tt()
    lo, hi = float(tt[0]), float(tt[-1])
    if hi > TWO_THETA_MAX_DEG:
        hint = ""
        # checked before it is offered: only a range that division by 100
        # puts inside (0, 180] is evidence of centidegrees, and only the
        # two/three-column reader is where a GSAS file lands unconverted.
        # Every other reader knows its unit, so ÷100 would be a wrong lead.
        if (fmt.name == "xy" and 0.0 < lo
                and hi / 100.0 <= TWO_THETA_MAX_DEG):
            hint = (f" Divided by 100 it would run {lo / 100:g}° to "
                    f"{hi / 100:g}°. GSAS writes 2θ in centidegrees, and a "
                    "GSAS file whose BANK record is missing reads this way.")
        if "axis" in fmt.options and data.metadata.get("declared_axis") is None:
            # offered, never taken: a flight time and an angle are both
            # ascending columns of numbers, and only the caller knows which
            hint += (" If the column is a flight time in µs, declare it with "
                     "axis='tof'.")
        raise ValueError(
            f"{name} was read as {fmt.title}, and its x axis runs {lo:g}° to "
            f"{hi:g}°. No scattering angle exceeds 180°, so this axis is not "
            f"2θ in degrees.{hint}")
    if lo > 0.0:
        return []
    from ..background.diagnostics import _exclusion_interval

    at_or_below = tt[tt <= 0.0]
    # widened outward and never empty, so the interval the message asks the
    # caller to exclude contains every point it counted: a lone point at
    # exactly 0° (#266's header row) would otherwise print as (0.000, 0.000),
    # which check_interval refuses
    ex_lo, ex_hi = _exclusion_interval(lo, float(at_or_below[-1]))
    return [Diagnostic(
        level="warning", code="PATTERN_X_AXIS_IMPLAUSIBLE",
        message=(
            f"{name}: the x axis starts at {lo:g}°, and {at_or_below.size} of "
            f"its {tt.size} points sit at or below 0°. The file was read as "
            f"{fmt.title}, and that reader takes the axis to be 2θ in "
            f"degrees."),
        where=[f"{ex_lo:.3f}-{ex_hi:.3f}"],
        suggestion=(
            "Check that the axis is 2θ in degrees. If it is, exclude the "
            f"interval ({ex_lo:.3f}, {ex_hi:.3f}) before fitting."),
        value=lo,
    )]


def _dead_channel_diagnostics(data: PatternData, name: str) -> list[Diagnostic]:
    """``PATTERN_DEAD_CHANNELS`` for a pattern just read — see
    :func:`~rietx.background.diagnostics.dead_channels`, which is the one
    authority and answers nothing without the file's own σ column."""
    from ..background.diagnostics import _dead_interval, dead_channels

    if data.sigma is None or data.axis != "two_theta":
        return []  # the run and window lengths are degrees of 2θ
    out = []
    for run in dead_channels(data.tt(), data.y(), data.sig()):
        lo, hi = _dead_interval(run)
        out.append(Diagnostic(
            level="warning", code="PATTERN_DEAD_CHANNELS",
            message=(
                f"{name}: {run.n_channels} channel(s) at "
                f"{lo:.3f}-{hi:.3f}° carry {run.level_fraction:.2%} of the "
                "local background, with an esd that fell with them. They "
                f"weigh about {run.weight_ratio:,.0f}× a live channel there."),
            where=[f"{lo:.3f}-{hi:.3f}"],
            suggestion=(
                f"Exclude the interval ({lo:.3f}, {hi:.3f}) before fitting."),
        ))
    return out


def list_scans(path: str | Path) -> list[ScanInfo]:
    """What there is to choose between in a file that holds several measurements.

    The companion to the ``scan`` reader option: a choice cannot honestly be
    offered without saying what the alternatives are, which is what a CLI
    listing and the import wizard's scan picker both need.  It is *not* on the
    preview path — ``scan_count`` travels in the pattern's own metadata from the
    single read, so showing "3 scans" never costs a second parse of a 60 MB file.

    A format that holds one measurement per file is refused rather than answered
    with a one-element list: "this file has one scan" and "this format has no
    scan structure" are different answers, and only the second is true of a
    pdCIF.
    """
    p = Path(path)
    fmt = identify_format(p)
    if fmt.scans is None:
        raise ValueError(f"{p.name} was read as {fmt.title}, which holds one "
                         "measurement per file — there are no scans to list")
    return fmt.scans(p)


def identify_format(path: str | Path) -> PatternFormat:
    """Which registered format claims ``path`` — the dispatch, written once.

    Reachable as a refusal since ``xy`` stopped being total: a file no format
    claims is one this build cannot read, and saying **which formats it can**
    is the whole difference between a message and a traceback.  Built from the
    registry rather than written out, so a format added tomorrow appears in it.

    **The list is the readers, not the registry** — ``refuses`` entries are
    filtered out, as ``cli.py`` already does for the same purpose.  They are
    formats recognised *in order to be declined*, so listing one under
    "Supported" contradicts the sentence it follows, and WP-1407 made that
    visible rather than new: with a peak-list entry it read oddly, and with an
    "Unrecognised binary .raw" entry it told a user their unrecognised binary
    ``.raw`` was unreadable and then offered it as a supported format.
    """
    p = Path(path)
    for fmt in PATTERN_FORMATS:
        if fmt.matches(p):
            return fmt
    why = " (it looks binary)" if looks_binary(head(p)) else ""
    known = ", ".join(f"{f.title} [{', '.join(f.extensions) or 'any'}]"
                      for f in PATTERN_FORMATS if f.refuses is None)
    raise ValueError(
        f"{p.name} is not a powder pattern this build can read{why}. "
        f"Supported: {known}")
