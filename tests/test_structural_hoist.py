"""WP-2314 angle 1: one structure-factor expansion serves every structural column.

Before WP-2314 each coordinate or ADP column of the analytic Jacobian called
``d_f2_d_xyz`` or ``d_f2_d_uaniso``, and each call expanded the whole phase's
structure factor to rebuild A for one atom's bracket.  The hoist builds A, B
and every atom's bracket in one pass (``structure_factor.d_f2_d_sites``),
cached for one Jacobian evaluation.  It changes no arithmetic, so its bar is
the bytes: every array, and every Jacobian column, equals the pre-change one
bit for bit.

The oracle is the two kernels as they stood at 94804b716, copied below
verbatim with their docstrings shortened.  They stay here, frozen, because the
package's own kernels are now the batched function asked for one atom, and a
test comparing that with itself would pass whatever the hoist did.
"""
from __future__ import annotations

import numpy as np
import pytest

from rietx import Instrument, PatternData
from rietx.backend import get_backend
from rietx.crystallography import structure_factor as SF
from rietx.crystallography.adp import VOIGT
from rietx.crystallography.lattice import d_spacings
from rietx.crystallography.structure_factor import (
    PhaseSites,
    _orbit_sum,
    _orbit_terms,
    d_f2_d_sites,
    transposed_rotation_indices,
)
from rietx.model.forward import CompiledModel, compile_model
from rietx.optimize.least_squares import _make_jacobian
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import Dispersion
from rietx.schemas.structure import AnisoU, Atom, Cell, Phase, Structure


def _pre_d_f2_d_xyz(
    hkl: np.ndarray,
    d: np.ndarray,
    sites: PhaseSites,
    xyz: np.ndarray,
    occ: np.ndarray,
    biso: np.ndarray,
    j: int,
    uaniso: np.ndarray | None = None,
    astar: np.ndarray | None = None,
) -> np.ndarray:
    """``d_f2_d_xyz`` as of 94804b716, before WP-2314."""
    xp = get_backend()
    stol = 1.0 / (2.0 * xp.asarray(d, dtype=np.float64))  # s = sinθ/λ = 1/(2d)
    h = xp.asarray(hkl, dtype=np.float64)
    A = xp.zeros(len(h), dtype=np.complex128)
    B = None if sites.f_anom is None else xp.zeros(len(h), dtype=np.complex128)
    dA = xp.zeros((len(h), 3), dtype=np.complex128)
    dB = None if B is None else xp.zeros((len(h), 3), dtype=np.complex128)
    for jj in range(sites.n_asym):
        amp_a, amp_b, phase, dw = _orbit_terms(
            h, stol, sites, xyz, occ, biso, uaniso, astar, jj)
        orbit = _orbit_sum(phase, dw)
        A = A + amp_a * orbit
        if B is not None:
            B = B + amp_b * orbit
        if jj == j:
            rth = transposed_rotation_indices(h, sites.ops[jj][0])  # (m, N, 3)
            weighted = phase if dw is None else phase * dw
            bracket = (weighted[:, :, None] * rth).sum(axis=0)
            dA = amp_a[:, None] * (2.0j * xp.pi) * bracket
            if dB is not None:
                dB = amp_b[:, None] * (2.0j * xp.pi) * bracket
    out = 2.0 * xp.real(xp.conj(A)[:, None] * dA)
    if B is not None:
        out = out + 2.0 * xp.real(xp.conj(B)[:, None] * dB)
    return out


