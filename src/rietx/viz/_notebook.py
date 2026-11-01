"""A figure's light and dark images as one notebook output (WP-1970).

The fit figures (:mod:`rietx.viz.plots`) and the structure figure
(:mod:`rietx.viz.figure3d.render`) both emit this pair.  It imports nothing
from rietx, so the structure figure reaches it without crossing the boundary
WP-1505's split has to inject or move (``tests/test_figure_boundary.py``).

The dark image is hidden by an inline style, and a ``<style>`` keyed on
:data:`DARK_MARKERS` swaps the two.  A frontend that strips ``<style>`` from
an output keeps inline styles, so it shows the light figure: GitHub, and
JupyterLab on a notebook opened with its outputs.  The classes take an
``rx-`` prefix because in a Sphinx page the ``<style>`` applies to the whole
page.  pydata-sphinx-theme's ``only-light`` and ``only-dark`` classes switch the manual with
no ``<style>`` at all.
"""

from __future__ import annotations

import base64
import warnings

#: Where each frontend marks a dark theme, read from its source (WP-1970):
#: JupyterLab 4, Notebook 7 and JupyterLite; VS Code's dark and dark
#: high-contrast themes; Colab.  A page carrying none of them shows the
#: light figure.
DARK_MARKERS = ('body[data-jp-theme-light="false"]', "body.vscode-dark",
                "body.vscode-high-contrast:not(.vscode-high-contrast-light)",
                'html[theme="dark"]')


def wants_html(include, exclude) -> bool:
    """Whether a display asked for ``text/html``, so the dark copy is worth
    drawing.  IPython filters the bundle by ``include``/``exclude`` itself;
    this only skips drawing what it would drop."""
    return ((include is None or "text/html" in include)
            and (exclude is None or "text/html" not in exclude))


def no_dark_copy(exc: Exception) -> None:
    """The dark copy is an addition, so a failure in it warns and costs only
    the pair; the PNG still shows."""
    warnings.warn(f"no dark copy of this figure, so it shows light only: {exc!r}",
                  stacklevel=3)


def pair_html(light: bytes, dark: bytes, width: int) -> str:
    """Two PNGs as one output, of which the frontend's theme shows one."""
    def img(png: bytes, role: str, hidden: bool) -> str:
        style = "max-width:100%;height:auto" + (";display:none" if hidden else "")
        return (f'<img class="rx-fig-{role} only-{role}" width="{width}" '
                f'style="{style}" alt="" '
                f'src="data:image/png;base64,{base64.b64encode(png).decode()}">')

    hide = ", ".join(f"{m} .rx-fig-light" for m in DARK_MARKERS)
    show = ", ".join(f"{m} .rx-fig-dark" for m in DARK_MARKERS)
    return (f"<div>{img(light, 'light', False)}{img(dark, 'dark', True)}"
            f"<style>{hide} {{display:none !important}} "
            f"{show} {{display:inline !important}}</style></div>")
