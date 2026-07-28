"""Backend conformance — the rules a *new* backend inherits automatically.

The agreement matrix (``test_cross_backend.py``) proves that the backends
shipped today compute the same Jacobian.  This file is the other half: it is
driven by the **registry** (``backend.api.BACKEND_NAMES``) rather than by a
hand-written list, so a backend added to the registry is immediately held to
every rule below — op parity, the traced decode, the residual row layout — and
a backend added *without* wiring its agreement rows fails the meta-test at the
bottom instead of shipping unvalidated.

That inversion is the point.  v0.4 shipped two derivative paths (WP-0405's
Voigt shape, WP-0406's restraint rows) that no matrix row evaluated, because
the matrix takes its configs from an explicit list; both were caught by hand at
integration.  Nothing here can be forgotten by omission: the loop is over the
registry, and the parts a backend must implement are read from the shim's own
vocabulary.

Every optional backend self-skips when its package is absent, so the file is
green on a numpy-only checkout.
"""

from __future__ import annotations

import numpy as np
import pytest

from pxrdref.backend import traced
from pxrdref.backend.api import (
    _OP_NAMES,
    BACKEND_NAMES,
    BACKEND_REQUIRES,
    EXPERIMENTAL_BACKENDS,
    NumpyBackend,
    backend_dtype_note,
    resolve_backend,
)
from pxrdref.backend.linalg64 import COLUMN_REL_L2_MAX, to_host_fp64
from pxrdref.backend.traced import make_traced_decode, make_traced_residual
from pxrdref.model import rows as row_layout
from pxrdref.optimize.least_squares import _make_residual
from pxrdref.params.transforms import to_physical
from tests.test_backend_shim import STATES

#: every op the shim promises, plus the non-``_OP_NAMES`` primitives
REQUIRED_CALLABLES = (*_OP_NAMES, "window_add", "segment_sum", "scalarize",
                      "full_precision")
REQUIRED_ATTRS = ("name", "pi", "linalg")


def backend_or_skip(name: str):
    """The backend instance, or a skip when its optional package is absent."""
    package = BACKEND_REQUIRES.get(name)
    if package is not None:
        pytest.importorskip(package)
    try:
        return resolve_backend(name)
    except (ImportError, RuntimeError) as exc:      # no MPS device, e.g.
        pytest.skip(f"backend {name!r} unavailable: {exc}")


@pytest.mark.parametrize("name", BACKEND_NAMES)
def test_backend_implements_the_whole_vocabulary(name):
    """Every registered backend provides every op, with no silent gaps.

    The lists come from the shim itself, so adding an op to ``_OP_NAMES``
    without implementing it on some backend fails here — for *all* backends at
    once, not only the one whose own test file someone remembered to update.
    """
    xp = backend_or_skip(name)
    missing = [op for op in REQUIRED_CALLABLES if not callable(getattr(xp, op, None))]
    assert not missing, f"{name}: missing ops {missing}"
    for attr in REQUIRED_ATTRS:
        assert getattr(xp, attr, None) is not None, f"{name}: missing {attr}"
    assert callable(getattr(xp.linalg, "inv", None))
    assert callable(getattr(xp.linalg, "det", None))


@pytest.mark.parametrize("name", BACKEND_NAMES)
def test_transform_ops_match_the_reference_transforms(name):
    """``xp.logaddexp`` / ``xp.exp`` / ``xp.sigmoid`` reproduce
    ``params.transforms.to_physical``.

    The traced decode is written once against these three ops, so a backend
    whose sigmoid saturates differently (or whose softplus takes a linear
    branch above some threshold, as ``torch.nn.functional.softplus`` does)
    would decode a *different physical model* while every shape check passed.
    """
    xp = backend_or_skip(name)
    u = np.array([-40.0, -3.0, -0.5, 0.0, 0.5, 3.0, 40.0])
    with xp.full_precision():
        got = {
            "softplus": to_host_fp64(xp.logaddexp(xp.zeros_like(xp.asarray(u)),
                                                  xp.asarray(u))),
            "exp": to_host_fp64(xp.exp(xp.asarray(u))),
            "logit": to_host_fp64(xp.sigmoid(xp.asarray(u))),
        }
    for kind, values in got.items():
        want = np.array([to_physical(float(x), kind) for x in u])
        # fp32 devices carry their own floor; the point is the *branch*, not ulps
        tol = 1e-5 if "mps" in name else 1e-12
        assert np.allclose(values, want, rtol=tol, atol=tol), f"{name}/{kind}"


