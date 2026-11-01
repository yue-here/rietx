"""The derived block: a nonlinear map applied after the affine one (WP-1804).

The rigid-body seam WP-1803 decided (``docs/DESIGN.md`` § Parameter system,
"Rigid bodies"): a block maps declared input entries to declared, locked output
entries in ``decode``, and every reader of C that has to know what a derived
row depends on reads the block's local Jacobian at θ (esds, restraint rows) or
its declared reach (the pattern readers).  The toy block here is WP-1803's
C₆Br body placed by an origin and an anchored rotation increment — the schema
that declares bodies for real is WP-1805's; this file tests the seam alone.

Every check can fail: the esd test is against a central finite difference of
``decode`` (never a formula sharing code with the block), and a planted sign in
the block's Jacobian must make it fail (WP-1803's positive arm).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from rietx import Instrument, PatternData
from rietx.crystallography import rotation
from rietx.crystallography.adp import cartesian_basis
from rietx.model.forward import compile_model
from rietx.model.restraints import restraint_partials
from rietx.params.derived import (
    DerivedBlock,
    cartesian_frame,
    d_cartesian_frame_d_cell,
    fractional_frame,
)
from rietx.params.vector import AffineTie, ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.structure import Atom, BondRestraint, Cell, Phase, Structure

LAB = Instrument.debye_scherrer(wavelength=1.5406)
CELL = (7.21, 8.13, 9.47, 84.3, 97.6, 104.2)        # WP-1803's triclinic P-1 cell
_CELL_NAMES = ("a", "b", "c", "alpha", "beta", "gamma")


def _c6br_template() -> np.ndarray:
    """WP-1803's synthetic body: an ideal D6h ring, C–C 1.39 Å, C–Br 1.90 Å,
    centred on its centroid (Cartesian, Å)."""
    ring = np.array([[1.39 * math.cos(k * math.pi / 3), 1.39 * math.sin(k * math.pi / 3), 0.0]
                     for k in range(6)])
    br = ring[0] * (1.0 + 1.90 / 1.39)
    pts = np.vstack([ring, br])
    return pts - pts.mean(axis=0)


class _PoseBlock(DerivedBlock):
    """x_i = o + M⁻¹(cell)·Exp(δω)·R₀·T_i, the toy body of WP-1803.

    Inputs: the six cell entries, three origin entries, three rotation-increment
    entries (rad).  ``flip`` plants the sign error WP-1803's positive arm used:
    the cross-product term of ∂x/∂δω with its sign reversed.
    """

    def __init__(self, template, r0, cell_paths, origin_paths, rot_paths, out_paths,
                 flip=False):
        self.template = np.asarray(template, dtype=np.float64)
        self.r0 = np.asarray(r0, dtype=np.float64)
        self.inputs = (*cell_paths, *origin_paths, *rot_paths)
        self.outputs = tuple(out_paths)
        self.flip = flip

    def _parts(self, x):
        cell, o, w = x[:6], x[6:9], x[9:12]
        minv = np.asarray(fractional_frame(tuple(cell)))
        rot = np.asarray(rotation.matrix_from_vector(w)) @ self.r0
        return cell, o, w, minv, rot

    def evaluate(self, x):
        _, o, _, minv, rot = self._parts(np.asarray(x, dtype=np.float64))
        return (o + (minv @ rot @ self.template.T).T).ravel()

    def jacobian(self, x):
        x = np.asarray(x, dtype=np.float64)
        cell, o, w, minv, rot = self._parts(x)
        n = len(self.template)
        jac = np.zeros((3 * n, 12))
        rel = (minv @ rot @ self.template.T).T            # M⁻¹·R·T_i, fractional
        dm = d_cartesian_frame_d_cell(tuple(cell))
        dr = np.asarray(rotation.d_matrix_d_vector(w, self.r0))
        if self.flip:
            dr = -dr
        for i in range(n):
            rows = slice(3 * i, 3 * i + 3)
            for q in range(6):
                jac[rows, q] = -minv @ dm[q] @ rel[i]
            jac[rows, 6:9] = np.eye(3)
            for k in range(3):
                jac[rows, 9 + k] = minv @ dr[k] @ self.template[i]
        return jac

    def evaluate_traced(self, x):
        from rietx.backend import get_backend
        xp = get_backend()
        cell = tuple(x[:6])
        o = xp.stack(list(x[6:9]))
        w = xp.stack(list(x[9:12]))
        minv = fractional_frame(cell)
        rot = xp.matmul(rotation.matrix_from_vector(w), xp.asarray(self.r0))
        out = []
        for t in self.template:
            p = o + xp.matmul(minv, xp.matmul(rot, xp.asarray(t)))
            out.extend([p[0], p[1], p[2]])
        return out

    def reach_pattern(self):
        return np.ones((len(self.outputs), 12), dtype=bool)


def _structure(n_body: int, extra_free: bool = True) -> Structure:
    def P(v, vary=False):
        return Parameter(value=v, vary=vary)
    atoms = [Atom(label=f"B{i}", species="C" if i < 6 else "Br",
                  x=P(0.1 * i), y=P(0.2), z=P(0.3)) for i in range(n_body)]
    if extra_free:
        atoms.append(Atom(label="Li", species="Li", x=P(0.61, True), y=P(0.37, True),
                          z=P(0.12, True)))
    return Structure(phases=[Phase(
        name="tri", space_group="P1",
        cell=Cell(a=P(CELL[0], True), b=P(CELL[1], True), c=P(CELL[2], True),
                  alpha=P(CELL[3], True), beta=P(CELL[4], True), gamma=P(CELL[5], True)),
        atoms=atoms, scale=Parameter(value=1e-3, vary=True, min=0.0,
                                     transform="softplus"))])


def _build_block(flip=False, r0=None, origin=(0.31, 0.42, 0.27), restraint=False):
    """A (table, block, structure) with the toy body declared over atoms 0..6 of phase 0.

    ``restraint`` puts a bond restraint between body atom 6 (the Br) and the
    free Li (atom 7) in the structure first, so a model compiled from it has a
    restraint block reaching across a body row.
    """
    tmpl = _c6br_template()
    s = _structure(len(tmpl))
    if restraint:
        s.phases[0].restraints = [BondRestraint(atom_i=6, atom_j=7, target=2.0,
                                                sigma=0.02, op_index=0)]
    table = ParameterTable(s, LAB)
    for k, v in zip("xyz", origin, strict=True):
        table.add_parameter(f"phases.0.rigid_bodies.0.origin.{k}", v, vary=True)
    for k in range(3):
        table.add_parameter(f"phases.0.rigid_bodies.0.rotation.{k}", 0.0, vary=True)
    outs = []
    for i in range(len(tmpl)):
        for c in "xyz":
            e = table.entries[table._paths[f"phases.0.atoms.{i}.{c}"]]
            e.tie, e.locked, e.vary = None, True, False
            outs.append(f"phases.0.atoms.{i}.{c}")
    table._rebuild()
    block = _PoseBlock(
        tmpl, np.eye(3) if r0 is None else r0,
        [f"phases.0.cell.{n}" for n in _CELL_NAMES],
        [f"phases.0.rigid_bodies.0.origin.{k}" for k in "xyz"],
        [f"phases.0.rigid_bodies.0.rotation.{k}" for k in range(3)], outs, flip=flip)
    table.add_derived(block)
    return table, block, s


def _with_block(**kw):
    table, block, _ = _build_block(**kw)
    return table, block


def _toy_pattern() -> PatternData:
    tt = np.arange(10.0, 60.0, 0.05)
    return PatternData(two_theta=tt.tolist(), intensity=np.ones_like(tt).tolist())


def _theta_at(table, rotation_deg=(3.0, -2.0, 1.5)):
    theta = table.x0().copy()
    for k in range(3):
        theta[table.free_paths.index(f"phases.0.rigid_bodies.0.rotation.{k}")] = \
            math.radians(rotation_deg[k])
    return theta


def _random_covariance(m: int, seed: int = 7):
    rng = np.random.default_rng(seed)
    a = rng.normal(size=(m, m))
    cov = a @ a.T + m * np.eye(m)
    s = np.sqrt(np.diag(cov)) * 1e-3
    corr = cov / np.sqrt(np.outer(np.diag(cov), np.diag(cov)))
    return s, corr


def _fd_jacobian(table, theta, h=1e-6):
    """Central FD of ``decode`` over θ: the oracle shares no code with a block."""
    paths = [e.path for e in table.entries]
    jac = np.zeros((len(paths), len(theta)))
    for c in range(len(theta)):
        tp, tm = theta.copy(), theta.copy()
        tp[c] += h
        tm[c] -= h
        vp, vm = table.decode(tp), table.decode(tm)
        jac[:, c] = [(vp[p] - vm[p]) / (2 * h) for p in paths]
    return jac


# ----------------------------------------------------------- the frame contract
def test_closed_form_frame_is_cartesian_basis_over_random_cells():
    """The closed-form M equals adp.cartesian_basis (the Cholesky factor) to
    1e-14 relative over 2000 random cells, and M⁻¹ is its inverse."""
    rng = np.random.default_rng(1803)
    worst = worst_inv = 0.0
    n = 0
    while n < 2000:
        lengths = rng.uniform(2.0, 30.0, size=3)
        angles = rng.uniform(55.0, 125.0, size=3)
        cell = (*lengths, *angles)
        ca, cb, cg = np.cos(np.radians(angles))
        if 1 - ca * ca - cb * cb - cg * cg + 2 * ca * cb * cg <= 1e-3:
            continue                      # not a cell
        n += 1
        m = np.asarray(cartesian_frame(cell))
        ref = cartesian_basis(*cell)
        worst = max(worst, float(np.abs(m - ref).max() / np.abs(ref).max()))
        worst_inv = max(worst_inv, float(np.abs(
            np.asarray(fractional_frame(cell)) @ m - np.eye(3)).max()))
    assert worst < 1e-14
    assert worst_inv < 1e-14


def test_frame_cell_derivative_matches_central_fd():
    m0 = d_cartesian_frame_d_cell(CELL)
    for q in range(6):
        h = 1e-6 * max(1.0, abs(CELL[q]))
        up = list(CELL)
        dn = list(CELL)
        up[q] += h
        dn[q] -= h
        fd = (np.asarray(cartesian_frame(tuple(up)))
              - np.asarray(cartesian_frame(tuple(dn)))) / (2 * h)
        assert np.abs(m0[q] - fd).max() < 1e-8 * max(1.0, np.abs(fd).max()), q


def test_frame_jacfwd_is_finite_under_jax():
    jax = pytest.importorskip("jax")
    from rietx.backend import resolve_backend
    from rietx.backend.traced import active

    xp = resolve_backend("jax")
    with active(xp):
        jac = jax.jacfwd(lambda c: fractional_frame(tuple(c[i] for i in range(6))))(
            xp.asarray(np.array(CELL)))
    assert np.all(np.isfinite(np.asarray(jac)))


# ------------------------------------------------- no block: bit-identical
def test_no_block_readers_are_c_itself():
    s = _structure(3)
    table = ParameterTable(s, LAB)
    assert table.derived == []
    theta = table.x0()
    assert table.local_jacobian(theta) is table.constraint_block()[0]
    assert table.reach_block() is table.constraint_block()[0]


# ------------------------------------------------- the block in decode
def test_decode_applies_the_block_and_commit_keeps_it_rigid():
    table, block = _with_block()
    theta = _theta_at(table)
    values = table.decode(theta)
    tmpl = _c6br_template()
    m = np.asarray(cartesian_frame(CELL))
    xyz = np.array([[values[f"phases.0.atoms.{i}.{c}"] for c in "xyz"]
                    for i in range(len(tmpl))])
    cart = (m @ xyz.T).T
    for i in range(len(tmpl)):
        for j in range(i):
            assert abs(np.linalg.norm(cart[i] - cart[j])
                       - np.linalg.norm(tmpl[i] - tmpl[j])) < 1e-12
    table.commit(theta)
    for i in range(len(tmpl)):
        for c in "xyz":
            p = f"phases.0.atoms.{i}.{c}"
            assert table.entries[table._paths[p]].value == values[p]


def test_body_esds_equal_central_fd_chain_and_a_planted_sign_fails():
    """σ from ``stderr_physical`` equals diag(J·Cov·Jᵀ) with J a central FD of
    ``decode``, to 1e-9 relative, at a 3° increment — and a block whose
    Jacobian carries WP-1803's planted sign does not."""
    table, _ = _with_block()
    theta = _theta_at(table)
    s, corr = _random_covariance(len(theta))
    jac_fd = _fd_jacobian(table, theta)
    cov = corr * np.outer(s, s)
    var_fd = np.einsum("ij,jk,ik->i", jac_fd, cov, jac_fd)
    esd = table.stderr_physical(theta, s, corr)
    body_rows = [f"phases.0.atoms.{i}.{c}" for i in range(7) for c in "xyz"]
    for p in body_rows:
        i = table._paths[p]
        assert esd[p] == pytest.approx(math.sqrt(var_fd[i]), rel=1e-9), p
    # the C anchor rows carry no esd at all: these are locked rows
    assert np.all(table.constraint_block()[0][[table._paths[p] for p in body_rows]]
                  .toarray() == 0.0)

    flipped, _ = _with_block(flip=True)
    esd_bad = flipped.stderr_physical(theta, s, corr)
    ratios = [esd_bad[p] / esd[p] for p in body_rows]
    assert max(abs(r - 1.0) for r in ratios) > 1e-2


