"""WP-1419 C2: the cell of an operator-list child through a ``DerivedBlock`` (#286).

A child phase whose ``parent_cell`` is set refines its parent's cell under the
parent's own constraints plus the Γ strains its own group allows; its six cell
parameters are a :class:`~rietx.params.parent_cell.ParentCellBlock`'s locked
outputs (``crystallography.metric``).  The acceptance this file pins:

* the five displacive children of the shipped Pnma LaMnO₃ that
  ``magnetic_supercell`` refused (a C-centred type in a primitive doubled cell,
  no metric the closest-type lookup could state) now build;
* with every strain held, the derived route is bit-identical to the child
  stated with its own cell, over the k-sweep's settings and the tabulated
  settings, and the metrics it can reach are exactly the child group's
  invariant ones — a **span** test both ways, never a dimension count (the
  root CLAUDE.md's Rᵀ trap, whose positive arm is here too);
* esds reach the child's cell through the block;
* a freed strain recovers a planted one, and comes back at zero within its esd
  where none was planted.
"""

from __future__ import annotations

import functools
import itertools
from fractions import Fraction

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography import metric
from rietx.crystallography import symmetry as sym
from rietx.crystallography.cif import structure_from_cif
from rietx.crystallography.lattice import direct_metric_tensor
from rietx.crystallography.magnetic import isotropy
from rietx.crystallography.magnetic import supercell as sc
from rietx.crystallography.magnetic.operators import parse_transform
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import EmissionLine, Instrument, Source
from rietx.schemas.pattern import PatternData
from rietx.schemas.structure import Atom, Cell, ParentCell, Phase, Structure

pytestmark = pytest.mark.xdist_group("parent-cell")   # the LaMnO₃ candidates, once

INSTRUMENT = Instrument(source=Source(lines=[EmissionLine(wavelength=1.540598)]))
TWO_THETA = np.arange(5.0, 100.0, 0.02)
CELL_NAMES = ("a", "b", "c", "alpha", "beta", "gamma")
VOIGT = ((0, 0), (1, 1), (2, 2), (0, 1), (0, 2), (1, 2))


def _cell(values) -> Cell:
    return Cell(**{n: Parameter(value=v) for n, v in zip(CELL_NAMES, values, strict=True)})


def _one_atom(symbol: str, values, xyz=(0.11, 0.13, 0.17), ops=None) -> Phase:
    """A generic one-atom phase: a nominal cell and a general position.

    ``candidates`` reads a site only through its stabiliser and orbit, so no
    fitted or published structure is involved.
    """
    return Phase(name="p", space_group=symbol, symmetry_operations=ops,
                 cell=_cell(values),
                 atoms=[Atom(label="M1", species="Fe", x=Parameter(value=float(xyz[0])),
                             y=Parameter(value=float(xyz[1])),
                             z=Parameter(value=float(xyz[2])),
                             occ=Parameter(value=1.0), biso=Parameter(value=0.5))])


def _voigt(g) -> np.ndarray:
    return np.array([g[i][j] for i, j in VOIGT], dtype=np.float64)


def _span_residual(columns, basis) -> float:
    """Largest relative distance of a column from the span of ``basis``'s rows."""
    columns = [np.asarray(c, dtype=np.float64) for c in columns]
    if not columns:
        return 0.0
    q, _ = np.linalg.qr(np.asarray(basis, dtype=np.float64).T)
    return max(float(np.linalg.norm(c - q @ (q.T @ c))
                     / max(np.linalg.norm(c), 1e-300)) for c in columns)


def _metric_tangent(table: ParameterTable) -> list[np.ndarray]:
    """∂G′/∂θ (Voigt) of phase 0's decoded cell, one column per free entry.

    Central differences in θ through ``decode`` — so through the block, and the
    affine ties of the parent's own cell — with a 1e-6 relative step.
    """
    theta = table.x0()
    cols = []
    for k in range(len(theta)):
        h = 1e-6 * max(1.0, abs(theta[k]))

        def g(t):
            v = table.decode(t)
            return _voigt(direct_metric_tensor(*(v[f"phases.0.cell.{n}"]
                                                 for n in CELL_NAMES)))
        up, down = theta.copy(), theta.copy()
        up[k] += h
        down[k] -= h
        cols.append((g(up) - g(down)) / (2.0 * h))
    return cols


def _invariant_metrics(phase: Phase) -> np.ndarray:
    group = sym.resolve_group(phase.space_group, phase.symmetry_operations)
    return metric.invariant_metric_basis(metric.rotations_of(group)).astype(np.float64)


# ---------------------------------------------------------------------------
# the shipped Pnma LaMnO₃ and the five children main refused
# ---------------------------------------------------------------------------
@functools.lru_cache(maxsize=1)
def _lamno3() -> Phase:
    return structure_from_cif("tests/data/gsas2_bt1_lamno3.cif").phases[0]


@functools.lru_cache(maxsize=8)
def _candidates(k):
    parent = _lamno3()
    la = parent.atoms[0]
    return isotropy.candidates(parent.space_group, (la.x.value, la.y.value, la.z.value),
                               k, kind="displacive").candidates


def _child(k, irrep, direction, **kwargs):
    cand = next(c for c in _candidates(k)
                if c.irrep_label == irrep and c.direction.label == direction)
    return sc.magnetic_supercell(_lamno3(), cand, nuclear_group="magnetic", **kwargs)


#: (k, irrep, direction) → the child's label and how many Γ strains its group
#: allows, measured on this fixture.  The three Cm/Cc children are monoclinic
#: in a cell whose axes are not conventional for them, so one shear survives;
#: Cmc2₁'s mm2 leaves the parent's orthorhombic metric as it is.
REFUSED_FIVE = (
    (((0.5, 0.5, 0), "S1", "(rank 2)#3"), "Cm [unnamed in 2a,a+b,c]", 1),
    (((0, 0.5, 0.5), "S1", "(rank 1)#2"), "Cmc21 [unnamed in a,2b,b+c]", 0),
    (((0, 0.5, 0.5), "S2", "(rank 1)#2"), "Cmc21 [unnamed in a,2b,b+c]", 0),
    (((0.5, 0.5, 0.5), "S1", "(rank 2)#2"), "Cc [unnamed in 2a,a+b,a+c]", 1),
    (((0.5, 0.5, 0.5), "S1", "(rank 2)#3"), "Cm [unnamed in 2a,a+b,a+c]", 1),
)


