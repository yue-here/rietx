"""The compiled tier (WP-1115, a Rust wheel since WP-1940) against the numpy
path it accelerates.

Two things are checked here and they are different in kind.

**The arithmetic**, at the bar each kernel claims in ``model/compiled.py``:

* the **scatter** is bit-identical, and that is not a tolerance dressed up as
  one — no library function enters the sum, so the two implementations perform
  the same IEEE operations in the same order and the assertion is on the raw
  bit pattern;
* the **profile kernels** agree to rounding — 1e-13 relative, WP-1112's bar —
  and on symmetric rows they are bit-identical *where that was measured*.
  Which is a property of the platform rather than of the code: the kernels
  call the C library's ``exp``, numpy its own vectorised routine, and the two
  agree bit for bit on darwin/arm64 against numpy 2.5.2 and miss by ~3e-17 on
  Linux.  The bit is therefore asserted only there, for the same reason
  ``test_backend_shim`` pins its goldens to one platform.  The pad tail is
  excluded from the bit assertion either way: numpy reaches it by multiplying
  the computed value by ``mask``, so a negative value lands on ``-0.0`` there
  while the kernel never writes it at all, and nothing downstream can see the
  difference because the scatter drops the pad.

**The contract**, which is the half a green arithmetic test would not notice: a
build without the wheel, with a wheel of another interface, or with the tier
switched off must produce a working fit rather than an ``ImportError``.  A
decline must also say so, once, and reach ``capabilities()``.  The fallback is
only real if something runs it, so the switch is exercised here and, one rank
up, by every golden in ``tests/test_backend_shim.py``.

What is deliberately *not* asserted: that the compiled path is faster.  Wall
clock belongs in ``examples/bench_refinement.py``, where it is quoted as a
range with its venv and platform (CLAUDE.md § Commands); a timing assertion in
a suite that runs under ``-n auto`` measures the machine, not the change.
"""

from __future__ import annotations

import platform
import sys
import tomllib
import types
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx import Instrument, PatternData
from rietx._about import COMPILED_ENV
from rietx.model import compiled
from rietx.model.forward import BatchLayout, accumulate_planes, compile_model
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.structure import Atom, Cell, Phase, Structure

pytestmark = pytest.mark.skipif(
    not compiled.available(),
    reason=f"the rietx-kernels wheel did not load: {compiled.unavailable()}")


@pytest.fixture(autouse=True)
def _restore_switch():
    """Every test here moves the switch; none may leak it to the next module."""
    was = compiled.set_enabled(None)
    yield
    compiled.set_enabled(was)


def _bits_equal(a, b) -> bool:
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    return a.shape == b.shape and np.array_equal(a.view(np.int64),
                                                 b.view(np.int64))


def _rel(a, b) -> float:
    scale = float(np.abs(b).max()) or 1.0
    return float(np.abs(np.asarray(a) - np.asarray(b)).max()) / scale


def _both(fn):
    """``fn()`` on the numpy path and on the compiled one, in that order."""
    compiled.set_enabled(False)
    want = fn()
    compiled.set_enabled(True)
    return fn(), want


