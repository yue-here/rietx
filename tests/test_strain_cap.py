"""The two-tier soft caps on sample broadening — strain (below) and size.

The size half is the same two-tier shape (a per-stage armed-on-contact solver
bound plus a corpus flag that bounds nothing), and since 1.10 the same bound
too: a line no wider than the fitted range, with 1/cosθ in place of tanθ.  The
2 nm crystallite floor that used to sit beside it was removed (WP-2002, the B8
ruling of 2026-10-19), because a small size stays a physical quantity; the
5 nm flag now carries the warning that below about 2 nm the Bragg-peak model
may not describe the pattern.  The size tests are the second half of this
module.

--- strain ---


Measured on a 248-pattern CuO→Cu reduction series (issue #140): Cu's
``lor_strain`` exceeded 1 in 133 of 248 patterns and peaked at 1.1e5, the
support phase's at 2.2e5, against 0.3 in the TOPAS protocol for the same data.
The consequences were a starved 16 wt % phase, weight fractions inflated ×1.19
and a covariance that overflowed until 179 of 248 patterns returned
weight-fraction esds above 100 wt %.

Two tiers, because the numbers do two jobs and are two orders of magnitude
apart:

* ``params.vector.strain_cap`` — a **solver bound** derived from the pattern's
  own fitted 2θ extent (a line wider than the interval it was measured over is
  not a line).  Protects the numerics, says nothing about the specimen, and
  reports itself through the ``BOUND_HIT`` machinery that already existed.
* ``refine.STRAIN_FLAG_WIDTH`` — a **flag** set from the corpus of 606 solved
  TOPAS refinements.  Protects the interpretation, changes no number.

The rule the whole design turns on is identity: a bound is never free, since
TRF takes its per-coordinate trust-region scale from the distance to it, so a
fit whose strain stays where the data can express it must get **no bound at
all**.  ``test_a_fit_below_the_cap_is_bounded_exactly_as_before`` is that
assertion; it was also checked end to end against ``origin/main``, where the
FAP acceptance protocol reproduced all 33 parameters and its Rwp bit for bit.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

import rietx as rx
from rietx.model.profiles.caglioti import (
    SCHERRER_K,
    size_coefficient_for_size,
)
from rietx.params.vector import (
    SIZE_CAP_ARM_RTOL,
    SIZE_CAP_RANGE_FRACTION,
    STRAIN_CAP_ARM_RTOL,
    STRAIN_CAP_RANGE_FRACTION,
    ParameterTable,
    size_cap,
    size_cap_hi,
    strain_cap,
    strain_cap_hi,
)
from rietx.refine import SIZE_FLAG_SIZE_A, STRAIN_FLAG_WIDTH


def _cell() -> rx.Cell:
    """A cubic cell — the cap cares about nothing in it."""
    p = rx.Parameter
    return rx.Cell(a=p(value=4.0, min=1.0), b=p(value=4.0, min=1.0),
                   c=p(value=4.0, min=1.0), alpha=p(value=90.0),
                   beta=p(value=90.0), gamma=p(value=90.0))


def _phase(name: str = "p", **kw) -> rx.Phase:
    p = rx.Parameter
    return rx.Phase(
        name=name, space_group="P m -3 m", cell=_cell(),
        atoms=[rx.Atom(label="A", species="Si", x=p(value=0.0),
                       y=p(value=0.0), z=p(value=0.0))],
        **kw)


class _FakeModel:
    """Enough ``CompiledModel`` for the tier-2 flags: it reads ``phases`` only
    to learn how many there are, ``line_wavelengths`` for the size flag's
    Scherrer conversion, and the values out of the decoded dict."""

    def __init__(self, n: int = 1, wavelength: float = 1.5406):
        self.phases = [object()] * n
        self.line_wavelengths = (wavelength,)


# ----------------------------------------------------------------------
# tier 1: the number comes from the data
# ----------------------------------------------------------------------
def test_the_cap_is_the_fitted_range_over_tan_theta_max():
    """Γ_L = lor_strain·tanθ, held to one fitted range at the highest θ."""
    cap = strain_cap(10.0, 80.0)
    assert cap == pytest.approx(
        STRAIN_CAP_RANGE_FRACTION * 70.0 / math.tan(math.radians(40.0)))
    # the statement it encodes: at the top of the range, that much strain and
    # nothing else contributes exactly one range's worth of FWHM
    assert cap * math.tan(math.radians(40.0)) == pytest.approx(70.0)


def test_the_cap_is_self_scaling_rather_than_a_constant():
    """A lab scan and a low-angle synchrotron scan get different caps.

    The point of deriving it from the data: no magic constant, and the bound
    tracks what the measurement can express.  A short high-angle scan can state
    a *tighter* bound than a long low-angle one, because tanθ is bigger there —
    the same strain buys more width.
    """
    lab = strain_cap(15.0, 80.0)
    synchrotron = strain_cap(0.5, 50.0)
    narrow = strain_cap(70.0, 80.0)
    assert lab != synchrotron != narrow
    assert narrow < lab < synchrotron
    # Generous by construction: the tightest of the three is a deliberately
    # pathological 10°-wide window at high angle, and even that clears the
    # TOPAS protocol's 0.3 on this data by 40× and the tier-2 flag by 8×.  A
    # cap that could fire on an honest fit would be worse than no cap.
    assert min(lab, synchrotron, narrow) > 30 * 0.3
    assert min(lab, synchrotron, narrow) > 5 * STRAIN_FLAG_WIDTH


def test_a_range_that_states_nothing_caps_nothing():
    """"No claim" is the honest output, not a bound of zero."""
    assert strain_cap(10.0, 10.0) == math.inf   # empty range
    assert strain_cap(80.0, 10.0) == math.inf   # reversed
    assert strain_cap(0.0, 0.0) == math.inf
    # a pattern reaching 2θ = 180° would put tanθ on its pole; the cap stays
    # finite and positive rather than collapsing for an arithmetic reason
    assert 0.0 < strain_cap(0.0, 180.0) < math.inf


def test_the_gaussian_term_is_capped_as_a_variance():
    """``gauss_strain`` multiplies tan²θ, so it takes the square of the width.

    One number governs both terms; there is no second constant to calibrate.
    """
    cap = strain_cap(10.0, 80.0)
    assert strain_cap_hi("gauss_strain", cap * cap, math.inf, cap) == cap * cap
    # a variance below the squared width is not capped even though its bare
    # number is far above the width itself
    assert strain_cap_hi("gauss_strain", cap * 1.5, math.inf, cap) == math.inf


# ----------------------------------------------------------------------
# tier 1: it is armed only where it is needed — this is what buys identity
# ----------------------------------------------------------------------
def test_the_cap_is_armed_only_where_the_term_has_reached_it():
    cap = strain_cap(10.0, 80.0)
    assert strain_cap_hi("lor_strain", 0.02, math.inf, cap) == math.inf
    assert strain_cap_hi("lor_strain", 1.0, math.inf, cap) == math.inf
    assert strain_cap_hi("lor_strain", cap, math.inf, cap) == cap
    assert strain_cap_hi("lor_strain", 1.1e5, math.inf, cap) == cap


def test_the_arming_test_has_hysteresis_so_a_capped_stage_stays_capped():
    """TRF leaves a bounded iterate a hair inside its bound.

    An exactly-equal test would disarm the cap on the very next stage and let
    the runaway restart, alternating capped and uncapped stages so that whether
    the answer is bounded came down to the parity of the stage count.
    """
    cap = strain_cap(10.0, 80.0)
    just_inside = cap * (1.0 - STRAIN_CAP_ARM_RTOL / 2.0)
    assert just_inside < cap
    assert strain_cap_hi("lor_strain", just_inside, math.inf, cap) == cap
    # and the slack is not so wide that it reaches a value a fit means
    assert strain_cap_hi("lor_strain", cap / 2.0, math.inf, cap) == math.inf


def test_a_caller_declared_bound_outranks_the_cap_and_silences_it():
    """The one-line off switch: any finite ``Parameter.max`` is the claim.

    ``cell_window``'s rule, and TOPAS's — *"user defined min/max limits
    override the defaults"*.  ±inf is what a Parameter carries when nobody set
    its bounds, so an infinite side is the only side on which no claim was
    made.
    """
    cap = strain_cap(10.0, 80.0)
    # tighter than the cap
    assert strain_cap_hi("lor_strain", 1.1e5, 0.3, cap) == 0.3
    # *looser* than the cap — deliberately enormous, which is how a caller
    # switches the cap off rather than merely moving it
    assert strain_cap_hi("lor_strain", 1.1e5, 1e9, cap) == 1e9
    # and a cap of inf (an unusable range) never invents one
    assert strain_cap_hi("lor_strain", 1.1e5, math.inf, math.inf) == math.inf


# ----------------------------------------------------------------------
# tier 1: identity, at the table
# ----------------------------------------------------------------------
def _one_phase_table(strain: float, **kw) -> ParameterTable:
    phase = _phase(lor_strain=rx.Parameter(
        value=strain, min=0.0, transform="softplus", **kw))
    table = ParameterTable(rx.Structure(phases=[phase]),
                           rx.Instrument.bragg_brentano())
    table.set_vary(["phases.*.lor_strain"], True)
    return table


def test_a_fit_below_the_cap_is_bounded_exactly_as_before():
    """**The assertion the whole design exists to keep.**

    A finite bound changes the solver's step in a coordinate even where it is
    never approached, so an untriggered fit must not get one.  Compared as the
    bound arrays themselves rather than as a fit result, because that is the
    only thing the cap can possibly change: identical bounds in, identical
    trajectory out.
    """
    table = _one_phase_table(0.02)
    lo_before, hi_before = table.bounds()
    table.freeze_strain_cap(strain_cap(10.0, 80.0))
    lo_after, hi_after = table.bounds()
    assert np.array_equal(lo_before, lo_after)
    assert np.array_equal(hi_before, hi_after)
    # and the strain column really is the unbounded one, so the comparison
    # above is not vacuously true of some other column
    k = table.free_paths.index("phases.0.lor_strain")
    assert hi_after[k] == math.inf


def test_a_term_past_the_cap_is_bounded_at_the_table():
    table = _one_phase_table(1.1e5)
    cap = strain_cap(10.0, 80.0)
    table.freeze_strain_cap(cap)
    _, hi = table.bounds()
    k = table.free_paths.index("phases.0.lor_strain")
    # the column is the coefficient itself since WP-1938, so the cap is the
    # bound as written
    assert hi[k] == pytest.approx(cap, rel=1e-9)


def test_no_claim_frozen_caps_nothing():
    """``None`` is ``freeze_cell_windows``' convention and means no claim."""
    table = _one_phase_table(1.1e5)
    table.freeze_strain_cap(None)
    _, hi = table.bounds()
    assert hi[table.free_paths.index("phases.0.lor_strain")] == math.inf


