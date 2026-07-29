"""WPEM benchmark case 7 — operando LixNiyO2 cathode, 157 patterns, Fig. 3a.

The paper reports no agreement factors and no numbers for this case.  Its claim
is qualitative and about *throughput*: WPEM in batch mode tracks the lattice
evolution of a layered NCM-type cathode through a charge cycle, showing the
c axis expanding and then collapsing at high state of charge (the H2-H3
transition), read off the (0 0 3) reflection.

So this run does not chase an Rwp comparison.  It asks whether ``pxrdref``
reproduces the *physics claim* on the same 157 patterns, and it uses the one
tool the paper's batch mode does not have: ``refine_sequential`` with
``direction="both"``, which chains the series forward and backward and flags
every parameter where the two trajectories disagree by more than their esds
allow (``SEQUENTIAL_PATH_DEPENDENT``).  A warm-started chain is path-dependent
by construction; running it one way and reporting the trajectory does not
separate a measured trend from an ordering artefact, and this is the check
that does.

Data: ``CASES/Insitu XRD/data/{1..157}.xlsx``, 329 points each,
10.09-61.78 deg, Cu Kalpha (identified from the LiNiO2 reflection positions —
the notebooks do not state it).  Structure: ``CASES/Insitu XRD/LiNiO2.cif``,
R-3m, a = 2.87549, c = 14.18056 A.
"""

from __future__ import annotations

import json

import numpy as np
from bench import DATA, OUT, RESULTS, Timer
from insitu_io import series

import pxrdref as pr

CASE = "insitu"
N_PATTERNS = 157
LIMITS = (14.0, 61.7)  # drop the two edge channels that carry cell-window signal


