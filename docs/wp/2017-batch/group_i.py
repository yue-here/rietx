"""WP-2017 group I: the position bounds' removal on three laboratory flat plates.

On 2026-10-20 (commit 3d63e9db5) ``Instrument.zero_shift`` lost its default ±0.5°,
``Geometry.sample_displacement`` and the two capillary offsets their ±1 mm, and
``sample_transparency`` its ceiling of 0.05.  One family stood behind it, 11-BM NAC, where
the bound acted as a prior that held.  Fits and arms were fixed in WP-2017 § What each group
inherits, "I, its fits and arms", before anything ran (2026-11-16).

Families (Bragg-Brentano flat plates; each protocol holds the zero shift):

- ``fap``: lab FAP under its GSAS protocol, 15-130°.  Reference GSAS's cell.
- ``lab6``: NIST SRM 660c under the calibrated protocol, 20.3-150.9°.  Reference the CIF
  block's cell and displacement.
- ``srm1976a``: the sintered SRM 1976a plate (X'Pert) under its TOPAS-mirrored textured
  protocol, 20-118.6°, with a cell stage added (the protocol holds the cell).  Reference the
  TOPAS file's held cell and refined displacement.

Ranges: ``full`` (the protocol's) and ``narrow`` (from its low end to the 2θ at which the
smallest eigenvalue of the unit-column Gram of {1, cos θ, tan θ} on the pattern's channels
reaches NAC's capillary trio over 2-24°).  Arms: ``shipped`` (zero held); ``free`` (zero on
with the displacement, unbounded); ``bounded`` (``free`` with the pre-1.10 bounds);
``noise`` (``free`` nudged 1e-12).  Positive arm: 11-BM NAC 2-24°, zero and both offsets
free, ``free`` against ``bounded``, which must repeat 1097 and about 5111 ppm.

    .venv/bin/python docs/wp/2017-batch/group_i.py          # every family, range and arm
    .venv/bin/python docs/wp/2017-batch/group_i.py canary   # srm1976a narrow free + bounded
    .venv/bin/python docs/wp/2017-batch/group_i.py summary  # write group_i_summary.md

``WP2017I_RAW`` names the raw directory (default ``~/.cache/rietx/wp-2017-i``);
``WP2017I_WORKERS`` the pool (default 4).  Figures: ``tests/output/wp2017_groupI_*.png``.
"""

from __future__ import annotations

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

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
os.environ.setdefault("RIETX_TELEMETRY", "0")
os.environ.setdefault("MPLBACKEND", "Agg")

from rietx._about import COMPILED_THREADS_ENV  # noqa: E402

os.environ.setdefault(COMPILED_THREADS_ENV, "1")

import numpy as np  # noqa: E402

import rietx as rx  # noqa: E402
from rietx.model import compiled  # noqa: E402

RAW = Path(os.environ.get("WP2017I_RAW", Path.home() / ".cache" / "rietx" / "wp-2017-i"))
JSONL = RAW / "group_i.jsonl"
SUMMARY = HERE / "group_i_summary.md"
OUT = ROOT / "tests" / "output"
WORKERS = int(os.environ.get("WP2017I_WORKERS", "4"))

FAMILIES = ("fap", "lab6", "srm1976a")
RANGES = ("full", "narrow")
ARMS = ("shipped", "free", "bounded", "noise")
NAC_ARMS = ("shipped", "free", "bounded")
NUDGE = 1e-12
ZERO = "instrument.zero_shift"
DISP = "instrument.geometry.sample_displacement"
TRANSP = "instrument.geometry.sample_transparency"
#: the pre-1.10 defaults (3d63e9db5): (min, max)
OLD_BOUNDS = {ZERO: (-0.5, 0.5), DISP: (-1.0, 1.0), TRANSP: (0.0, 0.05)}
AT_BOUND = 1e-6

