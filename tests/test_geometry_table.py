"""Interatomic distances and angles, with esds from the full covariance (WP-1072).

McCusker *et al.* (1999) §11 makes the chemical sense of the structure one of
the two most important criteria for judging a Rietveld refinement, and §10 says
the e.s.d. of a derived quantity must use "the whole correlation matrix, not
just the diagonal elements".  What is checked here:

* the **distances themselves**, against three published structures whose
  geometry is known independently of this package;
* the **neighbour search is complete**, by orbit counting — |A_ij|·m_i =
  |A_ji|·m_j is a relation the search cannot satisfy by accident, and it caught
  a same-site deduplication that was silently dropping real neighbours;
* the **esd chain**, against a Monte Carlo through ``decode`` — which exercises
  the parameter transforms and the affine coordinate-DOF ties, neither of which
  a partials-only comparison would reach;
* the **symmetry-image pin** the WP asks for: three symmetry-equivalent bonds
  must agree in length *and* in esd, which they do only when each image's
  rotation enters the derivative on the correct side;
* that a **code round-trips** — applying the operation the row names to the
  published coordinates reproduces the distance the row quotes.
"""

from __future__ import annotations

import math
from pathlib import Path

import gemmi
import numpy as np
import pytest

from rietx import Instrument, PatternData, Refinement
from rietx.model import geometry as geom
from rietx.model.forward import compile_model
from rietx.model.geometry import geometry_table, symmetry_operations
from rietx.model.restraints import _metric_g
from rietx.params.vector import ParameterTable
from rietx.schemas.structure import BondRestraint, Structure
from tests.test_acceptance_qpa_roundrobin import (
    corundum_phase,
    fluorite_phase,
    zincite_phase,
)
from tests.test_coordinates import RUTILE_OX, make_rutile, synthesize_rutile

OUT = Path(__file__).parent / "output"
LAB = Instrument.debye_scherrer(wavelength=1.5406)


def _blank(lo: float = 15.0, hi: float = 80.0, step: float = 0.05) -> PatternData:
    tt = np.arange(lo, hi, step)
    return PatternData(two_theta=tt.tolist(), intensity=np.ones_like(tt).tolist())


def _table_for(phase, *, vary: list[str] | None = None):
    """``(GeometryTable, structure, ParameterTable, theta)`` for one phase."""
    structure = Structure(phases=[phase])
    model = compile_model(structure, LAB, _blank(), mode="rietveld")
    table = ParameterTable(structure, LAB)
    if vary is not None:
        table.set_vary(["*"], False)
        table.set_vary(vary, True)
    theta = table.x0()
    return geometry_table(model, table, theta, structure), structure, table, theta


def _distances(g, a: str, b: str) -> list[float]:
    """Sorted bonded distances between the named labels, rounded to 0.1 mÅ."""
    return sorted(round(d.distance, 4) for d in g.bonds
                  if (d.atom_1, d.atom_2) == (a, b))


# ----------------------------------------------------------------------
# the numbers
# ----------------------------------------------------------------------
def test_corundum_matches_the_published_geometry():
    """α-Al₂O₃ against Lewis, Schwarzenbach & Flack (1982) Acta Cryst. A38, 733.

    Al sits in a distorted octahedron: three short Al–O at 1.8551 Å and three
    long at 1.9709 Å, O–Al–O angles at 79.6/86.4/90.8/101.2/164.2°, and the
    shared octahedron edges as the short O···O contacts.  The input
    coordinates are the published ones rounded to five decimals, which is
    where the sub-milliångström difference comes from.
    """
    g, *_ = _table_for(corundum_phase())
    assert _distances(g, "Al", "O") == [1.8548] * 3 + [1.9712] * 3
    angles = sorted(round(a.angle, 2) for a in g.angles
                    if (a.atom_1, a.atom_2, a.atom_3) == ("O", "Al", "O"))
    assert angles == ([79.63] * 3 + [86.37] * 3 + [90.79] * 3
                      + [101.17] * 3 + [164.22] * 3)
    # the shared octahedron edges, McCusker §11's "nonbonding" half
    edges = sorted({round(d.distance, 3) for d in g.contacts
                    if (d.atom_1, d.atom_2) == ("O", "O")})
    assert edges == [2.524, 2.620, 2.725, 2.866]


