"""The additive component seam, and humps as its first member.

:data:`~rietx.schemas.instrument.ExtraComponent` is a union discriminated on
``kind``; :class:`~rietx.schemas.instrument.HumpComponent` is its one member,
three parameters (position, height, width) summed on top of whichever
:data:`~rietx.schemas.instrument.Background` model is in use.  Almost every test
here exists because one of those three could be wrong in a way nothing else
would notice:

* the empty default has to be **exactly** off, not approximately (the
  ``restraints``/``microstrain``/``surface_roughness`` idiom);
* the paths have to be registered in ``_collect_instrument`` **and** written back
  in ``apply_to_models``, or a refined hump silently reverts at the next stage;
* the peak paths must stay out of ``bkg_paths``, whose branch of
  ``_make_jacobian`` claims an exact linear column;
* the whole-model FD column has to be the *declared* fallback, and exact —
  including on the rows it never writes;
* and the width bound is the feature's physical content, not a numerical
  guard: a free position/height/width is a Bragg peak with no cell behind it,
  and enough of those improve any Rwp.

The last section covers the v1.2 rename (WP-1102).  Its load-bearing tests are
the ones about *paths* rather than values: a stored value under a vanished
field raises, while a stored plan glob under the old spelling loads clean and
then frees nothing.
"""

from __future__ import annotations

import json
import typing

import numpy as np
import pytest
from pydantic import ValidationError

import rietx as rx
from rietx.background.models import hump_curve
from rietx.io.exporters import _background_description
from rietx.io.instrument_profile import save_instrument_profile
from rietx.model.components import COMPONENT_AGGREGATE, EXTRA_TICK_KEY
from rietx.model.corrections import lorentz_polarization
from rietx.model.forward import WINDOW_AREA_TOL, compile_model
from rietx.model.profiles.pseudovoigt import pseudo_voigt
from rietx.optimize.least_squares import _make_jacobian, _make_residual
from rietx.optimize.statistics import (
    _span_basis,
    background_absorption,
    extra_peak_absorption,
)
from rietx.params.vector import ParameterTable, extra_component_parameters
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import (
    COMPONENT_FIELDS,
    EXTRA_PEAK_FWHM_MIN,
    HUMP_FIELDS,
    HUMP_FWHM_MIN,
    PEAK_FIELDS,
    BackgroundChebyshev,
    BackgroundPSpline,
    ExtraComponent,
    HumpComponent,
    Instrument,
    PeakComponent,
)
from rietx.schemas.migrate import READ_POINTS, migrate_document_text
from rietx.schemas.pattern import PatternData
from rietx.schemas.plan import PlanSpec, StageSpec
from rietx.strategy.staged import (
    BACKGROUND_ABSORPTION_GUARD,
    HUMP_MIN_WIDTH_MULT,
    PLAN_PRESETS,
    check_hump_width,
)
from tests.test_schemas import make_lab6

WAVELENGTH = 1.5405929
PEAK_PATHS = tuple(f"instrument.extra_components.0.{n}"
                   for n in HUMP_FIELDS)


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------
def _peak(position=32.0, height=400.0, fwhm=7.0, *, vary=True) -> HumpComponent:
    return HumpComponent(
        label="hump",
        position=Parameter(value=position, unit="deg", vary=vary),
        height=Parameter(value=height, min=0.0, unit="counts",
                         transform="softplus", vary=vary),
        fwhm=Parameter(value=fwhm, min=HUMP_FWHM_MIN, unit="deg",
                       transform="softplus", vary=vary))


def _instrument(*, peaks=(), background=None) -> Instrument:
    ins = rx.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.source.dispersion = None      # declined, never inherited
    ins.profile.w.value = 3e-3
    ins.profile.x.value = 5e-3
    if background is not None:
        ins.background = background
    ins.extra_components = list(peaks)
    return ins