#: (reference cell rows, reference displacement mm or None, source)
REFERENCES = {
    "fap": ({"a": 9.371724, "c": 6.885867}, None, "GSAS's converged FAP.EXP"),
    "lab6": ({"a": 4.156780}, -0.07877, "the CIF block (20.85 °C)"),
    "srm1976a": ({"a": 4.758877, "c": 12.992880}, -0.08930, "the TOPAS .inp (cell held there)"),
    "nac": ({"a": 10.2510}, None, "the NAC acceptance band's centre"),
}


def _old_bounds(ins, paths) -> None:
    """Put the pre-1.10 default bounds back on the named instrument parameters."""
    for path in paths:
        lo, hi = OLD_BOUNDS.get(path, (-1.0, 1.0))      # the capillary offsets: ±1 mm
        owner, name = (ins, "zero_shift") if path == ZERO else (
            ins.geometry, path.rsplit(".", 1)[1])
        p = getattr(owner, name)
        setattr(owner, name, p.model_copy(update={"min": lo, "max": hi}))


def _flat_trio_eigenvalue(tt: np.ndarray) -> float:
    """Smallest eigenvalue of the unit-column Gram of {1, cos θ, tan θ}: zero shift,
    flat-plate displacement and a cell's shift on these channels."""
    th = np.radians(tt / 2.0)
    cols = np.vstack([np.ones_like(th), np.cos(th), np.tan(th)])
    cols /= np.linalg.norm(cols, axis=1, keepdims=True)
    return float(np.linalg.eigvalsh(cols @ cols.T).min())


def _nac_target() -> float:
    from tests.test_acceptance_nac import LIMITS, build_nac_inputs
    from tests.test_capillary_displacement import _trio_min_eigenvalue

    data = build_nac_inputs()[0]
    tt = np.asarray(data.two_theta, dtype=float)
    return _trio_min_eigenvalue(tt[(tt >= LIMITS[0]) & (tt <= LIMITS[1])])


def narrow_limits(tt: np.ndarray, lo: float, hi: float, target: float) -> tuple[float, float]:
    """(lo, x): the smallest x on the channels at which the trio's eigenvalue reaches target."""
    tt = np.sort(tt[(tt >= lo) & (tt <= hi)])
    for x in tt[20:]:
        if _flat_trio_eigenvalue(tt[tt <= x]) >= target:
            return float(tt[0]), float(x)
    return float(tt[0]), float(tt[-1])


def build(family: str):
    """(data, structure, instrument, plan, (lo, hi), prepare)."""
    if family == "srm1976a":
        from tests import test_acceptance_srm1976a_texture as t

        data = rx.read_pattern(t.PATTERN)
        st, ins = t._structure(True), t._instrument()
        stages = [
            rx.Stage("scale_bkg", ["phases.0.scale", "instrument.background.*"]),
            rx.Stage("displacement", [DISP]),
            rx.Stage("cell", ["phases.0.cell.*"]),          # added: the protocol holds it
            rx.Stage("w", ["instrument.profile.w"]),
            rx.Stage("widths", ["instrument.profile.u", "instrument.profile.v",
                                "instrument.profile.x", "instrument.profile.y"]),
            rx.Stage("biso", ["phases.0.atoms.*.biso"]),
            rx.Stage("texture", ["phases.0.texture.*"]),
            rx.Stage("aberrations", [TRANSP, "instrument.geometry.axial_sl"]),
            rx.Stage("final", ["phases.0.atoms.*.biso", "phases.0.texture.*"]),
        ]
        plan = rx.RefinementPlan(stages=stages, intermediate_ftol=1e-6, closing_window_tol=1e-3)

        def prepare(ref):
            ref.tie_equal(["instrument.geometry.axial_sl", "instrument.geometry.axial_hl"])

        return data, st, ins, plan, t.LIMITS, prepare
    from tests import test_window_domain as w

    data, st, ins, plan, _ = w._protocol(family)
    tt = np.asarray(data.two_theta, dtype=float)
    return data, st, ins, plan, (float(tt.min()), float(tt.max())), None


def _free_zero(plan) -> None:
    """Turn the zero shift on in the stage that turns the displacement on: one block."""
    for stage in plan.stages:
        if DISP in stage.turn_on:
            stage.turn_on = [*stage.turn_on, ZERO]
            return
    raise RuntimeError("no displacement stage")


