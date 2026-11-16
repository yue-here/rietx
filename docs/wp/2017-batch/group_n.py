"""WP-2017 group N: the four hand rows, each claim measured.

The four are hand rows (no ``_audit`` row carries them).  Claims, fits and arms were fixed in
WP-2017 § What each group inherits, "N, its four claims and arms", before anything ran
(2026-11-16).  Bar as group A: 0.1 plain esd over the larger esd on every row that is not a
background coefficient, past a noise arm (every refinable non-zero start ×(1 + 1e-12)).

- ``seed`` — the Le Bail/Pawley intensity seed (``compile_model``: max(median y_obs, 1) on
  every reflection of a fresh compile).  ``mode="lebail"`` and ``"pawley"`` under
  ``RefinementPlan.mccusker_default()`` on ``fap``, ``nac`` (NAC alone, its protocol's Le Bail
  pass: closing stage off) and ``lab6``.  Arms ``x1`` (shipped), ``x0.01``, ``x100``,
  ``shaped`` (the seed times a lognormal draw, σ 1, ``default_rng(2017)``, per reflection) and
  ``noise``; applied by wrapping ``refine.compile_model``, which counts what it rewrote.
- ``flat`` — ``refine._FLAT_AXIS_TEST_DIRECTIONS``.  ``test_magnetic``'s #599 case
  (``rh``: R-3m:R, a = 4 Å, α = 70°, truth (1.5, 2, 3), start (3.0, 0.2, 0.2)), the same on
  ``P 4/m m m`` (``tet``), and ``test_joint_flat_moments``' joint #599 case (``joint``).  Arms
  ``shipped``, ``rot30`` (both directions turned 30° about (1, 2, 3)/√14), ``rng`` (a pair drawn
  by ``default_rng(2017)`` on the sphere, rejected within 5° of an axis, face or body diagonal)
  and ``noise`` (the moment's and the scale's starts ×(1 + 1e-12), on the phase objects, the
  same way on the joint path).  Spy: ``_flat_rotation_axis`` records the pair it read.
- ``arpls`` — ``arpls``'s ``max_iter`` 50 and ``tol`` 1e-3 through ``arpls.__kwdefaults__``.
  Arms ``shipped``, ``tight`` (500, 1e-6), ``loose`` (10, 1e-2) on ``fap``, ``nac``, ``cpd1a``,
  ``lab6``, ``si640c`` (2-50°) and ``srm1976a`` (20-118.6°).  No fit unless a pick changes.
- ``floor`` — ``params.vector.FLOOR_SEEDS`` (the dict mutated in place).  Arms ``shipped``,
  ``x10``, ``d10`` and ``noise`` on ``fap``, ``nac``, ``cpd1a``, ``lab6`` under their protocols.
  Control: a counting dict on ``least_squares.FLOOR_SEEDS`` counts the reads.

    .venv/bin/python docs/wp/2017-batch/group_n.py          # every task
    .venv/bin/python docs/wp/2017-batch/group_n.py canary   # fap Le Bail x1/x100, rh shipped/rot30
    .venv/bin/python docs/wp/2017-batch/group_n.py summary  # write group_n_summary.md

``WP2017N_RAW`` names the raw directory (default ``~/.cache/rietx/wp-2017-n``);
``WP2017N_WORKERS`` the pool (default 4).
"""

from __future__ import annotations

import importlib
import json
import math
import os
import platform
import re
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

RAW = Path(os.environ.get("WP2017N_RAW", Path.home() / ".cache" / "rietx" / "wp-2017-n"))
JSONL = RAW / "group_n.jsonl"
SUMMARY = HERE / "group_n_summary.md"
WORKERS = int(os.environ.get("WP2017N_WORKERS", "4"))
NUDGE = 1e-12

