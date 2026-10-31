"""Torsion angles with esds, the request form, and the torsion restraint (WP-1815).

The torsion row is a view over what a fit already knows: the value from the
model, the esd J·Cov·Jᵀ through the covariance every other esd comes from.
What is checked here, and against what:

* the **values and their sign**, against two published ``_geom_torsion``
  loops written by two other programs — TOPAS-6 (glutaric acid–
  isonicotinamide, 0.01°) and SHELXL-2019 (benzoic acid, 0.1°) — and the
  table's **completeness**, every published chain being one of its rows;
* the **esd**, against a Monte Carlo of the same covariance through
  ``decode``, the angle recomputed from gemmi's orthogonalisation and wrapped
  as a circular difference, so no code is shared with the propagation: a
  gauche chain, one near 0° and one at exactly 180°.  The last fails with a
  central-difference partial, which straddles the ±180° cut (#759 § 2's
  6·10⁶° esd);
* the **negative arms**, where the right esd is none: a torsion held at 180°
  by an inversion centre, and a bond and a torsion fixed by a rigid body's
  template; and the **positive arm** beside them, the biphenyl twist, whose
  row's esd is the twist parameter's own, from a real fit.  That equality is
  also where the Bérar-Lelann factor is seen to enter once;
* that **the cap lists and never measures**: its note counts exactly what it
  drops, and a row's esd does not depend on the cap or the atom order;
* the **request**: a row the table lists comes back identical, a symmetry
  code round-trips, and with no live fit the values stand and the esds are
  ``None``;
* the **restraint**: its row is the circular difference over σ, smooth across
  the ±180° cut, with partials equal to a central difference of the row.

Data from Linberg, K., Röder, B., Al-Sabbagh, D., Emmerling, F. & Michalchuk,
A. A. L. (2023). Controlling polymorphism in molecular cocrystals by variable
temperature ball milling. *Faraday Discuss.* 241, 178–193,
doi:10.1039/d2fd00115b (COD 1567181); and from Rajput, D. & Dalvi, S. V.
(2026). Brittle or plastic? Revisiting the mechanical behavior of benzoic acid
crystals. *CrystEngComm* 28, 3874–3883, doi:10.1039/d6ce00164e (COD 7252065).
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import gemmi
import numpy as np
import pytest

from rietx import Instrument, PatternData, Refinement
from rietx.crystallography.cif import structure_from_cif
from rietx.crystallography.structure_factor import compile_phase_sites
from rietx.model import geometry as geom
from rietx.model import restraints as rst
from rietx.model.forward import compile_model
from rietx.model.geometry import geometry_from_sites, request_table
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.results import GeometryRequest
from rietx.schemas.structure import Atom, Cell, Phase, Structure, TorsionRestraint
from rietx.strategy.staged import RefinementPlan, Stage
from tests.test_body_torsions import INS, LABELS, POSE_GLOBS, TWIST
from tests.test_body_torsions import _structure as biphenyl_structure
from tests.test_body_torsions import _synthesize as biphenyl_pattern

DATA = Path(__file__).parent / "data"
LAB = Instrument.debye_scherrer(wavelength=1.5406)
CELL = (7.21, 8.13, 9.47, 84.3, 97.6, 104.2)
CELL_NAMES = ("a", "b", "c", "alpha", "beta", "gamma")


def wrap(d: float) -> float:
    """``d`` into (−180, 180], written here rather than imported."""
    return (d + 180.0) % 360.0 - 180.0 if (d + 180.0) % 360.0 else 180.0


def dihedral_from_values(values: dict, ip: int, rows) -> float:
    """The torsion of four (atom, op, shift) entries, through gemmi's frame.

    Shares no code with ``model.restraints``: gemmi orthogonalises, numpy
    crosses, and the sign is Klyne–Prelog's as the atan2 form states it.
    """
    cell = gemmi.UnitCell(*(values[f"phases.{ip}.cell.{k}"] for k in CELL_NAMES))
    pts = []
    for j, (rot, tran) in rows:
        frac = np.array([values[f"phases.{ip}.atoms.{j}.{c}"] for c in "xyz"])
        img = rot @ frac + tran
        pts.append(np.array(cell.orthogonalize(gemmi.Fractional(*img)).tolist()))
    b1, b2, b3 = pts[1] - pts[0], pts[2] - pts[1], pts[3] - pts[2]
    n1, n2 = np.cross(b1, b2), np.cross(b2, b3)
    return math.degrees(math.atan2(np.linalg.norm(b2) * (b1 @ n2), n1 @ n2))


# ----------------------------------------------------------------------
# a free four-atom chain in a triclinic P1 cell, with a planted covariance
# ----------------------------------------------------------------------
def chain_phase(cart: np.ndarray, *, sg: str = "P1", labels=("A", "B", "C", "D"),
                cell=CELL) -> Phase:
    """Four carbons at the Cartesian positions ``cart`` (Å, gemmi's frame)."""
    uc = gemmi.UnitCell(*cell)
    atoms = []
    for lab, p in zip(labels, cart, strict=True):
        f = uc.fractionalize(gemmi.Position(*p))
        atoms.append(Atom(label=lab, species="C", x=Parameter(value=f.x),
                          y=Parameter(value=f.y), z=Parameter(value=f.z)))
    P = Parameter
    return Phase(name="chain", space_group=sg, atoms=atoms,
                 cell=Cell(**{k: P(value=v) for k, v in zip(CELL_NAMES, cell,
                                                             strict=True)}),
                 scale=P(value=1e-3))


def chain_at(phi: float) -> np.ndarray:
    """A–B–C–D with 1.5 Å bonds, 112° bond angles and torsion ``phi`` (deg),
    built in a local frame and placed well inside the cell."""
    t = math.radians(112.0)
    b = np.zeros(3)
    c = np.array([1.5, 0.0, 0.0])
    a = b + 1.5 * np.array([-math.cos(t), math.sin(t), 0.0])
    p = math.radians(phi)
    # D about the B→C axis: at phi = 0 it eclipses A
    d = c + 1.5 * np.array([math.cos(t), math.sin(t) * math.cos(p),
                            math.sin(t) * math.sin(p)])
    origin = np.array([2.6, 3.1, 3.4])
    return np.array([a, b, c, d]) + origin


def planted(structure: Structure, seed: int, *, sd_frac: float = 2.5e-3):
    """A table with every chain coordinate and three cell entries free, and a
    random correlated covariance on them (internal units)."""
    table = ParameterTable(structure, LAB)
    table.set_vary(["*"], False)
    table.set_vary(["phases.0.atoms.*.dof.*", "phases.0.cell.a",
                    "phases.0.cell.c", "phases.0.cell.gamma"], True)
    n = len(table.free_paths)
    rng = np.random.default_rng(seed)
    g = rng.normal(size=(n, n))
    corr = g @ g.T + n * np.eye(n)
    d = np.sqrt(np.diag(corr))
    corr = corr / np.outer(d, d)
    sd = np.full(n, sd_frac)
    for k, path in enumerate(table.free_paths):
        if ".cell." in path:
            sd[k] = 4e-3
    return table, table.x0(), sd, corr


def _torsion_mc(structure, table, theta, sd, corr, request, seed, n_draws):
    """The circular standard deviation of each requested torsion over draws
    of the internal vector, recomputed by :func:`dihedral_from_values`."""
    cov = corr * np.outer(sd, sd)
    rng = np.random.default_rng(seed)
    draws = rng.multivariate_normal(theta, cov, size=n_draws)
    symops = [(np.array(op.rot, float) / gemmi.Op.DEN,
               np.array(op.tran, float) / gemmi.Op.DEN)
              for op in gemmi.SpaceGroup(structure.phases[0].space_group).operations()]
    phase = structure.phases[0]
    labels = [a.label for a in phase.atoms]

    def rows_of(entry):
        out = []
        for ref in entry:
            lab, code = (ref, ".") if isinstance(ref, str) else ref
            if code == ".":
                rot, tran = np.eye(3), np.zeros(3)
            else:
                k, klm = code.split("_")
                rot, tran = symops[int(k) - 1]
                tran = tran + np.array([int(ch) - 5 for ch in klm], float)
            out.append((labels.index(lab), (rot, tran)))
        return out

    entries = [rows_of(e) for e in request.torsions]
    centre = [dihedral_from_values(table.decode(theta), 0, e) for e in entries]
    dev = np.array([[wrap(dihedral_from_values(table.decode(t), 0, e) - c)
                     for e, c in zip(entries, centre, strict=True)] for t in draws])
    return dev.std(axis=0, ddof=1), centre


# ----------------------------------------------------------------------
# the values and the sign, against two published loops
# ----------------------------------------------------------------------
def _published(path: Path) -> list[tuple[tuple[str, ...], float]]:
    block = gemmi.cif.read(str(path)).sole_block()
    loop = block.find([f"_geom_torsion_atom_site_label_{k}" for k in range(1, 5)]
                      + ["_geom_torsion"])
    return [(tuple(row[k] for k in range(4)), float(re.sub(r"\(.*\)", "", row[4])))
            for row in loop]


@pytest.mark.parametrize(("name", "tol"), [
    # TOPAS prints two decimals: half a digit
    ("cod_1567181.cif", 0.005 + 1e-9),
    # SHELXL prints one decimal from unrounded coordinates; the CIF's
    # coordinates carry four, about 5e-4 Å on each of four atoms, which moves
    # a ring torsion by up to ~0.04° (measured worst 0.058°)
    ("cod_7252065.cif", 0.1),
])
def test_torsions_match_two_programs_published_loops(name, tol):
    """Every published torsion, by request, to the precision it was printed.

    Two programs and two kinds of chain: TOPAS-6 on a cocrystal with a
    gauche 64.66° and amide twists of ±13°, SHELXL-2019 on a benzoic acid
    whose every torsion sits within 1.5° of 0° or 180°, where the sign is
    the convention's hardest case.  An opposite sign convention fails both
    (64.66 against −64.66).  The full table holds each published chain as a
    row, read in either direction.
    """
    path = DATA / name
    published = _published(path)
    assert len(published) >= 12
    ref = Refinement(structure_from_cif(path), LAB, history=False)
    got = ref.geometry(GeometryRequest(torsions=[k for k, _ in published]))
    assert not got.notes
    for (labels, want), row in zip(published, got.torsions, strict=True):
        assert (row.atom_1, row.atom_2, row.atom_3, row.atom_4) == labels
        assert abs(wrap(row.angle - want)) <= tol, (labels, row.angle, want)
        assert -180.0 < row.angle <= 180.0
        assert row.stderr is None          # no fit, no covariance
    table = ref.geometry()
    listed = {(r.atom_1, r.atom_2, r.atom_3, r.atom_4) for r in table.torsions}
    listed |= {k[::-1] for k in listed}
    assert all(labels in listed for labels, _ in published)


def test_the_sign_follows_klyne_and_prelog():
    """Looking along B → C, D turned clockwise from A is positive.

    Built from the definition rather than from a formula: A on +x, B at the
    origin, C on +z, so the view along B → C looks down +z, and a D placed
    at +60° counter-clockwise *seen from above* is clockwise to that viewer.
    """
    for want in (60.0, -60.0, 150.0, -150.0):
        p = math.radians(want)
        cart = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 1.5],
                         [math.cos(p), math.sin(p), 1.5]]) * 1.2 + 3.0
        structure = Structure(phases=[chain_phase(cart, cell=(9.0, 9.0, 9.0,
                                                              90.0, 90.0, 90.0))])
        ref = Refinement(structure, LAB, history=False)
        (row,) = ref.geometry({"torsions": [["A", "B", "C", "D"]]}).torsions
        assert row.angle == pytest.approx(want, abs=1e-9)


