"""``MOMENT_PAIR_DEGENERATE`` on a ``solve_magnetic`` solution names its class (#742).

The solution lists the pairs of every class of every k tried, and a pair's
``where`` is two parameter paths that two classes share, so without the class a
pair found for a rival is indistinguishable from the winner's.
"""

from __future__ import annotations

import pytest

import rietx as rx
from rietx.schemas.common import Diagnostic
from rietx.schemas.structure import MagneticSymmetry, Moment


def _pair() -> Diagnostic:
    return Diagnostic(level="info", code="MOMENT_PAIR_DEGENERATE",
                      message="a and b are a powder-degenerate moment pair",
                      where=["phases.0.atoms.0.moment.dof0",
                             "phases.0.atoms.1.moment.dof0"], value=3.5)


def test_the_message_opens_with_the_class_and_nothing_else_moves():
    from rietx.strategy.magnetic import _named_for_class

    (named,) = _named_for_class([_pair()], 2, (0, 0, 0))
    assert named.message.startswith("class 2: a and b are")
    assert named.where == _pair().where and named.value == 3.5
    assert named.code == "MOMENT_PAIR_DEGENERATE"


def test_a_propagation_vector_off_gamma_is_named_too():
    from rietx.strategy.magnetic import _named_for_class

    (named,) = _named_for_class([_pair()], 0, (0.5, 0, 0.5))
    assert named.message.startswith("class 0 (k = (0.5, 0, 0.5)): ")