def _pre_d_f2_d_uaniso(
    hkl: np.ndarray,
    d: np.ndarray,
    sites: PhaseSites,
    xyz: np.ndarray,
    occ: np.ndarray,
    biso: np.ndarray,
    j: int,
    uaniso: np.ndarray,
    astar: np.ndarray,
) -> np.ndarray:
    """``d_f2_d_uaniso`` as of 94804b716, before WP-2314."""
    xp = get_backend()
    stol = 1.0 / (2.0 * xp.asarray(d, dtype=np.float64))  # s = sinθ/λ = 1/(2d)
    h = xp.asarray(hkl, dtype=np.float64)
    s = xp.asarray(astar, dtype=np.float64)
    A = xp.zeros(len(h), dtype=np.complex128)
    B = None if sites.f_anom is None else xp.zeros(len(h), dtype=np.complex128)
    dA = np.zeros((len(h), 6), dtype=np.complex128)
    dB = None if B is None else np.zeros((len(h), 6), dtype=np.complex128)
    for jj in range(sites.n_asym):
        amp_a, amp_b, phase, dw = _orbit_terms(
            h, stol, sites, xyz, occ, biso, uaniso, astar, jj)
        orbit = _orbit_sum(phase, dw)
        A = A + amp_a * orbit
        if B is not None:
            B = B + amp_b * orbit
        if jj == j:
            if dw is None:
                raise ValueError(f"atom {j} is isotropic: no U^ij to differentiate")
            q = transposed_rotation_indices(h, sites.ops[jj][0])  # (m, N, 3)
            for v, (c, e) in enumerate(VOIGT):
                fold = 1.0 if c == e else 2.0
                de = (-2.0 * xp.pi ** 2 * fold * s[c] * s[e]) * q[:, :, c] * q[:, :, e]
                bracket = (phase * dw * de).sum(axis=0)
                dA[:, v] = amp_a * bracket
                if dB is not None:
                    dB[:, v] = amp_b * bracket
    out = 2.0 * xp.real(xp.conj(A)[:, None] * dA)
    if B is not None:
        out = out + 2.0 * xp.real(xp.conj(B)[:, None] * dB)
    return out


# ----------------------------------------------------------------------
# the fixture: general and special sites, isotropic and anisotropic atoms
# ----------------------------------------------------------------------
def _atom(label, species, xyz, aniso=None) -> Atom:
    x, y, z = xyz
    return Atom(label=label, species=species, x=Parameter(value=x),
                y=Parameter(value=y), z=Parameter(value=z),
                biso=Parameter(value=0.6), aniso=aniso)


def _structure() -> Structure:
    """P2₁/c: Fe anisotropic on the 2a centre (no coordinate DOF, six ADP
    DOFs), and three general atoms, one of them anisotropic too."""
    return Structure(phases=[Phase(
        name="toy", space_group="P21/c",
        cell=Cell(a=Parameter(value=5.2), b=Parameter(value=6.4),
                  c=Parameter(value=7.8), alpha=Parameter(value=90.0),
                  beta=Parameter(value=105.0), gamma=Parameter(value=90.0)),
        scale=Parameter(value=1e-3),
        atoms=[
            _atom("Fe", "Fe", (0.0, 0.0, 0.0), AnisoU.from_values(
                (0.010, 0.012, 0.009, 0.001, 0.002, -0.001))),
            _atom("C", "C", (0.23, 0.31, 0.42)),
            _atom("O", "O", (0.61, 0.18, 0.77), AnisoU.from_values(
                (0.014, 0.011, 0.016, 0.002, -0.001, 0.003))),
            _atom("N", "N", (0.12, 0.66, 0.29)),
        ])])


def _model_and_table(dispersion: bool, free=("phases.0.atoms.*.dof.*",
                                             "phases.0.atoms.*.adp.*",
                                             "phases.0.scale")):
    structure = _structure()
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 1e-2
    # declared both ways: B is the anomalous half every bracket carries
    ins.source.dispersion = Dispersion() if dispersion else None
    grid = np.arange(10.0, 90.0, 0.02)
    pattern = PatternData(two_theta=grid.tolist(),
                          intensity=np.zeros_like(grid).tolist())
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    for glob in free:
        assert table.set_vary([glob], True), glob
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
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


