"""The commensurate k ≠ 0 statement: a nuclear phase in its magnetic supercell.

Every fixture here is synthetic and written in this file, with **exact**
coordinates — 1/3 rather than 0.333333 — because the headline control is a
bit-level one and a coordinate rounded in the parent and snapped in the child
would show up as a failure of the arithmetic rather than of the input.

The three controls the rung is bought with:

* the child's nuclear |F_N|² is the parent's on every parent reflection, up to
  the index² a repeated cell puts there by the phase sum, and **identically
  zero** on every superlattice position;
* the child cell's volume is |det P| times the parent's;
* the magnetic group in the child cell identifies to the candidate's own BNS
  number.

and the fence that keeps the statement honest: a parent whose operations carry
a half translation along the doubled axis has **no** Hermann-Mauguin symbol in
the child cell, and is never stated with a symbol that would generate the wrong
absences.  Since the operation-list phase (#448) that case is *stated* — as the
child's own operation list under a bracketed label, with a
``CHILD_GROUP_UNNAMED`` diagnostic — instead of refused, and the three controls
above are asserted on such a child too.  Two refusals remain and both are named
here: an operation list whose point group and lattice name no tabulated group
at all (its cell has no metric constraints), and a ``nuclear_group="parent"``
child whose nuclear orbit the magnetic group cannot cover.
"""

from __future__ import annotations

import re
from fractions import Fraction

import numpy as np
import pytest

from rietx.crystallography.adp import direct_metric_tensor
from rietx.crystallography.magnetic.isotropy import candidates
from rietx.crystallography.magnetic.operators import identify
from rietx.crystallography.magnetic.supercell import (
    SupercellStatement,
    anti_translation_residual,
    child_basis,
    magnetic_supercell,
)
from rietx.crystallography.structure_factor import (
    compile_phase_sites,
    structure_factors_squared,
)
from rietx.crystallography.symmetry import d_spacings, generate_reflections
from rietx.schemas.common import Parameter as P
from rietx.schemas.structure import Atom, Cell, Phase

#: A synthetic Pbcm parent with a magnetic B site.  Pbcm is a group with glide
#: and screw absences, so the child's reflection list is not the trivial case.
PBCM_CELL = (5.0, 9.0, 9.5, 90.0, 90.0, 90.0)
HALF_A = (Fraction(1, 2), 0, 0)

#: A symmorphic tetragonal parent at k = (0, 0, ½): no translation anywhere, so
#: the child symbol is the parent's and the arithmetic is as clean as it gets.
P4MMM_CELL = (4.0, 4.0, 6.0, 90.0, 90.0, 90.0)
HALF_C = (0, 0, Fraction(1, 2))


def _cell(a, b, c, alpha, beta, gamma) -> Cell:
    return Cell(a=P(value=a), b=P(value=b), c=P(value=c), alpha=P(value=alpha),
                beta=P(value=beta), gamma=P(value=gamma))


def pbcm_parent() -> Phase:
    """Fe at a general-ish Pbcm position, O elsewhere; exact coordinates."""
    return Phase(
        name="synthetic Pbcm", space_group="P b c m", cell=_cell(*PBCM_CELL),
        atoms=[
            Atom(label="Fe", species="Fe", x=P(value=0.25), y=P(value=0.125),
                 z=P(value=0.25), biso=P(value=0.4)),
            Atom(label="O", species="O", x=P(value=0.0), y=P(value=0.375),
                 z=P(value=0.25), biso=P(value=0.6)),
        ])


def p4mmm_parent() -> Phase:
    return Phase(
        name="synthetic P4/mmm", space_group="P 4/m m m", cell=_cell(*P4MMM_CELL),
        atoms=[
            Atom(label="Mn", species="Mn", x=P(value=0.0), y=P(value=0.0),
                 z=P(value=0.0), biso=P(value=0.3)),
            Atom(label="O", species="O", x=P(value=0.5), y=P(value=0.0),
                 z=P(value=0.0), biso=P(value=0.5)),
        ])


def _nuclear_f2(phase: Phase, hkl: np.ndarray) -> np.ndarray:
    """⟨|F_N|²⟩ on the given integer indices, the forward model's own call."""
    cell = phase.cell.lengths_angles()
    sites = compile_phase_sites(phase, None, neutron=True)
    hkl = np.asarray(hkl, dtype=np.int64)
    d = d_spacings(hkl, *cell)
    xyz = np.array([[a.x.value, a.y.value, a.z.value] for a in phase.atoms])
    occ = np.array([a.occ.value for a in phase.atoms])
    biso = np.array([a.biso.value for a in phase.atoms])
    return structure_factors_squared(hkl, d, sites, xyz, occ, biso, None, None)


def _volume(cell) -> float:
    return float(np.sqrt(np.linalg.det(direct_metric_tensor(*cell))))


def _p_matrix(statement: SupercellStatement) -> np.ndarray:
    from rietx.crystallography.magnetic.supercell import _parse_basis

    return np.array([[float(v) for v in row]
                     for row in _parse_basis(statement.transform)])


def _statement(parent: Phase, site, k, *, species, ion, index: int = 0
               ) -> tuple[SupercellStatement, object]:
    cand = candidates(parent.space_group, site, k).candidates[index]
    return magnetic_supercell(parent, cand, magnetic_species=species, ion=ion,
                              magnitude=2.0), cand


# =========================================================== the three controls
def test_the_childs_nuclear_structure_factor_is_the_parents():
    """|F_c|² = |det P|²·|F_p|² on every parent reflection, to 1e-12 relative.

    The index² is not a fudge and not a normalisation choice: the child cell
    holds the parent's atoms |det P| times, and at a reciprocal-lattice point
    the parent *has* (h_child = Pᵀ·h_parent) every copy enters the phase sum
    with the same phase, so F_child = |det P|·F_parent exactly.  A site counted
    twice, an orbit only half enumerated, or a wrong multiplicity all show up
    here as a ratio that is not the same on every row.
    """
    statement, _cand = _statement(pbcm_parent(), (0.25, 0.125, 0.25), HALF_A,
                                  species="Fe", ion="Fe3+")
    parent, child = pbcm_parent(), statement.phase
    refl = generate_reflections(parent.space_group, parent.cell.lengths_angles(),
                                1.8, two_theta_max=120.0)
    mapped = np.rint(refl.hkl @ _p_matrix(statement)).astype(np.int64)
    f2_parent = _nuclear_f2(parent, refl.hkl)
    f2_child = _nuclear_f2(child, mapped)
    live = f2_parent > 1e-9
    assert live.sum() > 20
    ratio = f2_child[live] / f2_parent[live]
    assert np.allclose(ratio, statement.index ** 2, rtol=1e-12, atol=0.0)
    # and a row the parent computes as zero stays zero
    assert np.all(f2_child[~live] < 1e-12)


def test_a_superlattice_position_has_no_nuclear_intensity_at_all():
    """Exactly zero, not small: a doubled cell of the parent's own atoms.

    These are the rows the magnetic term lives on, so if the nuclear model put
    anything there the fit would report a moment it did not need.  The
    cancellation is the phase sum's — every atom appears with its
    anti-translation image at Q·t = ½ — so the residue is the last bit of a
    ~10³ fm² sum, and the assertion is against the *scale of the pattern*
    rather than against an absolute epsilon that would mean nothing.
    """
    statement, _cand = _statement(pbcm_parent(), (0.25, 0.125, 0.25), HALF_A,
                                  species="Fe", ion="Fe3+")
    child = statement.phase
    refl = generate_reflections(child.space_group, child.cell.lengths_angles(),
                                1.8, two_theta_max=120.0)
    inverse = np.linalg.inv(_p_matrix(statement).T)
    back = (inverse @ refl.hkl.T).T
    is_parent = np.all(np.abs(back - np.rint(back)) < 1e-8, axis=1)
    assert int((~is_parent).sum()) > 10, "no superlattice row to test"
    f2 = _nuclear_f2(child, refl.hkl)
    scale = float(np.max(f2[is_parent]))
    assert float(np.max(f2[~is_parent])) < 1e-12 * scale


def _pattern_with_moments_at_zero(phase: Phase) -> np.ndarray:
    """The forward model's pattern of ``phase`` with every moment held at zero."""
    import rietx as rx
    from rietx.schemas.structure import Structure

    quiet = phase.model_copy(deep=True)
    for atom in quiet.atoms:
        if atom.moment is not None:
            for component in ("crystalaxis_x", "crystalaxis_y", "crystalaxis_z"):
                getattr(atom.moment, component).value = 0.0
                getattr(atom.moment, component).vary = False
    instrument = rx.Instrument.constant_wavelength_neutron(2.0, fwhm_deg=0.4)
    return np.asarray(rx.Refinement(Structure(phases=[quiet]), instrument)
                      .predict(np.linspace(10.0, 110.0, 2001)))


