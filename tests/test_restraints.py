"""Soft restraints: bond/angle/value penalty rows (WP-0406).

A restraint contributes a √w·(computed − target)/σ residual row kept in the
covariance but excluded from Rwp/Durbin-Watson/Bérar-Lelann.  The rows are
nonlinear in the coordinates and cell (unlike the P-spline / Pawley precedents),
so the analytic row-Jacobian is checked against finite differences of the
augmented residual, and the data-row statistics are proved unchanged.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from rietx import Instrument, PatternData, Refinement, Stage
from rietx.crystallography.structure_factor import compile_phase_sites
from rietx.model.forward import compile_model
from rietx.model.restraints import (
    _atom_xyz,
    _metric_g,
    _resolve_image,
    summarise_restraints,
)
from rietx.optimize.least_squares import (
    _make_jacobian,
    _make_residual,
    run_multi_least_squares,
)
from rietx.optimize.statistics import compute_statistics
from rietx.params.multi import MultiParameterTable
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.structure import (
    AngleRestraint,
    Atom,
    BondRestraint,
    Cell,
    Phase,
    Structure,
    ValueRestraint,
)
from tests.test_coordinates import RUTILE_OX, make_rutile, synthesize_rutile

OUT = Path(__file__).parent / "output"
LAB = Instrument.debye_scherrer(wavelength=1.5406)


def _save(result, name: str) -> None:
    pytest.importorskip("matplotlib")
    OUT.mkdir(exist_ok=True)
    from rietx.viz.plots import plot_result

    plot_result(result, path=str(OUT / name))


def _blank(lo=15.0, hi=80.0, step=0.05) -> PatternData:
    tt = np.arange(lo, hi, step)
    return PatternData(two_theta=tt.tolist(), intensity=np.ones_like(tt).tolist())


def _rutile_with_bond(o_x: float, target: float, sigma: float) -> Structure:
    s = make_rutile(o_x, vary_coords=True)
    s.phases[0].restraints = [BondRestraint(atom_i=0, atom_j=1, target=target, sigma=sigma)]
    return s


def _true_ti_o_bond() -> float:
    """The Ti–O apical bond length in the reference rutile (min-image)."""
    s = _rutile_with_bond(RUTILE_OX, target=0.0, sigma=1.0)
    model = compile_model(s, LAB, _blank(), mode="rietveld")
    table = ParameterTable(s, LAB)
    return summarise_restraints(model.restraints, table.decode(table.x0())).rows[0].computed


def _triclinic(restraints) -> tuple[Structure, ParameterTable]:
    """A P1 cell with generic, non-collinear atoms — every cell angle and
    coordinate DOF is free, so the ∂G/∂{a..γ} and angle quotient rules are all
    exercised by one FD comparison."""
    def P(v):
        return Parameter(value=v, vary=True, min=0.1)

    s = Structure(phases=[Phase(
        name="tri", space_group="P1",
        cell=Cell(a=P(5.1), b=P(5.7), c=P(6.3),
                  alpha=Parameter(value=88.0, vary=True),
                  beta=Parameter(value=95.0, vary=True),
                  gamma=Parameter(value=101.0, vary=True)),
        atoms=[Atom(label="A", species="Fe", x=Parameter(value=0.12, vary=True),
                    y=Parameter(value=0.20, vary=True), z=Parameter(value=0.33, vary=True)),
               Atom(label="B", species="O", x=Parameter(value=0.40, vary=True),
                    y=Parameter(value=0.15, vary=True), z=Parameter(value=0.50, vary=True)),
               Atom(label="C", species="O", x=Parameter(value=0.05, vary=True),
                    y=Parameter(value=0.55, vary=True), z=Parameter(value=0.22, vary=True))],
        scale=Parameter(value=1e-2, vary=True, min=0.0, transform="softplus"),
        restraints=restraints)])
    return s, ParameterTable(s, LAB)


# ------------------------------------------------------------ (a) recovery
def test_bond_restraint_recovers_perturbed_coordinate():
    """A bond-length restraint at the true distance recovers a displaced atom."""
    pattern = synthesize_rutile()
    target = _true_ti_o_bond()
    s = _rutile_with_bond(RUTILE_OX + 0.012, target=target, sigma=0.005)  # ~0.05 Å off
    s.phases[0].scale.value = 6e-3
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 1.2e-2

    ref = Refinement(s, ins)
    result = ref.fit(pattern, plan="mccusker_structural")
    assert result.status == "converged"
    assert result.statistics.gof < 1.3
    assert result.restraints is not None and result.restraints.n_restraints == 1

    row = result.restraints.rows[0]
    assert row.kind == "bond" and row.atoms == [0, 1]
    assert abs(row.deviation_over_sigma) < 3.0, "restraint left unsatisfied"

    o = ref.fitted_structure.phases[0].atoms[1]
    x_par = result.parameter("phases.0.atoms.1.x")
    assert x_par.stderr is not None and x_par.stderr > 0
    assert o.x.value == pytest.approx(RUTILE_OX, abs=max(5 * x_par.stderr, 5e-4))
    assert o.y.value == o.x.value  # site-symmetry [110] tie held throughout

    # no spurious tension when data and restraint agree
    assert not [d for d in result.diagnostics if d.code == "RESTRAINT_TENSION"]
    _save(result, "restraint_bond_rutile.png")


def test_bond_restraint_has_teeth():
    """A tight restraint with a shifted target measurably biases the coordinate
    away from the data-only optimum — proof the row actually pulls."""
    pattern = synthesize_rutile()
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 1.2e-2

    free = make_rutile(RUTILE_OX, vary_coords=True)
    free.phases[0].scale.value = 8e-3
    x_free = Refinement(free, ins, history=False).fit(
        pattern, plan="mccusker_structural").parameter("phases.0.atoms.1.x").value

    pulled_struct = _rutile_with_bond(RUTILE_OX, target=_true_ti_o_bond() + 0.05, sigma=0.003)
    pulled_struct.phases[0].scale.value = 8e-3
    x_pulled = Refinement(pulled_struct, ins, history=False).fit(
        pattern, plan="mccusker_structural").parameter("phases.0.atoms.1.x").value
    assert abs(x_pulled - x_free) > 1e-3, "restraint had no effect on the coordinate"


# ------------------------------------------------- (b) analytic Jacobian vs FD
def test_restraint_jacobian_matches_fd_per_kind():
    """Analytic restraint-row Jacobian vs FD of the augmented residual, <5e-3,
    for bond, angle and value rows simultaneously (triclinic → cell-angle
    partials exercised too)."""
    s, table = _triclinic([
        BondRestraint(atom_i=0, atom_j=1, target=2.0, sigma=0.02, op_index=0),
        AngleRestraint(atom_i=1, atom_j=0, atom_k=2, target_deg=100.0, sigma=1.0,
                       op_index_i=0, op_index_k=0),
        ValueRestraint(path="phases.0.atoms.1.occ", target=0.9, sigma=0.05),
    ])
    model = compile_model(s, LAB, _blank(20.0, 90.0, 0.1), mode="rietveld",
                          moving_paths=set(table.moving_paths))
    n_data = len(model.tt)
    kinds = [r.kind for r in summarise_restraints(
        model.restraints, table.decode(table.x0())).rows]
    assert kinds == ["bond", "angle", "value"]  # no degenerate (collinear) angle

    theta = table.x0()
    J = _make_jacobian(model, table)(theta)
    residual = _make_residual(model, table)
    r0 = residual(theta)
    assert J.shape == (len(r0), len(theta))
    assert len(r0) == n_data + model.restraints.n_rows

    for row in range(model.restraints.n_rows):
        for c in range(len(theta)):
            h = 1e-6 * max(1.0, abs(theta[c]))
            tp = theta.copy()
            tp[c] += h
            fd = (residual(tp)[n_data + row] - r0[n_data + row]) / h
            an = J[n_data + row, c]
            denom = max(abs(fd), abs(an), 1e-8)
            assert abs(an - fd) / denom < 5e-3, (
                f"restraint row {row} ({kinds[row]}), col {c}: "
                f"analytic {an:.3e} vs FD {fd:.3e}")


# --------------------------------------------- (c) statistics exclude the rows
def test_data_row_statistics_bit_identical_to_no_restraint():
    """Rwp/DW/χ²/n_points at the same parameters are bit-identical whether or
    not restraint rows are present — the residual splits them below the data."""
    pattern = synthesize_rutile()
    s0 = make_rutile(RUTILE_OX, vary_coords=True)
    s_r = make_rutile(RUTILE_OX, vary_coords=True)
    s_r.phases[0].restraints = [
        BondRestraint(atom_i=0, atom_j=1, target=1.90, sigma=0.01),
        ValueRestraint(path="phases.0.atoms.1.occ", target=0.8, sigma=0.02)]

    m0 = compile_model(s0, LAB, pattern, mode="rietveld")
    mr = compile_model(s_r, LAB, pattern, mode="rietveld")
    table = ParameterTable(s0, LAB)
    theta = table.x0()

    r0 = _make_residual(m0, table)(theta)
    rr = _make_residual(mr, table)(theta)
    n_data = len(m0.tt)
    assert len(rr) == len(r0) + mr.restraints.n_rows == n_data + 2
    assert np.array_equal(rr[:n_data], r0[:n_data]), "restraints perturbed data rows"

    values = table.decode(theta)
    st0 = compute_statistics(m0.y_obs, m0.evaluate(values), m0.sigma, n_free=1)
    st_r = compute_statistics(mr.y_obs, mr.evaluate(values), mr.sigma, n_free=1)
    assert (st0.rwp, st0.durbin_watson, st0.chi2, st0.esd_inflation, st0.n_points) == (
        st_r.rwp, st_r.durbin_watson, st_r.chi2, st_r.esd_inflation, st_r.n_points)

    # and the reported n_points from a real fit counts data rows only
    result = Refinement(s_r, LAB, history=False).fit(pattern, plan="mccusker_structural")
    assert result.statistics.n_points == len(pattern.two_theta)


# ------------------------------------------------------------ (d) conventions
def test_schema_json_round_trip():
    s = _rutile_with_bond(RUTILE_OX, target=1.95, sigma=0.01)
    s.phases[0].restraints += [
        AngleRestraint(atom_i=1, atom_j=0, atom_k=1, target_deg=90.0, sigma=2.0,
                       op_index_k=1, translation_k=(0, -1, 0)),
        ValueRestraint(path="phases.0.atoms.1.occ", target=1.0, sigma=0.05)]
    back = Structure.model_validate_json(s.model_dump_json())
    assert back == s
    kinds = [type(r).__name__ for r in back.phases[0].restraints]
    assert kinds == ["BondRestraint", "AngleRestraint", "ValueRestraint"]
    assert isinstance(back.phases[0].restraints[1].translation_k, tuple)


def test_angle_vertex_is_the_middle_atom():
    """The vertex of an i–j–k angle is the *middle* atom j: u = x_i − x_j,
    v = x_k − x_j."""
    s, table = _triclinic([AngleRestraint(atom_i=0, atom_j=1, atom_k=2,
                                          target_deg=0.0, sigma=1.0,
                                          op_index_i=0, op_index_k=0)])
    model = compile_model(s, LAB, _blank(20.0, 90.0, 0.2), mode="rietveld")
    values = table.decode(table.x0())
    computed = summarise_restraints(model.restraints, values).rows[0].computed

    g = _metric_g(s.phases[0].cell.lengths_angles())
    xj = _atom_xyz(s.phases[0], 1)  # vertex = middle atom (atom_j)
    u = _atom_xyz(s.phases[0], 0) - xj
    v = _atom_xyz(s.phases[0], 2) - xj
    cos = (u @ g @ v) / np.sqrt((u @ g @ u) * (v @ g @ v))
    assert computed == pytest.approx(np.degrees(np.arccos(cos)), abs=1e-6)

    # a different atom as vertex gives a different angle (sanity: j really is used)
    xi = _atom_xyz(s.phases[0], 0)
    u2 = _atom_xyz(s.phases[0], 1) - xi
    v2 = _atom_xyz(s.phases[0], 2) - xi
    other = np.degrees(np.arccos((u2 @ g @ v2) / np.sqrt((u2 @ g @ u2) * (v2 @ g @ v2))))
    assert abs(other - computed) > 1.0


def test_min_image_freezes_nearest_image():
    """With no op_index the compile freezes the closest symmetry image; with an
    explicit op_index it uses exactly that operation."""
    s = make_rutile()
    sites = compile_phase_sites(s.phases[0])
    cell = s.phases[0].cell.lengths_angles()
    g = _metric_g(cell)
    x_i = _atom_xyz(s.phases[0], 0)      # Ti at origin
    x_j = _atom_xyz(s.phases[0], 1)      # O
    rot, tr, n = _resolve_image(sites, 1, x_i, x_j, None, (0, 0, 0), g)

    # brute-force minimum image over the same op subset × {-1,0,1}^3
    ops_r, ops_t = sites.ops[1]
    best = np.inf
    for mi in range(len(ops_r)):
        img0 = ops_r[mi] @ x_j + ops_t[mi]
        for na in (-1, 0, 1):
            for nb in (-1, 0, 1):
                for nc in (-1, 0, 1):
                    dx = img0 + np.array([na, nb, nc]) - x_i
                    d2 = float(dx @ (g @ dx))
                    if d2 > 1e-6:
                        best = min(best, d2)
    chosen = (rot @ x_j + tr + n) - x_i
    assert float(chosen @ (g @ chosen)) == pytest.approx(best, rel=1e-12)

    # explicit op_index bypasses the search and picks that operation verbatim
    rot0, tr0, n0 = _resolve_image(sites, 1, x_i, x_j, 2, (1, 0, 0), g)
    assert np.array_equal(rot0, ops_r[2]) and np.array_equal(tr0, ops_t[2])
    assert np.array_equal(n0, np.array([1.0, 0.0, 0.0]))


def test_min_image_does_not_depend_on_the_stored_cell():
    """The auto-search finds the same nearest image wherever the coordinates
    are stored: shifting an atom by whole lattice vectors (a CIF that keeps a
    molecule whole across a cell edge, a rigid body placed about any origin)
    leaves its restrained distance unchanged.  P2₁ toy: Li at x = 0.10 and an
    O whose 2₁ image sits 2.0 Å away; moved two cells along a, the old
    {−1,0,1}³ shell about n = 0 could not reach that image."""
    cell = Cell(a=Parameter(value=5.0), b=Parameter(value=6.0), c=Parameter(value=7.0),
                alpha=Parameter(value=90.0), beta=Parameter(value=90.0),
                gamma=Parameter(value=90.0))

    def phase(shift):
        li = np.array([0.10, 0.10, 0.10]) + shift
        o = np.array([-0.10, -0.40, -0.10 + 2.0 / 7.0])   # 2₁ image: (0.10, 0.10, 0.10 − 2/7)
        return Phase(name="t", space_group="P 1 21 1", cell=cell, atoms=[
            Atom(label="Li1", species="Li", x=Parameter(value=li[0]),
                 y=Parameter(value=li[1]), z=Parameter(value=li[2])),
            Atom(label="O1", species="O", x=Parameter(value=o[0]),
                 y=Parameter(value=o[1]), z=Parameter(value=o[2]))])

    g = _metric_g(cell.lengths_angles())
    for shift in ([0, 0, 0], [1, 0, 0], [2, 0, 0], [-3, 2, 1], [0, 0, 5]):
        ph = phase(np.array(shift, dtype=np.float64))
        sites = compile_phase_sites(ph)
        x_i, x_j = _atom_xyz(ph, 0), _atom_xyz(ph, 1)
        rot, tr, n = _resolve_image(sites, 1, x_i, x_j, None, (0, 0, 0), g)
        dx = rot @ x_j + tr + n - x_i
        assert float(np.sqrt(dx @ (g @ dx))) == pytest.approx(2.0, abs=1e-9), shift


def test_min_image_refreezes_when_coordinates_move():
    """Frozen-per-stage: a recompile at moved coordinates re-resolves the image
    (the discrete choice tracks the coordinates between stages)."""
    ins = LAB
    s_near = _rutile_with_bond(0.02, target=1.0, sigma=1.0)   # O close to Ti
    s_far = _rutile_with_bond(0.30, target=1.0, sigma=1.0)    # O near mid-cell
    d_near = summarise_restraints(
        compile_model(s_near, ins, _blank(), mode="rietveld").restraints,
        ParameterTable(s_near, ins).decode(ParameterTable(s_near, ins).x0())).rows[0].computed
    d_far = summarise_restraints(
        compile_model(s_far, ins, _blank(), mode="rietveld").restraints,
        ParameterTable(s_far, ins).decode(ParameterTable(s_far, ins).x0())).rows[0].computed
    assert d_near < d_far  # different min-image frozen at each compile-time position


# --------------------------- (d2) MIN_IMAGE_SHELL over its domain (WP-2002, B10)
#: the longest pair a restraint names: bonds and anti-bump contacts, in Å
_PAIR_MAX_ANG = 4.0


def _reduced(cell):
    """The Niggli-reduced cell of ``cell`` (gemmi's Gruber reduction)."""
    import gemmi

    gv = gemmi.GruberVector(gemmi.UnitCell(*cell), None)
    gv.niggli_reduce()
    c = gv.get_cell()
    return (c.a, c.b, c.c, c.alpha, c.beta, c.gamma)


def _domain_cells(kind, rng, n):
    lengths = lambda: rng.uniform(2.4, 30.0, 3)  # noqa: E731
    if kind == "hexagonal":
        return [(a, a, c, 90.0, 90.0, 120.0)
                for a, c in zip(rng.uniform(2.4, 30.0, n), rng.uniform(2.4, 60.0, n),
                                strict=True)]
    if kind == "rhombohedral":
        return [(a, a, a, al, al, al)
                for a, al in zip(rng.uniform(3.0, 15.0, n), rng.uniform(30.0, 115.0, n),
                                 strict=True)]
    if kind == "reduced_triclinic":
        cells = []
        while len(cells) < n:
            cell = (*lengths(), *rng.uniform(40.0, 140.0, 3))
            try:
                ok = _metric_g(cell)
            except ValueError:
                continue
            if np.linalg.eigvalsh(ok).min() > 0:
                cells.append(_reduced(cell))
        return cells
    if kind == "reduced_monoclinic":
        return [_reduced((*lengths(), 90.0, beta, 90.0))
                for beta in rng.uniform(90.0, 160.0, n)]
    assert kind == "monoclinic_beta_135_150"
    return [(*lengths(), 90.0, beta, 90.0) for beta in rng.uniform(135.0, 150.0, n)]


def _image_misses(cells, rng, pairs_per_cell):
    """``(misses at any distance, misses within _PAIR_MAX_ANG, pairs within it)``.

    The reference is the shell :func:`rietx.model.geometry._shell` sizes to
    reach the centred image's distance, which no nearest image exceeds.  It
    spans ceil(d·√G*ₖₖ) + 1 cells along each axis, so by the plane-spacing
    bound it holds every image closer than that distance, in any cell.  It is
    sized from the pair alone, never from what the search found, so the
    search's first pass is checked rather than repeated.  That is the
    geometry table's neighbour search, whose completeness
    ``tests/test_geometry_table.py`` proves against a plain enumeration.
    Orbit counting cannot do it here: in P 1 the search from i and the search
    from j share their rounded centre up to a sign, so a miss from one end is
    the same miss from the other.
    """
    from types import SimpleNamespace

    from rietx.model.geometry import _shell

    sites = SimpleNamespace(ops={0: (np.eye(3)[None], np.zeros((1, 3)))})
    missed = missed_short = short = 0
    for cell in cells:
        g = _metric_g(cell)
        for _ in range(pairs_per_cell):
            ref = rng.uniform(-0.5, 0.5, 3) + rng.integers(-2, 3, 3)
            x = rng.uniform(-0.5, 0.5, 3) + rng.integers(-2, 3, 3)
            _r, _t, n = _resolve_image(sites, 0, ref, x, None, None, g)
            dx = x + n - ref
            found = float(np.sqrt(dx @ g @ dx))
            f = x - ref
            centred = f + np.round(-f)
            reach = float(np.sqrt(centred @ g @ centred))
            if reach < 1e-3:   # coincident: the nearest is a lattice vector away
                reach = float(np.sqrt(np.diag(g).min()))
            cand = centred[None, :] + _shell(g, reach + 1e-9)
            d2 = np.einsum("sa,ab,sb->s", cand, g, cand)
            best = float(np.sqrt(d2[d2 > 1e-6].min()))
            short += best <= _PAIR_MAX_ANG
            if found > best * (1.0 + 1e-12):
                missed += 1
                missed_short += best <= _PAIR_MAX_ANG
    return missed, missed_short, short


@pytest.mark.parametrize("kind", [
    "reduced_triclinic", "reduced_monoclinic", "hexagonal", "rhombohedral",
    "monoclinic_beta_135_150"])
# slow: a domain sweep, 7.2 s for its four passing cells in the fast tier locally
# (WP-2002 handover), which would join the fast tier's tail on CI
@pytest.mark.slow
def test_one_image_shell_finds_the_nearest_image_over_its_domain(kind):
    """The minimum-image search against a complete one, in any cell (B10,
    ruled 2026-10-19).  The bar is exactness, since a missed image restrains
    the wrong pair.

    ``MIN_IMAGE_SHELL`` = 1 alone was exact on every **Niggli-reduced** cell
    (400 000 random pairs over 1000 of them, lengths 2.4-30 Å), on hexagonal
    cells and on rhombohedral axes from α = 30° to 115°.  A cell stored
    unreduced was outside it: monoclinic β past about 110° missed images
    beyond the restraint range, past 129° within 4 Å, past 136° within 3 Å,
    and at β 135-150° 72 of 2518 pairs within 4 Å (595 of 10 000 at any
    distance; a shell of 2 still missed 10 of 14 105).  The search now sizes
    a second pass from the first pass's distance, as ``geometry._shell``
    sizes the neighbour search, so the stored setting no longer matters.

    Made to fail on 2026-10-21 with the module constant patched to 0 and no
    second pass: the four reduced rows missed 1742, 766, 1651 and 2031 of
    their 10 000 pairs.  With the second pass removed, the monoclinic row
    misses again.
    """
    rng = np.random.default_rng({"reduced_triclinic": 1, "reduced_monoclinic": 2,
                                 "hexagonal": 3, "rhombohedral": 4,
                                 "monoclinic_beta_135_150": 5}[kind])
    cells = _domain_cells(kind, rng, 100)
    missed, missed_short, short = _image_misses(cells, rng, 100)
    assert short > 500, f"{kind}: only {short} pairs within {_PAIR_MAX_ANG} A"
    assert missed == missed_short == 0, (
        f"{kind}: {missed} of 10000 pairs missed their nearest image, "
        f"{missed_short} of {short} within {_PAIR_MAX_ANG} A")


# ------------------------------------------------- (e) the c_w schedule (1074)
def _scaled_triclinic(c_w: float):
    """The (b) fixture compiled at a given stage c_w; returns (model, table)."""
    s, table = _triclinic([
        BondRestraint(atom_i=0, atom_j=1, target=2.0, sigma=0.02, op_index=0),
        AngleRestraint(atom_i=1, atom_j=0, atom_k=2, target_deg=100.0, sigma=1.0,
                       op_index_i=0, op_index_k=0),
        ValueRestraint(path="phases.0.atoms.1.occ", target=0.9, sigma=0.05),
    ])
    model = compile_model(s, LAB, _blank(20.0, 90.0, 0.1), mode="rietveld",
                          moving_paths=set(table.moving_paths),
                          restraint_weight_scale=c_w)
    return model, table


def test_stage_scale_multiplies_every_restraint_row_by_sqrt_cw():
    """c_w weights S_G, so each row — the thing squared — carries √c_w, and the
    data rows above it are untouched (McCusker eq 7: S = S_y + c_w·S_G)."""
    m1, table = _scaled_triclinic(1.0)
    m4, _ = _scaled_triclinic(4.0)
    theta = table.x0()
    r1 = _make_residual(m1, table)(theta)
    r4 = _make_residual(m4, table)(theta)
    n_data = len(m1.tt)
    n_restr = m1.restraints.n_rows

    assert np.array_equal(r1[:n_data], r4[:n_data]), "data rows moved"
    np.testing.assert_allclose(r4[n_data:], 2.0 * r1[n_data:], rtol=0, atol=0)
    # the Jacobian carries the same factor, and only on those rows
    J1 = _make_jacobian(m1, table)(theta)
    J4 = _make_jacobian(m4, table)(theta)
    assert np.array_equal(J1[:n_data], J4[:n_data])
    np.testing.assert_allclose(J4[n_data:], 2.0 * J1[n_data:], rtol=0, atol=0)
    assert len(r4) == n_data + n_restr


def test_zero_scale_keeps_the_rows_in_the_layout():
    """c_w = 0 silences the restraints without removing their rows: the block
    membership the statistics exclusion is built on must not change mid-plan."""
    m0, table = _scaled_triclinic(0.0)
    r0 = _make_residual(m0, table)(table.x0())
    n_data = len(m0.tt)
    assert m0.restraints.n_rows == 3
    assert len(r0) == n_data + 3
    assert np.array_equal(r0[n_data:], np.zeros(3))


def test_identity_default_is_the_pre_schedule_row():
    """The default takes the identity path: rows are exactly √w·(computed −
    target)/σ, the WP-0406 formula, with no √1.0 round trip in between."""
    s, table = _triclinic([
        BondRestraint(atom_i=0, atom_j=1, target=2.0, sigma=0.02, op_index=0),
        ValueRestraint(path="phases.0.atoms.1.occ", target=0.9, sigma=0.05),
    ])
    # compiled without the argument at all — the pre-WP-1074 call
    m = compile_model(s, LAB, _blank(20.0, 90.0, 0.1), mode="rietveld",
                      moving_paths=set(table.moving_paths))
    assert m.restraint_weight_scale == 1.0
    rows = _make_residual(m, table)(table.x0())[len(m.tt):]
    report = summarise_restraints(m.restraints, table.decode(table.x0()))
    hand = np.array([np.sqrt(r.weight) * r.deviation / r.sigma for r in report.rows])
    np.testing.assert_allclose(rows, hand, rtol=0, atol=0)


def test_restraint_jacobian_matches_fd_under_a_scale():
    """The analytic block and FD of the augmented residual agree at c_w ≠ 1 —
    the two seams (row build, Jacobian block) cannot drift apart silently."""
    model, table = _scaled_triclinic(7.5)
    theta = table.x0()
    J = _make_jacobian(model, table)(theta)
    residual = _make_residual(model, table)
    r0 = residual(theta)
    n_data = len(model.tt)

    for row in range(model.restraints.n_rows):
        for c in range(len(theta)):
            h = 1e-6 * max(1.0, abs(theta[c]))
            tp = theta.copy()
            tp[c] += h
            fd = (residual(tp)[n_data + row] - r0[n_data + row]) / h
            an = J[n_data + row, c]
            denom = max(abs(fd), abs(an), 1e-8)
            assert abs(an - fd) / denom < 5e-3, (
                f"row {row}, col {c}: analytic {an:.3e} vs FD {fd:.3e}")


def test_a_negative_scale_is_refused():
    s, table = _triclinic([BondRestraint(atom_i=0, atom_j=1, target=2.0, sigma=0.02)])
    with pytest.raises(ValueError, match="restraint_weight_scale"):
        compile_model(s, LAB, _blank(20.0, 90.0, 0.1), mode="rietveld",
                      restraint_weight_scale=-1.0)


def test_the_report_records_the_scale_it_was_measured_under():
    """A result carries no plan, so S_G's weighting is only knowable if the
    report says it: the penalty in S is weight_scale·restraint_chi2."""
    m, table = _scaled_triclinic(9.0)
    report = summarise_restraints(m.restraints, table.decode(table.x0()),
                                  m.restraint_weight_scale)
    assert report.weight_scale == 9.0
    # deviations stay unscaled — the geometry question, not the weighting one
    plain = summarise_restraints(m.restraints, table.decode(table.x0()))
    assert plain.weight_scale == 1.0
    assert plain.restraint_chi2 == report.restraint_chi2


def test_the_scale_is_recorded_on_the_node_and_survives_a_cherry_pick():
    """``NodeAction`` carries the stage's own arguments, so a stiff stage
    cherry-picked elsewhere runs stiff (the seed/strain_seed rule, WP-1004)."""
    from rietx import Stage

    pattern = synthesize_rutile()
    s = _rutile_with_bond(RUTILE_OX + 0.008, target=_true_ti_o_bond(), sigma=0.01)
    s.phases[0].scale.value = 6e-3
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 1.2e-2

    ref = Refinement(s, ins)
    ref.run_stage(pattern, Stage("scale_bkg", ["phases.*.scale",
                                               "instrument.background.*"]))
    ref.run_stage(pattern, Stage("stiff", ["phases.*.atoms.*.dof.*"],
                                 restraint_weight_scale=25.0))
    node = ref.history[ref.history.order[-1]]
    assert node.action.restraint_weight_scale == 25.0
    assert "restraint_weight_scale=25.0" in node.action.api_call()
    # an unscaled stage keeps its pre-WP-1074 line exactly
    assert "restraint_weight_scale" not in ref.history[
        ref.history.order[-2]].action.api_call()

    ref.cherry_pick(node.id, pattern)
    picked = ref.history[ref.history.order[-1]]
    assert picked.action.restraint_weight_scale == 25.0


def test_the_stage_spec_mirror_round_trips_the_scale():
    from rietx import Stage
    from rietx.schemas.plan import StageSpec

    stage = Stage("stiff", ["phases.*.atoms.*.dof.*"], restraint_weight_scale=12.5)
    spec = StageSpec.from_stage(stage)
    assert spec.restraint_weight_scale == 12.5
    assert spec.model_validate_json(spec.model_dump_json()).to_stage(
        ).restraint_weight_scale == 12.5


# ---------------------------------------- (f) the schedule on an under-
# determined case: stiff while the model is approximate, relaxed as it improves
#
# P-1 rather than P1 on purpose.  In P1 the inverted structure is an *exact*
# powder degeneracy (|F(h)|² is unchanged by x → −x) and it preserves every
# interatomic distance, so restraints cannot tell the two apart at any c_w and
# a wrong-basin fit is not evidence about the schedule.  A centrosymmetric
# group is its own inverse, so that degeneracy is gone.
#
# The heavy atom sits on the inversion centre (0 DOFs, origin fixed); the two
# oxygens are general positions, 6 coordinate DOFs against 35 reflections over
# 12-34° — under-determined the way McCusker §8 opens, "powder diffraction data
# … suffer from an inherent loss of information".
_SCHED_TRUE = {1: (0.2600, 0.1450, 0.1200), 2: (-0.1400, 0.2300, 0.1550)}
#: a bad start: Zr-O1 begins at 3.73 Å, an impossible bond.  A *specific* bad
#: start, not a magnitude claim — whether one escapes the basin depends on the
#: direction it went, and starts of this size in other directions converge fine.
_SCHED_START = {1: (0.545729, -0.212793, 0.178534),
                2: (-0.219488, 0.166629, 0.124816)}
_SCHED_FREE = ["phases.0.atoms.1.dof.*", "phases.0.atoms.2.dof.*"]


def _sched_structure(coords, restraints=()) -> Structure:
    def P(v, **kw):
        return Parameter(value=v, **kw)

    atoms = [Atom(label="Zr", species="Zr", x=P(0.0), y=P(0.0), z=P(0.0),
                  biso=P(0.5))]
    for i, (x, y, z) in coords.items():
        atoms.append(Atom(label=f"O{i}", species="O", x=P(x), y=P(y), z=P(z),
                          biso=P(3.0)))  # weak scatterers, damped at high Q
    return Structure(phases=[Phase(
        name="p-1", space_group="P -1",
        cell=Cell(a=P(6.10, min=0.1), b=P(6.55, min=0.1), c=P(7.02, min=0.1),
                  alpha=P(88.0), beta=P(99.5), gamma=P(95.0)),
        atoms=atoms,
        scale=Parameter(value=8e-3, vary=True, min=0.0, transform="softplus"),
        restraints=list(restraints))])


def _sched_instrument() -> Instrument:
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 8e-3
    return ins


def schedule_inputs():
    """(pattern, [true Zr-O1, true Zr-O2]) for the under-determined P-1 case.

    A plain function beside the fixture so `docs/docs/make_figures.py` draws
    the manual's c_w figure from *this* case rather than from a second copy of
    it: the picture in the manual and the assertions below then cannot disagree
    about what the schedule did.
    """
    ins = _sched_instrument()
    truth = _sched_structure(_SCHED_TRUE)
    tt = np.arange(12.0, 34.0, 0.02)
    blank = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(truth, ins, blank, mode="rietveld")
    table = ParameterTable(truth, ins)
    y = model.evaluate(table.decode(table.x0())) + 30.0
    y = np.random.default_rng(7).poisson(np.maximum(y, 1.0)).astype(float)
    pattern = PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())

    probe = _sched_structure(_SCHED_TRUE, [
        BondRestraint(atom_i=0, atom_j=j, target=0.0, sigma=1.0,
                      op_index=0, translation=[0, 0, 0]) for j in (1, 2)])
    pm = compile_model(probe, ins, blank, mode="rietveld")
    pt = ParameterTable(probe, ins)
    bonds = [r.computed for r in summarise_restraints(
        pm.restraints, pt.decode(pt.x0())).rows]
    return pattern, bonds


