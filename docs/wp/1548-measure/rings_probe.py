"""Probe: cycles of the drawn bond graph and their planarity, per organic phase."""
import collections
import sys
import warnings

import numpy as np

from rietx.crystallography.cif import structure_from_cif
from rietx.gui import structure3d as s3

warnings.simplefilter("ignore")


def cycles(edges, maxlen=8):
    """For each edge, the shortest cycle through it (a superset of the SSSR)."""
    adj = collections.defaultdict(set)
    for i, j in edges:
        adj[i].add(j)
        adj[j].add(i)
    found = {}
    for u, v in edges:
        prev = {u: None}
        q = collections.deque([u])
        while q:
            x = q.popleft()
            if x == v:
                break
            for y in adj[x]:
                if {x, y} == {u, v} or y in prev:
                    continue
                prev[y] = x
                q.append(y)
        if v not in prev:
            continue
        path, x = [], v
        while x is not None:
            path.append(x)
            x = prev[x]
        if len(path) <= maxlen:
            found.setdefault(frozenset(path), path)
    return list(found.values())


def deviation(P):
    c = P.mean(0)
    _, _, vt = np.linalg.svd(P - c)
    d = (P - c) @ vt[2]
    return float(np.abs(d).max())


EXT = ((0, 2), (0, 2), (0, 2)) if "--block" in sys.argv else None
for f in [a for a in sys.argv[1:] if not a.startswith("--")]:
    g = s3.build(structure_from_cif(f), extent=EXT, max_atoms=5000)
    pos = np.array([a["pos"] for a in g["atoms"]])
    el = [g["sites"][a["site"]]["element"] for a in g["atoms"]]
    key = {tuple(np.round(q, 3)): k for k, q in enumerate(pos)}
    edges, airborne = set(), 0
    for b in g["bonds"]:
        i, j = key.get(tuple(np.round(b["a"], 3))), key.get(tuple(np.round(b["b"], 3)))
        if i is None or j is None:
            airborne += 1
            continue
        edges.add((min(i, j), max(i, j)))
    edges = sorted(edges)
    rows = collections.Counter()
    for c in cycles(edges):
        comp = "".join(sorted(el[i] for i in c))
        rows[(len(c), comp, round(deviation(pos[c]), 3))] += 1
    print(f, len(g["atoms"]), "atoms", len(edges), "bonds", airborne, "airborne")
    for (k, comp, mx), n in sorted(rows.items()):
        print(f"   size {k} {comp:16s} max|d|={mx:.3f} A  x{n}")
