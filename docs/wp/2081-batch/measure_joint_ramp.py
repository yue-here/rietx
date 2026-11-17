"""WP-2081: one joint fit of the real ramp against the one-pattern-at-a-time chain.

Run from the repository root:

    .venv/bin/python docs/wp/2081-batch/measure_joint_ramp.py ARM [--frames 0,6,16]

The data, model and truth are ``measure_real_ramp.py``'s: 17 CuCr2O4 + CuO
patterns from APS 11-BM, ``Fddd`` on every frame, b = c above about 130 K, and
|b - c| = 0.00746 Å at 10 K in the paper.  "Closes" means |b - c| under 1e-4 Å.

Every arm is one ``MultiHistogramRefinement`` over the frames named, started
from the ``lab_sample_refine`` chain's answer on each frame.  That chain is
rerun once and cached (``--chain PATH``), because ``real_ramp.json`` keeps
the cell and setup terms only.

- ``A``: the ``.prm`` profile held; one zero shift common to every pattern.
  Per pattern: cell, scale, background, the four sample width terms.
- ``B``: zero and U, V, W, X, Y common to every pattern; per pattern as A.
- ``B2``: B from a start whose common profile terms are moved by 30 %.
- ``C``: B with no sample width term free, each held at the chain's value
  for its frame (so the chain's temperature-dependent width stays built in).
- ``C0``: C with every sample width set to zero, so the one common profile is
  the whole width of every frame.

Every plan has two stages: scale, background and the common setup terms, then
cell and widths.  In B the package holds U, X and Y from stage 2 on, because
each has a per-pattern specimen twin of the same angular shape
(``_hold_width_twins_multi``, ``StageResult.width_twins_held``), so they keep
the values stage 1 fitted with the chain's widths held.  A held term is absent
from ``result.parameters``; its value is read off ``ref.fitted_instruments``.

Per-pattern Biso is held at the chain's value of that frame (declared
per-pattern so the starts may differ).  What the chain's ``lab_sample_refine``
also freed and these arms do not: Biso.

The solver's last outcome is captured by wrapping ``run_multi_least_squares``
for this process alone, because ``RefinementResult`` carries no correlation
matrix (``MultiHistogramRefinement.fit`` keeps ``outcome.correlation`` to
itself).  No Rwp is used as evidence: the arms free different parameters.

Writes ``joint_ramp.json`` beside this file, one key per arm and frame set.
``--report`` reprints it without fitting.  ``--plot H,...`` saves an
obs/calc/difference PNG per histogram into ``--plot-dir``.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("RIETX_TELEMETRY", "0")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import measure_real_ramp as mrr  # noqa: E402
import numpy as np  # noqa: E402

import rietx as rx  # noqa: E402
import rietx.multi as rxmulti  # noqa: E402
from rietx.params.multi import SharingMap  # noqa: E402

OUT = HERE / "joint_ramp.json"
PROFILE = ("u", "v", "w", "x", "y")
WIDTHS = ["phases.*.lor_size", "phases.*.lor_strain",
          "phases.*.gauss_size", "phases.*.gauss_strain"]
CLOSED = 1e-4   # Å, the WP's "closes"


# --------------------------------------------------------------------------
# the chain's answer, every frame's models
def chain_models(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    paths = sorted(mrr.DATA.glob("OH_*.fxye"))
    patterns = [rx.read_pattern(p) for p in paths]
    temps = [mrr.temperature(p) for p in paths]
    structure, instrument = mrr.models()
    series = rx.SequentialRefinement(structure, instrument)
    t0 = time.time()
    result = series.fit(patterns, x=temps, x_label="T (K)", plan="lab_sample_refine")
    frames = [{"T": e.x, "rung": e.rung, "status": e.status,
               "structure": series.fitted_structures[k].model_dump(mode="json"),
               "instrument": series.fitted_instruments[k].model_dump(mode="json"),
               "params": {p.path: [p.value, p.stderr]
                          for p in series.results_[k].parameters}}
              for k, e in enumerate(result.entries)]
    record = {"seconds": round(time.time() - t0, 1), "frames": frames,
              "codes": [d.code for d in result.diagnostics]}
    path.write_text(json.dumps(record), encoding="utf-8")
    return record


# --------------------------------------------------------------------------
def sharing(arm: str) -> SharingMap:
    shared = ["instrument.zero_shift"]
    if arm != "A":
        shared += [f"instrument.profile.{t}" for t in PROFILE]
    return SharingMap(
        per_histogram=["phases.*.cell.*", *WIDTHS, "phases.*.microstrain.*",
                       "phases.*.atoms.*.biso", "phases.*.atoms.*.adp.*"],
        shared=shared)


def plan(arm: str) -> rx.RefinementPlan:
    setup = ["instrument.zero_shift"]
    if arm != "A":
        setup += [f"instrument.profile.{t}" for t in PROFILE]
    last = ["phases.*.cell.*"] + ([] if arm.startswith("C") else WIDTHS)
    return rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg_setup", ["phases.*.scale", "instrument.background.*", *setup]),
        rx.Stage("cell_width", last),
    ])


def starts(chain: dict, frames: list[int], arm: str):
    structures, instruments = [], []
    for k in frames:
        f = chain["frames"][k]
        s = rx.Structure.model_validate(f["structure"])
        ins = rx.Instrument.model_validate(f["instrument"])
        if arm == "B2":
            for t in PROFILE:
                p = getattr(ins.profile, t)
                p.value = p.value * 1.3 if p.value != 0.0 else 1e-3
        if arm == "C0":       # no sample width at all: the common profile is the width
            for phase in s.phases:
                for w in ("lor_size", "lor_strain", "gauss_size", "gauss_strain"):
                    getattr(phase, w).value = 0.0
        structures.append(s)
        instruments.append(ins)
    return structures, instruments


class Capture:
    """Keeps the joint solver's last outcome; counts evaluation events."""

    def __init__(self):
        self.outcomes, self.kinds = [], {}
        self._orig = rxmulti.run_multi_least_squares

    def __enter__(self):
        def wrapped(*a, **kw):
            out = self._orig(*a, **kw)
            self.outcomes.append(out)
            return out
        rxmulti.run_multi_least_squares = wrapped
        return self

    def __exit__(self, *exc):
        rxmulti.run_multi_least_squares = self._orig

    def event(self, ev):
        kind = getattr(ev, "kind", None) or (ev.get("kind") if isinstance(ev, dict) else None)
        self.kinds[kind] = self.kinds.get(kind, 0) + 1


