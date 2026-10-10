"""WP-1501 — the structure figure and the viewer's geometry: what they share.

``rietx.viz.figure3d`` draws the geometry ``rietx.gui.structure3d.build``
returns.  They are two halves that one day stand apart (WP-1505 makes the
join an adapter), and every rietx module either half imports, lazily or not,
is something that split has to inject or move.  This pins the list, so its
growth is seen.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import rietx

ROOT = Path(rietx.__file__).parent

#: Measured 2026-09-30.  ``gui.structure3d`` is the figure's one upward
#: import, made inside ``render_structure``.  2026-10-01:
#: ``crystallography.species``, whose ``element_symbol`` the viewer now reads a
#: species with instead of a parser of its own that disagreed on ``D`` (#576
#: review, follow-up 2).  It is that parser alone, moved out of
#: ``optimize.qpa`` so the split is not committed to qpa's imports (#590
#: review).  2026-10-10: ``model.compiled`` left with the numba rasteriser
#: (WP-1940), whose switch, cache and thread pool were the figure's from there.
BOUNDARY = {
    "rietx._about",
    "rietx.crystallography.adp",
    "rietx.crystallography.species",
    "rietx.crystallography.symmetry",
    "rietx.gui.structure3d",
    "rietx.viz.theme",
}


def _is_module(dotted: str) -> bool:
    try:
        return importlib.util.find_spec(dotted) is not None
    except (ImportError, ValueError):
        return False


def _imports(path: Path, package: str) -> set[str]:
    """Every rietx module ``path`` imports, anywhere in the file, absolute."""
    out: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names if a.name.split(".")[0] == "rietx"}
        elif isinstance(node, ast.ImportFrom):
            parts = package.split(".")
            if node.level:
                parts = parts[:len(parts) - node.level + 1]
                parts += node.module.split(".") if node.module else []
            else:
                parts = (node.module or "").split(".")
            if parts[0] != "rietx":
                continue
            base = ".".join(parts)
            for a in node.names:
                # ``from . import scene`` names a module, ``from ..x import f`` a name in one
                out.add(f"{base}.{a.name}" if _is_module(f"{base}.{a.name}") else base)
    return out


def test_the_figure_and_the_geometry_share_a_known_set_of_modules():
    found: set[str] = set()
    for path in sorted((ROOT / "viz" / "figure3d").glob("*.py")):
        found |= _imports(path, "rietx.viz.figure3d")
    found |= _imports(ROOT / "gui" / "structure3d.py", "rietx.gui")
    found = {m for m in found if not m.startswith("rietx.viz.figure3d")}
    assert found == BOUNDARY, (
        f"new: {sorted(found - BOUNDARY)}, gone: {sorted(BOUNDARY - found)}; each is a "
        "dependency WP-1505's split has to inject or move")
