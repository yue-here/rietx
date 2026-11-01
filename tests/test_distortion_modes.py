"""Displacive modes in Å, complete and in the reference metric (WP-1419 chunk 1).

What is pinned, and against what:

* **The unit.**  Perez-Mato, Orobengoa & Aroyo (2010), *Acta Cryst.* A66, 558,
  eq. (3), p. 560: Σ mult·|ε|² = 1 over a primitive cell of the child lattice,
  in Å.  The I-centred case is checked against a closed form (an R4+ tilt of
  a cubic perovskite into I4/mcm, A = 4·a·δ over half the conventional cell),
  and the parent-cell variant against 1/√index.
* **The metric.**  Orobengoa et al. (2009), *J. Appl. Cryst.* 42, 820, § 2.2,
  p. 822: the analysis is made in the unstrained reference metric.  In it
  Σ A_τ² = ‖u‖² and the irreps at one k are orthogonal; in the child's strained
  metric neither holds, and the positive arm measures that the check can fail.
* **Completeness.**  Σ n_modes equals the child's free coordinates, counted
  independently from its Wyckoff positions (``wyckoff.coordinate_basis``) less
  its floating origin.
* **LaMnO₃ against Table 13** (Perez-Mato 2010 p. 577).  The fixture
  ``gsas2_bt1_lamno3.cif`` is a different determination from the paper's
  (Rodríguez-Carvajal et al. 1998, 300 K), and the paper's own idealised cubic
  input cell is in its supplementary material, which is not held, so the bar
  is 0.03 Å rather than the printed 0.01 Å.  Labels are matched through the
  isotropy subgroup and the mode count Table 13 prints beside each irrep, and
  M2+ against M3+ by the geometry that defines them (a Jahn–Teller stretch
  along the Mn–O bond, a rotation across it).  B cation at the origin.
"""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.cif import structure_from_cif
from rietx.crystallography.representation import distortion as D
from rietx.crystallography.representation.irreps import small_irreps, star
from rietx.crystallography.representation.modes import basis_vectors, magnetic_representation
from rietx.crystallography.symmetry import resolve_group
from rietx.crystallography.wyckoff import (
    coordinate_basis,
    floating_origin_basis,
    stabilizer_rotations,
)

pytestmark = pytest.mark.xdist_group("distortion-modes")  # the module fixture is built once

DATA = Path(__file__).parent / "data"
P_ = rx.Parameter
A_CUBIC = 3.9

#: The LaMnO₃ Pnma child in the (a+c, 2b, −a+c) setting of Table 13 (p. 576),
#: with Mn at the parent origin.
LAMNO3_P = [[1, 0, -1], [0, 2, 0], [1, 0, 1]]
LAMNO3_ORIGIN = [0.5, 0.0, 0.5]

#: Perez-Mato, Orobengoa & Aroyo (2010) Table 13, p. 577, LaMnO₃ column:
#: irrep → (isotropy subgroup, number of modes, amplitude in Å).
TABLE_13 = {
    "R4+": ("Imma", 1, 1.19),
    "R5+": ("Imma", 2, 0.09),
    "X5+": ("Cmcm", 2, 0.56),
    "M2+": ("P4/mbm", 1, 0.36),
    "M3+": ("P4/mbm", 1, 0.90),
}


def _atom(label, species, x, y, z):
    return rx.Atom(label=label, species=species, x=P_(value=x), y=P_(value=y), z=P_(value=z))


def _cell(a, b, c):
    return rx.Cell(a=P_(value=a), b=P_(value=b), c=P_(value=c),
                   alpha=P_(value=90.0), beta=P_(value=90.0), gamma=P_(value=90.0))


def _perovskite(a=A_CUBIC, a_site="La", b_site="Mn"):
    return rx.Phase(name="cubic", space_group="P m -3 m", cell=rx.Cell.cubic(a), atoms=[
        _atom(b_site, b_site, 0, 0, 0),
        _atom(a_site, a_site, 0.5, 0.5, 0.5),
        _atom("O", "O", 0.5, 0, 0)])


