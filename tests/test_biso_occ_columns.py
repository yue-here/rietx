"""WP-2314 angle 3: the Biso and occupancy columns from the structure-factor cache.

Before angle 3 a Biso or occupancy column went to the peak chain, which
re-runs ``phase_peaks`` at a perturbed θ, so every such column re-expanded
the whole phase's structure factor.  Now ``structure_factor.d_f2_d_sites``
returns ∂|F|²/∂B_j and ∂|F|²/∂occ_j from the one expansion the coordinate
columns already share, and ``_site_scalar_column`` sums them through C.

The oracles are exact, as the root CLAUDE.md asks of a new branch.  ⟨|F|²⟩
is quadratic in occ_j, so a central difference in occupancy is exact at any
step.  It is quadratic in t_j = exp(−B_j s²) per reflection, so three
evaluations fix the quadratic and its derivative in t exactly, at any spacing.
With extinction off the pattern is linear in |F|², so a whole occupancy
column is a central difference of the residual at a 100 % step.
"""
from __future__ import annotations

import numpy as np
import pytest

from rietx import Instrument, PatternData
from rietx.crystallography import structure_factor as SF
from rietx.crystallography.lattice import d_spacings
from rietx.crystallography.structure_factor import (
    d_f2_d_sites,
    structure_factors_squared,
)
from rietx.model import compiled
from rietx.model.forward import compile_model
from rietx.optimize import least_squares as LS
from rietx.optimize.least_squares import _make_jacobian, _make_residual
from rietx.params.vector import VAR_PREFIX, AffineTie, ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import Dispersion
from rietx.schemas.structure import AnisoU, Atom, Cell, Phase, Structure

EPS = np.finfo(np.float64).eps


@pytest.fixture(autouse=True)
def _numpy_path():
    """The numpy path declared, never inherited (``tests/CLAUDE.md`` §
    Quoting numbers)."""
    was = compiled.set_enabled(False)
    try:
        yield
    finally:
        compiled.set_enabled(was)


def _atom(label, species, xyz, occ=1.0, aniso=None) -> Atom:
    x, y, z = xyz
    return Atom(label=label, species=species, x=Parameter(value=x),
                y=Parameter(value=y), z=Parameter(value=z),
                occ=Parameter(value=occ), biso=Parameter(value=0.6), aniso=aniso)


def _structure(extinction: float = 0.0) -> Structure:
    """P2₁/c, as ``test_structural_hoist``'s: Fe anisotropic on the 2a
    centre, C and N general and isotropic, O general and anisotropic.  C and
    N share an occupancy budget (0.6 + 0.4), the shape of two species on one
    site."""
    phase = Phase(
        name="toy", space_group="P21/c",
        cell=Cell(a=Parameter(value=5.2), b=Parameter(value=6.4),
                  c=Parameter(value=7.8), alpha=Parameter(value=90.0),
                  beta=Parameter(value=105.0), gamma=Parameter(value=90.0)),
        scale=Parameter(value=1e-3),
        atoms=[
            _atom("Fe", "Fe", (0.0, 0.0, 0.0), aniso=AnisoU.from_values(
                (0.010, 0.012, 0.009, 0.001, 0.002, -0.001))),
            _atom("C", "C", (0.23, 0.31, 0.42), occ=0.6),
            _atom("O", "O", (0.61, 0.18, 0.77), aniso=AnisoU.from_values(
                (0.014, 0.011, 0.016, 0.002, -0.001, 0.003))),
            _atom("N", "N", (0.12, 0.66, 0.29), occ=0.4),
        ])
    phase.extinction = extinction
    return Structure(phases=[phase])


#: every Biso and occupancy this fixture can free: Fe and O are anisotropic,
#: so their Biso is force-fixed and never a column
ISO_BISO = ("phases.0.atoms.1.biso", "phases.0.atoms.3.biso")
OCC = tuple(f"phases.0.atoms.{j}.occ" for j in range(4))