# ----------------------------------------------------------------------
# the esd, against a Monte Carlo
# ----------------------------------------------------------------------
@pytest.mark.parametrize(("phi", "seed"), [(-65.0, 1), (3.0, 2), (180.0, 3)],
                         ids=["gauche", "near_0", "exactly_180"])
def test_the_esd_matches_a_monte_carlo_of_the_covariance(phi, seed):
    """σ(φ) from J·Cov·Jᵀ against 4 000 draws through ``decode``.

    The draws go through the coordinate DOF ties and the cell entries, and
    the angle is recomputed by gemmi's orthogonalisation, then taken as a
    circular difference from the centre, so a draw across ±180° is a small
    deviation rather than a 360° one.  5 % is the WP's bar: the sampling
    error of a standard deviation at 4 000 draws is 1.1 %, and the
    linearisation's own error at a 1-2° esd is far below it.

    ``exactly_180`` is a planar zig-zag in a P1 cell: z equal for all four
    atoms, so the triple product is exactly zero and the angle is 180.0 to
    the bit — the case a central difference of φ turns into 6·10⁶°.
    """
    if phi == 180.0:
        f = np.array([[0.30, 0.30, 0.40], [0.42, 0.40, 0.40],
                      [0.54, 0.30, 0.40], [0.66, 0.40, 0.40]])
        uc = gemmi.UnitCell(*CELL)
        cart = np.array([uc.orthogonalize(gemmi.Fractional(*r)).tolist() for r in f])
        phase = chain_phase(cart)
        for atom, r in zip(phase.atoms, f, strict=True):     # exact fractions
            atom.x.value, atom.y.value, atom.z.value = (float(v) for v in r)
    else:
        phase = chain_phase(chain_at(phi))
    structure = Structure(phases=[phase])
    table, theta, sd, corr = planted(structure, seed)
    request = GeometryRequest(torsions=[("A", "B", "C", "D")])
    sites = [compile_phase_sites(p) for p in structure.phases]
    (row,) = request_table(request, sites, table, theta, structure,
                           stderr_internal=sd, correlation=corr).torsions
    if phi == 180.0:
        assert row.angle == 180.0
    else:
        assert row.angle == pytest.approx(phi, abs=1e-6)
    assert row.stderr is not None and 0.2 < row.stderr < 20.0
    mc, (centre,) = _torsion_mc(structure, table, theta, sd, corr, request,
                                seed=100 + seed, n_draws=4000)
    assert wrap(centre - row.angle) == pytest.approx(0.0, abs=1e-9)
    assert row.stderr == pytest.approx(mc[0], rel=0.05)
    # the diagonal-only number is a different number with correlations
    assert row.stderr_diagonal is not None and row.stderr_diagonal != row.stderr


