"""Satellites at G ± k with no moment model (WP-1326).

The tests worth having here are the ones that would still pass if the
enumeration were wrong in the ways the FullProf manual warns about, so each one
below turns on something a *naive* satellite generator gets wrong rather than
merely checking that a list comes back:

* the ±k rule respects **centring** — the manual's two worked examples on a C
  lattice, and the same test on P, I, F and R;
* the multiplicity is **enumerated**, and the plausible product formula
  |Laue orbit of H| × |star of k| disagrees with it on every centring;
* glide and screw absences are conditions on the **nuclear structure factor**
  and are not applied to a satellite (the naive error, run as a control);
* the reciprocal-space action is **Rᵀ**, and using R changes the count on a
  hexagonal cell (the trap M-5 measured is invisible elsewhere);
* a Rietveld stage contributes **exactly zero** at a satellite, so every number
  a phase without a propagation vector produces is bit-identical.

Everything is synthetic; nothing here reads a vendored pattern.
"""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction

import numpy as np
import pytest
from pydantic import ValidationError

import rietx as rx
from rietx.crystallography.magnetic.irreps import star
from rietx.crystallography.satellites import (
    KCandidate,
    check_candidate_denominators,
    check_propagation_vector,
    format_kvector,
    merge_satellites,
    minus_k_is_k,
    reciprocal_lattice_mask,
    satellite_orbit,
    satellite_reflections,
    zone_boundary_candidates,
)
from rietx.crystallography.symmetry import (
    generate_reflections,
    get_spacegroup,
    reflection_orbits,
    rotation_matrices,
)
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.report.satellites import analyse_satellites
from rietx.schemas.structure import (
    MOMENT_MODEL_FIELDS,
    refuse_moment_model_with_k,
)

CELL = (4.0, 5.0, 6.0, 90.0, 90.0, 90.0)
LAMBDA = 2.4067          # HB-2A's Ge(113) wavelength, a plausible CW neutron λ
TT_MAX = 110.0


def _phase(k=None, *, symbol: str = "P m m m", cell=CELL, name: str = "Fe"):
    P = rx.Parameter
    a, b, c, al, be, ga = cell
    return rx.Phase(
        name=name, space_group=symbol,
        cell=rx.Cell(a=P(value=a), b=P(value=b), c=P(value=c),
                     alpha=P(value=al), beta=P(value=be), gamma=P(value=ga)),
        atoms=[rx.Atom(label="Fe", species="Fe", x=P(value=0.0),
                       y=P(value=0.0), z=P(value=0.0), biso=P(value=0.4))],
        scale=P(value=1.0), propagation_vector=k)


def _grid() -> np.ndarray:
    return np.arange(10.0, TT_MAX, 0.02)


def _neutron(fwhm_deg: float = 0.4) -> rx.Instrument:
    return rx.Instrument.constant_wavelength_neutron(LAMBDA, fwhm_deg=fwhm_deg)


def _pattern(y=None) -> rx.PatternData:
    tt = _grid()
    if y is None:
        y = np.ones_like(tt)
    return rx.PatternData(two_theta=tt.tolist(), intensity=np.asarray(y).tolist())


def _values(structure, instrument):
    table = ParameterTable(structure, instrument)
    return table.decode(table.x0())


# ===================================================== the ±k equivalence rule


def test_the_manuals_two_worked_examples_on_a_c_lattice():
    """(½ 0 0) is two vectors on a C lattice and (0 0 ½) is one.

    The FullProf manual's rule is that k ≡ −k exactly when 2k is a vector of
    the **reciprocal lattice**, and the reciprocal lattice of a C-centred
    direct lattice is the sublattice h + k = 2n.  So 2k = (1, 0, 0) is *not* a
    lattice point and ±k are distinct, while 2k = (0, 0, 1) is one and they are
    the same vector.  A generator that reduced k componentwise modulo 1 would
    call both of them single, which is the error this pins.
    """
    assert minus_k_is_k("C 2/m", ("1/2", 0, 0)) is False
    assert minus_k_is_k("C 2/m", (0, 0, "1/2")) is True
    # the same k on a primitive lattice of the same point group: now (1, 0, 0)
    # *is* a reciprocal-lattice vector, so the answer flips.  That is what
    # makes the C-lattice answer a statement about centring and not about k.
    assert minus_k_is_k("P 2/m", ("1/2", 0, 0)) is True


@pytest.mark.parametrize("symbol, k, expected", [
    ("P 2/m", ("1/2", 0, 0), True),
    ("C 2/m", ("1/2", 0, 0), False),
    ("C 2/m", ("1/2", "1/2", 0), True),     # (1,1,0) obeys h+k=2n
    ("I 4/m m m", (0, 0, "1/2"), False),    # (0,0,1) violates h+k+l=2n
    ("I 4/m m m", ("1/2", "1/2", 0), True),
    ("F m -3 m", (0, 0, "1/2"), False),     # (0,0,1) is mixed parity
    ("F m -3 m", ("1/2", "1/2", "1/2"), True),   # (1,1,1) is all-odd
    ("R -3 c:H", (0, 0, "1/2"), False),     # (0,0,1) violates -h+k+l=3n
    ("R -3 c:H", (0, 0, "3/2"), True),      # (0,0,3) obeys it
])
def test_the_pm_k_rule_on_every_centring(symbol, k, expected):
    """±k on P, C, I, F and R — the rule is the lattice's, not the group's."""
    assert minus_k_is_k(symbol, k) is expected
    # and it agrees with the direct statement of the same fact: 2k is in the
    # reciprocal lattice iff it is an integer triple obeying every centring
    # condition
    two_k = [2 * c for c in (Fraction(str(x)) for x in k)]
    integral = all(c.denominator == 1 for c in two_k)
    direct = integral and bool(reciprocal_lattice_mask(
        symbol, np.array([[int(c) for c in two_k]]))[0])
    assert direct is expected


# ================================================ multiplicity by enumeration


CENTRING_CASES = [
    ("P", "P m -3 m"), ("I", "I 4/m m m"), ("F", "F m -3 m"),
    ("R", "R -3 c:H"), ("C", "C 2/m"),
]
PROBE_K = [(0, 0, "1/2"), ("1/2", "1/2", 0), ("1/2", "1/2", "1/2"),
           ("1/2", 0, 0), ("1/3", "1/3", 0)]
PROBE_H = [(1, 0, 0), (1, 1, 0), (1, 1, 1), (2, 1, 0), (0, 0, 0), (0, 0, 2)]


def test_the_product_formula_disagrees_with_enumeration_on_every_centring():
    """|Laue orbit of H| × |star of k| is not the satellite multiplicity.

    A3 of issue #257 asks for the ±k / multiplicity test on P, I, F and R as
    well as C, "since the coincidence rule is where the enumeration and a
    formula disagree".  It does — on all five, and in **both** directions,
    which is stronger than the WP's "minus coincidences" wording admits:

    * the product over-counts when two operations of the Laue group send
      H + k to the same Q (their images of H and of k are correlated, being
      images under the same R);
    * it *under*-counts because ``star`` reduces each arm Rᵀk back into the
      first cell, which shifts the parent by a reciprocal-lattice vector, so
      the sum RᵀH + Rᵀk need not be a member of orbit(H) plus an arm.

    Measured pairs are printed by this test's failure message; the assertion is
    that at least one disagreement exists per centring, so the formula can
    never be quietly substituted for the enumeration.
    """
    disagreements: dict[str, list[str]] = {}
    for centring, symbol in CENTRING_CASES:
        found: list[str] = []
        for k in PROBE_K:
            n_star = len(star(symbol, k))
            for h in PROBE_H:
                orbit_h = len(reflection_orbits(symbol, np.array([h]))[0])
                enumerated = len(satellite_orbit(symbol, h, 1, k))
                if enumerated != orbit_h * n_star:
                    found.append(
                        f"k={format_kvector(k)} H={h}: enumerated "
                        f"{enumerated}, formula {orbit_h}x{n_star}="
                        f"{orbit_h * n_star}")
        disagreements[centring] = found
        assert found, (
            f"{centring} ({symbol}): the product formula agreed with the "
            "enumeration on every probe, so this control proves nothing")
    # both directions are represented somewhere, which is the part the WP's
    # "minus coincidences" wording does not cover
    assert any("enumerated 24, formula 6x3=18" in row
               for row in disagreements["P"]), disagreements["P"]


