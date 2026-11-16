"""WP-2017 group J: Le Bail and Pawley refining the Kα2/Kα1 weight, against Rietveld.

Since 84b9e87a2 (WP-2002, 2026-10-20) Le Bail and Pawley refine ``.source.lines.``.  One
standard stood behind it, SRM 660c, where Le Bail's ratio sat 1.7σ from Rietveld's.  Fits and
arms were fixed in WP-2017 § What each group inherits, "J, its fits and arms", before anything
ran (2026-11-16).

Families: ``lab6`` (SRM 660c, NIST calibrated protocol, weight already free), ``fap`` (FAP,
GSAS protocol) and ``srm1976a`` (SRM 1976a, textured TOPAS-mirrored protocol), the last two
with a ``lines`` stage appended that frees the Kα2 weight alone.  Arms: ``<mode>`` (weight
free), ``<mode>_held`` (weight held at its 0.5 start) and ``<mode>_noise`` for each of
rietveld, lebail and pawley.  Positive arm: SRM 660c repeats WP-2002's three ratios.

    .venv/bin/python docs/wp/2017-batch/group_j.py          # every family and arm
    .venv/bin/python docs/wp/2017-batch/group_j.py canary   # srm1976a rietveld + lebail
    .venv/bin/python docs/wp/2017-batch/group_j.py summary  # write group_j_summary.md

``WP2017J_RAW`` names the raw directory (default ``~/.cache/rietx/wp-2017-j``);
``WP2017J_WORKERS`` the pool (default 4).  Figures: ``tests/output/wp2017_groupJ_*.png``.
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

import rietx as rx  # noqa: E402
from rietx.model import compiled  # noqa: E402

RAW = Path(os.environ.get("WP2017J_RAW", Path.home() / ".cache" / "rietx" / "wp-2017-j"))
JSONL = RAW / "group_j.jsonl"
SUMMARY = HERE / "group_j_summary.md"
OUT = ROOT / "tests" / "output"
WORKERS = int(os.environ.get("WP2017J_WORKERS", "4"))

FAMILIES = ("lab6", "fap", "srm1976a")
MODES = ("rietveld", "lebail", "pawley")
ARMS = tuple(f"{m}{s}" for m in MODES for s in ("", "_held", "_noise"))
NUDGE = 1e-12
WEIGHT = "instrument.source.lines.1.weight"
LINES = "instrument.source.lines.*.weight"
#: WP-2002's SRM 660c ratios (2nd session of 2026-10-20), the positive arm
WP2002 = {"rietveld": (0.5126, 0.0048), "pawley": (0.5145, 0.0036), "lebail": (0.5224, 0.0033)}
DEGENERACY = 0.5


def build(family: str):
    """(data, structure, instrument, plan, fit kwargs, prepare): the weight free."""
    if family == "srm1976a":
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
            rx.Stage("lines", [LINES]),                     # added: the Kα2 weight alone
        ]
        plan = rx.RefinementPlan(stages=stages, intermediate_ftol=1e-6, closing_window_tol=1e-3)

        def prepare(ref):
            ref.tie_equal(["instrument.geometry.axial_sl", "instrument.geometry.axial_hl"])

        return data, st, ins, plan, {"two_theta_limits": t.LIMITS}, prepare
    from tests import test_window_domain as w

    data, st, ins, plan, kw = w._protocol(family)
    if not any(LINES in s.turn_on for s in plan.stages):
        plan.stages.append(rx.Stage("lines", [LINES]))
    return data, st, ins, plan, kw, None


def _held(plan) -> None:
    """Take the weight out of every stage (an emptied stage goes)."""
    for stage in plan.stages:
        stage.turn_on = [g for g in stage.turn_on if g != LINES]
    plan.stages = [s for s in plan.stages if s.turn_on]


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


def fit_one(task: dict) -> dict:
    family, arm = task["family"], task["arm"]
    mode = arm.split("_")[0]
    warnings.simplefilter("ignore")
    compiled.set_enabled(True)
    row: dict = {"family": family, "arm": arm, "mode": mode}
    try:
        data, st, ins, plan, kw, prepare = build(family)
        if arm.endswith("_held"):
            _held(plan)
        row["weight_start"] = ins.source.lines[1].weight.value
        ref = rx.Refinement(st, ins, history=False)
        if prepare:
            prepare(ref)
        if arm.endswith("_noise"):
            row["n_nudged"] = _nudged(ref)
        result = ref.fit(data, mode=mode, plan=plan, **kw)
        OUT.mkdir(parents=True, exist_ok=True)
        png = OUT / f"wp2017_groupJ_{family}_{arm}.png"
        result.plot(path=str(png))
        import matplotlib.pyplot as plt

        plt.close("all")
        row.update({
            "rows": {p.path: [p.value, p.stderr_uncorrected] for p in result.parameters},
            "esd_reported": {p.path: p.stderr for p in result.parameters},
            "rwp": result.statistics.rwp, "status": result.status,
            "n_eval": int(sum(s.n_iterations for s in result.stages)),
            "codes": sorted({d.code for d in result.diagnostics}),
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


def sweep(tasks: list[dict]) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    done = {(r["family"], r["arm"]) for r in read_rows() if "error" not in r}
    todo = [t for t in tasks if (t["family"], t["arm"]) not in done]
    if not todo:
        return
    with ProcessPoolExecutor(max_workers=max(1, min(WORKERS, len(todo))),
                             mp_context=get_context("spawn")) as pool:
        for future in as_completed([pool.submit(fit_one, t) for t in todo]):
            row = future.result()
            row["meta"] = _meta()
            with JSONL.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
            print(row["family"], row["arm"],
                  row.get("error") or f"{row['rwp']:.7f} {row['n_eval']} {row['status']}",
                  flush=True)


def _fmt(x, spec=".3g") -> str:
    return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, spec)


def _cmp(a: dict, b: dict, path: str):
    """(|a − b| over √(e_a² + e_b²), over the larger esd), reported esds."""
    va, vb = a["rows"][path][0], b["rows"][path][0]
    es = [e for e in (a["esd_reported"].get(path), b["esd_reported"].get(path))
          if e and math.isfinite(e)]
    if not es:
        return float("nan"), float("nan")
    return abs(va - vb) / math.sqrt(sum(e * e for e in es)), abs(va - vb) / max(es)


def _worst(cur: dict, ref: dict, prefix: str = "phases.0.cell."):
    """Largest |cur − ref| over the larger plain esd among rows under ``prefix``."""
    worst = (0.0, None)
    for path, (value, e1) in cur.items():
        if not path.startswith(prefix) or path not in ref:
            continue
        v0, e0 = ref[path]
        esds = [e for e in (e0, e1) if e is not None and math.isfinite(e) and e > 0.0]
        if esds:
            worst = max(worst, (abs(value - v0) / max(esds), path), key=lambda t: t[0])
    return worst


def summary() -> None:
    rows = {(r["family"], r["arm"]): r for r in read_rows()}
    meta = next((r["meta"] for r in rows.values() if "meta" in r), {})
    lines = [
        "# WP-2017 group J: Le Bail and Pawley refining the Kα2/Kα1 weight",
        "",
        "Written by `group_j.py summary` from the raw rows of the workstation run; families "
        "and arms in its docstring.",
        f"Commit `{meta.get('head', '?')[:9]}`, {meta.get('platform', '?')}, numpy "
        f"{meta.get('numpy', '?')}, rietx-kernels {meta.get('kernels', '?')}, compiled tier on, "
        "one kernel thread.",
        "",
        "Weight: the refined Kα2/Kα1 with its reported (plain) esd; `vs 0.5` in reported esds. "
        "`vs Rietveld`: combined σ = √(e₁² + e₂²) of the reported esds, then over the larger. "
        "`free−held`: largest cell shift, weight free against held in that mode, in plain esd "
        "over the larger (0.1 bar); `noise`: the free arm against its nudged twin, same measure.",
        "",
        "| Family | Mode | weight | vs 0.5 | vs Rietveld | free−held cell | noise | "
        "Rwp free / held | evals | codes |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for f in FAMILIES:
        rv = rows.get((f, "rietveld"))
        for m in MODES:
            fr, hd, nz = rows.get((f, m)), rows.get((f, f"{m}_held")), rows.get((f, f"{m}_noise"))
            if fr is None:
                continue
            if "error" in fr:
                lines.append(f"| `{f}` | {m} | {fr['error']} ||||||||")
                continue
            if WEIGHT not in fr["rows"]:
                lines.append(f"| `{f}` | {m} | weight not refined (control failed) ||||||||")
                continue
            w, e = fr["rows"][WEIGHT]
            er = fr["esd_reported"].get(WEIGHT)
            vs05 = abs(w - DEGENERACY) / er if er else float("nan")
            vr = "—"
            if m != "rietveld" and rv and "error" not in rv and WEIGHT in rv["rows"]:
                c, lg = _cmp(fr, rv, WEIGHT)
                vr = f"{_fmt(c, '.2f')}σ ({_fmt(lg, '.2f')})"
            fh = _worst(fr["rows"], hd["rows"]) if hd and "error" not in hd else (None, None)
            nn = _worst(nz["rows"], fr["rows"]) if nz and "error" not in nz else (None, None)
            rh = _fmt(hd["rwp"], ".5f") if hd and "error" not in hd else "—"
            codes = ", ".join(c for c in fr["codes"] if c in (
                "FLAT_DIRECTION", "HIGH_CORRELATION", "BOUND_HIT", "FLOOR_HIT",
                "PAWLEY_OVERLAP_UNRESOLVED")) or "—"
            lines.append(
                f"| `{f}` | {m} | {w:.4f} ± {_fmt(er, '.2g')} ({_fmt(e, '.2g')}) | "
                f"{_fmt(vs05, '.2f')} | {vr} | {_fmt(fh[0])} `{fh[1]}` | {_fmt(nn[0])} | "
                f"{fr['rwp']:.5f} / {rh} | {fr['n_eval']} | {codes} |")
    lines += ["", "Positive arm, SRM 660c against WP-2002 (2026-10-20):", "",
              "| Mode | WP-2002 | here |", "|---|---|---|"]
    for m in MODES:
        r = rows.get(("lab6", m))
        got = (f"{r['rows'][WEIGHT][0]:.4f} ± {_fmt(r['esd_reported'].get(WEIGHT), '.2g')}"
               if r and "error" not in r and WEIGHT in r["rows"] else "—")
        lines.append(f"| {m} | {WP2002[m][0]:.4f} ± {WP2002[m][1]} | {got} |")
    errors = [f"`{k[0]}` {k[1]}: {r['error']}" for k, r in rows.items() if "error" in r]
    if errors:
        lines += ["", "Refused fits:", ""] + [f"- {x}" for x in errors]
    lines += ["", "Figures: `tests/output/wp2017_groupJ_<family>_<arm>.png`.", ""]
    SUMMARY.write_text("\n".join(lines), encoding="utf-8")
    print(SUMMARY)


def _tasks(families=FAMILIES, arms=ARMS) -> list[dict]:
    return [{"family": f, "arm": a} for f in families for a in arms]


def main(argv: list[str]) -> None:
    mode = argv[1] if len(argv) > 1 else "all"
    if mode == "summary":
        summary()
        return
    if mode == "canary":
        sweep(_tasks(("srm1976a",), ("rietveld", "lebail")))
        return
    sweep(_tasks())


if __name__ == "__main__":
    main(sys.argv)
