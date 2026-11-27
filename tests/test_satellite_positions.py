"""Satellite positions at a real modulation vector q (WP-1993, N-W3a).

``satellite_positions`` gives the distinct positions Q = H + m·q of a phase,
one d per Laue orbit, at a q that may be incommensurate.  Each test below is
one arm that could fail:

* **the rational path is today's, bit for bit**: every rational k the WP-1326
  fixtures use, declared as a ``ModulationVector`` with a ``Fraction`` λ,
  returns exactly ``satellite_d_spacings``'s array (same values, same order);
  and the real path's merge, run with no free part, reproduces that array
  too, which is what verifies the merge the real path uses;
* **a real q against an independent enumeration**: NbTe₄, P4/mcc, q =
  (½, ½, γ) with γ = 0.691 (Dušek et al. 2001, pp. 402-403), positions to
  m = ±2 counted against a brute-force enumeration written here (the full
  integer grid, d = 1/√(QᵀG*Q), the 4/mmm orbit read off by hand), and the
  main reflections untouched;
* **the 1326 negative control still fails**: glide absences applied to the
  parents change the count, so the call never applies them;
* **the refusals**: a vector of numbers as q, ``lambdas=None``, ``lambdas`` of
  the wrong length, a signed or empty harmonic set.

Everything is synthetic; nothing here reads a vendored pattern.
"""

from __future__ import annotations

import inspect
import math
from fractions import Fraction

import gemmi
import numpy as np
import pytest

from rietx.crystallography.satellites import (
    _parent_grid,
    _position_orbits,
    _resolve,
    check_propagation_vector,
    lattice_two_theta,
    satellite_d_spacings,
    satellite_positions,
    satellite_reflections,
    zone_boundary_candidates,
)
from rietx.crystallography.superspace import ModulationVector
from rietx.crystallography.symmetry import generate_reflections

LAMBDA = 2.4067          # the WP-1326 tests' CW-neutron wavelength
CU_KA1 = 1.540593        # NbTe₄ was measured with Cu Kα₁ (Dušek et al. 2001, p. 402)

# ============================================== the WP-1326 fixtures, rational

#: every (group, cell, λ, 2θ window) the WP-1326 tests generate satellites on,
#: from ``tests/test_satellites.py`` and ``tests/test_satellites_acceptance.py``
FIXTURES = [
    ("P m m m", (4.0, 5.0, 6.0, 90, 90, 90), LAMBDA, (0.0, 110.0)),
    ("P m m m", (4.0, 5.0, 6.0, 90, 90, 90), LAMBDA, (10.0, 110.0)),
    ("P m -3 m", (4.0, 4.0, 4.0, 90, 90, 90), LAMBDA, (0.0, 110.0)),
    ("I 4/m m m", (4.0, 4.0, 6.0, 90, 90, 90), LAMBDA, (0.0, 110.0)),
    ("F m -3 m", (5.0, 5.0, 5.0, 90, 90, 90), LAMBDA, (0.0, 110.0)),
    ("R -3 c:H", (5.0, 5.0, 7.0, 90, 90, 120), LAMBDA, (0.0, 110.0)),
    ("C 2/m", (5.0, 6.0, 7.0, 90, 92, 90), LAMBDA, (0.0, 110.0)),
    ("P b c a", (5.0, 6.0, 7.0, 90, 90, 90), LAMBDA, (0.0, 110.0)),
    ("P 21/c", (5.0, 6.0, 7.0, 90, 95, 90), LAMBDA, (0.0, 110.0)),
    ("P 6_3 c m", (5.0, 5.0, 7.0, 90, 90, 120), LAMBDA, (0.0, 110.0)),
    ("P 1 21/c 1", (15.0, 10.0, 20.0, 90, 95, 90), 1.2, (8.0, 70.0)),
    ("P -3", (5.0, 5.0, 6.0, 90, 90, 120), 1.2, (8.0, 70.0)),
    ("C 2/m", (5.0, 6.0, 7.0, 90, 92, 90), 1.2, (8.0, 70.0)),
    ("P 42/m n m", (4.57539, 4.57539, 8.85381, 90, 90, 90), LAMBDA, (5.0, 110.0)),
    ("P -6 m 2", (5.6487, 5.6487, 14.4658, 90, 90, 120), LAMBDA, (4.0, 110.0)),
    ("F m m m", (5.0, 5.4, 5.8, 90, 90, 90), LAMBDA, (0.0, 110.0)),
    ("F m m m", (7.5083, 7.8315, 7.6841, 90, 90, 90), 1.227, (6.0, 125.7)),
]