SEED_FAMILIES = ("fap", "nac", "lab6")
SEED_MODES = ("lebail", "pawley")
SEED_ARMS = ("x1", "x0.01", "x100", "shaped", "noise")
FLAT_CASES = ("rh", "tet", "joint")
FLAT_ARMS = ("shipped", "rot30", "rng", "noise")
ARPLS_PATTERNS = ("fap", "nac", "cpd1a", "lab6", "si640c", "srm1976a")
ARPLS_ARMS = {"shipped": (50, 1e-3), "tight": (500, 1e-6), "loose": (10, 1e-2)}
FLOOR_FAMILIES = ("fap", "nac", "cpd1a", "lab6")
FLOOR_ARMS = ("shipped", "x10", "d10", "noise")
MOMENT = "phases.0.atoms.0.moment"


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
            "status": result.status,
            "n_eval": int(sum(s.n_iterations for s in result.stages)),
            "codes": sorted({d.code for d in result.diagnostics})}


# ---------------------------------------------------------------- (1) intensity seed
def _seed_fit(task: dict) -> dict:
    refine = importlib.import_module("rietx.refine")

    family, mode, arm = task["family"], task["mode"], task["arm"]
    rng = np.random.default_rng(2017)
    counts = {"compiles": 0, "rewritten": 0}
    original = refine.compile_model

    def wrapped(*args, **kwargs):
        model = original(*args, **kwargs)
        if arm in ("x1", "noise") or getattr(model, "mode", None) not in ("lebail", "pawley"):
            return model
        counts["compiles"] += 1
        for cp in model.phases:
            if cp.hkl_intensity is None:
                continue
            n = len(cp.hkl_intensity)
            if arm == "shaped":
                cp.hkl_intensity = cp.hkl_intensity * rng.lognormal(0.0, 1.0, n)
            else:
                cp.hkl_intensity = cp.hkl_intensity * float(arm[1:])
            counts["rewritten"] += n
        return model

    plan = rx.RefinementPlan.mccusker_default()
    if family == "nac":
        from tests.test_acceptance_nac import LIMITS, build_nac_inputs

        data, st, ins = build_nac_inputs()
        kw = {"two_theta_limits": LIMITS}
        plan.closing_window_tol = None   # the protocol's Le Bail pass, as measured
    else:
        from tests import test_window_domain as w

        data, st, ins, _plan, kw = w._protocol(family)
    refine.compile_model = wrapped
    try:
        ref = rx.Refinement(st, ins, history=False)
        row = {"n_nudged": _nudged(ref)} if arm == "noise" else {}
        result = ref.fit(data, mode=mode, plan=plan, **kw)
    finally:
        refine.compile_model = original
    row.update({"rows": _rows(result), **_stats(result), **counts,
                "closing": plan.closing_window_tol})
    return row


# ---------------------------------------------------------------- (2) flat-axis directions
def _rotation(axis, angle: float) -> np.ndarray:
    from rietx.refine import _rotate

    k = np.asarray(axis, dtype=np.float64)
    k = k / np.linalg.norm(k)
    return np.column_stack([_rotate(e, k, angle) for e in np.eye(3)])


def _special_directions() -> list[np.ndarray]:
    out = []
    for v in ([1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 1, 0], [1, -1, 0], [1, 0, 1], [1, 0, -1],
              [0, 1, 1], [0, 1, -1], [1, 1, 1], [1, 1, -1], [1, -1, 1], [-1, 1, 1]):
        v = np.asarray(v, dtype=np.float64)
        out.append(v / np.linalg.norm(v))
    return out


def flat_pair(arm: str) -> np.ndarray:
    refine = importlib.import_module("rietx.refine")

    shipped = np.array(refine._FLAT_AXIS_TEST_DIRECTIONS, dtype=np.float64)
    if arm in ("shipped", "noise"):
        return shipped
    if arm == "rot30":
        r = _rotation((1.0, 2.0, 3.0), math.radians(30.0))
        return (r @ shipped.T).T
    rng = np.random.default_rng(2017)
    special = _special_directions()
    pair = []
    while len(pair) < 2:
        v = rng.normal(size=3)
        v /= np.linalg.norm(v)
        if all(math.degrees(math.acos(min(1.0, abs(float(v @ s))))) >= 5.0 for s in special):
            pair.append(v)
    return np.array(pair)


