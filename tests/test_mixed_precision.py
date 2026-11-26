"""WP-0403: the mixed-precision policy and the fp64 host boundary.

Three things are under test, in increasing cost:

1. **The policy object** — that ``residual_dtype``/``solve_dtype`` cannot be
   configured away from fp64, that ``cast_columns`` is column-granular and is
   the identity under the default policy, and that ``require_fp64`` refuses a
   reduced-precision residual at the covariance solve.
2. **The wiring** — that ``_jacobian_for`` (the assembly point both the numpy
   and jax paths exit through) actually applies the active policy, producing
   columns that are bit-for-bit the fp32 round-trip of the fp64 ones and agree
   within the WP-0403/0404 bars.
3. **The parameter-level gate** — that SRM 660c refined with fp32-simulated
   Jacobian columns lands on the same lattice parameter within 3e-5 Å and the
   same Rwp within 1e-4.

What the CPU simulation does and does not prove
-----------------------------------------------
Round-tripping ``float64 → float32 → float64`` reproduces the fp32
*representation* limit exactly — which is what a device fp32 column costs when
it crosses the host boundary — but not the error a device accumulates *inside*
an fp32 forward pass, which is strictly larger.  So the measured agreement here
(rel-L2 ~3e-8, cosine 1 - 1e-16) sits orders of magnitude inside bars sized for
real hardware.  That is expected and is the point: this suite proves the
*plumbing* — that reduced columns cannot leak into the residual or the solve —
while the device's own numerics are WP-0408's (torch-MPS) to measure.
``examples/validate_cuda_mixed_precision.py`` is the same assertions against a
real CUDA device, for whenever one exists.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.backend.linalg64 import (
    COLUMN_COSINE_MIN,
    COLUMN_REL_L2_MAX,
    FP32_JACOBIAN,
    FP64,
    MixedPrecisionPolicy,
    column_agreement,
    get_precision_policy,
    precision_policy,
    require_fp64,
    to_host_fp64,
)
from rietx.optimize.least_squares import (
    _jacobian_for,
    _make_jacobian,
    _make_residual,
    covariance_estimates,
)
from tests.test_backend_shim import STATES

OUT = Path(__file__).parent / "output"

#: WP-0403 parameter-level gate on SRM 660c
A_TOL = 3e-5      # Å
RWP_TOL = 1e-4    # absolute


# ----------------------------------------------------------------------
# 1. the policy object
# ----------------------------------------------------------------------
def test_residual_and_solve_dtypes_are_not_configurable():
    """The invariant is code, not a setting: there is no fp32 spelling."""
    for policy in (FP64, FP32_JACOBIAN):
        assert policy.residual_dtype is np.float64
        assert policy.solve_dtype is np.float64
    # frozen dataclass + read-only properties ⇒ neither can be assigned
    with pytest.raises(AttributeError):
        FP32_JACOBIAN.residual_dtype = np.float32
    with pytest.raises(Exception):  # noqa: B017 - FrozenInstanceError is a subclass
        FP64.jacobian_dtype = "fp32"
    # ...and the constructor rejects anything but the two known precisions
    with pytest.raises(ValueError, match="jacobian_dtype"):
        MixedPrecisionPolicy(jacobian_dtype="fp16")


def test_default_policy_is_fp64_and_cast_is_the_identity():
    assert get_precision_policy() == FP64
    assert not FP64.reduced
    rng = np.random.default_rng(0)
    J = rng.normal(size=(64, 7))
    out = FP64.cast_columns(J)
    # bit-identical: the numpy path must not pay for a policy nobody enabled
    assert np.array_equal(out, J)
    assert out.dtype == np.float64


def test_fp32_cast_is_exactly_the_float32_round_trip():
    rng = np.random.default_rng(1)
    J = rng.normal(size=(128, 9)) * np.geomspace(1e-8, 1e6, 9)
    out = FP32_JACOBIAN.cast_columns(J)
    assert out.dtype == np.float64          # comes back fp64 for the host solve
    assert np.array_equal(out, J.astype(np.float32).astype(np.float64))
    assert not np.array_equal(out, J)       # it really did lose bits
    # the loss is bounded by the fp32 unit roundoff, elementwise
    assert np.all(np.abs(out - J) <= np.finfo(np.float32).eps * np.abs(J))


def test_cast_columns_is_column_granular():
    """cast_columns == cast_column applied down each column, and nothing else.

    The loop is the contract's shape: a device backend hands columns back one
    at a time, and a hook shaped like this structurally cannot reach the
    residual or the normal matrix.
    """
    rng = np.random.default_rng(2)
    J = rng.normal(size=(50, 6))
    stacked = np.column_stack([FP32_JACOBIAN.cast_column(J[:, c])
                               for c in range(J.shape[1])])
    assert np.array_equal(FP32_JACOBIAN.cast_columns(J), stacked)
    # a single column is accepted as-is (1-D), not silently transposed
    assert np.array_equal(FP32_JACOBIAN.cast_columns(J[:, 0]),
                          FP32_JACOBIAN.cast_column(J[:, 0]))
    # the policy has no residual hook at all — reduction is columns-only
    assert not hasattr(FP32_JACOBIAN, "cast_residual")


def test_precision_policy_scope_restores_the_previous_policy():
    assert get_precision_policy() == FP64
    with precision_policy(FP32_JACOBIAN):
        assert get_precision_policy() == FP32_JACOBIAN
    assert get_precision_policy() == FP64
    # ...even when the body raises
    with pytest.raises(RuntimeError), precision_policy(FP32_JACOBIAN):
        raise RuntimeError("boom")
    assert get_precision_policy() == FP64


def test_require_fp64_rejects_reduced_precision():
    ok = np.ones(4, dtype=np.float64)
    assert require_fp64(ok, "residual") is not None
    for bad in (np.ones(4, dtype=np.float32), np.ones(4, dtype=np.float16)):
        with pytest.raises(TypeError, match="invariant 2"):
            require_fp64(bad, "residual")
    # to_host_fp64 is the opposite hook: it *does* cast, and only it does
    assert to_host_fp64(np.ones(4, dtype=np.float32)).dtype == np.float64


def test_covariance_solve_upcasts_columns_but_refuses_a_reduced_residual():
    """The two halves of the boundary, at the one place JᵀJ is formed."""
    rng = np.random.default_rng(3)
    J = rng.normal(size=(200, 5))
    r = rng.normal(size=200)

    e64, _ = covariance_estimates(J, r, 5)
    # an fp32-typed Jacobian is upcast here rather than rejected: reduced
    # columns are legal, and this is where they re-enter fp64
    e32, _ = covariance_estimates(J.astype(np.float32), r, 5)
    assert np.allclose(e32, e64, rtol=1e-5)
    # an fp32 residual is a bug upstream, and is refused rather than upcast
    with pytest.raises(TypeError, match="invariant 2"):
        covariance_estimates(J, r.astype(np.float32), 5)


def test_normal_equations_square_the_conditioning():
    """Why the solve can never be fp32, made executable.

    cond(JᵀJ) = cond(J)² (Higham 2002, ch. 20).  On a Vandermonde design with
    cond(J) ≈ 10⁵ — mild next to a Rietveld normal matrix with cell, zero and
    displacement free together — the normal matrix sits at ≈ 10¹⁰, past what
    fp32's 1.2e-7 unit roundoff can resolve at all.  Reducing the *columns*
    instead leaves the recovered coefficients at full accuracy.
    """
    t = np.linspace(0.0, 1.0, 400)
    J = np.vander(t, 8, increasing=True)
    beta = np.arange(1.0, 9.0)
    y = J @ beta

    cond_J = np.linalg.cond(J)
    assert np.linalg.cond(J.T @ J) > 0.5 * cond_J**2

    # fp32 columns, fp64 normal equations: the WP-0403 policy — coefficients
    # recovered to better than 1e-4 relative
    J32 = FP32_JACOBIAN.cast_columns(J)
    b_policy = np.linalg.solve(J32.T @ J32, J32.T @ y)
    assert np.max(np.abs(b_policy - beta) / beta) < 1e-4

    # fp32 normal equations: the violation — orders of magnitude worse
    Jf = J.astype(np.float32)
    N = (Jf.T @ Jf).astype(np.float64)
    b_bad = np.linalg.solve(N, (Jf.T @ y.astype(np.float32)).astype(np.float64))
    err_bad = np.max(np.abs(b_bad - beta) / beta)
    assert err_bad > 100 * np.max(np.abs(b_policy - beta) / beta), (
        f"fp32 normal equations gave {err_bad:.2e} relative error — expected "
        "them to be far worse than the fp32-column policy")


# ----------------------------------------------------------------------
# 2. the wiring: the policy reaches the assembled Jacobian
# ----------------------------------------------------------------------
@pytest.mark.parametrize("state", ["toy_rich", "toy_pawley", "toy_lebail"])
def test_policy_reaches_the_assembled_jacobian(state):
    """``_jacobian_for`` applies the active policy, per column, on every mode."""
    built = STATES[state]()
    assert built is not None
    model, table, _ = built
    theta = table.x0()
    if model.pawley is not None:
        theta = np.concatenate([theta, model.pawley_x0()])

    jac = _jacobian_for(model, table, "numpy")
    J64 = jac(theta)
    with precision_policy(FP32_JACOBIAN):
        J32 = jac(theta)

    # the wrapper is transparent under the default policy...
    assert np.array_equal(J64, _make_jacobian(model, table)(theta))
    # ...and is exactly the column-wise fp32 round-trip under the fp32 one
    assert np.array_equal(J32, FP32_JACOBIAN.cast_columns(J64))
    assert not np.array_equal(J32, J64)
    assert J32.dtype == np.float64

    rel, cos = column_agreement(J64, J32)
    assert rel < COLUMN_REL_L2_MAX, f"{state}: worst column rel-L2 {rel:.3e}"
    assert cos > COLUMN_COSINE_MIN, f"{state}: worst column cosine {cos:.8f}"


def test_residual_is_untouched_by_a_reduced_precision_policy():
    """The residual is fp64 whatever the policy says — it has no cast hook."""
    built = STATES["toy_rich"]()
    model, table, _ = built
    theta = table.x0()
    residual = _make_residual(model, table)
    r64 = residual(theta)
    with precision_policy(FP32_JACOBIAN):
        r32 = residual(theta)
    assert r64.dtype == np.float64 and r32.dtype == np.float64
    assert np.array_equal(r64, r32)


# ----------------------------------------------------------------------
# 3. the parameter-level gate on real data
# ----------------------------------------------------------------------
@pytest.mark.slow
def test_srm660c_fp32_columns_refine_to_the_same_answer():
    """The WP-0403 acceptance: reduced Jacobian columns, unchanged answer.

    SRM 660c on the NIST-calibrated protocol (zero held, displacement refined
    — see test_acceptance_srm660c for the provenance), refined twice.  The
    fp32-column run must land on the same lattice parameter within 3e-5 Å and
    the same Rwp within 1e-4 of the pure-fp64 run.
    """
    from tests.test_acceptance_srm660c import build_srm_inputs

    data, structure, instrument = build_srm_inputs()
    plan = rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        rx.Stage("disp", ["instrument.geometry.sample_displacement"]),
        rx.Stage("cell", ["phases.*.cell.*"]),
        rx.Stage("profile_w", ["instrument.profile.w"]),
        rx.Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                             "instrument.profile.x", "instrument.profile.y"]),
        rx.Stage("lines_axial", ["instrument.source.lines.*.weight",
                                 "instrument.geometry.axial_sl",
                                 "instrument.geometry.axial_hl"]),
        rx.Stage("biso", ["phases.*.atoms.*.biso"]),
    ])

    ref64 = rx.Refinement(structure, instrument, history=False)
    result64 = ref64.fit(data, plan=plan)
    a64 = ref64.fitted_structure.phases[0].cell.a.value

    ref32 = rx.Refinement(structure, instrument, history=False)
    with precision_policy(FP32_JACOBIAN):
        result32 = ref32.fit(data, plan=plan)
    a32 = ref32.fitted_structure.phases[0].cell.a.value
    # the policy must not have leaked out of the with-block
    assert get_precision_policy() == FP64

    assert result32.status == "converged"
    assert abs(a32 - a64) < A_TOL, (
        f"fp32 columns moved a by {abs(a32 - a64):.3e} Å "
        f"(fp64 {a64:.6f}, fp32 {a32:.6f})")
    assert abs(result32.statistics.rwp - result64.statistics.rwp) < RWP_TOL, (
        f"Rwp {result64.statistics.rwp:.6f} → {result32.statistics.rwp:.6f}")
    # ...and the fp32-column run is still a good fit in absolute terms, not
    # merely equal to a degraded reference
    assert result32.statistics.rwp < 0.10

    # esds come off the fp32-column Jacobian through the fp64 solve; they are
    # a squared-conditioning quantity, so agreement here is the sharper check
    e64 = result64.parameter("phases.0.cell.a").stderr
    e32 = result32.parameter("phases.0.cell.a").stderr
    assert e64 is not None and e32 is not None
    assert abs(e32 - e64) < 0.05 * e64, f"esd {e64:.3e} → {e32:.3e}"

    # obs/calc/diff for visual inspection (tests/output/, gitignored) — Rwp
    # equality would hide a locally-bad fit
    from rietx.viz.plots import plot_result
    OUT.mkdir(exist_ok=True)
    plot_result(result32, path=str(OUT / "mixed_precision_srm660c_fp32.png"))
    plot_result(result32, path=str(OUT / "mixed_precision_srm660c_fp32_lowangle.png"),
                two_theta_limits=(20.6, 22.2))
    plot_result(result64, path=str(OUT / "mixed_precision_srm660c_fp64.png"))
