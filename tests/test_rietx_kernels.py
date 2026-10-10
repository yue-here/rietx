"""The ``rietx_kernels`` wheel refuses every call its raw writes cannot survive.

The crate writes its output planes through raw pointers (``kernels/src/lib.rs``
says why), so a call numba would have run wrongly (before WP-1940) is, in
Rust, undefined behaviour or a wrapped index.  Each binding therefore checks its arguments
before releasing the GIL.  Every case below is one well-formed call with one
defect, and the well-formed call itself is the control, so a blanket refusal
cannot pass.

Whether the kernels' *arithmetic* is right is ``test_compiled_kernels.py``'s
question, asked through ``model.compiled``, and the agreement pass in
``examples/aot_spike/bench_aot_kernels.py`` asks it inside real fits.
"""

from __future__ import annotations

import numpy as np
import pytest

rk = pytest.importorskip("rietx_kernels")

N, W, NN = 6, 9, 5
ROWS = np.array([0, 2, 3, 5], dtype=np.int64)


def _i64(*v):
    return np.array(v, dtype=np.int64)


@pytest.fixture
def fcj():
    """A well-formed ``omega_fcj`` call, by keyword."""
    rng = np.random.default_rng(0)
    x = np.sort(rng.uniform(10, 12, (N, W)), axis=1)
    pos = x[:, W // 2].copy()
    return dict(
        out=np.zeros((N, W)), x=x, rows=ROWS.copy(),
        w1=rng.uniform(0.05, 0.1, N), w2=rng.uniform(0.1, 0.9, N),
        width=_i64(9, 7, 9, 4, 9, 8),
        phi=pos[ROWS][:, None] + rng.normal(0, 0.01, (len(ROWS), NN)),
        om=rng.uniform(0, 1, (len(ROWS), NN)), spell=1, lo=0, hi=len(ROWS))


def _read_only(a):
    a.setflags(write=False)
    return a


def _overlapping_x(c):
    """``out`` and ``x`` as two views of one buffer, a row apart."""
    big = np.vstack([c["x"], c["x"][:1]])
    c["out"], c["x"] = big[1:], big[:N]


# one defect each, applied to the well-formed call
DEFECTS = {
    "out is x": (lambda c: c.update(out=c["x"]), "shares memory"),
    "out overlaps x": (_overlapping_x, "shares memory"),
    "out overlaps phi": (lambda c: c.update(
        phi=c["out"].reshape(-1)[:len(ROWS) * NN].reshape(len(ROWS), NN)),
        "shares memory"),
    "Fortran-ordered x": (lambda c: c.update(x=np.asfortranarray(c["x"])),
                          "x must be C-contiguous"),
    "om narrower than phi": (lambda c: c.update(om=c["om"][:, :-1].copy()),
                             "om has shape"),
    "phi short of rows": (lambda c: c.update(phi=c["phi"][:-1].copy(),
                                             om=c["om"][:-1].copy()),
                          "phi has 3"),
    "negative row": (lambda c: c.update(rows=_i64(0, -1, 3, 5)), "row -1"),
    "row past x": (lambda c: c.update(rows=_i64(0, N, 3, 5)), f"row {N}"),
    # two pool chunks of one call would write row 2 at once
    "repeated row": (lambda c: c.update(rows=_i64(0, 2, 3, 2), lo=0, hi=2),
                     "row 2 appears twice"),
    "negative width": (lambda c: c.update(width=_i64(9, 7, -1, 4, 9, 8)),
                       "window width -1"),
    "width past x": (lambda c: c.update(width=_i64(9, 7, W + 1, 4, 9, 8)),
                     "window width"),
    "hi past rows": (lambda c: c.update(hi=len(ROWS) + 1), "row range"),
    "lo past hi": (lambda c: c.update(lo=3, hi=2), "row range"),
    "w1 short": (lambda c: c.update(w1=c["w1"][:-1].copy()), "w1 has"),
    "unknown spell": (lambda c: c.update(spell=2), "spell 2"),
    "read-only out": (lambda c: c.update(out=_read_only(c["out"])),
                      "out must be writeable"),
    "out misshapen": (lambda c: c.update(out=np.zeros((N, W + 1))),
                      "out has shape"),
}


def test_the_well_formed_call_is_accepted_and_writes_its_rows(fcj):
    rk.omega_fcj(**fcj)
    written = np.flatnonzero(fcj["out"].any(axis=1))
    assert written.tolist() == ROWS.tolist()


@pytest.mark.parametrize("defect", DEFECTS)
def test_one_defect_is_refused_by_name(fcj, defect):
    apply, says = DEFECTS[defect]
    apply(fcj)
    with pytest.raises(ValueError, match=says):
        rk.omega_fcj(**fcj)


def test_two_basis_outputs_may_not_share_a_plane(fcj):
    z = np.zeros((N, W))
    pos = fcj["x"][:, W // 2].copy()
    tail = (fcj["x"], ROWS, pos, fcj["w1"], fcj["w2"], fcj["width"], 0,
            len(ROWS))
    rk.bases_sym(z, np.zeros_like(z), np.zeros_like(z), np.zeros_like(z), *tail)
    with pytest.raises(ValueError, match="two output planes share memory"):
        rk.bases_sym(z, z, np.zeros_like(z), np.zeros_like(z), *tail)


def test_the_axial_planes_are_checked_only_when_they_are_read(fcj):
    """Without ``has_ax`` the caller passes (0, 0) placeholders for the four
    axial node planes and both axial outputs, and they must pass; with it, a
    placeholder where a plane belongs is refused."""
    e = np.zeros((0, 0))
    outs = [np.zeros((N, W)) for _ in range(4)]
    nodes = (fcj["phi"], fcj["om"], fcj["phi"] * 0.5, fcj["om"] * 0.5)
    head = (fcj["x"], ROWS, fcj["w1"], fcj["w2"], fcj["width"], *nodes)
    rk.bases_fcj(*outs, e, e, *head, e, e, e, e, False, 0, len(ROWS))
    with pytest.raises(ValueError, match="dphi_sl has shape"):
        rk.bases_fcj(*outs, np.zeros((N, W)), np.zeros((N, W)), *head,
                     e, *nodes[1:], True, 0, len(ROWS))


def _scatter(y, i0, i1, coefs, n_terms):
    rng = np.random.default_rng(1)
    planes = rng.uniform(0, 1, (4, 3, 8))
    e1, e2 = np.zeros(0), np.zeros((0, 0))
    args = []
    for t in range(4):
        live = t < min(n_terms, 4)
        args += [coefs if live else e1, planes[t] if live else e2]
    rk.accum(y, i0, i1, *args, n_terms)


SCATTER = {
    "window wider than a plane": (dict(i1=_i64(4, 14, 20)), "not inside"),
    "window past y": (dict(y=np.zeros(19)), "window end 20"),
    "negative start": (dict(i0=_i64(-1, 5, 12)), "window start -1"),
    "no terms": (dict(n_terms=0), "n_terms 0"),
    "five terms": (dict(n_terms=5), "n_terms 5"),
    "short coefficients": (dict(coefs=np.ones(2)), "c0 has 2"),
}


@pytest.mark.parametrize("defect", SCATTER)
def test_the_scatter_refuses_a_window_it_cannot_hold(defect):
    call = dict(y=np.zeros(30), i0=_i64(0, 5, 12), i1=_i64(4, 12, 20),
                coefs=np.ones(3), n_terms=2)
    _scatter(**call)
    change, says = SCATTER[defect]
    call.update(change)
    with pytest.raises(ValueError, match=says):
        _scatter(**call)


def test_the_kernel_interface_is_the_major_version():
    assert rk.KERNEL_ABI == int(rk.__version__.split(".")[0])
