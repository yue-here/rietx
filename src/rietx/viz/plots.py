"""Static obs/calc/difference plotting (matplotlib/Agg).

This renderer produces the standard Rietveld panel: observed points, calculated
line, the difference below them, and per-phase reflection tick rows below
*that*.  The interactive plotly viewer is :mod:`rietx.viz.html`; the
VLM-readable montage is :func:`plot_for_vlm` here, and it is deliberately *not*
held to any of what follows — it is drawn for a vision model, not for a person.

Six house conventions decide the panel's *layout*, not merely its colours, and
each is load-bearing enough to state once here rather than in the drawing code:

* **The reading order down the figure is data, residual, reflection rows**, in
  every mode.  The residual is the thing being read against the peaks it
  belongs to, so nothing may come between them; the rows are the index of what
  the model contains, and an index goes at the foot.
* **Every label goes in the right-hand gutter**, and the curve names go there
  as one block bottom-aligned with the data they name.  A figure carrying
  curves, a residual and one row per phase has more than one kind of feature,
  and one convention for all of them costs the reader a single lookup instead
  of one per feature.  The block is what keeps three converging names off each
  other and off whatever is drawn below them, at any figure size; `curve`
  alignment puts each name level with where its own curve ends, which reads
  better on a pattern whose curves stay apart.  Either way there is no legend
  box: a legend makes the eye leave the data to decode a colour.
* **Colour is assigned by role, never by series index.**  Observed is neutral
  dark markers (it is the measurement), calculated is the one accent line, the
  residual is a subordinate grey, the background a muted tint of the accent it
  is part of — and a *single* phase's tick row is neutral dark rather than the
  first phase colour, because colour is for telling rows apart and one row has
  nothing to be told apart from.  A modelled curve is also dashed, so the
  figure survives greyscale.
* **The left spine and its y ticks span only the quantity being read**, on both
  axes.  Whatever shares an axis without numbers of its own — the offset
  residual, the tick rows — sits outside those bounds, and the spine stops at
  the tallest point rather than at the last tick, so no peak escapes above the
  end of the axis.
* **The layout is arithmetic in display distance, not in counts.**  Headroom,
  row spacing, the gap between gutter labels: all of it is solved in the
  intensity axis's *transformed* space, which is what lets ``y_scale=`` move to
  a log or a root axis without a single fraction of the data range needing to
  be retuned.  Row spacing in particular comes from the type size — every row
  carries a gutter label, so the gap between rows has to clear a line of type,
  and rows spaced evenly in data coordinates put their labels on top of each
  other as soon as the figure or the phase count changes.
* **When the residual takes its own panel the two are separated, not butted.**
  A butted join wants ticks on both sides to earn its ink, and those ticks
  claim to be a shared axis the reader can trace — which is a promise the upper
  panel cannot keep once its own scale is nonlinear.  A plain gap, interior
  spine hidden, says what is true: two quantities over one x range.

Fit statistics are a corner annotation, not a title — the caption is the title,
and a panel that will be pasted into a report should not arrive carrying a
second one.
"""

from __future__ import annotations

import numpy as np

from .._about import DIST_NAME
from ..schemas.results import RefinementResult

#: One type size for the whole figure, in points, sized for the ~7.6 in wide
#: panel :func:`plot_result` builds by default (a report column or a screen).
#: The figure is built at the size it is read; scaling it in the document
#: afterwards divides this by the same factor, which is where most unreadable
#: figures come from.  ``font_size=`` moves it for another exposure surface.
BASE = 11.0

#: The x axis a pattern may be drawn against.  2θ is the measurement's own
#: coordinate and is meaningless without the wavelength beside it; *Q* and *d*
#: are derived from it *through* the wavelength and are therefore comparable
#: across wavelengths, which is the whole reason to use them — so they need
#: ``wavelength=`` and their axis label carries no λ.
X_AXES = ("two_theta", "q", "d")

#: Intensity scales.  ``sqrt`` is the counting-statistics one — equal display
#: distance for equal Poisson σ, so a weak peak's shape is readable beside a
#: strong one without either being misrepresented; ``log`` compresses hardest
#: and cannot show a channel at or below zero; ``asinh`` is linear near zero
#: and logarithmic beyond it, so it survives the negative channels a
#: background-subtracted pattern carries.
Y_SCALES = ("linear", "sqrt", "log", "asinh")

#: Colours by role, per background.  The roles are fixed; only the hues change
#: with the ground.  Observed is neutral dark and calculated is the accent on
#: both, but the residual, the background line and the zero rule have to be
#: chosen per ground: subordinate means *darker* than the text on a white page
#: and *dimmer* than it on a black one, and a single ``dark_background`` context
#: around the call would flip the axes while leaving all three unchanged — which
#: is the whole reason ``style=`` exists.
#: The background line takes a *muted* version of the calculated hue rather
#: than a third grey: it is a component of the calculated curve, so the hue
#: says what it is, and the grey it would otherwise share with the residual is
#: too faint to carry its own gutter label on a white page.
PALETTES = {
    "light": {"obs": "#1a1a1a", "calc": "#ff7f0e", "bkg": "#b5793a",
              "diff": "#737373", "zero": "#c9c9c9", "band": "#2a9d2a",
              "tick": "#1a1a1a",
              "phase": ["#1f77b4", "#d62728", "#2ca02c", "#9467bd"]},
    "dark": {"obs": "#d2c9bd", "calc": "#ff9d4d", "bkg": "#c99a6a",
             "diff": "#8f8f8f", "zero": "#4a4a4a", "band": "#4fd44f",
             "tick": "#d2c9bd", "fg": "#f1ece5", "rule": "#d2c9bd",
             "ground": "#1d1813",
             "phase": ["#6fb1ff", "#ff7b7b", "#6ede8a", "#c9a6ff"]},
}


