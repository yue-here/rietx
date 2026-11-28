"""WP-2315 R5 (b): the Pawley fits the lattice merge moves, measured.

Runs three real-data Pawley fits (default ``mode="pawley"`` plan) and prints,
per case, the reflection and column counts, the wall, Rwp and the cell with
its esd, as one JSON line.  Run it once under the branch and once under a
main snapshot (``PYTHONPATH=<snapshot>/src``), from the worktree root, so the
test helpers import:

    .venv/bin/python docs/wp/2315-probe/merge_measure.py branch
    PYTHONPATH=/tmp/main/src .venv/bin/python docs/wp/2315-probe/merge_measure.py main

Cases and their independent references:
- FAP.XRA (P 63/m): GSAS's converged cell in FAP.EXP (a cross-code reference).
- SRM 660c LaB6 (P m -3 m): the CIF block's cell, 4.156780 Å.
- corundum.prn, SRM 676a (R -3 c, hexagonal axes): the certificate's c/a.
"""

from __future__ import annotations

import json
import sys
import time

import rietx as rx


def _cell(ref, result, ip=0):
    out = {}
    for k in ("a", "c"):
        row = result.parameter(f"phases.{ip}.cell.{k}")
        out[k] = (row.value, row.stderr) if row is not None else None
    return out


def _run(name, data, structure, instrument, **kw):
    t0 = time.perf_counter()
    ref = rx.Refinement(structure, instrument, history=False)
    result = ref.fit(data, mode="pawley", **kw)
    wall = time.perf_counter() - t0
    pb = ref._model.pawley
    n_refl = sum(len(cp.reflections) for cp in ref._model.phases)
    return ref, result, {
        "case": name, "n_refl": n_refl, "n_col": int(pb.n),
        "merged_groups": len(getattr(pb, "merged", []) or []),
        "wall_s": round(wall, 2), "rwp": result.statistics.rwp,
        "n_free": result.statistics.n_free_parameters,
        "status": result.status, "cell": _cell(ref, result)}


def main(arm: str) -> None:
    from tests.test_acceptance_fap import EXP, build_fap_inputs
    from tests.test_acceptance_qpa_roundrobin import (
        DATA,
        corundum_phase,
        qarr_instrument,
        seed_scales,
    )
    from tests.test_acceptance_srm660c import build_srm_inputs

    rows = []
    data, s, ins = build_fap_inputs()
    ref, result, row = _run("FAP.XRA", data, s, ins)
    row["reference"] = {"a": EXP.phases[0].cell.a, "c": EXP.phases[0].cell.c}
    rows.append((ref, result, row))

    data, s, ins = build_srm_inputs()
    ref, result, row = _run("SRM660c", data, s, ins)
    row["reference"] = {"a": 4.156780}
    rows.append((ref, result, row))

    data = rx.read_pattern(DATA / "corundum.prn")
    s = rx.Structure(phases=[corundum_phase()])
    ins = qarr_instrument()
    seed_scales(s, ins, data)
    ref, result, row = _run("corundum", data, s, ins)
    row["reference"] = {"c_over_a": 12.99231 / 4.759355}
    rows.append((ref, result, row))

    for ref, result, row in rows:
        print(json.dumps({"arm": arm, **row}))
        if arm == "branch":
            result.plot(path=f"tests/output/wp2315_{row['case']}_pawley.png")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "branch")