@pytest.mark.parametrize("state", list(STATES))
@pytest.mark.parametrize("name", [n for n in BACKEND_NAMES if n != "numpy"])
def test_traced_residual_matches_the_numpy_reference(name, state):
    """The traced twin equals ``_make_residual`` row for row, on every golden
    state — which is what makes the shared row layout a *checked* claim rather
    than a structural hope.

    Runs the full state matrix (Le Bail penalty rows, Pawley aux block and
    overlap restraints, soft restraints, aniso/PO/extinction) against every
    registered backend, so a new backend inherits the whole grid.
    """
    xp = backend_or_skip(name)
    built = STATES[state]()
    if built is None:
        pytest.skip(f"dataset for state {state!r} not present")
    model, table, _extras = built

    theta = table.x0()
    if model.pawley is not None:
        theta = np.concatenate([theta, model.pawley_x0()])

    want = _make_residual(model, table)(theta)
    # no set_backend / precision scope here on purpose: the traced residual
    # opens its own (``backend.traced.active``), and a backend that needs the
    # caller to do it would fail this test rather than fail in the field
    got = to_host_fp64(make_traced_residual(model, table, xp)(theta))

    assert got.shape == want.shape == (row_layout.n_rows(model),), (
        f"{name}/{state}: {got.shape} vs {want.shape} vs layout "
        f"{row_layout.n_rows(model)}")

    if "float32" in backend_dtype_note(name):
        # A reduced-precision *device* residual cannot match the fp64 one and is
        # never asked to: it exists to carry Jacobian columns, and cost, χ² and
        # every statistic are computed from the numpy fp64 residual (invariant
        # 2).  WP-0403's physics puts the gap at ~10 counts lost to cancellation
        # at 10⁵, i.e. ~1e-4 of the weighted residual — measured 3e-5…1.4e-4
        # here, against WP-0403's own fp32 bar.  What must still hold exactly is
        # the *layout*, asserted above.
        rel = np.linalg.norm(got - want) / np.linalg.norm(want)
        assert rel < COLUMN_REL_L2_MAX, f"{name}/{state}: rel-L2 {rel:.3e}"
    else:
        assert np.allclose(got, want, rtol=1e-9, atol=1e-9 * max(1.0, float(
            np.abs(want).max()))), (
            f"{name}/{state}: worst {np.abs(got - want).max():.3e}")


@pytest.mark.parametrize("state", list(STATES))
@pytest.mark.parametrize("name", [n for n in BACKEND_NAMES if n != "numpy"])
def test_traced_decode_matches_the_numpy_decode(name, state):
    """θ → physical values agrees with ``ParameterTable.decode``.

    Separated from the residual test because a decode that is wrong only for a
    *transformed* parameter (softplus width, logit occupancy) can still produce
    a residual that looks fine at θ₀ — the transforms are near-identity in the
    middle of their range.
    """
    xp = backend_or_skip(name)
    built = STATES[state]()
    if built is None:
        pytest.skip(f"dataset for state {state!r} not present")
    model, table, _extras = built
    theta = table.x0()

    want = table.decode(theta)
    with traced.active(xp):     # decode is a building block, not a whole residual
        got = {k: to_host_fp64(v) for k, v in
               make_traced_decode(table, xp)(xp.asarray(theta)).items()}
    assert set(got) == set(want), f"{name}/{state}: decoded paths differ"
    tol = 1e-5 if "mps" in name else 1e-10
    for path, value in want.items():
        assert np.isclose(float(got[path]), value, rtol=tol, atol=tol), (
            f"{name}/{state}/{path}")


def test_every_backend_is_covered_by_the_agreement_matrix():
    """A new backend cannot ship without its Jacobian-agreement rows.

    ``test_cross_backend.METHODS`` is an explicit dict — that is deliberate,
    since each row carries its own bars — so this test is what stops it from
    falling behind the registry.  ``torch-mps`` is the one documented
    exception: its fp32 is the *device's*, not a policy's, so it is compared
    against the torch fp64 Jacobian under reduced-precision bars in
    ``test_backend_torch.py`` rather than against the analytic one here.
    """
    from tests import test_cross_backend as matrix

    covered = {m.split("+")[0] for m in matrix.METHODS} | {"numpy"}
    expected = set(BACKEND_NAMES) - {"torch-mps"}
    missing = expected - covered
    assert not missing, (
        f"backend(s) {sorted(missing)} are in the registry but have no row in "
        "tests/test_cross_backend.py::METHODS — add the row (and its bars) "
        "rather than relaxing this test")


def test_experimental_backends_are_declared_and_optional():
    """The experimental set is exactly the torch pair, and nothing in it is a
    hard dependency: ``BACKEND_REQUIRES`` names an extra for each."""
    assert EXPERIMENTAL_BACKENDS == {"torch", "torch-mps"}
    assert all(BACKEND_REQUIRES.get(n) for n in EXPERIMENTAL_BACKENDS)
    # numpy is never experimental and never optional
    assert "numpy" not in EXPERIMENTAL_BACKENDS
    assert "numpy" not in BACKEND_REQUIRES
    assert isinstance(resolve_backend("numpy"), NumpyBackend)
