"""WP-2224 task 3: a re-fit after a model swap that adds a block at its identity.

Each case first fits a standard without the block, adds the block at the value
where it changes nothing (``Refinement.edit``), and then fits from that state
twice: the plan collapsed into one stage (``single``) and the plan as declared
(``staged``, ``refit="stages"``).  Both run with no closing stage, the default
WP-2222 sets and the one WP-2224 § Measured is against.

Cases:
  brucite+md    March-Dollase on (001) at r = 1, freed by a last ``po`` stage
  brucite+sh    spherical-harmonics texture to order 4 at zero, freed by ``texture``
  nac+caf2      NAC fitted alone, then the CaF2 impurity added at scale 1e-7

  swap.py OUT.jsonl [case,case]

One JSON line per fit.  Run with RIETX_TELEMETRY=0, one fit at a time.
"""
import json
import sys
import time
import warnings

from rietx.refine import Refinement
from rietx.schemas.structure import PreferredOrientation, SphericalHarmonicTexture
from rietx.strategy.refit import _collapse
from rietx.strategy.staged import Stage
from rietx.viz import compare

warnings.simplefilter("ignore")
OUT = sys.argv[1]
ONLY = sys.argv[2].split(",") if len(sys.argv) > 2 and sys.argv[2] else None
DATA = compare.default_data_dir()


def _std(key):
    return next(s for s in compare.STANDARDS if s.key == key)


def _no_close(plan):
    plan.closing_window_tol = None
    return plan


def brucite(block):
    std = _std("brucite")

    def before():
        inputs = std.build(DATA)
        return inputs, _no_close(inputs.plan)

    def swap(ref):
        structure = ref.structure.model_copy(deep=True)
        phase = structure.phases[0]
        if block == "md":
            phase.preferred_orientation = PreferredOrientation(axis=(0, 0, 1))
        else:
            phase.texture = SphericalHarmonicTexture(order=4)
        ref.edit(structure=structure)

    def after(inputs):
        plan = _no_close(std.build(DATA).plan)
        if block == "md":
            plan.stages.append(Stage("po", ["phases.*.preferred_orientation.r"]))
        else:
            plan.stages.append(Stage("texture", ["phases.*.texture.*"]))
        return plan

    return before, swap, after


def nac_caf2():
    std = _std("nac")

    def before():
        inputs = std.build(DATA)
        inputs.structure.phases = inputs.structure.phases[:1]
        return inputs, _no_close(inputs.plan)

    def swap(ref):
        full = std.build(DATA).structure
        structure = ref.structure.model_copy(deep=True)
        structure.phases.append(full.phases[1])
        ref.edit(structure=structure)

    def after(inputs):
        return _no_close(std.build(DATA).plan)

    return before, swap, after


CASES = {"brucite+md": brucite("md"), "brucite+sh": brucite("sh"),
         "nac+caf2": nac_caf2()}


def row(case, arm, dt, res):
    st = res.statistics
    return {"case": case, "arm": arm, "seconds": dt, "status": res.status,
            "rwp": st.rwp, "nfev": [s.n_iterations for s in res.stages],
            "stage_names": [s.name for s in res.stages],
            "codes": sorted({d.code for d in res.diagnostics
                             if d.level in ("warning", "error")}),
            "params": {p.path: [p.value, p.stderr] for p in res.parameters}}


with open(OUT, "a", encoding="utf-8") as fh:
    for case, (before, swap, after) in CASES.items():
        if ONLY and case not in ONLY:
            continue
        inputs, plan0 = before()
        kw = dict(two_theta_limits=inputs.two_theta_limits)
        ref = Refinement(inputs.structure, inputs.instrument)
        first = ref.fit(inputs.data, plan=plan0, **kw)
        print(case, "first", first.status, f"rwp={first.statistics.rwp:.5f}", flush=True)
        swap(ref)
        start = ref._head_id
        for arm in ("single", "staged"):
            ref.checkout(start)
            plan = after(inputs)
            run = _collapse(plan) if arm == "single" else plan
            t0 = time.perf_counter()
            res = ref.fit(inputs.data, plan=run, refit="stages", **kw)
            dt = time.perf_counter() - t0
            fh.write(json.dumps(row(case, arm, dt, res), default=str) + "\n")
            fh.flush()
            print(case, arm, f"{dt:.2f}s", res.status, f"rwp={res.statistics.rwp:.5f}",
                  f"nfev={sum(s.n_iterations for s in res.stages)}", flush=True)
