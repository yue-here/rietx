"""A child refined on its mode amplitudes, from the statement to a converged fit (WP-1419 C3a).

``displacive_statement(parent, child, (P, p))`` states a child as its parent
plus one absolute amplitude per symmetry-adapted mode (Perez-Mato, Orobengoa &
Aroyo 2010, *Acta Cryst.* A66, 558, eqs. 3–7), seeds a child that sits at its
parent, and returns the per-parent-site Biso ties.  What is pinned, and
against what:

* **NaTaO₃ P4/mbm at 843 K** (Kennedy, Prodjosantoso & Howard 1999, *J.
  Phys.: Condens. Matter* 11, 6319, doi:10.1088/0953-8984/11/33/302, Table 1:
  a = 5.5503, c = 3.9335 Å, O2 at (¼+u, ¾+u, 0) with u = 0.0241 on Wyckoff
  **4g**, the printed "2b" being a misprint): one M-point mode, which
  Perez-Mato 2010 Table 14 gives as 0.38 Å.  The code's own decomposition of
  the published structure is pinned, and the fit is asked to return it.
* **LaMnO₃ Pnma** from the shipped GSAS-II tutorial CIF (``tests/data/README.md``)
  against Pm-3m, Mn at the origin, in Table 13's setting (a+c, 2b, −a+c;
  ½, 0, ½): seven modes in five irreps.
* Both cases are simulated with rietx's own forward model and Poisson noise:
  the question is whether the block recovers a planted structure from the
  parent, not whether the forward model is right.

**The interpretation table for the multi-irrep case** (acceptance 5, written
2026-10-21 17:54 before the first run):

=====================================================  ==================================
outcome                                                reading
=====================================================  ==================================
converges to the planted A_τ from the default seed     row E met on a multi-irrep child
converges to the planted A_τ in another domain         met; the domain is the seed's
                                                       (Perez-Mato 2010 § 7)
converges to another A_τ pattern, comparable χ²        a false minimum from the seed's
                                                       relative signs: a finding for the
                                                       reporting design, not this block
does not converge                                      a defect in the block or the seed
=====================================================  ==================================

The run landed in the first row (``test_lamno3_from_its_parent_reaches_every_planted_a_tau``).
"""

from __future__ import annotations

import functools
import itertools
import math
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.cif import structure_from_cif
from rietx.crystallography.representation import distortion as D
from rietx.params.vector import ParameterTable
from rietx.schemas.structure import Structure

#: the module fixtures each pin their tests to one worker, by dataset
NATAO3_GROUP = pytest.mark.xdist_group("displacive-natao3")
LAMNO3_GROUP = pytest.mark.xdist_group("displacive-lamno3")

DATA = Path(__file__).parent / "data"
P_ = rx.Parameter
AMPS = "phases.0.distortion_modes.modes.*.amplitude"

# --------------------------------------------------------------------------
# NaTaO₃ (Kennedy et al. 1999, Table 1, 843 K)
# --------------------------------------------------------------------------
NATAO3_A, NATAO3_C, NATAO3_U = 5.5503, 3.9335, 0.0241
NATAO3_T = ([[1, 1, 0], [-1, 1, 0], [0, 0, 1]], [0, 0, 0])
#: the code's decomposition of Kennedy's structure, Å (measured 2026-10-21 on
#: this branch, macOS arm64); Perez-Mato 2010 Table 14 prints 0.38
NATAO3_A_TAU = 0.378621159765

# --------------------------------------------------------------------------
# LaMnO₃ (the shipped GSAS-II tutorial CIF) against Pm-3m, Mn at the origin
# --------------------------------------------------------------------------
LAMNO3_T = ([[1, 0, -1], [0, 2, 0], [1, 0, 1]], [0.5, 0.0, 0.5])


def _atom(label, species, x, y, z, biso=0.5):
    return rx.Atom(label=label, species=species, x=P_(value=x), y=P_(value=y),
                   z=P_(value=z), biso=P_(value=biso))


def _cell(a, b, c):
    return rx.Cell(a=P_(value=a), b=P_(value=b), c=P_(value=c), alpha=P_(value=90.0),
                   beta=P_(value=90.0), gamma=P_(value=90.0))


def natao3_parent(a=NATAO3_A / math.sqrt(2.0)):
    return rx.Phase(name="NaTaO3-cubic", space_group="P m -3 m", cell=rx.Cell.cubic(a), atoms=[
        _atom("Ta", "Ta", 0, 0, 0, 0.7), _atom("Na", "Na", 0.5, 0.5, 0.5, 3.4),
        _atom("O", "O", 0.5, 0, 0, 3.1)])


def natao3_child(u=NATAO3_U, cell=None):
    """Kennedy's 843 K P4/mbm structure, O2 at ``u`` (B from Table 1)."""
    return rx.Phase(name="NaTaO3", space_group="P 4/m b m",
                    cell=cell or _cell(NATAO3_A, NATAO3_A, NATAO3_C), atoms=[
                        _atom("Ta", "Ta", 0, 0, 0, 0.7), _atom("Na", "Na", 0, 0.5, 0.5, 3.4),
                        _atom("O1", "O", 0, 0, 0.5, 3.1),
                        _atom("O2", "O", 0.25 + u, 0.75 + u, 0, 2.4)])