@pytest.mark.slow
@pytest.mark.xdist_group("magnetic-solve-two-site")
def test_the_two_site_winner_measures_the_sum_and_difference(monkeypatch):
    """The two-site Pnma set of ``test_magnetic_solve``, which carried this
    file's end-to-end naming check until WP-1930 showed both its pairs were
    stopping points.

    Mn1 (4b) and Mn2 (4a) are related by c/2, so l-even and l-odd reflections
    measure m₁ + m₂ and m₁ − m₂ separately.  Swapping the two moduli leaves
    the size of each combination unchanged.  The swapped point is a second
    minimum, χ² higher by only 0.66 (2556.51 against 2555.85, macOS arm64).  The flat start lands on it
    under both drivers since the floor seed went (WP-1938 D4), so the sweep
    reports two minima, and either assignment may win until the tie row lands
    (#1424): the test asserts the sum and the difference, which are the same
    for both.
    Under LM the released starts reach it only because the moduli climb before
    the angles turn (D12): freed together, they stopped at χ² 454 660.

    Both moments lie along **a**, where the pattern is even in every angle, so
    the angle columns vanish there.  Before WP-1929 the covariance kept them,
    equilibrated to unit norm, and how far from **a** the solver stopped
    decided the moduli esds and ρ.  Issue #820 measured ρ at −0.962 on one
    macOS venv and −0.498 on Linux, either side of ``MOMENT_PAIR_RHO_MIN``.
    Under LM on macOS arm64 the esds were 0.031 and 0.159 μ_B, and the pair
    was named.  The stationary-angle test now leaves the four angle columns out
    at the winner's stop, so the moduli esds are 0.00150 and 0.00111 μ_B with
    ρ −0.24 (the three class-0 stops of WP-1929's measurement read
    0.00150-0.00151 and 0.00111-0.00112), and no pair is named.

    Class 2, the flat model, is still a stopping point, so nothing is asserted
    about it.  On macOS arm64 and on Intel Xeon CI runners all three of its
    starts stopped at m ≈ 0 under TRF.  On AMD EPYC 7763 runners two of the
    three reached m₁ ≈ m₂ ≈ 0.097 and named the pair: the runner's CPU decided
    (#865).
    """
    from rietx.strategy import magnetic as solve
    from tests import test_magnetic_solve as T

    # ρ is read from the covariance the pair fold reads, keyed by the result
    # it was taken from, so the winner's own is the one asserted
    taken: dict[int, list] = {}
    measure = solve._moment_correlations

    def recorded(ref, result):
        pairs = measure(ref, result)
        taken[id(result)] = pairs or []
        return pairs

    monkeypatch.setattr(solve, "_moment_correlations", recorded)

    instrument = T.neutron()
    truth = T.candidate_named("P n m a", T.MN_SITE, (0, 0, 0), T.A_TYPE_BNS)
    ops, cent = truth.group.xyz_strings()
    # Drawn by ``predict`` at the closing windows, where the winner's closing
    # stage measures it (WP-2002).  Without that stage the window misfit
    # inflated both esds by the same 1.61 (0.00242 and 0.00179).
    data = T.simulate(T.two_site(
        m1=Moment.from_values((3.5, 0.0, 0.0), "Mn3+"),
        m2=Moment.from_values((0.7, 0.0, 0.0), "Mn3+"),
        magnetic=MagneticSymmetry(operations=list(ops),
                                  centerings=list(cent))), instrument)
    ref = T.nuclear_fit(T.two_site(), data, instrument)
    solution = rx.solve_magnetic(ref, data, sites=["Mn1", "Mn2"], ion="Mn3+")

    winner = next(t for t in solution.trials if t.class_index == 0)
    assert solution.best is not None and solution.best.class_index == 0
    m1, m2 = winner.moments
    # What the pattern measures is m1 + m2 and m1 - m2 (Mn1 and Mn2 are
    # related by c/2); the two moduli swapped is a second minimum within the
    # tie width (#1424), so no site's modulus is asserted alone.  Signed along
    # a, where both moments lie, so a flipped relative sign (3.5, -0.7) fails.
    a1, a2 = m1.crystalaxis[0], m2.crystalaxis[0]
    assert abs(a1 + a2) == pytest.approx(4.20, abs=0.02)
    assert abs(a1 - a2) == pytest.approx(2.80, abs=0.02)
    # both assignments are on the record (#1424, D8's machinery): the two
    # one-site starts end on opposite sites, and every start is in one of
    # them, the winner's first
    assert winner.n_minima == len(winner.minima) == 2, winner.minima
    first, second = (dict(x.moduli) for x in winner.minima)
    for moduli in (first, second):
        assert sorted(moduli.values()) == pytest.approx([0.70, 3.50], abs=0.02)
    assert (first["Mn1"] > first["Mn2"]) != (second["Mn1"] > second["Mn2"])
    assert sorted(s for x in winner.minima for s in x.starts) == sorted(
        ["flat", "Mn1 only, then released", "Mn2 only, then released"])
    assert winner.minima[0].starts[0] == winner.start
    assert winner.minima[0].chi2 <= winner.minima[1].chi2
    assert any("class 0:" in c and "2 distinct minima" in c
               for c in solution.caveats), solution.caveats
    # esds and rho matched by size, not by site
    assert sorted(r.esd for r in winner.moments) == pytest.approx(
        [0.00111, 0.00150], rel=0.05)
    assert not any(row.paired_with for row in winner.moments)
    (pair,) = taken[id(winner._result)]
    assert pair.rho == pytest.approx(-0.24, abs=0.02)
    # the record that moved them: the winner's last stage left its four
    # angle columns out, and the solution says so through the fit's own code
    stage = winner._result.stages[-1]
    (passed,) = [t for t in stage.moment_angle_tests if t.zeroed]
    assert len(passed.paths) == 4 and passed.statistic <= passed.cut
    assert "MOMENT_ANGLE_STATIONARY" in {d.code for d in winner._result.diagnostics}


def _start(label, chi2_red, n_free, rwp, moduli):
    """A constructed start: its statistics, and a fitted structure carrying
    a moment along **a** of each given size on an orthorhombic cell."""
    from types import SimpleNamespace as NS

    stats = NS(chi2=chi2_red, n_points=1000, n_free_parameters=n_free, rwp=rwp)
    cell = NS(**{k: NS(value=v) for k, v in zip(
        ("a", "b", "c", "alpha", "beta", "gamma"),
        (5.74, 7.70, 5.54, 90.0, 90.0, 90.0))})
    atoms = [NS(label=site, moment=Moment.from_values((m, 0.0, 0.0), "Mn3+"))
             for site, m in moduli.items()]
    atoms.append(NS(label="O1", moment=None))
    structure = NS(phases=[NS(cell=cell, atoms=atoms)])
    return (label, NS(fitted_structure=structure), NS(statistics=stats))