#: the k the WP-1326 tests name beside each group's own zone-boundary set
NAMED_K = [(0, 0, "1/2"), ("1/2", "1/2", 0), ("1/2", "1/2", "1/2"),
           ("1/2", 0, 0), ("1/3", "1/3", 0), (1, 0, 0)]


def _rational_cases():
    for symbol, cell, lam, window in FIXTURES:
        seen = set()
        for k in [c.k for c in zone_boundary_candidates(symbol)] + NAMED_K:
            try:
                kk = check_propagation_vector(symbol, k)
            except ValueError:          # k ≡ 0 on this lattice: no satellites
                continue
            if kk not in seen:
                seen.add(kk)
                yield symbol, cell, lam, window, kk


RATIONAL_CASES = list(_rational_cases())


def _on_axis(kk, axis: int) -> tuple[ModulationVector, tuple[Fraction]]:
    """k as a λ fixed at a rational value on the line along ``axis``."""
    rational = tuple(Fraction(0) if i == axis else c for i, c in enumerate(kk))
    free = tuple(1 if i == axis else 0 for i in range(3))
    return ModulationVector(rational, (free,)), (kk[axis],)


def test_every_wp1326_k_is_bit_identical_through_the_exact_path():
    """Positive arm, the rational path: ``satellite_positions`` at
    ``harmonics=(1,)`` is ``satellite_d_spacings`` for that k, bit for bit,
    on every k the WP-1326 fixtures generate satellites at, and the line the
    k is declared on (x, y or z) changes nothing."""
    assert len(RATIONAL_CASES) == 133, len(RATIONAL_CASES)
    for i, (symbol, cell, lam, (lo, hi), kk) in enumerate(RATIONAL_CASES):
        for axis in range(3):
            line, values = _on_axis(kk, axis)
            assert line.value(*values) == kk
        line, values = _on_axis(kk, i % 3)
        got = satellite_positions(symbol, cell, lam, (lo, hi), line, values)
        want = satellite_d_spacings(symbol, cell, lam, hi, [kk], lo)[0]
        assert len(want) > 0, (symbol, kk)
        assert got.dtype == want.dtype and np.array_equal(got, want) \
            and got.tobytes() == want.tobytes(), (symbol, kk)


def test_a_line_off_the_axes_takes_the_same_exact_path():
    """(½, ½, 0) on the line (α, α, 0) at α = ½, and on (½, ½, γ) at γ = 0."""
    k = (Fraction(1, 2), Fraction(1, 2), Fraction(0))
    want = satellite_d_spacings("P m m m", (4.0, 5.0, 6.0, 90, 90, 90),
                                LAMBDA, 110.0, [k])[0]
    for q, lam in [("(α,α,0)", Fraction(1, 2)), ("(1/2,1/2,γ)", 0)]:
        got = satellite_positions("P m m m", (4.0, 5.0, 6.0, 90, 90, 90),
                                  LAMBDA, (0.0, 110.0), q, lam)
        assert got.tobytes() == want.tobytes(), q


def test_the_real_paths_merge_with_no_free_part_is_todays_merge():
    """Verification of the merge the real path uses: run with an exact q and
    the orders (1, −1), ``_position_orbits`` returns ``satellite_d_spacings``'s
    array bit for bit, on every WP-1326 case.  The real path adds only the
    free part's code to the same integer keys, so a merge that differed here
    would differ there."""
    grids: dict = {}
    for symbol, cell, lam, (lo, hi), kk in RATIONAL_CASES:
        sg = _resolve(symbol)
        key = (symbol, cell, lam, hi)
        if key not in grids:
            grids[key] = _parent_grid(sg, cell, lam, hi)
        got = _position_orbits(sg, cell, grids[key], kk, (), (), (1, -1),
                               lam, hi, lo)
        want = satellite_d_spacings(symbol, cell, lam, hi, [kk], lo)[0]
        assert got.tobytes() == want.tobytes(), (symbol, kk)


