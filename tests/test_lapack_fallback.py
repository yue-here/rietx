"""A decomposition LAPACK's divide-and-conquer driver does not converge on is
repeated with its QR-iteration twin, and the stage counts it (WP-2002).

Met on macOS's system LAPACK, whose ``gesdd`` failed on a TRF step on CPD
brucite (``tests/test_acceptance_stephens.py``).  No small matrix makes
Accelerate fail on demand, so these tests make the first driver fail by hand
and check that the fallback reaches each call, that the answer is the twin's,
and that a caller outside the package keeps SciPy's behaviour.
"""

import ast
import pathlib

import numpy as np
import pytest
import scipy.linalg
from scipy.optimize import least_squares

import rietx as rx
from rietx.optimize import lapack
from tests.test_refine_synthetic import perturbed_models, synthesize

RNG = np.random.default_rng(11)


def _failing(monkeypatch, name):
    def fail(*args, **kwargs):
        raise np.linalg.LinAlgError(f"{name} did not converge (injected)")
    monkeypatch.setattr(np.linalg, name, fail)


def _symmetric(n=6):
    a = RNG.normal(size=(n, n))
    return a @ a.T + np.eye(n)


def test_a_converging_decomposition_is_numpys_own():
    a = _symmetric()
    before = lapack.retries()
    w, v = lapack.eigh(a)
    ref_w, ref_v = np.linalg.eigh(a)
    assert np.array_equal(w, ref_w) and np.array_equal(v, ref_v)
    assert lapack.retries() == before


@pytest.mark.parametrize("name", ["eigh", "eigvalsh", "svd", "lstsq", "pinv"])
def test_each_fallback_returns_the_twins_answer_and_is_counted(monkeypatch, name):
    a = _symmetric() if name.startswith("eig") else RNG.normal(size=(9, 4))
    b = RNG.normal(size=9)
    ref = {"eigh": lambda: np.linalg.eigh(a)[0],
           "eigvalsh": lambda: np.linalg.eigvalsh(a),
           "svd": lambda: np.linalg.svd(a, full_matrices=False)[1],
           "lstsq": lambda: np.linalg.lstsq(a, b, rcond=None)[0],
           "pinv": lambda: np.linalg.pinv(a)}[name]()
    _failing(monkeypatch, name)
    before = lapack.retries()
    got = {"eigh": lambda: lapack.eigh(a)[0],
           "eigvalsh": lambda: lapack.eigvalsh(a),
           "svd": lambda: lapack.svd(a, full_matrices=False)[1],
           "lstsq": lambda: lapack.lstsq(a, b)[0],
           "pinv": lambda: lapack.pinv(a)}[name]()
    assert lapack.retries() == before + 1
    np.testing.assert_allclose(got, ref, rtol=1e-12, atol=1e-12)


@pytest.mark.parametrize("name", ["svd", "lstsq", "pinv"])
def test_a_non_finite_input_keeps_numpys_linalgerror(name):
    """numpy reports a NaN as non-convergence.  The fallback re-raises that
    error rather than SciPy's ``ValueError``, so every ``except LinAlgError``
    (``_guarded_covariance``'s rule, #225) still catches it, and counts none."""
    a = RNG.normal(size=(9, 4))
    a[2, 1] = np.nan
    call = {"svd": lambda: lapack.svd(a, full_matrices=False),
            "lstsq": lambda: lapack.lstsq(a, RNG.normal(size=9)),
            "pinv": lambda: lapack.pinv(a)}[name]
    before = lapack.retries()
    with pytest.raises(np.linalg.LinAlgError):
        call()
    assert lapack.retries() == before


def test_a_stacked_eigh_falls_back_matrix_by_matrix(monkeypatch):
    stack = np.stack([_symmetric(), _symmetric()])
    ref_w, ref_v = np.linalg.eigh(stack)
    _failing(monkeypatch, "eigh")
    w, v = lapack.eigh(stack)
    np.testing.assert_allclose(w, ref_w, rtol=1e-12)
    # eigenvectors up to sign
    np.testing.assert_allclose(np.abs(np.einsum("kij,kij->kj", v, ref_v)), 1.0, rtol=1e-12)


