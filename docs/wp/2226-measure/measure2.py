"""WP-2226 task 1, second pass.

(1) Option A with the frozen branch replaced by a rewindow whenever a window
    sized at the new values differs from the frozen one at all ("A-exact"):
    its error against a fresh 2 % compile, and its cost.
(2) The nac axial case split into window and quadrature: a fresh compile at
    2 % (declared FCJ node rule), at 1.99 % (closing node rule, ~2 % windows)
    and at 1e-3, as fractions of the strongest peak and in σ.
(3) Timings of preview.evaluate per case under both arms, repeated, for the
    load-quiet ranges.

Run from the repository root with an output directory outside the tree:
``.venv/bin/python docs/wp/2226-measure/measure2.py <out-dir>``.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("RIETX_TELEMETRY", "0")

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from measure import cases, fitted, fresh, set_tol  # noqa: E402

from rietx.gui import preview  # noqa: E402
from rietx.model import forward  # noqa: E402
from rietx.model.forward import recorded_window_tol  # noqa: E402

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
REPS = 15

rows = []
for name in ("fap", "nac"):
    project = fitted(name)
    res = project.refinement.result_
    tol2 = recorded_window_tol(res.stages[-1].window_area_tol)
    set_tol(project, None)
    case_list = cases(project, name)
    # (3) the timings, alternating arms per case so the load hits both
    for label, edits in case_list:
        times = {}
        for arm, tol in (("status quo", None), ("A", tol2)):
            set_tol(project, tol)
            preview.evaluate(project, {"values": edits})  # warm the base
            ts = []
            for _ in range(REPS):
                t0 = time.perf_counter()
                preview.evaluate(project, {"values": edits})
                ts.append(time.perf_counter() - t0)
            times[arm] = [round(1e3 * min(ts), 2), round(1e3 * float(np.median(ts)), 2),
                          round(1e3 * max(ts), 2)]
        # (1) A-exact: rewindow at the new values whenever anything moved
        set_tol(project, tol2)
        base = preview._base(project)
        with base.lock, preview._edited(project, base, edits):
            values = base.table.decode(base.table.x0())
            branch = preview._choose(base, values)
            if branch == "recompiled":
                ex_err, ex_ms = None, None
            else:
                ts = []
                for _ in range(REPS):
                    t0 = time.perf_counter()
                    model = forward.rewindow(base.model, values)
                    y = np.asarray(model.evaluate(values))
                    ts.append(time.perf_counter() - t0)
                m_own, y_own = fresh(project, edits, tol2)
                ex_err = float(np.max(np.abs(y - y_own) / np.asarray(m_own.sigma)))
                ex_ms = [round(1e3 * min(ts), 2), round(1e3 * float(np.median(ts)), 2)]
        row = {"pattern": name, "case": label, "A_branch": branch, "ms": times,
               "A_exact_err_sigma": ex_err, "A_exact_rewindow_eval_ms": ex_ms}
        rows.append(row)
        print(json.dumps(row), flush=True)
    if name == "nac":
        # (2) the axial case split
        edits = {"instrument.geometry.axial_sl": 0.025}
        curves = {tol: fresh(project, edits, tol) for tol in (0.02, 0.0199, 1e-3)}
        ref_m, ref_y = curves[1e-3]
        sig = np.asarray(ref_m.sigma)
        ymax = float(np.max(np.abs(ref_y)))
        split = {f"{tol}": {"sigma": float(np.max(np.abs(y - ref_y) / sig)),
                            "frac_of_max": float(np.max(np.abs(y - ref_y)) / ymax)}
                 for tol, (m, y) in curves.items()}
        print(json.dumps({"nac axial split vs 1e-3": split}), flush=True)
        rows.append({"nac_axial_split": split})
    set_tol(project, None)

(OUT / "rows2.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