@pytest.mark.parametrize(("k", "index"), [((0, 0, 0), 1), (HALF_A, 2)])
def test_the_restated_scale_reproduces_the_parents_pattern(k, index):
    """Moments at zero, the child computes the parent's pattern at the parent's scale.

    The first control above has F_child = |det P|·F_parent, so the child's
    scale is the parent's over |det P|²; carried unchanged (main before this
    test) the k = (½,0,0) child computed the parent's pattern ×4.000000 to
    6e-15, and a held scale started a restated fit four times too strong.
    k = 0 is the arm that cannot fail: |det P| = 1, nothing to divide.
    """
    parent = pbcm_parent().model_copy(update={"scale": P(value=1.7)})
    cand = candidates(parent.space_group, (0.25, 0.125, 0.25), k).candidates[0]
    statement = magnetic_supercell(parent, cand, magnetic_species="Fe",
                                   ion="Fe3+", magnitude=2.0)
    assert statement.index == index
    assert statement.phase.scale.value == pytest.approx(1.7 / index ** 2,
                                                        rel=1e-15)
    y_parent = _pattern_with_moments_at_zero(parent)
    y_child = _pattern_with_moments_at_zero(statement.phase)
    live = y_parent > 1e-3 * y_parent.max()
    assert live.sum() > 100
    assert np.allclose(y_child[live] / y_parent[live], 1.0, rtol=1e-9, atol=0.0)


def test_the_restated_scale_keeps_the_weight_fraction():
    """S·Z·M·V is the parent's: the cell mass and volume each grow by |det P|."""
    from rietx.optimize.qpa import phase_zmv

    parent = pbcm_parent()
    statement, _cand = _statement(parent, (0.25, 0.125, 0.25), HALF_A,
                                  species="Fe", ion="Fe3+")
    child = statement.phase

    def zmv(phase: Phase) -> float:
        return phase_zmv(phase.space_group, phase.cell.lengths_angles(),
                         [(a.species, a.x.value, a.y.value, a.z.value,
                           a.occ.value) for a in phase.atoms]).zmv

    assert child.scale.value * zmv(child) == pytest.approx(
        parent.scale.value * zmv(parent), rel=1e-12)


def test_the_child_cell_volume_is_det_p_times_the_parents():
    statement, _cand = _statement(pbcm_parent(), (0.25, 0.125, 0.25), HALF_A,
                                  species="Fe", ion="Fe3+")
    ratio = (_volume(statement.phase.cell.lengths_angles())
             / _volume(PBCM_CELL))
    assert statement.index == 2
    assert ratio == pytest.approx(2.0, rel=1e-14)
    # and the child cell is the parent's axes with one of them doubled
    assert statement.transform == "2a,b,c;0,0,0"


def test_a_magnetic_statement_with_no_magnetic_species_is_refused():
    """No ``magnetic_species`` used to return a magnetic phase with no moment.

    Main before this test returned it silently: the k = (½,0,0) Pbcm child
    had zero moment sites, an empty ``diagnostics`` and a magnetic group set,
    so it compiled and fitted with no magnetic term at all.  The positive arm
    is the same call naming the species, which places a moment on both Fe
    sites of the child.
    """
    parent = pbcm_parent()
    cand = candidates(parent.space_group, (0.25, 0.125, 0.25), HALF_A).candidates[0]
    named = magnetic_supercell(parent, cand, magnetic_species="Fe", ion="Fe3+")
    assert sum(a.moment is not None for a in named.phase.atoms) == 2
    with pytest.raises(ValueError, match="no magnetic_species was given"):
        magnetic_supercell(parent, cand, ion="Fe3+")
    with pytest.raises(ValueError, match="no magnetic_species was given"):
        magnetic_supercell(parent, group=named.group, transform=named.transform,
                           ion="Fe3+")


def test_a_displacive_candidate_needs_no_magnetic_species():
    """The one statement that carries no moment by design is not refused."""
    parent = pbcm_parent()
    cand = next(c for c in candidates(parent.space_group, (0.25, 0.125, 0.25),
                                      HALF_A, kind="displacive").candidates)
    statement = magnetic_supercell(parent, cand, nuclear_group="magnetic")
    assert statement.phase.atoms
    assert all(a.moment is None for a in statement.phase.atoms)


def test_a_parent_biso_bound_reaches_the_child():
    """A bound a caller stated on the parent's Biso binds every child the
    site becomes, whatever the schema's default (none since WP-1534)."""
    parent = pbcm_parent()
    parent.atoms[1].biso = P(value=26.8, min=0.0, max=26.8)
    statement, _cand = _statement(parent, (0.25, 0.125, 0.25), HALF_A,
                                  species="Fe", ion="Fe3+")
    hot = [a.biso for a in statement.phase.atoms if a.label.startswith("O")]
    assert hot and all((b.value, b.max) == (26.8, 26.8) for b in hot)


def test_a_polar_parents_floating_origin_reaches_the_child():
    """``Phase.floating_origin`` is copied, and the child's own table holds
    one DOF along the child group's polar axis (WP-1912, review of #929 item 5)."""
    from rietx.params.vector import ParameterTable
    from rietx.schemas.instrument import Instrument
    from rietx.schemas.structure import Structure

    parent = Phase(
        name="synthetic P4mm", space_group="P 4 m m", cell=_cell(*P4MMM_CELL),
        floating_origin="hold",
        atoms=[
            Atom(label="Mn", species="Mn", x=P(value=0.0), y=P(value=0.0),
                 z=P(value=0.0), biso=P(value=0.3)),
            Atom(label="O", species="O", x=P(value=0.5), y=P(value=0.5),
                 z=P(value=0.375), biso=P(value=0.5)),
        ])
    statement, _cand = _statement(parent, (0, 0, 0), HALF_C, species="Mn",
                                  ion="Mn3+")
    child = statement.phase
    assert child.floating_origin == "hold"
    table = ParameterTable(Structure(phases=[child]),
                           Instrument.bragg_brentano(radiation="CuKa"))
    assert table.origin_holds == {"phases.0.atoms.0.dof.0": (0, (0, 0, 1))}


def test_the_group_in_the_child_cell_identifies_to_the_candidates_bns():
    """The transform is a change of setting, not a change of group.

    ``MagneticGroup.transformed`` completes the lattice as well as conjugating
    the rotations; without the completion the result is a *subgroup* wearing
    the right symbol.  spglib re-identifying the transported group as the same
    BNS number is the check that the completion happened.
    """
    from rietx.crystallography.magnetic.supercell import _child_lattice, _parse_basis

    statement, cand = _statement(pbcm_parent(), (0.25, 0.125, 0.25), HALF_A,
                                 species="Fe", ion="Fe3+")
    lattice = _child_lattice(PBCM_CELL, _parse_basis(statement.transform))
    assert identify(statement.group, lattice=lattice).bns_number == cand.bns_number
    assert cand.msg_type == 4                       # k ≠ 0, 2k ∈ L*: always IV


# ========================================================== the atom list
def test_every_parent_site_appears_exactly_index_times_and_no_more():
    """Each parent orbit splits into exactly ``index`` child orbits.

    The count is the whole of the "counted twice" failure: |det P| parent cells
    of atoms in the child cell, partitioned into child orbits, one asymmetric
    atom each.  Asserted as a count per parent site rather than in total, so
    that two sites cancelling each other's error cannot pass it.
    """
    statement, _cand = _statement(pbcm_parent(), (0.25, 0.125, 0.25), HALF_A,
                                  species="Fe", ion="Fe3+")
    from collections import Counter

    per_parent = Counter(j for j, _coset in statement.site_map)
    assert set(per_parent) == {0, 1}
    assert all(n == statement.index for n in per_parent.values())
    # and the cosets are distinct within each parent site
    for j in per_parent:
        cosets = [c for pj, c in statement.site_map if pj == j]
        assert sorted(cosets) == list(range(statement.index))


def test_the_moments_are_antiparallel_across_the_anti_translation():
    """The statement *is* the candidate: seeded on the group's own orbit.

    The anti-centring says m(x + t) = −m(x); the seeding propagates one seed
    over ``MagneticGroup.site_orbit``, so this holds by construction and
    :func:`anti_translation_residual` is zero on the stated structure.  It is
    asserted rather than assumed because the seeding is the only place the
    physics of a type IV group enters the atom list.
    """
    statement, _cand = _statement(pbcm_parent(), (0.25, 0.125, 0.25), HALF_A,
                                  species="Fe", ion="Fe3+")
    child = statement.phase
    moments = {a.label: np.array(a.moment.values())
               for a in child.atoms if a.moment is not None}
    assert len(moments) == 2
    (first, second) = (moments[k] for k in sorted(moments))
    assert np.linalg.norm(first) > 0.5
    assert np.allclose(second, -first, atol=1e-12)
    assert anti_translation_residual(child) == pytest.approx(0.0, abs=1e-12)