# ======================================================= NbTe₄, a real q

#: NbTe₄: P4/mcc(½,½,γ), γ = 0.691, a = 4.499, c = 6.837 Å (Dušek, Petříček,
#: Wunschel, Dinnebier & van Smaalen (2001). J. Appl. Cryst. 34, 398,
#: § 4.2, pp. 402-403); 5-140° 2θ is the range they measured with Cu Kα₁
NBTE4 = ("P 4/m c c", (4.499, 4.499, 6.837, 90.0, 90.0, 90.0))
NBTE4_Q = "(1/2,1/2,γ)"
GAMMA = 0.691
WINDOW = (5.0, 140.0)


def _metric_star(cell) -> np.ndarray:
    """G* = G⁻¹, with G the direct metric written out from the six numbers."""
    a, b, c, al, be, ga = cell
    ca, cb, cg = (math.cos(math.radians(x)) for x in (al, be, ga))
    g = np.array([[a * a, a * b * cg, a * c * cb],
                  [a * b * cg, b * b, b * c * ca],
                  [a * c * cb, b * c * ca, c * c]])
    return np.linalg.inv(g)


def _nbte4_brute_force(gamma: float, orders, *, glide_absences: bool = False):
    """The positions of H + m·(½, ½, γ) by hand: {orbit key: d}.

    H runs over the full integer grid (P lattice: every integer H is a
    reciprocal-lattice vector), d = 1/√(QᵀG*Q), and the orbit under the Laue
    group 4/mmm is read off the exact indices: 4/mmm permutes and negates
    Q_x and Q_y and negates Q_z, so (sorted |2Q_x|, |2Q_y|) and Q_z = l + mγ
    up to sign identify the orbit.  The window carries the generators'
    documented 0.1 % slack in d at each end (``satellite_reflections`` keeps
    d ≥ 0.999·d_min and d ≤ 1.001·d_max).  ``glide_absences=True`` drops
    every parent H the c glides of P4/mcc forbid (the naive generator).
    """
    gstar = _metric_star(NBTE4[1])
    lam = CU_KA1
    d_min = 0.999 * lam / (2 * math.sin(math.radians(WINDOW[1] / 2)))
    d_max = 1.001 * lam / (2 * math.sin(math.radians(WINDOW[0] / 2)))
    ops = gemmi.SpaceGroup(NBTE4[0]).operations()
    rng = range(-12, 13)
    out: dict = {}
    edge = []
    for h in rng:
        for k in rng:
            for ell in range(-16, 17):
                if glide_absences and ops.is_systematically_absent([h, k, ell]):
                    continue
                for m in orders:
                    qv = np.array([h + m / 2, k + m / 2, ell + m * gamma])
                    d = 1.0 / math.sqrt(qv @ gstar @ qv)
                    edge.append(min(abs(d / d_min - 1), abs(d / d_max - 1)))
                    if not d_min <= d <= d_max:
                        continue
                    z = max((ell, m), (-ell, -m))
                    key = (tuple(sorted((abs(2 * h + m), abs(2 * k + m)))), z)
                    out.setdefault(key, d)
    return out, min(edge)


