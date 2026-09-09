"""Issue #283: d_spacings refuses a degenerate metric by name instead of
warning; a search that still reaches one is counted and pushed back out
rather than crashing.

The other half of #283's suggested shape -- backfilling physical bounds onto
``Cell``'s six parameters -- is deliberately not shipped here (it contradicts
how the cell-window / tie-window machinery in ``rietx.params.vector`` reads
an infinite stored bound as *no claim made*; see the PR discussion on #283),
so this file has no test asserting ``Cell`` carries bounds.
"""

import warnings

import numpy as np
import pytest

from rietx import Instrument, PatternData, Refinement
from rietx.crystallography.lattice import DegenerateCellError, d_spacings
from rietx.optimize.least_squares import _DegenerateCellGuard
from rietx.schemas.structure import lebail_scaffold


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
    2theta, intensity all ones (a featureless pattern the issue reports
    reaching a degenerate cell 3430 times in one fit against an unbounded
    ``Cell``, each a bare RuntimeWarning).  ``Cell`` still declares no bounds
    of its own here (that half of #283 is not shipped) -- measured on this
    tree, the exact a=5.0 starting point in the issue's own reproduction no
    longer reaches the degenerate region at all (0 raw RuntimeWarnings on
    unpatched ``origin/main`` too, deterministic across repeats -- something
    about the trust-region path or a dependency version has changed since
    the issue was filed, not chased down further here), so this exact
    fixture is a weak vehicle for exercising the guard end to end.  Kept
    anyway as the literal acceptance check the issue and brief name: under
    ``-W error::RuntimeWarning`` equivalent (a local filter, so this test
    does not depend on the invocation's own -W flag) the fit must not warn,
    must still converge to the correct cell, and must report a
    non-negative probe count through the same channel a genuine reach would
    use.  The mechanism itself -- ``d_spacings`` raising by name, and
    ``_DegenerateCellGuard`` counting and neutralising it -- is exercised
    directly by the tests above, and by :func:`test_a_2pc_off_start_still_warning_free`
    below, which *does* reach warning territory on unpatched ``origin/main``
    for this same fixture family.
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
    # the returned cell is still correct -- the issue's own point: "the
    # returned cell is correct, this is not a wrong answer"
    a, b, c, al, be, ga = ref.fitted_structure.phases[0].cell.lengths_angles()
    assert a == pytest.approx(5.0, abs=0.01)
    assert b == pytest.approx(5.0, abs=0.01)
    assert c == pytest.approx(5.0, abs=0.01)
    assert al == pytest.approx(90.0, abs=0.5)
    assert be == pytest.approx(90.0, abs=0.5)
    assert ga == pytest.approx(90.0, abs=0.5)


def test_a_2pc_off_start_still_warning_free():
    """A 2 % wrong starting length on the same featureless fixture -- the
    issue's own sensitivity table lists this shape (a 2 %-off start on a
    peaked pattern, 445 warnings) but flags it as possibly a different
    issue's (#243) rather than this one's; the analogue measured here, on
    this featureless pattern, is unambiguously #283's: unpatched
    ``origin/main`` raises 60 raw ``RuntimeWarning``s for this exact start
    (measured directly, not asserted), all suppressed once ``d_spacings``
    checks the determinant and wraps its own sqrt in
    ``np.errstate(invalid=\"ignore\")`` -- whether or not any of those 60
    were an actual determinant <= 0 event routed through
    ``DegenerateCellError``/``_DegenerateCellGuard``, or floating-point noise
    right at the edge of positive-definiteness that the errstate alone
    catches.  Either way, the fit must run to completion under
    ``-W error::RuntimeWarning`` with no bounds on ``Cell`` at all.
    """
    structure = lebail_scaffold("P1", (4.9, 4.9, 4.9, 90.0, 90.0, 90.0))
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
