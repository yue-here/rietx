"""WP-1940: the ``rietx-kernels`` wheel against the numpy path it accelerates.

Run: ``.venv/bin/python examples/aot_spike/bench_aot_kernels.py [--repeats N]
[--cases trigger,cpd-1a] [--skip 1,2,3] [--gate]``

The wheel is a dependency of rietx, so a ``[dev]`` venv already has it.  A
crate built from ``kernels/`` replaces it:
``maturin develop --release --uv -m kernels/Cargo.toml`` with the venv active.

**The reference is the numpy path**, the arithmetic ``RIETX_COMPILED=0`` runs.
It was numba until WP-1940 removed numba.  :data:`NUMPY` holds one twin per
kernel, taking the wheel's positional signature and filling the same output
rows with the expression ``model/forward.py`` runs when that kernel declines:
``accumulate_planes`` for the scatter, ``_omega_batch``'s two fallbacks for
Ω, and ``derivative_bases``' two for the bases.  The arithmetic is the
package's own functions, called here (``pseudo_voigt``,
``pseudo_voigt_basis``, ``pseudo_voigt_derivs``, ``_node_mix``,
``accumulate_planes``).  Only the slicing is transcribed, so a twin cannot
drift from the fallback in its arithmetic.  Each twin writes a row's window
and leaves its pad tail alone, as the kernel does.  The fallback writes the
pad too, and its caller zeroes it before anything reads it.

Three measurements:

1. **Agreement, per call, inside a real fit.**  One fit runs with every kernel
   call shadowed.  Each call runs the wheel and then the twin on the same
   inputs, and the twin's outputs are the ones the fit goes on with.  So the
   fit is the numpy path's, and its final parameters must be bit-identical to
   a second fit run with the tier switched off.  That proves the twins are the
   fallback on every call these fits make.  A third fit, the numpy path again,
   says whether the comparison can be made at all.  On macOS x86_64 under
   numpy 2.4.6 two identical numpy-path fits in one process differ by up to
   ~1e-3 esd (WP-1940), and there the twins' gap is reported, never gated.  Serial: the pool's worker count is
   forced to 1, so each call covers all its rows.  The comparison is over the
   rows the call wrote, in window.  Per kernel the table gives the calls, the
   calls that were bit-identical, the largest relative difference (the largest
   absolute difference over the plane's largest magnitude,
   ``tests/test_compiled_kernels._rel``), the largest distance in ulps, and
   which arms ran (:data:`ARM`).  The bar each call must meet is the one
   ``tests/test_compiled_kernels.py`` asserts for the wheel against the numpy
   path (:data:`BAR`):

   - ``accum``, the scatter: the bit, on every platform.  It has no library
     call (``test_the_scatter_is_bit_identical_at_every_arity``).
   - ``omega_sym`` and ``bases_sym``: under 1e-15 relative, and the bit on
     darwin/arm64, where the C library's ``exp`` and numpy's agree
     (``test_symmetric_rows_land_on_the_numpy_doubles``,
     ``test_the_forward_and_the_bases_keep_their_separate_spellings``).
   - ``omega_fcj`` and ``bases_fcj``: under 1e-13 relative on every platform
     (``test_fcj_rows_agree_to_rounding_on_every_plane``).  The kernel sums
     the nodes in a loop and numpy in a matmul, so the bit is not claimed.

   ``--gate`` exits 1 unless the wheel loaded, this section ran, every kernel
   was called, every call met its bar, and each case's twins reproduced the
   numpy path.  ``kernels.yml``'s ``test`` job runs it on each wheel's own
   platform.
2. **End to end.**  Three arms, interleaved (bench_refinement rule 2), on the
   default thread count: the wheel, the wheel with the pool's worker count
   forced to 1 (``wheel, inline``), and the numpy path
   (``compiled.set_enabled(False)``).  The final parameter vector is compared
   to the numpy path's first repeat: identical, or the largest difference in
   esd units, the fit-level guard's quantity (WP-1940 § The relaxed rule
   item 3).  Before the arms, one fit on the wheel reports each kernel's calls
   and seconds, inline against pooled, as ``compiled._splits`` decided them.
3. **Startup**: importing ``rietx_kernels``, ``rietx``, and ``rietx`` with
   the kernels loaded, each in a fresh process.

``cython/`` holds WP-1939's Cython candidates.  This bench stopped building
and running them at WP-1940, and their numbers are in WP-1939's file.

Wall clock is a range, never a figure (bench_refinement rule 1).
"""