def _ground_rc(hue: dict) -> dict:
    """Ground, type, spines and ticks on a dark page.

    ``dark_background`` paints a pure black ground and leaves type, spines and
    ticks at pure white, and both ends of that are wider than the page the
    figure goes onto: the landing page and the manual's dark theme sit their
    figures on a warm near-black panel and set body text to a warm off-white.
    Matching them is what makes the figure part of the page rather than a
    brighter card laid on top of it, so ``ground`` is that panel colour and the
    type takes ``fg``.

    Spines, tick marks and the observed curve then step *down* from the type to
    ``rule``: on a white page they are darker than the text, and dimmer is what
    the same subordination means here — at the type's own value they read as
    white however warm the hue is.  Light keeps matplotlib's own black on
    white; nothing about a white page needs correcting.
    """
    fg, rule = hue["fg"], hue["rule"]
    return {"figure.facecolor": hue["ground"], "axes.facecolor": hue["ground"],
            "savefig.facecolor": hue["ground"],
            "text.color": fg, "axes.labelcolor": fg,
            "xtick.labelcolor": fg, "ytick.labelcolor": fg,
            "axes.edgecolor": rule, "xtick.color": rule, "ytick.color": rule}


def _rc(font_size: float) -> dict:
    """rcParams the panel draws under, scoped to the call.

    One sans face at one size, maths included, so ``2θ`` matches the digits
    beside it; no grid, no top/right spine.  This is a *style context* rather
    than a global ``rcParams`` update precisely so a caller's own settings come
    back the moment the call returns.
    """
    return {
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans"],
        "mathtext.fontset": "dejavusans",
        "font.size": font_size,
        "axes.labelsize": font_size,
        "xtick.labelsize": font_size,
        "ytick.labelsize": font_size,
        "legend.fontsize": font_size,
        "axes.grid": False,
        "axes.spines.top": False,
        "axes.spines.right": False,
        # gutter labels sit outside the axes; without this a long phase name
        # would be cropped at the canvas edge on save
        "savefig.bbox": "tight",
    }


def _hkl_marker():
    """A reflection tick drawn as a lens rather than a bar.

    Pointed at the ends and slightly convex at the sides, so the extra ink sits
    at the centre of the mark: it stays legible at small size without being
    thickened into a heavy black comb across the bottom of the figure.
    """
    from matplotlib.path import Path

    return Path([(0, -1), (0.17, 0), (0, 1), (-0.17, 0), (0, -1)],
                [Path.MOVETO, Path.CURVE3, Path.CURVE3, Path.CURVE3, Path.CURVE3])


def _spread(ys: list[float], min_gap: float) -> list[float]:
    """Keep each label level with its own feature, never closer than a line.

    Observed and calculated converge at the right-hand end of most patterns, so
    their gutter labels want the same height.  Pushing them apart by exactly one
    line of type — order preserved, group recentred — keeps each as near its own
    curve as it can be.  Moving one of them to a different convention instead
    would trade a small overlap for the whole figure's label convention.
    """
    order = sorted(range(len(ys)), key=lambda i: ys[i])
    vals = sorted(ys)
    for k in range(1, len(vals)):
        vals[k] = max(vals[k], vals[k - 1] + min_gap)
    shift = (sum(ys) - sum(vals)) / len(ys)
    out = [0.0] * len(ys)
    for i, v in zip(order, vals, strict=True):
        out[i] = v + shift
    return out


def _x_values(two_theta, x_axis: str, wavelength: float | None):
    """The abscissa the panel is drawn against, and its axis label.

    Q = 4π sinθ/λ and d = λ/(2 sinθ) are the same measurement in a coordinate
    that does not depend on the wavelength, which is why neither label repeats
    it and why the 2θ label must.
    """
    tt = np.asarray(two_theta, dtype=float)
    if x_axis == "two_theta":
        label = r"$2\theta$ (degrees)"
        if wavelength is not None:
            label += f", $\\lambda$ = {wavelength:g} Å"
        return tt, label
    sin_theta = np.sin(np.radians(tt) / 2.0)
    if tt.size and np.min(sin_theta) <= 0.0:
        raise ValueError(f"x_axis={x_axis!r} is undefined at 2θ ≤ 0; window the "
                         "pattern with two_theta_range=")
    if x_axis == "q":
        return 4.0 * np.pi * sin_theta / wavelength, r"$Q$ (Å$^{-1}$)"
    return wavelength / (2.0 * sin_theta), r"$d$ (Å)"