def _gesdd_fails(monkeypatch):
    """TRF's step SVD fails under ``gesdd``, as Accelerate's did on brucite."""
    assert lapack._install_trf_svd(), "SciPy's TRF no longer calls scipy.linalg.svd by name"
    real = scipy.linalg.svd

    def svd(a, *args, **kwargs):
        if kwargs.get("lapack_driver", "gesdd") == "gesdd":
            raise np.linalg.LinAlgError("SVD did not converge (injected)")
        return real(a, *args, **kwargs)
    monkeypatch.setattr(lapack, "_trf_svd_original", svd)


def _linear_problem():
    a = RNG.normal(size=(40, 5))
    y = a @ np.arange(1.0, 6.0) + 0.01 * RNG.normal(size=40)
    return (lambda x: a @ x - y), (lambda x: a), np.zeros(5)


def test_trfs_step_falls_back_inside_the_package_and_raises_outside(monkeypatch):
    fun, jac, x0 = _linear_problem()
    bounds = (np.full(5, -10.0), np.full(5, 10.0))
    ref = least_squares(fun, x0, jac=jac, bounds=bounds, method="trf")
    _gesdd_fails(monkeypatch)
    before = lapack.retries()
    with lapack.scipy_trf():
        got = least_squares(fun, x0, jac=jac, bounds=bounds, method="trf")
    assert lapack.retries() > before
    np.testing.assert_allclose(got.x, ref.x, rtol=1e-10)
    # a caller of SciPy's TRF outside the package keeps SciPy's raise
    with pytest.raises(np.linalg.LinAlgError):
        least_squares(fun, x0, jac=jac, bounds=bounds, method="trf")


def test_a_trf_stage_records_its_fallbacks(monkeypatch):
    data = synthesize()
    plan = rx.RefinementPlan(stages=[rx.Stage("scale", ["phases.*.scale"])])
    plan.closing_window_tol = None
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, solver="trf", history=False).fit(data, plan=plan)
    _gesdd_fails(monkeypatch)
    structure, ins = perturbed_models()
    got = rx.Refinement(structure, ins, solver="trf", history=False).fit(data, plan=plan)
    assert ref.stages[0].n_lapack_fallbacks == 0
    assert got.stages[0].n_lapack_fallbacks > 0
    assert got.statistics.rwp == pytest.approx(ref.statistics.rwp, rel=1e-9)


#: what a fit and its report run: the step and the esds (``optimize/``), the
#: table, the model, the stage runner's holds, the report, the background
#: pick and the solve costing.  ``crystallography/`` and ``indexing/`` are
#: left out: their decompositions act on small symmetry matrices or are caught
#: by their own handlers, and none has been met failing.
FIT_PATH = ("optimize", "model", "params", "report", "background", "solve",
            "refine.py", "multi.py", "sequential.py")


def test_the_fit_path_decomposes_only_through_the_fallbacks():
    """A bare numpy decomposition on the fit path would raise out of a fit, or
    withhold its esds or a report, where the fallback answers."""
    package = pathlib.Path(rx.__file__).parent
    names = {"eigh", "eigvalsh", "svd", "lstsq", "pinv", "cond"}
    found = []
    paths = [p for entry in FIT_PATH for p in (
        sorted((package / entry).rglob("*.py")) if (package / entry).is_dir()
        else [package / entry])]
    for path in paths:
        if path.name == "lapack.py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr in names
                    and ast.unparse(node.func.value) in {"np.linalg", "numpy.linalg",
                                                         "scipy.linalg", "linalg"}):
                found.append(f"{path.relative_to(package)}:{node.lineno}")
    assert not found, found
