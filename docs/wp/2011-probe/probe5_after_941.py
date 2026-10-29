"""Task 1: Le Bail against Pawley in the shipped check, on the tree with #941.

Calls the shipped ``validate_by_lebail`` itself and swaps the mode inside it, by
wrapping ``Refinement.fit`` so a ``mode="lebail"`` call becomes ``"pawley"``.
So the line screen, the width seeding and the plan are exactly what
``index_pattern`` runs, and the mode is the only variable.  Each case runs
four ways: {lebail, pawley} x {freeze_profile False, True}.  Each candidate
runs with the picked peak list (the line screen's path, which ``index_pattern``
always takes) and without one (the fitted-background path, reached only by a
direct call).

Cases: the nine true cells of probe 2 (refined once by an ordinary Le Bail fit
from the literature value, as there), the synthetic LaB6 wrong cells of probe 1
(seed 11), and magnetite's P rival from the indexer's own run.

Run from the worktree root:  .venv/bin/python docs/wp/2011-probe/probe5_after_941.py truths|lab6|magnetite
Rows go to $WP2011_OUT/rows5_<which>.json; one JSON line per check on stdout.
"""
from __future__ import annotations

import contextlib
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).parent))

from probe_lebail_vs_pawley import OUT  # noqa: E402

from rietx.indexing.workflow import validate_by_lebail  # noqa: E402
from rietx.refine import Refinement  # noqa: E402

_FIT = Refinement.fit


@contextlib.contextmanager
def fit_mode(mode):
    """Inside the block, every structure-free ``Refinement.fit`` runs as ``mode``.

    Either structure-free mode is rewritten, so the swap works on both sides
    of the switch (the validation passed ``"lebail"`` before it and
    ``"pawley"`` after)."""
    def fit(self, *a, **kw):
        if kw.get("mode") in ("lebail", "pawley"):
            kw["mode"] = mode
        return _FIT(self, *a, **kw)
    Refinement.fit = fit
    try:
        yield
    finally:
        Refinement.fit = _FIT


def one(case, cand, data, ins, peaks, *, mode, freeze, path):
    with fit_mode(mode):
        t0 = time.perf_counter()
        v, result = validate_by_lebail(cand, data, ins, peaks=peaks,
                                       freeze_profile=freeze, with_result=True)
        secs = time.perf_counter() - t0
    codes = sorted({d.code for d in result.diagnostics}) if result is not None else []
    floors = sorted({p for d in result.diagnostics if d.code == "FLOOR_HIT"
                     for p in d.where}) if result is not None else []
    rec = dict(
        case=case, mode=mode, freeze=freeze, path=path, secs=round(secs, 3),
        n_refl=v.n_reflections, rwp=round(v.rwp, 4), status=v.status,
        absent=v.predicted_but_absent,
        absent_unc=v.predicted_but_absent_uncancellable,
        absent_unc_win=v.predicted_but_absent_uncancellable_in_window,
        absent_source=v.absent_source, unmatched=v.unmatched_observed,
        bkg_mean=(round(float(np.mean(result.y_background)), 2)
                  if result is not None else None),
        floors=floors, codes=codes)
    print(json.dumps(rec), flush=True)
    return rec


def run(rows, case, cand, data, ins, peaks):
    for path, pk in (("peaks", peaks), ("no_peaks", None)):
        for freeze in (False, True):
            for mode in ("lebail", "pawley"):
                rows.append(one(case, cand, data, ins, pk, mode=mode,
                                freeze=freeze, path=path))


def _cell_of(ref):
    cell = ref.structure.phases[0].cell
    return tuple(float(getattr(cell, k).value)
                 for k in ("a", "b", "c", "alpha", "beta", "gamma"))


