"""WP-0401 backend-shim bit-identity goldens.

The op-shim routing and purity refactors (WP-0401) must not change a single
computed number on the numpy path.  This file freezes that claim: each state
below is compiled, evaluated and differentiated exactly as the solver does,
and compared **bit-for-bit** (``np.array_equal``) against golden arrays
captured from the pre-shim tree.

States (chosen to cover every refactored code path):

* ``srm660c`` — real lab data, Bragg-Brentano + Kα doublet + FCJ + Chebyshev
  background; displacement/transparency/extinction free *at their 0 off-values*
  (gates the unconditional-evaluation refactor's exact identities).
* ``nac`` — real synchrotron data, two phases, coordinate DOF columns.
* ``toy_lebail`` — Le Bail partitioning (3 cycles) + P-spline penalty rows.
* ``toy_pawley`` — Pawley intensity block: aux Jacobian columns + overlap
  restraint rows.
* ``toy_rich`` — aniso ADPs + March-Dollase + extinction + displacement/
  transparency/zero all *on* (nonzero), unequal axial S/L ≠ H/L.
* ``toy_restraints`` — Rietveld rutile with bond, angle and value soft-restraint
  rows (WP-0406): the nonlinear penalty stripe below the data rows, its residual
  and analytic Jacobian columns locked for the cross-backend CI (WP-0404).
* ``toy_roughness`` — Bragg-Brentano rutile with Suortti surface roughness on
  (WP-0502): an exp of a reciprocal sin, folded into all three intensity
  assemblies (phase_peaks plus both analytic column builders).

Golden bit patterns are environment-pinned (they depend on the numpy/BLAS
build); they live in ``tests/data/backend_goldens/`` and are documented in
``tests/data/README.md``.  If the environment shifts, re-baseline **from a
tree that passes the full suite**, never from a mid-refactor tree:

    .venv/bin/python -m tests.test_backend_shim
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import pxrdref as pr
from pxrdref.model.forward import compile_model
from pxrdref.optimize.least_squares import _make_jacobian, _make_residual
from pxrdref.params.vector import ParameterTable
from pxrdref.schemas.instrument import (
    BackgroundChebyshev,
    BackgroundPSpline,
    Instrument,
    RoughnessSuortti,
)
from pxrdref.schemas.pattern import PatternData
from pxrdref.schemas.structure import PreferredOrientation

DATA = Path(__file__).parent / "data"
GOLDEN_DIR = DATA / "backend_goldens"


# ----------------------------------------------------------------------
# state builders — deterministic (model, table, extras) triples
# ----------------------------------------------------------------------
def _free(table: ParameterTable, patterns: list[str]) -> None:
    table.set_vary(["*"], False)
    for pat in patterns:
        assert table.set_vary([pat], True), f"nothing freed by {pat!r}"


def _state_srm660c():
    path = DATA / "nist_srm660c_100a.cif"
    if not path.exists():
        return None
    data = pr.read_pdcif(path, block="_meas")
    structure = pr.Structure(phases=[pr.Phase(
        name="LaB6", space_group="P m -3 m", cell=pr.Cell.cubic(4.1568),
        atoms=[
            pr.Atom(label="La", species="La", x=pr.Parameter(value=0.0),
                    y=pr.Parameter(value=0.0), z=pr.Parameter(value=0.0),
                    biso=pr.Parameter(value=0.355, min=0.0, max=25.0)),
            pr.Atom(label="B", species="B", x=pr.Parameter(value=0.198),
                    y=pr.Parameter(value=0.5), z=pr.Parameter(value=0.5),
                    biso=pr.Parameter(value=0.276, min=0.0, max=25.0)),
        ],
        scale=pr.Parameter(value=1e-4, min=0.0, transform="softplus"),
    )])
    instrument = pr.Instrument.bragg_brentano(monochromator_two_theta=26.6)
    instrument.profile.w.value = 2e-3
    instrument.profile.x.value = 5e-3
    instrument.geometry.axial_sl.value = 0.025
    instrument.geometry.axial_hl.value = 0.025
    instrument.background = BackgroundChebyshev.with_terms(6)

    table = ParameterTable(structure, instrument)
    # displacement, transparency and extinction free at their 0.0 off-values:
    # the FD Jacobian steps them on, so the exact-identity claim is exercised
    _free(table, [
        "phases.0.scale", "instrument.background.*",
        "instrument.geometry.sample_displacement",
        "instrument.geometry.sample_transparency",
        "instrument.zero_shift", "phases.0.cell.a",
        "instrument.profile.u", "instrument.profile.v", "instrument.profile.w",
        "instrument.profile.x", "instrument.profile.y",
        "instrument.source.lines.1.weight",
        "instrument.geometry.axial_sl", "instrument.geometry.axial_hl",
        "phases.0.atoms.*.biso", "phases.0.extinction",
    ])
    model = compile_model(structure, instrument, data, mode="rietveld",
                          free_paths=set(table.free_paths))
    return model, table, {}


def _caf2_phase() -> pr.Phase:
    return pr.Phase(
        name="CaF2", space_group="F m -3 m", cell=pr.Cell.cubic(5.4631),
        atoms=[
            pr.Atom(label="Ca", species="Ca2+", x=pr.Parameter(value=0.0),
                    y=pr.Parameter(value=0.0), z=pr.Parameter(value=0.0),
                    biso=pr.Parameter(value=0.6, min=0.0, max=25.0)),
            pr.Atom(label="F", species="F1-", x=pr.Parameter(value=0.25),
                    y=pr.Parameter(value=0.25), z=pr.Parameter(value=0.25),
                    biso=pr.Parameter(value=0.9, min=0.0, max=25.0)),
        ],
        scale=pr.Parameter(value=1e-7, min=0.0, transform="softplus"),
    )


def _state_nac():
    if not (DATA / "11BM_NAC.fxye").exists():
        return None
    data = pr.read_pattern(DATA / "11BM_NAC.fxye")
    structure = pr.Structure.from_cif(str(DATA / "cod_1000236.cif"))
    structure.phases[0].scale.value = 1e-6
    structure.phases.append(_caf2_phase())
    instrument = Instrument.debye_scherrer(wavelength=0.4139090)
    instrument.profile.w.value = 2e-5
    instrument.profile.x.value = 2e-3
    instrument.background = BackgroundChebyshev.with_terms(6)

    table = ParameterTable(structure, instrument)
    _free(table, [
        "phases.*.scale", "instrument.background.*",
        "phases.0.cell.a", "phases.1.cell.a", "instrument.zero_shift",
        "instrument.profile.w", "instrument.profile.x",
        "phases.0.atoms.*.dof.*",
        "phases.0.atoms.0.biso", "phases.1.atoms.0.biso",
    ])
    model = compile_model(structure, instrument, data, mode="rietveld",
                          two_theta_limits=(2.0, 24.0),
                          free_paths=set(table.free_paths))
    return model, table, {}


def _toy_base(*, c_near_a: bool = False) -> tuple[pr.Structure, Instrument, PatternData]:
    """Deterministic rutile toy: y_obs from a perturbed copy of the model.

    ``c_near_a`` squeezes the tetragonal cell pseudo-cubic so (hkl)/(lkh)
    partners nearly coincide — that is what puts overlapped groups (and hence
    restraint rows) into the Pawley state.
    """
    from tests.test_coordinates import make_rutile

    structure = make_rutile()
    structure.phases[0].scale.value = 8.0e-3
    if c_near_a:
        structure.phases[0].cell.c.value = 4.5910
    instrument = Instrument.debye_scherrer(wavelength=1.5406)
    instrument.profile.w.value = 8e-3
    grid = np.arange(15.0, 80.0, 0.02)
    empty = PatternData(two_theta=grid.tolist(),
                        intensity=np.zeros_like(grid).tolist())
    sim_structure = structure.model_copy(deep=True)
    sim_structure.phases[0].cell.a.value += 0.005
    sim_structure.phases[0].cell.c.value -= 0.004
    sim_structure.phases[0].scale.value = 9.2e-3
    sim = compile_model(sim_structure, instrument, empty, mode="rietveld")
    sim_table = ParameterTable(sim_structure, instrument)
    y = sim.evaluate(sim_table.decode(sim_table.x0())) + 30.0
    pattern = PatternData(two_theta=sim.tt.tolist(), intensity=y.tolist())
    return structure, instrument, pattern


_TOY_WHOLE_PATTERN_FREE = [
    "phases.0.cell.a", "phases.0.cell.c", "instrument.zero_shift",
    "instrument.profile.w", "instrument.background.*",
]


def _state_toy_lebail():
    structure, instrument, pattern = _toy_base()
    instrument.background = BackgroundPSpline.for_range(15.0, 80.0)
    table = ParameterTable(structure, instrument)
    _free(table, _TOY_WHOLE_PATTERN_FREE)
    model = compile_model(structure, instrument, pattern, mode="lebail",
                          free_paths=set(table.free_paths))
    model.lebail_update(table.decode(table.x0()), n_cycles=3)
    intens = np.concatenate([cp.hkl_intensity for cp in model.phases])
    return model, table, {"lebail_intensity": intens}


def _state_toy_pawley():
    structure, instrument, pattern = _toy_base(c_near_a=True)
    instrument.background = BackgroundChebyshev.with_terms(4)
    table = ParameterTable(structure, instrument)
    _free(table, _TOY_WHOLE_PATTERN_FREE)
    model = compile_model(structure, instrument, pattern, mode="pawley",
                          free_paths=set(table.free_paths))
    # mirror the staged runner's seeding: one Le Bail partition, then the
    # equal-split restraint on the seeded scale
    model.lebail_update(table.decode(table.x0()), n_cycles=3)
    model.build_pawley_restraint()
    return model, table, {"pawley_x0": model.pawley_x0()}


def _state_toy_rich():
    """Every optional intensity physics ON and nonzero at the expansion point."""
    from tests.test_aniso_adp import make_aniso_rutile

    structure = make_aniso_rutile()
    phase = structure.phases[0]
    phase.scale.value = 8.0e-3
    phase.extinction.value = 3e-4
    phase.preferred_orientation = PreferredOrientation(axis=(0, 0, 1))
    phase.preferred_orientation.r.value = 0.85
    instrument = Instrument.bragg_brentano(monochromator_two_theta=26.6)
    instrument.profile.w.value = 8e-3
    instrument.profile.x.value = 5e-3
    instrument.zero_shift.value = 0.01
    instrument.geometry.sample_displacement.value = -0.08
    instrument.geometry.sample_transparency.value = 0.005
    instrument.geometry.axial_sl.value = 0.03
    instrument.geometry.axial_hl.value = 0.02

    grid = np.arange(15.0, 80.0, 0.02)
    empty = PatternData(two_theta=grid.tolist(),
                        intensity=np.zeros_like(grid).tolist())
    sim_structure = structure.model_copy(deep=True)
    sim_structure.phases[0].cell.a.value = 4.5987
    sim_structure.phases[0].preferred_orientation.r.value = 0.9
    sim = compile_model(sim_structure, instrument, empty, mode="rietveld")
    sim_table = ParameterTable(sim_structure, instrument)
    y = sim.evaluate(sim_table.decode(sim_table.x0())) + 20.0
    pattern = PatternData(two_theta=sim.tt.tolist(), intensity=y.tolist())

    table = ParameterTable(structure, instrument)
    _free(table, [
        "phases.0.scale", "phases.0.cell.a", "phases.0.cell.c",
        "phases.0.atoms.*.dof.*", "phases.0.atoms.*.adp.*",
        "phases.0.preferred_orientation.r", "phases.0.extinction",
        "instrument.zero_shift",
        "instrument.geometry.sample_displacement",
        "instrument.geometry.sample_transparency",
        "instrument.profile.u", "instrument.profile.v", "instrument.profile.w",
        "instrument.profile.x", "instrument.profile.y",
        "instrument.geometry.axial_sl", "instrument.geometry.axial_hl",
        "instrument.source.lines.1.weight", "instrument.background.*",
    ])
    model = compile_model(structure, instrument, pattern, mode="rietveld",
                          free_paths=set(table.free_paths))
    return model, table, {}


def _state_toy_restraints():
    """Rietveld rutile carrying bond, angle and value soft-restraint rows.

    Locks the WP-0406 restraint stripe under the bit-identity gate: the rows are
    nonlinear in the coordinates and cell, so their residual and analytic
    Jacobian columns are the new surface a backend could drift on.  The angle
    names explicit orbit ops so the two O neighbours of Ti form a non-degenerate
    angle (auto min-image would pick the same image for both).
    """
    from pxrdref.schemas.structure import (
        AngleRestraint,
        BondRestraint,
        ValueRestraint,
    )

    structure, instrument, pattern = _toy_base()
    structure.phases[0].atoms[1].x.vary = True  # free the O coordinate DOF
    structure.phases[0].restraints = [
        BondRestraint(atom_i=0, atom_j=1, target=1.95, sigma=0.01),
        AngleRestraint(atom_i=1, atom_j=0, atom_k=1, target_deg=90.0, sigma=1.5,
                       op_index_i=0, op_index_k=1),
        ValueRestraint(path="phases.0.atoms.1.occ", target=0.95, sigma=0.03),
    ]
    instrument.background = BackgroundChebyshev.with_terms(4)
    table = ParameterTable(structure, instrument)
    _free(table, [
        "phases.0.cell.a", "phases.0.cell.c", "phases.0.scale",
        "phases.0.atoms.1.dof.0", "phases.0.atoms.1.occ",
        "instrument.zero_shift", "instrument.background.*",
    ])
    model = compile_model(structure, instrument, pattern, mode="rietveld",
                          free_paths=set(table.free_paths))
    return model, table, {}


def _state_toy_roughness():
    """Rietveld rutile on a Bragg-Brentano mount carrying Suortti roughness.

    Locks the WP-0502 stripe: the correction is an ``xp.exp`` of a reciprocal
    of ``xp.sin``, evaluated per (line, reflection) and folded into three
    separate intensity assemblies (phase_peaks and the two analytic column
    builders).  A backend that got any of them subtly wrong would show up here
    before it showed up in a fit.  Bragg-Brentano because the schema refuses a
    roughness block on a capillary, so this state cannot reuse ``_toy_base``.
    """
    from tests.test_coordinates import make_rutile

    structure = make_rutile()
    structure.phases[0].scale.value = 8.0e-3
    structure.phases[0].atoms[1].x.vary = True
    instrument = Instrument.bragg_brentano()
    instrument.profile.w.value = 8e-3
    instrument.background = BackgroundChebyshev.with_terms(4)
    instrument.geometry.surface_roughness = RoughnessSuortti(
        a=pr.Parameter(value=0.45, min=0.0, max=1.0),
        b=pr.Parameter(value=0.32, min=0.0, max=5.0, transform="softplus"))
    grid = np.arange(12.0, 80.0, 0.02)
    empty = PatternData(two_theta=grid.tolist(),
                        intensity=np.zeros_like(grid).tolist())
    sim = compile_model(structure, instrument, empty, mode="rietveld")
    sim_table = ParameterTable(structure, instrument)
    y = sim.evaluate(sim_table.decode(sim_table.x0())) + 30.0
    pattern = PatternData(two_theta=sim.tt.tolist(), intensity=y.tolist())

    table = ParameterTable(structure, instrument)
    _free(table, [
        "phases.0.cell.a", "phases.0.cell.c", "phases.0.scale",
        "phases.0.atoms.1.dof.0", "phases.0.atoms.0.biso",
        "instrument.geometry.surface_roughness.*",
        "instrument.zero_shift", "instrument.background.*",
    ])
    model = compile_model(structure, instrument, pattern, mode="rietveld",
                          free_paths=set(table.free_paths))
    return model, table, {}


STATES = {
    "srm660c": _state_srm660c,
    "nac": _state_nac,
    "toy_lebail": _state_toy_lebail,
    "toy_pawley": _state_toy_pawley,
    "toy_rich": _state_toy_rich,
    "toy_restraints": _state_toy_restraints,
    "toy_roughness": _state_toy_roughness,
}


def _capture(name: str) -> dict[str, np.ndarray] | None:
    """Evaluate + residual + Jacobian arrays at the state's expansion point."""
    built = STATES[name]()
    if built is None:
        return None
    model, table, extras = built
    theta = table.x0()
    if model.pawley is not None:
        theta = np.concatenate([theta, model.pawley_x0()])
    values = table.decode(theta[:len(table.free_paths)])
    out = dict(extras)
    out["free_paths"] = np.array(table.free_paths, dtype="U")
    out["theta"] = theta
    out["y_calc"] = model.evaluate(values)
    out["residual"] = _make_residual(model, table)(theta)
    out["jacobian"] = _make_jacobian(model, table)(theta)
    return out