def test_the_residual_sees_a_structure_that_has_left_its_own_group():
    """The negative arm for the residual — a control that cannot fail is no control.

    Flipping one of the two moments makes the pair *parallel*, which the
    anti-centring forbids, and the residual has to report it at twice the
    moment.  Without this row a residual that always returned zero would pass
    the test above.
    """
    statement, _cand = _statement(pbcm_parent(), (0.25, 0.125, 0.25), HALF_A,
                                  species="Fe", ion="Fe3+")
    child = statement.phase
    magnetic = [a for a in child.atoms if a.moment is not None]
    flipped = magnetic[1].moment.model_copy(deep=True)
    for name in ("crystalaxis_x", "crystalaxis_y", "crystalaxis_z"):
        getattr(flipped, name).value = -getattr(flipped, name).value
    atoms = [a.model_copy(update={"moment": flipped}) if a is magnetic[1] else a
             for a in child.atoms]
    broken = child.model_construct(**{**child.__dict__, "atoms": atoms})
    size = float(np.max(np.abs(magnetic[0].moment.values())))
    assert anti_translation_residual(broken) == pytest.approx(2.0 * size, rel=1e-9)


# ========================================================== the symbol fence
def test_a_half_translation_along_the_doubled_axis_is_stated_as_an_operator_list():
    """P2₁2₁2₁ at k = (½, 0, 0) has no Hermann-Mauguin symbol in its child cell.

    Its 2₁ along **a** carries a ½ that becomes a ¼ in the doubled cell, and no
    standard operation list contains a quarter translation.  A statement made
    under the *symbol* would give a phase whose ``space_group`` generates
    neither its own site orbits nor its own systematic absences — silently,
    because both would still be *a* group.  This used to be a refusal for that
    reason; since #448 the child carries its own operation list under a
    bracketed label, so the orbits and the absences come from the operations
    and the label is only a label.  The ``CHILD_GROUP_UNNAMED`` diagnostic
    carries what the refusal used to say: the cell, the symbol spglib found and
    the mechanism.
    """
    parent = Phase(
        name="synthetic P212121", space_group="P 21 21 21",
        cell=_cell(6.0, 7.0, 8.0, 90.0, 90.0, 90.0),
        atoms=[Atom(label="Fe", species="Fe", x=P(value=0.125),
                    y=P(value=0.25), z=P(value=0.375), biso=P(value=0.4))])
    cand = candidates("P 21 21 21", (0.125, 0.25, 0.375), HALF_A).candidates[0]
    # ``nuclear_group="magnetic"``, because the parent route has a *second*
    # obstruction here that this rung does not lift: the magnetic orbit of the
    # site is four images and the parent-derived nuclear orbit is eight, so the
    # stated group determines no moment for half of them and
    # ``magnetic_supercell`` refuses by name (the test below).
    statement = magnetic_supercell(parent, cand, magnetic_species="Fe",
                                   ion="Fe3+", nuclear_group="magnetic")
    assert statement.child_group_named is False
    assert statement.child_space_group == "P21 [unnamed in 2a,b,c]"
    assert statement.phase.space_group == statement.child_space_group
    ops = statement.phase.symmetry_operations
    assert ops is not None and len(ops) == 4
    assert any("1/4" in op for op in ops), ops
    note, = statement.diagnostics
    assert note.code == "CHILD_GROUP_UNNAMED"
    assert note.level == "info"
    # relative to the returned phase: the statement cannot know its index
    assert note.where == ["space_group"]
    assert "2a,b,c" in note.message
    assert "its own 4 symmetry operations" in note.message
    assert "metric constraints" in note.message


def test_the_parent_route_is_refused_when_the_magnetic_orbit_is_smaller():
    """The obstruction the symbol refusal used to hide, now named where it is.

    ``nuclear_group="parent"`` for a k that lowers the crystal class gives the
    child a nuclear orbit larger than the magnetic group's orbit of the same
    site, and no moment the stated group determines for the surplus images.
    ``compile_magnetic_sites`` always refused that — at *compile*.  While the
    unnamed child was refused one step earlier for the unrelated reason that no
    symbol named it, the compile never saw the case; now that the child is
    stated, the check has to be here, where the documented remedy
    (``nuclear_group="magnetic"``) is still reachable and
    ``strategy.magnetic._supercell`` takes it by itself.
    """
    parent = Phase(
        name="synthetic P212121", space_group="P 21 21 21",
        cell=_cell(6.0, 7.0, 8.0, 90.0, 90.0, 90.0),
        atoms=[Atom(label="Fe", species="Fe", x=P(value=0.125),
                    y=P(value=0.25), z=P(value=0.375), biso=P(value=0.4))])
    cand = candidates("P 21 21 21", (0.125, 0.25, 0.375), HALF_A).candidates[0]
    with pytest.raises(ValueError) as exc:
        magnetic_supercell(parent, cand, magnetic_species="Fe", ion="Fe3+")
    msg = str(exc.value)
    assert "determines no moment for that atom" in msg
    assert "nuclear_group='magnetic'" in msg
    # and the remedy the message names does state it
    assert magnetic_supercell(parent, cand, magnetic_species="Fe", ion="Fe3+",
                              nuclear_group="magnetic").child_group_named is False


def test_the_unnamed_child_keeps_the_superlattice_free_of_nuclear_intensity():
    """The property the old refusal was protecting, now measured on the child.

    A doubled cell holding the parent's atoms twice has |F_N|² identically zero
    at every reciprocal-lattice point the parent does not have — by the phase
    sum, not by a tolerance — and the magnetic term is not zero there, so the
    superlattice intensity is entirely the moment's.  Both halves would break
    for a phase whose ``space_group`` did not generate its own operations, so
    this is the assertion that says the operation list is doing the symbol's
    job.  The same two claims the ``pbcm`` case above makes for a *named* child,
    made here for one no symbol names.
    """
    import rietx as rx
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable
    from rietx.schemas.instrument import BackgroundChebyshev
    from rietx.schemas.pattern import PatternData
    from rietx.schemas.structure import Structure

    parent = Phase(
        name="synthetic P212121", space_group="P 21 21 21",
        cell=_cell(6.0, 7.0, 8.0, 90.0, 90.0, 90.0),
        atoms=[Atom(label="Fe", species="Fe", x=P(value=0.125),
                    y=P(value=0.25), z=P(value=0.375), biso=P(value=0.4))])
    cand = candidates("P 21 21 21", (0.125, 0.25, 0.375), HALF_A).candidates[0]
    statement = magnetic_supercell(parent, cand, magnetic_species="Fe",
                                   ion="Fe3+", magnitude=4.0,
                                   nuclear_group="magnetic")
    child = statement.phase
    assert statement.child_group_named is False

    instrument = rx.Instrument.constant_wavelength_neutron(2.0, fwhm_deg=0.3)
    instrument.background = BackgroundChebyshev(
        coefficients=[P(value=0.0) for _ in range(3)])
    x = np.arange(10.0, 120.0, 0.05)
    pattern = PatternData(two_theta=x.tolist(), intensity=[1.0] * len(x))
    structure = Structure(phases=[child])
    model = compile_model(structure, instrument, pattern)
    table = ParameterTable(structure, instrument)
    values = table.decode(table.x0())
    cp = model.phases[0]
    assert cp.magnetic is not None

    cell = tuple(values[f"phases.0.cell.{k}"]
                 for k in ("a", "b", "c", "alpha", "beta", "gamma"))
    d = np.asarray(cp.reflections.d)
    nuclear = np.asarray(model._nuclear_f2(0, d, values, cell))
    magnetic = np.asarray(model._magnetic_f2(0, d, values, cell))
    # with P = 2a,b,c a superlattice row is one with odd h
    is_parent = cp.reflections.hkl[:, 0] % 2 == 0
    assert int((~is_parent).sum()) > 10
    assert float(np.max(nuclear[~is_parent])) < 1e-20 * float(np.max(nuclear[is_parent]))
    assert float(np.max(magnetic[~is_parent])) > 1.0


def test_the_same_parent_is_accepted_at_a_k_the_cell_does_carry():
    """The positive arm for the fence: it is the axis, not the group.

    P2₁2₁2₁ at k = (0, 0, ½) doubles **c**, and its 2₁ along c is the one whose
    ½ becomes a ¼ — so that is refused too, while k = (0, ½, 0)… would be as
    well.  The arm that must pass is therefore a different parent: P4/mmm is
    symmorphic, has no translation anywhere, and states cleanly at k = (0,0,½).
    Without it the refusal above would be consistent with the statement never
    working at all.
    """
    statement, cand = _statement(p4mmm_parent(), (0.0, 0.0, 0.0), HALF_C,
                                 species="Mn", ion="Mn2+")
    assert statement.transform == "a,b,2c;0,0,0"
    assert statement.index == 2
    assert statement.phase.magnetic_symmetry is not None
    assert statement.phase.magnetic_symmetry.bns_number == cand.bns_number
    assert statement.phase.magnetic_symmetry.propagation_vector_parent == \
        ("0", "0", "1/2")
    ratio = (_volume(statement.phase.cell.lengths_angles()) / _volume(P4MMM_CELL))
    assert ratio == pytest.approx(2.0, rel=1e-14)