def test_a_locked_lor_strain_cannot_be_capped():
    """A Stephens block *locks* ``lor_strain`` — no contradiction is possible.

    Its isotropic direction is identically that column, so a declared
    ``microstrain`` block holds the term fixed; a fixed entry is not in the
    free vector and ``bounds()`` never sees it.  The cap therefore cannot
    contradict the lock, which is the interaction worth pinning rather than
    assuming.
    """
    from rietx.schemas.structure import StephensStrain

    phase = _phase(
        lor_strain=rx.Parameter(value=1.1e5, min=0.0, transform="softplus"),
        microstrain=StephensStrain.isotropic(1e-3, _cell()))
    table = ParameterTable(rx.Structure(phases=[phase]),
                           rx.Instrument.bragg_brentano())
    assert table.set_vary(["phases.*.lor_strain"], True) == []
    table.freeze_strain_cap(strain_cap(10.0, 80.0))
    assert "phases.0.lor_strain" not in table.free_paths
    table.bounds()   # and it does not raise


# ----------------------------------------------------------------------
# tier 2: the flag, and what it must not do
# ----------------------------------------------------------------------
def test_the_flag_sits_above_the_corpus_of_solved_refinements():
    """Set from the archive's 606 TOPAS refinements, not from taste.

    p99 of 1213 strain records is 1.21 and the hand-written ceilings those
    authors used top out at 1.5; above that the corpus holds 8 records in 5
    contexts, every one a divergence signature.  Pinned so that a later edit
    to the constant has to argue with the survey.
    """
    assert STRAIN_FLAG_WIDTH == 1.5
    # two orders of magnitude below the numerical fence on a normal lab scan:
    # the tiers must not collapse into each other
    assert strain_cap(10.0, 80.0) > 30 * STRAIN_FLAG_WIDTH