@pytest.fixture(scope="module")
def lamno3():
    child = structure_from_cif(DATA / "gsas2_bt1_lamno3.cif").phases[0]
    parent = _perovskite()
    return parent, child, D.mode_amplitudes(parent, child, (LAMNO3_P, LAMNO3_ORIGIN))


def _i4mcm(delta, a=A_CUBIC):
    """SrTiO₃-type R4+ (a,0,0) tilt: O2 at 8h (¼−δ, ¾−δ, 0) of I4/mcm."""
    child = rx.Phase(name="tilt", space_group="I 4/m c m",
                     cell=_cell(a * 2 ** 0.5, a * 2 ** 0.5, 2 * a), atoms=[
                         _atom("Ti", "Ti", 0, 0, 0), _atom("Sr", "Sr", 0, 0.5, 0.25),
                         _atom("O1", "O", 0, 0, 0.25),
                         _atom("O2", "O", 0.25 - delta, 0.75 - delta, 0)])
    transform = ([[1, 1, 0], [-1, 1, 0], [0, 0, 2]], [0, 0, 0])
    return _perovskite(a, "Sr", "Ti"), child, transform


def _p4mm(shift=0.0, a=A_CUBIC):
    """A BaTiO₃-type Γ4− (a,0,0) child, P4mm on the parent cell, z shifted by ``shift``."""
    child = rx.Phase(name="polar", space_group="P 4 m m", cell=_cell(a, a, 1.01 * a), atoms=[
        _atom("Ti", "Ti", 0, 0, 0.02 + shift), _atom("Ba", "Ba", 0.5, 0.5, 0.6 + shift),
        _atom("O1", "O", 0, 0, 0.47 + shift), _atom("O2", "O", 0.5, 0, 0.01 + shift)])
    return _perovskite(a, "Ba", "Ti"), child, (np.eye(3), np.zeros(3))


def _free_coordinates(phase) -> int:
    """The child's coordinate degrees of freedom from its Wyckoff positions alone."""
    group = resolve_group(phase.space_group, phase.symmetry_operations)
    n = sum(len(coordinate_basis(stabilizer_rotations(
        group, np.array([a.x.value, a.y.value, a.z.value])))) for a in phase.atoms)
    return n - len(floating_origin_basis(group))


def _inner(u, v, metric, lattice_points=1):
    return float(np.einsum("ni,ij,nj->", u, metric, v)) / lattice_points


def _bond_parallel_share(vector, basis) -> float:
    """Share of the O displacement along the Mn–O bond it sits on (parent frame)."""
    big, small = basis.transform
    num = den = 0.0
    for pos, sp, u in zip(basis.positions, basis.species, vector):
        if sp != "O":
            continue
        parent = (big @ pos + small) % 1.0
        axis = int(np.argmin(np.abs(parent - 0.5)))
        up = big @ u
        num += up[axis] ** 2
        den += float(up @ up)
    return num / den


def _label_lamno3(decomposition) -> dict[str, object]:
    """Table 13's labels for the five rows, from subgroup, count and geometry."""
    rows = {}
    comps = {(c.k, c.irrep): c for c in decomposition.basis.components}
    for row in decomposition.rows:
        group = row.isotropy_group.split(" ")[0]
        comp = comps[(row.k, row.irrep)]
        if group == "Imma":
            rows["R4+" if row.n_modes == 1 else "R5+"] = row
        elif group == "Cmcm":
            rows["X5+"] = row
        elif group == "P4/mbm":
            share = _bond_parallel_share(comp.vectors[0], decomposition.basis)
            assert share < 1e-12 or share > 1 - 1e-12, share
            rows["M2+" if share > 0.5 else "M3+"] = row
    return rows


# --------------------------------------------------------------------------
# LaMnO3 against Table 13
# --------------------------------------------------------------------------