def _state(*, peaks=(), background=None, free=PEAK_PATHS, lo=15.0, hi=110.0,
           step=0.05):
    """A compiled LaB6 model over a flat pattern, with ``free`` freed."""
    structure = make_lab6()
    structure.phases[0].scale.value = 3e-4
    ins = _instrument(peaks=peaks, background=background)
    tt = np.arange(lo, hi, step)
    data = PatternData(two_theta=tt.tolist(),
                       intensity=(np.full_like(tt, 200.0)).tolist())
    table = ParameterTable(structure, ins)
    if free:
        table.set_vary(list(free), True)
    model = compile_model(structure, ins, data, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    return structure, ins, data, table, model


# ----------------------------------------------------------------------
# the empty default is exactly off
# ----------------------------------------------------------------------
def test_the_empty_default_is_byte_identical_to_no_field_at_all():
    """The ``restraints``/``microstrain``/``surface_roughness`` idiom, pinned.

    Two halves, because "off" has to hold in both directions: the serialized
    instrument differs from a pre-``extra_components`` one by exactly the empty
    list, and the parameter table it produces is unchanged.
    """
    ins = _instrument()
    dumped = ins.model_dump(mode="json")
    assert dumped["extra_components"] == []
    without = {k: v for k, v in dumped.items() if k != "extra_components"}
    assert json.loads(json.dumps(without)) == without   # nothing else moved

    table = ParameterTable(make_lab6(), ins)
    assert not [e.path for e in table.entries if "extra_components" in e.path]
    assert extra_component_parameters(ins.extra_components) == []


def test_a_declared_peak_at_zero_height_leaves_the_background_bit_identical():
    """``height`` may take ``min=0.0`` under softplus because zero *is* the off
    state — so this is the promise that bound is allowed to make."""
    _s, _i, _d, table_off, model_off = _state(peaks=(), free=())
    _s, _i, _d, table_on, model_on = _state(
        peaks=(_peak(height=0.0, vary=False),), free=())
    off = np.asarray(model_off.background(table_off.decode(table_off.x0())))
    on = np.asarray(model_on.background(table_on.decode(table_on.x0())))
    assert model_on.component_paths and not model_off.component_paths
    assert np.array_equal(off, on)          # bit-identical, not allclose


# ----------------------------------------------------------------------
# the schema
# ----------------------------------------------------------------------
def test_json_round_trip_keeps_every_peak_parameter():
    ins = _instrument(peaks=(_peak(), _peak(position=70.0, height=10.0)))
    back = Instrument.model_validate(json.loads(ins.model_dump_json()))
    assert len(back.extra_components) == 2
    assert back.extra_components[1].position.value == 70.0
    assert back.extra_components[0].label == "hump"
    assert back.extra_components[0].fwhm.transform == "softplus"


def test_a_stored_zero_width_bound_is_repaired_rather_than_deserialized():
    """The ``MARCH_R_MIN`` precedent: the broken bound outlives the default.

    A project or history node written with ``min: 0.0`` would otherwise come
    back with a reachable zero width, and the Gaussian divides by it.
    """
    peak = HumpComponent.model_validate({
        "position": {"value": 20.0},
        "height": {"value": 1.0, "min": 0.0, "transform": "softplus"},
        "fwhm": {"value": 0.0, "min": 0.0, "transform": "softplus"}})
    assert peak.fwhm.min == HUMP_FWHM_MIN
    assert peak.fwhm.value == HUMP_FWHM_MIN
    # a caller's own positive bound is left alone
    kept = HumpComponent.model_validate({
        "position": {"value": 20.0},
        "height": {"value": 1.0, "min": 0.0, "transform": "softplus"},
        "fwhm": {"value": 3.0, "min": 1.0, "transform": "softplus"}})
    assert kept.fwhm.min == 1.0


def test_the_restated_softplus_floor_still_equals_the_one_that_decides():
    """Three spellings of one number, pinned to the one with the vote.

    ``_SOFTPLUS_FLOOR`` in ``schemas/instrument.py`` (the repair above) and in
    ``schemas/structure.py`` (``PreferredOrientation.r``, pre-existing on main)
    are both restatements — declared rather than imported, to keep the schemas
    importing nothing from ``params``.  The number that actually decides whether
    a softplus lower bound exists is ``transforms._SOFTPLUS_MIN``: ``to_internal``
    maps any ``min`` at or under it to −∞.  Nothing else asserts the copies track
    it, so changing ``transforms`` would leave both repairs pointing at a bound
    the transform no longer forgives, in silence.  Pin them.
    """
    from rietx.params.transforms import _SOFTPLUS_MIN
    from rietx.schemas.instrument import _SOFTPLUS_FLOOR as _INSTRUMENT_FLOOR
    from rietx.schemas.structure import _SOFTPLUS_FLOOR as _STRUCTURE_FLOOR

    assert _INSTRUMENT_FLOOR == _SOFTPLUS_MIN
    assert _STRUCTURE_FLOOR == _SOFTPLUS_MIN


def test_the_restated_four_ln2_still_equals_the_profiles_own():
    """One number, four spellings, pinned — the softplus-floor idiom above.

    ``FOUR_LN2_NEG`` in ``background/models.py`` is a fourth restatement of the
    Gaussian's −4 ln2 normalisation, declared rather than imported so the
    ``background`` package pulls no private out of ``model.profiles``.  Its own
    docstring argues it has a single owner and no second spelling to reproduce —
    which is exactly the state the softplus floor was in before it drifted.  Pin
    it to the pseudo-Voigt copy so retuning one cannot leave this one behind in
    silence.

    The compiled kernels' copy (``K4LN2`` in ``kernels/src/lib.rs``) is Rust
    since WP-1940 and cannot be imported here.  ``test_compiled_kernels.py``
    holds it instead: it compares the kernels' Ω against the numpy profile
    built on ``_PV_4LN2``, to the bit where that was measured.
    """
    from rietx.background.models import FOUR_LN2_NEG
    from rietx.model.profiles.pseudovoigt import _4LN2 as _PV_4LN2

    assert FOUR_LN2_NEG == -_PV_4LN2


def test_the_curve_is_a_gaussian_of_the_declared_fwhm():
    """Half height at ±Γ/2 — the property the −4 ln2 constant exists for."""
    xp = rx.backend.get_backend()
    tt = np.array([32.0 - 3.5, 32.0, 32.0 + 3.5], dtype=np.float64)
    y = np.asarray(hump_curve(tt, 32.0, 400.0, 7.0, xp))
    assert y[1] == pytest.approx(400.0, rel=1e-15)
    assert y[0] == pytest.approx(200.0, rel=1e-12)
    assert y[2] == pytest.approx(200.0, rel=1e-12)


def test_the_peak_lands_at_its_declared_position_on_the_fit_grid():
    _s, _i, _d, table, model = _state(peaks=(_peak(),), free=())
    y = np.asarray(model.background(table.decode(table.x0())))
    assert model.tt[int(np.argmax(y))] == pytest.approx(32.0, abs=0.05)


# ----------------------------------------------------------------------
# table wiring — the pair that silently loses a refined value
# ----------------------------------------------------------------------
def test_both_halves_of_the_table_know_the_peak_paths():
    _s, ins, _d, table, _m = _state(peaks=(_peak(),))
    assert set(PEAK_PATHS) <= set(table.free_paths)
    # the helper is the one authority both sides read
    assert [sub for sub, _p in extra_component_parameters(ins.extra_components)] \
        == [f"0.{n}" for n in HUMP_FIELDS]


def test_a_refined_peak_survives_a_stage_boundary():
    """``_collect_instrument`` and ``apply_to_models`` must both know the paths.

    This is the test ``params/vector.py``'s own comment asks for: a parameter
    registered in one and forgotten in the other loses its refined value at the
    next recompile, silently, and the file says it has been bitten before.
    """
    structure, ins, _d, table, _m = _state(peaks=(_peak(),))
    for path, value in zip(PEAK_PATHS, (41.0, 555.0, 9.5), strict=True):
        table.entries[table._paths[path]].value = value
    table.apply_to_models(structure, ins)

    peak = ins.extra_components[0]
    assert (peak.position.value, peak.height.value, peak.fwhm.value) \
        == (41.0, 555.0, 9.5)
    # and the rebuilt table — what the next stage compiles from — agrees
    rebuilt = ParameterTable(structure, ins)
    values = {e.path: e.value for e in rebuilt.entries}
    assert [values[p] for p in PEAK_PATHS] == [41.0, 555.0, 9.5]


# ----------------------------------------------------------------------
# the linear block, and the Jacobian's declared reach
# ----------------------------------------------------------------------
def test_peak_paths_never_join_the_linear_background_block():
    """``bkg_paths`` names a block ``_make_jacobian`` claims an *exact* column
    for, on the grounds that y is linear in it.  A peak is not."""
    for background in (BackgroundChebyshev.with_terms(5),
                       BackgroundPSpline.for_range(15.0, 110.0,
                                                   knot_step_deg=8.0)):
        _s, _i, _d, _t, model = _state(peaks=(_peak(),), background=background)
        peak_paths = {p for triple in model.component_paths for p in triple}
        assert peak_paths and set(model.bkg_paths).isdisjoint(peak_paths)


@pytest.mark.parametrize("path", PEAK_PATHS)
def test_no_analytic_branch_claims_a_peak_path(path):
    """The FD fallback is declared, not discovered (WP-1070's failure mode)."""
    _s, _i, _d, _t, model = _state(peaks=(_peak(),))
    assert model.scalar_chain_supported(path) is False


def test_the_fd_column_matches_a_hand_written_derivative():
    """Each peak column against a hand-written derivative, not against another FD.

    The whole-model FD is the right *fallback* and the wrong *reference*
    (CLAUDE.md § Invariants), so the oracle here is the analytic derivative of
    the Gaussian chained through the transform.  ``position`` and ``fwhm`` are
    nonlinear in their parameter, so their columns carry O(h) truncation error
    and the bar says so.

    ``height`` is different and its bar is derived rather than declared.  y is
    **linear** in h, so that column has no truncation error at any step — but
    that is not the same as being exact.  ``_make_jacobian`` takes a *forward*
    difference of the whole residual at h = 1e-6·max(1, |θ|), so the two
    vectors it subtracts agree to ~h·∂r/∂u and the accuracy floor is the
    **cancellation** term ε·max|r|/h.  This is the invariant's own sentence —
    "the error growing as the step shrinks is cancellation rather than a
    defect" — and it is why the bar cannot be zero-with-a-tight-tolerance.

    That distinction is not academic here.  An earlier version of this test
    called the column exact and asserted a flat ``1e-9 * scale``, which on this
    fixture is 7.07e-11 against a floor of 7.45e-11 — a bar sitting *on* the
    floor, so which side of it a platform lands is decided by BLAS summation
    order.  It passed CI py3.11, py3.13 and py3.14 and failed py3.12 at 1.22×
    the floor, while this machine measured 0.34×.  The margin below is over the
    floor, which is the quantity that actually moves.
    """
    _s, _i, _d, table, model = _state(peaks=(_peak(),))
    theta = table.x0()
    jac = _make_jacobian(model, table)(theta)
    values = table.decode(theta)
    free = list(table.free_paths)
    sqrt_w = 1.0 / model.sigma
    n_data = len(model.tt)

    tt = model.tt
    pos = values[PEAK_PATHS[0]]
    height = values[PEAK_PATHS[1]]
    fwhm = values[PEAK_PATHS[2]]
    u = (tt - pos) / fwhm
    curve = height * np.exp(-4.0 * np.log(2.0) * u * u)

    from rietx.params.transforms import dphys_dinternal

    def dpdu(path):
        e = table.entries[table._paths[path]]
        return dphys_dinternal(float(theta[free.index(path)]), e.transform)

    expect = {
        # ∂/∂2θ₀ = +8 ln2 · u/Γ · curve
        PEAK_PATHS[0]: 8.0 * np.log(2.0) * u / fwhm * curve,
        PEAK_PATHS[1]: curve / height,
        # ∂/∂Γ = +8 ln2 · u²/Γ · curve
        PEAK_PATHS[2]: 8.0 * np.log(2.0) * u * u / fwhm * curve,
    }
    # ε·max|r|/h, with h spelled exactly as ``_make_jacobian`` spells it — the
    # floor is a property of this fixture's residual, so it is measured here
    # rather than carried as a constant that would rot when the fixture moves.
    resid = _make_residual(model, table)(theta)[:n_data]

    def cancellation_floor(path):
        h = 1e-6 * max(1.0, abs(float(theta[free.index(path)])))
        return np.finfo(np.float64).eps * np.max(np.abs(resid)) / h

    # relative, against the column's own scale, for the two truncation-limited
    # columns; absolute, against the floor, for the one that has no truncation
    # term to be limited by.  4× is ~3× clear of the worst reading seen on any
    # CI platform and still leaves the height column ~2500× tighter than these.
    rel_bars = {PEAK_PATHS[0]: 2e-5, PEAK_PATHS[2]: 2e-5}
    for path, dy in expect.items():
        col = jac[:n_data, free.index(path)]
        # the residual is (y_obs − y_calc)/σ, hence the minus sign
        truth = -sqrt_w * dy * dpdu(path)
        err = np.max(np.abs(col - truth))
        if path in rel_bars:
            assert err <= rel_bars[path] * np.max(np.abs(truth)), path
        else:
            assert err <= 4.0 * cancellation_floor(path), path


def test_a_peak_column_is_exactly_zero_on_every_row_below_the_data():
    """Why writing only the data rows is *exact* rather than short.

    A P-spline background carries penalty rows √λ·D₂·c in the background
    *coefficients*; a peak parameter moves none of them, so the rows the FD
    leaves at their zero initialisation are the rows whose true value is zero.
    """
    _s, _i, _d, table, model = _state(
        peaks=(_peak(),),
        background=BackgroundPSpline.for_range(15.0, 110.0, knot_step_deg=8.0),
        free=(*PEAK_PATHS, "instrument.background.c3"))
    theta = table.x0()
    jac = _make_jacobian(model, table)(theta)
    n_data = len(model.tt)
    assert jac.shape[0] > n_data, "the P-spline penalty rows are the point"
    free = list(table.free_paths)
    for path in PEAK_PATHS:
        assert np.array_equal(jac[n_data:, free.index(path)],
                              np.zeros(jac.shape[0] - n_data))
    # and the coefficient column beside it is *not* zero there, so the test
    # above is not passing because the block is empty
    assert np.any(jac[n_data:, free.index("instrument.background.c3")])


def test_the_residual_sees_the_peak():
    """A sanity floor under the Jacobian tests: the term reaches the residual."""
    _s, _i, _d, table, model = _state(peaks=(_peak(),))
    theta = table.x0()
    r = np.asarray(_make_residual(model, table)(theta))
    lowered = theta.copy()
    lowered[list(table.free_paths).index(PEAK_PATHS[1])] -= 1.0
    assert not np.array_equal(r, np.asarray(
        _make_residual(model, table)(lowered)))


# ----------------------------------------------------------------------
# the width guard — the feature's physical content
# ----------------------------------------------------------------------
def test_a_broad_peak_trips_nothing_and_a_narrow_one_is_reported():
    _s, _i, _d, table, model = _state(peaks=(_peak(fwhm=7.0),))
    assert check_hump_width(table, model) == []

    values = {e.path: e.value for e in table.entries}
    gamma = float(model.instrument_fwhm_deg(values[PEAK_PATHS[0]], values))
    assert 7.0 / gamma > HUMP_MIN_WIDTH_MULT

    narrow = 0.5 * HUMP_MIN_WIDTH_MULT * gamma
    table.entries[table._paths[PEAK_PATHS[2]]].value = narrow
    findings = check_hump_width(table, model)
    assert [f.code for f in findings] == ["HUMP_TOO_NARROW"]
    assert findings[0].paths == (PEAK_PATHS[2],)
    assert findings[0].value == pytest.approx(narrow / gamma)
    assert "instrumental" in str(findings[0])


def test_the_guard_is_silent_without_a_model_or_without_peaks():
    """The ``check_stephens_positive`` convention: no model, no claim."""
    _s, _i, _d, table, model = _state(peaks=())
    assert check_hump_width(table, model) == []
    assert check_hump_width(table, None) == []


def test_the_width_guard_abstains_where_the_resolution_is_not_evaluable():
    """Report-or-abstain, never guess a physical floor.

    A schema-legal but ill-conditioned Caglioti quadratic Γ_G² = U·tan²θ +
    V·tanθ + W can dip negative; ``gaussian_fwhm`` then clamps Γ_G² to its
    numerical floor, and with no Lorentzian X/Y left to carry a width the total
    instrumental resolution collapses to ~1e-4°.  Judging a peak against that
    would silently *endorse* it (any real width clears 4·1e-4°), so the guard
    abstains rather than pass.  Pins the abstention against the rejected
    alternative — flooring Γ_instrument at an invented physical value, which
    would start flagging here.
    """
    structure = make_lab6()
    structure.phases[0].scale.value = 3e-4
    ins = rx.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.source.dispersion = None
    ins.profile.u.value = 0.05
    ins.profile.v.value = -0.5      # drives Γ_G² negative across the range
    ins.profile.w.value = 0.001
    ins.profile.x.value = 0.0       # no Lorentzian width to recover it
    ins.profile.y.value = 0.0
    # 0.15° is near a genuine resolution and would be flagged at a healthy angle
    ins.extra_components = [_peak(position=150.0, height=50.0, fwhm=0.15,
                                  vary=False)]
    tt = np.arange(15.0, 160.0, 0.05)
    data = PatternData(two_theta=tt.tolist(),
                       intensity=np.full_like(tt, 200.0).tolist())
    table = ParameterTable(structure, ins)
    model = compile_model(structure, ins, data, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    values = {e.path: e.value for e in table.entries}
    assert float(model.instrument_fwhm_deg(150.0, values)) < 1e-3  # collapsed
    assert check_hump_width(table, model) == []          # abstained


def test_findings_are_in_the_diagnostic_emission_order():
    """``findings()`` promises 'the order the diagnostics are emitted in'
    (``refine._guard_diagnostics``): a narrow-peak finding is emitted *before*
    the background- and roughness-absorption findings, so it must sort there."""
    from rietx.strategy.staged import GuardFinding, GuardReport

    r = GuardReport()
    narrow = GuardFinding.narrow_hump(
        "instrument.extra_components.0.fwhm", 0.2, 0.1, 30.0)
    bg = GuardFinding.background_absorption("phases.0.scale", 0.9)
    rough = GuardFinding.background_absorption("phases.0.atoms.0.biso", 0.95)
    r.narrow_humps = [narrow]
    r.background_correlations = [bg]
    r.roughness_correlations = [rough]
    flat = r.findings()
    assert flat.index(narrow) < flat.index(bg) < flat.index(rough)


def test_the_width_bound_is_measured_against_the_instrument_alone():
    """Γ_inst must not depend on which phase one asks about — the question is
    how narrow a *real* reflection can be at that angle."""
    structure, ins, data, table, model = _state(peaks=(_peak(),))
    values = {e.path: e.value for e in table.entries}
    before = float(model.instrument_fwhm_deg(32.0, values))
    structure.phases[0].lor_size.value = 0.4     # heavy sample broadening
    table2 = ParameterTable(structure, ins)
    model2 = compile_model(structure, ins, data, mode="rietveld")
    after = float(model2.instrument_fwhm_deg(
        32.0, {e.path: e.value for e in table2.entries}))
    assert after == pytest.approx(before, rel=1e-15)


# ----------------------------------------------------------------------
# the absorption block, and the span it is built from
# ----------------------------------------------------------------------
def test_a_softplus_off_state_does_not_by_itself_make_a_zero_column():
    """Why the ``_span_basis`` filter changes nothing that shipped before it.

    ``to_internal`` clamps, so a softplus parameter at its own off state has a
    tiny-but-real derivative rather than none, and no design row is zero either.
    An exactly-zero column comes from a **product** — a peak at zero height —
    which is what the filter is for.
    """
    from rietx.params.transforms import dphys_dinternal, to_internal

    u = to_internal(0.0, "softplus")
    assert np.isfinite(u) and dphys_dinternal(u, "softplus") > 0.0

    _s, _i, _d, _t, model = _state(
        peaks=(),
        background=BackgroundPSpline.for_range(15.0, 110.0, knot_step_deg=8.0),
        free=())
    assert all(np.any(row) for row in model.bkg_design)

    # the product, which is exactly zero: h = 0 kills ∂y/∂2θ₀ and ∂y/∂Γ
    _s, _i, _d, table, model = _state(peaks=(_peak(height=0.0),))
    theta = table.x0()
    jac = _make_jacobian(model, table)(theta)
    free = list(table.free_paths)
    n_data = len(model.tt)
    for path in (PEAK_PATHS[0], PEAK_PATHS[2]):
        assert not np.any(jac[:n_data, free.index(path)]), path


def test_a_zero_column_is_dropped_from_a_projection_span():
    """LAPACK's Q is orthonormal whatever the rank of A, so a zero column of A
    becomes an arbitrary direction and saturates every R² at 1."""
    jac = np.zeros((6, 4))
    jac[:, 0] = [1.0, 1.0, 0.0, 0.0, 0.0, 0.0]      # the only real column
    jac[:, 3] = [0.0, 0.0, 0.0, 1.0, 0.0, 0.0]      # the target
    assert _span_basis(jac, [0, 1, 2]).shape == (6, 1)
    r2 = background_absorption(jac, ["instrument.background.c0",
                                     "instrument.extra_components.0.position",
                                     "instrument.extra_components.0.fwhm",
                                     "phases.0.scale"], frozenset())
    assert r2["phases.0.scale"] == pytest.approx(0.0, abs=1e-12)
    # all-zero block: the projector is zero, i.e. "imitates nothing"
    assert _span_basis(np.zeros((6, 2)), [0, 1]).shape == (6, 0)


def test_a_non_finite_column_withholds_the_statistic_rather_than_reporting_nan():
    """The opposite of the zero column: it *silences* the guard.

    A zero column saturates every R² at 1; one NaN entry poisons the QR and
    every R² comes back ``nan``, which compares ``False`` against the
    threshold — so ``BACKGROUND_ABSORPTION`` never fires and
    ``FitReport.background.worst_absorption`` carries ``nan`` instead of a
    number.  ``np.any`` does not catch it, NaN being truthy.  Absence is a
    state every consumer already handles (WP-1130).
    """
    free = ["instrument.background.c0", "instrument.background.c1",
            "phases.0.scale"]
    jac = np.zeros((6, 3))
    jac[:, 0] = [1.0, 1.0, 0.0, 0.0, 0.0, 0.0]
    jac[:, 1] = [0.0, 1.0, 1.0, 0.0, 0.0, 0.0]
    jac[:, 2] = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    assert "phases.0.scale" in background_absorption(jac, free, frozenset())

    for col, value in [(0, np.nan), (1, np.inf),      # the block
                       (2, np.nan), (2, np.inf)]:     # the target
        bad = jac.copy()
        bad[3, col] = value
        assert background_absorption(bad, free, frozenset()) == {}, (col, value)

    # a NaN column is *not* quietly dropped from the span the way a zero one
    # is: it spans something unknown, and narrowing the span would understate
    # every R² built on it
    bad = jac.copy()
    bad[3, 0] = np.nan
    assert _span_basis(bad, [0, 1]).shape[1] == 2


def test_hump_columns_join_the_background_block():
    """The statistic asks what the *whole declared background* can imitate."""
    jac = np.zeros((5, 2))
    jac[:, 0] = [1.0, 0.0, 0.0, 0.0, 0.0]
    jac[:, 1] = [1.0, 1.0, 0.0, 0.0, 0.0]
    with_hump = background_absorption(
        jac, ["instrument.extra_components.0.height", "phases.0.scale"],
        frozenset())
    without = background_absorption(jac, ["instrument.profile.w",
                                          "phases.0.scale"], frozenset())
    assert with_hump["phases.0.scale"] == pytest.approx(0.5)
    assert without == {}       # no background column at all, nothing to project


def test_a_declared_peak_is_not_background_flexibility():
    """The seam's second member had to split this statistic in two (WP-1103).

    `instrument.extra_components.` stopped meaning "background" the moment the
    union gained a peak: a `PeakComponent` is not in `y_background`, so its
    columns in the background block would report a perfectly stiff background
    as absorbing whatever a declared holder line happens to be correlated with.

    The two statistics **partition** the declared components — the same set is
    excluded from one and taken by the other — so a component is counted once,
    which is clause 2 of the member contract reaching a statistic instead of a
    curve.
    """
    jac = np.zeros((5, 2))
    jac[:, 0] = [1.0, 0.0, 0.0, 0.0, 0.0]
    jac[:, 1] = [1.0, 1.0, 0.0, 0.0, 0.0]
    free = ["instrument.extra_components.0.area", "phases.0.scale"]
    peaks = frozenset({"instrument.extra_components.0."})

    # as a hump it is background; as a peak it is not
    assert background_absorption(jac, free, frozenset())["phases.0.scale"] \
        == pytest.approx(0.5)
    assert background_absorption(jac, free, peaks) == {}
    assert extra_peak_absorption(jac, free, peaks)["phases.0.scale"] \
        == pytest.approx(0.5)
    assert extra_peak_absorption(jac, free, frozenset()) == {}


def test_the_two_absorption_statistics_partition_the_components():
    """One model, one prefix set, and no component in both blocks or neither."""
    structure = make_lab6()
    ins = _instrument(peaks=[
        HumpComponent(position=Parameter(value=35.0, unit="deg")),
        make_peak(center=40.0, area=300.0),
    ])
    tt = np.arange(30.0, 50.0, 0.01)
    data = PatternData(two_theta=tt.tolist(),
                       intensity=np.full_like(tt, 50.0).tolist())
    table = ParameterTable(structure, ins)
    model = compile_model(structure, ins, data, mode="rietveld",
                          moving_paths=set(table.moving_paths))

    prefixes = model.peak_component_prefixes()
    assert prefixes == {"instrument.extra_components.1."}

    declared = [f"instrument.extra_components.{i}.{n}"
                for i, names in ((0, HUMP_FIELDS), (1, PEAK_FIELDS))
                for n in names]
    in_bg = {p for p in declared if not p.startswith(tuple(prefixes))}
    in_pk = {p for p in declared if p.startswith(tuple(prefixes))}
    assert in_bg | in_pk == set(declared)
    assert not (in_bg & in_pk)


def test_a_hump_is_a_roughness_nuisance_too():
    """The sibling of ``background_absorption`` folding humps into its block
    (candidate 3): a declared hump is background flexibility that refines
    regardless, so the roughness/ADP comparison projects it out first — three
    columns per hump left in would swamp the partial R² exactly as the scale
    does.  Was matched only for ``instrument.background.`` while its sibling
    already matched ``instrument.extra_components.``.
    """
    from rietx.optimize.statistics import _roughness_nuisance

    none: frozenset[str] = frozenset()
    assert _roughness_nuisance("instrument.extra_components.0.height", none)
    assert _roughness_nuisance("instrument.extra_components.3.position", none)
    assert _roughness_nuisance("instrument.background.c2", none)
    assert _roughness_nuisance("phases.0.scale", none)
    assert not _roughness_nuisance("phases.0.atoms.0.biso", none)
    assert not _roughness_nuisance(
        "instrument.geometry.surface_roughness.suortti_b", none)


def test_a_declared_peak_is_not_a_roughness_nuisance():
    """The partition reaches the *third* statistic, not only the first two.

    ``background_absorption`` excludes the peak-landing components and
    ``extra_peak_absorption`` takes them; ``roughness_absorption`` projects the
    same partition out as nuisance, so all three divide one list the same way.
    Projecting a declared sharp peak out here would shrink the very partial R²
    the roughness guard is read from — and the ``mccusker_structural`` plan
    frees the two blocks in the same fit.
    """
    from rietx.optimize.statistics import _roughness_nuisance

    peaks = frozenset({"instrument.extra_components.1."})
    assert not _roughness_nuisance("instrument.extra_components.1.center", peaks)
    assert not _roughness_nuisance("instrument.extra_components.1.area", peaks)
    # index 1 and index 11 are different components: the trailing dot is why
    assert _roughness_nuisance("instrument.extra_components.11.height", peaks)
    # a hump declared beside it is still a nuisance
    assert _roughness_nuisance("instrument.extra_components.0.height", peaks)
    assert _roughness_nuisance("instrument.background.c2", peaks)


# ----------------------------------------------------------------------
# the surfaces
# ----------------------------------------------------------------------
def test_the_structural_plan_can_free_a_declared_peak_and_nothing_else():
    globs = [g for stage in PLAN_PRESETS["mccusker_structural"]().stages
             for g in stage.turn_on]
    assert "instrument.extra_components.*" in globs

    # declared: the glob frees exactly the three
    _s, _i, _d, table, _m = _state(peaks=(_peak(vary=False),), free=())
    before = set(table.free_paths)
    table.set_vary(["instrument.extra_components.*"], True)
    assert set(table.free_paths) - before == set(PEAK_PATHS)

    # not declared: the same glob frees nothing, which is what makes the stage
    # safe in a plan that runs against instruments with no hump
    _s, _i, _d, empty, _m = _state(peaks=(), free=())
    unchanged = set(empty.free_paths)
    empty.set_vary(["instrument.extra_components.*"], True)
    assert set(empty.free_paths) == unchanged


def test_no_plan_and_no_estimator_ever_adds_a_peak():
    """The model may not grow its own free peaks — that is the whole safety
    property of a term whose three parameters improve any Rwp."""
    for build in PLAN_PRESETS.values():
        for stage in build().stages:
            for glob in stage.turn_on:
                assert "extra_components" not in glob or glob.endswith(".*")
    tt = np.arange(10.0, 90.0, 0.05)
    data = PatternData(two_theta=tt.tolist(),
                       intensity=(200.0 + 400.0 * np.exp(
                           -0.5 * ((tt - 25.0) / 6.0) ** 2)).tolist())
    for kind in ("chebyshev", "pspline"):
        bkg = rx.auto_background(data, kind=kind, wavelength=WAVELENGTH)
        assert not hasattr(bkg, "extra_components")


def test_the_cif_description_and_the_instrument_profile_both_say_so():
    ins = _instrument(peaks=(_peak(),))
    assert "1 explicit Gaussian background peak" in _background_description(ins)
    two = _instrument(peaks=(_peak(), _peak(position=70.0)))
    assert "2 explicit Gaussian background peaks" in _background_description(two)
    assert "background peak" not in _background_description(_instrument())


# ----------------------------------------------------------------------
# the claim, on a synthetic case whose truth is known
# ----------------------------------------------------------------------
#: The synthetic hump, in the shape of the case the feature was built for: a
#: constant-wavelength neutron pattern with ~0.3° lines and a 5.8°-wide feature
#: near 14.4° 2θ, which on that instrument is ~20× the resolution.  Truth, so a
#: test can ask whether it comes back rather than whether Rwp fell.
HUMP_TRUTH = {"position": 14.4, "height": 90.0, "fwhm": 5.8}
HUMP_BISO = 0.35


def synthetic_hump_case():
    """``(data, structure, instrument_without_peak, truth)`` for the hump case.

    A **generator** as well as a fixture: ``docs/manual/make_figures.py``
    imports this so the committed figure and the assertion below draw the same
    case.  A figure with its own copy of a case can disagree with the test that
    proves the claim, and nobody would find out (that script's own rule).

    The instrument returned declares **no** peak — the two fits differ by
    exactly that, which is what makes the comparison mean anything.
    """
    structure = make_lab6()
    phase = structure.phases[0]
    phase.scale.value = 4e-4
    for atom in phase.atoms:
        atom.biso.value = HUMP_BISO
    ins = rx.Instrument.constant_wavelength_neutron(2.078, fwhm_deg=0.30)
    ins.background = BackgroundChebyshev.with_terms(4)

    tt = np.arange(6.0, 120.0, 0.05)
    grid = PatternData(two_theta=tt.tolist(), intensity=[0.0] * len(tt))
    table = ParameterTable(structure, ins)
    model = compile_model(structure, ins, grid, mode="rietveld")
    xp = rx.backend.get_backend()
    y = (np.asarray(model.evaluate(table.decode(table.x0())))
         + 900.0 - 1.2 * model.tt
         + np.asarray(hump_curve(
             model.tt, HUMP_TRUTH["position"], HUMP_TRUTH["height"],
             HUMP_TRUTH["fwhm"], xp)))
    rng = np.random.default_rng(11)
    data = PatternData(
        two_theta=model.tt.tolist(),
        intensity=rng.poisson(np.maximum(y, 1.0)).astype(float).tolist())
    return data, structure, ins, dict(HUMP_TRUTH)


def fit_hump_case(*, with_peak: bool):
    """One arm of the comparison: the same case with and without the peak."""
    data, structure, ins, truth = synthetic_hump_case()
    if with_peak:
        ins.extra_components = [_peak(position=13.0, height=30.0, fwhm=5.0,
                                      vary=False)]
    plan = PLAN_PRESETS["mccusker_structural"]()
    return rx.refine(data, structure, ins, plan=plan), truth


@pytest.mark.xdist_group("background-peak-hump")
def test_a_known_hump_comes_back_within_its_esds():
    """The record field, not Rwp, is the evidence (root CLAUDE.md).

    The peak is seeded 1.4° off and 0.8° narrow, so this asks whether the three
    parameters *find* a feature whose truth is known — the claim the feature
    actually makes.  It deliberately does **not** assert that the structural
    parameters improve: on this fixture they are not determined well enough to
    carry such a claim (scale esd 209 on a value of 0.046), and the real-data
    measurement in `docs/manual/using/data.md` reports what happened there,
    including where it did not go the expected way.
    """
    result, truth = fit_hump_case(with_peak=True)
    got = {row.path.rsplit(".", 1)[1]: row for row in result.parameters
           if "extra_components" in row.path}
    assert set(got) == set(HUMP_FIELDS)
    for name in ("position", "fwhm", "height"):
        row = got[name]
        assert row.stderr is not None and row.stderr > 0.0, name
        assert abs(row.value - truth[name]) <= 2.0 * row.stderr, (
            f"{name}: {row.value} vs truth {truth[name]} ± {row.stderr}")
    assert not [d for d in result.diagnostics
                if d.code == "HUMP_TOO_NARROW"]
    assert result.n_extra_components == 1


@pytest.mark.xdist_group("background-peak-hump")
def test_the_declared_count_reaches_the_record_and_the_report():
    """A projection, not a second count — the two must never disagree."""
    from rietx.report import build_report

    result, _truth = fit_hump_case(with_peak=True)
    assert result.n_extra_components == 1
    assert build_report(result).background.n_peaks == 1

    none, _truth = fit_hump_case(with_peak=False)
    assert none.n_extra_components == 0
    assert build_report(none).background.n_peaks == 0


def test_a_replayed_node_reports_the_peaks_its_instrument_declares():
    """The count is *declared*, so it does not live behind the guard.

    ``Identifiability``'s four other members are read off the final Jacobian and
    so exist only where a solve measured them — ``replay`` is evaluate-only and
    correctly carries ``None`` there, which is a tested invariant and stays one
    (asserted below, both halves).  The declared count is not a measurement:
    it is ``len(model.component_paths)``, available wherever a compiled model is,
    and behind that guard it read 0 on every replayed node — "none declared",
    which is a different claim from the true one.

    The bar is the *count*, not a statistic, so the fit underneath is
    deliberately the cheapest one that commits a node.
    """
    from rietx.report import build_report

    structure = make_lab6()
    structure.phases[0].scale.value = 3e-4
    ins = _instrument(peaks=(_peak(vary=False),))
    tt = np.arange(15.0, 60.0, 0.05)
    data = PatternData(two_theta=tt.tolist(),
                       intensity=np.full_like(tt, 200.0).tolist())

    ref = rx.Refinement(structure, ins)
    result = ref.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage(name="bkg", turn_on=["instrument.background.*"], max_iter=2)]))
    assert result.n_extra_components == 1

    replayed = rx.replay(ref.history, result.node_id, data)
    # the invariant this field used to be gated by, intact in both directions
    assert replayed.identifiability is None
    assert build_report(replayed).background.absorption is None
    # and the declared count, which never needed it
    assert replayed.n_extra_components == 1
    assert build_report(replayed).background.n_peaks == 1


