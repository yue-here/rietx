"""FIT2D / pyFAI ``.chi`` — an azimuthally integrated synchrotron pattern.

Spec: Hammersley (1997/2016), *FIT2D: An Introduction and Overview*, ESRF
Internal Report ESRF97HA02T, § "CHI file format"; the same four-line header is
what pyFAI's ``save1D``/``AzimuthalIntegrator.integrate1d`` writes.

    line 1   title, usually the source image's filename
    line 2   the **x-axis label** — and this is the whole difficulty
    line 3   the y-axis label
    line 4   ``<npoints>`` optionally followed by ``<ndatasets>``
    line 5…  the points, ``x y`` (some writers add a third σ column)

Two things about this format cost more than parsing it.

**Line 4 is why it needs a reader of its own.**  ``2000 1`` is a perfectly good
pair of floats, so the ASCII-column fallback appends it as a data point at
x = 2000, y = 1 — a phantom peak-free point far outside the pattern, which
survives every plot and quietly widens the fitted range.

**The x axis may not be 2θ at all.**  Integration output is written on 2θ, on q
or on d, and the file says which only in prose that no one standardised.
Reading a q axis as 2θ produces a confident wrong cell from values that parse
perfectly, so a recognisably non-2θ axis is **refused** rather than converted:
the conversion needs a wavelength this reader has not been given, and inventing
one is the failure this package exists to avoid.  The label patterns below are
this format's share of that; :func:`base.check_axis` decides.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from ...schemas.common import Diagnostic
from ...schemas.pattern import PatternData
from .base import PatternFormat, ascending, check_axis, head, pattern_data

#: Labels that are recognisably 2θ.  Checked first, because "2-Theta Angle
#: (Degrees)" must not be read as a d axis by the ``d`` in "Degrees".
_TWO_THETA = re.compile(r"2\s*[-_]?\s*theta|\btth\b|\b2th\b|θ", re.I)

#: Labels that are recognisably **not** 2θ, with what each one is, so the
#: refusal can say what the file actually holds rather than only what it lacks.
_OTHER_AXES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bq\b|\bq[\s_\-]*\(|q_?(nm|a|å)", re.I), "a scattering vector q"),
    (re.compile(r"\bd\b[\s_\-]*\(|\bd[\s_\-]*spacing\b|\bd\b\s*$", re.I),
     "a d-spacing"),
    (re.compile(r"\bradial|\bpixel|\bchannel\b", re.I), "a detector coordinate"),
)


def read_chi(path: str | Path, *,
             diagnostics: list[Diagnostic] | None = None) -> PatternData:
    p = Path(path)
    lines = p.read_text(encoding=head(p).encoding, errors="replace").splitlines()
    if len(lines) < 5:
        raise ValueError(f"{p.name}: a .chi has a four-line header and at least "
                         f"one point; this file has {len(lines)} line(s)")

    x_label = lines[1].strip()
    is_two_theta = bool(_TWO_THETA.search(x_label))
    other = next((what for label, what in _OTHER_AXES if label.search(x_label)), None)
    check_axis(x_label, path=p, field="the x-axis label on line 2",
               two_theta=is_two_theta, other=None if is_two_theta else other,
               remedy=("Converting it needs the wavelength it was integrated at, "
                       "which this file does not carry — so re-integrate on 2θ, "
                       "or convert the axis yourself and write a two-column "
                       "file."),
               diagnostics=diagnostics)

    rows = []
    for line in lines[4:]:
        parts = line.replace(",", " ").split()
        if not parts:
            continue
        try:
            vals = [float(v) for v in parts[:3]]
        except ValueError:
            raise ValueError(f"{p.name}: {line.strip()!r} follows the four-line "
                             "header but is not a row of numbers") from None
        if len(vals) >= 2:
            rows.append(vals)
    if not rows:
        raise ValueError(f"{p.name}: the four-line header is followed by no data")

    n_cols = min(len(r) for r in rows)
    arr = np.array([r[:n_cols] for r in rows], dtype=np.float64)
    # a third column with no positive σ reaches read_pattern's hook (WP-1952)
    sigma = arr[:, 2] if n_cols >= 3 else None
    tt, y, sig = ascending(arr[:, 0], arr[:, 1], sigma, path=p, fmt=CHI,
                           diagnostics=diagnostics)
    # the x label verbatim, never normalised: it is the only record of what the
    # integration actually produced, and PATTERN_X_AXIS_ASSUMED points at it
    return pattern_data(p, tt, y, sig, source_file=p.name, format="chi",
                        x_label=x_label, title=lines[0].strip())


def _header_shape(h) -> list[str] | None:
    """The four header lines when they have the shape a ``.chi`` header has.

    Bounded — this is all ``head()``'s 4 kB.  Lines 1-3 must be present, not
    commented (a commented header is an ``.xy`` with prose on top) and not
    parse as a row of numbers; line 4 must be one or two integers.
    """
    lines = h.text.splitlines()
    if len(lines) < 5:
        return None
    for line in lines[:3]:
        s = line.strip()
        if not s or s.startswith(("#", "!", "'", "/", ";")):
            return None
        parts = s.replace(",", " ").split()
        try:
            [float(v) for v in parts[:2]]
        except ValueError:
            continue
        if len(parts) >= 2:
            return None      # a row of numbers: this is data, not a header
    counts = lines[3].split()
    if not 1 <= len(counts) <= 2 or not all(c.lstrip("+").isdigit() for c in counts):
        return None
    return lines


def looks_chi(p: Path) -> bool:
    """Two gates, and the second one is the only O(N) sniff in the package.

    The shape gate above is bounded and cheap.  It is not decisive on its own:
    an ``.xy`` with a three-line prose header and a lone integer on the fourth
    would pass it.  What *is* decisive is line 4's own claim — ``npoints`` must
    equal the number of rows that follow — so the second gate reads the file.

    That is a stated exemption to the bounded-head rule, not a free ride: it
    costs O(N), it runs only behind the shape gate (so it is rare), and it buys
    the one thing the shape cannot, which is the difference between this format
    and the catch-all it would otherwise fall into.
    """
    if _header_shape(head(p)) is None:
        return False
    try:
        lines = p.read_text(encoding=head(p).encoding, errors="replace").splitlines()
    except OSError:
        return False
    declared = int(lines[3].split()[0])
    return declared == sum(1 for line in lines[4:] if line.strip())


CHI = PatternFormat(
    name="chi",
    title="FIT2D / pyFAI integrated pattern (.chi)",
    extensions=(".chi",),
    sniff=("a four-line header — title, x label, y label, point count — whose "
           "declared count matches the rows that follow"),
    sigma="a third column when the writer emitted one, else the Poisson fallback",
    matches=looks_chi,
    read=read_chi,
    options=("nonpositive_sigma",),
)
