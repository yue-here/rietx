"""WP-1020 — reduction, Bravais determination, dedup, and ambiguity.

The two property tests here are the WP's acceptance criteria: Niggli reduction
must be **idempotent** and **unimodular-invariant** on hypothesis-generated cells,
because every downstream comparison (dedup, ambiguity, "is this the parent in a
different setting") is stated in terms of the reduced form.  If reduction is not
canonical, none of those questions is well posed.

The rest are about refusals: symmetry that appears only at a loose tolerance is
reported ambiguous rather than claimed, and a derivative lattice that explains the
data as well as the parent is reported as a partner with the reflections that would
break the tie.
"""

from __future__ import annotations

import subprocess
import sys

import numpy as np
import pytest
from hypothesis import HealthCheck, assume, example, given, settings
from hypothesis import strategies as st

from rietx.crystallography.lattice import cell_volume
from rietx.indexing.ambiguity import (
    AMBIGUITY_EXTEND_FACTOR,
    MAX_AMBIGUITY_INDEX,
    SUPERCELL_CHANCE_ALPHA,
    _derivative_transform,
    ambiguity_partners,
    chance_rate,
    derivative_cells,
    hnf_matrices,
    lattice_point_group,
    supercell_chance,
    transform_cell,
    uncancellable,
)
from rietx.indexing.qspace import af_from_cell
from rietx.indexing.reduce import (
    BRAVAIS_OBLIQUITIES,
    CELL_EQUALITY_CHI2,
    SYSTEM_RANK,
    bravais_screen,
    cell_from_vectors,
    conventional_cell,
    equal_reduced,
    lattice_vectors,
    reduce_cell,
    reduced_af,
    reduction,
    same_lattice,
)
from rietx.schemas.indexing import q_esd_of_two_theta

LAM = 1.5405929

lengths = st.floats(min_value=3.0, max_value=25.0, allow_nan=False)
angles = st.floats(min_value=65.0, max_value=115.0, allow_nan=False)


def _valid(cell) -> bool:
    """Is this parameter set a real lattice?  Angle triples are not free."""
    try:
        return float(cell_volume(*cell)) > 1.0
    except (ValueError, np.linalg.LinAlgError):
        return False


def _unimodular(rng: np.random.Generator, n: int = 4) -> np.ndarray:
    """A random integer matrix with |det| = 1, as a product of shears."""
    m = np.eye(3, dtype=np.int64)
    for _ in range(n):
        i, j = rng.choice(3, size=2, replace=False)
        e = np.eye(3, dtype=np.int64)
        e[i, j] = int(rng.integers(-2, 3))
        m = m @ e
    return m


# ----------------------------------------------------------------------
# Reduction is canonical
# ----------------------------------------------------------------------
@settings(max_examples=60, deadline=None,
          suppress_health_check=[HealthCheck.filter_too_much])
@given(lengths, lengths, lengths, angles, angles, angles)
def test_niggli_reduction_is_idempotent(a, b, c, al, be, ga):
    """``niggli(niggli(C)) == niggli(C)`` — reduction reaches a fixed point."""
    cell = (a, b, c, al, be, ga)
    assume(_valid(cell))
    once = reduce_cell(cell)
    twice = reduce_cell(once.cell)
    assert np.allclose(twice.cell, once.cell, atol=1e-6)
    assert np.allclose(reduce_cell(twice.cell).cell, once.cell, atol=1e-6)


@settings(max_examples=40, deadline=None,
          suppress_health_check=[HealthCheck.filter_too_much])
@given(lengths, lengths, lengths, angles, angles, angles,
       st.integers(min_value=0, max_value=2 ** 32 - 1))
def test_niggli_reduction_is_unimodular_invariant(a, b, c, al, be, ga, seed):
    """A change of basis is not a change of lattice.

    This is what makes every downstream question well posed: dedup asks whether
    two candidates reduce to the same cell, and ambiguity asks about the ones that
    *do not*.  If reduction depended on the setting, both would be noise.
    """
    cell = (a, b, c, al, be, ga)
    assume(_valid(cell))
    rng = np.random.default_rng(seed)
    t = _unimodular(rng)
    assume(abs(round(float(np.linalg.det(t)))) == 1)
    other = transform_cell(cell, t)
    assume(_valid(other))

    want = reduce_cell(cell).cell
    got = reduce_cell(other).cell
    assert np.allclose(got, want, atol=1e-4), f"{cell} vs {other}: {got} != {want}"


def test_already_reduced_is_gemmis_predicate_and_not_a_fixed_point_test():
    """A caveat worth pinning, because the field invites the wrong reading.

    ``already_reduced`` is gemmi's own ``is_niggli``, and on floating-point input
    it can be False for a cell whose reduction changes nothing: measured on
    (3, 3, 3, 65°, 65°, 65°), where the reduced parameters carry ~1e-15 noise the
    predicate's tolerance does not absorb.  Idempotence is therefore asserted on
    the parameters, never on this flag.
    """
    cell = (3.0, 3.0, 3.0, 65.0, 65.0, 65.0)
    once = reduce_cell(cell)
    twice = reduce_cell(once.cell)
    assert np.allclose(twice.cell, once.cell, atol=1e-9)
    assert twice.already_reduced is False


def test_delaunay_reduction_is_available_and_distinct():
    """Both reductions exist and are the dependency's, not ours."""
    cell = (8.875, 16.408, 7.137, 90.0, 93.84, 90.0)
    niggli = reduce_cell(cell, kind="niggli")
    delaunay = reduce_cell(cell, kind="delaunay")
    assert niggli.kind == "niggli" and delaunay.kind == "delaunay"
    assert float(cell_volume(*niggli.cell)) == pytest.approx(
        float(cell_volume(*cell)), rel=1e-9)
    assert float(cell_volume(*delaunay.cell)) == pytest.approx(
        float(cell_volume(*cell)), rel=1e-9)
    with pytest.raises(ValueError, match="niggli"):
        reduce_cell(cell, kind="buerger")


def test_lattice_vectors_round_trip():
    cell = (7.0, 8.0, 9.0, 85.0, 95.0, 100.0)
    assert np.allclose(cell_from_vectors(lattice_vectors(cell)), cell, rtol=1e-12)


# ----------------------------------------------------------------------
# Bravais: two opinions, swept
# ----------------------------------------------------------------------
def test_high_symmetry_is_stable_across_the_sweep():
    screen = bravais_screen((4.1566,) * 3 + (90.0,) * 3, cell_esd=1e-4)
    assert screen.system == "cubic"
    assert not screen.ambiguous
    assert not screen.methods_disagree
    assert set(screen.by_obliquity.values()) == {"cubic"}


def test_pseudosymmetry_is_reported_ambiguous_not_claimed():
    """A 1 % tetragonal distortion looks cubic to a loose obliquity and not to a
    tight one.  The answer is the *stable* one, plus a flag — the same refusal
    ``direction="both"`` makes for a sequential trajectory."""
    screen = bravais_screen((4.1566, 4.1566, 4.20, 90.0, 90.0, 90.0),
                            cell_esd=1e-3)
    assert screen.system == "tetragonal"
    assert screen.system_loosest == "cubic"
    assert screen.ambiguous
    assert SYSTEM_RANK[screen.system_loosest] > SYSTEM_RANK[screen.system]