def test_save_instrument_profile_strips_the_peaks(tmp_path):
    """A hump belongs to this specimen and this sample environment, so carrying
    one into the next sample would put a free peak where nothing measured."""
    path = tmp_path / "profile.json"
    save_instrument_profile(_instrument(peaks=(_peak(),)), path)
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert "extra_components" not in doc["instrument"]
    assert rx.load_instrument_profile(path).extra_components == []


# ----------------------------------------------------------------------
# the v1.2 rename: old files open, old code does not (WP-1102)
# ----------------------------------------------------------------------


def test_a_v1_2_instrument_block_still_deserializes():
    """The loud half.  ``background_peaks`` was this field's name in v1.2."""
    doc = json.loads(_instrument(peaks=(_peak(),)).model_dump_json())
    doc["background_peaks"] = doc.pop("extra_components")
    migrated = Instrument.model_validate(doc)
    assert len(migrated.extra_components) == 1
    assert migrated.extra_components[0].fwhm.value == pytest.approx(7.0)
    assert migrated.extra_components[0].kind == "hump"


def test_writing_the_old_field_name_in_code_still_raises():
    """The direction the break runs in: documents are repaired, code is not.

    A caller who kept ``instrument.background_peaks = [...]`` gets a refusal
    rather than an attribute that quietly goes nowhere, which is what a model
    without ``extra="forbid"`` would have handed them.
    """
    ins = _instrument()
    with pytest.raises(ValueError):
        ins.background_peaks = [_peak()]


