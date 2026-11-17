"""WP-2017 group R: the width terms, `width_twins_held` and `ProfileTCHZ:y` unfloored.

Fits and arms were fixed in WP-2017, "R, its fits and arms", before anything ran (2026-11-17).
Three parts, one task kind each:

- ``r1`` ``width_twins_held`` on multi-phase fits freeing an instrument width with every seen
  phase's twin: ``lab6cbn`` (``PLAN_DEGENERATE``, the positive arm), ``cpd1a`` (``qpa_plan()``,
  its closing stage), ``nac`` and ``cucr_cold`` (a ``size_strain`` stage inserted after
  ``profile``).  Arms by replacing ``refine._hold_width_twins``: ``held`` (shipped), ``none``,
  ``specimen`` (the specimen twins held instead), ``noise`` (held, starts ×(1 + 1e-12)).
- ``r2`` ``instrument.profile.y`` min −180 (shipped) against 0 (``yfloor``), and ``noise``, on
  ``fap``, ``nac``, ``cpd1a``, ``lab6``; and ``lab6ss``: SRM 660c with a ``size_strain`` stage
  after ``profile`` under ``shipped`` and ``yfloor``.
- ``r3`` brucite (``iso``, ``aniso`` with its Stephens block) and corundum under
  ``test_acceptance_stephens._plan``, solver ``lm`` and ``trf``, closing ``none`` and ``1e-3``.

    .venv/bin/python docs/wp/2017-batch/group_r.py          # every task
    .venv/bin/python docs/wp/2017-batch/group_r.py canary   # r1 lab6cbn held, r2 lab6 yfloor
    .venv/bin/python docs/wp/2017-batch/group_r.py summary  # write group_r_summary.md

``WP2017R_RAW`` names the raw directory (default ``~/.cache/rietx/wp-2017-r``);
``WP2017R_WORKERS`` the pool (default 4).
"""

from __future__ import annotations

import copy
import importlib
import json
import os
import sys
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import get_context
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import group_p as gp  # noqa: E402  (sets sys.path, the env and the thread count)
import numpy as np  # noqa: E402

import rietx as rx  # noqa: E402
from rietx.model import compiled  # noqa: E402
from rietx.schemas.instrument import TCHZ_CEILING_DEG  # noqa: E402

refine_mod = importlib.import_module("rietx.refine")

RAW = Path(os.environ.get("WP2017R_RAW", Path.home() / ".cache" / "rietx" / "wp-2017-r"))
JSONL = RAW / "group_r.jsonl"
SUMMARY = HERE / "group_r_summary.md"
WORKERS = int(os.environ.get("WP2017R_WORKERS", "4"))

R1_FAMILIES = ("lab6cbn", "cpd1a", "nac", "cucr_cold")
R1_ARMS = ("held", "none", "specimen", "noise")
R2_FAMILIES = ("fap", "nac", "cpd1a", "lab6")
R2_ARMS = ("shipped", "yfloor", "noise")
R3_FITS = ("brucite_iso", "brucite_aniso", "corundum")
SOLVERS = ("lm", "trf")
CLOSINGS = ("none", "1e-3")
WIDTHS = ("u", "v", "w", "x", "y")
PHASE_WIDTHS = ("lor_size", "lor_strain", "gauss_size", "gauss_strain")
SIZE_STRAIN = rx.Stage("size_strain", ["phases.*.lor_size", "phases.*.lor_strain"], seed=1e-4)


def _with_size_strain(plan: rx.RefinementPlan) -> rx.RefinementPlan:
    plan = copy.deepcopy(plan)
    i = [s.name for s in plan.stages].index("profile")
    plan.stages.insert(i + 1, copy.deepcopy(SIZE_STRAIN))
    return plan


def _r1_build(family: str):
    if family == "lab6cbn":
        from tests import test_acceptance_lab6_cbn as t

        st, ins = t._inputs()
        return (rx.read_pattern(t.PATTERN), st, ins, copy.deepcopy(t.PLAN_DEGENERATE),
                {"two_theta_limits": t.LIMITS})
    if family == "cpd1a":
        return gp._protocol("cpd1a")
    if family == "nac":
        data, st, ins, plan, kw = gp._protocol("nac")
        return data, st, ins, _with_size_strain(plan), kw
    import group_g

    data, st, ins, plan = group_g.database_start("cucr_cold")
    return data, st, ins, _with_size_strain(plan), {}