def test_zincite_and_fluorite_coordination_numbers():
    """Wurtzite ZnO (3 + 1 tetrahedral) and fluorite CaF₂ (cubic 8 : 4).

    The count of rows naming an atom is its coordination number, which is the
    property this table exists to make readable.
    """
    g, *_ = _table_for(zincite_phase())
    assert _distances(g, "Zn", "O") == [1.9734] * 3 + [1.992]
    assert _distances(g, "O", "Zn") == [1.9734] * 3 + [1.992]

    g, *_ = _table_for(fluorite_phase())
    # a√3/4 with a = 5.4631 Å; Ca is 8-coordinate, F is 4-coordinate
    assert _distances(g, "Ca", "F") == [2.3656] * 8
    assert _distances(g, "F", "Ca") == [2.3656] * 4


def test_linear_angle_is_exactly_180_degrees():
    """Fluorite's F–Ca–F through the Ca site is linear, and must read 180.000.

    ``restraints`` clamps cos θ just inside [−1, 1] because a restraint row's
    derivative goes as 1/sin θ; reusing that for a *reported* angle gives
    179.997°.  The geometry table uses the half-angle form instead.
    """
    g, *_ = _table_for(fluorite_phase())
    straight = [a.angle for a in g.angles if a.angle > 179.0]
    assert straight, "fluorite has linear F–Ca–F angles"
    assert max(abs(a - 180.0) for a in straight) < 1e-9


def test_metal_metal_pairs_are_contacts_not_bonds():
    """A covalent-radius criterion is not evidence of an Al···Al bond.

    Corundum's face- and edge-sharing Al pairs are at 2.65 and 2.79 Å, inside
    the 2.82 Å the radii plus the slack allow.  Listed, but as contacts — and
    so they are not arms of any reported angle.
    """
    g, *_ = _table_for(corundum_phase())
    al_al = [d for d in g.distances if (d.atom_1, d.atom_2) == ("Al", "Al")]
    assert al_al and not any(d.bonded for d in al_al)
    assert min(d.distance for d in al_al) < 2.82   # inside the radius criterion
    assert not any("Al" in (a.atom_1, a.atom_3) for a in g.angles
                   if a.atom_2 == "Al")


# ----------------------------------------------------------------------
# the search is complete
# ----------------------------------------------------------------------
@pytest.mark.parametrize("builder", [corundum_phase, zincite_phase, fluorite_phase])
def test_orbit_counting_confirms_every_neighbour_was_found(builder):
    """|A_ij|·m_i = |A_ji|·m_j — the relation a partial search cannot satisfy.

    Counting the i→j neighbours of one atom against the j→i neighbours of the
    other, weighted by the site multiplicities, counts every i–j bond in the
    cell twice by two different routes.  A missing lattice shell, a dropped
    orbit op or an over-eager deduplication all break it; nothing else here
    would have noticed (the deduplication this caught was passing every
    distance-value test in this file).
    """
    phase = builder()
    structure = Structure(phases=[phase])
    model = compile_model(structure, LAB, _blank(), mode="rietveld")
    table = ParameterTable(structure, LAB)
    g = geometry_table(model, table, table.x0(), structure)
    mult = [len(ops[0]) for ops in model.phases[0].sites.ops]

    counts: dict[tuple[int, int, float], int] = {}
    for d in g.distances:
        key = (d.atom_index_1, d.atom_index_2, round(d.distance, 6))
        counts[key] = counts.get(key, 0) + 1
    for (i, j, dist), n_ij in counts.items():
        n_ji = counts.get((j, i, dist))
        assert n_ji is not None, f"{i}->{j} at {dist} has no reverse rows"
        assert n_ij * mult[i] == n_ji * mult[j]


