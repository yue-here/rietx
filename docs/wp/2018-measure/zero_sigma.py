"""C27: the rules that act on σ, on a file with one σ set to 0 (WP-2018, task 3).

Re-derived at bc77a934e: WP-1952 replaced ``_floor_sigma`` (a floor at a
thousandth of the column's median esd).  A channel whose stated σ is zero or
negative now leaves the fit under the reader option ``nonpositive_sigma=
"exclude"`` (the default; ``PatternData.in_range_mask``) or is weighted by the
Poisson fallback √max(y, 1) under ``"poisson"`` (``_poisson_where_nonpositive``,
schemas/pattern.py), and ``RefinementResult.sig`` applies the same function
again to the σ the fit stored.  The dataset is a copy of
``tests/data/11BM_LaB6_cBN_mg2044.xye`` with σ planted at the strongest channel
inside the fitted range, refined under ``tests/test_acceptance_lab6_cbn.py``'s
``PLAN_SHARED`` protocol, in arms:

  original      the vendored file
  zero_exclude  σ = 0 at that channel, the default rule
  zero_poisson  σ = 0 at that channel, ``nonpositive_sigma="poisson"``
  floor         the positive arm: σ = 1e-3 × the column's median esd at that
                channel, the value the retired floor gave a zero, which no rule
                touches

Per arm: Rwp, the channel count and ``sigma_rule``, the reader's diagnostics,
the σ the result stores at the channel, whether ``result.sig()`` equals
``result.sigma`` bit for bit, the cell rows the fit reports (cBN; LaB₆'s cell is not
free under this plan), both weight fractions and scales.

``sig()`` changes only a stored σ ≤ 0, and no arm's fit stores one, so its
equality check cannot fail on a fit's own result.  Its positive arm,
``sig_on_stored_zero``, runs in every arm after the fit: a copy of the result
with σ = 0 planted at its strongest fitted channel, which ``sig()`` should
return as √max(y, 1) there and bit for bit everywhere else.

usage (repo root): python docs/wp/2018-measure/zero_sigma.py [arm ...]
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import numpy as np
from common import diagnostics, emit, provenance

os.environ.setdefault("RIETX_TELEMETRY", "0")

import rietx as rx  # noqa: E402
from tests.test_acceptance_lab6_cbn import LIMITS, PATTERN, PLAN_SHARED, _inputs  # noqa: E402

ARMS = ("original", "zero_exclude", "zero_poisson", "floor")
PATHS = ("phases.0.cell.a", "phases.1.cell.a", "phases.1.cell.c",
         "phases.0.scale", "phases.1.scale")


def _planted(arm, tmp: Path):
    """The vendored file, or a copy with σ planted at the strongest channel."""
    if arm == "original":
        return PATTERN, None
    lines = PATTERN.read_text().splitlines()
    rows = [(i, line.split()) for i, line in enumerate(lines)
            if line.strip() and not line.lstrip().startswith(("/", "#"))]
    tt = np.array([float(r[0]) for _, r in rows])
    y = np.array([float(r[1]) for _, r in rows])
    sig = np.array([float(r[2]) for _, r in rows])
    inside = (tt >= LIMITS[0]) & (tt <= LIMITS[1])
    k = int(np.flatnonzero(inside)[np.argmax(y[inside])])
    value = 0.0 if arm.startswith("zero") else 1e-3 * float(np.median(sig))
    i, parts = rows[k]
    lines[i] = f"{parts[0]} {parts[1]} {value!r}"
    path = tmp / PATTERN.name
    path.write_text("\n".join(lines) + "\n")
    return path, {"two_theta": tt[k], "y": y[k], "sigma_file": sig[k],
                  "sigma_planted": value}


def fit(arm, tmp):
    path, planted = _planted(arm, tmp)
    found = []
    options = {"nonpositive_sigma": "poisson"} if arm == "zero_poisson" else {}
    data = rx.read_pattern(path, diagnostics=found, **options)
    structure, ins = _inputs()
    ref = rx.Refinement(structure, ins, history=False)
    result = ref.fit(data, plan=PLAN_SHARED, two_theta_limits=LIMITS, telemetry=False)
    return result, planted, found


def _stored_zero(result):
    """``sig()`` on a copy of ``result`` storing σ = 0 at its strongest channel."""
    tt = np.asarray(result.two_theta, dtype=np.float64)
    y = np.asarray(result.y_obs, dtype=np.float64)
    sigma = np.asarray(result.sigma, dtype=np.float64).copy()
    k = int(np.argmax(y))
    sigma[k] = 0.0
    got = result.model_copy(update={"sigma": sigma.tolist()}).sig()
    poisson = float(np.sqrt(max(y[k], 1.0)))
    return {"two_theta": float(tt[k]), "y": float(y[k]), "sig_at_channel": float(got[k]),
            "poisson": poisson, "equals_poisson": bool(got[k] == poisson),
            "others_bit_for_bit": bool(np.array_equal(np.delete(got, k),
                                                      np.delete(sigma, k)))}


def main(arms):
    emit({"provenance": provenance(), "fixture": "11BM_LaB6_cBN_mg2044.xye, PLAN_SHARED"})
    with tempfile.TemporaryDirectory() as tmp:
        for arm in arms:
            try:
                result, planted, found = fit(arm, Path(tmp))
            except Exception as exc:      # a crash is a measured outcome here
                emit({"arm": arm, "error": f"{type(exc).__name__}: {exc}"[:400]})
                continue
            tt = np.asarray(result.two_theta)
            stored = np.asarray(result.sigma)
            at = None
            if planted is not None:
                hit = np.flatnonzero(np.isclose(tt, planted["two_theta"], atol=1e-9))
                at = float(stored[hit[0]]) if hit.size else "not in the fit"
            rows = {p.path: [p.value, p.stderr] for p in result.parameters
                    if p.path in PATHS}
            qpa = ([[r.name, r.weight_fraction, r.weight_fraction_stderr]
                    for r in result.qpa.phases] if result.qpa else None)
            emit({"arm": arm, "rwp": result.statistics.rwp, "status": result.status,
                  "n_points": result.statistics.n_points,
                  "sigma_rule": result.sigma_rule.model_dump() if result.sigma_rule else None,
                  "planted": planted, "sigma_stored_at_channel": at,
                  "sig_equals_sigma": bool(np.array_equal(result.sig(), stored)),
                  "sig_on_stored_zero": _stored_zero(result),
                  "reader_diagnostics": [[d.code, d.message[:200]] for d in found],
                  "params": rows, "qpa": qpa,
                  "diagnostics": diagnostics(result)})


if __name__ == "__main__":
    main(sys.argv[1:] or ARMS)