from __future__ import annotations

import argparse
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("RIETX_TELEMETRY", "0")

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "examples"))
sys.path.insert(0, str(REPO / "tests"))

import numpy as np  # noqa: E402

import rietx as rx  # noqa: E402
from rietx.model import compiled  # noqa: E402
from rietx.model.forward import (  # noqa: E402
    _BASES_CHUNK_ROWS,
    _node_mix,
    accumulate_planes,
)
from rietx.model.profiles.pseudovoigt import (  # noqa: E402
    pseudo_voigt,
    pseudo_voigt_basis,
    pseudo_voigt_derivs,
)

#: positional indices of each kernel's *output* arrays
OUTPUTS = {
    "accum": (0,),
    "omega_sym": (0,),
    "omega_fcj": (0,),
    "bases_sym": (0, 1, 2, 3),
    "bases_fcj": (0, 1, 2, 3, 4, 5),
}

#: the argument that picks each kernel's arm (WP-1940): the scatter's term
#: count, Ω's spelling (0 forward, 1 basis), the FCJ bases' axial planes.
#: ``bases_sym`` has one arm.
ARM = {
    "accum": (11, "n_terms"),
    "omega_sym": (7, "spell"),
    "omega_fcj": (8, "spell"),
    "bases_fcj": (19, "has_ax"),
}

#: the platform where the C library's ``exp`` and numpy's were measured equal
MEASURED_PLATFORM = ("darwin", "arm64")
ON_MEASURED = (sys.platform, platform.machine()) == MEASURED_PLATFORM

#: each kernel's bar against the numpy path, as tests/test_compiled_kernels.py
#: asserts it (the module docstring names the test behind each): ``"bit"``, or
#: the relative difference a call must stay under
BAR: dict[str, str | float] = {
    "accum": "bit",
    "omega_sym": "bit" if ON_MEASURED else 1e-15,
    "bases_sym": "bit" if ON_MEASURED else 1e-15,
    "omega_fcj": 1e-13,
    "bases_fcj": 1e-13,
}


# -- the numpy twins ----------------------------------------------------------
#
# Each takes its kernel's positional signature (kernels/src/lib.rs) and writes
# what model/forward.py's fallback beside the ``compiled`` call computes.


def _window(plane: np.ndarray, rs: np.ndarray, width: np.ndarray,
            values: np.ndarray) -> None:
    """Write ``values`` into the rows ``rs`` of ``plane``, in window only."""
    inwin = np.arange(plane.shape[1])[None, :] < width[rs, None]
    plane[rs] = np.where(inwin, values, plane[rs])


def _np_accum(y, i0, i1, c0, p0, c1, p1, c2, p2, c3, p3, n_terms):
    """``accumulate_planes``, with ``y``'s running sum carried in.

    The kernel adds into ``y``, and ``compiled.accumulate`` calls it once a
    part, so ``y`` holds the earlier parts' sum.  ``np.bincount`` adds its
    input in order from zero, so ``y`` goes in as a first part of one term at
    coefficient 1.0.  Both steps are exact: 1.0·y is y, and 0 + y is y.  Each
    point's additions then arrive in the order the package's single
    ``bincount`` over every part makes them.  The layout's ``idx`` is
    ``forward._batch_layout``'s.
    """
    n = len(y)
    w_max = p0.shape[1]
    ar = np.arange(w_max, dtype=np.int64)[None, :]
    lay = _Layout(i0, np.minimum(i0[:, None] + ar, np.maximum(i1 - 1, 0)[:, None]),
                  w_max)
    carry = _Layout(np.zeros(n), np.arange(n, dtype=np.int64)[:, None], 1)
    terms = list(zip((c0, c1, c2, c3), (p0, p1, p2, p3)))[:n_terms]
    was = compiled.set_enabled(False)
    try:
        y[...] = accumulate_planes(n, [(carry, [(np.ones(n), y[:, None])]),
                                       (lay, terms)])
    finally:
        compiled.set_enabled(was)