@pytest.mark.parametrize("case,label,n_strain", REFUSED_FIVE,
                         ids=[f"{c[0]}{c[1]}{c[2]}".replace(" ", "")
                              for c, _, _ in REFUSED_FIVE])
def test_the_five_refused_pnma_children_build(case, label, n_strain):
    """Each builds, states its cell through the parent, and predicts.

    The negative arm is the same call with ``parent_cell=False``: the refusal
    main gave, so these five need the derived cell and nothing else.
    """
    with pytest.raises(ValueError, match="cell's metric constraints are undefined"):
        _child(*case, parent_cell=False)
    statement = _child(*case)
    phase = statement.phase
    assert phase.space_group == label
    assert phase.parent_cell is not None
    assert phase.parent_cell.space_group == _lamno3().space_group
    assert phase.parent_cell.transform == statement.transform
    assert len(phase.parent_cell.strain) == n_strain
    assert all(p.value == 0.0 and not p.vary for p in phase.parent_cell.strain)
    # the stated cell is the parent's carried through P, to the bit
    p_matrix, _ = parse_transform(statement.transform)
    assert phase.cell.lengths_angles() == sc._child_cell_parameters(
        _lamno3().cell.lengths_angles(), p_matrix)
    assert any("Phase.parent_cell" in d.message for d in statement.diagnostics)

    table = ParameterTable(Structure(phases=[phase]), INSTRUMENT)
    for n in CELL_NAMES:
        entry = table.entries[table._paths[f"phases.0.cell.{n}"]]
        assert entry.locked and entry.tie is None
    assert table.derived_paths() == {f"phases.0.cell.{n}" for n in CELL_NAMES}
    y = np.asarray(rx.Refinement(Structure(phases=[phase]), INSTRUMENT).predict(TWO_THETA))
    assert np.isfinite(y).all() and y.max() > 0.0


def test_a_plan_glob_frees_the_parent_cell_never_the_childs_or_a_strain():
    """``phases.*.cell.*`` reaches the parent's free edges and nothing else.

    The child's six are locked (the block writes them) and a strain is freed
    only by naming it: a plan written for an ordinary phase refines this one's
    cell the way #746 asks, with the strain held until the data show one.
    """
    phase = _child((0.5, 0.5, 0), "S1", "(rank 2)#3").phase
    table = ParameterTable(Structure(phases=[phase]), INSTRUMENT)
    hits = table.set_vary(["phases.*.cell.*"], True)
    assert sorted(hits) == [f"phases.0.parent_cell.cell.{n}" for n in ("a", "b", "c")]
    assert table.set_vary(["phases.*.parent_cell.strain.*"], True) == [
        "phases.0.parent_cell.strain.0"]


# ---------------------------------------------------------------------------
# strains held: bit-identical, and the span is the child group's
# ---------------------------------------------------------------------------
#: Q-17's k-sweep rows (parent setting, k, a nominal cell of its own system),
#: the settings whose children ``magnetic_supercell`` once could not state.
SWEEP_ROWS = (
    ("P c c 2", ("1/2", "1/2", "0"), (6.0, 7.0, 8.0, 90.0, 90.0, 90.0)),
    ("C m m 2", ("0", "0", "1/2"), (6.0, 7.0, 9.0, 90.0, 90.0, 90.0)),
    ("P c c a", ("1/2", "1/2", "0"), (6.0, 7.0, 8.0, 90.0, 90.0, 90.0)),
    ("P c c n", ("1/2", "1/2", "0"), (6.0, 7.0, 8.0, 90.0, 90.0, 90.0)),
    ("P 42 c m", ("0", "0", "1/2"), (6.0, 6.0, 9.0, 90.0, 90.0, 90.0)),
    ("P 42 c m", ("1/2", "1/2", "0"), (6.0, 6.0, 9.0, 90.0, 90.0, 90.0)),
    ("P 42 n m", ("0", "0", "1/2"), (6.0, 6.0, 9.0, 90.0, 90.0, 90.0)),
    ("P 4 c c", ("1/2", "1/2", "0"), (6.0, 6.0, 9.0, 90.0, 90.0, 90.0)),
    ("P -4 c 2", ("1/2", "1/2", "0"), (6.0, 6.0, 9.0, 90.0, 90.0, 90.0)),
    ("P 42/m c m", ("0", "0", "1/2"), (6.0, 6.0, 9.0, 90.0, 90.0, 90.0)),
    ("P 42/n n m:1", ("0", "0", "1/2"), (6.0, 6.0, 9.0, 90.0, 90.0, 90.0)),
    ("P 42/m n m", ("0", "0", "1/2"), (6.0, 6.0, 9.0, 90.0, 90.0, 90.0)),
    ("P 42/n c m:1", ("0", "0", "1/2"), (6.0, 6.0, 9.0, 90.0, 90.0, 90.0)),
    ("P n -3 m:1", ("0", "0", "1/2"), (6.0, 6.0, 6.0, 90.0, 90.0, 90.0)),
    ("P 6 m m", ("0", "0", "1/2"), (6.0, 6.0, 9.0, 90.0, 90.0, 120.0)),
)
#: one row per k-family and lattice for the fast run; the slow run takes all
FAST_ROWS = tuple(r for r in SWEEP_ROWS if r[0] in ("P 4 c c", "P 6 m m", "C m m 2"))
GENERAL = (Fraction(11, 100), Fraction(13, 100), Fraction(17, 100))
ORIGIN = (Fraction(0), Fraction(0), Fraction(0))
#: a magnetic candidate needs its moment-bearing species named (#1077's refusal)
MOMENT = {"magnetic_species": "Fe", "ion": "Fe3+"}


def _sweep_children(rows):
    """Every child of every candidate of each row, at the origin and a general
    site, by both nuclear routes.

    Yields (ordinary statement, derived statement); the ordinary one is
    ``parent_cell=None``'s, which is itself a derived cell exactly where the
    child group names no tabulated type in its axes.
    """
    for (setting, k, values), site in itertools.product(rows, (ORIGIN, GENERAL)):
        kk = tuple(Fraction(c) for c in k)
        parent = _one_atom(setting, values, xyz=site)
        for cand in isotropy.candidates(setting, site, kk):
            for route in ("magnetic", "parent"):
                try:
                    ordinary = sc.magnetic_supercell(parent, cand, nuclear_group=route,
                                                     **MOMENT)
                except ValueError:
                    continue        # a route that does not reach this child at all
                derived = sc.magnetic_supercell(parent, cand, nuclear_group=route,
                                                parent_cell=True, **MOMENT)
                yield ordinary, derived