def test_symmetry_code_regenerates_the_image_it_names():
    """Applying the coded operation to the published coordinates gives the row.

    A code is an index into the operation order
    :func:`symmetry_operations` lists (and the exported CIF carries), plus a
    ``klm`` lattice shift offset by 5.  Re-deriving the distance that way uses
    none of the machinery that produced it.
    """
    phase = corundum_phase()
    g, structure, table, theta = _table_for(phase)
    values = table.decode(theta)
    cell = tuple(values[f"phases.0.cell.{k}"]
                 for k in ("a", "b", "c", "alpha", "beta", "gamma"))
    metric = _metric_g(cell)
    triplets = symmetry_operations(phase.space_group)
    xyz = [np.array([values[f"phases.0.atoms.{j}.{c}"] for c in "xyz"])
           for j in range(len(phase.atoms))]

    checked = 0
    for row in g.distances:
        code = row.symmetry_2
        assert code is not None, "corundum needs no shift outside the code"
        if code == ".":
            image = xyz[row.atom_index_2]
        else:
            n, klm = code.split("_")
            op = gemmi.Op(triplets[int(n) - 1])
            shift = np.array([int(c) - 5 for c in klm], dtype=float)
            rot = np.array(op.rot, dtype=float) / gemmi.Op.DEN
            tran = np.array(op.tran, dtype=float) / gemmi.Op.DEN
            image = rot @ xyz[row.atom_index_2] + tran + shift
        dx = image - xyz[row.atom_index_1]
        assert math.sqrt(dx @ metric @ dx) == pytest.approx(row.distance, abs=1e-9)
        checked += 1
    assert checked > 20


# ----------------------------------------------------------------------
# the esds (McCusker §10)
# ----------------------------------------------------------------------
def _rutile_with_covariance(rho: float = 0.6, *, restraints=(),
                            restraint_weight_scale: float = 1.0):
    """Rutile with a planted correlated covariance on (a, c, O-DOF).

    A planted covariance rather than a fitted one, so the propagation is
    checked against an exactly known input.  The tetragonal ``b ← a`` tie
    plus the 4f site's single DOF (x and y move together) make the affine
    block non-trivial.

    ``restraints``/``restraint_weight_scale`` exist for the WP-1074 seam pin
    below: they change the compiled *model* and must change nothing here.
    """
    structure = make_rutile(vary_coords=True)
    structure.phases[0].restraints = list(restraints)
    table = ParameterTable(structure, LAB)
    table.set_vary(["*"], False)
    table.set_vary(["phases.0.cell.a", "phases.0.cell.c",
                    "phases.0.atoms.1.dof.0"], True)
    free = list(table.free_paths)
    assert len(free) == 3
    theta = table.x0()
    stderr_internal = np.array([4e-4, 3e-4, 2e-4])
    correlation = np.array([[1.0, rho, -rho],
                            [rho, 1.0, rho / 2],
                            [-rho, rho / 2, 1.0]])
    model = compile_model(structure, LAB, _blank(), mode="rietveld",
                          restraint_weight_scale=restraint_weight_scale)
    return model, structure, table, theta, stderr_internal, correlation


def test_esd_matches_a_monte_carlo_through_decode():
    """σ from J·Cov·Jᵀ against sampling the same covariance through ``decode``.

    The Monte Carlo perturbs the *internal* vector and decodes, so it goes
    through the softplus on ``a``, the ``b ← a`` crystal-system tie and the
    4f site's x = y = DOF constraint exactly as a refinement does.

    The 5 % bar is set on measurement, not on hope.  The disagreement here has
    a floor of ~2 % that more samples do not remove — the linearisation
    J·Cov·Jᵀ rests on, against a Monte Carlo that carries the curvature — so
    the sample count buys only the scatter around it: over eight seeds at
    5 000 draws the worst row lands between 0.9 % and 2.4 %, and 20 000 draws
    (4× the wall clock) measured 1.9 %.
    """
    model, structure, table, theta, sd, corr = _rutile_with_covariance()
    g = geometry_table(model, table, theta, structure,
                       stderr_internal=sd, correlation=corr)
    rows = [d for d in g.distances if d.atom_index_1 == 0][:4]
    assert rows and all(d.stderr is not None for d in rows)

    cov_int = corr * np.outer(sd, sd)
    rng = np.random.default_rng(20260815)
    draws = rng.multivariate_normal(theta, cov_int, size=5000)
    samples = np.array([
        [_distance_at(table.decode(t), d) for d in rows] for t in draws])
    assert samples.shape == (5000, len(rows))
    mc = samples.std(axis=0, ddof=1)
    for row, sigma in zip(rows, mc, strict=True):
        assert row.stderr == pytest.approx(sigma, rel=0.05)


