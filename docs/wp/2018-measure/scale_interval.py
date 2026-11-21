"""C2: the profile interval's refits against the support hold (WP-2018, task 3).

``Refinement.profile_interval`` pins a parameter and refits everything else
through ``run_stage``; since #1075 each refit starts from the fit's own free
set (``parameter_interval._walk``'s ``fresh()``), so it cannot free what the
fit held, but every refit is a stage, and the stage re-decides the support
hold (WP-1301, WP-1523) from where it starts.  A weak phase's scale pinned low
can therefore hold that phase's cell (and more) where the fit left it free:
the half of the pair still live.  Two datasets, two arms each:

  cpd1a       ``qarr/cpd-1a`` under the round robin's ``qpa_plan()``, three
              phases; the interval on ``phases.0.scale`` (corundum, 1.15 wt %
              weighed, the smallest weighed fraction in the round robin)
  trace       ``tests/test_qpa_multimodal.py``'s two-basin trace fit (C1's
              fixture); the interval on ``phases.1.scale`` (CaF₂, 0.93(33)
              wt %): the positive arm, a phase near the support threshold
              where a pinned scale below it must reach the hold

  shipped     the interval as main runs it
  no_hold     the same fit; during the interval only, the stage-start hold
              (``refine._hold_unsupported_phases``) and the collapse at the
              answer (``refine._unsupported_phase_paths(..., at_answer=True)``)
              act on nothing, so each refit frees exactly the fit's free set

Per refit (a ``run_stage`` named ``interval:<path>``): the pinned value, what
the stage held, released and collapsed, and data χ².  Then the interval's
ends, stops and refit count per arm.

usage (repo root): python docs/wp/2018-measure/scale_interval.py [dataset_arm ...]
"""
from __future__ import annotations

import importlib
import os
import sys

from common import OUT, emit, patched, provenance, record

os.environ.setdefault("RIETX_TELEMETRY", "0")

import rietx as rx  # noqa: E402
from rietx.strategy.fraction_profile import data_chi2  # noqa: E402

refine_module = importlib.import_module("rietx.refine")

ARMS = ("cpd1a_shipped", "cpd1a_no_hold", "trace_shipped", "trace_no_hold")
TARGET = {"cpd1a": "phases.0.scale", "trace": "phases.1.scale"}

_FITS: dict = {}


def _fit(dataset: str):
    """One fit per dataset, shared by both arms (the arms differ only in the probe)."""
    if dataset in _FITS:
        return _FITS[dataset]
    if dataset == "cpd1a":
        from tests.test_acceptance_qpa_roundrobin import (
            DATA,
            corundum_phase,
            fluorite_phase,
            qarr_instrument,
            qpa_plan,
            seed_scales,
            zincite_phase,
        )
        data = rx.read_pattern(DATA / "cpd-1a.prn")
        structure = rx.Structure(phases=[corundum_phase(), zincite_phase(),
                                         fluorite_phase()])
        ins = qarr_instrument()
        seed_scales(structure, ins, data)
        ref = rx.Refinement(structure, ins)
        result = ref.fit(data, plan=qpa_plan(), telemetry=False)
    else:
        from tests.test_qpa_multimodal import HUMP, TRACE_SCALE, _fitted
        ref, result, data = _fitted(TRACE_SCALE, HUMP)
    _FITS[dataset] = (ref, result, data)
    return _FITS[dataset]


def _refit_spy(log):
    real = rx.Refinement.run_stage

    def run_stage(self, data, stage, *a, **k):
        r = real(self, data, stage, *a, **k)
        if stage.name.startswith("interval:"):
            s = r.stages[-1]
            path = stage.name[len("interval:"):]
            pinned = next((e.value for e in self._working_table().entries
                           if e.path == path), None)
            log.append({"value": pinned, "chi2": data_chi2(r.statistics),
                        "held": list(s.held), "released": list(s.released),
                        "collapsed": list(s.collapsed or []),
                        "codes": sorted({d.code for d in r.diagnostics})})
        return r

    return run_stage


def measure(arm: str):
    dataset, _, how = arm.partition("_")
    ref, result, data = _fit(dataset)
    path = TARGET[dataset]
    refits: list = []
    paths = refine_module._unsupported_phase_paths

    def no_collapse(*a, **k):
        return [] if k.get("at_answer") else paths(*a, **k)

    with patched(rx.Refinement, "run_stage", _refit_spy(refits)):
        if how == "no_hold":
            with patched(refine_module, "_hold_unsupported_phases",
                         lambda *a, **k: ([], {}, set())), \
                    patched(refine_module, "_unsupported_phase_paths", no_collapse):
                iv = ref.profile_interval(data, path)
        else:
            iv = ref.profile_interval(data, path)
    phases = [p.name for p in result.qpa.phases] if result.qpa else []
    rec = record(result, [path] + [f"phases.{i}.cell.a" for i in range(len(phases))])
    rec.update(
        target=path, phases=phases,
        fractions={q.name: (q.weight_fraction, q.weight_fraction_stderr)
                   for q in result.qpa.phases} if result.qpa else None,
        interval={"value": iv.value, "stderr": iv.stderr, "lower": iv.lower,
                  "upper": iv.upper, "lower_stop": iv.lower_stop,
                  "upper_stop": iv.upper_stop, "one_sided": iv.one_sided,
                  "cut": iv.delta_chi2_cut, "chi2_fit": iv.chi2_fit,
                  "chi2_lowest": iv.chi2_lowest, "fit_is_minimum": iv.fit_is_minimum,
                  "n_refits": iv.n_refits,
                  "points": [p.model_dump() for p in iv.points]},
        refits=refits)
    return result, rec


def main(arms):
    emit({"provenance": provenance()})
    OUT.mkdir(parents=True, exist_ok=True)
    for arm in arms:
        try:
            result, rec = measure(arm)
        except Exception as exc:          # a crash is a measured outcome here
            emit({"arm": arm, "error": f"{type(exc).__name__}: {exc}"[:400]})
            continue
        rec["arm"] = arm
        emit(rec)
        if arm.endswith("_shipped"):
            result.plot(path=str(OUT / f"c2_{arm.split('_')[0]}.png"))
            import matplotlib.pyplot as plt
            plt.close("all")


if __name__ == "__main__":
    main(sys.argv[1:] or ARMS)
