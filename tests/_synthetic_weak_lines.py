"""Synthetic patterns whose weak lines decide the indexing answer (WP-2078 task 2).

Three builders, each drawn by the package's own forward model
(``Refinement.predict``) with Poisson counting noise from a fixed seed, so a
test rebuilds the same pattern every run and no data file is read:

* :func:`weak_second_phase` (a): a host with a trace second phase, whose lines
  sit below 1 % of the host's strongest line and still pass the picker's
  significance screen.  The weak lines are *not* the host's.
* :func:`weak_superlattice` (b): a host whose weak lines are its own, the
  ordering reflections of a superlattice.  The supercell is the truth, and the
  subcell is what a search loses it to.
* :func:`planted_silicon` (c): WP-1969's synthetic Si (issue #933) with twelve
  Gaussian lines planted at 1-5 % of the strongest.

Each returns a :class:`WeakLineFixture`: the pattern, the instrument it was
drawn with, the picked list, the true lattice, and where the weak lines are.
:func:`floored` cuts a picked list at a fraction of its strongest usable line,
the treatment issue #1291 measured, for the tests that compare the two.

Every structure is public or idealised; no number here comes from a measured
pattern.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field

import numpy as np

import rietx as rx
from rietx.indexing.engines import weak_line_floor
from rietx.schemas.indexing import PeakList

#: the synchrotron wavelength of WP-1969's Si reproducer, used for all three
LAM = 0.825739


@dataclass(frozen=True)
class WeakLineFixture:
    """One synthetic pattern and what is true about it."""

    name: str
    data: rx.PatternData
    instrument: rx.Instrument
    peaks: PeakList
    #: the true lattice, as ``rank_of_lattice`` reads it: conventional cell
    cell: tuple[float, ...]
    centring: str
    two_theta_range: tuple[float, float]
    #: 2θ of the lines the host does not own (a, c) or of the ordering lines (b)
    weak_two_theta: tuple[float, ...] = field(default_factory=tuple)


def _cif(name: str, sg_number: int, hm: str, cell, atoms) -> str:
    a, b, c, al, be, ga = cell
    rows = "".join(f"{lab} {el} {x} {y} {z} {occ} {biso}\n"
                   for lab, el, x, y, z, occ, biso in atoms)
    return (f"data_{name}\n_cell_length_a {a}\n_cell_length_b {b}\n"
            f"_cell_length_c {c}\n_cell_angle_alpha {al}\n_cell_angle_beta {be}\n"
            f"_cell_angle_gamma {ga}\n_space_group_IT_number {sg_number}\n"
            f"_symmetry_space_group_name_H-M '{hm}'\nloop_\n_atom_site_label\n"
            "_atom_site_type_symbol\n_atom_site_fract_x\n_atom_site_fract_y\n"
            "_atom_site_fract_z\n_atom_site_occupancy\n_atom_site_B_iso_or_equiv\n"
            + rows)


def _structure(cif: str) -> rx.Structure:
    with tempfile.NamedTemporaryFile("w", suffix=".cif", delete=False) as f:
        f.write(cif)
    try:
        return rx.Structure.from_cif(f.name)
    finally:
        os.unlink(f.name)


def _instrument() -> rx.Instrument:
    """WP-1969's synchrotron line shape (#916's tuned profile), f₀ only.

    Dispersion is declared off rather than inherited, so a change of the
    default cannot move the pattern a recorded rank was measured on.
    """
    ins = rx.Instrument.debye_scherrer(wavelength=LAM)
    ins.profile.w.value, ins.profile.u.value, ins.profile.x.value = 3e-4, 5e-4, 5e-3
    ins.source.dispersion = None
    return ins


def _profile(cif: str, ins: rx.Instrument, tt: np.ndarray) -> np.ndarray:
    s = _structure(cif)
    return np.asarray(rx.Refinement(s, ins, history=False).predict(two_theta=tt))


def _counts(y: np.ndarray, tt: np.ndarray, background: float,
            seed: int) -> rx.PatternData:
    obs = np.random.default_rng(seed).poisson(y + background).astype(float)
    return rx.PatternData(two_theta=list(tt), intensity=list(obs),
                          sigma=list(np.sqrt(np.maximum(obs, 1.0))))


def _lines(cif: str, two_theta_range) -> np.ndarray:
    from rietx.crystallography.symmetry import generate_reflections

    s = _structure(cif)
    ph = s.phases[0]
    cell = tuple(float(getattr(ph.cell, k).value)
                 for k in ("a", "b", "c", "alpha", "beta", "gamma"))
    refl = generate_reflections(ph.space_group, cell, LAM, two_theta_range[1])
    tt = np.degrees(2.0 * np.arcsin(LAM / (2.0 * np.asarray(refl.d))))
    tt = np.unique(np.round(tt, 4))
    return tt[(tt >= two_theta_range[0]) & (tt <= two_theta_range[1])]


def floored(peaks: PeakList, fraction: float) -> PeakList:
    """``peaks`` cut to its usable lines at or above ``fraction`` of the strongest.

    Issue #1291's treatment, as a list: every usable line whose intensity is at
    least ``fraction`` × the strongest usable line's, and nothing else.  On a
    position-only list (one intensity everywhere) it removes nothing.
    """
    return weak_line_floor(peaks, fraction)


def _grid(lo: float, hi: float) -> np.ndarray:
    return np.round(np.arange(lo - 0.012, hi + 2.0, 0.004), 3)


def _pick(name, data, ins, rng_tt, cell, centring, weak) -> WeakLineFixture:
    peaks = rx.pick_peaks(data, ins, two_theta_range=rng_tt)
    return WeakLineFixture(name=name, data=data, instrument=ins, peaks=peaks,
                           cell=tuple(float(v) for v in cell),
                           centring=centring, two_theta_range=rng_tt,
                           weak_two_theta=tuple(float(t) for t in weak))


# ----------------------------------------------------------------------------
# (c) WP-1969's synthetic Si with twelve planted lines
# ----------------------------------------------------------------------------
A_SI = 5.4311
SI_CIF = _cif("Si", 227, "F d -3 m", (A_SI,) * 3 + (90.0,) * 3,
              [("Si1", "Si", 0.125, 0.125, 0.125, 1.0, 0.5)])
SI_RANGE = (12.1, 60.0)


def planted_silicon(seed: int = 1, plant_seed: int = 7,
                    n_planted: int = 12) -> WeakLineFixture:
    """Si (F d -3 m, a = 5.4311 Å) at λ 0.8257 Å, 12.1-60°, with ``n_planted``
    Gaussian lines (FWHM 0.025°) at 1-5 % of the strongest line's height.

    Issue #933's reproducer as PR #951's spike built it: the same structure,
    profile, counts (1.3e6 on the strongest line over 7700 background) and the
    same planted positions and heights (``plant_seed``).  One Poisson draw
    (``seed``) over the sum, where the spike drew twice.
    """
    ins = _instrument()
    tt = _grid(*SI_RANGE)
    y = _profile(SI_CIF, ins, tt)
    y = y / y.max() * 1.3e6
    rng = np.random.default_rng(plant_seed)
    planted = np.sort(rng.uniform(13.0, 58.0, n_planted))
    for p in planted:
        y = y + (0.01 + 0.04 * rng.random()) * 1.3e6 * np.exp(
            -4.0 * np.log(2.0) * (tt - p) ** 2 / 0.025 ** 2)
    data = _counts(y, tt, 7700.0, seed)
    return _pick("planted_silicon", data, ins, SI_RANGE, (A_SI,) * 3 + (90.0,) * 3,
                 "F", planted)


# ----------------------------------------------------------------------------
# (a) a host with a trace second phase
# ----------------------------------------------------------------------------
A_MO = 3.1470
#: molybdenum (I m -3 m), the host; an idealised cell at the room-temperature value
MO_CIF = _cif("Mo", 229, "I m -3 m", (A_MO,) * 3 + (90.0,) * 3,
              [("Mo1", "Mo", 0.0, 0.0, 0.0, 1.0, 0.3)])
#: α-MoO₃ (P b n m), the trace phase an oxidised molybdenum powder carries:
#: cell and sites from Sitepu, O'Connor & Li (2005), *J. Appl. Cryst.* 38,
#: 158-167 (doi:10.1107/S0021889804031231; COD 9009669), B = 8π²·U_iso
MOO3_CIF = _cif("MoO3", 62, "P b n m", (3.9616, 13.856, 3.6978, 90.0, 90.0, 90.0),
                [("Mo1", "Mo", 0.073, 0.101, 0.25, 1.0, 2.2),
                 ("O1", "O", 0.544, 0.426, 0.25, 1.0, 2.0),
                 ("O2", "O", 0.615, 0.091, 0.25, 1.0, 2.1),
                 ("O3", "O", 0.053, 0.223, 0.25, 1.0, 0.9)])
HOST_RANGE = (12.1, 55.0)


def weak_second_phase(trace: float = 0.006, seed: int = 3,
                      two_theta_range: tuple[float, float] = HOST_RANGE,
                      ) -> WeakLineFixture:
    """Molybdenum with an α-MoO₃ trace whose strongest line is ``trace`` × the host's.

    Both phases are drawn by ``predict`` with one instrument and summed, each
    normalised to its own strongest line, so ``trace`` is the ratio of the two
    phases' strongest peak heights: 0.006 puts every oxide line under a 1 %
    floor.  The range is 12.1-55°, narrowed from 12.1-60° so a search finishes
    well inside the whole-run ceiling.  The host owns six lines in it (a cubic
    search needs five), so with
    the trace at the default the foreign lines outnumber the host's on the
    picked list.  Counts
    and background as :func:`planted_silicon`.
    """
    ins = _instrument()
    tt = _grid(*two_theta_range)
    host = _profile(MO_CIF, ins, tt)
    imp = _profile(MOO3_CIF, ins, tt)
    y = (host / host.max() + trace * imp / imp.max()) * 1.3e6
    data = _counts(y, tt, 7700.0, seed)
    host_lines = _lines(MO_CIF, two_theta_range)
    weak = np.array([t for t in _lines(MOO3_CIF, two_theta_range)
                     if np.min(np.abs(host_lines - t)) > 0.05])
    return _pick("weak_second_phase", data, ins, two_theta_range,
                 (A_MO,) * 3 + (90.0,) * 3, "I", weak)


# ----------------------------------------------------------------------------
# (b) a superlattice host whose weak lines are its own
# ----------------------------------------------------------------------------
A_DP = 7.8862
SUB_RANGE = (8.0, 60.0)


def _double_perovskite(antisite: float) -> str:
    """Idealised B-site-ordered Sr₂FeMoO₆ (F m -3 m, a = 2·a_p).

    ``antisite`` is the fraction of each B site held by the other cation; the
    ordering reflections (h, k, l all odd) scale as (1 − 2·antisite)², and at
    0.5 the cell is the cubic perovskite subcell.  O sits at the ideal x = 1/4,
    so the ordering lines are the B-site contrast alone.  Idealised: the real
    compound is tetragonal, and nothing here is a refined structure.
    """
    s = antisite
    return _cif("dp", 225, "F m -3 m", (A_DP,) * 3 + (90.0,) * 3, [
        ("Sr1", "Sr", 0.25, 0.25, 0.25, 1.0, 0.6),
        ("Fe1", "Fe", 0.0, 0.0, 0.0, 1.0 - s, 0.4),
        ("Mo1", "Mo", 0.0, 0.0, 0.0, s, 0.4),
        ("Mo2", "Mo", 0.5, 0.5, 0.5, 1.0 - s, 0.4),
        ("Fe2", "Fe", 0.5, 0.5, 0.5, s, 0.4),
        ("O1", "O", 0.25, 0.0, 0.0, 1.0, 0.7)])


def weak_superlattice(antisite: float = 0.1, seed: int = 5,
                      two_theta_range: tuple[float, float] = SUB_RANGE,
                      ) -> WeakLineFixture:
    """A partly ordered double perovskite: the supercell F 2·a_p is the truth.

    Its ordering reflections (h, k, l all odd) are the weak lines, structural
    and the host's own; ``antisite`` sets how weak.  At the default 0.1 the
    strongest, (111), is about 2.3 % of the strongest line and the rest sit
    between 0.1 and 1.4 %, so the 0.5, 1 and 2 % floors each remove some.
    Counts and background as :func:`planted_silicon`.
    """
    ins = _instrument()
    tt = _grid(*two_theta_range)
    cif = _double_perovskite(antisite)
    y = _profile(cif, ins, tt)
    data = _counts(y / y.max() * 1.3e6, tt, 7700.0, seed)
    all_lines = _lines(cif, two_theta_range)
    d = LAM / (2.0 * np.sin(np.radians(all_lines / 2.0)))
    hkl2 = (A_DP / d) ** 2
    # h, k, l all odd ⇔ h² + k² + l² ≡ 3 (mod 8)
    weak = all_lines[(np.abs(hkl2 - np.round(hkl2)) < 1e-3)
                     & (np.round(hkl2).astype(int) % 8 == 3)]
    return _pick("weak_superlattice", data, ins, two_theta_range,
                 (A_DP,) * 3 + (90.0,) * 3, "F", weak)
