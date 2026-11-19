"""WP-2017 group K (Q16a): ``MODEL_FAR_FROM_DATA``'s level on a thinned family and on collapses.

The constant is ``refine.MODEL_FAR_FROM_DATA_ALPHA`` (0.05): the error fires when the fit's
χ² is no better than a background-only fit's by Hamilton's (1965) R-factor ratio test at
that level (Yue's ruling of 2026-11-17).  This batch measures, per fit, the quantity that
test compares, Hamilton's p (``tests/reach_harness.py``: the fit is justified, and the code
silent, exactly when p < α), on the family the 2026-11-19 pre-registration fixed (WP-2017
handover, "part B …: registered before any run").  The tools are ``tests/reach_harness.py``:
``thin`` and the reach harness.

**Family.**  Four acceptance protocols, each on its own pattern:

- corundum: ``qarr/corundum.prn`` under ``test_acceptance_srm676a``'s protocol.  Chosen over
  SRM 1976a's X'Pert plate because its protocol is the one with an independent referent on
  this specimen (SRM 676a's certified cell), it is a single phase with no texture model to
  choose, and it is a different laboratory and instrument from FAP's and SRM 660c's;
- FAP: the GSAS-II LabData tutorial under ``test_acceptance_fap``'s GSAS protocol;
- SRM 660c: NIST's LaB₆ data under ``test_acceptance_srm660c``'s calibrated protocol;
- NAC: APS 11-BM NAC + CaF₂ under ``test_acceptance_nac``'s protocol, its Rietveld start the
  protocol's Le Bail pass on the unthinned pattern.

**Arms**, fixed here before anything ran:

``correct``    the protocol's own start, on the pattern as measured and thinned to 0.05, 0.1,
               0.2, 0.5 and 1 counts a channel, seeds 1, 2 and 3 (64 fits);
``scale0``     the same 64 data, every phase scale held at 0: a full collapse by construction;
``displaced``  the reach harness's starts: the main phase's cell lengths × (1 ± 1.5 %) and
               (1 ± 3 %) under the protocol plan, ``mccusker_default`` and, on the three
               laboratory patterns, ``lab_bragg_brentano``; and the zero shift + 0.2° under
               ``mccusker_default``.  On the pattern as measured and at 0.5 and 0.1 counts a
               channel, seeds 1-3 (13 starts × 7 data on a laboratory pattern, 9 × 7 on NAC).

**Classes.**  A displaced fit is ``reached``, ``error`` or ``silent``
(``reach_harness.classify``) against the ``correct`` fit on the same data, at 1e-3 relative on
``a``.  Its main phase's scale over that correct fit's names what it found: a **full
collapse** below 1e-3, a **partial capture** between 1e-3 and 0.5 when the cell was not
reached, otherwise **other**.  The collapse set the edges read is every ``scale0`` fit and
every displaced full collapse; the correct set is every ``correct`` fit.

**The edges.**  The largest p over the correct set and the smallest over the collapse set,
each with its case.  The row's regression test (``tests/test_far_from_data_family.py``)
picks its cases from these rows.

    .venv/bin/python docs/wp/2017-batch/group_k.py          # the batch, resumes
    .venv/bin/python docs/wp/2017-batch/group_k.py canary   # 4 cases
    .venv/bin/python docs/wp/2017-batch/group_k.py summary  # write group_k_summary.md

``WP2017K_RAW`` names the directory for the raw rows (default ``~/.cache/rietx/wp-2017-k``);
``WP2017K_WORKERS`` the pool (default 4).
"""

from __future__ import annotations

import dataclasses
import json
import os
import platform
import signal
import subprocess
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager
from multiprocessing import get_context
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("RIETX_TELEMETRY", "0")
os.environ.setdefault("MPLBACKEND", "Agg")

from rietx._about import COMPILED_THREADS_ENV  # noqa: E402

os.environ.setdefault(COMPILED_THREADS_ENV, "1")

import rietx as rx  # noqa: E402
from rietx.model import compiled  # noqa: E402
from rietx.refine import MODEL_FAR_FROM_DATA_ALPHA  # noqa: E402
from tests import reach_harness as h  # noqa: E402

