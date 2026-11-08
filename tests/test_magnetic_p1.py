"""``restate_phase_in_p1``: the cell listed atom by atom, each with its moment.

Everything here is synthetic.  The one claim that carries weight is the
**positive arm**: rietx's own ``predict()`` on the restatement equals its
``predict()`` on the original, nuclear and magnetic parts, to ~1e-12.  The
restatement is built from the forward model's own orbit operations and the
magnetic group's own axial matrices, so the arm alone would pass for a wrong
convention used in both places; the other tests state what is expected
independently of that code:

* the moments of a primed group are written out from the group's operators
  (ε·det(R)·R, with the time reversal), not read back from the function;
* the atom counts are the Wyckoff multiplicities of the tables;
* a restatement with one time reversal dropped is **not** the original: the
  magnetic intensity moves, so the positive arm has the power to see it.
"""

from __future__ import annotations

from fractions import Fraction

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.magnetic.isotropy import candidates
from rietx.crystallography.magnetic.p1 import (
    restate_in_p1,
    restate_phase_in_p1,
)
from rietx.crystallography.magnetic.supercell import magnetic_supercell
from rietx.crystallography.symmetry import resolve_group, site_orbit
from rietx.schemas.common import Parameter as P
from rietx.schemas.structure import (
    AnisoU,
    Atom,
    Cell,
    Moment,
    Phase,
)

LAMBDA = 2.4
GRID = np.arange(10.0, 120.0, 0.05)


def _cell(a, b, c, alpha=90.0, beta=90.0, gamma=90.0) -> Cell:
    return Cell(a=P(value=a), b=P(value=b), c=P(value=c), alpha=P(value=alpha),
                beta=P(value=beta), gamma=P(value=gamma))


def _atom(label, species, xyz, *, moment=None, aniso=None) -> Atom:
    return Atom(label=label, species=species, x=P(value=xyz[0]),
                y=P(value=xyz[1]), z=P(value=xyz[2]),
                biso=P(value=0.4, unit="A^2"), moment=moment, aniso=aniso)


def mnf2(**kw) -> Phase:
    """Rutile MnF2, P 4_2/mnm, BNS 136.499 (P4_2'/mnm'): Mn on 2a, m ∥ c.

    The group is type III: the screw and the n-glide are primed, so the
    body-centre Mn carries the *opposite* moment.
    """
    return Phase(
        name="MnF2", space_group="P 42/m n m", cell=_cell(4.8734, 4.8734, 3.3099),
        atoms=[_atom("Mn", "Mn", (0.0, 0.0, 0.0),
                     moment=Moment.from_values((0.0, 0.0, 4.6), "Mn2+",
                                               vary=True)),
               _atom("F", "F", (0.3050, 0.3050, 0.0), **kw)],
        magnetic_symmetry="136.499")


def _predict(phase: Phase) -> np.ndarray:
    ref = rx.Refinement(rx.Structure(phases=[phase]),
                        rx.Instrument.constant_wavelength_neutron(LAMBDA),
                        history=False)
    return np.asarray(ref.predict(GRID))


def _nuclear_only(phase: Phase) -> Phase:
    return phase.model_copy(update={
        "magnetic_symmetry": None,
        "atoms": [a.model_copy(update={"moment": None}) for a in phase.atoms]})


def _agree(a: np.ndarray, b: np.ndarray, tol=1e-12) -> float:
    dev = float(np.max(np.abs(a - b)) / np.max(np.abs(a)))
    assert dev < tol, dev
    return dev


# ---------------------------------------------------------------- k = 0, primed


def test_a_primed_group_restates_with_the_opposite_moment_on_the_centre():
    p1 = restate_phase_in_p1(mnf2())
    mn = [a for a in p1.atoms if a.species == "Mn"]
    assert [a.label for a in mn] == ["Mn_1", "Mn_2"]
    assert mn[0].moment.values() == pytest.approx((0.0, 0.0, 4.6), abs=1e-12)
    assert mn[1].moment.values() == pytest.approx((0.0, 0.0, -4.6), abs=1e-12)
    assert [round(float(v), 12) for v in (mn[1].x.value, mn[1].y.value,
                                           mn[1].z.value)] == [0.5, 0.5, 0.5]


