"""Lattice-forced Pawley coincidences merge into one intensity column (WP-2315, R5 (b)).

Ruled 2026-11-27 (WP-2317 R5, "go (b)"): reflections whose d agree for every
metric of their Laue class carry one Pawley column, the group sum measured and
each member's share unmeasured.  Accidental coincidences keep the soft
equal-F² restraint.  The detection is
:func:`rietx.crystallography.symmetry.lattice_coincidences`.
"""

from __future__ import annotations

import itertools

import numpy as np
import pytest

from rietx.crystallography.symmetry import (
    as_group,
    cell_constraints,
    generate_reflections,
    lattice_coincidences,
)

# ---------------------------------------------------------------------------
# detection, against GSAS-II's per-Laue-class integer identities
# ---------------------------------------------------------------------------


def _gsas2_rule(laue: str, h1, h2) -> bool | None:
    """GSAS-II 5.8.4 ``GSASIIstrIO.GetPawleyConstr`` (lines 955-998), its
    integer identities restated.  ``None`` for the classes where GSAS-II
    compares d to 1e-4 instead (-1, 2/m, mmm), which is an accidental
    tolerance and not a lattice identity."""
    (ih, ik, il), (jh, jk, jl) = h1, h2
    if laue in ("4/m", "4/mmm"):
        return abs(il) == abs(jl) and ih**2 + ik**2 == jh**2 + jk**2
    if laue in ("3R", "3mR"):
        return (ih**2 + ik**2 + il**2 == jh**2 + jk**2 + jl**2
                and ih * ik + ih * il + ik * il == jh * jk + jh * jl + jk * jl)
    if laue in ("3", "3m1", "31m", "6/m", "6/mmm"):
        return abs(il) == abs(jl) and ih**2 + ik**2 + ih * ik == jh**2 + jk**2 + jh * jk
    if laue in ("m3", "m3m"):
        return ih**2 + ik**2 + il**2 == jh**2 + jk**2 + jl**2
    return None


#: one space group per Laue class, its GSAS-II Laue label, and a cell of it
CASES = [
    ("P -1", "-1", (5.1, 6.3, 7.2, 81.0, 97.0, 104.0)),
    ("P 1 2/m 1", "2/m", (5.1, 6.3, 7.2, 90.0, 103.0, 90.0)),
    ("P 1 1 2/m", "2/m", (5.1, 6.3, 7.2, 90.0, 90.0, 103.0)),
    ("P m m m", "mmm", (5.1, 6.3, 7.2, 90.0, 90.0, 90.0)),
    ("P 4/m", "4/m", (6.1, 6.1, 4.3, 90.0, 90.0, 90.0)),
    ("I 41/a", "4/m", (6.1, 6.1, 11.3, 90.0, 90.0, 90.0)),
    ("P 4/m m m", "4/mmm", (6.1, 6.1, 4.3, 90.0, 90.0, 90.0)),
    ("P -3", "3", (6.1, 6.1, 4.3, 90.0, 90.0, 120.0)),
    ("R -3:H", "3", (6.1, 6.1, 14.3, 90.0, 90.0, 120.0)),
    ("R -3:R", "3R", (5.7, 5.7, 5.7, 62.0, 62.0, 62.0)),
    ("R -3 m:R", "3mR", (5.7, 5.7, 5.7, 62.0, 62.0, 62.0)),
    ("P -3 m 1", "3m1", (6.1, 6.1, 4.3, 90.0, 90.0, 120.0)),
    ("P -3 1 m", "31m", (6.1, 6.1, 4.3, 90.0, 90.0, 120.0)),
    ("P 6/m", "6/m", (6.1, 6.1, 4.3, 90.0, 90.0, 120.0)),
    ("P 63/m m c", "6/mmm", (6.1, 6.1, 4.3, 90.0, 90.0, 120.0)),
    ("P m -3", "m3", (6.1, 6.1, 6.1, 90.0, 90.0, 90.0)),
    ("I a -3 d", "m3m", (12.1, 12.1, 12.1, 90.0, 90.0, 90.0)),
    ("F m -3 m", "m3m", (8.1, 8.1, 8.1, 90.0, 90.0, 90.0)),
]


