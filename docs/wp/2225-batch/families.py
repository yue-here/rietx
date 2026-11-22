"""WP-2225 task 1: options 1 and 2 beside today's hold, on the multi-phase families and the
four standards whose plan holds a twin.

  families.py OUT.jsonl FAMILY[,FAMILY] [CLOSING[,CLOSING]]

FAMILY: cpd1a_b0.5, cpd1a_b1.5 (the round-robin cpd-1a from the two Biso starts of
`tests/test_staged_start_invariance`), lab6cbn (`PLAN_DEGENERATE`, X and Y freed beside both
phases' Lorentzian widths), lab6cbn_shared (`PLAN_SHARED`, no twin pair: the suite's trusted
protocol, run under `today` alone), brucite_steph (brucite with an all-zero Stephens block,
`tests/test_acceptance_stephens._plan(texture=True, stephens=True)`, default LM driver),
and the comparison standards zincite, fluorite, corundum, brucite.
CLOSING: decl (the protocol's own setting), off (None), on (1e-3).  Default decl.
ARMS=opt2,... in the environment runs only those arms.

Arms, each from the protocol's start:
  today    the shipped width twin hold
  opt1     swap on the floor (`swap.swap_hold`): a pair whose specimen twins all sit on
           their floor at a stage start holds the twins and frees the instrument column
  opt2     today's fit, then rounds of a two-stage plan until Rwp moves under 1e-7 (at most
           8 rounds): every glob the plan frees before the first stage that held a twin,
           then every glob the plan frees, each half collapsed as a warm re-fit collapses a
           plan (`strategy.refit._collapse`: no seed, the half's last-stage ftol, restraint
           weight and window slack) under the plan's own plan-level settings, refit="stages".
           No round runs when the first stage held a twin or only the closing stage did.
           `iterations` and `seconds` total the first fit and every round.
  nohold   the hold switched off (the hold-off reference)
`today` and `opt1` are each followed by one staged re-fit under the same rule (`+1`,
refit="stages"), the WP's acceptance reading.

Each row: Rwp, chi2, iterations, seconds, the last stage's held paths and twin pairs, the
profile u v w x y off the model, weight fractions with esds, warning codes, every reported
parameter (value, plain esd, reported esd), and for brucite_steph the count of reflections with σ²(M) < 0.
"""
import copy
import json
import os
import sys
import time
import warnings
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402

import rietx as rx  # noqa: E402
from rietx.schemas.plan import CLOSING_WINDOW_TOL  # noqa: E402
from rietx.strategy.refit import _collapse  # noqa: E402
from rietx.viz import compare  # noqa: E402

warnings.simplefilter("ignore")
RF = sys.modules["rietx.refine"]
TODAY = RF._hold_width_twins
import swap  # noqa: E402  (imports nothing it runs)

OUTPNG = ROOT / "tests" / "output"


def nohold(table, unseen):
    return [], {}, {}


RULES = {"today": TODAY, "opt1": swap.swap_hold, "opt2": TODAY, "nohold": nohold}


def family(name):
    """(data, structure, instrument, plan, fit kwargs, phase names)."""
    if name.startswith("cpd1a_b"):
        from tests.test_window_domain import _protocol
        data, st, ins, plan, kw = _protocol("cpd1a")
        b = float(name.split("_b")[1])
        for ph in st.phases:
            for atom in ph.atoms:
                atom.biso.value = b
        return data, st, ins, plan, kw
    if name.startswith("lab6cbn"):
        import tests.test_acceptance_lab6_cbn as m
        st, ins = m._inputs()
        plan = copy.deepcopy(m.PLAN_SHARED if name.endswith("shared") else m.PLAN_DEGENERATE)
        return rx.read_pattern(m.PATTERN), st, ins, plan, {"two_theta_limits": m.LIMITS}
    if name == "brucite_steph":
        import tests.test_acceptance_stephens as m
        from tests.test_acceptance_qpa_roundrobin import (
            DATA,
            brucite_phase,
            qarr_instrument,
            seed_scales,
        )
        data = rx.read_pattern(DATA / "brucite.prn")
        st = rx.Structure(phases=[m._with_block(brucite_phase(textured=True))])
        ins = qarr_instrument()
        seed_scales(st, ins, data)
        return data, st, ins, m._plan(texture=True, stephens=True), {}
    std = next(s for s in compare.STANDARDS if s.key == name)
    inp = std.build(compare.default_data_dir())
    return (inp.data, inp.structure, inp.instrument, inp.plan,
            {"two_theta_limits": inp.two_theta_limits})