def test_a_torsion_held_at_180_by_an_inversion_centre_has_no_esd():
    """A–B–B′–A′ across a centre of symmetry is 180° by symmetry, so its
    variance is exactly zero and only roundoff is left of J·Cov·Jᵀ:
    ``VARIANCE_CANCELLATION_FLOOR`` reports it as no esd, never 0(0).  The
    torsion beside it, A–B–B′ and a fourth atom not on the image chain, keeps
    its esd under the same covariance — the positive arm of the same fixture.
    """
    f = np.array([[0.37, 0.41, 0.58], [0.46, 0.52, 0.55], [0.40, 0.60, 0.70]])
    uc = gemmi.UnitCell(*CELL)
    cart = np.array([uc.orthogonalize(gemmi.Fractional(*r)).tolist() for r in f])
    phase = chain_phase(np.vstack([cart, cart[2] + 0.1]), sg="P-1")
    phase.atoms = phase.atoms[:3]
    for atom, r in zip(phase.atoms, f, strict=True):
        atom.x.value, atom.y.value, atom.z.value = (float(v) for v in r)
    structure = Structure(phases=[Phase.model_validate(phase.model_dump())])
    table, theta, sd, corr = planted(structure, 7)
    sites = [compile_phase_sites(p) for p in structure.phases]
    # operation 2 of P-1 is the inversion; B' = 1 - B sits 0.15 Å-ish away
    request = GeometryRequest(torsions=[
        ("A", "B", ("B", "2_666"), ("A", "2_666")),
        ("C", "B", ("B", "2_666"), ("A", "2_666"))])
    fixed, free = request_table(request, sites, table, theta, structure,
                                stderr_internal=sd, correlation=corr).torsions
    assert fixed.angle == pytest.approx(180.0, abs=1e-9)
    assert fixed.stderr is None and fixed.stderr_diagonal is None
    assert free.stderr is not None and free.stderr > 0.0
    assert (fixed.symmetry_3, fixed.symmetry_4) == ("2_666", "2_666")