def test_the_symmorphic_child_reproduces_its_parents_structure_factor_too():
    """The |F_N|² control on the second parent, so it is not a Pbcm accident."""
    statement, _cand = _statement(p4mmm_parent(), (0.0, 0.0, 0.0), HALF_C,
                                  species="Mn", ion="Mn2+")
    parent, child = p4mmm_parent(), statement.phase
    refl = generate_reflections(parent.space_group, P4MMM_CELL, 1.5,
                                two_theta_max=120.0)
    mapped = np.rint(refl.hkl @ _p_matrix(statement)).astype(np.int64)
    f2_parent = _nuclear_f2(parent, refl.hkl)
    f2_child = _nuclear_f2(child, mapped)
    live = f2_parent > 1e-9
    assert np.allclose(f2_child[live] / f2_parent[live], 4.0, rtol=1e-12)


# ========================================================== the scope fences
def test_the_basis_is_the_unreduced_one_and_says_why():
    """``magnetic_cell``'s reduction is right there and wrong here — asserted.

    ``isotropy.magnetic_cell`` reduces the supercell basis so spglib can
    identify a group in it; for P6/mmm-family parents that reduction returns
    a γ = 60° cell, and the nuclear operations of a hexagonal Hermann-Mauguin
    symbol are written for γ = 120°.  :func:`child_basis` returns the
    unreduced doubling, and the two are asserted to *differ* so that a future
    change to either is a test failure rather than a silent γ.
    """
    from rietx.crystallography.magnetic.isotropy import magnetic_cell

    reduced = magnetic_cell("P -6 m 2", HALF_C).basis
    unreduced = child_basis("P -6 m 2", HALF_C)
    assert unreduced == ((Fraction(1), Fraction(0), Fraction(0)),
                         (Fraction(0), Fraction(1), Fraction(0)),
                         (Fraction(0), Fraction(0), Fraction(2)))
    assert reduced != unreduced
    # k = 0 needs no doubling and the two agree there
    assert child_basis("P -6 m 2", (0, 0, 0)) == magnetic_cell("P -6 m 2",
                                                                (0, 0, 0)).basis


def test_a_k_outside_the_rungs_scope_is_refused_by_magnetic_cells_own_message():
    """One authority on which k this rung admits: ``magnetic_cell``'s fence."""
    with pytest.raises(ValueError, match="outside the reciprocal lattice"):
        child_basis("P 3", (Fraction(1, 3), Fraction(1, 3), 0))


def test_an_anisotropic_parent_is_refused_rather_than_copied():
    """U* transforms; copying it onto an image is wrong in an oblique setting."""
    from rietx.schemas.structure import AnisoU

    parent = p4mmm_parent()
    atoms = [parent.atoms[0].model_copy(update={
        "aniso": AnisoU.from_values((0.01, 0.01, 0.02, 0.0, 0.0, 0.0))}),
        parent.atoms[1]]
    parent = parent.model_copy(update={"atoms": atoms})
    cand = candidates("P 4/m m m", (0.0, 0.0, 0.0), HALF_C).candidates[0]
    with pytest.raises(ValueError, match="anisotropic displacement"):
        magnetic_supercell(parent, cand, magnetic_species="Mn", ion="Mn2+")


def test_a_species_with_no_form_factor_ion_is_refused_by_name():
    parent = p4mmm_parent()
    cand = candidates("P 4/m m m", (0.0, 0.0, 0.0), HALF_C).candidates[0]
    with pytest.raises(ValueError, match="form-factor ion"):
        magnetic_supercell(parent, cand, magnetic_species="Mn")
    with pytest.raises(ValueError, match="is a species or a"):
        magnetic_supercell(parent, cand, magnetic_species="Cu", ion="Cu2+")


# ================================= the statement reaches the forward model
def test_the_statement_compiles_on_a_neutron_scan_and_the_superlattice_is_all_magnetic():
    """The whole point: a k ≠ 0 model the constant-wavelength arm computes.

    On a superlattice row the nuclear term is exactly zero and the magnetic
    term is not, so the intensity there is **entirely** the moment's — which is
    what makes the k ≠ 0 hypothesis testable against the data at all.  Both
    halves are asserted on the same compiled model rather than argued: a
    statement that put nuclear intensity on those rows would fit them with the
    structure and report no moment, and one whose magnetic term were zero
    there would have nothing to fit them with.
    """
    import rietx as rx
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable
    from rietx.schemas.instrument import BackgroundChebyshev
    from rietx.schemas.pattern import PatternData
    from rietx.schemas.structure import Structure

    statement, _cand = _statement(pbcm_parent(), (0.25, 0.125, 0.25), HALF_A,
                                  species="Fe", ion="Fe3+")
    child = statement.phase
    instrument = rx.Instrument.constant_wavelength_neutron(2.0, fwhm_deg=0.3)
    instrument.background = BackgroundChebyshev(
        coefficients=[P(value=0.0) for _ in range(3)])
    x = np.arange(10.0, 120.0, 0.05)
    pattern = PatternData(two_theta=x.tolist(), intensity=[1.0] * len(x))
    structure = Structure(phases=[child])

    model = compile_model(structure, instrument, pattern)
    table = ParameterTable(structure, instrument)
    values = table.decode(table.x0())
    cp = model.phases[0]
    assert cp.magnetic is not None
    assert cp.mag_members is not None and cp.mag_members.shape[1] == 3

    cell = tuple(values[f"phases.0.cell.{k}"]
                 for k in ("a", "b", "c", "alpha", "beta", "gamma"))
    d = np.asarray(cp.reflections.d)
    nuclear = np.asarray(model._nuclear_f2(0, d, values, cell))
    magnetic = np.asarray(model._magnetic_f2(0, d, values, cell))

    inverse = np.linalg.inv(_p_matrix(statement).T)
    back = (inverse @ cp.reflections.hkl.T).T
    is_parent = np.all(np.abs(back - np.rint(back)) < 1e-8, axis=1)
    assert int((~is_parent).sum()) > 10

    # Not by WP-1327's mask — these rows are *allowed* by the child symbol, so
    # the mask is 1 on them and the zero is the phase sum's own cancellation
    # between a site and its anti-translation image.  1e-29 of the pattern's
    # own scale, which is float64 saying "exactly".
    assert float(np.max(nuclear[~is_parent])) < 1e-20 * float(np.max(nuclear[is_parent]))
    assert float(np.max(magnetic[~is_parent])) > 1.0   # and it is a real peak
    # the moment DOFs really are two independent columns, one per coset
    paths = [p for p in values if p.endswith(".moment.dof0")]
    assert len(paths) == 2


# ================================= the anti-centring as a constraint
def test_the_anti_translation_ties_remove_the_ferromagnetic_mode():
    """A tie per anti-centring pair, and the fit stays inside its own group.

    Without them the statement carries two independent moment columns per
    parent site, one combination of which is the ferromagnetic mode the
    declared group forbids, and nothing else in a fit holds it at zero.  With
    them the pair is one column and
    ``anti_translation_residual`` stays at zero through a refinement.
    """
    import rietx as rx
    from rietx.crystallography.magnetic.supercell import anti_translation_ties
    from rietx.schemas.instrument import BackgroundChebyshev
    from rietx.schemas.structure import Structure

    statement, _cand = _statement(pbcm_parent(), (0.25, 0.125, 0.25), HALF_A,
                                  species="Fe", ion="Fe3+")
    child = statement.phase
    ties = anti_translation_ties(child)
    assert len(ties) == 1                        # one Fe orbit, one anti-centring
    (target, source, scale, offset), = ties
    assert target.endswith(".moment.dof0") and source.endswith(".moment.dof0")
    assert target != source
    assert (scale, offset) == (-1.0, 0.0)        # a line: μ is signed

    instrument = rx.Instrument.constant_wavelength_neutron(2.0, fwhm_deg=0.3)
    instrument.background = BackgroundChebyshev(
        coefficients=[P(value=1.0)] + [P(value=0.0) for _ in range(2)])
    x = np.arange(10.0, 120.0, 0.05)
    y = np.ones_like(x)
    pattern = rx.PatternData(two_theta=x.tolist(), intensity=y.tolist())
    ref = rx.Refinement(Structure(phases=[child]), instrument)
    ref.tie(target, source, scale=scale, offset=offset)
    ref.fit(pattern, plan=rx.RefinementPlan(stages=[
        rx.Stage("moment", ["phases.*.atoms.*.moment.dof*",
                            "instrument.background.c*"])]))
    assert anti_translation_residual(ref.structure.phases[0]) == \
        pytest.approx(0.0, abs=1e-9)


