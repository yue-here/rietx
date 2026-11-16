"""WP-2017 group Q: the held SNIP of issue #1569, and the three Le Bail rows.

Fits and arms were fixed in WP-2017 § What each group inherits, "Q, its fits and arms",
before anything ran (2026-11-16).  Every arm has a noise twin (every refinable non-zero start
×(1 + 1e-12)); rows are read in plain esd over the larger esd, Rwp, evaluations, status and
codes beside.

(Q1) **The held SNIP** (``docs/skill/rietx/references/judging.md``, "Under a broad hump, hold
SNIP").

- ``syn`` — #1569's construction: SRM 660c's LaB₆ model (``build_srm_inputs``' structure and
  instrument: Cu Kα₁/Kα₂, FCJ on), 15-120° at 0.02°, background 200 + 60·T₁ plus a Gaussian
  hump at 28° (FWHM 10°, height 150), Poisson noise from ``default_rng(20261112)``; Rietveld under
  ``mccusker_default()`` with a Biso stage appended.  Arms ``cheb`` (the instrument's 6-term
  Chebyshev co-refined), ``ps1`` and ``ps001`` (P-spline, λ 1 and 0.01), ``snip7`` and
  ``snip14`` (SNIP held under a 4-term Chebyshev at half-windows 7 and 14 points) and ``truth``
  (the true background held under the same 4 terms: the positive arm).
- ``real`` — SRM 1976a (its texture protocol) and FAP (GSAS-II's protocol), Rietveld:
  ``cheb`` (each protocol's own background, co-refined) against ``snip3`` (held, half-window
  3 FWHM in points, the FWHM read off the ``cheb`` fit's strongest calculated peak).
- ``lebail`` — PbSO₄ (the Durham TOPAS ``Pbso4.raw``, X-ray) and #726's pattern (the IUCr CPD
  SRM 676a corundum on WP-1910's fixture, 20-90°), Le Bail under ``mccusker_default()``:
  ``cheb`` against ``snip3``, read on the cell and widths.

(Q2) **The three rows**, each side of its value, on ``lab6cbn``, ``fap`` and ``cpd1a``.

- ``conv`` — ``refine.LEBAIL_CONVERGED_REL`` 1e-4 (shipped), 1e-3, 1e-5; Le Bail under
  ``mccusker_default()`` with ``lebail_passes = 5``; the stop's reason and kept pass recorded.
- ``tol`` — ``StageSpec:lebail_tol`` 1e-7 (shipped), 1e-6, 1e-9 on every stage (cap 100 000 at
  1e-9, as ``test_lebail_cycles`` does below the default); FAP's (5 0 6)/(10 −5 0) split read.
- ``gap`` — ``report.schemas.LEBAIL_GAP_CYCLES`` 5 (shipped), 2, 20: each family's Rietveld
  protocol fitted once, the layer-0 gap read three times from the converged state
  (``layer0.lebail_gap``'s keyword default set in place), ratio against ``LEBAIL_GAP_NOTABLE``.

    .venv/bin/python docs/wp/2017-batch/group_q.py          # every task
    .venv/bin/python docs/wp/2017-batch/group_q.py canary   # syn cheb + truth, fap tol 1e-6
    .venv/bin/python docs/wp/2017-batch/group_q.py summary  # write group_q_summary.md

``WP2017Q_RAW`` names the raw directory (default ``~/.cache/rietx/wp-2017-q``);
``WP2017Q_WORKERS`` the pool (default 4).
"""

from __future__ import annotations

import dataclasses
import importlib
import json
import math
import os
import platform
import subprocess
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import get_context
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
os.environ.setdefault("RIETX_TELEMETRY", "0")
os.environ.setdefault("MPLBACKEND", "Agg")

from rietx._about import COMPILED_THREADS_ENV  # noqa: E402

os.environ.setdefault(COMPILED_THREADS_ENV, "1")

import rietx as rx  # noqa: E402
from rietx.model import compiled  # noqa: E402
from rietx.schemas.instrument import BackgroundChebyshev, BackgroundPSpline  # noqa: E402

RAW = Path(os.environ.get("WP2017Q_RAW", Path.home() / ".cache" / "rietx" / "wp-2017-q"))
JSONL = RAW / "group_q.jsonl"
SUMMARY = HERE / "group_q_summary.md"
WORKERS = int(os.environ.get("WP2017Q_WORKERS", "4"))
NUDGE = 1e-12