def _flat_fit(task: dict) -> dict:
    refine = importlib.import_module("rietx.refine")

    case, arm = task["case"], task["arm"]
    pair = flat_pair(arm)
    shipped = refine._FLAT_AXIS_TEST_DIRECTIONS
    original = refine._flat_rotation_axis
    seen: list = []

    def spy(model, values, base):
        axis = original(model, values, base)
        seen.append({"pair": np.asarray(refine._FLAT_AXIS_TEST_DIRECTIONS).round(6).tolist(),
                     "axis": None if axis is None else np.asarray(axis).tolist()})
        return axis

    truth, start = (1.5, 2.0, 3.0), (3.0, 0.2, 0.2)
    k = 1.0 + NUDGE if arm == "noise" else 1.0
    start = tuple(k * s for s in start)
    refine._FLAT_AXIS_TEST_DIRECTIONS = pair
    refine._flat_rotation_axis = spy
    try:
        if case == "joint":
            from tests import test_joint_flat_moments as j

            orig_phase = j._phase

            def phase(sg, moment, scale=1.0):
                return orig_phase(sg, moment, scale * (k if moment == start else 1.0))

            j._phase = phase
            try:
                joint, result = j._joint("R -3 m:R", truth, start)
            finally:
                j._phase = orig_phase
            fitted = joint.fitted_structures[0].phases[0].atoms[0].moment.values()
        else:
            from tests import test_magnetic as tm

            sg = "R -3 m:R" if case == "rh" else "P 4/m m m"
            start_phase = tm._rhombohedral(start, sg)
            start_phase.scale.value *= k
            ref, result = tm._fit(tm._rhombohedral(truth, sg), start_phase)
            fitted = ref.fitted_structure.phases[0].atoms[0].moment.values()
    finally:
        refine._FLAT_AXIS_TEST_DIRECTIONS = shipped
        refine._flat_rotation_axis = original
    last = result.stages[-1]
    stats = _stats(result)
    if stats["rwp"] is None:
        stats["rwp"] = getattr(getattr(result, "statistics", None), "rwp", None)
    return {"rows": _rows(result), **stats, "pair": pair.round(6).tolist(),
            "spy_calls": len(seen),
            "spy_pairs": sorted({json.dumps(s["pair"]) for s in seen}),
            "spy_axes": [s["axis"] for s in seen if s["axis"] is not None][-3:],
            "held": list(last.held),
            "held_any": sorted({h for s in result.stages for h in s.held}),
            "flat_axes": {k2: list(v) for k2, v in last.moment_flat_axes.items()},
            "turned": list(last.moment_turned),
            "fitted": [float(v) for v in fitted]}


# ---------------------------------------------------------------- (3) arpls max_iter/tol
def _limited(data, limits):
    if limits is None:
        return data
    tt = np.asarray(data.two_theta)
    m = (tt >= limits[0]) & (tt <= limits[1])
    upd = {"two_theta": tt[m].tolist(), "intensity": np.asarray(data.intensity)[m].tolist()}
    if data.sigma is not None:
        upd["sigma"] = np.asarray(data.sigma)[m].tolist()
    return data.model_copy(update=upd)


def _arpls_pattern(pattern: str):
    """(data restricted to the fitted range, fit builder or None)."""
    if pattern == "si640c":
        from tests import test_acceptance_si640c as si

        return _limited(rx.read_pattern(si.PATTERN), si.FULL_LIMITS), si.FULL_LIMITS
    if pattern == "srm1976a":
        from tests import test_acceptance_srm1976a_texture as t

        return _limited(rx.read_pattern(t.PATTERN), t.LIMITS), t.LIMITS
    if pattern == "nac":
        from tests.test_acceptance_nac import LIMITS, build_nac_inputs

        return _limited(build_nac_inputs()[0], LIMITS), LIMITS
    from tests import test_window_domain as w

    data, _s, _i, _p, kw = w._protocol(pattern)
    lim = kw.get("two_theta_limits")
    return _limited(data, lim), lim


def _arpls_reads(data) -> dict:
    from rietx.background import auto, estimators, select

    mask = data.in_range_mask()
    tt, y, sig = data.tt()[mask], data.y()[mask], data.sig()[mask]
    al = estimators.auto_lambda(y)
    sel = select.select_arpls_lambda(data)
    keep = select.peak_mask(tt, y, sig)
    choice = auto.auto_background(data)
    pick = choice.background.model_dump(mode="json")
    return {"auto_lambda": al, "select_lambda": sel.selected, "keep": keep, "y": y, "sig": sig,
            "pick": json.dumps(pick, sort_keys=True), "pick_kind": choice.kind,
            "n_pick": len(json.dumps(pick))}


