"""WP-2017 group L: the magnetic solve's three tier-3 counts.

Rows: ``strategy.magnetic.SOLVE_MINIMUM_RTOL`` (1e-4, two starts' Rwp apart by more than this
count as two minima), ``SOLVE_TOP_K`` (3, candidate k's carried down) and
``SOLVE_K_TRIALS`` (2, k's given a full trial).  Solves and arms were fixed in WP-2017 § What
each group inherits, "L, its solves and arms", before anything ran (2026-11-16).

Solves (``rx.solve_magnetic`` from the nuclear fit each acceptance suite builds; the compiled tier on, where
``test_magnetic_series``'s ramp fixture runs numpy, so its fit is built the same way, not
bit for bit):

- ``cr2wo6_4k``, ``cr2wo6_150k``: HFIR HB-2A, ``conftest.cr2wo6_nuclear``'s construction,
  ``sites=["Cr1"]``, ``ion="Cr3+"``.
- ``lamno3_50k``: NIST BT-1, ``conftest.lamno3_nuclear``'s construction, ``sites=["Mn2"]``,
  ``ion="Mn3+"``.
- ``ba2fesbse5_1p5k``: LLB G4.1, ``test_magnetic_series``'s nuclear fit at 1.5 K,
  ``sites=["Fe1"]``, ``ion="Fe3+"``.

Arms: ``shipped``; ``rtol_lo``/``rtol_hi`` (``SOLVE_MINIMUM_RTOL`` 1e-5 and 1e-3, patched on
the module); ``topk_2``/``topk_4``; ``ktrials_1``/``ktrials_3`` (the keywords whose defaults
the constants are); ``repeat`` (the shipped solve again: the floor).

    .venv/bin/python docs/wp/2017-batch/group_l.py          # every solve and arm, resumes
    .venv/bin/python docs/wp/2017-batch/group_l.py canary   # cr2wo6_4k shipped + topk_2
    .venv/bin/python docs/wp/2017-batch/group_l.py summary  # write group_l_summary.md

``WP2017L_RAW`` names the raw directory (default ``~/.cache/rietx/wp-2017-l``);
``WP2017L_WORKERS`` the pool (default 4).
"""

from __future__ import annotations

import importlib
import json
import math
import os
import platform
import subprocess
import sys
import time
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
from rietx.strategy import magnetic  # noqa: E402

RAW = Path(os.environ.get("WP2017L_RAW", Path.home() / ".cache" / "rietx" / "wp-2017-l"))
JSONL = RAW / "group_l.jsonl"
SUMMARY = HERE / "group_l_summary.md"
WORKERS = int(os.environ.get("WP2017L_WORKERS", "4"))

SOLVES = ("cr2wo6_4k", "cr2wo6_150k", "lamno3_50k", "ba2fesbse5_1p5k")
ARMS = ("shipped", "rtol_lo", "rtol_hi", "topk_2", "topk_4", "ktrials_1", "ktrials_3", "repeat")
RTOL = {"rtol_lo": 1e-5, "rtol_hi": 1e-3}
TOPK = {"topk_2": 2, "topk_4": 4}
KTRIALS = {"ktrials_1": 1, "ktrials_3": 3}


def _cr2wo6(temp: str):
    from tests.test_acceptance_magnetic import (
        DATA,
        NUCLEAR_STAGES,
        _fit,
        _instrument,
        _trirutile,
    )

    d150 = rx.read_pattern(DATA / "gsas2_hb2a_cr2wo6_150K.dat")
    ref150, _ = _fit(_trirutile(), _instrument(), d150, NUCLEAR_STAGES,
                     closing_window_tol=None)
    if temp == "150":
        return ref150, d150, {"sites": ["Cr1"], "ion": "Cr3+"}
    d4 = rx.read_pattern(DATA / "gsas2_hb2a_cr2wo6_4K.dat")
    ref4, _ = _fit(ref150.structure.model_copy(deep=True),
                   ref150.instrument.model_copy(deep=True), d4, NUCLEAR_STAGES,
                   closing_window_tol=None)
    return ref4, d4, {"sites": ["Cr1"], "ion": "Cr3+"}


def _lamno3():
    from rietx.crystallography.cif import structure_from_cif
    from tests.test_acceptance_magnetic_lamno3 import (
        CONTAMINANT,
        DATA,
        NUCLEAR_STAGES,
        _fit,
        _instrument,
    )

    data = rx.read_pattern(DATA / "gsas2_bt1_lamno3_50K.gsas")
    data = data.model_copy(update={"excluded_regions": [CONTAMINANT]})
    ref, _ = _fit(structure_from_cif(DATA / "gsas2_bt1_lamno3.cif"), _instrument(), data,
                  NUCLEAR_STAGES)
    return ref, data, {"sites": ["Mn2"], "ion": "Mn3+"}