def test_a_stage_restraint_scale_never_reaches_the_geometry_esds():
    """WP-1074's seam: a stage's c_w must not reach these esds.

    The geometry table calls ``restraint_partials`` with σ = weight = 1 so its
    ``pref`` is 1 and the partials come back unweighted — that is the whole
    reason those numbers are ∂(distance)/∂p and not ∂(row)/∂p.  A stage c_w
    reaching them would scale every esd by √c_w (×10 at the c_w = 100 below)
    while leaving the distances and the ``stderr/stderr_diagonal`` ratio alone.

    This and the Monte Carlo above cover different halves, which was measured
    rather than assumed by injecting both bugs.  An **unconditional** error in
    ``pref`` (a bare factor) fails the Monte Carlo and passes here, because
    both sides of this comparison carry it.  A leak **conditioned on the
    model** — c_w threaded into the partials, the case this WP creates the
    opportunity for — passes the Monte Carlo, whose fixture declares no
    restraints and runs at c_w = 1, and fails here.  Neither test alone is the
    guard the WP-1072 mailbox expected.
    """
    def table_of(**kw):
        model, structure, table, theta, sd, corr = _rutile_with_covariance(**kw)
        return model, geometry_table(model, table, theta, structure,
                                     stderr_internal=sd, correlation=corr)

    _, plain = table_of()
    model, scaled = table_of(
        restraints=[BondRestraint(atom_i=0, atom_j=1, target=1.95, sigma=0.01)],
        restraint_weight_scale=100.0)
    # the model really is carrying both, or the pin is vacuous
    assert model.restraints is not None and model.restraint_weight_scale == 100.0

    for a, b in zip(plain.distances, scaled.distances, strict=True):
        assert a.distance == b.distance
        assert a.stderr == b.stderr
        assert a.stderr_diagonal == b.stderr_diagonal
    assert any(d.stderr for d in plain.distances)
    for a, b in zip(plain.angles, scaled.angles, strict=True):
        assert a.angle == b.angle
        assert a.stderr == b.stderr
        assert a.stderr_diagonal == b.stderr_diagonal


def _distance_at(values: dict[str, float], row) -> float:
    """The row's distance recomputed from a decoded value dict.

    Deliberately re-derived here from the *symmetry code* rather than from the
    frozen image, so the Monte Carlo shares no code path with the propagation
    it checks.
    """
    cell = tuple(values[f"phases.{row.phase_index}.cell.{k}"]
                 for k in ("a", "b", "c", "alpha", "beta", "gamma"))
    metric = _metric_g(cell)
    base = f"phases.{row.phase_index}.atoms"
    x1 = np.array([values[f"{base}.{row.atom_index_1}.{c}"] for c in "xyz"])
    x2 = np.array([values[f"{base}.{row.atom_index_2}.{c}"] for c in "xyz"])
    code = row.symmetry_2
    if code == ".":
        image = x2
    else:
        n, klm = code.split("_")
        triplets = symmetry_operations("P42/mnm")
        op = gemmi.Op(triplets[int(n) - 1])
        rot = np.array(op.rot, dtype=float) / gemmi.Op.DEN
        tran = np.array(op.tran, dtype=float) / gemmi.Op.DEN
        image = rot @ x2 + tran + np.array([int(c) - 5 for c in klm], dtype=float)
    dx = image - x1
    return math.sqrt(dx @ metric @ dx)