def _hold_specimen(table, unseen):
    """The specimen columns the record pairs with are held, not the instrument column."""
    names = table.free_paths
    flats = refine_mod._width_twin_flats([(table, np.arange(len(names)), unseen)], len(names))
    if not flats:
        return [], {}, {}
    held = sorted({names[k] for ks in flats.values() for k in ks})
    reach = refine_mod._reach_beyond_self(table, held)
    table.set_vary(held, False)
    return held, reach, {names[c]: [names[k] for k in ks] for c, ks in flats.items()}


def _widths(ref: rx.Refinement, result) -> dict:
    """Every width, read off the fitted models (a held row leaves ``result.parameters``)."""
    esd = {p.path: p.stderr_uncorrected for p in result.parameters}
    at = {p.path for p in result.parameters if getattr(p, "at_bound", None)}
    ins, st = ref.fitted_instrument, ref.fitted_structure
    out = {}
    for n in WIDTHS:
        path = f"instrument.profile.{n}"
        par = getattr(ins.profile, n)
        out[path] = [par.value, esd.get(path), par.vary, path in at, par.min, par.max]
    for i, ph in enumerate(st.phases):
        for n in PHASE_WIDTHS:
            path = f"phases.{i}.{n}"
            par = getattr(ph, n)
            out[path] = [par.value, esd.get(path), par.vary, path in at, par.min, par.max]
    return out


def _gamma_l_min(widths: dict, data, n_phases: int) -> list:
    """min over the pattern of (X + lor_size)/cos θ + (Y + lor_strain) tan θ, per phase."""
    tt = np.asarray(data.two_theta, dtype=float)
    th = np.radians(tt / 2.0)
    x = widths["instrument.profile.x"][0]
    y = widths["instrument.profile.y"][0]
    out = []
    for i in range(n_phases):
        gl = ((x + widths[f"phases.{i}.lor_size"][0]) / np.cos(th)
              + (y + widths[f"phases.{i}.lor_strain"][0]) * np.tan(th))
        j = int(np.argmin(gl))
        out.append([float(gl[j]), float(tt[j])])
    return out


def _row(ref, result, data) -> dict:
    row = gp._result_row(result)
    row["twins"] = [[s.name, s.width_twins_held] for s in result.stages]
    row["held"] = [[s.name, list(s.held)] for s in result.stages]
    row["widths"] = _widths(ref, result)
    row["gamma_l_min"] = _gamma_l_min(row["widths"], data, len(ref.fitted_structure.phases))
    row["cells"] = {f"phases.{i}": [ph.cell.a.value, ph.cell.b.value, ph.cell.c.value]
                    for i, ph in enumerate(ref.fitted_structure.phases)}
    row["names"] = [ph.name for ph in ref.fitted_structure.phases]
    return row


def _r1(task: dict) -> dict:
    family, arm = task["family"], task["arm"]
    data, st, ins, plan, kw = _r1_build(family)
    hold = {"none": lambda table, unseen: ([], {}, {}),
            "specimen": _hold_specimen}.get(arm, refine_mod._hold_width_twins)
    with gp._set(refine_mod, _hold_width_twins=hold):
        ref = rx.Refinement(st, ins, history=False)
        n = gp._nudged(ref) if arm == "noise" else 0
        result = ref.fit(data, plan=plan, **kw)
    row = _row(ref, result, data)
    row["n_nudged"] = n
    return row


def _r2(task: dict) -> dict:
    family, arm = task["family"], task["arm"]
    fam = "lab6" if family == "lab6ss" else family
    data, st, ins, plan, kw = gp._protocol(fam)
    if family == "lab6ss":
        plan = _with_size_strain(plan)
    if arm == "yfloor":
        ins.profile.y.min = 0.0
    ref = rx.Refinement(st, ins, history=False)
    n = gp._nudged(ref) if arm == "noise" else 0
    result = ref.fit(data, plan=plan, **kw)
    row = _row(ref, result, data)
    row["n_nudged"] = n
    return row


def _r3(task: dict) -> dict:
    from tests import test_acceptance_stephens as t
    from tests.test_acceptance_qpa_roundrobin import (
        DATA,
        brucite_phase,
        corundum_phase,
        qarr_instrument,
        seed_scales,
    )

    fit, solver, closing = task["family"], task["solver"], task["closing"]
    name = "corundum" if fit == "corundum" else "brucite"
    if fit == "corundum":
        phase, plan = corundum_phase(), t._plan(texture=False, stephens=False)
    elif fit == "brucite_iso":
        phase, plan = brucite_phase(textured=True), t._plan(texture=True, stephens=False)
    else:
        phase = t._with_block(brucite_phase(textured=True))
        plan = t._plan(texture=True, stephens=True)
    plan.closing_window_tol = None if closing == "none" else float(closing)
    data = rx.read_pattern(DATA / f"{name}.prn")
    st = rx.Structure(phases=[phase])
    ins = qarr_instrument()
    seed_scales(st, ins, data)
    ref = rx.Refinement(st, ins, solver=solver, history=False)
    result = ref.fit(data, plan=plan)
    return _row(ref, result, data)


