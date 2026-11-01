"""Ruling 3's sweep: do the three Pawley constants move the validation's readings?

The generality review (2026-10-27) asked for the validation's ``rwp``,
``unmatched_observed`` and ``status`` on probe 5's fourteen cells under
``PAWLEY_OVERLAP_FWHM_FRAC`` 0.25 and 1.0, ``PAWLEY_OVERLAP_LAMBDA`` 0.1 and
10, and every pattern divided by its maximum (where
``PAWLEY_OFF_DATA_SCALE_FLOOR`` may bind).  Each case runs the shipped
``validate_by_lebail`` (Pawley, peak-list path, widths free) once per variant.

- ``frac=…`` patches ``forward.PAWLEY_OVERLAP_FWHM_FRAC``, which
  ``_overlap_groups`` reads at call time.  The picker imported its own copy, so
  the peak list is the base one.  The fit's grouping moves, and so does the
  line screen's testable mask (``extinction.testable_mask`` calls
  ``_overlap_groups``), which ``predicted_but_absent`` reads.
- ``lam=…`` wraps ``CompiledModel.build_pawley_restraint``, whose default
  argument was bound at definition.  λ weights the off-data ridge as well as
  the equal-split rows.
- ``scaled`` divides intensity and σ by the maximum count, so χ² is unchanged
  and only the intensity units move; peaks are re-picked from the scaled
  pattern, as a user's would be.  ``scaled_nosigma`` divides the intensity
  alone, leaving σ to the Poisson fallback √max(y, 1), as a normalised export
  with no esd column would arrive.  Dropped after its first run: the picker
  finds no peak under σ = 1 and the line screen then raises on the empty list
  (``screen.fwhm_at``), so it measures the picker, not the floor.

Every variant records the smallest on-data Pawley intensity maximum the ridge
saw (``ridge_s_min``): the floor binds where that is under 1.

Run from the worktree root:
    .venv/bin/python docs/wp/2011-probe/probe9_constants.py truths|lab6|magnetite
Rows go to $WP2011_OUT/rows9_<which>.json; one JSON line per check on stdout.
"""
from __future__ import annotations

import contextlib
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).parent))

import probe5_after_941 as p5  # noqa: E402
from probe_lebail_vs_pawley import OUT  # noqa: E402

import rietx.model.forward as fwd  # noqa: E402
from rietx.indexing.pick import pick_peaks  # noqa: E402
from rietx.indexing.workflow import validate_by_lebail  # noqa: E402

_BUILD = fwd.CompiledModel.build_pawley_restraint
RIDGE_S: list[float] = []
GROUPS: list[int] = []


@contextlib.contextmanager
def variant(frac=None, lam=None):
    old_frac = fwd.PAWLEY_OVERLAP_FWHM_FRAC

    def build(self, lam_=fwd.PAWLEY_OVERLAP_LAMBDA):
        _BUILD(self, lam if lam is not None else lam_)
        pb = self.pawley
        if pb is not None:
            GROUPS.append(sum(len(g) for g in pb.groups))
        if pb is not None and pb.off_data:
            intens = self.pawley_x0()
            off = np.zeros(pb.n, dtype=bool)
            off[pb.off_data] = True
            for a, b in pb.phase_slices:
                on = intens[a:b][~off[a:b]]
                RIDGE_S.append(float(on.max()) if len(on) else 0.0)

    if frac is not None:
        fwd.PAWLEY_OVERLAP_FWHM_FRAC = frac
    fwd.CompiledModel.build_pawley_restraint = build
    try:
        yield
    finally:
        fwd.PAWLEY_OVERLAP_FWHM_FRAC = old_frac
        fwd.CompiledModel.build_pawley_restraint = _BUILD


def _scaled(data, sigma):
    y = np.asarray(data.intensity, dtype=np.float64)
    top = float(y.max())
    upd = {"intensity": (y / top).tolist()}
    upd["sigma"] = (np.asarray(data.sig()) / top).tolist() if sigma else None
    return data.model_copy(update=upd)


VARIANTS = [("base", {}, None), ("frac=0.25", {"frac": 0.25}, None),
            ("frac=1.0", {"frac": 1.0}, None), ("lam=0.1", {"lam": 0.1}, None),
            ("lam=10", {"lam": 10.0}, None), ("scaled", {}, True)]


def run(rows, case, cand, data, ins, peaks, **_):
    for name, kw, scale in VARIANTS:
        d, pk = data, peaks
        if scale is not None:
            d = _scaled(data, sigma=scale)
            pk = pick_peaks(d, ins)
        RIDGE_S.clear()
        GROUPS.clear()
        with variant(**kw):
            t0 = time.perf_counter()
            v, result = validate_by_lebail(cand, d, ins, peaks=pk, with_result=True)
            secs = time.perf_counter() - t0
        codes = sorted({x.code for x in result.diagnostics}) if result is not None else []
        rec = dict(case=case, variant=name, secs=round(secs, 3), mode=v.mode,
                   n_refl=v.n_reflections, n_peaks=len(pk.peaks) if hasattr(pk, "peaks") else None,
                   rwp=round(v.rwp, 4), status=v.status, unmatched=v.unmatched_observed,
                   absent=v.predicted_but_absent,
                   grouped=(max(GROUPS) if GROUPS else None),
                   ridge_s_min=(round(min(RIDGE_S), 4) if RIDGE_S else None),
                   codes=codes)
        rows.append(rec)
        print(json.dumps(rec), flush=True)


if __name__ == "__main__":
    which = sys.argv[1]
    p5.run = run
    rows: list[dict] = []
    {"truths": p5.truths, "lab6": p5.lab6, "magnetite": p5.magnetite}[which](rows)
    (OUT / f"rows9_{which}.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