def test_nbte4_positions_to_second_order_match_an_independent_enumeration():
    """Positive arm, a real q: NbTe₄ at γ = 0.691, m = ±1, ±2, 5-140° at
    Cu Kα₁.  The count of distinct positions and the d-spacings (the first
    ten quoted, all compared) agree with the brute force above."""
    got = satellite_positions(*NBTE4, CU_KA1, WINDOW, NBTE4_Q, (GAMMA,),
                              harmonics=(1, 2))
    ref, edge = _nbte4_brute_force(GAMMA, (1, -1, 2, -2))
    # nothing sits within 1e-6 of the window's ends, so rounding cannot
    # decide the count
    assert edge > 1e-6, edge
    want = np.sort(np.array(list(ref.values())))[::-1]
    assert len(got) == len(want) == 356, (len(got), len(want))
    np.testing.assert_allclose(got[:10], [
        11.063107, 6.114756, 5.351573, 4.947178, 4.363261,
        4.225587, 4.167567, 4.037033, 3.412456, 3.328466], atol=5e-7)
    np.testing.assert_allclose(got, want, rtol=1e-12, atol=0)
    # first order alone is the m = ±1 half of the same enumeration
    first = satellite_positions(*NBTE4, CU_KA1, WINDOW, NBTE4_Q, GAMMA)
    ref1, _ = _nbte4_brute_force(GAMMA, (1, -1))
    assert len(first) == len(ref1) == 156
    np.testing.assert_allclose(
        first, np.sort(np.array(list(ref1.values())))[::-1], rtol=1e-12, atol=0)


def test_nbte4_leaves_the_main_reflections_untouched():
    """No (h k l 0) change: the main reflections of the phase are the same
    array after the call, and no satellite position lands on one."""
    before = generate_reflections(NBTE4[0], NBTE4[1], CU_KA1, WINDOW[1], WINDOW[0])
    got = satellite_positions(*NBTE4, CU_KA1, WINDOW, NBTE4_Q, GAMMA,
                              harmonics=(1, 2))
    after = generate_reflections(NBTE4[0], NBTE4[1], CU_KA1, WINDOW[1], WINDOW[0])
    assert before.d.tobytes() == after.d.tobytes()
    assert before.hkl.tobytes() == after.hkl.tobytes()
    # the nearest satellite is 4.1e-5 in d from a main line (measured): close,
    # since γ is a float, but no position is a main reflection
    gap = np.min(np.abs(got[:, None] / before.d[None, :] - 1.0))
    assert gap > 1e-6, gap


def test_the_real_path_meets_the_exact_path_at_a_rational_value():
    """γ = 0.691 as a float (real path) and as Fraction(691, 1000) (exact
    path) are the same positions: no coincidence is special to 691/1000."""
    for harmonics in [(1,), (1, 2), (2,)]:
        real = satellite_positions(*NBTE4, CU_KA1, WINDOW, NBTE4_Q, GAMMA,
                                   harmonics=harmonics)
        exact = satellite_positions(*NBTE4, CU_KA1, WINDOW, NBTE4_Q,
                                    Fraction(691, 1000), harmonics=harmonics)
        assert len(real) == len(exact), harmonics
        np.testing.assert_allclose(real, exact, rtol=1e-12, atol=0)


def test_two_free_parameters_on_a_hexagonal_cell():
    """q = (α, β, 0) on P 6_3 c m: the real path merges only under the
    operations that keep both free directions, and must still meet the exact
    path at a rational point."""
    cell = (5.0, 5.0, 7.0, 90, 90, 120)
    real = satellite_positions("P 6_3 c m", cell, LAMBDA, (5.0, 110.0),
                               "(α,β,0)", (0.231, 0.117))
    exact = satellite_positions("P 6_3 c m", cell, LAMBDA, (5.0, 110.0),
                                "(α,β,0)", (Fraction(231, 1000), Fraction(117, 1000)))
    assert len(real) == len(exact) > 0
    np.testing.assert_allclose(real, exact, rtol=1e-12, atol=0)


