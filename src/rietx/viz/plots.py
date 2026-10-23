"""Static obs/calc/difference plotting (matplotlib/Agg).

This renderer produces the standard Rietveld panel: observed points, calculated
line, the difference below them, and per-phase reflection tick rows below
*that*.  The interactive viewer is :mod:`rietx.viz.html`; the
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

from functools import partial

import numpy as np

from .._about import DIST_NAME
from ..schemas.results import RefinementResult
from .theme import PHASE_COLOURS

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
#:
#: ``phase`` is the one entry that is **not** chosen per ground, and not chosen
#: here at all: it is :data:`~rietx.viz.theme.PHASE_COLOURS`, which the GUI and
#: ``rietx watch`` draw a tick row in too (WP-1438).  A role colour answers
#: "what kind of thing is this", so it follows the page it is drawn on; a
#: categorical colour answers "which one of them", so it follows the phase and
#: nothing else.  ``tick`` — the *single*-phase row — stays a role and stays
#: per ground.
#:
#: The last five roles are :func:`plot_trajectory`'s (WP-1970): the measured
#: series, a held or verdict-less point, a pattern refitted cold, one the
#: ladder could not rescue, and an Rwp outlier.  Light's are the GUI's
#: ``--accent``, ``--muted`` and ``--bad`` and two darker hues, and dark's
#: are the same tokens' dark values.  ``unrecovered`` sits nearer the type
#: than ``reseeded`` on both grounds, so the worse verdict carries more ink.
#:
#: The ``index_`` roles, ``absent``, ``unmatched`` and ``candidate`` are
#: :mod:`rietx.viz.indexing`'s (WP-1972).  Light's are the hues those figures
#: have always drawn.  A light hue this table already held (``series``,
#: ``reseeded``, ``band``) keeps that role's dark colour.  Each new one keeps
#: its OKLab hue and gains 0.19 in lightness, the mean lift of those three
#: pairs, so the candidate rows keep the lightness steps that tell them apart.
#: The two greys swap their order of ink, as ``obs`` and ``diff`` do, and
#: ``absent``'s amber reads on both grounds as it is.  ``candidate`` is ranked
#: like ``phase`` but is chosen per ground, because four of its hues are other
#: roles' light colours, and a light colour takes one dark colour wherever it
#: is drawn.
PALETTES = {
    # `ground` is the page the figure sits on.  Dark's is the manual's and the
    # landing page's warm panel, which is what `_ground_rc` paints; light's is
    # matplotlib's own white, and it is declared rather than assumed because
    # `viz/html.py` needs something to put its legend behind (WP-1429).
    "light": {"obs": "#1a1a1a", "calc": "#ff7f0e", "bkg": "#b5793a",
              "diff": "#737373", "zero": "#c9c9c9", "band": "#2a9d2a",
              "tick": "#1a1a1a", "ground": "#ffffff",
              "phase": list(PHASE_COLOURS),
              "series": "#1f5fa8", "held": "#6b6b6b", "reseeded": "#c23b22",
              "unrecovered": "#8b1a1a", "outlier": "#b8860b",
              "index_obs": "#1f5fa8", "index_calc": "#c23b22",
              "index_bkg": "#7a7a7a", "index_diff": "#4a4a4a",
              "absent": "#f2c14e", "unmatched": "#7a1fa8",
              "candidate": ["#1f5fa8", "#c23b22", "#2a9d2a", "#7a1fa8",
                            "#d17b0f", "#0f8c8c", "#a8195f", "#5a5a9d"]},
    "dark": {"obs": "#d2c9bd", "calc": "#ff9d4d", "bkg": "#c99a6a",
             "diff": "#8f8f8f", "zero": "#4a4a4a", "band": "#4fd44f",
             "tick": "#d2c9bd", "fg": "#f1ece5", "rule": "#d2c9bd",
             "ground": "#1d1813",
             "phase": list(PHASE_COLOURS),
             "series": "#7fb2ea", "held": "#9a9a94", "reseeded": "#e8776a",
             "unrecovered": "#ffb0a0", "outlier": "#d9a62e",
             "index_obs": "#7fb2ea", "index_calc": "#e8776a",
             "index_bkg": "#8a8a8a", "index_diff": "#b5b5b5",
             "absent": "#f2c14e", "unmatched": "#b561e8",
             "candidate": ["#7fb2ea", "#e8776a", "#4fd44f", "#b561e8",
                           "#ffbd7c", "#60c8c7", "#eb5d97", "#9193db"]},
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


def _x_values(two_theta, x_axis: str, wavelength: float | None,
              radiation: str | None = None):
    """The abscissa the panel is drawn against, and its axis label.

    Q = 4π sinθ/λ and d = λ/(2 sinθ) are the same measurement in a coordinate
    that does not depend on the wavelength, which is why neither label repeats
    it and why the 2θ label must.  ``radiation`` (``"Cu Kα"``) goes on the 2θ
    label before λ, in one form whichever of the two is known:
    ``2θ (degrees), Cu Kα, λ = 1.54059 Å``.
    """
    tt = np.asarray(two_theta, dtype=float)
    if x_axis == "two_theta":
        label = r"$2\theta$ (degrees)"
        if radiation is not None:
            label += f", {radiation}"
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


def _palette(style: str) -> dict:
    """The palette ``style`` names, or a ``ValueError`` naming the choices."""
    if style not in PALETTES:
        raise ValueError(f"style must be one of {sorted(PALETTES)}, not {style!r}")
    return PALETTES[style]


def _check_panel_args(style: str, x_axis: str, y_scale: str,
                      wavelength: float | None) -> None:
    """The keyword checks every panel shares, raised before anything is drawn."""
    _palette(style)
    if x_axis not in X_AXES:
        raise ValueError(f"x_axis must be one of {list(X_AXES)}, not {x_axis!r}")
    if y_scale not in Y_SCALES:
        raise ValueError(f"y_scale must be one of {list(Y_SCALES)}, not {y_scale!r}")
    if x_axis != "two_theta" and wavelength is None:
        raise ValueError(f"x_axis={x_axis!r} is derived from 2θ through the "
                         "wavelength; pass wavelength=")


def _pyplot():
    """``matplotlib.pyplot``, or an error naming what to install.

    Matplotlib is a dependency since WP-1545; an install made with
    ``--no-deps`` or a distribution's package can still lack it.

    A script, the CLI and the GUI server get the Agg canvas, because a GUI
    backend drawing off the main thread fails on macOS. A Jupyter kernel's
    backend is left alone (WP-1544). Forcing Agg there made every rietx
    figure display as ``<Figure size …>`` text, and the next ``plt.show()``
    in the session warned that Agg "cannot be shown", whichever was imported
    first.
    """
    try:
        import matplotlib
        if not _in_kernel():
            matplotlib.use("Agg", force=False)
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover
        raise ImportError(f"plotting needs matplotlib, a {DIST_NAME} dependency this "
                          "environment lacks: pip install matplotlib") from exc
    return plt


#: What a figure shown in a notebook cell is encoded at (WP-1544): twice a
#: 100-dpi screen, so it is sharp on a HiDPI display and is drawn at its
#: designed size by the width the bundle declares, and a 256-colour palette.
#: Measured on the FAP fit figure: 194 kB as a 300-dpi RGBA PNG, 52 kB this
#: way, with 98.84 % of pixels unchanged and the rest antialiased edges within
#: 31/255. A file written with ``path=`` or ``savefig`` is untouched.
_NOTEBOOK_DPI = 100
_NOTEBOOK_DENSITY = 2
_NOTEBOOK_COLOURS = 256

_FIGURE_CLASS = None


def _figure_class():
    """The ``Figure`` every rietx plot draws on: matplotlib's own, with a
    notebook encoding of its own (:data:`_NOTEBOOK_DPI`).

    IPython builds a figure's output from ``_repr_mimebundle_``
    (:func:`_notebook_bundle`): the PNG, and the light and dark pair as HTML
    beside it, from one encode of the light figure (WP-1970).  It then ranks
    a PNG formatter registered for a type above the bundle's PNG, and the
    inline backend registers one for ``Figure``, which a subclass inherits
    through its MRO.  So a PNG formatter returning ``None`` is registered for
    this subclass alone, in a running IPython, which leaves the bundle's PNG
    standing; the caller's own figures keep the backend's formatter.
    ``_repr_png_`` answers a caller outside IPython. Built on first use,
    because this module imports matplotlib lazily.

    Pickle finds a class by its module and qualified name, so the class is
    named as a module attribute, and the module's ``__getattr__`` builds it
    when an unpickle in a fresh process asks for it (WP-1971).
    """
    global _FIGURE_CLASS
    if _FIGURE_CLASS is None:
        from matplotlib.figure import Figure

        class _NotebookFigure(Figure):
            #: The palette the figure was drawn in, set by the plot that
            #: drew it; ``None`` where the figure has no dark form.
            _rietx_style = None

            def _repr_png_(self):
                return _notebook_png(self)

            def _repr_mimebundle_(self, include=None, exclude=None):
                return _notebook_bundle(self, include, exclude)

        _NotebookFigure.__qualname__ = "_NotebookFigure"
        _FIGURE_CLASS = _NotebookFigure
    _register_notebook_png(_FIGURE_CLASS)
    return _FIGURE_CLASS


def __getattr__(name: str):
    """``_NotebookFigure``, built on first use, for pickle to find."""
    if name == "_NotebookFigure":
        return _figure_class()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _register_notebook_png(cls) -> None:
    """Stop a running IPython's PNG formatter encoding ``cls`` itself, so the
    bundle's PNG stands. Nothing happens outside IPython, or once it is done."""
    import sys
    if "IPython" not in sys.modules:
        return
    from IPython import get_ipython
    shell = get_ipython()
    if shell is None:
        return
    formatter = shell.display_formatter.formatters["image/png"]
    if cls not in formatter.type_printers:
        formatter.for_type(cls, lambda fig: None)