def lamno3_parent(a=3.9):
    return rx.Phase(name="LaMnO3-cubic", space_group="P m -3 m", cell=rx.Cell.cubic(a), atoms=[
        _atom("Mn", "Mn", 0, 0, 0), _atom("La", "La", 0.5, 0.5, 0.5), _atom("O", "O", 0.5, 0, 0)])


def lamno3_child():
    return structure_from_cif(DATA / "gsas2_bt1_lamno3.cif").phases[0]


def at_parent(parent, child, transform) -> rx.Phase:
    """``child`` with every atom moved back to its parent-derived position."""
    record = D.displacive_statement(parent, child, transform, seed=0.0).phase.distortion_modes
    atoms = [a.model_copy(update={c: getattr(a, c).model_copy(update={"value": float(v)})
                                  for c, v in zip("xyz", record.base[j])})
             for j, a in enumerate(child.atoms)]
    return child.model_copy(update={"atoms": atoms})


def neutron():
    return rx.Instrument.constant_wavelength_neutron(1.5, fwhm_deg=0.35)


def simulate(phase, seed, tt=np.arange(11.0, 135.0, 0.05)) -> rx.PatternData:
    """rietx's own pattern of ``phase``, 20 000 counts at the top, 300 flat, Poisson."""
    y = np.asarray(rx.Refinement(Structure(phases=[phase]), neutron(), history=False)
                   .predict(tt))
    y = y / y.max() * 20000.0 + 300.0
    counts = np.random.default_rng(seed).poisson(y).astype(float)
    return rx.PatternData(two_theta=tt.tolist(), intensity=counts.tolist(),
                          sigma=np.sqrt(np.maximum(counts, 1.0)).tolist())


def fit(phase, data, **kw):
    ref = rx.Refinement(Structure(phases=[phase]), neutron(), history=kw.pop("history", False))
    result = ref.fit(data, plan=rx.RefinementPlan.mccusker_structural(), **kw)
    return ref, result


def amplitudes(result) -> dict[str, tuple[float, float | None]]:
    return {p.path: (p.value, p.stderr) for p in result.parameters
            if p.path.endswith(".amplitude")}


@pytest.fixture(scope="module")
def natao3_data():
    return simulate(natao3_child(), seed=7)


@pytest.fixture(scope="module")
def natao3_fit(natao3_data):
    statement = D.displacive_statement(natao3_parent(), natao3_child(0.0), NATAO3_T)
    ref, result = fit(statement.phase, natao3_data)
    return statement, ref, result


@pytest.fixture(scope="module")
def lamno3_data():
    return simulate(lamno3_child(), seed=11, tt=np.arange(10.0, 150.0, 0.05))


# --------------------------------------------------------------------------
# the statement
# --------------------------------------------------------------------------

def test_natao3_is_one_m_point_mode_of_0_38_angstrom():
    """Kennedy's structure decomposes to one mode on O2, 0.378 Å (Table 14: 0.38)."""
    statement = D.displacive_statement(natao3_parent(), natao3_child(), NATAO3_T)
    (mode,) = statement.phase.distortion_modes.modes
    assert (mode.site, mode.k, mode.isotropy_group) == ("O", ("1/2", "1/2", "0"), "P4/mbm (127)")
    assert not mode.parent_invariant
    assert abs(mode.amplitude.value) == pytest.approx(NATAO3_A_TAU, abs=1e-9)
    assert abs(abs(mode.amplitude.value) - 0.38) < 0.01
    # our arithmetic, in the reference metric: 4 O2 per cell, each moved u·a_ref·√2
    a_ref = statement.phase.distortion_modes.reference_cell[0]
    assert abs(mode.amplitude.value) == pytest.approx(
        math.sqrt(4.0) * NATAO3_U * a_ref * math.sqrt(2.0), rel=1e-12)
    assert statement.seed == {}  # a distorted child is never seeded


def test_lamno3_keys_each_mode_by_irrep_k_group_and_site():
    """Seven modes, one per (irrep, orbit) piece, whose norms are the A_τ of mode_amplitudes."""
    parent, child = lamno3_parent(), lamno3_child()
    record = D.displacive_statement(parent, child, LAMNO3_T).phase.distortion_modes
    assert len(record.modes) == 7
    assert {m.site for m in record.modes} == {"La", "O"}
    per_irrep: dict[tuple, float] = {}
    for m in record.modes:
        key = (m.irrep, m.k)
        per_irrep[key] = per_irrep.get(key, 0.0) + m.amplitude.value ** 2
    rows = D.mode_amplitudes(parent, child, LAMNO3_T).rows
    assert {(r.irrep, r.k): r.amplitude for r in rows} == pytest.approx(
        {k: math.sqrt(v) for k, v in per_irrep.items()}, abs=1e-12)
    # La moves in X5+ and R5+ only (the A cation at ½½½ is on 1b): two of seven
    assert sum(m.site == "La" for m in record.modes) == 2