@pytest.fixture(scope="module")
def schedule_case():
    return schedule_inputs()


def _sched_run(pattern, bonds, c_w_first, c_w_second):
    """The three stages, run one at a time so each boundary can be read.

    Both plans have the same shape and the same bad start; c_w is the only
    variable.  Returns (result after the first coordinate stage, final result).
    """
    s = _sched_structure(_SCHED_START, [
        BondRestraint(atom_i=0, atom_j=j, target=bonds[j - 1], sigma=0.02,
                      op_index=0, translation=[0, 0, 0]) for j in (1, 2)])
    ref = Refinement(s, _sched_instrument(), history=False)
    ref.run_stage(pattern, Stage("scale_bkg", ["phases.*.scale",
                                               "instrument.background.*"]))
    first = ref.run_stage(pattern, Stage("coords_a", _SCHED_FREE,
                                         restraint_weight_scale=c_w_first))
    final = ref.run_stage(pattern, Stage("coords_b", _SCHED_FREE,
                                         restraint_weight_scale=c_w_second))
    return first, final


def _sched_coords(result):
    return {i: np.array([result.parameter(f"phases.0.atoms.{i}.{c}").value
                         for c in "xyz"]) for i in _SCHED_TRUE}


def _sched_error(result) -> float:
    got = _sched_coords(result)
    return float(np.sqrt(np.mean(
        [((got[i] - np.array(v)) ** 2).sum() for i, v in _SCHED_TRUE.items()])))