class _Layout:
    """The three ``BatchLayout`` fields ``accumulate_planes`` reads."""

    def __init__(self, i0, idx, w_max):
        self.i0, self.idx, self.w_max = i0, idx, w_max


def _basis(spell: int):
    """``_omega_batch``'s choice of spelling, for a pseudo-Voigt model."""
    return pseudo_voigt if spell == compiled.SPELL_FORWARD else pseudo_voigt_basis


def _np_omega_sym(out, x, rows, pos, w1, w2, width, spell, lo, hi):
    """``_omega_batch``'s symmetric rows."""
    rs = rows[lo:hi]
    _window(out, rs, width,
            _basis(spell)(x[rs] - pos[rs, None], w1[rs, None], w2[rs, None]))


def _chunks(rows, lo, hi):
    """The fallback's chunks of ``_BASES_CHUNK_ROWS``: (rows, bucket slice)."""
    for a in range(lo, hi, _BASES_CHUNK_ROWS):
        s = slice(a, min(hi, a + _BASES_CHUNK_ROWS))
        yield rows[s], s


def _np_omega_fcj(out, x, rows, w1, w2, width, phi, om, spell, lo, hi):
    """``_omega_batch``'s FCJ bucket."""
    for rs, s in _chunks(rows, lo, hi):
        x3 = x[rs][:, None, :] - phi[s][:, :, None]
        _window(out, rs, width, _node_mix(
            om[s], _basis(spell)(x3, w1[rs, None, None], w2[rs, None, None])))


def _np_bases_sym(omega, d_pos, d_gamma, d_eta, x, rows, pos, w1, w2, width,
                  lo, hi):
    """``derivative_bases``' symmetric rows."""
    rs = rows[lo:hi]
    pv, ddx, ddg, dde = pseudo_voigt_derivs(
        x[rs] - pos[rs, None], w1[rs, None], w2[rs, None])
    for plane, v in ((omega, pv), (d_pos, -ddx), (d_gamma, ddg), (d_eta, dde)):
        _window(plane, rs, width, v)


def _np_bases_fcj(omega, d_pos, d_gamma, d_eta, d_sl, d_hl, x, rows, w1, w2,
                  width, phi, om, dphi, dom, dphi_sl, dom_sl, dphi_hl, dom_hl,
                  has_ax, lo, hi):
    """``derivative_bases``' FCJ bucket.  The caller differences the node
    planes before the call either way, so ``dphi`` and ``dom`` here are the
    fallback's ``dphi`` and ``dom``."""
    for rs, s in _chunks(rows, lo, hi):
        phi_c, om_c = phi[s], om[s]
        x3 = x[rs][:, None, :] - phi_c[:, :, None]
        pv, ddx, ddg, dde = pseudo_voigt_derivs(
            x3, w1[rs, None, None], w2[rs, None, None])
        out = [(omega, _node_mix(om_c, pv)), (d_gamma, _node_mix(om_c, ddg)),
               (d_eta, _node_mix(om_c, dde)),
               (d_pos, _node_mix(dom[s], pv) - _node_mix(om_c * dphi[s], ddx))]
        if has_ax:
            out += [(planes, _node_mix(dw[s], pv) - _node_mix(om_c * dp[s], ddx))
                    for planes, dp, dw in ((d_sl, dphi_sl, dom_sl),
                                           (d_hl, dphi_hl, dom_hl))]
        for plane, v in out:
            _window(plane, rs, width, v)