# ----------------------------------------------------------------------
# a rigid body: the template's rows have no esd, the twist's has its own
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def biphenyl_fit():
    """WP-1808's biphenyl: a 30° twist planted, recovered by a two-stage fit."""
    pattern = biphenyl_pattern(biphenyl_structure(30.0))
    ref = Refinement(biphenyl_structure(0.0), INS, history=False)
    result = ref.fit(pattern, plan=RefinementPlan(stages=[
        Stage("pose", POSE_GLOBS, max_iter=100),
        Stage("twist", ["phases.*.rigid_bodies.*.torsions.*.twist"], max_iter=200)]))
    return ref, result


def test_a_template_fixed_bond_and_torsion_report_no_esd(biphenyl_fit):
    """A body moves as a whole, so a distance or a torsion inside one ring is
    the template's: its partials do not vanish one by one (every atom
    moves), but J·Cov·Jᵀ cancels to roundoff and the floor reports ``None``.
    The pose's own esds are finite, so the covariance is not empty."""
    ref, result = biphenyl_fit
    assert result.parameter(TWIST).stderr is not None
    got = ref.geometry({"distances": [["C0", "C1"]],
                        "torsions": [["C0", "C1", "C2", "C3"],
                                     ["C7", "C8", "C9", "C10"]]})
    (bond,) = got.distances
    assert bond.distance == pytest.approx(1.39, abs=1e-9)
    assert bond.stderr is None
    assert all(t.stderr is None for t in got.torsions)
    assert all(abs(wrap(t.angle)) < 1e-6 for t in got.torsions)