def _nudged(ref: rx.Refinement) -> int:
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


def _nac(arm: str):
    from tests.test_acceptance_nac import LIMITS, build_nac_inputs
    from tests.test_capillary_displacement import ACROSS_PATH, ALONG_PATH

    data, st, ins = build_nac_inputs()
    plan = rx.RefinementPlan.mccusker_default()
    if arm != "shipped":
        ins.geometry.goniometer_radius_mm = 1000.0
        plan.stages.append(rx.Stage("capillary_displacement", [ZERO, ALONG_PATH, ACROSS_PATH]))
        if arm == "bounded":
            _old_bounds(ins, [ZERO, ALONG_PATH, ACROSS_PATH])
    return data, st, ins, plan, LIMITS, None


def fit_one(task: dict) -> dict:
    family, rng, arm = task["family"], task["range"], task["arm"]
    warnings.simplefilter("ignore")
    compiled.set_enabled(True)
    row: dict = {"family": family, "range": rng, "arm": arm}
    try:
        if family == "nac":
            data, st, ins, plan, limits, prepare = _nac(arm)
        else:
            data, st, ins, plan, limits, prepare = build(family)
            if rng == "narrow":
                limits = tuple(task["limits"])
            if arm != "shipped":
                _free_zero(plan)
            if arm == "bounded":
                _old_bounds(ins, [ZERO, DISP, TRANSP])
        row["limits"] = list(limits)
        ref = rx.Refinement(st, ins, history=False)
        if prepare:
            prepare(ref)
        if arm == "noise":
            row["n_nudged"] = _nudged(ref)
        result = ref.fit(data, plan=plan, two_theta_limits=limits)
        OUT.mkdir(parents=True, exist_ok=True)
        png = OUT / f"wp2017_groupI_{family}_{rng}_{arm}.png"
        result.plot(path=str(png))
        import matplotlib.pyplot as plt

        plt.close("all")
        row.update({
            "rows": {p.path: [p.value, p.stderr_uncorrected] for p in result.parameters},
            # the reported esd (Bérar-Lelann inflated), the one the reference page means
            "esd_reported": {p.path: p.stderr for p in result.parameters},
            "esd_factor": getattr(result.statistics, "esd_inflation", None),
            "rwp": result.statistics.rwp, "status": result.status,
            "n_eval": int(sum(s.n_iterations for s in result.stages)),
            "codes": sorted({d.code for d in result.diagnostics}),
            "flat": [sorted(d.where) for d in result.diagnostics if d.code == "FLAT_DIRECTION"],
            "bound_hit": [sorted(d.where) for d in result.diagnostics
                          if d.code in ("BOUND_HIT", "FLOOR_HIT")],
            "png": str(png.relative_to(ROOT)),
        })
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


def ranges() -> dict:
    """Each family's narrow range, computed from its channels before any fit."""
    path = RAW / "ranges.json"
    if path.exists():
        return json.loads(path.read_text())
    target = _nac_target()
    out = {"nac_target": target}
    for family in FAMILIES:
        data, _, _, _, (lo, hi), _ = build(family)
        tt = np.asarray(data.two_theta, dtype=float)
        nlo, nhi = narrow_limits(tt, lo, hi, target)
        sel = tt[(tt >= lo) & (tt <= hi)]
        out[family] = {"full": [lo, hi], "narrow": [nlo, nhi],
                       "eig_full": _flat_trio_eigenvalue(sel),
                       "eig_narrow": _flat_trio_eigenvalue(sel[sel <= nhi])}
    RAW.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1))
    return out


def _tasks(families=FAMILIES, rngs=RANGES, arms=ARMS, nac=True) -> list[dict]:
    lim = ranges()
    tasks = [{"family": f, "range": r, "arm": a, "limits": lim[f][r]}
             for f in families for r in rngs for a in arms]
    if nac:
        tasks += [{"family": "nac", "range": "full", "arm": a, "limits": None} for a in NAC_ARMS]
    return tasks