def _partition(groups) -> set[frozenset[int]]:
    return {frozenset(g) for g in groups}


def _gsas2_partition(laue, hkl) -> set[frozenset[int]]:
    parent = list(range(len(hkl)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, j in itertools.combinations(range(len(hkl)), 2):
        if _gsas2_rule(laue, hkl[i], hkl[j]):
            parent[find(j)] = find(i)
    out: dict[int, set[int]] = {}
    for i in range(len(hkl)):
        out.setdefault(find(i), set()).add(i)
    return {frozenset(s) for s in out.values() if len(s) >= 2}


@pytest.mark.parametrize(("symbol", "laue", "cell"), CASES,
                         ids=[c[0].replace(" ", "") for c in CASES])
def test_the_detection_reproduces_gsas2_identities_on_each_laue_class(symbol, laue, cell):
    refl = generate_reflections(symbol, cell, 1.0, two_theta_max=110.0)
    hkl = [tuple(int(v) for v in h) for h in refl.hkl]
    ours = _partition(lattice_coincidences(symbol, refl.hkl))
    if _gsas2_rule(laue, (1, 0, 0), (0, 1, 0)) is None:
        # GSAS-II ties these classes only by a d tolerance; no identity holds
        assert ours == set()
    else:
        assert ours == _gsas2_partition(laue, hkl)
        assert ours, f"{symbol}: expected lattice coincidences within 110 deg"


def _random_allowed_cell(symbol, rng) -> tuple[float, ...]:
    """A cell drawn at random inside the setting's metric, from
    :func:`cell_constraints` (the package's one authority for cell ties)."""
    cons = cell_constraints(as_group(symbol))
    cell = {"a": rng.uniform(4, 9), "b": rng.uniform(4, 9), "c": rng.uniform(4, 9),
            "alpha": rng.uniform(70, 110), "beta": rng.uniform(70, 110),
            "gamma": rng.uniform(70, 110)}
    for dep, src in cons.ties.items():
        cell[dep] = cell[src]
    cell.update(cons.fixed_angles)
    return tuple(cell[k] for k in ("a", "b", "c", "alpha", "beta", "gamma"))


def _d(hkl, cell) -> np.ndarray:
    from rietx.crystallography.lattice import d_spacings
    return np.asarray(d_spacings(np.asarray(hkl, dtype=float), *cell))


@pytest.mark.parametrize(("symbol", "laue", "cell"), CASES,
                         ids=[c[0].replace(" ", "") for c in CASES])
def test_the_groups_are_exactly_the_d_classes_of_a_random_allowed_cell(symbol, laue, cell):
    """At a random cell of the setting, equal d (to 1e-11) is the partition."""
    rng = np.random.default_rng(7)
    refl = generate_reflections(symbol, cell, 1.0, two_theta_max=110.0)
    ours = _partition(lattice_coincidences(symbol, refl.hkl))
    for _ in range(3):
        d = _d(refl.hkl, _random_allowed_cell(symbol, rng))
        order = np.argsort(d)
        classes, run = set(), [int(order[0])]
        for a, b in zip(order[:-1], order[1:]):
            if abs(d[b] - d[a]) <= 1e-11 * d[a]:
                run.append(int(b))
            else:
                if len(run) >= 2:
                    classes.add(frozenset(run))
                run = [int(b)]
        if len(run) >= 2:
            classes.add(frozenset(run))
        assert classes == ours


def test_the_textbook_cubic_and_tetragonal_pairs():
    cubic = np.array([[3, 3, 3], [5, 1, 1], [4, 1, 0], [3, 2, 2]])
    groups = lattice_coincidences("P m -3 m", cubic)
    # 333/511 (27) and 410/322 (17)
    assert _partition(groups) == {frozenset({0, 1}), frozenset({2, 3})}
    tetra = np.array([[2, 1, 0], [1, 2, 0], [2, 1, 1]])
    assert _partition(lattice_coincidences("P 4/m", tetra)) == {frozenset({0, 1})}
    # under 4/mmm, 120 is 210's symmetry equivalent: no reflection list holds both
    assert lattice_coincidences("P m m m", tetra) == []
