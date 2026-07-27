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

from pxrdref.crystallography.dispersion import dispersion
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
    "Al": complex(0.2130, 0.2455),
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


# ----------------------------------------------------------------------
# the tabulation
# ----------------------------------------------------------------------
CU_KA1_LAMBDA = 1.5405929
MO_KA1_LAMBDA = 0.7093


def test_table_matches_international_tables_at_cu_ka():
    """The published check values every crystallographer knows.

    ``CU_KA1`` above is *International Tables* Vol. C §4.2.6, which is itself
    Cromer-Liberman — so this asserts the loader (grid units, column order,
    interpolation, the f1-vs-f′ convention) rather than the physics.
    """
    for species, want in CU_KA1.items():
        fp, fpp = dispersion(species, CU_KA1_LAMBDA)
        assert fp == pytest.approx(want.real, abs=0.005), species
        assert fpp == pytest.approx(want.imag, abs=0.005), species


def test_matches_gemmi_independently():
    """gemmi *computes* Cromer-Liberman rather than interpolating a table.

    An agreement to 1e-3 e across Z and energy therefore catches a mis-parsed
    grid, a swapped column or a units slip in a way the hand-entered check
    values above cannot.  It also pins the **relativistic convention**: gemmi
    applies the Kissel & Pratt (1990) high-energy-limit correction, worth
    −1.3 e at uranium, so f′ agreeing here is what says the bundled table is
    the corrected variant and not the 1970 one.

    The two tolerances differ by two orders of magnitude and that is the
    point: f″ is a direct cross-section readout and matches to 2e-4 e, while
    f″-independent additive corrections (the relativistic term, orbital
    quadrature) live entirely in f′, where the DABAX run and gemmi's port
    differ by up to 1.7e-2 e — measured at the grid *nodes*, so it is a real
    difference between two Cromer-Liberman implementations, not interpolation.
    Both bounds are far below the 1.3 e that would separate the corrected
    variant from the 1970 one.

    Not asserted for every element: gemmi's f′ is known to disagree with every
    published tabulation for a few lanthanides and actinides (Ce by ~11 e near
    19 keV), so the oracle is used over the range where it is sound rather
    than blindly.
    """
    import gemmi

    from pxrdref.crystallography.attenuation import _HC_EV_ANGSTROM

    for lam in (CU_KA1_LAMBDA, MO_KA1_LAMBDA, 0.4139090):
        for el in ("O", "Mg", "Al", "Si", "Ca", "Ti", "Fe", "Zn", "Sr", "Zr",
                   "Ag", "Ba", "La", "W", "Pb", "U"):
            fp, fpp = dispersion(el, lam)
            g_fp, g_fpp = gemmi.cromer_liberman(
                gemmi.Element(el).atomic_number, _HC_EV_ANGSTROM / lam)
            assert fpp == pytest.approx(g_fpp, abs=1e-3), (el, lam, "f''")
            assert fp == pytest.approx(g_fp, abs=3e-2), (el, lam, "f'")


def test_the_table_carries_the_kissel_pratt_correction():
    """Which relativistic convention the bundled file uses, asserted not assumed.

    Cromer-Liberman's high-energy limit uses (5/3)·E_tot/mc²; Kissel & Pratt
    (1990) showed the coefficient should be 1.  The gap is Z-dependent and
    energy-independent — 0.065 e at Fe but **1.3 e at uranium** — so a wrong
    guess here is a silent few-per-cent intensity error for heavy elements.
    gemmi applies the correction, and agrees at U to far better than the size
    of the correction itself.
    """
    import gemmi

    from pxrdref.crystallography.attenuation import _HC_EV_ANGSTROM

    fp, _ = dispersion("U", CU_KA1_LAMBDA)
    g_fp, _ = gemmi.cromer_liberman(92, _HC_EV_ANGSTROM / CU_KA1_LAMBDA)
    assert abs(fp - g_fp) < 0.05
    assert abs(fp - (g_fp + 1.306)) > 1.0   # the uncorrected value is excluded


def test_f_double_prime_reproduces_the_mcmaster_photoabsorption():
    """Optical theorem across two independent compilations, Z = 8 → 57.

    σ_photo = 2·r_e·λ·f″ ties the f″ of a 1983 Cromer-Liberman calculation to
    the photoelectric column of the 1969 McMaster compilation the attenuation
    path already bundles.  They share no inputs, so agreement is evidence both
    are being read correctly — and the ~5 % scatter is the genuine
    disagreement between the two tabulations, not a bug, which is why µ is not
    re-sourced from f″.
    """
    from pxrdref.crystallography.attenuation import photoelectric_cross_section
    from pxrdref.crystallography.dispersion import photoabsorption_barn

    for el in ("O", "F", "Mg", "Al", "Si", "Ca", "Fe", "Zn", "Zr", "La"):
        _fp, fpp = dispersion(el, CU_KA1_LAMBDA)
        implied = photoabsorption_barn(fpp, CU_KA1_LAMBDA)
        tabulated = photoelectric_cross_section(el, CU_KA1_LAMBDA)
        assert implied == pytest.approx(tabulated, rel=0.06), el