def test_a_satellite_orbit_is_a_multiplicity():
    """|orbit| divides |Laue group with Friedel| — orbit-stabiliser, enumerated.

    This is the invariant ``site_orbit`` asserts one rank over, and it is the
    honest replacement for the product formula: a count that fails it is not a
    multiplicity, whatever a formula says.
    """
    for _centring, symbol in CENTRING_CASES:
        sg = get_spacegroup(symbol)
        order = 2 * len(rotation_matrices(sg))     # Rᵀ and −Rᵀ
        for k in PROBE_K:
            for h in PROBE_H:
                n = len(satellite_orbit(symbol, h, 1, k))
                assert order % n == 0, (symbol, k, h, n, order)


def test_the_generated_multiplicity_is_the_enumerated_orbit():
    """The ``ReflectionSet`` multiplicity is the orbit it claims to count."""
    refl = satellite_reflections("P 6_3 c m", (5.0, 5.0, 7.0, 90, 90, 120),
                                 LAMBDA, TT_MAX, ("1/3", "1/3", 0))
    assert len(refl) > 10
    for i in range(0, len(refl), 7):
        h = tuple(int(v) for v in refl.hkl[i])
        m = int(refl.satellite_order[i])
        assert len(satellite_orbit("P 6_3 c m", h, m, ("1/3", "1/3", 0))) \
            == int(refl.multiplicity[i])


# ============================================================ negative controls


def test_applying_structure_absences_to_a_satellite_loses_reflections():
    """The naive error the WP names, run as a control on P 2₁/c.

    A glide or a screw axis is a condition on the *nuclear structure factor*.
    A satellite has no nuclear structure factor, so those conditions say
    nothing about where it may sit — only the centring conditions, which are
    conditions on the *lattice*, do.  ``P b c a`` has three glide planes and a
    primitive lattice, so the correct answer applies nothing and the naive one
    applies all of them.

    **The control does not fire on every group and k**, which is worth knowing
    before trusting a single case: the Laue-orbit merge rescues a dropped
    parent whenever another member of the same orbit survives, so ``P 2₁/c``
    with k = (0, 0, ½) measures 83 either way.  The pairs below were chosen by
    measuring, not by reading the symbol.
    """
    cell = (5.0, 6.0, 7.0, 90.0, 90.0, 90.0)
    for symbol, cel, k, lo, hi in [
        ("P b c a", cell, (0, 0, "1/2"), 41, 51),
        ("P 21/c", (5.0, 6.0, 7.0, 90.0, 95.0, 90.0), ("1/2", 0, 0), 69, 80),
        ("R -3 c:H", (5.0, 5.0, 7.0, 90.0, 90.0, 120.0), (0, 0, "1/2"), 13, 19),
    ]:
        args = (symbol, cel, LAMBDA, TT_MAX, k)
        correct = satellite_reflections(*args)
        naive = satellite_reflections(*args, apply_structure_absences=True)
        assert (len(naive), len(correct)) == (lo, hi), (
            f"{symbol} k={format_kvector(k)}: measured "
            f"{len(naive)} naive against {len(correct)} correct")
        assert len(naive) < len(correct)
    # on a group with no glide or screw the two must agree exactly, which is
    # what makes the differences above attributable to those conditions
    same = ("P m m m", CELL, LAMBDA, TT_MAX, (0, 0, "1/2"))
    assert len(satellite_reflections(*same)) == \
        len(satellite_reflections(*same, apply_structure_absences=True))


def _orbit_with_untransposed_rotations(symbol, hkl, m, k) -> int:
    """The satellite orbit computed with R instead of Rᵀ — the M-5 trap."""
    sg = get_spacegroup(symbol)
    rot = np.rint(rotation_matrices(sg)).astype(np.int64)   # NOT transposed
    images_op = np.concatenate([rot, -rot], axis=0)
    kk = [Fraction(str(c)) for c in k]
    q = 1
    for c in kk:
        q = q * c.denominator // np.gcd(q, c.denominator)
    q = int(q)
    base = (q * np.asarray(hkl, dtype=np.int64)
            + int(m) * np.array([int(c * q) for c in kk], dtype=np.int64))
    images = np.einsum("mij,j->mi", images_op, base)
    return len({tuple(int(v) for v in im) for im in images})


def test_using_r_instead_of_r_transpose_changes_the_count_on_a_hexagonal_cell():
    """The reciprocal-space action is Rᵀ, and here it is visible.

    {Rᵀ} is a group too, so an orbit *count* is right either way in an
    orthogonal setting and the trap is invisible there — which is exactly why
    M-5 asks for a trigonal or hexagonal cell.  On P 6₃cm the two answers
    differ for a satellite of k = (⅓, ⅓, 0).
    """
    probes = [(1, 0, 0), (1, 1, 0), (2, 1, 0), (1, 0, 1), (2, 0, 1),
              (1, 2, 3), (3, 1, 0), (0, 1, 2)]
    measured = {}
    for symbol, k in [("P 6_3 c m", (0, 0, "1/2")),
                      ("R -3 c:H", (0, 0, "1/2"))]:
        differing = [
            (h, len(satellite_orbit(symbol, h, 1, k)),
             _orbit_with_untransposed_rotations(symbol, h, 1, k))
            for h in probes
            if len(satellite_orbit(symbol, h, 1, k))
            != _orbit_with_untransposed_rotations(symbol, h, 1, k)]
        measured[symbol] = differing
        assert differing, (
            f"{symbol}: R and Rᵀ gave the same orbit size for every probe on "
            "a hexagonal cell, so this control cannot see the transpose trap")
    # on P 6₃cm the wrong action *over*-counts and on R -3 c it does both, so
    # a test that only checked "the count is smaller" would miss half of it
    assert any(a > b for _h, a, b in measured["P 6_3 c m"])
    assert any(a < b for _h, a, b in measured["R -3 c:H"])
    # and the control is not simply always-different: in an orthogonal setting
    # the two sets of matrices coincide and the counts must agree
    for h in [(1, 0, 0), (1, 1, 0), (1, 1, 1)]:
        assert len(satellite_orbit("P m m m", h, 1, (0, 0, "1/2"))) == \
            _orbit_with_untransposed_rotations("P m m m", h, 1, (0, 0, "1/2"))


# ============================================================== the schema field


def test_any_spelling_of_k_is_stored_canonically():
    for spelling in [(0, 0, 0.5), ("0", "0", "1/2"),
                     (Fraction(0), Fraction(0), Fraction(1, 2)),
                     (0, 0, Fraction(2, 4))]:
        assert _phase(spelling).propagation_vector == ("0", "0", "1/2")
    # and the stored form survives a JSON round trip byte for byte
    phase = _phase((0, 0, 0.5))
    again = rx.Phase.model_validate_json(phase.model_dump_json())
    assert again.propagation_vector == phase.propagation_vector


