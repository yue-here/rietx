"""The chart every browser page draws with, as the files a server sends (WP-1461).

``static/`` holds the chart module and the uPlot vendored beside it, at the pin
``gui/package.json`` holds. ``rietx watch`` and ``rietx compare`` serve these
from where the wheel keeps them, so both pages draw with no network and no
optional dependency, where plotly needed the ``viz`` extra and 4.8 MB. The GUI
bundles the same files into its dist instead.

A fixed table rather than a directory served whole: four names cannot be
walked out of.
"""

from __future__ import annotations

from pathlib import Path

CHART_DIR = Path(__file__).parent / "static"

#: Each file a page loads, and what it is served as.
CHART_FILES = {
    "rxplot.mjs": "text/javascript; charset=utf-8",
    "uPlot.iife.min.js": "text/javascript; charset=utf-8",
    "uPlot.min.css": "text/css; charset=utf-8",
    # the SVG export's, fetched on a page's first SVG and never before
    "svgcanvas.esm.js": "text/javascript; charset=utf-8",
}
