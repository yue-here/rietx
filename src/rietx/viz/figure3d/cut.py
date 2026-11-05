"""Cut a structure figure's geometry and recolour part of it (WP-1501).

The geometry is the dict ``rietx.gui.structure3d.build`` returns.  Its
``bonds`` (``i``, ``j``) and ``polyhedra`` (``center``, ``vertices``,
``bonds``) are indices into ``atoms`` and ``bonds``, so an atom cannot be
deleted by hand without renumbering every later index.  :func:`keep` is the
one place that renumbers.

Four builders name atoms in crystallographic terms and return a boolean array
over ``atoms``, combined with ``&``, ``|`` and ``~``: :func:`select`,
:func:`plane`, :func:`sphere` and :func:`component`.  The vocabulary follows
OVITO (expression selection, then delete selected; slice with a normal, a
distance and a slab width), VESTA (a cutoff plane as (hkl) and a distance in
d-spacings or Å; a boundary search that keeps bonded atoms and whole
polyhedra), Jmol (``within``) and pymatgen/ASE (molecules as connected
components of the bond graph).

Everything here acts on the finite graph ``build`` produced, which is the
extent it was asked for (one cell by default) and the images its bonds and
polyhedra reach.  Two images of one atom are two atoms, so a piece is finite,
and each atom's ``image`` (which atom of the cell, by which lattice translation)
is what :func:`periodicity` reads to say whether the piece repeats.  A bond's
``j`` is an image of its far end and not always the atom at that end, so every
function here finds the far end by image (:func:`_far`).
"""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence

import numpy as np
from scipy.sparse import coo_array
from scipy.sparse.csgraph import connected_components

from . import scene as sc

#: A plane is crossed by an atom lying on it within this many d-spacings.  The
#: images a cell builds sit on the cell's faces to floating-point noise.
PLANE_TOLERANCE = 1e-6
#: How many vertices two polyhedra share to be joined, per ``via=``.
SHARED = {"corners": 1, "edges": 2, "faces": 3}
VIA = ("bonds", *SHARED)
PLANE_UNITS = ("d", "angstrom")
#: What a site colour may be; ``white`` and ``black`` are the names
#: ``render_structure(background=)`` takes.
NAMED_COLOURS = {"white": "#ffffff", "black": "#000000"}


def site_colour(value) -> str:
    """A site colour as ``#rrggbb``, or a ``ValueError`` naming the forms taken."""
    if isinstance(value, str):
        hex_ = NAMED_COLOURS.get(value.lower(), value)
        if sc._HEX.match(hex_):
            return hex_.lower()
    raise ValueError(f"colour {value!r}: give '#rrggbb', 'white' or 'black'; the "
                     "scene draws any other spelling mid-grey without a message")


def _mask(geometry: Mapping, mask, name: str = "mask") -> np.ndarray:
    out = np.asarray(mask)
    n = len(geometry["atoms"])
    if out.dtype != bool or out.shape != (n,):
        raise ValueError(f"{name}: a boolean array with one entry per atom ({n}), "
                         f"as select, plane, sphere and component return; got "
                         f"dtype {out.dtype} and shape {out.shape}")
    return out


def _far(geometry: Mapping, missing: int | None = None) -> np.ndarray:
    """The index of the atom at each bond's far end, ``b``, found by image.

    ``build``'s ``j`` is an atom the bond's far end is a translate of, so it can
    sit a cell away from ``b``.  The far end is the atom whose image is ``b``'s:
    the orbit atom ``j`` is an image of, translated by the whole cells between
    that atom and ``b``.  A far end the figure does not hold (an atom cap left
    it out) falls back on ``j``, which is what the bond was before, or is
    ``missing`` when one is given: the report counts those bonds as ending in
    mid-air (:func:`~.render._dangling`).
    """
    atoms = geometry["atoms"]
    inverse = np.linalg.inv(np.asarray(geometry["lattice"], dtype=np.float64).T)
    at = {(a["image"][0], *a["image"][1]): k for k, a in enumerate(atoms)}
    home: dict[int, np.ndarray] = {}
    for a in atoms:
        o, n = a["image"]
        home.setdefault(o, np.asarray(a["frac"], dtype=np.float64) - n)
    bonds = geometry["bonds"]
    out = np.empty(len(bonds), dtype=int)
    if not bonds:
        return out
    # one matrix product for every bond rather than one a bond: this runs on
    # every render through the report's dangling count
    orbit = [atoms[b["j"]]["image"][0] for b in bonds]
    ends = np.array([b["b"] for b in bonds], dtype=np.float64).reshape(-1, 3)
    cells = np.rint(ends @ inverse.T - np.array([home[o] for o in orbit])).astype(int).tolist()
    for k, (b, o, n) in enumerate(zip(bonds, orbit, cells)):
        out[k] = at.get((o, *n), b["j"] if missing is None else missing)
    return out