# ----------------------------------------------------------------------
# shim primitives
# ----------------------------------------------------------------------
def test_numpy_backend_attributes_are_numpy_functions():
    """Zero-overhead claim: the numpy backend's ops ARE the numpy callables
    (plain-function attributes must not have bound as methods)."""
    from pxrdref.backend import NumpyBackend, get_backend

    xp = get_backend()
    assert isinstance(xp, NumpyBackend)
    assert xp.exp is np.exp
    assert xp.clip is np.clip
    assert xp.einsum is np.einsum
    assert xp.linalg is np.linalg
    assert xp.pi == np.pi


def test_window_add_functional_contract():
    from pxrdref.backend import get_backend

    xp = get_backend()
    y = np.zeros(6)
    out = xp.window_add(y, 2, 5, np.array([1.0, 2.0, 3.0]))
    # callers thread the return value; the numpy impl mutates in place
    assert out is y
    assert np.array_equal(out, [0.0, 0.0, 1.0, 2.0, 3.0, 0.0])
    out = xp.window_add(out, 0, 0, np.zeros(0))  # empty frozen window is legal
    assert np.array_equal(out, [0.0, 0.0, 1.0, 2.0, 3.0, 0.0])


def test_segment_sum_matches_bincount():
    from pxrdref.backend import get_backend

    xp = get_backend()
    vals = np.array([1.0, 2.0, 4.0, 8.0, 16.0])
    seg = np.array([0, 2, 2, 0, 3])
    got = xp.segment_sum(vals, seg, 5)
    assert np.array_equal(got, np.bincount(seg, weights=vals, minlength=5))
    assert got.shape == (5,)  # n buckets even when the tail is empty