SYN_LO, SYN_HI, SYN_STEP = 15.0, 120.0, 0.02
SYN_SEED = 20261112
SYN_SCALE = float(os.environ.get("WP2017Q_SYN_SCALE", "5e-3"))   # calibrated: cheb La esd ~0.016
SYN_LADDER = (1e-3, 3e-2)          # count levels either side, cheb/snip7/snip10/truth
SYN_SEEDS = (20261113, 20261114)   # two more Poisson draws at SYN_SCALE, same four arms
HUMP = (28.0, 10.0, 150.0)          # centre, FWHM, height
TRUTH = {"phases.0.atoms.0.biso": 0.355, "phases.0.atoms.1.biso": 0.276}
SYN_ARMS = ("cheb", "ps1", "ps001", "snip7", "snip10", "snip14", "truth")
SYN_SUB = ("cheb", "snip7", "snip10", "truth")
REAL = ("srm1976a", "fap")
LEBAIL = ("pbso4", "corundum726")
Q2_FAMILIES = ("lab6cbn", "fap", "cpd1a")
CONV_ARMS = {"shipped": 1e-4, "1e-3": 1e-3, "1e-5": 1e-5}
TOL_ARMS = {"shipped": 1e-7, "1e-6": 1e-6, "1e-9": 1e-9}
GAP_ARMS = (5, 2, 20)
REFERENCE_CAP = 100_000
PBSO4_CELL = (8.480, 5.398, 6.959, 90.0, 90.0, 90.0)   # Hill (1992), P n m a


def _nudged(ref) -> int:
    values = {}
    for row in ref.parameters():
        if not row.refinable or row.value == 0.0:
            continue
        value = row.value * (1.0 + NUDGE)
        if not row.lo <= value <= row.hi:
            value = row.value * (1.0 - NUDGE)
        values[row.path] = value
    ref.set_values(values)
    return len(values)


def _rows(result) -> dict:
    return {p.path: [p.value, getattr(p, "stderr_uncorrected", p.stderr)]
            for p in result.parameters}


def _stats(result) -> dict:
    return {"rwp": result.statistics.rwp if hasattr(result, "statistics") else None,
            "gof": getattr(result.statistics, "gof", None),
            "status": result.status,
            "n_eval": int(sum(s.n_iterations for s in result.stages)),
            "codes": sorted({d.code for d in result.diagnostics})}


def _absorption(ref) -> dict:
    try:
        bg = ref.report().background
    except Exception as exc:  # noqa: BLE001
        return {"absorption_error": f"{type(exc).__name__}: {exc}"[:200]}
    if bg is None:
        return {"worst_absorption": None}
    return {"worst_absorption": bg.worst_absorption, "worst_absorption_path": bg.worst_absorption_path}


def _fwhm_points(result) -> float | None:
    """Half-maximum width, in channels, of the strongest calculated peak above background."""
    tt = np.asarray(result.two_theta, dtype=float)
    net = np.asarray(result.y_calc, dtype=float) - np.asarray(result.y_background, dtype=float)
    if tt.size < 5:
        return None
    i = int(np.argmax(net))
    half = net[i] / 2.0
    lo = i
    while lo > 0 and net[lo] > half:
        lo -= 1
    hi = i
    while hi < net.size - 1 and net[hi] > half:
        hi += 1
    left = lo + (half - net[lo]) / (net[lo + 1] - net[lo]) if net[lo + 1] != net[lo] else lo
    right = hi - 1 + (net[hi - 1] - half) / (net[hi - 1] - net[hi]) if net[hi - 1] != net[hi] else hi
    return float(right - left)


def _snip_held(tt, y, half_window: int, n_terms: int = 4):
    from rietx.background import snip

    est = snip(np.asarray(y, dtype=float), int(half_window))
    return rx.BackgroundFixedPlusChebyshev.from_pattern(
        rx.PatternData(two_theta=list(map(float, tt)), intensity=est.tolist()),
        n_terms=n_terms, source="snip")


# ---------------------------------------------------------------- (Q1) synthetic
def syn_background(tt) -> np.ndarray:
    tt = np.asarray(tt, dtype=float)
    x = 2.0 * (tt - SYN_LO) / (SYN_HI - SYN_LO) - 1.0
    c, fwhm, h = HUMP
    return 200.0 + 60.0 * x + h * np.exp(-4.0 * math.log(2.0) * ((tt - c) / fwhm) ** 2)


