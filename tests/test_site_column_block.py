"""WP-2314 angle 2: the site columns go onto the pattern as one block per phase.

Every coordinate, ADP, Biso and occupancy column of a Rietveld Jacobian moves
only |F_N|², so each is its ∂|F_N|² chained through the same intensity
factors (scale, multiplicity, preferred orientation, Lorentz-polarisation,
extinction, absorption, roughness, per emission line) and laid onto the
pattern.  Before angle 2 each column rebuilt those factors.  Now one
(N, K) block goes through the chain per phase per Jacobian
(``least_squares._site_columns``).  It changes no arithmetic: each column
meets the same multiplies in the same order, so the bar is the bytes.

The oracle is the per-column builder as it stood at cd4a461f1, copied below
with its docstring shortened, since the package's chain now serves both
shapes and a test comparing it with itself would pass whatever it did.
"""
from __future__ import annotations

import numpy as np
import pytest

from rietx import Instrument, PatternData
from rietx.crystallography.lattice import d_spacings
from rietx.model import compiled
from rietx.model.forward import CompiledModel, accumulate_planes, compile_model
from rietx.optimize import least_squares as LS
from rietx.params.vector import AffineTie, ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import Dispersion, RoughnessSuortti
from rietx.schemas.structure import PreferredOrientation
from tests.test_biso_occ_columns import _structure


@pytest.fixture(autouse=True)
def _numpy_path():
    """Bit-identity, so the path is declared, never inherited
    (``tests/CLAUDE.md`` § Quoting numbers)."""
    was = compiled.set_enabled(False)
    try:
        yield
    finally:
        compiled.set_enabled(was)


#: every site column the fixture frees: the general atoms' coordinate DOFs,
#: the anisotropic atoms' ADP DOFs, the isotropic Biso and the occupancies
FREE = ("phases.0.atoms.*.dof.*", "phases.0.atoms.*.adp.*",
        "phases.0.atoms.1.biso", "phases.0.atoms.3.biso",
        "phases.0.atoms.*.occ", "phases.0.scale")


def _state(*, ties: bool, corrections: bool):
    """``(model, table)`` on ``test_biso_occ_columns``' P2₁/c phase.

    ``corrections`` puts every factor of the intensity chain on: a Kα
    doublet, a finite-thickness flat plate, Suortti roughness, a
    March-Dollase axis and extinction off zero.  ``ties`` makes N's
    coordinates follow C's and N's occupancy the remainder of C's, so the
    columns cross atoms and take the site branch rather than the
    one-atom one.
    """
    structure = _structure(1.5 if corrections else 0.0)
    if corrections:
        ins = Instrument.bragg_brentano(radiation="CuKa", mu_t=0.4, thickness_mm=0.2)
        ins.geometry.surface_roughness = RoughnessSuortti(
            a=Parameter(value=0.9), b=Parameter(value=0.3))
        structure.phases[0].preferred_orientation = PreferredOrientation(
            axis=(0, 0, 1), r=Parameter(value=0.85))
    else:
        ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 1e-2
    ins.source.dispersion = Dispersion()
    grid = np.arange(10.0, 90.0, 0.02)
    pattern = PatternData(two_theta=grid.tolist(),
                          intensity=np.zeros_like(grid).tolist())
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    for glob in FREE:
        assert table.set_vary([glob], True), glob
    if ties:
        for k in range(3):
            table.set_tie(f"phases.0.atoms.3.dof.{k}",
                          AffineTie.identity(f"phases.0.atoms.1.dof.{k}"))
        table.set_tie("phases.0.atoms.3.occ", AffineTie(
            terms=(("phases.0.atoms.1.occ", -1.0),), const=1.0))
        table.refresh_ties()
    table.apply_to_models(structure, ins)
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    if corrections:
        assert len(model.line_lambdas(table.decode(table.x0()))) == 2
        assert not model.phases[0].skip_extinction
    return model, table


def _theta(table):
    """x0 moved off its stored values, so no column sits at a special point."""
    theta = table.x0()
    return theta + 1e-3 * np.cos(np.arange(len(theta)))