HERE = Path(__file__).resolve().parent
RAW = Path(os.environ.get("WP2017K_RAW", Path.home() / ".cache" / "rietx" / "wp-2017-k"))
JSONL = RAW / "group_k.jsonl"
SUMMARY = HERE / "group_k_summary.md"
WORKERS = int(os.environ.get("WP2017K_WORKERS", "4"))
FIT_GUARD_S = 1200

LEVELS = (0.05, 0.1, 0.2, 0.5, 1.0)
SEEDS = (1, 2, 3)
DISPLACED_LEVELS = (0.5, 0.1)
ERRORS = (-0.03, -0.015, 0.015, 0.03)
LAB = ("corundum", "fap", "srm660c")
CELL_TOL = 1e-3
COLLAPSE_RATIO = 1e-3
PARTIAL_RATIO = 0.5
ZERO_OFFSET = 0.2


def data_variants(levels) -> list[tuple[float | None, int]]:
    return [(None, 0)] + [(m, s) for m in levels for s in SEEDS]


def displaced_starts(family: str) -> list[dict]:
    plans = ("protocol", "mccusker_default") + (("lab_bragg_brentano",) if family in LAB else ())
    out = [{"plan": p, "cell_error": e} for p in plans for e in ERRORS]
    out.append({"plan": "mccusker_default", "zero_offset": ZERO_OFFSET})
    return out


def tasks() -> list[dict]:
    out = []
    for fam in h.FAMILIES:
        for m, s in data_variants(LEVELS):
            out.append({"arm": "correct", "case": dataclasses.asdict(
                h.Case(fam, mean_counts=m, seed=s))})
            out.append({"arm": "scale0", "case": dataclasses.asdict(
                h.Case(fam, mean_counts=m, seed=s, scale_zero=True))})
        for m, s in data_variants(DISPLACED_LEVELS):
            for d in displaced_starts(fam):
                out.append({"arm": "displaced", "case": dataclasses.asdict(
                    h.Case(fam, mean_counts=m, seed=s, **d))})
    return out


def canary_tasks() -> list[dict]:
    keep = {("correct", "fap", 0.05, 1), ("scale0", "nac", 0.05, 1),
            ("displaced", "fap", None, 0), ("correct", "corundum", None, 0)}
    out = []
    for t in tasks():
        c = t["case"]
        key = (t["arm"], c["family"], c["mean_counts"], c["seed"])
        if key in keep and (t["arm"] != "displaced" or (c["plan"] == "mccusker_default"
                                                        and c["cell_error"] == -0.03)):
            out.append(t)
            keep.discard(key)
    return out


class FitTimeout(BaseException):
    """Past the runaway guard.  A ``BaseException``, so no handler in the package eats it."""


@contextmanager
def guarded(seconds: int):
    def alarm(signum, frame):
        raise FitTimeout

    was = signal.signal(signal.SIGALRM, alarm)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, was)


def fit_one(task: dict) -> dict:
    warnings.simplefilter("ignore")
    compiled.set_enabled(True)
    case = h.Case(**task["case"])
    row: dict = {"arm": task["arm"], "case": case.name, **task["case"]}
    try:
        with guarded(FIT_GUARD_S):
            row.update(h.run_case(case))
    except FitTimeout:
        row.update(status="timeout", error=f"FitTimeout: past {FIT_GUARD_S} s")
    except Exception as exc:  # noqa: BLE001  a refused fit is a result of the sweep
        row["error"] = f"{type(exc).__name__}: {str(exc).splitlines()[0][:300]}"
    return row


# -- running -----------------------------------------------------------------------------


def read_rows() -> list[dict]:
    if not JSONL.exists():
        return []
    with JSONL.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _meta() -> dict:
    import importlib.metadata as md

    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True,
                          text=True, check=False).stdout.strip() or "unknown"
    return {"head": head, "platform": f"{platform.system()} {platform.machine()}",
            "python": platform.python_version(), "rietx": rx.__version__,
            "rietx_file": rx.__file__, "numpy": md.version("numpy"),
            "scipy": md.version("scipy"), "kernels": md.version("rietx-kernels"),
            "workers": WORKERS, "alpha": MODEL_FAR_FROM_DATA_ALPHA}