def test_the_statement_reproduces_the_childs_coordinates():
    """x = base + Σ A·v gives back the stated child, and its table builds."""
    child = lamno3_child()
    phase = D.displacive_statement(lamno3_parent(), child, LAMNO3_T).phase
    for got, want in zip(phase.atoms, child.atoms, strict=True):
        for c in "xyz":
            assert getattr(got, c).value == pytest.approx(getattr(want, c).value, abs=1e-12)
    ParameterTable(Structure(phases=[phase]), neutron())


def _case(name):
    return {
        "natao3": lambda: (natao3_parent(), natao3_child(0.0), NATAO3_T),
        "lamno3": lambda: (lamno3_parent(),
                           at_parent(lamno3_parent(), lamno3_child(), LAMNO3_T), LAMNO3_T),
        "p1_pair": p1_pair,
    }[name]()


@functools.cache
def _actions(name):
    """(the statement, its mode fields, G's actions, |H|) for one case, built once.

    The fields are rebuilt the way the statement builds them, independently of
    the statement's own seed check.
    """
    parent, child, transform = _case(name)
    statement = D.displacive_statement(parent, child, transform)
    basis, ref = D._distortion_basis(parent, child, transform, "average")
    big, small = basis.transform
    labels = [a.label for a in parent.atoms]
    order = sorted(range(len(basis.components)),
                   key=lambda i: basis.components[i].primary is not True)
    fields = np.array([v for i in order for _, v in D._site_modes(
        basis.components[i], ref, labels, D._whitener(basis))])
    assert len(fields) == len(statement.phase.distortion_modes.modes)
    actions = D._parent_actions(parent, ref, big, small)
    n_h = len(D._operations(D._group(child))[0])
    return statement, fields, actions, n_h


def _stabiliser(name, amps) -> tuple[int, int]:
    """(|Stab_G(field)|, |H|) for the field ``amps`` puts on the case's modes."""
    _, fields, actions, n_h = _actions(name)
    field = np.tensordot(np.asarray(amps, dtype=float), fields, axes=1)
    return D._stabiliser_order(field, actions), n_h


@pytest.mark.xdist_group("displacive-stabiliser")
@pytest.mark.parametrize("case", ["natao3", "lamno3", "p1_pair"])
def test_the_seed_has_exactly_the_child_group_as_its_stabiliser(case):
    """Acceptance 10: the seed's stabiliser in G is H, by the parent operations' actions."""
    statement = _actions(case)[0]
    seed = [m.amplitude.value for m in statement.phase.distortion_modes.modes]
    assert math.sqrt(sum(a * a for a in seed)) == pytest.approx(D.DISTORTION_SEED, rel=1e-12)
    assert seed[0] > 0.0  # the driving mode's sign chooses the domain
    assert len(statement.seed) == len(seed)
    order, n_h = _stabiliser(case, seed)
    assert order == n_h


@pytest.mark.xdist_group("displacive-stabiliser")
def test_a_seed_along_one_basis_mode_can_have_more_symmetry_than_the_child():
    """Acceptance 10's positive arm: the check can fail, and does where it should.

    LaMnO₃'s Pnma is the intersection of two isotropy subgroups (R4+'s Imma,
    M3+'s P4/mbm), so a seed along the R4+ mode alone keeps Imma: eight more
    operations than Pnma, a stationary point for every mode Imma forbids.
    """
    record = _actions("lamno3")[0].phase.distortion_modes
    keys = [m.isotropy_group for m in record.modes]
    for group in ("Imma (74)", "P4/mbm (127)"):
        one = [1.0 if (k == group and i == keys.index(group)) else 0.0
               for i, k in enumerate(keys)]
        order, n_h = _stabiliser("lamno3", one)
        assert order > n_h, group


def test_seed_zero_states_the_child_at_the_parent_unseeded():
    statement = D.displacive_statement(natao3_parent(), natao3_child(0.0), NATAO3_T, seed=0.0)
    assert statement.seed == {}
    assert [m.amplitude.value for m in statement.phase.distortion_modes.modes] == [0.0]


def test_every_operation_of_the_child_group_carries_each_mode_onto_itself():
    """Row D made concrete: the declared group is the mode field's own stabiliser.

    Positive arm: a lost parent operation (the parent translation a_p) maps the
    NaTaO₃ mode to its negative, so the same check run with it fails.
    """
    parent, child = natao3_parent(), natao3_child()
    basis, ref = D._distortion_basis(parent, child, NATAO3_T, "average")
    ((label, v),) = D._site_modes(basis.components[0], ref, ["Ta", "Na", "O"], D._whitener(basis))
    rot, tran = D._operations(D._group(child))

    def carried(r, t) -> bool:
        image = D._wrap(basis.positions @ r.T.astype(float) + t[None, :])
        for n, pos in enumerate(image):
            d = basis.positions - pos[None, :]
            d -= np.rint(d)
            (hit,) = np.flatnonzero(np.all(np.abs(d) < 1e-6, axis=1))
            if not np.allclose(r @ v[n], v[hit], atol=1e-12):
                return False
        return True

    assert all(carried(r, t) for r, t in zip(rot, tran))
    # the parent translation (1, 0, 0)_p is (½, −½, 0) in the child cell
    assert not carried(np.eye(3, dtype=np.int64), np.array([0.5, -0.5, 0.0]))