PARTS = {"r1": _r1, "r2": _r2, "r3": _r3}


def fit_one(task: dict) -> dict:
    warnings.simplefilter("ignore")
    compiled.set_enabled(True)
    row: dict = dict(task)
    t0 = time.time()
    try:
        row.update(PARTS[task["part"]](task))
    except Exception as exc:  # noqa: BLE001  a refused fit is a result of the sweep
        lines = str(exc).splitlines()
        row["error"] = f"{type(exc).__name__}: {lines[0] if lines else ''}"
    row["seconds"] = time.time() - t0
    return row


def _key(t: dict) -> tuple:
    return (t["part"], t["family"], t.get("arm", ""), t.get("solver", ""), t.get("closing", ""))


def _tasks() -> list[dict]:
    tasks = [{"part": "r1", "family": f, "arm": a} for f in R1_FAMILIES for a in R1_ARMS]
    tasks += [{"part": "r2", "family": f, "arm": a} for f in R2_FAMILIES for a in R2_ARMS]
    tasks += [{"part": "r2", "family": "lab6ss", "arm": a} for a in ("shipped", "yfloor")]
    tasks += [{"part": "r3", "family": f, "solver": s, "closing": c}
              for f in R3_FITS for s in SOLVERS for c in CLOSINGS]
    return tasks


def read_rows() -> list[dict]:
    return gp.read_rows(JSONL)


def sweep(tasks: list[dict]) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    done = {_key(r) for r in read_rows() if "error" not in r}
    todo = [t for t in tasks if _key(t) not in done]
    if not todo:
        return
    with ProcessPoolExecutor(max_workers=max(1, min(WORKERS, len(todo))),
                             mp_context=get_context("spawn")) as pool:
        for future in as_completed([pool.submit(fit_one, t) for t in todo]):
            row = future.result()
            row["meta"] = gp._meta() | {"workers": WORKERS}
            with JSONL.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
            print(*_key(row), row.get("error")
                  or f"{row.get('rwp', 0):.7f} {row.get('n_eval', '')} "
                     f"{row.get('status', '')} {row['seconds']:.0f}s", flush=True)


# -- summary ----------------------------------------------------------------

f = gp._fmt


def _pm(v, e) -> str:
    return f"{v:.5g}" if e is None else f"{v:.5g}({e:.2g})"


def _wd(row: dict, keys) -> str:
    w = row["widths"]
    out = []
    for k in keys:
        if k in w:
            v, e, vary, at, lo, hi = w[k]
            tag = " floor" if (lo is not None and abs(v - lo) <= 1e-9 and lo == 0.0) else ""
            tag += " ±180" if abs(abs(v) - TCHZ_CEILING_DEG) <= 1e-6 else ""
            out.append(f"{k.split('.', 1)[1]} {_pm(v, e)}{'' if vary else ' (fixed)'}{tag}")
    return "; ".join(out)


def _twin_stages(row: dict) -> str:
    named = [f"{n}: {sorted(t)}" for n, t in row["twins"] if t]
    return ", ".join(named) if named else "none recorded"


def _flat_codes(row: dict) -> str:
    c = [x for x in row["codes"] if x in ("HIGH_CORRELATION", "COVARIANCE_DIRECTION_DISCARDED",
                                           "RESOLUTION_NOT_POSITIVE", "BOUND_HIT", "FLOOR_HIT",
                                           "STEPHENS_STRAIN_NOT_POSITIVE")]
    return ", ".join(c) or "—"


def _frac(row: dict) -> str:
    fr = row.get("fractions") or {}
    return ", ".join(f"{k} {v:.3f}" for k, v in fr.items()) or "—"