def run(todo_all: list[dict]) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    done = {(r["arm"], r["case"]) for r in read_rows() if "error" not in r}
    todo = [t for t in todo_all if (t["arm"], h.Case(**t["case"]).name) not in done]
    print(f"{len(todo)} of {len(todo_all)} to run; {_meta()}", flush=True)
    if not todo:
        return
    # NAC's Le Bail seed once per worker; the longest starts (displaced, unthinned) first
    todo.sort(key=lambda t: (t["arm"] != "displaced", t["case"]["mean_counts"] is not None))
    with ProcessPoolExecutor(max_workers=min(WORKERS, len(todo)),
                             mp_context=get_context("spawn")) as pool:
        futures = [pool.submit(fit_one, t) for t in todo]
        for future in as_completed(futures):
            row = future.result()
            row["meta"] = _meta()
            with JSONL.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
            print(row["arm"], row["case"], row.get("status"), row.get("rwp"),
                  row.get("far_from_data", {}).get("p"), row.get("error", ""), flush=True)


# -- reading -----------------------------------------------------------------------------


def _key(row: dict) -> tuple:
    return (row["family"], row["mean_counts"], row["seed"])


def label(row: dict, ref: dict | None) -> str:
    """``scale0``, or for a displaced fit: reached / full collapse / partial capture / other."""
    if row["arm"] == "scale0":
        return "full collapse (held)"
    if row["arm"] == "correct" or ref is None:
        return row["arm"]
    ratio = row["scales"][0] / ref["scales"][0]
    if ratio < COLLAPSE_RATIO:
        return "full collapse"
    if h.classify(row, ref["a"], CELL_TOL) == "reached":
        return "reached"
    return "partial capture" if ratio < PARTIAL_RATIO else "other"


def _fmt(x, spec=".3g") -> str:
    return "—" if x is None else format(x, spec)


def _counts(m) -> str:
    return "as measured" if m is None else f"{m:g}"