def test_a_mixed_occupancy_parent_is_refused_by_name():
    """Inherited from the basis: the modes carry no occupancy weight."""
    parent = natao3_parent()
    parent = parent.model_copy(update={"atoms": [*parent.atoms, _atom("K", "K", 0.5, 0.5, 0.5)]})
    with pytest.raises(ValueError, match="share one site"):
        D.displacive_statement(parent, natao3_child(), NATAO3_T)


# --------------------------------------------------------------------------
# the Biso ties, written once
# --------------------------------------------------------------------------

def test_the_statements_biso_ties_are_the_one_helpers():
    """O2 follows O1 (one parent O) in NaTaO₃; O4 follows O3 in LaMnO₃."""
    for parent, child, transform, want in (
            (natao3_parent(), natao3_child(), NATAO3_T,
             (("phases.0.atoms.3.biso", "phases.0.atoms.2.biso", 1.0, 0.0),)),
            (lamno3_parent(), lamno3_child(), LAMNO3_T,
             (("phases.0.atoms.3.biso", "phases.0.atoms.2.biso", 1.0, 0.0),))):
        statement = D.displacive_statement(parent, child, transform)
        assert statement.biso_ties == D.parent_site_ties(statement.site_map) == want


def test_solve_magnetics_ties_are_byte_identical_after_the_move():
    """The helper replaced ``_parent_site_ties``' body; its answer did not move."""
    from rietx.crystallography.magnetic.isotropy import candidates
    from rietx.crystallography.magnetic.supercell import magnetic_supercell
    from rietx.strategy.magnetic import _parent_site_ties
    from tests.test_magnetic_k_trials import tetragonal

    truth = candidates("P 4/m m m", (0.0, 0.0, 0.0), (0, 0, "1/2"))[0]
    statement = magnetic_supercell(tetragonal(), truth, magnetic_species=["Mn1"],
                                   ion={"Mn1": "Mn3+"}, magnitude=3.0)
    # the body as it stood on main before the move, verbatim
    first: dict[int, int] = {}
    before = []
    for i, (parent_atom, _coset) in enumerate(statement.site_map):
        if parent_atom not in first:
            first[parent_atom] = i
            continue
        before.append((f"phases.0.atoms.{i}.biso",
                       f"phases.0.atoms.{first[parent_atom]}.biso", 1.0, 0.0))
    assert repr(_parent_site_ties(statement)) == repr(tuple(before))
    assert before


# --------------------------------------------------------------------------
# acceptance 1: the amplitude is absolute
# --------------------------------------------------------------------------

def p1_pair():
    """#286's toy: a P 1 parent with one Sr, and its c-doubled child, the pair at ¼ and ¾."""
    parent = rx.Phase(name="toy", space_group="P 1", cell=_cell(4.0, 4.0, 4.0),
                      atoms=[_atom("Sr", "Sr", 0.0, 0.0, 0.5)])
    child = rx.Phase(name="toy-2c", space_group="P 1", cell=_cell(4.0, 4.0, 8.0),
                     atoms=[_atom("Sr1", "Sr", 0.0, 0.0, 0.25), _atom("Sr2", "Sr", 0.0, 0.0, 0.75)])
    return parent, child, (np.diag([1.0, 1.0, 2.0]), np.zeros(3))


def _pair_offsets(ref) -> tuple[float, float]:
    atoms = ref.structure.phases[0].atoms
    return atoms[0].z.value - 0.25, atoms[1].z.value - 0.75


def test_ten_unrelated_writes_leave_an_antiphase_pair_where_its_amplitude_put_it(monkeypatch):
    """Acceptance 1: the four states of the prototype's M3 item 1, and the arm that drifts.

    The pair is moved by one z mode, ±u about its base.  Ten unrelated
    ``set_values`` leave both coordinates bit-for-bit where the amplitude put
    them, so the pair stays symmetric.  **Positive arm**: the same move written
    as a variable tied onto the two coordinate DOFs, on a build whose
    ``rebase_anchored_dofs`` is disabled, re-applies itself at every write
    (#286, 2026-09-16: z ran 0.26 → 0.30 over four such calls).
    """
    parent, child, transform = p1_pair()
    statement = D.displacive_statement(parent, child, transform, seed=0.0)
    record = statement.phase.distortion_modes
    (z_mode,) = [m for m, mode in enumerate(record.modes) if mode.vectors[0][2] != 0.0]
    ref = rx.Refinement(Structure(phases=[statement.phase]), neutron(), history=False)
    amp = f"phases.0.distortion_modes.modes.{z_mode}.amplitude"
    ref.set_values({amp: 0.08})
    up, down = _pair_offsets(ref)
    assert up == pytest.approx(-down, abs=1e-15) and abs(up) == pytest.approx(0.08 / 8.0 / math.sqrt(2.0), rel=1e-12)
    for _ in range(10):
        ref.set_values({"phases.0.scale": 0.02})
        assert _pair_offsets(ref) == (up, down)

    from rietx.params.vector import ParameterTable as Table

    monkeypatch.setattr(Table, "rebase_anchored_dofs", lambda self, paths: [])
    drift = rx.Refinement(Structure(phases=[child]), neutron(), history=False)
    drift.add_variable("A", 0.01, min=-0.5, max=0.5)
    drift.tie("phases.0.atoms.0.dof.2", "vars.A")
    drift.tie("phases.0.atoms.1.dof.2", "vars.A", scale=-1.0)
    for _ in range(10):
        drift.set_values({"phases.0.scale": 0.02})
    moved = _pair_offsets(drift)
    assert abs(moved[0]) > 5 * 0.01 and abs(moved[1]) > 5 * 0.01


