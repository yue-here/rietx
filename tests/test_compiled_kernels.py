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
  Which is a property of the platform rather than of the code: the symmetric
  kernels call the C library's ``exp``, numpy its own vectorised routine, and
  the two agree bit for bit on darwin/arm64 against numpy 2.5.2 and miss by
  ~3e-17 on Linux.  The bit is therefore asserted only there, for the same
  reason ``test_backend_shim`` pins its goldens to one platform.  The pad tail
  is excluded from the bit assertion either way: numpy reaches it by
  multiplying the computed value by ``mask``, so a negative value lands on
  ``-0.0`` there while the kernel never writes it at all, and nothing
  downstream can see the difference because the scatter drops the pad.  From
  ``rietx-kernels`` 1.2.0 the FCJ kernels on x86-64 call SLEEF's ``exp``,
  held to its documented 1.0 ulp (WP-1940 § The relaxed rule);
* and a **whole fit** on the kernels lands where the numpy path's does, its
  parameters in esd units and its curve in σ, both under runaway bars.

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

import importlib.util
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


def _rel(a, b, scale=None) -> float:
    """The largest difference over ``scale``, or over ``b``'s largest value."""
    scale = scale or float(np.abs(b).max()) or 1.0
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
def _model(*, axial: bool, hl: float = 0.030):
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
        ins.geometry.axial_hl.value = hl
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

    The symmetric kernels call the C library's ``exp``; numpy calls its own vectorised
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


FCJ_PLANES = ("omega", "d_pos", "d_gamma", "d_eta", "d_sl", "d_hl")