def summary() -> None:
    rows = [r for r in read_rows() if "part" in r]
    by = {_key(r): r for r in rows}
    meta = next((r["meta"] for r in rows if "meta" in r), {})
    lines = ["# WP-2017 group R, read from group_r.jsonl", "",
             f"head {meta.get('head', '?')[:9]}, {meta.get('platform', '?')}, numpy "
             f"{meta.get('numpy', '?')}, rietx-kernels {meta.get('kernels', '?')}, "
             f"{meta.get('workers', '?')} workers, 1 kernel thread a worker, compiled tier on.", "",
             f"{len(rows)} rows, {sum('error' in r for r in rows)} errors.", ""]
    for r in rows:
        if "error" in r:
            lines.append(f"- error: {_key(r)}: {r['error']}")
    lines += ["", "Shift: the largest move of a row that is not background against the "
              "family's shipped arm, in plain esd over the larger esd (rows with an esd on both "
              "sides only; a held row has none), background beside.", ""]

    lines += ["## R1. `width_twins_held`", "",
              "| family | arm | Rwp | evals | status | shift esd | row | bkg esd | QPA wt % | "
              "twins recorded | flat/bound codes |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for fam in R1_FAMILIES:
        base = by.get(("r1", fam, "held", "", ""))
        for arm in R1_ARMS:
            r = by.get(("r1", fam, arm, "", ""))
            if r is None or "error" in r:
                continue
            s, p = gp._shift(r["rows"], base["rows"]) if base else (None, None)
            b, _ = gp._shift(r["rows"], base["rows"], background=True) if base else (None, None)
            lines.append(f"| {fam} | {arm} | {r['rwp']:.6f} | {r['n_eval']} | {r['status']} | "
                         f"{f(s)} | {p or '—'} | {f(b)} | {_frac(r)} | {_twin_stages(r)} | "
                         f"{_flat_codes(r)} |")
    lines += ["", "Widths at the answer (value(plain esd); fixed = not free at the end; floor = on "
              "a 0 lower bound; ±180 = on the ceiling):", ""]
    for fam in R1_FAMILIES:
        for arm in R1_ARMS:
            r = by.get(("r1", fam, arm, "", ""))
            if r is None or "error" in r:
                continue
            keys = [k for k in r["widths"] if k.endswith((".x", ".y", ".u", "lor_size",
                                                          "lor_strain"))]
            lines.append(f"- {fam} {arm} ({', '.join(r['names'])}): {_wd(r, keys)}; "
                         f"cells {r['cells']}")
    lines.append("")

    lines += ["## R2. `ProfileTCHZ:y` against Y ≥ 0", "",
              "| family | arm | Rwp | evals | Y | X | shift esd | row | bkg esd | cell a | "
              "lor_size, lor_strain | codes |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for fam in (*R2_FAMILIES, "lab6ss"):
        base = by.get(("r2", fam, "shipped", "", ""))
        for arm in R2_ARMS:
            r = by.get(("r2", fam, arm, "", ""))
            if r is None or "error" in r:
                continue
            s, p = gp._shift(r["rows"], base["rows"]) if base else (None, None)
            b, _ = gp._shift(r["rows"], base["rows"], background=True) if base else (None, None)
            w = r["widths"]
            ss = ", ".join(_pm(*w[f"phases.{i}.{n}"][:2]) for i in range(len(r["names"]))
                           for n in ("lor_size", "lor_strain"))
            lines.append(f"| {fam} | {arm} | {r['rwp']:.6f} | {r['n_eval']} | "
                         f"{_pm(*w['instrument.profile.y'][:2])} | "
                         f"{_pm(*w['instrument.profile.x'][:2])} | {f(s)} | {p or '—'} | {f(b)} | "
                         f"{r['cells']['phases.0'][0]:.6f} | {ss} | {_flat_codes(r)} |")
    lines.append("")

    lines += ["## R3. TRF and the ±180 bound", "",
              "| fit | solver | closing | Rwp | evals | status | min Γ_L (deg) at 2θ | widths | "
              "twins recorded | codes |", "|---|---|---|---|---|---|---|---|---|---|"]
    for fit in R3_FITS:
        for sv in SOLVERS:
            for c in CLOSINGS:
                r = by.get(("r3", fit, "", sv, c))
                if r is None or "error" in r:
                    continue
                g = r["gamma_l_min"][0]
                keys = ["instrument.profile.x", "instrument.profile.y", "instrument.profile.u",
                        "phases.0.lor_size", "phases.0.lor_strain"]
                lines.append(f"| {fit} | {sv} | {c} | {r['rwp']:.6f} | {r['n_eval']} | "
                             f"{r['status']} | {g[0]:.4g} at {g[1]:.1f} | {_wd(r, keys)} | "
                             f"{_twin_stages(r)} | {_flat_codes(r)} |")
    SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(SUMMARY)


def main(argv: list[str]) -> None:
    mode = argv[1] if len(argv) > 1 else "all"
    if mode == "summary":
        summary()
        return
    if mode == "canary":
        sweep([{"part": "r1", "family": "lab6cbn", "arm": "held"},
               {"part": "r2", "family": "lab6", "arm": "yfloor"}])
        return
    if mode in PARTS:
        sweep([t for t in _tasks() if t["part"] == mode])
        return
    sweep(_tasks())


if __name__ == "__main__":
    main(sys.argv)