@NATAO3_GROUP
def test_a_second_fit_reports_the_amplitude_the_first_left(natao3_fit, natao3_data):
    """Acceptance 1, the other two states: a second fit() and a replayed node."""
    statement, _, first = natao3_fit
    ref = rx.Refinement(Structure(phases=[statement.phase]), neutron())
    one = ref.fit(natao3_data, plan=rx.RefinementPlan.mccusker_structural())
    two = ref.fit(natao3_data, plan=rx.RefinementPlan.mccusker_structural())
    (a1, s1), = amplitudes(one).values()
    (a2, _), = amplitudes(two).values()
    assert a1 == pytest.approx(amplitudes(first)[next(iter(amplitudes(first)))][0], abs=1e-9)
    assert a2 == pytest.approx(a1, abs=0.01 * s1)
    replayed = rx.replay(ref.history, two.node_id, natao3_data)
    rows = {p.path: p.value for p in replayed.parameters}
    o2 = ref.fitted_structure.phases[0].atoms[3]
    assert rows["phases.0.atoms.3.x"] == pytest.approx(o2.x.value, abs=1e-14)
    assert rows["phases.0.atoms.3.y"] == pytest.approx(o2.y.value, abs=1e-14)


# --------------------------------------------------------------------------
# acceptance 2 and 3: the parent, and the zero gradient there
# --------------------------------------------------------------------------

def _child_cell(parent, transform):
    """The child cell Pᵀ·G·P of a cubic parent, its angles exactly 90° here."""
    big = np.asarray(transform[0], dtype=float)
    a = parent.cell.a.value
    lengths = a * np.sqrt(np.sum(big * big, axis=0))
    return _cell(*lengths)


@pytest.mark.parametrize("case", ["natao3", "lamno3"])
def test_with_every_amplitude_zero_the_child_is_the_parent_times_det_p_squared(case):
    """Acceptance 2 (the WP's A = 0 control), on two parents.

    The child at the parent carries |det P| copies of every parent atom, so
    F_child = |det P|·F_parent on the parent's reflections, zero on the
    superlattice ones, and the child at the parent's scale draws |det P|² times
    the parent's pattern.  Bar: round-off in the cell (the child's lengths are
    √2·a, whose last bit moves a peak flank), 1e-10 of the top.
    """
    parent, child, transform = {
        "natao3": (natao3_parent(), natao3_child(0.0), NATAO3_T),
        "lamno3": (lamno3_parent(), at_parent(lamno3_parent(), lamno3_child(), LAMNO3_T),
                   LAMNO3_T)}[case]
    biso = {a.label: a.biso.value for a in parent.atoms}
    statement = D.displacive_statement(parent, child, transform, seed=0.0)
    labels = [parent.atoms[s].label for s in statement.site_map]
    atoms = [a.model_copy(update={"biso": P_(value=biso[lab])})
             for a, lab in zip(statement.phase.atoms, labels, strict=True)]
    phase = statement.phase.model_copy(update={"atoms": atoms,
                                               "cell": _child_cell(parent, transform)})
    tt = np.arange(10.0, 120.0, 0.02)
    y_child = np.asarray(rx.Refinement(Structure(phases=[phase]), neutron()).predict(tt))
    y_parent = np.asarray(rx.Refinement(Structure(phases=[parent]), neutron()).predict(tt))
    det = round(abs(np.linalg.det(np.asarray(transform[0], dtype=float))))
    assert np.max(np.abs(y_child - det ** 2 * y_parent)) <= 1e-10 * np.max(y_child)


def _chi2_of(phase, data, amps: dict[str, float]) -> float:
    ref = rx.Refinement(Structure(phases=[phase]), neutron(), history=False)
    ref.set_values(amps)
    y = np.asarray(ref.predict(np.asarray(data.two_theta)))
    sig = np.asarray(data.sigma)
    # the planted scale is unknown here, so the best scale: χ² stays a smooth
    # even function of the amplitudes
    obs = np.asarray(data.intensity) - 300.0
    s = float(obs @ y / (y @ y))
    return float(np.sum(((obs - s * y) / sig) ** 2))