def test_a_legitimately_broad_fit_is_not_flagged():
    """The regression that matters: nanocrystalline and defective specimens
    live in the corpus's 0.4-1.5 tail (dozens of independent files) and must
    stay silent, or the flag is noise and gets ignored."""
    from rietx.refine import _strain_flag_diagnostics

    structure = rx.Structure(phases=[_phase("nanocrystalline")])
    for width in (0.3, 0.7, 1.2, 1.5):
        values = {"phases.0.lor_strain": width, "phases.0.gauss_strain": 0.0}
        assert _strain_flag_diagnostics(_FakeModel(), values, structure) == [], width


def test_the_flag_names_the_phase_and_the_value():
    from rietx.refine import _strain_flag_diagnostics

    structure = rx.Structure(phases=[_phase("mayenite")])
    found = _strain_flag_diagnostics(
        _FakeModel(),
        {"phases.0.lor_strain": 2.2e5, "phases.0.gauss_strain": 0.0},
        structure)
    assert [d.code for d in found] == ["STRAIN_UNUSUALLY_LARGE"]
    d = found[0]
    assert d.where == ["phases.0.lor_strain"]
    assert d.value == pytest.approx(2.2e5)
    assert "mayenite" in d.message and "2.2e+05" in d.message
    assert "BOUND_HIT" in d.suggestion
    assert d.level == "warning"