def test_a_stored_plan_glob_is_migrated_and_not_merely_the_value():
    """The silent half, and the whole reason the repair is textual.

    A v1.2 project's saved plan frees ``instrument.background_peaks.*``.
    Migrate only the field and the document opens, the stage runs, the glob
    matches nothing, and the declared hump is never refined — a plausible
    answer with no error anywhere.  The path is what this pins.
    """
    doc = json.dumps({
        "plan": {"stages": [{"name": "humps",
                             "turn_on": ["instrument.background_peaks.*"]}]},
        "free_paths": ["instrument.background_peaks.0.height"],
    })
    out, changed = migrate_document_text(doc)
    assert changed
    parsed = json.loads(out)
    assert parsed["plan"]["stages"][0]["turn_on"] == [
        "instrument.extra_components.*"]
    assert parsed["free_paths"] == ["instrument.extra_components.0.height"]


def test_an_rxt_row_is_migrated_though_it_carries_no_instrument_prefix():
    """The gap a prefix-anchored rule leaves, caught in review.

    ``.rxt`` renders each block with its own prefix stripped, so a v1.2
    document spells the row ``background_peaks.0.fwhm``. A repair anchored on
    ``instrument.`` migrates the project JSON and the history tree and misses
    the text document — the same silent class the whole module exists for.
    """
    doc = ("rxt 1\n"
           "instrument\n"
           "  zero_shift        @ 0.0021\n"
           "  background_peaks.0.fwhm  @ 5.4\n")
    out, changed = migrate_document_text(doc)
    assert changed
    assert "extra_components.0.fwhm" in out
    assert "background_peaks" not in out


def test_the_plan_block_renders_globs_in_full_and_is_covered_too():
    """The other spelling in the same file: a stage line carries the prefix."""
    line = "stage humps       free instrument.background_peaks.*\n"
    out, _ = migrate_document_text(line)
    assert out.strip().endswith("instrument.extra_components.*")


def test_the_migration_is_a_no_op_on_a_document_this_release_wrote():
    """It runs unconditionally on every read, so it must cost nothing."""
    doc = _instrument(peaks=(_peak(),)).model_dump_json()
    out, changed = migrate_document_text(doc)
    assert out == doc and not changed


def test_the_migration_is_idempotent():
    once, _ = migrate_document_text(
        '{"free_paths": ["instrument.background_peaks.0.fwhm"]}')
    twice, changed = migrate_document_text(once)
    assert twice == once and not changed


@pytest.mark.parametrize("stored,expected", [
    # the JSON key, in a project document or a history node
    ('"background_peaks": []', '"extra_components": []'),
    # a dot-path in free_paths
    ("instrument.background_peaks.0.fwhm",
     "instrument.extra_components.0.fwhm"),
    # the same row in an .rxt, where the block prefix is stripped
    ("background_peaks.0.fwhm", "extra_components.0.fwhm"),
    # a glob written without the dot, which fnmatch accepts
    ("instrument.background_peaks*", "instrument.extra_components*"),
    # the bare path, no trailing anything
    ("instrument.background_peaks", "instrument.extra_components"),
])
def test_every_shape_the_legacy_name_reaches_a_document_in(stored, expected):
    """Four spellings plus the bare one, and one rule has to catch all of them.

    Anchoring on any single shape misses the others; the first version of this
    module anchored on ``instrument.`` and missed the ``.rxt`` row.
    """
    assert migrate_document_text(stored)[0] == expected


def test_a_word_that_merely_contains_the_legacy_name_is_left_alone():
    """The word boundary is what keeps the rule from over-reaching."""
    for safe in ("background_peaksish", "my_background_peaks_note"):
        out, changed = migrate_document_text(safe)
        assert out == safe and not changed


def test_a_v1_2_project_directory_opens_and_its_plan_still_frees_the_hump(
        tmp_path):
    """The acceptance row, end to end rather than at the repair.

    Everything above pins the textual rule; this pins the thing the rule is
    for. A project written by v1.2 is reconstructed on disk in the old
    spelling — the instrument's field *and* the saved plan's glob — and then
    opened by this release. The assertion that matters is the second one: the
    document could open cleanly with the plan quietly freeing nothing, which is
    the failure mode with no error attached to it.
    """
    from tests.test_project import _create, _write_xye
    from tests.test_refine_synthetic import synthesize

    pattern_file = _write_xye(tmp_path / "synth.xye", synthesize())
    _create(tmp_path / "s.rex", pattern_file, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale"]),
        rx.Stage("humps", ["instrument.extra_components.*"]),
    ]))
    doc_path = tmp_path / "s.rex" / "project.json"

    # rewrite the saved project the way v1.2 wrote it
    written = doc_path.read_text(encoding="utf-8")
    written = written.replace("instrument.extra_components.",
                              "instrument.background_peaks.")
    doc_path.write_text(written, encoding="utf-8")
    assert "background_peaks" in doc_path.read_text(encoding="utf-8")

    reopened = rx.Project.open(tmp_path / "s.rex")
    globs = [g for stage in reopened.doc.plan.stages for g in stage.turn_on]
    assert "instrument.extra_components.*" in globs
    assert not any("background_peaks" in g for g in globs)


def test_every_declared_read_point_exists_and_is_callable():
    """``READ_POINTS`` is a claim, and a claim is checked (WP-1076).

    The tuple says these three readers migrate.  Renaming or moving one
    without moving the tuple leaves it describing a reader that is gone, and
    nothing else would go red.
    """
    import importlib

    for dotted in READ_POINTS:
        parts = dotted.split(".")
        for i in range(len(parts), 1, -1):
            try:
                module = importlib.import_module(".".join(parts[:i]))
            except ModuleNotFoundError:
                continue
            break
        else:                                    # pragma: no cover - a failure
            raise AssertionError(f"no importable module in {dotted}")
        target = module
        for part in parts[i:]:
            target = getattr(target, part)
        assert callable(target), dotted


def test_a_v1_2_result_json_still_opens_under_the_new_count_name():
    """The other renamed field, and the one the textual repair cannot reach.

    ``n_background_peaks`` carries no word boundary before the legacy name, so
    ``migrate_document_text`` leaves it alone by construction, and a saved
    result is read at a fourth point (``rietx html <result.json>``) that is not
    one of ``READ_POINTS``.  Repaired at the schema instead, the way the
    instrument's own field is, so a v1.2 result opens rather than raising
    ``extra_forbidden`` — old documents open.
    """
    from rietx.schemas.results import RefinementResult

    doc = {"mode": "rietveld", "status": "converged",
           "provenance": {"package_version": "1.2.0"},
           "two_theta": [10.0], "y_obs": [1.0], "y_calc": [1.0],
           "parameters": [],
           "statistics": {"rwp": 1.0, "rp": 1.0, "rexp": 1.0, "chi2": 1.0,
                          "gof": 1.0, "n_points": 1, "n_free_parameters": 0},
           "n_background_peaks": 2}
    assert migrate_document_text(json.dumps(doc))[1] is False
    assert RefinementResult.model_validate(doc).n_extra_components == 2


# ----------------------------------------------------------------------
# The second member: a declared sharp peak (WP-1103)
#
# `HumpComponent` alone left clause 2 of the member contract — a member's
# aggregate membership is *declared data*, never read off the class name — as a
# design intention with nothing exercising it.  These tests are what make it a
# tested one, so the ones that matter most are the ones about *where the member
# lands* rather than about arithmetic: a peak is not background, its curve must
# leave `y_background` alone, and its positions must reach the tick list.
# ----------------------------------------------------------------------


def make_peak(center=28.4, span=0.4, area=None, **kw):
    """A `PeakComponent` with the finite centre bounds the schema requires."""
    kw.setdefault("center", Parameter(value=center, min=center - span,
                                      max=center + span, unit="deg"))
    if area is not None:
        kw.setdefault("area", area if isinstance(area, Parameter) else
                      Parameter(value=area, min=0.0, unit="counts*deg",
                                transform="softplus"))
    return PeakComponent(**kw)


