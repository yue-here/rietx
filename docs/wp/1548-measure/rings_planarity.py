"""WP-1548: the planarity spread of the smallest rings on every carbon-bearing CIF.

Runs :func:`rietx.viz.figure3d.rings.smallest_rings` over the drawn bonds of
each CIF under ``tests/data`` (recursively) and ``src/rietx/data`` whose first
phase carries carbon, drawn as a 2×2×2 block so that a ring one cell edge cuts
closes.  A phase too large for the block cap is drawn as one cell's block
instead, and says so.  Prints every ring of 3-8 atoms with its composition and
its largest distance from its mean plane, then the five- and six-rings either
side of :data:`rietx.viz.figure3d.rings.PLANAR_RING_TOLERANCE`.

    .venv/bin/python docs/wp/1548-measure/rings_planarity.py > docs/wp/1548-measure/rings_planarity.txt
"""

import collections
import pathlib
import time
import warnings

import numpy as np

from rietx.crystallography.cif import structure_from_cif
from rietx.gui import structure3d as s3
from rietx.viz.figure3d import rings

warnings.simplefilter("ignore")
ROOT = pathlib.Path(__file__).resolve().parents[3]
CAP = 6000
FLAT, PUCKERED = [], []


def element(geometry, k):
    return geometry["sites"][geometry["atoms"][k]["site"]]["element"]


def draw(structure):
    for n in (2, 1):
        try:
            return n, s3.build(structure, extent=((0, n), (0, n), (0, n)), max_atoms=CAP)
        except ValueError:
            continue
    return 0, None


files = sorted(p for d in ("tests/data", "src/rietx/data") for p in (ROOT / d).rglob("*.cif"))
print(f"{len(files)} CIFs under tests/data and src/rietx/data; tolerance "
      f"{rings.PLANAR_RING_TOLERANCE} A, sizes {rings.RING_SIZES}\n")
skipped = collections.Counter()
for path in files:
    name = path.relative_to(ROOT)
    try:
        structure = structure_from_cif(str(path))
    except Exception as exc:  # noqa: BLE001 - a survey reports what it cannot read
        skipped[f"unreadable ({type(exc).__name__})"] += 1
        continue
    species = {s3.element_symbol(a.species) for a in structure.phases[0].atoms}
    if "C" not in species:
        skipped["no carbon"] += 1
        continue
    started = time.perf_counter()
    n, g = draw(structure)
    if g is None:
        print(f"{name}: past {CAP} atoms even as one cell, not drawn\n")
        continue
    edges = rings.bond_edges(g)
    found = rings.smallest_rings(edges, len(g["atoms"]), max_size=8)
    pos = np.array([a["pos"] for a in g["atoms"]])
    rows = collections.Counter()
    for ring in found:
        comp = "".join(sorted(element(g, k) for k in ring))
        dev = rings.ring_deviation(pos[ring])
        rows[(len(ring), comp, round(dev, 3))] += 1
        if len(ring) in rings.RING_SIZES:
            (FLAT if dev <= rings.PLANAR_RING_TOLERANCE else PUCKERED).append((dev, str(name), comp))
    cut = g.get("cut", {}).get("segments", 0)
    print(f"{name}: {''.join(sorted(species))}  {n}x{n}x{n} block, {len(g['atoms'])} atoms, "
          f"{len(edges)} bonds{f', {cut} segments trimmed' if cut else ''}, "
          f"{len(found)} rings, {time.perf_counter() - started:.1f} s")
    for (k, comp, dev), count in sorted(rows.items()):
        print(f"   size {k} {comp:16s} max|d|={dev:.3f} A  x{count}")
    print()

print("skipped:", dict(skipped))
print(f"\nfive- and six-rings: {len(FLAT)} within the tolerance, {len(PUCKERED)} past it")
if FLAT:
    dev, name, comp = max(FLAT)
    print(f"flattest bound: largest planar deviation {dev:.3f} A ({comp}, {name})")
if PUCKERED:
    dev, name, comp = min(PUCKERED)
    print(f"puckered bound: smallest non-planar deviation {dev:.3f} A ({comp}, {name})")
per = collections.defaultdict(lambda: [None, None])
for dev, name, _ in FLAT:
    per[name][0] = max(dev, per[name][0] or 0.0)
for dev, name, _ in PUCKERED:
    per[name][1] = dev if per[name][1] is None else min(dev, per[name][1])
print("\nper phase: (largest planar, smallest puckered) five- or six-ring deviation, A")
def fmt(v):
    return "   -  " if v is None else f"{v:.3f}"


for name, (flat, puck) in sorted(per.items()):
    print(f"   {fmt(flat)}  {fmt(puck)}  {name}")
gap = [(d, n, c) for d, n, c in FLAT + PUCKERED if 0.05 < d < 0.2]
print(f"\nfive- and six-rings between 0.05 and 0.2 A: {len(gap)}")
for dev, name, comp in sorted(gap):
    print(f"   {dev:.3f} {comp} {name}")


# The puckering amplitude at which the test turns a ring away, from Cremer &
# Pople's ring coordinates (Cremer, D. & Pople, J. A. (1975). A general
# definition of ring puckering coordinates. J. Am. Chem. Soc. 97, 1354-1358):
# z_j = sqrt(2/N) q2 cos(phi + 4 pi j/N) (+ q3 (-1)^j / sqrt(N) for N = 6),
# laid over a regular polygon, measured by the same ring_deviation.  The
# least-deviating phase is taken for each form, so the crossing is the
# smallest amplitude any ring of that form needs to be turned away.
def crossing(n, form):
    radius = 1.4 / (2 * np.sin(np.pi / n))
    angle = 2 * np.pi * np.arange(n) / n

    def worst(q):
        devs = []
        for phi in np.linspace(0, 2 * np.pi, 361):
            if form == "chair":
                z = q * (-1.0) ** np.arange(n) / np.sqrt(n)
            else:
                z = np.sqrt(2 / n) * q * np.cos(phi + 4 * np.pi * np.arange(n) / n)
            p = np.c_[radius * np.cos(angle), radius * np.sin(angle), z]
            devs.append(rings.ring_deviation(p))
        return min(devs)

    lo, hi = 0.0, 2.0
    for _ in range(50):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if worst(mid) <= rings.PLANAR_RING_TOLERANCE else (lo, mid)
    return lo


print("\npuckering amplitude Q (Cremer & Pople 1975) above which a ring is turned away, "
      "at its least-deviating phase:")
for n, form in ((5, "envelope/twist"), (6, "boat/twist-boat"), (6, "chair")):
    print(f"   {n}-ring {form:16s} Q > {crossing(n, form.split('/')[0]):.3f} A")
