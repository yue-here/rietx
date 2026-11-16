"""Observed and difference Fourier maps of a converged Rietveld fit (WP-1901).

The first rung of structure solution a user sees: what the pattern says the
density is, against what the model says, on the model's own phases.  A free
function over a fitted :class:`~rietx.refine.Refinement`, not a method on it.

**The coefficients.**  The magnitudes are the McCusker et al. (1999), J. Appl.
Cryst. 32, 36, §6 "observed" intensities
:meth:`~rietx.model.forward.CompiledModel.structure_intensity_partition`
returns, I_obs = m·|F_obs|², and their calculated twins I_calc = m·⟨|F|²⟩, so

    |F_obs,k| = √(I_obs,k / m_k),      |F_calc,k| = √(I_calc,k / m_k).

The phases are the model's: φ(h) = arg A(h), A the real-amplitude sum of
:func:`~rietx.crystallography.structure_factor.structure_factors_ab`, computed
for **every member** of each reflection's Laue orbit, Friedel mates included
(:func:`~rietx.crystallography.symmetry.reflection_orbits`), rather than
derived from the representative's phase through the operations' translations.
The maps are the syntheses ρ(r) = (1/V) Σ_h F(h) exp(−2πi h·r) (Coppens, Su &
Becker 2006, *International Tables for Crystallography* Vol. C, ch. 8.7,
eq. 8.7.3.1 in its lattice-sum form; the difference map is their
Table 8.7.3.1's residual map)

    ρ_obs(x) = (1/V) Σ_h |F_obs(h)| e^{iφ(h)} e^{−2πi h·x},
    Δρ(x)    = (1/V) Σ_h (|F_obs(h)| − |F_calc(h)|) e^{iφ(h)} e^{−2πi h·x},

summed by one FFT over a grid fine enough that no index aliases.  F(000) is
left out of both, so each map has zero mean over the cell: the peaks and their
significance do not depend on it, and an absolute density needs a count of the
cell's electrons the fit does not refine.

**The phase convention when f″ ≠ 0.**  The powder pattern carries the Friedel
average ⟨|F|²⟩ = |A|² + |B|² (``structure_factor``'s module docstring), and a
Fourier coefficient needs one phase.  This module takes arg A, the phase of the
dispersion-free part including f′, and the magnitude √⟨|F|²⟩.  It is exact
when the source declares no dispersion (B is ``None``).  Otherwise A and B are
both complex, so arg A differs from arg (A + iB) by up to asin(|B|/|A|) while
|B| < |A|, and without bound past it; arg A is then the phase of
½(F(h) + F(−h)*), the Friedel-averaged coefficient a real map is built from.
:attr:`FourierMaps.phase_convention` states which held.

**Model bias.**  I_obs is I_calc times the reflection's own observed/calculated
count ratio, and the phases are the model's, so both maps lean towards the
model that made them.  A missing atom still shows, attenuated, because the
counts it scatters are in the data; a wrong atom is pulled towards looking
right.  Every map carries that caveat (:attr:`FourierMaps.caveats`), and a map
is never evidence for the fit that partitioned it: a peak is a place to look,
and the evidence for an atom placed there is the refit with it.

**Significance.**  Each peak's height over σ, the root-mean-square of the map
over the cell.  That σ is the map's own spread, signal and noise together, so
on a difference map with a large real peak it understates that peak's
significance.  It is not a counting-statistics esd, and it is not a bar: the
complete 11-BM NAC model leaves difference peaks to about 5σ of its own map
(WP-1901's handover), so what significance an atom needs is the reader's call.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import numpy as np

from ..crystallography.lattice import cell_volume, d_spacings, direct_metric_tensor
from ..crystallography.structure_factor import structure_factors_ab
from ..crystallography.symmetry import expand_positions, reflection_orbits, resolve_group

if TYPE_CHECKING:
    from ..model.forward import CompiledModel
    from ..refine import Refinement
    from ..schemas.structure import Structure

_CELL_KEYS = ("a", "b", "c", "alpha", "beta", "gamma")


@dataclass(frozen=True)
class MapPeak:
    """One local extremum of a map, one per orbit under the space group.

    ``xyz`` is fractional, refined between grid points by a parabola through
    each axis's three points; ``height`` is the map there, in the map's units;
    ``significance`` is ``height / sigma`` of the map it came from (negative
    for a hole).  ``nearest_atom`` and ``nearest_distance`` (Å) name the
    closest image of any model atom, over every symmetry and lattice image.
    """

    xyz: tuple[float, float, float]
    height: float
    significance: float
    nearest_atom: str | None
    nearest_distance: float | None


@dataclass(frozen=True)
class FourierMap:
    """One synthesis on the grid, with its σ and its extrema.

    ``grid`` is (n_a, n_b, n_c); point (i, j, k) sits at fractional
    (i/n_a, j/n_b, k/n_c).  ``sigma`` is its root-mean-square over the cell,
    the unit of every ``significance``.  ``peaks`` are the maxima above zero,
    highest first; ``holes`` the minima below zero, deepest first.  Neither is
    thresholded: a significance cut is the reader's (WP-1901).  ``n_merged``
    counts the extrema left out of the two lists as lying within one grid
    spacing of an image of a stronger one kept.
    """

    kind: Literal["observed", "difference"]
    grid: np.ndarray
    sigma: float
    peaks: tuple[MapPeak, ...]
    holes: tuple[MapPeak, ...]
    n_merged: int


@dataclass(frozen=True)
class FourierMaps:
    """The observed and difference maps of one phase, and what they rest on.

    ``d_min`` (Å) is the shortest d among the reflections used, which sets
    the maps' resolution; ``grid_step`` (Å) the largest spacing of the grid
    the maps were drawn on, which the no-aliasing rule may make finer than
    the step asked for; ``n_reflections`` counts the unique reflections with
    an observed share, ``n_unobserved`` those the partition could give none
    (no profile in the fitted range), left out of both maps.  ``units`` is
    e/Å³ for X-rays and fm/Å³ for neutrons.
    """

    phase: str
    space_group: str
    cell: tuple[float, float, float, float, float, float]
    observed: FourierMap
    difference: FourierMap
    d_min: float
    grid_step: float
    n_reflections: int
    n_unobserved: int
    units: str
    phase_convention: str
    caveats: tuple[str, ...]


def fourier_maps(refinement: Refinement, phase: int = 0, *,
                 grid_step: float | None = None) -> FourierMaps:
    """Observed and difference Fourier maps of ``phase`` at the last fit's answer.

    The refinement must have run a Rietveld fit: the observed magnitudes are
    the partition of the data by the structural model, which a Le Bail or
    Pawley fit has none of.  ``grid_step`` (Å) is the largest spacing between
    grid points along each axis; ``None`` takes a third of ``d_min``, three
    samples across the shortest fringe the data resolve.  The grid is enlarged
    beyond that wherever needed so that no reflection index aliases.
    """
    model = getattr(refinement, "_model", None)
    answer = getattr(refinement, "_answer", None)
    if model is None or answer is None:
        raise RuntimeError("fourier_maps needs a fitted Refinement: call fit() first")
    return fourier_maps_from_model(model, answer["values"], answer["structure"],
                                   phase, grid_step=grid_step)


def fourier_maps_from_model(model: CompiledModel, values: dict[str, float],
                            structure: Structure, phase: int = 0, *,
                            grid_step: float | None = None) -> FourierMaps:
    """:func:`fourier_maps` over a compiled model and decoded values.

    ``structure`` supplies the phase's name and atom labels, and must be the
    structure ``values`` describe.
    """
    if model.mode != "rietveld":
        raise ValueError(
            "a Fourier map needs the structural model's partition of the data; "
            f"this model's mode is {model.mode!r}, which carries no phases")
    if not 0 <= phase < len(model.phases):
        raise IndexError(f"phase {phase} is out of range: the model has "
                         f"{len(model.phases)}")
    cp = model.phases[phase]
    refl = cp.reflections
    if refl.satellite_order is not None or cp.magnetic is not None \
            or cp.nuclear_mask is not None:
        raise NotImplementedError(
            "a Fourier map of a magnetic or modulated phase is not built: its "
            "intensities carry a magnetic or satellite term the nuclear phases "
            "do not describe")
    if grid_step is not None and not grid_step > 0.0:
        raise ValueError(f"grid_step must be positive, got {grid_step!r}")

    cell = tuple(float(values[f"phases.{phase}.cell.{k}"]) for k in _CELL_KEYS)
    i_obs, i_calc = model.structure_intensity_partition(values)[phase]
    mult = np.asarray(refl.multiplicity, dtype=np.float64)
    live = np.isfinite(i_obs) & np.isfinite(i_calc)
    if not np.any(live):
        raise ValueError("no reflection of this phase has an observed share")
    f_obs = np.sqrt(np.maximum(i_obs[live], 0.0) / mult[live])
    f_calc = np.sqrt(np.maximum(i_calc[live], 0.0) / mult[live])
    hkl = np.asarray(refl.hkl, dtype=np.int64)[live]
    d = np.asarray(d_spacings(hkl, *cell), dtype=np.float64)
    d_min = float(d.min())

    group = resolve_group(refl.spacegroup, refl.operations)
    orbits = reflection_orbits(group, hkl)
    sizes = np.array([len(o) for o in orbits])
    members = np.concatenate(orbits)
    d_members = np.repeat(d, sizes)
    xyz, occ, biso, uaniso, astar = model._site_values(phase, values, cell)
    a_part, b_part = structure_factors_ab(members, d_members, cp.sites, xyz, occ,
                                          biso, uaniso, astar)
    unit_phase = np.exp(1j * np.angle(np.asarray(a_part)))
    coeff_obs = np.repeat(f_obs, sizes) * unit_phase
    coeff_diff = np.repeat(f_obs - f_calc, sizes) * unit_phase

    lengths = np.array(cell[:3])
    step = d_min / 3.0 if grid_step is None else float(grid_step)
    hmax = np.abs(members).max(axis=0)
    shape = tuple(_fft_size(max(int(np.ceil(lengths[i] / step)), 2 * int(hmax[i]) + 1))
                  for i in range(3))
    volume = float(cell_volume(*cell))
    rho_obs = _synthesis(members, coeff_obs, shape, volume)
    rho_diff = _synthesis(members, coeff_diff, shape, volume)

    atoms = structure.phases[phase].atoms
    sites = [(atoms[j].label, np.asarray(xyz[j], dtype=np.float64))
             for j in range(cp.sites.n_asym)]
    metric = direct_metric_tensor(*cell)
    merge = float(max(lengths[i] / shape[i] for i in range(3)))
    images = _atom_images(group, sites)

    def _map(kind, grid):
        sigma = float(np.sqrt(np.mean(grid * grid)))
        peaks, n_peaks_merged = _extrema(grid, sigma, group, metric, images, merge,
                                         sign=1.0)
        holes, n_holes_merged = _extrema(grid, sigma, group, metric, images, merge,
                                         sign=-1.0)
        return FourierMap(kind=kind, grid=grid, sigma=sigma, peaks=peaks, holes=holes,
                          n_merged=n_peaks_merged + n_holes_merged)

    neutron = cp.sites.b_coh is not None
    dispersive = b_part is not None
    caveats = (
        "model bias: the observed magnitudes are the data partitioned by this "
        "model's calculated profiles, and the phases are this model's, so both "
        "maps lean towards it (McCusker et al. 1999, §6); a peak is a place to "
        "look, never evidence for the fit that partitioned it",
        f"resolution: reflections to d_min = {d_min:.3f} Å, "
        f"{int(live.sum())} with an observed share and "
        f"{int((~live).sum())} without, which are left out of both maps",
        "F(000) is omitted: each map has zero mean over the cell",
    ) + (("negative nuclear density is real for a species with b < 0",)
         if neutron else ())
    return FourierMaps(
        phase=structure.phases[phase].name,
        space_group=str(refl.spacegroup),
        cell=cell,
        observed=_map("observed", rho_obs),
        difference=_map("difference", rho_diff),
        d_min=d_min,
        grid_step=merge,
        n_reflections=int(live.sum()),
        n_unobserved=int((~live).sum()),
        units="fm/Å³" if neutron else "e/Å³",
        phase_convention=(
            "phase of A (f0 + f'), magnitude sqrt(|A|^2 + |B|^2): f'' is declared"
            if dispersive else "phase of F = A: no f'' declared, so exact"),
        caveats=caveats,
    )


def _fft_size(n: int) -> int:
    """The smallest integer ≥ n with no prime factor above 5."""
    while True:
        m = n
        for p in (2, 3, 5):
            while m % p == 0:
                m //= p
        if m == 1:
            return n
        n += 1


def _synthesis(hkl: np.ndarray, coeff: np.ndarray, shape: tuple[int, int, int],
               volume: float) -> np.ndarray:
    """(1/V) Σ_h F(h) e^{−2πi h·x} on the grid, by one forward FFT.

    numpy's ``fftn`` is X[k] = Σ_n x[n] e^{−2πi k·n/N}, so the coefficient of
    index h goes at n = h mod N and the transform is the synthesis at
    x = k/N.  The orbits hold each Friedel pair, so the imaginary part is
    roundoff and is dropped.
    """
    grid = np.zeros(shape, dtype=np.complex128)
    idx = tuple(np.mod(hkl[:, i], shape[i]) for i in range(3))
    np.add.at(grid, idx, coeff)
    return np.fft.fftn(grid).real / volume


def _atom_images(group, sites) -> list[tuple[str, np.ndarray]]:
    """Every orbit image of every model atom, as (label, (m, 3) fractional)."""
    return [(label, np.array(expand_positions(group, x))) for label, x in sites]


def _min_distance(p: np.ndarray, others: np.ndarray, metric: np.ndarray) -> float:
    """Shortest distance (Å) from ``p`` to any lattice image of ``others``."""
    delta = p[None, :] - others
    delta -= np.round(delta)
    shifts = np.array([(i, j, k) for i in (-1, 0, 1) for j in (-1, 0, 1)
                       for k in (-1, 0, 1)], dtype=np.float64)
    trial = delta[:, None, :] + shifts[None, :, :]
    d2 = np.einsum("...i,ij,...j->...", trial, metric, trial)
    return float(np.sqrt(max(d2.min(), 0.0)))


def _extrema(grid: np.ndarray, sigma: float, group, metric: np.ndarray,
             images, merge: float, *, sign: float) -> tuple[tuple[MapPeak, ...], int]:
    """Local maxima of ``sign·grid`` above zero, one per orbit, and how many merged.

    A grid point is an extremum when it is at least its 13 neighbours on the
    lexicographically positive side and exceeds the other 13.  The tie-break
    is not cosmetic: an atom on a mirror or an axis that falls midway between
    two grid points gives those two points the same value to the bit, and a
    strict test on all 26 keeps neither, dropping the atom from the list
    (LaMnO₃'s La1 at y = ¼ on a 54-point b axis, WP-1901's review).
    Each is refined by an axis-wise parabola, then dropped if it lies within
    ``merge`` (Å, one grid spacing) of an image of a stronger one already
    kept: a map with the space group's symmetry repeats each peak over the
    orbit, and the list keeps one.
    """
    g = sign * grid
    is_max = g > 0.0
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            for dk in (-1, 0, 1):
                if di == dj == dk == 0:
                    continue
                other = np.roll(g, (di, dj, dk), axis=(0, 1, 2))
                is_max &= (g >= other) if (di, dj, dk) > (0, 0, 0) else (g > other)
    idx = np.argwhere(is_max)
    order = np.argsort(-g[tuple(idx.T)])
    shape = np.array(grid.shape)
    kept: list[MapPeak] = []
    kept_images: list[np.ndarray] = []
    n_merged = 0
    for row in idx[order]:
        # f(t) = f0 + ½(f₊ − f₋)t + ½(f₋ − 2f0 + f₊)t² per axis: the vertex
        # sits at t* = ½(f₋ − f₊)/(f₋ − 2f0 + f₊) and rises ¼(f₊ − f₋)t*
        frac = np.empty(3)
        height = float(g[tuple(row)])
        height_fit = height
        for axis in range(3):
            lo, hi = row.copy(), row.copy()
            lo[axis] = (lo[axis] - 1) % shape[axis]
            hi[axis] = (hi[axis] + 1) % shape[axis]
            fm, fp = float(g[tuple(lo)]), float(g[tuple(hi)])
            curv = fm - 2.0 * height + fp
            off = 0.5 * (fm - fp) / curv if curv < 0.0 else 0.0
            frac[axis] = (row[axis] + off) / shape[axis]
            height_fit += 0.25 * (fp - fm) * off
        frac = np.mod(frac, 1.0)
        if any(_min_distance(frac, im, metric) < merge for im in kept_images):
            n_merged += 1
            continue
        kept_images.append(np.array(expand_positions(group, frac)))
        label, dist = None, None
        for name, pos in images:
            r = _min_distance(frac, pos, metric)
            if dist is None or r < dist:
                label, dist = name, r
        value = sign * height_fit
        kept.append(MapPeak(xyz=(float(frac[0]), float(frac[1]), float(frac[2])),
                            height=value,
                            significance=value / sigma if sigma > 0.0 else float("nan"),
                            nearest_atom=label, nearest_distance=dist))
    return tuple(kept), n_merged
