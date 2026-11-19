"""WP-1548: the degree cap on ring finding, measured on every CIF on disk.

For each CIF under ``tests/data`` (recursively) and ``src/rietx/data`` whose
first phase reads, drawn as a 2×2×2 block (one cell's block where that passes
the cap), prints the largest number of drawn bonds on any atom, the largest on
an atom of a planar five- or six-ring found with no cap, and the planar rings
and time with and without :data:`rietx.viz.figure3d.rings.MAX_RING_DEGREE`.
A cap that turned a planar ring away would show as a difference in the count.

    .venv/bin/python docs/wp/1548-measure/rings_degree.py > docs/wp/1548-measure/rings_degree.txt
"""

import collections
import pathlib
import time
import warnings

from rietx.crystallography.cif import structure_from_cif
from rietx.gui import structure3d as s3
from rietx.viz.figure3d import rings

warnings.simplefilter("ignore")
ROOT = pathlib.Path(__file__).resolve().parents[3]
CAP = 6000


def draw(structure):
    for n in (2, 1):
        try:
            return n, s3.build(structure, extent=((0, n), (0, n), (0, n)), max_atoms=CAP)
        except ValueError:
            continue
    return 0, None


files = sorted(p for d in ("tests/data", "src/rietx/data") for p in (ROOT / d).rglob("*.cif"))
print(f"{len(files)} CIFs; cap {rings.MAX_RING_DEGREE} drawn bonds, sizes {rings.RING_SIZES}, "
      f"tolerance {rings.PLANAR_RING_TOLERANCE} A\n")
worst_ring_degree = 0
for path in files:
    name = path.relative_to(ROOT)
    try:
        structure = structure_from_cif(str(path))
    except Exception as exc:  # noqa: BLE001 - a survey reports what it cannot read
        print(f"{name}: unreadable ({type(exc).__name__})")
        continue
    n, g = draw(structure)
    if g is None:
        print(f"{name}: past {CAP} atoms even as one cell, not drawn")
        continue
    degree = collections.Counter()
    for i, j in rings.bond_edges(g):
        degree[i] += 1
        degree[j] += 1
    t0 = time.perf_counter()
    free = rings.planar_rings(g, max_degree=None)
    t1 = time.perf_counter()
    capped = rings.planar_rings(g)
    t2 = time.perf_counter()
    on_ring = max((degree[k] for ring in free for k in ring), default=0)
    worst_ring_degree = max(worst_ring_degree, on_ring)
    print(f"{name}: {n}x{n}x{n} block, {len(g['atoms'])} atoms, max degree "
          f"{max(degree.values(), default=0)}, on a planar ring {on_ring}; planar rings "
          f"{len(free)} uncapped in {t1 - t0:.2f} s, {len(capped)} capped in {t2 - t1:.2f} s")
print(f"\nlargest degree of a planar-ring atom on disk: {worst_ring_degree}")