def test_the_union_has_two_members_and_dispatches_on_kind_not_shape():
    """Both members round-trip to their own class through one list.

    A structural union would be free to pick either class for a blob whose
    fields happened to fit, which is the accident root CLAUDE.md names for
    `PlanSpec`; the discriminator is what makes the answer a lookup.
    """
    inst = _instrument(peaks=[
        HumpComponent(position=Parameter(value=20.0, unit="deg")),
        make_peak(label="holder 110"),
    ])
    blob = inst.model_dump(mode="json")
    back = Instrument.model_validate(json.loads(json.dumps(blob)))
    assert [type(c).__name__ for c in back.extra_components] == [
        "HumpComponent", "PeakComponent"]
    assert [c.kind for c in back.extra_components] == ["hump", "peak"]
    assert back.extra_components[1].label == "holder 110"
    assert back.model_dump(mode="json") == blob


def test_json_round_trip_keeps_every_peak_component_parameter():
    """Every declared field survives, values and bounds alike.

    `HUMP_FIELDS`' test one member over; the bounds are load-bearing here in a
    way they are not for a hump, because they size the frozen window.
    """
    peak = make_peak(area=Parameter(value=1234.5, min=0.0, unit="counts*deg",
                                    transform="softplus"),
                     eta=Parameter(value=0.75, min=0.0, max=1.0,
                                   transform="logit"),
                     all_lines=False)
    peak.fwhm.value = 0.123
    back = PeakComponent.model_validate(
        json.loads(json.dumps(peak.model_dump(mode="json"))))
    for name in PEAK_FIELDS:
        before, after = getattr(peak, name), getattr(back, name)
        assert (after.value, after.min, after.max) == (
            before.value, before.min, before.max), name
    assert back.all_lines is False


def test_a_centre_or_width_with_no_finite_bound_is_refused_and_suggests_one():
    """The refusal names the field, says why, and shows what to write.

    A window frozen at stage compile cannot follow an unbounded parameter, so
    this is unbuildable rather than merely loose — and unlike the width floor it
    cannot be repaired, because the range is a fact about the caller's pattern
    that the schema cannot see.
    """
    with pytest.raises(ValidationError, match=r"center needs finite min and max"):
        PeakComponent()
    # an unbounded width has to be *stated* now: one that leaves ``max`` unset
    # inherits the declared box, as an omitted field always did (WP-1321)
    with pytest.raises(ValidationError, match=r"fwhm needs finite min and max"):
        make_peak(fwhm=Parameter(value=0.1, min=EXTRA_PEAK_FWHM_MIN, max=float("inf"),
                                 unit="deg", transform="softplus"))
    inherited = make_peak(fwhm=Parameter(value=0.1, min=EXTRA_PEAK_FWHM_MIN,
                                         unit="deg", transform="softplus"))
    assert inherited.fwhm.max == PeakComponent.model_fields["fwhm"].default_factory().max
    with pytest.raises(ValidationError) as excinfo:
        PeakComponent()
    assert "Parameter(value=" in str(excinfo.value)


def test_a_stored_zero_width_bound_is_repaired_at_this_members_floor():
    """The hump's repair, at this member's floor, for the same reason.

    A stored `min: 0.0` deserializes straight back into the pole and no
    `default_factory` runs on that path, so the repair has to live in a
    validator.  The floor differs from the hump's by 20x and that is the whole
    difference: 5 channels of the finest scan step rather than of the coarsest.
    """
    blob = make_peak().model_dump(mode="json")
    blob["fwhm"]["min"] = 0.0
    blob["fwhm"]["value"] = 0.0
    back = PeakComponent.model_validate(blob)
    assert back.fwhm.min == EXTRA_PEAK_FWHM_MIN
    assert back.fwhm.value == EXTRA_PEAK_FWHM_MIN
    assert EXTRA_PEAK_FWHM_MIN == pytest.approx(5 * 0.001)


def test_the_field_registry_covers_every_member_and_agrees_with_the_union():
    """Clause 4: one authority for which fields a member refines.

    Both directions, because each catches a different mistake — a member with
    no row registers no parameters at all (silent), and a row for a member that
    no longer exists outlives it (also silent).
    """
    kinds = {m.model_fields["kind"].default
             for m in typing.get_args(ExtraComponent)}
    assert set(COMPONENT_FIELDS) == kinds
    assert set(COMPONENT_AGGREGATE) == kinds
    for kind, member in ((m.model_fields["kind"].default, m)
                         for m in typing.get_args(ExtraComponent)):
        declared = set(COMPONENT_FIELDS[kind])
        actual = {n for n, f in member.model_fields.items()
                  if f.annotation is Parameter}
        assert declared == actual, kind


def test_aggregate_membership_is_read_from_data_not_from_the_class_name():
    """Clause 2, and the reason this WP exists.

    The registry is keyed by the `kind` discriminator, so a member's
    destination is a lookup.  The assertion that matters is the second one: the
    two members' aggregates *differ*, which is what makes the lookup do work
    that a shared default could not.
    """
    assert COMPONENT_AGGREGATE["hump"] == "background"
    assert COMPONENT_AGGREGATE["peak"] == "ticks"
    assert len(set(COMPONENT_AGGREGATE.values())) == 2


def test_both_halves_of_the_table_know_the_peak_component_paths():
    """`_collect_instrument` and `apply_to_models`, the clause 4 pair.

    The hump's version of this test one member over; it is repeated rather than
    parametrised because the failure it catches is a *field list* going out of
    step, and a shared loop would use one field list for both halves.
    """
    structure = make_lab6()
    instrument = _instrument(peaks=[make_peak()])
    table = ParameterTable(structure, instrument)
    paths = [f"instrument.extra_components.0.{n}" for n in PEAK_FIELDS]
    for path in paths:
        assert path in table._paths, path
    for path, value in zip(paths, (28.5, 777.0, 0.25, 0.321), strict=True):
        table.entries[table._paths[path]].value = value
    table.apply_to_models(structure, instrument)

    peak = instrument.extra_components[0]
    assert (peak.center.value, peak.area.value, peak.fwhm.value,
            peak.eta.value) == (28.5, 777.0, 0.25, 0.321)


def test_a_mixed_list_registers_each_member_with_its_own_fields():
    """A hump and a peak in one list, each contributing its own paths.

    The regression this guards is the one `isinstance` would have caused: a
    single hardcoded field tuple silently reads `position` off a peak that has
    none, or registers a peak's `eta` against a hump.
    """
    comps = [HumpComponent(position=Parameter(value=20.0, unit="deg")),
             make_peak()]
    subs = [sub for sub, _ in extra_component_parameters(comps)]
    assert subs == ["0.position", "0.height", "0.fwhm",
                    "1.center", "1.area", "1.fwhm", "1.eta"]


def test_the_intensity_field_is_not_called_scale():
    """Le Bail and Pawley force-fix every `*.scale` path, and a peak must not be.

    A naming rule with a functional consequence, so it is asserted against the
    function that would have enforced it rather than against the string.
    """
    from rietx.refine import mode_fixed_path

    for mode in ("lebail", "pawley"):
        for name in PEAK_FIELDS:
            path = f"instrument.extra_components.0.{name}"
            assert not mode_fixed_path(path, mode), (path, mode)


# ----------------------------------------------------------------------
# the forward model: windows from bounds, and every emission line
# ----------------------------------------------------------------------