def main() -> None:
    patterns = series(DATA / "insitu/data", N_PATTERNS)
    tt = np.asarray(patterns[0].two_theta)
    print(f"in-situ LixNiyO2: {len(patterns)} patterns x {len(tt)} points, "
          f"{tt[0]:.2f}-{tt[-1]:.2f} deg")

    structure = pr.Structure.from_cif(str(DATA / "insitu/LiNiO2.cif"))
    phase = structure.phases[0]
    phase.name = "LixNiyO2"
    print(f"  model: {phase.space_group}, a={phase.cell.a.value:.5f} "
          f"c={phase.cell.c.value:.5f}, {len(phase.atoms)} sites")

    instrument = pr.Instrument.bragg_brentano(radiation="CuKa")
    instrument.background = pr.background.auto_background(patterns[0],
                                                          kind="chebyshev")

    # 329 points at 0.16 deg cannot support a structural refinement; this is a
    # lattice-tracking run, so only scale, background, cell and the widths move.
    plan = pr.RefinementPlan(stages=[
        pr.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        pr.Stage("zero", ["instrument.zero_shift"]),
        pr.Stage("cell", ["phases.*.cell.*"]),
        pr.Stage("profile_w", ["instrument.profile.w"]),
        pr.Stage("profile", ["instrument.profile.u", "instrument.profile.x"]),
    ])

    with Timer() as t:
        result = pr.refine_sequential(
            patterns, structure, instrument, plan=plan,
            two_theta_limits=LIMITS, x=list(range(1, len(patterns) + 1)),
            x_label="pattern index", direction="both")
    print(f"  {len(result.entries)} refinements in {t.seconds:.1f}s "
          f"({t.seconds / len(result.entries):.2f}s each)")

    rwp = np.array([e.statistics.rwp for e in result.entries])
    print(f"  Rwp over the series: median {np.median(rwp) * 100:.2f}%  "
          f"range {rwp.min() * 100:.2f}-{rwp.max() * 100:.2f}%")

    out: dict[str, list] = {}
    esd: dict[str, list] = {}
    for path in ("phases.0.cell.a", "phases.0.cell.c"):
        traj = result.trajectory(path)
        out[path] = [float(v) for v in traj.value]
        esd[path] = [None if s is None else float(s) for s in traj.stderr]
    a_vals = np.array([v for v in out.get("phases.0.cell.a", []) if v is not None])
    c_vals = np.array([v for v in out.get("phases.0.cell.c", []) if v is not None])
    if c_vals.size:
        peak = int(np.argmax(c_vals))
        print(f"  c axis: start {c_vals[0]:.4f} -> max {c_vals.max():.4f} "
              f"at pattern {peak + 1} -> end {c_vals[-1]:.4f} A "
              f"(expand {(c_vals.max() / c_vals[0] - 1) * 100:+.2f}%, "
              f"then collapse {(c_vals[-1] / c_vals.max() - 1) * 100:+.2f}%)")
    if a_vals.size:
        print(f"  a axis: start {a_vals[0]:.4f} -> end {a_vals[-1]:.4f} A "
              f"({(a_vals[-1] / a_vals[0] - 1) * 100:+.2f}%)")

    path_dependent = [d for d in result.diagnostics
                      if d.code == "SEQUENTIAL_PATH_DEPENDENT"]
    print(f"  forward/backward disagreement: {len(path_dependent)} parameter(s) "
          f"flagged SEQUENTIAL_PATH_DEPENDENT")
    for d in path_dependent[:6]:
        print(f"      {d.message[:160]}")

    RESULTS.mkdir(parents=True, exist_ok=True)
    RESULTS.joinpath(f"{CASE}.json").write_text(json.dumps({
        "case": CASE,
        "dataset": "CASES/Insitu XRD/data/{1..157}.xlsx",
        "n_patterns": len(result.entries),
        "n_points_each": int(len(tt)),
        "two_theta_range": list(LIMITS),
        "wavelengths": [float(line.wavelength) for line in instrument.source.lines],
        "seconds": round(t.seconds, 1),
        "seconds_per_pattern": round(t.seconds / len(result.entries), 3),
        "rwp_median": float(np.median(rwp)),
        "rwp_min": float(rwp.min()), "rwp_max": float(rwp.max()),
        "trajectories": out,
        "trajectory_esds": esd,
        "c_expand_then_collapse": (
            {"start": float(c_vals[0]), "max": float(c_vals.max()),
             "max_at_pattern": int(np.argmax(c_vals)) + 1,
             "end": float(c_vals[-1])} if c_vals.size else None),
        "path_dependent": [{"code": d.code, "message": d.message}
                           for d in path_dependent],
        "diagnostics": [{"level": d.level, "code": d.code, "message": d.message}
                        for d in result.diagnostics if d.code != "HIGH_CORRELATION"],
        "reference": {
            "source": "arXiv 2602.16372 Fig. 3a",
            "claim": "c axis first expands then collapses sharply at high state "
                     "of charge (H2-H3); no R factors or cell values published",
        },
    }, indent=2, default=float))
    print(f"  saved results/{CASE}.json")

    _plot_trajectories(out, rwp)


def _plot_trajectories(traj: dict[str, list], rwp: np.ndarray) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    OUT.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
    for ax, path, label in zip(axes, ("phases.0.cell.a", "phases.0.cell.c"),
                               ("a (Å)", "c (Å)")):
        values = traj.get(path) or []
        ax.plot(range(1, len(values) + 1), values, "-o", ms=2.5, color="#1f4f82")
        ax.set_ylabel(label)
        ax.grid(alpha=0.3)
    axes[2].plot(range(1, len(rwp) + 1), rwp * 100, "-o", ms=2.5, color="#8a2f2f")
    axes[2].set_ylabel("Rwp (%)")
    axes[2].set_xlabel("pattern index (charge cycle)")
    axes[2].grid(alpha=0.3)
    axes[0].set_title("operando LixNiyO2 — pxrdref sequential refinement, "
                      "157 patterns")
    fig.tight_layout()
    fig.savefig(OUT / "insitu_trajectories.png", dpi=140)
    plt.close(fig)
    print("  wrote output/insitu_trajectories.png")


if __name__ == "__main__":
    main()