def test_an_incommensurate_k_is_refused_by_name():
    with pytest.raises(ValidationError, match="incommensurate"):
        _phase((0, 0, 0.3123))


def test_k_equal_to_zero_is_refused_and_the_test_respects_centring():
    """A k that is a reciprocal-lattice vector is k = 0 and cannot be declared.

    Every satellite would land on a nuclear line: the reflection list would be
    exactly duplicated and no extraction could separate the two intensities.
    The test is the centring-aware one, so (0, 0, 1) is k = 0 on P and a
    perfectly good propagation vector on I.
    """
    with pytest.raises(ValidationError, match="k = 0"):
        _phase((0, 0, 1))
    with pytest.raises(ValidationError, match="k = 0"):
        _phase((0, 0, 0))
    # on a body-centred lattice (0, 0, 1) violates h + k + l = 2n, so it is not
    # a reciprocal-lattice vector and is a legitimate k
    assert _phase((0, 0, 1), symbol="I 4/m m m",
                  cell=(4.0, 4.0, 6.0, 90, 90, 90)).propagation_vector \
        == ("0", "0", "1")
    # the function behind the validator says the same thing on its own
    with pytest.raises(ValueError, match="k = 0"):
        check_propagation_vector("P m m m", (0, 0, 1))


def test_a_phase_carries_at_most_one_propagation_vector():
    """Structural, not a validator: the field is one triple.

    "More than one k on a phase" is a WP-1326 non-goal, and the honest way to
    fence it is a type that cannot express two.
    """
    with pytest.raises(ValidationError):
        _phase([(0, 0, "1/2"), ("1/2", 0, 0)])


def test_a_moment_model_beside_a_k_is_refused_and_the_hook_is_declared():
    """The refusal WP-1327 trips, and the hook it trips is still one tuple.

    Written and tested here before ``Phase.magnetic_symmetry`` existed, with
    ``MOMENT_MODEL_FIELDS`` empty so that the loop in the validator was a
    declared hook rather than dead code.  WP-1327 added the one field name and
    nothing else: the assertion below moved from ``== ()`` to naming it, which
    is the whole cost the hook was built to have.  The end-to-end refusal on a
    real phase lives in ``tests/test_magnetic.py``.
    """
    assert MOMENT_MODEL_FIELDS == ("magnetic_symmetry",)
    refuse_moment_model_with_k("Fe", [])          # nothing declared: silent
    with pytest.raises(ValueError, match="same thing"):
        refuse_moment_model_with_k("Fe", ["magnetic_space_group"])


# =========================================================== the compiled model


def test_a_phase_without_a_k_is_bit_identical():
    """Every number a fixture pins is unchanged with ``propagation_vector=None``.

    The acceptance line of WP-1326, measured rather than argued: the whole
    calculated profile, the reflection list and the tick positions are hashed
    against a model compiled from a phase that never heard of a propagation
    vector.  ``ReflectionSet.satellite_order`` is ``None`` there and
    ``CompiledPhase.nuclear_mask`` too, so the mask multiply never happens and
    the arithmetic is the arithmetic that ran before this WP existed.
    """
    structure = rx.Structure(phases=[_phase(None)])
    instrument = _neutron()
    model = compile_model(structure, instrument, _pattern())
    values = _values(structure, instrument)
    y = np.asarray(model.evaluate(values), dtype=np.float64)
    cp = model.phases[0]

    assert cp.satellites is None and cp.nuclear_mask is None
    assert cp.reflections.satellite_order is None
    assert cp.reflections.index is cp.reflections.hkl   # the same array object
    digest = hashlib.sha256(y.tobytes()).hexdigest()
    # the reference is this same tree with the field never mentioned, which is
    # what a shipped fixture is; recomputing it here is the point — the hash
    # exists so a later change to the satellite path that leaked into the
    # nuclear one fails rather than shifting a golden.
    plain = compile_model(rx.Structure(phases=[_phase()]), instrument,
                          _pattern())
    y_plain = np.asarray(plain.evaluate(values), dtype=np.float64)
    assert hashlib.sha256(y_plain.tobytes()).hexdigest() == digest


def test_a_rietveld_stage_contributes_exactly_zero_at_a_satellite():
    """Declaring k adds reflections and moves no calculated intensity at all.

    Bit-identical, not "close": this rung computes no magnetic structure
    factor, so the honest contribution at Q = H ± k is zero and the nuclear
    profile must come back unchanged to the last bit.
    """
    instrument = _neutron()
    pattern = _pattern()
    without = rx.Structure(phases=[_phase(None)])
    with_k = rx.Structure(phases=[_phase((0, 0, "1/2"))])
    y0 = np.asarray(compile_model(without, instrument, pattern).evaluate(
        _values(without, instrument)), dtype=np.float64)
    model = compile_model(with_k, instrument, pattern)
    y1 = np.asarray(model.evaluate(_values(with_k, instrument)),
                    dtype=np.float64)
    assert y1.tobytes() == y0.tobytes()

    cp = model.phases[0]
    assert cp.satellites is not None and len(cp.satellites) > 0
    assert int(cp.reflections.is_satellite.sum()) == len(cp.satellites)
    assert len(cp.reflections) == \
        len(compile_model(without, instrument, pattern).phases[0].reflections) \
        + len(cp.satellites)
    # the reflection list is still sorted by descending d after the merge, so
    # the Pawley overlap grouping (which walks neighbours) still sees
    # neighbours
    assert np.all(np.diff(cp.reflections.d) <= 1e-12)


def test_le_bail_puts_intensity_on_the_satellites():
    """The extraction is the measurement: a satellite row is a row it can fill.

    Positive arm: with satellite peaks in the data the extracted intensities on
    the satellite rows rise far above their seed.  Negative arm: on a pattern
    with *no* satellite intensity they are driven to the floor, so the test
    cannot pass by the rows merely existing.
    """
    instrument = _neutron()
    with_k = rx.Structure(phases=[_phase((0, 0, "1/2"))])
    values = _values(with_k, instrument)


    nuclear = np.asarray(compile_model(
        rx.Structure(phases=[_phase(None)]), instrument,
        _pattern()).evaluate(values), dtype=np.float64)

    # a pattern with satellite peaks: draw them through the model itself, so
    # they land exactly where a satellite is and nowhere else
    seed = compile_model(with_k, instrument, _pattern(), mode="lebail")
    cp = seed.phases[0]
    sat = cp.reflections.is_satellite
    cp.hkl_intensity = np.where(sat, 2000.0, 0.0)
    magnetic = np.asarray(seed.evaluate(values), dtype=np.float64)
    assert magnetic.max() > 0.05 * nuclear.max(), "the injected arm is invisible"

    # Read the **isolated** satellites, more than one FWHM from any nuclear
    # line.  A satellite sitting under a nuclear peak legitimately takes a
    # share of the partition — that is what a partition does — so including it
    # would blunt the negative arm into a statement about overlap rather than
    # about extraction.
    cell = tuple(values[f"phases.0.cell.{key}"]
                 for key in ("a", "b", "c", "alpha", "beta", "gamma"))
    refl = cp.reflections
    tt_all = np.asarray(refl.two_theta(cell, LAMBDA), dtype=np.float64)
    ticks = tt_all[~sat & np.isfinite(tt_all)]
    gap = np.min(np.abs(tt_all[:, None] - ticks[None, :]), axis=1)
    isolated = sat & np.isfinite(tt_all) & (gap > 1.0)
    assert int(isolated.sum()) >= 5, int(isolated.sum())

    measured = {}
    for label, y_obs in (("with", nuclear + magnetic), ("without", nuclear)):
        model = compile_model(with_k, instrument, _pattern(y_obs),
                              mode="lebail")
        model.lebail_update(values, n_cycles=8)
        got = np.asarray(model.phases[0].hkl_intensity, dtype=np.float64)
        mask = model.phases[0].reflections.is_satellite
        measured[label] = (float(np.median(got[isolated])),
                           float(np.median(got[~mask])))
    with_sat, with_nuc = measured["with"]
    no_sat, no_nuc = measured["without"]
    # positive arm: the extraction puts real intensity on the satellite rows
    assert with_sat > 0.2 * with_nuc, measured
    # negative arm, and it is the one that makes the test mean something: with
    # no satellite intensity in the data the isolated satellite rows are driven
    # to the partition's floor rather than filling themselves
    # It is not exactly zero and cannot be: the windows sit on the tails of
    # the nuclear peaks, and ``net`` is the observed profile above the declared
    # background, so a tail hands out a little intensity.  Measured 29.9
    # against a nuclear median of 1027 (2.9 %), and 2000-scale against that
    # with the arm injected.
    assert no_sat < 0.05 * no_nuc, measured
    assert with_sat > 10.0 * no_sat, measured