def test_lamno3_reproduces_table_13(lamno3):
    """Five irreps, each with Table 13's subgroup and mode count, at 0.03 Å.

    Measured 2026-10-13 (Mac): R4+ 1.194, R5+ 0.090, X5+ 0.554, M2+ 0.336,
    M3+ 0.896 Å against 1.19 / 0.09 / 0.56 / 0.36 / 0.90.  M2+ is the widest
    gap, 0.024 Å, and the one the strain moves most (0.371 in the child's own
    metric, which is the wrong one).
    """
    _, _, dec = lamno3
    rows = _label_lamno3(dec)
    assert sorted(rows) == sorted(TABLE_13)
    for label, (group, n_modes, amplitude) in TABLE_13.items():
        row = rows[label]
        assert row.isotropy_group.split(" ")[0] == group, label
        assert row.n_modes == n_modes, label
        assert row.amplitude == pytest.approx(amplitude, abs=0.03), label
        assert not row.primary, label  # Pnma needs R4+ and M3+ together
    # the R4+ tilt moves no La; R5+ does
    comps = {c.irrep: c for c in dec.basis.components if c.k == rows["R4+"].k}
    la = np.array([s == "La" for s in dec.basis.species])
    assert np.max(np.abs(comps[rows["R4+"].irrep].vectors[:, la])) < 1e-12
    assert np.max(np.abs(comps[rows["R5+"].irrep].vectors[:, la])) > 1e-3


def test_sum_of_squares_is_the_norm_in_the_reference_metric(lamno3):
    """Σ A_τ² = ‖u‖² to 1e-12 Å², and the strained child metric fails it.

    Positive arm: the same modes re-orthonormalised in the child's own metric
    (the kickoff's 2026-10-08 spike) give (Σ A²)^½ − ‖u‖ ≈ 0.007 Å on this
    fixture and same-k cross terms up to ≈ 0.05, so the check can fail.
    """
    _, child, dec = lamno3
    total_sq = sum(r.amplitude ** 2 for r in dec.rows)
    assert abs(total_sq - dec.total ** 2) < 1e-12
    assert dec.residual < 1e-12
    assert np.allclose(dec.translation, 0.0, atol=1e-12)  # Pnma is not polar

    a, b, c = (child.cell.a.value, child.cell.b.value, child.cell.c.value)
    strained = np.diag([a * a, b * b, c * c])
    u = dec.displacements
    wrong_sq, cross = 0.0, 0.0
    vectors = []
    for comp in dec.basis.components:
        v = D.normalise_in_cell(comp.vectors, strained)
        vectors.append((comp.k, v))
        wrong_sq += sum(_inner(m, u, strained) ** 2 for m in v)
    for (k1, v1), (k2, v2) in zip(vectors, vectors[1:]):
        if k1 == k2:
            cross = max(cross, max(abs(_inner(m, n, strained)) for m in v1 for n in v2))
    wrong_gap = abs(np.sqrt(wrong_sq) - np.sqrt(_inner(u, u, strained)))
    assert wrong_gap > 1e-3, wrong_gap
    assert cross > 1e-2, cross


def test_irreps_at_one_k_are_orthogonal_in_the_reference_metric(lamno3):
    """The whole basis is orthonormal over the primitive cell in G_ref, to 1e-12."""
    _, _, dec = lamno3
    basis = dec.basis
    stacked = np.concatenate([c.vectors for c in basis.components])
    gram = np.einsum("mni,ij,pnj->mp", stacked, basis.metric, stacked) / basis.lattice_points
    assert np.max(np.abs(gram - np.eye(len(stacked)))) < 1e-12
    same_k = [c for c in basis.components if c.k == ("1/2", "0", "1/2")]
    assert len(same_k) == 2  # M2+ and M3+ share the arm