def test_the_twist_torsion_carries_the_twist_esd_once(biphenyl_fit):
    """C1–C0–C6–C7 turns one for one with the twist, so its esd is the twist
    parameter's — the same covariance, read once.  The parameter's esd
    carries the Bérar-Lelann factor (``stderr``, against
    ``stderr_uncorrected``), so equality here says the factor entered once:
    a second application would multiply the row by it.  And the table that
    ``fit`` stored and the one ``Refinement.geometry`` builds are one table.
    """
    ref, result = biphenyl_fit
    par = result.parameter(TWIST)
    (row,) = ref.geometry({"torsions": [["C1", "C0", "C6", "C7"]]}).torsions
    assert row.stderr == pytest.approx(par.stderr, rel=1e-6)
    assert par.stderr_uncorrected is not None
    factor = par.stderr / par.stderr_uncorrected
    assert factor > 1.0 + 1e-3, factor   # or the pin could not see a second one
    # the template is coplanar and trans across C0–C6, so the row is 180°
    # turned by the twist, one way or the other
    stored = ref.fitted_structure.phases[0].rigid_bodies[0].torsions[0].angle
    assert min(abs(wrap(row.angle - 180.0 - stored)),
               abs(wrap(row.angle - 180.0 + stored))) < 1e-6, (row.angle, stored)
    again = ref.geometry()
    assert again == result.geometry
    assert any(t.stderr is not None for t in again.torsions)


# ----------------------------------------------------------------------
# the cap lists, it never measures
# ----------------------------------------------------------------------
def test_the_torsion_cap_note_counts_exactly_what_it_dropped(monkeypatch):
    """``MAX_TORSIONS_PER_ATOM`` (tier 1's cap clause): the capped table is
    the uncapped one's first rows about each atom, its note's count is the
    shortfall, and each kept row's esd is the one it has uncapped.

    Fluorapatite, whose densely bonded P and Ca reach the cap of 36, with a
    planted covariance on every free coordinate and the cell.
    """
    structure = structure_from_cif(DATA / "fluorapatite.cif")
    table = ParameterTable(structure, LAB)
    table.set_vary(["*"], False)
    table.set_vary(["phases.0.atoms.*.dof.*", "phases.0.cell.a", "phases.0.cell.c"],
                   True)
    n = len(table.free_paths)
    sd = np.full(n, 1e-3)
    corr = np.eye(n)
    sites = [compile_phase_sites(p) for p in structure.phases]

    def table_at(cap):
        monkeypatch.setattr(geom, "MAX_TORSIONS_PER_ATOM", cap)
        return geometry_from_sites(sites, table, table.x0(), structure,
                                   stderr_internal=sd, correlation=corr)

    full, capped = table_at(10 ** 6), table_at(5)
    assert not [n for n in full.notes if "torsion" in n]
    (note,) = [n for n in capped.notes if "torsion" in n]
    dropped = int(re.search(r": (\d+) torsion\(s\) beyond", note).group(1))
    assert dropped == len(full.torsions) - len(capped.torsions) > 0

    def key(r):
        return (r.atom_index_1, r.atom_index_2, r.atom_index_3, r.atom_index_4,
                r.symmetry_1, r.symmetry_3, r.symmetry_4)

    by_b: dict[int, list] = {}
    for r in full.torsions:
        by_b.setdefault(r.atom_index_2, []).append(r)
    for b, rows in by_b.items():
        kept = [r for r in capped.torsions if r.atom_index_2 == b]
        assert [key(r) for r in kept] == [key(r) for r in rows[:5]]
        for r, k in zip(rows[:5], kept, strict=True):
            assert k.angle == r.angle and k.stderr == r.stderr


@pytest.mark.parametrize("name", ["gsas2_bt1_lamno3.cif", "cod_1550439.cif",
                                  "fluorapatite.cif"])
def test_no_torsion_is_listed_again_from_its_other_end(monkeypatch, name):
    """The reversal of a listed chain, carried back by the inverse of its C
    image's operation, is never listed too — checked by positions to 1e-6
    with the codes the rows print, so neither the table's keys nor its
    rounding are reused.  LaMnO₃'s O3 x of 0.48775 sat on a tie of the 1e-4
    rounding the first version keyed on, and 20 of its 298 chains were
    listed twice; the irrational offset of ``_KEY_OFFSET`` ended it."""
    monkeypatch.setattr(geom, "MAX_TORSIONS_PER_ATOM", 10 ** 6)
    structure = structure_from_cif(DATA / name)
    phase = structure.phases[0]
    ops = [(np.array(op.rot, float) / gemmi.Op.DEN,
            np.array(op.tran, float) / gemmi.Op.DEN)
           for op in gemmi.SpaceGroup(phase.space_group).operations()]
    rows = Refinement(structure, LAB, history=False).geometry().torsions
    assert rows
    xyz = np.array([[a.x.value, a.y.value, a.z.value] for a in phase.atoms])

    def image(j, code):
        if code == ".":
            return np.eye(3), xyz[j], np.zeros(3)
        k, klm = code.split("_")
        rot, tran = ops[int(k) - 1]
        tran = tran + np.array([int(ch) - 5 for ch in klm], float)
        return rot, rot @ xyz[j] + tran, tran

    chains = []
    for r in rows:
        codes = (r.symmetry_1, r.symmetry_2, r.symmetry_3, r.symmetry_4)
        if None in codes:
            continue
        idx = (r.atom_index_1, r.atom_index_2, r.atom_index_3, r.atom_index_4)
        placed = [image(j, c) for j, c in zip(idx, codes, strict=True)]
        rot_c, _, tran_c = placed[2]
        inv = np.linalg.inv(rot_c)
        pos = [p for _, p, _ in placed]
        back = [inv @ (p - tran_c) for p in pos[::-1]]
        chains.append((idx, np.array(pos), idx[::-1], np.array(back)))
    for k, (idx, pos, _, _) in enumerate(chains):
        for m, (_, _, ridx, back) in enumerate(chains):
            if m != k and ridx == idx:
                assert np.abs(back - pos).max() > 1e-6, (rows[k], rows[m])