def test_the_pawley_block_takes_the_satellites_as_more_rows():
    """A satellite intensity is a column of θ in Pawley mode, like any other.

    The block's dimension, its bounds and its overlap groups all come from
    "the phase's reflections", so the satellites arrive as rows without the
    block knowing what a propagation vector is — which is the whole reason
    they were merged into one list rather than carried beside it.
    """
    instrument = _neutron()
    pattern = _pattern()
    without = rx.Structure(phases=[_phase(None)])
    with_k = rx.Structure(phases=[_phase((0, 0, "1/2"))])
    m0 = compile_model(without, instrument, pattern, mode="pawley")
    m1 = compile_model(with_k, instrument, pattern, mode="pawley")
    assert m1.pawley.n == m0.pawley.n + len(m1.phases[0].satellites)
    assert len(m1.pawley_x0()) == m1.pawley.n
    lo, hi = m1.pawley_bounds()
    assert len(lo) == len(hi) == m1.pawley.n
    assert np.all(lo >= 0.0)          # positivity is a box on every row
    # the overlap grouping sees the satellites: it walks neighbours in the
    # d-sorted list, which the merge kept sorted
    assert len(m1.pawley.groups) > len(m0.pawley.groups)
    assert m1.phases[0].tt_primary is not None
    assert len(m1.phases[0].tt_primary) == len(m1.phases[0].reflections)


def test_the_observation_count_counts_satellites():
    """A satellite is a reflection, and the observation count is reflections."""
    from rietx.optimize.statistics import count_unique_reflections

    instrument = _neutron()
    pattern = _pattern()
    without = rx.Structure(phases=[_phase(None)])
    with_k = rx.Structure(phases=[_phase((0, 0, "1/2"))])
    n0 = count_unique_reflections(compile_model(without, instrument, pattern),
                                  _values(without, instrument))
    n1 = count_unique_reflections(compile_model(with_k, instrument, pattern),
                                  _values(with_k, instrument))
    assert n1 > n0


def test_every_emission_line_gets_a_satellite_tick():
    """Ticks carry every line's positions, satellites included."""
    instrument = rx.Instrument.debye_scherrer(1.5406)   # Kα1/Kα2 doublet
    structure = rx.Structure(phases=[_phase((0, 0, "1/2"))])
    model = compile_model(structure, instrument, _pattern())
    values = _values(structure, instrument)
    cell = tuple(values[f"phases.0.cell.{k}"]
                 for k in ("a", "b", "c", "alpha", "beta", "gamma"))
    cp = model.phases[0]
    for lam in model.line_wavelengths:
        tt = cp.reflections.two_theta(cell, lam)
        assert np.isfinite(tt[cp.reflections.is_satellite]).any()


def test_friedel_merging_makes_the_plus_and_minus_k_sets_one_list():
    """The ±k rule is real and it does **not** change a powder position list.

    This is a correction to how WP-1326 states the rule.  As *sets*,
    {H − k} = −{H + k}, and a powder merges Q with −Q because d(Q) = d(−Q) —
    so the two sets are one list whatever the answer to "is 2k a
    reciprocal-lattice vector?", and every representative comes back at
    m = +1.  Measured on a C lattice with k = (½ 0 0), which is exactly the
    case where ±k are **distinct** vectors: 83 rows either way, the same
    d-spacings.

    Where the rule does bite is the moment model — whether S₋ₖ is an
    independent Fourier component or S\\*ₖ — which is WP-1327's, and the
    multiplicity of a satellite already contains its Friedel mate.  The
    enumeration still runs over both orders, because letting the merge
    collapse them is what *proves* the list complete rather than asserting it.
    """
    cell = (5.0, 6.0, 7.0, 90, 92, 90)
    assert minus_k_is_k("C 2/m", ("1/2", 0, 0)) is False
    plus = satellite_reflections("C 2/m", cell, LAMBDA, TT_MAX, ("1/2", 0, 0))
    minus = satellite_reflections("C 2/m", cell, LAMBDA, TT_MAX, ("-1/2", 0, 0))
    assert len(plus) == len(minus)
    assert np.allclose(np.sort(plus.d), np.sort(minus.d))
    assert set(int(m) for m in plus.satellite_order) == {1}


def test_a_no_k_le_bail_node_gains_exactly_one_null():
    """Review item 6: what a no-k ``ReflectionState`` dump changed, and only that.

    The pre-PR field set is written out literally (``origin/main`` at
    ``b16772f0``), so a new field cannot slip in beside this one unseen.  The
    null is kept rather than excluded, as every optional field here is.
    """
    from rietx.refine import _extract_reflections

    instrument = _neutron()
    structure = rx.Structure(phases=[_phase(None)])
    model = compile_model(structure, instrument, _pattern(), mode="lebail")
    model.phases[0].hkl_intensity = np.ones(len(model.phases[0].reflections))
    (state,) = _extract_reflections(model)
    dumped = json.loads(state.model_dump_json())
    assert dumped.pop("satellite_order") is None
    assert list(dumped) == ["phase_index", "hkl", "intensity", "kind",
                            "stderr", "varied"]


def test_a_le_bail_intensity_is_keyed_by_h_and_the_satellite_order():
    """H alone is not a key: a nuclear row and a satellite row can share it.

    H and H + k are two reflections at two positions carrying two intensities,
    and they have the same parent index.  The fourth index is what keeps a
    checkout from writing one row's intensity into the other's.
    """
    from rietx.refine import _reflection_keys

    cell = (5.0, 6.0, 7.0, 90, 92, 90)
    nuclear = generate_reflections("C 2/m", cell, LAMBDA, TT_MAX)
    sat = satellite_reflections("C 2/m", cell, LAMBDA, TT_MAX, ("1/2", 0, 0))
    merged = merge_satellites(nuclear, sat)

    keys = _reflection_keys(merged.hkl, merged.satellite_order)
    assert len(set(keys)) == len(keys), "two rows share a key"
    # dropping the order collides, which is what the fourth index is for
    three = {(h, k, ll) for h, k, ll, _ in keys}
    assert len(three) < len(keys), (
        "no parent index is shared between a nuclear row and a satellite, so "
        "this fixture cannot show why the order belongs in the key")
    # and a phase with no k produces exactly the old key with a constant 0
    plain = _reflection_keys(nuclear.hkl, None)
    assert all(key[3] == 0 for key in plain)
    assert len(set(plain)) == len(plain)


