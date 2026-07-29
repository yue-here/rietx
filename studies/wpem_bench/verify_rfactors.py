"""Reproduce WPEM's published Rp/Rwp from WPEM's own shipped fitted profile.

The whole benchmark rests on the claim that WPEM's agreement factors and
``pxrdref``'s are the same quantity.  Rather than argue it from the source, this
recomputes them: take WPEM's ``WPEMfittingProfile_*.csv`` (its y_calc, background
included) against the raw ``intensity.csv``, apply the formulas from
``EMBraggOpt/EMBraggSolver.py``, and check the result against the numbers printed
in the paper.

    Rp  = Σ|y_calc − y_obs| / Σ y_obs
    Rwp = sqrt( Σ (y_calc − y_obs)² / max(y_obs,1)  /  Σ y_obs )

Then evaluate the *textbook* Rwp — sqrt(Σ w Δ² / Σ w y_obs²) with Poisson
w = 1/σ², which is what ``pxrdref.optimize.statistics.compute_statistics``
computes — on the same two arrays.  If they agree, the comparison is sound.

Usage:  ../../.venv/bin/python verify_rfactors.py
"""

from __future__ import annotations

import numpy as np
from bench import DATA

CASES = {
    "PbSO4": ("pbso4/intensity.csv", "pbso4/wpem_profile.csv", 3.023, 7.124),
    "Tb2BaCoO5": ("tb2bacoo5/intensity.csv", "tb2bacoo5/wpem_profile.csv",
                  6.175, 10.107),
}


def read_two_column(path) -> tuple[np.ndarray, np.ndarray]:
    rows = np.loadtxt(DATA / path, delimiter=",")
    return rows[:, 0], rows[:, 1]


def wpem_factors(y_obs: np.ndarray, y_calc: np.ndarray) -> tuple[float, float]:
    """Verbatim from EMBraggSolver.up_parameter."""
    diff = np.abs(y_calc - y_obs)
    obs = y_obs.sum()
    rp = diff.sum() / obs * 100
    rwp = np.sqrt((diff ** 2 / np.maximum(y_obs, 1.0)).sum() / obs) * 100
    return float(rp), float(rwp)


def textbook_factors(y_obs: np.ndarray, y_calc: np.ndarray) -> tuple[float, float]:
    """What pxrdref computes: w = 1/sigma^2, sigma = sqrt(max(y,1))."""
    w = 1.0 / np.maximum(y_obs, 1.0)
    diff = y_obs - y_calc
    rp = np.abs(diff).sum() / np.abs(y_obs).sum() * 100
    rwp = np.sqrt((w * diff ** 2).sum() / (w * y_obs ** 2).sum()) * 100
    return float(rp), float(rwp)


def main() -> None:
    print(f"{'case':12s} {'source':22s} {'Rp %':>8s} {'Rwp %':>8s}")
    for name, (obs_path, calc_path, rp_pub, rwp_pub) in CASES.items():
        tt_obs, y_obs = read_two_column(obs_path)
        tt_calc, y_calc = read_two_column(calc_path)
        assert np.allclose(tt_obs, tt_calc), f"{name}: 2theta grids differ"
        print(f"{name:12s} {'paper':22s} {rp_pub:8.3f} {rwp_pub:8.3f}")
        rp, rwp = wpem_factors(y_obs, y_calc)
        print(f"{'':12s} {'WPEM formula':22s} {rp:8.3f} {rwp:8.3f}")
        rp2, rwp2 = textbook_factors(y_obs, y_calc)
        print(f"{'':12s} {'pxrdref formula':22s} {rp2:8.3f} {rwp2:8.3f}")
        print(f"{'':12s} {'-> formulas agree to':22s} "
              f"{abs(rp - rp2):8.2e} {abs(rwp - rwp2):8.2e}")
        print()


if __name__ == "__main__":
    main()