#: the reference, under the wheel's kernel names
NUMPY = {"accum": _np_accum, "omega_sym": _np_omega_sym,
         "omega_fcj": _np_omega_fcj, "bases_sym": _np_bases_sym,
         "bases_fcj": _np_bases_fcj}


# -- comparing ----------------------------------------------------------------


def _cases():
    import bench_refinement as br

    return {"trigger": br._trigger, "cpd-1a": br._cpd_1a, "nac": br._nac}


def _fit(setup):
    ref = rx.Refinement(setup.structure.model_copy(deep=True),
                        setup.instrument.model_copy(deep=True), history=False)
    t0 = time.perf_counter()
    result = ref.fit(setup.data, plan=setup.plan, mode=setup.mode,
                     two_theta_limits=setup.limits)
    return time.perf_counter() - t0, result


def _ordered(a: np.ndarray) -> np.ndarray:
    """Doubles as int64s that sort the way the values do (−0.0 maps to +0.0)."""
    i = a.view(np.int64)
    return np.where(i < 0, np.int64(np.iinfo(np.int64).min) - i, i)


def _max_ulps(a: np.ndarray, b: np.ndarray) -> float:
    """Largest ulp distance between two planes, exact across a sign change.

    Subtracting raw bit patterns wraps when the signs differ, so the distance
    is taken on the ordered integers, in uint64, where it cannot overflow.
    """
    oa, ob = _ordered(a), _ordered(b)
    hi = np.maximum(oa, ob).view(np.uint64)
    lo = np.minimum(oa, ob).view(np.uint64)
    return float((hi - lo).max())


def _compare(got: np.ndarray, want: np.ndarray) -> tuple[bool, float, float]:
    """(bit-identical, relative difference, ulps) of two flat arrays.

    The relative difference is ``tests/test_compiled_kernels._rel``'s.  A
    point that is NaN on both sides agrees.  A NaN on one side only is an
    infinite difference, so it can never pass a bar.
    """
    both = np.isnan(got) & np.isnan(want)
    if both.any():
        got, want = got[~both], want[~both]
    if np.array_equal(got.view(np.int64), want.view(np.int64)):
        return True, 0.0, 0.0
    if np.isnan(got).any() or np.isnan(want).any():
        return False, float("inf"), float("inf")
    scale = float(np.abs(want).max()) or 1.0
    return (False, float(np.abs(got - want).max()) / scale,
            _max_ulps(got, want))


#: positional indices of ``rows`` and ``width`` in each profile kernel
ROWS_WIDTH = {"omega_sym": (2, 6), "omega_fcj": (2, 5), "bases_sym": (5, 9),
              "bases_fcj": (7, 10)}


def _cells(kname: str, args: tuple):
    """What one call wrote, as a function flattening it out of a plane: the
    whole of ``y`` for the scatter, and the rows ``rows[lo:hi]`` in window for
    the others.  ``None`` for a plane the call did not build (``bases_fcj``'s
    axial pair when it is off)."""
    if kname == "accum":
        return lambda plane: plane.ravel()
    ir, iw = ROWS_WIDTH[kname]
    rs = args[ir][int(args[-2]):int(args[-1])]
    inwin = np.arange(args[0].shape[1])[None, :] < args[iw][rs, None]
    return lambda plane: plane[rs][inwin] if plane.size else None