def _check_sweep(rows) -> dict[str, float | int]:
    worst = {"children": 0, "own_cell": 0, "true_metric": 0.0,
             "derived_in_invariant": 0.0, "invariant_in_derived": 0.0,
             "own_route_spans": 0.0}
    for ordinary, derived in _sweep_children(rows):
        worst["children"] += 1
        phase = derived.phase
        invariant = _invariant_metrics(phase)
        g = _voigt(direct_metric_tensor(*phase.cell.lengths_angles()))
        worst["true_metric"] = max(worst["true_metric"], _span_residual([g], invariant))
        table = ParameterTable(Structure(phases=[phase.model_copy(deep=True)]), INSTRUMENT)
        table.set_vary(["phases.*.cell.*", "phases.*.parent_cell.strain.*"], True)
        tangent = _metric_tangent(table)
        worst["derived_in_invariant"] = max(worst["derived_in_invariant"],
                                            _span_residual(tangent, invariant))
        worst["invariant_in_derived"] = max(worst["invariant_in_derived"],
                                            _span_residual(list(invariant), tangent))
        if ordinary.phase.parent_cell is not None:
            continue
        worst["own_cell"] += 1
        assert ordinary.phase.cell.lengths_angles() == phase.cell.lengths_angles()
        own = ParameterTable(Structure(phases=[ordinary.phase.model_copy(deep=True)]),
                             INSTRUMENT)
        own.set_vary(["phases.*.cell.*"], True)
        own_tangent = _metric_tangent(own)
        worst["own_route_spans"] = max(worst["own_route_spans"],
                                       _span_residual(own_tangent, tangent),
                                       _span_residual(tangent, own_tangent))
        y_own = np.asarray(rx.Refinement(Structure(phases=[ordinary.phase]),
                                         INSTRUMENT).predict(TWO_THETA))
        y_derived = np.asarray(rx.Refinement(Structure(phases=[phase]),
                                             INSTRUMENT).predict(TWO_THETA))
        assert np.array_equal(y_own, y_derived), (phase.name, phase.space_group)
    return worst


def _assert_sweep(worst):
    # FD tangents at a 1e-6 step: the residuals are ~1e-10 where the spans
    # agree, and O(1) for a direction one side lacks
    assert worst["true_metric"] < 1e-12, worst
    assert worst["derived_in_invariant"] < 1e-7, worst
    assert worst["invariant_in_derived"] < 1e-7, worst
    assert worst["own_route_spans"] < 1e-7, worst
    assert worst["own_cell"] > 0, worst


def test_strains_held_the_derived_cell_is_the_childs_own_and_spans_its_metrics():
    """Fast subset of the sweep: (½,½,0) tetragonal, (0,0,½) hexagonal and C-centred."""
    worst = _check_sweep(FAST_ROWS)
    _assert_sweep(worst)
    assert worst["children"] >= 40, worst


@pytest.mark.slow
def test_the_whole_sweep_is_bit_identical_and_spans_the_childs_metrics():
    """All 15 sweep rows × every candidate × both routes (208 children).

    The 215 candidates give 430 (candidate, route) pairs.  365 built while a
    magnetic candidate could be stated with no moment; since #1077 it names its
    moment-bearing species, and 157 more pairs are then refused for their
    moments (a mixed-axis setting ``allowed_moment_basis`` cannot answer, a BNS
    label, a site image) before any cell is built.  61 of the 208 have a
    tabulated cell of their own, the rest need the parent's.
    """
    worst = _check_sweep(SWEEP_ROWS)
    _assert_sweep(worst)
    assert worst["children"] == 208, worst


#: One setting per ``cell_constraints`` branch: cubic, tetragonal, hexagonal,
#: trigonal on hexagonal and on rhombohedral axes, the three monoclinic unique
#: axes, triclinic, P- and C-orthorhombic (WP-1419's "ten named settings", with
#: the three monoclinic axes counted separately).
NAMED_SETTINGS = (
    ("F d -3 m:2", (8.4, 8.4, 8.4, 90.0, 90.0, 90.0)),
    ("I 41/a m d:2", (5.8, 5.8, 9.4, 90.0, 90.0, 90.0)),
    ("P 63/m m c", (3.2, 3.2, 5.2, 90.0, 90.0, 120.0)),
    ("R -3 c:H", (4.9, 4.9, 13.8, 90.0, 90.0, 120.0)),
    ("R -3 c:R", (5.4, 5.4, 5.4, 56.3, 56.3, 56.3)),
    ("P 2 1 1", (5.1, 6.2, 7.3, 97.4, 90.0, 90.0)),
    ("P 1 21/m 1", (5.1, 6.2, 7.3, 90.0, 103.1, 90.0)),
    ("P 1 1 2", (5.1, 6.2, 7.3, 90.0, 90.0, 111.9)),
    ("P -1", (5.1, 6.2, 7.3, 84.3, 97.6, 104.2)),
    ("P n m a", (5.7, 7.7, 5.5, 90.0, 90.0, 90.0)),
    ("C m c m", (3.1, 10.2, 4.3, 90.0, 90.0, 90.0)),
)


def _restated(symbol: str, values) -> tuple[Phase, Phase]:
    """A setting stated with its own cell, and through itself as the parent."""
    child_cell = metric.cell_from_metric(metric.child_metric(values, np.eye(3)))
    own = _one_atom(symbol, child_cell)
    through = own.model_copy(update={"parent_cell": ParentCell(
        space_group=symbol, transform="a,b,c;0,0,0", cell=_cell(values))})
    return own, through


