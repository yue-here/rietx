"""WP-2314 angle 4: a column whose reach crosses atoms, from the structure-factor cache.

Before angle 4 such a column went to the peak chain, which re-runs
``phase_peaks`` at a perturbed θ, so every one re-expanded the whole phase's
structure factor.  Three shapes reach across atoms here: a tie between two
atoms' coordinates (two species on one site), a named variable over several
sites or over one atom's coordinate and ADP, and a distortion-mode amplitude.
Each is now ``_site_column``: the cached ∂|F|²/∂p of every site row the
column moves, summed with the row's ∂p/∂θ_c from the table's local Jacobian.
A rigid body's columns keep the peak chain, for the reason
``_site_reach_ok``'s docstring measures.

The oracle is the chain rule itself, which is exact: the column equals the sum
of the single-row columns ∂y/∂p_q, each built by the single-atom kernel
(``coordinate_intensity_grad`` with no cache, one expansion per call), weighted
by the same ∂p_q/∂θ_c.  The two differ by rounding alone.  A
Richardson-extrapolated central difference of the residual checks the whole
column against the model, at a bar set from its truncation.
"""
from __future__ import annotations

import numpy as np
import pytest

from rietx import Instrument, PatternData
from rietx.crystallography import structure_factor as SF
from rietx.model import compiled
from rietx.model.forward import accumulate_planes, compile_model
from rietx.optimize import least_squares as LS
from rietx.optimize.least_squares import _make_jacobian, _make_residual
from rietx.params.vector import VAR_PREFIX, AffineTie, ParameterTable
from tests.test_biso_occ_columns import _structure

#: C (atom 1) and N (atom 3) are general positions, O (atom 2) is general
#: and anisotropic; ``_structure``'s P2₁/c
C_DOFS = tuple(f"phases.0.atoms.1.dof.{k}" for k in range(3))


@pytest.fixture(autouse=True)
def _numpy_path():
    """The numpy path declared, never inherited (``tests/CLAUDE.md`` §
    Quoting numbers)."""
    was = compiled.set_enabled(False)
    try:
        yield
    finally:
        compiled.set_enabled(was)


def cross_atom_state(*, ties: bool = True, dispersion: bool = True,
                     extinction: float = 0.0, **compile_kw):
    """``(model, table)`` with three shapes of cross-atom reach free.

    ``ties`` declares them: N's three coordinate DOFs following C's (the
    co-sited tie ``tests.test_large_cell_refinement.tie_co_sited`` makes), a
    named variable driving O's first coordinate DOF and its first ADP DOF
    (a reach inside one atom that the coordinate branch reads only half of),
    and a second variable driving C's Biso and O's occupancy.  Without
    ``ties`` the same paths are free and independent.  It is
    ``test_cross_backend``'s ``site_cross_atom`` state too, which passes
    ``compile_kw`` on to ``compile_model``.
    """
    from rietx.schemas.instrument import Dispersion

    structure = _structure(extinction)
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 1e-2
    ins.source.dispersion = Dispersion() if dispersion else None
    grid = np.arange(10.0, 90.0, 0.02)
    pattern = PatternData(two_theta=grid.tolist(),
                          intensity=np.zeros_like(grid).tolist())
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    if ties:
        for k in range(3):
            table.set_tie(f"phases.0.atoms.3.dof.{k}", AffineTie.identity(C_DOFS[k]))
        table.add_parameter(f"{VAR_PREFIX}D", 0.0, vary=True, lo=-1.0, hi=1.0)
        table.set_tie("phases.0.atoms.2.dof.0", AffineTie(
            terms=((f"{VAR_PREFIX}D", 1.0),), const=0.0))
        table.set_tie("phases.0.atoms.2.adp.0", AffineTie(
            terms=((f"{VAR_PREFIX}D", 0.01),),
            const=float(table.entries[table._paths["phases.0.atoms.2.adp.0"]].value)))
        table.add_parameter(f"{VAR_PREFIX}S", 0.6, vary=True, lo=0.0, hi=2.0)
        table.set_tie("phases.0.atoms.1.biso", AffineTie.identity(f"{VAR_PREFIX}S"))
        table.set_tie("phases.0.atoms.2.occ", AffineTie(
            terms=((f"{VAR_PREFIX}S", 0.5),), const=0.7))
        table.refresh_ties()
        free = C_DOFS
    else:
        free = (*C_DOFS, *(f"phases.0.atoms.3.dof.{k}" for k in range(3)),
                "phases.0.atoms.2.dof.0", "phases.0.atoms.2.adp.0",
                "phases.0.atoms.1.biso", "phases.0.atoms.2.occ")
    for glob in free:
        assert table.set_vary([glob], True), glob
    table.apply_to_models(structure, ins)
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths), **compile_kw)
    return model, table