def test_physical_covariance_uses_the_local_jacobian():
    table, _ = _with_block()
    theta = _theta_at(table)
    s, corr = _random_covariance(len(theta))
    paths = ["phases.0.atoms.6.x", "phases.0.atoms.6.y", "phases.0.atoms.7.x"]
    jac_fd = _fd_jacobian(table, theta)[[table._paths[p] for p in paths]]
    expected = jac_fd @ (corr * np.outer(s, s)) @ jac_fd.T
    got = table.physical_covariance(theta, s, corr, paths)
    assert np.allclose(got, expected, rtol=1e-8, atol=1e-18)


def test_reach_is_declared_not_numeric():
    """An atom at the body's pivot has a zero rotation column at δω = 0, yet
    the declared reach lists it: a freeze must not rest on an instantaneous
    zero (WP-1803 measured 28 numeric rows against 42 declared)."""
    tmpl = _c6br_template()
    shift = tmpl[0].copy()                 # make atom 0 the pivot
    table, block = _with_block()
    block.template = tmpl - shift
    table._refresh_derived()
    theta = table.x0()
    jac = table.local_jacobian(theta).toarray()
    rot0 = table.free_paths.index("phases.0.rigid_bodies.0.rotation.0")
    pivot_rows = [table._paths[f"phases.0.atoms.0.{c}"] for c in "xyz"]
    assert np.all(jac[pivot_rows, rot0] == 0.0)          # numerically still
    reach = table.column_reach()["phases.0.rigid_bodies.0.rotation.0"]
    assert {f"phases.0.atoms.0.{c}" for c in "xyz"} <= set(reach)
    assert len([p for p in reach if ".atoms." in p]) == 21
    moving = set(table.moving_paths)
    assert {f"phases.0.atoms.{i}.{c}" for i in range(7) for c in "xyz"} <= moving
    # the cell reaches every body row (the cell is live in the map)
    assert set(table.column_reach()["phases.0.cell.a"]) >= {
        f"phases.0.atoms.{i}.{c}" for i in range(7) for c in "xyz"}
    # entry_reach agrees with column_reach on every free path
    er = table.entry_reach()
    for p, rows in table.column_reach().items():
        assert er[p] == rows, p