def test_a_checkpoint_restores_the_satellite_row_and_not_its_parent():
    """The (H, m) key, end to end through the history's own restore path.

    A nuclear row and its satellite share a parent index, so a three-index key
    writes one row's extracted intensity into the other's — silently, and into
    a *fixed point* that a later Le Bail cycle would then walk away from.  The
    round trip below is the assertion that cannot pass by accident: the values
    are made distinguishable per row first.
    """
    from rietx.refine import _extract_reflections, _restore_lebail

    instrument = _neutron()
    with_k = rx.Structure(phases=[_phase((0, 0, "1/2"))])
    model = compile_model(with_k, instrument, _pattern(), mode="lebail")
    n = len(model.phases[0].reflections)
    marked = np.arange(1.0, n + 1.0)
    model.phases[0].hkl_intensity = marked.copy()

    states = _extract_reflections(model)
    assert len(states) == 1
    assert states[0].satellite_order is not None
    assert sorted(set(states[0].satellite_order)) == [0, 1]
    # a parent index really is shared, or this fixture proves nothing
    parents = [tuple(h) for h in states[0].hkl]
    assert len(set(parents)) < len(parents)

    fresh = compile_model(with_k, instrument, _pattern(), mode="lebail")
    fresh.phases[0].hkl_intensity = np.zeros(n)
    _restore_lebail(states, fresh)
    assert np.array_equal(fresh.phases[0].hkl_intensity, marked)


# ================================================= the candidate set (#257 A1/A2)


def test_the_default_generator_is_the_set_the_wp_fixes():
    seven = zone_boundary_candidates("P -1")
    assert [c.vector for c in seven] == [
        "(0, 0, 1/2)", "(0, 1/2, 0)", "(0, 1/2, 1/2)", "(1/2, 0, 0)",
        "(1/2, 0, 1/2)", "(1/2, 1/2, 0)", "(1/2, 1/2, 1/2)"]
    # the two third-order points join on a hexagonal or trigonal lattice
    hexagonal = {c.vector for c in zone_boundary_candidates("P 6_3 c m")}
    assert "(1/3, 1/3, 0)" in hexagonal and "(1/3, 1/3, 1/2)" in hexagonal
    assert "(1/3, 1/3, 0)" not in {c.vector
                                   for c in zone_boundary_candidates("P m m m")}


def test_the_count_falls_with_the_point_group_and_not_with_centring():
    """The WP says "fewer distinct ones under centring". That is not what happens.

    No two members of {0, ½}³ can ever be reciprocal-lattice equivalent,
    whatever the centring: every difference has a half-integer component, and
    the reciprocal lattice is a *sublattice* of the integer grid.  What does
    reduce the count is the **star** — arms of one star generate the identical
    satellite list, so keeping all of them would put exact ties in a ranking
    meant to be read.  Recorded as a test because it is a correction to the
    WP's own text.
    """
    from rietx.crystallography.magnetic.irreps import equivalent_kvectors

    raw = [(Fraction(h, 2), Fraction(k, 2), Fraction(ll, 2))
           for h in (0, 1) for k in (0, 1) for ll in (0, 1)
           if (h, k, ll) != (0, 0, 0)]
    for symbol in ("P -1", "C 2/m", "I 4/m m m", "F m -3 m", "R -3 c:H"):
        for i, a in enumerate(raw):
            for b in raw[i + 1:]:
                assert not equivalent_kvectors(symbol, a, b), (symbol, a, b)
    # the reduction is the point group's: seven on P-1, three on P m -3 m
    assert len(zone_boundary_candidates("P -1")) == 7
    assert len(zone_boundary_candidates("P m -3 m")) == 3
    # and centring alone does not reduce it — C 2/m has the same point group as
    # P 2/m and the same count
    assert len(zone_boundary_candidates("C 2/m")) == \
        len(zone_boundary_candidates("P 2/m"))


def test_arms_of_one_star_generate_the_same_satellite_list():
    """Which is why the generator keeps one representative per star."""
    symbol, cell = "P m -3 m", (4.0, 4.0, 4.0, 90, 90, 90)
    arms = star(symbol, (0, 0, "1/2"))
    assert len(arms) == 3
    lists = [satellite_reflections(symbol, cell, LAMBDA, TT_MAX, arm)
             for arm in arms]
    for other in lists[1:]:
        assert np.allclose(np.sort(other.d), np.sort(lists[0].d))
        assert sorted(other.multiplicity.tolist()) == \
            sorted(lists[0].multiplicity.tolist())


def test_labels_are_positional_and_by_the_plain_vector_with_the_cdml_hook_open():
    """Issue #257 A2: label where there is a label, and do not invent one."""
    candidates = zone_boundary_candidates("P m m m")
    assert [c.name for c in candidates] == [f"k{i + 1}"
                                            for i in range(len(candidates))]
    for c in candidates:
        assert c.vector == format_kvector(c.k)
        assert c.cdml is None, (
            "a CDML label appeared without the k-label tables being sourced; "
            "a made-up label would look like CDML and disagree with it")
        assert c.label == c.vector          # falls back to what is knowable
        assert c.origin == "zone_boundary"


def test_a_generator_that_returns_an_unusable_k_is_refused():
    """A generator is a caller's function, so the arm validates rather than trusts."""
    zero = (KCandidate(k=(Fraction(0),) * 3, name="k1", vector="(0, 0, 0)",
                       origin="test"),)
    with pytest.raises(ValueError, match="k = 0"):
        check_candidate_denominators(zero)
    wild = (KCandidate(k=(Fraction(1, 97), Fraction(0), Fraction(0)),
                       name="k1", vector="(1/97, 0, 0)", origin="test"),)
    with pytest.raises(ValueError, match="commensurate only"):
        check_candidate_denominators(wild)


# ================================================================== the report arm


def _arm_inputs(structure, instrument, k):
    """A compiled model, its ticks, and the satellite positions of ``k``.

    The ticks are the real ones: the arm sorts a residual peak into "on a
    calculated line", "on a reciprocal-lattice point the structure factor
    forbids" and "neither", and handing it an empty tick list would send every
    peak through the lattice test.
    """
    from rietx.crystallography.lattice import two_theta_deg

    model = compile_model(structure, instrument, _pattern())
    values = _values(structure, instrument)
    cell = tuple(values[f"phases.0.cell.{key}"]
                 for key in ("a", "b", "c", "alpha", "beta", "gamma"))
    ticks = np.asarray(model.phases[0].reflections.two_theta(cell, LAMBDA),
                       dtype=np.float64)
    ticks = ticks[np.isfinite(ticks)]
    refl = satellite_reflections(structure.phases[0].space_group, cell,
                                 LAMBDA, TT_MAX, k, two_theta_min=10.0)
    tt = np.asarray(two_theta_deg(refl.d, LAMBDA), dtype=np.float64)
    tt = tt[np.isfinite(tt) & (tt > 12.0) & (tt < TT_MAX - 1.0)]
    return model, values, np.sort(tt)[:8], ticks


