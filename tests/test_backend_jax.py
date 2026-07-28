"""WP-0402 jax backend: chunked jacfwd vs analytic/FD, isolation, end-to-end.

Everything here needs jax (``pytest.importorskip``) except the claim the
subprocess test proves: a numpy-only *process* never imports jax and never
sees the global x64 flag — pxrdref's fp64 comes from the *scoped*
``enable_x64`` at the jacfwd/jit call sites only.

Column agreement uses the WP-0402 acceptance bars (<5e-3 rel-L2, cosine
>0.99999) against both the analytic Jacobian and plain forward differences
of the numpy residual.  Columns that are numerically dead at the expansion
point (softplus parameters parked at the zero floor, dp/du ≈ 1e-12; e.g.
``profile.y`` in the ``toy_rich`` state, column norm ~1e-9 against a median
of ~1e3) are skipped — the same "dead FD column" convention as
``test_v02_core.test_analytic_jacobian_matches_fd``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

jax = pytest.importorskip("jax")

import pxrdref as pr  # noqa: E402
from pxrdref.backend import (  # noqa: E402
    NumpyBackend,
    get_backend,
    resolve_backend,
)
from pxrdref.backend.jax_backend import (  # noqa: E402
    make_jax_jacobian,
    make_traced_residual,
)
from pxrdref.model.forward import compile_model  # noqa: E402
from pxrdref.optimize.least_squares import (  # noqa: E402
    _make_jacobian,
    _make_residual,
)
from pxrdref.params.vector import ParameterTable  # noqa: E402
from tests.test_backend_shim import STATES  # noqa: E402
from tests.test_v02_core import ANALYTIC_FAMILIES, _lab_state  # noqa: E402

DATA = Path(__file__).parent / "data"
OUT = Path(__file__).parent / "output"

#: a column is "live" when its norm clears this fraction of the largest
#: column's — below it the value is transform-floor noise, not a derivative
DEAD_COL_FRAC = 1e-6


def _combined_theta(model, table) -> np.ndarray:
    theta = table.x0()
    if model.pawley is not None:
        theta = np.concatenate([theta, model.pawley_x0()])
    return theta


def _column_agreement(J_ref, J_test, labels, *, rel=5e-3, cos_min=0.99999,
                      loose=frozenset()):
    """Assert per-column rel-L2 + cosine agreement, skipping dead columns.

    ``loose`` columns get a 2e-2 / 0.9995 bar: reserved for parameters sitting
    exactly on a documented kink of the parameterisation, where one-sided,
    subgradient and central estimates legitimately differ (see the S/L == H/L
    note in ``test_jacfwd_matches_analytic_on_state``).
    """
    assert J_ref.shape == J_test.shape
    scale = np.linalg.norm(J_ref, axis=0).max()
    n_live = 0
    for c in range(J_ref.shape[1]):
        a, b = J_ref[:, c], J_test[:, c]
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        if max(na, nb) < DEAD_COL_FRAC * scale:
            continue
        n_live += 1
        bar, cbar = (2e-2, 0.9995) if labels[c] in loose else (rel, cos_min)
        err = np.linalg.norm(a - b) / max(na, nb)
        assert err < bar, f"{labels[c]}: rel-L2 {err:.2e}"
        cos = float(a @ b) / (na * nb)
        assert cos > cbar, f"{labels[c]}: cosine {cos:.7f}"
    assert n_live > 0, "every column was dead — the comparison proved nothing"


# ----------------------------------------------------------------------
# isolation: lazy import, scoped x64, backend restore
# ----------------------------------------------------------------------
def test_numpy_only_process_never_imports_jax_nor_sets_x64():
    """The strongest form of the WP claim, in a fresh subprocess: importing
    pxrdref and running the numpy path never imports jax, and when the user
    then imports jax themselves its world is untouched (x64 off, fp32)."""
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

assert "jax" not in sys.modules, "numpy-only path imported jax"

import jax
import jax.numpy as jnp
assert jax.config.jax_enable_x64 is False, "x64 flag was set globally"
assert jnp.zeros(1).dtype.name == "float32", "jax default dtype was changed"
"""
    proc = subprocess.run([sys.executable, "-c", code],
                          cwd=Path(__file__).parent.parent,
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_x64_and_global_backend_never_leak():
    import jax.numpy as jnp

    model, table, _ = STATES["toy_lebail"]()
    make_jax_jacobian(model, table)(_combined_theta(model, table))

    assert isinstance(get_backend(), NumpyBackend)
    assert jax.config.jax_enable_x64 is False
    assert jnp.zeros(1).dtype.name == "float32"


def test_unknown_backend_rejected():
    # "cupy", not "torch": torch became a real backend with WP-0408, so this
    # needs a name that is genuinely absent from the registry
    with pytest.raises(ValueError, match="unknown backend"):
        resolve_backend("cupy")
    structure, ins, _ = _lab_state()
    with pytest.raises(NotImplementedError, match="unknown backend"):
        pr.Refinement(structure, ins, backend="cupy", history=False)


def test_jax_backend_ops_functional_contract():
    """The immutable-backend flavours of the two scatter primitives."""
    import jax.numpy as jnp

    xp = resolve_backend("jax")
    y = jnp.zeros(6)
    out = xp.window_add(y, 2, 5, jnp.array([1.0, 2.0, 3.0]))
    assert out is not y  # functional: a NEW array, input untouched
    assert np.allclose(np.asarray(y), 0.0)
    assert np.allclose(np.asarray(out), [0, 0, 1, 2, 3, 0])

    vals = jnp.array([1.0, 2.0, 4.0, 8.0, 16.0])
    seg = jnp.array([0, 2, 2, 0, 3])
    got = np.asarray(xp.segment_sum(vals, seg, 5))
    assert np.array_equal(got, np.bincount(np.asarray(seg),
                                           weights=np.asarray(vals), minlength=5))


# ----------------------------------------------------------------------
# jacfwd vs analytic vs FD
# ----------------------------------------------------------------------
def test_jacfwd_matches_analytic_and_fd_on_families():
    """The 18 analytic-column families, jax against both references."""
    structure, ins, pattern = _lab_state()
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    for path in ANALYTIC_FAMILIES:
        assert table.set_vary([path], True), path
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          free_paths=set(table.free_paths))

    theta = table.x0()
    J_an = _make_jacobian(model, table)(theta)
    J_jax = make_jax_jacobian(model, table)(theta)
    _column_agreement(J_an, J_jax, table.free_paths)

    # plain forward differences of the numpy residual, same step rule as
    # test_analytic_jacobian_matches_fd — the reference independent of both
    residual = _make_residual(model, table)
    r0 = residual(theta)
    J_fd = np.empty_like(J_an)
    for c in range(len(theta)):
        h = 1e-6 * max(1.0, abs(theta[c]))
        tp = theta.copy()
        tp[c] += h
        J_fd[:, c] = (residual(tp) - r0) / h
    _column_agreement(J_fd, J_jax, table.free_paths)


