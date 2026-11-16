"""C1 on ``tests/test_qpa_multimodal.py``'s two-basin trace (WP-2018, task 3).

``Refinement.profile_fraction`` pins CaF₂'s ``lor_strain`` on its default
12-point FWHM grid and refits each point through ``run_stage`` under the fit's
own plan settings, so every refit meets the stage-start support hold and the
collapse restore (WP-1320's clash, measured then under the pre-WP-1523 test).
Two arms, same fit, same grid:

  shipped     the probe as main runs it (``phase_support_sigma`` = the plan's, 3)
  no_support  the probe's refits under ``phase_support_sigma = None`` (hold,
              release, collapse and default cell window off); the fit itself
              is the shipped one

Per point: W, data χ², Rwp, Δχ² against the arm's best, admissible, CaF₂'s
scale and a with esds, and what the refit held or collapsed.  Then the
probe's own range, excess and diagnostics per arm.  The loop below is
``strategy.fraction_profile.profile_fraction``'s, with the refit's result kept.

usage (repo root): python docs/wp/2018-measure/fraction_profile.py [arm ...]
"""
from __future__ import annotations

import sys

import numpy as np
from common import OUT, emit, provenance, row, stages

from rietx.strategy.fraction_profile import (
    data_chi2,
    default_fwhm_grid,
    head_restored,
    width_value,
)
from rietx.strategy.staged import Stage
from tests.test_qpa_multimodal import AXIS, HUMP, TRACE_SCALE, _fitted

ARMS = ("shipped", "no_support")
PATHS = ("phases.1.scale", "phases.1.cell.a", AXIS)


def points(ref, data, settings):
    result = ref.result_
    tt = np.asarray(result.two_theta, dtype=np.float64)
    lo, hi = float(tt.min()), float(tt.max())
    theta_mid = 0.25 * (lo + hi)
    out = []
    with head_restored(ref):
        trial = ref._trial()
        trial.set_vary([AXIS], False)
        for f in default_fwhm_grid(hi - lo):
            value = width_value("lor_strain", f, theta_mid)
            trial.set_values({AXIS: value})
            r = trial.run_stage(data, Stage(f"profile:{AXIS}", []),
                                telemetry=False, **settings)
            w = r.qpa.phases[1].weight_fraction if r.qpa is not None else None
            out.append({"fwhm": f, "value": value, "W": w,
                        "chi2": data_chi2(r.statistics), "rwp": r.statistics.rwp,
                        "params": {p: row(r, p) for p in PATHS},
                        "stage": stages(r)[-1],
                        "codes": sorted({d.code for d in r.diagnostics})})
    return out


def main(arms):
    emit({"provenance": provenance(), "fixture": "test_qpa_multimodal (trace, hump)"})
    ref, result, data = _fitted(TRACE_SCALE, HUMP)
    fit_row = result.qpa.phases[1]
    emit({"fit": {"rwp": result.statistics.rwp, "chi2": data_chi2(result.statistics),
                  "W": fit_row.weight_fraction, "W_esd": fit_row.weight_fraction_stderr,
                  "params": {p: row(result, p) for p in PATHS},
                  "settings": dict(ref._plan_settings),
                  "codes": sorted({d.code for d in result.diagnostics})}})
    shipped = dict(ref._plan_settings)
    OUT.mkdir(parents=True, exist_ok=True)
    for arm in arms:
        settings = dict(shipped)
        if arm == "no_support":
            settings["phase_support_sigma"] = None
        pts = points(ref, data, settings)
        # the probe itself, under the same settings: _trial copies them
        ref._plan_settings = settings
        try:
            prof = ref.profile_fraction(data, "CaF2")
        finally:
            ref._plan_settings = shipped
        best = min([data_chi2(result.statistics), *(p["chi2"] for p in pts)])
        for p in pts:
            p["dchi2"] = p["chi2"] - best
        emit({"arm": arm, "points": pts,
              "profile": {"range_low": prof.range_low, "range_high": prof.range_high,
                          "excess": prof.excess, "cut": prof.delta_chi2_cut,
                          "fit_admissible": prof.fit_admissible,
                          "admissible": [p.admissible for p in prof.points],
                          "W": [p.weight_fraction for p in prof.points],
                          "chi2": [p.chi2 for p in prof.points],
                          "codes": [d.code for d in prof.diagnostics]}})
        _plot(prof, arm)


def _plot(prof, arm):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(5, 3.6))
    xs = [p.fwhm for p in prof.points if p.chi2 is not None]
    ys = [p.delta_chi2 for p in prof.points if p.chi2 is not None]
    ws = [p.weight_fraction for p in prof.points if p.chi2 is not None]
    ax.semilogy([max(x, 5e-3) for x in xs], [max(y, 1e-2) for y in ys], "o-")
    ax.axhline(prof.delta_chi2_cut, ls="--", c="k", lw=0.8)
    for x, y, w in zip(xs, ys, ws, strict=True):
        ax.annotate(f"{100 * w:.2g}%", (max(x, 5e-3), max(y, 1e-2)), fontsize=6)
    ax.set_xscale("log")
    ax.set_xlabel("CaF2 FWHM pinned (deg; 0 drawn at 5e-3)")
    ax.set_ylabel("Δχ² to best (floored at 1e-2)")
    ax.set_title(f"C1 width profile, {arm}")
    fig.tight_layout()
    fig.savefig(OUT / f"c1_fraction_profile_{arm}.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main(sys.argv[1:] or ARMS)
