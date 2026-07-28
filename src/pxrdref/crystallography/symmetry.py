"""Space-group symmetry via gemmi: operators, absences, unique hkl generation.

gemmi (MPL-2.0, used as a dependency) owns the symbol → operators mapping, the
systematic-absence test, and centring information.  Reflection multiplicities
are computed here by explicit orbit counting under the **Laue** group (the
point group of the diffraction pattern, i.e. the crystal point group plus
inversion), so ±h are always merged into one orbit.

**Merging ±h is exact with or without anomalous scattering, but for two
different reasons — do not "fix" it when dispersion is on.**  Without f″,
|F(h)|² = |F(−h)|² (Friedel's law) and the two are literally the same number.
With f″ they differ in a non-centrosymmetric group, but a powder cannot
separate them either way: d(h) = d(−h), so the pair lands in one peak and what
the peak measures is the *orbit average*.  ``structure_factor`` returns exactly
that average in closed form (⟨|F|²⟩ = |A|² + |B|², see its module docstring),
which is why one representative per Laue orbit remains the correct — not the
approximate — thing to enumerate here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import gemmi
import numpy as np

from .lattice import d_spacings, two_theta_deg


def get_spacegroup(symbol: str) -> gemmi.SpaceGroup:
    """Resolve an H-M symbol (or IT number given as a string) via gemmi."""
    sg = gemmi.find_spacegroup_by_name(symbol)
    if sg is None:
        try:
            sg = gemmi.find_spacegroup_by_number(int(symbol))
        except (ValueError, TypeError):
            sg = None
    if sg is None:
        raise ValueError(f"unknown space group symbol: {symbol!r}")
    return sg


def rotation_matrices(sg: gemmi.SpaceGroup) -> np.ndarray:
    """Integer rotation parts of all symmetry operations, shape (M, 3, 3).

    gemmi stores rotations scaled by Op.DEN (=24).
    """
    ops = sg.operations()
    mats = []
    for op in ops:
        r = np.array(op.rot, dtype=np.float64) / gemmi.Op.DEN
        mats.append(r)
    return np.array(mats)


def expand_positions(sg: gemmi.SpaceGroup, xyz: np.ndarray, *, tol: float = 1e-4
                     ) -> list[np.ndarray]:
    """Orbit of one fractional position under the space group.

    Returns the distinct equivalent positions (each wrapped into [0,1)); the
    orbit length is the site multiplicity.  Coincident images (special
    positions) are deduplicated with tolerance ``tol``.
    """
    ops = sg.operations()
    seen: list[np.ndarray] = []
    for op in ops:
        r = np.array(op.rot, dtype=np.float64) / gemmi.Op.DEN
        t = np.array(op.tran, dtype=np.float64) / gemmi.Op.DEN
        p = (r @ np.asarray(xyz, dtype=np.float64) + t) % 1.0
        dup = False
        for q in seen:
            diff = np.abs(p - q)
            diff = np.minimum(diff, 1.0 - diff)  # periodic distance
            if np.all(diff < tol):
                dup = True
                break
        if not dup:
            seen.append(p)
    return seen


@dataclass
class ReflectionSet:
    """Unique reflections in a d-range, frozen for one refinement stage.

    Attributes
    ----------
    hkl : (N, 3) int array — one representative per orbit.
    multiplicity : (N,) int — orbit size under the Laue group (Friedel incl.).
    d : (N,) float — d-spacings at the cell used for generation (refresh with
        :meth:`update_positions` when the cell moves during refinement).
    """

    hkl: np.ndarray
    multiplicity: np.ndarray
    d: np.ndarray
    spacegroup: str = ""
    extra: dict = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.hkl)

    def two_theta(self, cell: tuple[float, float, float, float, float, float],
                  wavelength: float) -> np.ndarray:
        d = d_spacings(self.hkl, *cell)
        return two_theta_deg(d, wavelength)


def reflection_orbits(sg_symbol: str, hkl_reps: np.ndarray) -> list[np.ndarray]:
    """Distinct symmetry+Friedel equivalents of each representative reflection.

    Returns one ``(m_k, 3)`` integer array per row of ``hkl_reps``, listing the
    Laue-group orbit (Friedel mates included) — the same set ``generate_reflections``
    counts to get the multiplicity, so ``len(orbit) == multiplicity``.  The
    reciprocal-space action is the **transposed** rotation (see the comment in
    ``generate_reflections``); this is the frozen discrete object the
    March-Dollase correction averages over, computed once per stage.
    """
    rots = rotation_matrices(get_spacegroup(sg_symbol))
    rot_int = np.rint(np.transpose(rots, (0, 2, 1))).astype(np.int64)
    orbits: list[np.ndarray] = []
    for h in np.asarray(hkl_reps, dtype=np.int64):
        images = np.einsum("mij,j->mi", rot_int, h)
        images = np.vstack([images, -images])  # Friedel mates
        uniq = sorted({tuple(map(int, im)) for im in images})
        orbits.append(np.array(uniq, dtype=np.int64))
    return orbits


def generate_reflections(sg_symbol: str,
                         cell: tuple[float, float, float, float, float, float],
                         wavelength: float,
                         two_theta_max: float,
                         two_theta_min: float = 0.0) -> ReflectionSet:
    """Enumerate the symmetry-unique, absence-allowed reflections in range.

    Strategy: enumerate all integer hkl in the sphere d ≥ d_min =
    λ/(2 sin(θ_max)), drop systematic absences (gemmi), group the survivors
    into Laue-group orbits (including Friedel mates), and keep one
    representative per orbit with its orbit size as the multiplicity.
    """
    sg = get_spacegroup(sg_symbol)
    ops = sg.operations()

    d_min = wavelength / (2.0 * np.sin(np.radians(two_theta_max / 2.0)))
    a, b, c = cell[0], cell[1], cell[2]
    hmax = int(np.floor(a / d_min)) + 1
    kmax = int(np.floor(b / d_min)) + 1
    lmax = int(np.floor(c / d_min)) + 1

    rng_h = np.arange(-hmax, hmax + 1)
    rng_k = np.arange(-kmax, kmax + 1)
    rng_l = np.arange(-lmax, lmax + 1)
    H, K, L = np.meshgrid(rng_h, rng_k, rng_l, indexing="ij")
    hkl = np.column_stack([H.ravel(), K.ravel(), L.ravel()]).astype(np.int64)
    hkl = hkl[~np.all(hkl == 0, axis=1)]

    d = d_spacings(hkl, *cell)
    keep = d >= d_min * 0.999
    if two_theta_min > 0.0:
        d_max = wavelength / (2.0 * np.sin(np.radians(max(two_theta_min, 1e-3) / 2.0)))
        keep &= d <= d_max * 1.001
    hkl, d = hkl[keep], d[keep]

    # systematic absences via gemmi GroupOps (vectorised where available)
    try:
        absent = np.asarray(ops.systematic_absences(hkl), dtype=bool)
    except (AttributeError, TypeError):
        absent = np.array([ops.is_systematically_absent(list(map(int, h))) for h in hkl])
    hkl, d = hkl[~absent], d[~absent]

    # Laue-group orbits.  A real-space operation x' = Rx + t acts on Miller
    # indices (column form) as h' = Rᵀ h; the orbit therefore uses the
    # transposed rotations.  ({Rᵀ} ≠ {R} as a set outside cubic/orthogonal
    # settings — e.g. trigonal threefold axes — so the transpose matters.)
    # Friedel mates ±h are merged.  Exact with or without anomalous
    # scattering — the powder measures the ±h average and structure_factor
    # returns it in closed form; see the module docstring.
    rots = rotation_matrices(sg)
    rot_int = np.rint(np.transpose(rots, (0, 2, 1))).astype(np.int64)
    canon: dict[tuple[int, int, int], int] = {}
    order: list[tuple[int, int, int]] = []
    counts: dict[tuple[int, int, int], set[tuple[int, int, int]]] = {}
    for h in hkl:
        images = np.einsum("mij,j->mi", rot_int, h)
        images = np.vstack([images, -images])  # Friedel
        keys = [tuple(map(int, im)) for im in images]
        rep = max(keys)  # canonical representative: lexicographically largest
        if rep not in canon:
            canon[rep] = len(order)
            order.append(rep)
            counts[rep] = set()
        counts[rep].update(keys)

    reps = np.array(order, dtype=np.int64)
    mult = np.array([len(counts[tuple(r)]) for r in reps], dtype=np.int64)
    d_reps = d_spacings(reps, *cell)
    sort = np.argsort(-d_reps)  # ascending 2θ = descending d
    return ReflectionSet(hkl=reps[sort], multiplicity=mult[sort], d=d_reps[sort],
                         spacegroup=sg.xhm())