def _arpls_task(task: dict) -> dict:
    from rietx.background import estimators, select

    pattern, arm = task["pattern"], task["arm"]
    data, _lim = _arpls_pattern(pattern)
    defaults = dict(estimators.arpls.__kwdefaults__)
    base = _arpls_reads(data)
    lams = sorted({select.PEAK_MASK_BASELINE_LAMBDA, base["auto_lambda"], base["select_lambda"],
                   1e7})
    ship_base = {lam: estimators.arpls(base["y"], lam) for lam in lams}
    estimators.arpls.__kwdefaults__.update(max_iter=ARPLS_ARMS[arm][0], tol=ARPLS_ARMS[arm][1])
    try:
        arm_reads = _arpls_reads(data)
        arm_base = {lam: estimators.arpls(base["y"], lam) for lam in lams}
        kw_read = dict(estimators.arpls.__kwdefaults__)
    finally:
        estimators.arpls.__kwdefaults__.update(defaults)
    sig = np.where(base["sig"] > 0, base["sig"], 1.0)
    moves = {f"{lam:.3g}": float(np.max(np.abs(arm_base[lam] - ship_base[lam]) / sig))
             for lam in lams}
    flips = int(np.sum(arm_reads["keep"] != base["keep"]))
    return {"kwdefaults_read": kw_read, "lams": lams, "baseline_move_sigma": moves,
            "mask_flips": flips, "n_background": int(np.sum(base["keep"])),
            "auto_lambda": [base["auto_lambda"], arm_reads["auto_lambda"]],
            "select_lambda": [base["select_lambda"], arm_reads["select_lambda"]],
            "pick_kind": [base["pick_kind"], arm_reads["pick_kind"]],
            "pick_same": base["pick"] == arm_reads["pick"],
            "refit": None if base["pick"] == arm_reads["pick"] else "owed: pick changed"}


# ---------------------------------------------------------------- (4) FLOOR_SEEDS
class _Counting(dict):
    reads = 0

    def get(self, key, default=None):
        type(self).reads += 1
        return super().get(key, default)


def _floor_fit(task: dict) -> dict:
    from rietx.optimize import least_squares as ls
    from rietx.params import vector

    family, arm = task["family"], task["arm"]
    shipped = dict(vector.FLOOR_SEEDS)
    factor = {"x10": 10.0, "d10": 0.1}.get(arm, 1.0)
    counting = _Counting({k: v * factor for k, v in shipped.items()})
    _Counting.reads = 0
    orig_ls = ls.FLOOR_SEEDS
    vector.FLOOR_SEEDS.update(counting)
    ls.FLOOR_SEEDS = counting
    try:
        from tests import test_window_domain as w

        data, st, ins, plan, kw = w._protocol(family)
        ref = rx.Refinement(st, ins, history=False)
        row = {"n_nudged": _nudged(ref)} if arm == "noise" else {}
        result = ref.fit(data, plan=plan, **kw)
    finally:
        ls.FLOOR_SEEDS = orig_ls
        vector.FLOOR_SEEDS.update(shipped)
    units = {p.path: getattr(p, "unit", None) for p in result.parameters}
    row.update({"rows": _rows(result), **_stats(result), "seeds": dict(counting),
                "floor_reads": _Counting.reads,
                "units": {k: v for k, v in units.items() if v in shipped}})
    if result.qpa is not None:
        row["fractions"] = {f.name: 100.0 * f.weight_fraction for f in result.qpa.phases}
    return row


# ---------------------------------------------------------------- driver
def _key(t: dict) -> tuple:
    return tuple(t[k] for k in ("part", "family", "mode", "case", "pattern", "arm") if k in t)


def run_one(task: dict) -> dict:
    warnings.simplefilter("ignore")
    compiled.set_enabled(True)
    row = dict(task)
    try:
        fn = {"seed": _seed_fit, "flat": _flat_fit, "arpls": _arpls_task,
              "floor": _floor_fit}[task["part"]]
        row.update(fn(task))
    except Exception as exc:  # noqa: BLE001  a refused fit is a result of the sweep
        row["error"] = importlib.import_module("group_a")._error_line(exc)
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


