#!/usr/bin/env python3
"""Copy the pinned uPlot and svgcanvas into ``src/rietx/viz/static``, the one step that writes them.

Every browser chart rietx draws builds on uPlot, and its SVG export on
svgcanvas (WP-1461). The GUI bundles both, while ``rietx watch``, ``rietx
compare`` and the page ``write_html`` writes read them from the installed
package. So the package carries one copy of each, and this script is the only
writer of those copies. ``npm run build`` runs it before vite.

The version statement is the exact pin in ``gui/package.json``. A copy is
refused when the installed package disagrees with the pin, since a stale
``node_modules`` would otherwise vendor the wrong release under the right name.
Each copy's version is written to ``VENDORED.json`` beside it, and uPlot's
banner names its own. ``tests/test_gui_dist.py`` imports this file by path and
holds both equal to the pins, in the ordinary suite, where there is no node.

A pin bump therefore goes: edit the pin (or merge the Dependabot pull request),
``npm --prefix gui install``, ``npm --prefix gui run build``. The vendored
directory is in ``build_info.py``'s digest, so a hand edit of a vendored file
reads as a stale dist.

Usage (from the ``gui/`` directory)::

    python3 scripts/vendor.py
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

#: Where the copy goes, relative to ``gui/``.
VENDOR_RELATIVE = Path("..") / "src" / "rietx" / "viz" / "static"

#: Each npm package, and each file taken from it with the name it is written as.
#: A licence travels beside its code because a file ``write_html`` writes
#: leaves the package, and MIT asks for the notice in every copy. svgcanvas's
#: carries canvas2svg's notice too, the library it grew from.
PACKAGES = {
    "uplot": {
        "dist/uPlot.iife.min.js": "uPlot.iife.min.js",
        "dist/uPlot.min.css": "uPlot.min.css",
        "LICENSE": "uPlot.LICENSE",
    },
    "svgcanvas": {
        "dist/svgcanvas.esm.js": "svgcanvas.esm.js",
        "LICENSE": "svgcanvas.LICENSE",
    },
}

#: What was copied, as ``{package: version}``, written beside the copies.
RECORD = "VENDORED.json"

#: The file whose first line names the release: ``/*! <url> (v1.6.32) */``.
BANNERED = "uPlot.iife.min.js"


def pin(gui_dir: Path, package: str = "uplot") -> str:
    """The exact version ``gui/package.json`` pins ``package`` at, refusing a range."""
    deps = json.loads((gui_dir / "package.json").read_text(encoding="utf-8"))
    spec = deps.get("dependencies", {}).get(package, "")
    if not re.fullmatch(r"\d+\.\d+\.\d+", spec):
        raise SystemExit(f"gui/package.json must pin {package} exactly, "
                         f"not {spec!r}: the vendored copy follows the pin")
    return spec


def recorded(vendor_dir: Path) -> dict[str, str]:
    """The versions the last vendoring wrote, or an empty record without one."""
    try:
        return json.loads((vendor_dir / RECORD).read_text(encoding="utf-8"))
    except OSError:
        return {}


def banner_version(vendor_dir: Path) -> str | None:
    """The release the vendored file names in its banner, or None without one."""
    try:
        with (vendor_dir / BANNERED).open(encoding="utf-8") as f:
            first = f.readline()
    except OSError:
        return None
    found = re.search(r"\(v(\d+\.\d+\.\d+)\)", first)
    return found.group(1) if found else None


def main() -> int:
    gui_dir = Path(__file__).resolve().parent.parent
    target = (gui_dir / VENDOR_RELATIVE).resolve()
    versions = {}
    # every package checked before any file is written, so a refusal leaves
    # the copies and their record as they were
    for package in PACKAGES:
        source = gui_dir / "node_modules" / package
        wanted = pin(gui_dir, package)
        if not (source / "package.json").is_file():
            print(f"node_modules has no {package}: run `npm --prefix gui ci` first",
                  file=sys.stderr)
            return 1
        installed = json.loads((source / "package.json").read_text(encoding="utf-8"))["version"]
        if installed != wanted:
            print(f"node_modules holds {package} {installed}, the pin is {wanted}: "
                  f"run `npm --prefix gui install` first", file=sys.stderr)
            return 1
        versions[package] = wanted
    target.mkdir(parents=True, exist_ok=True)
    for package, files in PACKAGES.items():
        for src, name in files.items():
            shutil.copyfile(gui_dir / "node_modules" / package / src, target / name)
        print(f"vendored {package} {versions[package]} into {VENDOR_RELATIVE.as_posix()}")
    (target / RECORD).write_text(json.dumps(versions, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