def site_scalar_state(*, dispersion: bool = True, ties: bool = True,
                      extinction: float = 0.0, free=(*ISO_BISO, *OCC),
                      extra_free=(), **compile_kw):
    """``(model, table)`` with the given Biso and occupancy rows free.

    ``ties`` declares the three shapes a Biso or occupancy column takes
    through C: N's Biso following C's (two co-sited species), N's occupancy
    the remainder of C's (coefficient −1, constant 1), and a named variable
    driving Fe's and O's occupancies at coefficients 1 and 0.5.  It is
    ``test_cross_backend``'s ``site_scalars`` state too, which passes
    ``compile_kw`` on to ``compile_model``.
    """
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
        table.add_parameter(f"{VAR_PREFIX}Q", 1.0, vary=True, lo=0.0, hi=2.0)
        table.set_tie("phases.0.atoms.3.biso",
                      AffineTie.identity("phases.0.atoms.1.biso"))
        table.set_tie("phases.0.atoms.3.occ",
                      AffineTie(terms=(("phases.0.atoms.1.occ", -1.0),), const=1.0))
        table.set_tie("phases.0.atoms.0.occ", AffineTie.identity(f"{VAR_PREFIX}Q"))
        table.set_tie("phases.0.atoms.2.occ",
                      AffineTie(terms=((f"{VAR_PREFIX}Q", 0.5),), const=0.5))
        table.refresh_ties()
    for glob in (*free, *extra_free):
        if ties and glob in ("phases.0.atoms.3.biso", "phases.0.atoms.3.occ",
                             "phases.0.atoms.0.occ", "phases.0.atoms.2.occ"):
            continue
        assert table.set_vary([glob], True), glob
    table.apply_to_models(structure, ins)
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths), **compile_kw)
    return model, table


def _theta(table):
    """x0 moved off its stored values, so no column sits at a special point."""
    theta = table.x0()
    return theta + 1e-3 * np.cos(np.arange(len(theta)))


def _kernel_args(model, values):
    cp = model.phases[0]
    cell = tuple(values[f"phases.0.cell.{k}"]
                 for k in ("a", "b", "c", "alpha", "beta", "gamma"))
    d = d_spacings(cp.reflections.index, *cell)
    xyz, occ, biso, uaniso, astar = model._site_values(0, values, cell)
    return cp.reflections.hkl, d, cp.sites, xyz, occ, biso, uaniso, astar


def _f2_at(args, *, occ=None, biso=None):
    hkl, d, sites, xyz, occ0, biso0, uaniso, astar = args
    return structure_factors_squared(hkl, d, sites, xyz,
                                     occ0 if occ is None else occ,
                                     biso0 if biso is None else biso,
                                     uaniso, astar)


@pytest.mark.parametrize("dispersion", [True, False], ids=["dispersion", "none"])
def test_the_site_scalar_gradients_meet_their_exact_oracles(dispersion):
    """Every atom's ∂|F|²/∂occ against a central difference at half its
    occupancy, and every isotropic atom's ∂|F|²/∂B against the derivative of
    the quadratic in t through B ± 1 Å².  Both oracles are exact, so the bar
    is rounding: 64 ulp of the largest |F|² over the step (measured at most
    1.5 on darwin/arm64).  An anisotropic atom's Biso moves nothing, so its
    gradient is zero."""
    model, table = site_scalar_state(dispersion=dispersion, ties=False)
    values = table.decode(_theta(table))
    args = _kernel_args(model, values)
    hkl, d, sites, xyz, occ, biso, uaniso, astar = args
    assert (sites.f_anom is not None) is dispersion
    atoms = range(sites.n_asym)
    _gx, _gu, g_b, g_o = d_f2_d_sites(hkl, d, sites, xyz, occ, biso, uaniso, astar,
                                      biso_atoms=atoms, occ_atoms=atoms)
    f2 = _f2_at(args)
    scale = float(np.max(np.abs(f2)))
    for j in atoms:
        h = 0.5 * float(occ[j])
        up, down = occ.copy(), occ.copy()
        up[j] += h
        down[j] -= h
        want = (_f2_at(args, occ=up) - _f2_at(args, occ=down)) / (2.0 * h)
        assert np.any(want != 0.0)
        assert np.max(np.abs(g_o[j] - want)) <= 64 * EPS * scale / h, j

    stol = 1.0 / (2.0 * np.asarray(d, dtype=np.float64))
    s2 = stol * stol
    delta = 1.0
    for j in atoms:
        if sites.aniso[j]:
            assert not np.any(g_b[j]), j
            moved = biso.copy()
            moved[j] += delta
            assert _f2_at(args, biso=moved).tobytes() == f2.tobytes(), j
            continue
        b0 = float(biso[j])
        fs, ts = [], []
        for b in (b0 - delta, b0, b0 + delta):
            moved = biso.copy()
            moved[j] = b
            fs.append(_f2_at(args, biso=moved))
            ts.append(np.exp(-b * s2))
        (fm, f0, fp), (tm, t0, tp) = fs, ts
        # the derivative at t0 of the quadratic through the three points
        dfdt = (fm * (t0 - tp) / ((tm - t0) * (tm - tp))
                + f0 * (2.0 * t0 - tm - tp) / ((t0 - tm) * (t0 - tp))
                + fp * (t0 - tm) / ((tp - tm) * (tp - t0)))
        want = dfdt * (-s2 * t0)
        assert np.any(want != 0.0)
        assert np.max(np.abs(g_b[j] - want)) <= 64 * EPS * scale / delta, j