def _peak_state(peak, *, lo=30.0, hi=50.0, step=0.005, radiation="CuKa",
                one_line=False):
    """A compiled model over a flat pattern with the phases switched off.

    The phases are off (`scale = 0`) so that every count in `evaluate` belongs
    to the declared peak: these tests are about *where the member lands*, and a
    Bragg contribution underneath would hide a peak landing in the wrong place.

    ``one_line`` drops the source to its primary line, which is a different
    thing from ``all_lines=False`` on the component — a source that *has* no
    Kα2 against a component that declines to image onto the one the source has.
    Their agreement is the assertion, so the two have to be built differently.
    """
    structure = make_lab6()
    structure.phases[0].scale.value = 0.0
    ins = rx.Instrument.bragg_brentano(radiation=radiation)
    ins.source.dispersion = None
    if one_line:
        ins.source.lines = [ins.source.lines[0]]
    ins.extra_components = [peak]
    tt = np.arange(lo, hi, step)
    data = PatternData(two_theta=tt.tolist(),
                       intensity=np.zeros_like(tt).tolist())
    table = ParameterTable(structure, ins)
    model = compile_model(structure, ins, data, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    return structure, ins, data, table, model


def test_a_declared_peak_is_not_background_anywhere():
    """Clause 2, where it actually bites.

    `background()` is the one authority every background consumer calls —
    `result.y_background`, the partition net, `report.texture`, `viz.live`.  A
    hump is inside it; a peak must not be, or every one of those would draw a
    holder reflection as background.
    """
    _s, _i, _d, table, model = _peak_state(
        make_peak(center=40.0, area=500.0))
    values = table.decode(table.x0())
    assert np.allclose(np.asarray(model.background(values)), 0.0)
    assert np.asarray(model.extra_peak_curve(values)).max() > 0.0


def test_the_peak_carries_its_declared_area_and_apex():
    """The unit-area pseudo-Voigt, so `area` is an area and the apex follows.

    Checked against the closed form rather than against a stored number: at the
    centre, pV(0) = 2η/(πΓ) + (1−η)(2/Γ)√(ln2/π), so the apex is a prediction
    and not a regression baseline.
    """
    peak = make_peak(center=40.0, area=500.0)
    _s, _i, _d, table, model = _peak_state(peak, one_line=True)
    y = np.asarray(model.extra_peak_curve(table.decode(table.x0())))
    gamma, eta = peak.fwhm.value, peak.eta.value
    apex = 500.0 * (2 * eta / (np.pi * gamma)
                    + (1 - eta) * (2 / gamma) * np.sqrt(np.log(2) / np.pi))
    assert y.max() == pytest.approx(apex, rel=1e-9)
    assert model.tt[int(np.argmax(y))] == pytest.approx(40.0, abs=0.005)


def test_every_emission_line_gets_an_image_at_its_own_bragg_angle():
    """Kα2 is physically there, and it is placed by Bragg's law, not by offset.

    `RefinementResult.ticks`' lesson one member over: a source with two lines
    makes two peaks out of one holder reflection, and a model that draws only
    the primary leaves the second as unexplained intensity.
    """
    peak = make_peak(center=40.0, area=500.0)
    peak.fwhm.value = 0.02                     # sharp enough to resolve
    _s, ins, _d, table, model = _peak_state(peak, lo=38.0, hi=42.0, step=0.001)
    y = np.asarray(model.extra_peak_curve(table.decode(table.x0())))
    ratio = float(model.peak_components[0].lam_ratio[1])
    expected = 2 * np.degrees(np.arcsin(ratio * np.sin(np.radians(20.0))))

    apexes = [float(model.tt[i]) for i in range(1, len(y) - 1)
              if y[i] > y[i - 1] and y[i] >= y[i + 1] and y[i] > 0.05 * y.max()]
    assert len(apexes) == 2
    assert apexes[0] == pytest.approx(40.0, abs=0.001)
    assert apexes[1] == pytest.approx(expected, abs=0.001)


def test_the_second_line_carries_its_own_lp_and_not_the_bare_weight():
    """The measured correction, asserted as a difference from the bare weight.

    Holding `weight` alone biases the fitted primary position — −2e-4° and
    −0.26 mean σ pull on lab Cu Kα LaB6 (WP-1018).  The gain is small (here
    ~0.6 % of the weight) and one-sided, which is exactly why it is a bias
    rather than noise, so the test asserts the *sign and size* of the departure
    rather than that a correction happened.
    """
    peak = make_peak(center=40.0, area=500.0)
    peak.fwhm.value = 0.02
    _s, _i, _d, table, model = _peak_state(peak, lo=38.0, hi=42.0, step=0.001)
    values = table.decode(table.x0())
    y = np.asarray(model.extra_peak_curve(values))

    ratio = float(model.peak_components[0].lam_ratio[1])
    pos2 = 2 * np.degrees(np.arcsin(ratio * np.sin(np.radians(20.0))))
    pol = float(values["instrument.polarization"])
    weight = float(values["instrument.source.lines.1.weight"])
    gain = weight * float(lorentz_polarization(np.float64(pos2), pol)
                          / lorentz_polarization(np.float64(40.0), pol))
    assert gain != weight
    assert gain == pytest.approx(weight, rel=1e-2)

    # the whole curve is the two images summed at that gain.  Each baseline is
    # built at its *own* centre rather than one baseline scaled twice: the two
    # images sit 0.1 deg apart, so on a finite grid their truncated tails are
    # not the same number and a single scaled baseline is only good to ~1e-6.
    def _one_at(centre):
        peak = make_peak(center=centre, area=500.0)
        peak.fwhm.value = 0.02
        _s, _i, _d, tb, mb = _peak_state(peak, lo=38.0, hi=42.0, step=0.001,
                                         one_line=True)
        return np.trapezoid(
            np.asarray(mb.extra_peak_curve(tb.decode(tb.x0()))), mb.tt)

    assert np.trapezoid(y, model.tt) == pytest.approx(
        _one_at(40.0) + gain * _one_at(pos2), rel=1e-9)


def test_all_lines_false_places_exactly_one_image():
    """A fluorescence line or a detector artefact has no Kα2.

    Placing one would be a claim about physics that is not happening, so the
    flag is not a convenience: it is the difference between modelling a
    diffraction peak and modelling something else.
    """
    peak = make_peak(center=40.0, area=500.0)
    peak.all_lines = False
    _s, _i, _d, table, model = _peak_state(peak)
    y = np.asarray(model.extra_peak_curve(table.decode(table.x0())))

    single = make_peak(center=40.0, area=500.0)
    _s2, _i2, _d2, t2, m2 = _peak_state(single, one_line=True)
    assert np.allclose(y, np.asarray(m2.extra_peak_curve(t2.decode(t2.x0()))))


def test_a_centre_driven_to_either_bound_stays_inside_its_frozen_window():
    """The invariant this member's bounds exist for.

    Windows are frozen at stage compile and sized from `center`'s bounds, so
    the claim is that *every* state the solver can legally reach is covered.
    Tested at both bounds rather than at one, and by comparing against an
    unwindowed evaluation on the same grid: a window that clipped the peak
    would leave a difference, and a window merely centred on the starting value
    would clip at the far bound only.
    """
    peak = make_peak(center=40.0, span=0.4, area=500.0)
    _s, _i, _d, table, model = _peak_state(peak, one_line=True)
    win = model.peak_components[0].win
    i0, i1 = int(win[0, 0]), int(win[0, 1])

    for edge in (peak.center.min, peak.center.max):
        values = table.decode(table.x0())
        values["instrument.extra_components.0.center"] = edge
        y = np.asarray(model.extra_peak_curve(values))
        assert model.tt[int(np.argmax(y))] == pytest.approx(edge, abs=0.005)
        # the profile is entirely inside the frozen index range, to the same
        # area tolerance every phase window is held to
        full = np.zeros_like(y)
        gamma, eta = peak.fwhm.value, peak.eta.value
        full[:] = 500.0 * pseudo_voigt(model.tt - edge, gamma, eta)
        kept = np.trapezoid(y, model.tt) / np.trapezoid(full, model.tt)
        assert kept > 1.0 - WINDOW_AREA_TOL
        assert y[:i0].sum() == 0.0 and y[i1:].sum() == 0.0


def test_a_window_holding_no_fitted_channel_is_refused_and_names_the_peak():
    """A dead column, said out loud at compile rather than at a missing esd.

    It is a refusal about *arithmetic*, not about expertise: a peak that is in
    range is never questioned however implausible, which is the whole stance of
    this WP.  The message names the component and quotes both ranges, in the
    `check_interval` sentence shape.
    """
    peak = make_peak(center=95.0, span=1.0, label="holder 110")
    with pytest.raises(ValueError, match=r"holder 110.*covers no fitted channel"):
        _peak_state(peak, lo=30.0, hi=50.0)

    # unlabelled, the dot-path is the name
    with pytest.raises(ValueError, match=r"extra_components\[0\]"):
        _peak_state(make_peak(center=95.0, span=1.0), lo=30.0, hi=50.0)


def test_a_model_declaring_no_peak_is_bit_identical_to_the_pre_member_one():
    """The empty default is exactly off, one member over.

    `extra_peak_curve` returns the additive identity and `evaluate` is
    unchanged to the bit — not approximately unchanged, because every golden in
    the suite would otherwise move for a feature nobody asked for.
    """
    structure = make_lab6()
    ins = _instrument()
    tt = np.arange(20.0, 60.0, 0.02)
    data = PatternData(two_theta=tt.tolist(),
                       intensity=np.full_like(tt, 50.0).tolist())
    table = ParameterTable(structure, ins)
    model = compile_model(structure, ins, data, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    values = table.decode(table.x0())
    assert model.peak_components == ()
    assert np.asarray(model.extra_peak_curve(values)).tobytes() == \
        np.zeros(len(tt)).tobytes()
    direct = (np.asarray(model.background(values))
              + np.asarray(model.bragg_component(values)))
    assert np.asarray(model.evaluate(values)).tobytes() == direct.tobytes()


def test_a_hump_and_a_peak_are_compiled_into_different_places():
    """The partition, asserted on the compiled model rather than on a curve.

    This is clause 2 reaching the thing that consumes it: `component_paths` is
    the background-landing list and `peak_components` the tick-landing one, and
    a member is sorted into them by its declared aggregate.  Before this WP the
    compile assumed every member was a hump and would have built
    `…1.position` for a peak that has no such field.
    """
    structure = make_lab6()
    ins = _instrument(peaks=[
        HumpComponent(position=Parameter(value=35.0, unit="deg")),
        make_peak(center=40.0),
    ])
    tt = np.arange(30.0, 50.0, 0.01)
    data = PatternData(two_theta=tt.tolist(),
                       intensity=np.zeros_like(tt).tolist())
    table = ParameterTable(structure, ins)
    model = compile_model(structure, ins, data, mode="rietveld",
                          moving_paths=set(table.moving_paths))

    assert model.component_paths == (
        ("instrument.extra_components.0.position",
         "instrument.extra_components.0.height",
         "instrument.extra_components.0.fwhm"),)
    assert len(model.peak_components) == 1
    assert model.peak_components[0].index == 1
    assert set(model.peak_components[0].paths.values()) == {
        f"instrument.extra_components.1.{n}" for n in PEAK_FIELDS}


# ----------------------------------------------------------------------
# ticks: a declared peak is not an unindexed impurity
# ----------------------------------------------------------------------


def _holder_fit(area=900.0, centre=43.55, *, declare=True, free=True,
                seed=0, lo=20.0, hi=90.0, step=0.02):
    """LaB6 with a synthetic holder doublet injected, refined with or without it.

    The truth pattern always contains the holder peak; ``declare`` controls
    whether the *fit* is told about it.  That pairing is the whole design case:
    the same data, once with the intruder modelled and once with it left to be
    absorbed by whatever is nearest.
    """
    rng = np.random.default_rng(seed)
    structure = make_lab6()
    structure.phases[0].scale.value = 3e-4
    ins = rx.Instrument.bragg_brentano(radiation="CuKa")
    ins.source.dispersion = None
    ins.profile.w.value = 3e-3
    ins.profile.x.value = 5e-3

    tt = np.arange(lo, hi, step)
    blank = PatternData(two_theta=tt.tolist(),
                        intensity=np.zeros_like(tt).tolist())

    truth = make_peak(center=centre, span=0.55, area=area)
    truth.fwhm.value = 0.18
    ins_t = ins.model_copy(deep=True)
    ins_t.extra_components = [truth]
    tab_t = ParameterTable(structure, ins_t)
    m_t = compile_model(structure, ins_t, blank, mode="rietveld",
                        moving_paths=set(tab_t.moving_paths))
    y = np.asarray(m_t.evaluate(tab_t.decode(tab_t.x0()))) + 40.0
    data = PatternData(two_theta=tt.tolist(),
                       intensity=rng.poisson(np.maximum(y, 0.1)).astype(float).tolist())

    ins_fit = ins.model_copy(deep=True)
    stages = [StageSpec(name="scale_bkg",
                        turn_on=["phases.*.scale", "instrument.background.*"])]
    if declare:
        pk = make_peak(center=centre - 0.05, span=0.55, area=area * 0.55)
        pk.fwhm.value = 0.15
        ins_fit.extra_components = [pk]
        if free:
            stages.append(StageSpec(name="holder",
                                    turn_on=["instrument.extra_components.*"]))
    stages.append(StageSpec(name="cell", turn_on=["phases.*.cell.*",
                                                  "instrument.zero_shift"]))
    stages.append(StageSpec(name="profile", turn_on=["instrument.profile.w",
                                                     "instrument.profile.x"]))
    ref = rx.Refinement(structure.model_copy(deep=True), ins_fit, history=False)
    return ref.fit(data, plan=PlanSpec(stages=stages)), truth


def test_declared_peaks_reach_the_tick_list_under_one_reserved_key():
    """Clause 2's destination, end to end.

    Layer 0 reads `ticks` to decide what is unindexed, so a declared peak that
    is not in it is reported as an impurity by a fit that put intensity there
    on purpose — the Kα2-ticks bug one member over.  Every emission line's
    image is listed, for exactly that reason.
    """
    result, _truth = _holder_fit()
    assert EXTRA_TICK_KEY in result.ticks
    assert "LaB6" in result.ticks
    extra = result.ticks[EXTRA_TICK_KEY]
    assert len(extra) == 2                      # Kα1 and its Kα2 image
    assert extra == sorted(extra)
    assert extra[1] > extra[0]


def test_a_joint_fit_writes_the_same_reserved_key_as_a_single_one():
    """The tick list has two builders, and both owe clause 2's destination.

    `multi.MultiHistogramRefinement._ticks` is the joint fit's own tick
    builder, so a declared peak missing from it is reported as an unindexed
    impurity by every histogram's Layer 0 — the identical failure the test
    above pins for a single histogram, on the surface that does not share its
    code path.  Both now read `CompiledModel.extra_peak_tick_positions`, which
    is why they cannot disagree about where the images fall.
    """
    from rietx.multi import MultiHistogramRefinement

    structure = make_lab6()
    ins = _instrument(peaks=[make_peak(center=40.0)])
    ins.extra_components[0].area.value = 500.0
    tt = np.arange(30.0, 50.0, 0.01)
    data = PatternData(two_theta=tt.tolist(),
                       intensity=np.zeros_like(tt).tolist())
    table = ParameterTable(structure, ins)
    model = compile_model(structure, ins, data, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    values = table.decode(table.x0())

    ticks, tick_hkl, tick_support = MultiHistogramRefinement._ticks(
        None, model, structure, values)
    assert EXTRA_TICK_KEY in ticks
    assert ticks[EXTRA_TICK_KEY] == model.extra_peak_tick_positions(values)
    assert "LaB6" in ticks
    # a peak declared by centre has no Miller index, so it gets no row at all
    # rather than an empty one, which would claim it had none of its own
    # (WP-1438). The phase beside it does, one per tick.
    assert EXTRA_TICK_KEY not in tick_hkl
    assert len(tick_hkl["LaB6"]) == len(ticks["LaB6"])
    # support rides beside every row, the declared peak's included, paired by
    # index as the single fit's is (WP-1344: the low-angle boundary reads it)
    assert {k: len(v) for k, v in tick_support.items()} == {
        k: len(v) for k, v in ticks.items()}

    # and nothing appears for a model that declares no peak
    plain = _instrument()
    plain_table = ParameterTable(structure, plain)
    plain_model = compile_model(structure, plain, data, mode="rietveld",
                                moving_paths=set(plain_table.moving_paths))
    assert EXTRA_TICK_KEY not in MultiHistogramRefinement._ticks(
        None, plain_model, structure, plain_table.decode(plain_table.x0()))[0]


def test_a_phase_named_like_the_reserved_key_is_refused():
    """A tick list is read by name, so the collision loses a whole phase.

    Refused rather than renamed — the name is the caller's — and only when a
    peak is actually declared, so no existing model starts failing for a name
    it has always had.
    """
    structure = make_lab6()
    structure.phases[0].name = EXTRA_TICK_KEY
    tt = np.arange(30.0, 50.0, 0.01)
    data = PatternData(two_theta=tt.tolist(),
                       intensity=np.zeros_like(tt).tolist())

    clean = _instrument()
    table = ParameterTable(structure, clean)
    compile_model(structure, clean, data, mode="rietveld",
                  moving_paths=set(table.moving_paths))   # no peak: allowed

    ins = _instrument(peaks=[make_peak(center=40.0)])
    table = ParameterTable(structure, ins)
    with pytest.raises(ValueError, match=r"collides with the reserved"):
        compile_model(structure, ins, data, mode="rietveld",
                      moving_paths=set(table.moving_paths))


def test_a_declared_holder_peak_is_refined_back_to_the_truth():
    """The design case, measured rather than asserted.

    Every parameter of the injected doublet comes back within a few esds, which
    is what makes the *rest* of this WP's claims worth anything: an evidence
    channel over a peak the fit cannot find would report nothing useful.
    """
    result, truth = _holder_fit()
    got = {p.path.rsplit(".", 1)[1]: p for p in result.parameters
           if "extra_components" in p.path}
    assert set(got) == set(PEAK_FIELDS)
    for name, expected in (("center", truth.center.value),
                           ("area", truth.area.value),
                           ("fwhm", truth.fwhm.value)):
        row = got[name]
        assert row.stderr is not None and row.stderr > 0.0, name
        assert abs(row.value - expected) < 4.0 * row.stderr, (
            name, row.value, expected, row.stderr)


def test_a_declared_peak_is_not_in_the_reported_background():
    """`y_background` is what a reader sees drawn as background.

    A hump belongs there; a holder reflection does not, and putting it there
    would make the plot claim the intruder was diffuse scattering.
    """
    result, _truth = _holder_fit()
    assert float(np.max(result.y_background)) < 60.0     # the flat 40 counts


# ----------------------------------------------------------------------
# Le Bail / Pawley: the subtraction side, never the denominator
# ----------------------------------------------------------------------


def _lebail_extraction(peak=None, *, cycles=6, lo=20.0, hi=90.0, step=0.02):
    """Extracted per-hkl intensities for a LaB6 pattern, with or without a peak.

    Returns the extracted intensity vector so two runs can be compared.  The
    *data* is the same in both calls; what changes is whether the model knows
    about the intruder sitting on top of it.
    """
    structure = make_lab6()
    structure.phases[0].scale.value = 3e-4
    ins = _instrument()
    tt = np.arange(lo, hi, step)
    blank = PatternData(two_theta=tt.tolist(),
                        intensity=np.zeros_like(tt).tolist())
    return structure, ins, tt, blank


def test_a_declared_peak_leaves_extracted_intensities_unbiased():
    """Clause 3: the component joins the *net*, not the denominator.

    A holder line sitting on a reflection is counts that are not the phase's.
    Subtracted from the net, the phase keeps its own intensity; left in, the
    partition hands the phase a share of the holder — and it does so silently,
    because the extracted intensity has no independent truth to check against.

    So the test compares against the extraction from a pattern that never had
    the intruder: declaring the peak must recover *that* answer, not merely
    change the answer.
    """
    structure, ins, tt, blank = _lebail_extraction()

    # clean truth
    table_c = ParameterTable(structure, ins)
    m_c = compile_model(structure, ins, blank, mode="rietveld",
                        moving_paths=set(table_c.moving_paths))
    y_clean = np.asarray(m_c.evaluate(table_c.decode(table_c.x0()))) + 40.0

    # the same pattern with a holder line dropped **onto a strong reflection**,
    # which is the only placement that tests anything: an intruder in empty
    # background is subtracted by the background block whatever the net does.
    strongest = float(tt[int(np.argmax(y_clean))])
    intruder = make_peak(center=strongest, span=0.5, area=400.0)

    ins_t = ins.model_copy(deep=True)
    ins_t.extra_components = [intruder]
    tab_t = ParameterTable(structure, ins_t)
    m_t = compile_model(structure, ins_t, blank, mode="rietveld",
                        moving_paths=set(tab_t.moving_paths))
    y_dirty = np.asarray(m_t.evaluate(tab_t.decode(tab_t.x0()))) + 40.0

    def extract(y, instrument):
        data = PatternData(two_theta=tt.tolist(), intensity=y.tolist())
        table = ParameterTable(structure, instrument)
        model = compile_model(structure, instrument, data, mode="lebail",
                              moving_paths=set(table.moving_paths))
        values = table.decode(table.x0())
        model.lebail_update(values, n_cycles=8)
        return np.asarray(model.phases[0].hkl_intensity, dtype=np.float64)

    clean = extract(y_clean, ins)
    declared = extract(y_dirty, ins_t)      # intruder present AND declared
    ignored = extract(y_dirty, ins)         # intruder present, NOT declared

    scale = np.maximum(clean, clean.max() * 1e-6)
    err_declared = np.abs(declared - clean) / scale
    err_ignored = np.abs(ignored - clean) / scale

    # Declaring it recovers the clean extraction to machine precision — the
    # injected curve *is* the model's own, so subtracting it from the net
    # restores the clean net bit for bit, which is the strongest form this
    # claim can take.  Ignoring it inflates the worst reflection 160.9 -> 547.2
    # (measured, this fixture): the phase is handed the holder's counts and
    # nothing says so, because an extracted intensity has no independent truth
    # to be checked against.
    assert err_declared.max() < 1e-9
    assert err_ignored.max() > 2.0


def test_peak_component_paths_stay_refinable_under_lebail_and_pawley():
    """The reason the intensity field is not called `scale`.

    `mode_fixed_path` force-fixes every `*.scale`, every `.atoms.` path and
    every `.source.lines.` path under Le Bail and Pawley — and a declared peak
    has to keep refining there, because Le Bail is exactly where a caller
    reaches for a holder they cannot index.
    """
    structure = make_lab6()
    ins = _instrument(peaks=[make_peak(center=40.0)])
    tt = np.arange(30.0, 50.0, 0.01)
    data = PatternData(two_theta=tt.tolist(),
                       intensity=np.full_like(tt, 50.0).tolist())

    from rietx.refine import mode_fixed_path

    for mode in ("lebail", "pawley"):
        table = ParameterTable(structure, ins)
        table.set_vary(["instrument.extra_components.*"], True)
        freed = {p for p in table.free_paths if "extra_components" in p}
        assert freed == {f"instrument.extra_components.0.{n}"
                         for n in PEAK_FIELDS}, mode
        assert not any(mode_fixed_path(p, mode) for p in freed), mode
        compile_model(structure, ins, data, mode=mode,
                      moving_paths=set(table.moving_paths))


def test_both_partition_nets_subtract_the_same_curve():
    """Le Bail and Pawley must not partition one pattern two ways.

    Two call sites, one subtraction: the test reads the net each builds rather
    than trusting that both were edited, which is the failure clause 4 names
    one layer down (a change made in one of a pair).
    """
    structure = make_lab6()
    structure.phases[0].scale.value = 3e-4
    ins = _instrument(peaks=[make_peak(center=40.0, area=500.0)])
    tt = np.arange(30.0, 50.0, 0.01)
    data = PatternData(two_theta=tt.tolist(),
                       intensity=np.full_like(tt, 500.0).tolist())

    table = ParameterTable(structure, ins)
    model = compile_model(structure, ins, data, mode="lebail",
                          moving_paths=set(table.moving_paths))
    values = table.decode(table.x0())
    curve = np.asarray(model.extra_peak_curve(values))
    assert curve.max() > 0.0

    net = np.maximum(np.asarray(model.y_obs) - np.asarray(model.background(values))
                     - curve, 0.0)
    assert net.min() >= 0.0
    # the curve is genuinely taken out of the net where the peak is
    apex = int(np.argmax(curve))
    assert net[apex] < float(np.asarray(model.y_obs)[apex])


# ----------------------------------------------------------------------
# the Jacobian: the FD fallback is declared, not discovered
# ----------------------------------------------------------------------


@pytest.mark.parametrize("name", PEAK_FIELDS)
def test_no_analytic_branch_claims_a_peak_component_path(name):
    """WP-1070's failure mode: a branch that claims a path it does not reach.

    `_make_jacobian` dispatches on the free path's *name*, and a branch that
    answers for a path it was not written for returns a column that is wrong
    rather than absent.  The hump's version of this test one member over; the
    peak needs its own because its four names are different names.
    """
    structure = make_lab6()
    ins = _instrument(peaks=[make_peak(center=40.0, area=300.0)])
    tt = np.arange(30.0, 50.0, 0.01)
    data = PatternData(two_theta=tt.tolist(),
                       intensity=np.full_like(tt, 50.0).tolist())
    table = ParameterTable(structure, ins)
    model = compile_model(structure, ins, data, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    path = f"instrument.extra_components.0.{name}"
    assert model.scalar_chain_supported(path) is False


def test_peak_component_paths_never_join_the_linear_background_block():
    """`bkg_paths` is a block whose columns are claimed *exact* design rows.

    A declared peak is nonlinear in its centre, width and mixing, so a path of
    its in that tuple would take the "y is linear in this coefficient" branch
    and get a silently wrong column — the hump's reason, and it applies to this
    member with one more nonlinear parameter.
    """
    structure = make_lab6()
    ins = _instrument(peaks=[make_peak(center=40.0, area=300.0)],
                      background=BackgroundChebyshev.with_terms(5))
    tt = np.arange(30.0, 50.0, 0.01)
    data = PatternData(two_theta=tt.tolist(),
                       intensity=np.full_like(tt, 50.0).tolist())
    table = ParameterTable(structure, ins)
    model = compile_model(structure, ins, data, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    peak_paths = {f"instrument.extra_components.0.{n}" for n in PEAK_FIELDS}
    assert set(model.bkg_paths).isdisjoint(peak_paths)
    assert model.component_paths == ()          # it is not a hump either


# ----------------------------------------------------------------------
# evidence: recommend, never refuse
# ----------------------------------------------------------------------


def _clean_lab6(seed=1, lo=20.0, hi=90.0, step=0.02, boost_at=None,
                boost_frac=0.35):
    """A LaB6 pattern the model can fit exactly, optionally with one line boosted.

    ``boost_at`` adds intensity to a single reflection that no parameter of the
    model can produce, which is the state a caller reaches for a declared peak
    in as a *shortcut* — the use `EXTRA_PEAK_ON_REFLECTION` exists to name.
    """
    rng = np.random.default_rng(seed)
    structure = make_lab6()
    structure.phases[0].scale.value = 3e-4
    ins = rx.Instrument.bragg_brentano(radiation="CuKa")
    ins.source.dispersion = None
    ins.profile.w.value = 3e-3
    ins.profile.x.value = 5e-3
    tt = np.arange(lo, hi, step)
    blank = PatternData(two_theta=tt.tolist(),
                        intensity=np.zeros_like(tt).tolist())
    table = ParameterTable(structure, ins)
    model = compile_model(structure, ins, blank, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    y = np.asarray(model.evaluate(table.decode(table.x0()))) + 40.0
    strongest = float(tt[int(np.argmax(y))])
    if boost_at is not None:
        y = y + boost_frac * y.max() * np.exp(-((tt - boost_at) / 0.08) ** 2)
    data = PatternData(
        two_theta=tt.tolist(),
        intensity=rng.poisson(np.maximum(y, 0.1)).astype(float).tolist())
    return structure, ins, data, strongest


def _fit_with_peak(structure, ins, data, peak, turn_on):
    ins_fit = ins.model_copy(deep=True)
    ins_fit.extra_components = [peak]
    ref = rx.Refinement(structure.model_copy(deep=True), ins_fit, history=False)
    return ref.fit(data, plan=PlanSpec(stages=[
        StageSpec(name="scale_bkg",
                  turn_on=["phases.*.scale", "instrument.background.*"]),
        StageSpec(name="component", turn_on=list(turn_on))]))


def test_a_declared_peak_the_data_cannot_see_says_so():
    """The honest evidence for "not needed", and it is not an Rwp comparison.

    A peak reaches the pattern only through `area × profile`, so at zero area
    nothing constrains its centre either — WP-1110 item 13's zero-scale phase,
    one rank down.  The area's own esd is *absent*, which is the equilibrated
    covariance telling the truth; the diagnostic is what makes that legible
    without a reader knowing to look for a missing number.
    """
    structure, ins, data, _strong = _clean_lab6()
    peak = make_peak(center=43.5, span=0.5, area=0.0)
    result = _fit_with_peak(structure, ins, data, peak,
                            ["instrument.extra_components.*"])

    codes = [d.code for d in result.diagnostics]
    assert "EXTRA_PEAK_NO_INTENSITY" in codes
    assert "EXTRA_PEAK_ON_REFLECTION" not in codes

    fired = next(d for d in result.diagnostics
                 if d.code == "EXTRA_PEAK_NO_INTENSITY")
    assert any(p.endswith(".center") for p in fired.where)
    assert any(p.endswith(".area") for p in fired.where)

    area = next(p for p in result.parameters if p.path.endswith(".area"))
    assert area.stderr is None                    # unmeasured, not precise


def test_a_declared_peak_on_a_predicted_line_is_named_as_a_degeneracy():
    """The impurity-shortcut use, reported and never refused.

    It may be exactly right — a holder line overlapping a sample peak is the
    design case — so the finding is about *interpretation*: two terms describe
    one peak and nothing in Rwp says which owns the counts.
    """
    _s, _i, _d, strong = _clean_lab6()          # where the strongest line is
    structure2, ins2, data2, _ = _clean_lab6(seed=1, boost_at=strong)

    peak = make_peak(center=strong, span=0.5, area=50.0)
    result = _fit_with_peak(structure2, ins2, data2, peak,
                            ["instrument.extra_components.0.area",
                             "instrument.extra_components.0.fwhm"])

    fired = [d for d in result.diagnostics
             if d.code == "EXTRA_PEAK_ON_REFLECTION"]
    assert len(fired) == 1
    assert "degeneracy" in fired[0].message
    assert fired[0].level == "warning"
    assert any(p.endswith(".center") for p in fired[0].where)
    # reported, never refused: the fit completed and carries an answer
    assert result.status == "converged"
    area = next(p for p in result.parameters if p.path.endswith(".area"))
    assert area.value > 0.0


def test_the_match_tolerance_is_layer_zeros_own_constant():
    """Two consumers of one question must not answer it with two numbers.

    A component inside Layer 0's tolerance is a component Layer 0 would have
    matched to that reflection, so the diagnostic has to use Layer 0's number
    and not a second one that happens to be similar.
    """
    import inspect

    from rietx.report.layer0 import LAYER0_MATCH_TOL_DEG, build_layer0

    assert LAYER0_MATCH_TOL_DEG == 0.08
    sig = inspect.signature(build_layer0)
    assert sig.parameters["match_tol_deg"].default == LAYER0_MATCH_TOL_DEG


def test_the_evidence_channel_never_refuses_a_declared_peak():
    """The WP's stance, asserted rather than assumed.

    Every path that could have become a gate is a `Diagnostic` instead: the
    fit converges, the parameters come back, and the findings are advice.  The
    only refusals this member has are about arithmetic — a window with no
    channels in it, and a phase name collision — both of which are tested
    elsewhere and neither of which is about whether the peak is plausible.
    """
    structure, ins, data, strong = _clean_lab6(seed=1, boost_at=None)
    peak = make_peak(center=strong, span=0.5, area=50.0)
    result = _fit_with_peak(structure, ins, data, peak,
                            ["instrument.extra_components.*"])
    assert result.status in ("converged", "max_iter")
    assert any("extra_components" in p.path for p in result.parameters)
    for d in result.diagnostics:
        assert d.level in ("info", "warning")     # never an error


def test_the_peak_absorption_statistic_separates_the_three_cases():
    """The measurement that decided no threshold ships (WP-1103).

    Three arms on one fixture: a declared peak in empty background that the
    data cannot see; the design case, a real overlapping intruder away from any
    line; and the parasitic case, a peak sitting on a reflection and absorbing
    misfit the model should have carried.

    Measured R² of the worst structural column on the peak's span:

        healthy (nothing there)      0.0000
        design case (real intruder)  0.0004
        parasitic (on a reflection)  0.2099

    The separation is real — three orders of magnitude — and it is still **not
    enough to ship a threshold on**: three arms of one synthetic fixture, one
    phase, one component.  The background guard's 0.25 was measured across real
    cases, and borrowing it here would not even have fired on the parasitic arm
    (0.2099 < 0.25), which is the concrete argument against copying a number
    across a seam because the statistic is the same.  So the table is reported
    and the *positional* test carries the verdict.

    This test pins the ordering rather than the numbers, so a change that
    inverts the evidence fails while one that moves it does not.
    """
    def worst(result):
        table = (dict(result.identifiability.extra_peak_absorption)
                 if result.identifiability else {})
        return max(table.values()) if table else None

    structure, ins, data, strong = _clean_lab6()
    free = ["instrument.extra_components.0.area",
            "instrument.extra_components.0.fwhm", "phases.*.atoms.*.biso"]

    healthy = worst(_fit_with_peak(structure, ins, data,
                                   make_peak(center=43.5, span=0.5, area=200.0),
                                   free))
    s2, i2, d2, _ = _clean_lab6(seed=1, boost_at=strong)
    parasitic = worst(_fit_with_peak(s2, i2, d2,
                                     make_peak(center=strong, span=0.5,
                                               area=200.0), free))

    assert healthy is not None and parasitic is not None
    assert healthy < 0.01
    assert parasitic > 20 * max(healthy, 1e-6)
    # and the borrowed background threshold would have missed it
    assert parasitic < BACKGROUND_ABSORPTION_GUARD


def test_the_two_declared_counts_split_when_the_members_do():
    """`n_extra_components` is the list; `n_background_components` is the humps.

    They were one number while a hump was the only member, and the field that
    consumes the second — `BackgroundEvidence.n_peaks`, which a reader uses to
    judge how flexible the background was allowed to be — went on reading the
    first.  Nothing caught it: every existing test declares humps only, where
    the two agree.  A declared sharp peak is freedom the caller granted, but it
    is not *background* freedom, and counting it as such overstates exactly
    what the absorption table beside it measures.
    """
    from rietx.report import build_report

    structure = make_lab6()
    structure.phases[0].scale.value = 3e-4
    ins = _instrument(peaks=[
        HumpComponent(position=Parameter(value=35.0, unit="deg")),
        make_peak(center=40.0, area=300.0),
        make_peak(center=45.0, area=300.0),
    ])
    tt = np.arange(15.0, 60.0, 0.05)
    data = PatternData(two_theta=tt.tolist(),
                       intensity=np.full_like(tt, 200.0).tolist())

    ref = rx.Refinement(structure, ins)
    result = ref.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage(name="bkg", turn_on=["instrument.background.*"], max_iter=2)]))

    assert result.n_extra_components == 3          # the list
    assert result.n_background_components == 1     # the humps
    assert build_report(result).background.n_peaks == 1

    # and a replayed node carries both, being declarations rather than
    # measurements — the reason the first one lives on the result at all
    replayed = rx.replay(ref.history, result.node_id, data)
    assert replayed.n_extra_components == 3
    assert replayed.n_background_components == 1


def test_the_counts_agree_when_only_humps_are_declared():
    """The pre-1103 case, pinned so the split cannot drift into it.

    Every v1.2-era caller declares humps alone, and for them the two numbers
    are the same number — which is why nothing noticed when one of them
    silently became the other.
    """
    structure = make_lab6()
    structure.phases[0].scale.value = 3e-4
    ins = _instrument(peaks=(_peak(vary=False), _peak(position=70.0,
                                                      vary=False)))
    tt = np.arange(15.0, 60.0, 0.05)
    data = PatternData(two_theta=tt.tolist(),
                       intensity=np.full_like(tt, 200.0).tolist())
    ref = rx.Refinement(structure, ins)
    result = ref.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage(name="bkg", turn_on=["instrument.background.*"], max_iter=2)]))

    assert result.n_extra_components == 2
    assert result.n_background_components == result.n_extra_components


