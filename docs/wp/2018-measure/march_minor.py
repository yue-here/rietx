"""C29: the March-Dollase floor, the tie window and the unseen-phase hold on a minor phase (WP-2018, task 3).

``PreferredOrientation.r`` has a pole guard at ``MARCH_R_MIN`` (1e-6) and no
ceiling since WP-2002 B9 (schemas/structure.py), a stored ``min`` of 0 is
repaired to it, ``tie_window`` derives a tied source's solver window from that
floor (params/vector.py), and the unseen-phase hold holds a structural path of
a phase the data cannot see, ``r`` among them (refine.py).  No vendored
pattern has a textured minor phase, so one is built the way
``tests/_synthetic_weak_lines.weak_second_phase`` builds its trace: Mo (the
host) plus α-MoO₃ drawn with r = ``R_TRUE`` along [010], each normalised to its
strongest line and summed at ``trace`` × the host's height, Poisson counts on
7700 background, the fixture's synchrotron instrument.  Fitted with Mo and
MoO₃ declared, MoO₃'s r free from 1.0, in arms named ``<trace>_<variant>``:

  trace         0 (the oxide absent), 0.006 (the fixture's trace) or 0.03
  shipped       as on main
  nosupport     ``phase_support_sigma = None``: no hold, no collapse
  tied, tied_nosupport
                MoO₃'s r tied to a variable, r = 0.5·vars.rv (rv free from 2),
                so ``tie_window`` bounds rv from r's floor: rv ≥ 2e-6
  pole          the positive arm (trace 0 only): r started at 2e-6, next to
                its floor, with the hold off, so the floor can be met

A probe record first: cos²α of MoO₃'s (0k0), k = 1-11, against the [010] axis
(``preferred_orientation.cos2_alpha``) less 1, and ``march_term`` of them at
r = 2e-6, 1e-5 and the floor, to show what the pole arm's fit evaluated.

Per arm: Rwp, MoO₃'s r (or rv) with esd and ``at_bound``, both scales, what
each stage held, released or collapsed, every code.

usage (repo root): python docs/wp/2018-measure/march_minor.py [arm ...]
"""
from __future__ import annotations

import os
import sys

import numpy as np
from common import emit, provenance, record

os.environ.setdefault("RIETX_TELEMETRY", "0")

import rietx as rx  # noqa: E402
from rietx.schemas.structure import PreferredOrientation  # noqa: E402
from tests._synthetic_weak_lines import (  # noqa: E402
    HOST_RANGE,
    MO_CIF,
    MOO3_CIF,
    _grid,
    _instrument,
    _structure,
)

R_TRUE = 0.6
TRACES = {"0": 0.0, "0.006": 0.006, "0.03": 0.03}
ARMS = tuple(f"{t}_{v}" for t in TRACES
             for v in ("shipped", "nosupport", "tied", "tied_nosupport")) + ("0_pole",)
R_PATH = "phases.1.preferred_orientation.r"
PATHS = (R_PATH, "vars.rv", "phases.0.scale", "phases.1.scale", "phases.1.cell.a")


def _oxide(r: float, vary: bool):
    phase = _structure(MOO3_CIF).phases[0]
    phase.preferred_orientation = PreferredOrientation(axis=(0, 1, 0))
    phase.preferred_orientation.r.value = r
    phase.preferred_orientation.r.vary = vary
    return phase


def pattern(trace: float, seed: int = 3) -> rx.PatternData:
    ins = _instrument()
    tt = _grid(*HOST_RANGE)
    host = np.asarray(rx.Refinement(_structure(MO_CIF), ins, history=False)
                      .predict(two_theta=tt))
    y = host / host.max()
    if trace:
        imp = np.asarray(rx.Refinement(rx.Structure(phases=[_oxide(R_TRUE, False)]),
                                       ins, history=False).predict(two_theta=tt))
        y = y + trace * imp / imp.max()
    obs = np.random.default_rng(seed).poisson(y * 1.3e6 + 7700.0).astype(float)
    return rx.PatternData(two_theta=list(tt), intensity=list(obs),
                          sigma=list(np.sqrt(np.maximum(obs, 1.0))))


def fit(arm: str, data):
    trace, variant = arm.split("_", 1)
    host = _structure(MO_CIF).phases[0]
    oxide = _oxide(2e-6 if variant == "pole" else 1.0, True)
    oxide.scale.value = 1e-6 if not TRACES[trace] else oxide.scale.value
    structure = rx.Structure(phases=[host, oxide])
    ins = _instrument()
    ref = rx.Refinement(structure, ins, history=False)
    r_glob = R_PATH
    if variant.startswith("tied"):
        ref.add_variable("rv", 2.0, vary=True)
        ref.tie(R_PATH, "vars.rv", scale=0.5)
        r_glob = "vars.rv"
    plan = rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        rx.Stage("cell", ["phases.*.cell.*"]),
        rx.Stage("texture", [r_glob]),
    ])
    if variant.endswith("nosupport") or variant == "pole":
        plan.phase_support_sigma = None
    return ref, ref.fit(data, plan=plan, telemetry=False)


def probe():
    from rietx.model import preferred_orientation as po

    cell = _oxide(1.0, False).cell
    gstar = np.diag([1 / cell.a.value ** 2, 1 / cell.b.value ** 2, 1 / cell.c.value ** 2])
    h = np.array([[0, k, 0] for k in range(1, 12)], dtype=np.float64)
    cos2 = np.asarray(po.cos2_alpha(h, np.array([0, 1, 0]), gstar))
    with np.errstate(invalid="ignore"):
        return {"cos2_minus_1": (cos2 - 1.0).tolist(),
                **{f"march_term_r={r:g}": np.asarray(po.march_term(cos2, r)).tolist()
                   for r in (1e-6, 2e-6, 1e-5)}}


def main(arms):
    emit({"provenance": provenance(), "fixture": "Mo + textured MoO3 trace",
          "r_true": R_TRUE, "probe": probe()})
    cache = {}
    for arm in arms:
        trace = arm.split("_", 1)[0]
        if trace not in cache:
            cache[trace] = pattern(TRACES[trace])
        try:
            ref, result = fit(arm, cache[trace])
        except Exception as exc:          # a crash is a measured outcome here
            emit({"arm": arm, "error": f"{type(exc).__name__}: {exc}"[:400]})
            continue
        rec = record(result, PATHS)
        rec["arm"] = arm
        rec["r_committed"] = ref.structure.phases[1].preferred_orientation.r.value
        rec["n_iterations"] = [s.n_iterations for s in result.stages]
        emit(rec)


if __name__ == "__main__":
    main(sys.argv[1:] or ARMS)