@pytest.mark.parametrize("name", [
    "toy_lebail",
    "toy_pawley",
    "toy_rich",
    "toy_stephens",
    "toy_anomalous",
    pytest.param("srm660c", marks=pytest.mark.slow),
])
def test_jacfwd_matches_analytic_on_state(name):
    """Whole-matrix agreement on the shim states (Le Bail snapshot + P-spline
    penalty rows; Pawley aux block + restraint rows; aniso ADPs + March-
    Dollase + extinction + FCJ asymmetry; hkl-dependent Stephens widths, whose
    √ of a monomial matmul jacfwd has to trace; the Friedel-averaged
    |A|² + |B|² of a non-centrosymmetric anomalous structure, where both
    structural derivative kernels carry a second term; real doublet lab
    data)."""
    built = STATES[name]()
    if built is None:
        pytest.skip(f"dataset for state {name!r} not present")
    model, table, _ = built
    theta = _combined_theta(model, table)

    # the traced residual is the numpy residual, row for row
    r_np = _make_residual(model, table)(theta)
    from pxrdref.backend import set_backend
    set_backend("jax")
    try:
        from pxrdref.backend.jax_backend import _enable_x64
        with _enable_x64():
            r_jax = np.asarray(make_traced_residual(model, table)(theta))
    finally:
        set_backend("numpy")
    assert r_jax.shape == r_np.shape
    np.testing.assert_allclose(r_jax, r_np, rtol=1e-9,
                               atol=1e-12 * float(np.abs(r_np).max()))

    labels = list(table.free_paths)
    if model.pawley is not None:
        labels += [f"pawley.I{k}" for k in range(model.pawley.n)]

    # srm660c starts at axial S/L == H/L — exactly the FCJ quadrature-split
    # kink (ξ_kink = |S/L − H/L| = 0), a genuinely non-smooth point where the
    # forward node-FD (analytic), the sign(0) = 0 subgradient (jax) and
    # central FD legitimately disagree at the few-1e-3 level (measured:
    # analytic and jax each sit 3.0e-3 from central FD, on opposite sides).
    # _lab_state/toy_rich use unequal ratios for this reason; the end-to-end
    # test shows the subgradient is immaterial for convergence.
    values = table.decode(table.x0())
    loose = (frozenset({"instrument.geometry.axial_sl",
                        "instrument.geometry.axial_hl"})
             if values["instrument.geometry.axial_sl"]
             == values["instrument.geometry.axial_hl"] else frozenset())

    J_an = _make_jacobian(model, table)(theta)
    J_jax = make_jax_jacobian(model, table)(theta)
    _column_agreement(J_an, J_jax, labels, loose=loose)