@pytest.mark.xdist_group("restraint-schedule")
def test_a_flat_weak_weight_lets_the_geometry_go(schedule_case):
    """The control, and McCusker §8's own failure mode: with the restraints at
    c_w = 1 against 1100 channels they are nearly inaudible, and from this start
    the fit converges with "unreasonably long" (§8) Zr-O — measured 4.83 Å for a
    1.87 Å bond, the restraint 148σ in tension.

    It *converges*, and the data-row statistics are the weaker signal by far:
    Rwp 0.0393 against the scheduled fit's 0.0327, GoF 1.23 against 1.02, and a
    difference curve inside ±3σ but for three excursions (see the saved PNG).
    A reader watching Rwp sees a slightly worse fit; a reader watching the
    restraint deviation sees a 4.8 Å bond.  That is why the deviation is what
    this WP's evidence is read off."""
    pattern, bonds = schedule_case
    _, result = _sched_run(pattern, bonds, 1.0, 1.0)

    assert result.status == "converged"
    worst = max(abs(r.deviation_over_sigma) for r in result.restraints.rows)
    assert worst > 50.0, "the control was supposed to leave the geometry behind"
    assert max(r.computed for r in result.restraints.rows) > 4.0
    assert _sched_error(result) > 0.1
    assert [d for d in result.diagnostics if d.code == "RESTRAINT_TENSION"]
    _save(result, "restraint_schedule_flat.png")


