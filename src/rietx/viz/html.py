"""The self-contained interactive page: one fit, drawn by the chart module.

``write_html(result, path)`` writes the Rietveld figure every browser page of
rietx draws (WP-1461): the observed points over the model, a band of reflection
ticks, and the residual under both, with the same gestures. A drag zooms, the
wheel zooms about the pointer, shift-wheel and alt-drag pan, a double-click
resets, and the legend hides a curve.

Everything is inlined: uPlot and svgcanvas with their licences, the chart
module (``static/rxplot.mjs``), this page's own script and stylesheet
(``figure/``) and the fit's curves. So the file opens from a disk or an email with no
network, no server and no optional dependency. It used to embed plotly.js,
4.8 MB of every file (§ Staying on plotly in the WP).

The curves are :func:`rietx.viz.packed.curve_arrays`' payload, the one the GUI
draws, sent as base64 so every value is the fit's own double. Past
``max_points`` channels they are decimated as the GUI's are, on the observed,
calculated and Δ/σ curves together, so a misfit spike survives as a peak top
does.
"""

from __future__ import annotations

import base64
import json
from html import escape
from pathlib import Path

import numpy as np

from ..schemas.results import RefinementResult
from . import packed, theme
from .chart import CHART_DIR
from .plots import PALETTES

#: This page's script and stylesheet.
FIGURE_DIR = Path(__file__).parent / "figure"

#: The one import ``figure.mjs`` makes. The file answers it by inlining the
#: module before the script, so the statement itself is taken out.
_IMPORT = "import {exportButtons, hklLabel, nearest, pattern, unpack} from '../static/rxplot.mjs';\n"

#: The residual each mode draws, as ``rxplot.pattern`` names it, and the
#: payload array it reads.
_RESIDUAL = {True: ("weighted", "delta"), False: ("delta", "delta_raw")}


def _script_safe(text: str, name: str) -> str:
    """``text`` unchanged, refused if it could end the element it is inlined in."""
    lowered = text.lower()
    if "</script" in lowered or "<!--" in lowered:
        raise ValueError(f"{name} holds '</script' or '<!--', so it cannot be "
                         "inlined in a <script> element")
    return text


def _notice(name: str) -> str:
    """A vendored licence, to be written as a comment beside its code."""
    text = (CHART_DIR / name).read_text(encoding="utf-8").strip()
    if "*/" in text:
        raise ValueError(f"{name} holds '*/', so it cannot be its code's comment")
    return text