def syn_inputs(scale: float = SYN_SCALE, seed: int = SYN_SEED):
    """(data, structure, instrument, peak counts) of #1569's construction."""
    from tests.test_acceptance_srm660c import build_srm_inputs

    _d, st, ins = build_srm_inputs()
    st.phases[0].scale.value = scale
    ins.background = BackgroundChebyshev.with_terms(6)
    grid = np.round(np.arange(SYN_LO, SYN_HI + SYN_STEP / 2, SYN_STEP), 6)
    y = np.asarray(rx.Refinement(st, ins, history=False).predict(grid)) + syn_background(grid)
    obs = np.random.default_rng(seed).poisson(np.maximum(y, 0.0)).astype(float)
    data = rx.PatternData(two_theta=grid.tolist(), intensity=obs.tolist(),
                          sigma=np.sqrt(np.maximum(obs, 1.0)).tolist())
    return data, st, ins, float(y.max() - syn_background(grid)[int(np.argmax(y))])


def _syn_fit(task: dict) -> dict:
    arm, noise = task["arm"], task["noise"]
    data, st, ins, peak = syn_inputs(task.get("scale", SYN_SCALE), task.get("seed", SYN_SEED))
    tt, y = np.asarray(data.two_theta), np.asarray(data.intensity)
    if arm == "cheb":
        ins.background = BackgroundChebyshev.with_terms(6)
    elif arm in ("ps1", "ps001"):
        ins.background = BackgroundPSpline.for_range(
            SYN_LO, SYN_HI, lambda_smooth={"ps1": 1.0, "ps001": 0.01}[arm])
    elif arm.startswith("snip"):
        ins.background = _snip_held(tt, y, int(arm[4:]))
    elif arm == "truth":
        ins.background = rx.BackgroundFixedPlusChebyshev.from_pattern(
            rx.PatternData(two_theta=tt.tolist(), intensity=syn_background(tt).tolist()),
            n_terms=4)
    plan = rx.RefinementPlan.mccusker_default()
    plan.stages.append(rx.Stage("biso", ["phases.*.atoms.*.biso"]))
    ref = rx.Refinement(st, ins, history=False)
    row = {"n_nudged": _nudged(ref)} if noise else {}
    result = ref.fit(data, plan=plan)
    rtt = np.asarray(result.two_theta)
    m = (rtt >= 26.0) & (rtt <= 30.0)
    ratio = float(np.mean(np.asarray(result.y_background)[m] / syn_background(rtt[m])))
    row.update({"rows": _rows(result), **_stats(result), **_absorption(ref),
                "bkg_over_truth_26_30": ratio, "fwhm_points": _fwhm_points(result),
                "peak_counts": peak})
    return row


# ---------------------------------------------------------------- (Q1) real, Rietveld
def _real_inputs(pattern: str):
    """(data, structure, instrument, plan, fit kwargs, prepare)."""
    if pattern == "srm1976a":
        from tests import test_acceptance_srm1976a_texture as t

        data = rx.read_pattern(t.PATTERN)
        st, ins = t._structure(True), t._instrument()
        tex = ["phases.0.texture.*"]
        stages = [
            rx.Stage("scale_bkg", ["phases.0.scale", "instrument.background.*"]),
            rx.Stage("displacement", ["instrument.geometry.sample_displacement"]),
            rx.Stage("w", ["instrument.profile.w"]),
            rx.Stage("widths", ["instrument.profile.u", "instrument.profile.v",
                                "instrument.profile.x", "instrument.profile.y"]),
            rx.Stage("biso", ["phases.0.atoms.*.biso"]),
            rx.Stage("texture", tex),
            rx.Stage("aberrations", ["instrument.geometry.sample_transparency",
                                     "instrument.geometry.axial_sl"]),
            rx.Stage("final", ["phases.0.atoms.*.biso", *tex]),
        ]
        plan = rx.RefinementPlan(stages=stages, intermediate_ftol=1e-6, closing_window_tol=1e-3)

        def prepare(ref):
            ref.tie_equal(["instrument.geometry.axial_sl", "instrument.geometry.axial_hl"])

        return data, st, ins, plan, {"two_theta_limits": t.LIMITS}, prepare
    from tests import test_window_domain as w

    data, st, ins, plan, kw = w._protocol(pattern)
    return data, st, ins, plan, kw, None