def _tasks(parts=("seed", "flat", "arpls", "floor")) -> list[dict]:
    tasks: list[dict] = []
    if "floor" in parts:
        tasks += [{"part": "floor", "family": f, "arm": a}
                  for f in ("lab6", "cpd1a", "nac", "fap") for a in FLOOR_ARMS]
    if "flat" in parts:
        tasks += [{"part": "flat", "case": c, "arm": a} for c in FLAT_CASES for a in FLAT_ARMS]
    if "seed" in parts:
        tasks += [{"part": "seed", "family": f, "mode": m, "arm": a}
                  for f in ("lab6", "nac", "fap") for m in SEED_MODES for a in SEED_ARMS]
    if "arpls" in parts:
        tasks += [{"part": "arpls", "pattern": p, "arm": a}
                  for p in ARPLS_PATTERNS for a in ARPLS_ARMS]
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


#: the width rows (``RefinedParameter`` carries no unit): Caglioti terms, X/Y, sample widths
WIDTH = re.compile(r"\.profile\.(u|v|w|x|y)$|\.(lor_size|lor_strain|gauss_size|gauss_strain)$")
SL = "instrument.geometry.axial_sl"
HL = "instrument.geometry.axial_hl"


def _ordered(rows: dict) -> dict:
    if SL in rows and HL in rows and rows[SL][0] > rows[HL][0]:
        rows = dict(rows)
        rows[SL], rows[HL] = rows[HL], rows[SL]
    return rows


def _shift(cur: dict, ref: dict):
    """Largest |cur − ref| over the larger plain esd, rows that are not background."""
    cur, ref = _ordered(cur), _ordered(ref)
    worst = (0.0, None)
    for path, (value, e1) in cur.items():
        if path.startswith("instrument.background.") or path not in ref:
            continue
        v0, e0 = ref[path]
        esds = [e for e in (e0, e1) if e is not None and math.isfinite(e) and e > 0.0]
        if not esds:
            continue
        worst = max(worst, (abs(value - v0) / max(esds), path), key=lambda t: t[0])
    return worst


def _missing(cur: dict, ref: dict) -> str:
    gone = sorted(set(ref) ^ set(cur))
    return ", ".join(f"`{g}`" for g in gone[:3]) + (" …" if len(gone) > 3 else "")


def _same(a: dict, b: dict) -> bool:
    return a["rows"] == b["rows"] and a.get("rwp") == b.get("rwp") and a["n_eval"] == b["n_eval"]


def _axis_angle(a, b) -> float | None:
    if not a or not b:
        return None
    u, v = np.asarray(a, float), np.asarray(b, float)
    c = abs(float(u @ v)) / float(np.linalg.norm(u) * np.linalg.norm(v))
    return math.degrees(math.acos(min(1.0, c)))


def _cmp_line(r: dict, base: dict) -> str:
    if r is base:
        return "—"
    s = _shift(r["rows"], base["rows"])
    tag = " (bit-identical)" if _same(r, base) else ""
    miss = _missing(r["rows"], base["rows"])
    return f"{_fmt(s[0])} `{s[1]}`{tag}" + (f"; rows differ: {miss}" if miss else "")


