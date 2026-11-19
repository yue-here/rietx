"""WP-2017 group B, Q4: ``lm.BVLS_MAX_COLUMNS`` (128) on three Pawley fits, either side.

Registered in WP-2017's handover log ("2026-11-19 (part B ...: registered before any run)")
before anything here ran.  At or under the constant, the LM step is BVLS on the scaled
normal matrix; above it, projected conjugate gradients (``bccg.projected_cg``).  The same
constant decides whether the bound test reads the driver's exact active set
(``staged``) and whether ``least_squares`` hands the solver a sparse normal matrix, and all
three read ``lm.BVLS_MAX_COLUMNS`` at call time, so one patch moves every reader.

Families, group C's Pawley protocol (``fit(data, mode="pawley")`` under the default Pawley
plan, from ``tests.test_window_domain._protocol``'s data, structure and instrument; NAC
after its Le Bail pass with CaF2 appended): ``fap`` (lab Bragg-Brentano, GSAS protocol),
``nac`` (APS 11-BM) and ``cpd1a`` (the qarr laboratory), three laboratories, instruments and
materials, the first two above the cut at the shipped value and cpd-1a under it.

Arms: ``shipped``; ``flip``, the constant moved just across the fit's own largest solve
(read off the shipped arm), so that solve takes the other path: to its column count for a
fit above the cut (every solve BVLS), to one less for a fit under it (its largest solves
projected CG); ``noise``, shipped with every free start × (1 + 1e-12).  A spy on
``lm._solve_step`` records each solve's column count and path; ``flip`` measured something
only where its largest solve took the other path.  Read: every row against ``shipped`` in
plain esd over the larger esd (0.1 bar), past ``noise``; Rwp, evaluations, status; the
references group C reads (FAP's GSAS cell, NAC's and CaF2's cells).

    python docs/wp/2017-batch/group_b_q4.py            # shipped and noise, then flip; resumes
    python docs/wp/2017-batch/group_b_q4.py canary     # cpd1a shipped
    python docs/wp/2017-batch/group_b_q4.py summary    # write group_b_q4_summary.md
"""

from __future__ import annotations

import json
import os
import pickle
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager
from multiprocessing import get_context
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import group_c as c  # noqa: E402

import rietx as rx  # noqa: E402
from rietx.model import compiled  # noqa: E402
from rietx.optimize import lm  # noqa: E402
from tests import test_window_domain as w  # noqa: E402

RAW = Path(os.environ.get("WP2017C_RAW", c.RAW))
JSONL = RAW / "group_b_q4.jsonl"
SUMMARY = HERE / "group_b_q4_summary.md"
WORKERS = int(os.environ.get("WP2017C_WORKERS", "4"))
FAMILIES = ("fap", "nac", "cpd1a")
SHIPPED = 128
BAR = 0.1


@contextmanager
def patched(value: int):
    assert lm.BVLS_MAX_COLUMNS == SHIPPED
    try:
        lm.BVLS_MAX_COLUMNS = value
        yield
    finally:
        lm.BVLS_MAX_COLUMNS = SHIPPED


@contextmanager
def spied(solves: list):
    real = lm._solve_step

    def spy(A, b, *args, **kwargs):
        n = len(b)
        solves.append([n, "pcg" if n > lm.BVLS_MAX_COLUMNS else "bvls"])
        return real(A, b, *args, **kwargs)

    lm._solve_step = spy
    try:
        yield
    finally:
        lm._solve_step = real


def fit_one(task: dict) -> dict:
    family, arm, value = task["family"], task["arm"], task["value"]
    warnings.simplefilter("ignore")
    compiled.set_enabled(True)
    row: dict = {"family": family, "arm": arm, "value": value}
    try:
        data, st, ins, kw = pickle.loads(c._start_path(family).read_bytes())
        ref = rx.Refinement(st, ins, history=False)
        if arm == "noise":
            row["n_nudged"] = c._nudged(ref)
        solves: list = []
        with patched(value), spied(solves):
            result = ref.fit(data, mode="pawley", **kw)
        ns = [s[0] for s in solves]
        top = max(ns) if ns else None
        row.update({
            "n_solves": len(solves), "max_columns": top,
            "paths_at_max": sorted({s[1] for s in solves if s[0] == top}),
            "n_pcg": sum(1 for s in solves if s[1] == "pcg"),
            "n_bvls": sum(1 for s in solves if s[1] == "bvls"),
            "column_counts": sorted(set(ns)),
            "rows": {p: list(v) for p, v in w._rows(result).items()},
            "n_pawley": int(ref._model.pawley.n),
            "rwp": result.statistics.rwp, "status": result.status,
            "n_eval": int(sum(s.n_iterations for s in result.stages)),
            "codes": sorted({d.code for d in result.diagnostics}),
        })
    except Exception as exc:  # noqa: BLE001  a refused fit is a result of the sweep
        row["error"] = c.group_a._error_line(exc)
    return row