def _notebook_png(fig) -> tuple[bytes, dict]:
    """``fig`` as a notebook shows it: a PNG at :data:`_NOTEBOOK_DENSITY` times
    :data:`_NOTEBOOK_DPI`, palette-quantised without dithering, with its width
    in CSS pixels so the frontend draws it at its designed size.
    ``(data, metadata)``, the pair an IPython formatter may return.

    The width alone (WP-1957): a frontend that narrows an image to its output
    column and keeps a declared height squashes a figure declaring both in any
    column narrower than the figure.  With only a width it scales whole."""
    import io

    from PIL import Image

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=_NOTEBOOK_DPI * _NOTEBOOK_DENSITY,
                bbox_inches="tight", facecolor=fig.get_facecolor())
    image = Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
    palette = image.quantize(colors=_NOTEBOOK_COLOURS,
                             method=Image.Quantize.MEDIANCUT,
                             dither=Image.Dither.NONE)
    out = io.BytesIO()
    palette.save(out, format="PNG", optimize=True)
    return out.getvalue(), {"width": image.size[0] // _NOTEBOOK_DENSITY}


def _notebook_bundle(fig, include=None, exclude=None) -> tuple[dict, dict]:
    """``fig`` as a notebook output: ``(data, metadata)`` by MIME type.

    ``image/png`` is :func:`_notebook_png`, for a frontend that renders no
    HTML, such as a PDF export.  A figure drawn light also carries
    ``text/html`` (WP-1970): a light and a dark image, of which the
    frontend's theme shows one (:mod:`rietx.viz._notebook`).  Every frontend
    measured ranks HTML first.

    The dark image is :func:`_darkened` on a copy, so whatever the caller
    added to the returned figure shows in both.  The light one is encoded
    first: its draw creates the tick artists the copy then recolours."""
    from ._notebook import no_dark_copy, pair_html, wants_html

    light, meta = _notebook_png(fig)
    data, metadata = {"image/png": light}, {"image/png": meta}
    if fig._rietx_style != "light" or not wants_html(include, exclude):
        return data, metadata
    import copy

    # A figure pyplot still holds (any backend but the inline one) would
    # register its copy with pyplot too, through Figure.__setstate__: one
    # stray figure, or window, per display.  Detached, the copy is not.
    manager = fig.canvas.manager
    fig.canvas.manager = None
    try:
        twin = copy.deepcopy(fig)
    except Exception as exc:  # noqa: BLE001 - the light figure still shows
        no_dark_copy(exc)
        return data, metadata
    finally:
        fig.canvas.manager = manager
    try:
        dark, _ = _notebook_png(_darkened(twin))
    except Exception as exc:  # noqa: BLE001 - the light figure still shows
        no_dark_copy(exc)
        return data, metadata
    data["text/html"] = pair_html(light, dark, meta["width"])
    return data, metadata


def _darkened(fig):
    """``fig``, drawn light, recoloured in place to the dark palette.

    Three maps, which are what :func:`_style_context` changes between the two
    palettes.  A :data:`PALETTES` role takes the same role's dark colour, and
    a ranked list's entry the same entry's.  Matplotlib's own black takes
    ``fg`` on text and ``rule`` on every other line, as :func:`_ground_rc`
    sets them.  White takes ``ground``.  So a rietx
    figure comes out as the one drawn with ``style="dark"``, pixel for pixel,
    and a caller's own ink in any other colour is left as drawn.  The
    redraw it replaces would have dropped what the caller added (WP-1970).
    """
    from matplotlib.collections import Collection
    from matplotlib.colors import to_hex, to_rgba
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    from matplotlib.text import Text

    light, dark = PALETTES["light"], PALETTES["dark"]
    roles = {}
    for k, v in light.items():
        if k != "ground":
            pairs = zip(v, dark[k], strict=True) if isinstance(v, list) else [(v, dark[k])]
            roles.update((one.lower(), two) for one, two in pairs)
    ground, fg, rule = {"#ffffff": dark["ground"]}, {"#000000": dark["fg"]}, {
        "#000000": dark["rule"]}

    def ink(colour, *maps):
        if isinstance(colour, str) and colour.lower() in ("none", "auto"):
            return colour
        rgba = to_rgba(colour)
        key = to_hex(rgba[:3])
        for table in maps:
            if key in table and rgba[3] > 0:
                return to_rgba(table[key], rgba[3])
        return colour

    def patch(p):
        p.set_facecolor(ink(p.get_facecolor(), roles, ground, rule))
        p.set_edgecolor(ink(p.get_edgecolor(), roles, rule))

    for artist in fig.findobj():
        if isinstance(artist, Text):
            artist.set_color(ink(artist.get_color(), roles, fg))
            for box in (artist.get_bbox_patch(), getattr(artist, "arrow_patch", None)):
                if box is not None:
                    patch(box)
        elif isinstance(artist, Line2D):
            artist.set_color(ink(artist.get_color(), roles, rule))
            artist.set_markerfacecolor(ink(artist.get_markerfacecolor(), roles, rule))
            artist.set_markeredgecolor(ink(artist.get_markeredgecolor(), roles, rule))
        elif isinstance(artist, Patch):
            patch(artist)
        elif isinstance(artist, Collection):
            for get, put, maps in ((artist.get_facecolor, artist.set_facecolor,
                                    (roles, ground, rule)),
                                   (artist.get_edgecolor, artist.set_edgecolor,
                                    (roles, rule))):
                old = get()
                new = [ink(c, *maps) for c in old]
                if any(to_rgba(a) != to_rgba(b) for a, b in zip(old, new, strict=True)):
                    put(new)
    return fig


def _handed_back(fig, style: str | None = None):
    """``fig``, detached from pyplot when the backend is a notebook's inline one.

    The inline backend draws every figure pyplot holds when a cell ends, and
    Jupyter draws a returned figure as the cell's value, so a bare
    ``result.plot()`` showed twice; after it, figures stopped flushing and
    surfaced in a later cell's ``plt.show()`` (measured, WP-1544). Detached,
    the returned figure is the cell's one output, and a trailing ``;`` hides it
    as IPython means it to. Everywhere else pyplot keeps the figure, so a
    script's own ``plt.show()`` still finds it.
    """
    import matplotlib
    import matplotlib.pyplot as plt
    if "inline" in matplotlib.get_backend():
        plt.close(fig)
    # the palette it was drawn in, which says whether a notebook may show a
    # dark copy beside it (WP-1970); None, as for plot_for_vlm, says not
    fig._rietx_style = style
    return fig


def _in_kernel() -> bool:
    """Whether this process is a Jupyter kernel, whose backend (inline, or
    whatever ``%matplotlib`` chose) is the notebook's to keep.  Only there:
    a script whose matplotlibrc names a GUI backend still gets Agg, because
    ``summary(plot=)`` and the GUI server draw off the main thread."""
    import sys
    return "ipykernel" in sys.modules


def _style_context(plt, style: str, font_size: float):
    """The panel's style context: the house rc, and on dark the page's ground."""
    hue = PALETTES[style]
    return plt.style.context([_rc(font_size)] if style == "light"
                             else ["dark_background", _rc(font_size), _ground_rc(hue)])


def _ground_context(plt, style: str):
    """The trajectory's and the indexing figures' style context: the page's
    ground on dark, and on light nothing, since those figures predate the house
    rc and keep their own type."""
    if style == "light":
        from contextlib import nullcontext
        return nullcontext()
    return plt.style.context(["dark_background", _ground_rc(PALETTES[style])])


def _title(ax, title: str | None, font_size: float) -> None:
    """A caller's title, in the panel's own type, or nothing at all.

    Absent by default: the caption is a paper figure's title, and a panel bound
    for a report should not arrive carrying a second one (the module rule).  A
    notebook cell or a batch of thirty patterns has no caption, so ``title=``
    names the figure there — at the body size, since one size for the whole
    figure is the rule a larger title would be the first exception to.
    """
    if title is not None:
        ax.set_title(title, fontsize=font_size, pad=0.6 * font_size)


#: Where a gutter label starts, as a fraction of the axes width.
_GUTTER_X = 1.012
#: How far beside the axes :func:`_height_clip` reaches, in axes widths: far
#: enough that a spine's own width is never cut.
_CLIP_REACH = 100.0
#: How far above and below the axes :func:`_height_clip` reaches, in axes
#: heights, so a spine ending on the axes edge keeps its last row of pixels;
#: at 0 three of the six pinned renders change.  It is also how far a spine
#: can reach past the axes after a caller's ``set_ylim``: 15 px of 871.
_CLIP_MARGIN = 0.02


def _height_clip(artist, ax) -> None:
    """Clip ``artist``, placed in data height beyond the axes, to their height.

    A bounded spine is drawn on the axes edge, where matplotlib clips
    nothing.  After a caller's ``set_ylim`` it can reach far above or below
    the view, and a tight save then grows the canvas to reach it: 871 px tall
    became 13 369 px (WP-1971).  A tight save measures a clipped artist by its
    visible part, so this keeps the figure its designed size.
    """
    from matplotlib.transforms import Bbox, TransformedBbox

    artist.set_clip_box(TransformedBbox(
        Bbox([[-_CLIP_REACH, -_CLIP_MARGIN], [_CLIP_REACH, 1.0 + _CLIP_MARGIN]]),
        ax.transAxes))
    artist.set_clip_on(True)


def _gutter_label(ax, y: float, text: str, colour) -> None:
    """``text`` in the right-hand gutter of ``ax``, level with data height ``y``.

    The x position is a fraction of the axes width, so the label stays beside
    the axes under a caller's ``set_xlim``.  In data coordinates a zoom to a
    tenth of the range put it nine axes widths away, and the notebook image
    grew to reach it (WP-1971).  It is an annotation anchored at height ``y``
    inside the axes, so a caller's ``set_ylim`` that leaves ``y`` outside the
    view hides the whole label, which a tight save then does not measure.  A
    clip box would slice a label straddling its edge instead.
    """
    gutter = ax.get_yaxis_transform()
    ax.annotate(text, xy=(0.5, y), xycoords=gutter, xytext=(_GUTTER_X, y),
                textcoords=gutter, annotation_clip=True, color=colour,
                ha="left", va="center")


def _tick_over(value: float, _pos, scale: float) -> str:
    """A tick number divided by the power of ten its axis label carries.
    Module-level, so the figure holding it pickles (WP-1971)."""
    return f"{value / scale:g}"


def _intensity_axis(ax, y_scale: str, forward, inverse, base: float, top: float,
                    u_top: float, u_head: float) -> float:
    """Ticks, formatter, spine and label of the intensity axis; the drawn floor.

    One function for every figure that draws an intensity, so a pattern read
    from a file and the fit of it carry the same axis.  It runs *after*
    ``set_ylim``, because the label is placed over the region it names as a
    fraction of the drawn range, and it returns that range's floor in display
    space for the gutter arithmetic that follows it.
    """
    from matplotlib.ticker import (
        FuncFormatter,
        MaxNLocator,
        NullLocator,
        ScalarFormatter,
    )

    # y ticks and the left spine cover only the intensity being read; the
    # spine spans the data rather than stopping at the last tick, so no
    # peak escapes above the end of the axis
    if y_scale == "log":
        # the decades inside the measured range, and no others: matplotlib's
        # locator happily puts a labelled tick a whole decade above the
        # tallest peak, where the spine has already stopped
        lo_k = int(np.ceil(np.log10(base)))
        hi_k = int(np.floor(np.log10(top)))
        if hi_k < lo_k:
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
            ax.yaxis.set_major_formatter(
                FuncFormatter(partial(_tick_over, scale=10.0 ** k)))
            y_label = f"Intensity ($10^{{{k}}}$ arb. units)"
        else:
            fmt = ScalarFormatter(useMathText=True)
            fmt.set_useOffset(False)
            ax.yaxis.set_major_formatter(fmt)
    ax.spines["left"].set_bounds(base, top)
    _height_clip(ax.spines["left"], ax)
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

    return u_bottom


def plot_result(result: RefinementResult, *, path: str | None = None,
                two_theta_range: tuple[float, float] | None = None,
                show_background: bool = True, weighted: bool = False,
                style: str = "light", wavelength: float | None = None,
                x_axis: str = "two_theta", y_scale: str = "linear",
                label_align: str = "bottom",
                figsize: tuple[float, float] | None = None,
                font_size: float = BASE, dpi: int = 300,
                title: str | None = None):
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

    ``title`` names the figure above the data panel, in the panel's own type.
    It is off by default and the default figure is unchanged by it: a panel for
    a report takes its title from the caption, and the fit statistics stay a
    corner annotation either way.
    """
    _check_panel_args(style, x_axis, y_scale, wavelength)
    if label_align not in ("bottom", "curve"):
        raise ValueError("label_align must be 'bottom' or 'curve', not "
                         f"{label_align!r}")
    plt = _pyplot()
    from matplotlib.ticker import MaxNLocator

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

    with _style_context(plt, style, font_size):
        line_in = 1.35 * font_size / 72.0
        if figsize is None:
            figsize = (7.6, 4.4) if inline else (7.6, 5.6)
        left, right, top_m, bottom_m = 0.13, 0.805, 0.965, 0.125
        if inline:
            fig, ax = plt.subplots(figsize=figsize, dpi=dpi, FigureClass=_figure_class())
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
                2, 1, figsize=figsize, dpi=dpi, FigureClass=_figure_class(), sharex=True,
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

        u_bottom = _intensity_axis(ax, y_scale, forward, inverse, base, top,
                                   u_top, u_head)

        # fit statistics as a corner annotation, above the data ceiling so it
        # can never collide with a peak; in axes coordinates, as the y label
        # is, so a caller's zoom keeps it in the corner
        s = result.statistics
        ax.text(0.0, (u_top + 0.055 * u_span - u_bottom) / (u_head - u_bottom),
                f"{result.mode}    $R_\\mathrm{{wp}}$ = {s.rwp:.4f}"
                f"    GoF = {s.gof:.2f}", ha="left", va="bottom",
                transform=ax.transAxes)

        # one label convention for the whole figure: the right-hand gutter
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
            _gutter_label(ax, float(inverse(u_value)), text, colour)
        for i, ((name, _), y) in enumerate(zip(rows, row_y, strict=True)):
            colour = (hue["tick"] if n_rows == 1
                      else hue["phase"][i % len(hue["phase"])])
            _gutter_label(row_axes, y, name, colour)

        if inline:
            ax.set_xlabel(x_label)
        else:
            axd.set_xlim(x0, x1)
            axd.set_ylim(row_floor, r_head)
            axd.set_yticks([t for t in MaxNLocator(nbins=3).tick_values(r_lo, r_hi)
                            if r_lo <= t <= r_hi])
            axd.spines["left"].set_bounds(r_lo, r_hi)
            _height_clip(axd.spines["left"], axd)
            axd.set_ylabel(r"$\Delta/\sigma$" if weighted else "obs $-$ calc",
                           labelpad=6,
                           y=(0.5 * (r_lo + r_hi) - row_floor)
                           / (r_head - row_floor))
            axd.set_xlabel(x_label)
            if weighted:
                _gutter_label(axd, 0.0, r"$\pm 3\sigma$", hue["band"])
            # separated, not butted: a butted join needs ticks on both sides to
            # earn its ink, and those ticks claim a shared axis the reader can
            # trace — which two different quantities are not
            ax.spines["bottom"].set_visible(False)
            ax.tick_params(axis="x", bottom=False, labelbottom=False)
            axd.tick_params(axis="x", direction="out")
        _title(ax, title, font_size)

        if path is not None:
            fig.savefig(path)
    return _handed_back(fig, style)


def _starting_model(ref, data):
    """What ``ref`` draws over ``data`` at its parameters as they stand, from
    one compile: each phase's reflection positions keyed by phase name, and
    the background with the 2θ of the channels it was evaluated on.

    Compiled as :meth:`Refinement.predict` compiles, so the background is
    :meth:`CompiledModel.background` over the channels a fit would use: the
    curve a fit over the pattern's whole range starts from.  A fit given
    ``two_theta_limits`` maps its Chebyshev terms onto that narrower range
    instead, so its starting curve differs.  The ticks are placed by
    :func:`~rietx.viz.snapshot.stage_ticks`.  Neither depends on the windows,
    so this compiles the declared stages' narrow ones rather than
    ``compile_model``'s closing default."""
    from ..model.forward import WINDOW_AREA_TOL, compile_model
    from ..params.vector import ParameterTable
    from .snapshot import stage_ticks
    table = ParameterTable(ref.structure, ref.instrument)
    compiled = compile_model(ref.structure, ref.instrument, data, mode="rietveld",
                             moving_paths=set(table.moving_paths),
                             window_area_tol=WINDOW_AREA_TOL)
    values = table.decode(table.x0())
    rows = stage_ticks(compiled, values, max_per_phase=10**9)
    names = [p.name for p in ref.structure.phases]
    ticks = {names[int(key.split()[-1])]: row["two_theta"]
             for key, row in rows.items()}
    return (ticks, np.asarray(compiled.tt, dtype=float),
            np.asarray(compiled.background(values), dtype=float))


def _stated_radiation(model, data) -> tuple[float | None, str | None]:
    """The primary λ and the anode a pattern's figure can name, read and never
    inferred: from ``model``'s source when there is a model, else from what the
    file stated (``data.metadata``), else nothing.

    A source carries no anode name, so an X-ray source is named only where its
    lines are one entry of the radiation table to the last digit, which is
    what a preset such as ``bragg_brentano(radiation="CuKa")`` builds.  A
    wavelength near a Kα1 names nothing, because a synchrotron beam can sit
    within any tolerance of one, and a neutron source is never named.  A
    file's own ``anode`` is named when it is an element the table carries, as
    Kα1 where the file records a Kα2 wavelength of zero (the doublet was not
    used) and as Kα otherwise.
    """
    from ..schemas.instrument import _KA_DOUBLETS, _RADIATIONS

    def spelt(key: str) -> str:            # "CuKa1" -> "Cu Kα1"
        element, line = key.split("Ka")
        return f"{element} Kα{line}"

    if model is not None:
        source = model.instrument.source
        lines = tuple(line.wavelength.value for line in getattr(source, "lines", ()))
        name = next((key for key, table in _RADIATIONS.items()
                     if source.kind == "xray_cw" and lines == table), None)
        return (getattr(source, "primary_wavelength", None),
                spelt(name) if name is not None else None)

    def stated(key: str) -> float | None:
        try:
            return float(data.metadata[key])
        except (KeyError, TypeError, ValueError):
            return None

    lam = stated("wavelength")
    element = str(data.metadata.get("anode", "")).strip().capitalize()
    name = None
    if f"{element}Ka" in _KA_DOUBLETS:
        name = spelt(f"{element}Ka1" if stated("wavelength_alpha2") == 0.0
                     else f"{element}Ka")
    return (lam if lam is not None and np.isfinite(lam) and lam > 0.0 else None,
            name)


def plot_pattern(data, *, path: str | None = None,
                 two_theta_range: tuple[float, float] | None = None,
                 x_axis: str = "two_theta", wavelength: float | None = None,
                 y_scale: str = "linear", style: str = "light",
                 figsize: tuple[float, float] | None = None,
                 font_size: float = BASE, dpi: int = 300,
                 title: str | None = None, model=None):
    """A measured pattern on its own, before any model exists.

    The data panel of :func:`plot_result` with nothing modelled in it: the same
    margins, gutter, intensity axis and keywords, built from the same helpers,
    so the pattern read from a file and the fit of it are one style and the
    peaks sit at the same height in both.  ``data`` is a
    :class:`~rietx.schemas.pattern.PatternData`; :meth:`PatternData.plot` is
    the peer of :meth:`RefinementResult.plot` and forwards here (WP-1444).

    The observed channels are markers, as in the result panel, because they are
    discrete counts.  σ is **not** drawn even when the file carried it: a √y
    band on a log axis is a different figure.  ``data.excluded_regions`` are
    shaded as bands over the channels they hold back, and those channels are
    still drawn — a result drops them, leaving a gap where the fit saw nothing,
    but here they are a measurement the next fit will not use, and hiding them
    would say they were never collected.

    ``two_theta_range``, ``x_axis``/``wavelength``, ``y_scale``, ``style``,
    ``figsize``/``font_size``/``dpi`` and ``title`` mean exactly what they
    mean on :func:`plot_result`; the default size is the result panel's own,
    so a before-and-after pair lines up.

    A notebook output has no caption, so the 2θ label names the radiation
    whenever something states it (WP-2037): ``2θ (degrees), Cu Kα, λ =
    1.54059 Å``.  A :class:`PatternData` carries no wavelength of its own, so
    the label reads ``model``'s source, else the anode and wavelength the file
    recorded in ``data.metadata``, else stays ``2θ (degrees)``.  The anode is
    named only where a preset built the source's lines from the radiation
    table or the file names one, never from a wavelength's nearness
    (:func:`_stated_radiation`), so a neutron or synchrotron source shows λ
    alone.  An explicit ``wavelength=`` replaces both.  Q and d still need
    ``wavelength=``, because the stated λ names the axis and converts nothing.

    ``model``, a :class:`~rietx.Refinement`, draws what it already holds over
    the data, at the parameters as they stand and before any fit (WP-1544,
    WP-2037), so each part can be checked against the data before a fit uses
    it.  One row of reflection ticks per phase goes under the data, where the
    result panel puts them: the check that the cell is close and λ is right
    before a fit is asked to find either.  The positions are
    :func:`rietx.viz.snapshot.stage_ticks`', every emission line included.  The
    background is drawn as the result panel draws it, dashed in the
    background colour with its name in the gutter, over the channels a fit
    would use: the check that it runs through the counts between the peaks.  A
    background that is zero everywhere, the default instrument's, is not
    drawn.  The intensity axis reaches the background where it leaves the
    data's range, so a starting value far off is in the picture.  A row sits
    below the data floor, so ``model=`` needs the linear axis.

    2θ only: every axis this draws (2θ, Q, d) is reached through an angle, and
    a time-of-flight pattern is refused by name rather than drawn as degrees.
    """
    from ..schemas.pattern import require_two_theta

    require_two_theta(data, "plot_pattern()")
    _check_panel_args(style, x_axis, y_scale, wavelength)
    if model is not None and y_scale != "linear":
        raise ValueError("model= draws its tick rows below the data floor, "
                         "which only a linear intensity axis has room for")
    plt = _pyplot()
    from matplotlib.ticker import MaxNLocator

    tt = np.asarray(data.two_theta, dtype=float)
    y_obs = np.asarray(data.intensity, dtype=float)
    if two_theta_range is not None:
        keep = (tt >= two_theta_range[0]) & (tt <= two_theta_range[1])
        if not keep.any():
            raise ValueError(f"two_theta_range {two_theta_range} contains no points")
        tt, y_obs = tt[keep], y_obs[keep]
    hue = PALETTES[style]

    lam, radiation = ((wavelength, None) if wavelength is not None
                      else _stated_radiation(model, data))
    x, x_label = _x_values(tt, x_axis, lam, radiation)
    if x.size > 1 and x[0] > x[-1]:
        # mirrored rather than reversed, as the result panel does it
        x, y_obs = x[::-1], y_obs[::-1]
    ticks, bkg_tt, y_bkg = (_starting_model(model, data) if model is not None
                            else ({}, np.empty(0), np.empty(0)))
    rows = [(name, _x_values(np.asarray(pos, dtype=float), x_axis, wavelength)[0])
            for name, pos in ticks.items()]
    n_rows = len(rows)
    inside = (bkg_tt >= tt.min()) & (bkg_tt <= tt.max())
    bkg_tt, y_bkg = bkg_tt[inside], y_bkg[inside]
    # zero everywhere is the default instrument's background: nothing to check
    has_bkg = bool(y_bkg.size and np.any(y_bkg))

    with _style_context(plt, style, font_size):
        if figsize is None:
            figsize = (7.6, 4.4)
        fig, ax = plt.subplots(figsize=figsize, dpi=dpi, FigureClass=_figure_class())
        fig.subplots_adjust(left=0.13, right=0.805, top=0.965, bottom=0.125)

        x0, x1 = float(x.min()), float(x.max())
        t0, t1 = float(tt.min()), float(tt.max())
        for lo, hi in data.excluded_regions:
            # a region is in 2θ like the window, and is clipped to the drawn
            # 2θ span *before* it is converted: a beamstop region from 2θ = 0
            # has no d or Q edge, and only its drawn part is shaded.  Its edges
            # then follow x_axis, and on a d axis they arrive in the other order
            lo, hi = max(float(lo), t0), min(float(hi), t1)
            if hi <= lo:
                continue
            ends = _x_values(np.array([lo, hi], dtype=float), x_axis, wavelength)[0]
            a, b = sorted(float(e) for e in ends)
            ax.axvspan(a, b, color=hue["zero"], alpha=0.5, lw=0, zorder=0)
        ax.plot(x, y_obs, marker="x", ms=0.24 * font_size, mew=0.6,
                color=hue["obs"], ls="none", zorder=2)
        if has_bkg:
            # modelled, so dashed, in the result panel's background ink.  Over
            # the markers, where the result panel draws its calculated curve:
            # it is the model being checked, and under a full range's markers
            # (5753 on FAP.XRA) it was hidden wherever it ran through the counts
            ax.plot(_x_values(bkg_tt, x_axis, wavelength)[0], y_bkg, "--",
                    lw=0.8, color=hue["bkg"], zorder=3)

        top = float(y_obs.max())
        if y_scale == "log":
            if top <= 0.0:
                raise ValueError("y_scale='log' needs at least one positive "
                                 "intensity channel")
            floor = float(y_obs[y_obs > 0.0].min())
        else:
            floor = min(float(y_obs.min()), 0.0)
        if has_bkg:
            # model= is linear-only, so a background below zero is drawable
            top = max(top, float(y_bkg.max()))
            floor = min(floor, float(y_bkg.min()))
        forward, inverse, setter, floor = _y_scale(y_scale, floor, top)
        if setter is not None:
            ax.set_yscale(setter[0], **setter[1])
        u_top, u_floor = float(forward(top)), float(forward(floor))
        u_span = (u_top - u_floor) or 1.0
        # the result panel's headroom, kept though nothing is annotated in it:
        # the same data then reaches the same height in both figures
        u_head = u_top + 0.20 * u_span
        base = floor if y_scale == "log" else min(floor, 0.0)

        row_y, row_floor = [], floor
        if n_rows:
            # the result panel's inline rows, with no residual between them and
            # the data: the first row sits a small gap under the floor
            head = float(inverse(u_head))
            span = top - floor or 1.0
            line_frac = (1.35 * font_size / 72.0) / (ax.get_position().height
                                                     * fig.get_size_inches()[1])
            denom = 1.0 - line_frac * (n_rows + 0.6)
            rows_top = floor - 0.03 * span
            row_gap = (line_frac * (head - rows_top) / denom if denom > 0.35
                       else 0.10 * span)
            row_y = [rows_top - (i + 1) * row_gap for i in range(n_rows)]
            row_floor = row_y[-1] - 0.6 * row_gap
            marker = _hkl_marker()
            for i, ((_, positions), y) in enumerate(zip(rows, row_y, strict=True)):
                pos = positions[(positions >= x0) & (positions <= x1)]
                colour = (hue["tick"] if n_rows == 1
                          else hue["phase"][i % len(hue["phase"])])
                ax.plot(pos, np.full(pos.size, y), ls="none", marker=marker,
                        ms=1.1 * font_size, mfc=colour, mec=colour, mew=0)

        ax.set_xlim(x0, x1)
        ax.set_ylim(row_floor, float(inverse(u_head)))
        ax.xaxis.set_major_locator(MaxNLocator(nbins=6))
        u_bottom = _intensity_axis(ax, y_scale, forward, inverse, base, top,
                                   u_top, u_head)
        ax.set_xlabel(x_label)

        # the gutter convention: the curve names as one block at the foot of
        # the data, as the result panel's default block, background lowest
        fig_h = fig.get_size_inches()[1]
        ax_h_in = ax.get_position().height * fig_h
        min_gap = 1.15 * font_size * (u_head - u_bottom) / (ax_h_in * 72.0)
        anchor = max(u_bottom, float(forward(floor))) + 0.55 * min_gap
        names = [("observed", hue["obs"])]
        if has_bkg:
            names.append(("background", hue["bkg"]))
        for i, (text, colour) in enumerate(names):
            _gutter_label(ax, float(inverse(anchor + (len(names) - 1 - i) * min_gap)),
                          text, colour)
        for i, ((name, _), y) in enumerate(zip(rows, row_y, strict=True)):
            colour = (hue["tick"] if n_rows == 1
                      else hue["phase"][i % len(hue["phase"])])
            _gutter_label(ax, y, name, colour)
        _title(ax, title, font_size)

        if path is not None:
            fig.savefig(path)
    return _handed_back(fig, style)


def plot_for_vlm(result: RefinementResult, report=None, *,
                 path: str, n_regions: int = 4, dpi: int = 140):
    """Annotated multi-panel montage drawn for a vision-language model to read.

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

    There is no ``title=`` here, and a call passing one is refused by name
    (WP-1444).  Every panel title in the montage is already evidence the model
    reads as text — the overview's carries Rwp, GoF and the legend of the
    shading — so a caller's words prefixed to it would push those numbers
    further from the start of the line or across a wrap, the one place this
    figure cannot afford to lose them.  A batch keys its montages by ``path``.
    """
    if not str(path).lower().endswith(".png"):
        raise ValueError("plot_for_vlm writes PNG only (JPEG artifacts destroy "
                         "thin peak/difference lines); pass a .png path")
    plt = _pyplot()

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
    fig = plt.figure(figsize=(3.2 * max(n_cols, 3), 8.5), dpi=dpi, FigureClass=_figure_class())
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
    return _handed_back(fig)


def plot_trajectory(series, paths, *, path: str | None = None,
                    dpi: int = 150, mark_diagnostics: bool = True,
                    title: str | None = None, style: str = "light"):
    """Parameter trajectories across a sequential series (WP-0505).

    One stacked panel per requested display path, resolved through
    :meth:`SeriesResult.resolve_trajectory` — a refined parameter's dot-path, or
    a derived ``"qpa.<phase>"`` weight fraction, ``"r_bragg.<phase>"`` or
    ``"r_f.<phase>"`` agreement index, or ``"magnetic.<site>"`` (WP-1329: |m|
    against the axis, the unsupported patterns drawn **hollow and without a
    bar**, a pattern with no verdict as a cross, and the onset bracket shaded, so a held moment cannot be read off
    the figure as a small measured one) — plotted against the series
    coordinate.
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
    trajectory reads as data that was never collected.  A point every rung
    left above the Rwp fence (``SEQUENTIAL_RWP_OUTLIER``, WP-1469) is boxed:
    a fit unlike its neighbours', whose values need that pattern's own fit
    opened before they are read.

    ``title`` names the whole figure above its stacked panels, whose own
    left-hand titles stay the parameter each one draws; absent by default,
    and the default figure is unchanged by it.

    ``style="dark"`` draws on the dark page's ground in the dark palette's
    trajectory roles (WP-1970), as :func:`plot_result`'s does.
    """
    hue = _palette(style)
    plt = _pyplot()

    if isinstance(paths, str):
        paths = [paths]
    paths = list(paths)
    if not paths:
        raise ValueError("plot_trajectory needs at least one parameter path")

    jumps = {d.where[0] for d in series.diagnostics
             if d.code == "SEQUENTIAL_DISCONTINUITY" and d.where}
    # the pair each flag names, read off its record (WP-1469) — re-deriving it
    # here as the largest step shaded a different step whenever the scan had
    # left a pattern out, or the largest step failed the σ leg
    flagged = {s.path: s.labels for s in (series.discontinuities or [])}
    unstable = {d.where[0] for d in series.diagnostics
                if d.code == "SEQUENTIAL_PATH_DEPENDENT" and d.where}
    reseeded = {e.label for e in series.entries if e.reseeded}
    unrecovered = {e.label for e in series.entries if e.status == "diverged"}
    outliers = {e.label for e in series.entries if e.above_fence}

    with _ground_context(plt, style):
        fig, axes = plt.subplots(len(paths), 1, figsize=(8, 2.4 * len(paths)),
                                 dpi=dpi, FigureClass=_figure_class(), sharex=True, squeeze=False)
        for ax, name in zip(axes[:, 0], paths, strict=True):
            traj = series.resolve_trajectory(name)
            x, value, sd = traj.arrays()
            yerr = np.where(np.isfinite(sd), sd, 0.0)
            # A magnetic trajectory carries a per-point verdict, and the whole
            # point of WP-1329 is that a held point must not look like a small
            # measured moment: it is drawn hollow, with no bar (``stderr`` is
            # already ``None`` there, so ``arrays()`` handed us NaN), and the onset
            # bracket is shaded between the two patterns that straddle it.  The
            # line runs through every point, while the filled marker is drawn only
            # where the verdict is "supported" — otherwise the hollow square sits
            # over a filled measurement mark.  Guarded on the attribute rather than
            # on the type so an ordinary Trajectory takes exactly the path it took
            # before.
            supported = getattr(traj, "supported", None)
            if supported:
                ax.plot(x, value, "-", lw=1.0, color=hue["series"])
                ax.errorbar(x, np.where(supported, value, np.nan), yerr=yerr,
                            fmt="o", ms=4, capsize=2, color=hue["series"])
            else:
                ax.errorbar(x, value, yerr=yerr,
                            fmt="o-", ms=4, lw=1.0, capsize=2, color=hue["series"])
            if supported:
                measured = getattr(traj, "measured", None) or [True] * len(supported)
                held_ix = [i for i, ok in enumerate(supported)
                           if not ok and measured[i]]
                blind_ix = [i for i, m in enumerate(measured) if not m]
                if held_ix:
                    ax.plot(x[held_ix], value[held_ix], "s", ms=7, mfc="none",
                            mec=hue["held"], mew=1.2, ls="none",
                            label="held (unsupported)")
                # no verdict at all (no esd, or a diverged fit): not the data
                # saying "no moment", so it gets its own mark
                if blind_ix:
                    ax.plot(x[blind_ix], value[blind_ix], "x", ms=7,
                            color=hue["held"], mew=1.2, ls="none",
                            label="no verdict")
                if held_ix or blind_ix:
                    ax.legend(fontsize=7, loc="best", frameon=False)
                onset = getattr(traj, "onset", None)
                if onset is not None and onset.x is not None:
                    ax.axvspan(onset.bracket[0], onset.bracket[1],
                               color=hue["series"], alpha=0.10, lw=0)
            if mark_diagnostics:
                for i, label in enumerate(traj.labels):
                    if label in reseeded:
                        ax.plot(x[i], value[i], "o", ms=10, mfc="none",
                                mec=hue["reseeded"], mew=1.2)
                    if label in unrecovered:
                        ax.plot(x[i], value[i], "x", ms=11, color=hue["unrecovered"],
                                mew=2.0)
                    if label in outliers:
                        ax.plot(x[i], value[i], "s", ms=11, mfc="none",
                                mec=hue["outlier"], mew=1.4)
                if name in flagged:
                    first, last = flagged[name]
                    if first in traj.labels and last in traj.labels:
                        ax.axvspan(x[traj.labels.index(first)],
                                   x[traj.labels.index(last)],
                                   color=hue["reseeded"], alpha=0.10, lw=0)
                elif name in jumps and len(x) > 1 and series.discontinuities is None:
                    # a document written before the record: what older versions drew
                    k = int(np.argmax(np.abs(np.diff(value))))
                    ax.axvspan(x[k], x[k + 1], color=hue["reseeded"], alpha=0.10, lw=0)
            flag = "  [path-dependent]" if name in unstable else ""
            ax.set_ylabel(name.split(".")[-1] if len(name) > 24 else name, fontsize=8)
            ax.set_title(f"{name}{flag}", fontsize=9, loc="left")
            ax.tick_params(labelsize=8)
        axes[-1, 0].set_xlabel(series.x_label)
        if title is not None:
            fig.suptitle(title, fontsize=10)
        fig.tight_layout()
        if path is not None:
            fig.savefig(path)
    return _handed_back(fig, style)