def test_full_covariance_and_diagonal_only_disagree():
    """§10's point, measured: ignoring the correlations changes the answer."""
    model, structure, table, theta, sd, corr = _rutile_with_covariance()
    g = geometry_table(model, table, theta, structure,
                       stderr_internal=sd, correlation=corr)
    ratios = [d.stderr / d.stderr_diagonal for d in g.distances
              if d.stderr and d.stderr_diagonal]
    assert ratios
    assert max(abs(r - 1.0) for r in ratios) > 0.05

    # and with an identity correlation the two constructions coincide exactly
    g0 = geometry_table(model, table, theta, structure, stderr_internal=sd,
                        correlation=np.eye(3))
    for d in g0.distances:
        if d.stderr:
            assert d.stderr == pytest.approx(d.stderr_diagonal, rel=1e-12)


def test_symmetry_equivalent_bonds_agree_in_length_and_in_esd():
    """The image pin: an equivalent bond's esd must equal its parent's.

    Length agreement alone is weak — it holds for any consistent placement of
    the image.  The esd additionally requires each image's rotation to enter
    the derivative chain on the correct side (``Rᵀ`` acting on the metric
    gradient, ``R`` on the position), which is the trap the ADP and indexing
    work both fell into with a passing degrees-of-freedom count.
    """
    model, structure, table, theta, sd, corr = _rutile_with_covariance()
    g = geometry_table(model, table, theta, structure,
                       stderr_internal=sd, correlation=corr)
    groups: dict[tuple, list] = {}
    for d in g.distances:
        groups.setdefault((d.atom_index_1, d.atom_index_2,
                           round(d.distance, 9)), []).append(d)
    equivalent = [rows for rows in groups.values() if len(rows) > 1]
    assert equivalent, "rutile has symmetry-equivalent Ti–O bonds"
    for rows in equivalent:
        esds = [r.stderr for r in rows]
        assert all(e is not None for e in esds)
        assert max(esds) == pytest.approx(min(esds), rel=1e-12)


def test_a_symmetry_fixed_angle_carries_no_esd():
    """Rutile's 90° and 180° O–Ti–O angles report no esd; its 99° one does.

    Two different failures, one answer.  At 90° symmetry holds the angle while
    its partials against the individual x, y, z entries do not vanish, so
    gᵀ·Cov·g reaches zero by cancelling and lands on roundoff —
    ``90.00000000000(43)``.  At 180° the geometry is at a stationary point,
    where the linearisation J·Cov·Jᵀ rests on does not hold at all and the
    partials that come back are the cos-clamp's.  Both are absence of
    information, so both report ``None``.
    """
    model, structure, table, theta, sd, corr = _rutile_with_covariance()
    g = geometry_table(model, table, theta, structure,
                       stderr_internal=sd, correlation=corr)
    fixed = [a for a in g.angles
             if min(abs(a.angle - 90.0), abs(a.angle - 180.0)) < 1e-6]
    free = [a for a in g.angles
            if min(abs(a.angle - 90.0), abs(a.angle - 180.0)) > 1.0]
    assert fixed and free
    assert all(a.stderr is None and a.stderr_diagonal is None for a in fixed)
    assert all(a.stderr is not None and a.stderr > 1e-4 for a in free)


def test_no_covariance_gives_no_esd_rather_than_a_diagonal_one():
    """An evaluate-only pass reports the geometry and withholds every esd."""
    g, *_ = _table_for(corundum_phase())
    assert g.distances and g.angles
    assert all(d.stderr is None and d.stderr_diagonal is None
               for d in g.distances)
    assert all(a.stderr is None for a in g.angles)


def test_a_fully_fixed_row_reports_none_not_zero():
    """Every coordinate symmetry-fixed and the cell held: absence, not σ = 0.

    ``weight_fractions``' rule one rank over — an all-zero covariance block is
    absence of information.  In fluorite both sites are fully fixed by
    symmetry, so with only the scale free no Ca–F row has a source of
    variance at all.
    """
    structure = Structure(phases=[fluorite_phase()])
    table = ParameterTable(structure, LAB)
    table.set_vary(["*"], False)
    table.set_vary(["phases.0.scale"], True)
    model = compile_model(structure, LAB, _blank(), mode="rietveld")
    theta = table.x0()
    g = geometry_table(model, table, theta, structure,
                       stderr_internal=np.array([1e-4]),
                       correlation=np.eye(1))
    assert g.distances
    assert all(d.stderr is None for d in g.distances)