@pytest.mark.parametrize("symbol,values", NAMED_SETTINGS, ids=[s for s, _ in NAMED_SETTINGS])
def test_a_named_setting_through_itself_is_its_own_cell(symbol, values):
    """No strain, the setting's own cell freedom, the same pattern to the bit.

    A group is its own parent here (P = I), so the strain space S is empty and
    the parent's constraints must reach exactly the metrics the setting's own
    ``cell_constraints`` reach — on every branch, including the two trigonal
    axis choices and all three monoclinic axes the tabulated lookup gets wrong
    under a correct count.
    """
    own, through = _restated(symbol, values)
    t_own = ParameterTable(Structure(phases=[own]), INSTRUMENT)
    t_through = ParameterTable(Structure(phases=[through]), INSTRUMENT)
    assert [e.path for e in t_through.entries if ".parent_cell.strain." in e.path] == []
    t_own.set_vary(["phases.*.cell.*"], True)
    t_through.set_vary(["phases.*.cell.*"], True)
    a, b = _metric_tangent(t_own), _metric_tangent(t_through)
    assert _span_residual(a, b) < 1e-7 and _span_residual(b, a) < 1e-7
    assert _span_residual(list(_invariant_metrics(own)), b) < 1e-7
    y_own = np.asarray(rx.Refinement(Structure(phases=[own]), INSTRUMENT).predict(TWO_THETA))
    y_through = np.asarray(rx.Refinement(Structure(phases=[through]),
                                         INSTRUMENT).predict(TWO_THETA))
    assert np.array_equal(y_own, y_through)


def test_the_metric_is_invariant_under_rt_g_r_not_r_g_rt():
    """The Rᵀ trap's positive arm: hexagonal γ = 120° is in one span, not the other.

    Both rotation sets are groups, so both invariant subspaces have dimension
    two; only asserting where the true metric lies tells them apart.
    """
    rotations = metric.rotations_of(sym.get_spacegroup("P 6 m m"))
    g = _voigt(direct_metric_tensor(3.2, 3.2, 5.2, 90.0, 90.0, 120.0))
    right = metric.invariant_metric_basis(rotations)
    wrong = metric.invariant_metric_basis([r.T for r in rotations])
    assert len(right) == len(wrong) == 2
    assert _span_residual([g], right) < 1e-15
    assert _span_residual([g], wrong) > 0.1


# ---------------------------------------------------------------------------
# the block itself
# ---------------------------------------------------------------------------
def _blocks():
    """(block, x) at points away from every special value, three parent systems."""
    rng = np.random.default_rng(1419)
    out = []
    cm = _child((0.5, 0.5, 0), "S1", "(rank 2)#3").phase
    out.append(ParameterTable(Structure(phases=[cm]), INSTRUMENT).derived[0])
    hexagonal = _one_atom("P 6 m m", (6.0, 6.0, 9.0, 90.0, 90.0, 120.0), xyz=GENERAL)
    for cand in isotropy.candidates("P 6 m m", GENERAL, (0, 0, Fraction(1, 2))):
        st = sc.magnetic_supercell(hexagonal, cand, nuclear_group="magnetic",
                                   parent_cell=True, **MOMENT)
        if len(st.phase.parent_cell.strain) == 2:
            out.append(ParameterTable(Structure(phases=[st.phase]), INSTRUMENT).derived[0])
            break
    points = []
    for block in out:
        x = []
        for path in block.inputs:
            name = path.rsplit(".", 1)[-1]
            x.append({"a": 5.7, "b": 7.7, "c": 5.5}.get(name, 0.0) if "strain" not in path
                     else rng.uniform(-0.02, 0.02))
        x = np.array(x)
        x[3:6] = [91.3, 87.9, 118.2]        # off every fixed angle: the map's general point
        points.append((block, x))
    return points


def test_the_block_jacobian_is_exact_and_its_reach_is_declared():
    """Analytic ∂(a′…γ′)/∂(parent cell, strains) against a central difference.

    Positive arm: the same comparison catches a Jacobian that drops the strain's
    length scaling (∂Δ/∂ℓ), the one term a strain held at zero never exercises.
    """
    blocks = _blocks()
    assert len(blocks) == 2 and len(blocks[1][0].basis) == 2
    for block, x in blocks:
        exact = block.jacobian(x)
        fd = np.zeros_like(exact)
        for k in range(len(x)):
            h = 1e-6 * max(1.0, abs(x[k]))
            up, down = x.copy(), x.copy()
            up[k] += h
            down[k] -= h
            fd[:, k] = (block.evaluate(up) - block.evaluate(down)) / (2.0 * h)
        assert np.abs(exact - fd).max() < 1e-7 * max(1.0, np.abs(exact).max())
        declared = block.reach_pattern()
        assert not np.any((np.abs(exact) > 1e-12) & ~declared)
        # the planted error: the strain scaled by lengths frozen at x, i.e. a
        # Jacobian that forgets ∂Δ/∂ℓ; its own difference quotient is what such
        # a Jacobian would equal, and the comparison above must tell them apart
        frozen = np.zeros_like(exact)
        lengths = x[:3].copy()

        def frozen_map(y):
            g = direct_metric_tensor(*y[:6])
            e = np.tensordot(y[6:], block.basis, axes=1)
            return np.array(metric.cell_from_metric(
                block.p.T @ (g + 2.0 * np.outer(lengths, lengths) * e) @ block.p))
        for k in range(len(x)):
            h = 1e-6 * max(1.0, abs(x[k]))
            up, down = x.copy(), x.copy()
            up[k] += h
            down[k] -= h
            frozen[:, k] = (frozen_map(up) - frozen_map(down)) / (2.0 * h)
        assert np.abs(frozen - fd).max() > 1e3 * np.abs(exact - fd).max()


def test_the_traced_twin_is_the_numpy_map():
    """``evaluate_traced`` on the numpy backend is ``evaluate`` (no snap at a
    general point), so the jax and torch rows differentiate the same map."""
    for block, x in _blocks():
        traced = np.array([float(v) for v in block.evaluate_traced(list(x))])
        assert np.allclose(traced, block.evaluate(x), rtol=0, atol=1e-12)


def test_with_strains_held_the_block_is_the_supercell_builders_cell():
    """Strain amplitudes of exactly zero add an exact zero: the same bits."""
    for block, x in _blocks():
        x0 = x.copy()
        x0[6:] = 0.0
        parent = tuple(float(v) for v in x0[:6])
        assert tuple(block.evaluate(x0)) == metric.cell_from_metric(
            metric.child_metric(parent, block.p))


