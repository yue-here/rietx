"""WP-2017 group F: ``auto_background``'s pick near its two triggers.

Four rows: ``background.auto.HUMP_TRIGGER`` (0.05) picks the P-spline's knot step,
``_KNOT_STEP_HUMPY_DEG`` (3°) above it and ``_KNOT_STEP_SMOOTH_DEG`` (8°) below;
``AIR_SCATTER_TRIGGER`` (0.3) declares the 1/(2θ) air term above it.  Patterns and arms
were fixed in WP-2017 § What each group inherits, "F, its patterns and arms", before
anything ran (2026-11-16).

Each pattern's instrument background is ``auto_background(data)``'s pick.  Arms:
``pick`` (shipped triggers); ``knot_flip`` (``HUMP_TRIGGER`` moved just across the
pattern's own ``amorphous_hump_score``); ``air_flip`` (``AIR_SCATTER_TRIGGER`` just across
its ``air_scatter_gain``); ``both_flip``; ``noise`` (the pick, every free start value that
is not zero ×(1 + 1e-12)).  Control: the arm's ``BackgroundChoice`` must carry the
flipped knot step or air term.

Patterns:

- ``si640c``: 11-BM Si SRM 640c in its Kapton capillary, ``test_acceptance_si640c``'s
  XND-range protocol with the background replaced (the scale/background stage also frees
  ``air_scatter`` when the pick declares it).  References: XND's λ, and that suite's
  measured-blank arm, ``blank``: the run-4736 empty capillary held under a refined
  multiplier with a cubic, the hump as measured.
- ``cpd-1a`` … ``cpd-1h``: the QPA acceptance protocol.  Reference: the weighed fractions.

    .venv/bin/python docs/wp/2017-batch/group_f.py          # every pattern and arm, resumes
    .venv/bin/python docs/wp/2017-batch/group_f.py canary   # si640c and cpd-1a, pick
    .venv/bin/python docs/wp/2017-batch/group_f.py summary  # write group_f_summary.md

``WP2017F_RAW`` names the raw directory (default ``~/.cache/rietx/wp-2017-f``);
``WP2017F_WORKERS`` the pool (default 4).  Figures: ``tests/output/wp2017_groupF_*.png``.
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
from contextlib import contextmanager
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
from rietx.background import auto  # noqa: E402
from rietx.model import compiled  # noqa: E402
from tests import test_window_domain as w  # noqa: E402

RAW = Path(os.environ.get("WP2017F_RAW", Path.home() / ".cache" / "rietx" / "wp-2017-f"))
JSONL = RAW / "group_f.jsonl"
SUMMARY = HERE / "group_f_summary.md"
OUT = ROOT / "tests" / "output"
WORKERS = int(os.environ.get("WP2017F_WORKERS", "4"))

PATTERNS = ("si640c",) + tuple(f"cpd-1{c}" for c in "abcdefgh")
ARMS = ("pick", "knot_flip", "air_flip", "both_flip", "noise", "blank")
NUDGE = 1e-12
#: a trigger moved this far past the pattern's own score, relative
ACROSS = 1e-3


@contextmanager
def triggers(hump: float, air: float):
    h0, a0 = auto.HUMP_TRIGGER, auto.AIR_SCATTER_TRIGGER
    auto.HUMP_TRIGGER, auto.AIR_SCATTER_TRIGGER = hump, air
    try:
        yield
    finally:
        auto.HUMP_TRIGGER, auto.AIR_SCATTER_TRIGGER = h0, a0


def _across(score: float, trigger: float) -> float:
    """A trigger just on the other side of ``score`` from ``trigger``."""
    if score > trigger:
        return score * (1.0 + ACROSS) + 1e-12
    return score * (1.0 - ACROSS) - 1e-12


def build(pattern: str):
    """(data, structure, instrument, plan, fit kwargs, prepare, auto kwargs)."""
    if pattern == "si640c":
        from tests import test_acceptance_si640c as si

        data = rx.read_pattern(si.PATTERN)

        def prepare(ref):
            ref.tie_equal(["instrument.geometry.axial_sl", "instrument.geometry.axial_hl"])

        return (data, si._structure(), si._instrument(si.FULL_LIMITS), si._plan(asymmetric=True),
                {"two_theta_limits": si.FULL_LIMITS}, prepare,
                {"two_theta_limits": si.FULL_LIMITS})
    data, st, ins, plan = importlib.import_module("group_g")._cpd(pattern)
    return data, st, ins, plan, {}, None, {}


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
    pattern, arm = task["pattern"], task["arm"]
    warnings.simplefilter("ignore")
    compiled.set_enabled(True)
    row: dict = {"pattern": pattern, "arm": arm}
    try:
        if arm == "blank":
            from tests import test_acceptance_si640c as si

            result = si._fit_chebyshev(3, blank_scale=1.0, free_scale=True).result
            row["choice"] = None
        else:
            data, st, ins, plan, kw, prepare, akw = build(pattern)
            base = auto.auto_background(data, **akw)
            hump, air = auto.HUMP_TRIGGER, auto.AIR_SCATTER_TRIGGER
            if arm in ("knot_flip", "both_flip"):
                hump = _across(base.amorphous_hump_score, base.hump_trigger)
            if arm in ("air_flip", "both_flip"):
                air = _across(base.air_scatter_gain, base.air_scatter_trigger)
            with triggers(hump, air):
                choice = auto.auto_background(data, **akw)
            ins.background = choice.background
            if pattern == "si640c" and choice.air_scatter:
                plan.stages[0].turn_on = [*plan.stages[0].turn_on,
                                          "instrument.background.air_scatter"]
            row["choice"] = {"knot_step_deg": choice.knot_step_deg,
                             "air_scatter": choice.air_scatter,
                             "hump_score": choice.amorphous_hump_score,
                             "air_gain": choice.air_scatter_gain,
                             "hump_trigger": hump, "air_trigger": air,
                             "pick_knot": base.knot_step_deg, "pick_air": base.air_scatter}
            ref = rx.Refinement(st, ins, history=False)
            if prepare:
                prepare(ref)
            if arm == "noise":
                row["n_nudged"] = _nudged(ref)
            result = ref.fit(data, plan=plan, **kw)
        OUT.mkdir(parents=True, exist_ok=True)
        png = OUT / f"wp2017_groupF_{pattern}_{arm}.png"
        result.plot(path=str(png))
        import matplotlib.pyplot as plt

        plt.close("all")
        row.update({
            "rows": {p.path: [p.value, p.stderr_uncorrected] for p in result.parameters},
            "rwp": result.statistics.rwp, "status": result.status,
            "n_eval": int(sum(s.n_iterations for s in result.stages)),
            "codes": sorted({d.code for d in result.diagnostics}),
            "png": str(png.relative_to(ROOT)),
        })
        try:
            row["fractions"] = {f.name: 100.0 * f.weight_fraction for f in result.qpa.phases}
        except Exception:  # noqa: BLE001
            row["fractions"] = None
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


def _tasks(patterns=PATTERNS, arms=ARMS) -> list[dict]:
    return [{"pattern": p, "arm": a} for p in patterns for a in arms
            if a != "blank" or p == "si640c"]


def sweep(tasks: list[dict]) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    done = {(r["pattern"], r["arm"]) for r in read_rows() if "error" not in r}
    todo = [t for t in tasks if (t["pattern"], t["arm"]) not in done]
    if not todo:
        return
    with ProcessPoolExecutor(max_workers=max(1, min(WORKERS, len(todo))),
                             mp_context=get_context("spawn")) as pool:
        for future in as_completed([pool.submit(fit_one, t) for t in todo]):
            row = future.result()
            row["meta"] = _meta()
            with JSONL.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
            print(row["pattern"], row["arm"],
                  row.get("error") or f"{row['rwp']:.7f} {row['n_eval']} {row['choice']}",
                  flush=True)


def _fmt(x, spec=".3g") -> str:
    return "—" if x is None or (isinstance(x, float) and not math.isfinite(x)) else format(x, spec)


def summary() -> None:
    from tests.test_acceptance_qpa_roundrobin import WEIGHED
    from tests.test_acceptance_si640c import XND

    rows = read_rows()
    latest = {(r["pattern"], r["arm"]): r for r in rows}
    meta = dict(next((r["meta"] for r in reversed(rows) if "meta" in r), {}))
    lines = ["# WP-2017 group F: auto_background's pick near its triggers", "",
             f"Run at `{meta.get('head', '?')[:9]}`, {meta.get('platform', '?')}, Python "
             f"{meta.get('python', '?')}, numpy {meta.get('numpy', '?')}, rietx-kernels "
             f"{meta.get('kernels', '?')}, {meta.get('workers', '?')} workers, compiled tier on, "
             "one kernel thread.  Written by `group_f.py summary`; patterns and arms in its "
             "docstring.", "",
             f"Shipped triggers: `HUMP_TRIGGER` {auto.HUMP_TRIGGER:g}, `AIR_SCATTER_TRIGGER` "
             f"{auto.AIR_SCATTER_TRIGGER:g}.", "",
             "| Pattern | Arm | hump score | air gain | knot step | air term | Rwp | evaluations "
             "| status | model shift vs pick (row) | background | reference | air code |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    errors = []
    for pat in PATTERNS:
        p = latest.get((pat, "pick"))
        for arm in ARMS:
            r = latest.get((pat, arm))
            if r is None:
                continue
            if "error" in r:
                errors.append(r)
                lines.append(f"| {pat} | {arm} | {r['error']} |" + " |" * 11)
                continue
            c = r.get("choice") or {}
            if p and "error" not in p and arm != "pick":
                m = w._shift(r["rows"], p["rows"], background=False)
                b = w._shift(r["rows"], p["rows"], background=True)
                shift, bshift = f"{_fmt(m[0])} (`{m[1]}`)", _fmt(b[0])
            else:
                shift = bshift = "—"
            if pat == "si640c":
                lam = r["rows"].get("instrument.source.lines.0.wavelength")
                ref = f"λ {1e6 * (lam[0] / XND['lam'] - 1):+.2f} ppm from XND" if lam else "—"
            elif r.get("fractions"):
                ref = ", ".join(f"{k} {v - WEIGHED[pat].get(k, 0.0):+.2f}"
                                for k, v in r["fractions"].items()) + " wt %"
            else:
                ref = "—"
            flipped = ""
            if c and arm in ("knot_flip", "both_flip") and c["knot_step_deg"] == c["pick_knot"]:
                flipped = " (knot NOT flipped)"
            if c and arm in ("air_flip", "both_flip") and c["air_scatter"] == c["pick_air"]:
                flipped += " (air NOT flipped)"
            lines.append(
                f"| {pat} | {arm}{flipped} | {_fmt(c.get('hump_score'))} | "
                f"{_fmt(c.get('air_gain'))} | {_fmt(c.get('knot_step_deg'))} | "
                f"{c.get('air_scatter', '—')} | {r['rwp']:.7f} | {r['n_eval']} | {r['status']} | "
                f"{shift} | {bshift} | {ref} | "
                f"{'yes' if 'AIR_SCATTER_UNDECLARED' in r['codes'] else 'no'} |")
    blank, pick = latest.get(("si640c", "blank")), latest.get(("si640c", "pick"))
    if blank and pick and "error" not in blank and "error" not in pick:
        lines += ["", "Si SRM 640c, each arm against the measured-blank arm on λ, zero and "
                  "Biso (plain esd over the larger esd):", ""]
        keys = ("instrument.source.lines.0.wavelength", "instrument.zero_shift",
                "phases.0.atoms.0.biso")
        for arm in ARMS[:-1]:
            r = latest.get(("si640c", arm))
            if not r or "error" in r:
                continue
            parts = []
            for k in keys:
                if k in r["rows"] and k in blank["rows"]:
                    sub = {k: r["rows"][k]}
                    parts.append(f"{k.split('.')[-1]} "
                                 f"{_fmt(w._shift(sub, {k: blank['rows'][k]}, background=False)[0])}")
            lines.append(f"- {arm}: " + ", ".join(parts))
    if errors:
        lines += ["", "## Errors", ""] + [f"- {r['pattern']} {r['arm']}: {r['error']}"
                                           for r in errors]
    lines.append("")
    SUMMARY.write_text("\n".join(lines), encoding="utf-8")
    print(SUMMARY)


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "summary":
        summary()
    elif arg == "canary":
        sweep(_tasks(("si640c", "cpd-1a"), ("pick",)))
    else:
        sweep(_tasks())