def test_the_moments_are_the_groups_own_axial_action_written_out():
    """Independent of the function: ε·det(R)·R from each operator of 136.499,
    applied by hand to the asymmetric-unit moment, must be one of the moments
    the restatement lists, at the image that operator reaches."""
    phase = mnf2()
    group = phase.magnetic_symmetry.group()
    m = np.array([0.0, 0.0, 4.6])
    by_position: dict[tuple, np.ndarray] = {}
    for op in group.all_operations():
        image = np.round(op.act_on_site(np.zeros(3)), 9)
        moment = op.time_reversal * np.linalg.det(op.matrix) * op.matrix @ m
        by_position.setdefault(tuple(image), moment)
    p1 = restate_phase_in_p1(phase)
    listed = {tuple(np.round([a.x.value, a.y.value, a.z.value], 9)):
              np.array(a.moment.values())
              for a in p1.atoms if a.moment is not None}
    assert set(listed) == set(by_position)
    for position, moment in by_position.items():
        assert listed[position] == pytest.approx(moment, abs=1e-12)


def test_the_restatement_predicts_what_the_original_does():
    """The positive arm, nuclear and magnetic parts together and then the
    magnetic part alone (the difference of the two predictions)."""
    original = mnf2()
    p1 = restate_phase_in_p1(original)
    total = _agree(_predict(original), _predict(p1))
    assert total < 1e-12
    magnetic = _predict(original) - _predict(_nuclear_only(original))
    magnetic_p1 = _predict(p1) - _predict(_nuclear_only(p1))
    assert np.max(magnetic) > 0.01 * np.max(_predict(original))   # a real signal
    _agree(magnetic, magnetic_p1, tol=1e-9)


def test_dropping_one_time_reversal_is_not_the_original():
    """The negative arm: flip the moment the primed operation gave the body
    centre back to what an unprimed operation would give.  The equality that
    held above fails, so it can see the sign."""
    p1 = restate_phase_in_p1(mnf2())
    wrong = p1.model_copy(update={"atoms": [
        a.model_copy(update={"moment": Moment.from_values(
            (0.0, 0.0, 4.6), "Mn2+", vary=False)}) if a.label == "Mn_2" else a
        for a in p1.atoms]})
    original = _predict(mnf2())
    deviation = float(np.max(np.abs(_predict(wrong) - original))
                      / np.max(original))
    assert deviation > 0.05, deviation


def test_site_counts_are_the_wyckoff_multiplicities():
    p1 = restate_phase_in_p1(mnf2())
    species = [a.species for a in p1.atoms]
    assert species.count("Mn") == 2          # 2a
    assert species.count("F") == 4           # 4f
    sg = resolve_group("P 42/m n m", None)
    for a, expected in (("Mn", 2), ("F", 4)):
        original = next(x for x in mnf2().atoms if x.species == a)
        orbit = site_orbit(sg, [original.x.value, original.y.value,
                                original.z.value])
        assert orbit.multiplicity == expected


def test_the_restatement_is_p1_group_1_1_and_everything_is_held():
    p1 = restate_phase_in_p1(mnf2())
    assert p1.space_group == "P 1" and p1.symmetry_operations is None
    assert p1.magnetic_symmetry.bns_number == "1.1"
    assert p1.propagation_vector is None
    for atom in p1.atoms:
        for param in (atom.x, atom.y, atom.z, atom.occ, atom.biso):
            assert not param.vary
        if atom.moment is not None:
            assert not atom.moment.vary
    assert not any(getattr(p1.cell, n).vary
                   for n in ("a", "b", "c", "alpha", "beta", "gamma"))
    # the source is not touched
    assert mnf2().atoms[0].moment.vary


def test_a_nuclear_phase_restates_without_a_magnetic_block():
    plain = _nuclear_only(mnf2())
    p1 = restate_phase_in_p1(plain)
    assert p1.magnetic_symmetry is None
    assert all(a.moment is None for a in p1.atoms)
    _agree(_predict(plain), _predict(p1))


def test_an_anisotropic_displacement_tensor_is_rotated_with_its_image():
    """F on 4f of P4_2/mnm: U12 ≠ 0 changes sign between the two mirror images
    that the 4-fold relates (x,x,0) → (-x,-x,0) → (1/2-x, 1/2+x, 1/2), so a copy
    of the asymmetric-unit tensor is wrong on half of them and the pattern
    betrays it."""
    aniso = AnisoU.from_values((0.012, 0.012, 0.020, 0.004, 0.0, 0.0))
    original = mnf2(aniso=aniso)
    p1 = restate_phase_in_p1(original)
    f = [a for a in p1.atoms if a.species == "F"]
    u12 = [a.aniso.u12.value for a in f]
    assert sorted(round(v, 9) for v in u12) == [-0.004, -0.004, 0.004, 0.004]
    _agree(_predict(original), _predict(p1))