def _ba2fesbse5():
    """``test_magnetic_series._ba2fesbse5_ramp_fits``'s nuclear fit at 1.5 K, built as there."""
    from tests.test_magnetic_series import BA_ATOMS, BA_LAMBDA, BA_LOW, _ba_pattern

    def par(v, **kw):
        return rx.Parameter(value=v, **kw)

    parent = rx.Phase(
        name="Ba2FeSbSe5", space_group="P n m a",
        cell=rx.Cell(a=par(12.650), b=par(9.140), c=par(9.170),
                     alpha=par(90.0), beta=par(90.0), gamma=par(90.0)),
        atoms=[rx.Atom(label=lab, species=sp, x=par(x), y=par(y), z=par(z),
                       occ=par(1.0), biso=par(u * 8.0 * np.pi ** 2, unit="A^2"))
               for lab, sp, x, y, z, u in BA_ATOMS])
    first = _ba_pattern(1.5)
    inst = rx.Instrument.constant_wavelength_neutron(BA_LAMBDA)
    inst.profile.w.value = 0.0025
    inst.profile.x.value = 0.0
    inst.background = rx.auto_background(
        first, two_theta_limits=(BA_LOW, float(first.two_theta[-1])),
        wavelength=BA_LAMBDA, seed=True).background
    bkg = ["phases.0.scale", "instrument.background.c*"]
    width = [f"instrument.profile.{k}" for k in "uvwx"]
    cell = ["instrument.zero_shift", "phases.0.cell.*"]
    stages = [("scale_bkg", bkg), ("zero", bkg + cell[:1]), ("cell", bkg + cell),
              ("widths", bkg + cell + width),
              ("coords", bkg + cell + width + ["phases.0.atoms.*.dof.*"]),
              ("biso", bkg + cell + width + ["phases.0.atoms.*.dof.*",
                                             "phases.0.atoms.*.biso"])]
    plan = rx.RefinementPlan(stages=[rx.Stage(n, list(p), max_iter=200) for n, p in stages],
                             intermediate_ftol=1e-6)
    ref = rx.Refinement(rx.Structure(phases=[parent]), inst, history=False)
    ref.fit(first, plan=plan)
    return ref, first, {"sites": ["Fe1"], "ion": "Fe3+"}


def build(solve: str):
    if solve == "cr2wo6_4k":
        return _cr2wo6("4")
    if solve == "cr2wo6_150k":
        return _cr2wo6("150")
    if solve == "lamno3_50k":
        return _lamno3()
    return _ba2fesbse5()


def _trial(t) -> dict:
    return {"class": t.class_index, "group": t.bns_number, "rep": t.representative,
            "status": t.status, "rwp": t.rwp, "delta_bic": t.delta_bic,
            "n_starts": t.n_starts, "n_minima": t.n_minima, "fit_status": t.fit_status}


def fit_one(task: dict) -> dict:
    solve, arm = task["solve"], task["arm"]
    warnings.simplefilter("ignore")
    compiled.set_enabled(True)
    row: dict = {"solve": solve, "arm": arm}
    rtol0 = magnetic.SOLVE_MINIMUM_RTOL
    try:
        ref, data, kw = build(solve)
        if arm in TOPK:
            kw["top_k"] = TOPK[arm]
        if arm in KTRIALS:
            kw["k_trials"] = KTRIALS[arm]
        magnetic.SOLVE_MINIMUM_RTOL = RTOL.get(arm, rtol0)
        t0 = time.perf_counter()
        sol = rx.solve_magnetic(ref, data, **kw)
        row["wall_s"] = time.perf_counter() - t0
        row.update({
            "verdict": sol.verdict, "space_group": sol.space_group,
            "k": list(sol.k) if sol.k else None, "k_route": sol.k_route,
            "k_candidates": [list(c) for c in sol.k_candidates],
            "k_trials": [{"k": list(kt.k), "matched": kt.matched,
                          "worst_offset_deg": kt.worst_offset_deg,
                          "best_delta_bic": kt.best_delta_bic, "n_refined": kt.n_refined}
                         for kt in sol.k_trials],
            "trials": [_trial(t) for t in sol.trials],
            "codes": sorted({d.code for d in sol.diagnostics}),
        })
    except Exception as exc:  # noqa: BLE001  a refused solve is a result of the sweep
        row["error"] = importlib.import_module("group_a")._error_line(exc)
    finally:
        magnetic.SOLVE_MINIMUM_RTOL = rtol0
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
    done = {(r["solve"], r["arm"]) for r in read_rows() if "error" not in r}
    todo = [t for t in tasks if (t["solve"], t["arm"]) not in done]
    if not todo:
        return
    # the long solve first, so it does not start last
    todo.sort(key=lambda t: t["solve"] != "ba2fesbse5_1p5k")
    with ProcessPoolExecutor(max_workers=max(1, min(WORKERS, len(todo))),
                             mp_context=get_context("spawn")) as pool:
        for future in as_completed([pool.submit(fit_one, t) for t in todo]):
            row = future.result()
            row["meta"] = _meta()
            with JSONL.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
            print(row["solve"], row["arm"],
                  row.get("error") or f"{row['verdict']} {row['space_group']} k={row['k']} "
                  f"{row['wall_s']:.0f} s", flush=True)