@pytest.mark.xdist_group("restraint-schedule")
def test_stiff_then_relaxed_holds_the_geometry_and_converges(schedule_case):
    """The schedule of eq (7): c_w high while the model is approximate, reduced
    "during the course of the refinement as the structural model improves".

    Same plan shape as the control, same data, same bad start — the only
    variable is c_w — and it recovers both oxygens to 1e-3 in fractional
    coordinates with the bonds intact.  The stiff stage is checked at its own
    boundary, because a schedule buys a *path*: what the first stage does is
    move the model into the basin the second one then converges in.

    The failure mode §8 warns of stays a caller's problem: "if the geometric
    assumptions are invalid …, the refinement will not progress satisfactorily".
    A stiff c_w makes a wrong restraint more authoritative, not less.
    """
    pattern, bonds = schedule_case
    stiff, result = _sched_run(pattern, bonds, 300.0, 1.0)

    assert result.status == "converged"
    # the first coordinate stage already holds the geometry: its restraint rows
    # come back within a σ of target, from a 3.73 Å start
    assert max(abs(r.deviation_over_sigma) for r in stiff.restraints.rows) < 1.0
    assert stiff.restraints.weight_scale == 300.0

    worst = max(abs(r.deviation_over_sigma) for r in result.restraints.rows)
    assert worst < 3.0, "the relaxed stage threw the geometry away again"
    assert _sched_error(result) < 0.01
    assert result.restraints.weight_scale == 1.0
    assert not [d for d in result.diagnostics if d.code == "RESTRAINT_TENSION"]
    _save(result, "restraint_schedule_stiff_then_relaxed.png")