def test_the_arm_ranks_the_true_k_first_by_generated_positions():
    """The positive arm, scored on positions the generator produced, not by eye."""
    instrument = _neutron()
    structure = rx.Structure(phases=[_phase(None)])
    model, values, peaks, ticks = _arm_inputs(structure, instrument,
                                              (0, 0, "1/2"))
    evidence = analyse_satellites(model, values, residual_two_theta=peaks,
                                  ticks=ticks, structure=structure)
    assert len(evidence) == 1
    arm = evidence[0]
    assert arm.radiation == "neutron"
    assert arm.n_residual_peaks == len(peaks)
    # ``P m m m`` has no systematic absence, so every reciprocal-lattice point
    # carries a tick and the k = 0 bucket must stay empty here
    assert arm.excess_on_absent_lattice_lines == 0
    assert arm.n_unexplained >= 5, arm.note
    assert arm.candidates[0].vector == "(0, 0, 1/2)"
    assert arm.candidates[0].matched == arm.n_unexplained
    assert arm.candidates[0].matched_fraction == pytest.approx(1.0)
    # never a singleton: the whole enumerated set is published, ranked
    assert len(arm.candidates) == len(zone_boundary_candidates("P m m m"))
    # and the ranking is a ranking — the runner-up does not also explain
    # everything, or the top row would mean nothing
    assert arm.candidates[1].matched < arm.candidates[0].matched
    runner = arm.candidates[1]
    assert (f"runner-up {runner.vector} indexes {runner.matched} "
            f"(from {runner.n_satellites})") in arm.note
    assert "no chance baseline" in arm.note and "a tie" not in arm.note
    assert arm.generator == "zone_boundary_candidates"
    assert "incommensurate" in arm.note


def test_the_note_carries_the_comparison_that_judges_the_best_candidate():
    """Review item 2: the best's positions and the runner-up ride in the note.

    Peaks at the satellites of (1/3, 0, 0), which the zone-boundary set does
    not contain, so whatever it indexes is chance — the no-order shape.  A note
    naming its best without ``n_satellites`` and the runner-up's ``matched``
    would read as a finding.
    """
    instrument = _neutron()
    structure = rx.Structure(phases=[_phase(None)])
    model, values, peaks, ticks = _arm_inputs(structure, instrument,
                                              ("1/3", 0, 0))
    arm = analyse_satellites(model, values, residual_two_theta=peaks,
                             ticks=ticks)[0]
    best, runner = arm.candidates[0], arm.candidates[1]
    assert 0 < best.matched < arm.n_unexplained, arm.note
    assert (f"indexes {best.matched} of them" in arm.note
            and f"from {best.n_satellites} satellite position(s)" in arm.note)
    # measured: (0, 0, 1/2) and (1/2, 0, 0) each index 1 of 5, from 31 and
    # 30 positions — a tie, and the note must say the ranking chose nothing
    assert runner.matched == best.matched, arm.note
    assert (f"runner-up {runner.vector} also indexes {runner.matched} "
            f"(from {runner.n_satellites})") in arm.note
    assert "a tie" in arm.note and "chooses nothing" in arm.note


def test_the_arm_takes_a_generator_and_a_different_set_changes_the_ranking():
    """Issue #257 A1: the candidate set is a parameter from day one."""
    instrument = _neutron()
    structure = rx.Structure(phases=[_phase(None)])
    model, values, peaks, ticks = _arm_inputs(structure, instrument,
                                              ("1/3", 0, 0))

    default = analyse_satellites(model, values, residual_two_theta=peaks,
                                 ticks=ticks)[0]
    # (1/3, 0, 0) is not in the zone-boundary set, so the default cannot
    # explain these peaks — which is the WP's own "a good pattern can score
    # nothing" case
    assert default.candidates[0].matched < default.n_unexplained

    def thirds(space_group):
        return (KCandidate(k=(Fraction(1, 3), Fraction(0), Fraction(0)),
                           name="k1", vector="(1/3, 0, 0)", origin="test"),
                KCandidate(k=(Fraction(0), Fraction(1, 3), Fraction(0)),
                           name="k2", vector="(0, 1/3, 0)", origin="test"))

    swapped = analyse_satellites(model, values, residual_two_theta=peaks,
                                 ticks=ticks, generator=thirds)[0]
    assert swapped.generator == "thirds"
    assert swapped.candidates[0].vector == "(1/3, 0, 0)"
    assert swapped.candidates[0].matched == swapped.n_unexplained
    assert swapped.n_unexplained >= 5
    assert [c.vector for c in swapped.candidates] != \
        [c.vector for c in default.candidates]


def test_the_arm_names_the_k_zero_ambiguity_when_the_excess_is_on_nuclear_lines():
    """A residual peak on a calculated line is scored against no candidate."""
    instrument = _neutron()
    structure = rx.Structure(phases=[_phase(None)])
    model = compile_model(structure, instrument, _pattern())
    values = _values(structure, instrument)
    cell = tuple(values[f"phases.0.cell.{k}"]
                 for k in ("a", "b", "c", "alpha", "beta", "gamma"))
    ticks = np.asarray(model.phases[0].reflections.two_theta(cell, LAMBDA),
                       dtype=np.float64)
    ticks = np.sort(ticks[np.isfinite(ticks)])[:3]
    arm = analyse_satellites(model, values, residual_two_theta=ticks,
                             ticks=ticks)[0]
    assert arm.n_residual_peaks == 3
    assert arm.excess_on_nuclear_lines == 3
    assert arm.excess_on_absent_lattice_lines == 0
    assert arm.n_unexplained == 0
    assert arm.candidates == []          # nothing to score, and not a verdict
    assert "sits on nuclear lines" in arm.note
    assert "above its ordering temperature" in arm.note


def _absent_001_arm(instrument):
    """The arm on one residual peak at the absent (0 0 1) of ``P 4₂/mnm``."""
    from rietx.crystallography.lattice import two_theta_deg

    cell = (4.57539, 4.57539, 8.85381, 90.0, 90.0, 90.0)
    structure = rx.Structure(phases=[_phase(None, symbol="P 42/m n m",
                                            cell=cell)])
    model = compile_model(structure, instrument, _pattern())
    values = _values(structure, instrument)
    lam = float(model.line_lambdas(values)[0])
    tt_001 = float(two_theta_deg(np.array([cell[2]]), lam)[0])
    ticks = np.asarray(model.phases[0].reflections.two_theta(cell, lam),
                       dtype=np.float64)
    ticks = ticks[np.isfinite(ticks)]
    return analyse_satellites(model, values, residual_two_theta=[tt_001],
                              ticks=ticks)[0]


def test_a_forbidden_lattice_peak_on_neutrons_names_all_four_causes():
    """Review item 1: the arm names what it cannot exclude, magnetism among them.

    "Forbidden" is forbidden under the group the fit *assumed*, so a peak there
    is no result about magnetism: a nuclear group lower than the assumed one,
    λ/2 and an impurity line put intensity there too.  On neutrons a k = 0
    magnetic structure is the fourth, because an axial structure factor can
    obey the complementary absence rule (Gallego et al. 2012).
    """
    arm = _absent_001_arm(_neutron(fwhm_deg=0.35))
    assert arm.radiation == "neutron"
    assert arm.excess_on_absent_lattice_lines == 1
    for cause in ("too high", "λ/2", "impurity", "k = 0 magnetic structure"):
        assert cause in arm.note, (cause, arm.note)
    assert "four causes" in arm.note
    assert "result rather than an ambiguity" not in arm.note
    assert arm.candidates == []


def test_a_forbidden_lattice_peak_on_x_rays_has_no_magnetic_reading():
    """The same peak on an X-ray histogram: three causes, none magnetic."""
    # λ as the neutron case, so (0 0 1) lands inside the same grid
    arm = _absent_001_arm(rx.Instrument.debye_scherrer(LAMBDA))
    assert arm.radiation == "xray"
    assert arm.excess_on_absent_lattice_lines == 1
    for cause in ("too high", "λ/2", "impurity"):
        assert cause in arm.note, (cause, arm.note)
    assert "three causes" in arm.note
    assert "k = 0 magnetic" not in arm.note
    assert "Gallego" not in arm.note