def _sqrt_forward(v):
    return np.sqrt(np.clip(np.asarray(v, dtype=float), 0.0, None))


def _sqrt_inverse(t):
    return np.asarray(t, dtype=float) ** 2


def _y_scale(scale: str, floor: float, top: float):
    """``(forward, inverse, set_yscale args, usable floor)`` for an intensity axis.

    The panel's layout is arithmetic in *display* distance — headroom as a
    fraction of the drawn span, a gutter gap of one line of type — so every
    scale hands back the pair that converts between counts and that distance.
    The pair only has to agree with matplotlib's own scale up to an affine map
    (log10 against ln, say): every use here is a ratio of differences.  ``asinh``
    is the exception that has to match *exactly*, because its shape depends on
    ``linear_width``, so the same width is passed to both halves.
    """
    if scale == "linear":
        return (lambda v: np.asarray(v, dtype=float),
                lambda t: np.asarray(t, dtype=float), None, floor)
    if scale == "sqrt":
        return (_sqrt_forward, _sqrt_inverse,
                ("function", {"functions": (_sqrt_forward, _sqrt_inverse)}),
                max(floor, 0.0))
    if scale == "log":
        return (lambda v: np.log10(np.clip(np.asarray(v, dtype=float),
                                           1e-300, None)),
                lambda t: np.power(10.0, np.asarray(t, dtype=float)),
                ("log", {}), floor)
    width = max(abs(top), 1.0) * 0.02
    return (lambda v: width * np.arcsinh(np.asarray(v, dtype=float) / width),
            lambda t: width * np.sinh(np.asarray(t, dtype=float) / width),
            ("asinh", {"linear_width": width}), floor)


def _nice_ticks(forward, inverse, lo: float, hi: float, n: int = 4):
    """Ticks a reader would name, spaced evenly in *display* distance.

    A locator working on the data values bunches every tick against the top of
    a root or asinh axis, which is the axis's whole point defeated.  Spacing
    them evenly in the transformed space and rounding each to two significant
    figures puts them where the eye expects them and still lands on numbers
    worth reading.
    """
    grid = np.linspace(float(forward(lo)), float(forward(hi)), n + 1)
    out: list[float] = []
    for value in np.asarray(inverse(grid), dtype=float):
        if value == 0.0:
            rounded = 0.0
        else:
            step = 10.0 ** (np.floor(np.log10(abs(value))) - 1.0)
            rounded = float(np.round(value / step) * step)
        if lo <= rounded <= hi and (not out or rounded > out[-1]):
            out.append(rounded)
    return out