def test_symmetry_is_monotone_in_the_tolerance():
    """Loosening a tolerance can only *add* symmetry — the property that makes
    "stable across the sweep" equal to "the tightest tolerance's answer"."""
    for cell in ((4.1566, 4.1566, 4.20, 90.0, 90.0, 90.0),
                 (7.0, 7.05, 9.0, 90.0, 90.2, 90.0),
                 (5.0, 5.0, 5.0, 89.5, 90.0, 90.0)):
        screen = bravais_screen(cell, cell_esd=1e-3)
        ranks = [SYSTEM_RANK[screen.by_obliquity[t]]
                 for t in sorted(BRAVAIS_OBLIQUITIES)]
        assert ranks == sorted(ranks), f"{cell}: {screen.by_obliquity}"


def test_conventional_cell_recovers_a_centred_lattice():
    """The piece a reduced cell cannot give: a primitive bcc cell *is* cubic I.

    An engine that finds the primitive rhombohedral-looking cell must report the
    conventional one, or the answer looks like a different lattice from the one in
    every database.
    """
    prim = (3.6, 3.6, 3.6, 109.4712206, 109.4712206, 109.4712206)
    conv, centring, symbol = conventional_cell(prim)
    assert centring == "I"
    assert symbol.startswith("Im-3m")
    assert conv[0] == pytest.approx(conv[1]) == pytest.approx(conv[2])
    assert conv[3] == pytest.approx(90.0, abs=1e-6)
    # the conventional cell has twice the volume — two lattice points
    assert float(cell_volume(*conv)) == pytest.approx(
        2.0 * float(cell_volume(*prim)), rel=1e-6)


#: The two fallbacks of ``reduce.py`` that read spglib's ``None``, each with
#: the call that reaches it and what it must answer when spglib declines.
#: ``conventional_cell`` returns the cell unchanged under ``P`` with no symbol;
#: ``bravais_screen`` falls back to ``triclinic`` with no symbol at every
#: tolerance of its sweep.  A cell of 1e-4 Å is the degenerate input measured in
#: Yue's review of #389 — spglib's spacegroup search fails on it either way, so
#: the *only* thing this pair of runs varies is the error mode.
_SPGLIB_REFUSAL_PROBE = """
import spgrep                                   # flips OLD_ERROR_HANDLING False
import spglib.error
from rietx.indexing.reduce import bravais_screen, conventional_cell

assert spglib.error.OLD_ERROR_HANDLING is False, "spgrep no longer flips the flag"
degenerate = (1e-4,) * 3 + (90.0, 90.0, 90.0)
cell, centring, symbol = conventional_cell(degenerate)
assert cell == degenerate and centring == "P" and symbol == "", (cell, centring, symbol)
screen = bravais_screen(degenerate, cell_esd=1e-6)
assert set(screen.by_symprec.values()) == {"triclinic"}, screen.by_symprec
assert set(screen.spglib_symbols.values()) == {""}, screen.spglib_symbols
print("OK")
"""