def _names(values, what: str, have: Sequence[str]) -> list[str]:
    names = [values] if isinstance(values, str) else list(values)
    unknown = [v for v in names if v not in have]
    if unknown:
        raise ValueError(f"{what} {unknown[0]!r}: this phase has no such {what}; "
                         f"its {what}s are {sorted(set(have))}")
    return names


def select(geometry: Mapping, *, species=None, element=None, label=None, site=None,
           boundary: bool | None = None) -> np.ndarray:
    """The atoms of the named sites, as a boolean array over ``atoms``.

    ``species`` is as the legend spells it (``"Na1+"``), ``element`` a symbol,
    ``label`` a site label, ``site`` an index or indices into ``sites``; each
    takes one value or several.  ``boundary=True`` keeps only the images
    outside the cell, ``False`` only those inside.  Criteria combine with
    *and*.  A name the phase lacks raises and lists what it has, since a mask
    that selects nothing looks like success.  Two sites can share a species, so
    one site is told from its sibling by ``label=`` or ``site=``.
    """
    sites, atoms = geometry["sites"], geometry["atoms"]
    keep = np.ones(len(sites), dtype=bool)
    for value, key in ((species, "species"), (element, "element"), (label, "label")):
        if value is not None:
            names = _names(value, key, [s[key] for s in sites])
            keep &= np.array([s[key] in names for s in sites], dtype=bool)
    if site is not None:
        wanted = [site] if isinstance(site, (int, np.integer)) else list(site)
        bad = [k for k in wanted if not isinstance(k, (int, np.integer))
               or isinstance(k, bool) or not 0 <= k < len(sites)]
        if bad:
            raise ValueError(f"site {bad[0]!r}: this phase has sites 0 to {len(sites) - 1}")
        only = np.zeros(len(sites), dtype=bool)
        only[[int(k) for k in wanted]] = True
        keep &= only
    at = np.array([keep[a["site"]] for a in atoms], dtype=bool)
    if boundary is not None:
        at &= np.array([a["boundary"] == bool(boundary) for a in atoms], dtype=bool)
    return at


def plane(geometry: Mapping, hkl, distance: float, *, width: float | None = None,
          inverse: bool = False, units: str = "d") -> np.ndarray:
    """The atoms on the origin side of the plane (hkl) at ``distance``.

    The planes of the family (hkl) are spaced ``d`` apart, so ``distance=1``
    is the first plane beyond the origin's and ``distance=0`` the origin's own
    (VESTA's cutoff plane).  ``units="angstrom"`` reads ``distance`` and
    ``width`` in Å along the plane's normal.  ``width`` keeps the slab from
    ``distance`` to ``distance + width`` instead.  ``inverse`` keeps what the
    plane would have cut.  An atom on the plane is on the kept side of it.
    """
    if units not in PLANE_UNITS:
        raise ValueError(f"units {units!r}: give one of {PLANE_UNITS}")
    h = np.asarray(hkl, dtype=np.float64)
    if h.shape != (3,) or not np.isfinite(h).all() or not h.any():
        raise ValueError(f"hkl {hkl!r}: three numbers, not all zero")
    lattice = np.asarray(geometry["lattice"], dtype=np.float64)          # rows a, b, c
    d_hkl = 1.0 / float(np.sqrt(h @ np.linalg.inv(lattice @ lattice.T) @ h))
    scale = 1.0 if units == "d" else 1.0 / d_hkl
    if not np.isfinite(float(distance)):
        raise ValueError(f"distance {distance!r}: a finite number, since a NaN keeps "
                         "nothing and looks like success")
    lo = float(distance) * scale
    if width is not None and not (np.isfinite(float(width)) and float(width) > 0):
        raise ValueError(f"width {width!r}: a positive thickness")
    frac = np.array([a["frac"] for a in geometry["atoms"]], dtype=np.float64).reshape(-1, 3)
    h_dot_x = frac @ h
    tol = PLANE_TOLERANCE
    if width is None:
        inside = h_dot_x <= lo + tol
    else:
        inside = (h_dot_x >= lo - tol) & (h_dot_x <= lo + float(width) * scale + tol)
    return ~inside if inverse else inside