def sweep(tasks: list[dict]) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    done = {(r["family"], r["range"], r["arm"]) for r in read_rows() if "error" not in r}
    todo = [t for t in tasks if (t["family"], t["range"], t["arm"]) not in done]
    if not todo:
        return
    with ProcessPoolExecutor(max_workers=max(1, min(WORKERS, len(todo))),
                             mp_context=get_context("spawn")) as pool:
        for future in as_completed([pool.submit(fit_one, t) for t in todo]):
            row = future.result()
            row["meta"] = _meta()
            with JSONL.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
            print(row["family"], row["range"], row["arm"],
                  row.get("error") or f"{row['rwp']:.7f} {row['n_eval']} {row['status']}",
                  flush=True)


def _fmt(x, spec=".3g") -> str:
    return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, spec)


def _shift(cur: dict, ref: dict, paths=None):
    """Largest |cur − ref| over the larger plain esd, non-background rows (or ``paths``)."""
    worst = (0.0, None)
    for path, (value, e1) in cur.items():
        if path.startswith("instrument.background.") or path not in ref:
            continue
        if paths is not None and path not in paths:
            continue
        v0, e0 = ref[path]
        esds = [e for e in (e0, e1) if e is not None and math.isfinite(e) and e > 0.0]
        if not esds:
            continue
        worst = max(worst, (abs(value - v0) / max(esds), path), key=lambda t: t[0])
    return worst


def _cell_paths(rows: dict) -> list[str]:
    return [p for p in rows if p.startswith("phases.0.cell.") and p.rsplit(".", 1)[1] in "abc"]


def _bound_reached(row: dict) -> list[str]:
    hits = []
    for path, (lo, hi) in OLD_BOUNDS.items():
        if path in row["rows"]:
            v = row["rows"][path][0]
            if v - lo <= AT_BOUND or hi - v <= AT_BOUND:
                hits.append(path.rsplit(".", 1)[1])
    for path in row["rows"]:
        if "capillary_offset" in path:
            v = row["rows"][path][0]
            if 1.0 - abs(v) <= AT_BOUND:
                hits.append(path.rsplit(".", 1)[1])
    return hits


