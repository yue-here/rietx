"""WP-2017 group G, part B (PR #1577): B1.1 at 2 and 3 widths, a third family, a phase under 1 wt %.

Registered in WP-2017's handover log ("2026-11-19 (part B ...: registered before any run)")
before anything here ran.  The hold under trial is ``PHASE_SUPPORT_SIGMA`` (3) and its two
defaults.  ``group_g.py`` (2026-11-16) found it unreached on real trace phases started one
FWHM off; the maintainer's walk (Q1, Q2) owed the same at 2 and 3 widths, a phase under
1 wt %, and a third family named from disk before running.

Families and starts (each a whole fit through the closing stage):

- the five bases of ``group_g.OFF_STARTS`` (cpd-1a corundum, cpd-1b zincite, cpd-1c
  fluorite, the CuCr2O4 ramp's coldest and hottest frames with CuO), from the database
  cell at ``s3`` (to read the one-FWHM step off this tree's answer) and from ``n`` = 2 and 3
  FWHM off: the minor phase's cell lengths × (1 + n·Δd/d), Δd/d as ``group_g.off_factor``;
- ``nac``: 11-BM NAC with its CaF2 impurity, ``tests.test_window_domain._protocol("nac")``
  (the Le Bail seed, then ``mccusker_default`` with a Biso stage), CaF2 from 5.4631 Å and
  1, 2 and 3 FWHM off.  The third family: another laboratory and material, the
  instrument shared with the CuCr2O4 ramp;
- two published APS 11-BM patterns outside the tree, with their authors' refinements
  (``group_g_b11_offtree.py``, which cites them): Cr2WO6 with Cr2O3 under 1 wt %
  (``cr2wo6``), and GeCo2O4 at 6.6 K with Co10Ge3O16 (``geco``).  The registration's
  under-1 % case was GeCo2O4, from a catalogue row reading 0.30 wt %; its authors' files read
  1.37, so it ran as a fourth near-1 % case and Cr2WO6 carries the under-1 % one.

Arms: ``s3`` (shipped), ``s1``, ``off`` (None) and ``noise`` (3, every free start nudged by
1e-12 relative).  Each fit records ``group_g.fit_record``'s row, plus every call of
``refine._answer_significance``: the minor phase's significance in σ and the threshold it
was compared with, in call order, which is the number the hold decides on.

    python docs/wp/2017-batch/group_g_b11.py canary    # the new bases at s3
    python docs/wp/2017-batch/group_g_b11.py           # all, database starts first, resumes
    python docs/wp/2017-batch/group_g_b11.py summary   # write group_g_b11_summary.md

``WP2017G_RAW`` names the raw directory (shared with ``group_g.py``'s off-start files),
``WP2017G_EXT`` the directory holding the off-tree files (their two bases load only when
all three are there), ``WP2017G_WORKERS`` the pool; ``summary`` writes only the bases loaded.
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import warnings
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import group_g as g  # noqa: E402
import numpy as np  # noqa: E402

import rietx as rx  # noqa: E402
from rietx.model import compiled  # noqa: E402

RAW = g.RAW
JSONL = RAW / "group_g_b11.jsonl"
SUMMARY = HERE / "group_g_b11_summary.md"
EXT = Path(os.environ.get("WP2017G_EXT", Path.home() / ".cache" / "rietx" / "wp-2017-g-ext"))
ARMS = ("s3", "s1", "off", "noise")
SIGMA = {"s3": 3.0, "s1": 1.0, "off": None, "noise": 3.0}
OLD_BASES = g.OFF_STARTS
NEW_BASES: tuple[str, ...] = ("nac",)
MINOR = {**{b: g.STARTS[b][1] for b in OLD_BASES}, "nac": "CaF2"}
#: references: weight % of the minor phase and its source
REF_WT = {"cpd1a": 1.15, "cpd1b": 1.36, "cpd1c": 1.36, "cucr_cold": 1.1, "cucr_hot": 1.1,
          "nac": None}
REF_CELL = {"nac": [5.4631] * 3}

import group_g_b11_offtree as _offtree  # noqa: E402

_OFFTREE = _offtree if _offtree.available(EXT) else None
if _OFFTREE is not None:
    NEW_BASES = NEW_BASES + tuple(_OFFTREE.BASES)
    MINOR.update(_OFFTREE.MINOR)
    REF_WT.update(_OFFTREE.REF_WT)


def database_start(base: str) -> tuple:
    """(data, structure, instrument, plan, fit kwargs) from the minor phase's start cell."""
    if base in OLD_BASES:
        data, st, ins, plan = g.database_start(base)
        return data, st, ins, plan, {}
    if base == "nac":
        from tests.test_window_domain import _protocol
        data, st, ins, plan, kw = _protocol("nac")
        return data, st, ins, plan, kw
    if _OFFTREE is not None and base in _OFFTREE.BASES:
        return _OFFTREE.database_start(base, g, EXT)
    raise KeyError(base)