def test_the_flag_reads_gauss_strain_as_a_variance():
    """``gauss_strain`` is deg², so it is compared as its square root.

    Without the conversion the flag would fire on every Gaussian variance above
    1.5 deg² — a width of only 1.22 deg — and be wrong about the units.
    """
    from rietx.refine import _strain_flag_diagnostics

    structure = rx.Structure(phases=[_phase()])
    below = {"phases.0.lor_strain": 0.0,
             "phases.0.gauss_strain": STRAIN_FLAG_WIDTH ** 2 * 0.9}
    above = {"phases.0.lor_strain": 0.0,
             "phases.0.gauss_strain": STRAIN_FLAG_WIDTH ** 2 * 1.5}
    assert _strain_flag_diagnostics(_FakeModel(), below, structure) == []
    flagged = _strain_flag_diagnostics(_FakeModel(), above, structure)
    assert [d.where for d in flagged] == [["phases.0.gauss_strain"]]
    # reported as the width it contributes, not as the stored variance
    assert flagged[0].value == pytest.approx(
        math.sqrt(STRAIN_FLAG_WIDTH ** 2 * 1.5))


# ======================================================================
# SIZE — the second half.  Same two-tier shape, the range bound alone.
# ======================================================================
_CU = 1.5406       # Cu Kα, the archive's dominant lab wavelength


def _size_coeff_nm(size_nm: float, lam: float = _CU) -> float:
    """The ``lor_size`` coefficient (deg 2θ) a crystallite of ``size_nm`` gives."""
    return size_coefficient_for_size(size_nm * 10.0, lam)   # nm → Å


# ----------------------------------------------------------------------
# tier 1: the number comes from the data, as the strain cap's does
# ----------------------------------------------------------------------
def test_the_size_cap_is_the_fitted_range_times_cos_theta_max():
    """Γ_L,size = lor_size/cosθ, held to one fitted range at the highest θ."""
    cap = size_cap(10.0, 80.0)
    assert cap == pytest.approx(
        SIZE_CAP_RANGE_FRACTION * 70.0 * math.cos(math.radians(40.0)))
    # the statement it encodes: at the top of the range, that much size
    # broadening and nothing else contributes exactly one range's worth of FWHM
    assert cap / math.cos(math.radians(40.0)) == pytest.approx(70.0)
    # ≈ 54 deg on this scan, which Scherrer reads at Cu Kα as ≈ 0.15 nm: the
    # number the B8 ruling quotes for where the bound now sits
    assert cap == pytest.approx(53.62, abs=0.01)
    assert _size_coeff_nm(0.148) == pytest.approx(cap, rel=0.01)


def test_the_size_cap_needs_no_wavelength_and_tracks_the_scan():
    """The bound is a statement about the measurement, so λ does not enter it.

    A lab scan and a low-angle synchrotron scan get different caps out of the
    one rule, and a short window near 2θ = 180° gets the tightest, because
    1/cosθ is largest there.
    """
    import inspect

    assert list(inspect.signature(size_cap).parameters) == ["tt_min", "tt_max"]
    lab = size_cap(10.0, 80.0)
    synchrotron = size_cap(0.5, 50.0)
    steep = size_cap(170.0, 178.0)
    assert lab != synchrotron
    assert steep < lab
    # a range that states nothing caps nothing
    assert size_cap(10.0, 10.0) == math.inf
    assert size_cap(80.0, 10.0) == math.inf


def test_a_sub_2nm_crystallite_runs_free():
    """**The B8 ruling, size half**: no crystallite floor.

    A 1 nm and a 0.5 nm crystallite at Cu Kα are coefficients of ≈ 7.9 and
    ≈ 15.9 deg, far inside the ≈ 54 deg range cap, so neither is bounded.
    Before 1.10 both were held at the 2 nm floor (≈ 3.97 deg).
    """
    cap = size_cap(10.0, 80.0)
    for size_nm in (1.0, 0.5):
        coeff = _size_coeff_nm(size_nm)
        assert size_cap_hi("lor_size", coeff, math.inf, cap) == math.inf, size_nm
        assert size_cap_hi("gauss_size", coeff ** 2, math.inf, cap) == math.inf