# ---------------------------------------------------------------------------
# esds through the block
# ---------------------------------------------------------------------------
def test_esds_reach_the_child_cell_through_the_block():
    """σ(child) = diag(J_block·C·Cov·Cᵀ·J_blockᵀ)^½, and nothing for a held cell."""
    ref = rx.Refinement(Structure(phases=[
        _child((0.5, 0.5, 0), "S1", "(rank 2)#3").phase.model_copy(deep=True)]),
        INSTRUMENT.model_copy(deep=True))
    ref.set_values({"phases.0.parent_cell.strain.0": 0.003})   # off the 90° point
    table = ParameterTable(ref.structure, INSTRUMENT)
    table.set_vary(["*"], False)
    theta = table.x0()
    assert table.stderr_physical(theta, np.zeros(0)) == {}      # held: no cell esd
    table.set_vary(["phases.*.cell.*", "phases.*.parent_cell.strain.*"], True)
    theta = table.x0()
    n = len(theta)
    rng = np.random.default_rng(7)
    s = rng.uniform(1e-5, 1e-4, n)
    a = rng.normal(size=(n, n))
    corr = np.corrcoef(a @ a.T + n * np.eye(n))
    got = table.stderr_physical(theta, s, corr)
    cov = table._cov_free(theta, s, corr)
    block = table.derived[0]
    rows = [table._paths[q] for q in block.inputs]
    c_in = table.constraint_block()[0].toarray()[rows]
    x = np.array([table.entries[r].value for r in rows])
    j = block.jacobian(x) @ c_in
    want = np.sqrt(np.diag(j @ cov @ j.T))
    for q, w in zip(block.outputs, want, strict=True):
        if w == 0.0:
            assert got.get(q) in (None, 0.0), q      # 90° held by the parent's group
        else:
            assert got[q] == pytest.approx(w, rel=1e-12), q
    assert got["phases.0.cell.gamma"] > 0.0 and got["phases.0.cell.alpha"] > 0.0


# ---------------------------------------------------------------------------
# a freed strain recovers a planted one
# ---------------------------------------------------------------------------
#: the planted shear, and the seed a freed strain starts from: a strain sits on
#: a stationary point of the pattern at zero (below), so it is moved off it
#: before it is freed, as ``Stage.strain_seed`` moves a Stephens block
PLANTED = 0.004
SEED = 0.001


@functools.lru_cache(maxsize=4)
def _pattern(strain: float) -> PatternData:
    phase = _child((0.5, 0.5, 0), "S1", "(rank 2)#3").phase
    truth = rx.Refinement(Structure(phases=[phase.model_copy(deep=True)]),
                          INSTRUMENT.model_copy(deep=True))
    truth.set_values({"phases.0.parent_cell.strain.0": strain})
    tt = np.arange(10.0, 110.0, 0.01)
    y = np.asarray(truth.predict(tt))
    rng = np.random.default_rng(1419)
    return PatternData(two_theta=tt.tolist(),
                       intensity=rng.poisson(y / y.max() * 2e4 + 50.0).astype(float).tolist())


def _refit(strain: float, free_strain: bool):
    phase = _child((0.5, 0.5, 0), "S1", "(rank 2)#3").phase
    ref = rx.Refinement(Structure(phases=[phase.model_copy(deep=True)]),
                        INSTRUMENT.model_copy(deep=True))
    ref.set_values({"phases.0.parent_cell.cell.a": _lamno3().cell.a.value * 1.0005,
                    "phases.0.parent_cell.strain.0": SEED if free_strain else 0.0})
    cell = ["phases.*.scale", "instrument.background.*", "phases.*.cell.*"]
    plan = rx.RefinementPlan(stages=[
        rx.Stage(name="scale", turn_on=["phases.*.scale", "instrument.background.*"]),
        rx.Stage(name="cell", turn_on=cell + (["phases.*.parent_cell.strain.*"]
                                              if free_strain else []))])
    return ref, ref.fit(_pattern(strain), plan=plan, telemetry=False)


def _row(result, path):
    return next(p for p in result.parameters if p.path == path)


def test_the_sign_of_a_strain_is_a_domain_here():
    """+s and −s are one powder pattern while the atoms keep the parent's symmetry.

    The parent operation the shear breaks maps one onto the other, and every
    atom here sits on its parent position, so it is a symmetry of the atoms:
    the two cells are orientation domains of one structure (measured 1.2e-13 of
    the peak, against 1.38 for +s against 0).  So a fit measures |s|, and the
    sign it reports is the seed's.
    """
    phase = _child((0.5, 0.5, 0), "S1", "(rank 2)#3").phase
    tt = np.arange(10.0, 110.0, 0.01)
    ys = []
    for s in (PLANTED, -PLANTED, 0.0):
        ref = rx.Refinement(Structure(phases=[phase.model_copy(deep=True)]),
                            INSTRUMENT.model_copy(deep=True))
        ref.set_values({"phases.0.parent_cell.strain.0": s})
        ys.append(np.asarray(ref.predict(tt)))
    peak = ys[0].max()
    assert np.abs(ys[0] - ys[1]).max() < 1e-10 * peak
    assert np.abs(ys[0] - ys[2]).max() > 0.5 * peak


@pytest.mark.parametrize("planted", [PLANTED, -PLANTED])
def test_a_freed_strain_recovers_a_planted_one(planted):
    """|s| = 0.004 comes back within 3σ, in the seed's domain (measured 0.0039995(13)).

    The child is the Cm one in 2a, a+b, c: the shear moves α′ and β′ off 90°,
    which no parent edge can, so the strain is identifiable from the splitting.
    The refined structure rebuilds a table (its stored child cell is the one its
    parent and strain give), and every child cell parameter carries an esd.
    """
    ref, result = _refit(planted, free_strain=True)
    row = _row(result, "phases.0.parent_cell.strain.0")
    assert row.stderr is not None and row.stderr < 1e-5
    assert abs(row.value - abs(planted)) < 3.0 * row.stderr
    assert abs(row.value - abs(planted)) < 2e-5
    for n in CELL_NAMES:
        assert _row(result, f"phases.0.cell.{n}").stderr is not None
    ParameterTable(ref.structure, ref.instrument)           # no drift refusal
    assert ref.structure.phases[0].parent_cell.strain[0].value == row.value