class _Shadow:
    """Per kernel: calls, bit-identical calls, calls past the bar, the largest
    relative difference and ulp distance, and per-arm call counts, so a zero
    says which arms it covers."""

    def __init__(self, wheel: dict):
        self.wheel = wheel
        self.calls: dict[str, int] = {}
        self.same: dict[str, int] = {}
        self.past: dict[str, int] = {}
        self.rel: dict[str, float] = {}
        self.ulps: dict[str, float] = {}
        self.arms: dict[str, dict] = {}
        self.arm_past: dict[str, set] = {}

    def wrap(self, kname: str):
        outs = OUTPUTS[kname]
        bar = BAR[kname]

        def call(*args):
            self.calls[kname] = self.calls.get(kname, 0) + 1
            arm = args[ARM[kname][0]] if kname in ARM else None
            if arm is not None:
                arm = int(arm)
                seen = self.arms.setdefault(kname, {})
                seen[arm] = seen.get(arm, 0) + 1
            before = [args[i].copy() for i in outs]
            self.wheel[kname](*args)
            got = [args[i].copy() for i in outs]
            for i, b in zip(outs, before):
                args[i][...] = b
            NUMPY[kname](*args)
            cut = _cells(kname, args)
            same, rel, ulps = True, 0.0, 0.0
            for i, g in zip(outs, got):
                g, w = cut(g), cut(args[i])
                if g is None:
                    continue
                s, r, u = _compare(g, w)
                same, rel, ulps = same and s, max(rel, r), max(ulps, u)
            self.same[kname] = self.same.get(kname, 0) + same
            self.rel[kname] = max(self.rel.get(kname, 0.0), rel)
            self.ulps[kname] = max(self.ulps.get(kname, 0.0), ulps)
            if not (same if bar == "bit" else rel < bar):
                self.past[kname] = self.past.get(kname, 0) + 1
                self.arm_past.setdefault(kname, set()).add(arm)

        return call


def agreement(case: str, wheel: dict) -> tuple[int, set[str], bool]:
    """Print the table; return how many calls missed their bar, which kernels
    the fit called, and the twins check: ``"same"``, ``"drifted"``, or
    ``"unchecked"`` where the numpy path does not reproduce itself."""
    print(f"\n## 1. Agreement with the numpy path inside one {case} fit "
          "(threads = 1)\n")
    shadow = _Shadow(wheel)
    setup = _cases()[case]()
    compiled._KERNELS = {k: shadow.wrap(k) for k in OUTPUTS}
    try:
        _w, on_twins = _fit(setup)
    finally:
        compiled._KERNELS = wheel
    was = compiled.set_enabled(False)
    try:
        _w, on_numpy = _fit(setup)
        _w, again = _fit(setup)
    finally:
        compiled.set_enabled(was)
    final = {p.path: (p.value, p.stderr) for p in on_numpy.parameters}
    gap = _theta_gap(final, {p.path: (p.value, p.stderr)
                             for p in on_twins.parameters})
    noise = _theta_gap(final, {p.path: (p.value, p.stderr)
                               for p in again.parameters})
    print(f"The fit on the twins' outputs, against the numpy path: {gap}.")
    if noise != "bit-identical":
        print(f"The numpy path against itself: {noise}.  It does not reproduce "
              "itself here, so the twins cannot be checked against it, and "
              "their gap is reported, not gated.")
    print()
    print("| kernel | calls | arms ran (calls) | bit-identical | max rel | "
          "max ulp | bar | past the bar |")
    print("|---|---|---|---|---|---|---|---|")
    for k in OUTPUTS:
        if k not in shadow.calls:
            continue
        arms = shadow.arms.get(k)
        ran = ("—" if arms is None else f"{ARM[k][1]} " + ", ".join(
            f"{a}: {c}" for a, c in sorted(arms.items())))
        bar = BAR[k] if BAR[k] == "bit" else f"< {BAR[k]:.0e}"
        past = shadow.past.get(k, 0)
        if past:
            where = sorted(shadow.arm_past[k], key=str)
            past = f"{past} (arms {', '.join(map(str, where))})"
        print(f"| {k} | {shadow.calls[k]} | {ran} | {shadow.same.get(k, 0)} | "
              f"{shadow.rel.get(k, 0.0):.1e} | {shadow.ulps.get(k, 0.0):.0f} | "
              f"{bar} | {past} |")
    twins = ("unchecked" if noise != "bit-identical"
             else "same" if gap == "bit-identical" else "drifted")
    return sum(shadow.past.values()), set(shadow.calls), twins


