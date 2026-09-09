"""Issue #283: Cell's six parameters declare bounds; d_spacings refuses a
degenerate metric by name instead of warning; a bounded search that still
reaches one is counted and pushed back out rather than crashing.
"""

import warnings

import numpy as np
import pytest

from rietx import Instrument, PatternData, Refinement
from rietx.crystallography.lattice import DegenerateCellError, d_spacings
from rietx.optimize.least_squares import _DegenerateCellGuard
from rietx.schemas.common import Parameter
from rietx.schemas.structure import (
    CELL_ANGLE_MAX,
    CELL_ANGLE_MIN,
    CELL_LENGTH_MAX,
    CELL_LENGTH_MIN,
    Cell,
    lebail_scaffold,
)


def test_default_cell_has_physical_bounds():
    """A Cell built the way lebail_scaffold and Cell.cubic do -- bare
    Parameter(value=...), no min/max -- gets physical bounds backfilled."""
    c = Cell.cubic(5.0)
    for name in ("a", "b", "c"):
        p = getattr(c, name)
        assert p.min == CELL_LENGTH_MIN
        assert p.max == CELL_LENGTH_MAX
    for name in ("alpha", "beta", "gamma"):
        p = getattr(c, name)
        assert p.min == CELL_ANGLE_MIN
        assert p.max == CELL_ANGLE_MAX


def test_backfill_does_not_override_a_narrowed_bound():
    """A caller who already narrowed one side (viz/compare.py's
    ``_p(9.3717, min=1.0)`` idiom) keeps it; only the *unset* side (still at
    Parameter's own -inf/inf) is backfilled."""
    c = Cell(a=Parameter(value=9.3717, min=1.0),
             b=Parameter(value=9.3717, min=1.0),
             c=Parameter(value=6.8859, min=1.0),
             alpha=Parameter(value=90.0), beta=Parameter(value=90.0),
             gamma=Parameter(value=90.0))
    assert c.a.min == 1.0          # untouched
    assert c.a.max == CELL_LENGTH_MAX  # backfilled


def test_d_spacings_refuses_degenerate_cell_by_name():
    """alpha=beta=gamma=180 deg: zero-volume cell, refused loudly instead of
    the previous bare RuntimeWarning + NaN."""
    hkl = np.array([[1, 1, 0]])
    d_spacings(hkl, 5.0, 5.0, 5.0, 90.0, 90.0, 90.0)  # sanity: ordinary cell is fine

    with pytest.raises(DegenerateCellError) as excinfo:
        d_spacings(hkl, 5.0, 5.0, 5.0, 180.0, 180.0, 180.0)
    message = str(excinfo.value)
    # naming the cell and the determinant, per the issue's suggested shape
    assert "alpha=180.0" in message
    assert "determinant" in message
    assert "degenerate" in message


def test_d_spacings_refuses_equal_angle_rhombohedral_past_120deg():
    """A combination *within* Cell's own per-parameter angle bounds
    (10-170 deg) can still be degenerate: for a=b=c and alpha=beta=gamma,
    the direct metric's determinant is proportional to (1 - cos)^2 (1 + 2cos),
    which is exactly zero at 120 deg and negative beyond -- so the bound box
    alone does not guarantee a positive-definite metric everywhere inside it.
    """
    hkl = np.array([[1, 0, 0]])
    d_spacings(hkl, 5.0, 5.0, 5.0, 119.0, 119.0, 119.0)  # still admissible

    with pytest.raises(DegenerateCellError):
        d_spacings(hkl, 5.0, 5.0, 5.0, 130.0, 130.0, 130.0)  # inside (10, 170), still degenerate


def test_degenerate_cell_guard_counts_and_neutralises():
    """Unit test of the search-side guard in isolation: a residual that
    raises DegenerateCellError on some trials is counted and answered with a
    penalised (never crashing) residual once a good point has been seen."""
    calls = {"n": 0}

    def inner(theta):
        calls["n"] += 1
        if theta[0] > 1.0:
            raise DegenerateCellError("synthetic degenerate probe")
        return np.array([theta[0], 2.0 * theta[0]])

    guard = _DegenerateCellGuard(inner)

    r0 = guard(np.array([0.5]))
    assert np.array_equal(r0, [0.5, 1.0])
    assert guard.n_degenerate == 0

    r1 = guard(np.array([5.0]))  # degenerate trial
    assert guard.n_degenerate == 1
    assert np.array_equal(r1, r0 * 10.0)  # penalised, not raised

    r2 = guard(np.array([9.0]))  # another degenerate trial
    assert guard.n_degenerate == 2
    assert np.array_equal(r2, r0 * 10.0)

    r3 = guard(np.array([0.2]))  # back to a good point
    assert np.array_equal(r3, [0.2, 0.4])
    assert guard.n_degenerate == 2  # unchanged


def test_degenerate_cell_guard_reraises_if_never_seen_a_good_point():
    def inner(theta):
        raise DegenerateCellError("synthetic")

    guard = _DegenerateCellGuard(inner)
    with pytest.raises(DegenerateCellError):
        guard(np.array([0.0]))


def test_issue_283_fixture_no_runtime_warning_and_counted():
    """The issue's own reproduction: P1, a=5 A, lambda=1.5406 A, 20-60 deg
    2theta, intensity all ones (a featureless pattern -- the cell stage is
    underdetermined and the trust region used to probe alpha=beta=gamma near
    180 deg 3430 times in one fit, each a bare RuntimeWarning).  Run under
    ``-W error::RuntimeWarning`` equivalent (a local filter, so this test does
    not depend on the invocation's own -W flag): the fit must not warn, and
    every stage's degenerate-probe count is reported (unconditionally
    non-negative; 0 is the expected value now that Cell's own bounds keep the
    search away from the pathological region for this fixture).
    """
    structure = lebail_scaffold("P1", (5.0, 5.0, 5.0, 90.0, 90.0, 90.0))
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    tt = np.arange(20.0, 60.0, 0.02)
    pattern = PatternData(two_theta=tt.tolist(), intensity=np.ones_like(tt).tolist())

    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        ref = Refinement(structure, ins)
        result = ref.fit(pattern, mode="lebail", plan="profile_only")

    assert result.status == "converged"
    cell_stage = next(s for s in result.stages if s.name == "cell")
    assert cell_stage.n_degenerate_cell_probes >= 0
    # the cell never left the physical box the search was given
    a, b, c, al, be, ga = ref.fitted_structure.phases[0].cell.lengths_angles()
    for length in (a, b, c):
        assert CELL_LENGTH_MIN <= length <= CELL_LENGTH_MAX
    for angle in (al, be, ga):
        assert CELL_ANGLE_MIN <= angle <= CELL_ANGLE_MAX