def plot_result(result: RefinementResult, *, path: str | None = None,
                two_theta_range: tuple[float, float] | None = None,
                show_background: bool = True, weighted: bool = False,
                style: str = "light", wavelength: float | None = None,
                x_axis: str = "two_theta", y_scale: str = "linear",
                label_align: str = "bottom",
                figsize: tuple[float, float] | None = None,
                font_size: float = BASE, dpi: int = 300):
    """Standard Rietveld panel: observed, calculated, difference, tick rows.

    The difference is the classic ``obs − calc`` on the intensity axis, at the
    intensity's own scale and never magnified, sitting a small fixed gap under
    the data's floor so it can be read against the peaks it belongs to.  The
    reflection rows come below *it*.

    ``weighted=True`` draws Δ/σ instead, in its own panel with a ±3σ band.  A
    raw difference shares the intensity axis, so a deviation on a strong peak
    dominates the eye even when it is statistically insignificant; Δ/σ has
    expectation 1 under a correct model, which puts the curve on an absolute
    statistical scale (Toby, 2024, J. Appl. Cryst. 57, 175).  It is not the
    intensity in the intensity's units, so it cannot share that axis — which is
    exactly why it is not the default: the panel it needs costs the reader the
    one thing the classic layout gives away free, a residual and the peak that
    caused it in one glance.

    ``y_scale`` moves the intensity axis: ``"sqrt"`` gives equal display
    distance to equal Poisson σ, ``"log"`` compresses hardest, ``"asinh"``
    survives channels at or below zero.  Any of them forces the difference into
    its own panel too, because an offset raw difference is negative by
    construction and a nonlinear intensity axis cannot draw it — that panel is
    linear and in the intensity's own units, so nothing is rescaled, only
    moved.  ``x_axis="q"``/``"d"`` redraws against Q or d-spacing, which need
    ``wavelength=``; a *d* axis is drawn ascending, so the pattern is mirrored
    rather than the axis reversed.

    ``label_align="bottom"`` (the default) puts the curve names in the gutter as
    one block, bottom-aligned with the data they name, which is what keeps them
    off each other and off the residual's own label at any figure size;
    ``"curve"`` puts each name level with where its curve ends, which reads
    better when the curves stay apart.

    ``two_theta_range`` is a window on the pattern, not a crop of a whole-range
    figure: the intensity scale, the residual offset and the tick rows are all
    built from what the window contains, so a zoom is a figure of its own data.
    It is in 2θ whatever ``x_axis`` is, because it selects channels rather than
    describing the drawing.

    ``wavelength`` puts λ on the 2θ axis, which is meaningless without it.  It
    is a parameter rather than a lookup because a :class:`RefinementResult`
    does not carry the emission line — pass
    ``instrument.source.lines[0].wavelength.value`` (a ``Parameter`` since
    WP-1134, so ``.value`` is required here), or leave it off and say the
    source in the caption.

    ``figsize``/``font_size`` are the exposure surface: build the figure at the
    width it will be read at rather than scaling it afterwards.  The defaults
    suit a report column or a screen at roughly 7.6 in.  ``dpi`` is high enough
    that the type and the reflection marks do not fringe on a retina display;
    a ``.svg`` or ``.pdf`` ``path`` sidesteps the question entirely.

    ``style="dark"`` picks the dark-ground palette above and draws through
    matplotlib's ``dark_background`` style, for a figure going onto a dark page.
    """
    if style not in PALETTES:
        raise ValueError(f"style must be one of {sorted(PALETTES)}, not {style!r}")
    if x_axis not in X_AXES:
        raise ValueError(f"x_axis must be one of {list(X_AXES)}, not {x_axis!r}")
    if y_scale not in Y_SCALES:
        raise ValueError(f"y_scale must be one of {list(Y_SCALES)}, not {y_scale!r}")
    if label_align not in ("bottom", "curve"):
        raise ValueError("label_align must be 'bottom' or 'curve', not "
                         f"{label_align!r}")
    if x_axis != "two_theta" and wavelength is None:
        raise ValueError(f"x_axis={x_axis!r} is derived from 2θ through the "
                         "wavelength; pass wavelength=")
    try:
        import matplotlib
        matplotlib.use("Agg", force=False)
        import matplotlib.pyplot as plt
        from matplotlib.ticker import (
            FuncFormatter,
            MaxNLocator,
            NullLocator,
            ScalarFormatter,
        )
    except ImportError as exc:  # pragma: no cover
        raise ImportError(f"plotting needs matplotlib: pip install '{DIST_NAME}[viz]'") from exc

    tt = np.asarray(result.two_theta, dtype=float)
    y_obs = np.asarray(result.y_obs, dtype=float)
    y_calc = np.asarray(result.y_calc, dtype=float)
    y_bkg = np.asarray(result.y_background, dtype=float)
    sigma = result.sig()
    if two_theta_range is not None:
        keep = (tt >= two_theta_range[0]) & (tt <= two_theta_range[1])
        if not keep.any():
            raise ValueError(f"two_theta_range {two_theta_range} contains no points")
        tt, y_obs, y_calc = tt[keep], y_obs[keep], y_calc[keep]
        sigma = sigma[keep]
        y_bkg = y_bkg[keep] if y_bkg.size == keep.size else y_bkg[:0]
    hue = PALETTES[style]
    has_bkg = bool(show_background and y_bkg.size == tt.size and np.any(y_bkg))

    x, x_label = _x_values(tt, x_axis, wavelength)
    if x.size > 1 and x[0] > x[-1]:
        # d ascends as 2θ descends.  Mirror the pattern rather than reversing
        # the axis: an axis that counts down is read wrong at a glance, and
        # everything downstream — where a curve ends, which end the gutter is
        # on — then follows from the drawn order without a special case.
        back = slice(None, None, -1)
        x, y_obs, y_calc, sigma = x[back], y_obs[back], y_calc[back], sigma[back]
        y_bkg = y_bkg[back]
    diff = y_obs - y_calc
    rows = [(name, _x_values(np.asarray(pos, dtype=float), x_axis, wavelength)[0])
            for name, pos in result.ticks.items()]
    n_rows = len(rows)

    # a raw difference is negative by construction, so it can share the
    # intensity axis only while that axis is linear
    inline = not weighted and y_scale == "linear"

    with plt.style.context([_rc(font_size)] if style == "light"
                           else ["dark_background", _rc(font_size), _ground_rc(hue)]):
        line_in = 1.35 * font_size / 72.0
        if figsize is None:
            figsize = (7.6, 4.4) if inline else (7.6, 5.6)
        left, right, top_m, bottom_m = 0.13, 0.805, 0.965, 0.125
        if inline:
            fig, ax = plt.subplots(figsize=figsize, dpi=dpi)
            axd = None
            hspace = 0.0
        else:
            # the lower panel is sized for what it must hold — the residual
            # trace plus one line of type per phase row — rather than given a
            # fixed share, which would crush the rows on a six-phase fit
            avail = figsize[1] * (top_m - bottom_m)
            gap_in = 0.30
            lower_in = min(0.50 * (avail - gap_in),
                           max(0.70, 0.78 + (n_rows + 1.0) * line_in))
            upper_in = avail - gap_in - lower_in
            hspace = gap_in / (0.5 * (upper_in + lower_in))
            fig, (ax, axd) = plt.subplots(
                2, 1, figsize=figsize, dpi=dpi, sharex=True,
                gridspec_kw={"height_ratios": [upper_in, lower_in]})
        # explicit margins rather than tight_layout: the gutter on the right is
        # reserved for the labels, and the row spacing below needs to know the
        # axes height in inches *before* anything is drawn
        fig.subplots_adjust(left=left, right=right, top=top_m, bottom=bottom_m,
                            hspace=hspace)

        # observed data is markers, never a line — it is discrete counts
        ax.plot(x, y_obs, marker="x", ms=0.24 * font_size, mew=0.6,
                color=hue["obs"], ls="none", zorder=2)
        ax.plot(x, y_calc, "-", lw=1.0, color=hue["calc"], zorder=3)
        if has_bkg:
            # modelled, so dashed: the epistemic line style, held across figures
            ax.plot(x, y_bkg, "--", lw=0.8, color=hue["bkg"], zorder=1)

        x0, x1 = float(x.min()), float(x.max())
        top = float(y_obs.max())
        if y_scale == "log":
            if top <= 0.0:
                raise ValueError("y_scale='log' needs at least one positive "
                                 "intensity channel")
            floor = float(y_obs[y_obs > 0.0].min())    # top > 0, so this exists
        else:
            floor = min(float(y_obs.min()), 0.0)
        forward, inverse, setter, floor = _y_scale(y_scale, floor, top)
        if setter is not None:
            ax.set_yscale(setter[0], **setter[1])

        u_top, u_floor = float(forward(top)), float(forward(floor))
        u_span = (u_top - u_floor) or 1.0
        u_head = u_top + 0.20 * u_span     # headroom for the corner annotation
        head = float(inverse(u_head))
        span = top - floor or 1.0
        # the tick numbers and the left spine start at zero — or at the lowest
        # measured channel where that is below zero, and at the lowest positive
        # one on a log axis, which cannot reach zero at all
        base = floor if y_scale == "log" else min(floor, 0.0)

        fig_h = fig.get_size_inches()[1]
        row_axes = ax if inline else axd
        row_h_in = row_axes.get_position().height * fig_h
        # a row carries a gutter label, so the gap between rows must clear a
        # line of type.  The axes range is itself linear in the gap, so solve
        # for it rather than guessing a fraction of the data that stops working
        # at the next figure size or phase count.
        line_frac = line_in / row_h_in
        denom = 1.0 - line_frac * (n_rows + 0.6)

        if inline:
            # the residual's own top sits a fixed small gap under the data's
            # floor: same axes, same scale, close enough to read against the
            # peaks it belongs to
            diff_zero = floor - 0.03 * span - float(diff.max())
            rows_top = diff_zero + float(diff.min())
            row_gap = (line_frac * (head - rows_top) / denom if denom > 0.35
                       else 0.10 * span)
            ax.plot(x, diff + diff_zero, "-", lw=0.7, color=hue["diff"], zorder=2)
            ax.axhline(diff_zero, lw=0.4, color=hue["zero"], zorder=1)
        else:
            diff_zero = None
            resid = diff / sigma if weighted else diff
            r_hi, r_lo = float(np.max(resid)), float(np.min(resid))
            if weighted:
                r_hi, r_lo = max(r_hi, 3.0), min(r_lo, -3.0)
            r_span = (r_hi - r_lo) or 1.0
            r_head = r_hi + 0.08 * r_span
            rows_top = r_lo - 0.08 * r_span
            row_gap = (line_frac * (r_head - rows_top) / denom if denom > 0.35
                       else 0.15 * r_span)
            axd.plot(x, resid, "-", lw=0.6, color=hue["diff"])
            if weighted:
                axd.axhspan(-3, 3, color=hue["band"], alpha=0.15, lw=0)
            else:
                axd.axhline(0.0, lw=0.4, color=hue["zero"], zorder=1)

        marker = _hkl_marker()
        row_y = [rows_top - (i + 1) * row_gap for i in range(n_rows)]
        for i, ((_, positions), y) in enumerate(zip(rows, row_y, strict=True)):
            pos = positions[(positions >= x0) & (positions <= x1)]
            # one phase has nothing to be told apart from, so it takes the
            # neutral dark rather than the first phase colour
            colour = (hue["tick"] if n_rows == 1
                      else hue["phase"][i % len(hue["phase"])])
            row_axes.plot(pos, np.full(pos.size, y), ls="none", marker=marker,
                          ms=1.1 * font_size, mfc=colour, mec=colour, mew=0)

        # with no rows at all the floor still has to hold whatever the gutter
        # puts lowest, which converges there on any pattern ending in background
        row_floor = (row_y[-1] - 0.6 * row_gap) if n_rows else rows_top - 0.8 * row_gap
        ax.set_xlim(x0, x1)
        ax.set_ylim(row_floor if inline else floor, head)
        ax.xaxis.set_major_locator(MaxNLocator(nbins=6))

        # y ticks and the left spine cover only the intensity being read; the
        # spine spans the data rather than stopping at the last tick, so no
        # peak escapes above the end of the axis
        log_sub_decade = False
        if y_scale == "log":
            # the decades inside the measured range, and no others: matplotlib's
            # locator happily puts a labelled tick a whole decade above the
            # tallest peak, where the spine has already stopped
            lo_k = int(np.ceil(np.log10(base)))
            hi_k = int(np.floor(np.log10(top)))
            log_sub_decade = hi_k < lo_k
            if log_sub_decade:
                # a pattern that lives inside one decade has no decade to label,
                # and asking for the ones inside its range returns none at all
                ax.set_yticks(_nice_ticks(forward, inverse, base, top))
                ax.yaxis.set_minor_locator(NullLocator())
                fmt = ScalarFormatter(useMathText=True)
                fmt.set_useOffset(False)
                ax.yaxis.set_major_formatter(fmt)
            else:
                step = max(1, (hi_k - lo_k) // 5 + 1)
                ax.set_yticks([10.0 ** k for k in range(lo_k, hi_k + 1, step)])
                ax.set_yticks([m * 10.0 ** k for k in range(lo_k - 1, hi_k + 1)
                               for m in range(2, 10)
                               if base <= m * 10.0 ** k <= top], minor=True)
        elif y_scale == "linear":
            ax.set_yticks([t for t in MaxNLocator(nbins=4).tick_values(base, top)
                           if base <= t <= top])
        else:
            ax.set_yticks(_nice_ticks(forward, inverse, base, top))
            # the asinh scale keeps its own minor locator, which puts a mark
            # above the tallest peak where the spine has already stopped
            ax.yaxis.set_minor_locator(NullLocator())
        y_label = "Intensity (arb. units)"
        if y_scale != "log":
            # a shared power of ten, carried in the axis *label*: six-digit
            # counts eat the left margin, and the exponent is the same for every
            # tick.  matplotlib's own offset text says the same thing, but it
            # floats above the axes a whole headroom away from the numbers it
            # multiplies — the reader meets the multiplier where they meet the
            # quantity instead.  An additive offset is refused outright: it
            # moves the origin without saying so, which a multiplier does not.
            k = int(np.floor(np.log10(abs(top)))) if top != 0.0 else 0
            if k >= 4 or k <= -3:
                scale_10 = 10.0 ** k
                ax.yaxis.set_major_formatter(
                    FuncFormatter(lambda v, _p, m=scale_10: f"{v / m:g}"))
                y_label = f"Intensity ($10^{{{k}}}$ arb. units)"
            else:
                fmt = ScalarFormatter(useMathText=True)
                fmt.set_useOffset(False)
                ax.yaxis.set_major_formatter(fmt)
        ax.spines["left"].set_bounds(base, top)
        # the label belongs over the region it labels, not centred on an axis
        # most of which carries no numbers.  ``y=`` moves it there and leaves
        # matplotlib's own horizontal placement alone, which is what keeps it
        # clear of a six-digit tick label.
        u_bottom = float(forward(ax.get_ylim()[0]))
        # ``ha`` is what centres a rotated label *vertically*, so ``y=`` alone
        # moves it over the region it names; ``va`` would push it sideways into
        # the tick numbers, which is exactly the collision this avoids
        ax.set_ylabel(y_label, labelpad=6,
                      y=(0.5 * (float(forward(base)) + u_top) - u_bottom)
                      / (u_head - u_bottom))

        # fit statistics as a corner annotation, above the data ceiling so it
        # can never collide with a peak
        s = result.statistics
        ax.text(x0, float(inverse(u_top + 0.055 * u_span)),
                f"{result.mode}    $R_\\mathrm{{wp}}$ = {s.rwp:.4f}"
                f"    GoF = {s.gof:.2f}", ha="left", va="bottom")

        # one label convention for the whole figure: the right-hand gutter
        x_gut = x1 + 0.012 * (x1 - x0)
        tail = slice(-max(5, x.size // 50), None)
        ends = [(float(y_obs[tail].mean()), "observed", hue["obs"]),
                (float(y_calc[tail].mean()), "calculated", hue["calc"])]
        if has_bkg:
            ends.append((float(y_bkg[tail].mean()), "background", hue["bkg"]))
        ax_h_in = ax.get_position().height * fig_h
        min_gap = 1.15 * font_size * (u_head - u_bottom) / (ax_h_in * 72.0)
        if label_align == "bottom":
            # one block, bottom-aligned with the data it names.  Its lowest
            # member sits half a line inside the axes so nothing is half-clipped.
            # (inline mode is linear-only, so u and intensity are the same
            # number here and ``diff_zero`` needs no transform.)
            anchor = max(u_bottom, float(forward(floor))) + 0.55 * min_gap
            placed = [anchor + (len(ends) - 1 - i) * min_gap
                      for i in range(len(ends))]
            if inline:
                if placed and placed[-1] - diff_zero < min_gap:
                    lift = min_gap - (placed[-1] - diff_zero)
                    placed = [u + lift for u in placed]
                ends.append((diff_zero, "obs $-$ calc", hue["diff"]))
                placed.append(diff_zero)
        else:
            if inline:
                # spread with the curves rather than beside them: a raw residual
                # sits just under the data floor, which is exactly where the
                # background label wants to be on a pattern ending in background
                ends.append((diff_zero, "obs $-$ calc", hue["diff"]))
            placed = _spread([float(forward(e[0])) for e in ends], min_gap)
            # curves that all converge on the data floor spread downward into
            # what is below them, which is either the first tick row — anchored
            # to its marks and unable to move — or the bottom of the axes.  Lift
            # the group clear of whichever it is, keeping the spacing inside it.
            lowest = (float(forward(row_y[0])) + min_gap if (inline and row_y)
                      else u_bottom + 0.55 * min_gap)
            placed = [u + max(0.0, lowest - min(placed)) for u in placed]
        for u_value, (_, text, colour) in zip(placed, ends, strict=True):
            ax.text(x_gut, float(inverse(u_value)), text, color=colour,
                    ha="left", va="center", clip_on=False)
        for i, ((name, _), y) in enumerate(zip(rows, row_y, strict=True)):
            colour = (hue["tick"] if n_rows == 1
                      else hue["phase"][i % len(hue["phase"])])
            row_axes.text(x_gut, y, name, color=colour, ha="left", va="center",
                          clip_on=False)

        if inline:
            ax.set_xlabel(x_label)
        else:
            axd.set_xlim(x0, x1)
            axd.set_ylim(row_floor, r_head)
            axd.set_yticks([t for t in MaxNLocator(nbins=3).tick_values(r_lo, r_hi)
                            if r_lo <= t <= r_hi])
            axd.spines["left"].set_bounds(r_lo, r_hi)
            axd.set_ylabel(r"$\Delta/\sigma$" if weighted else "obs $-$ calc",
                           labelpad=6,
                           y=(0.5 * (r_lo + r_hi) - row_floor)
                           / (r_head - row_floor))
            axd.set_xlabel(x_label)
            if weighted:
                axd.text(x_gut, 0.0, r"$\pm 3\sigma$", color=hue["band"],
                         ha="left", va="center", clip_on=False)
            # separated, not butted: a butted join needs ticks on both sides to
            # earn its ink, and those ticks claim a shared axis the reader can
            # trace — which two different quantities are not
            ax.spines["bottom"].set_visible(False)
            ax.tick_params(axis="x", bottom=False, labelbottom=False)
            axd.tick_params(axis="x", direction="out")

        if path is not None:
            fig.savefig(path)
    return fig


def plot_for_vlm(result: RefinementResult, report=None, *,
                 path: str, n_regions: int = 4, dpi: int = 140):
    """Annotated multi-panel montage rendered for what VLMs *can* read.

    VLM benchmarks (CharXiv, ChartMuseum) show frontier models fail precise
    value extraction from dense single-panel plots, so this montage trades
    density for annotated redundancy: a full-pattern overview, a Δ/σ panel
    (model error in noise units — flat ±3 band means done), and the worst-N
    misfit regions auto-zoomed from the FitReport, each titled with its exact
    numbers so the model reads text, not pixels.  Unmatched observed peaks
    are marked explicitly.

    PNG only, high contrast — JPEG's block artifacts shred one-pixel peak
    outlines and difference curves, which is precisely the evidence a VLM is
    asked to judge.
    """
    if not str(path).lower().endswith(".png"):
        raise ValueError("plot_for_vlm writes PNG only (JPEG artifacts destroy "
                         "thin peak/difference lines); pass a .png path")
    try:
        import matplotlib
        matplotlib.use("Agg", force=False)
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover
        raise ImportError(f"plotting needs matplotlib: pip install '{DIST_NAME}[viz]'") from exc

    if report is None:
        from ..report import build_layer0
        report = build_layer0(result)

    tt = np.asarray(result.two_theta)
    y_obs = np.asarray(result.y_obs)
    y_calc = np.asarray(result.y_calc)
    sigma = result.sig()
    delta = y_obs - y_calc

    regions = sorted(report.regions, key=lambda r: -r.chi2_share)[:n_regions]
    n_cols = max(len(regions), 1)
    fig = plt.figure(figsize=(3.2 * max(n_cols, 3), 8.5), dpi=dpi)
    gs = fig.add_gridspec(3, n_cols, height_ratios=[2.2, 1.0, 1.6], hspace=0.45)

    # -- panel 1: full pattern
    ax = fig.add_subplot(gs[0, :])
    ax.plot(tt, y_obs, ".", ms=1.6, color="#1f5fa8", label="observed")
    ax.plot(tt, y_calc, "-", lw=0.9, color="#c23b22", label="calculated")
    for i, region in enumerate(regions):
        ax.axvspan(region.two_theta_lo, region.two_theta_hi, color="#f2c14e",
                   alpha=0.45, lw=0)
        ax.annotate(f"R{i + 1}", ((region.two_theta_lo + region.two_theta_hi) / 2,
                                  ax.get_ylim()[1] * 0.95),
                    ha="center", fontsize=9, fontweight="bold", color="#8a6d00")
    for u in report.unmatched:
        if u.kind == "unmatched_obs":
            ax.axvline(u.two_theta, color="#7a1fa8", lw=0.8, ls=":", alpha=0.8)
    s = result.statistics
    ax.set_title(f"{result.mode}: Rwp={s.rwp:.4f}, GoF={s.gof:.2f}; "
                 f"shaded = worst regions, dotted = unmatched observed peaks",
                 fontsize=10)
    ax.set_ylabel("intensity")
    ax.legend(loc="upper right", fontsize=8, frameon=False)

    # -- panel 2: Δ/σ across the pattern
    ax = fig.add_subplot(gs[1, :])
    ax.plot(tt, delta / sigma, "-", lw=0.5, color="#333333")
    ax.axhspan(-3, 3, color="#2a9d2a", alpha=0.15, lw=0)
    ax.set_ylabel(r"$\Delta/\sigma$")
    ax.set_xlabel(r"2$\theta$ (deg)")
    ax.set_title(r"model error in noise units (green band = ±3$\sigma$; "
                 "a correct model stays inside)", fontsize=9)

    # -- panels 3..: worst regions zoomed
    for i, region in enumerate(regions):
        axr = fig.add_subplot(gs[2, i])
        pad = 0.1 * (region.two_theta_hi - region.two_theta_lo)
        lo, hi = region.two_theta_lo - pad, region.two_theta_hi + pad
        m = (tt >= lo) & (tt <= hi)
        axr.plot(tt[m], y_obs[m], ".", ms=2.5, color="#1f5fa8")
        axr.plot(tt[m], y_calc[m], "-", lw=1.1, color="#c23b22")
        span = float(y_obs[m].max() - y_obs[m].min()) if np.any(m) else 1.0
        axr.plot(tt[m], delta[m] - 0.15 * span, "-", lw=0.8, color="#4a4a4a")
        axr.set_title(f"R{i + 1}: {region.two_theta_lo:.2f}-"
                      f"{region.two_theta_hi:.2f}°\n"
                      f"local Rwp={region.local_rwp:.3f}, "
                      f"{region.chi2_share:.0%} of χ², "
                      f"max|Δ/σ|={region.max_abs_delta_over_sigma:.0f}",
                      fontsize=8)
        axr.tick_params(labelsize=7)

    fig.savefig(path, format="png")
    return fig


def plot_trajectory(series, paths, *, path: str | None = None,
                    dpi: int = 150, mark_diagnostics: bool = True):
    """Parameter trajectories across a sequential series (WP-0505).

    One stacked panel per requested display path, resolved through
    :meth:`SeriesResult.resolve_trajectory` — a refined parameter's dot-path, or
    a derived ``"qpa.<phase>"`` weight fraction, ``"r_bragg.<phase>"`` or
    ``"r_f.<phase>"`` agreement index — plotted against the series coordinate.
    **Error bars appear only where the kind has an esd to carry**: a refined
    parameter and a weight fraction do, an agreement index does not (its
    ``stderr`` column is ``None`` throughout, and a zero-height bar would read
    as an infinitely precise residual), so those panels draw the curve alone.
    Patterns the reseed guard refitted cold are ringed rather than dropped, and
    a discontinuity the series flagged is marked between its two points — the
    plot shows the same fences the diagnostics carry, so a trajectory is never
    read as smoother than it was measured to be.

    A pattern the escalation ladder could not rescue (``SEQUENTIAL_UNRECOVERED``,
    WP-1051) is crossed out instead of ringed, and that difference is the whole
    point of drawing it: a ringed point is a **good fit** reached from a
    different starting model, while a crossed one is a diverged fit whose value
    is not a measurement at all.  It is still plotted, because a gap in a
    trajectory reads as data that was never collected.
    """
    try:
        import matplotlib
        matplotlib.use("Agg", force=False)
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover
        raise ImportError(f"plotting needs matplotlib: pip install '{DIST_NAME}[viz]'") from exc

    if isinstance(paths, str):
        paths = [paths]
    paths = list(paths)
    if not paths:
        raise ValueError("plot_trajectory needs at least one parameter path")

    jumps = {d.where[0] for d in series.diagnostics
             if d.code == "SEQUENTIAL_DISCONTINUITY" and d.where}
    unstable = {d.where[0] for d in series.diagnostics
                if d.code == "SEQUENTIAL_PATH_DEPENDENT" and d.where}
    reseeded = {e.label for e in series.entries if e.reseeded}
    unrecovered = {e.label for e in series.entries if e.status == "diverged"}

    fig, axes = plt.subplots(len(paths), 1, figsize=(8, 2.4 * len(paths)),
                             dpi=dpi, sharex=True, squeeze=False)
    for ax, name in zip(axes[:, 0], paths, strict=True):
        traj = series.resolve_trajectory(name)
        x, value, sd = traj.arrays()
        ax.errorbar(x, value, yerr=np.where(np.isfinite(sd), sd, 0.0),
                    fmt="o-", ms=4, lw=1.0, capsize=2, color="#1f5fa8")
        if mark_diagnostics:
            for i, label in enumerate(traj.labels):
                if label in reseeded:
                    ax.plot(x[i], value[i], "o", ms=10, mfc="none",
                            mec="#c23b22", mew=1.2)
                if label in unrecovered:
                    ax.plot(x[i], value[i], "x", ms=11, color="#8b1a1a",
                            mew=2.0)
            if name in jumps and len(x) > 1:
                k = int(np.argmax(np.abs(np.diff(value))))
                ax.axvspan(x[k], x[k + 1], color="#c23b22", alpha=0.10, lw=0)
        flag = "  [path-dependent]" if name in unstable else ""
        ax.set_ylabel(name.split(".")[-1] if len(name) > 24 else name, fontsize=8)
        ax.set_title(f"{name}{flag}", fontsize=9, loc="left")
        ax.tick_params(labelsize=8)
    axes[-1, 0].set_xlabel(series.x_label)
    fig.tight_layout()
    if path is not None:
        fig.savefig(path)
    return fig