def test_the_arm_calls_a_peak_on_a_forbidden_lattice_point_the_k_zero_signature():
    """A peak on a forbidden lattice point, and the correction the Cr₂WO₆ data forced.

    Intensity at a reciprocal-lattice point the assumed group's glide or screw
    forbids needs no k — whatever put it there (the two tests above name the
    candidates) — so it must not be handed to the candidate ranking, which
    would "explain" it with whichever k happens to put a satellite nearby.

    ``P 4₂/mnm`` with the Cr₂WO₆ cell: (0 0 1) is a reciprocal-lattice point
    and a systematic absence, so it carries no tick.
    """
    from rietx.crystallography.lattice import two_theta_deg
    from rietx.crystallography.satellites import lattice_two_theta

    cell = (4.57539, 4.57539, 8.85381, 90.0, 90.0, 90.0)
    instrument = _neutron(fwhm_deg=0.35)
    structure = rx.Structure(phases=[_phase(None, symbol="P 42/m n m",
                                            cell=cell)])
    model = compile_model(structure, instrument, _pattern())
    values = _values(structure, instrument)
    tt_001 = float(two_theta_deg(np.array([cell[2]]), LAMBDA)[0])
    assert 15.0 < tt_001 < 16.5, tt_001
    # it is a lattice position and it is not a tick
    lattice = lattice_two_theta("P 42/m n m", cell, LAMBDA, TT_MAX,
                                two_theta_min=10.0)
    assert np.min(np.abs(lattice - tt_001)) < 1e-6
    ticks = np.asarray(model.phases[0].reflections.two_theta(cell, LAMBDA),
                       dtype=np.float64)
    ticks = ticks[np.isfinite(ticks)]
    assert np.min(np.abs(ticks - tt_001)) > 1.0

    arm = analyse_satellites(model, values, residual_two_theta=[tt_001],
                             ticks=ticks)[0]
    assert arm.excess_on_absent_lattice_lines == 1
    assert arm.excess_on_nuclear_lines == 0
    assert arm.n_unexplained == 0
    assert arm.candidates == []
    assert "forbids" in arm.note and "k = 0" in arm.note


def test_the_arm_says_an_x_ray_satellite_is_a_superstructure_reflection():
    """And the declared k still contributes exactly zero calculated intensity."""
    instrument = rx.Instrument.debye_scherrer(1.5406)
    structure = rx.Structure(phases=[_phase((0, 0, "1/2"))])
    model = compile_model(structure, instrument, _pattern())
    values = _values(structure, instrument)
    arm = analyse_satellites(model, values, residual_two_theta=[25.0],
                             ticks=[], structure=structure)[0]
    assert arm.radiation == "xray"
    assert "superstructure" in arm.note
    assert arm.declared_k == ["0", "0", "1/2"]

    # zero satellite intensity, measured: the Rietveld profile is bit-identical
    # to the one the same phase draws without a propagation vector
    plain = rx.Structure(phases=[_phase(None)])
    y0 = np.asarray(compile_model(plain, instrument, _pattern()).evaluate(
        _values(plain, instrument)), dtype=np.float64)
    y1 = np.asarray(model.evaluate(values), dtype=np.float64)
    assert y1.tobytes() == y0.tobytes()
    peaks = model.phase_peaks(0, values)
    sat = model.phases[0].reflections.is_satellite
    for _pos, _w1, _w2, intensity in peaks:
        assert np.all(np.asarray(intensity)[sat] == 0.0)


def test_the_arm_reports_the_pm_k_rule_and_the_star_beside_each_candidate():
    instrument = _neutron()
    structure = rx.Structure(phases=[_phase(None, symbol="C 2/m",
                                            cell=(5.0, 6.0, 7.0, 90, 92, 90))])
    model = compile_model(structure, instrument, _pattern())
    values = _values(structure, instrument)
    arm = analyse_satellites(model, values, residual_two_theta=[25.0],
                             ticks=[])[0]
    by_vector = {c.vector: c for c in arm.candidates}
    assert by_vector["(1/2, 0, 0)"].minus_k_distinct is True
    assert by_vector["(0, 0, 1/2)"].minus_k_distinct is False
    assert all(c.n_satellites > 0 for c in arm.candidates)
    assert all(c.star_size >= 1 for c in arm.candidates)


def test_a_k_zero_signature_is_not_handed_to_the_candidate_ranking():
    """The Cr₂WO₆ shape, synthetic: intensity at absent lattice points only.

    Positive arm and negative control in one fixture.  Intensity is injected at
    the systematically absent (0 0 1) and (1 0 2) of ``P 4₂/mnm`` — where a
    k = 0 magnetic structure puts it — and at nothing else.  The arm must
    classify those as the k = 0 signature and hand **nothing** to the
    candidate ranking; a version that scored them would report a zone-boundary
    k that is not there, which is the confident wrong singleton this rule
    prevents.
    """
    from rietx.crystallography.lattice import two_theta_deg

    cell = (4.57539, 4.57539, 8.85381, 90.0, 90.0, 90.0)
    instrument = _neutron(fwhm_deg=0.35)
    structure = rx.Structure(phases=[_phase(None, symbol="P 42/m n m",
                                            cell=cell)])
    model = compile_model(structure, instrument, _pattern())
    values = _values(structure, instrument)
    d_absent = np.array([[0, 0, 1], [1, 0, 2]], dtype=np.float64)
    from rietx.crystallography.lattice import d_spacings
    tt = np.asarray(two_theta_deg(d_spacings(d_absent, *cell), LAMBDA),
                    dtype=np.float64)
    ticks = np.asarray(model.phases[0].reflections.two_theta(cell, LAMBDA),
                       dtype=np.float64)
    ticks = ticks[np.isfinite(ticks)]

    arm = analyse_satellites(model, values, residual_two_theta=tt,
                             ticks=ticks)[0]
    assert arm.excess_on_absent_lattice_lines == 2, arm.note
    assert arm.n_unexplained == 0
    assert arm.candidates == []
    assert "forbids" in arm.note

    # the control: the same two positions on a group with **no** absences are
    # ordinary nuclear lines, so the k = 0 bucket stays empty and the arm says
    # the excess is on nuclear lines instead
    plain = rx.Structure(phases=[_phase(None, symbol="P 4/m m m", cell=cell)])
    plain_model = compile_model(plain, instrument, _pattern())
    plain_values = _values(plain, instrument)
    plain_ticks = np.asarray(
        plain_model.phases[0].reflections.two_theta(cell, LAMBDA),
        dtype=np.float64)
    plain_ticks = plain_ticks[np.isfinite(plain_ticks)]
    control = analyse_satellites(plain_model, plain_values,
                                 residual_two_theta=tt, ticks=plain_ticks)[0]
    assert control.excess_on_absent_lattice_lines == 0, control.note
    assert control.excess_on_nuclear_lines == 2, control.note