def sphere(geometry: Mapping, centre, radius: float) -> np.ndarray:
    """The atoms within ``radius`` Å of ``centre``, itself included.

    ``centre`` is an index into ``atoms`` or a Cartesian point in Å.  An index,
    because a label names several images; ``select(label=)`` finds them.
    """
    pos = np.array([a["pos"] for a in geometry["atoms"]], dtype=np.float64).reshape(-1, 3)
    if isinstance(centre, (int, np.integer)) and not isinstance(centre, bool):
        if not 0 <= centre < len(pos):
            raise ValueError(f"centre {centre!r}: this figure has atoms 0 to {len(pos) - 1}")
        point = pos[int(centre)]
    else:
        point = np.asarray(centre, dtype=np.float64)
        if point.shape != (3,) or not np.isfinite(point).all():
            raise ValueError(f"centre {centre!r}: an atom index or a Cartesian point in Å")
    if not float(radius) >= 0:
        raise ValueError(f"radius {radius!r}: a distance in Å, zero or more")
    return np.linalg.norm(pos - point, axis=1) <= float(radius)


def component(geometry: Mapping, atom: int, *, via: str = "bonds") -> np.ndarray:
    """The connected piece of the figure holding ``atom``.

    ``via="bonds"`` walks the bonds.  ``"corners"``, ``"edges"`` and ``"faces"``
    walk the polyhedra that share at least one, two or three vertices, and the
    piece is their centres and vertices.  The second kind is needed where the
    first reaches everything: rutile's TiO₆ chains are edge-sharing, and by
    bonds every Ti reaches every other through O.  An atom in no polyhedron has
    no piece by ``"corners"``, and ``"edges"`` and ``"faces"`` start only from a
    polyhedron's centre, since the polyhedra round a shared vertex need not
    touch each other; both raise otherwise.
    """
    if via not in VIA:
        raise ValueError(f"via {via!r}: give one of {VIA}")
    atoms = geometry["atoms"]
    if (not isinstance(atom, (int, np.integer)) or isinstance(atom, bool)
            or not 0 <= atom < len(atoms)):
        raise ValueError(f"atom {atom!r}: an index into atoms, 0 to {len(atoms) - 1}")
    n = len(atoms)
    if via == "bonds":
        i = [b["i"] for b in geometry["bonds"]]
        j = _far(geometry)
        graph = coo_array((np.ones(len(i)), (i, j)), shape=(n, n))
        _, label = connected_components(graph, directed=False)
        return label == label[atom]
    polys = geometry["polyhedra"]
    members = [{p["center"], *p["vertices"]} for p in polys]
    if via == "corners":
        seeds = [k for k, m in enumerate(members) if atom in m]
    else:
        # a vertex belongs to every polyhedron that shares it, and those need not
        # share an edge or a face with each other, so only a centre starts a piece
        seeds = [k for k, p in enumerate(polys) if p["center"] == atom]
    if not seeds:
        raise ValueError(f"atom {atom}: " + (
            f"in no polyhedron, so there is no piece joined by {via}"
            if via == "corners" else
            f"the centre of no polyhedron, so there is no piece joined by {via}; "
            "give a polyhedron's centre")
            + "; via='bonds' walks the bonds")
    need = SHARED[via]
    verts = [set(p["vertices"]) for p in polys]
    seen, todo = set(seeds), list(seeds)
    while todo:
        k = todo.pop()
        for m in range(len(polys)):
            if m not in seen and len(verts[k] & verts[m]) >= need:
                seen.add(m)
                todo.append(m)
    out = np.zeros(n, dtype=bool)
    for k in seen:
        out[list(members[k])] = True
    return out