@NATAO3_GROUP
def test_the_pattern_is_even_in_a_single_driving_mode(natao3_data):
    """Acceptance 3: χ²(+A) = χ²(−A), the lost translation's domain pair."""
    phase = D.displacive_statement(natao3_parent(), natao3_child(0.0), NATAO3_T,
                                   seed=0.0).phase
    amp = "phases.0.distortion_modes.modes.0.amplitude"
    for a in (0.05, 0.2, 0.37):
        plus, minus = (_chi2_of(phase, natao3_data, {amp: s * a}) for s in (1.0, -1.0))
        assert plus == pytest.approx(minus, rel=1e-12)


@LAMNO3_GROUP
def test_every_non_identity_column_is_zero_at_the_parent(lamno3_data):
    """Acceptance 3: the central difference of χ² at A = 0 vanishes, mode by mode.

    Against the one-sided difference at the same step, which is the size the
    column would have if anything but symmetry held it at zero.
    """
    parent = lamno3_parent()
    child = at_parent(parent, lamno3_child(), LAMNO3_T)
    phase = D.displacive_statement(parent, child, LAMNO3_T, seed=0.0).phase
    h = 1e-3
    c0 = _chi2_of(phase, lamno3_data, {})
    for m, mode in enumerate(phase.distortion_modes.modes):
        assert not mode.parent_invariant
        amp = f"phases.0.distortion_modes.modes.{m}.amplitude"
        plus = _chi2_of(phase, lamno3_data, {amp: h})
        minus = _chi2_of(phase, lamno3_data, {amp: -h})
        central = (plus - minus) / (2 * h)
        one_sided = (plus - c0) / h
        assert abs(central) <= 1e-9 * abs(one_sided), (mode.irrep, central, one_sided)


@NATAO3_GROUP
def test_an_identity_irrep_mode_has_a_column_at_the_parent_and_is_not_refused(natao3_data):
    """Acceptance 3's positive arm: a parent with a free coordinate.

    A BaTiO₃-type P4mm parent stated as its own child: every mode is the
    identity irrep (each atom's free z, the translation removed), the parent is
    not a stationary point along any of them, and the all-zero refusal lets
    the block refine from zero.
    """
    parent = rx.Phase(name="polar", space_group="P 4 m m", cell=_cell(3.99, 3.99, 4.03), atoms=[
        _atom("Ti", "Ti", 0, 0, 0.02), _atom("Ba", "Ba", 0.5, 0.5, 0.52),
        _atom("O1", "O", 0, 0, 0.49), _atom("O2", "O", 0.5, 0, 0.0)])
    statement = D.displacive_statement(parent, parent, (np.eye(3), np.zeros(3)))
    modes = statement.phase.distortion_modes.modes
    assert modes and all(m.parent_invariant for m in modes)
    assert statement.seed == {}
    assert all(m.amplitude.value == 0.0 for m in modes)
    table = ParameterTable(Structure(phases=[statement.phase]), neutron())
    assert len(table.set_vary([AMPS], True)) == len(modes)
    data = simulate(parent.model_copy(update={"atoms": [
        a.model_copy(update={"z": P_(value=a.z.value + d)})
        for a, d in zip(parent.atoms, (0.0, 0.01, -0.01, 0.005), strict=True)]}), seed=3)
    h = 1e-3
    amp = "phases.0.distortion_modes.modes.0.amplitude"
    plus, minus = (_chi2_of(statement.phase, data, {amp: s * h}) for s in (1.0, -1.0))
    assert abs(plus - minus) / (2 * h) > 1.0


# --------------------------------------------------------------------------
# acceptance 4 and 5: start at the parent and converge
# --------------------------------------------------------------------------

@NATAO3_GROUP
def test_natao3_from_its_parent_returns_the_planted_amplitude(natao3_fit, natao3_data):
    """Acceptance 4 (milestone row E): one M-point mode, from the seed to 0.378 Å.

    |A| is compared, the sign being a domain; within its esd and 0.01 Å.
    Seeds of ±s give ±A with Rwp equal to ten digits (twelve before main's closing stage, 2.7e-11 after), and a fit freeing the
    block exactly at zero is refused rather than run.
    """
    statement, _, result = natao3_fit
    assert statement.seed == {"phases.0.distortion_modes.modes.0.amplitude": D.DISTORTION_SEED}
    assert result.status == "converged"
    ((value, esd),) = amplitudes(result).values()
    assert abs(abs(value) - NATAO3_A_TAU) < min(esd, 0.01)

    flipped = statement.phase.model_copy(deep=True)
    rec = flipped.distortion_modes
    rec.modes[0].amplitude.value = -D.DISTORTION_SEED
    for c, k in (("x", 0), ("y", 1)):
        getattr(flipped.atoms[3], c).value = rec.base[3][k] - D.DISTORTION_SEED * rec.modes[0].vectors[3][k]
    _, other = fit(flipped, natao3_data)
    ((value2, _),) = amplitudes(other).values()
    assert value2 == pytest.approx(-value, abs=1e-6)
    assert other.statistics.rwp == pytest.approx(result.statistics.rwp, rel=1e-10)

    unseeded = D.displacive_statement(natao3_parent(), natao3_child(0.0), NATAO3_T, seed=0.0)
    with pytest.raises(ValueError, match="exactly zero"):
        fit(unseeded.phase, natao3_data)