def summary() -> None:
    rows = read_rows()
    latest = {_key(r): r for r in rows}
    meta = next((r["meta"] for r in rows if "meta" in r), {})
    L = ["# WP-2017 group N: the four hand rows", "",
         "Written by `group_n.py summary` from the raw rows of the workstation run; claims, "
         "fits and arms in its docstring.",
         f"Commit `{meta.get('head', '?')[:9]}`, {meta.get('platform', '?')}, numpy "
         f"{meta.get('numpy', '?')}, rietx-kernels {meta.get('kernels', '?')}, compiled tier on, "
         "one kernel thread.", "",
         "Every comparison: the arm against the shipped arm in plain esd over the larger esd, "
         "every row that is not a background coefficient, S/L and H/L ordered (0.1 bar); "
         "`noise` the nudged twin of shipped.", ""]

    L += ["## (1) The Le Bail/Pawley intensity seed", "",
          "| Family | Mode | Arm | Rwp | evals | status | compiles rewritten | reflections "
          "rewritten | against x1 | codes that differ |", "|---|---|---|---|---|---|---|---|---|---|"]
    for f in SEED_FAMILIES:
        for m in SEED_MODES:
            base = latest.get(("seed", f, m, "x1"))
            for a in SEED_ARMS:
                r = latest.get(("seed", f, m, a))
                if r is None:
                    continue
                if "error" in r:
                    L.append(f"| `{f}` | {m} | {a} | {r['error']} |||||||")
                    continue
                cmp = _cmp_line(r, base) if base and "error" not in base and a != "x1" else "—"
                codes = (set(r["codes"]) ^ set(base["codes"])) if base and "error" not in base \
                    else set()
                L.append(f"| `{f}` | {m} | {a} | {_fmt(r['rwp'], '.6f')} | {r['n_eval']} | "
                         f"{r['status']} | {r['compiles']} | {r['rewritten']} | {cmp} | "
                         f"{', '.join(sorted(codes)) or '—'} |")

    L += ["", "## (2) `refine._FLAT_AXIS_TEST_DIRECTIONS`", "",
          "Held: the last stage's held rows. Flat axis: the stage record's axis (crystal axes); "
          "angle: between this arm's axis and shipped's. Spy: `_flat_rotation_axis` calls and the "
          "pairs it read (control: the arm's pair must be among them). The patterns are noise-free, so "
          "an esd here is a rounding-scale number (1e-18 to 1e-13): the moment rows' largest "
          "absolute change (rad, μ_B) rides beside the esd reading.", "",
          "| Case | Arm | Rwp | evals | status | held | flat axis | angle to shipped's (°) | "
          "turned | spy calls | spy saw arm's pair | against shipped |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in FLAT_CASES:
        base = latest.get(("flat", c, "shipped"))
        for a in FLAT_ARMS:
            r = latest.get(("flat", c, a))
            if r is None:
                continue
            if "error" in r:
                L.append(f"| `{c}` | {a} | {r['error']} ||||||||||")
                continue
            ax = next(iter(r["flat_axes"].values()), None)
            bax = next(iter(base["flat_axes"].values()), None) if base and "error" not in base \
                else None
            saw = json.dumps(r["pair"]) in r["spy_pairs"] if r["spy_calls"] else "no call"
            cmp = _cmp_line(r, base) if base and "error" not in base and a != "shipped" else "—"
            if cmp != "—":
                d = max(abs(v[0] - base["rows"][k][0]) for k, v in r["rows"].items()
                        if ".moment." in k and k in base["rows"])
                cmp += f"; moment rows Δ ≤ {d:.1e}"
            L.append(f"| `{c}` | {a} | {_fmt(r['rwp'], '.6f')} | {r['n_eval']} | {r['status']} | "
                     f"{', '.join(h.rsplit('.', 1)[-1] for h in r['held']) or 'none'} | "
                     f"{'(' + ', '.join(f'{v:.4f}' for v in ax) + ')' if ax else '—'} | "
                     f"{_fmt(_axis_angle(ax, bax), '.2g')} | {len(r['turned'])} | "
                     f"{r['spy_calls']} | {saw} | {cmp} |")

    L += ["", "## (3) `arpls`'s `max_iter` and `tol`", "",
          "Baseline move: the largest |arm − shipped| / σ over the fitted channels at each λ a "
          "caller passes (1e7 = `PEAK_MASK_BASELINE_LAMBDA` and the default; `auto_lambda`'s and "
          "`select_arpls_lambda`'s shipped picks). Mask flips: channels `peak_mask` moves between "
          "background and peak. λ picks and `auto_background`'s pick: shipped → arm.", "",
          "| Pattern | Arm | kwdefaults read | baseline move (σ) at λ | mask flips / background "
          "channels | `auto_lambda` | `select_arpls_lambda` | `auto_background` pick |",
          "|---|---|---|---|---|---|---|---|"]
    for p in ARPLS_PATTERNS:
        for a in ARPLS_ARMS:
            r = latest.get(("arpls", p, a))
            if r is None:
                continue
            if "error" in r:
                L.append(f"| `{p}` | {a} | {r['error']} ||||||")
                continue
            kw = r["kwdefaults_read"]
            mv = "; ".join(f"{k}: {_fmt(v)}" for k, v in r["baseline_move_sigma"].items())
            L.append(f"| `{p}` | {a} | {kw['max_iter']}, {kw['tol']:g} | {mv} | "
                     f"{r['mask_flips']} / {r['n_background']} | "
                     f"{r['auto_lambda'][0]:.0e} → {r['auto_lambda'][1]:.0e} | "
                     f"{r['select_lambda'][0]:.0e} → {r['select_lambda'][1]:.0e} | "
                     f"{'same' if r['pick_same'] else 'CHANGED (' + r['pick_kind'][1] + ')'} |")

    L += ["", "## (4) `params.vector.FLOOR_SEEDS`", "",
          "Floor reads: `least_squares` reads of the table during the fit (control: 0 means the "
          "arm measured nothing). Width esd ratio: the arm's plain esd over shipped's on the rows "
          "whose unit is in the table (the Caglioti terms, X, Y and the sample widths), smallest "
          "and largest.", "",
          "| Family | Arm | Rwp | evals | status | floor reads | against shipped | width esd ratio "
          "(min, max) | codes that differ |", "|---|---|---|---|---|---|---|---|---|"]
    for f in FLOOR_FAMILIES:
        base = latest.get(("floor", f, "shipped"))
        for a in FLOOR_ARMS:
            r = latest.get(("floor", f, a))
            if r is None:
                continue
            if "error" in r:
                L.append(f"| `{f}` | {a} | {r['error']} |||||||")
                continue
            ratio, cmp, codes = "—", "—", set()
            if base and "error" not in base and a != "shipped":
                cmp = _cmp_line(r, base)
                widths = r["units"] or [k for k in r["rows"] if WIDTH.search(k)]
                rs = [r["rows"][k][1] / base["rows"][k][1] for k in widths
                      if k in base["rows"] and r["rows"][k][1] and base["rows"][k][1]]
                ratio = f"{min(rs):.4f}, {max(rs):.4f}" if rs else "no width row"
                codes = set(r["codes"]) ^ set(base["codes"])
            L.append(f"| `{f}` | {a} | {_fmt(r['rwp'], '.6f')} | {r['n_eval']} | {r['status']} | "
                     f"{r['floor_reads']} | {cmp} | {ratio} | {', '.join(sorted(codes)) or '—'} |")
    L += ["", "Width rows whose esd moved by more than a factor of two (plain esd, shipped → arm):",
          ""]
    for f in FLOOR_FAMILIES:
        base = latest.get(("floor", f, "shipped"))
        if not base or "error" in base:
            continue
        for a in FLOOR_ARMS[1:]:
            r = latest.get(("floor", f, a))
            if not r or "error" in r:
                continue
            for k, (v, e) in r["rows"].items():
                v0, e0 = base["rows"].get(k, (None, None))
                if WIDTH.search(k) and e and e0 and not 0.5 <= e / e0 <= 2.0:
                    L.append(f"- `{f}` {a}: `{k}` at {v0:.4g}, esd {e0:.3g} → {e:.3g}")
    L.append("")
    SUMMARY.write_text("\n".join(L), encoding="utf-8")
    print(SUMMARY)


def main(argv: list[str]) -> None:
    mode = argv[1] if len(argv) > 1 else "all"
    if mode == "summary":
        summary()
        return
    if mode == "canary":
        sweep([{"part": "seed", "family": "fap", "mode": "lebail", "arm": "x1"},
               {"part": "seed", "family": "fap", "mode": "lebail", "arm": "x100"},
               {"part": "flat", "case": "rh", "arm": "shipped"},
               {"part": "flat", "case": "rh", "arm": "rot30"},
               {"part": "arpls", "pattern": "fap", "arm": "loose"}])
        return
    if mode in ("seed", "flat", "arpls", "floor"):
        sweep(_tasks((mode,)))
        return
    sweep(_tasks())


if __name__ == "__main__":
    main(sys.argv)
