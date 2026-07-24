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

from pxrdref import Instrument, PatternData, Refinement
from pxrdref.crystallography.structure_factor import compile_phase_sites
from pxrdref.model.forward import compile_model
from pxrdref.model.restraints import (
    _atom_xyz,
    _metric_g,
    _resolve_image,
    summarise_restraints,
)
from pxrdref.optimize.least_squares import (
    _make_jacobian,
    _make_residual,
    run_multi_least_squares,
)
from pxrdref.optimize.statistics import compute_statistics
from pxrdref.params.multi import MultiParameterTable
from pxrdref.params.vector import ParameterTable
from pxrdref.schemas.common import Parameter
from pxrdref.schemas.structure import (
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
    from pxrdref.viz.plots import plot_result

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
                          free_paths=set(table.free_paths))
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
