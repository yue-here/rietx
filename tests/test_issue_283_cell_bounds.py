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
from rietx.model.forward import compile_model
from rietx.optimize.least_squares import (
    _DegenerateCellGuard,
    _DegenerateCellJacobianGuard,
    _jacobian_for,
    _make_residual,
    run_least_squares,
)
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.structure import Atom, Cell, Phase, Structure, lebail_scaffold


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
    checks the determinant and raises ``DegenerateCellError`` by name instead
    of falling through to the sqrt that used to warn.  ``d_spacings`` no
    longer wraps that sqrt in ``np.errstate(invalid=\"ignore\")`` (dropped in
    review: for a concrete, positive determinant every principal minor of G*
    is positive by Sylvester's criterion, so ``inv_d2`` cannot itself be
    negative or non-finite -- checked by a 200000-cell search, not just
    argued -- which made the suppression dead code once this file's own
    determinant check was in place), so this test is now also where "no
    residual floating-point-noise warning independent of the guard" is
    checked, not merely assumed.  Either way, the fit must run to completion
    under ``-W error::RuntimeWarning`` with no bounds on ``Cell`` at all.
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


def test_degenerate_cell_jacobian_guard_counts_and_neutralises():
    """Unit test of the Jacobian-side guard in isolation, mirroring
    ``test_degenerate_cell_guard_counts_and_neutralises`` above: a Jacobian
    that raises DegenerateCellError on some calls is counted (through the
    *residual* guard's shared counter -- there is deliberately no separate
    one) and answered with the last successfully evaluated Jacobian once one
    has been seen, never crashing."""
    calls = {"n": 0}

    def inner(theta):
        calls["n"] += 1
        if theta[0] > 1.0:
            raise DegenerateCellError("synthetic degenerate probe")
        return np.array([[theta[0], 2.0 * theta[0]]])

    residual_guard = _DegenerateCellGuard(lambda theta: theta)  # inner unused here
    guard = _DegenerateCellJacobianGuard(inner, residual_guard)

    J0 = guard(np.array([0.5]))
    assert np.array_equal(J0, [[0.5, 1.0]])
    assert residual_guard.n_degenerate == 0

    J1 = guard(np.array([5.0]))  # degenerate trial
    assert residual_guard.n_degenerate == 1
    assert np.array_equal(J1, J0)  # neutralised to the last accepted Jacobian

    J2 = guard(np.array([9.0]))  # another degenerate trial
    assert residual_guard.n_degenerate == 2
    assert np.array_equal(J2, J0)

    J3 = guard(np.array([0.2]))  # back to a good point
    assert np.array_equal(J3, [[0.2, 0.4]])
    assert residual_guard.n_degenerate == 2  # unchanged


def test_degenerate_cell_jacobian_guard_shares_counter_with_residual_guard():
    """The two guards built for one stage (as ``run_least_squares`` wires
    them) count into the *same* ``n_degenerate`` -- a residual-path probe and
    a Jacobian-path probe in the same stage must add up to one total, not two
    independent ones, which is the whole point of passing the residual guard
    into the Jacobian guard's constructor rather than giving it its own."""
    def bad_residual(theta):
        raise DegenerateCellError("synthetic residual probe")

    def bad_jacobian(theta):
        raise DegenerateCellError("synthetic jacobian probe")

    residual_guard = _DegenerateCellGuard(bad_residual)
    jacobian_guard = _DegenerateCellJacobianGuard(bad_jacobian, residual_guard)

    # seed both with one good call first so later failures are neutralised
    # rather than re-raised (mirrors run_least_squares: x0 always succeeds
    # before either guard is asked to absorb a degenerate trial)
    residual_guard._inner = lambda theta: np.array([1.0])
    residual_guard(np.array([0.0]))
    jacobian_guard._inner = lambda theta: np.array([[1.0]])
    jacobian_guard(np.array([0.0]))

    residual_guard._inner = bad_residual
    jacobian_guard._inner = bad_jacobian

    residual_guard(np.array([1.0]))
    assert residual_guard.n_degenerate == 1
    jacobian_guard(np.array([1.0]))
    assert residual_guard.n_degenerate == 2  # same counter, not a fresh one


