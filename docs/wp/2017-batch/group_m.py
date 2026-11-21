"""WP-2017 group M: the two starts, measured with and without the closing stage.

``structure.BISO_SEED`` (0.5 Å²) and ``instrument.HARMONIC_WEIGHT_SEED`` (0.01) are approved
at tier 3 as answer-invariant *behind the closing stage*; both rows owe the start measured
without it.  Starts and arms were fixed in WP-2017 § What each group inherits, "M, its starts
and arms", before anything ran (2026-11-16).

Every fit runs twice: ``closing`` (the protocol's ``closing_window_tol``, 1e-3) and ``none``
(``closing_window_tol=None``, the plan ending on its last declared stage).

- ``BISO_SEED``: ``fap``, ``nac``, ``cpd1a``, ``lab6`` as ``test_window_domain._protocol``
  builds them, every atom's Biso started at 0.5 (``b05``, the seed) or 1.5 (``b15``), and
  ``noise`` (0.5, every refinable non-zero start ×(1 + 1e-12)).
- ``HARMONIC_WEIGHT_SEED``: ``test_staged_start_invariance``'s synthetic CW neutron corundum,
  λ/2 at true weights 0, 0.003 and 0.05 (families ``harm0``, ``harm0.003``, ``harm0.05``),
  seeds 0.001, 0.01 (shipped) and 0.3, and ``noise`` on 0.01.

Positive arm: under ``closing`` the pairs must repeat the start test's readings.

    .venv/bin/python docs/wp/2017-batch/group_m.py          # every fit
    .venv/bin/python docs/wp/2017-batch/group_m.py canary   # fap b05/b15 under none
    .venv/bin/python docs/wp/2017-batch/group_m.py summary  # write group_m_summary.md

``WP2017M_RAW`` names the raw directory (default ``~/.cache/rietx/wp-2017-m``);
``WP2017M_WORKERS`` the pool (default 4).  Figures: ``tests/output/wp2017_groupM_*.png``.
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

RAW = Path(os.environ.get("WP2017M_RAW", Path.home() / ".cache" / "rietx" / "wp-2017-m"))
JSONL = RAW / "group_m.jsonl"
SUMMARY = HERE / "group_m_summary.md"
OUT = ROOT / "tests" / "output"
WORKERS = int(os.environ.get("WP2017M_WORKERS", "4"))

BISO_FAMILIES = ("fap", "nac", "cpd1a", "lab6")
BISO_ARMS = ("b05", "b15", "noise")
HARM_WEIGHTS = (0.0, 0.003, 0.05)
HARM_ARMS = ("s0.001", "s0.01", "s0.3", "noise")
CLOSINGS = ("closing", "none")
NUDGE = 1e-12
WEIGHT = "instrument.source.lines.1.weight"

#: the start test's readings under the closing stage (the harness's positive arm)
START_TEST = {"fap": "0.000", "nac": "0.000", "cpd1a": "15.68 (xfail)", "lab6": "<= 0.1",
              "harm": "<= 0.003"}

#: reference cells (family -> {phase index: {axis: value}}), beside the bar
CELL_REFS = {
    "fap": ({0: {"a": 9.371724, "c": 6.885867}}, "GSAS's converged FAP.EXP"),
    "nac": ({0: {"a": 10.2510}, 1: {"a": 5.4631}}, "the NAC suite's NAC and CaF2 cells"),
    "lab6": ({0: {"a": 4.156780}}, "the CIF block"),
}


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


def _biso_build(family: str, arm: str):
    from tests import test_window_domain as w

    data, st, ins, plan, kw = w._protocol(family)
    biso = 1.5 if arm == "b15" else 0.5
    for phase in st.phases:
        for atom in phase.atoms:
            atom.biso.value = biso
    harmonics = len(getattr(ins.source, "harmonics", None) or [])
    return data, st, ins, plan, kw, harmonics


def _harm_build(weight: float, arm: str):
    from rietx.schemas.instrument import BackgroundChebyshev
    from tests import test_staged_start_invariance as t
    from tests.test_acceptance_qpa_roundrobin import corundum_phase

    pattern, scale = t._synthetic(weight)
    seed = 0.01 if arm == "noise" else float(arm[1:])
    st = rx.Structure(phases=[corundum_phase()])
    st.phases[0].scale.value = scale * 0.8
    st.phases[0].cell.a.value *= 1.0005
    st.phases[0].cell.c.value *= 1.0005
    for atom in st.phases[0].atoms:
        atom.biso.value = 0.5
    ins = t._neutron(seed)
    ins.background = BackgroundChebyshev.with_terms(6)
    ins.background.coefficients[0].value = 500.0
    base = rx.RefinementPlan.mccusker_structural()
    plan = rx.RefinementPlan(stages=[
        *base.stages, rx.Stage("harmonic", ["instrument.source.lines.*.weight"])])
    return pattern, st, ins, plan, {"two_theta_limits": t._LIMITS}, 1, scale


def fit_one(task: dict) -> dict:
    family, closing, arm = task["family"], task["closing"], task["arm"]
    warnings.simplefilter("ignore")
    compiled.set_enabled(True)
    row: dict = {"family": family, "closing": closing, "arm": arm}
    try:
        if family.startswith("harm"):
            data, st, ins, plan, kw, harmonics, scale = _harm_build(float(family[4:]), arm)
            row["true_scale"] = scale
        else:
            data, st, ins, plan, kw, harmonics = _biso_build(family, arm)
        row["harmonics_declared"] = harmonics
        row["closing_declared"] = plan.closing_window_tol
        if closing == "none":
            plan.closing_window_tol = None
        ref = rx.Refinement(st, ins, history=False)
        if arm == "noise":
            row["n_nudged"] = _nudged(ref)
        result = ref.fit(data, plan=plan, **kw)
        OUT.mkdir(parents=True, exist_ok=True)
        png = OUT / f"wp2017_groupM_{family}_{closing}_{arm}.png"
        result.plot(path=str(png))
        import matplotlib.pyplot as plt

        plt.close("all")
        rows = {p.path: [p.value, p.stderr_uncorrected] for p in result.parameters}
        row.update({
            "rows": rows,
            "last_stage": result.stages[-1].name,
            "n_biso": sum(1 for p in rows if p.endswith(".biso")),
            "weight_refined": WEIGHT in rows,
            "rwp": result.statistics.rwp, "status": result.status,
            "n_eval": int(sum(s.n_iterations for s in result.stages)),
            "codes": sorted({d.code for d in result.diagnostics}),
            "png": str(png.relative_to(ROOT)),
        })
        if result.qpa is not None:
            row["fractions"] = {f.name: 100.0 * f.weight_fraction for f in result.qpa.phases}
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


def _tasks(families=BISO_FAMILIES, closings=CLOSINGS, arms=BISO_ARMS, harm=True) -> list[dict]:
    tasks = [{"family": f, "closing": c, "arm": a}
             for f in families for c in closings for a in arms]
    if harm:
        tasks += [{"family": f"harm{w:g}", "closing": c, "arm": a}
                  for w in HARM_WEIGHTS for c in closings for a in HARM_ARMS]
    # the slowest families first
    order = {"lab6": 0, "cpd1a": 1, "nac": 2, "fap": 3}
    return sorted(tasks, key=lambda t: order.get(t["family"], 4))


def sweep(tasks: list[dict]) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    done = {(r["family"], r["closing"], r["arm"]) for r in read_rows() if "error" not in r}
    todo = [t for t in tasks if (t["family"], t["closing"], t["arm"]) not in done]
    if not todo:
        return
    with ProcessPoolExecutor(max_workers=max(1, min(WORKERS, len(todo))),
                             mp_context=get_context("spawn")) as pool:
        for future in as_completed([pool.submit(fit_one, t) for t in todo]):
            row = future.result()
            row["meta"] = _meta()
            with JSONL.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
            print(row["family"], row["closing"], row["arm"],
                  row.get("error") or f"{row['rwp']:.7f} {row['n_eval']} {row['status']}",
                  flush=True)


def _fmt(x, spec=".3g") -> str:
    return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, spec)


SL = "instrument.geometry.axial_sl"
HL = "instrument.geometry.axial_hl"


def _ordered(rows: dict) -> dict:
    """S/L and H/L reported smaller first, as the start test orders them."""
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


def _same(a: dict, b: dict) -> bool:
    return a["rows"] == b["rows"] and a["rwp"] == b["rwp"] and a["n_eval"] == b["n_eval"]


def _refs(family: str, r: dict) -> str:
    if family == "cpd1a" and r.get("fractions"):
        from tests.test_acceptance_qpa_roundrobin import WEIGHED

        w = WEIGHED["cpd-1a"]
        return ", ".join(f"{k} {v - w.get(k, 0.0):+.2f}" for k, v in r["fractions"].items())
    if family.startswith("harm"):
        true = float(family[4:])
        if WEIGHT not in r["rows"]:
            return "weight held"
        v, e = r["rows"][WEIGHT]
        k = abs(v - true) / e if e else float("nan")
        return f"weight {v:.5f}±{_fmt(e, '.2g')} ({_fmt(k, '.2f')} esd from {true:g})"
    cells, _ = CELL_REFS.get(family, ({}, ""))
    out = []
    for ph, axes in cells.items():
        for ax, ref in axes.items():
            p = f"phases.{ph}.cell.{ax}"
            if p in r["rows"]:
                v, e = r["rows"][p]
                k = abs(v - ref) / e if e else float("nan")
                out.append(f"{ph}.{ax} {1e6 * (v - ref) / ref:+.0f} ppm ({_fmt(k, '.2f')})")
    return "; ".join(out) or "—"


def _weight_col(family: str, r: dict) -> str:
    """The λ/2 weight refined (synthetic only; on X-ray line 1 is Kα2, not a harmonic)."""
    if not family.startswith("harm"):
        return "—"
    return "yes" if r["weight_refined"] else "no"


def summary() -> None:
    rows = {(r["family"], r["closing"], r["arm"]): r for r in read_rows()}
    meta = next((r["meta"] for r in rows.values() if "meta" in r), {})
    families = [*BISO_FAMILIES, *(f"harm{w:g}" for w in HARM_WEIGHTS)]
    lines = [
        "# WP-2017 group M: the two starts with and without the closing stage",
        "",
        "Written by `group_m.py summary` from the raw rows of the workstation run; families and "
        "arms in its docstring.",
        f"Commit `{meta.get('head', '?')[:9]}`, {meta.get('platform', '?')}, numpy "
        f"{meta.get('numpy', '?')}, rietx-kernels {meta.get('kernels', '?')}, compiled tier on, "
        "one kernel thread.",
        "",
        "Every fit. `closing`: the protocol's closing stage (1e-3); `none`: "
        "`closing_window_tol=None`. Biso rows: refined Biso rows in the answer (0 = the start is "
        "the answer). Reference: cell distance in ppm (plain esd), cpd-1a's fractions minus the "
        "weighed (wt %), the synthetic's weight against its truth.",
        "",
        "| Family | Closing | Arm | last stage | Rwp | evals | status | Biso rows | λ/2 weight "
        "refined | harmonics declared | reference |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for f in families:
        arms = HARM_ARMS if f.startswith("harm") else BISO_ARMS
        for c in CLOSINGS:
            for a in arms:
                r = rows.get((f, c, a))
                if r is None:
                    continue
                if "error" in r:
                    lines.append(f"| `{f}` | {c} | {a} | {r['error']} ||||||||")
                    continue
                lines.append(
                    f"| `{f}` | {c} | {a} | {r['last_stage']} | {r['rwp']:.6f} | {r['n_eval']} | "
                    f"{r['status']} | {r['n_biso']} | {_weight_col(f, r)} | "
                    f"{r['harmonics_declared']} | {_refs(f, r)} |")
    lines += [
        "",
        "The start's reach, per closing setting: the other start (Biso 1.5; seeds 0.001 and 0.3) "
        "against the shipped one (Biso 0.5; seed 0.01), in plain esd over the larger esd on every "
        "row that is not a background coefficient, S/L and H/L ordered (0.1 bar); `noise` the "
        "nudged twin against shipped; `closing's move` the shipped start without the closing "
        "stage against with it; `start test` what `tests/test_staged_start_invariance.py` reads "
        "under the closing stage.",
        "",
        "| Family | Closing | other start(s) | noise | closing's move | codes that differ | "
        "start test |",
        "|---|---|---|---|---|---|---|",
    ]
    for f in families:
        harm = f.startswith("harm")
        base_arm, others = ("s0.01", ("s0.001", "s0.3")) if harm else ("b05", ("b15",))
        for c in CLOSINGS:
            base = rows.get((f, c, base_arm))
            if base is None or "error" in base:
                continue
            reads, codes = [], set()
            for o in others:
                r = rows.get((f, c, o))
                if r is None or "error" in r:
                    reads.append(f"{o}: —")
                    continue
                s = _shift(r["rows"], base["rows"])
                tag = " (bit-identical)" if _same(r, base) else ""
                reads.append(f"{o}: {_fmt(s[0])} `{s[1]}`{tag}")
                codes |= set(r["codes"]) ^ set(base["codes"])
            nz = rows.get((f, c, "noise"))
            nn = _shift(nz["rows"], base["rows"]) if nz and "error" not in nz else (None, None)
            move = ""
            if c == "none":
                cl = rows.get((f, "closing", base_arm))
                if cl and "error" not in cl:
                    m = _shift(base["rows"], cl["rows"])
                    move = f"{_fmt(m[0])} `{m[1]}`"
            st = START_TEST["harm" if harm else f] if c == "closing" else ""
            lines.append(f"| `{f}` | {c} | {'; '.join(reads)} | {_fmt(nn[0])} | {move or '—'} | "
                         f"{', '.join(sorted(codes)) or '—'} | {st or '—'} |")
    lines += ["", "Figures: `tests/output/wp2017_groupM_<family>_<closing>_<arm>.png`.", ""]
    SUMMARY.write_text("\n".join(lines), encoding="utf-8")
    print(SUMMARY)


def main(argv: list[str]) -> None:
    mode = argv[1] if len(argv) > 1 else "all"
    if mode == "summary":
        summary()
        return
    if mode == "canary":
        sweep(_tasks(("fap",), ("none",), ("b05", "b15"), harm=False))
        return
    sweep(_tasks())


if __name__ == "__main__":
    main(sys.argv)