def summary() -> None:
    rows = {(r["family"], r["range"], r["arm"]): r for r in read_rows()}
    lim = ranges()
    meta = next((r["meta"] for r in rows.values() if "meta" in r), {})
    lines = [
        "# WP-2017 group I: the position bounds' removal on three flat plates",
        "",
        "Written by `docs/wp/2017-batch/group_i.py summary` from its raw rows (not committed).",
        f"Commit `{meta.get('head', '?')[:9]}`, {meta.get('platform', '?')}, numpy "
        f"{meta.get('numpy', '?')}, rietx-kernels {meta.get('kernels', '?')}, compiled tier on, "
        "one kernel thread.",
        "",
        f"Narrow range: the 2θ at which the {{1, cos θ, tan θ}} Gram eigenvalue reaches NAC's "
        f"capillary trio over 2-24°, {lim['nac_target']:.3g}.",
        "",
        "| Family | full | eig | narrow | eig |",
        "|---|---|---|---|---|",
    ]
    for f in FAMILIES:
        r = lim[f]
        lines.append(f"| `{f}` | {r['full'][0]:.1f}-{r['full'][1]:.1f}° | {r['eig_full']:.2g} | "
                     f"{r['narrow'][0]:.1f}-{r['narrow'][1]:.1f}° | {r['eig_narrow']:.2g} |")
    lines += [
        "",
        "Cell: each cell row's distance from the reference in ppm, then in its own plain esd and "
        "in its reported (inflated) esd. "
        "Zero (°) and displacement (mm) with plain esds. `b−f`: largest shift of any "
        "non-background row, bounded against free, in plain esd over the larger esd "
        "(0.1 bar); `f−s` the same, free against shipped; `noise`: free against its nudged twin.",
        "",
        "| Family | Range | Arm | Rwp | evals | cell ppm (esd) | zero | displacement | "
        "at old bound | codes |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    cmp_lines = ["", "| Family | Range | b−f | f−s | noise | bounded reached |",
                 "|---|---|---|---|---|---|"]
    for f in (*FAMILIES, "nac"):
        cell_ref, _, _ = REFERENCES[f]
        for rng in (RANGES if f != "nac" else ("full",)):
            for arm in (ARMS if f != "nac" else NAC_ARMS):
                r = rows.get((f, rng, arm))
                if r is None:
                    continue
                if "error" in r:
                    lines.append(f"| `{f}` | {rng} | {arm} | {r['error']} |||||||")
                    continue
                cells = []
                for p in _cell_paths(r["rows"]):
                    ax = p.rsplit(".", 1)[1]
                    if ax not in cell_ref:
                        continue
                    v, e = r["rows"][p]
                    ppm = 1e6 * (v - cell_ref[ax]) / cell_ref[ax]
                    k = abs(v - cell_ref[ax]) / e if e else float("nan")
                    er = (r.get("esd_reported") or {}).get(p)
                    kr = abs(v - cell_ref[ax]) / er if er else float("nan")
                    cells.append(f"{ax} {ppm:+.0f} ({_fmt(k, '.2f')}; {_fmt(kr, '.2f')})")
                z = r["rows"].get(ZERO)
                d = r["rows"].get(DISP) or next(
                    (v for p, v in r["rows"].items() if "capillary_offset" in p), None)
                offs = [f"{v[0]:+.3f}±{_fmt(v[1], '.2g')}" for p, v in r["rows"].items()
                        if "capillary_offset" in p]
                disp = ", ".join(offs) if f == "nac" and offs else (
                    f"{d[0]:+.4f}±{_fmt(d[1], '.2g')}" if d else "held")
                zero = f"{z[0]:+.4f}±{_fmt(z[1], '.2g')}" if z else "held"
                codes = [c for c in r["codes"] if c in ("FLAT_DIRECTION", "HIGH_CORRELATION",
                                                         "BOUND_HIT", "FLOOR_HIT")]
                lines.append(f"| `{f}` | {rng} | {arm} | {r['rwp']:.5f} | {r['n_eval']} | "
                             f"{'; '.join(cells)} | {zero} | {disp} | "
                             f"{', '.join(_bound_reached(r)) or '—'} | {', '.join(codes) or '—'} |")
            fr, bd = rows.get((f, rng, "free")), rows.get((f, rng, "bounded"))
            sh, nz = rows.get((f, rng, "shipped")), rows.get((f, rng, "noise"))
            ok = [x for x in (fr, bd, sh, nz) if x and "error" not in x]
            if fr in ok and bd in ok:
                same = fr["rows"] == bd["rows"] and fr["rwp"] == bd["rwp"] \
                    and fr["n_eval"] == bd["n_eval"]
                reached = bool(_bound_reached(bd) or bd["bound_hit"])
                bf = _shift(bd["rows"], fr["rows"])
                fs = _shift(fr["rows"], sh["rows"]) if sh in ok else (None, None)
                nn = _shift(nz["rows"], fr["rows"]) if nz in ok else (None, None)
                verdict = "unreached (bit-identical)" if same and not reached else (
                    "yes" if reached else "no, but not identical")
                cmp_lines.append(
                    f"| `{f}` | {rng} | {_fmt(bf[0])} `{bf[1]}` | {_fmt(fs[0])} `{fs[1]}` | "
                    f"{_fmt(nn[0])} | {verdict} |")
    lines += cmp_lines
    lines += ["", "Figures: `tests/output/wp2017_groupI_<family>_<range>_<arm>.png`.", ""]
    SUMMARY.write_text("\n".join(lines), encoding="utf-8")
    print(SUMMARY)


def main(argv: list[str]) -> None:
    mode = argv[1] if len(argv) > 1 else "all"
    if mode == "summary":
        summary()
        return
    if mode == "ranges":
        print(json.dumps(ranges(), indent=1))
        return
    if mode == "canary":
        sweep([t for t in _tasks(("srm1976a",), ("narrow",), ("free", "bounded"), nac=False)])
        return
    sweep(_tasks())


if __name__ == "__main__":
    main(sys.argv)
