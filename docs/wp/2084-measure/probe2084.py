"""WP-2084 probe: what separates the two SRM 660c width minima.

usage: probe2084.py ARM OUTDIR TREE   (TREE: the worktree root, for ``tests.``)
One fit of ``tests.test_window_domain._protocol("lab6")`` through the closing
stage, compiled tier on, about a second.  The numbers it produced are in the WP
file's Findings (2026-11-16).
ARM is  floor=<f>[,start=<armname>][,nudge=<k>][,nodes=<per_fwhm>][,cwt=<tol>]
  floor  AXIAL_SIZING_FLOOR for the whole fit
  start  warm start from <OUTDIR>/<tag>.state.json, <tag> an earlier arm's output tag (fitted structure+instrument)
  nudge  multiply the profile.w start by (1 + k*1e-14)
  nodes  fcj.CLOSING_NODES_PER_FWHM
  cwt    plan.closing_window_tol
  ftol   plan.intermediate_ftol (none = every stage at the solver's own)
  biso   every atom's Biso start
  onface lm._ON_FACE (rows the start violates by less than this are kept)
  cone   off: no Γ_G² >= 1e-8 rows in any stage (the clamp in the model stays)
Writes <OUTDIR>/<tag>.json (numbers) and <tag>.state.json (fitted state).
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
TREE = Path(sys.argv[3]) if len(sys.argv) > 3 else None
if TREE is not None:
    sys.path.insert(0, str(TREE))           # for `tests.`

import rietx as rx  # noqa: E402
import rietx.model.forward as fwd  # noqa: E402
import rietx.model.profiles.fcj as fcj  # noqa: E402
from rietx.model import compiled  # noqa: E402

R = sys.modules["rietx.refine"]


def parse(arm: str) -> dict:
    out = {}
    for kv in arm.split(","):
        k, v = kv.split("=", 1)
        out[k] = v
    return out


def tag_of(arm: str) -> str:
    return arm.replace("=", "").replace(",", "_").replace(".", "p").replace("-", "m")


def main():
    arm, outdir = sys.argv[1], Path(sys.argv[2])
    outdir.mkdir(parents=True, exist_ok=True)
    a = parse(arm)
    tag = tag_of(arm)
    from tests.test_window_domain import _protocol
    data, st, ins, plan, kw = _protocol("lab6")
    if "start" in a:
        src = json.loads((outdir / f"{a['start']}.state.json").read_text())
        st = rx.Structure.model_validate(src["structure"])
        ins = rx.Instrument.model_validate(src["instrument"])
    if "nudge" in a:
        k = float(a["nudge"])
        ins.profile.w.value = ins.profile.w.value * (1.0 + k * 1e-14)
    if "ftol" in a:
        plan.intermediate_ftol = None if a["ftol"] == "none" else float(a["ftol"])
    if "biso" in a:
        for phase in st.phases:
            for atom in phase.atoms:
                atom.biso.value = float(a["biso"])
    if "cwt" in a:
        plan.closing_window_tol = float(a["cwt"])
    fwd.AXIAL_SIZING_FLOOR = float(a["floor"])
    if "onface" in a:
        import rietx.optimize.lm as LM
        LM._ON_FACE = float(a["onface"])
    if "nodes" in a:
        fcj.CLOSING_NODES_PER_FWHM = float(a["nodes"])
    assert fwd.AXIAL_SIZING_FLOOR == float(a["floor"])

    compiles = []
    orig = R.compile_model

    def rec(*args, **kwargs):
        m = orig(*args, **kwargs)
        try:
            cp = m.phases[0]
            hkl = getattr(cp.reflections, "hkl", None)
            compiles.append({
                "window_area_tol": kwargs.get("window_area_tol"),
                "axial_free": bool(kwargs.get("moving_paths") and
                                   "instrument.geometry.axial_sl" in kwargs["moving_paths"]),
                "sl_start": float(args[1].geometry.axial_sl.value),
                "hkl": None if hkl is None else np.asarray(hkl).tolist(),
                "fcj_n": np.asarray(cp.fcj_n).tolist(),
                "win_len": (np.asarray(cp.win)[..., 1] - np.asarray(cp.win)[..., 0]).tolist(),
            })
        except Exception as e:  # record, never break the fit
            compiles.append({"error": repr(e)})
        return m

    R.compile_model = rec

    import rietx.optimize.least_squares as LS
    cone = []
    orig_g = LS.gaussian_width_inequalities

    def rec_g(model, table, x0):
        out_ = orig_g(model, table, x0)
        try:
            # every candidate row, kept or not, by its slack at x0: re-run with
            # the drop disabled is not possible, so rebuild the angles here
            values = table.decode(x0)
            lams = model.line_lambdas(values)
            cp = model.phases[0]
            cell = tuple(values[f"phases.0.cell.{k}"] for k in ("a", "b", "c", "alpha", "beta", "gamma"))
            _d, tt_lines = model._cell_block(cp, cell, lams)
            u_, v_, w_ = (values[f"instrument.profile.{k}"] for k in "uvw")
            rows_ = []
            for il, tt_ in enumerate(tt_lines):
                tt_ = np.asarray(tt_, dtype=float)
                win = cp.win[il]
                used = (win[:, 1] > win[:, 0]) & np.isfinite(tt_)
                for i in np.flatnonzero(used):
                    t = np.tan(np.radians(0.5 * tt_[i]))
                    rows_.append((il, round(float(tt_[i]), 4), u_ * t * t + v_ * t + w_))
            cone.append({"n_blocks": len(out_),
                         "n_kept": int(sum(b.T.shape[0] for b in out_)),
                         "applied": a.get("cone") != "off",
                         "free_uvw": [p for p in ("instrument.profile.u", "instrument.profile.v", "instrument.profile.w") if p in table.free_paths],
                         "rows_at_start": sorted(rows_, key=lambda r: r[2])[:4]})
        except Exception as e:
            cone.append({"error": repr(e), "n_kept": int(sum(b.T.shape[0] for b in out_))})
        return out_

    LS.gaussian_width_inequalities = rec_g
    if a.get("cone") == "off":
        LS.gaussian_width_inequalities = lambda model, table, x0: (rec_g(model, table, x0), [])[1]
    was = compiled.set_enabled(True)
    t0 = time.time()
    ref = rx.Refinement(st, ins, history=True)
    res = ref.fit(data, plan=plan, **kw)
    wall = time.time() - t0
    tier = compiled.enabled()
    compiled.set_enabled(was)

    rows = {p.path: (p.value, p.stderr_uncorrected) for p in res.parameters}
    fi = ref.fitted_instrument
    fs = ref.fitted_structure
    u, v, w = fi.profile.u.value, fi.profile.v.value, fi.profile.w.value
    # Γ_G² at every LaB6 reflection in range, both lines
    a_cell = fs.phases[0].cell.a.value
    tt = np.asarray(data.two_theta, dtype=float)
    lo, hi = float(tt.min()), float(tt.max())
    lams = [ln.wavelength.value if hasattr(ln.wavelength, "value") else ln.wavelength
            for ln in fi.source.lines]
    Ns = sorted({h * h + k * k + m * m for h in range(0, 12) for k in range(0, 12)
                 for m in range(0, 12)} - {0})
    refl = []
    for N in Ns:
        for il, lam in enumerate(lams):
            s = lam * math.sqrt(N) / (2 * a_cell)
            if s >= 1:
                continue
            t2 = 2 * math.degrees(math.asin(s))
            if lo <= t2 <= hi:
                t = math.tan(math.radians(t2 / 2))
                refl.append({"N": N, "line": il, "tt": t2,
                             "gg2": u * t * t + v * t + w})
    # where Γ_G² first goes negative (u t² + v t + w = 0, the smallest positive root)
    root = None
    disc = v * v - 4 * u * w
    if u != 0 and disc >= 0:
        ts = [(-v + sg * math.sqrt(disc)) / (2 * u) for sg in (1, -1)]
        ts = [t for t in ts if t > 0]
        if ts:
            root = 2 * math.degrees(math.atan(min(ts)))
    stages = []
    for st_ in res.stages:
        stages.append({"name": st_.name, "status": st_.status, "n_iter": st_.n_iterations,
                       "cost_initial": st_.cost_initial, "cost_final": st_.cost_final,
                       "ftol": st_.ftol, "window_area_tol": st_.window_area_tol,
                       "n_constraint_truncations": st_.n_constraint_truncations,
                       "rwp": st_.rwp, "termination": st_.termination})
    trace = []
    try:
        tree = ref.history
        for node in tree.lineage(tree.head):
            ins_ = node.state.instrument
            trace.append({
                "label": node.label, "cost_final": node.metrics.cost_final,
                "u": ins_.profile.u.value, "v": ins_.profile.v.value,
                "w": ins_.profile.w.value, "x": ins_.profile.x.value,
                "y": ins_.profile.y.value, "sl": ins_.geometry.axial_sl.value,
                "a": node.state.structure.phases[0].cell.a.value,
                "disp": ins_.geometry.sample_displacement.value,
            })
    except Exception as e:
        trace.append({"error": repr(e)})
    diags = [{"code": d.code, "message": d.message} for d in res.diagnostics
             if d.code in ("CONSTRAINT_ACTIVE", "RESOLUTION_NOT_POSITIVE",
                           "RESOLUTION_UNCONSTRAINED")]
    s = res.statistics
    out = {
        "arm": arm, "tag": tag, "wall_s": wall, "rietx": rx.__file__,
        "floor": fwd.AXIAL_SIZING_FLOOR, "closing_nodes_per_fwhm": fcj.CLOSING_NODES_PER_FWHM,
        "status": res.status, "rwp": s.rwp, "gof": s.gof, "chi2_red": s.gof ** 2,
        "n_points": s.n_points, "n_free": s.n_free_parameters,
        "rows": rows, "uvw": [u, v, w], "gg2_root_tt": root, "range": [lo, hi],
        "reflections": refl, "stages": stages, "trace": trace, "diagnostics": diags,
        "compiled_tier": tier, "compiles": compiles, "cone": cone,
    }
    (outdir / f"{tag}.json").write_text(json.dumps(out, indent=1))
    (outdir / f"{tag}.state.json").write_text(json.dumps({
        "structure": fs.model_dump(mode="json"), "instrument": fi.model_dump(mode="json")}))
    print(f"{tag} status={res.status} chi2_red={s.gof ** 2:.6f} rwp={s.rwp:.6f} "
          f"u={u:.6g} v={v:.6g} w={w:.6g} sl={fi.geometry.axial_sl.value:.6g} "
          f"a={a_cell:.8f} root={root} wall={wall:.0f}s")


if __name__ == "__main__":
    main()