def test_the_basis_is_complete(lamno3):
    """Σ n_modes is the child's free coordinates: Pnma 7, I4/mcm 1, P4mm 3.

    The polar case is the one the acoustic removal decides: four z
    coordinates less the floating origin.  The 2×2×2 P1 child is every
    displacement of 40 atoms less the three translations, and its stars are
    the multi-arm case: each irrep is one component over all three X or M
    arms, with the mode count the per-arm decomposition gives.
    """
    parent, child, dec = lamno3
    assert dec.basis.n_modes == _free_coordinates(child) == 7
    for build in (lambda: _i4mcm(0.01), _p4mm):
        p, c, t = build()
        assert D.distortion_basis(p, c, t).n_modes == _free_coordinates(c)
    assert D.distortion_basis(*_p4mm()).n_modes == 3

    p1 = rx.Phase(name="p1", space_group="P 1", cell=rx.Cell.cubic(2 * A_CUBIC),
                  atoms=[_atom("Mn", "Mn", 0, 0, 0)])
    basis = D.distortion_basis(parent, p1, (2 * np.eye(3), np.zeros(3)))
    assert basis.n_modes == 3 * 40 - 3
    group = resolve_group("P m -3 m", None)
    by_star: dict = {}
    for comp in basis.components:
        assert len(comp.arms) == len(star(group, [_frac(x) for x in comp.k]))
        by_star.setdefault(comp.k, []).append(comp)
    for k_text, comps in by_star.items():
        k = [_frac(x) for x in k_text]
        expected = {}
        for site in ((0, 0, 0), (0.5, 0.5, 0.5), (0.5, 0, 0)):
            rep = magnetic_representation("P m -3 m", site, k, kind="polar")
            for ir in small_irreps("P m -3 m", k):
                n = basis_vectors(rep, ir).free_real_amplitudes
                if n:
                    expected[ir.label] = expected.get(ir.label, 0) + n
        arms = len(comps[0].arms)
        if k_text == ("0", "0", "0"):
            acoustic = [lab for lab, n in expected.items() if n >= 3]
            expected[max(acoustic, key=lambda lab: expected[lab])] -= 3
        expected = {lab: arms * n for lab, n in expected.items() if n}
        assert {c.irrep: c.n_modes for c in comps} == expected, k_text


def _frac(text):
    return Fraction(text)


# --------------------------------------------------------------------------
# the unit
# --------------------------------------------------------------------------

def test_an_i_centred_child_sums_over_half_its_conventional_cell():
    """R4+ (a,0,0) → I4/mcm: A = 4·a·δ exactly, not 4√2·a·δ.

    Eight O2 atoms in the conventional cell move by 2·a·δ each; the primitive
    cell holds four of them, so A = √4·2aδ.  Summing the conventional cell
    would give √2 times that.
    """
    delta = 0.01
    parent, child, transform = _i4mcm(delta)
    dec = D.mode_amplitudes(parent, child, transform)
    assert dec.basis.lattice_points == 2
    (row,) = dec.rows
    assert row.amplitude == pytest.approx(4 * A_CUBIC * delta, abs=1e-12)
    assert row.isotropy_group == "I4/mcm (140)"
    assert row.primary
    assert row.k == ("1/2", "1/2", "1/2")


def test_the_parent_cell_normalisation_is_one_over_root_index(lamno3):
    """Normalised over one parent cell instead, every amplitude is A/√index (index 4)."""
    _, _, dec = lamno3
    basis = dec.basis
    index = 4
    u = dec.displacements
    for comp, row in zip(basis.components, dec.rows):
        parent_cell = D.normalise_in_cell(comp.vectors, basis.metric,
                                          lattice_points=basis.lattice_points * index)
        amps = [_inner(m, u, basis.metric, basis.lattice_points * index) for m in parent_cell]
        assert np.linalg.norm(amps) == pytest.approx(row.amplitude / np.sqrt(index),
                                                     rel=1e-12, abs=1e-15)