@pytest.mark.parametrize("symbol", ["P 6/m m m", "P 6_3 c m", "P -3"])
def test_the_free_part_moves_by_r_transpose_on_a_hexagonal_cell(symbol):
    """q = (α, 0, 0) on a hexagonal cell, where Rᵀ and R keep different
    operations on the line: the real path's merge of the free part must agree
    with the exact path's, which codes the whole of Q through Rᵀ."""
    cell = (5.0, 5.0, 7.0, 90, 90, 120)
    real = satellite_positions(symbol, cell, LAMBDA, (5.0, 110.0), "(α,0,0)",
                               0.231, harmonics=(1, 2))
    exact = satellite_positions(symbol, cell, LAMBDA, (5.0, 110.0), "(α,0,0)",
                                Fraction(231, 1000), harmonics=(1, 2))
    assert len(real) == len(exact) > 0, (len(real), len(exact))
    np.testing.assert_allclose(real, exact, rtol=1e-12, atol=0)


def test_a_q_outside_the_first_cell_gives_the_same_positions():
    """γ = 2.3 and −1.7 are γ = 0.3 shifted by lattice vectors (0, 0, 2) and
    (0, 0, −2): the same positions, which the parent grid reaches only by
    widening for |m·q_i| up to 6.9 at m = 3."""
    args = ("P m m m", (4.0, 5.0, 6.0, 90, 90, 90), LAMBDA, (5.0, 110.0), "(0,0,γ)")
    ref = satellite_positions(*args, 0.3, harmonics=(1, 2, 3))
    assert len(ref) > 0
    for gamma in (2.3, -1.7, Fraction(23, 10)):
        got = satellite_positions(*args, gamma, harmonics=(1, 2, 3))
        assert len(got) == len(ref), (gamma, len(got), len(ref))
        np.testing.assert_allclose(got, ref, rtol=1e-12, atol=0)


# ====================================================== negative controls


def test_the_1326_control_still_fails_and_the_call_never_applies_glides():
    """The planted error (glide and screw absences applied to satellites)
    still loses satellites on P b c a at k = (0, 0, ½), 41 against 51; the
    call has no such switch and returns the correct 51."""
    cell = (5.0, 6.0, 7.0, 90.0, 90.0, 90.0)
    args = ("P b c a", cell, LAMBDA, 110.0, (0, 0, "1/2"))
    naive = satellite_reflections(*args, apply_structure_absences=True)
    correct = satellite_reflections(*args)
    assert (len(naive), len(correct)) == (41, 51)
    got = satellite_positions("P b c a", cell, LAMBDA, (0.0, 110.0), "(0,0,γ)",
                              Fraction(1, 2))
    assert len(got) == len(correct)
    assert "absence" not in " ".join(inspect.signature(satellite_positions).parameters)


def test_glide_absences_on_the_parents_change_the_nbte4_count():
    """The same control on the real q: P4/mcc's c glides, applied to H, drop
    positions the brute force without them keeps, so a generator that applied
    them would fail the enumeration test above."""
    naive, _ = _nbte4_brute_force(GAMMA, (1, -1, 2, -2), glide_absences=True)
    got = satellite_positions(*NBTE4, CU_KA1, WINDOW, NBTE4_Q, GAMMA,
                              harmonics=(1, 2))
    assert len(naive) < len(got), (len(naive), len(got))


# ============================================================ the refusals


@pytest.mark.parametrize("q", [(0.5, 0.5, 0.691), np.array([0.5, 0.5, 0.691]),
                               (Fraction(1, 2), Fraction(1, 2), Fraction(691, 1000))])
def test_a_vector_of_numbers_as_q_is_refused_by_name(q):
    """The likeliest misuse: q passed as three numbers.  Refused before any
    work, naming the declared form and the commensurate entry point."""
    with pytest.raises(TypeError, match=r"ModulationVector\.parse.*satellite_reflections"):
        satellite_positions(*NBTE4, CU_KA1, WINDOW, q, (GAMMA,))


def test_text_without_a_free_direction_is_refused_by_name():
    with pytest.raises(ValueError, match="satellite_reflections"):
        satellite_positions(*NBTE4, CU_KA1, WINDOW, "(1/2,1/2,0.691)", (GAMMA,))


