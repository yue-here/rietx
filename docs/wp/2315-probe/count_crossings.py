"""WP-2315 task 1: how often a Pawley step crosses a width row, per stage.

A measurement scaffold, not package code.  It wraps ``lm.minimize`` and
``lm._solve_constrained_step`` and prints, for every least-squares run a case
makes, the free-column count, the crossings by block label
(``LMOutcome.truncated_by``), the run's wall and the time spent in the
constrained step.  Nothing it prints is a structural claim.

    RIETX_TELEMETRY=0 .venv/bin/python docs/wp/2315-probe/count_crossings.py CASE [SOLVER]

    CASE    bigcell:TTMAX   WP-2317 probe 1's pattern (P 21 21 21, 10 atoms),
                            Pawley, mccusker_default
            fap             the GSAS-II FAP.XRA tutorial, Pawley, default plan
                            (tests/test_acceptance_fap.py's protocol)
            nac             11-BM NAC, Pawley, default plan, the whole file
            nac:TTMAX       the same, 2θ ≤ TTMAX
            qarr:SAMPLE     a QPA round-robin sample 1 pattern (cpd-1a..1h,
                            lab Cu to high angle), its three phases, Pawley,
                            default plan
            fap-index       index_pattern on FAP.XRA, as the fap_index fixture
                            (hexagonal and trigonal, preset "full"): every
                            candidate's Pawley validation fit
            bench:KEY       a single-fit case of examples/bench_refinement.py
                            (e.g. bigcell-pawley, bigcell-pawley-120), run
                            as that harness's _run_once runs it
    SOLVER  lm (default) | trf

    PROBE=path   run a variant of probe 1 in its place (bigcell only).  The
                 WP's strained variant is probe 1 with the truth's
                 ``lor_strain`` set to 0.03 (the start keeps 0.0).

The wrapper's own charge is two ``perf_counter`` calls a constrained step.
"""
import os
import runpy
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import rietx as rx  # noqa: E402
from rietx.optimize import lm  # noqa: E402

case = sys.argv[1]
solver = sys.argv[2] if len(sys.argv) > 2 else "lm"
runs: list[dict] = []
_in_step = [0.0]

_minimize, _constrained = lm.minimize, lm._solve_constrained_step


def minimize(residual, jacobian, x0, **kw):
    _in_step[0] = 0.0
    t0 = time.perf_counter()
    out = _minimize(residual, jacobian, x0, **kw)
    runs.append(dict(n=len(x0), crossings=out.n_truncated, by=dict(out.truncated_by),
                     wall=time.perf_counter() - t0, step=_in_step[0],
                     n_ineq=sum(len(iq.c) for iq in kw.get("inequalities") or [])))
    return out


def constrained(*a, **kw):
    t0 = time.perf_counter()
    try:
        return _constrained(*a, **kw)
    finally:
        _in_step[0] += time.perf_counter() - t0


lm.minimize, lm._solve_constrained_step = minimize, constrained

_init = rx.Refinement.__init__


def init(self, *a, **kw):
    kw.setdefault("solver", solver)
    _init(self, *a, **kw)


rx.Refinement.__init__ = init

t0 = time.perf_counter()
result = None
if case.startswith("bigcell:"):
    os.environ.setdefault("PROFILE", "0")
    sys.argv = ["probe1", "pawley", "P 21 21 21", case.split(":")[1], "10"]
    ns = runpy.run_path(os.environ.get(
        "PROBE", str(ROOT / "docs/wp/2317-probe/probe1_bigcell.py")))
    result = ns["res"]
elif case == "fap":
    from tests.test_acceptance_fap import build_fap_inputs
    data, st, ins = build_fap_inputs()
    result = rx.Refinement(st, ins).fit(data, mode="pawley", telemetry=False)
elif case.startswith("nac"):
    from tests.test_acceptance_nac import build_nac_inputs
    data, st, ins = build_nac_inputs()
    lim = (None if case == "nac"
           else (float(data.two_theta[0]), float(case.split(":")[1])))
    result = rx.Refinement(st, ins).fit(data, mode="pawley", two_theta_limits=lim,
                                        telemetry=False)
elif case.startswith("qarr:"):
    from tests.test_acceptance_qpa_roundrobin import (
        DATA,
        corundum_phase,
        fluorite_phase,
        qarr_instrument,
        zincite_phase,
    )
    data = rx.read_pattern(DATA / f"{case.split(':')[1]}.prn")
    st = rx.Structure(phases=[corundum_phase(), fluorite_phase(), zincite_phase()])
    result = rx.Refinement(st, qarr_instrument()).fit(data, mode="pawley",
                                                      telemetry=False)
elif case == "fap-index":
    from rietx.indexing import index_pattern
    from rietx.indexing.engines import SearchSpec
    from rietx.indexing.pick import pick_peaks
    from tests.test_acceptance_fap import build_fap_inputs
    data, _st, ins = build_fap_inputs()
    spec = SearchSpec(systems=("hexagonal", "trigonal"), max_volume=600.0,
                      budget_seconds=300.0, n_unindexed=3)
    res = index_pattern(pick_peaks(data, ins), data=data, instrument=ins, spec=spec,
                        preset="full")
    print(f"index_pattern: {len(res.candidates)} candidates")
elif case.startswith("bench:"):
    sys.path.insert(0, str(ROOT / "examples"))
    import bench_refinement as bench
    key = case.split(":", 1)[1]
    found = next((c for c in bench.CASES if c.key == key), None)
    if found is None:
        raise SystemExit(f"unknown bench case {key!r}; one of "
                         f"{', '.join(c.key for c in bench.CASES)}")
    setup = found.build()
    if setup.patterns is not None:
        raise SystemExit(f"bench case {key!r} is a series; bench:KEY runs "
                         "single-fit cases only")
    # a build may fit (nac's Le Bail seed); its runs are not the case's
    runs.clear()
    ref = rx.Refinement(setup.structure.model_copy(deep=True),
                        setup.instrument.model_copy(deep=True), history=False)
    if setup.prepare is not None:
        setup.prepare(ref)
    t0 = time.perf_counter()
    result = ref.fit(setup.data, plan=setup.plan, mode=setup.mode,
                     two_theta_limits=setup.limits, telemetry=False)
else:
    raise SystemExit(f"unknown case {case!r}")
wall = time.perf_counter() - t0

print(f"case {case}  solver {solver}  wall {wall:.1f} s  runs {len(runs)}")
if result is not None:
    print(f"Rwp {result.statistics.rwp:.6f}")
    for st in result.stages:
        print(f"  stage {st.name:<24} n_iter {st.n_iterations:>4}  "
              f"crossings {st.n_constraint_truncations:>3}  status {st.status}")
past = [r for r in runs if r["n"] > lm.BVLS_MAX_COLUMNS]
print(f"least-squares runs {len(runs)}, past BVLS_MAX_COLUMNS {len(past)}, "
      f"crossing {sum(1 for r in runs if r['crossings'])}")
for i, r in enumerate(runs):
    print(f"  run {i:>3}  n {r['n']:>5}  rows {r['n_ineq']:>5}  "
          f"crossings {r['crossings']:>3}  wall {r['wall']:7.2f} s  "
          f"constrained step {r['step']:7.2f} s  {r['by']}")
print(f"total constrained-step time {sum(r['step'] for r in runs):.1f} s "
      f"of {wall:.1f} s")