def test_the_gaussian_size_term_is_capped_as_a_variance():
    """``gauss_size`` multiplies 1/cos²θ, so it takes the square of the width."""
    cap = size_cap(10.0, 80.0)
    assert size_cap_hi("gauss_size", cap * cap, math.inf, cap) == cap * cap
    assert size_cap_hi("gauss_size", cap * 1.5, math.inf, cap) == math.inf


# ----------------------------------------------------------------------
# tier 1: armed only on contact — identity
# ----------------------------------------------------------------------
def test_the_size_cap_is_armed_only_where_the_term_has_reached_it():
    cap = size_cap(10.0, 80.0)
    # a 4 nm or 3 nm crystallite is never armed — Michael's "a real fit at
    # 3–4 nm must run free"
    assert size_cap_hi("lor_size", _size_coeff_nm(4.0), math.inf, cap) == math.inf
    assert size_cap_hi("lor_size", _size_coeff_nm(3.0), math.inf, cap) == math.inf
    # only a term whose line has reached the range cap is bounded
    assert size_cap_hi("lor_size", cap, math.inf, cap) == cap
    assert size_cap_hi("lor_size", 1e5, math.inf, cap) == cap


def test_the_size_arming_test_has_hysteresis():
    cap = size_cap(10.0, 80.0)
    just_inside = cap * (1.0 - SIZE_CAP_ARM_RTOL / 2.0)
    assert just_inside < cap
    assert size_cap_hi("lor_size", just_inside, math.inf, cap) == cap
    assert size_cap_hi("lor_size", cap / 2.0, math.inf, cap) == math.inf


def test_a_caller_declared_size_bound_outranks_the_cap():
    """The off switch: any finite ``lor_size.max`` is the claim, tighter *or*
    looser — including a deliberately enormous one that switches the cap off."""
    cap = size_cap(10.0, 80.0)
    assert size_cap_hi("lor_size", 1e5, 1.0, cap) == 1.0       # tighter
    assert size_cap_hi("lor_size", 1e5, 1e9, cap) == 1e9       # off switch
    assert size_cap_hi("lor_size", 1e5, math.inf, math.inf) == math.inf


def _one_phase_size_table(coeff: float, **kw) -> ParameterTable:
    phase = _phase(lor_size=rx.Parameter(
        value=coeff, min=0.0, transform="softplus", **kw))
    table = ParameterTable(rx.Structure(phases=[phase]),
                           rx.Instrument.bragg_brentano())
    table.set_vary(["phases.*.lor_size"], True)
    return table


def test_a_nanocrystalline_fit_below_the_cap_is_bounded_exactly_as_before():
    """**The identity assertion, size half.**

    A 33 nm crystallite (the smallest well-determined size in the corpus) frees
    ``lor_size`` far below the range cap, so it must get no bound at all and be
    bit-identical to an uncapped build.  Compared as the bound arrays, the only
    thing the cap can change.
    """
    table = _one_phase_size_table(_size_coeff_nm(33.0))
    lo_before, hi_before = table.bounds()
    table.freeze_size_cap(size_cap(10.0, 80.0))
    lo_after, hi_after = table.bounds()
    assert np.array_equal(lo_before, lo_after)
    assert np.array_equal(hi_before, hi_after)
    k = table.free_paths.index("phases.0.lor_size")
    assert hi_after[k] == math.inf


def test_a_size_term_on_the_cap_is_bounded_at_the_table():
    cap = size_cap(10.0, 80.0)
    table = _one_phase_size_table(1e5)          # a runaway sub-Å "crystallite"
    table.freeze_size_cap(cap)
    _, hi = table.bounds()
    k = table.free_paths.index("phases.0.lor_size")
    assert hi[k] == pytest.approx(cap, rel=1e-9)


# ----------------------------------------------------------------------
# tier 2: the flag, and what it must not do
# ----------------------------------------------------------------------
def test_the_size_flag_sits_below_the_smallest_real_corpus_fit():
    """5 nm: below the ≈ 33 nm corpus floor, and far above the range cap.

    Pinned so a later edit has to argue with the survey, and so the two tiers
    cannot collapse into each other: on a Cu 10–80° scan the bound sits near
    0.15 nm, so every size the flag names is one the bound left free.
    """
    assert SIZE_FLAG_SIZE_A == 50.0            # 5 nm
    assert SIZE_FLAG_SIZE_A / 10.0 < 33.0                          # below corpus floor
    assert _size_coeff_nm(SIZE_FLAG_SIZE_A / 10.0) < size_cap(10.0, 80.0)


