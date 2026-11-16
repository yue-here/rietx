"""C3 and C10 on ``tests/test_absent_phase.py``'s fixture (WP-2018, task 3).

LaB₆ that is there plus a LaB₆ copy at a = 5.2 Å and scale 1e-9 that is not,
fitted with ``mccusker_default``, in four arms:

  default     main as shipped: support window, support hold/release/collapse, cell reset
  no_reset    ``refine.reset_cell_runaway`` patched to reset nothing
  no_support  ``plan.phase_support_sigma = None`` (hold, release, collapse and
              default cell window off; PHASE_UNCONSTRAINED still read at the default)
  neither     both off
  no_hold     ``refine._hold_unsupported_phases`` patched to hold nothing, so the
              support window, the collapse and the reset act alone
  window_only no_hold, and the collapse at the answer patched to collapse nothing
              (``_unsupported_phase_paths(..., at_answer=True)`` returns []): the
              support window and the reset act alone
  escape_no_hold, escape_no_support
              the positive arms: no_hold / no_support with the "cell" stage's
              first solve answering 1.3 x the absent phase's a, the injection
              ``tests/test_cell_runaway_safety.py`` uses, so a path the reset
              must reach exists; under no_hold the collapse reaches it too

C3 reads the absent phase's cell (value, esd, at_bound), which action took it
and in which stage; C10 reads whether PHASE_UNCONSTRAINED and FLOOR_HIT both
name phase 1, and the scale's row.

usage (repo root): python docs/wp/2018-measure/absent_phase.py [arm ...]
"""
from __future__ import annotations

import importlib
import sys

from common import OUT, emit, patched, provenance, record

import rietx as rx
from tests.test_absent_phase import _absent_phase_inputs
from tests.test_refine_synthetic import synthesize

# ``rietx.refine`` the attribute is the function; the module is imported by name
refine_module = importlib.import_module("rietx.refine")

ARMS = ("default", "no_reset", "no_support", "neither", "no_hold", "window_only",
        "escape_no_hold", "escape_no_support")
PATHS = ("phases.1.cell.a", "phases.1.scale", "phases.0.cell.a", "phases.0.scale")


ESCAPE = 1.3


def _escaping(real):
    """``run_least_squares`` whose "cell" stage's first solve escapes phase 1's a."""
    import dataclasses

    done = set()

    def solve(model, table, **kwargs):
        outcome = real(model, table, **kwargs)
        stage = kwargs.get("stage")
        if stage != "cell" or stage in done or "phases.1.cell.a" not in table.free_paths:
            return outcome
        done.add(stage)
        table.commit(outcome.theta)
        entry = table.entries[table._paths["phases.1.cell.a"]]
        entry.value = ESCAPE * entry.value
        table.refresh_ties()
        return dataclasses.replace(outcome, theta=table.x0())

    solve.done = done
    return solve


def fit(arm: str):
    if arm.startswith("escape_"):
        solve = _escaping(refine_module.run_least_squares)
        with patched(refine_module, "run_least_squares", solve):
            ref, result = fit(arm[len("escape_"):])
        assert solve.done, "the injection never ran"
        return ref, result
    plan = rx.RefinementPlan.mccusker_default()
    if arm in ("no_support", "neither"):
        plan.phase_support_sigma = None
    structure, ins = _absent_phase_inputs()
    ref = rx.Refinement(structure, ins, history=False)
    if arm in ("no_hold", "window_only",
        "escape_no_hold", "escape_no_support"):
        paths = refine_module._unsupported_phase_paths

        def no_collapse(*a, **k):
            return [] if k.get("at_answer") else paths(*a, **k)

        with patched(refine_module, "_hold_unsupported_phases",
                     lambda *a, **k: ([], {}, set())), \
                patched(refine_module, "_unsupported_phase_paths",
                        no_collapse if arm == "window_only" else paths):
            return ref, ref.fit(synthesize(), plan=plan, telemetry=False)
    if arm in ("no_reset", "neither"):
        with patched(refine_module, "reset_cell_runaway", lambda table, start: []):
            return ref, ref.fit(synthesize(), plan=plan, telemetry=False)
    return ref, ref.fit(synthesize(), plan=plan, telemetry=False)


def main(arms):
    emit({"provenance": provenance(), "fixture": "test_absent_phase"})
    OUT.mkdir(parents=True, exist_ok=True)
    for arm in arms:
        try:
            ref, result = fit(arm)
        except Exception as exc:          # a crash is a measured outcome here
            emit({"arm": arm, "error": f"{type(exc).__name__}: {exc}"[:400]})
            continue
        rec = record(result, PATHS)
        rec["arm"] = arm
        # a held cell has no row in result.parameters: the committed value
        rec["cell_a"] = [p.cell.a.value for p in ref.structure.phases]
        emit(rec)
        result.plot(path=str(OUT / f"c3_absent_phase_{arm}.png"))


if __name__ == "__main__":
    main(sys.argv[1:] or ARMS)