def test_the_values_on_the_line_are_declared_not_inferred():
    with pytest.raises(ValueError, match="lambdas=None"):
        satellite_positions(*NBTE4, CU_KA1, WINDOW, NBTE4_Q)
    with pytest.raises(ValueError, match="1 free parameter.*2 value"):
        satellite_positions(*NBTE4, CU_KA1, WINDOW, NBTE4_Q, (GAMMA, 0.1))
    with pytest.raises(ValueError, match="2 free parameter.*1 value"):
        satellite_positions(*NBTE4, CU_KA1, WINDOW, "(α,β,0)", (0.2,))
    with pytest.raises(TypeError, match="not a real number"):
        satellite_positions(*NBTE4, CU_KA1, WINDOW, NBTE4_Q, ("0.691",))
    with pytest.raises(ValueError, match="not finite"):
        satellite_positions(*NBTE4, CU_KA1, WINDOW, NBTE4_Q, (float("nan"),))


@pytest.mark.parametrize("harmonics", [(1, -1), (0,), (), (1.0,)])
def test_harmonics_are_a_declared_set_of_positive_orders(harmonics):
    """(1, −1) is the likeliest slip (the orders, not |m|): refused, saying
    both signs are taken."""
    with pytest.raises(ValueError, match="both signs"):
        satellite_positions(*NBTE4, CU_KA1, WINDOW, NBTE4_Q, GAMMA,
                            harmonics=harmonics)


@pytest.mark.parametrize("window", [(140.0, 5.0), (5.0, 190.0), 140.0])
def test_a_window_the_call_cannot_honour_is_refused(window):
    with pytest.raises(ValueError, match="two_theta_range"):
        satellite_positions(*NBTE4, CU_KA1, window, NBTE4_Q, GAMMA)


def test_k_equal_to_zero_is_refused_on_the_exact_path():
    """γ = 0 on (0, 0, γ) is k = 0, refused as ``satellite_reflections``
    refuses it, at every harmonic set."""
    for harmonics in [(1,), (1, 2)]:
        with pytest.raises(ValueError, match="k = 0"):
            satellite_positions("P m m m", (4.0, 5.0, 6.0, 90, 90, 90), LAMBDA,
                                (0.0, 110.0), "(0,0,γ)", 0, harmonics=harmonics)


# ================================================ what a declaration means


def test_a_float_at_a_commensurate_value_is_read_as_generic():
    """λ = 0.5 as a float keeps H + q and H′ − q apart, which coincide at ½;
    the same value as a Fraction merges them.  Same positions, counted once
    per orbit only on the exact path: the docstring's advice, measured."""
    args = ("P m m m", (4.0, 5.0, 6.0, 90, 90, 90), LAMBDA, (0.0, 110.0), "(0,0,γ)")
    real = satellite_positions(*args, 0.5)
    exact = satellite_positions(*args, Fraction(1, 2))
    assert (len(real), len(exact)) == (64, 32)
    np.testing.assert_array_equal(np.unique(np.round(real, 9)),
                                  np.unique(np.round(exact, 9)))


def test_a_harmonic_whose_mq_is_a_lattice_vector_sits_on_the_lattice_points():
    """k = (0, 0, ½), m = 2: 2k = (0, 0, 1) is in L*, so the second order is
    every reciprocal-lattice point but the origin, as the k-grid reads it
    (``indexing/kvector.py`` takes ``lattice_two_theta`` for such an order)."""
    cell = (4.0, 5.0, 6.0, 90, 90, 90)
    got = satellite_positions("P m m m", cell, LAMBDA, (0.0, 110.0), "(0,0,γ)",
                              Fraction(1, 2), harmonics=(2,))
    tt = np.degrees(2 * np.arcsin(LAMBDA / (2 * got)))
    np.testing.assert_array_equal(
        np.unique(np.round(tt, 9)),
        lattice_two_theta("P m m m", cell, LAMBDA, 110.0))
    both = satellite_positions("P m m m", cell, LAMBDA, (0.0, 110.0), "(0,0,γ)",
                               Fraction(1, 2), harmonics=(1, 2))
    first = satellite_positions("P m m m", cell, LAMBDA, (0.0, 110.0), "(0,0,γ)",
                                Fraction(1, 2))
    assert len(both) == len(first) + len(got)