def scoped(h: int, path: str) -> str:
    return f"hist.{h}.{path}"


def run(arm: str, frames: list[int], chain: dict, plot: list[int], plot_dir: Path) -> dict:
    paths = sorted(mrr.DATA.glob("OH_*.fxye"))
    data = [rx.read_pattern(paths[k]) for k in frames]
    structures, instruments = starts(chain, frames, arm)
    t0 = time.time()
    ref = rx.MultiHistogramRefinement(structures, instruments, sharing=sharing(arm))
    with Capture() as cap:
        result = ref.fit(data, plan=plan(arm), events=cap.event)
    seconds = round(time.time() - t0, 1)
    vals = {p.path: (p.value, p.stderr) for p in result.parameters}
    last = cap.outcomes[-1]
    free = list(ref.mtable.free_paths)

    def get(h, path):
        for key in (scoped(h, path), path):
            if key in vals:
                return list(vals[key])
        return [None, None]

    rows = []
    for h, k in enumerate(frames):
        row = {"T": chain["frames"][k]["T"], "frame": k}
        for n in "abc":
            row[n] = get(h, f"phases.0.cell.{n}")
        for w in ("lor_size", "lor_strain", "gauss_size", "gauss_strain"):
            row[w] = get(h, f"phases.0.{w}")
            row["CuO_" + w] = get(h, f"phases.1.{w}")
        row["scale"] = get(h, "phases.0.scale")
        # what the fitted model holds, free or not (a held row is absent from
        # result.parameters, so its value is read off the model itself)
        ins = ref.fitted_instruments[h]
        row["profile_model"] = {t: getattr(ins.profile, t).value for t in PROFILE}
        row["zero_model"] = ins.zero_shift.value
        hr = result.histograms[h]
        row["gof"] = hr.statistics.gof
        row["rwp"] = hr.statistics.rwp
        row["codes"] = [d.code for d in hr.diagnostics]
        rows.append(row)
    common = {"zero_shift": get(0, "instrument.zero_shift")}
    for t in PROFILE:
        common[t] = get(0, f"instrument.profile.{t}")
        if common[t][0] is None:     # held at the end: the model's value, no esd
            common[t] = [rows[0]["profile_model"][t], None, "held at the answer"]
    # the largest |ρ| between a common setup column and any per-pattern width column
    corr = []
    if last.correlation is not None and len(free) == last.correlation.shape[0]:
        c = np.asarray(last.correlation)
        setup_idx = [i for i, p in enumerate(free) if p.startswith("instrument.")]
        width_idx = [i for i, p in enumerate(free)
                     if any(p.endswith(w) for w in ("_size", "_strain"))]
        for i in setup_idx:
            for j in width_idx:
                corr.append((abs(float(c[i, j])), free[i], free[j], float(c[i, j])))
        for i in setup_idx:          # common against common
            for j in setup_idx:
                if j > i:
                    corr.append((abs(float(c[i, j])), free[i], free[j], float(c[i, j])))
        corr.sort(reverse=True)
    codes: dict[str, int] = {}
    for d in result.diagnostics:
        codes[d.code] = codes.get(d.code, 0) + 1
    for name in plot:
        draw(result, frames, frames.index(name), plot_dir, arm, rows)
    return {
        "arm": arm, "frames": frames, "seconds": seconds, "status": result.status,
        "stages": [{"name": s.name, "status": s.status, "n_iterations": s.n_iterations,
                    "termination": s.termination,
                    "width_twins_held": s.width_twins_held, "held": s.held,
                    "fixed": s.fixed, "blocked_by_hold": s.blocked_by_hold,
                    "unknown_paths": s.unknown_paths} for s in result.stages],
        "n_eval_events": cap.kinds.get("eval", 0), "event_kinds": cap.kinds,
        "n_free": len(free), "chi2_cost_final": float(last.cost_final),
        "gof": result.statistics.gof, "rwp": result.statistics.rwp,
        "common": common, "rows": rows, "codes": codes,
        "diagnostics": [{"code": d.code, "message": d.message[:300],
                         "where": list(getattr(d, "where", []) or [])[:6]}
                        for d in result.diagnostics],
        "at_bound": [p.path for p in result.parameters if p.at_bound],
        "top_setup_corr": [list(x[1:]) for x in corr[:15]],
    }