def test_the_arm_reaches_the_report_end_to_end():
    """`Refinement.report()` carries the arm, and it speaks on the abstained branch.

    The pattern is a nuclear profile plus intensity drawn at the satellites of
    (0, 0, ½) and nowhere else; the model fitted to it knows nothing of any k,
    so those peaks reach Layer 0 as unexplained and the arm has to name the k
    that put them there.
    """
    instrument = _neutron(fwhm_deg=0.3)
    plain = rx.Structure(phases=[_phase(None)])
    with_k = rx.Structure(phases=[_phase((0, 0, "1/2"))])
    values = _values(with_k, instrument)

    nuclear = np.asarray(compile_model(plain, instrument, _pattern()).evaluate(
        _values(plain, instrument)), dtype=np.float64)
    seed = compile_model(with_k, instrument, _pattern(), mode="lebail")
    cp = seed.phases[0]
    cp.hkl_intensity = np.where(cp.reflections.is_satellite, 900.0, 0.0)
    magnetic = np.asarray(seed.evaluate(values), dtype=np.float64)

    data = _pattern(nuclear + magnetic + 20.0)
    ref = rx.Refinement(plain, instrument)
    result = ref.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"]),
    ]))
    assert result.statistics.rwp > 0.0
    report = ref.report()
    assert report.satellites, "the arm did not reach the report"
    arm = report.satellites[0]
    assert arm.n_unexplained > 0, arm.note
    assert arm.candidates[0].vector == "(0, 0, 1/2)", [
        (c.vector, c.matched) for c in arm.candidates]
    assert arm.candidates[0].matched >= 0.5 * arm.n_unexplained
    assert arm.declared_k is None
    # and the report round-trips through JSON with the new section
    again = type(report).model_validate_json(report.model_dump_json())
    assert again.satellites[0].candidates[0].vector == "(0, 0, 1/2)"

    # obs/calc/diff for visual inspection (tests/output/, gitignored): the
    # satellite peaks the nuclear model puts nothing under are what the
    # difference curve is made of, and Rwp alone does not show where they are
    from pathlib import Path

    from rietx.viz.plots import plot_result
    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    plot_result(result, path=str(out / "satellites_k_00half.png"))


# ================================================ a satellite is named by (H, m)
#
# Review item 3 (#468): every reader that *identifies* a reflection or
# computes its geometry takes the satellite's own index H + m·k or its (H, m)
# label, never the parent H alone.  The readers that want the parent — the
# structure factor, the Le Bail key's H half — are the ones that already read
# ``hkl`` beside ``satellite_order``.


def test_a_stephens_phase_with_k_gives_its_satellites_their_own_d():
    """Finite, distinct satellite d from H + m·k — never the parent's.

    The satellite of (0, 0, 0) at k = (0, 0, ½) sits at d = 2c; read off the
    parent it would be d = ∞, and every other satellite would share its
    parent's d and Stephens direction.
    """
    from rietx.crystallography.lattice import d_spacings
    from rietx.crystallography.stephens import monomial_matrix
    from rietx.report.strain import _components, analyse_strain
    from rietx.schemas.structure import StephensStrain

    phase = _phase((0, 0, "1/2"))
    phase.microstrain = StephensStrain.isotropic(800.0, phase.cell)
    structure = rx.Structure(phases=[phase])
    instrument = _neutron()
    model = compile_model(structure, instrument, _pattern())
    values = _values(structure, instrument)
    refl = model.phases[0].reflections
    sat = refl.is_satellite
    assert sat.any()

    d, *_rest = _components(model, values, 0)
    assert np.all(np.isfinite(d))
    np.testing.assert_array_equal(d, d_spacings(refl.index, *CELL))
    origin = sat & np.all(refl.hkl == 0, axis=1)
    assert origin.sum() == 1
    assert d[origin][0] == pytest.approx(2.0 * CELL[2])
    # a satellite and its parent's nuclear row are two d-spacings
    nuclear_d = dict(zip(map(tuple, refl.hkl[~sat]), d[~sat], strict=True))
    shared = [i for i in np.flatnonzero(sat) if tuple(refl.hkl[i]) in nuclear_d]
    assert shared
    assert all(d[i] != nuclear_d[tuple(refl.hkl[i])] for i in shared)
    # the compiled Stephens directions are the satellites' too
    np.testing.assert_array_equal(model.phases[0].strain_monomials,
                                  monomial_matrix(refl.index))
    # and the analysis runs, never naming a satellite by a parent it is not
    for row in analyse_strain(model, values):
        for name in (row.broadest_hkl, row.narrowest_hkl):
            assert name is None or len(name) == 3


def test_a_satellite_tick_is_labelled_by_its_order_not_its_parent():
    """(0, 0, ½) is ``[0, 0, 0, 1]``, never ``(0 0 0)``; nuclear rows keep three."""
    instrument = _neutron()
    structure = rx.Structure(phases=[_phase((0, 0, "1/2"))])
    ref = rx.Refinement(structure, instrument, history=False)
    result = ref.fit(_pattern(), plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale"], max_iter=2)]))
    labels = result.tick_hkl["Fe"]
    assert len(labels) == len(result.ticks["Fe"])
    assert [0, 0, 0] not in labels
    assert [0, 0, 0, 1] in labels
    assert [0, 0, 1] in labels and [0, 0, 1, 1] in labels
    assert all(len(r) == 3 or (len(r) == 4 and r[3] != 0) for r in labels)
    # the live snapshot's tick list carries the same labels
    from rietx.viz.snapshot import stage_ticks

    snap = stage_ticks(compile_model(structure, instrument, _pattern()),
                       _values(structure, instrument))["phase 0"]["hkl"]
    assert [0, 0, 0, 1] in snap and [0, 0, 0] not in snap


def test_plus_k_and_minus_k_satellites_of_one_parent_carry_two_labels():
    """Where ±k are two vectors, one H carries both orders and two labels.

    ``P -3`` with k = (⅓, ⅓, 0): 2k is not a reciprocal-lattice vector, so some
    parents have a satellite at H + k *and* at H − k.  Measured: 56 rows on 50
    parents.  Labelled by H alone those rows collide; by (H, m) none does.
    """
    from rietx.crystallography.symmetry import (
        reflection_label,
        reflection_label_row,
    )

    refl = satellite_reflections("P -3", (5.0, 5.0, 6.0, 90, 90, 120), LAMBDA,
                                 TT_MAX, ("1/3", "1/3", 0))
    assert set(int(m) for m in refl.satellite_order) == {-1, 1}
    by_h = {tuple(h) for h in refl.hkl}
    assert len(by_h) < len(refl)
    rows = [tuple(reflection_label_row(r)) for r in refl.hklm]
    strings = [reflection_label(r) for r in refl.hklm]
    assert len(set(rows)) == len(refl) and len(set(strings)) == len(refl)
    assert any(s.endswith("+k") for s in strings)
    assert any(s.endswith("-k") for s in strings)
    # the nuclear spelling is what a diagnostic printed before
    assert reflection_label((1, 0, -2, 0)) == str((1, 0, -2))
    assert reflection_label_row((1, 0, -2, 0)) == [1, 0, -2]


def test_the_shared_grid_gives_every_candidate_its_own_list_bit_for_bit():
    """Review item 4: one parent grid per phase, and not one bit moves.

    The arm scores positions, so it builds the k-independent parent grid once
    and offsets it per candidate (``satellite_d_spacings``).  Each array must
    be *exactly* ``satellite_reflections(…, k).d`` — same orbits, same
    representative, same order — or the ranking would move with the speed-up.
    """
    from rietx.crystallography.satellites import satellite_d_spacings

    cases = [("P 1 21/c 1", (15.0, 10.0, 20.0, 90, 95, 90)),
             ("P -3", (5.0, 5.0, 6.0, 90, 90, 120)),
             ("C 2/m", (5.0, 6.0, 7.0, 90, 92, 90))]
    for symbol, cell in cases:
        ks = [c.k for c in zone_boundary_candidates(symbol)]
        shared = satellite_d_spacings(symbol, cell, 1.2, 70.0, ks,
                                      two_theta_min=8.0)
        assert len(shared) == len(ks)
        for k, d in zip(ks, shared, strict=True):
            one = satellite_reflections(symbol, cell, 1.2, 70.0, k,
                                        two_theta_min=8.0).d
            assert d.dtype == one.dtype and d.tobytes() == one.tobytes(), \
                (symbol, k)