def summary() -> None:
    rows = [r for r in read_rows() if "error" not in r]
    errors = [r for r in read_rows() if "error" in r]
    # one row per (arm, case): the last written
    by = {(r["arm"], r["case"]): r for r in rows}
    rows = list(by.values())
    ref = {_key(r): r for r in rows if r["arm"] == "correct"}
    meta = rows[0]["meta"] if rows else {}
    alpha = meta.get("alpha", MODEL_FAR_FROM_DATA_ALPHA)
    for r in rows:
        r["label"] = label(r, ref.get(_key(r)))
        r["class"] = (h.classify(r, ref[_key(r)]["a"], CELL_TOL)
                      if _key(r) in ref else None)
        r["p"] = h.p_value(r)
        r["ratio"] = (r["scales"][0] / ref[_key(r)]["scales"][0]
                      if _key(r) in ref and ref[_key(r)]["scales"][0] else None)
    correct = [r for r in rows if r["arm"] == "correct"]
    collapse = [r for r in rows if r["label"].startswith("full collapse")]
    lines = ["# WP-2017 group K, `MODEL_FAR_FROM_DATA`'s level on a thinned family", "",
             f"Rows: {len(rows)} fits ({len(errors)} raised or timed out), head "
             f"`{meta.get('head', '?')[:9]}`, {meta.get('platform', '?')}, Python "
             f"{meta.get('python', '?')}, numpy {meta.get('numpy', '?')}, scipy "
             f"{meta.get('scipy', '?')}, rietx-kernels {meta.get('kernels', '?')}; α = {alpha:g}. "
             "Written by `group_k.py summary`; the raw rows are not committed.", "",
             "p is Hamilton's upper-tail probability of the fit against the background-only fit, "
             "the quantity `MODEL_FAR_FROM_DATA` compares with α (it fires at p ≥ α; an "
             "undefined test reads 1).  Arms, classes and labels: the script's docstring, fixed "
             "before the run.", ""]

    def edge(rs, pick):
        return pick(rs, key=lambda r: r["p"]) if rs else None

    hi = edge(correct, max)
    lo = edge(collapse, min)
    lines += ["## The edges", "",
              f"- Largest p over the {len(correct)} correct fits: "
              f"{_fmt(hi and hi['p'], '.3e')} ({hi and hi['case']}, Rwp {_fmt(hi and hi['rwp'], '.4f')}, "
              f"F {_fmt(hi and hi['far_from_data'].get('F'))}).",
              f"- Smallest p over the {len(collapse)} full collapses: "
              f"{_fmt(lo and lo['p'], '.6g')} ({lo and lo['case']}, Rwp {_fmt(lo and lo['rwp'], '.4f')}, "
              f"F {_fmt(lo and lo['far_from_data'].get('F'))}).",
              f"- Correct fits flagged: {sum(h.flagged(r) for r in correct)}; full collapses "
              f"not flagged: {sum(not h.flagged(r) for r in collapse)}.",
              f"- Spy and code agree (flagged ⇔ p ≥ α) on "
              f"{sum(h.flagged(r) == (r['p'] >= alpha) for r in rows)} of {len(rows)} rows.", ""]
    near = sorted((r for r in correct), key=lambda r: -r["p"])[:5]
    lines += ["Five correct fits with the largest p: " + "; ".join(
        f"{r['case']} {r['p']:.3e}" for r in near) + ".", ""]
    near = sorted(collapse, key=lambda r: r["p"])[:5]
    lines += ["Five full collapses with the smallest p: " + "; ".join(
        f"{r['case']} {r['p']:.6g}" for r in near) + ".", ""]

    lines += ["## Correct starts and held collapses, by family and count", "",
              "| family | counts a channel | correct: fits | Rwp | flagged | largest p | "
              "smallest F | scale0: fits | Rwp | flagged | smallest p |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for fam in h.FAMILIES:
        for m in (None, *LEVELS):
            c = [r for r in correct if r["family"] == fam and r["mean_counts"] == m]
            z = [r for r in rows if r["arm"] == "scale0" and r["family"] == fam
                 and r["mean_counts"] == m]
            if not c and not z:
                continue

            def rng(rs, k):
                return (f"{min(r[k] for r in rs):.3f}-{max(r[k] for r in rs):.3f}"
                        if rs else "—")

            fs = [r["far_from_data"].get("F") for r in c if r["far_from_data"].get("F")]
            lines.append(
                f"| {fam} | {_counts(m)} | {len(c)} | {rng(c, 'rwp')} | "
                f"{sum(h.flagged(r) for r in c)} | "
                f"{_fmt(max((r['p'] for r in c), default=None), '.2e')} | "
                f"{_fmt(min(fs, default=None))} | {len(z)} | {rng(z, 'rwp')} | "
                f"{sum(h.flagged(r) for r in z)} | "
                f"{_fmt(min((r['p'] for r in z), default=None), '.6g')} |")
    lines.append("")

    disp = [r for r in rows if r["arm"] == "displaced"]
    lines += ["## Displaced starts (the reach harness)", "",
              "| family | counts | fits | reached | error | silent | full collapse | "
              "partial capture | other |", "|---|---|---|---|---|---|---|---|---|"]
    for fam in h.FAMILIES:
        for m in (None, *DISPLACED_LEVELS):
            d = [r for r in disp if r["family"] == fam and r["mean_counts"] == m]
            if not d:
                continue
            cls = [r["class"] for r in d]
            lab = [r["label"] for r in d]
            lines.append(f"| {fam} | {_counts(m)} | {len(d)} | {cls.count('reached')} | "
                         f"{cls.count('error')} | {cls.count('silent')} | "
                         f"{lab.count('full collapse')} | {lab.count('partial capture')} | "
                         f"{lab.count('other')} |")
    lines.append("")
    lines += ["Every displaced fit that did not reach its answer:", "",
              "| case | class | label | scale / correct | Rwp | usable | flagged | p | errors |",
              "|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(disp, key=lambda r: r["case"]):
        if r["label"] == "reached":
            continue
        lines.append(f"| {r['case']} | {r['class']} | {r['label']} | {_fmt(r['ratio'])} | "
                     f"{r['rwp']:.4f} | {r['usable']} | {h.flagged(r)} | {r['p']:.3g} | "
                     f"{', '.join(r['error_codes']) or '—'} |")
    lines.append("")
    if errors:
        lines += ["## Raised or timed out", ""]
        lines += [f"- {r['arm']} {r['case']}: {r['error']}" for r in errors]
        lines.append("")
    SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(SUMMARY)


def main(argv: list[str]) -> None:
    if argv[:1] == ["summary"]:
        summary()
    elif argv[:1] == ["canary"]:
        run(canary_tasks())
    else:
        run(tasks())


if __name__ == "__main__":
    main(sys.argv[1:])