def pool_engagement(setup) -> None:
    """One fit on the wheel, each pooled-kernel call counted and timed by the
    way ``compiled._splits`` sent it.  The entry points evaluate ``_splits``
    as ``_spread``'s last argument, so the decision lands just before the
    call."""
    calls: dict[tuple[str, bool], list[float]] = {}
    splits, spread = compiled._splits, compiled._spread
    last: list = [None]

    def counted_splits(kernel, *a):
        s = splits(kernel, *a)
        # a one-worker pool runs a split call inline, so it is not "pooled"
        last[0] = (kernel, s and compiled._POOL_WORKERS > 1)
        return s

    def timed_spread(fn, n_rows, split):
        t0 = time.perf_counter()
        spread(fn, n_rows, split)
        calls.setdefault(last[0], []).append(time.perf_counter() - t0)

    compiled._splits, compiled._spread = counted_splits, timed_spread
    try:
        _fit(setup)
    finally:
        compiled._splits, compiled._spread = splits, spread
    print("| kernel | inline calls | inline s | pooled calls | pooled s |")
    print("|---|---|---|---|---|")
    for k in OUTPUTS:
        inl, pooled = calls.get((k, False), []), calls.get((k, True), [])
        if inl or pooled:
            print(f"| {k} | {len(inl)} | {sum(inl):.3f} | {len(pooled)} | "
                  f"{sum(pooled):.3f} |")
    print()


def _theta_gap(ref: dict, got: dict) -> str:
    """How far one arm's final parameters sit from the numpy path's.

    A path present on one side only, a value differing where no positive esd
    exists to scale it, or an esd differing beside an equal value, is counted
    rather than dropped, so a difference never reads as 0 esd.
    """
    if got == ref:
        return "bit-identical"
    worst, unscaled, esd_only = 0.0, 0, 0
    for path, (v, e) in ref.items():
        if path not in got:
            continue
        gv, ge = got[path]
        if gv == v:
            esd_only += ge != e
            continue
        gap = abs(gv - v) / e if e and e > 0 else float("nan")
        if gap != gap:
            unscaled += 1
        else:
            worst = max(worst, gap)
    out = f"max {worst:.1e} esd"
    missing = len(ref.keys() - got.keys()) + len(got.keys() - ref.keys())
    if unscaled:
        out += f", {unscaled} differing with no esd to scale (or NaN)"
    if missing:
        out += f", {missing} paths on one side only"
    if esd_only:
        out += f", {esd_only} with the same value and another esd"
    return out


def end_to_end(case: str, wheel: dict, repeats: int) -> None:
    workers = compiled._pool()._max_workers
    print(f"\n## 2. End to end, {case}, {repeats} interleaved repeats "
          f"(threads = {workers})\n")
    setup = _cases()[case]()
    pool_engagement(setup)
    arms = ("numpy", "wheel", "wheel, inline")
    walls: dict[str, list[float]] = {a: [] for a in arms}
    finals: dict[str, list[dict[str, tuple[float, float | None]]]] = {
        a: [] for a in arms}
    rwp: dict[str, float] = {}
    for rep in range(repeats):
        order = arms[rep % len(arms):] + arms[:rep % len(arms)]
        for arm in order:
            was = compiled.set_enabled(arm != "numpy")
            if arm == "wheel, inline":
                compiled._POOL_WORKERS = 1
            try:
                wall, res = _fit(setup)
            finally:
                compiled.set_enabled(was)
                compiled._POOL_WORKERS = workers
            walls[arm].append(wall)
            finals[arm].append({p.path: (p.value, p.stderr) for p in res.parameters})
            rwp[arm] = res.statistics.rwp
    # every repeat against the numpy path's first, so an arm that varies run
    # to run (the numpy path's own repeats included) cannot pass on its last
    # repeat alone
    ref = finals["numpy"][0]
    print("| arm | wall min–max s | median | ×numpy (median) | Rwp | "
          "final θ vs numpy |")
    print("|---|---|---|---|---|---|")
    med_np = statistics.median(walls["numpy"])
    for arm, ws in walls.items():
        same = " / ".join(sorted({_theta_gap(ref, got) for got in finals[arm]}))
        print(f"| {arm} | {min(ws):.2f}–{max(ws):.2f} | "
              f"{statistics.median(ws):.2f} | {med_np / statistics.median(ws):.2f}× | "
              f"{rwp[arm]:.6f} | {same} |")