def _claimed(monkeypatch) -> list[int]:
    """The columns ``_site_scalar_column`` builds, in order."""
    seen: list[int] = []
    real = LS._site_scalar_column

    def record(model, table, bases, values, c, *a, **k):
        seen.append(c)
        return real(model, table, bases, values, c, *a, **k)

    monkeypatch.setattr(LS, "_site_scalar_column", record)
    return seen


@pytest.mark.parametrize("dispersion", [True, False], ids=["dispersion", "none"])
def test_an_occupancy_column_is_exact_at_a_full_step(dispersion, monkeypatch):
    """With extinction off the pattern is linear in |F|², so it is quadratic
    in each occupancy, and in any affine combination of them.  A central
    difference of the residual at a step of the whole value is then exact,
    the bar the root CLAUDE.md sets for a branch whose model is polynomial in
    its parameter, here 64 ulp of the largest residual over the step
    (measured at most 4.1 on darwin/arm64).  Covers the remainder tie
    (coefficient −1, constant 1) and the named variable at coefficients 1 and
    0.5."""
    model, table = site_scalar_state(dispersion=dispersion, free=OCC)
    assert set(table.free_paths) == {"phases.0.atoms.1.occ", f"{VAR_PREFIX}Q"}
    seen = _claimed(monkeypatch)
    theta = _theta(table)
    J = _make_jacobian(model, table)(theta)
    assert sorted(seen) == [0, 1]
    residual = _make_residual(model, table)
    for c, path in enumerate(table.free_paths):
        h = float(theta[c])
        up, down = theta.copy(), theta.copy()
        up[c] += h
        down[c] -= h
        want = (residual(up) - residual(down)) / (2.0 * h)
        scale = float(np.max(np.abs(residual(theta))))
        assert np.max(np.abs(want)) > 1e-6 * scale, path
        assert np.max(np.abs(J[:, c] - want)) <= 64 * EPS * scale / h, path


@pytest.mark.parametrize("extinction", [0.0, 30.0], ids=["no-ext", "ext"])
def test_a_biso_column_meets_the_converged_difference(extinction, monkeypatch):
    """Biso is not polynomial in the pattern, so the whole column is held to a
    Richardson-extrapolated central difference.  Extinction at 30 makes the
    G = E + x·dE/dx factor of the chain live.  The co-sited tie puts N's Biso
    in C's column.  The bar, 1e-9 of the column's norm, is 270 times the
    3.7e-12 measured on darwin/arm64."""
    model, table = site_scalar_state(free=(*ISO_BISO, *OCC), extinction=extinction)
    assert model.phases[0].skip_extinction is (extinction == 0.0)
    seen = _claimed(monkeypatch)
    theta = _theta(table)
    J = _make_jacobian(model, table)(theta)
    assert sorted(seen) == list(range(len(table.free_paths)))
    residual = _make_residual(model, table)
    c = table.free_paths.index("phases.0.atoms.1.biso")

    def central(h):
        up, down = theta.copy(), theta.copy()
        up[c] += h
        down[c] -= h
        return (residual(up) - residual(down)) / (2.0 * h)

    h = 1e-2
    want = (4.0 * central(h / 2) - central(h)) / 3.0
    assert np.linalg.norm(J[:, c] - want) <= 1e-9 * np.linalg.norm(want)