def test_a_strain_nothing_planted_returns_to_zero_and_a_held_one_cannot_fit():
    """The two negative arms of the recovery.

    Freed from the seed on an unstrained pattern, the strain goes back to zero
    (measured |s| < 1e-7 before main's WP-2002 solver changes, 1.8e-5 after, inside its own
    1.4e-5 esd and 1/50 of the seed; the bound is 1e-4, still 1/10 of the seed).  Its esd there is **not** a measurement: the pattern
    is even in s, so its first derivative vanishes at zero and the linearised
    esd is the curvature's artefact (6e-3 to 2e-2 measured) — which is why this
    asserts the value and not the esd.  Held at zero on the strained pattern,
    nothing else can take up the shear.
    """
    _, null = _refit(0.0, free_strain=True)
    assert abs(_row(null, "phases.0.parent_cell.strain.0").value) < 1e-4
    _, free = _refit(PLANTED, free_strain=True)
    _, held = _refit(PLANTED, free_strain=False)
    assert held.statistics.rwp > 1.5 * free.statistics.rwp


# ---------------------------------------------------------------------------
# refusals and round trip
# ---------------------------------------------------------------------------
def test_an_edited_child_cell_is_refused_not_overwritten():
    phase = _child((0.5, 0.5, 0), "S1", "(rank 2)#3").phase.model_copy(deep=True)
    phase.cell.gamma.value += 0.01
    with pytest.raises(ValueError, match=r"phases\.0\.cell\.gamma is stored as .* "
                                         r"cannot tell which was edited"):
        ParameterTable(Structure(phases=[phase]), INSTRUMENT)


def test_a_strain_list_of_the_wrong_length_says_the_right_one():
    phase = _child((0.5, 0.5, 0), "S1", "(rank 2)#3").phase.model_copy(deep=True)
    phase.parent_cell.strain.append(Parameter(value=0.0))
    with pytest.raises(ValueError, match="needs exactly 1"):
        ParameterTable(Structure(phases=[phase]), INSTRUMENT)


def test_a_child_that_is_not_a_subgroup_under_the_transform_is_refused():
    phase = _child((0.5, 0.5, 0), "S1", "(rank 2)#3").phase.model_copy(deep=True)
    phase.parent_cell.space_group = "P 21 21 21"
    with pytest.raises(ValueError, match="not a subgroup of this parent"):
        ParameterTable(Structure(phases=[phase]), INSTRUMENT)


def test_an_operator_list_parent_has_no_cell_to_carry():
    parent = _lamno3()
    unnamed = parent.model_copy(update={
        "space_group": "P n m a [explicit]",
        "symmetry_operations": [op.triplet() for op in
                                sym.get_spacegroup("P n m a").operations()]})
    cand = next(c for c in _candidates((0.5, 0.5, 0))
                if c.irrep_label == "S1" and c.direction.label == "(rank 2)#3")
    with pytest.raises(ValueError, match="parent states its group as an operation list"):
        sc.magnetic_supercell(unnamed, cand, nuclear_group="magnetic", parent_cell=True)


def test_a_parent_cell_child_round_trips_through_json_to_the_bit():
    phase = _child((0.5, 0.5, 0.5), "S1", "(rank 2)#2").phase
    structure = Structure(phases=[phase])
    again = Structure.model_validate_json(structure.model_dump_json())
    assert again == structure
    a = ParameterTable(structure, INSTRUMENT)
    b = ParameterTable(again, INSTRUMENT)
    assert [e.value for e in a.entries] == [e.value for e in b.entries]


def test_the_drift_tolerance_refuses_any_edit_and_passes_round_off():
    """``PARENT_CELL_DRIFT_TOL`` (1e-9 relative) from both sides.

    A stored child cell is the derived one to the bit, so the tolerance only has
    to sit above round-off and below any edit a person makes: a millionth of a
    degree on γ is refused, a change at the 1e-13 level is not.
    """
    from rietx.params.vector import PARENT_CELL_DRIFT_TOL

    base = _child((0.5, 0.5, 0), "S1", "(rank 2)#3").phase
    gamma = base.cell.gamma.value
    assert 1e-6 / max(abs(gamma), 1.0) > PARENT_CELL_DRIFT_TOL
    edited = base.model_copy(deep=True)
    edited.cell.gamma.value = gamma + 1e-6
    with pytest.raises(ValueError, match=r"phases\.0\.cell\.gamma is stored as"):
        ParameterTable(Structure(phases=[edited]), INSTRUMENT)
    rounded = base.model_copy(deep=True)
    rounded.cell.gamma.value = gamma * (1.0 + 1e-13)
    ParameterTable(Structure(phases=[rounded]), INSTRUMENT)


def test_the_cosine_snap_removes_round_off_and_nothing_physical(monkeypatch):
    """``COSINE_SNAP`` (1e-12 on a cosine) from both sides.

    Pᵀ·G·P of a hexagonal cell gives cos γ = -0.49999999999999983.  Snapped, γ is
    the angle of the exact cosine -½, the one every route to this metric
    reports; unsnapped it is 119.99999999999999, one rounding away.  A real
    departure, a cosine 1e-9 off -½ (6e-8°), is left alone.
    """
    exact = float(np.degrees(np.arccos(-0.5)))
    g = metric.child_metric((3.2, 3.2, 5.2, 90.0, 90.0, 120.0), np.eye(3))
    assert metric.cell_from_metric(g)[3:] == (90.0, 90.0, exact)
    monkeypatch.setattr(metric, "COSINE_SNAP", 0.0)
    assert metric.cell_from_metric(g)[5] != exact
    monkeypatch.undo()
    lengths = np.sqrt(np.diag(g))
    off = np.array(g, dtype=np.float64)
    off[0, 1] = off[1, 0] = (-0.5 + 1e-9) * lengths[0] * lengths[1]
    assert metric.cell_from_metric(off)[5] != exact


# ---------------------------------------------------------------------------
# review of #1108: the parent's cell is a cell to every safeguard
# ---------------------------------------------------------------------------
PARENT_A = "phases.0.parent_cell.cell.a"
STRAIN_0 = "phases.0.parent_cell.strain.0"


def _cm_table(**edits) -> ParameterTable:
    phase = _child((0.5, 0.5, 0), "S1", "(rank 2)#3").phase.model_copy(deep=True)
    for name, value in edits.items():
        getattr(phase.parent_cell.cell, name).value = value
    return ParameterTable(Structure(phases=[phase]), INSTRUMENT)