def truths(rows):
    from tests.test_acceptance_fap import build_fap_inputs
    from tests.test_acceptance_indexing import _qarr
    from tests.test_acceptance_nac import build_nac_inputs
    from tests.test_acceptance_srm660c import build_srm_inputs
    from rietx.indexing.pick import pick_peaks
    from rietx.indexing.workflow import seed_widths, structure_from_candidate
    from rietx.schemas.indexing import CellCandidate

    hexa = (90.0, 90.0, 120.0)
    right = (90.0, 90.0, 90.0)
    sets = [
        ("srm660c", lambda: build_srm_inputs()[::2], "cubic", "P", (4.15678,) * 3 + right),
        ("nac", lambda: build_nac_inputs()[::2], "cubic", "I", (10.2510,) * 3 + right),
        ("fap", lambda: build_fap_inputs()[::2], "hexagonal", "P", (9.3717, 9.3717, 6.8859) + hexa),
        ("corundum", lambda: _qarr("corundum.prn"), "trigonal", "R", (4.7589, 4.7589, 12.991) + hexa),
        ("brucite", lambda: _qarr("brucite.prn"), "trigonal", "P", (3.142, 3.142, 4.766) + hexa),
        ("zincite", lambda: _qarr("zincite.prn"), "hexagonal", "P", (3.2498, 3.2498, 5.2066) + hexa),
        ("zircon", lambda: _qarr("zircon.prn"), "tetragonal", "I", (6.6042, 6.6042, 5.9796) + right),
        ("fluorite", lambda: _qarr("fluorite.prn"), "cubic", "F", (5.4630,) * 3 + right),
        ("magnetite", lambda: _qarr("magnetit.prn"), "cubic", "F", (8.3941,) * 3 + right),
    ]
    only = sys.argv[2:] or None
    for name, load, system, centring, cell0 in sets:
        if only and name not in only:
            continue
        data, ins = load()
        peaks = pick_peaks(data, ins)
        start = CellCandidate(cell=cell0, cell_esd=(0.0,) * 6, system=system,
                              centring=centring)
        # probe 2's neutral cell refinement, unchanged, so the cells match
        seeded, _ = seed_widths(ins, peaks)
        ref = Refinement(structure_from_candidate(start), seeded, history=False)
        ref.fit(data, mode="lebail", plan="profile_only", telemetry=False)
        ref.fit(data, mode="lebail", plan="profile_only", telemetry=False)
        cand = CellCandidate(cell=_cell_of(ref), cell_esd=(0.0,) * 6,
                             system=system, centring=centring)
        run(rows, name, cand, data, ins, peaks)


def lab6(rows):
    from probe2_lebail_vs_pawley import lab6_data
    from tests.test_indexing_consensus import TRUE_A, _candidate, _instrument
    from rietx.indexing.pick import pick_peaks

    data = lab6_data(11)
    ins = _instrument()
    peaks = pick_peaks(data, ins)
    for name, f in (("lab6_truth", 1.0), ("lab6_doubled", 2.0),
                    ("lab6_a_sqrt5", math.sqrt(5.0)), ("lab6_metric_1pc", 1.01)):
        run(rows, name, _candidate(TRUE_A * f), data, ins, peaks)


def magnetite(rows):
    from tests.test_acceptance_indexing import _qarr
    from rietx.indexing.pick import pick_peaks
    from rietx.schemas.indexing import CellCandidate

    data, ins = _qarr("magnetit.prn")
    peaks = pick_peaks(data, ins)
    cached = OUT / "magnetite_candidates.json"
    if not cached.exists():
        # probe 1's search, on this tree: the indexer's own truth and P rival
        from tests.test_acceptance_indexing import (
            REAL_DATA_BUDGET_SECONDS,
            REAL_DATA_N_UNINDEXED,
        )
        from rietx.indexing import index_pattern
        from rietx.indexing.engines import SearchSpec

        spec = SearchSpec(systems=("cubic",), max_volume=700.0,
                          budget_seconds=REAL_DATA_BUDGET_SECONDS,
                          n_unindexed=REAL_DATA_N_UNINDEXED)
        res = index_pattern(peaks, data=data, instrument=ins, spec=spec, preset="full")
        top = res.candidates[0]
        rival = [c for c in res.candidates[1:] if c.centring == "P"
                 and abs(c.cell[0] / top.cell[0] - 1.0) < 1e-3][0]
        cached.write_text(json.dumps([c.model_dump(mode="json") for c in (top, rival)]),
                          encoding="utf-8")
    best, rival = [CellCandidate.model_validate(c)
                   for c in json.loads(cached.read_text(encoding="utf-8"))]
    run(rows, "magnetite_truth_F", best, data, ins, peaks)
    run(rows, "magnetite_rival_P", rival, data, ins, peaks)


if __name__ == "__main__":
    which = sys.argv[1]
    rows: list[dict] = []
    {"truths": truths, "lab6": lab6, "magnetite": magnetite}[which](rows)
    (OUT / f"rows5_{which}.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