def test_a_torsion_esd_does_not_depend_on_the_order_atoms_are_listed():
    """Stop rule 5's question, measured: the same molecule with its atoms
    listed in reverse gives the same torsions with the same esds (as a
    multiset of |angle| and esd, since which end a chain is read from may
    change), under the same physical covariance."""
    cart = np.vstack([chain_at(-65.0), chain_at(170.0)[2:] + [0.0, 0.0, 3.0]])

    def torsions(order):
        labs = ["A", "B", "C", "D", "E", "F"]
        phase = chain_phase(cart[order], labels=[labs[k] for k in order])
        structure = Structure(phases=[phase])
        table = ParameterTable(structure, LAB)
        table.set_vary(["*"], False)
        table.set_vary(["phases.0.atoms.*.dof.*"], True)
        # one physical covariance: σ per atom label, so reordering moves it
        sd = np.array([1e-3 * (1 + order[int(p.split(".")[3])] % 3)
                       for p in table.free_paths])
        sites = [compile_phase_sites(p) for p in structure.phases]
        req = GeometryRequest(torsions=[("A", "B", "C", "D")])
        row = request_table(req, sites, table, table.x0(), structure,
                            stderr_internal=sd, correlation=np.eye(len(sd)))
        listed = geometry_from_sites(sites, table, table.x0(), structure,
                                     stderr_internal=sd,
                                     correlation=np.eye(len(sd))).torsions
        return row.torsions[0], sorted((round(abs(t.angle), 9), round(t.stderr, 12))
                                       for t in listed)

    one, rows_one = torsions([0, 1, 2, 3, 4, 5])
    two, rows_two = torsions([5, 4, 3, 2, 1, 0])
    assert one.angle == pytest.approx(two.angle, abs=1e-9)
    assert one.stderr == pytest.approx(two.stderr, rel=1e-12)
    assert rows_one and rows_one == rows_two


# ----------------------------------------------------------------------
# the request
# ----------------------------------------------------------------------
def test_a_requested_row_is_the_tables_row():
    """Paracetamol: every torsion the table lists, asked for by its labels and
    codes, comes back with the same value; the distances and angles too."""
    structure = structure_from_cif(DATA / "cod_2104364.cif")
    ref = Refinement(structure, LAB, history=False)
    table = ref.geometry()
    assert len(table.torsions) == 40
    req = GeometryRequest(
        torsions=[((t.atom_1, t.symmetry_1), (t.atom_2, t.symmetry_2),
                   (t.atom_3, t.symmetry_3), (t.atom_4, t.symmetry_4))
                  for t in table.torsions],
        distances=[((d.atom_1, d.symmetry_1), (d.atom_2, d.symmetry_2))
                   for d in table.distances[:30]],
        angles=[((a.atom_1, a.symmetry_1), (a.atom_2, a.symmetry_2),
                 (a.atom_3, a.symmetry_3)) for a in table.angles])
    got = ref.geometry(req)
    for a, b in zip(table.torsions, got.torsions, strict=True):
        assert b.angle == pytest.approx(a.angle, abs=1e-9)
        assert (b.symmetry_3, b.symmetry_4) == (a.symmetry_3, a.symmetry_4)
    for a, b in zip(table.distances[:30], got.distances, strict=True):
        assert b.distance == pytest.approx(a.distance, abs=1e-12)
        assert b.bonded == a.bonded
    for a, b in zip(table.angles, got.angles, strict=True):
        assert b.angle == pytest.approx(a.angle, abs=1e-9)