def _theta(table):
    """x0 moved off its stored values, so no column sits at a special point."""
    theta = table.x0()
    return theta + 1e-3 * np.cos(np.arange(len(theta)))


def _claimed(monkeypatch) -> list[int]:
    """The columns ``_site_column`` builds, in order."""
    seen: list[int] = []
    real = LS._site_column

    def record(model, table, bases, values, c, *a, **k):
        seen.append(c)
        return real(model, table, bases, values, c, *a, **k)

    monkeypatch.setattr(LS, "_site_column", record)
    return seen


def _row_column(model, values, bases, q: str) -> np.ndarray:
    """∂y_calc/∂p_q for one site row, by the single-atom kernel (no cache)."""
    m = LS._SITE_ROW_PATH.match(q)
    ip, j, name = int(m.group(1)), int(m.group(2)), m.group(3)
    if name in ("x", "y", "z"):
        e = np.zeros(3)
        e[("x", "y", "z").index(name)] = 1.0
        dint = model.coordinate_intensity_grad(ip, j, e, values)
    elif name in ("biso", "occ"):
        grads = model.structural_f2_grads(
            ip, values, biso_atoms=(j,) if name == "biso" else (),
            occ_atoms=(j,) if name == "occ" else ())
        dint = model.site_intensity_grad(
            ip, (grads[2] if name == "biso" else grads[3])[j], values)
    else:
        e = np.zeros(6)
        e[("u11", "u22", "u33", "u12", "u13", "u23").index(name)] = 1.0
        dint = model.adp_intensity_grad(ip, j, e, values)
    pp = bases.planes[ip]
    coef = np.where(pp.finite, LS._gather_per_line(pp.layout, dint), 0.0)
    return accumulate_planes(len(model.tt), [(pp.layout, [(coef, pp.omega)])])


def _chain_rule(model, table, theta, c: int) -> np.ndarray:
    """Σ_q ∂p_q/∂θ_c · ∂y/∂p_q over the column's site rows, as a residual
    column (the Jacobian's sign and weights)."""
    values = table.decode(theta)
    bases = model.derivative_bases(values, None)
    lj = table.local_jacobian(np.asarray(theta, dtype=np.float64)).tocsc()
    path, extra, _own = LS._column_identities(table, LS._column_extras(table))[c]
    col = np.zeros(len(model.tt))
    for q in (path, *extra):
        if LS._SITE_ROW_PATH.match(q) and (w := float(lj[table._paths[q], c])):
            col += w * _row_column(model, values, bases, q)
    return -col / model.sigma


def _richardson(residual, theta, c: int, h: float) -> np.ndarray:
    def central(step):
        up, down = theta.copy(), theta.copy()
        up[c] += step
        down[c] -= step
        return (residual(up) - residual(down)) / (2.0 * step)

    return (4.0 * central(h / 2) - central(h)) / 3.0