# -- the scatter --------------------------------------------------------------
def _layout(rng, rows: int, w: int, n_points: int) -> BatchLayout:
    i0 = np.sort(rng.integers(0, n_points - w - 1, rows)).astype(np.int64)
    i1 = i0 + rng.integers(max(w // 2, 1), w, rows)
    width = i1 - i0
    w_max = int(width.max())
    ar = np.arange(w_max, dtype=np.int64)[None, :]
    idx = np.minimum(i0[:, None] + ar, np.maximum(i1 - 1, 0)[:, None])
    return BatchLayout(
        il=np.zeros(rows, dtype=np.int64), k=np.arange(rows), i0=i0, i1=i1,
        width=width, w_max=w_max, idx=idx, x=np.zeros((rows, w_max)),
        mask=(ar < width[:, None]).astype(np.float64),
        fcj=np.zeros(rows, dtype=np.int64), buckets={0: np.arange(rows)},
        line_ptr=np.array([0, rows]))


@pytest.mark.parametrize("n_terms", [1, 2, 3, 4])
def test_the_scatter_is_bit_identical_at_every_arity(n_terms):
    """All four arities, because each is a separate branch of the kernel.

    One term is what every intensity-only column and the forward build; four is
    ``_peak_chain_column``'s full set.  A branch written with the two adds
    folded into one expression would pass a tolerance test and fail this.
    """
    rng = np.random.default_rng(11)
    n_points = 4000
    parts = []
    for _ in range(3):
        lay = _layout(rng, 400, 51, n_points)
        terms = [(rng.standard_normal(len(lay.i0)),
                  rng.standard_normal((len(lay.i0), lay.w_max)) * lay.mask)
                 for _ in range(n_terms)]
        parts.append((lay, terms))
    got, want = _both(lambda: accumulate_planes(n_points, parts))
    assert _bits_equal(got, want)


def test_the_scatter_declines_an_arity_it_was_not_written_for():
    """Five terms is not a shape the kernel has a branch for, and the honest
    answer is the numpy expression rather than a wrong sum or a raise."""
    rng = np.random.default_rng(12)
    lay = _layout(rng, 50, 21, 500)
    terms = [(rng.standard_normal(len(lay.i0)),
              rng.standard_normal((len(lay.i0), lay.w_max)) * lay.mask)
             for _ in range(compiled.MAX_TERMS + 1)]
    compiled.set_enabled(True)
    assert compiled.accumulate(500, [(lay, terms)]) is None
    got, want = _both(lambda: accumulate_planes(500, [(lay, terms)]))
    assert _bits_equal(got, want)


# -- the profile kernels ------------------------------------------------------
def _model(*, axial: bool):
    phases = [
        Phase(name="a", space_group="P21/c",
              cell=Cell(a=Parameter(value=5.2), b=Parameter(value=6.4),
                        c=Parameter(value=7.8), alpha=Parameter(value=90.0),
                        beta=Parameter(value=105.0),
                        gamma=Parameter(value=90.0)),
              atoms=[Atom(label="Fe", species="Fe", x=Parameter(value=0.0),
                          y=Parameter(value=0.0), z=Parameter(value=0.0)),
                     Atom(label="C", species="C", x=Parameter(value=0.23),
                          y=Parameter(value=0.31), z=Parameter(value=0.42))],
              scale=Parameter(value=1e-3)),
    ]
    if axial:
        ins = Instrument.bragg_brentano(radiation="CuKa",
                                        goniometer_radius_mm=173.0)
        ins.geometry.axial_sl.value = 0.025
        ins.geometry.axial_hl.value = 0.030
    else:
        ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 1e-2
    structure = Structure(phases=phases)
    grid = np.arange(10.0, 90.0, 0.02)
    pattern = PatternData(two_theta=grid.tolist(),
                          intensity=np.zeros_like(grid).tolist())
    model = compile_model(structure, ins, pattern)
    table = ParameterTable(structure, ins)
    return model, table.decode(table.x0())


def test_symmetric_rows_land_on_the_numpy_doubles():
    """A symmetric row is a straight transcription, so the only thing that can
    move it is ``exp``, and whether that moves it is a **property of the
    platform, not of the code**.

    The kernels call the C library's ``exp``; numpy calls its own vectorised
    routine.  Measured: they agree bit for bit on darwin/arm64 against numpy
    2.5.2, and miss by ~3e-17 relative on Linux — which cost a CI round, and is
    why the bar this test enforces everywhere is the rounding one.  The bit is
    asserted only where it was measured, on the same platform and for the same
    reason ``test_backend_shim``'s goldens are pinned to one: it is a real
    property worth not losing silently, and it is not portable.

    In window only, either way: see the module docstring on the pad tail.
    """
    model, values = _model(axial=False)
    assert not any(np.any(cp.batch.fcj > 0) for cp in model.phases)
    got, want = _both(lambda: model.derivative_bases(values))
    on_the_measured_platform = (sys.platform, platform.machine()) == ("darwin",
                                                                     "arm64")
    for gp, wp in zip(got.planes, want.planes):
        inwin = gp.layout.mask > 0
        for name in ("omega", "d_pos", "d_gamma", "d_eta"):
            a, b = getattr(gp, name)[inwin], getattr(wp, name)[inwin]
            assert _rel(a, b) < 1e-15, f"{name} past the rounding bar"
            if on_the_measured_platform:
                assert _bits_equal(a, b), (
                    f"{name} moved off the numpy bits on darwin/arm64, where "
                    "they were measured identical — a transcription changed")


def test_the_forward_and_the_bases_keep_their_separate_spellings():
    """Ω from the forward and Ω from the bases must stay 1-2 ulp apart.

    They are built by the same kernel under different ``spell`` flags, which is
    exactly the way to lose the distinction by accident — one shared code path
    and one forgotten argument.  Two guards, and the second is deliberately
    platform-gated rather than dressed up as portable.

    **That the two spells produce different output** is checkable anywhere and
    catches the likeliest mistake, a forgotten argument leaving both callers on
    one spelling.  **Which of them is which** cannot be established by
    magnitude off the measured platform, and pretending otherwise would be the
    weakest kind of green: the gap between the spellings is 1-2 ulp, and so is
    the gap between the C library's ``exp`` and numpy's, so on Linux "used the other
    spelling" and "used the right one" are literally the same size — measured
    at 2.87e-17 against a 5.74e-17 spelling gap, a factor of two.  On
    darwin/arm64, where ``exp`` agrees, each compiled Ω is bit-equal to its own
    numpy function and a swap is unmissable.  So that is where the identity is
    asserted, on the same argument that pins ``test_backend_shim``'s goldens to
    one platform.
    """
    model, values = _model(axial=False)

    def pair():
        fwd = model._phase_component_batched(0, values)
        omega = model.derivative_bases(values, profile_derivs=False).planes[0]
        inten = omega.inten
        bas = accumulate_planes(len(model.tt),
                                [(omega.layout, [(inten, omega.omega)])])
        return fwd, bas

    (g_fwd, g_bas), (w_fwd, w_bas) = _both(pair)
    assert not _bits_equal(w_fwd, w_bas), \
        "the numpy spellings stopped differing — this guard proves nothing"
    assert not _bits_equal(g_fwd, g_bas), \
        "the compiled kernel lost the spelling distinction"
    if (sys.platform, platform.machine()) == ("darwin", "arm64"):
        assert _bits_equal(g_fwd, w_fwd), \
            "the compiled forward stopped reproducing pseudo_voigt"
        assert _bits_equal(g_bas, w_bas), \
            "the compiled bases Ω stopped reproducing _components"


def test_fcj_rows_agree_to_rounding_on_every_plane():
    """Including the two axial planes, which are node-FD differences divided by
    1e-7 and so the place a last-digit disagreement is most amplified."""
    model, values = _model(axial=True)
    assert any(np.any(cp.batch.fcj > 0) for cp in model.phases)
    got, want = _both(lambda: model.derivative_bases(values))
    for gp, wp in zip(got.planes, want.planes):
        for name in ("omega", "d_pos", "d_gamma", "d_eta", "d_sl", "d_hl"):
            a, b = getattr(gp, name), getattr(wp, name)
            assert (a is None) == (b is None), f"{name} present on one path only"
            if a is None:
                continue
            assert _rel(a, b) < 1e-13, f"{name} past the rounding bar"


def test_the_forward_agrees_with_the_scalar_loop_on_fcj_data():
    """The oracle chain, end to end: the compiled path against the
    per-reflection loop that neither batching nor compiling may drift from."""
    model, values = _model(axial=True)
    compiled.set_enabled(True)
    for ip in range(len(model.phases)):
        got = model._phase_component_batched(ip, values)
        want = model._phase_component_scalar(ip, values)
        assert _rel(got, want) < 1e-13


# -- the pool -----------------------------------------------------------------
def test_the_pool_engages_on_work_never_on_rows():
    """The 512-row floor this replaced (WP-1940) was wrong both ways.  No call
    of the trigger fit reached it, so its 1.6 ms FCJ calls ran on one core,
    while a 512-row symmetric call over a narrow window is tens of µs of work
    that splitting slows to 0.2-0.5×."""
    def splits(kernel, n_rows, nodes, width, w_max):
        return compiled._splits(kernel, np.arange(n_rows),
                                np.full(n_rows, width, dtype=np.int64), nodes,
                                w_max)

    # the trigger fit's largest FCJ call, measured at 1.6 ms (omega) inline
    assert splits("omega_fcj", 494, 8, 151, 167)
    assert splits("bases_fcj", 494, 8, 151, 167)
    # more rows than the old floor, too little work to pay for the dispatch
    assert not splits("omega_sym", 512, 1, 20, 30)
    assert not splits("bases_sym", 512, 1, 20, 30)
    # one padded bound, two summed widths: the sum decides, not the padding
    assert not splits("omega_sym", 2000, 1, 10, 100)
    assert splits("omega_sym", 2000, 1, 50, 100)


@pytest.mark.parametrize("axial", [False, True])
def test_a_split_call_lands_on_the_inline_bits(monkeypatch, axial):
    """Rows are disjoint and each is computed whole inside one chunk, so where
    the threshold sits must not move a bit of any plane.  Asserted with every
    call forced through a four-worker pool, since the suite runs one kernel
    thread per xdist worker and would otherwise never split at all.

    ``axial=False`` reaches the two symmetric kernels, ``axial=True`` the two
    FCJ ones with the axial planes built.
    """
    model, values = _model(axial=axial)
    compiled.set_enabled(True)

    def planes():
        out = [model._phase_component_batched(ip, values)
               for ip in range(len(model.phases))]
        for p in model.derivative_bases(values).planes:
            out += [a for a in (p.omega, p.d_pos, p.d_gamma, p.d_eta, p.d_sl,
                                p.d_hl) if a is not None]
        return out

    monkeypatch.setattr(compiled, "_THREAD_MIN_NS", float("inf"))
    want = planes()
    pool = ThreadPoolExecutor(max_workers=4)
    real, submitted = pool.submit, []
    monkeypatch.setattr(
        pool, "submit", lambda *a: submitted.append(a) or real(*a))
    monkeypatch.setattr(compiled, "_POOL", pool)
    monkeypatch.setattr(compiled, "_POOL_WORKERS", 4)
    monkeypatch.setattr(compiled, "_THREAD_MIN_NS", 0.0)
    real_splits, split = compiled._splits, set()

    def counted(kernel, *a):
        s = real_splits(kernel, *a)
        if s:
            split.add(kernel)
        return s

    monkeypatch.setattr(compiled, "_splits", counted)
    try:
        got = planes()
    finally:
        pool.shutdown()
    assert submitted, "nothing reached the pool, so nothing was compared"
    reached = ({"omega_fcj", "bases_fcj"} if axial
               else {"omega_sym", "bases_sym"})
    assert reached <= split, f"never split: {sorted(reached - split)}"
    assert len(got) == len(want)
    for g, w in zip(got, want):
        assert _bits_equal(g, w)


# -- the contract -------------------------------------------------------------
def test_the_switch_turns_the_tier_off_without_a_reinstall():
    """``RIETX_COMPILED=0``'s python-level twin: the knob a user who cannot run
    the compiled tier reaches for, since an extra could not have removed it."""
    compiled.set_enabled(False)
    assert not compiled.enabled()
    model, values = _model(axial=True)
    assert np.isfinite(model.evaluate(values)).all()
    compiled.set_enabled(True)
    assert compiled.enabled()


def _fresh_load(monkeypatch, wheel=None, *, absent=False):
    """Forget this process's load and warning, with ``wheel`` (or no wheel at
    all) where ``import rietx_kernels`` will look.  ``monkeypatch`` puts the
    real module and every latch back after the test."""
    monkeypatch.setattr(compiled, "_KERNELS", None)
    monkeypatch.setattr(compiled, "_UNAVAILABLE", None)
    monkeypatch.setattr(compiled, "_WARNED", False)
    if absent:
        # ``None`` in sys.modules makes the import raise, as a missing wheel does
        monkeypatch.setitem(sys.modules, "rietx_kernels", None)
    elif wheel is not None:
        monkeypatch.setitem(sys.modules, "rietx_kernels", wheel)


def _wheel(**changes):
    """A stand-in for the wheel: the real one's names, with ``changes`` applied
    and a ``None`` change deleting the name."""
    import rietx_kernels

    fake = types.ModuleType("rietx_kernels")
    for name in ("__version__", "KERNEL_ABI", *compiled.KERNEL_NAMES):
        setattr(fake, name, getattr(rietx_kernels, name))
    for name, value in changes.items():
        if value is None:
            delattr(fake, name)
        else:
            setattr(fake, name, value)
    return fake


def test_a_build_without_the_wheel_still_fits(monkeypatch):
    """The soft import is why the wheel can be a hard dependency and a
    ``--no-deps`` install still work, so the test removes the wheel rather than
    reading the code and believing it."""
    model, values = _model(axial=True)
    compiled.set_enabled(True)
    want = model.evaluate(values)
    _fresh_load(monkeypatch, absent=True)
    assert not compiled.available()
    assert compiled.unavailable().startswith(
        "importing rietx_kernels raised ModuleNotFoundError")
    assert compiled.accumulate(len(model.tt), []) is None
    got = model.evaluate(values)
    assert _rel(got, want) < 1e-13


def test_a_wheel_of_another_interface_is_declined_by_both_numbers(monkeypatch):
    """pip's ``<N+1`` refuses this first; the integer check is for an install
    that went round the resolver, and its reason must name both sides."""
    other = compiled.KERNEL_ABI + 1
    _fresh_load(monkeypatch, _wheel(KERNEL_ABI=other, __version__=f"{other}.0.0"))
    assert not compiled.available()
    why = compiled.unavailable()
    assert f"rietx_kernels {other}.0.0 has kernel interface {other}" in why
    assert f"this rietx calls interface {compiled.KERNEL_ABI}" in why


def test_a_wheel_lacking_a_kernel_is_declined_by_name(monkeypatch):
    """A kernel the wheel lacks declines the whole tier, as a wrong interface
    number does.  Serving the other four would make which path ran a function
    of which kernel a call reached."""
    _fresh_load(monkeypatch, _wheel(bases_fcj=None, omega_sym="not a kernel"))
    assert not compiled.available()
    assert compiled.unavailable().endswith("lacks the kernels omega_sym, bases_fcj")
    assert compiled.bases_fcj(*[None] * 16) is False


def test_a_decline_warns_once_and_never_when_the_numpy_path_was_chosen(
        monkeypatch):
    """A tier that did not run must say so (WP-1521), once a process, and only
    when it was wanted.  ``RIETX_COMPILED=0`` and :func:`set_enabled` are both
    a choice of the numpy path, so neither warns."""
    monkeypatch.delenv(COMPILED_ENV, raising=False)
    _fresh_load(monkeypatch, absent=True)
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        compiled.set_enabled(None)
        assert not compiled.enabled()
        compiled.set_enabled(None)
        assert not compiled.enabled()
        compiled.set_enabled(True)
        compiled.enabled()
    runtime = [w for w in seen if issubclass(w.category, RuntimeWarning)]
    assert len(runtime) == 1, [str(w.message) for w in runtime]
    text = str(runtime[0].message)
    assert compiled.unavailable() in text
    pin = f"rietx-kernels>={compiled.KERNEL_ABI},<{compiled.KERNEL_ABI + 1}"
    assert f'pip install "{pin}"' in text
    assert f"{COMPILED_ENV}=0" in text

    monkeypatch.setenv(COMPILED_ENV, "0")
    _fresh_load(monkeypatch, absent=True)
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        compiled.set_enabled(None)
        assert not compiled.enabled()
        assert not compiled.available()
    assert not [w for w in seen if issubclass(w.category, RuntimeWarning)]


def test_capabilities_says_why_the_kernels_did_not_load(monkeypatch):
    """The flag says the build is slow; the reason says what to do about it."""
    assert rx.capabilities().compiled_kernels_unavailable is None
    _fresh_load(monkeypatch, _wheel(KERNEL_ABI=compiled.KERNEL_ABI + 1))
    compiled.set_enabled(None)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        caps = rx.capabilities()
    assert caps.features["compiled_kernels_active"] is False
    assert caps.features["compiled_kernels"] is False
    assert caps.compiled_kernels_unavailable == compiled.unavailable()
    assert "kernel interface" in caps.compiled_kernels_unavailable
    # forcing the switch on cannot make a declined tier run (WP-1521)
    compiled.set_enabled(True)
    assert rx.capabilities().features["compiled_kernels_active"] is False


def test_the_pin_is_the_kernel_interface_and_numba_is_gone():
    """``pyproject``'s range and :data:`compiled.KERNEL_ABI` are one number
    written twice, so a bump of either alone fails here."""
    path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    project = tomllib.loads(path.read_text(encoding="utf-8"))["project"]
    deps = project["dependencies"]
    abi = compiled.KERNEL_ABI
    assert [d for d in deps if d.startswith("rietx-kernels")] == [
        f"rietx-kernels>={abi},<{abi + 1}"]
    every = deps + [d for extra in project["optional-dependencies"].values()
                    for d in extra]
    assert not [d for d in every if d.lower().startswith(("numba", "llvmlite"))]


def test_the_thread_count_is_settable_and_never_zero(monkeypatch):
    """A pool of zero workers raises, and the environment is a stranger's."""
    from rietx._about import COMPILED_THREADS_ENV

    for raw, want in (("1", 1), ("4", 4), ("0", 1), ("-3", 1), ("", None),
                      ("many", None)):
        monkeypatch.setenv(COMPILED_THREADS_ENV, raw)
        got = compiled.n_threads()
        assert got >= 1
        if want is not None:
            assert got == want, f"{raw!r} gave {got}"