def test_scattering_share_of_the_total_is_small_but_real():
    """Why µ keeps its own table: f″ is photoabsorption, µ is beam removal.

    The gap is Rayleigh + Compton.  It is a few per cent and it is *largest
    for light elements* (photoabsorption grows about as Z⁴, Rayleigh as Z²),
    which is exactly where the McMaster table was already known to be weakest
    — so re-sourcing µ from f″ would trade one small error for another.
    """
    from pxrdref.crystallography.attenuation import (
        photoelectric_cross_section,
        total_cross_section,
    )

    share = {}
    for el in ("O", "Al", "Ca", "Fe", "La"):
        pe = photoelectric_cross_section(el, CU_KA1_LAMBDA)
        tot = total_cross_section(el, CU_KA1_LAMBDA)
        share[el] = (tot - pe) / tot
    assert all(0.0 < v < 0.10 for v in share.values()), share
    assert share["O"] > share["La"]


def test_edges_are_detected_and_refused_not_smeared():
    """f″ jumps ~8× across one grid interval; interpolating it is nonsense."""
    from pxrdref.crystallography.attenuation import _HC_EV_ANGSTROM
    from pxrdref.crystallography.dispersion import edges

    zn_k = edges("Zn")
    assert len(zn_k) == 1
    assert zn_k[0] == pytest.approx(9659.0, rel=3e-3)
    with pytest.raises(ValueError, match="contains an absorption edge"):
        dispersion("Zn", _HC_EV_ANGSTROM / zn_k[0])
    # La has three L edges and a K edge inside the tabulated band
    assert len(edges("La")) == 4


def test_near_edge_flags_the_xanes_region():
    from pxrdref.crystallography.attenuation import _HC_EV_ANGSTROM
    from pxrdref.crystallography.dispersion import edges, near_edge

    zn_k = edges("Zn")[0]
    assert near_edge("Zn", _HC_EV_ANGSTROM / (zn_k + 30.0)) == pytest.approx(zn_k)
    assert near_edge("Zn", _HC_EV_ANGSTROM / (zn_k + 500.0)) is None
    assert near_edge("Zn", CU_KA1_LAMBDA) is None


def test_ions_resolve_to_the_element():
    """f′/f″ are core-level effects, so the charge is dropped — unlike f₀."""
    from pxrdref.crystallography.dispersion import normalize_element

    assert normalize_element("Zn2+") == "Zn"
    assert normalize_element("O2-") == "O"
    assert normalize_element("FE") == "Fe"
    assert dispersion("Zn2+", CU_KA1_LAMBDA) == dispersion("Zn", CU_KA1_LAMBDA)


def test_hydrogen_is_zero_not_a_refusal():
    """Z = 1, 2 are absent from the tabulation and have no X-ray edge.

    Refusing them would make every hydrous phase (brucite, fluorapatite)
    un-refinable with dispersion on, to protect a ~1e-3 e correction.
    """
    assert dispersion("H", CU_KA1_LAMBDA) == (0.0, 0.0)
    assert dispersion("He", MO_KA1_LAMBDA) == (0.0, 0.0)


def test_out_of_band_wavelength_is_refused():
    with pytest.raises(ValueError, match="outside the tabulated"):
        dispersion("Fe", 6.0)      # 2.07 keV, below the 3 keV floor
    with pytest.raises(ValueError, match="outside the tabulated"):
        dispersion("Fe", 0.1)      # 124 keV, above the 70 keV ceiling


def test_unknown_element_is_refused():
    with pytest.raises(KeyError, match="Z = 3-98"):
        dispersion("Cf", CU_KA1_LAMBDA)  # Z = 98 is the last; Es is not there
        dispersion("Es", CU_KA1_LAMBDA)


def test_dispersion_map_is_keyed_by_the_raw_species_label():
    from pxrdref.crystallography.dispersion import dispersion_map

    m = dispersion_map(["Zn2+", "O2-", "Zn2+"], CU_KA1_LAMBDA)
    assert set(m) == {"Zn2+", "O2-"}
    assert m["Zn2+"].real == pytest.approx(-1.546, abs=5e-3)


def test_table_covers_every_element_the_test_data_uses():
    for el in ("Na", "Ca", "Al", "F", "La", "B", "Zn", "O", "Mg", "Fe",
               "Zr", "Si", "P"):
        fp, fpp = dispersion(el, CU_KA1_LAMBDA)
        assert fpp > 0.0
        assert abs(fp) < 30.0