def split(name: str) -> tuple[str, int]:
    """``cpd1a_off2`` -> ("cpd1a", 2); ``nac`` -> ("nac", 0)."""
    if "_off" in name:
        base, n = name.rsplit("_off", 1)
        return base, int(n)
    return name, 0


def _significance_spy(calls: list):
    rf = importlib.import_module("rietx.refine")
    real = rf._answer_significance

    def spy(*args, **kwargs):
        out = real(*args, **kwargs)
        calls.append({"sigma": kwargs.get("sigma", rf.PHASE_SUPPORT_SIGMA),
                      "sig": [float(v) for v in np.asarray(out)]})
        return out
    return rf, real, spy


def fit_one(task: dict) -> dict:
    name, arm = task["start"], task["arm"]
    base, n = split(name)
    minor = MINOR[base]
    warnings.simplefilter("ignore")
    compiled.set_enabled(True)
    row: dict = {"start": name, "base": base, "n_fwhm": n, "arm": arm, "minor_name": minor}
    calls: list = []
    rf, real, spy = _significance_spy(calls)
    try:
        data, st, ins, plan, kw = database_start(base)
        if n:
            one = json.loads((RAW / f"off_{base}.json").read_text(encoding="utf-8"))
            factor = 1.0 + n * (one["factor"] - 1.0)
            g.displace(st, minor, factor)
            row["off"] = {**one, "n": n, "factor_n": factor}
        st0 = st.model_copy(deep=True)
        ref = rx.Refinement(st, ins, history=False)
        plan = g.dataclasses.replace(plan, phase_support_sigma=SIGMA[arm])
        if arm == "noise":
            row["nudge"] = g._nudged(ref, plan)
        rf._answer_significance = spy
        try:
            with g.guarded(g.FIT_GUARD_S):
                result = ref.fit(data, plan=plan, **kw)
        finally:
            rf._answer_significance = real
        row.update(g.fit_record(result, ref.fitted_structure, st0, minor))
        ip = row["minor"]["index"]
        row["significance"] = [{"sigma": c["sigma"], "minor": c["sig"][ip]
                                if ip < len(c["sig"]) else None} for c in calls]
        if arm == "s3" and n == 0:
            (RAW / f"off_{base}.json").write_text(
                json.dumps(g.off_factor(ref, minor)), encoding="utf-8")
    except g.FitTimeout:
        row.update(status="timeout", error=f"FitTimeout: past {g.FIT_GUARD_S} s")
    except Exception as exc:  # noqa: BLE001  a refused fit is a result of the sweep
        row["error"] = g._error_line(exc)
    return row


def tasks() -> tuple[list[dict], list[dict]]:
    first = [{"start": b, "arm": "s3"} for b in OLD_BASES]
    first += [{"start": b, "arm": a} for b in NEW_BASES for a in ARMS]
    second = [{"start": f"{b}_off{n}", "arm": a}
              for b in OLD_BASES for n in (2, 3) for a in ARMS]
    second += [{"start": f"{b}_off{n}", "arm": a}
               for b in NEW_BASES for n in (1, 2, 3) for a in ARMS]
    return first, second


def run(canary: bool = False) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    print("rietx", rx.__file__, g._head(), flush=True)
    if canary:
        g._run([{"start": b, "arm": "s3"} for b in NEW_BASES], fit_one, JSONL)
        return
    first, second = tasks()
    g._run(first, fit_one, JSONL)
    g._run(second, fit_one, JSONL)


# -- reading -----------------------------------------------------------------------------


def _min_sig(row: dict) -> tuple[float | None, float | None]:
    """The lowest significance the hold compared (σ-threshold calls only), and the last."""
    vals = [c["minor"] for c in row.get("significance", []) if c["minor"] is not None]
    return (min(vals) if vals else None), (vals[-1] if vals else None)