# ------------------------------------------------------------ k != 0, a child


def _pbcm_child() -> Phase:
    parent = Phase(
        name="synthetic Pbcm", space_group="P b c m",
        cell=_cell(5.0, 9.0, 9.5),
        atoms=[_atom("Fe", "Fe", (0.25, 0.125, 0.25)),
               _atom("O", "O", (0.0, 0.375, 0.25))])
    cand = candidates(parent.space_group, (0.25, 0.125, 0.25),
                      (Fraction(1, 2), 0, 0)).candidates[0]
    return magnetic_supercell(parent, cand, magnetic_species="Fe", ion="Fe3+",
                              magnitude=2.0).phase


def test_a_k_not_zero_child_restates_and_predicts_the_same():
    """The supercell ``magnetic_supercell`` states for a k = (½, 0, 0) order:
    anti-translations (time reversal on a lattice translation) are in its
    group, and every Fe image carries the sign its operation gives it."""
    child = _pbcm_child()
    group = child.magnetic_symmetry.group()
    assert any(op.time_reversal == -1 for op in group.all_operations())
    p1 = restate_phase_in_p1(child)
    sg = resolve_group(child.space_group, child.symmetry_operations)
    expected = sum(site_orbit(sg, [a.x.value, a.y.value, a.z.value]).multiplicity
                   for a in child.atoms)
    assert len(p1.atoms) == expected
    fe = [a for a in p1.atoms if a.moment is not None]
    signs = {round(float(np.sign(sum(a.moment.values()))), 0) for a in fe}
    assert signs == {-1.0, 1.0}            # both senses are listed
    _agree(_predict(child), _predict(p1))


def test_a_restated_structure_restates_every_phase():
    structure = rx.Structure(phases=[mnf2(), _nuclear_only(mnf2())])
    p1 = restate_in_p1(structure)
    assert [len(p.atoms) for p in p1.phases] == [6, 6]
    assert all(p.space_group == "P 1" for p in p1.phases)


def test_restraints_are_refused_by_name():
    bad = mnf2().model_copy(update={"restraints": [object()]})
    with pytest.raises(ValueError, match="restraint"):
        restate_phase_in_p1(bad)


# --------------------------------------------------- the TOPAS writer's opt-in


def test_the_writer_refuses_a_supercell_child_and_p1_expand_serves_it(tmp_path):
    """No keyword for the parent k, and the child's family group is unnamed in
    its cell: both are the refusals ``write_topas_inp`` gave a ``solve_magnetic``
    result.  The P 1 restatement states neither."""
    child = _pbcm_child()
    structure = rx.Structure(phases=[child])
    with pytest.raises(ValueError):
        rx.write_topas_inp(structure, tmp_path / "refused.inp")
    path = tmp_path / "p1.inp"
    rx.write_topas_inp(structure, path, p1_expand=True)
    text = path.read_text(encoding="utf-8")
    assert "mag_space_group 1.1" in text
    assert "occ Fe+3" in text                 # the ion, TOPAS's spelling
    assert "\n  space_group " not in text    # a magnetic str states only mag_space_group
    assert text.count("site ") == len(restate_phase_in_p1(child).atoms)


def test_a_p1_inp_reads_back_as_the_same_prediction(tmp_path):
    """The TOPAS-free check: write the restatement, read it with rietx's own
    reader, and ``predict()`` equals the original's (neutron, so the species
    respelling as the ion changes nothing)."""
    original = mnf2()
    structure = rx.Structure(phases=[original])
    path = tmp_path / "mnf2.inp"
    rx.write_topas_inp(structure, path, p1_expand=True)
    back = rx.read_project_model(path).to_structure()
    assert len(back.phases[0].atoms) == 6
    assert back.phases[0].space_group.replace(" ", "") == "P1"
    # the file states every flag held; the scale is the original's
    phase = back.phases[0].model_copy(update={
        "scale": original.scale.model_copy()})
    _agree(_predict(original), _predict(phase), tol=1e-9)


def test_p1_expand_leaves_the_default_alone(tmp_path):
    path = tmp_path / "plain.inp"
    rx.write_topas_inp(rx.Structure(phases=[_nuclear_only(mnf2())]), path)
    assert 'space_group "P 42/m n m"' in path.read_text(encoding="utf-8")