@pytest.mark.parametrize("dispersion", [True, False], ids=["dispersion", "none"])
@pytest.mark.parametrize("extinction", [0.0, 30.0], ids=["no-ext", "ext"])
def test_a_cross_atom_column_is_the_chain_rule_over_the_cache(
        dispersion, extinction, monkeypatch):
    """Every column of the tied state is ``_site_column``'s, and each equals
    the chain rule over single-atom kernels to rounding: 1e-12 of the
    column's norm, against 1.9e-16 measured on darwin/arm64.  Extinction at
    30 makes the chain's G = E + x·dE/dx factor live.  The co-sited tie, the
    coordinate-plus-ADP variable and the Biso-plus-occupancy variable are all
    here, so the three dispatch claims new to angle 4 are each exercised."""
    model, table = cross_atom_state(dispersion=dispersion, extinction=extinction)
    assert table.free_paths == [*C_DOFS, f"{VAR_PREFIX}D", f"{VAR_PREFIX}S"]
    seen = _claimed(monkeypatch)
    theta = _theta(table)
    J = _make_jacobian(model, table)(theta)
    assert sorted(seen) == list(range(len(theta)))
    for c, path in enumerate(table.free_paths):
        want = _chain_rule(model, table, theta, c)
        assert np.linalg.norm(want) > 0.0, path
        assert (np.linalg.norm(J[:len(want), c] - want)
                <= 1e-12 * np.linalg.norm(want)), path


def test_a_cross_atom_column_meets_the_converged_difference():
    """The whole column against the model: a Richardson-extrapolated central
    difference of the residual at h = 1e-3.  The bar, 1e-7 of the column's
    norm, is 44 times the 2.3e-9 measured on darwin/arm64 over these five
    columns, the extrapolation's own truncation."""
    model, table = cross_atom_state(extinction=30.0)
    theta = _theta(table)
    J = _make_jacobian(model, table)(theta)
    residual = _make_residual(model, table)
    for c, path in enumerate(table.free_paths):
        want = _richardson(residual, theta, c, 1e-3)
        assert np.linalg.norm(J[:, c] - want) <= 1e-7 * np.linalg.norm(want), path


def test_a_tied_column_is_the_sum_of_its_untied_columns():
    """At equal parameter values, C's tied DOF column is C's untied column
    plus N's: the tie's coefficients are both 1, so the identity is exact and
    the bar is rounding, 1e-12 of the norm (1.7e-16 measured on
    darwin/arm64)."""
    tied_model, tied = cross_atom_state(ties=True)
    free_model, free = cross_atom_state(ties=False)
    theta_t = _theta(tied)
    values = tied.decode(theta_t)
    theta_f = np.array([values[p] for p in free.free_paths])
    Jt = _make_jacobian(tied_model, tied)(theta_t)
    Jf = _make_jacobian(free_model, free)(theta_f)
    for k in range(3):
        want = (Jf[:, free.free_paths.index(C_DOFS[k])]
                + Jf[:, free.free_paths.index(f"phases.0.atoms.3.dof.{k}")])
        got = Jt[:, tied.free_paths.index(C_DOFS[k])]
        assert np.linalg.norm(got - want) <= 1e-12 * np.linalg.norm(want), k


def test_a_mode_column_is_the_chain_rule_over_the_cache(monkeypatch):
    """A distortion-mode amplitude reaches its atoms' coordinates through C.
    It is ``_site_column``'s, equals the chain rule over single-atom kernels
    to 1e-12 of its norm (1.1e-15 measured on darwin/arm64), and meets a
    Richardson-extrapolated difference to 1e-7 of its norm (9.6e-12
    measured)."""
    from tests.test_cross_backend import CONFIGS

    model, table, _ = CONFIGS["distortion_modes"]()
    seen = _claimed(monkeypatch)
    theta = table.x0()
    J = _make_jacobian(model, table)(theta)
    residual = _make_residual(model, table)
    c = table.free_paths.index("phases.0.distortion_modes.modes.0.amplitude")
    assert c in seen
    want = _chain_rule(model, table, theta, c)
    assert np.linalg.norm(J[:, c] - want) <= 1e-12 * np.linalg.norm(want)
    fd = _richardson(residual, theta, c, 1e-3)
    assert np.linalg.norm(J[:, c] - fd) <= 1e-7 * np.linalg.norm(fd)