def _cell_left(row: dict, db: dict | None) -> float | None:
    """The share of the off start's cell offset left against the database start's s3
    answer, mean over the lengths: 0 recovered, 1 never moved."""
    if db is None or not row.get("off") or row["minor"]["cell"] is None:
        return None
    ans, start = db["minor"]["cell"], row["minor"]["cell_start"]
    if ans is None:
        return None
    left = [(c - a) / (s - a) for c, a, s in zip(row["minor"]["cell"], ans, start)
            if abs(s - a) > 0]
    return float(np.mean(left)) if left else None


def summary() -> None:
    rows = [r for r in g.read_rows(JSONL) if r["base"] in MINOR]
    key = {(r["start"], r["arm"]): r for r in rows}
    out = ["# WP-2017 group G part B: B1.1 at 2 and 3 widths, NAC, a phase under 1 wt %", ""]
    meta = rows[0].get("meta", {}) if rows else {}
    out.append(f"Rows: {len(rows)} fits, head `{meta.get('head', '?')}`, {meta.get('platform', '?')}. "
               "Written by `group_g_b11.py summary`; the raw rows are not committed.")
    out += ["", "Columns: the minor phase's lowest significance the hold compared (σ, "
            "`refine._answer_significance`) and its value at the answer; the stages that held it; "
            "its weight % (esd) against the reference; the share of the off start's cell offset left "
            "against the database start's `s3` answer (0 recovered); Rwp; evaluations; the largest "
            "shift of any other row against the same start's `s3`, in plain esd (background apart); "
            "and whether `PHASE_UNCONSTRAINED` fired.", "",
            "| start | n FWHM | arm | minor | σ min / at answer | held in | wt % (ref) | cell left | Rwp "
            "| evals | shift vs s3 | bkg shift | PHASE_UNCONSTRAINED |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    order = [b for b in OLD_BASES] + list(NEW_BASES)
    for base in order:
        for n in (0, 1, 2, 3):
            name = base if n == 0 else f"{base}_off{n}"
            db = key.get((base, "s3"))
            s3 = key.get((name, "s3"))
            for arm in ARMS:
                r = key.get((name, arm))
                if r is None:
                    continue
                if "error" in r:
                    out.append(f"| {base} | {n} | {arm} | {MINOR[base]} | error: {r['error']} "
                               "| | | | | | | | |")
                    continue
                lo, last = _min_sig(r)
                wt, wte = g._wt(r, MINOR[base])
                ref = REF_WT[base]
                held = ", ".join(s["name"] for s in r["stages"]
                                 if r["minor"]["index"] in s["held_phases"]) or "none"
                left = _cell_left(r, db)
                if s3 is not None and r is not s3 and "error" not in s3:
                    sh, path, bsh, _ = g.shift(r, s3)
                    shift_text = f"{g._fmt(sh)} {path}"
                    bkg_text = g._fmt(bsh)
                else:
                    shift_text = bkg_text = "—"
                out.append(
                    f"| {base} | {n} | {arm} | {MINOR[base]} | {g._fmt(lo, '.1f')} / "
                    f"{g._fmt(last, '.1f')} | {held} | "
                    f"{'—' if wt is None else f'{wt:.2f}({wte:.2f})'} "
                    f"({'—' if ref is None else ref}) | "
                    f"{'—' if left is None else f'{left:.3f}'} | {r['rwp']:.4f} | {r['n_eval']} | "
                    f"{shift_text} | {bkg_text} | "
                    f"{'yes' if 'PHASE_UNCONSTRAINED' in r['codes'] else 'no'} |")
    out += ["", "## Off starts", ""]
    for base in order:
        p = RAW / f"off_{base}.json"
        if p.exists():
            o = json.loads(p.read_text(encoding="utf-8"))
            out.append(f"- `{base}`: line {tuple(o['hkl'])} at {o['two_theta']:.4f}°, FWHM "
                       f"{o['fwhm']:.5f}°, one-FWHM factor {o['factor']:.6f}")
    out += ["", "## Codes per fit", ""]
    for r in rows:
        if "error" not in r:
            out.append(f"- {r['start']} {r['arm']}: {', '.join(r['codes']) or 'none'}")
    Path(os.environ.get("WP2017G_SUMMARY", SUMMARY)).write_text("\n".join(out) + "\n", encoding="utf-8")
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