def _time_subprocess(code: str, n: int = 5) -> list[float]:
    out = []
    for _ in range(n):
        t0 = time.perf_counter()
        subprocess.run([sys.executable, "-c", code], check=True, cwd=HERE)
        out.append(time.perf_counter() - t0)
    return out


def startup() -> None:
    print("\n## 3. Startup, fresh process each (s, min–max of 5)\n")
    rows = [
        ("python + numpy", "import numpy"),
        ("+ import rietx_kernels", "import numpy, rietx_kernels"),
        ("+ import rietx", "import rietx"),
        ("+ import rietx, kernels loaded",
         "import rietx; from rietx.model import compiled; "
         "assert compiled.available()"),
    ]
    for label, code in rows:
        ts = _time_subprocess(code)
        print(f"| {label} | {min(ts):.3f}–{max(ts):.3f} |")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--cases", default="trigger,cpd-1a")
    ap.add_argument("--skip", default="", help="comma list of 1,2,3")
    ap.add_argument("--gate", action="store_true",
                    help="exit 1 unless the wheel loaded, every kernel was "
                         "called and met its bar against the numpy path, and "
                         "the twins reproduced that path (kernels.yml, "
                         "WP-1940)")
    args = ap.parse_args(argv)
    skip = set(filter(None, args.skip.split(",")))
    compiled.set_enabled(True)
    wheel = compiled._kernels()
    if wheel is None:
        print(f"GATE: the wheel did not load, because {compiled.unavailable()}")
        return 1
    import rietx_kernels

    print(f"# WP-1940 kernel agreement — {platform.platform()}, python "
          f"{platform.python_version()}, numpy {np.__version__}, rietx_kernels "
          f"{rietx_kernels.__version__} (interface {rietx_kernels.KERNEL_ABI}), "
          f"rietx {rx.__version__}")
    past, called, drifted, unchecked = 0, set(), [], []
    for case in args.cases.split(","):
        if "1" not in skip:
            # serial: ``_spread`` runs a kernel inline when the pool it reads
            # has one worker, and it reads the count the pool was built with
            pool = compiled._pool()
            compiled._POOL_WORKERS = 1
            try:
                bad, ran, twins = agreement(case, wheel)
            finally:
                compiled._POOL_WORKERS = pool._max_workers
            past += bad
            called |= ran
            {"drifted": drifted, "unchecked": unchecked}.get(
                twins, []).append(case)
        if "2" not in skip:
            end_to_end(case, wheel, args.repeats)
    if "3" not in skip:
        startup()
    if args.gate:
        # a kernel no case called agrees vacuously, so it fails the gate too
        never = sorted(set(OUTPUTS) - called)
        if "1" in skip:
            print("GATE: the agreement pass was skipped")
            return 1
        if past or never or drifted:
            print(f"GATE: {past} calls past their bar; never called: "
                  f"{', '.join(never) or 'none'}; the twins left the numpy "
                  f"path in: {', '.join(drifted) or 'none'}")
            return 1
        print("GATE: every kernel was called and every call met its bar; "
              "the twins reproduced the numpy path"
              + (f" except where it does not reproduce itself: "
                 f"{', '.join(unchecked)}" if unchecked else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