def test_jacfwd_pawley_linear_columns_exact():
    """The Pawley intensity block is exactly linear — both sides are exact,
    so they must agree far tighter than the FD-chained table columns."""
    model, table, _ = STATES["toy_pawley"]()
    theta = _combined_theta(model, table)
    n_table = len(table.free_paths)

    J_an = _make_jacobian(model, table)(theta)
    J_jax = make_jax_jacobian(model, table)(theta)
    aux_an, aux_jax = J_an[:, n_table:], J_jax[:, n_table:]
    scale = np.linalg.norm(aux_an)
    assert scale > 0
    assert np.linalg.norm(aux_an - aux_jax) / scale < 1e-8
    # restraint rows are the constant matrix R itself
    n_res = model.pawley.restraint.shape[0]
    np.testing.assert_allclose(J_jax[-n_res:, n_table:],
                               model.pawley.restraint, rtol=0, atol=1e-12)


def test_chunk_size_invariance():
    """Padding/trimming of the trailing seed block must not change a value."""
    model, table, _ = STATES["toy_lebail"]()
    theta = _combined_theta(model, table)
    J32 = make_jax_jacobian(model, table)(theta)
    J5 = make_jax_jacobian(model, table, chunk_size=5)(theta)
    np.testing.assert_allclose(J5, J32, rtol=1e-12, atol=1e-12)


# ----------------------------------------------------------------------
# end-to-end: SRM 660c under backend="jax"
# ----------------------------------------------------------------------
@pytest.mark.slow
def test_srm660c_end_to_end_jax_matches_numpy():
    """Full staged NIST-protocol refinement with the jax Jacobian: same
    convergence, cell within 1e-6 Å of the numpy backend's."""
    from tests.test_acceptance_srm660c import (
        A_REFERENCE,
        _nist_calibrated_plan,
        build_srm_inputs,
    )

    data, structure, instrument = build_srm_inputs()

    results = {}
    for backend in ("numpy", "jax"):
        ref = pr.Refinement(structure, instrument, backend=backend, history=False)
        res = ref.fit(data, plan=_nist_calibrated_plan())
        assert res.status == "converged", backend
        results[backend] = (ref, res)

    a_np = results["numpy"][0].fitted_structure.phases[0].cell.a.value
    a_jax = results["jax"][0].fitted_structure.phases[0].cell.a.value
    assert abs(a_jax - a_np) <= 1e-6, f"Δa = {a_jax - a_np:.2e} Å"
    assert abs(a_jax - A_REFERENCE) < 2e-4  # still inside the acceptance band
    rwp_np = results["numpy"][1].statistics.rwp
    rwp_jax = results["jax"][1].statistics.rwp
    assert abs(rwp_jax - rwp_np) < 1e-4

    # obs/calc/diff PNGs for visual inspection (tests/output/, gitignored)
    from pxrdref.viz.plots import plot_result
    OUT.mkdir(exist_ok=True)
    plot_result(results["jax"][1], path=str(OUT / "srm660c_jax_fit.png"))
    plot_result(results["jax"][1], path=str(OUT / "srm660c_jax_fit_lowangle.png"),
                two_theta_range=(20.6, 22.2))
    plot_result(results["jax"][1], path=str(OUT / "srm660c_jax_fit_highangle.png"),
                two_theta_range=(147.5, 150.9))