def test_a_legitimately_nanocrystalline_fit_is_not_flagged():
    """The regression that matters: a real ≈ 33 nm corpus fit stays silent, and
    so does the whole plausible nanocrystalline band down to the flag.

    Pinned at the smallest *well-determined* size the archive actually contains
    (a 33 nm rutile size–strain fit), not an assumed round number, so the
    permissiveness is measured rather than asserted."""
    from rietx.refine import _size_flag_diagnostics

    structure = rx.Structure(phases=[_phase("rutile")])
    for size_nm in (33.0, 20.0, 10.0, 6.0):
        values = {"phases.0.lor_size": _size_coeff_nm(size_nm),
                  "phases.0.gauss_size": 0.0}
        assert _size_flag_diagnostics(_FakeModel(), values, structure) == [], size_nm


def test_the_size_flag_names_the_phase_and_the_size():
    from rietx.refine import _size_flag_diagnostics

    structure = rx.Structure(phases=[_phase("Cu")])
    found = _size_flag_diagnostics(
        _FakeModel(),
        {"phases.0.lor_size": _size_coeff_nm(1.5), "phases.0.gauss_size": 0.0},
        structure)
    assert [d.code for d in found] == ["SIZE_UNUSUALLY_SMALL"]
    d = found[0]
    assert d.where == ["phases.0.lor_size"]
    assert d.value == pytest.approx(1.5, rel=1e-3)     # reported in nm
    assert "Cu" in d.message and "1.5 nm" in d.message
    # the Bragg-model caveat the 2 nm floor's removal moved into the message
    assert "Debye scattering equation" in d.message
    assert "BOUND_HIT" in d.suggestion
    assert d.level == "warning"


def test_the_size_flag_reads_gauss_size_as_a_variance():
    """``gauss_size`` is deg², so the size is read from its square root."""
    from rietx.refine import _size_flag_diagnostics

    structure = rx.Structure(phases=[_phase()])
    coeff_3nm = _size_coeff_nm(3.0)
    below = {"phases.0.lor_size": 0.0, "phases.0.gauss_size": coeff_3nm ** 2}
    above = {"phases.0.lor_size": 0.0,
             "phases.0.gauss_size": _size_coeff_nm(1.0) ** 2}
    # a 3 nm Gaussian size IS flagged (below 5 nm), proving the sqrt is taken:
    # without it the stored variance would be read as a huge coefficient and the
    # apparent size would be sub-Å, still flagged but for the wrong reason — so
    # check the reported size is the 3 nm one, not the variance's
    flagged_below = _size_flag_diagnostics(_FakeModel(), below, structure)
    assert [d.where for d in flagged_below] == [["phases.0.gauss_size"]]
    assert flagged_below[0].value == pytest.approx(3.0, rel=1e-3)
    flagged_above = _size_flag_diagnostics(_FakeModel(), above, structure)
    assert flagged_above[0].value == pytest.approx(1.0, rel=1e-3)


def test_the_size_flag_reads_the_sample_coefficient_in_nm_via_scherrer():
    """The flag uses the caglioti Scherrer constant and the pattern wavelength.

    A different wavelength moves the size for the same coefficient, which is why
    the flag reads a size (transferable) rather than a coefficient in degrees.
    """
    from rietx.model.profiles.caglioti import apparent_size_from_size_coefficient
    from rietx.refine import _size_flag_diagnostics

    structure = rx.Structure(phases=[_phase()])
    coeff = _size_coeff_nm(3.0, _CU)      # 3 nm at Cu Kα
    # the SAME coefficient read at a shorter wavelength is a smaller crystallite
    short = _FakeModel(wavelength=0.4139)
    d = _size_flag_diagnostics(short, {"phases.0.lor_size": coeff}, structure)
    assert d and d[0].value < 3.0
    expected_nm = apparent_size_from_size_coefficient(coeff, 0.4139, SCHERRER_K) / 10.0
    assert d[0].value == pytest.approx(expected_nm, rel=1e-6)