def _pre_change_site_columns(model, bases, values, ip, df2s):
    """``_site_columns`` built the pre-change way: the chain, the gather and
    the accumulation once per column, as ``_structural_column`` and
    ``_site_column`` did at cd4a461f1."""
    out = []
    for df2 in df2s:
        if df2 is None:
            out.append(np.zeros(len(model.tt)))
            continue
        dint = model.site_intensity_grad(ip, df2, values)
        pp = bases.planes[ip]
        coef = np.where(pp.finite, LS._gather_per_line(pp.layout, dint), 0.0)
        terms = [(coef, pp.omega)] if np.any(coef != 0.0) else []
        out.append(accumulate_planes(len(model.tt), [(pp.layout, terms)]))
    return out


def _site_branch_columns(model, table, monkeypatch) -> list[int]:
    """The columns the two site branches send to ``_site_columns``."""
    seen: list[int] = []
    real = LS._site_columns

    def record(model_, bases, values, ip, df2s):
        seen.append(len(df2s))
        return real(model_, bases, values, ip, df2s)

    monkeypatch.setattr(LS, "_site_columns", record)
    LS._make_jacobian(model, table)(_theta(table))
    monkeypatch.setattr(LS, "_site_columns", real)
    return seen


@pytest.mark.parametrize("corrections", [True, False], ids=["corrections", "plain"])
@pytest.mark.parametrize("ties", [True, False], ids=["tied", "untied"])
def test_the_jacobian_is_byte_equal_to_the_per_column_build(ties, corrections,
                                                            monkeypatch):
    """Every column of one Jacobian evaluation, site columns or not."""
    model, table = _state(ties=ties, corrections=corrections)
    n_site = sum(1 for p in table.free_paths if ".atoms." in p)
    assert _site_branch_columns(model, table, monkeypatch) == [n_site]
    theta = _theta(table)
    block = LS._make_jacobian(model, table)(theta)
    assert all(np.any(block[:, c] != 0.0) for c in range(len(theta)))
    monkeypatch.setattr(LS, "_site_columns", _pre_change_site_columns)
    before = LS._make_jacobian(model, table)(theta)
    assert block.tobytes() == before.tobytes()


def test_a_block_through_the_chain_is_each_column_alone():
    """``_f2_derivative_chain`` on (N, K) against K one-column calls, with
    every factor on.  This is the arithmetic claim the Jacobian test rests
    on, asserted where it is made."""
    model, table = _state(ties=False, corrections=True)
    values = table.decode(_theta(table))
    cell = tuple(values[f"phases.0.cell.{k}"]
                 for k in ("a", "b", "c", "alpha", "beta", "gamma"))
    d = d_spacings(model.phases[0].reflections.index, *cell)
    rng = np.random.default_rng(2314)
    block = rng.standard_normal((len(d), 5))
    together = model._f2_derivative_chain(0, values, cell, d, block)
    assert len(together) == 2
    for k in range(block.shape[1]):
        alone = model._f2_derivative_chain(0, values, cell, d, block[:, k].copy())
        for il in range(2):
            assert together[il][:, k].tobytes() == alone[il].tobytes(), (k, il)


def _chains_per_jacobian(monkeypatch, *, per_column: bool) -> int:
    calls = [0]
    real = CompiledModel._f2_derivative_chain

    def counting(self, *a, **k):
        calls[0] += 1
        return real(self, *a, **k)

    monkeypatch.setattr(CompiledModel, "_f2_derivative_chain", counting)
    if per_column:
        monkeypatch.setattr(LS, "_site_columns", _pre_change_site_columns)
    model, table = _state(ties=True, corrections=False)
    LS._make_jacobian(model, table)(_theta(table))
    return calls[0]


def test_one_chain_serves_every_site_column(monkeypatch):
    """The cost shape angle 2 buys, and its runaway guard in place of a
    wall-clock budget (``tests/CLAUDE.md`` § Budgets in tests): one pass
    through the intensity chain per phase per Jacobian, whatever the number
    of site columns."""
    assert _chains_per_jacobian(monkeypatch, per_column=False) == 1


def test_the_chain_guard_trips_on_a_chain_per_column(monkeypatch):
    """The guard is evidence only if its counter sees a return to the
    per-column build."""
    assert _chains_per_jacobian(monkeypatch, per_column=True) > 10
