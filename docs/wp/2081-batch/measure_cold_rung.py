"""WP-2081: what a setup parameter is on a frame the ladder sends to the cold rung.

Run from the repository root:

    .venv/bin/python docs/wp/2081-batch/measure_cold_rung.py

The series is the first four patterns of ``tests/test_sequential.py``'s
thermal LaB6 ramp (true zero shift 0.008 deg, start model 0.0). Frame 2's two
warm rungs are made to raise, the way issue #224's runaway neighbour made them
raise, so the ladder keeps its cold rung. Four arms:

- ``free``: the default. The plan frees ``instrument.zero_shift`` on every frame.
- ``free_forced``: the same, frame 2 forced to the cold rung.
- ``held_forced``: ``constrain`` holds the zero shift from frame 1 on, which is
  the nearest spelling of "refine on frame 0, then freeze"; frame 2 forced cold.
- ``hooks_forced``: the three-hook workaround. ``on_result`` keeps frame 0's
  zero shift, ``prepare`` writes it into every later frame's instrument, and
  ``constrain`` holds it; frame 2 forced cold.

Prints one row per frame and writes ``cold_rung.json`` beside this file.
"""

from __future__ import annotations

import json
import os
import platform
import sys
import time
from pathlib import Path

os.environ.setdefault("RIETX_TELEMETRY", "0")
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import rietx  # noqa: E402
from rietx import sequential  # noqa: E402
from rietx.sequential import SequentialRefinement, _PatternRaised  # noqa: E402
from tests.test_sequential import (  # noqa: E402
    A0,
    RAMP,
    TRUE_ZERO,
    _simulate,
    _start_models,
)

N = 4
FORCED = 2
PATH = "instrument.zero_shift"

_original_fit_one = SequentialRefinement._fit_one


def _forcing(self, data, label, previous, *args, **kwargs):
    """Raise on frame FORCED's warm rungs, so the ladder reaches the cold one."""
    index = args[8]  # _fit_one's positional ``index``
    if index == FORCED and previous is not None:
        raise _PatternRaised(RuntimeError("forced to the cold rung (WP-2081)"))
    return _original_fit_one(self, data, label, previous, *args, **kwargs)


def run(arm: str, patterns) -> list[dict]:
    structure, instrument = _start_models()
    series = SequentialRefinement(structure, instrument)
    kept: dict[str, float] = {}

    def on_result(index, result):
        if index == 0:
            kept["zero"] = sequential._value_of(result, PATH)

    def prepare(index, data, structure, instrument):
        if index > 0 and "zero" in kept:
            instrument.zero_shift.value = kept["zero"]

    def constrain(index, ref):
        if index > 0:
            ref.hold(PATH)

    hooks: dict = {}
    if arm == "held_forced":
        hooks = {"constrain": constrain}
    elif arm == "hooks_forced":
        hooks = {"constrain": constrain, "prepare": prepare,
                 "on_result": on_result}
    forced = arm != "free"
    SequentialRefinement._fit_one = _forcing if forced else _original_fit_one
    try:
        result = series.fit(patterns, plan="mccusker_default", **hooks)
    finally:
        SequentialRefinement._fit_one = _original_fit_one
    rows = []
    for k, entry in enumerate(result.entries):
        ins = series.fitted_instruments[k]
        st = series.fitted_structures[k]
        a_true = A0 * (1.0 + RAMP * k)
        a_fit = st.phases[0].cell.a.value
        esd = next((p.stderr for p in series.results_[k].parameters
                    if p.path == PATH), None)
        rows.append({
            "arm": arm, "frame": k, "rung": entry.rung,
            "rungs_tried": entry.rungs_tried,
            "zero_shift": ins.zero_shift.value, "zero_esd": esd,
            "cell_a_ppm": 1e6 * (a_fit - a_true) / a_true,
            "gof": entry.statistics.gof if entry.statistics else None,
        })
    return rows


def main() -> None:
    t0 = time.time()
    patterns = [_simulate(A0 * (1.0 + RAMP * k), seed=11 + k) for k in range(N)]
    out = {
        "platform": f"{platform.system()} {platform.machine()}",
        "python": platform.python_version(),
        "rietx": rietx.__version__,
        "venv": "worktree .venv, [dev]",
        "true_zero_shift": TRUE_ZERO,
        "start_zero_shift": 0.0,
        "rows": [],
    }
    for arm in ("free", "free_forced", "held_forced", "hooks_forced"):
        out["rows"].extend(run(arm, patterns))
    out["seconds"] = round(time.time() - t0, 1)
    print(f"{'arm':13s} {'frame':>5s} {'rung':>11s} {'zero (deg)':>11s} "
          f"{'esd':>9s} {'cell a (ppm)':>12s} {'GoF':>6s}")
    for r in out["rows"]:
        esd = "held" if r["zero_esd"] is None else f"{r['zero_esd']:.2e}"
        print(f"{r['arm']:13s} {r['frame']:5d} {r['rung']:>11s} "
              f"{r['zero_shift']:11.5f} {esd:>9s} {r['cell_a_ppm']:12.1f} "
              f"{r['gof']:6.3f}")
    print(f"{out['platform']}, Python {out['python']}, rietx {out['rietx']}, "
          f"{out['seconds']} s")
    Path(__file__).with_name("cold_rung.json").write_text(
        json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