def test_a_higher_dimensional_subspace_ties_through_the_angles_too():
    """m′ = −m is affine in (μ, φ) because an anti-centring acts as −I.

    Not a rotation: {1 | t, −1} carries ε·det(I)·I = −**I**, and the antipode
    of a direction inside a plane is φ + π — an affine map of the DOFs, and the
    only reason the constraint can be spelled as ties at all.  A
    rotation-related pair is deliberately *not* emitted: those atoms are one
    nuclear orbit and WP-1327's ``mom_mat`` already carries them exactly.
    """
    from rietx.crystallography.magnetic.supercell import anti_translation_ties

    for index in range(8):
        statement, _cand = _statement(p4mmm_parent(), (0.0, 0.0, 0.0), HALF_C,
                                      species="Mn", ion="Mn2+", index=index)
        atom = next(a for a in statement.phase.atoms if a.moment is not None)
        dim = len(statement.group.allowed_moment_basis(
            (atom.x.value, atom.y.value, atom.z.value)))
        if dim == 2:
            break
    else:                                        # pragma: no cover - fixture
        pytest.fail("no two-dimensional moment subspace in this candidate set")
    ties = anti_translation_ties(statement.phase)
    assert len(ties) == 2
    scales = {t.rsplit(".", 1)[1]: (s, o) for t, _src, s, o in ties}
    assert scales["dof0"] == (1.0, 0.0)                     # |m| is unchanged
    assert scales["dof1"] == (1.0, pytest.approx(np.pi))    # φ → φ + π
    # and applying them really does state the antipode
    from rietx.crystallography.magnetic.moments import moment_frame, moment_from_dofs

    cell = statement.phase.cell.lengths_angles()
    magnetic = [a for a in statement.phase.atoms if a.moment is not None]
    frames = [moment_frame(statement.group.allowed_moment_basis(
        (a.x.value, a.y.value, a.z.value)), cell) for a in magnetic]
    source_dofs = np.array([1.7, 0.4])
    target_dofs = np.array([1.7 * scales["dof0"][0] + scales["dof0"][1],
                            0.4 * scales["dof1"][0] + scales["dof1"][1]])
    assert np.allclose(moment_from_dofs(frames[1], target_dofs),
                       -moment_from_dofs(frames[0], source_dofs), atol=1e-12)


# ================= the explicit route, for a k ``candidates`` will not take
def test_the_explicit_route_reproduces_the_candidate_route_exactly():
    """A group and its transform state the same phase a candidate does.

    The explicit route exists because ``candidates``' scope fence (2k in the
    reciprocal lattice) is not this module's: a supercell statement needs a child
    lattice, which every commensurate k has, and a magnetic space group in that
    cell, which a database or a k-SUBGROUPSMAG table supplies.  What must not
    differ is the *answer* when both routes are available, and that is asserted
    here rather than argued — same symbol, same cell, same atoms, same operator
    list.
    """
    statement, cand = _statement(pbcm_parent(), (0.25, 0.125, 0.25), HALF_A,
                                 species="Fe", ion="Fe3+")
    again = magnetic_supercell(
        pbcm_parent(), group=statement.group, transform=statement.transform,
        k=cand.cell.k, bns_number=cand.bns_number, magnetic_species="Fe",
        ion="Fe3+", magnitude=2.0)
    assert again.child_space_group == statement.child_space_group
    assert again.transform == statement.transform
    assert again.index == statement.index
    assert again.site_map == statement.site_map
    assert (again.phase.cell.lengths_angles()
            == statement.phase.cell.lengths_angles())
    for a, b in zip(again.phase.atoms, statement.phase.atoms):
        assert a.label == b.label and a.species == b.species
        assert (a.x.value, a.y.value, a.z.value) == (b.x.value, b.y.value, b.z.value)
        assert (a.moment is None) == (b.moment is None)
        if a.moment is not None:
            assert np.allclose(a.moment.values(), b.moment.values(), atol=1e-12)
    assert (again.phase.magnetic_symmetry.operations
            == statement.phase.magnetic_symmetry.operations)



def test_a_bns_number_the_group_is_not_is_refused_on_both_routes():
    """#605: ``bns_number`` was stored on the child phase unchecked, so a
    caller's wrong number was re-exported beside operators it contradicts.

    A BNS number labels a group's type, so it is checked against the group's
    own identification.  Positive arm: the candidate's own number passes, on
    the explicit route exactly as in the test above."""
    statement, cand = _statement(pbcm_parent(), (0.25, 0.125, 0.25), HALF_A,
                                 species="Fe", ion="Fe3+")
    own = statement.group.identify().bns_number
    assert cand.bns_number == own
    wrong = "1.1" if own != "1.1" else "2.4"
    with pytest.raises(ValueError, match=rf"bns_number '{re.escape(wrong)}'"
                                         rf".*BNS {re.escape(own)}"):
        magnetic_supercell(
            pbcm_parent(), group=statement.group, transform=statement.transform,
            k=cand.cell.k, bns_number=wrong, magnetic_species="Fe",
            ion="Fe3+", magnitude=2.0)
    with pytest.raises(ValueError, match=re.escape(wrong)):
        magnetic_supercell(pbcm_parent(), cand, bns_number=wrong,
                           magnetic_species="Fe", ion="Fe3+")
    kept = magnetic_supercell(
        pbcm_parent(), group=statement.group, transform=statement.transform,
        k=cand.cell.k, bns_number=own, magnetic_species="Fe", ion="Fe3+",
        magnitude=2.0)
    assert kept.phase.magnetic_symmetry.bns_number == own

def test_the_magnetic_nuclear_group_keeps_the_structure_factor_identity():
    """``nuclear_group="magnetic"`` costs constraints, not correctness.

    Stating the child phase under the magnetic group's own nuclear part gives a
    *larger* asymmetric unit — the parent's symmetry no longer relates those
    sites — and that is the whole cost.  |F_N|² is untouched, because every atom
    of the child cell is still listed exactly once; asserted against the parent
    on the same reflections as the default route's own control.
    """
    parent = pbcm_parent()
    default, cand = _statement(parent, (0.25, 0.125, 0.25), HALF_A,
                               species="Fe", ion="Fe3+")
    wider = magnetic_supercell(parent, group=default.group,
                               transform=default.transform, k=cand.cell.k,
                               nuclear_group="magnetic",
                               magnetic_species="Fe", ion="Fe3+", magnitude=2.0)
    assert len(wider.phase.atoms) >= len(default.phase.atoms)
    refl = generate_reflections(parent.space_group, PBCM_CELL, 1.8,
                                two_theta_max=120.0)
    mapped = np.rint(refl.hkl @ _p_matrix(wider)).astype(np.int64)
    f2_parent = _nuclear_f2(parent, refl.hkl)
    f2_child = _nuclear_f2(wider.phase, mapped)
    live = f2_parent > 1e-9
    assert np.allclose(f2_child[live] / f2_parent[live], wider.index ** 2,
                       rtol=1e-12)


def test_the_lattice_cosets_are_the_integer_lattice_not_the_parents():
    """|det P| of them, and a negative determinant is not a special case.

    ℤ³/L_child, not L/L_child: ``expand_positions`` already lists a centred
    parent's centring image among the orbit, so adding L/L_child on top counts
    every atom of a centred parent twice.  The count is asserted against
    |det P| directly, and against a transform written with negative entries —
    which is what a database setting routinely gives, to keep a frame
    right-handed.
    """
    from rietx.crystallography.magnetic.supercell import _parse_basis, lattice_cosets

    for text, want in (("a,b,2c;0,0,0", 2), ("2a,b,c;0,0,0", 2),
                       ("-a,2b,-c;0,1/2,0", 2), ("a,2b,2c;0,0,0", 4),
                       ("a,b,c;0,0,0", 1)):
        basis, _origin = _parse_basis(text), None
        cosets = lattice_cosets(basis)
        assert len(cosets) == want, text
        assert len({tuple(c) for c in cosets}) == want
        assert (0, 0, 0) in {tuple(c) for c in cosets}


def test_a_non_standard_setting_of_the_identified_type_is_found():
    """spglib identifies a *type*; the child cell is in whichever setting it is.

    Mn₃O₄'s child group comes back as ``P b c n`` (#60) while the cell is in the
    ``bca`` setting, where the symbol is ``P b n a`` — the symbol the GSAS-II
    Magnetic-V tutorial names in prose.  Refusing on the standard setting alone
    would refuse a statement expressible one qualifier over, so all tabulated
    settings are tried.
    """
    from rietx.crystallography.magnetic.supercell import _settings_of

    settings = _settings_of("P b c n")
    assert settings[0] == "P b c n"
    assert "P b n a" in settings
    assert len(set(settings)) == len(settings)