def test_a_reach_past_biso_and_occupancy_takes_the_peak_chain(monkeypatch):
    """A tie carrying a Biso column onto a cell length moves every peak, which
    the branch cannot see.  The column is declined by its reach and built by
    the peak chain, which still meets the difference."""
    structure = _structure()
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 1e-2
    ins.source.dispersion = None
    grid = np.arange(10.0, 90.0, 0.02)
    pattern = PatternData(two_theta=grid.tolist(),
                          intensity=np.zeros_like(grid).tolist())
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    table.set_tie("phases.0.cell.c",
                  AffineTie(terms=(("phases.0.atoms.1.biso", 0.01),), const=7.794))
    table.refresh_ties()
    assert table.set_vary(["phases.0.atoms.1.biso"], True)
    table.apply_to_models(structure, ins)
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    seen = _claimed(monkeypatch)
    theta = _theta(table)
    J = _make_jacobian(model, table)(theta)
    assert seen == []
    residual = _make_residual(model, table)
    h = 1e-4
    want = (residual(theta + h) - residual(theta - h)) / (2.0 * h)
    assert np.linalg.norm(J[:, 0] - want) <= 1e-4 * np.linalg.norm(want)


def _expansions_per_jacobian(monkeypatch) -> dict[str, tuple[int, int]]:
    """``_orbit_terms`` calls in one Jacobian evaluation, with one Biso column
    free and with every Biso and occupancy column, ties included, as
    ``{name: (calls, columns)}``."""
    calls = [0]
    real = SF._orbit_terms

    def counting(*a, **k):
        calls[0] += 1
        return real(*a, **k)

    monkeypatch.setattr(SF, "_orbit_terms", counting)
    counts = {}
    for name, free, ties in (("one", ("phases.0.atoms.1.biso",), False),
                             ("all", (*ISO_BISO, *OCC), False),
                             ("tied", (*ISO_BISO, *OCC), True)):
        model, table = site_scalar_state(free=free, ties=ties)
        jacobian = _make_jacobian(model, table)
        theta = _theta(table)
        calls[0] = 0
        jacobian(theta)
        counts[name] = (calls[0], len(theta))
    assert [counts[k][1] for k in ("one", "all", "tied")] == [1, 6, 3], counts
    return counts


def test_one_expansion_serves_every_biso_and_occupancy_column(monkeypatch):
    """WP-2314's runaway guard for angle 3, the companion of
    ``test_structural_hoist.test_one_expansion_serves_every_structural_column``,
    whose fixture frees no Biso.  ``_orbit_terms`` calls per evaluation do not
    grow with the number of Biso and occupancy columns.  On the peak chain
    each such column re-expanded the phase, one call per atom, so a return to
    it trips this count on every machine where a wall-clock budget would
    sense load (``tests/CLAUDE.md`` § Budgets in tests)."""
    counts = _expansions_per_jacobian(monkeypatch)
    assert counts["all"][0] == counts["one"][0] == counts["tied"][0], counts


def test_the_count_guard_trips_on_the_peak_chain(monkeypatch):
    """The guard above is evidence only if its counter sees a return.  With
    the branch declining every column, the peak chain builds them, and the
    count grows with the free columns."""
    monkeypatch.setattr(LS, "_site_scalar_reach_ok", lambda *a, **k: False)
    counts = _expansions_per_jacobian(monkeypatch)
    assert counts["all"][0] > 2 * counts["one"][0], counts
