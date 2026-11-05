"""WP-2081: the default against a fixed instrument on one real ramp.

Run from the repository root:

    .venv/bin/python docs/wp/2081-batch/measure_real_ramp.py

The series is ``tests/data/seqrefine_cucr2o4/``: 17 CuCr2O4 + CuO patterns from
APS 11-BM, 6.8 to 288.7 K, development data (WP-2003's family B). The instrument
is the file's own 11-BM ``.prm``. The model is ``Fddd`` throughout, which is
what ``tests/data/README.md`` says should fit the whole ramp.

Three routes over the same frames:

- ``default``: ``plan="mccusker_default"``, as ``refine_sequential`` runs it.
- ``cautious``: scale, background and cell only, with the ``.prm``'s profile and
  zero fixed because no plan frees them.
- ``sample``: ``plan="lab_sample_refine"``.
- ``cautious_cold_profile`` and ``cautious_hot_profile``: the cautious plan with
  the zero shift and profile taken from the default chain's fit of the coldest
  and the hottest frame. This is the expert's order, step 2 before step 4.

What is independent of rietx (``tests/data/README.md``, Suchomel et al. 2012):
the ``Fddd`` cell at 10 K, and b = c in truth above about 130 K. No Rwp is used
as evidence here.

Writes ``real_ramp.json`` beside this file. About fifteen minutes; ``--report``
reprints the numbers from that file without fitting, ``--step-two`` reruns only
the last two routes, and ``--cold-check`` refits a few frames from the CIF.
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

import numpy as np  # noqa: E402

import rietx as rx  # noqa: E402
from rietx.schemas.instrument import BackgroundChebyshev  # noqa: E402

DATA = ROOT / "tests" / "data" / "seqrefine_cucr2o4"
#: Table I of Suchomel et al. (2012), 10 K, in the axis order of the paper.
PAPER = {"a": 7.71271, "b": 8.53611, "c": 8.54357}
SETUP = ("instrument.zero_shift", "instrument.profile.u", "instrument.profile.v",
         "instrument.profile.w", "instrument.profile.x", "instrument.profile.y")
CAUTIOUS = rx.RefinementPlan(stages=[
    rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
    rx.Stage("cell", ["phases.*.cell.*"]),
])


def temperature(path: Path) -> float:
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[:30]:
        if "Temp (K)" in line:
            return float(line.split("=")[-1].split()[0])
    raise ValueError(f"no temperature in {path}")


def models():
    main = rx.Structure.from_cif(DATA / "CuCr2O4.cif")
    minor = rx.Structure.from_cif(DATA / "CuO.cif")
    structure = main.model_copy(deep=True)
    structure.phases = list(main.phases) + list(minor.phases)
    structure.phases[0].name, structure.phases[1].name = "CuCr2O4", "CuO"
    for phase in structure.phases:
        for atom in phase.atoms:
            if atom.biso.value <= 0.0:  # the README's reset of O's stated Biso
                atom.biso.value = 0.3
    structure.phases[0].scale.value = 1.0
    structure.phases[1].scale.value = 0.05
    instrument = rx.read_gsas_prm(DATA / "OH_00.prm")
    instrument.background = BackgroundChebyshev.with_terms(8)
    return structure, instrument


def run(arm: str, plan, patterns, temps, setup: dict | None = None) -> dict:
    structure, instrument = models()
    for path, value in (setup or {}).items():
        target = (instrument if path == SETUP[0].split(".")[1] else instrument.profile)
        getattr(target, path).value = value
    series = rx.SequentialRefinement(structure, instrument)
    t0 = time.time()
    result = series.fit(patterns, x=temps, x_label="T (K)", plan=plan)
    rows = []
    for k, entry in enumerate(result.entries):
        fit = series.results_[k]
        values = {p.path: (p.value, p.stderr) for p in fit.parameters}
        rows.append({
            "T": entry.x, "rung": entry.rung, "status": entry.status,
            "gof": entry.statistics.gof if entry.statistics else None,
            "a": values.get("phases.0.cell.a", (None, None)),
            "b": values.get("phases.0.cell.b", (None, None)),
            "c": values.get("phases.0.cell.c", (None, None)),
            "setup": {p: values.get(p, (None, None)) for p in SETUP},
        })
    return {"arm": arm, "seconds": round(time.time() - t0, 1), "rows": rows,
            "codes": [d.code for d in result.diagnostics]}


def report(out: dict) -> None:
    first = out["rows"][0]
    # the tutorial's CIF has b > c and the paper c > b, so the model's b is the
    # paper's c: an axis relabelling, compared here in the paper's order
    near = {"a": first["a"][0], "b": first["c"][0], "c": first["b"][0]}
    ppm = {n: 1e6 * (near[n] - PAPER[n]) / PAPER[n] for n in "abc"}
    print(f"{out['arm']}: {out['seconds']} s, rungs "
          f"{sorted({r['rung'] for r in out['rows']})}, status "
          f"{sorted({r['status'] for r in out['rows']})}")
    print(f"  coldest frame ({first['T']:.1f} K) against the paper's 10 K cell, ppm: "
          + " ".join(f"{n} {v:+.0f}" for n, v in ppm.items())
          + f"; esd a {1e6 * first['a'][1] / PAPER['a']:.1f}, distortion c-b "
          f"{near['c'] - near['b']:.5f} A against {PAPER['c'] - PAPER['b']:.5f}")
    hot = [r for r in out["rows"] if r["T"] > 160.0]
    gaps = [(r["b"][0] - r["c"][0]) / np.hypot(r["b"][1], r["c"][1]) for r in hot]
    ppm = [1e6 * abs(r["b"][0] - r["c"][0]) / PAPER["b"] for r in hot]
    print(f"  b-c above 160 K ({len(hot)} frames): median |gap| "
          f"{np.median(ppm):.1f} ppm, {np.median(np.abs(gaps)):.1f} combined esds, "
          f"max {np.max(np.abs(gaps)):.1f}")
    for path in SETUP:
        vals = [r["setup"][path][0] for r in out["rows"]]
        if vals[0] is None:
            continue
        esd = float(np.median([r["setup"][path][1] for r in out["rows"]]))
        print(f"  {path}: first {vals[0]:.5g} last {vals[-1]:.5g} "
              f"spread {np.ptp(vals):.3g} = {np.ptp(vals) / esd:.1f} esd")


def cold_check(saved: Path, patterns, temps) -> None:
    """Refit single frames from the CIF, so no neighbour's closed gap is inherited.

    At b = c the gap's first derivative vanishes, so a warm chain that closed
    could stay closed whatever the next frame says. This separates the two.
    """
    record = json.loads(saved.read_text(encoding="utf-8"))
    routes = {r["arm"]: r for r in record["routes"]}
    rows = []
    for arm, source, frames in (("cautious_cold_profile", 0, (3, 4, 6, 9)),
                                ("cautious_hot_profile", -1, (9, 13, 14, 15))):
        setup = {p.split(".")[-1]: v[0]
                 for p, v in routes["default"]["rows"][source]["setup"].items()}
        for k in frames:
            structure, instrument = models()
            for path, value in setup.items():
                target = instrument if path == "zero_shift" else instrument.profile
                getattr(target, path).value = value
            start = structure.phases[0].cell
            fit = rx.Refinement(structure, instrument).fit(patterns[k], plan=CAUTIOUS)
            values = {p.path: (p.value, p.stderr) for p in fit.parameters}
            row = {"arm": arm, "T": temps[k], "status": fit.status,
                   "start_gap": start.b.value - start.c.value,
                   "gap": values["phases.0.cell.b"][0] - values["phases.0.cell.c"][0],
                   "esd": float(np.hypot(values["phases.0.cell.b"][1],
                                         values["phases.0.cell.c"][1])),
                   "chain_gap": routes[arm]["rows"][k]["b"][0]
                   - routes[arm]["rows"][k]["c"][0]}
            print(row)
            rows.append(row)
    record["cold_check"] = rows
    saved.write_text(json.dumps(record, indent=1), encoding="utf-8")


def main() -> None:
    t0 = time.time()
    saved = Path(__file__).with_name("real_ramp.json")
    if "--report" in sys.argv:  # reread the saved fits, about ten minutes saved
        for route in json.loads(saved.read_text(encoding="utf-8"))["routes"]:
            report(route)
        return
    paths = sorted(DATA.glob("OH_*.fxye"))
    patterns = [rx.read_pattern(p) for p in paths]
    temps = [temperature(p) for p in paths]
    if "--cold-check" in sys.argv:
        cold_check(saved, patterns, temps)
        return
    if "--step-two" in sys.argv:
        routes = json.loads(saved.read_text(encoding="utf-8"))["routes"]
        routes = [r for r in routes if not r["arm"].startswith("cautious_")]
    else:
        routes = [run("default", "mccusker_default", patterns, temps),
                  run("cautious", CAUTIOUS, patterns, temps),
                  run("sample", "lab_sample_refine", patterns, temps)]
    # Yue's step 2 before step 4: zero and profile from the default chain's fit
    # of one frame, the coldest and the hottest in turn, then the cautious plan
    for arm, row in (("cautious_cold_profile", routes[0]["rows"][0]),
                     ("cautious_hot_profile", routes[0]["rows"][-1])):
        setup = {p.split(".")[-1]: v[0] for p, v in row["setup"].items()}
        routes.append(run(arm, CAUTIOUS, patterns, temps, setup))
    for route in routes:
        report(route)
    record = {"platform": f"{platform.system()} {platform.machine()}",
              "python": platform.python_version(), "rietx": rx.__version__,
              "venv": "worktree .venv, [dev]", "routes": routes,
              "seconds": round(time.time() - t0, 1)}
    print(f"{record['platform']}, Python {record['python']}, rietx "
          f"{record['rietx']}, {record['seconds']} s")
    saved.write_text(json.dumps(record, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