def _limited_arrays(data, kw):
    tt, y = np.asarray(data.two_theta, dtype=float), np.asarray(data.intensity, dtype=float)
    return tt, y


def _one_fit(data, st, ins, plan, kw, prepare, noise, mode="rietveld"):
    ref = rx.Refinement(st, ins, history=False)
    if prepare is not None:
        prepare(ref)
    n = _nudged(ref) if noise else None
    result = ref.fit(data, mode=mode, plan=plan, **kw)
    return ref, result, n


def _pair_task(task: dict, build, mode: str) -> dict:
    """``cheb`` then ``snip3`` (window from the ``cheb`` fit), each plain and nudged."""
    out = {}
    data, st, ins, plan, kw, prepare = build(task["pattern"])
    tt, y = _limited_arrays(data, kw)
    ref, res, _ = _one_fit(data, st.model_copy(deep=True), ins.model_copy(deep=True),
                           plan, kw, prepare, False, mode)
    fwhm = _fwhm_points(res)
    window = max(1, int(round(3.0 * fwhm))) if fwhm else None
    out["cheb"] = {"rows": _rows(res), **_stats(res), **_absorption(ref), "fwhm_points": fwhm}
    data, st, ins, plan, kw, prepare = build(task["pattern"])
    ref, res, n = _one_fit(data, st.model_copy(deep=True), ins.model_copy(deep=True),
                           plan, kw, prepare, True, mode)
    out["cheb_noise"] = {"rows": _rows(res), **_stats(res), "n_nudged": n}
    for noise in (False, True):
        data, st, ins, plan, kw, prepare = build(task["pattern"])
        ins.background = _snip_held(tt, y, window)
        ref, res, n = _one_fit(data, st, ins, plan, kw, prepare, noise, mode)
        out["snip3_noise" if noise else "snip3"] = {
            "rows": _rows(res), **_stats(res), "n_nudged": n,
            **({} if noise else _absorption(ref)), "half_window": window}
    return {"arms": out}


def _real_fit(task: dict) -> dict:
    return _pair_task(task, _real_inputs, "rietveld")


# ---------------------------------------------------------------- (Q1) real, Le Bail
def _lebail_inputs(pattern: str):
    from tests.test_acceptance_qpa_roundrobin import _phase

    plan = rx.RefinementPlan.mccusker_default()
    if pattern == "pbso4":
        from rietx.schemas.instrument import EmissionLine, Source
        from tests import local_data

        path = local_data.dataset("durham-topas/pbso4")
        if path is None:
            raise FileNotFoundError("durham-topas/pbso4 not on this machine")
        data = rx.read_pattern(path / "Pbso4.raw")
        ins = rx.Instrument.bragg_brentano()
        ins.source = Source(
            lines=[EmissionLine(wavelength=1.5405),
                   EmissionLine(wavelength=1.5443,
                                weight=rx.Parameter(value=0.5, min=0.0, max=1.0))],
            polarization=rx.Parameter(value=0.5, min=0.0, max=1.0), dispersion=None)
        ins.background = BackgroundChebyshev.with_terms(6)
        ins, _seeded = importlib.import_module("rietx.indexing.workflow").seed_widths(
            ins, rx.pick_peaks(data, ins))
        st = rx.Structure(phases=[_phase("PbSO4", "P n m a", PBSO4_CELL, [("Pb", "Pb", 0.188, 0.25, 0.167, 1.0)])])
        return data, st, ins, plan, {}, None
    from rietx.indexing.workflow import seed_widths
    from tests.test_acceptance_qpa_roundrobin import DATA, corundum_phase, qarr_instrument
    from tests.test_extinction_symbol import CORUNDUM_CELL, CORUNDUM_RANGE

    data = rx.read_pattern(DATA / "corundum.prn")
    ins, _seeded = seed_widths(qarr_instrument(), rx.pick_peaks(data, qarr_instrument()))
    phase = corundum_phase()
    for name, v in zip(("a", "b", "c"), CORUNDUM_CELL[:3], strict=True):
        getattr(phase.cell, name).value = v
    return data, rx.Structure(phases=[phase]), ins, plan, {"two_theta_limits": CORUNDUM_RANGE}, None


def _lebail_fit(task: dict) -> dict:
    return _pair_task(task, _lebail_inputs, "lebail")