def test_unmeasured_column_blinds_the_body_rows():
    table, _ = _with_block()
    theta = _theta_at(table)
    s, corr = _random_covariance(len(theta))
    s = s.copy()
    s[table.free_paths.index("phases.0.rigid_bodies.0.rotation.1")] = np.inf
    esd = table.stderr_physical(theta, s, corr)
    assert "phases.0.atoms.3.x" not in esd           # absent, never zero
    assert "phases.0.atoms.7.x" in esd               # the free Li is untouched


def test_set_tie_refuses_a_derived_or_locked_source():
    table, _ = _with_block()
    with pytest.raises(ValueError, match=r"phases\.0\.atoms\.7\.x.*phases\.0\.atoms\.2\.x"):
        table.set_tie("phases.0.atoms.7.x",
                      AffineTie(terms=(("phases.0.atoms.2.x", 1.0),)))
    s = Structure(phases=[Phase(
        name="cub", space_group="F m -3 m", cell=Cell.cubic(5.43),
        atoms=[Atom(label="Si", species="Si", x=Parameter(value=0.0),
                    y=Parameter(value=0.0), z=Parameter(value=0.0)),
               Atom(label="Li", species="Li", x=Parameter(value=0.1),
                    y=Parameter(value=0.2), z=Parameter(value=0.3))])])
    plain = ParameterTable(s, LAB)
    with pytest.raises(ValueError, match=r"phases\.0\.atoms\.1\.occ.*phases\.0\.cell\.alpha"):
        plain.set_tie("phases.0.atoms.1.occ",
                      AffineTie(terms=(("phases.0.cell.alpha", 0.01),)))