def _json(value) -> str:
    """JSON that cannot close the ``<script>`` element it is inlined in."""
    return (json.dumps(value, ensure_ascii=False)
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def _legend(ticks: dict, has_background: bool, weighted: bool, hue: dict) -> list[dict]:
    """The legend's entries in the order the curves are drawn.

    An all-zero background is no background and gets no entry. A tick row
    takes the observed points' ink when it is the only one, as the chart's
    ``phaseInk`` draws it: colour tells rows apart, and one row has nothing to
    be told from.
    """
    out = [{"id": "obs", "label": "observed", "ink": hue["obs"], "mark": "dot"},
           {"id": "calc", "label": "calculated", "ink": hue["calc"], "mark": "line"}]
    if has_background:
        out.append({"id": "bkg", "label": "background", "ink": hue["bkg"], "mark": "dash"})
    out.append({"id": "diff", "label": "Δ/σ" if weighted else "difference",
                "ink": hue["diff"], "mark": "line"})
    for row, name in enumerate(ticks):
        ink = hue["obs"] if len(ticks) <= 1 else hue["phase"][row % len(hue["phase"])]
        out.append({"id": f"ticks:{name}", "label": f"hkl: {name}", "ink": ink,
                    "mark": "tick"})
    return out


def page(result: RefinementResult, *, weighted: bool = False,
         max_points: int | None = None) -> str:
    """The page :func:`write_html` writes, as a string.

    ``weighted`` draws Δ/σ with its ±3σ band, and otherwise the raw
    difference, as :func:`rietx.viz.plots.plot_result` does by default.
    ``max_points`` is the channel budget past which the curves are decimated,
    :data:`rietx.viz.packed.CURVES_CEILING` unless given. The chart paints each
    pixel column's lowest and highest point, and that ceiling is the pattern
    size it was measured to draw with no long frame.

    The colours are :data:`rietx.viz.plots.PALETTES`' light set, the matplotlib
    figure's rather than the GUI's theme tokens, since this and
    ``plot_result`` are two files of one fit and a reader flipping between them
    must not relearn which curve is which. The axes and grid take the light
    theme's chrome from :mod:`rietx.viz.theme`, as every other page's do.
    """
    s = result.statistics
    n = len(result.two_theta)
    curves = packed.curve_arrays(result.two_theta, result.y_obs, np.ones(n, dtype=bool),
                                 result, weighted=None, ceiling=max_points)
    residual, array = _RESIDUAL[bool(weighted)]
    # A result is fitted at every channel it carries, so the page builds
    # `kept` and `fitted` itself, and it draws one residual of the three. An
    # all-zero background is no background: sent, it would draw a line at zero
    # that no legend entry can hide, and pull the intensity axis down to it.
    has_background = bool(np.any(curves.arrays.get("y_background", [])))
    keep = ("two_theta", "y_obs", "y_calc", array) + (("y_background",) if has_background else ())
    body = packed.pack(curves.header, {k: v for k, v in curves.arrays.items() if k in keep})

    hue = PALETTES["light"]
    title = f"{result.mode}  Rwp={s.rwp:.4f}  GoF={s.gof:.2f}"
    spec = {
        "residual": residual, "band": bool(weighted),
        "labels": {"y": "intensity", "resid": "Δ/σ" if weighted else "Δ"},
        "colors": {"obs": hue["obs"], "masked": hue["obs"], "calc": hue["calc"],
                   "bkg": hue["bkg"], "diff": hue["diff"], "zero": hue["zero"],
                   "band": hue["band"], "phase": list(hue["phase"])},
        "legend": _legend(curves.header.get("ticks", {}), has_background,
                          bool(weighted), hue),
    }

    chrome = theme.TOKENS["light"]
    uplot = _script_safe((CHART_DIR / "uPlot.iife.min.js").read_text(encoding="utf-8"),
                         "uPlot")
    notice = _notice("uPlot.LICENSE")
    svgcanvas = _script_safe((CHART_DIR / "svgcanvas.esm.js").read_text(encoding="utf-8"),
                             "svgcanvas")
    svg_notice = _notice("svgcanvas.LICENSE")
    module = _script_safe((CHART_DIR / "rxplot.mjs").read_text(encoding="utf-8"), "rxplot.mjs")
    script = (FIGURE_DIR / "figure.mjs").read_text(encoding="utf-8")
    if script.count(_IMPORT) != 1:
        raise ValueError(f"figure.mjs must import the chart module as {_IMPORT.strip()!r}")
    script = _script_safe(script.replace(_IMPORT, ""), "figure.mjs")
    css = (CHART_DIR / "uPlot.min.css").read_text(encoding="utf-8") + "\n" + \
        (FIGURE_DIR / "figure.css").read_text(encoding="utf-8")
    if "</style" in css.lower():
        raise ValueError("a stylesheet holds '</style', so it cannot be inlined")
    tokens = (f":root {{ --fg: {chrome['--fg']}; --line: {chrome['--line']}; "
              f"--muted: {chrome['--muted']}; --ground: {hue['ground']}; }}")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>
{tokens}
{css}
</style>
</head>
<body>
<header><h1>{escape(title)}</h1><span id="exports"></span><div id="readout"></div></header>
<div id="plot"></div>
<script type="application/json" id="spec">{_json(spec)}</script>
<script type="application/octet-stream" id="curves">
{base64.b64encode(body).decode("ascii")}
</script>
<script>
/*
{notice}
*/
{uplot}
</script>
<script type="module">
/*
{svg_notice}
*/
{svgcanvas}
window.rxSvgcanvas = {{ Context }};
</script>
<script type="module">
{module}
{{
{script}
}}
</script>
</body>
</html>
"""


def write_html(result: RefinementResult, path: str, *, weighted: bool = False,
               max_points: int | None = None) -> None:
    """Render a :class:`RefinementResult` to a self-contained HTML file.

    ``weighted`` defaults off, matching :func:`rietx.viz.plots.plot_result`:
    both are a file someone takes away and reads as a figure, so they show the
    same difference. :func:`page` builds the file and says what is in it.
    """
    Path(path).write_text(page(result, weighted=weighted, max_points=max_points),
                          encoding="utf-8")