# ---------------------------------------------------------------- (Q2) the three rows
def _q2_inputs(family: str):
    if family == "lab6cbn":
        from tests import test_acceptance_lab6_cbn as t

        st, ins = t._inputs()
        return rx.read_pattern(t.PATTERN), st, ins, t.PLAN_SHARED, {"two_theta_limits": t.LIMITS}
    from tests import test_window_domain as w

    data, st, ins, plan, kw = w._protocol(family)
    return data, st, ins, plan, kw


def _fap_pair(ref) -> dict | None:
    """FAP's (5 0 6) and (10 −5 0) ≡ (5 5 0): share of the pair's summed intensity."""
    model = getattr(ref, "_model", None)
    if model is None:
        return None
    cp = model.phases[0]
    hkl = np.asarray(cp.reflections.hkl)
    inv = hkl[:, 0] ** 2 + hkl[:, 0] * hkl[:, 1] + hkl[:, 1] ** 2
    a = np.flatnonzero((inv == 25) & (np.abs(hkl[:, 2]) == 6))
    b = np.flatnonzero((inv == 75) & (hkl[:, 2] == 0))
    if a.size != 1 or b.size != 1 or cp.hkl_intensity is None:
        return {"found": [a.size, b.size]}
    ia, ib = float(cp.hkl_intensity[a[0]]), float(cp.hkl_intensity[b[0]])
    return {"I506": ia, "I550": ib, "share506": ia / (ia + ib) if ia + ib > 0 else None,
            "d": [float(cp.reflections.d[a[0]]), float(cp.reflections.d[b[0]])]}


def _q2_fit(task: dict) -> dict:
    part, family, arm, noise = task["part"], task["family"], task["arm"], task["noise"]
    refine = importlib.import_module("rietx.refine")
    data, st, ins, rplan, kw = _q2_inputs(family)
    if part == "gap":
        from rietx.report import layer0

        ref = rx.Refinement(st, ins, history=False)
        n = _nudged(ref) if noise else None
        result = ref.fit(data, plan=rplan, **kw)
        saved = dict(layer0.lebail_gap.__kwdefaults__)
        gaps = {}
        try:
            for k in GAP_ARMS:
                layer0.lebail_gap.__kwdefaults__["n_cycles"] = k
                g = ref.report().lebail_gap
                gaps[str(k)] = None if g is None else {
                    "ratio": g.ratio, "rwp_lebail": g.rwp_lebail, "n_cycles": g.n_cycles}
        finally:
            layer0.lebail_gap.__kwdefaults__.update(saved)
        return {"rows": _rows(result), **_stats(result), "gaps": gaps, "n_nudged": n}
    plan = rx.RefinementPlan.mccusker_default()
    saved_rel = refine.LEBAIL_CONVERGED_REL
    if part == "conv":
        plan.lebail_passes = 5
        refine.LEBAIL_CONVERGED_REL = CONV_ARMS[arm]
    else:
        tol = TOL_ARMS[arm]
        plan.stages = [dataclasses.replace(
            s, lebail_tol=tol, lebail_cycles=REFERENCE_CAP if tol < 1e-7 else s.lebail_cycles)
            for s in plan.stages]
    try:
        ref = rx.Refinement(st, ins, history=False)
        n = _nudged(ref) if noise else None
        result = ref.fit(data, mode="lebail", plan=plan, **kw)
    finally:
        refine.LEBAIL_CONVERGED_REL = saved_rel
    row = {"rows": _rows(result), **_stats(result), "n_nudged": n,
           "read_rel": CONV_ARMS.get(arm) if part == "conv" else None,
           "stage_tols": sorted({s.lebail_tol for s in plan.stages})}
    stop = [d for d in result.diagnostics if d.code == "LEBAIL_ALTERNATION_STOPPED"]
    if stop:
        row["stop"] = (getattr(stop[0], "message", None) or str(stop[0]))[:400]
    if family == "fap":
        row["pair"] = _fap_pair(ref)
    return row


# ---------------------------------------------------------------- runner
def _key(t: dict) -> tuple:
    return tuple(t[k] for k in ("part", "family", "pattern", "arm", "noise", "scale", "seed") if k in t)


def run_one(task: dict) -> dict:
    warnings.simplefilter("ignore")
    compiled.set_enabled(True)
    row = dict(task)
    try:
        fn = {"syn": _syn_fit, "real": _real_fit, "lebail": _lebail_fit,
              "conv": _q2_fit, "tol": _q2_fit, "gap": _q2_fit}[task["part"]]
        row.update(fn(task))
    except Exception as exc:  # noqa: BLE001  a refused fit is a result of the sweep
        lines = str(exc).splitlines()
        row["error"] = f"{type(exc).__name__}: {lines[0] if lines else ''}"
    return row


