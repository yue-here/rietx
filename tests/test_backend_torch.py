"""WP-0408 torch backend: op contract, isolation, fp64-CPU Jacobian, MPS fp32.

Everything here needs torch (``pytest.importorskip``) except the claim the
subprocess test proves: a numpy-only *process* never imports torch.

The cross-backend *agreement matrix* deliberately does not live here — it lives
in ``tests/test_cross_backend.py``, whose ``"torch"`` and ``"torch+fp32"`` rows
this WP activates across all six configs at once (the 18 analytic families, Le
Bail with P-spline penalty rows, Pawley with its aux block and restraint rows,
the aniso/PO/extinction state, real srm660c/nac data, and the stacked
multi-histogram layout).  What is here is what that matrix cannot express: the
op-level contract, process isolation, and the two device-specific claims (fp32
columns crossing the fp64 host boundary, and an end-to-end MPS refine).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

import pxrdref as pr  # noqa: E402
from pxrdref.backend import get_backend, resolve_backend, set_backend  # noqa: E402
from pxrdref.backend.api import _OP_NAMES, NumpyBackend  # noqa: E402

OUT = Path(__file__).parent / "output"

_MPS = torch.backends.mps.is_available()
requires_mps = pytest.mark.skipif(not _MPS, reason="no Apple GPU / MPS build")


# ----------------------------------------------------------------------
# the op contract
# ----------------------------------------------------------------------
def test_every_shim_op_is_implemented():
    """The whole WP-0401 vocabulary, present and callable.

    ``_OP_NAMES`` is the shared tuple the Protocol is written from, so a new op
    added for one backend cannot silently go missing on this one.
    """
    xp = resolve_backend("torch")
    missing = [op for op in _OP_NAMES if not callable(getattr(xp, op, None))]
    assert not missing, f"TorchBackend is missing shim ops: {missing}"
    assert callable(xp.linalg.inv) and callable(xp.linalg.det)
    assert xp.pi == np.pi


def test_ops_accept_numpy_arguments_and_match_numpy():
    """torch ops take tensors only, so the backend coerces — and the coercion
    must not change any value.  This is the property the hot path relies on when
    it hands a frozen numpy constant to ``xp.*``."""
    xp, npb = resolve_backend("torch"), NumpyBackend()
    a = np.array([0.25, 1.5, 4.0])
    b = np.array([2.0, 0.5, -1.0])
    m = np.array([[4.0, 1.0], [1.0, 3.0]])
    m3 = np.array([[4.0, 1.0, -0.5], [1.0, 3.0, 0.25], [-0.5, 0.25, 2.0]])
    cases = {
        "exp": (xp.exp(a), npb.exp(a)),
        "sqrt": (xp.sqrt(a), npb.sqrt(a)),
        "log": (xp.log(a), npb.log(a)),
        "radians": (xp.radians(a), npb.radians(a)),
        "degrees": (xp.degrees(a), npb.degrees(a)),
        "sign": (xp.sign(b), npb.sign(b)),
        "power": (xp.power(a, 1.5), npb.power(a, 1.5)),
        "clip": (xp.clip(b, 0.0, 1.0), npb.clip(b, 0.0, 1.0)),
        "maximum": (xp.maximum(a, 1.0), npb.maximum(a, 1.0)),
        "minimum": (xp.minimum(a, b), npb.minimum(a, b)),
        "where": (xp.where(a > 1.0, a, 0.0), npb.where(a > 1.0, a, 0.0)),
        "matmul": (xp.matmul(m, a[:2]), npb.matmul(m, a[:2])),
        "einsum": (xp.einsum("ni,ij,nj->n", m, m, m), npb.einsum("ni,ij,nj->n", m, m, m)),
        "sum": (xp.sum(a), npb.sum(a)),
        "cumsum": (xp.cumsum(a), npb.cumsum(a)),
        "diff": (xp.diff(a), npb.diff(a)),
        "stack": (xp.stack([a, b]), npb.stack([a, b])),
        "concatenate": (xp.concatenate([a, b]), npb.concatenate([a, b])),
        "full_like": (xp.full_like(a, 2.5), npb.full_like(a, 2.5)),
        "inv": (xp.linalg.inv(m), npb.linalg.inv(m)),
        "det": (xp.linalg.det(m), npb.linalg.det(m)),
        # the 3×3 branch is the one that actually runs (metric tensors) and it is
        # a hand-written cofactor expansion, not torch.linalg.det — see
        # backend.api._TorchLinalg
        "det3": (xp.linalg.det(m3), npb.linalg.det(m3)),
        "inv3": (xp.linalg.inv(m3), npb.linalg.inv(m3)),
    }
    for name, (got, want) in cases.items():
        np.testing.assert_allclose(np.asarray(got), want, rtol=1e-12, atol=1e-14,
                                   err_msg=f"op {name}")
    assert xp.isfinite(np.array([1.0, np.inf])).tolist() == [True, False]


def test_complex_ops_match_numpy():
    """The structure factor's complex path: ``exp`` of an imaginary argument,
    ``conj``, ``real`` — and ``imag`` of a *real* array, which torch's own
    ``imag`` refuses but numpy returns as zeros."""
    xp, npb = resolve_backend("torch"), NumpyBackend()
    z = np.array([0.3 + 0.4j, -1.0 + 2.0j])
    np.testing.assert_allclose(np.asarray(xp.exp(z)), npb.exp(z), rtol=1e-12)
    np.testing.assert_allclose(np.asarray(xp.conj(z)), npb.conj(z), rtol=1e-12)
    # |F|² the way structure_factors_squared spells it — the traced F on the
    # left, which is the rule the module docstring states
    zt = xp.asarray(z)
    np.testing.assert_allclose(np.asarray(xp.real(zt * xp.conj(zt))),
                               npb.real(z * npb.conj(z)), rtol=1e-12)
    real = np.array([1.0, 2.0])
    np.testing.assert_array_equal(np.asarray(xp.imag(real)), npb.imag(real))
    assert xp.zeros(3, dtype=np.complex128).dtype == torch.complex128


def test_scatter_primitives_are_functional():
    """``window_add``/``segment_sum`` via out-of-place ``index_add``: a NEW
    tensor, input untouched (the WP-0401 contract for immutable backends)."""
    xp = resolve_backend("torch")
    y = torch.zeros(6, dtype=torch.float64)
    out = xp.window_add(y, 2, 5, np.array([1.0, 2.0, 3.0]))
    assert out is not y
    assert np.allclose(np.asarray(y), 0.0)
    assert np.allclose(np.asarray(out), [0, 0, 1, 2, 3, 0])

    vals = np.array([1.0, 2.0, 4.0, 8.0, 16.0])
    seg = np.array([0, 2, 2, 0, 3])
    got = np.asarray(xp.segment_sum(vals, seg, 5))
    np.testing.assert_array_equal(got, np.bincount(seg, weights=vals, minlength=5))


def test_dtype_is_bound_once_per_instance():
    """WP-0401's "bind once, not per op": device and dtype are fixed by the
    instance, so a ``dtype=np.float64`` request from the hot path is honoured by
    *kind* — which on MPS means fp32, the whole point of the device."""
    cpu = resolve_backend("torch")
    assert cpu.asarray(np.zeros(2), dtype=np.float64).dtype == torch.float64
    assert cpu.asarray(np.zeros(2, dtype=np.complex128)).dtype == torch.complex128
    if _MPS:
        mps = resolve_backend("torch-mps")
        assert mps.asarray(np.zeros(2), dtype=np.float64).dtype == torch.float32
        assert mps.zeros(2, dtype=np.complex128).dtype == torch.complex64
        assert mps.device.type == "mps"


def test_backends_are_cached_and_named():
    assert resolve_backend("torch") is resolve_backend("torch")
    assert resolve_backend("torch").name == "torch"
    if _MPS:
        assert resolve_backend("torch-mps") is resolve_backend("torch-mps")
        assert resolve_backend("torch-mps") is not resolve_backend("torch")
        assert resolve_backend("torch-mps").name == "torch-mps"


# ----------------------------------------------------------------------
# isolation
# ----------------------------------------------------------------------
def test_numpy_only_process_never_imports_torch():
    """torch is a ~500 MB import; a numpy-path refinement must never trigger it
    (the WP-0402 claim for jax, restated for the second optional backend)."""
    code = """