def draw(result, frames, h, plot_dir: Path, arm: str, rows) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    hr = result.histograms[h]
    tt, yo, yc = (np.asarray(hr.two_theta), np.asarray(hr.y_obs), np.asarray(hr.y_calc))
    row = rows[h]
    a, b, c = row["a"][0], row["b"][0], row["c"][0]
    lam = 0.413263

    def tth(hkl):
        d = 1.0 / np.sqrt((hkl[0] / a) ** 2 + (hkl[1] / b) ** 2 + (hkl[2] / c) ** 2)
        return 2 * np.degrees(np.arcsin(lam / (2 * d)))

    # (0 8 0)/(0 0 8) separates b from c alone; (2 6 2)/(2 2 6) as a second
    pairs = [((0, 8, 0), (0, 0, 8)), ((2, 6, 2), (2, 2, 6))]
    fig, axes = plt.subplots(3, 1, figsize=(10, 10))
    ax = axes[0]
    ax.plot(tt, yo, ".", ms=1.5, color="0.2", label="observed")
    ax.plot(tt, yc, "-", lw=0.7, color="C3", label="calculated")
    off = yo.min() - 0.1 * (yo.max() - yo.min())
    ax.plot(tt, yo - yc + off, "-", lw=0.5, color="C0", label="obs - calc")
    ax.set_title(f"arm {arm}, {row['T']:.1f} K: b - c = {b - c:+.5f} Å")
    ax.set_xlabel("2θ (°)")
    ax.legend(frameon=False, fontsize=8)
    for ax, (p, q) in zip(axes[1:], pairs, strict=True):
        lo, hi = sorted((tth(p), tth(q)))
        m = (tt > lo - 0.04) & (tt < hi + 0.04)
        ax.plot(tt[m], yo[m], "o", ms=3, color="0.2")
        ax.plot(tt[m], yc[m], "-", color="C3")
        ax.plot(tt[m], yo[m] - yc[m] + yo[m].min() - 0.15 * np.ptp(yo[m]), "-", color="C0")
        for pos, lab in ((tth(p), p), (tth(q), q)):
            ax.axvline(pos, color="0.6", lw=0.5)
            ax.text(pos, yo[m].max(), "".join(map(str, lab)), fontsize=8, ha="center")
        ax.set_xlabel("2θ (°)")
    fig.tight_layout()
    out = plot_dir / f"joint_{arm}_{row['T']:.0f}K.png"
    fig.savefig(out, dpi=110)
    plt.close(fig)
    print("plot", out)