def test_normalise_in_cell_keeps_the_span_and_drops_dependent_fields():
    rng = np.random.default_rng(7)
    fields = rng.normal(size=(3, 4, 3))
    fields = np.concatenate([fields, fields[:1] + 2 * fields[1:2]])
    metric = np.array([[4.0, 0.3, 0.0], [0.3, 5.0, 0.1], [0.0, 0.1, 6.0]])
    out = D.normalise_in_cell(fields, metric, lattice_points=2)
    assert out.shape == (3, 4, 3)
    gram = np.einsum("mni,ij,pnj->mp", out, metric, out) / 2
    assert np.max(np.abs(gram - np.eye(3))) < 1e-12
    coeff, *_ = np.linalg.lstsq(out.reshape(3, -1).T, fields.reshape(4, -1).T, rcond=None)
    assert np.allclose(out.reshape(3, -1).T @ coeff, fields.reshape(4, -1).T, atol=1e-12)


# --------------------------------------------------------------------------
# invariance
# --------------------------------------------------------------------------

def test_amplitudes_do_not_depend_on_the_basis_inside_an_irrep(lamno3):
    """A random rotation of the two-mode R5+ and X5+ bases leaves A_τ unchanged."""
    _, _, dec = lamno3
    basis, u = dec.basis, dec.displacements
    rng = np.random.default_rng(11)
    for comp, row in zip(basis.components, dec.rows):
        if comp.n_modes < 2:
            continue
        q, _ = np.linalg.qr(rng.normal(size=(comp.n_modes, comp.n_modes)))
        rotated = np.tensordot(q, comp.vectors, axes=1)
        amps = [_inner(m, u, basis.metric, basis.lattice_points) for m in rotated]
        assert np.linalg.norm(amps) == pytest.approx(row.amplitude, abs=1e-12)


def test_a_domain_of_the_child_has_the_same_amplitudes(lamno3):
    """The child carried by a parent 4-fold the child lacks: same A_τ per subgroup.

    The domain sits on other arms of the X and M stars, so this also checks
    that no amplitude depends on which arm the child chose.
    """
    parent, child, dec = lamno3
    rot = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]])
    other = D.mode_amplitudes(parent, child, (rot @ np.array(LAMNO3_P),
                                              rot @ np.array(LAMNO3_ORIGIN)))
    key = lambda r: (r.isotropy_group, r.n_modes, round(r.amplitude, 9))  # noqa: E731
    assert sorted(map(key, other.rows)) == sorted(map(key, dec.rows))
    assert {r.k for r in other.rows} != {r.k for r in dec.rows}
    for a, b in zip(sorted(other.rows, key=key), sorted(dec.rows, key=key)):
        assert a.amplitude == pytest.approx(b.amplitude, abs=1e-12)


def test_a_polar_child_loses_its_global_translation():
    """Shifting a P4mm child along its polar axis changes the translation, not A_τ."""
    base = D.mode_amplitudes(*_p4mm())
    moved = D.mode_amplitudes(*_p4mm(shift=0.05))
    (row,) = base.rows
    assert row.isotropy_group == "P4mm (99)" and row.primary and row.n_modes == 3
    assert moved.rows[0].amplitude == pytest.approx(row.amplitude, abs=1e-12)
    assert base.translation[2] == pytest.approx(0.022, abs=1e-12)
    assert moved.translation[2] == pytest.approx(0.072, abs=1e-12)
    assert abs(sum(r.amplitude ** 2 for r in base.rows) - base.total ** 2) < 1e-12


# --------------------------------------------------------------------------
# the reference metric
# --------------------------------------------------------------------------

def test_the_reference_metric_is_the_parent_symmetric_part(lamno3):
    """'average' is Pᵀ·(tr G/3)·P for a cubic parent; 'parent' is the parent's cell."""
    parent, child, _ = lamno3
    big = np.array(LAMNO3_P, float)
    inv = np.linalg.inv(big)
    a, b, c = (child.cell.a.value, child.cell.b.value, child.cell.c.value)
    in_parent = inv.T @ np.diag([a * a, b * b, c * c]) @ inv
    expected = big.T @ (np.trace(in_parent) / 3 * np.eye(3)) @ big
    got = D.reference_metric(parent, child, (LAMNO3_P, LAMNO3_ORIGIN))
    assert np.max(np.abs(got - expected)) < 1e-12
    got = D.reference_metric(parent, child, (LAMNO3_P, LAMNO3_ORIGIN), reference="parent")
    assert np.max(np.abs(got - big.T @ (A_CUBIC ** 2 * np.eye(3)) @ big)) < 1e-12