# ======================================================================
# The one λ selector the size flag reads
# ======================================================================
def test_one_selector_answers_which_line_for_the_size_flag():
    """Every reading of a size coefficient as a crystallite uses one λ.

    Two copies of "the longest positive emission line" is the divergence class
    the root CLAUDE.md's *one authority per fact* rule exists for: two readers
    would come to disagree about which crystallite a coefficient implies, and
    nothing would go red.  So there is one selector and the flag imports it.
    The solver's size bound no longer reads a wavelength at all (the 2 nm floor
    went in WP-2002), so its empty state is the flag's alone: a source with no
    λ gives the flag nothing to read a size with, and it says nothing.
    """
    from rietx.optimize.least_squares import _longest_line_wavelength
    from rietx.refine import _size_flag_diagnostics

    class _Model(_FakeModel):
        def __init__(self, lines):
            self.phases = [object()]
            self.line_wavelengths = lines
            self.tt_min, self.tt_max = 10.0, 80.0

    # the longest line, and the Kα2 offset never being the one chosen
    assert _longest_line_wavelength(_Model((1.5406, 1.5444))) == 1.5444
    # a non-positive line is not a line
    assert _longest_line_wavelength(_Model((0.0, 1.5406))) == 1.5406
    assert _longest_line_wavelength(_Model(())) is None

    # the flag reads that selector: the same coefficient, the longer line
    structure = rx.Structure(phases=[_phase()])
    coeff = _size_coeff_nm(3.0, _CU)
    both = _Model((1.5406, 1.5444))
    d = _size_flag_diagnostics(both, {"phases.0.lor_size": coeff}, structure)
    only_long = _size_flag_diagnostics(_FakeModel(wavelength=1.5444),
                                       {"phases.0.lor_size": coeff}, structure)
    assert [x.value for x in d] == [x.value for x in only_long]

    # the empty state: no λ, no size to read, no diagnostic
    none = _Model(())
    assert _size_flag_diagnostics(none, {"phases.0.lor_size": coeff}, structure) == []


# ======================================================================
# tier 2 in a JOINT (multi-histogram) refinement
# ======================================================================
def _broad_structure(strain: float, size_coeff: float) -> rx.Structure:
    """One phase whose sample widths sit past both tier-2 flags, held there.

    Held (``vary=False``) rather than refined on purpose: a flag reads the
    *value* a result carries, so this asks the question the reviewer's finding is
    about — does the joint result builder look? — without a synthetic fit having
    to be coaxed into a runaway first.  It also keeps tier 1 out of the way: an
    unfree entry is no column of θ, so no bound is applied and nothing but the
    flag can move.
    """
    p = rx.Parameter
    return rx.Structure(phases=[rx.Phase(
        name="broad", space_group="P m -3 m", cell=_cell(),
        atoms=[rx.Atom(label="A", species="Si", x=p(value=0.0), y=p(value=0.0),
                       z=p(value=0.0))],
        scale=p(value=1.0, vary=True),
        lor_strain=p(value=strain), lor_size=p(value=size_coeff))])


def _flat_pattern(instrument, tt_lo: float, tt_hi: float) -> rx.PatternData:
    """A synthetic pattern of that structure — enough for a one-stage joint fit."""
    from rietx.model.forward import compile_model

    tt = np.arange(tt_lo, tt_hi, 0.05)
    blank = rx.PatternData(two_theta=tt.tolist(),
                           intensity=np.zeros_like(tt).tolist())
    structure = _broad_structure(_JOINT_STRAIN, _JOINT_SIZE_COEFF)
    model = compile_model(structure, instrument, blank, mode="rietveld")
    table = ParameterTable(structure, instrument)
    y = model.evaluate(table.decode(table.x0()))
    return rx.PatternData(two_theta=model.tt.tolist(),
                          intensity=(np.maximum(y, 1.0) + 10.0).tolist())


#: 2.0 deg against a 1.5 flag, and a 3 nm crystallite at Cu Kα against a 5 nm
#: flag — both a modest step past their threshold, so the test is about the
#: wiring and not about how far out a runaway goes.
_JOINT_STRAIN = 2.0
_JOINT_SIZE_COEFF = size_coefficient_for_size(30.0, 1.5406, SCHERRER_K)