def read_rows() -> list[dict]:
    return c.read_rows(JSONL)


def _run(tasks: list[dict]) -> None:
    done = {(r["family"], r["arm"]) for r in read_rows() if "error" not in r}
    todo = [t for t in tasks if (t["family"], t["arm"]) not in done]
    if not todo:
        return
    with ProcessPoolExecutor(max_workers=min(WORKERS, len(todo)),
                             mp_context=get_context("spawn")) as pool:
        for fut in as_completed([pool.submit(fit_one, t) for t in todo]):
            row = fut.result()
            row["meta"] = c._meta()
            with JSONL.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
            print(row["family"], row["arm"], row.get("status"), row.get("max_columns"),
                  row.get("paths_at_max"), row.get("error", ""), flush=True)


def run(canary: bool = False) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    print("rietx", rx.__file__, flush=True)
    fams = ("cpd1a",) if canary else FAMILIES
    for f in fams:
        c.build_start(f)
    _run([{"family": f, "arm": a, "value": SHIPPED} for f in fams
          for a in (("shipped",) if canary else ("shipped", "noise"))])
    if canary:
        return
    shipped = {r["family"]: r for r in read_rows() if r["arm"] == "shipped" and "error" not in r}
    flips = []
    for f in fams:
        top = shipped[f]["max_columns"]
        flips.append({"family": f, "arm": "flip",
                      "value": top if top > SHIPPED else top - 1})
    _run(flips)


def _fmt(x, spec=".3g") -> str:
    return "—" if x is None else format(x, spec)


def summary() -> None:
    rows = {(r["family"], r["arm"]): r for r in read_rows()}
    meta = next(iter(rows.values()), {}).get("meta", {})
    out = ["# WP-2017 group B, Q4: `BVLS_MAX_COLUMNS` on three Pawley fits", "",
           f"Rows: {len(rows)} fits, head `{meta.get('head', '?')}`, {meta.get('platform', '?')}, "
           f"numpy {meta.get('numpy', '?')}, rietx-kernels {meta.get('kernels', '?')}.  Written by "
           "`group_b_q4.py summary`; the raw rows are not committed.", "",
           "Columns: the constant; the largest LM solve's column count and the path it took; "
           "solves by path; Rwp; evaluations; status; the largest shift of any row against "
           "`shipped` in plain esd over the larger esd, and of the background rows apart.", "",
           "| family | arm | constant | largest solve | its path | BVLS / PCG solves | Rwp "
           "| evals | status | shift vs shipped | bkg shift |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for f in FAMILIES:
        base = rows.get((f, "shipped"))
        for arm in ("shipped", "noise", "flip"):
            r = rows.get((f, arm))
            if r is None:
                continue
            if "error" in r:
                out.append(f"| {f} | {arm} | {r['value']} | error: {r['error']} | | | | | | | |")
                continue
            if base is not None and r is not base:
                sh, path = w._shift(r["rows"], base["rows"], background=False)
                bsh, _ = w._shift(r["rows"], base["rows"], background=True)
                st = f"{_fmt(sh)} {path}"
                bt = _fmt(bsh)
            else:
                st = bt = "—"
            out.append(f"| {f} | {arm} | {r['value']} | {r['max_columns']} | "
                       f"{', '.join(r['paths_at_max'])} | {r['n_bvls']} / {r['n_pcg']} | "
                       f"{r['rwp']:.6f} | {r['n_eval']} | {r['status']} | {st} | {bt} |")
    out += ["", "## References", ""]
    for f in FAMILIES:
        ref = c.references(f)
        for arm in ("shipped", "flip"):
            r = rows.get((f, arm))
            if not ref or r is None or "error" in r:
                continue
            parts = []
            for name, (where, val) in ref.items():
                kind, _, path = where.partition(":")
                if kind == "rows" and path in r["rows"]:
                    v, e = r["rows"][path]
                    parts.append(f"{name} {v:.6f}({'—' if e is None else f'{e:.6f}'}) vs {val}")
            out.append(f"- {f} {arm}: " + "; ".join(parts))
    out += ["", "## Codes", ""]
    for (f, arm), r in rows.items():
        if "error" not in r:
            out.append(f"- {f} {arm}: {', '.join(r['codes']) or 'none'}")
    SUMMARY.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(SUMMARY)


def main(argv: list[str]) -> None:
    if argv[:1] == ["summary"]:
        summary()
    elif argv[:1] == ["canary"]:
        run(canary=True)
    else:
        run()


if __name__ == "__main__":
    main(sys.argv[1:])