# ---------------------------------------------------------- diagnostics/guards
def test_restraint_tension_flags_conflict_with_data():
    """A restraint fighting the data (tight σ, target far from the true bond)
    fires RESTRAINT_TENSION — a bad sub-fit is never hidden."""
    pattern = synthesize_rutile()
    s = _rutile_with_bond(RUTILE_OX, target=_true_ti_o_bond() + 0.10, sigma=0.004)
    s.phases[0].scale.value = 8e-3
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 1.2e-2
    result = Refinement(s, ins, history=False).fit(pattern, plan="mccusker_structural")
    flagged = [d for d in result.diagnostics if d.code == "RESTRAINT_TENSION"]
    assert flagged, "restraint fighting the data was not flagged"
    assert "rutile" in " ".join(flagged[0].where)
    assert abs(result.restraints.rows[0].deviation_over_sigma) > 3.0


def test_multi_histogram_restraints_raise():
    s = _rutile_with_bond(RUTILE_OX, target=1.95, sigma=0.01)
    model = compile_model(s, LAB, _blank(20.0, 80.0, 0.1), mode="rietveld")
    mtable = MultiParameterTable(s, [LAB])
    with pytest.raises(NotImplementedError, match="multi-histogram"):
        run_multi_least_squares([model], mtable)


def test_lebail_pawley_ignore_restraints():
    """Restraints are Rietveld-only: Le Bail/Pawley compile no restraint rows."""
    s = _rutile_with_bond(RUTILE_OX, target=1.95, sigma=0.01)
    for mode in ("lebail", "pawley"):
        model = compile_model(s, LAB, _blank(), mode=mode)
        assert model.restraints is None