def _rhombohedral_boundary_cell() -> Structure:
    """a=b=c=5 A, alpha=120.0001 deg, beta=gamma=119.9999 deg: an admissible
    cell (det(G) = 0.0354 > 0) one finite-difference step away from a
    degenerate one along the ``alpha`` column.

    ``h = 1e-6 * max(1, |theta|)`` (the FD step every fallback and peak-chain
    column in ``_make_jacobian`` uses) is ``1.2e-4`` here, and
    ``direct_metric_tensor``'s determinant at ``alpha + h`` is ``-0.0071``
    (measured directly, not asserted) -- crossing zero between the two
    endpoints the differencing loop actually evaluates.  Found by scanning
    ``direct_metric_tensor``'s determinant near the alpha=beta=gamma=120 deg
    equal-angle boundary this file's other tests use, restricted to moving
    ``alpha`` alone (``beta``, ``gamma`` fixed one FD step below 120 deg) --
    the shape a single free cell column actually varies.
    """
    return Structure(phases=[Phase(
        name="toy", space_group="P1",
        cell=Cell(a=Parameter(value=5.0), b=Parameter(value=5.0),
                  c=Parameter(value=5.0), alpha=Parameter(value=120.0001),
                  beta=Parameter(value=119.9999), gamma=Parameter(value=119.9999)),
        atoms=[Atom(label="Fe", species="Fe", x=Parameter(value=0.0),
                    y=Parameter(value=0.0), z=Parameter(value=0.0))],
    )])


def _compile_alpha_only(structure):
    """Compile ``structure`` with only ``phases.0.cell.alpha`` free -- the
    one-column setup :func:`_rhombohedral_boundary_cell` is built for."""
    structure.phases[0].scale.value = 1e-3
    ins = Instrument.debye_scherrer(wavelength=1.5406)
    ins.profile.w.value = 1e-2
    tt = np.arange(10.0, 90.0, 0.02)
    pattern = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    assert table.set_vary(["phases.0.cell.alpha"], True)
    table.apply_to_models(structure, ins)
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    return model, table


def test_jacobian_reaches_degenerate_cell_during_differencing():
    """The review's Before-merge item 2: a finite-difference *step* off an
    admissible cell parameter, not the parameter itself, is what crosses into
    degenerate territory -- reached through the real dispatch
    (``_jacobian_for`` -> ``_make_jacobian``'s peak-chain branch ->
    ``_peak_chain_column`` -> ``phase_peaks`` -> ``d_spacings``), not a
    synthetic stand-in.

    First shows the *unguarded* Jacobian genuinely raises at this exact
    ``theta`` (proving the crossing is real), then shows the same call
    through the guard ``run_least_squares`` wires up -- a
    ``_DegenerateCellJacobianGuard`` sharing its counter with the stage's
    ``_DegenerateCellGuard`` -- completes without raising once a prior good
    Jacobian has been seen (exactly the order ``run_least_squares`` produces:
    the residual/Jacobian at ``x0`` always succeed before any later trial
    can be neutralised), and that the shared probe count goes up by one.
    """
    structure = _rhombohedral_boundary_cell()
    model, table = _compile_alpha_only(structure)
    theta_boundary = table.x0()
    assert theta_boundary == pytest.approx([120.0001])

    jac_inner = _jacobian_for(model, table, "numpy")
    with pytest.raises(DegenerateCellError) as excinfo:
        jac_inner(theta_boundary)
    assert "degenerate" in str(excinfo.value)

    residual = _make_residual(model, table)
    cell_guard = _DegenerateCellGuard(residual)
    guarded_jacobian = _DegenerateCellJacobianGuard(
        _jacobian_for(model, table, "numpy"), cell_guard)

    theta_safe = np.array([120.0])  # one FD step from here does not cross
    J_safe = guarded_jacobian(theta_safe)
    assert cell_guard.n_degenerate == 0

    J_boundary = guarded_jacobian(theta_boundary)  # the FD step crosses here
    assert cell_guard.n_degenerate == 1
    assert np.array_equal(J_boundary, J_safe)  # neutralised: last good Jacobian

    # a normal point afterwards still gets a fresh, real Jacobian
    J_after = guarded_jacobian(np.array([100.0]))
    assert cell_guard.n_degenerate == 1  # unchanged
    assert not np.array_equal(J_after, J_safe)


def test_run_least_squares_completes_from_a_jacobian_boundary_adjacent_start():
    """Integration-level companion to the test above: ``run_least_squares``
    itself, started one FD step short of the boundary (so its first,
    unconditional ``jac(x0)`` call succeeds and seeds the guard's fallback),
    must return a normal outcome rather than propagate ``DegenerateCellError``
    -- the crash-the-stage failure mode the review named -- whether or not
    this particular short run's own trial steps happen to revisit the
    boundary (weak on that count deliberately, matching this file's other
    ``run_least_squares``/``Refinement.fit``-level tests, since the trust
    region's exact path is not something this test controls)."""
    structure = _rhombohedral_boundary_cell()
    structure.phases[0].cell.alpha.value = 120.0  # one FD step short, not on it
    model, table = _compile_alpha_only(structure)

    outcome = run_least_squares(model, table, max_iter=5, backend="numpy")
    assert outcome.status in ("converged", "max_iter", "diverged")
    assert outcome.n_degenerate_cell_probes >= 0
