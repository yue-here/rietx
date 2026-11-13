"""WP-1420's grid: a subgroup started at its parent's cell, chained and cold.

    python -m tests.repro_1420 cold [--sign -1]
    python -m tests.repro_1420 chains [--sign -1] [--start 0.002]

The construction is :mod:`tests.test_identity_point_seed`'s (issue #267's,
fully synthetic): a Cu ``F m -3 m`` parent and its ``I 4/m m m`` subgroup, an
eight-pattern series with the subgroup present from p004 at a fraction of the
parent's scale.  Every run here walks seven noise draws (the issue's 20260904
and 1-6) at fractions 0.15, 0.25 and 0.40; ``--sign -1`` reverses the true
distortion.

``cold`` fits p004 and p007 alone from the identity point and from
±``OFF_IDENTITY``, and prints which side each start ended on and the two Rwp.
``chains`` runs the series through ``SequentialRefinement`` with
``carry=("*",)``, from the identity point under ``direction="both"`` (or from
``--start`` off it, forward only), and prints the side per present pattern,
the patterns where the subgroup carried ``PHASE_UNCONSTRAINED``, and the
``SEQUENTIAL_PATH_DEPENDENT`` findings on its cell.

The counts in ``docs/docs/guides/series.md`` § Start a subgroup off its
parent's cell and in WP-1420's 2026-11-04 entry came from these runs
(``[dev]``, darwin arm64); each takes a few minutes serially.
"""

from __future__ import annotations

import argparse
import math

import numpy as np

import rietx as rx
from rietx.schemas.structure import Structure
from tests.test_identity_point_seed import (
    GRID,
    OFF_IDENTITY,
    PLAN,
    TRUE_TET,
    _instrument,
    _parent,
    _subgroup,
)

DRAWS = (20260904, 1, 2, 3, 4, 5, 6)
FRACTIONS = (0.15, 0.25, 0.40)
ONSET, N_PATTERNS = 4, 8
#: the start's scale, relative to the parent's (issue #267's seed)
SEED_SCALE = 0.02


def series(draw: int, fraction: float, true_tet: float):
    """The eight patterns, and the parent's scale, for one draw."""
    truth = Structure(phases=[_parent(1.0), _subgroup(0.0, true_tet)])
    y = rx.Refinement(truth, _instrument(), history=False).predict(GRID)
    s_parent = 4.0e4 / float(np.max(y) - np.min(y))
    truth.phases[0].scale.value = s_parent
    rng = np.random.default_rng(draw)
    patterns = []
    for k in range(N_PATTERNS):
        truth.phases[1].scale.value = fraction * s_parent if k >= ONSET else 0.0
        y = rx.Refinement(truth, _instrument(), history=False).predict(GRID)
        counts = rng.poisson(np.maximum(y, 0.0)).astype(float)
        patterns.append(rx.PatternData(
            two_theta=GRID.tolist(), intensity=counts.tolist(),
            sigma=np.sqrt(np.maximum(counts, 1.0)).tolist()))
    return patterns, s_parent


def start(s_parent: float, tet: float) -> Structure:
    return Structure(phases=[_parent(0.9 * s_parent),
                             _subgroup(SEED_SCALE * s_parent, tet)])


def side(parameters) -> str:
    """``+``/``-`` past ±1e-3 in c/(a√2) − 1, ``0`` near the identity point."""
    p = {q.path: q.value for q in parameters}
    if "phases.1.cell.a" not in p:
        return "h"                                   # held: no cell reported
    t = p["phases.1.cell.c"] / (p["phases.1.cell.a"] * math.sqrt(2.0)) - 1.0
    return "+" if t > 1e-3 else "-" if t < -1e-3 else "0"


def cold(sign: int) -> None:
    right = n = 0
    for fraction in FRACTIONS:
        for draw in DRAWS:
            patterns, s_parent = series(draw, fraction, sign * TRUE_TET)
            for k in (ONSET, N_PATTERNS - 1):
                fits = {lab: rx.Refinement(start(s_parent, tet), _instrument(),
                                           history=False).fit(patterns[k], plan=PLAN)
                        for lab, tet in (("id", 0.0), ("+", OFF_IDENTITY),
                                         ("-", -OFF_IDENTITY))}
                lower = min(("+", "-"), key=lambda s: fits[s].statistics.rwp)
                ok = side(fits[lower].parameters) == ("+" if sign > 0 else "-")
                right, n = right + ok, n + 1
                print(f"f={fraction:.2f} draw={draw:>8} p{k:03d} "
                      + " ".join(f"{lab}:{side(r.parameters)} rwp={r.statistics.rwp:.4f}"
                                 for lab, r in fits.items())
                      + f" lower={lower} true={ok}", flush=True)
    print(f"the lower Rwp of the two starts is the true side in {right} of {n}")


def chains(sign: int, offset: float | None) -> None:
    for fraction in FRACTIONS:
        for draw in DRAWS:
            patterns, s_parent = series(draw, fraction, sign * TRUE_TET)
            tets = [0.0] if offset is None else [offset, -offset]
            for tet in tets:
                sr = rx.SequentialRefinement(start(s_parent, tet), _instrument(),
                                             carry=("*",), history=False)
                direction = "both" if offset is None else "forward"
                result = sr.fit(patterns, plan=PLAN, direction=direction)
                runs = [("forward", result)]
                if sr.backward_ is not None:
                    runs.append(("backward", sr.backward_))
                cell_pd = sum(d.code == "SEQUENTIAL_PATH_DEPENDENT"
                              and any(w.startswith("phases.1.cell") for w in d.where)
                              for d in result.diagnostics)
                for name, s in runs:
                    sides = "".join(side(e.parameters) for e in s.entries[ONSET:])
                    held = [e.label for e in s.entries
                            if any(d.code == "PHASE_UNCONSTRAINED"
                                   and any(w.startswith("phases.1.") for w in d.where)
                                   for d in e.diagnostics)]
                    rwp = np.mean([e.statistics.rwp for e in s.entries[ONSET:]])
                    print(f"f={fraction:.2f} draw={draw:>8} start={tet:+.4f} "
                          f"{name:>8} sides={sides} rwp={rwp:.4f} "
                          f"unconstrained={','.join(held) or '-'} "
                          f"cell_path_dependent={cell_pd}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("what", choices=("cold", "chains"))
    ap.add_argument("--sign", type=int, choices=(1, -1), default=1)
    ap.add_argument("--start", type=float, default=None,
                    help="chains only: two forward chains started ± this far off")
    a = ap.parse_args()
    cold(a.sign) if a.what == "cold" else chains(a.sign, a.start)


if __name__ == "__main__":
    main()