def periodicity(geometry: Mapping, mask) -> int:
    """How many independent lattice directions the atoms ``mask`` keeps repeat in, 0 to 3.

    A molecule is 0, a chain 1, a layer 2 and a framework 3 (Larsen et al.,
    2019, *Phys. Rev. Materials* 3, 034003; pymatgen's
    ``get_dimensionality_larsen``).  The bonds between kept atoms join them in
    the graph of the cell's own atoms, each bond carrying the lattice
    translation between its ends' images.  Round a cycle those add to a lattice
    vector, zero when the piece closes on itself and not when it reaches its
    own image a cell away.  The answer is the rank of the vectors, and for a
    mask of several pieces the largest.  A piece is seen as periodic only if the
    figure draws the image it reaches, so a mask of one cell's atoms without the
    bond neighbours ``build`` adds reads as 0 (:func:`component` returns them).
    """
    kept = _mask(geometry, mask)
    atoms = geometry["atoms"]
    around: dict[int, list[tuple[int, np.ndarray]]] = {}
    for b, j in zip(geometry["bonds"], _far(geometry)):
        if kept[b["i"]] and kept[j]:
            (o, n), (p, m) = atoms[b["i"]]["image"], atoms[j]["image"]
            t = np.asarray(m) - np.asarray(n)
            around.setdefault(o, []).append((p, t))
            around.setdefault(p, []).append((o, -t))
    # a potential per atom of the cell, from a spanning tree of each piece; an
    # edge the tree does not use closes a cycle whose translation is the gap
    potential: dict[int, np.ndarray] = {}
    best = 0
    for root in around:
        if root in potential:
            continue
        potential[root] = np.zeros(3, dtype=int)
        piece, todo = [], [root]
        while todo:
            o = todo.pop()
            for p, t in around[o]:
                if p not in potential:
                    potential[p] = potential[o] + t
                    todo.append(p)
                else:
                    piece.append(potential[o] + t - potential[p])
        if piece:
            best = max(best, int(np.linalg.matrix_rank(np.array(piece, dtype=np.float64))))
    return best


#: What ``keep(..., complete=)`` takes: nothing, both, or one of the two.
COMPLETE = (False, True, "bonds", "polyhedra")