@LAMNO3_GROUP
def test_lamno3_from_its_parent_reaches_every_planted_a_tau(lamno3_data):
    """Acceptance 5: seven modes in five irreps, all free, from the builder's seed.

    Pass: each A_τ of the refined structure within 0.01 Å of the planted
    structure's own decomposition.  Measured 2026-10-21: the worst is 0.001 Å,
    the first row of the interpretation table.
    """
    parent, truth = lamno3_parent(), lamno3_child()
    start = at_parent(parent, truth, LAMNO3_T)
    statement = D.displacive_statement(parent, start, LAMNO3_T)
    assert len(statement.seed) == 7
    ref, result = fit(statement.phase, lamno3_data)
    assert result.status == "converged"
    planted = {(r.irrep, r.k): r.amplitude for r in D.mode_amplitudes(parent, truth, LAMNO3_T).rows}
    got = {(r.irrep, r.k): r.amplitude
           for r in D.mode_amplitudes(parent, ref.fitted_structure.phases[0], LAMNO3_T).rows}
    assert got == pytest.approx(planted, abs=0.01)


@pytest.mark.slow
@pytest.mark.xdist_group("displacive-seed")
def test_the_seed_magnitude_does_not_move_the_answer(natao3_fit, natao3_data, lamno3_data):
    """``DISTORTION_SEED`` at 0.003, 0.01 and 0.03 Å: one answer, by margin.

    The constant's audit row reads this: the converged amplitudes agree to a
    hundredth of their esds (measured 2026-10-21: NaTaO₃ to 8 decimals,
    LaMnO₃ to 4), on two perovskites and untested beyond them.
    """
    def run(parent, child, transform, data, seed):
        statement = D.displacive_statement(parent, child, transform, seed=seed)
        _, result = fit(statement.phase, data)
        return amplitudes(result)

    lamno3 = at_parent(lamno3_parent(), lamno3_child(), LAMNO3_T)
    for parent, child, transform, data in (
            (natao3_parent(), natao3_child(0.0), NATAO3_T, natao3_data),
            (lamno3_parent(), lamno3, LAMNO3_T, lamno3_data)):
        answers = [run(parent, child, transform, data, s) for s in (0.003, 0.01, 0.03)]
        for path, (value, esd) in answers[1].items():
            for other in (answers[0], answers[2]):
                assert abs(other[path][0] - value) <= 0.01 * esd, path


# --------------------------------------------------------------------------
# acceptance 6: real data, coordinates against modes
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def bt1():
    from tests.test_acceptance_magnetic_lamno3 import (
        _B,
        CELL,
        CONTAMINANT,
        LIMITS,
        WIDTHS,
        ZERO,
        _instrument,
    )

    data = rx.read_pattern(DATA / "gsas2_bt1_lamno3_50K.gsas").model_copy(
        update={"excluded_regions": [CONTAMINANT]})
    stages = [("scale_bkg", _B), ("zero", _B + [ZERO]), ("cell", _B + [ZERO, CELL]),
              ("widths", _B + [ZERO, CELL, *WIDTHS])]

    def plan(stages):
        return rx.RefinementPlan(stages=[rx.Stage(name=n, turn_on=list(t), max_iter=200)
                                         for n, t in stages], intermediate_ftol=1e-6)

    start = rx.Refinement(structure_from_cif(DATA / "gsas2_bt1_lamno3.cif"), _instrument(),
                          history=False)
    start.fit(data, plan=plan(stages), two_theta_limits=LIMITS)
    final = _B + [ZERO, CELL, *WIDTHS, "phases.0.atoms.*.biso"]
    runs = {}
    statement = D.displacive_statement(lamno3_parent(), start.structure.phases[0], LAMNO3_T)
    for label, structure, free in (
            ("coordinates", start.structure.model_copy(deep=True), "phases.0.atoms.*.dof.*"),
            ("modes", Structure(phases=[statement.phase]), AMPS)):
        ref = rx.Refinement(structure, start.instrument.model_copy(deep=True), history=False)
        result = ref.fit(data, plan=plan([("final", final + [free])]), two_theta_limits=LIMITS)
        runs[label] = (ref, result)
    return statement, runs


