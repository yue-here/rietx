"""E-RAMP: the in-situ ramp episode, simulated with rietx's own forward model.

    python tests/eval_agent_surface/episodes/ramp.py <workspace> [N]

Writes N ``.xye`` patterns and ``host.cif`` into an empty directory, and
nothing else.  That directory *is* the episode: the agent gets the patterns,
the host phase, and no script, notebook or note saying what was done to them.

**This is the 2026-08-26 baseline's own generator**, moved here so the episode
can be rebuilt instead of being a directory somebody kept
(``~/rietx-agent-runs/2026-08-26-insitu-ramp/``).  The simulation half is
unchanged — same seed, same grid, same order of draws — so the patterns are
byte-for-byte the ones that run was given, which is what makes the baseline's
economics comparable at all.  `test_episode_ramp.py` asserts that against the
preserved copy when it is present and skips when it is not.  The half that is
new is the writer: the original script simulated and refined in one process and
never wrote the patterns out.

**The truth, which the agent is told none of.** NAC (COD 1000236) on a Cu Kα
Bragg-Brentano geometry, 15-60° 2θ at 0.02°:

* the host cell expands 0.8 % over 25 → 720 °C, with a first-order step of
  +0.16 % at 430 °C;
* a CaF₂ phase is **absent below the step** and grows above it to a plateau;
* the CaF₂ cell is **held constant** in the simulation, which is not physical
  and is the trap: the baseline agent noticed and refused to quote it;
* Poisson noise, σ = √counts.

Do not add a truth file to the workspace.  The round scores the route and the
price, not the destination (PROTOCOL.md § What is not being scored), and the
truth is compared against a run afterwards, from here.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import numpy as np

import rietx as rx
from rietx.model.forward import WINDOW_AREA_TOL, compile_model
from rietx.params.vector import ParameterTable
from rietx.schemas.instrument import BackgroundChebyshev

# The host CIF ships with the package's test data; the episode hands the agent a
# copy under a name that says nothing about what else is in the patterns.
HOST_CIF = Path(__file__).resolve().parents[2] / "data" / "cod_1000236.cif"

T0, T1, T_TR = 25.0, 720.0, 430.0
GRID = np.arange(15.0, 60.0 + 1e-9, 0.02)
A0 = 10.2570
SEED = 20260826
N_PATTERNS = 68


def a_of_T(T: float) -> float:
    """Host cell edge (Å): linear expansion with a first-order step at 430 °C."""
    if T <= T_TR:
        return A0 * (1 + 8.0e-6 * (T - 25.0))
    return A0 * (1 + 8.0e-6 * (T_TR - 25.0) + 1.6e-3 + 1.10e-5 * (T - T_TR))


def w_of_T(T: float) -> float:
    """Second-phase weight: zero below the step, ramping to a plateau over 90 K."""
    return 0.0 if T <= T_TR else min(1.0, (T - T_TR) / 90.0)


def caf2(scale: float) -> rx.Phase:
    return rx.Phase(
        name="CaF2", space_group="F m -3 m", cell=rx.Cell.cubic(5.4631),
        atoms=[
            rx.Atom(label="Ca", species="Ca2+", x=rx.Parameter(value=0.0),
                    y=rx.Parameter(value=0.0), z=rx.Parameter(value=0.0),
                    biso=rx.Parameter(value=0.6, min=0.0, max=25.0)),
            rx.Atom(label="F", species="F1-", x=rx.Parameter(value=0.25),
                    y=rx.Parameter(value=0.25), z=rx.Parameter(value=0.25),
                    biso=rx.Parameter(value=0.9, min=0.0, max=25.0)),
        ],
        scale=rx.Parameter(value=scale, min=0.0, transform="softplus"))


def instrument() -> rx.Instrument:
    ins = rx.Instrument.bragg_brentano(radiation="CuKa", monochromator_two_theta=26.6)
    ins.profile.u.value = 0.010
    ins.profile.v.value = -0.005
    ins.profile.w.value = 0.050
    ins.profile.x.value = 0.030
    ins.background = BackgroundChebyshev.with_terms(4)
    return ins


def host_structure() -> rx.Structure:
    s = rx.Structure.from_cif(str(HOST_CIF))
    s.phases[0].name = "NAC"
    return s


def simulate(n: int = N_PATTERNS) -> tuple[np.ndarray, list[np.ndarray]]:
    """Temperatures and Poisson counts, in the order the baseline drew them.

    One ``rng.poisson`` draw per pattern, in ascending temperature: the RNG's
    consumption order is part of the episode's identity, so a loop that
    reorders or adds a draw produces a different dataset under the same seed.
    """
    temps = np.linspace(T0, T1, n)
    truth = host_structure()
    truth.phases[0].scale.value = 6.0e-5
    truth.phases.append(caf2(0.0))

    ins = instrument()
    ins.background.coefficients[0].value = 260.0
    ins.background.coefficients[1].value = -70.0
    ins.background.coefficients[2].value = 25.0

    rng = np.random.default_rng(SEED)
    counts: list[np.ndarray] = []
    for T in temps:
        truth.phases[0].cell.a.value = a_of_T(T)
        truth.phases[1].scale.value = 4.0e-4 * w_of_T(T)
        # at the declared stages' windows, the draw the registered baseline
        # was captured from: predict's default became the closing stage's
        # fraction in WP-2002's seventh round, and moved 149 935 of 153 068
        # channels
        table = ParameterTable(truth, ins)
        grid = rx.PatternData(two_theta=GRID.tolist(), intensity=np.zeros_like(GRID).tolist())
        y = compile_model(truth, ins, grid, mode="rietveld",
                          moving_paths=set(table.moving_paths),
                          window_area_tol=WINDOW_AREA_TOL).evaluate(table.decode(table.x0()))
        counts.append(rng.poisson(np.maximum(y, 0.0)).astype(float))
    return temps, counts


def pattern_name(index: int, T: float) -> str:
    return f"ramp_{index:02d}_{T:.0f}C.xye"


def format_pattern(counts: np.ndarray) -> str:
    """2θ, counts, σ = √max(counts, 1) — the fallback σ, written to the file.

    The reader would compute the same σ from the counts, but an episode that
    withholds it would be measuring `read_pattern`'s Poisson fallback rather
    than the agent (root CLAUDE.md § Weights).
    """
    sigma = np.sqrt(np.maximum(counts, 1.0))
    return "".join(f"{x:.4f} {y:.1f} {s:.4f}\n"
                   for x, y, s in zip(GRID, counts, sigma))


def write_workspace(out: Path, n: int = N_PATTERNS) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    temps, counts = simulate(n)
    written = []
    for i, (T, y) in enumerate(zip(temps, counts)):
        path = out / pattern_name(i, T)
        path.write_text(format_pattern(y), encoding="utf-8")
        written.append(path)
    shutil.copyfile(HOST_CIF, out / "host.cif")
    written.append(out / "host.cif")
    return written


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    out = Path(argv[1])
    n = int(argv[2]) if len(argv) > 2 else N_PATTERNS
    written = write_workspace(out, n)
    print(f"{len(written)} files in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