# --------------------------------------------------------------------------
def summary(rec: dict) -> dict:
    rows = sorted(rec["rows"], key=lambda r: r["T"])
    gap = [abs(r["b"][0] - r["c"][0]) for r in rows]
    closes = None
    for i in range(1, len(rows)):
        if gap[i - 1] >= CLOSED and gap[i] < CLOSED:
            closes = (rows[i - 1]["T"], rows[i]["T"])
    if gap[0] < CLOSED:
        closes = "closed at the coldest frame"
    elif all(g >= CLOSED for g in gap):
        closes = "never"
    first, hot = rows[0], rows[-1]
    near = {"a": first["a"][0], "b": first["c"][0], "c": first["b"][0]}
    ppm = {n: 1e6 * (near[n] - mrr.PAPER[n]) / mrr.PAPER[n] for n in "abc"}
    return {
        "closes_between": closes,
        "cold_T": first["T"], "cold_gap": gap[0],
        "cold_gap_esd": float(np.hypot(first["b"][1], first["c"][1])),
        "hot_T": hot["T"], "hot_b_minus_c": hot["b"][0] - hot["c"][0],
        "hot_esd": float(np.hypot(hot["b"][1], hot["c"][1])),
        "zero": rec["common"]["zero_shift"],
        "esd_a_ppm": 1e6 * first["a"][1] / mrr.PAPER["a"],
        "ppm": ppm, "mean_ppm": float(np.mean(list(ppm.values()))),
    }


def chain_summary(route: dict, frames: list[int]) -> dict:
    rows = [route["rows"][k] for k in frames]
    fake = {"rows": rows, "common": {"zero_shift": rows[0]["setup"]["instrument.zero_shift"]}}
    return summary(fake)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("arm", nargs="?", choices=["A", "B", "B2", "C", "C0"])
    ap.add_argument("--frames", default=",".join(map(str, range(17))))
    ap.add_argument("--chain", default=str(Path(tempfile.gettempdir())
                                           / "rietx_2081_chain_models.json"))
    ap.add_argument("--plot", default="")
    ap.add_argument("--plot-dir", default=str(HERE))
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    record = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"runs": {}}
    if not args.report:
        frames = [int(x) for x in args.frames.split(",")]
        chain = chain_models(Path(args.chain))
        plot = [int(x) for x in args.plot.split(",") if x]
        rec = run(args.arm, frames, chain, plot, Path(args.plot_dir))
        rec["summary"] = summary(rec)
        record["platform"] = (f"{platform.system()} {platform.machine()}, Python "
                              f"{platform.python_version()}, rietx {rx.__version__}, "
                              "compiled tier "
                              + ("on" if rx.capabilities().compiled_kernels_unavailable
                                 is None else "off"))
        record["runs"][f"{args.arm}:{args.frames}"] = rec
        OUT.write_text(json.dumps(record, indent=1), encoding="utf-8")
    real = json.loads((HERE / "real_ramp.json").read_text(encoding="utf-8"))
    routes = {r["arm"]: r for r in real["routes"]}
    for key, rec in record["runs"].items():
        s = rec["summary"]
        print(f"--- {key}: {rec['status']}, {rec['seconds']} s, {rec['n_eval_events']} evals, "
              f"free {rec['n_free']}")
        print(json.dumps(s))
        print("common", json.dumps(rec["common"]))
        print("codes", rec["codes"])
        for name in ("default", "sample"):
            print(f"  chain {name} on these frames:",
                  json.dumps(chain_summary(routes[name], rec["frames"])))


if __name__ == "__main__":
    main()