def test_the_two_routes_are_exclusive_and_say_so():
    parent = p4mmm_parent()
    cand = candidates("P 4/m m m", (0.0, 0.0, 0.0), HALF_C).candidates[0]
    with pytest.raises(ValueError, match="not both and not neither"):
        magnetic_supercell(parent, cand, group=cand.group,
                           transform="a,b,2c;0,0,0", magnetic_species="Mn",
                           ion="Mn2+")
    with pytest.raises(ValueError, match="not both and not neither"):
        magnetic_supercell(parent, magnetic_species="Mn", ion="Mn2+")
    with pytest.raises(ValueError, match="needs its transform"):
        magnetic_supercell(parent, group=cand.group, magnetic_species="Mn",
                           ion="Mn2+")
    with pytest.raises(ValueError, match="nuclear_group="):
        magnetic_supercell(parent, cand, nuclear_group="parental",
                           magnetic_species="Mn", ion="Mn2+")


def test_spglib_underscore_symbols_resolve_to_a_setting():
    """spglib's ``P2_1/m`` must reach the resolver as ``P21/m`` (Ba2FeSbSe5 case).

    Every candidate for Pnma at k = (1/2, 0, 1/2) was refused as inexpressible
    because the child's nuclear group came back from spglib with an underscore
    the resolver does not know; the fix is a normalisation, and this pins it.
    """
    from rietx.crystallography.magnetic import supercell as sc

    assert sc._settings_of("P2_1/m".replace("_", "")) == (
        "P 1 21/m 1", "P 1 1 21/m", "P 21/m 1 1")
    with pytest.raises(ValueError):
        sc.get_spacegroup("P2_1/m")


def test_pnma_half_zero_half_states_in_the_magnetic_nuclear_group():
    """Pnma, a 4c site, k = (1/2, 0, 1/2): four candidates, all statable.

    The ``parent`` route is correctly refused (a glide's half becomes a
    quarter in the 2a,b,a+c cell), the ``magnetic`` route states each as a
    P 1 21/m 1 supercell with four magnetic atoms.  BNS 11.55 (Pa2_1/m, the
    published Ba2FeSbSe5 group) is among them.
    """
    from rietx.crystallography.magnetic import supercell as sc
    from rietx.crystallography.magnetic.isotropy import candidates
    from rietx.schemas.common import Parameter
    from rietx.schemas.structure import Atom, Cell, Phase

    phase = Phase(name="t", space_group="P n m a",
                  cell=Cell(a=Parameter(value=12.6), b=Parameter(value=9.1),
                            c=Parameter(value=9.13), alpha=Parameter(value=90.0),
                            beta=Parameter(value=90.0), gamma=Parameter(value=90.0)),
                  atoms=[Atom(label="Fe1", species="Fe", x=Parameter(value=0.0979),
                              y=Parameter(value=0.25), z=Parameter(value=0.666))])
    found = candidates("P n m a", (0.0979, 0.25, 0.666), ("1/2", "0", "1/2"))
    assert sorted({c.bns_number for c in found}) == ["11.55", "14.82"]
    for c in found:
        with pytest.raises(ValueError):
            sc.magnetic_supercell(phase, candidate=c, magnetic_species="Fe",
                                  ion="Fe3+", nuclear_group="parent")
        st = sc.magnetic_supercell(phase, candidate=c, magnetic_species="Fe",
                                   ion="Fe3+", nuclear_group="magnetic")
        assert st.child_space_group == "P 1 21/m 1"
        assert sum(a.moment is not None for a in st.phase.atoms) == 4


def test_solver_falls_back_to_the_magnetic_nuclear_group_on_a_symbol_refusal():
    """`solve_magnetic`'s statement helper takes the documented remedy itself.

    Before this, the fallback fired only on the lattice-integrality refusal;
    the quarter-translation refusal (Pnma at k = (1/2, 0, 1/2)) made every
    candidate class "refused" and the solver abstain — for a reason with a
    documented answer, which is what the fallback is for.
    """
    from rietx.crystallography.magnetic.isotropy import candidates
    from rietx.schemas.common import Parameter
    from rietx.schemas.structure import Atom, Cell, Phase
    from rietx.strategy.magnetic import _supercell

    phase = Phase(name="t", space_group="P n m a",
                  cell=Cell(a=Parameter(value=12.6), b=Parameter(value=9.1),
                            c=Parameter(value=9.13), alpha=Parameter(value=90.0),
                            beta=Parameter(value=90.0), gamma=Parameter(value=90.0)),
                  atoms=[Atom(label="Fe1", species="Fe", x=Parameter(value=0.0979),
                              y=Parameter(value=0.25), z=Parameter(value=0.666))])
    c = next(c for c in candidates("P n m a", (0.0979, 0.25, 0.666), ("1/2", "0", "1/2"))
             if c.bns_number == "11.55")
    st, used = _supercell(phase, c, species="Fe", ions="Fe3+", magnitude=4.0,
                          nuclear_group="parent")
    assert used == "magnetic"
    assert st.child_space_group == "P 1 21/m 1"


def test_every_spglib_short_symbol_resolves_after_normalisation():
    """All 530 Hall settings: spglib's ``international_short`` reaches the resolver.

    Raw, exactly three fail — ``P2_1``, ``P2_1/m``,
    ``P2_1/c`` (the underscore spelling of a 2_1 screw); with the underscore
    stripped every one resolves, and to the right group number.  spglib's
    ``international_full`` (``P 2/m 2/m 2/m``) and ``international``
    (``P 2 = P 1 2 1``) forms are *not* accepted by the resolver and must not
    be handed to it — the child identification reads ``international_short``.
    """
    import spglib

    from rietx.crystallography.magnetic import supercell as sc

    unresolved, wrong, raw_fail = [], [], set()
    for hall in range(1, 531):
        t = spglib.get_spacegroup_type(hall)
        short = str(t["international_short"] if isinstance(t, dict) else t.international_short)
        number = int(t["number"] if isinstance(t, dict) else t.number)
        try:
            sc.get_spacegroup(short)
        except (ValueError, RuntimeError):
            raw_fail.add(short)
        try:
            sg = sc.get_spacegroup(short.replace("_", ""))
        except (ValueError, RuntimeError):
            unresolved.append(short)
            continue
        if sg.number != number:
            wrong.append((short, sg.number, number))
    assert raw_fail == {"P2_1", "P2_1/m", "P2_1/c"}
    assert unresolved == []
    assert wrong == []


# ================================================ an origin shift on the parent route
def pnnn_parent() -> Phase:
    """P n n n in origin choice 2 (at 1̄): the group whose origin choice matters.

    Centrosymmetric, and its two tabulated origins sit (¼, ¼, ¼) apart, so a
    shift between them is exactly the non-lattice origin a database setting
    routinely carries.  Fe on a 1̄ site, O on a 222 site.
    """
    return Phase(
        name="synthetic Pnnn:2", space_group="P n n n:2",
        cell=_cell(5.0, 6.0, 7.0, 90.0, 90.0, 90.0),
        atoms=[
            Atom(label="Fe", species="Fe", x=P(value=0.0), y=P(value=0.0),
                 z=P(value=0.0), biso=P(value=0.4)),
            Atom(label="O", species="O", x=P(value=0.25), y=P(value=0.25),
                 z=P(value=0.25), biso=P(value=0.6)),
        ])


def _child_site_set(parent: Phase, p_matrix, shift, index: int) -> list[np.ndarray]:
    """Every atom of the child cell, derived here and not by the builder.

    x_c = P⁻¹·(g·x + n − p) over the parent's orbit and the integer translations
    n in a box wide enough to reach every coset, deduplicated modulo the child
    lattice.  Written independently of ``_child_positions`` so the two can
    disagree.
    """
    from rietx.crystallography.symmetry import expand_positions, resolve_group

    sg = resolve_group(parent.space_group, parent.symmetry_operations)
    inverse = np.linalg.inv(np.asarray(p_matrix, dtype=np.float64))
    p = np.array([float(v) for v in shift])
    out: list[np.ndarray] = []
    for atom in parent.atoms:
        xyz = np.array([atom.x.value, atom.y.value, atom.z.value])
        for image in expand_positions(sg, xyz):
            for n in np.ndindex(3, 3, 3):
                q = (inverse @ (image + np.array(n, dtype=np.float64) - p)) % 1.0
                if not any(np.all(np.minimum(np.abs(q - r), 1 - np.abs(q - r)) < 1e-9)
                           for r in out):
                    out.append(q)
    per_cell = sum(len(expand_positions(sg, np.array(
        [a.x.value, a.y.value, a.z.value]))) for a in parent.atoms)
    assert len(out) == index * per_cell
    return out


def _assert_the_child_group_holds_the_child_positions(statement, parent, shift):
    """The child group's orbits of the stated atoms are exactly the child cell."""
    from rietx.crystallography.symmetry import expand_positions, resolve_group

    child = statement.phase
    sg = resolve_group(child.space_group, child.symmetry_operations)
    expected = _child_site_set(parent, _p_matrix(statement), shift, statement.index)
    stated: list[np.ndarray] = []
    for atom in child.atoms:
        stated.extend(expand_positions(sg, np.array(
            [atom.x.value, atom.y.value, atom.z.value])))
    assert len(stated) == len(expected)
    for q in stated:
        assert any(np.all(np.minimum(np.abs(q - r), 1 - np.abs(q - r)) < 1e-9)
                   for r in expected), q
    # and every operation maps the child position set onto itself
    for op in sg.operations():
        for q in expected:
            image = np.array([v for v in op.apply_to_xyz(list(q))]) % 1.0
            assert any(np.all(np.minimum(np.abs(image - r), 1 - np.abs(image - r))
                              < 1e-9) for r in expected), (op.triplet(), q)


