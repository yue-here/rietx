"""Validate the WP-0403 mixed-precision policy on real CUDA hardware.

**This script is documentation-as-code, not a CI gate.**  It is opt-in and
skips cleanly wherever no CUDA device exists — which includes the machine this
package is developed on (a Mac; Apple GPUs have no fp64 in any framework, so
the local real-hardware validation of the same policy arrives through the
torch-MPS backend in WP-0408 instead).

What it checks, when a CUDA box does exist
------------------------------------------
The claim under test is architecture invariant 2 (docs/DESIGN.md): Jacobian
*columns* are relative-accuracy tolerant and may be computed at fp32 on
device, while the residual used for cost/statistics and the JᵀJ solve stay
fp64 on host.  So it refines NIST SRM 660c twice — once on the pure fp64 path,
once with the device-fp32 policy active — and asserts:

* per-column agreement of the fp32 Jacobian against the fp64 one at the fp64
  solution, within ``COLUMN_REL_L2_MAX`` / ``COLUMN_COSINE_MIN``;
* the refined lattice parameter agrees to ``A_TOL`` Å and Rwp to ``RWP_TOL``;
* the residual and the covariance solve were fp64 throughout (``require_fp64``
  raises inside the solver if not).

Note what "device fp32" means here and why it is stronger than the CPU test.
``tests/test_mixed_precision.py`` simulates fp32 by round-tripping fp64
columns, which reproduces the fp32 *representation* limit exactly but not the
error a device accumulates *inside* an fp32 forward pass.  Only real hardware
computing the whole peak-chain in fp32 exercises that, which is the entire
reason this script exists.

Usage::

    python examples/validate_cuda_mixed_precision.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

import rietx as rx
from rietx.backend.linalg64 import (
    COLUMN_COSINE_MIN,
    COLUMN_REL_L2_MAX,
    FP32_JACOBIAN,
    column_agreement,
    precision_policy,
)
from rietx.model.forward import compile_model
from rietx.optimize.least_squares import _jacobian_for
from rietx.params.vector import ParameterTable

DATA = Path(__file__).resolve().parent.parent / "tests" / "data"

#: parameter-level bars, shared with WP-0404
A_TOL = 3e-5      # Å on the SRM 660c lattice parameter
RWP_TOL = 1e-4    # absolute, on the weighted profile R-factor


def find_cuda_backend() -> str | None:
    """The name of a rietx backend sitting on a real CUDA device, or None.

    jax is asked first (WP-0402), then torch (WP-0408).  Both imports are
    inside the function: this script must not import either on a machine that
    has neither.
    """
    try:
        import jax

        if any(d.platform == "gpu" for d in jax.devices()):
            return "jax"
    except Exception:  # noqa: BLE001 - absent or CPU-only jax is not an error
        pass
    try:
        import torch

        if torch.cuda.is_available():
            return "torch"
    except Exception:  # noqa: BLE001
        pass
    return None


def build_inputs():
    """The NIST-protocol SRM 660c state — mirrors tests/test_acceptance_srm660c."""
    path = DATA / "nist_srm660c_100a.cif"
    if not path.exists():
        raise SystemExit(f"SRM 660c dataset not present at {path}")
    data = rx.read_pdcif(path, block="_meas")
    structure = rx.Structure(phases=[rx.Phase(
        name="LaB6", space_group="P m -3 m", cell=rx.Cell.cubic(4.1568),
        atoms=[
            rx.Atom(label="La", species="La", x=rx.Parameter(value=0.0),
                    y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0),
                    biso=rx.Parameter(value=0.355, min=0.0, max=25.0)),
            rx.Atom(label="B", species="B", x=rx.Parameter(value=0.198),
                    y=rx.Parameter(value=0.5), z=rx.Parameter(value=0.5),
                    biso=rx.Parameter(value=0.276, min=0.0, max=25.0)),
        ],
        scale=rx.Parameter(value=1e-4, min=0.0),
    )])
    instrument = rx.Instrument.bragg_brentano(monochromator_two_theta=26.6)
    instrument.profile.w.value = 2e-3
    instrument.profile.x.value = 5e-3
    instrument.geometry.axial_sl.value = 0.025
    instrument.geometry.axial_hl.value = 0.025
    from rietx.schemas.instrument import BackgroundChebyshev
    instrument.background = BackgroundChebyshev.with_terms(6)
    return data, structure, instrument


def nist_plan() -> rx.RefinementPlan:
    """lab_bragg_brentano minus the zero error (the DBD is angle-calibrated)."""
    return rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        rx.Stage("disp", ["instrument.geometry.sample_displacement"]),
        rx.Stage("cell", ["phases.*.cell.*"]),
        rx.Stage("profile_w", ["instrument.profile.w"]),
        rx.Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                             "instrument.profile.x", "instrument.profile.y"]),
        # S/L alone, H/L held at its declared 0.025, as the preset (WP-2012).
        rx.Stage("lines_axial", ["instrument.source.lines.*.weight",
                                 "instrument.geometry.axial_sl"]),
        rx.Stage("biso", ["phases.*.atoms.*.biso"]),
    ])


def compare_columns(data, structure, instrument, backend: str) -> tuple[float, float]:
    """fp32-column vs fp64 Jacobian at the converged structure, per column."""
    table = ParameterTable(structure, instrument)
    table.set_vary(["*"], False)
    for pat in ("phases.*.scale", "phases.*.cell.*", "instrument.background.*",
                "instrument.profile.*", "instrument.geometry.sample_displacement",
                "phases.*.atoms.*.biso"):
        table.set_vary([pat], True)
    model = compile_model(structure, instrument, data, mode="rietveld",
                          free_paths=set(table.free_paths))
    theta = table.x0()

    jac = _jacobian_for(model, table, backend)
    J64 = jac(theta)
    with precision_policy(FP32_JACOBIAN):
        J32 = jac(theta)
    return column_agreement(J64, J32)


def main() -> int:
    backend = find_cuda_backend()
    if backend is None:
        print("no CUDA device visible to jax or torch — skipping "
              "(this script is opt-in; see the module docstring)")
        return 0
    print(f"CUDA device found; validating the mixed-precision policy on "
          f"backend={backend!r}")

    data, structure, instrument = build_inputs()

    ref64 = rx.Refinement(structure, instrument, backend=backend, history=False)
    result64 = ref64.fit(data, plan=nist_plan())
    a64 = ref64.fitted_structure.phases[0].cell.a.value

    ref32 = rx.Refinement(structure, instrument, backend=backend, history=False)
    with precision_policy(FP32_JACOBIAN):
        result32 = ref32.fit(data, plan=nist_plan())
    a32 = ref32.fitted_structure.phases[0].cell.a.value

    rel, cos = compare_columns(data, ref64.fitted_structure,
                               ref64.fitted_instrument, backend)
    da = abs(a32 - a64)
    drwp = abs(result32.statistics.rwp - result64.statistics.rwp)

    print(f"  worst column rel-L2 {rel:.3e}  (bar {COLUMN_REL_L2_MAX:.0e})")
    print(f"  worst column cosine {cos:.8f}  (bar {COLUMN_COSINE_MIN})")
    print(f"  a  fp64 {a64:.6f}  fp32-columns {a32:.6f}  "
          f"Δ {da:.2e} Å  (bar {A_TOL:.0e})")
    print(f"  Rwp fp64 {result64.statistics.rwp:.6f}  "
          f"fp32-columns {result32.statistics.rwp:.6f}  "
          f"Δ {drwp:.2e}  (bar {RWP_TOL:.0e})")

    failures = []
    if not rel < COLUMN_REL_L2_MAX:
        failures.append(f"column rel-L2 {rel:.3e} >= {COLUMN_REL_L2_MAX:.0e}")
    if not cos > COLUMN_COSINE_MIN:
        failures.append(f"column cosine {cos:.8f} <= {COLUMN_COSINE_MIN}")
    if not da < A_TOL:
        failures.append(f"lattice parameter moved {da:.2e} Å >= {A_TOL:.0e}")
    if not drwp < RWP_TOL:
        failures.append(f"Rwp moved {drwp:.2e} >= {RWP_TOL:.0e}")
    # residual/solve fp64 is enforced inside the solver by require_fp64; the
    # refines above completing at all is that assertion passing
    if failures:
        print("\nFAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nOK — fp32 Jacobian columns, fp64 residual and solve, same answer.")
    return 0


if __name__ == "__main__":
    np.set_printoptions(precision=6)
    sys.exit(main())