def test_best_start_picks_the_lowest_absolute_chi2_not_the_lowest_rwp():
    """``_best_start`` ranks starts by absolute weighted chi², the quantity the
    ranking compares (#1424).  Constructed starts, where the lowest Rwp and the
    lowest chi² disagree, so a pick by ``rwp``, by reduced chi² or by list order
    fails."""
    from rietx.strategy import magnetic as solve

    # absolute chi²: 1.0*990 = 990, 1.0005*990 = 990.495, 1.002*980 = 981.96;
    # the truth start has the highest reduced chi² and the highest Rwp, so a
    # pick by either (or by list order) fails
    flat = _start("flat", 1.0, 10, 0.050, {"Mn1": 0.70, "Mn2": 3.50})
    swap = _start("swap", 1.0005, 10, 0.040, {"Mn1": 0.701, "Mn2": 3.499})
    truth = _start("truth", 1.002, 20, 0.060, {"Mn1": 3.50, "Mn2": 0.70})
    best, n, minima = solve._best_start([flat, swap, truth])
    assert best[0] == "truth" and n == 3
    # two minima, lowest chi² first, each named by the starts that reached it
    assert [m.starts for m in minima] == [("truth",), ("flat", "swap")]
    assert [m.chi2 for m in minima] == pytest.approx([981.96, 990.0])
    assert dict(minima[0].moduli) == pytest.approx({"Mn1": 3.50, "Mn2": 0.70})
    assert dict(minima[1].moduli) == pytest.approx({"Mn1": 0.70, "Mn2": 3.50})
    best, _, _ = solve._best_start([truth, swap, flat])
    assert best[0] == "truth"


def test_distinct_minima_are_counted_by_moduli_not_by_rwp():
    """D8's machinery (#1424): two starts are one minimum when every site's
    |m| agrees to ``SOLVE_MINIMUM_MODULUS_RTOL`` of the largest, whatever
    their Rwp.  The swapped assignment at one Rwp is two minima, which the
    Rwp test this replaced counted as one; one minimum reached at two Rwp is
    one, which it counted as two; and moments the fit removed are one
    minimum whatever digit each stopped on."""
    from rietx.schemas.structure import MOMENT_FLOOR_MU_B
    from rietx.strategy import magnetic as solve

    rtol = solve.SOLVE_MINIMUM_MODULUS_RTOL

    def count(*moduli, rwps=None):
        starts = [_start(f"s{i}", 1.0 + 1e-3 * i, 10,
                         (rwps or [0.05] * len(moduli))[i], m)
                  for i, m in enumerate(moduli)]
        return [m.starts for m in solve._best_start(starts)[2]]

    truth, swap = {"Mn1": 3.5, "Mn2": 0.7}, {"Mn1": 0.7, "Mn2": 3.5}
    # the swap at one Rwp: two minima
    assert count(truth, swap) == [("s0",), ("s1",)]
    # one minimum at Rwp 2 % apart: one
    assert count(truth, {"Mn1": 3.49, "Mn2": 0.71},
                 rwps=[0.050, 0.051]) == [("s0", "s1")]
    # the tolerance is the boundary, read against the largest |m|
    step = rtol * 3.5
    assert count(truth, {"Mn1": 3.5, "Mn2": 0.7 + 0.9 * step}) == [("s0", "s1")]
    assert count(truth, {"Mn1": 3.5, "Mn2": 0.7 + 1.1 * step}) == [("s0",), ("s1",)]
    # the tolerance is read against the largest |m|, so a weak site beside a
    # strong one cannot separate two minima by itself: 0.3 against 0.6 beside
    # 3.5 differs by 0.3, under 0.1 * 3.5, and counts as one (the documented
    # limit in the constant's comment, not a measured property of real data)
    assert count({"Mn1": 3.5, "Mn2": 0.3},
                 {"Mn1": 3.5, "Mn2": 0.6}) == [("s0", "s1")]
    # two removed moments are one minimum; a removed and a kept one are two
    floor = MOMENT_FLOOR_MU_B
    assert count({"Mn1": 0.2 * floor, "Mn2": 0.0},
                 {"Mn1": 0.9 * floor, "Mn2": 0.5 * floor}) == [("s0", "s1")]
    assert count({"Mn1": 0.0, "Mn2": 0.0},
                 {"Mn1": 0.3, "Mn2": 0.0}) == [("s0",), ("s1",)]
    # a later start joins the minimum whose best start it matches, not the
    # minimum it happens to follow
    assert count(truth, swap, {"Mn1": 3.49, "Mn2": 0.70}) == [("s0", "s2"), ("s1",)]