def test_both_tier_2_flags_fire_per_histogram_in_a_joint_fit():
    """The joint result builder asks the same two questions the single one does.

    Before this was wired, a joint fit got tier 1 (``_freeze_strain_cap_multi`` /
    ``_freeze_size_cap_multi`` are called from ``run_multi_least_squares``) and
    **neither** tier-2 flag — the interpretive half the two-tier argument rests
    on, silently absent on exactly the multi-pattern work that most needs it.
    Measured on this fixture before the fix: both histograms came back with an
    empty ``diagnostics`` list while the identical numbers through
    ``Refinement.fit`` reported ``STRAIN_UNUSUALLY_LARGE`` and
    ``SIZE_UNUSUALLY_SMALL``.

    **Per histogram, and the size flag is why that is not a formality.**  The
    default :class:`~rietx.params.multi.SharingMap` puts size/strain on the
    *structure*, so there is one shared column — but a coefficient is only a
    crystallite once a λ is chosen, and λ is per histogram.  One reading would
    therefore quote one histogram's wavelength about all of them.

    Since WP-1131 the two readings **agree**, and that agreement is the
    assertion: the shared column is normalised by λ, so each histogram's copy
    is the coefficient that histogram needs and the crystallite behind them is
    one number.  Before it, the same fixture reported 3.0 nm and 1.384 nm — one
    specimen wearing the wavelength ratio as a size spread.
    """
    from rietx.schemas.instrument import BackgroundChebyshev

    p = rx.Parameter
    lams = (_CU, 0.7107)                      # Cu Kα and Mo Kα
    instruments = []
    for lam in lams:
        ins = rx.Instrument.debye_scherrer(wavelength=lam)
        ins.background = BackgroundChebyshev(coefficients=[p(value=10.0)])
        instruments.append(ins)
    patterns = [_flat_pattern(instruments[0], 15.0, 60.0),
                _flat_pattern(instruments[1], 7.0, 28.0)]

    plan = rx.RefinementPlan(stages=[
        rx.Stage(name="scale", turn_on=["phases.*.scale"], max_iter=3)])
    ref = rx.MultiHistogramRefinement(
        _broad_structure(_JOINT_STRAIN, _JOINT_SIZE_COEFF), instruments)
    result = ref.fit(patterns, plan=plan)

    assert len(result.histograms) == 2
    for h, hist in enumerate(result.histograms):
        codes = {d.code for d in hist.diagnostics}
        assert "STRAIN_UNUSUALLY_LARGE" in codes, f"hist {h}: {sorted(codes)}"
        assert "SIZE_UNUSUALLY_SMALL" in codes, f"hist {h}: {sorted(codes)}"

    def one(h, code):
        found = [d for d in result.histograms[h].diagnostics if d.code == code]
        assert len(found) == 1, found          # one term each, not both spellings
        return found[0]

    # strain is λ-free, so the two histograms report the one shared number
    assert [one(h, "STRAIN_UNUSUALLY_LARGE").value for h in (0, 1)] == \
        [_JOINT_STRAIN, _JOINT_STRAIN]

    # size is not λ-free, and since WP-1131 that is why the two rows agree
    # rather than why they differ: the shared column carries histogram 0's
    # wavelength and each copy is scaled to its own, so the crystallite behind
    # them is one number.  A disagreement here would mean the normalisation had
    # come undone — before it, these read 3.0 nm and 1.384 nm.
    sizes = [one(h, "SIZE_UNUSUALLY_SMALL").value for h in (0, 1)]
    assert sizes[0] == pytest.approx(3.0, rel=1e-3)
    assert sizes[1] == pytest.approx(sizes[0], rel=1e-9)
    # each histogram's own copy is the coefficient *it* needs, in the ratio of
    # the wavelengths — the thing that used to be true of the reported size
    coeffs = [ref.fitted_structures[h].phases[0].lor_size.value for h in (0, 1)]
    assert coeffs[1] / coeffs[0] == pytest.approx(lams[1] / lams[0], rel=1e-12)

    # the coefficient really is one shared column — otherwise the paragraph
    # above is about two independent parameters and proves nothing
    assert ref.mtable.sharing.is_shared("phases.0.lor_size")
    assert ref.mtable.sharing.is_shared("phases.0.lor_strain")
    # …which is why the flag's ``where`` is the joint table's own bare spelling,
    # with no ``hist.N.`` scope (unlike a wavelength row, which is per histogram)
    assert one(0, "SIZE_UNUSUALLY_SMALL").where == ["phases.0.lor_size"]
    assert one(0, "STRAIN_UNUSUALLY_LARGE").where == ["phases.0.lor_strain"]

    # a per-histogram statement stays per histogram: not duplicated to the top,
    # exactly like the QPA and specimen-absorption rows beside it
    top = {d.code for d in result.diagnostics}
    assert "STRAIN_UNUSUALLY_LARGE" not in top
    assert "SIZE_UNUSUALLY_SMALL" not in top