def test_the_spglib_fallbacks_survive_a_process_that_imported_spgrep():
    """``reduce.py``'s ``data is None`` fallbacks must be reachable either way (#389 §2).

    ``spglib.error.OLD_ERROR_HANDLING`` is a **process-global** flag, and
    ``spgrep/__init__.py`` (0.7.0) sets it ``False`` at import and never puts it
    back.  In that mode spglib *raises* ``SpglibError`` where it used to return
    ``None``, so both of this module's documented fallbacks became unreachable
    in any process that imported spgrep — which, since #389 puts spgrep in
    ``[dev]`` and in CI, is every dev environment.  Measured in the review:

    * ``conventional_cell((1e-4,) * 3 + (90, 90, 90))`` gave
      ``((1e-4, 1e-4, 1e-4, 90, 90, 90), "P", "")`` before the import, and
      ``SpglibCppError: spacegroup search failed`` after it.

    The run is a **subprocess** on purpose: the import is what flips the flag,
    it happens once per process, and ``tests/conftest.py`` puts spglib's own
    default back around every test — so no in-process test can show the
    reported state without setting the flag by hand, which is the one thing
    that would not prove the import still causes it.
    """
    pytest.importorskip("spgrep")            # the oracle whose import flips it
    done = subprocess.run([sys.executable, "-c", _SPGLIB_REFUSAL_PROBE],
                          capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip().endswith("OK")


# ----------------------------------------------------------------------
# Dedup
# ----------------------------------------------------------------------
def test_same_lattice_sees_through_a_setting_change():
    cell = (7.0, 8.0, 9.0, 85.0, 95.0, 100.0)
    other = transform_cell(cell, np.array([[1, 1, 0], [0, 1, 0], [0, 0, 1]]))
    equal, chi2 = same_lattice(af_from_cell(cell), af_from_cell(other))
    assert equal
    assert np.isnan(chi2)          # the covariance-free fallback ran


def test_symmetry_zero_components_at_rounding_level_do_not_split_a_lattice():
    """A monoclinic reduced D, E is zero; M·G·Mᵀ returns it as ~1e-18 noise of
    either sign (WP-2035), which a purely relative test calls a difference —
    the two settings of one prior lattice then dedup apart on some platforms
    (CI, Linux, py3.11 and 3.14: ``test_two_settings_of_one_prior_lattice``)."""
    red = np.array([1.9720631506620304e-02, 1.2753091867002138e-02,
                    3.7144002961060477e-03, -9.0e-19, -1.12e-18,
                    2.1241323203985479e-03])
    noisy = red.copy()
    noisy[3], noisy[4] = 4e-19, 2e-19
    assert equal_reduced(red, noisy)[0]
    # a real difference in the same slots still separates
    real = red.copy()
    real[3] = 1e-4
    assert not equal_reduced(red, real)[0]


def test_same_lattice_separates_genuinely_different_cells():
    a = af_from_cell((7.0, 8.0, 9.0, 85.0, 95.0, 100.0))
    b = af_from_cell((7.0, 8.0, 9.3, 85.0, 95.0, 100.0))
    equal, _chi2 = same_lattice(a, b)
    assert not equal


def test_cell_equality_respects_the_measured_precision():
    """The reason dedup is a χ² test and not a percentage.

    The *same* pair of cells is one lattice at laboratory precision and two at
    synchrotron precision — which a fixed percentage cannot express, and which is
    the whole point of carrying per-line σ this far.
    """
    a = af_from_cell((7.0, 8.0, 9.0, 90.0, 90.0, 90.0))
    b = af_from_cell((7.0005, 8.0, 9.0, 90.0, 90.0, 90.0))
    lab = np.diag(np.full(6, (2e-5) ** 2))
    synchrotron = np.diag(np.full(6, (2e-8) ** 2))

    same_lab, chi2_lab = same_lattice(a, b, cov_a=lab, cov_b=lab)
    same_sync, chi2_sync = same_lattice(a, b, cov_a=synchrotron,
                                        cov_b=synchrotron)
    assert same_lab and chi2_lab <= CELL_EQUALITY_CHI2
    assert not same_sync and chi2_sync > CELL_EQUALITY_CHI2


@settings(max_examples=60, deadline=None,
          suppress_health_check=[HealthCheck.filter_too_much])
@given(lengths, lengths, lengths, angles, angles, angles)
# issue #797 (and #843, the same cell): gemmi's reduction gave η the sign of
# the ε-sized value it treats as zero, so the reduced cell sat 1.2e-5 off T·af
@example(3.0, 11.0, 14.197202585325392, 65.0, 65.0, 65.0)
def test_the_reduction_map_takes_a_to_f_where_the_reduction_does(a, b, c, al,
                                                                  be, ga):
    """WP-1518: T·af is the reduced A..F, so T·cov·Tᵀ is its covariance.

    The map is built from gemmi's change-of-basis triplet, whose convention
    (R⁻¹, not R, Rᵀ or R⁻ᵀ) is exactly what a wrong reading would get wrong on
    every non-trivial reduction while leaving the identity ones right.
    """
    cell = (a, b, c, al, be, ga)
    assume(_valid(cell))
    af = af_from_cell(cell)
    red, t = reduction(af)
    assert np.array_equal(red, reduced_af(af))
    if t is None:
        assert np.allclose(red, af, rtol=1e-9, atol=1e-12 * np.max(np.abs(af)))
    else:
        assert np.array_equal(t, np.rint(t))
        assert np.allclose(t @ af, red, rtol=1e-9,
                           atol=1e-12 * np.max(np.abs(red)))


@pytest.mark.parametrize("cell", [
    (3.4481, 3.4481, 7.9668, 90.0, 89.9999997, 90.0),
    (10.1736, 10.1736, 7.2114, 90.0, 89.99999996617657, 90.0),
    (4.9378, 3.3955, 4.4419, 90.0, 89.99999877161947, 90.0),
    (11.2545, 7.4719, 8.663, 90.0, 89.99999996944449, 89.99998580312608),
    (3.0, 11.0, 14.197202585325392, 65.0, 65.0, 65.0),           # issue #797
])
def test_the_map_needs_no_sign_the_reduction_chose(cell):
    """Within ε gemmi gives a near-zero ξ, η or ζ either sign and the triplet
    does not say so.  Hypothesis's generic cells never land there.  Unmapped,
    the first four disagreed with red by 1.7e-9 to 6.6e-7 of its scale; a row
    flip of T then hid the sign and left the metric one ε away (the fifth,
    1.2e-5).  Since WP-1923 the reduced cell is the exact image, so the
    triplet's map alone takes af to red."""
    af = af_from_cell(cell)
    red, t = reduction(af)
    mapped = af if t is None else t @ af
    assert np.allclose(mapped, red, rtol=0.0, atol=1e-14 * np.max(np.abs(red)))


@pytest.mark.parametrize("centring", ["P", "C", "I", "F", "R"])
@settings(max_examples=40, deadline=None,
          suppress_health_check=[HealthCheck.filter_too_much])
@given(lengths, lengths, lengths, angles, angles, angles)
@example(3.0, 11.0, 14.197202585325392, 65.0, 65.0, 65.0)           # #797
@example(3.4481, 3.4481, 7.9668, 90.0, 89.9999997, 90.0)
@example(3.2, 16.0, 23.602486327493914, 81.0, 66.0, 65.0)           # WP-2035
@example(3.0, 4.0, 5.0, 89.99999, 70.0, 80.0)                       # WP-2035
def test_the_reduced_cell_is_the_exact_image_of_its_input(centring, a, b, c,
                                                          al, be, ga):
    """WP-1923: M·G·Mᵀ of the input under the recorded change of basis *is*
    the reduced metric, and it is gemmi's reduced vector to within the
    reduction's own ε.  Not ``is_niggli``: that predicate tests signs without
    ε, and it fails gemmi's own output on fp ties (``ReducedCell``'s note).

    WP-2035's cell (found by WP-1930) left gemmi's vector with every sign
    agreeing and ξ 2|η| off the image, G₂₃ at 1.1e-7 of max|G| on F and
    5.4e-8 on C, so a check of the signs alone kept it.  The primitive cell
    one angle 1e-5° from a right angle does the same through ξ (2.9e-7 on
    P): hypothesis's angles almost never land within ε of 90°."""
    cell = (a, b, c, al, be, ga)
    assume(_valid(cell))
    _assert_exact_image(cell, centring)


def _assert_exact_image(cell, centring):
    import gemmi

    from rietx.crystallography.lattice import direct_metric_tensor
    from rietx.indexing.reduce import NIGGLI_EPS_RELATIVE, _basis_change

    r = reduce_cell(cell, centring)
    m = _basis_change(r.change_of_basis)
    image = m @ np.asarray(direct_metric_tensor(*cell)) @ m.T
    got = np.asarray(direct_metric_tensor(*r.cell))
    assert np.allclose(got, image, rtol=0.0, atol=1e-12 * np.max(np.abs(image)))
    uc = gemmi.UnitCell(*cell)
    eps = NIGGLI_EPS_RELATIVE * uc.volume ** (1.0 / 3.0)
    gv = gemmi.GruberVector(uc, centring)
    gv.niggli_reduce(epsilon=eps)
    gv.normalize(epsilon=eps)
    A, B, C, xi, eta, zeta = gv.parameters
    theirs = np.array([[A, zeta / 2, eta / 2], [zeta / 2, B, xi / 2],
                       [eta / 2, xi / 2, C]])
    assert np.max(np.abs(got - theirs)) <= eps


_NEAR_RIGHT = st.tuples(st.floats(min_value=1e-7, max_value=1e-5),
                        st.sampled_from([-1.0, 1.0]))


@pytest.mark.parametrize("centring", ["P", "C", "I", "F", "R"])
@settings(max_examples=40, deadline=None,
          suppress_health_check=[HealthCheck.filter_too_much])
@given(lengths, lengths, lengths, angles, angles, angles,
       st.integers(0, 2), _NEAR_RIGHT)
def test_the_exact_image_holds_with_one_angle_within_epsilon_of_90(
        centring, a, b, c, al, be, ga, which, offset):
    """WP-2035's sweep: one angle 1e-7–1e-5° either side of 90° puts a
    Niggli parameter within the reduction's ε of zero, where gemmi's
    ``normalize`` and Křivý–Gruber steps disagree on a sign.  On ``main``'s
    sign-gated path about 30 % of such P cells left the exact image."""
    angs = [al, be, ga]
    angs[which] = 90.0 + offset[1] * offset[0]
    cell = (a, b, c, *angs)
    assume(_valid(cell))
    _assert_exact_image(cell, centring)


_SETTING_STEPS = st.sampled_from([(1, 0, 0, 1), (1, 0, 1, 1), (1, 0, -2, 1),
                                   (1, 2, 0, 1), (1, -2, 1, -1), (-1, 0, 0, 1),
                                   (1, 0, 3, 1), (3, -4, 2, -3)])


@pytest.mark.parametrize("centring", ["P", "C"])
@settings(max_examples=40, deadline=None,
          suppress_health_check=[HealthCheck.filter_too_much])
@given(lengths, lengths, lengths, st.floats(min_value=90.5, max_value=125.0),
       _SETTING_STEPS, st.booleans())
@example(4.541, 4.884, 10.198, 98.22, (-1, 0, 0, 1), False)      # issue #779
def test_a_monoclinic_cell_is_re_set_to_the_conventional_setting(
        centring, a, b, c, beta, step, swap):
    """WP-1923: whatever (a, c) basis an engine arrived at, the re-set lands
    on b unique, β obtuse, a and c the shortest translations normal to b,
    and on the cell spglib's ``std_lattice`` standardises the lattice to."""
    from rietx.indexing.qspace import cell_from_af
    from rietx.indexing.reduce import af_map, conventional_setting

    truth = (a, b, c, 90.0, beta, 90.0)
    assume(_valid(truth))
    p, q, r, s_ = step
    if centring == "C" and q % 2:
        q += 1
    assume(p * s_ - q * r in (1, -1))
    rows = [(p, 0, q), (0, p * s_ - q * r, 0), (r, 0, s_)]
    if swap and centring == "P":
        rows = [rows[2], (0, -rows[1][1], 0), rows[0]]
    engine_af = af_map(rows) @ af_from_cell(truth)
    engine_cell = cell_from_af(engine_af)
    assume(min(engine_cell[:3]) > 1.0 and max(engine_cell[:3]) < 200.0)

    change = conventional_setting(engine_af, "monoclinic", centring)
    got = engine_cell if change is None else cell_from_af(
        af_map(change) @ engine_af)
    if change is not None:
        m = np.asarray(change)
        assert round(np.linalg.det(m)) == 1
        if centring == "C":
            assert m[0, 2] % 2 == 0 and m[0, 0] % 2 == 1   # (a+b)/2 survives
    assert got[3] == pytest.approx(90.0, abs=1e-9)
    assert got[5] == pytest.approx(90.0, abs=1e-9)
    assert got[4] >= 90.0 - 1e-9
    if centring == "P":
        assert got[0] <= got[2] + 1e-9
        assert got[4] <= 120.0 + 1e-9               # a Gauss-reduced pair

    lat = lattice_vectors(truth)
    if centring == "C":                              # spglib reads a P basis
        lat = np.array([(lat[0] - lat[1]) / 2, (lat[0] + lat[1]) / 2, lat[2]])
    std, _, symbol = conventional_cell(cell_from_vectors(lat), symprec=1e-5)
    assume(symbol in ("P2/m", "C2/m"))               # not a higher lattice
    assert got == pytest.approx(std, rel=1e-7, abs=1e-6)


@pytest.mark.parametrize("centring", ["P", "C"])
@pytest.mark.parametrize("cell", [
    (4.541, 4.884, 10.198, 90.0, 90.0, 90.0),       # a right angle's rounding
    (10.8253, 22.1482, 10.8253, 90.0, 90.0, 90.0),  # and an a = c tie
])
def test_rounding_is_not_a_setting_to_re_set(centring, cell):
    """A right angle or a tie reached through a change of basis is re-set to
    the identity on the second pass, never flipped on its last bit."""
    from rietx.indexing.reduce import af_map, conventional_setting

    rows = [(0, 0, 1), (0, -1, 0), (1, 0, 4)] if centring == "P" \
        else [(1, 0, -6), (0, -1, 0), (0, 0, 1)]
    engine_af = af_map(rows) @ af_from_cell(cell)
    change = conventional_setting(engine_af, "monoclinic", centring)
    af = engine_af if change is None else af_map(change) @ engine_af
    assert conventional_setting(af, "monoclinic", centring) is None


def test_a_metric_that_is_no_lattice_has_no_setting():
    from rietx.indexing.reduce import conventional_setting

    assert conventional_setting(np.full(6, np.nan), "monoclinic") is None
    assert conventional_setting(np.array([0.05, 0.04, -0.01, 0.0, 0.001, 0.0]),
                                "monoclinic") is None


def test_a_re_set_carries_the_covariance_with_the_metric():
    """The fit's esds come from the re-set covariance, not the engine's: a
    sign flip of a and b leaves every esd alone, a c ← c + a step does not."""
    from rietx.indexing.engines import conventional_fit
    from rietx.indexing.qspace import CandidateFit, cell_esds, cell_from_af

    def fit_of(cell):
        af = af_from_cell(cell)
        cov = np.diag((1e-5 * np.abs(af) + 1e-9) ** 2)
        cov[0, 4] = cov[4, 0] = 0.3 * np.sqrt(cov[0, 0] * cov[4, 4])
        return CandidateFit(af=af, cov_af=cov, cell=cell_from_af(af),
                            cell_esd=cell_esds(af, cov), system="monoclinic",
                            n_lines=20, chi2_red=1.0, residual_q=np.zeros(20))

    acute = fit_of((4.541, 4.884, 10.198, 90.0, 81.78, 90.0))
    new, change = conventional_fit(acute, "monoclinic", "P")
    assert change == ((-1, 0, 0), (0, -1, 0), (0, 0, 1))
    assert new.cell[4] == pytest.approx(98.22)
    assert np.allclose(new.cell_esd, acute.cell_esd, rtol=1e-9)
    assert np.allclose(new.af, af_from_cell(new.cell), rtol=1e-12)

    long_c = fit_of((4.541, 4.884, 11.0, 90.0, 120.0, 90.0))
    new, change = conventional_fit(long_c, "monoclinic", "P")
    assert change == ((1, 0, 0), (0, 1, 0), (1, 0, 1))
    assert not np.allclose(new.cell_esd, long_c.cell_esd, rtol=1e-3)
    assert np.allclose(new.cell_esd, cell_esds(new.af, new.cov_af), rtol=0.0)

    tetragonal = fit_of((4.0, 4.0, 9.0, 90.0, 90.0, 90.0))
    assert conventional_fit(tetragonal, "tetragonal", "P") == (tetragonal, None)


def _own_frame_covariance(af: np.ndarray, rel: float, slots) -> np.ndarray:
    """A diagonal covariance in the setting an engine refined in."""
    return np.diag([(rel * af[s]) ** 2 if s in slots else 0.0
                    for s in range(6)])


def test_a_monoclinic_pair_apart_in_beta_is_two_lattices():
    """WP-1518's false merge: a covariance read in the wrong frame.

    Two b-unique cells 0.1° apart in β, each measured to 1e-4 on A, B, C and E.
    Near 90° their difference is almost all E, and the reduction moves E into
    the F slot, where an own-frame covariance has no variance.  Weighed there,
    χ² was 1.3 and the two merged; the second assert is that witness.
    """
    af_a = af_from_cell((7.1, 9.3, 5.2, 90.0, 91.0, 90.0))
    af_b = af_from_cell((7.1, 9.3, 5.2, 90.0, 91.1, 90.0))
    cov_a = _own_frame_covariance(af_a, 1e-4, (0, 1, 2, 4))
    cov_b = _own_frame_covariance(af_b, 1e-4, (0, 1, 2, 4))
    assert reduction(af_a)[1] is not None
    assert equal_reduced(reduced_af(af_a), reduced_af(af_b),
                         cov_a=cov_a, cov_b=cov_b)[0]
    same, chi2 = same_lattice(af_a, af_b, cov_a=cov_a, cov_b=cov_b)
    assert not same and chi2 > 1e5, chi2


def test_one_tetragonal_lattice_measured_twice_is_one_lattice():
    """WP-1518's false split, the other direction of the same defect.

    One (6, 6, 4) lattice measured with σ_A = 1e-6 (B tied to it) and
    σ_C = 1e-5, the second copy 2σ away in C.  The reduction moves C into the A
    slot, where the own-frame variance is a hundred times smaller.  Weighed
    there, χ² was 50 and one lattice split in two; weighed in one frame it is 2.
    """
    af_a = af_from_cell((6.0, 6.0, 4.0, 90.0, 90.0, 90.0))
    af_b = af_a + np.array([0.0, 0.0, 2e-5, 0.0, 0.0, 0.0])
    cov = np.zeros((6, 6))
    cov[:2, :2] = 1e-12
    cov[2, 2] = 1e-10
    assert reduction(af_a)[1] is not None
    assert not equal_reduced(reduced_af(af_a), reduced_af(af_b),
                             cov_a=cov, cov_b=cov)[0]
    same, chi2 = same_lattice(af_a, af_b, cov_a=cov, cov_b=cov)
    assert same and chi2 == pytest.approx(2.0, rel=1e-6)


@pytest.mark.parametrize("cell", [
    (4.0, 4.0, 6.0, 90.0, 90.0, 90.0),
    (4.759, 4.759, 12.99, 90.0, 90.0, 120.0),
])
def test_a_pair_already_in_its_reduced_setting_is_unchanged_to_the_bit(cell):
    """c > a keeps the setting, so no covariance is carried and χ² is the
    pre-WP-1518 number exactly (corundum's own hexagonal cell is one)."""
    af_a = af_from_cell(cell)
    af_b = af_a * (1.0 + np.array([3e-6, 3e-6, -2e-6, 0.0, 0.0, 1e-6]))
    rng = np.random.default_rng(1518)
    root = rng.standard_normal((6, 6)) * 1e-6 * np.max(np.abs(af_a))
    cov_a, cov_b = root @ root.T, 0.5 * root @ root.T
    assert reduction(af_a)[1] is None and reduction(af_b)[1] is None
    before = equal_reduced(reduced_af(af_a), reduced_af(af_b),
                           cov_a=cov_a, cov_b=cov_b)
    assert same_lattice(af_a, af_b, cov_a=cov_a, cov_b=cov_b) == before


# ----------------------------------------------------------------------
# Ambiguity
# ----------------------------------------------------------------------
@pytest.mark.parametrize("index,count", [(2, 7), (3, 13), (4, 35)])
def test_hnf_enumeration_counts(index, count):
    """7, 13, 35 — the closed sets.  A count mismatch is how an enumeration bug
    announces itself instead of silently dropping a partner."""
    ms = hnf_matrices(index)
    assert len(ms) == count
    assert all(round(float(np.linalg.det(m))) == index for m in ms)
    # Hermite normal form is canonical, so no matrix repeats
    assert len({m.tobytes() for m in ms}) == count


def test_hnf_rejects_a_nonpositive_index():
    with pytest.raises(ValueError):
        hnf_matrices(0)


def test_transform_cell_scales_the_volume_by_the_index():
    cell = (7.0, 8.0, 9.0, 85.0, 95.0, 100.0)
    for index in (2, 3, 4):
        for h in hnf_matrices(index):
            child = transform_cell(cell, h)
            assert float(cell_volume(*child)) == pytest.approx(
                index * float(cell_volume(*cell)), rel=1e-9)


def test_derivative_cells_drop_the_parent_in_a_new_setting():
    """A setting change is dedup's business, not ambiguity's — so a derivative
    that reduces to the parent must never be offered as a partner."""
    cell = (7.0, 8.0, 9.0, 85.0, 95.0, 100.0)
    parent = af_from_cell(cell)
    for _index, _h, child in derivative_cells(cell, max_index=3):
        equal, _ = same_lattice(parent, af_from_cell(child))
        assert not equal


def _lines(cell, system="cubic", centring="P", two_theta_max=90.0,
           esd_deg=0.01):
    """Every line ``cell`` predicts in range, with a declared σ.

    Via ``fom.predicted_lines`` rather than ``generate_reflections`` because the
    cells here are deliberately *not* in the setting a space-group symbol implies
    (a derivative of a cubic cell is tetragonal or worse), and the symbol-based
    generator returns NaN d-spacings for a cell its symmetry forbids.
    """
    from rietx.indexing.fom import predicted_lines

    _hkl, q = predicted_lines(cell, system, centring, LAM, two_theta_max)
    tt = np.degrees(2.0 * np.arcsin(LAM * np.sqrt(q) / 2.0))
    return q, q_esd_of_two_theta(tt, np.full_like(tt, esd_deg), LAM)


def test_a_supercell_is_excluded_by_the_lines_it_predicts_and_the_data_lacks():
    """A supercell is **not** an ambiguity: the data refute it (WP-1024).

    This test asserted the opposite until WP-1024, on the reasoning that a
    supercell indexes every observed line and so "cannot be excluded by the
    positions alone".  That reads only the observed positions and ignores the
    absences, which is exactly ``indexed_fraction``'s measured blind spot one
    module over — a doubled cubic cell needs lines at half the parent's
    d-spacings and they are not there.  Measured, the un-excluded screen reported
    **28 partners for this certified cubic cell**, which would have made WP-1024's
    confidence gate permanently ``low``: the indexer could never have answered.

    The crystallography agrees with the arithmetic: a 2a cell whose odd
    reflections are identically zero has the a-translation, so the *lattice* is
    the a-lattice and the supercell is a cell choice, not a rival hypothesis.
    """
    cell = (4.1566,) * 3 + (90.0,) * 3
    q, esd = _lines(cell)
    assert ambiguity_partners(cell, "cubic", "P", q, esd, LAM, 90.0,
                              max_index=2) == []


def test_a_surviving_partner_says_where_to_measure_to_break_the_tie():
    """When the extra lines *are* all present, the partner survives — and its
    discriminating reflections are then necessarily **outside** the measured
    range.

    That is a consequence of the exclusion rather than a separate rule: a partner
    whose in-range extras were absent is gone, and one whose in-range extras are
    present is not discriminated by them.  So the report is literally "collect
    further and look", which is why the partner's lines are predicted out to
    ``AMBIGUITY_EXTEND_FACTOR``·2θ_max.
    """
    parent = (4.1566,) * 3 + (90.0,) * 3
    child = transform_cell(parent, np.diag([1, 1, 2]))
    tt_max = 90.0
    # observe the *child's* lines: every extra the child needs is then present,
    # and the parent explains a subset of them
    q, esd = _lines(child, "triclinic", "P", tt_max)
    partners = ambiguity_partners(parent, "cubic", "P", q, esd, LAM, tt_max,
                                  max_index=2)
    assert partners, "a partner whose extra lines are all present must survive"
    with_refl = [p for p in partners if p.discriminating_reflections]
    assert with_refl, "no partner said what would break the tie"
    p = with_refl[0]
    assert p.volume > float(cell_volume(*parent))
    assert len(p.discriminating_reflections) == len(p.discriminating_two_theta)
    assert all(t > tt_max for t in p.discriminating_two_theta), (
        "an in-range extra is either absent (excluding the partner) or present "
        "(not discriminating), so the tie-breakers lie outside the range")
    assert all(t <= AMBIGUITY_EXTEND_FACTOR * tt_max
               for t in p.discriminating_two_theta)
    assert p.transformation and abs(round(float(np.linalg.det(
        np.array(p.transformation))))) == p.index


def _hkl(cell, centring="P", two_theta_max=95.0):
    """Every reflection a lattice allows, unmerged — the list a class filters."""
    from rietx.indexing.fom import lattice_reflections

    hkl, _q, _m = lattice_reflections(cell, "triclinic", centring, LAM,
                                      two_theta_max)
    return hkl


#: One cell per Bravais lattice, its system and its holohedry's order.
BRAVAIS_LATTICES = [
    ((5.02, 6.13, 7.71, 81.0, 103.2, 95.5), "triclinic", "P", 2),
    ((5.02, 6.13, 7.71, 90.0, 103.2, 90.0), "monoclinic", "P", 4),
    ((9.02, 6.13, 7.71, 90.0, 113.2, 90.0), "monoclinic", "C", 4),
    ((5.02, 6.13, 3.71, 90.0, 90.0, 90.0), "orthorhombic", "P", 8),
    ((5.02, 6.13, 3.71, 90.0, 90.0, 90.0), "orthorhombic", "C", 8),
    ((5.02, 6.13, 7.71, 90.0, 90.0, 90.0), "orthorhombic", "I", 8),
    ((5.02, 6.13, 7.71, 90.0, 90.0, 90.0), "orthorhombic", "F", 8),
    ((6.6, 6.6, 5.98, 90.0, 90.0, 90.0), "tetragonal", "P", 16),
    ((6.6, 6.6, 5.98, 90.0, 90.0, 90.0), "tetragonal", "I", 16),
    ((4.759, 4.759, 12.99, 90.0, 90.0, 120.0), "trigonal", "R", 12),
    ((3.14, 3.14, 4.77, 90.0, 90.0, 120.0), "hexagonal", "P", 24),
    ((4.1566,) * 3 + (90.0,) * 3, "cubic", "P", 48),
    ((6.6,) * 3 + (90.0,) * 3, "cubic", "I", 48),
    ((8.39,) * 3 + (90.0,) * 3, "cubic", "F", 48),
]


@pytest.mark.parametrize("cell, system, centring, order", BRAVAIS_LATTICES)
def test_the_point_group_search_recovers_every_holohedry(cell, system,
                                                          centring, order):
    """The {−1, 0, 1} search on the reduced basis finds the whole group.

    A self-check, the way :func:`hnf_matrices` checks its counts: a candidate
    set too small for some lattice would show up here as a short group, and
    reflections a glide could cancel would then be counted as extras.  The
    group is closed, holds the identity, and preserves the metric exactly.
    """
    from rietx.crystallography.lattice import direct_metric_tensor
    from rietx.indexing.reduce import reduce_cell

    ops, _m = lattice_point_group(cell, centring, rtol=1e-6)
    assert len(ops) == order
    keys = {tuple(w.ravel()) for w in ops}
    assert tuple(np.eye(3, dtype=int).ravel()) in keys
    assert all(tuple((a @ b).ravel()) in keys for a in ops for b in ops)
    g = np.asarray(direct_metric_tensor(*reduce_cell(cell, centring).cell))
    assert all(np.allclose(w @ g @ w.T, g, rtol=1e-9, atol=1e-9) for w in ops)


def test_a_pseudo_symmetric_metric_counts_the_symmetry_it_nearly_has():
    """The default tolerance is the Bravais screen's loosest, on purpose.

    A tetragonal cell with c/a = 1.002 could carry a cubic space group's
    extinctions on reflections that are general for tetragonal, so they are set
    aside too.  Tightened, the same metric has only its own group.
    """
    cell = (5.0, 5.0, 5.01, 90.0, 90.0, 90.0)
    assert len(lattice_point_group(cell, "P")[0]) == 48
    assert len(lattice_point_group(cell, "P", rtol=1e-6)[0]) == 16


@pytest.mark.parametrize("cell, system, centring, _order", [
    row for row in BRAVAIS_LATTICES if row[1] != "triclinic"])
def test_no_space_group_extinguishes_an_uncancellable_reflection(
        cell, system, centring, _order):
    """Derived, never transcribed: every space group of every lattice asked.

    ``compatible_groups`` enumerates each gemmi setting whose lattice is this
    one, and none of them may forbid a reflection :func:`uncancellable` keeps.
    Centring is the lattice's own condition and is decided first, so only
    centring-allowed reflections are asked.  And the rule is not vacuous: some
    group of each lattice does extinguish a reflection it sets aside.
    """
    from rietx.indexing.extinction import compatible_groups
    from rietx.indexing.fom import lattice_reflections

    hkl, _q, _m = lattice_reflections(cell, system, centring, LAM, 150.0)
    keep = uncancellable(cell, centring, hkl)
    assert keep.any() and not keep.all()
    groups = [g for g in compatible_groups(system, centring, cell)
              if g.crystal_system_str() == system
              or (system, g.crystal_system_str()) == ("hexagonal", "trigonal")]
    assert groups
    extinguished_elsewhere = False
    for sg in groups:
        absent = np.asarray(sg.operations()
                            .systematic_absences(hkl), dtype=bool)
        assert not absent[keep].any(), (sg.xhm(), hkl[keep & absent][:3])
        extinguished_elsewhere |= bool(absent[~keep].any())
    assert extinguished_elsewhere


def test_a_phantom_supercells_extras_sit_at_chance():
    """WP-1449: the pair question asked against chance rather than a bar.

    Only the parent's lines exist, so the doubled cell's extra lines are seen
    no more often than a position nothing is at — here not at all — and the
    test, powerful enough to have said otherwise, refutes it.  The partner form
    drops the same supercell, which is the claim that the two agree.  The
    p-value is the binomial one over the recorded counts, nothing else.
    """
    from scipy.stats import binom

    parent = (4.1566,) * 3 + (90.0,) * 3
    child = transform_cell(parent, np.diag([1, 1, 2]))
    q, esd = _lines(parent)                      # only the parent's lines exist

    assert ambiguity_partners(parent, "cubic", "P", q, esd, LAM, 90.0,
                              max_index=2) == []
    ev = supercell_chance(parent, "P", child, "P", q, esd)
    assert ev is not None and ev.index == 2
    assert ev.n_extra >= 5 and ev.n_seen <= ev.p0 * ev.n_extra + 1
    assert ev.p0 == chance_rate(q, esd, float(q.min()), float(q.max()))
    assert ev.p_value == pytest.approx(
        float(binom.sf(ev.n_seen - 1, ev.n_extra, ev.p0)), rel=1e-12)
    assert ev.p_floor < SUPERCELL_CHANCE_ALPHA <= ev.p_value
    assert ev.verdict() == "refuted"
    # every extra is off the parent's lattice: an odd l in the doubled axis
    assert all(hkl[2] % 2 for hkl in ev.extra_hkl)


def test_a_monoclinic_truths_phantom_supercells_are_never_supported():
    """WP-1449's measurement below high symmetry, on real monoclinic lists.

    Bethanechol's benchmark cannot ask it through a search: both of the
    paper's modes cap the volume under the truth's smallest supercell, and
    with the cap raised the ranking keeps every supercell out of the reported
    list. So each superlattice of the published P 2₁/n cell of index 2-4 is
    asked directly, against every set's twenty lines and the manual mode's
    window. All are phantoms. The test may lack the power to refute one,
    and then it moves nothing, but it must never call one supported.
    Measured 2026-09-29 on all ten sets: 544 refuted, and 6 undecided on set F
    alone, where a chance hit is 0.738 likely and an index-2 cell adds 9-14
    extras. Three sets span that range of p0 (Ba 0.299, E 0.429, F 0.738); Aa
    is the fourth because it is the nearest miss: an index-3 cell at 18 of 29
    extras seen, p = 0.0105 against α = 0.01, one coincident line from a false
    "supported".
    """
    from collections import Counter

    from rietx.indexing.ambiguity import derivative_cells
    from rietx.indexing.engines import match_window
    from rietx.schemas.indexing import PeakList
    from tests import bethanechol_benchmark as bench_mod

    bench = bench_mod.load()
    truth = tuple(bench_mod.truth_cell(bench))
    spec = bench_mod.spec_for(bench, "manual")
    children = derivative_cells(truth, max_index=4)
    assert len(children) == 7 + 13 + 35
    verdicts: Counter = Counter()
    for name in ("Aa", "Ba", "E", "F"):
        tt, lam = bench_mod.positions(bench, name)
        peaks = PeakList.from_positions(tt, wavelength=lam)
        q_obs, q_match = np.asarray(peaks.q()), match_window(peaks, spec)
        for index, _h, child in children:
            ev = supercell_chance(truth, "P", child, "P", q_obs, q_match,
                                  k_sigma=spec.k_sigma)
            assert ev is not None and ev.index == index, (name, child)
            verdict = ev.verdict()
            verdicts[verdict] += 1
            assert verdict != "supported", (name, child, ev.n_seen, ev.n_extra)
            if verdict == "undecided":
                # power runs out only where chance fills most windows, and
                # only for the smallest supercells, which add the fewest extras
                assert ev.p0 > 0.5 and index == 2, (name, child, ev.p0)
    assert verdicts["refuted"] >= 0.95 * sum(verdicts.values()), verdicts


def test_a_true_superstructures_extras_are_present():
    """The test is self-correcting, and that is what makes it a signature.

    An exact supercell whose extra lines are *present* is seen far beyond
    chance, so the rule declines to demote it: the doubled cell is then a
    lattice statement rather than a cell choice.  The blind spot that remains is
    the module docstring's, superlattice intensity below the picker's floor.
    """
    parent = (4.1566,) * 3 + (90.0,) * 3
    child = transform_cell(parent, np.diag([1, 1, 2]))
    q, esd = _lines(child, "triclinic", "P")     # the child's lines are there

    ev = supercell_chance(parent, "P", child, "P", q, esd)
    assert ev.n_seen == ev.n_extra >= 5
    assert ev.p_value < 1e-6
    assert ev.verdict() == "supported"
    # no parent line sits on them, so every one counts towards support
    assert ev.n_seen_unexplained == ev.n_seen
    assert ev.p_value_unexplained == ev.p_value


def test_an_extra_seen_only_on_a_parent_line_supports_nothing():
    """WP-1510: a pseudo-symmetric child's seen extras sit on the parent's lines.

    LaB6's half-volume rival (a/√2, a/√2, a) is isospectral with the cubic
    cell, and a tetragonal description with c 0.1 % short splits each cubic
    line it shares with the rival into an extra beside it.  Inside a 0.02°
    window two of its four extras are seen, p = 0.003 against p₀ = 0.023, so
    the count over every seen extra calls the larger cell supported.  Both sit
    on lines the rival explains, so none is seen on an unexplained line, and
    the pair is undecided: neither supported, which would move the child above
    the rival, nor refuted, since the extras are seen.  The finished LaB6
    search reported two such pairs, at 2 of 3.
    """
    a = 4.1566
    rival = (a / np.sqrt(2.0), a / np.sqrt(2.0), a, 90.0, 90.0, 90.0)
    child = (a, a, a * (1.0 - 1e-3), 90.0, 90.0, 90.0)
    q, esd = _lines((a,) * 3 + (90.0,) * 3, two_theta_max=145.0, esd_deg=0.02)

    ev = supercell_chance(rival, "P", child, "P", q, esd)
    assert ev is not None and ev.index == 2
    assert ev.n_seen >= 2 and ev.p_value < SUPERCELL_CHANCE_ALPHA
    assert ev.n_seen_unexplained == 0 and ev.p_value_unexplained == 1.0
    assert ev.verdict() == "undecided"


def test_the_uncancellable_extras_answer_without_the_class():
    """WP-1446's failure, reproduced, and answered without the extinction class.

    A superstructure whose class extinguishes some of its extras, and whose
    remaining ones are weak — eight observed, the rest below the floor, as on
    certified corundum.  Asked of the whole lattice, the extinguished extras
    count as absent and the true cell reads as chance.  The class removes them;
    so does counting only the reflections no class could remove, and the two
    counts agree here as they do on corundum (8 of 18 either way).
    """
    import gemmi

    from rietx.indexing.qspace import af_from_cell, design_matrix

    parent = (5.02, 6.13, 3.71, 90.0, 90.0, 90.0)
    child = transform_cell(parent, np.diag([1, 1, 2]))
    lattice = _hkl(child)
    absent = np.asarray(gemmi.find_spacegroup_by_name("P c c n").operations()
                        .systematic_absences(lattice), dtype=bool)
    allowed = lattice[~absent]

    q_parent, _esd = _lines(parent, "orthorhombic", "P")
    q_allowed = design_matrix(allowed) @ af_from_cell(child)
    weak = np.unique(np.round(q_allowed[allowed[:, 2] % 2 == 1], 12))[:8]
    q = np.sort(np.concatenate([q_parent, weak]))
    tt = np.degrees(2.0 * np.arcsin(LAM * np.sqrt(q) / 2.0))
    esd = q_esd_of_two_theta(tt, np.full_like(tt, 0.01), LAM)

    by_default = supercell_chance(parent, "P", child, "P", q, esd)
    by_class = supercell_chance(parent, "P", child, "P", q, esd,
                                child_hkl=allowed)
    by_lattice = supercell_chance(parent, "P", child, "P", q, esd,
                                  child_hkl=lattice)
    assert by_default.extra_q == pytest.approx(by_class.extra_q, rel=1e-12)
    # the eight present, and one more that chance puts inside a window
    assert by_default.n_seen == by_class.n_seen == 9
    assert all(h and k for h, k, _l in by_default.extra_hkl)   # off every zone
    assert by_default.verdict() == "supported"
    assert by_lattice.verdict() == "refuted"


@pytest.mark.parametrize("cell, centring, index", [
    ((6.6, 6.6, 6.6, 90.0, 90.0, 90.0), "I", 2),
    ((4.759, 4.759, 12.99, 90.0, 90.0, 120.0), "R", 3),
])
def test_a_primitive_description_of_a_centred_lattice_is_its_superlattice(
        cell, centring, index):
    """A P cell with a centred truth's own axes is a superlattice of it.

    Its conventional volume is the truth's, so a pair search on conventional
    cells finds no H at all; on the primitive reduced cells it is index 2 (I)
    or 3 (R), which is how the corundum, zircon, magnetite and NAC searches
    return them (WP-1449's table).  Its extras are exactly reflections the
    centring forbids, and with only the truth's lines present it is refuted.
    """
    from rietx.indexing.qspace import centring_allows

    q, esd = _lines(cell, "triclinic", centring)
    ev = supercell_chance(cell, centring, cell, "P", q, esd)
    assert ev is not None and ev.index == index
    assert ev.n_extra and not centring_allows(np.array(ev.extra_hkl),
                                              centring).any()
    assert ev.verdict() == "refuted"
    # the other way round is not a superlattice pair
    assert supercell_chance(cell, "P", cell, centring, q, esd) is None


@pytest.mark.parametrize("centring, index", [("F", 2), ("I", 4)])
def test_a_centred_supercell_of_an_orthogonal_lattice_is_paired(centring,
                                                                index):
    """The pairing is not fooled by a right angle written with noise.

    A cubic F or I cell of edge 2a is a superlattice of the P cell of edge a,
    at primitive index 2 and 4.  The transformed parent comes back with its
    right angles as fp noise, and a component-wise relative comparison, which
    is ``same_lattice``'s, calls that a different lattice: the dichotomy search
    returns both cells beside the truth, and before WP-1449 neither was paired.

    To 150° rather than 90°, and that is the power cost of counting only what
    no extinction can remove: to 90° the F cell's one uncancellable extra is
    531, and one extra reads *undecided*.
    """
    a = 4.1566
    parent = (a,) * 3 + (90.0,) * 3
    child = (2 * a,) * 3 + (90.0,) * 3
    q, esd = _lines(parent, two_theta_max=150.0)
    ev = supercell_chance(parent, "P", child, centring, q, esd)
    assert ev is not None and ev.index == index
    assert ev.verdict() == "refuted"
    short = _lines(parent)
    if centring == "F":
        assert supercell_chance(parent, "P", child, "F",
                                *short).verdict() == "undecided"


def test_a_test_that_could_not_have_rejected_chance_refutes_nothing():
    """No extra in range, or too few against the chance rate, is *undecided*.

    Even every extra seen could not reach α, so the outcome is not measured:
    a child whose extra lines all lie outside the range is the geometrical
    ambiguity :func:`ambiguity_partners` reports, and one extra seen against
    p₀ = 0.1 is what chance gives one time in ten.
    """
    from rietx.indexing.ambiguity import SupercellEvidence

    parent = (4.1566,) * 3 + (90.0,) * 3
    child = transform_cell(parent, np.diag([1, 1, 2]))
    q, esd = _lines(parent)
    first_extra = min(supercell_chance(parent, "P", child, "P", q, esd).extra_q)
    below = (float(q.min()), first_extra * 0.99)
    ev = supercell_chance(parent, "P", child, "P", q, esd, q_range=below)
    assert ev.n_extra == 0 and ev.p_value == 1.0 and ev.p_floor == 1.0
    assert ev.verdict() == "undecided"

    one = SupercellEvidence(index=2, extra_hkl=((0, 0, 1),), extra_q=(0.01,),
                            extra_seen=(True,), p0=0.1, p_value=0.1)
    assert one.verdict() == "undecided"
    assert one.verdict(alpha=0.2) == "supported"


def test_the_chance_rate_counts_overlapping_windows_once():
    """p₀ is the measure of the union of the windows, clipped to the range."""
    q = np.array([1.0, 1.5, 4.0, 9.8])
    esd = np.array([0.1, 0.1, 0.2, 0.2]) / 3.0     # half-widths 0.1, 0.1, 0.2, 0.2
    # [0.9, 1.1] ∪ [1.4, 1.6] ∪ [3.8, 4.2] ∪ [9.6, 10.0] ∩ [1.0, 10.0]
    assert chance_rate(q, esd, 1.0, 10.0) == pytest.approx(
        (0.1 + 0.2 + 0.4 + 0.4) / 9.0)
    overlap = np.array([2.0, 2.15])                # [1.9, 2.1] ∪ [2.05, 2.25]
    assert chance_rate(overlap, np.full(2, 0.1 / 3.0), 0.0, 10.0) == (
        pytest.approx(0.35 / 10.0))
    with pytest.raises(ValueError):
        chance_rate(q, esd, 2.0, 2.0)


def test_the_pair_form_does_not_turn_on_the_setting_the_engine_reported():
    """Two engines report the same doubled cubic lattice in different settings.

    The verdict has to be the same one, and so do the counts.  ``same_lattice``
    compares *reduced* forms, so an H found from the parent's side says nothing
    about the child's own basis, and ``H`` inverted onto a permuted basis gives
    a lattice of the parent's volume that is not the parent's — ``(2a, a,
    a/2)`` here, whose extras are a different set.  Measured before the
    enumeration moved into the child's frame, ``(a, a, 2a)`` was refuted and
    ``(2a, a, a)`` cleared (WP-1446).
    """
    parent = (4.1566,) * 3 + (90.0,) * 3
    natural = transform_cell(parent, np.diag([1, 1, 2]))
    permuted = (natural[2], natural[0], natural[1]) + (90.0,) * 3
    q, esd = _lines(parent)                      # only the parent's lines exist

    counts = []
    for child in (natural, permuted):
        h = _derivative_transform(parent, child)
        assert h is not None
        recovered = transform_cell(
            child, np.linalg.inv(np.asarray(h, dtype=float)))
        assert np.allclose(recovered, parent)
        ev = supercell_chance(parent, "P", child, "P", q, esd)
        assert ev.verdict() == "refuted"
        counts.append((ev.n_extra, ev.n_seen, ev.extra_q))
    assert counts[0][:2] == counts[1][:2]
    assert np.allclose(counts[0][2], counts[1][2], rtol=1e-12)


def test_a_derivative_transform_is_found_by_the_lattice_and_not_by_the_lines():
    """``H`` comes from ``same_lattice`` on the reduced forms, and ``det H`` is
    the index.

    The direction that matters is the refusal: an unrelated cell of the same
    volume as a genuine derivative has no H, so the volume prefilter cannot by
    itself demote anything.
    """
    parent = (4.1566,) * 3 + (90.0,) * 3
    child = transform_cell(parent, np.diag([1, 2, 2]))
    h = _derivative_transform(parent, child)
    assert h is not None
    assert abs(round(float(np.linalg.det(np.asarray(h, dtype=float))))) == 4

    # same volume as that index-4 derivative, unrelated metric
    v = float(cell_volume(*child))
    edge = v ** (1.0 / 3.0)
    unrelated = (edge * 1.31, edge * 0.83, edge / (1.31 * 0.83)) + (90.0,) * 3
    assert abs(cell_volume(*unrelated) / v - 1.0) < 1e-9
    assert _derivative_transform(parent, unrelated) is None


def test_ambiguity_index_is_fenced():
    """Index 2-4 is a fence, recorded rather than attempted: a high-index partner
    is more likely a numerical coincidence than a geometrical one."""
    assert MAX_AMBIGUITY_INDEX == 4
    cells = derivative_cells((5.0, 6.0, 7.0, 90.0, 90.0, 90.0))
    assert cells and max(index for index, _h, _c in cells) == MAX_AMBIGUITY_INDEX
