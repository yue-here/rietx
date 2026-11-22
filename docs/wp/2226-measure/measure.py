"""WP-2226 task 1: the GUI preview at the fit's 2 % windows, on fap and nac.

For each case of tests/test_gui_preview.py, under the status quo (the preview
compiles at compile_model's default 1e-3 windows) and under option A (the
preview compiles at the last fit's recorded fraction, 2 %):

- which branch the chooser picks,
- the preview's largest error against a fresh compile at its own fraction
  (what the tests assert), in σ,
- the preview's and the fresh-2 % compile's largest error against a fresh
  1e-3 compile (near-complete tails, the closest thing to the untruncated
  curve), in σ,

and at the base values the shift between the preview and the fit's own
y_calc / Rwp.

Run from the repository root with an output directory outside the tree:
``.venv/bin/python docs/wp/2226-measure/measure.py <out-dir>``.
"""

from __future__ import annotations

import json
import os
import sys
import time
from functools import partial
from pathlib import Path

os.environ.setdefault("RIETX_TELEMETRY", "0")

import numpy as np

from rietx.examples import build_example
from rietx.gui import preview
from rietx.model.forward import compile_model, recorded_window_tol

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)


def fitted(name):
    project = build_example(name, OUT / f"proj-{name}-{os.getpid()}")
    project.fit()
    return project


def fresh(project, edits, tol):
    r = project.refinement
    structure = r.structure.model_copy(deep=True)
    instrument = r.instrument.model_copy(deep=True)
    table = r._working_table()
    for e in table.entries:
        if e.path in edits:
            e.value = edits[e.path]
    table.refresh_ties()
    table.apply_to_models(structure, instrument)
    model = compile_model(structure, instrument, project.data, mode=project.doc.mode,
                          two_theta_limits=project.doc.two_theta_limits,
                          window_area_tol=tol)
    return model, np.asarray(model.evaluate(table.decode(table.x0())))


def set_tol(project, tol):
    """Point the preview's compiles at ``tol`` and drop its cached base."""
    preview.compile_model = partial(compile_model, window_area_tol=tol)
    preview._CACHE.pop(project, None)


def rwp(y_obs, y, sig):
    return float(np.sqrt(np.sum(((y_obs - y) / sig) ** 2) / np.sum((y_obs / sig) ** 2)))


def timed(project, edits, n=7):
    ts = []
    for _ in range(n):
        t0 = time.perf_counter()
        preview.evaluate(project, {"values": edits})
        ts.append(time.perf_counter() - t0)
    return [round(1e3 * min(ts), 2), round(1e3 * float(np.median(ts)), 2)]


def cases(project, name):
    base = preview._base(project)
    v = base.values
    fwhm = float(np.median(base.model.phase_peaks(0, v)[0][1]))
    out = [("base", {}),
           ("scale x0.5", {"phases.0.scale": v["phases.0.scale"] * 0.5}),
           ("scale x2", {"phases.0.scale": v["phases.0.scale"] * 2.0}),
           ("zero +1 FWHM", {"instrument.zero_shift": v["instrument.zero_shift"] + fwhm})]
    if name == "nac":
        out += [("cell a x1.0005", {"phases.0.cell.a": v["phases.0.cell.a"] * 1.0005}),
                ("lor_size 0.02", {"phases.0.lor_size": 0.02}),
                ("axial_sl 0.025", {"instrument.geometry.axial_sl": 0.025})]
    if name == "fap":
        out += [("w x4", {"instrument.profile.w": 4 * v["instrument.profile.w"]}),
                ("zero +1.0 deg", {"instrument.zero_shift": v["instrument.zero_shift"] + 1.0})]
    return out


if __name__ == "__main__":
    rows = []
    summary = {}
    for name in ("fap", "nac"):
        project = fitted(name)
        res = project.refinement.result_
        last_tol = recorded_window_tol(res.stages[-1].window_area_tol)
        y_fit = np.asarray(res.y_calc)
        sig_fit = np.asarray(res.sig())
        summary[name] = {"last_stage": res.stages[-1].name,
                         "last_stage_tol_recorded": res.stages[-1].window_area_tol,
                         "last_tol": last_tol, "rwp_fit": res.statistics.rwp,
                         "n_points": len(y_fit), "ymax": float(np.max(np.abs(y_fit)))}
        # the base cases are built at the status quo's compile, so both arms
        # take the same edits
        set_tol(project, None)
        case_list = cases(project, name)
        for arm, tol in (("status quo 1e-3", None), ("A: fit's fraction", last_tol)):
            set_tol(project, tol)
            for label, edits in case_list:
                answer = preview.evaluate(project, {"values": edits})
                y = answer.arrays["y_calc"]
                m_own, y_own = fresh(project, edits, tol)
                m_ref, y_ref = fresh(project, edits, None)
                sig = np.asarray(m_ref.sigma)
                row = {"pattern": name, "arm": arm, "case": label,
                       "evaluated": answer.header["evaluated"],
                       "err_vs_own_fresh_sigma": float(np.max(np.abs(y - y_own) / sig)),
                       "err_vs_1e3_fresh_sigma": float(np.max(np.abs(y - y_ref) / sig)),
                       "own_fresh_vs_1e3_sigma": float(np.max(np.abs(y_own - y_ref) / sig)),
                       "rwp": answer.header["rwp"],
                       "ms_min_median": timed(project, edits)}
                if label == "base":
                    row["vs_fit_ycalc_frac_of_max"] = float(
                        np.max(np.abs(y - y_fit)) / np.max(np.abs(y_fit)))
                    row["vs_fit_ycalc_counts"] = float(np.max(np.abs(y - y_fit)))
                    row["vs_fit_ycalc_sigma"] = float(np.max(np.abs(y - y_fit) / sig_fit))
                    row["rwp_minus_fit"] = answer.header["rwp"] - res.statistics.rwp
                rows.append(row)
                print(json.dumps(row), flush=True)
        # option B: the curves route redrawn at 1e-3 over the fit's own values
        _, y13 = fresh(project, {}, None)
        summary[name]["B_curves_rwp_1e3"] = rwp(np.asarray(res.y_obs), y13, sig_fit)
        summary[name]["B_curves_minus_fit_rwp"] = summary[name]["B_curves_rwp_1e3"] - res.statistics.rwp
        summary[name]["B_curves_shift_frac_of_max"] = float(
            np.max(np.abs(y13 - y_fit)) / np.max(np.abs(y_fit)))
        # what a full compile costs at each fraction (the "always recompile" arm)
        for tol in (None, last_tol):
            ts = []
            for _ in range(5):
                t0 = time.perf_counter()
                fresh(project, {}, tol)
                ts.append(time.perf_counter() - t0)
            summary[name][f"compile_ms_{tol}"] = [round(1e3 * min(ts), 1),
                                                  round(1e3 * float(np.median(ts)), 1)]
        print(json.dumps({name: summary[name]}), flush=True)

    (OUT / "rows.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