@pytest.fixture(scope="module")
def aot_bench():
    """``examples/aot_spike/bench_aot_kernels.py``, whose ``fcj_terms`` is the
    FCJ bases' bar denominator in both places."""
    path = (Path(__file__).resolve().parent.parent / "examples" / "aot_spike"
            / "bench_aot_kernels.py")
    spec = importlib.util.spec_from_file_location("bench_aot_kernels", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_one_agreeing_numpy_pair_does_not_make_a_noisy_platform_checkable(
        aot_bench):
    """The gate's twins check, as run 41378211395 read it on macOS x86_64.

    The numpy path agreed with itself on trigger in that run and the twins sat
    3.0e-06 esd away, the size of the numpy path's own differences there.  One
    agreeing pair does not show the path is deterministic, so on a platform in
    ``NONDETERMINISTIC`` the gap is reported.  Where the path is deterministic
    the same readings still fail the gate.
    """
    gap = "max 3.0e-06 esd, 7 with the same value and another esd"
    noise = "max 1.7e-07 esd, 7 with the same value and another esd"
    verdict = aot_bench.twins_verdict
    assert ("darwin", "x86_64") in aot_bench.NONDETERMINISTIC
    assert verdict(gap, "bit-identical", nondeterministic=True) == "unchecked"
    assert verdict(gap, "bit-identical", nondeterministic=False) == "drifted"
    assert verdict(gap, noise, nondeterministic=False) == "unchecked"
    for noisy in (True, False):
        assert verdict("bit-identical", noise, noisy) == "same"
        assert verdict("bit-identical", "bit-identical", noisy) == "same"


@pytest.mark.parametrize("hl", [0.030, 0.0])
def test_fcj_rows_agree_to_rounding_on_every_plane(aot_bench, monkeypatch, hl):
    """Including the two axial planes, which are node-FD differences divided by
    1e-7 and so the place a last-digit disagreement is most amplified.

    Each plane is held to its terms, the bench's :func:`fcj_terms`.  Two
    correct sums differ by about ε times their terms, and at H/L = 0 beside
    S/L > 0 (WP-1953) the ∂Ω/∂(H/L) plane is far smaller than its terms.  On
    this model it is 2.3e5 times smaller, and measured against its own size
    the gap is 4.2e-11, past the bar.  Against its terms it is 1.8e-16
    (darwin/arm64).
    """
    model, values = _model(axial=True, hl=hl)
    assert any(np.any(cp.batch.fcj > 0) for cp in model.phases)
    compiled.set_enabled(False)
    want = model.derivative_bases(values)
    compiled.set_enabled(True)
    wheel, terms = compiled._kernels(), dict.fromkeys(FCJ_PLANES, 0.0)

    def kernel(*args):
        wheel["bases_fcj"](*args)
        for name, t in zip(FCJ_PLANES, aot_bench.fcj_terms(args)):
            if t is not None and t.size:
                terms[name] = max(terms[name], float(t.max()))

    # one call a bucket, so ``terms`` is never written from two threads
    monkeypatch.setattr(compiled, "_THREAD_MIN_NS", float("inf"))
    monkeypatch.setattr(compiled, "_KERNELS", {**wheel, "bases_fcj": kernel})
    got = model.derivative_bases(values)
    for gp, wp in zip(got.planes, want.planes):
        for name in FCJ_PLANES:
            a, b = getattr(gp, name), getattr(wp, name)
            assert (a is None) == (b is None), f"{name} present on one path only"
            if a is None:
                continue
            assert terms[name] > 0, f"{name} built with no kernel call behind it"
            assert _rel(a, b, terms[name]) < 1e-13, f"{name} past the rounding bar"
    if hl == 0.0:
        # the case this one exists for: the plane is far smaller than its terms
        d_hl = max(float(np.abs(p.d_hl).max()) for p in want.planes
                   if p.d_hl is not None)
        assert terms["d_hl"] / d_hl > 1e3, "H/L = 0 no longer cancels here"


#: The bound on the FCJ kernels' ``exp``, in ulps of the true value: SLEEF's
#: documented 1.0 for the ``xexp`` they call on x86-64 from ``rietx-kernels``
#: 1.2.0 (``kernels/src/sleef.rs``).  The worst of the points below is 0.927,
#: at ``exp(425.2…)``.  On arm64 they call the C library's, measured at 0.509
#: on darwin/arm64, and the same bar holds it.
EXP_BOUND_ULPS = 1.0


def _wheel_exp():
    import rietx_kernels

    if not hasattr(rietx_kernels, "exp"):
        pytest.skip(f"rietx-kernels {rietx_kernels.__version__} predates "
                    "exposing the FCJ kernels' exponential (1.2.0)")
    return rietx_kernels.exp


def test_the_fcj_exponential_holds_its_stated_bound():
    """The relaxed rule's first clause (WP-1940): a transcendental is held to a
    stated bound, here 1.0 ulp against the true value, on each wheel's own
    platform: SLEEF's on x86-64, the C library's on arm64.  The reference is :mod:`decimal` at 60 digits, so it is the
    exact value and not another library's rounding of it.

    The points cover every regime the Gaussian exponent reaches, which is
    never positive: subnormal results, the wide windows' far tails, the core,
    tiny arguments, and the edges of the range reduction, ``(k + ½)·ln 2``.
    """
    from decimal import Decimal, localcontext

    exp = _wheel_exp()
    rng = np.random.default_rng(1940)
    x = np.concatenate([
        rng.uniform(-745.2, -708.4, 500),
        rng.uniform(-708.4, -40.0, 1000),
        rng.uniform(-40.0, 0.0, 1500),
        -np.exp(rng.uniform(np.log(1e-300), np.log(0.1), 300)),
        rng.uniform(0.0, 709.7, 200),
        (np.arange(-1074, 1024, 7) + 0.5) * np.log(2.0),
    ])
    got = np.empty_like(x)
    exp(got, x)
    worst, at = 0.0, None
    with localcontext() as ctx:
        ctx.prec = 60
        for a, b in zip(x.tolist(), got.tolist()):
            true = Decimal(a).exp()
            err = float(abs(Decimal(b) - true) / Decimal(np.spacing(float(true))))
            if err > worst:
                worst, at = err, a
    assert worst <= EXP_BOUND_ULPS, f"{worst:.3f} ulp at exp({at!r})"

    # SLEEF decides these by selection, not by its polynomial
    edges = np.array([0.0, -0.0, -np.inf, np.inf, np.nan, -1000.0001, 709.79])
    got = np.empty_like(edges)
    exp(got, edges)
    assert _bits_equal(got[:4], [1.0, 1.0, 0.0, np.inf])
    assert np.isnan(got[4]) and got[5] == 0.0 and got[6] == np.inf


def test_the_avx2_and_baseline_builds_give_the_same_bits():
    """``kernels/src/fcj.rs`` builds the x86-64 FCJ loops twice and says the
    two agree, because no fused operation enters either.  Every CI runner has
    AVX2, so the baseline build would otherwise never run; the wheel's
    ``force_baseline`` hook runs it, and every plane must match to the bit."""
    import rietx_kernels

    if not hasattr(rietx_kernels, "force_baseline"):
        pytest.skip(f"rietx-kernels {rietx_kernels.__version__} has one build")
    if platform.machine().lower() not in ("x86_64", "amd64"):
        pytest.skip("the FCJ loops have one build off x86-64")
    model, values = _model(axial=True)
    compiled.set_enabled(True)

    def planes(baseline: bool):
        was = rietx_kernels.force_baseline(baseline)
        try:
            b = model.derivative_bases(values)
            out = [model._phase_component_batched(0, values)]
            for p in b.planes:
                inwin = p.layout.mask > 0
                out += [getattr(p, name)[inwin] for name in
                        ("omega", "d_pos", "d_gamma", "d_eta", "d_sl", "d_hl")
                        if getattr(p, name) is not None]
            return out
        finally:
            rietx_kernels.force_baseline(was)

    for a, b in zip(planes(False), planes(True), strict=True):
        assert _bits_equal(a, b), "the AVX2 and baseline builds disagree"


def test_the_forward_agrees_with_the_scalar_loop_on_fcj_data():
    """The oracle chain, end to end: the compiled path against the
    per-reflection loop that neither batching nor compiling may drift from."""
    model, values = _model(axial=True)
    compiled.set_enabled(True)
    for ip in range(len(model.phases)):
        got = model._phase_component_batched(ip, values)
        want = model._phase_component_scalar(ip, values)
        assert _rel(got, want) < 1e-13


# -- a whole fit --------------------------------------------------------------
#: The fit-level guard's two bars (WP-1940 § The relaxed rule, item 3), each a
#: runaway guard and never a tolerance.  The trigger fit lands 0.42 esd from
#: the numpy path's on Linux x86-64 with 1.2.0's SLEEF ``exp`` (0.34 on 1.1.0),
#: and 0.22 on darwin/arm64, whose 1.2.0 build is 1.1.0's.  A SLEEF build for
#: arm64, which does not ship, measured 0.53.  All of it lies along one ridge:
#: the instrument's Lorentzian ``x`` against the phases' ``lor_size``, which
#: broaden alike.  The curve stays within 9.8e-5 σ there.  cpd-1a has no FCJ
#: rows and lands on the numpy path's bits on darwin/arm64, yet its curve
#: moved 1.68e-2 σ on the macOS x86-64 runner (i7-8700B, numpy 2.4.6) and
#: under 1e-2 σ when the same job reran: there a fit's stopping point is not
#: even repeatable (the bench's docstring).  That is the widest gap measured,
#: and the curve bar sits 15× above it.
FIT_THETA_ESD = 5.0
FIT_CURVE_SIGMA = 0.25

#: The paths compared in esd units leave out the width blocks, which the
#: trigger plan frees in sets the data cannot split.  Γ_G² =
#: (u + gauss_strain)·tan²θ + v·tanθ + w + gauss_size·(1 + tan²θ)
#: (``caglioti.gaussian_fwhm``), so each phase's peaks see only
#: w + gauss_size and u + gauss_strain + gauss_size.  With u, w and every
#: phase's two terms free, w trades against the gauss_sizes and u against
#: the gauss_strains at no cost, up to the floors.  Since WP-1938 the two
#: paths stop at different points of that set: w 0.00449 with every
#: gauss_size near 0 on numpy, w 5.3e-8 with each gauss_size near 0.0045 on
#: the kernels (darwin/arm64, ``[dev,jax]``).  χ²_red agrees to 2.7e-9
#: relative and the curve to 1.6e-4 σ, while the numpy end's esds, taken at
#: a corner of the set, put the gap at 54 esd.  On that run every other
#: parameter moved 0.11 esd at most (``profile.x``, now left out below).
#: The curve bar still covers every width in both blocks.
#:
#: The Lorentzian block is the same set.  Γ_L = (x + lor_size)/cosθ +
#: (y + lor_strain)·tanθ (``forward.py``'s phase loop), and the plan frees x,
#: y and every phase's two terms in one stage, so x trades against the
#: lor_sizes and y against the lor_strains at no cost.  Linux x86-64's Kernels
#: job put ``profile.x`` 181 esd apart once and passed on the same source
#: twice before it.  A start 1e-14 away does it on darwin/arm64: x at 0 and
#: every lor_size 0.0448 higher, while every other parameter agrees to 0.01
#: esd and the curve to 1.2e-4 σ.
WIDTH_NULL_SET = ("instrument.profile.u", "instrument.profile.w",
                  "instrument.profile.x", "instrument.profile.y")
WIDTH_NULL_SUFFIXES = (".gauss_size", ".gauss_strain", ".lor_size", ".lor_strain")


@pytest.fixture(scope="module")
def bench():
    """``examples/bench_refinement.py`` imported once for both cases, as
    ``test_bench_refinement.py``'s fixture of the same name imports it."""
    path = Path(__file__).resolve().parent.parent / "examples" / "bench_refinement.py"
    spec = importlib.util.spec_from_file_location("bench_refinement", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["bench_refinement"] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.slow
@pytest.mark.parametrize("case", ["trigger", "cpd-1a"])
def test_a_fit_on_the_kernels_lands_where_the_numpy_path_does(bench, case):
    """The relaxed rule's third clause: the two spike fits, once on each path.

    A last-bit difference in the kernels is amplified by the solver into where
    it stops, so the parameters are compared in esd units against a bar
    several times the measured gap, and the fitted curves in units of σ, which
    do not move along a flat direction.  The kernel bars above are the sharp
    test.  This one says a fit on the kernels is still the numpy path's fit.
    """
    try:
        setup = {"trigger": bench._trigger, "cpd-1a": bench._cpd_1a}[case]()
    except FileNotFoundError as exc:
        pytest.skip(str(exc))

    def fit(on: bool):
        compiled.set_enabled(on)
        ref = rx.Refinement(setup.structure.model_copy(deep=True),
                            setup.instrument.model_copy(deep=True), history=False)
        return ref.fit(setup.data, plan=setup.plan, mode=setup.mode,
                       two_theta_limits=setup.limits)

    want, got = fit(False), fit(True)
    w = {p.path: p for p in want.parameters}
    g = {p.path: p for p in got.parameters}
    # a phase held on one path only (WP-1301) is a fit that went elsewhere
    assert w.keys() == g.keys(), (
        f"refined on one path only: numpy {sorted(w.keys() - g.keys())}, "
        f"kernels {sorted(g.keys() - w.keys())}")
    shift = {k: abs(g[k].value - p.value) / p.stderr for k, p in w.items()
             if p.stderr is not None and np.isfinite(p.stderr) and p.stderr > 0
             and k not in WIDTH_NULL_SET
             and not k.endswith(WIDTH_NULL_SUFFIXES)}
    assert shift, "no refined parameter carries an esd to compare in"
    worst = max(shift, key=shift.get)
    assert shift[worst] < FIT_THETA_ESD, f"{worst} moved {shift[worst]:.3f} esd"
    dy = np.abs(np.asarray(got.y_calc) - np.asarray(want.y_calc)) / want.sig()
    assert dy.max() < FIT_CURVE_SIGMA, f"the curve moved {dy.max():.2e} σ"


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


def test_a_wheel_before_the_floor_is_declined_whole_and_says_so(monkeypatch):
    """A 1.4.0 wheel lacks the structure figure's ``render_rows_cued``
    (WP-1548).  Under the 1.5 floor it is declined like any wheel missing a
    kernel, so the indexer runs its numpy loop beside the model's, and the one
    warning names the pin that installs it."""
    monkeypatch.delenv(COMPILED_ENV, raising=False)
    _fresh_load(monkeypatch, _wheel(__version__="1.4.0", render_rows_cued=None))
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter("always")
        compiled.set_enabled(None)
        assert compiled.dichotomy_kernels() is None
    assert compiled.KERNEL_FLOOR == "1.5"
    assert compiled.unavailable() == "rietx_kernels 1.4.0 lacks the kernel render_rows_cued"
    runtime = [str(w.message) for w in seen if issubclass(w.category, RuntimeWarning)]
    assert len(runtime) == 1, runtime
    pin = f"rietx-kernels>={compiled.KERNEL_FLOOR},<{compiled.KERNEL_ABI + 1}"
    assert f'pip install "{pin}"' in runtime[0]


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
    pin = f"rietx-kernels>={compiled.KERNEL_FLOOR},<{compiled.KERNEL_ABI + 1}"
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
    """``pyproject``'s range is :data:`compiled.KERNEL_FLOOR` and
    :data:`compiled.KERNEL_ABI` written a second time, so a bump of either
    alone fails here.  The floor is a minor of the interface's major."""
    path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    project = tomllib.loads(path.read_text(encoding="utf-8"))["project"]
    deps = project["dependencies"]
    abi, floor = compiled.KERNEL_ABI, compiled.KERNEL_FLOOR
    assert floor.split(".")[0] == str(abi)
    assert [d for d in deps if d.startswith("rietx-kernels")] == [
        f"rietx-kernels>={floor},<{abi + 1}"]
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


def test_a_platform_without_threads_gets_one_whatever_is_asked(monkeypatch):
    """Pyodide's CPython has no threads, so a pool there could never start a
    worker: the count is one even when the environment asks for more (WP-1966)."""
    from rietx._about import COMPILED_THREADS_ENV

    monkeypatch.setattr(compiled, "_CAN_THREAD", False)
    monkeypatch.setenv(COMPILED_THREADS_ENV, "4")
    assert compiled.n_threads() == 1