def test_a_label_alone_takes_the_nearest_image_and_names_its_code():
    """With labels only, each atom sits nearest the one before it, and the
    row names the image it took, which reproduces the row when given back.

    Perhydropyrene (COD 1550439) lists half a molecule about an inversion
    centre, so the chains through the centre reach the other half by an
    image, and their rows carry its code."""
    structure = structure_from_cif(DATA / "cod_1550439.cif")
    ref = Refinement(structure, LAB, history=False)
    table = ref.geometry()
    across = [t for t in table.torsions if t.symmetry_4 not in (".", None)
              and t.symmetry_3 == "."]
    assert across
    t = across[0]
    (plain,) = ref.geometry({"torsions": [[t.atom_1, t.atom_2, t.atom_3,
                                           t.atom_4]]}).torsions
    assert plain.symmetry_4 == t.symmetry_4 != "."
    assert plain.angle == pytest.approx(t.angle, abs=1e-9)
    (coded,) = ref.geometry({"torsions": [[
        (plain.atom_1, plain.symmetry_1), (plain.atom_2, plain.symmetry_2),
        (plain.atom_3, plain.symmetry_3), (plain.atom_4, plain.symmetry_4)]]}
    ).torsions
    assert coded.angle == pytest.approx(plain.angle, abs=1e-12)


def test_a_bad_request_is_refused_by_name():
    structure = structure_from_cif(DATA / "cod_2104364.cif")
    ref = Refinement(structure, LAB, history=False)
    with pytest.raises(ValueError, match="no atom labelled 'Q9'"):
        ref.geometry({"distances": [["C1", "Q9"]]})
    with pytest.raises(ValueError, match="not of the CIF form"):
        ref.geometry({"distances": [["C1", ["C2", "2-555"]]]})
    with pytest.raises(ValueError, match="names operation 9"):
        ref.geometry({"distances": [["C1", ["C2", "9_555"]]]})
    with pytest.raises(ValueError, match="phase 3"):
        ref.geometry({"phase_index": 3, "distances": [["C1", "C2"]]})


def test_a_straight_chain_is_noted_not_listed():
    """A–B–C collinear: no torsion is defined, and the request says so."""
    cart = np.array([[0.0, 0.0, 0.0], [1.5, 0.0, 0.0], [3.0, 0.0, 0.0],
                     [3.5, 1.4, 0.0]]) + 2.0
    structure = Structure(phases=[chain_phase(cart, cell=(9.0, 9.0, 9.0,
                                                          90.0, 90.0, 90.0))])
    got = Refinement(structure, LAB, history=False).geometry(
        {"torsions": [["A", "B", "C", "D"]]})
    assert got.torsions == []
    assert len(got.notes) == 1 and "straight" in got.notes[0]


def test_with_no_live_fit_the_values_stand_and_the_esds_are_none(biphenyl_fit):
    """The covariance is never serialised, so a refinement holding the fitted
    model but no fit of its own (a reopened model, an edit, a checkout) has
    the values and no esds, as a replay's table does."""
    ref, _ = biphenyl_fit
    child = Refinement(ref.fitted_structure.model_copy(deep=True), INS,
                       history=False)
    assert child.result_ is None
    got = child.geometry({"torsions": [["C1", "C0", "C6", "C7"]]})
    want = ref.geometry({"torsions": [["C1", "C0", "C6", "C7"]]})
    (row,) = got.torsions
    assert row.angle == pytest.approx(want.torsions[0].angle, abs=1e-9)
    assert row.stderr is None and row.stderr_diagonal is None
    assert all(t.stderr is None for t in child.geometry().torsions)


@pytest.mark.parametrize("mode", ["lebail", "pawley"])
def test_no_geometry_outside_rietveld_from_the_verb(mode):
    """The verb answers what ``result.geometry`` does: nothing, in a mode
    whose dummy atom is not a structure."""
    from tests.test_coordinates import make_rutile, synthesize_rutile

    ref = Refinement(make_rutile(), LAB, history=False)
    ref.fit(synthesize_rutile(), mode=mode, plan="profile_only")
    assert ref.result_.geometry is None
    assert ref.geometry() is None


# ----------------------------------------------------------------------
# the restraint
# ----------------------------------------------------------------------
def _restrained(target: float, phi: float = 179.9):
    cart = chain_at(phi)
    phase = chain_phase(cart)
    phase.restraints = [TorsionRestraint(atoms=[0, 1, 2, 3], target_deg=target,
                                         sigma=0.5, weight=4.0)]
    structure = Structure(phases=[Phase.model_validate(phase.model_dump())])
    table = ParameterTable(structure, LAB)
    tt = np.arange(20.0, 40.0, 0.1)
    model = compile_model(structure, LAB, PatternData(
        two_theta=tt.tolist(), intensity=np.ones_like(tt).tolist()), mode="rietveld")
    return model, table