def read_rows(path: Path = JSONL) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _meta() -> dict:
    import importlib.metadata as md

    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True,
                          text=True, check=False).stdout.strip() or "unknown"
    return {"head": head, "platform": f"{platform.system()} {platform.machine()}",
            "python": platform.python_version(), "numpy": md.version("numpy"),
            "kernels": md.version("rietx-kernels"), "workers": WORKERS}


def _tasks(parts=("syn", "real", "lebail", "conv", "tol", "gap")) -> list[dict]:
    tasks: list[dict] = []
    if "real" in parts:
        tasks += [{"part": "real", "pattern": p} for p in REAL]
    if "gap" in parts:
        tasks += [{"part": "gap", "family": f, "arm": "all", "noise": nz}
                  for f in Q2_FAMILIES for nz in (False, True)]
    if "syn" in parts:
        tasks += [{"part": "syn", "arm": a, "noise": nz} for a in SYN_ARMS for nz in (False, True)]
        tasks += [{"part": "syn", "arm": a, "noise": False, "scale": sc}
                  for a in SYN_SUB for sc in SYN_LADDER]
        tasks += [{"part": "syn", "arm": a, "noise": False, "seed": sd}
                  for a in SYN_SUB for sd in SYN_SEEDS]
    if "lebail" in parts:
        tasks += [{"part": "lebail", "pattern": p} for p in LEBAIL]
    for part, arms in (("conv", CONV_ARMS), ("tol", TOL_ARMS)):
        if part in parts:
            tasks += [{"part": part, "family": f, "arm": a, "noise": nz}
                      for f in Q2_FAMILIES for a in arms for nz in (False, True)
                      if not (nz and a != "shipped")]
    return tasks


def sweep(tasks: list[dict]) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    done = {_key(r) for r in read_rows() if "error" not in r}
    todo = [t for t in tasks if _key(t) not in done]
    if not todo:
        return
    with ProcessPoolExecutor(max_workers=max(1, min(WORKERS, len(todo))),
                             mp_context=get_context("spawn")) as pool:
        for future in as_completed([pool.submit(run_one, t) for t in todo]):
            row = future.result()
            row["meta"] = _meta()
            with JSONL.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
            print(*_key(row), row.get("error") or
                  f"{row.get('rwp')} {row.get('n_eval')} {row.get('status')}", flush=True)


# ---------------------------------------------------------------- summary
def _fmt(x, spec=".3g") -> str:
    return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, spec)


def _shift(cur: dict, ref: dict, skip_bkg: bool = True):
    """Largest |Δ| / max(esd) over shared rows that are not background coefficients."""
    worst, where = 0.0, None
    for path, (v, e) in cur.items():
        if path not in ref or (skip_bkg and path.startswith("instrument.background")):
            continue
        v0, e0 = ref[path]
        es = max(e or 0.0, e0 or 0.0)
        if not es or not math.isfinite(es):
            continue
        s = abs(v - v0) / es
        if s > worst:
            worst, where = s, path
    return worst, where


def _biso(rows: dict) -> dict:
    return {p: rows[p] for p in rows if p.endswith(".biso")}