@pytest.mark.parametrize("shift", [(0, 0, Fraction(1, 4)), (Fraction(1, 2), 0, 0)])
def test_an_origin_shift_on_the_parent_route_restates_the_parent(shift):
    """``transform="a,b,2c;0,0,1/4"`` builds: restating a parent at a new origin.

    The parent route carries the parent's group through (P, p) and places the
    atoms at x_c = P⁻¹·(x − p); ``MagneticGroup.transformed`` realises
    x' = Q·x + q, so the group has to be handed Q = P⁻¹ and q = −P⁻¹·p.  It
    was handed p, which disagrees with the atoms by (I − W')·(p + P⁻¹·p): a
    lattice vector for ``1/2,0,0`` (which built) and a half-orbit for
    ``0,0,1/4`` (which was refused as a child cell "not holding a whole
    orbit").  The reviewer's reproduction, then the orbit identity asserted
    per operation.  The reproduction passed the unshifted *magnetic* group as
    it came; that group is not a symmetry of the shifted child (Mn at z = 3/8
    goes to 5/8, where there is none), and since issue #597 the child phase
    refuses it, so the magnetic group is carried to the child origin here as
    the next test carries it (``transformed`` under (I, −P⁻¹·p)).
    """
    from rietx.crystallography.magnetic.operators import format_transform

    parent = p4mmm_parent()
    cand = candidates(parent.space_group, (0.0, 0.0, 0.0), HALF_C).candidates[0]
    base = magnetic_supercell(parent, cand, magnetic_species="Mn", ion="Mn2+")
    transform = "a,b,2c;" + ",".join(str(v) for v in shift)
    with pytest.raises(ValueError, match="not a symmetry of the structure"):
        magnetic_supercell(parent, group=base.group, transform=transform,
                           k=cand.cell.k, magnetic_species="Mn", ion="Mn2+")
    child_origin = (-Fraction(shift[0]), -Fraction(shift[1]),
                    -Fraction(shift[2]) / 2)
    group = base.group.transformed(format_transform(
        [[1, 0, 0], [0, 1, 0], [0, 0, 1]], child_origin))
    statement = magnetic_supercell(parent, group=group, transform=transform,
                                   k=cand.cell.k, magnetic_species="Mn",
                                   ion="Mn2+")
    assert statement.transform == transform
    _assert_the_child_group_holds_the_child_positions(statement, parent, shift)
    refl = generate_reflections(parent.space_group, parent.cell.lengths_angles(),
                                1.5, two_theta_max=120.0)
    mapped = np.rint(refl.hkl @ _p_matrix(statement)).astype(np.int64)
    f2_parent, f2_child = _nuclear_f2(parent, refl.hkl), _nuclear_f2(
        statement.phase, mapped)
    live = f2_parent > 1e-9
    assert np.allclose(f2_child[live] / f2_parent[live], statement.index ** 2,
                       rtol=1e-12, atol=0.0)


@pytest.mark.parametrize("shift", [
    (Fraction(1, 4), Fraction(1, 4), Fraction(1, 4)),   # origin choice 2 → 1
    (0, Fraction(1, 4), 0),
    (Fraction(1, 2), 0, 0),
])
def test_a_non_lattice_origin_on_a_centrosymmetric_parent_keeps_its_orbits(shift):
    """The same identity on a group where the shift moves the 1̄ centres.

    P n n n:2 at k = (½, 0, 0), doubled a, with the magnetic group carried to
    the shifted child origin the way a caller supplying a database setting
    would (``transformed`` under (I, −P⁻¹·p)).  The child group must map the
    child's full position list onto itself, the stated atoms' orbits must be
    that list exactly, and the anti-translation law must hold on the seeds.
    """
    from rietx.crystallography.magnetic.operators import format_transform

    parent = pnnn_parent()
    cand = candidates(parent.space_group, (0.0, 0.0, 0.0), HALF_A).candidates[0]
    base = magnetic_supercell(parent, cand, magnetic_species="Fe", ion="Fe3+",
                              magnitude=2.0)
    assert base.transform == "2a,b,c;0,0,0"
    child_origin = (-Fraction(shift[0]) / 2, -Fraction(shift[1]),
                    -Fraction(shift[2]))
    group = base.group.transformed(format_transform(
        [[1, 0, 0], [0, 1, 0], [0, 0, 1]], child_origin))
    transform = "2a,b,c;" + ",".join(str(v) for v in shift)
    statement = magnetic_supercell(parent, group=group, transform=transform,
                                   k=cand.cell.k, magnetic_species="Fe",
                                   ion="Fe3+", magnitude=2.0)
    _assert_the_child_group_holds_the_child_positions(statement, parent, shift)
    assert anti_translation_residual(statement.phase) == pytest.approx(0.0, abs=1e-12)
    moments = [a.moment for a in statement.phase.atoms if a.moment is not None]
    assert moments


def test_an_origin_off_the_operation_grid_is_refused_by_name():
    """A 1/7 origin puts translations gemmi cannot carry: refused, not mis-stated."""
    parent = p4mmm_parent()
    cand = candidates(parent.space_group, (0.0, 0.0, 0.0), HALF_C).candidates[0]
    base = magnetic_supercell(parent, cand, magnetic_species="Mn", ion="Mn2+")
    with pytest.raises(ValueError, match="multiples of 1/24"):
        magnetic_supercell(parent, group=base.group,
                           transform="a,b,2c;1/3,1/5,1/7", k=cand.cell.k,
                           magnetic_species="Mn", ion="Mn2+")


# ============================================== the seed in an oblique child cell
def p6mmm_parent() -> Phase:
    return Phase(
        name="synthetic P6/mmm", space_group="P 6/m m m",
        cell=_cell(5.0, 5.0, 4.0, 90.0, 90.0, 120.0),
        atoms=[Atom(label="Mn", species="Mn", x=P(value=0.5), y=P(value=0.0),
                    z=P(value=0.0), biso=P(value=0.4))])


def _hexagonal_statement(bns: str, **kwargs) -> SupercellStatement:
    parent = p6mmm_parent()
    cand, = [c for c in candidates(parent.space_group, (0.5, 0.0, 0.0),
                                   HALF_C).candidates if c.bns_number == bns]
    return magnetic_supercell(parent, cand, magnetic_species="Mn", ion="Mn2+",
                              magnitude=3.0, **kwargs)


def test_the_seed_has_its_modulus_in_the_child_metric():
    """``magnitude`` is the seed modulus in μ_B, measured in the child's own cell.

    Crystal-axis components are on unit vectors along the cell axes, so a
    moment's modulus depends on the angles between them.  The seed used to be
    normalised in a unit cubic stand-in: on this hexagonal child (γ = 120°,
    BNS 193.262) it came out (1.342, 2.683, 0), modulus 2.324 μ_B for a
    requested 3.  The modulus is read here through ``moment_to_cartesian``,
    not through the metric the builder used.
    """
    from rietx.crystallography.magnetic.operators import moment_to_cartesian

    statement = _hexagonal_statement("193.262")
    cell = statement.phase.cell.lengths_angles()
    assert cell[5] == pytest.approx(120.0)
    seeded = [a for a in statement.phase.atoms if a.moment is not None]
    assert len(seeded) == 2
    for atom in seeded:
        cart = moment_to_cartesian(np.array(atom.moment.values()), cell)
        assert float(np.linalg.norm(cart)) == pytest.approx(3.0, rel=1e-12)


def test_the_seed_tilt_is_an_angle_in_the_child_metric():
    """On a rank-2 site the seed leaves the frame's first row at tan θ = SEED_TILT.

    ``tilted_seed`` puts ``SEED_TILT`` on every metric-orthonormal frame row
    beyond the first, so in the *right* metric the tilt is geometric:
    tan θ = SEED_TILT·√(rank − 1).  BNS 11.56 on the hexagonal child gives Mn a
    rank-2 in-plane basis; the angle is measured between Cartesian vectors.
    """
    from rietx.crystallography.magnetic.moments import SEED_TILT, moment_frame
    from rietx.crystallography.magnetic.operators import moment_to_cartesian

    statement = _hexagonal_statement("11.56", nuclear_group="magnetic")
    cell = statement.phase.cell.lengths_angles()
    atom = next(a for a in statement.phase.atoms if a.moment is not None)
    basis = statement.group.allowed_moment_basis(
        (atom.x.value, atom.y.value, atom.z.value))
    assert len(basis) == 2
    seed = moment_to_cartesian(np.array(atom.moment.values()), cell)
    row0 = moment_to_cartesian(moment_frame(basis, cell)[0], cell)
    assert float(np.linalg.norm(row0)) == pytest.approx(1.0, rel=1e-12)
    cos = float(seed @ row0) / float(np.linalg.norm(seed))
    sin = float(np.linalg.norm(np.cross(seed, row0))) / float(np.linalg.norm(seed))
    assert sin / cos == pytest.approx(SEED_TILT, rel=1e-9)
    assert float(np.linalg.norm(seed)) == pytest.approx(3.0, rel=1e-12)


