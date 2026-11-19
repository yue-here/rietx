"""``MODEL_FAR_FROM_DATA``'s level on real thinned fits and real collapses (WP-2017 group K).

The error fires when a fit's χ² is no better than a background-only fit's by Hamilton's
(1965) R-factor ratio test at ``refine.MODEL_FAR_FROM_DATA_ALPHA`` (Yue, 2026-11-17).  These
rows hold that level between the two kinds of fit it must tell apart, on cases taken from
the measured batch (``docs/wp/2017-batch/group_k.py``, ``group_k_summary.md``: corundum,
FAP, SRM 660c and NAC under their acceptance protocols, thinned to 0.05-1 counts a channel,
three seeds, 64 correct starts, 204 full collapses).

Each correct case is the family's correct start at 0.05 counts a channel, the sparsest level
and the one where p is largest, at the seed whose F was smallest.  Each collapse has every
phase scale at zero: held there (``scale_zero``), or reached from a start 3 % off
(corundum, the reach harness's displaced arm; the same landing under k·1e-14 perturbations of
W, k = ±1, ±3, ±7, 20).  The fits are real and the p is the one the package computed
(``reach_harness.far_from_data_spy``).
"""

from __future__ import annotations

import importlib

import pytest

from tests import reach_harness as h

pytestmark = [pytest.mark.slow, pytest.mark.xdist_group("far-from-data-family")]

CORRECT = (
    h.Case("fap", mean_counts=0.05, seed=3),        # the largest p of the 64 correct fits
    h.Case("srm660c", mean_counts=0.05, seed=3),
    h.Case("corundum", mean_counts=0.05, seed=2),
    h.Case("nac", mean_counts=0.05, seed=1),
)
COLLAPSES = (
    h.Case("fap", mean_counts=1.0, seed=2, scale_zero=True),   # the smallest p of the 204
    h.Case("fap", scale_zero=True),             # the ruling's case: unthinned FAP at Rwp 0.693
    h.Case("corundum", cell_error=-0.03),       # a displaced start that collapsed
    h.Case("nac", mean_counts=0.05, seed=1, scale_zero=True),
)


def _alpha() -> float:
    # read at call time, so the constant as the package holds it is the one compared
    return importlib.import_module("rietx.refine").MODEL_FAR_FROM_DATA_ALPHA


@pytest.fixture(scope="module")
def rows():
    return {c: h.run_case(c) for c in CORRECT + COLLAPSES}


@pytest.mark.parametrize("case", CORRECT, ids=lambda c: c.name)
def test_a_correct_thinned_fit_is_not_flagged(rows, case):
    row = rows[case]
    assert row["far_from_data"]["n_added"] > 0 and row["n_tests"] >= 1
    assert not h.flagged(row), row["far_from_data"]
    assert row["usable"]
    # sparse, so Rwp sits where the old 0.8 bar flagged correct fits (0.74-0.92 measured)
    assert row["rwp"] > 0.7


@pytest.mark.parametrize("case", COLLAPSES, ids=lambda c: c.name)
def test_a_full_collapse_is_flagged(rows, case):
    row = rows[case]
    assert all(s == 0.0 for s in row["scales"])     # every phase: a full collapse
    assert h.flagged(row), row["far_from_data"]
    assert "MODEL_FAR_FROM_DATA" in row["error_codes"]
    assert not row["usable"]


def test_the_level_sits_between_the_largest_correct_p_and_the_smallest_collapse_p(rows):
    # Both edges are far from 0.05, and the batch has no case nearer on either side.
    # Correct side: the largest p of the 64 correct fits is 4.65e-142, FAP thinned to 0.05
    # counts a channel at seed 3 (F 53.8 on 14 added parameters, Rwp 0.916), the same to 10
    # digits on Linux x86_64 and macOS arm64.  No correct fit comes within a decade of α.
    # Collapse side: every full collapse is no better than the background to rounding, F
    # within ±1.2e-12 of 0, so p is 1 on macOS arm64 and 1 - 1.2e-12 at the least on Linux
    # x86_64 (FAP at 1 count a channel, seed 2, held at scale 0, Rwp 0.866).  No collapse
    # comes within a decade of α either: any α in (4.65e-142, 1) separates the two.
    alpha = _alpha()
    hi = max(h.p_value(rows[c]) for c in CORRECT)
    lo = min(h.p_value(rows[c]) for c in COLLAPSES)
    assert hi < alpha < lo, (hi, alpha, lo)