# ----------------------------------------------------------------------
# carrier semantics and bounds
# ----------------------------------------------------------------------
def test_a_multi_phase_fit_keeps_the_phases_apart():
    """Three phases in one table, each with its own covariance block.

    Not a redundant shape check.  Every other test here is single-phase, and
    the second phase's esd path is the one nothing else reaches: a loop
    variable shadowing ``theta`` sent the previous phase's *last bond angle*
    into ``physical_covariance`` as the parameter vector, and only real
    two-phase data (11-BM NAC + its CaF₂ impurity) raised on it.
    """
    structure = Structure(phases=[corundum_phase(), zincite_phase(),
                                  fluorite_phase()])
    table = ParameterTable(structure, LAB)
    table.set_vary(["*"], False)
    table.set_vary(["phases.*.cell.a", "phases.*.atoms.*.dof.*"], True)
    free = list(table.free_paths)
    assert len(free) >= 5
    model = compile_model(structure, LAB, _blank(), mode="rietveld")
    theta = table.x0()
    sd = np.full(len(free), 1e-4)
    rng = np.random.default_rng(3)
    a = rng.normal(size=(len(free), len(free)))
    corr = np.corrcoef(a @ a.T)
    g = geometry_table(model, table, theta, structure,
                       stderr_internal=sd, correlation=corr)

    seen = {d.phase_index for d in g.distances}
    assert seen == {0, 1, 2}
    for ip, phase in enumerate(structure.phases):
        rows = [d for d in g.distances if d.phase_index == ip]
        labels = {a.label for a in phase.atoms}
        assert rows and all({d.atom_1, d.atom_2} <= labels for d in rows)
    # every phase that has a free coordinate or cell edge gets real esds
    assert all(any(d.stderr for d in g.distances if d.phase_index == ip)
               for ip in (0, 1, 2))


@pytest.mark.parametrize("mode", ["lebail", "pawley"])
def test_no_geometry_outside_rietveld(mode):
    """The dummy atom those modes require is not a structure to measure."""
    structure = Structure(phases=[corundum_phase()])
    model = compile_model(structure, LAB, _blank(), mode=mode)
    table = ParameterTable(structure, LAB)
    assert geometry_table(model, table, table.x0(), structure) is None


def test_the_contact_cap_is_recorded_not_silent(monkeypatch):
    """A bounded table says it was bounded (CLAUDE.md: no silent caps)."""
    monkeypatch.setattr(geom, "MAX_CONTACTS_PER_ATOM", 2)
    g, *_ = _table_for(corundum_phase())
    assert g.notes and "not listed" in g.notes[0]
    assert all(len([d for d in g.contacts if d.atom_index_1 == i]) <= 2
               for i in (0, 1))


# ----------------------------------------------------------------------
# the three report caps (WP-2002, B10)
# ----------------------------------------------------------------------
# ``CONTACT_MAX_ANG``, ``MAX_CONTACTS_PER_ATOM`` and ``MAX_ASYM_ATOMS`` bound
# what the table lists, never a number in it, so there is no error to bound
# over a domain.  What each claims is a contract on the output: everything
# inside the stated scope is listed, and whatever a cap leaves out is counted
# in ``GeometryTable.notes``.  The tests below hold that contract.  On the
# eight structure CIFs in tests/data the largest asymmetric unit is 32 atoms
# and the most contacts any atom has within 3.5 Å is 20 (cod_2104364,
# P 1 21/n 1), so neither count cap fires on them (measured 2026-10-21).


def _p1_phase(cell, atoms):
    from rietx.schemas.common import Parameter
    from rietx.schemas.structure import Atom, Cell, Phase

    p = Parameter
    return Phase(name="p1", space_group="P 1",
                 cell=Cell(**{k: p(value=v) for k, v in zip(
                     ("a", "b", "c", "alpha", "beta", "gamma"), cell, strict=True)}),
                 atoms=[Atom(label=label, species=species, x=p(value=x), y=p(value=y),
                             z=p(value=z)) for label, species, x, y, z in atoms])