import sys
import numpy as np
import pxrdref as pr
from pxrdref.model.forward import compile_model
from pxrdref.params.vector import ParameterTable

structure = pr.Structure(phases=[pr.Phase(
    name="LaB6", space_group="P m -3 m", cell=pr.Cell.cubic(4.1568),
    atoms=[pr.Atom(label="La", species="La", x=pr.Parameter(value=0.0),
                   y=pr.Parameter(value=0.0), z=pr.Parameter(value=0.0),
                   biso=pr.Parameter(value=0.4))],
    scale=pr.Parameter(value=1e-4, min=0.0, transform="softplus"))])
instrument = pr.Instrument.debye_scherrer(wavelength=1.5406)
tt = np.arange(15.0, 60.0, 0.05)
pattern = pr.PatternData(two_theta=tt.tolist(), intensity=[50.0] * len(tt))
table = ParameterTable(structure, instrument)
model = compile_model(structure, instrument, pattern)
model.evaluate(table.decode(table.x0()))
assert "torch" not in sys.modules, "numpy-only path imported torch"
"""
    proc = subprocess.run([sys.executable, "-c", code],
                          cwd=Path(__file__).parent.parent,
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_global_backend_never_leaks():
    """The Jacobian call flips the global backend to torch and must restore it —
    otherwise a later numpy residual evaluation would silently run on tensors."""
    from pxrdref.backend.torch_backend import make_torch_jacobian
    from tests.test_backend_shim import STATES

    model, table, _ = STATES["toy_lebail"]()
    make_torch_jacobian(model, table)(table.x0())
    assert isinstance(get_backend(), NumpyBackend)


def test_frozen_state_stays_host_numpy():
    """WP-0401 gotcha (1), sharpened for a device backend: leaking tensors into
    the compiled model would put non-fp64 arrays into frozen state."""
    from pxrdref.backend.torch_backend import make_torch_jacobian
    from tests.test_backend_shim import STATES

    model, table, _ = STATES["toy_rich"]()
    make_torch_jacobian(model, table)(table.x0())
    for cp in model.phases:
        for name, arr in (("win", cp.win), ("fcj_n", cp.fcj_n),
                          ("hkl", cp.reflections.hkl)):
            assert isinstance(arr, np.ndarray), f"{name} left host numpy"
    assert isinstance(model.tt, np.ndarray) and model.tt.dtype == np.float64


# ----------------------------------------------------------------------
# fp64 CPU: the traced residual and the jacfwd Jacobian
# ----------------------------------------------------------------------
def _combined_theta(model, table) -> np.ndarray:
    theta = table.x0()
    if model.pawley is not None:
        theta = np.concatenate([theta, model.pawley_x0()])
    return theta


@pytest.mark.parametrize("name", ["toy_lebail", "toy_pawley", "toy_rich"])
def test_traced_residual_matches_numpy_residual(name):
    """The torch residual is the numpy residual, row for row — the premise the
    column agreement rests on.  A row-layout drift here would show up in the
    matrix as a shape error or a wholesale column mismatch; this localises it."""
    from pxrdref.backend.torch_backend import make_traced_residual
    from pxrdref.optimize.least_squares import _make_residual
    from tests.test_backend_shim import STATES

    model, table, _ = STATES[name]()
    theta = _combined_theta(model, table)
    r_np = _make_residual(model, table)(theta)

    xp = resolve_backend("torch")
    set_backend(xp)
    try:
        r_torch = np.asarray(make_traced_residual(model, table, xp)(
            torch.as_tensor(theta, dtype=torch.float64)))
    finally:
        set_backend("numpy")
    assert r_torch.shape == r_np.shape
    np.testing.assert_allclose(r_torch, r_np, rtol=1e-9,
                               atol=1e-11 * float(np.abs(r_np).max()))


def test_chunk_size_invariance():
    """Padding/trimming of the trailing one-hot seed block must not move a value."""
    from pxrdref.backend.torch_backend import make_torch_jacobian
    from tests.test_backend_shim import STATES

    model, table, _ = STATES["toy_lebail"]()
    theta = _combined_theta(model, table)
    J32 = make_torch_jacobian(model, table)(theta)
    J5 = make_torch_jacobian(model, table, chunk_size=5)(theta)
    np.testing.assert_allclose(J5, J32, rtol=1e-12, atol=1e-12)


def test_jacobian_is_fp64_on_cpu():
    """CPU torch is an *independent fp64 row* of the agreement matrix, not a
    reduced-precision one — so its columns must arrive at full width."""
    from pxrdref.backend.torch_backend import make_torch_jacobian
    from tests.test_backend_shim import STATES

    model, table, _ = STATES["toy_rich"]()
    J = make_torch_jacobian(model, table)(_combined_theta(model, table))
    assert J.dtype == np.float64
    assert np.isfinite(J).all()


# ----------------------------------------------------------------------
# the user-facing wiring
# ----------------------------------------------------------------------
@pytest.mark.parametrize("backend", ["torch", "torch-mps"])
def test_backend_kwarg_refines_and_is_recorded(backend):
    """``backend=`` on ``Refinement`` reaches the solver, converges to the same
    answer as numpy, and lands in the result's provenance — a refinement whose
    columns were computed in fp32 has to *say* so to be reproducible."""
    from pxrdref.strategy.staged import RefinementPlan, Stage
    from tests.test_backend_shim import _toy_base

    if backend == "torch-mps" and not _MPS:
        pytest.skip("no Apple GPU / MPS build")
    structure, ins, pattern = _toy_base()
    plan = RefinementPlan(stages=[
        Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        Stage("cell", ["phases.*.cell.*"]),
    ])
    out = {}
    for name in ("numpy", backend):
        ref = pr.Refinement(structure, ins, backend=name, history=False)
        res = ref.fit(pattern, plan=plan)
        assert res.status == "converged", name
        out[name] = (ref.fitted_structure.phases[0].cell.a.value, res)

    a_np, res_np = out["numpy"]
    a_torch, res_torch = out[backend]
    assert abs(a_torch - a_np) < 1e-7, f"Δa = {a_torch - a_np:.2e} Å"
    assert res_torch.provenance.backend == backend
    assert res_torch.provenance.dtype == (
        "float64/jacobian:float32" if backend == "torch-mps" else "float64")
    assert res_np.provenance.backend == "numpy"


def test_multi_histogram_backend_kwarg():
    """The same kwarg on the multi-histogram entry point (the stacked Jacobian's
    column agreement is WP-0404's matrix; this is the plumbing)."""
    from pxrdref.multi import MultiHistogramRefinement
    from tests.test_multi_histogram import perturbed_inputs, synthesize

    data = [synthesize(0.41390, 3.0, 24.0, scale=5e-4, zero=0.006,
                       bkg=[40.0, -6.0, 1.5], seed=1),
            synthesize(0.71070, 6.0, 46.0, scale=9e-4, zero=-0.010,
                       bkg=[70.0, 5.0, -2.0], seed=2)]
    structure, instruments = perturbed_inputs()
    ref = MultiHistogramRefinement(structure, instruments, backend="torch")
    res = ref.fit(data, plan="mccusker_default")
    assert res.status == "converged"
    assert res.provenance.backend == "torch"
    assert len(res.histograms) == 2


def test_unknown_backend_still_rejected():
    from tests.test_backend_shim import _toy_base

    structure, ins, _ = _toy_base()
    with pytest.raises(NotImplementedError, match="unknown backend"):
        pr.Refinement(structure, ins, backend="cupy", history=False)


# ----------------------------------------------------------------------
# MPS fp32: the first real-hardware evidence about the WP-0403 policy
# ----------------------------------------------------------------------
@requires_mps
def test_mps_columns_are_fp32_on_device_and_fp64_on_host():
    """The WP-0403 boundary, measured on hardware rather than simulated.

    The device genuinely computes the whole peak chain in fp32 (no Apple GPU has
    fp64), and ``linalg64.to_host_fp64`` is the single place that widens it back
    — so what reaches JᵀJ is an fp64 array holding fp32-accurate columns.
    """
    from pxrdref.backend.linalg64 import (
        COLUMN_COSINE_MIN,
        COLUMN_REL_L2_MAX,
        column_agreement,
    )
    from pxrdref.backend.torch_backend import make_torch_jacobian
    from tests.test_backend_shim import STATES

    model, table, _ = STATES["toy_rich"]()
    theta = _combined_theta(model, table)
    J_ref = make_torch_jacobian(model, table)(theta)
    J_mps = make_torch_jacobian(model, table, device="mps")(theta)
    assert J_mps.dtype == np.float64, "columns must cross the host boundary as fp64"

    rel, cos = column_agreement(J_ref, J_mps)
    assert rel < COLUMN_REL_L2_MAX, f"worst column rel-L2 {rel:.3e}"
    assert cos > COLUMN_COSINE_MIN, f"worst column cosine {cos:.8f}"


@requires_mps
@pytest.mark.slow
def test_mps_refine_matches_numpy_cell():
    """End-to-end on real data: an MPS fp32-column refinement of SRM 676a
    corundum lands on the same cell as the numpy path.

    The bar (3e-5 Å) is WP-0403's fp32-column band, and the point of the test is
    that a *step* computed from reduced columns is re-measured against an fp64
    cost by the trust region, so it converges to the same answer.
    """
    from tests.test_acceptance_qpa_roundrobin import (
        DATA,
        corundum_phase,
        qarr_instrument,
        qpa_plan,
        seed_scales,
    )

    if not DATA.exists():
        pytest.skip("IUCr QPA round-robin dataset not present")
    data = pr.read_pattern(DATA / "corundum.prn")
    cells = {}
    for backend in ("numpy", "torch-mps"):
        structure = pr.Structure(phases=[corundum_phase()])
        ins = qarr_instrument()
        seed_scales(structure, ins, data)
        ref = pr.Refinement(structure, ins, backend=backend, history=False)
        res = ref.fit(data, plan=qpa_plan())
        assert res.status == "converged", backend
        cell = ref.fitted_structure.phases[0].cell
        cells[backend] = (cell.a.value, cell.c.value, res)

    a_np, c_np, res_np = cells["numpy"]
    a_mps, c_mps, res_mps = cells["torch-mps"]
    assert abs(a_mps - a_np) <= 3e-5, f"Δa = {a_mps - a_np:.2e} Å"
    assert abs(c_mps - c_np) <= 3e-5, f"Δc = {c_mps - c_np:.2e} Å"
    assert abs(res_mps.statistics.rwp - res_np.statistics.rwp) < 1e-3

    from pxrdref.viz.plots import plot_result
    OUT.mkdir(exist_ok=True)
    plot_result(res_mps, path=str(OUT / "srm676a_torch_mps_fit.png"))
    plot_result(res_mps, path=str(OUT / "srm676a_torch_mps_fit_lowangle.png"),
                two_theta_range=(24.0, 30.0))