def test_the_cell_parser_reads_the_parents_five_part_path():
    from rietx.params.vector import _cell_parameter_name

    assert _cell_parameter_name(PARENT_A, phases=None) == "a"
    assert _cell_parameter_name("phases.0.parent_cell.cell.gamma", phases={0}) == "gamma"
    assert _cell_parameter_name(PARENT_A, phases={1}) is None
    # neither the strain nor a made-up cell name is a cell parameter
    assert _cell_parameter_name(STRAIN_0, phases=None) is None
    assert _cell_parameter_name("phases.0.parent_cell.cell.z", phases=None) is None
    assert _cell_parameter_name("phases.0.cell.b", phases=None) == "b"


def test_an_unseen_phases_parent_cell_gets_the_stage_window():
    """WP-1301's window reached the child's six locked outputs and none of the
    parent's edges, so a floored-scale child could walk its cell unbounded."""
    table = _cm_table()
    table.set_vary(["phases.*.cell.*"], True)
    table.freeze_cell_windows({0})
    lo, hi = table.bounds()
    i = table.free_paths.index(PARENT_A)
    a = table.entries[table._paths[PARENT_A]].value
    assert np.isfinite(lo[i]) and np.isfinite(hi[i])
    assert lo[i] < a < hi[i] and hi[i] < 1.1 * a


def test_a_parent_cell_runaway_is_reset_and_named():
    from rietx.refine import _cell_runaway_diagnostic, reset_cell_runaway

    table = _cm_table()
    table.set_vary(["phases.*.cell.*"], True)
    start = {e.path: e.value for e in table.entries}
    entry = table.entries[table._paths[PARENT_A]]
    entry.value = 1.4 * start[PARENT_A]
    reset = reset_cell_runaway(table, start)
    assert PARENT_A in {c[0] for c in reset}
    assert entry.value == start[PARENT_A]
    diag = _cell_runaway_diagnostic(reset)
    assert diag is not None and PARENT_A in diag.where
    assert "1 phase" in diag.message or "phase's free cell" in diag.message
    # the child's cell is derived from the parent edge, not tied to it, and is
    # the cell the pattern uses: it loses the esd the parent edge loses
    from rietx.refine import _cell_runaway_withheld

    withheld = _cell_runaway_withheld(table, diag.where)
    assert PARENT_A in withheld
    assert "phases.0.cell.a" in withheld
    assert set(table._cell_blocks[0].outputs) <= withheld



def test_a_parent_cell_runaway_leaves_the_child_cell_with_no_esd_in_the_result():
    """The built result, not only the withheld set (review of #1108, round 2):
    the parent edge and the child cell it computes both report ``stderr is
    None`` after a ``CELL_RUNAWAY`` naming the edge, while every other free
    entry keeps the esd the solve measured."""
    from rietx.model.forward import compile_model
    from rietx.refine import _build_result, _cell_runaway_diagnostic, reset_cell_runaway

    phase = _child((0.5, 0.5, 0), "S1", "(rank 2)#3").phase.model_copy(deep=True)
    structure = Structure(phases=[phase])
    table = ParameterTable(structure, INSTRUMENT)
    table.set_vary(["phases.*.cell.*", "phases.*.scale"], True)
    start = {e.path: e.value for e in table.entries}
    table.entries[table._paths[PARENT_A]].value = 1.4 * start[PARENT_A]
    diag = _cell_runaway_diagnostic(reset_cell_runaway(table, start))
    assert diag is not None and PARENT_A in diag.where

    theta = table.x0()
    n = len(table.free_paths)
    model = compile_model(structure, INSTRUMENT, _pattern(SEED))
    result = _build_result(
        model, table, theta, mode="rietveld", status="converged",
        stage_results=[], diagnostics=[diag], structure=structure,
        stderr_internal=np.full(n, 1e-3), correlation=np.eye(n))
    esd = {p.path: p.stderr for p in result.parameters}
    assert PARENT_A in esd and "phases.0.cell.a" in esd
    assert esd[PARENT_A] is None
    assert esd["phases.0.cell.a"] is None
    # positive arm: the measured entries outside the runaway keep an esd
    kept = [p for p, s in esd.items() if p not in diag.where and s is not None]
    assert "phases.0.scale" in kept


def test_a_bound_on_the_parent_carries_to_the_child_built_from_it():
    parent = _lamno3().model_copy(deep=True)
    parent.cell.a.min, parent.cell.a.max = 5.683, 5.783
    cand = next(c for c in _candidates((0.5, 0.5, 0))
                if c.irrep_label == "S1" and c.direction.label == "(rank 2)#3")
    phase = sc.magnetic_supercell(parent, cand, nuclear_group="magnetic").phase
    assert (phase.parent_cell.cell.a.min, phase.parent_cell.cell.a.max) == (5.683, 5.783)
    # the vary flag stays the plan's, and an unbounded edge stays unbounded
    assert not phase.parent_cell.cell.a.vary
    assert phase.parent_cell.cell.c.min == -np.inf


def test_the_parent_moves_through_set_values_and_the_child_follows():
    """The refusal cannot tell which side was edited; the verb is the way."""
    phase = _child((0.5, 0.5, 0), "S1", "(rank 2)#3").phase.model_copy(deep=True)
    ref = rx.Refinement(Structure(phases=[phase]), INSTRUMENT.model_copy(deep=True))
    a0 = ref.structure.phases[0].cell.a.value
    ref.set_values({PARENT_A: _lamno3().cell.a.value * 1.001})
    assert ref.structure.phases[0].cell.a.value == pytest.approx(a0 * 1.001, rel=1e-12)
    ParameterTable(ref.structure, INSTRUMENT)    # and the table accepts the pair


def test_the_drift_refusal_names_both_sides_and_prints_plain_floats():
    phase = _child((0.5, 0.5, 0), "S1", "(rank 2)#3").phase.model_copy(deep=True)
    phase.parent_cell.cell.a.value *= 1.001
    with pytest.raises(ValueError) as caught:
        ParameterTable(Structure(phases=[phase]), INSTRUMENT)
    message = str(caught.value)
    assert "np.float64" not in message
    assert "cannot tell which was edited" in message and "set_values" in message