def _fmt(x, spec=".3g") -> str:
    return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, spec)


def _answer(r: dict) -> tuple:
    """What a reader takes from a solve: verdict, pick, k, and every trial's ranking."""
    return (r["verdict"], r["space_group"], tuple(r["k"] or ()), r["k_route"],
            tuple((t["class"], t["status"], t["delta_bic"], t["rwp"]) for t in r["trials"]),
            tuple((tuple(kt["k"]), kt["best_delta_bic"]) for kt in r["k_trials"]))


def _reached(arm: str, sh: dict) -> str:
    """Whether the arm's constant can act on this solve, read off the shipped solve."""
    if arm in TOPK:
        n = len(sh["k_candidates"])
        return f"{n} ranked k" if sh["k_route"] == "satellite ranking" else sh["k_route"]
    if arm in KTRIALS:
        return f"{len(sh['k_trials'])} k trial(s), {len(sh['k_candidates'])} ranked"
    if arm in RTOL:
        multi = [t for t in sh["trials"] if (t["n_starts"] or 0) >= 2]
        return f"{len(multi)} trial(s) with ≥ 2 starts"
    return ""


def summary() -> None:
    rows = {(r["solve"], r["arm"]): r for r in read_rows()}
    meta = next((r["meta"] for r in rows.values() if "meta" in r), {})
    lines = [
        "# WP-2017 group L: the magnetic solve's three counts",
        "",
        "Written by `group_l.py summary` from the raw rows of the workstation run; solves and "
        "arms in its docstring.",
        f"Commit `{meta.get('head', '?')[:9]}`, {meta.get('platform', '?')}, numpy "
        f"{meta.get('numpy', '?')}, rietx-kernels {meta.get('kernels', '?')}, compiled tier on, "
        "one kernel thread.",
        "",
        "`same answer`: verdict, pick, k, route, every trial's status, ΔBIC and Rwp, and the "
        "k-trial table all equal to `shipped`'s; `class trials same`: the class trials alone, "
        "every field.  `ranked k`: the list `top_k` cuts, with satellites matched.  `minima`: "
        "each trial's n_minima/n_starts.",
        "",
        "| Solve | Arm | verdict | pick | k (route) | ranked k (matched) | k trials | minima | "
        "same answer | class trials same | can act | wall s |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for s in SOLVES:
        sh = rows.get((s, "shipped"))
        for a in ARMS:
            r = rows.get((s, a))
            if r is None:
                continue
            if "error" in r:
                lines.append(f"| `{s}` | {a} | {r['error']} ||||||||||")
                continue
            same = "—" if a == "shipped" or sh is None or "error" in sh else (
                "yes" if _answer(r) == _answer(sh) else "**no**")
            minima = ", ".join(f"{t['n_minima']}/{t['n_starts']}" for t in r["trials"]
                               if t["n_starts"]) or "—"
            kt = "; ".join(f"({','.join(k['k'])}) ΔBIC {_fmt(k['best_delta_bic'], '.1f')}"
                           for k in r["k_trials"]) or "—"
            k = f"({','.join(r['k'])})" if r["k"] else "—"
            ranked = ", ".join(f"{c[0]} ({c[1]})" for c in r["k_candidates"]) or "—"
            tsame = "—" if a == "shipped" or sh is None or "error" in sh else (
                "yes" if r["trials"] == sh["trials"] else "**no**")
            can = _reached(a, sh) if sh and "error" not in sh else ""
            lines.append(f"| `{s}` | {a} | {r['verdict']} | {r['space_group'] or '—'} | "
                         f"{k} ({r['k_route']}) | {ranked} | {kt} | {minima} | {same} | "
                         f"{tsame} | {can} | "
                         f"{r['wall_s']:.0f} |")
    lines += ["", "Shipped trials (class, group, status, ΔBIC, Rwp):", ""]
    for s in SOLVES:
        sh = rows.get((s, "shipped"))
        if not sh or "error" in sh:
            continue
        lines.append(f"- `{s}`: " + "; ".join(
            f"{t['class']} {t['group']} {t['status']} {_fmt(t['delta_bic'], '.1f')} "
            f"{_fmt(t['rwp'], '.4f')}" for t in sh["trials"]))
    lines.append("")
    SUMMARY.write_text("\n".join(lines), encoding="utf-8")
    print(SUMMARY)


def _tasks(solves=SOLVES, arms=ARMS) -> list[dict]:
    return [{"solve": s, "arm": a} for s in solves for a in arms]


def main(argv: list[str]) -> None:
    mode = argv[1] if len(argv) > 1 else "all"
    if mode == "summary":
        summary()
        return
    if mode == "canary":
        sweep(_tasks(("cr2wo6_4k",), ("shipped", "topk_2")))
        return
    sweep(_tasks())


if __name__ == "__main__":
    main(sys.argv)