def row(fam, arm, clos, ref, res, dt, extra=None):
    prof = ref.instrument.profile
    last = res.stages[-1]
    out = {"family": fam, "arm": arm, "closing": clos, "seconds": dt,
           "rwp": res.statistics.rwp, "chi2": res.statistics.chi2,
           "iterations": sum(s.n_iterations for s in res.stages),
           "status": res.status,
           "held": list(last.held), "twins": dict(last.width_twins_held or {}),
           "swapped": sorted(set(swap.SWAPS)),
           "profile": {k: getattr(prof, k).value for k in "uvwxy" if hasattr(prof, k)},
           "codes": sorted({d.code for d in res.diagnostics
                            if d.level in ("warning", "error")}),
           "params": {p.path: [p.value, p.stderr_uncorrected, p.stderr] for p in res.parameters},
           "inflation": res.statistics.esd_inflation,
           "specimen": {p: v for p, v in
                        ((f"phases.{i}.{w}", getattr(ph, w).value)
                         for i, ph in enumerate(ref.structure.phases)
                         for w in ("gauss_size", "gauss_strain", "lor_size", "lor_strain"))}}
    # a single-phase fit carries no QPA block
    out["qpa"] = {} if res.qpa is None else {
        r.name: [100.0 * r.weight_fraction,
                 None if r.weight_fraction_stderr is None else 100.0 * r.weight_fraction_stderr]
        for r in res.qpa.phases}
    if fam == "brucite_steph":
        from tests.test_acceptance_stephens import _sigma2_of
        out["sigma2_negative"] = int(np.sum(_sigma2_of(ref) < 0.0))
    if extra:
        out.update(extra)
    return out


def plan_for(base, clos):
    p = copy.deepcopy(base)
    if clos == "off":
        p.closing_window_tol = None
    elif clos == "on":
        p.closing_window_tol = CLOSING_WINDOW_TOL
    return p


def fit(ref, data, plan, kw, refit="single"):
    swap.SWAPS.clear()
    t0 = time.perf_counter()
    res = ref.fit(data, plan=plan, refit=refit, **kw)
    return res, time.perf_counter() - t0


def plot(res, tag):
    OUTPNG.mkdir(exist_ok=True)
    res.plot(path=str(OUTPNG / f"wp2225_{tag}.png"))
    import matplotlib.pyplot as plt
    plt.close("all")


def main():
    out = sys.argv[1]
    fams = sys.argv[2].split(",")
    closings = sys.argv[3].split(",") if len(sys.argv) > 3 else ["decl"]
    with open(out, "a", encoding="utf-8") as fh:
        def put(r):
            fh.write(json.dumps(r, default=str) + "\n")
            fh.flush()
            q = " ".join(f"{k}={v[0]:.3f}" for k, v in r["qpa"].items()) if len(r["qpa"]) > 1 else ""
            print(f"{r['family']:14s} {r['closing']:4s} {r['arm']:9s} rwp={r['rwp']:.6f} "
                  f"it={r['iterations']} {r['seconds']:.1f}s twins={sorted(r['twins'])} "
                  f"swapped={r['swapped']} {q} {r.get('rounds', '')}", flush=True)

        for fam in fams:
            for clos in closings:
                arms = ["today"] if fam == "lab6cbn_shared" else ["today", "opt1", "opt2", "nohold"]
                if os.environ.get("ARMS"):  # e.g. ARMS=opt2 re-runs one arm
                    arms = [a for a in arms if a in os.environ["ARMS"].split(",")]
                for arm in arms:
                    RF._hold_width_twins = RULES[arm]
                    data, st, ins, base, kw = family(fam)
                    plan = plan_for(base, clos)
                    ref = rx.Refinement(st, ins, history=False)
                    res, dt = fit(ref, data, plan, kw)
                    if arm == "opt2":
                        names = [s.name for s in plan.stages]
                        k = next((i for i, s in enumerate(res.stages) if s.width_twins_held), None)
                        rounds, total, trace = 0, dt, [res.statistics.rwp]
                        its = sum(s.n_iterations for s in res.stages)
                        kp = (names.index(res.stages[k].name) if res.stages[k].name in names
                              else len(names)) if k is not None else None
                        # kp == 0 leaves no instrument-only stage, and kp == len(names) (the
                        # closing stage held first) makes it the whole plan: no round to run
                        if kp is not None and 0 < kp < len(names):
                            # `_collapse` carries each half's stage and plan fields (max_iter,
                            # ftol, restraint weight, window slack, strain_seed, no seed), as a
                            # warm re-fit does; the plan-level fields come from `plan` itself
                            inst = _collapse(replace(plan, stages=plan.stages[:kp])).stages[0]
                            whole = _collapse(plan).stages[0]
                            p2 = replace(plan, stages=[replace(inst, name="inst_round"),
                                                       replace(whole, name="all_round")])
                            for rounds in range(1, 9):
                                res, d2 = fit(ref, data, copy.deepcopy(p2), kw, refit="stages")
                                total += d2
                                its += sum(s.n_iterations for s in res.stages)
                                trace.append(res.statistics.rwp)
                                if abs(trace[-1] - trace[-2]) < 1e-7:
                                    break
                        # iterations and seconds both total the first fit and every round
                        put(row(fam, arm, clos, ref, res, total,
                                {"rounds": rounds, "rwp_trace": trace, "iterations": its,
                                 "first_held_stage": kp}))
                        plot(res, f"{fam}_{clos}_{arm}")
                        continue
                    put(row(fam, arm, clos, ref, res, dt))
                    plot(res, f"{fam}_{clos}_{arm}")
                    if arm in ("today", "opt1") and fam != "lab6cbn_shared":
                        res, dt = fit(ref, data, plan_for(base, clos), kw, refit="stages")
                        put(row(fam, arm + "+1", clos, ref, res, dt))
    RF._hold_width_twins = TODAY


if __name__ == "__main__":
    main()