@pytest.mark.parametrize("state", ["bodies", "toy_body", "bodies_site"])
def test_a_body_column_keeps_the_peak_chain(state, monkeypatch):
    """A rigid body's columns are declined by name (``_site_reach_ok``'s
    docstring has the measurement): the block's partials carry 1e-17
    residues where the truth is zero, which an analytic sum turns into a
    live column the covariance cannot tell from a measured one."""
    from tests.test_cross_backend import CONFIGS

    model, table, _ = CONFIGS[state]()
    seen = _claimed(monkeypatch)
    _make_jacobian(model, table)(table.x0())
    assert not any(".rigid_bodies." in table.free_paths[c] for c in seen)
    assert any(".rigid_bodies." in p for p in table.free_paths)


def test_a_reach_past_the_site_rows_takes_the_peak_chain(monkeypatch):
    """A tie carrying a coordinate column onto a cell length moves every
    peak, which the branch cannot see.  The column is declined by its reach
    and built by the peak chain, which still meets the difference."""
    structure = _structure()
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 1e-2
    ins.source.dispersion = None
    grid = np.arange(10.0, 90.0, 0.02)
    pattern = PatternData(two_theta=grid.tolist(),
                          intensity=np.zeros_like(grid).tolist())
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    table.set_tie("phases.0.atoms.3.dof.0", AffineTie.identity(C_DOFS[0]))
    table.set_tie("phases.0.cell.c",
                  AffineTie(terms=((C_DOFS[0], 0.01),), const=7.8))
    table.refresh_ties()
    assert table.set_vary([C_DOFS[0]], True)
    table.apply_to_models(structure, ins)
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    seen = _claimed(monkeypatch)
    theta = _theta(table)
    J = _make_jacobian(model, table)(theta)
    assert seen == []
    residual = _make_residual(model, table)
    want = _richardson(residual, theta, 0, 1e-4)
    assert np.linalg.norm(J[:, 0] - want) <= 1e-4 * np.linalg.norm(want)


def _expansions_per_jacobian(monkeypatch) -> dict[str, tuple[int, int]]:
    """``_orbit_terms`` calls in one Jacobian evaluation, with the untied and
    the tied state, as ``{name: (calls, columns)}``."""
    calls = [0]
    real = SF._orbit_terms

    def counting(*a, **k):
        calls[0] += 1
        return real(*a, **k)

    monkeypatch.setattr(SF, "_orbit_terms", counting)
    counts = {}
    for name, ties in (("free", False), ("tied", True)):
        model, table = cross_atom_state(ties=ties)
        jacobian = _make_jacobian(model, table)
        theta = _theta(table)
        calls[0] = 0
        jacobian(theta)
        counts[name] = (calls[0], len(theta))
    assert [counts[k][1] for k in ("free", "tied")] == [10, 5], counts
    return counts


def test_one_expansion_serves_every_cross_atom_column(monkeypatch):
    """WP-2314's runaway guard for angle 4, the companion of the hoist's and
    the Biso columns' guards.  ``_orbit_terms`` calls per evaluation are the
    same with the five cross-atom columns as with the ten independent ones.
    On the peak chain each cross-atom column re-expanded the phase, one call
    per atom, so a return to it trips this count on every machine where a
    wall-clock budget would sense load (``tests/CLAUDE.md`` § Budgets in
    tests)."""
    counts = _expansions_per_jacobian(monkeypatch)
    assert counts["free"][0] == counts["tied"][0], counts


def test_the_count_guard_trips_on_the_peak_chain(monkeypatch):
    """The guard above is evidence only if its counter sees a return.  With
    the branch declining every column, the peak chain builds the tied ones,
    and the count grows past the untied state's."""
    real = LS._site_reach_ok
    monkeypatch.setattr(LS, "_site_reach_ok", lambda ip, path, extra: (
        real(ip, path, extra) and not extra))
    counts = _expansions_per_jacobian(monkeypatch)
    assert counts["tied"][0] > 2 * counts["free"][0], counts
