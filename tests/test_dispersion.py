"""Anomalous scattering f′, f″ (WP-0504).

The load-bearing claim here is not "f becomes complex" — ``F`` was already
complex — it is that a *powder* measures the **Friedel average** of |F|².
``symmetry.generate_reflections`` merges ±h into one orbit and evaluates one
representative, which is exact only while f is real.  So the tests below are
built around structures where that distinction bites:

* **ZnO zincite, ``P 63 m c``** — non-centrosymmetric and polar, and Zn sits
  just *below* its K edge at Cu Kα (f′ ≈ −1.55), which is both the largest
  correction among the round-robin phases and the case where |F(h)|² ≠
  |F(−h)|².  It is the acceptance specimen too (``qarr/zincite.prn``).
* **Corundum ``R -3 c``** — centrosymmetric, where the closed form must
  collapse back to the representative's own |F|² *identically*, with no
  case analysis in the code.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from pxrdref.crystallography.lattice import d_spacings
from pxrdref.crystallography.scattering import f0
from pxrdref.crystallography.structure_factor import (
    compile_phase_sites,
    d_f2_d_uaniso,
    d_f2_d_xyz,
    structure_factors_squared,
)
from pxrdref.crystallography.symmetry import (
    generate_reflections,
    get_spacegroup,
    reflection_orbits,
)
from pxrdref.schemas.common import Parameter
from pxrdref.schemas.structure import AnisoU, Atom, Cell, Phase

#: f′, f″ at Cu Kα1 (International Tables for Crystallography Vol. C,
#: §4.2.6).  Hard-coded here so the structure-factor algebra is tested
#: independently of whatever tabulation ``crystallography.dispersion`` loads.
CU_KA1 = {
    "Zn": complex(-1.5491, 0.6778),
    "O": complex(0.0492, 0.0322),
    "Al": complex(0.2455, 0.2547),
}

ZINCITE_CELL = (3.2499, 3.2499, 5.2066, 90.0, 90.0, 120.0)
CORUNDUM_CELL = (4.7593, 4.7593, 12.9917, 90.0, 90.0, 120.0)


def _cell(cell6) -> Cell:
    a, b, c, al, be, ga = cell6
    return Cell(a=Parameter(value=a, min=0.1), b=Parameter(value=b, min=0.1),
                c=Parameter(value=c, min=0.1), alpha=Parameter(value=al),
                beta=Parameter(value=be), gamma=Parameter(value=ga))


def _atom(label, species, xyz, biso, aniso=None) -> Atom:
    return Atom(label=label, species=species,
                x=Parameter(value=xyz[0]), y=Parameter(value=xyz[1]),
                z=Parameter(value=xyz[2]),
                biso=Parameter(value=biso, min=0.0, max=25.0,
                               vary=aniso is None, unit="A^2"),
                aniso=aniso)


def zincite() -> Phase:
    return Phase(name="zincite", space_group="P 63 m c", cell=_cell(ZINCITE_CELL),
                 atoms=[_atom("Zn", "Zn", (1 / 3, 2 / 3, 0.0), 0.55),
                        _atom("O", "O", (1 / 3, 2 / 3, 0.3826), 0.55)])


def corundum() -> Phase:
    return Phase(name="corundum", space_group="R -3 c", cell=_cell(CORUNDUM_CELL),
                 atoms=[_atom("Al", "Al", (0.0, 0.0, 0.35216), 0.30),
                        _atom("O", "O", (0.30624, 0.0, 0.25), 0.30)])


def _site_arrays(phase: Phase):
    xyz = np.array([[a.x.value, a.y.value, a.z.value] for a in phase.atoms])
    occ = np.array([a.occ.value for a in phase.atoms])
    biso = np.array([a.biso.value for a in phase.atoms])
    uan = np.array([a.aniso.values() if a.aniso else (0.0,) * 6 for a in phase.atoms])
    return xyz, occ, biso, uan


def _f2(phase, cell6, hkl, f_anom=None, astar=None):
    sites = compile_phase_sites(phase, f_anom)
    xyz, occ, biso, uan = _site_arrays(phase)
    return structure_factors_squared(hkl, d_spacings(hkl, *cell6), sites,
                                     xyz, occ, biso, uan, astar)


# ----------------------------------------------------------------------
# the reference: brute-force |F|² at a single, literal hkl
# ----------------------------------------------------------------------
def _brute_f2(phase: Phase, cell6, h) -> float:
    """|F(h)|² summed over the *whole cell*, with complex f, from scratch.

    Deliberately shares nothing with the module under test: it expands the
    full space-group orbit of every atom rather than using the frozen op
    subsets, and multiplies a genuinely complex scattering factor.
    """
    sg = get_spacegroup(phase.space_group)
    k = 1.0 / (2.0 * float(d_spacings(np.array([h]), *cell6)[0]))
    total = 0.0 + 0.0j
    for atom in phase.atoms:
        x0 = np.array([atom.x.value, atom.y.value, atom.z.value])
        images: list[np.ndarray] = []
        for op in sg.operations():
            r = np.array(op.rot, dtype=np.float64) / 24.0
            t = np.array(op.tran, dtype=np.float64) / 24.0
            p = (r @ x0 + t) % 1.0
            if any(np.all(np.minimum(np.abs(p - q), 1.0 - np.abs(p - q)) < 1e-4)
                   for q in images):
                continue
            images.append(p)
        f = complex(float(f0(atom.species, np.array([k]))[0]), 0.0)
        f += CU_KA1[atom.species]
        dw = math.exp(-atom.biso.value * k * k)
        for p in images:
            total += atom.occ.value * f * dw * np.exp(2j * np.pi * float(np.dot(h, p)))
    return float((total * total.conjugate()).real)


# ----------------------------------------------------------------------
# the Friedel average
# ----------------------------------------------------------------------
def test_friedel_average_matches_the_explicit_orbit_average():
    """⟨|F|²⟩ = |A|² + |B|² is the *orbit* average, not the representative.

    The powder peak contains the whole Laue orbit including the Friedel
    mates, and with complex f its members no longer share one |F|².  This is
    the identity the whole WP rests on, so it is checked against a
    brute-force average over every member of every orbit.
    """
    phase = zincite()
    refl = generate_reflections(phase.space_group, ZINCITE_CELL,
                                wavelength=1.5405929, two_theta_max=130.0)
    orbits = reflection_orbits(phase.space_group, refl.hkl)
    got = _f2(phase, ZINCITE_CELL, refl.hkl, CU_KA1)
    want = np.array([np.mean([_brute_f2(phase, ZINCITE_CELL, g) for g in orb])
                     for orb in orbits])
    assert len(refl) > 20
    # atol keyed to the largest |F|²: a couple of reflections cancel to ~1e-29,
    # where the residue is fp noise rather than a structure factor
    np.testing.assert_allclose(got, want, rtol=1e-12, atol=1e-12 * want.max())


def test_representative_only_would_have_been_wrong():
    """Guards the *reason* for the previous test rather than its arithmetic.

    If some future refactor evaluates the complex F at the representative
    alone, the previous test fails — but only if the two actually differ on
    this structure.  Assert that they do, so the identity test cannot pass
    vacuously.
    """
    phase = zincite()
    refl = generate_reflections(phase.space_group, ZINCITE_CELL,
                                wavelength=1.5405929, two_theta_max=130.0)
    orbits = reflection_orbits(phase.space_group, refl.hkl)
    avg = np.array([np.mean([_brute_f2(phase, ZINCITE_CELL, g) for g in orb])
                    for orb in orbits])
    rep = np.array([_brute_f2(phase, ZINCITE_CELL, h) for h in refl.hkl])
    assert np.max(np.abs(rep - avg) / avg) > 5e-3


def test_centrosymmetric_average_is_the_representative_itself():
    """In a centro group A and B share one phase, so the cross term vanishes.

    Nothing in the code special-cases this; the test is what says so.
    """
    phase = corundum()
    refl = generate_reflections(phase.space_group, CORUNDUM_CELL,
                                wavelength=1.5405929, two_theta_max=90.0)
    got = _f2(phase, CORUNDUM_CELL, refl.hkl, CU_KA1)
    want = np.array([_brute_f2(phase, CORUNDUM_CELL, h) for h in refl.hkl])
    np.testing.assert_allclose(got, want, rtol=1e-12)


# ----------------------------------------------------------------------
# the off state
# ----------------------------------------------------------------------
def test_absent_dispersion_is_bit_identical():
    """No block ⇒ literally the same floats as the non-anomalous model.

    Bit-, not approximately-: this is the promise the backend goldens make,
    and fp multiplication is not associative, so it constrains the
    *association order* inside ``_orbit_terms``, not just the algebra.
    """
    phase = zincite()
    refl = generate_reflections(phase.space_group, ZINCITE_CELL,
                                wavelength=1.5405929, two_theta_max=90.0)
    zero = {"Zn": 0j, "O": 0j}
    np.testing.assert_array_equal(_f2(phase, ZINCITE_CELL, refl.hkl, None),
                                  _f2(phase, ZINCITE_CELL, refl.hkl, zero))


def test_zero_f_double_prime_leaves_only_the_real_shift():
    """f″ = 0 ⇒ B ≡ 0, and the result is |F|² of the f₀+f′ structure."""
    phase = zincite()
    hkl = np.array([[1, 0, 0], [0, 0, 2], [1, 0, 1], [2, -1, 3]])
    real_only = {s: complex(v.real, 0.0) for s, v in CU_KA1.items()}
    got = _f2(phase, ZINCITE_CELL, hkl, real_only)
    assert np.all(got > 0)
    # a real-only correction cannot break Friedel's law, so the
    # representative and the orbit average must still agree
    for i, h in enumerate(hkl):
        f = 0j
        sg = get_spacegroup(phase.space_group)
        k = 1.0 / (2.0 * float(d_spacings(np.array([h]), *ZINCITE_CELL)[0]))
        for atom in phase.atoms:
            x0 = np.array([atom.x.value, atom.y.value, atom.z.value])
            seen: list[np.ndarray] = []
            for op in sg.operations():
                r = np.array(op.rot, dtype=np.float64) / 24.0
                t = np.array(op.tran, dtype=np.float64) / 24.0
                p = (r @ x0 + t) % 1.0
                if any(np.all(np.minimum(np.abs(p - q), 1.0 - np.abs(p - q)) < 1e-4)
                       for q in seen):
                    continue
                seen.append(p)
            fj = float(f0(atom.species, np.array([k]))[0]) + real_only[atom.species].real
            dw = math.exp(-atom.biso.value * k * k)
            f += sum(atom.occ.value * fj * dw * np.exp(2j * np.pi * float(np.dot(h, p)))
                     for p in seen)
        assert got[i] == pytest.approx(abs(f) ** 2, rel=1e-12)


# ----------------------------------------------------------------------
# magnitude — why this is a correctness WP and not a refinement
# ----------------------------------------------------------------------
def test_zincite_bragg_power_drops_by_about_fifteen_percent():
    """Zn below its K edge at Cu Kα is a double-digit intensity error.

    The number this pins (0.844) is what the WP's pre-registered QPA
    prediction is built on, so a change to the structure-factor algebra that
    silently rescales intensities has to argue with it.
    """
    phase = zincite()
    refl = generate_reflections(phase.space_group, ZINCITE_CELL,
                                wavelength=1.5405929, two_theta_max=110.0)
    m = refl.multiplicity
    on = float(np.sum(m * _f2(phase, ZINCITE_CELL, refl.hkl, CU_KA1)))
    off = float(np.sum(m * _f2(phase, ZINCITE_CELL, refl.hkl, None)))
    assert on / off == pytest.approx(0.844, abs=0.01)


def test_corundum_bragg_power_rises():
    """Opposite sign to zincite — which is why QPA cannot absorb it."""
    phase = corundum()
    refl = generate_reflections(phase.space_group, CORUNDUM_CELL,
                                wavelength=1.5405929, two_theta_max=110.0)
    m = refl.multiplicity
    on = float(np.sum(m * _f2(phase, CORUNDUM_CELL, refl.hkl, CU_KA1)))
    off = float(np.sum(m * _f2(phase, CORUNDUM_CELL, refl.hkl, None)))
    assert on / off > 1.03


# ----------------------------------------------------------------------
# analytic gradients through the A/B form
# ----------------------------------------------------------------------
def _fd_f2(phase, cell6, hkl, f_anom, poke, *, step=1e-7):
    """Central difference of ⟨|F|²⟩ under a perturbation callable."""
    sites = compile_phase_sites(phase, f_anom)
    xyz, occ, biso, uan = _site_arrays(phase)
    d = d_spacings(hkl, *cell6)
    from pxrdref.crystallography.adp import reciprocal_axis_lengths
    astar = reciprocal_axis_lengths(*cell6)

    def value(sign):
        x2, u2 = xyz.copy(), uan.copy()
        poke(x2, u2, sign * step)
        return structure_factors_squared(hkl, d, sites, x2, occ, biso, u2, astar)

    return (value(+1) - value(-1)) / (2.0 * step)


def test_analytic_xyz_gradient_matches_fd_with_dispersion():
    phase = zincite()
    hkl = np.array([[1, 0, 0], [0, 0, 2], [1, 0, 1], [1, 0, 2], [2, -1, 3],
                    [1, 0, 3], [2, 0, 0], [2, -1, 2]])
    sites = compile_phase_sites(phase, CU_KA1)
    xyz, occ, biso, uan = _site_arrays(phase)
    from pxrdref.crystallography.adp import reciprocal_axis_lengths
    astar = reciprocal_axis_lengths(*ZINCITE_CELL)
    d = d_spacings(hkl, *ZINCITE_CELL)
    for j in (0, 1):
        got = d_f2_d_xyz(hkl, d, sites, xyz, occ, biso, j, uan, astar)
        for c in range(3):
            def poke(x2, _u2, h, j=j, c=c):
                x2[j, c] += h
            np.testing.assert_allclose(
                got[:, c], _fd_f2(phase, ZINCITE_CELL, hkl, CU_KA1, poke),
                rtol=2e-5, atol=1e-6)


def test_analytic_adp_gradient_matches_fd_with_dispersion():
    """The anisotropic kernel too — B shares the per-component sum with A."""
    phase = Phase(
        name="zincite-aniso", space_group="P 63 m c", cell=_cell(ZINCITE_CELL),
        atoms=[_atom("Zn", "Zn", (1 / 3, 2 / 3, 0.0), 0.55,
                     aniso=AnisoU.from_values(
                         (0.007, 0.007, 0.008, 0.0035, 0.0, 0.0))),
               _atom("O", "O", (1 / 3, 2 / 3, 0.3826), 0.55)])
    hkl = np.array([[1, 0, 0], [0, 0, 2], [1, 0, 1], [2, -1, 3], [1, 0, 3]])
    sites = compile_phase_sites(phase, CU_KA1)
    xyz, occ, biso, uan = _site_arrays(phase)
    from pxrdref.crystallography.adp import reciprocal_axis_lengths
    astar = reciprocal_axis_lengths(*ZINCITE_CELL)
    d = d_spacings(hkl, *ZINCITE_CELL)
    got = d_f2_d_uaniso(hkl, d, sites, xyz, occ, biso, 0, uan, astar)
    for v in range(6):
        def poke(_x2, u2, h, v=v):
            u2[0, v] += h
        np.testing.assert_allclose(
            got[:, v], _fd_f2(phase, ZINCITE_CELL, hkl, CU_KA1, poke, step=1e-8),
            rtol=1e-4, atol=1e-4)


def test_dispersion_actually_changes_the_gradient():
    """Keeps the two gradient tests from passing with B silently dropped."""
    phase = zincite()
    hkl = np.array([[1, 0, 0], [0, 0, 2], [1, 0, 1], [2, -1, 3]])
    xyz, occ, biso, uan = _site_arrays(phase)
    from pxrdref.crystallography.adp import reciprocal_axis_lengths
    astar = reciprocal_axis_lengths(*ZINCITE_CELL)
    d = d_spacings(hkl, *ZINCITE_CELL)
    on = d_f2_d_xyz(hkl, d, compile_phase_sites(phase, CU_KA1),
                    xyz, occ, biso, 1, uan, astar)
    off = d_f2_d_xyz(hkl, d, compile_phase_sites(phase),
                     xyz, occ, biso, 1, uan, astar)
    assert np.max(np.abs(on - off)) > 1e-3 * np.max(np.abs(off))


def test_f_anom_length_is_validated():
    from pxrdref.crystallography.structure_factor import PhaseSites

    with pytest.raises(ValueError, match="one entry per asymmetric-unit atom"):
        PhaseSites(ops=[], species=["Zn", "O"], f_anom=np.array([1 + 1j]))