def test_a_declared_peak_unclaims_the_two_instrument_paths_it_widens():
    """The WP-1070 invariant, which this member breaks in a new place.

    `extra_peak_curve` scales every non-primary image by
    `weight_l · Lp(2θ_l)/Lp(2θ_0)`, so with a peak compiled,
    `instrument.polarization` and each line `weight` move counts that no
    per-peak scalar chain evaluates.  An analytic branch claiming them returns
    the column **short** rather than raising — the failure mode that rule
    exists for — and the shortfall is the whole peak.

    Conditioned on a peak actually being compiled, so a model without one keeps
    the analytic column it has always had; both halves are asserted, because
    unclaiming the paths unconditionally would cost every ordinary fit its
    analytic polarization column.
    """
    structure = make_lab6()
    structure.phases[0].scale.value = 3e-4
    tt = np.arange(35.0, 45.0, 0.01)
    data = PatternData(two_theta=tt.tolist(),
                       intensity=np.full_like(tt, 50.0).tolist())
    widened = ("instrument.polarization", "instrument.source.lines.1.weight")

    def build(peaks):
        # a two-line source, because the widening *is* the Kalpha2 image: on a
        # single-line source there is no ratio to take and the curve does not
        # depend on either path.  The guard is deliberately blunter than that —
        # it fires whenever a peak is compiled — which costs a single-line
        # instrument an analytic column it would not have missed.  That is a
        # cheap trade (polarization is rarely freed and line 0's weight is
        # structurally locked) against a condition that could go stale.
        ins = rx.Instrument.bragg_brentano(radiation="CuKa")
        ins.source.dispersion = None
        ins.extra_components = list(peaks)
        table = ParameterTable(structure, ins)
        return table, compile_model(structure, ins, data, mode="rietveld",
                                    moving_paths=set(table.moving_paths))

    # without a peak: still claimed, as before this member existed
    _t, plain = build(())
    for path in widened:
        assert plain.scalar_chain_supported(path) is True, path

    # with one: unclaimed, and the curve really does move with both
    table, model = build([make_peak(center=40.0, span=0.4, area=500.0)])
    values = table.decode(table.x0())
    base = np.asarray(model.extra_peak_curve(values))
    for path in widened:
        assert model.scalar_chain_supported(path) is False, path
        bumped = dict(values)
        bumped[path] = values[path] + 1e-6
        moved = np.abs(np.asarray(model.extra_peak_curve(bumped)) - base).max()
        assert moved > 0.0, path