@pytest.mark.parametrize(("phi", "target", "want"), [
    (179.9, 180.0, -0.1), (-179.9, 180.0, 0.1), (-179.9, -170.0, -9.9),
    (10.0, -170.0, 180.0), (60.0, 75.0, -15.0)])
def test_the_restraint_row_is_the_circular_difference(phi, target, want):
    """√w·Δ/σ with Δ = φ − target wrapped into (−180, 180]: the two sides of
    the ±180° cut are 0.2° apart, not 359.8°."""
    model, table = _restrained(target, phi)
    values = table.decode(table.x0())
    (row,) = np.asarray(rst.restraint_residual(model.restraints, values))
    assert row == pytest.approx(2.0 * want / 0.5, abs=1e-6)
    report = rst.summarise_restraints(model.restraints, values)
    (r,) = report.rows
    assert r.kind == "torsion" and r.atoms == [0, 1, 2, 3]
    assert r.deviation == pytest.approx(want, abs=1e-6)


@pytest.mark.parametrize("phi", [179.9, -179.95, 64.0])
def test_the_restraint_partials_equal_a_central_difference_of_the_row(phi):
    """The analytic row against a central difference of the *row* — the
    circular difference, smooth at the cut — over every coordinate and cell
    entry, next to 180° and away from it."""
    model, table = _restrained(180.0, phi)
    values = table.decode(table.x0())
    analytic = rst.restraint_partials(model.restraints, values, table)[0]
    for path in [e.path for e in table.entries
                 if ".atoms." in e.path and e.path[-1] in "xyz"
                 or ".cell." in e.path]:
        h = 1e-6 if ".atoms." in path else 1e-5
        up, down = dict(values), dict(values)
        up[path] += h
        down[path] -= h
        fd = (np.asarray(rst.restraint_residual(model.restraints, up))[0]
              - np.asarray(rst.restraint_residual(model.restraints, down))[0]) / (2 * h)
        col = table._paths[path]
        assert analytic[col] == pytest.approx(fd, rel=1e-5, abs=1e-6), path


def test_a_restraint_on_a_straight_chain_is_refused():
    cart = np.array([[0.0, 0.0, 0.0], [1.5, 0.0, 0.0], [3.0, 0.0, 0.0],
                     [3.5, 1.4, 0.0]]) + 2.0
    phase = chain_phase(cart, cell=(9.0, 9.0, 9.0, 90.0, 90.0, 90.0))
    phase.restraints = [TorsionRestraint(atoms=[0, 1, 2, 3], target_deg=180.0,
                                         sigma=1.0)]
    structure = Structure(phases=[Phase.model_validate(phase.model_dump())])
    tt = np.arange(20.0, 40.0, 0.1)
    with pytest.raises(ValueError, match="no torsion is defined"):
        compile_model(structure, LAB, PatternData(
            two_theta=tt.tolist(), intensity=np.ones_like(tt).tolist()),
            mode="rietveld")


def test_the_restraint_schema_refuses_what_it_would_ignore():
    with pytest.raises(ValueError):
        TorsionRestraint(atoms=[0, 1, 2], target_deg=0.0, sigma=1.0)
    with pytest.raises(ValueError, match="would be ignored"):
        TorsionRestraint(atoms=[0, 1, 2, 3], target_deg=0.0, sigma=1.0,
                         translations=[(0, 0, 0), (1, 0, 0), (0, 0, 0), (0, 0, 0)])
    with pytest.raises(ValueError, match="finite"):
        TorsionRestraint(atoms=[0, 1, 2, 3], target_deg=float("nan"), sigma=1.0)
    with pytest.raises(ValueError, match="atoms\\[3\\]=7"):
        Phase(name="p", space_group="P1", scale=Parameter(value=1.0),
              cell=Cell(**{k: Parameter(value=v) for k, v in zip(
                  CELL_NAMES, CELL, strict=True)}),
              atoms=[Atom(label="A", species="C", x=Parameter(value=0.1),
                          y=Parameter(value=0.1), z=Parameter(value=0.1))],
              restraints=[TorsionRestraint(atoms=[0, 0, 0, 7], target_deg=0.0,
                                           sigma=1.0)])


def test_wrap_degrees_is_the_cif_range():
    for raw, want in [(180.0, 180.0), (-180.0, 180.0), (540.0, 180.0),
                      (-0.0, 0.0), (359.0, -1.0), (-181.0, 179.0)]:
        got = rst.wrap_degrees(raw)
        assert got == want and math.copysign(1.0, got) == math.copysign(1.0, want)
    assert LABELS[0] == "C0"     # the biphenyl's labels, read above