# ---------------------------------------------------------------------------
# a freed strain stays where the child's metric is positive definite
# ---------------------------------------------------------------------------
def test_a_freed_strain_is_bounded_where_the_metric_stays_positive_definite():
    table = _cm_table()
    table.set_vary([STRAIN_0], True)
    lo, hi = table.bounds()
    i = table.free_paths.index(STRAIN_0)
    assert np.isfinite(lo[i]) and lo[i] == -hi[i] and hi[i] > 0
    # the parent is orthorhombic, so its cosine matrix is the identity
    e = np.asarray(table._cell_blocks[0].basis[0])
    for sign in (1.0, -1.0):
        assert np.linalg.eigvalsh(np.eye(3) + 2.0 * sign * hi[i] * e)[0] > 0.0
    # a held strain carries no bound: nothing moves it
    table.set_vary([STRAIN_0], False)
    assert STRAIN_0 not in table.free_paths


def test_the_strain_bound_is_the_weyl_box_less_a_numerical_floor():
    """The bound is arithmetic, not a chosen fraction (#1224): Weyl's box
    λ_min(C)/(2·n·‖E‖₂), a relative ``PARENT_STRAIN_PD_MARGIN`` inside it.
    The positive arm is the box's own edge, where this child's metric is
    singular, so the floor is what keeps the bound inside the lattices."""
    from rietx.params.vector import PARENT_STRAIN_PD_MARGIN

    table = _cm_table()
    table.set_vary([STRAIN_0], True)
    hi = table.bounds()[1][table.free_paths.index(STRAIN_0)]
    e = np.asarray(table._cell_blocks[0].basis[0])
    n = len(table._cell_blocks[0].basis)
    box = 1.0 / (2.0 * n * float(np.max(np.abs(np.linalg.eigvalsh(e)))))  # C = I here
    assert hi == pytest.approx((1.0 - PARENT_STRAIN_PD_MARGIN) * box, rel=1e-14)
    edge = min(np.linalg.eigvalsh(np.eye(3) + 2.0 * s * box * e)[0] for s in (1.0, -1.0))
    assert abs(edge) < 1e-14                      # the box's edge: a singular metric
    at_bound = min(np.linalg.eigvalsh(np.eye(3) + 2.0 * s * hi * e)[0] for s in (1.0, -1.0))
    assert at_bound >= 0.5 * PARENT_STRAIN_PD_MARGIN  # the bound: positive definite


def test_a_stored_strain_past_the_cone_is_refused_by_name():
    phase = _child((0.5, 0.5, 0), "S1", "(rank 2)#3").phase.model_copy(deep=True)
    phase.parent_cell.strain[0].value = 5.0
    with pytest.raises(ValueError, match=r"parent_cell\.strain .* not positive definite"):
        ParameterTable(Structure(phases=[phase]), INSTRUMENT)


def test_a_caller_bound_on_a_strain_is_kept_where_tighter():
    phase = _child((0.5, 0.5, 0), "S1", "(rank 2)#3").phase.model_copy(deep=True)
    phase.parent_cell.strain[0].min, phase.parent_cell.strain[0].max = -1e-3, 2e-3
    table = ParameterTable(Structure(phases=[phase]), INSTRUMENT)
    table.set_vary([STRAIN_0], True)
    lo, hi = table.bounds()
    assert lo[0] == -1e-3 and hi[0] == 2e-3


# ---------------------------------------------------------------------------
# the strain basis is built from one invariant basis of the parent
# ---------------------------------------------------------------------------
def test_strain_basis_asks_the_parents_invariant_basis_once(monkeypatch):
    """Rebuilt per axis pair it was 0.24 s a call on a cubic parent, and
    ``ParameterTable`` calls it on every build."""
    calls = []
    real = metric.invariant_metric_basis
    monkeypatch.setattr(metric, "invariant_metric_basis",
                        lambda rotations: calls.append(len(rotations)) or real(rotations))
    parent = sym.get_spacegroup("P m -3 m")
    child = sym.get_spacegroup("P 4/m m m")
    basis = metric.strain_basis(metric.rotations_of(parent),
                                metric.in_parent_basis(np.eye(3), metric.rotations_of(child)),
                                {"alpha": 90.0, "beta": 90.0, "gamma": 90.0})
    assert len(basis) == 1
    assert len(calls) <= 2          # the parent's, and the child's


# ---------------------------------------------------------------------------
# PARENT_STRAIN_HELD: the hold under the cell glob is said aloud
# ---------------------------------------------------------------------------
def _small_pattern() -> PatternData:
    phase = _child((0.5, 0.5, 0), "S1", "(rank 2)#3").phase
    ref = rx.Refinement(Structure(phases=[phase.model_copy(deep=True)]),
                        INSTRUMENT.model_copy(deep=True))
    tt = np.arange(10.0, 40.0, 0.04)
    y = np.asarray(ref.predict(tt))
    return PatternData(two_theta=tt.tolist(),
                       intensity=(y / y.max() * 5e3 + 30.0).tolist())


def _held_findings(turn_on):
    phase = _child((0.5, 0.5, 0), "S1", "(rank 2)#3").phase
    ref = rx.Refinement(Structure(phases=[phase.model_copy(deep=True)]),
                        INSTRUMENT.model_copy(deep=True))
    ref.set_values({STRAIN_0: SEED})
    plan = rx.RefinementPlan(stages=[
        rx.Stage(name="scale", turn_on=["phases.*.scale"]),
        rx.Stage(name="cell", turn_on=turn_on, max_iter=5)])
    result = ref.fit(_small_pattern(), plan=plan, telemetry=False)
    return [d for d in result.diagnostics if d.code == "PARENT_STRAIN_HELD"]


def test_the_cell_glob_leaves_a_strain_held_and_says_so():
    (finding,) = _held_findings(["phases.*.scale", "phases.*.cell.*"])
    assert finding.level == "info"
    assert finding.where == [STRAIN_0]
    assert "set_values" in finding.suggestion and "phases.*.parent_cell.strain.*" in finding.suggestion


def test_naming_the_strain_silences_it_and_so_does_a_stage_with_no_edges():
    assert _held_findings(["phases.*.scale", "phases.*.cell.*",
                           "phases.*.parent_cell.strain.*"]) == []
    assert _held_findings(["phases.*.scale"]) == []