def test_a_parent_cell_that_breaks_its_own_symmetry_is_refused(lamno3):
    _, child, _ = lamno3
    bad = _perovskite()
    bad = bad.model_copy(update={"cell": _cell(3.9, 3.9, 4.0)})
    with pytest.raises(ValueError, match="REFERENCE_CELL_NOT_PARENT_SYMMETRIC"):
        D.mode_amplitudes(bad, child, (LAMNO3_P, LAMNO3_ORIGIN), reference="parent")


# --------------------------------------------------------------------------
# refusals
# --------------------------------------------------------------------------

def test_a_transform_that_is_not_a_subgroup_is_refused(lamno3):
    parent, child, _ = lamno3
    with pytest.raises(ValueError, match="CHILD_NOT_A_SUBGROUP"):
        D.mode_amplitudes(parent, child, (LAMNO3_P, [0.25, 0.0, 0.0]))


def test_a_child_whose_atoms_do_not_pair_is_refused(lamno3):
    parent, child, _ = lamno3
    fewer = child.model_copy(update={"atoms": child.atoms[:-1]})
    with pytest.raises(ValueError, match="CHILD_ATOMS_UNPAIRED"):
        D.mode_amplitudes(parent, fewer, (LAMNO3_P, LAMNO3_ORIGIN))


def _p1_supercell(multiples):
    """A one-atom P 1 parent (4, 5, 6 Å) and its supercell child along the axes."""
    parent = rx.Phase(name="p1", space_group="P 1", cell=_cell(4.0, 5.0, 6.0),
                      atoms=[_atom("Fe", "Fe", 0, 0, 0)])
    child = rx.Phase(name="p1-super", space_group="P 1",
                     cell=_cell(4.0 * multiples[0], 5.0 * multiples[1], 6.0 * multiples[2]),
                     atoms=[_atom("Fe", "Fe", 0, 0, 0)])
    return parent, child, (np.diag(multiples).astype(float), np.zeros(3))


@pytest.mark.parametrize("multiples, free", [((2, 1, 1), 3), ((3, 1, 1), 6), ((4, 1, 1), 9),
                                             ((3, 3, 1), 24)])
def test_a_k_whose_double_is_not_reciprocal_is_counted_once(multiples, free):
    """k and -k are separate classes in P 1 when 2k is no reciprocal vector; the real span of one
    already holds both fields, so the basis has 3N - 3 modes and not twice that.  The doubled
    cell, where every k is its own -k, is the arm that never failed."""
    basis = D.distortion_basis(*_p1_supercell(multiples))
    assert basis.n_modes == free


def _general_site_supercell(space_group, multiples, gamma=90.0):
    """A one-atom parent at a general position under ``space_group`` and its diagonal supercell."""
    def phase(name, group, m):
        b = 5.0 if space_group in ("P 2", "P -1") else 4.0  # tetragonal and hexagonal: a = b
        cell = rx.Cell(a=P_(value=4.0 * m[0]), b=P_(value=b * m[1]), c=P_(value=6.0 * m[2]),
                       alpha=P_(value=90.0), beta=P_(value=90.0), gamma=P_(value=gamma))
        return rx.Phase(name=name, space_group=group, cell=cell,
                        atoms=[_atom("Fe", "Fe", 0.1, 0.2, 0.3)])
    return (phase("parent", space_group, (1, 1, 1)), phase("child", "P 1", multiples),
            (np.diag(multiples).astype(float), np.zeros(3)))