@pytest.mark.xdist_group("displacive-bt1")
def test_the_shipped_bt1_pattern_refines_alike_on_coordinates_and_on_modes(bt1):
    """Acceptance 6: seven coordinate DOFs or seven modes, one start, one answer.

    The real BT-1 LaMnO₃ pattern with the GSAS-II tutorial's nuclear model
    (``test_acceptance_magnetic_lamno3``'s protocol to its widths stage), then
    one final stage freeing either.  The two are one linear reparametrisation,
    so the answers agree to the solver's stopping point (measured 2026-10-21:
    Rwp 6e-12 relative, coordinates 1.6e-9, esds 3e-7 relative), and the
    statement of the converged coordinate fit computes its pattern to
    round-off.
    """
    statement, runs = bt1
    assert statement.seed == {}
    (ref_c, res_c), (ref_m, res_m) = runs["coordinates"], runs["modes"]
    assert res_c.status == res_m.status == "converged"
    assert res_m.statistics.rwp == pytest.approx(res_c.statistics.rwp, rel=1e-9)
    rows_c = {p.path: p for p in ref_c.parameters()}
    rows_m = {p.path: p for p in ref_m.parameters()}
    for j in range(4):
        for c in "xyz":
            path = f"phases.0.atoms.{j}.{c}"
            assert rows_m[path].value == pytest.approx(rows_c[path].value, abs=1e-7), path
            if rows_c[path].esd is None:
                assert rows_m[path].esd is None, path
            else:
                assert rows_m[path].esd == pytest.approx(rows_c[path].esd, rel=1e-5), path
    # the exact half: the coordinate fit's answer, restated, draws the same pattern
    restated = D.displacive_statement(lamno3_parent(), ref_c.structure.phases[0], LAMNO3_T)
    tt = np.asarray(res_c.two_theta)
    y_c = np.asarray(ref_c.predict(tt))
    y_m = np.asarray(rx.Refinement(Structure(phases=[restated.phase]), ref_c.instrument)
                     .predict(tt))
    assert np.max(np.abs(y_m - y_c)) <= 1e-10 * np.max(y_c)


@NATAO3_GROUP
def test_a_mode_driven_coordinates_esd_is_its_amplitudes_through_the_vector(natao3_fit):
    """Acceptance 8 on a fit: one mode, so σ_x = |v_x|·σ_A exactly."""
    statement, ref, result = natao3_fit
    ((_, esd),) = amplitudes(result).values()
    v = statement.phase.distortion_modes.modes[0].vectors[3]
    rows = {p.path: p for p in ref.parameters()}
    assert rows["phases.0.atoms.3.x"].esd == pytest.approx(abs(v[0]) * esd, rel=1e-12)
    assert rows["phases.0.atoms.3.y"].esd == pytest.approx(abs(v[1]) * esd, rel=1e-12)


# --------------------------------------------------------------------------
# row D's Le Bail pin, and the P1 statement the reporting design will use
# --------------------------------------------------------------------------

def test_a_le_bail_fit_of_the_statement_ticks_the_crystals_reflections():
    """The statement keeps the child's one group, so Le Bail draws its reflections."""
    from rietx.model.forward import compile_model

    child = lamno3_child()
    statement = D.displacive_statement(lamno3_parent(), child, LAMNO3_T)
    tt = np.arange(10.0, 150.0, 0.05)
    data = rx.PatternData(two_theta=tt.tolist(), intensity=(100.0 + 0.0 * tt).tolist())
    counts = [len(compile_model(Structure(phases=[p]), neutron(), data, mode="lebail")
                  .phases[0].reflections.hkl)
              for p in (child, statement.phase)]
    assert counts[0] == counts[1] > 0


def test_a_p1_supercell_with_every_mode_builds_in_one_pass():
    """Acceptance 11: LaMnO₃'s parent in a P 1 2×2×2 cell, 117 modes in 20 irreps.

    The reporting design's "all modes free" arm.  Measured 2026-10-21 (macOS
    arm64, Mac only): statement 2.8 s, table 12 ms, one Jacobian of 118
    columns on 2200 points 0.30 s.  No fit is asked.
    """
    from rietx.model.forward import compile_model
    from rietx.optimize.least_squares import _jacobian_for

    parent = lamno3_parent()
    sites = [("Mn", (0, 0, 0)), ("La", (0.5, 0.5, 0.5)), ("O", (0.5, 0, 0)),
             ("O", (0, 0.5, 0)), ("O", (0, 0, 0.5))]
    atoms = [_atom(f"{sp}{n}_{s}", sp, (x + i) / 2, (y + j) / 2, (z + k) / 2)
             for n, (i, j, k) in enumerate(itertools.product(range(2), repeat=3))
             for s, (sp, (x, y, z)) in enumerate(sites)]
    child = rx.Phase(name="p1", space_group="P 1", cell=_cell(7.8, 7.8, 7.8), atoms=atoms)
    statement = D.displacive_statement(parent, child, (np.diag([2.0, 2.0, 2.0]), np.zeros(3)))
    modes = statement.phase.distortion_modes.modes
    assert len(modes) == 117 and len({(m.irrep, m.k) for m in modes}) == 20
    assert len(statement.seed) == 117
    structure = Structure(phases=[statement.phase])
    table = ParameterTable(structure, neutron())
    table.set_vary(["*"], False)
    assert len(table.set_vary([AMPS], True)) == 117
    tt = np.arange(10.0, 120.0, 0.05)
    data = rx.PatternData(two_theta=tt.tolist(), intensity=(100.0 + 0.0 * tt).tolist())
    model = compile_model(structure, neutron(), data, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    jac = _jacobian_for(model, table, "numpy")(table.x0())
    assert jac.shape[1] == 117 and np.all(np.isfinite(jac))