def test_an_inert_declaration_is_not_reported_as_having_refined_to_nothing():
    """`EXTRA_PEAK_NO_INTENSITY` is about what the *fit* did.

    A declared peak's area defaults to 0 and stays there unless a stage frees
    it, which is the ordinary case — declare now, free later, or never.  Firing
    there would warn about a refinement that never happened, on the most common
    state this member is in.
    """
    structure = make_lab6()
    structure.phases[0].scale.value = 3e-4
    ins = _instrument(peaks=[make_peak(center=40.0, span=0.4)])
    tt = np.arange(15.0, 60.0, 0.05)
    data = PatternData(two_theta=tt.tolist(),
                       intensity=np.full_like(tt, 200.0).tolist())
    ref = rx.Refinement(structure, ins, history=False)
    result = ref.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage(name="bkg", turn_on=["instrument.background.*"], max_iter=2)]))

    assert not [d for d in result.diagnostics
                if d.code.startswith("EXTRA_PEAK")]


def test_the_cif_background_description_counts_humps_only():
    """A deposited file must not claim flexibility the fit never granted.

    The same miscount as `n_extra_components`, in a third place and with a
    worse consequence: this sentence goes into the CIF a reader deposits.
    """
    from rietx.io.exporters import _background_description

    hump_only = _instrument(peaks=[
        HumpComponent(position=Parameter(value=35.0, unit="deg"))])
    assert "1 explicit Gaussian background peak" in \
        _background_description(hump_only)

    with_peak = _instrument(peaks=[
        HumpComponent(position=Parameter(value=35.0, unit="deg")),
        make_peak(center=40.0),
    ])
    assert "1 explicit Gaussian background peak" in \
        _background_description(with_peak)
    assert "2 explicit" not in _background_description(with_peak)

    peak_only = _instrument(peaks=[make_peak(center=40.0)])
    assert "explicit Gaussian background peak" not in \
        _background_description(peak_only)


def test_a_pre_v1_4_result_keeps_its_background_count_when_reopened():
    """Before v1.4 every declared component *was* background.

    A stored result carries only `n_extra_components`, so without the
    migration `report.background.n_peaks` comes back `None` — "nothing
    counted" — about a document that counted it perfectly well.
    """
    from rietx.schemas.results import RefinementResult

    doc = {"mode": "rietveld", "status": "converged",
           "provenance": {"package_version": "1.3.0"},
           "two_theta": [10.0], "y_obs": [1.0], "y_calc": [1.0],
           "parameters": [],
           "statistics": {"rwp": 1.0, "rp": 1.0, "rexp": 1.0, "chi2": 1.0,
                          "gof": 1.0, "n_points": 1, "n_free_parameters": 0},
           "n_extra_components": 2}
    reopened = RefinementResult.model_validate(doc)
    assert reopened.n_extra_components == 2
    assert reopened.n_background_components == 2

    # a v1.4 writer states both, so the migration never overrides a real answer
    doc_14 = dict(doc, n_extra_components=3, n_background_components=1)
    assert RefinementResult.model_validate(doc_14).n_background_components == 1