@pytest.mark.parametrize("space_group, multiples, gamma, site_order, first_arms", [
    ("P 4", (3, 3, 1), 90.0, 4, 4),   # a rotation takes k to -k: -k is an arm of k's own star
    ("P 4", (4, 4, 1), 90.0, 4, 4),
    ("P 2", (3, 1, 3), 90.0, 2, 2),
    ("P -1", (3, 1, 1), 90.0, 2, 2),  # inversion puts -k in every star
    ("P 3", (3, 3, 1), 120.0, 3, 3),  # three arms of one star, one irrep, one component
])
def test_every_arm_of_a_star_is_kept_when_minus_k_is_one_of_them(
        space_group, multiples, gamma, site_order, first_arms):
    """The skip is per star: a -k inside k's own star is an arm and stays, a -k that is another
    star is dropped.  The 3N - 3 count is the regression check for the crash, and the arms of the
    first non-Gamma star say how many the star has (the old skip halved them)."""
    parent, child, transform = _general_site_supercell(space_group, multiples, gamma)
    basis = D.distortion_basis(parent, child, transform)
    assert basis.n_modes == 3 * site_order * int(np.prod(multiples)) - 3
    first = next(c for c in basis.components if c.k != ("0", "0", "0"))
    assert len(first.arms) == first_arms
    labelled = [c for c in basis.components if c.k == first.k and c.irrep == first.irrep]
    assert len(labelled) == 1  # one irrep, one component, never split across arms


def test_two_atoms_on_one_parent_site_are_refused_by_name():
    parent = rx.Phase(name="mixed", space_group="P m -3 m", cell=rx.Cell.cubic(A_CUBIC), atoms=[
        _atom("La", "La", 0.5, 0.5, 0.5), _atom("Sr", "Sr", 0.5, 0.5, 0.5),
        _atom("Mn", "Mn", 0, 0, 0), _atom("O", "O", 0.5, 0, 0)])
    with pytest.raises(ValueError, match="'La' and 'Sr' share one site"):
        D.distortion_basis(parent, parent, (np.eye(3), np.zeros(3)))


def test_a_deuterated_child_pairs_with_its_hydrogenous_parent():
    """D is hydrogen to the species grammar, as everywhere else in the package."""
    parent = rx.Phase(name="p", space_group="P m -3 m", cell=rx.Cell.cubic(A_CUBIC),
                      atoms=[_atom("Mn", "Mn", 0, 0, 0), _atom("H", "H", 0.5, 0.5, 0.5)])
    child = parent.model_copy(deep=True)
    child.atoms[1].species = "D"
    decomposition = D.mode_amplitudes(parent, child, (np.eye(3), np.zeros(3)))
    assert decomposition.total == pytest.approx(0.0, abs=1e-9)
    assert decomposition.basis.species == ("Mn", "H")


def test_an_unidentified_probe_leaves_primary_unanswered(monkeypatch):
    """spglib naming no group checked nothing; a False there would read as "secondary"."""
    import spglib

    parent, child, transform = _i4mcm(0.01)
    named = D.distortion_basis(parent, child, transform)
    assert all(isinstance(c.primary, bool) for c in named.components)  # positive arm
    monkeypatch.setattr(spglib, "get_symmetry_dataset", lambda *a, **k: None)
    blind = D.distortion_basis(parent, child, transform)
    assert [c.primary for c in blind.components] == [None] * len(blind.components)
    assert {c.isotropy_group for c in blind.components} == {"unidentified"}


def test_a_supergroup_with_the_childs_operation_count_is_not_primary():
    """#1002: spglib lists only the operations that preserve the input cell, so the
    I4/mmm child of the cubic perovskite (32 of them) reads a component whose group is
    Fm-3m as the child's own when the two are compared by count."""
    parent, child, transform = _i4mcm(0.01)
    child = child.model_copy(update={"space_group": "I 4/m m m"})
    by_irrep = {c.irrep: c for c in D.distortion_basis(parent, child, transform).components}
    assert by_irrep["S4"].isotropy_group == "Fm-3m (225)"
    assert by_irrep["S4"].primary is False
    assert by_irrep["S6"].isotropy_group == "I4/mmm (139)"  # positive arm: the child's own
    assert by_irrep["S6"].primary is True
