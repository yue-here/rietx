"""Quantitative phase analysis (QPA) from refined Rietveld scales.

Weight fractions follow the scale-factor relation of Hill & Howard (1987),
J. Appl. Cryst. 20, 467 (see also Bish & Howard 1988, J. Appl. Cryst. 21, 86):
for phase ``p`` with refined scale ``S_p``,

    W_p = S_p·(Z·M·V)_p / Σ_q S_q·(Z·M·V)_q

with Z the formula units per cell, M the formula mass, V the cell volume.  All
three are derived from the refined model — the point of this package is to
remove the GUI-era ritual of typing Z·M·V by hand.  Occupancies enter the mass
(a partly-occupied site weighs less), so the cell mass Z·M is computed from the
*refined* occupancies, not a formula string.

The load-bearing, unambiguous quantity is the **cell mass** Z·M =
Σ_atoms occ·multiplicity·atomic_weight; the Z/M split is a display convenience
recovered by reducing the cell composition to integer formula units, and QPA
never depends on it (weight fractions use Z·M·V directly).

Scope: these are fractions of the **modelled crystalline** content.  An
unmodelled amorphous fraction or a missing phase still makes them sum to 1.
Internal-standard / amorphous quantification is fenced to v2.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

import gemmi
import numpy as np

from ..crystallography.lattice import cell_volume
from ..crystallography.symmetry import expand_positions, get_spacegroup
from ..schemas.results import PhaseQuantity, QuantitativePhaseAnalysis
from ..schemas.structure import Structure

_ELEMENT_RE = re.compile(r"^([A-Za-z]+)")


def element_symbol(species: str) -> str:
    """Element symbol from a scattering-species string (``"Fe3+"`` → ``"Fe"``).

    Takes the leading alphabetic run, then resolves it to a real element by
    trying the two-letter prefix before the one-letter one against gemmi's
    table.  A plain greedy two-letter parse mis-reads the valence-labelled
    species that are legal Waasmaier-Kirfel keys — ``"Cval"`` would become the
    non-element ``"Cv"``; here it falls back to ``"C"``, while ``"Siva"`` →
    ``"Si"`` and ``"Fe3+"`` → ``"Fe"`` resolve directly.  The ionic charge is
    irrelevant to the atomic mass.
    """
    m = _ELEMENT_RE.match(species.strip())
    if m is None:
        raise ValueError(f"cannot parse an element from species {species!r}")
    letters = m.group(1)
    for n in (2, 1):
        if len(letters) >= n:
            candidate = letters[:n].capitalize()
            if gemmi.Element(candidate).atomic_number != 0:
                return candidate
    raise ValueError(f"unrecognised element in species {species!r}")


def atomic_weight(species: str) -> float:
    """Standard atomic weight (g/mol) for a scattering species, via gemmi.

    gemmi carries the IUPAC standard atomic weights.  :func:`element_symbol`
    has already rejected any symbol gemmi maps to its placeholder element "X"
    (atomic number 0, weight 1.0), so a wrong-mass phase can never silently
    poison the QPA ratio.
    """
    return float(gemmi.Element(element_symbol(species)).weight)


@dataclass(frozen=True)
class ZMV:
    """Cell-mass / volume factors for one phase.

    ``cell_mass`` (= Z·M) and ``cell_volume`` are unambiguous; ``z`` and
    ``molar_mass`` are the best-effort integer-formula-unit split (``z`` = 1,
    ``molar_mass`` = ``cell_mass`` when the composition does not reduce to
    integers, e.g. under refined partial occupancy).
    """

    cell_mass: float      # Z·M, g/mol per unit cell (occupancy-weighted)
    cell_volume: float    # V, Å³
    zmv: float            # cell_mass · V
    z: int                # formula units per cell (>= 1)
    molar_mass: float     # M = cell_mass / z, g/mol per formula unit


def _formula_units(element_counts: dict[str, float], *, tol: float = 0.02) -> int:
    """Formula units per cell = GCD of the integer per-element cell counts.

    Returns 1 when any element count is not within ``tol`` of a positive
    integer (partial occupancy / solid solution), i.e. the composition does
    not reduce and the whole cell is treated as one formula unit.
    """
    integers = []
    for count in element_counts.values():
        rounded = round(count)
        if rounded <= 0 or abs(count - rounded) > tol:
            return 1
        integers.append(rounded)
    if not integers:
        return 1
    z = integers[0]
    for n in integers[1:]:
        z = math.gcd(z, n)
    return max(z, 1)


def phase_zmv(space_group: str, cell: tuple[float, float, float, float, float, float],
              atoms, multiplicities=None) -> ZMV:
    """Z·M·V factors for one phase.

    ``atoms`` is an iterable of ``(species, x, y, z, occ)`` for the
    asymmetric-unit atoms; each atom's cell contribution is
    ``occ · multiplicity``.

    ``multiplicities`` (one per atom, in order) supplies the site
    multiplicities directly — pass the counts frozen on the compiled model
    (``len(PhaseSites.ops[j][0])``) so QPA uses exactly the orbit the forward
    model used.  When omitted they are recomputed from the coordinates via
    :func:`crystallography.symmetry.expand_positions`; that path must only be
    fed coordinates that are genuinely on their site, because an atom refined
    to within the dedup tolerance of a special position would otherwise
    collapse its orbit and mis-weigh the cell.
    """
    sg = get_spacegroup(space_group) if multiplicities is None else None
    volume = cell_volume(*cell)
    cell_mass = 0.0
    element_counts: dict[str, float] = {}
    for idx, (species, x, y, z, occ) in enumerate(atoms):
        if multiplicities is not None:
            multiplicity = int(multiplicities[idx])
        else:
            multiplicity = len(expand_positions(sg, np.array([x, y, z], dtype=np.float64)))
        count = float(occ) * multiplicity
        cell_mass += count * atomic_weight(species)
        sym = element_symbol(species)
        element_counts[sym] = element_counts.get(sym, 0.0) + count
    z_units = _formula_units(element_counts)
    molar_mass = cell_mass / z_units if z_units else cell_mass
    return ZMV(cell_mass=cell_mass, cell_volume=volume, zmv=cell_mass * volume,
               z=z_units, molar_mass=molar_mass)


def weight_fractions(k, scales, scale_cov=None):
    """Weight fractions and their esds from refined scales.

    ``k`` is the per-phase Z·M·V, ``scales`` the refined phase scales; W_p =
    S_p·k_p / Σ_q S_q·k_q.  When ``scale_cov`` (the physical covariance of the
    scales, in phase order) is given, propagate it through the ratio:

        ∂W_p/∂S_j = (k_p·δ_pj − W_p·k_j) / D,   D = Σ_q S_q·k_q
        Cov(W) = J · Cov(S) · Jᵀ

    Returns ``(W, sigma_corr, sigma_indep)`` where ``sigma_indep`` uses only
    the covariance diagonal — the naïve independent-scale propagation, returned
    so callers can show that the correlated path genuinely differs.  Both esds
    are ``None`` when ``scale_cov`` is ``None`` or carries no variance (no scale
    was freed) — an all-zero block is absence of information, not σ(W) = 0.
    """
    k = np.asarray(k, dtype=np.float64)
    scales = np.asarray(scales, dtype=np.float64)
    a = scales * k
    total = a.sum()
    if total <= 0.0:
        raise ValueError("phase scales give a non-positive scaled total "
                         f"(Σ S·ZMV = {total}); cannot form weight fractions")
    w = a / total
    if scale_cov is None:
        return w, None, None
    cov = np.asarray(scale_cov, dtype=np.float64)
    if not np.any(cov):
        return w, None, None
    jac = (np.diag(k) - np.outer(w, k)) / total
    cov_w = jac @ cov @ jac.T
    sigma_corr = np.sqrt(np.maximum(np.diag(cov_w), 0.0))
    cov_w_indep = jac @ np.diag(np.diag(cov)) @ jac.T
    sigma_indep = np.sqrt(np.maximum(np.diag(cov_w_indep), 0.0))
    return w, sigma_corr, sigma_indep


def compute_qpa(structure: Structure, values: dict[str, float],
                scale_cov=None, multiplicities=None) -> QuantitativePhaseAnalysis:
    """Assemble the per-phase QPA rows from a decoded parameter dict.

    ``values`` is the physical value dict from ``ParameterTable.decode`` (refined
    cell, occupancies and scales); ``scale_cov`` is the physical covariance of
    the phase scales in phase order (``None`` when no esds were estimated).
    ``multiplicities`` (one list per phase, one entry per atom) should be the
    site multiplicities frozen on the compiled model, so QPA counts the same
    orbits the forward model did rather than re-deriving them from refined
    coordinates that may have drifted near a special position.
    """
    zmvs, scales = [], []
    for ip, phase in enumerate(structure.phases):
        base = f"phases.{ip}"
        cell = tuple(values[f"{base}.cell.{n}"]
                     for n in ("a", "b", "c", "alpha", "beta", "gamma"))
        atoms = [(atom.species,
                  values[f"{base}.atoms.{j}.x"], values[f"{base}.atoms.{j}.y"],
                  values[f"{base}.atoms.{j}.z"], values[f"{base}.atoms.{j}.occ"])
                 for j, atom in enumerate(phase.atoms)]
        mult = multiplicities[ip] if multiplicities is not None else None
        zmvs.append(phase_zmv(phase.space_group, cell, atoms, multiplicities=mult))
        scales.append(values[f"{base}.scale"])
    w, sigma_corr, _ = weight_fractions([z.zmv for z in zmvs], scales, scale_cov)
    rows = [
        PhaseQuantity(
            name=phase.name,
            weight_fraction=float(w[ip]),
            weight_fraction_stderr=(float(sigma_corr[ip]) if sigma_corr is not None
                                    else None),
            scale=float(scales[ip]),
            z=zmvs[ip].z, molar_mass=zmvs[ip].molar_mass,
            cell_mass=zmvs[ip].cell_mass, cell_volume=zmvs[ip].cell_volume,
            zmv=zmvs[ip].zmv,
        )
        for ip, phase in enumerate(structure.phases)
    ]
    return QuantitativePhaseAnalysis(phases=rows)