def test_the_contact_search_is_complete_in_an_unreduced_cell():
    """``CONTACT_MAX_ANG``: every pair within the radius is listed, in a cell
    where a fixed shell of lattice shifts is not enough.

    β = 150° on a 3 Å edge, stored unreduced.  The Si···O contact at 3.04 Å
    needs a shift outside {−1, 0, 1}³ around the centred image, so a search
    with that shell lists only the 1.92 Å bond.  Orbit counting cannot see
    this miss: in P 1 the search from either end loses the same image.  The
    reference is a plain enumeration over every shift in −8…8 along each axis,
    past any image within the radius here.

    Made to fail on 2026-10-21: ``geometry._shell`` patched to return the
    fixed {−1, 0, 1}³ shell dropped the 3.04 Å contact.
    """
    import itertools

    cell = (3.0, 6.0, 16.0, 90.0, 150.0, 90.0)
    phase = _p1_phase(cell, [("Si", "Si", 0.857, 0.034, 0.73),
                             ("O", "O", 0.176, 0.863, 0.541)])
    g, structure, _table, _theta = _table_for(phase)
    listed: dict[tuple[int, int], list[float]] = {}
    for d in g.distances:
        listed.setdefault((d.atom_index_1, d.atom_index_2), []).append(round(d.distance, 6))
    metric = _metric_g(cell)
    shifts = np.array(list(itertools.product(range(-8, 9), repeat=3)), dtype=np.float64)
    xyz = [np.array([a.x.value, a.y.value, a.z.value]) for a in structure.phases[0].atoms]
    for i, j in itertools.product(range(2), repeat=2):
        dx = (xyz[j] - xyz[i])[None, :] + shifts
        d = np.sqrt(np.einsum("sa,ab,sb->s", dx, metric, dx))
        expected = sorted(np.round(d[(d > 1e-3) & (d <= g.contact_max)], 6).tolist())
        assert sorted(listed.get((i, j), [])) == expected, (i, j)
    assert 3.035666 in listed[(0, 1)]


def test_the_contact_cap_note_counts_exactly_what_it_dropped(monkeypatch):
    """``MAX_CONTACTS_PER_ATOM``: the note's count is the capped table's
    shortfall against an uncapped one, and what is kept is the nearest.

    Made to fail on 2026-10-21, on a copy of the package whose note counted
    one extra contact for each capped atom: 33 against a shortfall of 31.
    """
    import re

    # the torsion cap's own note is test_the_torsion_cap_... (WP-1815)'s
    monkeypatch.setattr(geom, "MAX_TORSIONS_PER_ATOM", 10 ** 6)
    monkeypatch.setattr(geom, "MAX_CONTACTS_PER_ATOM", 10 ** 6)
    full, *_ = _table_for(corundum_phase())
    assert not full.notes
    monkeypatch.setattr(geom, "MAX_CONTACTS_PER_ATOM", 2)
    capped, *_ = _table_for(corundum_phase())
    (note,) = capped.notes
    dropped = int(re.search(r": (\d+) contact\(s\) beyond", note).group(1))
    assert dropped == len(full.contacts) - len(capped.contacts) > 0
    for i in {d.atom_index_1 for d in full.contacts}:
        nearest = sorted(d.distance for d in full.contacts if d.atom_index_1 == i)[:2]
        kept = sorted(d.distance for d in capped.contacts if d.atom_index_1 == i)
        assert kept == pytest.approx(nearest, abs=1e-12)
    assert len(capped.bonds) == len(full.bonds)


def test_a_phase_too_large_to_search_says_so(monkeypatch):
    monkeypatch.setattr(geom, "MAX_ASYM_ATOMS", 1)
    g, *_ = _table_for(corundum_phase())
    assert g.distances == [] and g.angles == []
    assert g.notes and "search limit" in g.notes[0]