def _pre_change_grads(self, ip, values, xyz_atoms=(), u_atoms=()):
    """``CompiledModel.structural_f2_grads`` built the pre-change way, one
    whole expansion per atom."""
    assert ip == 0
    hkl, d, sites, xyz, occ, biso, uaniso, astar = _kernel_args(self, values)
    return ({j: _pre_d_f2_d_xyz(hkl, d, sites, xyz, occ, biso, j, uaniso, astar)
             for j in xyz_atoms},
            {j: _pre_d_f2_d_uaniso(hkl, d, sites, xyz, occ, biso, j, uaniso, astar)
             for j in u_atoms})


@pytest.mark.parametrize("dispersion", [True, False], ids=["dispersion", "none"])
def test_every_atoms_gradient_is_the_pre_change_kernels_bytes(dispersion):
    model, table = _model_and_table(dispersion)
    values = table.decode(_theta(table))
    hkl, d, sites, xyz, occ, biso, uaniso, astar = _kernel_args(model, values)
    assert (sites.f_anom is not None) is dispersion
    atoms = range(sites.n_asym)
    aniso = [j for j in atoms if sites.aniso[j]]
    assert aniso == [0, 2]
    g_xyz, g_u = d_f2_d_sites(hkl, d, sites, xyz, occ, biso, uaniso, astar,
                              xyz_atoms=atoms, u_atoms=aniso)
    for j in atoms:
        want = _pre_d_f2_d_xyz(hkl, d, sites, xyz, occ, biso, j, uaniso, astar)
        assert np.any(want != 0.0)
        assert g_xyz[j].tobytes() == want.tobytes(), j
        assert SF.d_f2_d_xyz(hkl, d, sites, xyz, occ, biso, j, uaniso, astar
                             ).tobytes() == want.tobytes(), j
    for j in aniso:
        want = _pre_d_f2_d_uaniso(hkl, d, sites, xyz, occ, biso, j, uaniso, astar)
        assert np.any(want != 0.0)
        assert g_u[j].tobytes() == want.tobytes(), j
        assert SF.d_f2_d_uaniso(hkl, d, sites, xyz, occ, biso, j, uaniso, astar
                                ).tobytes() == want.tobytes(), j
    with pytest.raises(ValueError, match="isotropic"):
        d_f2_d_sites(hkl, d, sites, xyz, occ, biso, uaniso, astar, u_atoms=[1])


@pytest.mark.parametrize("dispersion", [True, False], ids=["dispersion", "none"])
def test_the_jacobian_is_byte_equal_to_the_pre_change_columns(dispersion, monkeypatch):
    """Every column of one analytic Jacobian evaluation, structural or not."""
    model, table = _model_and_table(dispersion)
    theta = _theta(table)
    hoisted = _make_jacobian(model, table)(theta)
    structural = [c for c, p in enumerate(table.free_paths)
                  if ".dof." in p or ".adp." in p]
    assert len(structural) == 3 * 3 + 2 * 6
    assert all(np.any(hoisted[:, c] != 0.0) for c in structural)
    monkeypatch.setattr(CompiledModel, "structural_f2_grads", _pre_change_grads)
    before = _make_jacobian(model, table)(theta)
    assert hoisted.tobytes() == before.tobytes()


def test_one_expansion_serves_every_structural_column(monkeypatch):
    """The cost shape the hoist buys.  ``_orbit_terms`` calls per evaluation
    do not grow with the number of structural columns; before WP-2314 each
    column added one call per atom."""
    calls = [0]
    real = SF._orbit_terms

    def counting(*a, **k):
        calls[0] += 1
        return real(*a, **k)

    monkeypatch.setattr(SF, "_orbit_terms", counting)
    counts = {}
    for name, free in (("one", ("phases.0.atoms.1.dof.0",)),
                       ("all", ("phases.0.atoms.*.dof.*", "phases.0.atoms.*.adp.*"))):
        model, table = _model_and_table(True, free)
        jacobian = _make_jacobian(model, table)
        theta = _theta(table)
        calls[0] = 0
        jacobian(theta)
        counts[name] = (calls[0], len(theta))
    assert counts["one"][1] == 1 and counts["all"][1] == 21
    assert counts["all"][0] == counts["one"][0], counts