def test_same_site_wraps_both_arguments():
    """#620 item 3: a stated x = -0.1 is the site at 0.9, not a match for 0.95.

    ``anti_translation_ties`` hands ``_same_site`` a raw coordinate beside an
    image ``act_on_site`` has wrapped into [0, 1); the difference 1.05 made
    ``1 - d`` negative, which passes ``<= tol`` for every pair.
    """
    from rietx.crystallography.magnetic.supercell import _same_site

    assert not _same_site((-0.1, 0.0, 0.0), (0.95, 0.0, 0.0))
    assert _same_site((-0.1, 0.0, 0.0), (0.9, 0.0, 0.0))     # positive arm
    assert _same_site((1.0, 0.0, 0.0), (0.0, 0.0, 0.0))


# ================================================ issue #612: rock salt at k = ½½½
HALF_HALF_HALF = (Fraction(1, 2), Fraction(1, 2), Fraction(1, 2))


def rock_salt_parent() -> Phase:
    """The textbook MnO / NiO parent: F m -3 m, metal at 4a, O at 4b (exact)."""
    return Phase(
        name="rock salt", space_group="F m -3 m", cell=_cell(4.445, 4.445, 4.445, 90, 90, 90),
        atoms=[
            Atom(label="Mn", species="Mn", x=P(value=0.0), y=P(value=0.0),
                 z=P(value=0.0), biso=P(value=0.3)),
            Atom(label="O", species="O", x=P(value=0.5), y=P(value=0.5),
                 z=P(value=0.5), biso=P(value=0.5)),
        ])


@pytest.mark.parametrize("bns", ["167.108", "12.63", "15.90", "2.7"])
def test_rock_salt_at_the_l_point_is_refused_by_name_on_both_branches(bns):
    """Issue #612: every refusal names its branch and its own cause.

    Before, ``nuclear_group="parent"`` quoted the inverse transform and called
    the parent's group the problem, ``"magnetic"`` said "carries the parent's
    space group" on the branch that never uses it, and 2.7 ended in a raw
    pydantic "has no atoms" because ``lattice_cosets`` rounded |det P| = ½ to
    zero cosets.  The causes, stated now:

    * ``"parent"``: the child lattice of k = (½,½,½) is not invariant under the
      cubic point group (k lowers the class), so the parent's group is not a
      group of the child cell.  The text ``MagneticGroup.transformed`` gave stays
      inside the message, because ``strategy.magnetic._supercell`` keys its
      fallback on "onto a lattice".
    * ``"magnetic"``: ``child_basis`` gives a primitive cell of the magnetic
      lattice, half the conventional cell, and atoms are placed by the
      conventional cell's translations modulo the child lattice.  Stating it
      needs a conventional child cell — the child-cell route, not built here —
      so the message says so instead of failing later.
    """
    parent = rock_salt_parent()
    found = candidates("F m -3 m", (0, 0, 0), HALF_HALF_HALF)
    assert [c.bns_number for c in found] == ["167.108", "12.63", "15.90", "2.7"]
    cand = next(c for c in found if c.bns_number == bns)
    with pytest.raises(ValueError) as parent_branch:
        magnetic_supercell(parent, cand, magnetic_species="Mn", ion="Mn2+",
                           magnitude=4.5, nuclear_group="parent")
    text = str(parent_branch.value)
    assert type(parent_branch.value) is ValueError
    assert "nuclear_group='parent'" in text
    assert "'F m -3 m' is not a group of the child cell" in text
    assert "b+c,a/2+b/2+c,a/2+b+c/2" in text           # the cell asked for, by name
    assert "lowers the crystal class" in text
    assert "onto a lattice" in text                     # the solver's fallback key
    with pytest.raises(ValueError) as magnetic_branch:
        magnetic_supercell(parent, cand, magnetic_species="Mn", ion="Mn2+",
                           magnitude=4.5, nuclear_group="magnetic")
    text = str(magnetic_branch.value)
    assert type(magnetic_branch.value) is ValueError    # not pydantic's
    assert "nuclear_group='magnetic'" in text
    assert "|det P| = 1/2" in text
    assert "child-cell route" in text and "#612" in text
    assert "parent's space group" not in text
    assert "has no atoms" not in text


def test_the_solver_fallback_on_rock_salt_ends_in_the_named_refusal():
    """``solve_magnetic``'s helper still falls back on the parent refusal (#612).

    The parent branch's new wording keeps the integrality text, so the fallback
    to ``nuclear_group="magnetic"`` still fires, and what reaches the caller is
    the magnetic branch's named refusal rather than a pydantic error.
    """
    from rietx.strategy.magnetic import _supercell

    cand = next(c for c in candidates("F m -3 m", (0, 0, 0), HALF_HALF_HALF)
                if c.bns_number == "15.90")
    with pytest.raises(ValueError, match=r"nuclear_group='magnetic'.*\|det P\| = 1/2"):
        _supercell(rock_salt_parent(), cand, species="Mn", ions="Mn2+",
                   magnitude=4.5, nuclear_group="parent")


def test_the_magnetic_branch_refusal_names_the_magnetic_groups_nuclear_part():
    """P 4/m m m at k = (0,0,½), 63.466: an orientation refusal on the right branch.

    Issue #612's positive arm.  Three of the four candidates build under both
    branches; 63.466 builds under ``"parent"`` and is refused under
    ``"magnetic"``, whose nuclear part is a C-centred group with diagonal axes
    in a, b, 2c.  That refusal used to say "carries the parent's space group"
    and to recommend ``nuclear_group='magnetic'`` — the branch that refused.
    """
    parent = p4mmm_parent()
    found = candidates("P 4/m m m", (0, 0, 0), HALF_C)
    built = []
    for cand in found:
        for branch in ("parent", "magnetic"):
            try:
                magnetic_supercell(parent, cand, magnetic_species="Mn", ion="Mn2+",
                                   magnitude=2.0, nuclear_group=branch)
                built.append((cand.bns_number, branch))
            except ValueError as exc:
                assert (cand.bns_number, branch) == ("63.466", "magnetic"), str(exc)
                text = str(exc)
                assert "nuclear_group='magnetic'" in text
                assert "magnetic group's own nuclear part" in text
                assert "parent's space group" not in text
                assert "State this structure in the magnetic group's nuclear part" \
                    not in text                                  # not its own remedy
                assert "child-cell route" in text
    assert len(built) == 7


def test_lattice_cosets_refuses_a_fractional_det_p():
    """|det P| = ½ has no ℤ³/L_child to list; it used to return () (#612)."""
    from rietx.crystallography.magnetic.supercell import lattice_cosets

    basis = child_basis("F m -3 m", HALF_HALF_HALF)
    with pytest.raises(ValueError, match=r"\|det P\| = 1/2"):
        lattice_cosets(basis)
    assert len(lattice_cosets(child_basis("P 4/m m m", HALF_C))) == 2   # positive arm


@pytest.mark.parametrize("transform, blames_k", [
    ("a,b,c/2;0,0,0", False),     # integral rotations, axes not lattice vectors
    ("a/2,b,c;0,0,0", True),      # a 4-fold no longer maps the lattice onto one
])
def test_the_parent_branch_explains_the_check_that_failed(transform, blames_k):
    """#787: ``MagneticGroup.transformed`` raises two refusals; the text keys on which.

    A user-supplied ``transform=`` with no k reaches both on P 4/m m m.  Halving
    c keeps every rotation integral but gives twice the operations |det P|
    allows (the new axis is not a lattice vector), and the message must not
    blame a k that is not there.  Halving a breaks the 4-fold's integrality,
    which is the class-lowering case, and keeps its explanation and the
    "onto a lattice" text the solver's fallback keys on.
    """
    cand = candidates("P 4/m m m", (0, 0, 0), HALF_C)[0]
    with pytest.raises(ValueError) as caught:
        magnetic_supercell(p4mmm_parent(), group=cand.group, transform=transform,
                           magnetic_species="Mn", ion="Mn2+", magnitude=2.0)
    text = str(caught.value)
    assert type(caught.value) is ValueError
    assert "nuclear_group='parent'" in text and repr(transform) in text
    assert ("lowers the crystal class" in text) is blames_k
    assert ("nuclear_group='magnetic' is the branch" in text) is blames_k
    assert ("onto a lattice" in text) is blames_k
    assert ("not a supercell of the parent cell" in text) is (not blames_k)
    assert ("not a cell of this group" in text) is (not blames_k)