def test_set_tie_refuses_a_source_tied_onto_a_derived_or_locked_row():
    """A tied source is read through its chain (the #773 round-2 gap).

    No writer builds a tie resting on a locked or derived row today (symmetry
    never does, and the verbs refuse it), so the middle link is planted on the
    entry.  Read only directly, the source passed and the target's C row came
    out empty: frozen, with no error.
    """
    table, _ = _with_block()
    table.entries[table._paths["phases.0.atoms.7.y"]].tie = AffineTie(
        terms=(("phases.0.atoms.2.x", 1.0),))
    with pytest.raises(ValueError, match=r"phases\.0\.atoms\.7\.y.*derived row "
                                         r"'phases\.0\.atoms\.2\.x'"):
        table.set_tie("phases.0.atoms.7.z",
                      AffineTie(terms=(("phases.0.atoms.7.y", 1.0),)))
    s = Structure(phases=[Phase(
        name="cub", space_group="F m -3 m", cell=Cell.cubic(5.43),
        atoms=[Atom(label="Li", species="Li", x=Parameter(value=0.1),
                    y=Parameter(value=0.2), z=Parameter(value=0.3))])])
    plain = ParameterTable(s, LAB)
    plain.entries[plain._paths["phases.0.atoms.0.occ"]].tie = AffineTie(
        terms=(("phases.0.cell.alpha", 0.01),))
    with pytest.raises(ValueError, match=r"phases\.0\.atoms\.0\.occ.*locked row "
                                         r"'phases\.0\.cell\.alpha'"):
        plain.set_tie("phases.0.atoms.0.biso",
                      AffineTie(terms=(("phases.0.atoms.0.occ", 1.0),)))