def keep(geometry: Mapping, mask, *, complete: bool | str = False) -> dict:
    """The geometry with only the atoms ``mask`` keeps, every index consistent.

    A bond survives when both its ends do, a polyhedron when its centre and
    every vertex do.  Those cut from a survivor are counted in ``note``
    (``"3 polyhedra cut · 12 bonds cut"``), so a cut figure says what it lost,
    and added to ``cut``.  ``cut`` keeps every count it held, so ``build``'s
    ``atoms``, the cell's images its atom cap left out, survive any number of
    cuts.  ``complete=True`` first re-adds the far ends of the bonds cut from a kept
    atom and the vertices of the polyhedra whose centre is kept, from the atoms
    ``build`` produced: VESTA's boundary search.  ``complete="polyhedra"``
    re-adds the vertices alone, so a window of whole polyhedra has nothing
    hanging off its edge, and ``complete="bonds"`` the far ends alone (#667).
    It completes only within what was built.  ``sites`` is untouched and
    ``atoms[k]["site"]`` keeps its meaning.  The input is not modified.
    """
    if isinstance(complete, np.bool_):      # ``mask.any()`` and the like
        complete = bool(complete)
    if not any(complete is c or (isinstance(c, str) and complete == c) for c in COMPLETE):
        raise ValueError(f"complete {complete!r}: one of False, True, 'bonds' or 'polyhedra'")
    atoms = geometry["atoms"]
    kept = _mask(geometry, mask).copy()
    bonds, polys = geometry["bonds"], geometry["polyhedra"]
    far = _far(geometry)
    first = kept.copy()
    if complete in (True, "bonds"):
        for b, j in zip(bonds, far):
            if first[b["i"]] or first[j]:
                kept[b["i"]] = kept[j] = True
    if complete in (True, "polyhedra"):
        for p in polys:
            if first[p["center"]]:
                kept[p["vertices"]] = True
    new = np.cumsum(kept) - 1
    bond_ok = [bool(kept[b["i"]] and kept[j]) for b, j in zip(bonds, far)]
    poly_ok = [bool(kept[p["center"]] and all(kept[v] for v in p["vertices"])) for p in polys]
    bond_at = np.cumsum(bond_ok) - 1
    cut_bonds = sum(1 for b, j, ok in zip(bonds, far, bond_ok)
                    if not ok and (kept[b["i"]] or kept[j]))
    cut_polys = sum(1 for p, ok in zip(polys, poly_ok)
                    if not ok and (kept[p["center"]] or any(kept[v] for v in p["vertices"])))
    out = dict(geometry)
    out["sites"] = copy.deepcopy(geometry["sites"])
    out["atoms"] = [dict(a) for a, k in zip(atoms, kept) if k]
    if "n_cell" in geometry:          # the block's own atoms lead ``atoms``, still
        out["n_cell"] = int(kept[:geometry["n_cell"]].sum())
    # ``j`` stays while its atom does, and is the far end's where it was cut
    out["bonds"] = [{**b, "i": int(new[b["i"]]), "j": int(new[b["j"] if kept[b["j"]] else j])}
                    for b, j, ok in zip(bonds, far, bond_ok) if ok]
    out["polyhedra"] = [
        {**p, "center": int(new[p["center"]]),
         "vertices": [int(new[v]) for v in p["vertices"]],
         "bonds": [int(bond_at[k]) for k in p["bonds"] if bond_ok[k]]}
        for p, ok in zip(polys, poly_ok) if ok]
    lost = [f"{n} {what} cut" for n, what in ((cut_polys, "polyhedra"), (cut_bonds, "bonds"))
            if n]
    # the same counts as numbers, running over successive cuts: the figure's
    # report reads these and never parses ``note``.  ``build``'s own counts
    # (``atoms``, the atom cap's) pass through
    before = geometry.get("cut", {})
    out["cut"] = {**before, "polyhedra": before.get("polyhedra", 0) + cut_polys,
                  "bonds": before.get("bonds", 0) + cut_bonds}
    if lost:
        out["note"] = " · ".join([*([geometry["note"]] if geometry.get("note") else []), *lost])
    return out


def recolour(geometry: Mapping, mask, colour) -> dict:
    """The geometry with the masked atoms, and the polyhedra centred on them, in ``colour``.

    Each site the mask reaches is copied once, in the new colour and marked
    ``"recoloured": True``, and the masked atoms point at the copy, so the
    scene rules are untouched and the rest of the site keeps its colour.
    ``colour`` is ``'#rrggbb'``, ``'white'`` or ``'black'``.  The input is not
    modified.
    """
    colour = site_colour(colour)
    chosen = _mask(geometry, mask)
    out = dict(geometry)
    out["sites"] = copy.deepcopy(geometry["sites"])
    out["atoms"] = [dict(a) for a in geometry["atoms"]]
    out["polyhedra"] = [dict(p) for p in geometry["polyhedra"]]
    copies: dict[int, int] = {}
    for a in (a for a, c in zip(out["atoms"], chosen) if c):
        if a["site"] not in copies:
            copies[a["site"]] = len(out["sites"])
            site = {k: v for k, v in out["sites"][a["site"]].items() if k != "dark_color"}
            out["sites"].append({**site, "color": colour, "recoloured": True})
        a["site"] = copies[a["site"]]
    for p in out["polyhedra"]:
        if chosen[p["center"]]:
            p["site"] = copies[geometry["atoms"][p["center"]]["site"]]
    return out