def test_set_backend_roundtrip():
    from pxrdref.backend import NumpyBackend, get_backend, set_backend

    original = get_backend()

    class _Marker(NumpyBackend):
        name = "marker"

    try:
        set_backend(_Marker())
        assert get_backend().name == "marker"
    finally:
        set_backend(original)
    assert get_backend() is original


# ----------------------------------------------------------------------
# the gate
# ----------------------------------------------------------------------
@pytest.mark.parametrize("name", [
    pytest.param("srm660c", marks=pytest.mark.slow),
    pytest.param("nac", marks=pytest.mark.slow),
    "toy_lebail",
    "toy_pawley",
    "toy_rich",
    "toy_restraints",
    "toy_roughness",
])
def test_numpy_path_bit_identical_to_golden(name):
    path = GOLDEN_DIR / f"{name}.npz"
    if not path.exists():
        pytest.skip(f"golden {path.name} not present")
    got = _capture(name)
    if got is None:
        pytest.skip(f"dataset for state {name!r} not present")
    with np.load(path) as ref:
        assert set(ref.files) == set(got), (
            f"{name}: golden keys {sorted(ref.files)} != captured {sorted(got)}")
        for key in ref.files:
            a, b = ref[key], got[key]
            assert a.shape == b.shape, f"{name}:{key} shape {a.shape} != {b.shape}"
            assert np.array_equal(a, b), (
                f"{name}:{key} diverged from the pre-shim golden "
                f"(max |Δ| = {np.max(np.abs(a - b)) if a.dtype.kind == 'f' else '?'})")


if __name__ == "__main__":
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    for name in STATES:
        got = _capture(name)
        if got is None:
            print(f"{name}: dataset missing, skipped")
            continue
        out = GOLDEN_DIR / f"{name}.npz"
        np.savez_compressed(out, **got)
        sizes = {k: v.shape for k, v in got.items()}
        print(f"{name}: wrote {out} ({out.stat().st_size / 1e6:.2f} MB) {sizes}")