def summary() -> None:
    rows = read_rows()
    meta = next((r["meta"] for r in rows if "meta" in r), {})
    out = ["# WP-2017 group Q, measured", "",
           f"Raw: `{JSONL.name}`, {len(rows)} rows; head `{meta.get('head', '?')[:9]}`, "
           f"{meta.get('platform')}, Python {meta.get('python')}, numpy {meta.get('numpy')}, "
           f"kernels {meta.get('kernels')}.", ""]
    err = [r for r in rows if "error" in r]
    if err:
        out += ["## Refused", ""] + [f"- {_key(r)}: {r['error']}" for r in err] + [""]
    ok = [r for r in rows if "error" not in r]

    syn = {(r["arm"], r["noise"]): r for r in ok if r["part"] == "syn"
           and "scale" not in r and "seed" not in r}
    if syn:
        out += ["## Q1, the synthetic (truth La 0.355, B 0.276 Å²)", "",
                "| arm | La Biso | (La − truth)/esd | B Biso | (B − truth)/esd | a (Å) | bkg/truth 26-30° "
                "| worst absorption | Rwp | evals | noise twin, worst plain esd |",
                "|---|---|---|---|---|---|---|---|---|---|---|"]
        for arm in SYN_ARMS:
            r = syn.get((arm, False))
            if r is None:
                continue
            la = r["rows"].get("phases.0.atoms.0.biso", [None, None])
            b = r["rows"].get("phases.0.atoms.1.biso", [None, None])
            a = r["rows"].get("phases.0.cell.a", [None, None])
            tw = syn.get((arm, True))
            s = _shift(tw["rows"], r["rows"]) if tw else (None, None)
            dz = [(x[0] - TRUTH[p]) / x[1] if x[0] is not None and x[1] else None
                  for x, p in ((la, "phases.0.atoms.0.biso"), (b, "phases.0.atoms.1.biso"))]
            out.append(
                f"| {arm} | {_fmt(la[0], '.4f')}({_fmt(la[1], '.4f')}) | {_fmt(dz[0], '.2f')} "
                f"| {_fmt(b[0], '.4f')}({_fmt(b[1], '.4f')}) | {_fmt(dz[1], '.2f')} "
                f"| {_fmt(a[0], '.6f')}({_fmt(a[1], '.1e')}) | {_fmt(r['bkg_over_truth_26_30'], '.3f')} "
                f"| {_fmt(r.get('worst_absorption'), '.3f')} {r.get('worst_absorption_path') or ''} "
                f"| {_fmt(r['rwp'], '.5f')} | {r['n_eval']} | {_fmt(s[0], '.2g')} {s[1] or ''} |")
        r0 = syn.get(("cheb", False))
        if r0:
            out += ["", f"Strongest peak {r0['peak_counts']:.0f} counts over background at scale "
                    f"{SYN_SCALE:g}; FWHM read off the cheb fit {_fmt(r0['fwhm_points'], '.2f')} "
                    "points (3 FWHM = the rule's window)."]
        out += ["", "Other count levels and Poisson draws (plain arms only):", "",
                "| scale | seed | arm | peak counts | La Biso | (La − truth)/esd | B Biso "
                "| (B − truth)/esd | bkg/truth 26-30° | worst absorption |",
                "|---|---|---|---|---|---|---|---|---|---|"]
        extra = [r for r in ok if r["part"] == "syn" and ("scale" in r or "seed" in r)]
        extra.sort(key=lambda r: (r.get("scale", SYN_SCALE), r.get("seed", SYN_SEED),
                                  SYN_ARMS.index(r["arm"])))
        for r in extra:
            la = r["rows"].get("phases.0.atoms.0.biso", [None, None])
            b = r["rows"].get("phases.0.atoms.1.biso", [None, None])
            dz = [(x[0] - TRUTH[p]) / x[1] if x[0] is not None and x[1] else None
                  for x, p in ((la, "phases.0.atoms.0.biso"), (b, "phases.0.atoms.1.biso"))]
            out.append(f"| {r.get('scale', SYN_SCALE):g} | {r.get('seed', SYN_SEED)} | {r['arm']} "
                       f"| {r['peak_counts']:.0f} | {_fmt(la[0], '.4f')}({_fmt(la[1], '.4f')}) "
                       f"| {_fmt(dz[0], '.2f')} | {_fmt(b[0], '.4f')}({_fmt(b[1], '.4f')}) "
                       f"| {_fmt(dz[1], '.2f')} | {_fmt(r['bkg_over_truth_26_30'], '.3f')} "
                       f"| {_fmt(r.get('worst_absorption'), '.3f')} |")
        out.append("")

    for part, title in (("real", "Q1, real patterns in Rietveld"), ("lebail", "Q1, real patterns in Le Bail")):
        rr = [r for r in ok if r["part"] == part]
        if not rr:
            continue
        out += [f"## {title} (no truth: direction only)", ""]
        for r in rr:
            arms = r["arms"]
            c, s = arms["cheb"], arms["snip3"]
            out += [f"### {r['pattern']}", "",
                    f"FWHM {_fmt(c.get('fwhm_points'), '.2f')} points, half-window "
                    f"{s.get('half_window')}. Rwp cheb {_fmt(c['rwp'], '.5f')}, snip3 "
                    f"{_fmt(s['rwp'], '.5f')}; GOF {_fmt(c.get('gof'), '.3f')} / "
                    f"{_fmt(s.get('gof'), '.3f')}; worst absorption {_fmt(c.get('worst_absorption'), '.3f')} "
                    f"{c.get('worst_absorption_path') or ''} / {_fmt(s.get('worst_absorption'), '.3f')} "
                    f"{s.get('worst_absorption_path') or ''}; codes added "
                    f"{sorted(set(s['codes']) - set(c['codes']))}, dropped "
                    f"{sorted(set(c['codes']) - set(s['codes']))}.", "",
                    "| row | cheb | snip3 | Δ / larger esd |", "|---|---|---|---|"]
            keys = [p for p in c["rows"] if not p.startswith("instrument.background")
                    and p in s["rows"] and (part == "lebail" or p.endswith(".biso")
                                            or ".cell." in p)]
            if part == "lebail":
                keys = [p for p in keys if ".cell." in p or "profile" in p or "lor_" in p]
            for p in keys:
                (v0, e0), (v1, e1) = c["rows"][p], s["rows"][p]
                es = max(e0 or 0.0, e1 or 0.0)
                d = (v1 - v0) / es if es else None
                out.append(f"| `{p}` | {_fmt(v0, '.6g')}({_fmt(e0, '.2g')}) | "
                           f"{_fmt(v1, '.6g')}({_fmt(e1, '.2g')}) | {_fmt(d, '+.2f')} |")
            for arm in ("cheb", "snip3"):
                tw = arms.get(f"{arm}_noise")
                if tw:
                    w, at = _shift(tw["rows"], arms[arm]["rows"])
                    out.append(f"\nNoise twin of {arm}: worst {_fmt(w, '.2g')} plain esd ({at}).")
            out.append("")

    for part, arms, title in (("conv", CONV_ARMS, "Q2, `LEBAIL_CONVERGED_REL` (5 passes)"),
                              ("tol", TOL_ARMS, "Q2, `StageSpec:lebail_tol`")):
        rr = {(r["family"], r["arm"], r["noise"]): r for r in ok if r["part"] == part}
        if not rr:
            continue
        out += [f"## {title}", "",
                "| family | arm | worst plain esd vs shipped | Rwp | evals | codes | stop / pair |",
                "|---|---|---|---|---|---|---|"]
        for f in Q2_FAMILIES:
            base = rr.get((f, "shipped", False))
            for a in [*arms, "noise"]:
                r = rr.get((f, "shipped", True)) if a == "noise" else rr.get((f, a, False))
                if r is None or base is None:
                    continue
                w, at = _shift(r["rows"], base["rows"])
                extra = r.get("stop", "") if part == "conv" else (
                    "" if not r.get("pair") else
                    f"506 share {_fmt(r['pair'].get('share506'), '.4f')}")
                out.append(f"| {f} | {a} | {_fmt(w, '.2g')} {at or ''} | {_fmt(r['rwp'], '.6f')} "
                           f"| {r['n_eval']} | {', '.join(c for c in r['codes'] if 'LEBAIL' in c)} "
                           f"| {extra} |")
        out.append("")

    rr = {(r["family"], r["noise"]): r for r in ok if r["part"] == "gap"}
    if rr:
        out += ["## Q2, `LEBAIL_GAP_CYCLES` (Rietveld protocol, gap read at 5, 2, 20)", "",
                "| family | twin | ratio at 5 | at 2 | at 20 | n_cycles echoed | Rwp |",
                "|---|---|---|---|---|---|---|"]
        for (f, nz), r in sorted(rr.items()):
            g = r["gaps"]
            ratios = [g.get(str(k)) or {} for k in GAP_ARMS]
            out.append(f"| {f} | {'noise' if nz else 'plain'} | "
                       + " | ".join(_fmt(x.get("ratio"), '.4f') for x in ratios)
                       + f" | {[x.get('n_cycles') for x in ratios]} | {_fmt(r['rwp'], '.5f')} |")
        out.append("")
    SUMMARY.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(SUMMARY)


def main(argv: list[str]) -> None:
    mode = argv[1] if len(argv) > 1 else "all"
    if mode == "summary":
        summary()
        return
    if mode == "canary":
        sweep([{"part": "syn", "arm": "cheb", "noise": False},
               {"part": "syn", "arm": "truth", "noise": False},
               {"part": "tol", "family": "fap", "arm": "1e-6", "noise": False}])
        return
    if mode in ("syn", "real", "lebail", "conv", "tol", "gap"):
        sweep(_tasks((mode,)))
        return
    sweep(_tasks())


if __name__ == "__main__":
    main(sys.argv)