def test_add_derived_refuses_an_unlocked_output():
    s = _structure(2)
    table = ParameterTable(s, LAB)
    table.add_parameter("phases.0.rigid_bodies.0.origin.x", 0.1)

    class _One(DerivedBlock):
        inputs = ("phases.0.rigid_bodies.0.origin.x",)
        outputs = ("phases.0.atoms.2.x",)          # the free Li: not locked

        def evaluate(self, x):
            return np.asarray(x)

        def jacobian(self, x):
            return np.eye(1)

        def evaluate_traced(self, x):
            return list(x)

        def reach_pattern(self):
            return np.ones((1, 1), dtype=bool)

    with pytest.raises(ValueError, match="locked entry"):
        table.add_derived(_One())


# ------------------------------------------- a restraint across a body's rows
def test_restraint_across_a_body_row_chains_through_the_block():
    """A bond restraint between a body atom and the free Li: the restraint
    block's ∂row/∂θ (R_phys · local Jacobian) against a central FD of the row
    value through ``decode`` — the row-24 acceptance of the gap table."""
    table, _ = _with_block()
    s = _structure(7)
    s.phases[0].restraints = [BondRestraint(atom_i=6, atom_j=7, target=2.0,
                                            sigma=0.02, op_index=0)]
    tt = np.arange(10.0, 60.0, 0.05)
    pattern = PatternData(two_theta=tt.tolist(), intensity=np.ones_like(tt).tolist())
    model = compile_model(s, LAB, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    theta = _theta_at(table)
    values = table.decode(theta)
    r_phys = restraint_partials(model.restraints, values, table)
    an = r_phys @ table.local_jacobian(theta).toarray()

    from rietx.model.restraints import _bond_value_np
    item = model.restraints.items[0]
    h = 1e-6
    for c in range(len(theta)):
        tp, tm = theta.copy(), theta.copy()
        tp[c] += h
        tm[c] -= h
        fd = (_bond_value_np(item, table.decode(tp))
              - _bond_value_np(item, table.decode(tm))) / (2 * h) / 0.02
        assert an[0, c] == pytest.approx(fd, rel=1e-6, abs=1e-6), table.free_paths[c]


# ------------------------------------------------- the traced twin
def test_traced_decode_applies_the_block_and_matches_the_local_jacobian():
    jax = pytest.importorskip("jax")
    from rietx.backend import resolve_backend
    from rietx.backend.traced import active, make_traced_decode

    table, _ = _with_block()
    theta = _theta_at(table)
    xp = resolve_backend("jax")
    decode = make_traced_decode(table, xp)
    body = [f"phases.0.atoms.{i}.{c}" for i in range(7) for c in "xyz"]
    with active(xp):
        th = xp.asarray(theta)
        traced = decode(th)
        got = np.array([float(traced[p]) for p in body])
        jac = np.asarray(jax.jacfwd(
            lambda t: xp.stack([decode(t)[p] for p in body]))(th))
    ref = table.decode(theta)
    assert np.allclose(got, [ref[p] for p in body], rtol=0, atol=1e-14)
    local = table.local_jacobian(theta).toarray()[[table._paths[p] for p in body]]
    # every free column here is identity-transform except the softplus scale,
    # which no body row reads
    assert np.allclose(jac, local, rtol=1e-10, atol=1e-13)


# ------------------------------------- the least-squares readers of the block
def _toy_model(table, structure):
    table.apply_to_models(structure, LAB)
    return compile_model(structure, LAB, _toy_pattern(), mode="rietveld",
                         moving_paths=set(table.moving_paths))


def test_column_extras_read_the_declared_reach_not_c():
    """A body DOF's column moves every body atom row, though no row of C says so.

    ``_column_extras`` is what sends such a column to the whole-model FD
    instead of a closed-form branch that would return it short; reading C
    (the pre-WP-1804 line) leaves the origin column standing for itself alone.
    """
    from rietx.optimize.least_squares import _column_extras

    table, _ = _with_block()
    extras = _column_extras(table)
    for path in ("phases.0.rigid_bodies.0.origin.x",
                 "phases.0.rigid_bodies.0.rotation.1",
                 "phases.0.cell.a"):
        got = set(extras[table.free_paths.index(path)])
        assert {f"phases.0.atoms.{i}.{c}" for i in range(7) for c in "xyz"} <= got, path
    # the free Li is not a body row: nothing extra on its own column
    assert extras[table.free_paths.index("phases.0.atoms.7.dof.0")] == ["phases.0.atoms.7.x"]


def test_restraint_rows_of_the_analytic_jacobian_chain_through_the_block():
    """``_make_jacobian``'s restraint rows against a central FD of the residual.

    The restraint here joins a body atom (a derived row) to the free Li.  The
    analytic block is ``R_phys @ ∂p/∂p_free``; with C in that slot (the
    pre-WP-1804 line) every body column of the restraint row is zero and the
    cell columns are short by the body atom's share.
    """
    from rietx.optimize.least_squares import _make_jacobian, _make_residual

    table, _, s = _build_block(restraint=True)
    model = _toy_model(table, s)
    assert model.restraints is not None
    theta = _theta_at(table)
    n_res = len(model.restraints.items)
    jac = _make_jacobian(model, table)(theta)[-n_res:]
    resid = _make_residual(model, table)
    fd = np.zeros_like(jac)
    for c in range(len(theta)):
        h = 1e-6 * max(1.0, abs(theta[c]))
        tp, tm = theta.copy(), theta.copy()
        tp[c] += h
        tm[c] -= h
        fd[:, c] = (resid(tp)[-n_res:] - resid(tm)[-n_res:]) / (2 * h)
    assert np.abs(jac).max() > 0.0
    scale = np.abs(fd).max()
    assert np.allclose(jac, fd, rtol=1e-5, atol=1e-6 * scale)
    # and the body columns are the ones that matter: not all zero
    body = [table.free_paths.index(f"phases.0.rigid_bodies.0.origin.{k}") for k in "xyz"]
    assert np.abs(jac[:, body]).max() > 1e-3 * scale


# ------------------------------------------------ declaration-order enforcement
def test_add_derived_refuses_an_output_an_earlier_block_reads():
    """The docstring's rule, enforced: blocks apply in one pass in declaration
    order, so a later block writing an earlier block's input leaves the first
    evaluated on a stale value."""

    class _Copy(DerivedBlock):
        def __init__(self, src, dst):
            self.inputs, self.outputs = (src,), (dst,)

        def evaluate(self, x):
            return np.asarray(x, dtype=float)

        def jacobian(self, x):
            return np.eye(1)

        def evaluate_traced(self, x):
            return list(x)

        def reach_pattern(self):
            return np.ones((1, 1), dtype=bool)

    def scratch_table():
        table = ParameterTable(_structure(2), LAB)
        for q in ("a", "b"):
            table.add_parameter(f"phases.0.scratch.{q}", 0.0)
            table.entries[table._paths[f"phases.0.scratch.{q}"]].locked = True
        table._rebuild()
        return table

    table = scratch_table()
    table.add_derived(_Copy("phases.0.scratch.a", "phases.0.scratch.b"))
    with pytest.raises(ValueError, match="earlier derived block"):
        table.add_derived(_Copy("phases.0.cell.a", "phases.0.scratch.a"))
    # declared in dependency order, the same pair is accepted
    ok = scratch_table()
    ok.add_derived(_Copy("phases.0.cell.a", "phases.0.scratch.a"))
    ok.add_derived(_Copy("phases.0.scratch.a", "phases.0.scratch.b"))