def test_a_bond_past_the_contact_radius_is_found():
    """``CONTACT_MAX_ANG`` bounds contacts, never bonds.  CsCl's Cs–Cl at
    a√3/2 = 3.571 Å is inside the radii's 2.44 + 1.02 + 0.4 = 3.86 Å and past
    the 3.5 Å contact radius, so each ion lists its eight counter-ions and
    nothing else: Cs···Cs and Cl···Cl sit at a = 4.123 Å.

    Made to fail on 2026-10-21: with the search stopped at the contact radius
    the table listed no distance at all.
    """
    phase = _p1_phase((4.123,) * 3 + (90.0,) * 3,
                      [("Cs", "Cs", 0.0, 0.0, 0.0), ("Cl", "Cl", 0.5, 0.5, 0.5)])
    phase = phase.model_copy(update={"space_group": "P m -3 m"})
    g, *_ = _table_for(phase)
    assert _distances(g, "Cs", "Cl") == [3.5706] * 8
    assert _distances(g, "Cl", "Cs") == [3.5706] * 8
    # no contact note; the eight-fold Cs–Cl chains are over the torsion cap
    # (WP-1815), which notes say in their own words
    assert g.contacts == [] and not [n for n in g.notes if "contact" in n]
    assert len([a for a in g.angles if a.atom_2 == "Cs"]) == 28


def test_the_criteria_travel_with_the_table():
    g, *_ = _table_for(corundum_phase())
    assert g.bond_slack == geom.BOND_SLACK_ANG
    assert g.contact_max == geom.CONTACT_MAX_ANG
    assert all(d.distance <= g.contact_max + 1e-9 for d in g.contacts)
    assert len(g.bonds) + len(g.contacts) == len(g.distances)


# ----------------------------------------------------------------------
# end to end
# ----------------------------------------------------------------------
def test_a_real_fit_recovers_the_synthesised_geometry():
    """Rutile refined from a synthetic pattern, against the structure that made it.

    TiO₂ has four equatorial Ti–O and two apical.  The truth here is the
    structure the pattern was synthesised from, not a remembered literature
    figure, so the assertion is about this refinement and not about how well
    the fixture matches a paper — and the tolerance is the *propagated* esd,
    which is the quantity this WP adds.
    """
    truth, *_ = _table_for(make_rutile().phases[0])
    reference = sorted(round(d.distance, 4) for d in truth.bonds
                       if (d.atom_1, d.atom_2) == ("Ti", "O"))
    assert len(reference) == 6 and len(set(reference)) == 2  # 4 + 2

    pattern = synthesize_rutile()
    structure = make_rutile(RUTILE_OX + 0.012)
    structure.phases[0].scale.value = 6.0e-3
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 1.2e-2
    ref = Refinement(structure, ins, history=False)
    result = ref.fit(pattern, plan="mccusker_structural")
    assert result.status == "converged"

    g = result.geometry
    assert g is not None
    rows = [d for d in g.bonds if (d.atom_1, d.atom_2) == ("Ti", "O")]
    assert len(rows) == 6
    assert all(d.stderr is not None and d.stderr > 0 for d in rows)
    for row, want in zip(sorted(rows, key=lambda d: d.distance), reference,
                         strict=True):
        assert row.distance == pytest.approx(want, abs=4 * row.stderr)
    # a Ti–O esd of a hundredth of an ångström or worse would mean the
    # propagation is picking up something other than this fit
    assert max(d.stderr for d in rows) < 0.01

    OUT.mkdir(exist_ok=True)
    pytest.importorskip("matplotlib")
    from rietx.viz.plots import plot_result

    plot_result(result, path=str(OUT / "geometry_rutile_fit.png"))


@pytest.mark.parametrize("cell", [(5.1, 6.3, 7.7, 81.0, 97.5, 112.0),
                                  (4.0, 4.0, 9.0, 90.0, 90.0, 120.0)])
def test_the_volume_gradient_is_the_volume_s_derivative(cell):
    """∂V/∂(a, b, c, α, β, γ) against a central difference, angles in degrees."""
    v, grad = geom._volume_and_gradient(*cell)
    assert v == pytest.approx(gemmi.UnitCell(*cell).volume, rel=1e-12)
    for k in range(6):
        h = 1e-6 * (1.0 if k < 3 else 10.0)
        up, down = list(cell), list(cell)
        up[k] += h
        down[k] -= h
        fd = (geom._volume_and_gradient(*up)[0] - geom._volume_and_gradient(*down)[0]) / (2 * h)
        assert grad[k] == pytest.approx(fd, rel=1e-7, abs=1e-9)
