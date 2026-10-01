"""A time-of-flight bank through the engine: table, result, solver, ``fit``.

The rung above :mod:`tests.test_forward_tof`, which proved the forward model
against a scratch least-squares harness.  What is checked here is that the
*engine* owns the fit — ``ParameterTable`` registers and writes back the bank's
calibration, ``run_least_squares`` takes the finite-difference path,
``Refinement.fit`` routes to :func:`~rietx.model.forward_tof.compile_tof_model`
and the :class:`~rietx.schemas.results.RefinementResult` that comes back says
which abscissa it holds.

**Every fixture is synthetic and written here.**  No line of any real
instrument file enters this repository; the bank below is a plausible 90°
detector with round constants, and the pattern is generated from the model it
is then refined against.

The constant-wavelength arm must not move by one bit while any of this lands,
which is what :func:`test_a_constant_wavelength_table_is_unchanged` pins at the
table and the shipped acceptance suites pin at the fit.
"""

from __future__ import annotations

import hashlib
import math

import numpy as np
import pytest

import rietx as rx
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter as P
from rietx.schemas.instrument import (
    BackgroundChebyshev,
    BackgroundPSpline,
    EmissionLine,
    Geometry,
    HumpComponent,
    Instrument,
    ProfileTOF,
    RoughnessSuortti,
    Source,
)
from rietx.schemas.pattern import TOF_NOT_EVALUATED, PatternData
from rietx.schemas.structure import (
    Atom,
    Cell,
    Phase,
    PreferredOrientation,
    StephensStrain,
    Structure,
)

# ----------------------------------------------------------------------
# the synthetic bank
# ----------------------------------------------------------------------
#: The generating cell.  Silicon's, near enough to be recognisable and not
#: taken from any certificate: nothing here is compared against one.
A_GEN = 5.4311946
#: The bank: DIFC 12000 µs/Å at 2θ = 90°, TZERO −5 µs, no DIFA and no DIFB.
DIFC_GEN, TZERO_GEN = 12000.0, -5.0
#: The generating profile — GSAS type 1 (all γ zero): α = 0.45/d, β = 0.055 +
#: 0.003/d⁴, σ² = 300·d².  The same shape ``test_forward_tof`` generates.
PROFILE_GEN = dict(alpha1=0.45, beta0=0.055, beta1=0.003, sig1=300.0)
#: 8000-45000 µs in 5 µs channels — d = 0.67-3.75 Å on this bank.  The step is
#: what makes the pattern well sampled: at 10 µs the median is 3.5 channels
#: across the FWHM and ``PATTERN_UNDERSAMPLED`` fires, which is a true
#: statement about the fixture and a distraction from what it is for.
TOF_LO, TOF_HI, TOF_STEP = 8000.0, 45000.0, 5.0


def silicon(a: float = A_GEN) -> Structure:
    """Si, Fd-3m:2, one atom on 8a — no free coordinate, one Biso."""
    return Structure(phases=[Phase(
        name="Si", space_group="F d -3 m :2",
        cell=Cell(a=P(value=a), b=P(value=a), c=P(value=a),
                  alpha=P(value=90.0), beta=P(value=90.0),
                  gamma=P(value=90.0)),
        scale=P(value=1.0, min=0.0),
        atoms=[Atom(label="Si", species="Si", x=P(value=0.125),
                    y=P(value=0.125), z=P(value=0.125),
                    biso=P(value=0.5, min=0.0, max=5.0))])])


def bank(*, difc: float = DIFC_GEN, tzero: float = TZERO_GEN,
         n_background: int = 4, **profile) -> Instrument:
    """The synthetic 90° bank, with a Chebyshev background."""
    coeffs = dict(PROFILE_GEN)
    coeffs.update(profile)
    ins = rx.Instrument.tof_neutron_bank(
        difc=difc, tzero=tzero, two_theta_bank_deg=90.0,
        profile=ProfileTOF(**{k: P(value=v, unit=None)
                              for k, v in coeffs.items()}))
    ins.background = BackgroundChebyshev(
        coefficients=[P(value=0.0) for _ in range(n_background)])
    return ins


# ----------------------------------------------------------------------
# 1. the parameter table
# ----------------------------------------------------------------------
#: Every path a ``neutron_tof`` table must carry for the forward model to be
#: able to read its own values — spelled here rather than derived, because the
#: point of the assertion is that these are the strings
#: ``CompiledTOFModel.calibration`` and ``.shape_parameters`` index ``values``
#: with.  A rename that kept both sides in step would pass a derived check and
#: fail this one, which is the direction that matters: the paths are a contract
#: with the plans a user writes.
TOF_PATHS = (
    "instrument.source.difc", "instrument.source.difa",
    "instrument.source.tzero", "instrument.source.difb",
    "instrument.source.profile_tof.alpha0",
    "instrument.source.profile_tof.alpha1",
    "instrument.source.profile_tof.beta0",
    "instrument.source.profile_tof.beta1",
    "instrument.source.profile_tof.sig0",
    "instrument.source.profile_tof.sig1",
    "instrument.source.profile_tof.sig2",
    "instrument.source.profile_tof.gam0",
    "instrument.source.profile_tof.gam1",
    "instrument.source.profile_tof.gam2",
)

#: What a time-of-flight forward branch cannot read, and must therefore find
#: **force-fixed** rather than merely unfree (WP-1073).  Caglioti is a
#: polynomial in tan θ, ``zero_shift`` is an offset in degrees and the four
#: aberrations are all shifts in deg 2θ — the flight-time counterparts of all
#: of them live in ``ProfileTOF`` and in the bank calibration.
#:
#: The four **phase** widths were on this list until T-3c and are not any more:
#: a crystallite size and a microstrain broaden a bank's peaks too, so the
#: branch reads all four and they are refinable on both arms
#: (``test_the_sample_widths_are_no_longer_locked_on_a_bank`` below).
TOF_LOCKED = (
    "instrument.geometry.axial_sl", "instrument.geometry.axial_hl",
    "instrument.geometry.capillary_offset_along_beam",
    "instrument.geometry.capillary_offset_across_beam",
)

#: The four the same table must now find **free-able** — T-3c's half of the
#: rule above.  Kept beside ``TOF_LOCKED`` so the two lists cannot drift.
TOF_SAMPLE_WIDTHS = (
    "phases.0.lor_size", "phases.0.lor_strain",
    "phases.0.gauss_size", "phases.0.gauss_strain",
)


def test_a_tof_table_registers_the_bank_calibration_and_profile():
    table = ParameterTable(silicon(), bank())
    paths = {e.path for e in table.entries}
    assert set(TOF_PATHS) <= paths
    # …and none of the constant-wavelength source's rows, which the source does
    # not carry at all: a white beam has no line list.
    assert not [p for p in paths if p.startswith("instrument.source.lines.")]


def test_the_calibration_is_fixed_by_default_but_not_locked():
    """A DIFC is a calibration, so it starts held — and freeing it against a
    *held* certified cell is exactly how a bank is calibrated, so it must not
    be ``locked``.  The same distinction line 0's wavelength draws."""
    table = ParameterTable(silicon(), bank())
    for e in table.entries:
        if e.path in TOF_PATHS:
            assert not e.vary, e.path
            assert not e.locked, e.path
    freed = ParameterTable(silicon(), bank())
    freed.set_vary(["instrument.source.difc"], True)
    assert "instrument.source.difc" in freed.free_paths


def test_what_the_tof_branch_cannot_read_is_force_fixed():
    """The WP-1073 rule.  Merely unfree would let any glob hand the solver a
    dead column — a parameter it moves and the forward model never reads."""
    table = ParameterTable(silicon(), bank())
    by_path = {e.path: e for e in table.entries}
    for path in TOF_LOCKED:
        assert by_path[path].locked, path
        assert not by_path[path].vary, path
    # a glob cannot free them, which is the property `locked` exists for
    table.set_vary(["instrument.geometry.*", "phases.*.lor_*",
                    "phases.*.gauss_*"], True)
    assert not (set(TOF_LOCKED) & set(table.free_paths))
    # and the constant-wavelength rows whose part a bank plays under its own
    # names are not rows at all (#442), so a glob naming them matches nothing
    from rietx.params.vector import BANK_ABSENT_PATHS

    assert not (set(BANK_ABSENT_PATHS) & set(by_path))


def test_the_sample_widths_are_no_longer_locked_on_a_bank():
    """T-3c: the specimen's size and strain broaden a bank's peaks, so the
    four phase widths are refinable there — the same glob that must not reach
    ``TOF_LOCKED`` must reach these."""
    table = ParameterTable(silicon(), bank())
    by_path = {e.path: e for e in table.entries}
    for path in TOF_SAMPLE_WIDTHS:
        assert not by_path[path].locked, path
    table.set_vary(["phases.*.lor_*", "phases.*.gauss_*"], True)
    assert set(TOF_SAMPLE_WIDTHS) <= set(table.free_paths)


def test_a_declared_free_capillary_offset_is_refused_by_name():
    """The one force-fix that raises instead of holding quietly: a *declared*
    ``vary=True`` is a claim the caller made, and eq (4) is in degrees."""
    ins = bank()
    ins.geometry.capillary_offset_along_beam.vary = True
    with pytest.raises(ValueError, match="neutron_tof bank"):
        ParameterTable(silicon(), ins)


def test_a_tof_table_round_trips_values_and_esds_through_apply_to_models():
    """The half-wired-parameter failure this module's docstring names: a
    constant registered in the collector and forgotten in ``apply_to_models``
    is refined, reported with an esd, and then silently lost at the next
    stage's recompile."""
    structure, instrument = silicon(), bank()
    table = ParameterTable(structure, instrument)
    by_path = {e.path: e for e in table.entries}
    # move every one of the fourteen off its stored value, and give each an esd
    moved = {p: by_path[p].value + 0.25 + 0.5 * i
             for i, p in enumerate(TOF_PATHS)}
    for p, v in moved.items():
        by_path[p].value = v
    esds = {p: 1e-3 * (i + 1) for i, p in enumerate(TOF_PATHS)}

    table.apply_to_models(structure, instrument, esds)

    src = instrument.source
    for p, want in moved.items():
        sub = p[len("instrument.source."):]
        holder = src.profile_tof if sub.startswith("profile_tof.") else src
        param = getattr(holder, sub.rsplit(".", 1)[-1])
        assert param.value == want, p
        assert param.stderr == esds[p], p
    # and the write reaches the *stored* container, not a throwaway: a second
    # table built from the written models sees the new values
    again = {e.path: e.value for e in ParameterTable(structure, instrument).entries}
    for p, want in moved.items():
        assert again[p] == want, p


#: sha256 of every row of four representative constant-wavelength tables —
#: path, value, ``vary``, ``locked``, both bounds and the tie repr —
#: measured on the parent of the time-of-flight forward model (the readers-and-
#: axis cut, which itself changes no constant-wavelength row) and unchanged by
#: it.  289 rows.  Re-measured on ``main`` f529fd78a (2026-11-06), identical:
#: the phase declares ``extinction=0.0`` (an opt-in block since WP-1944) and the
#: hump states ``position`` (required since WP-2013), each at the value the
#: field defaulted to before, so the four tables are the same rows as before.
#:
#: A hash rather than a list because the claim is *nothing moved*: a list would
#: have to be regenerated to be read, and regenerating it is exactly the act
#: that would hide the regression.  When it fires, print the two row lists and
#: diff them — the recipe is in this function.  A change on ``main`` that moves
#: a constant-wavelength row (WP-1454 made the P-spline's air term optional,
#: one row fewer here) re-measures it there, on the parent, never on this tree.
CW_TABLE_ROWS = 289
CW_TABLE_HASH = "14eb70c8c7279662ce610d19af8641c7641461f9e06fad81bdad1b5a2c2a58e4"


def _cw_models():
    """Four constant-wavelength pairs covering every optional block."""
    def p(v):
        return P(value=v)

    cell = Cell(a=p(3.15), b=p(3.15), c=p(4.77),
                alpha=p(90.0), beta=p(90.0), gamma=p(120.0))
    phase = Phase(name="brucite", space_group="P -3 m 1", cell=cell,
                  atoms=[Atom(label="Mg", species="Mg", x=p(0.0), y=p(0.0),
                              z=p(0.0), aniso=rx.AnisoU.isotropic(0.01, cell)),
                         Atom(label="O", species="O", x=p(1 / 3), y=p(2 / 3),
                              z=p(0.22))],
                  preferred_orientation=PreferredOrientation(axis=(0, 0, 1)),
                  microstrain=StephensStrain(), extinction=0.0)
    st = Structure(phases=[phase])
    spline = BackgroundPSpline(breakpoints=[10.0, 20.0, 30.0, 40.0],
                               coefficients=[p(0.0) for _ in range(6)])
    return [
        (st, Instrument(source=Source(lines=[
            EmissionLine(wavelength=1.540598),
            EmissionLine(wavelength=1.544426)]))),
        (st, Instrument(
            source=Source(lines=[EmissionLine(wavelength=1.540598)]),
            geometry=Geometry(kind="bragg_brentano",
                              goniometer_radius_mm=217.5,
                              surface_roughness=RoughnessSuortti()),
            background=spline,
            extra_components=[HumpComponent(position=p(0.0))])),
        (st, Instrument(
            source=Source(lines=[EmissionLine(wavelength=1.540598)]),
            geometry=Geometry(kind="debye_scherrer",
                              goniometer_radius_mm=217.5))),
        (st, rx.Instrument.constant_wavelength_neutron(wavelength=1.5401)),
    ]


def test_a_constant_wavelength_table_is_unchanged():
    h = hashlib.sha256()
    n = 0
    for structure, instrument in _cw_models():
        for e in ParameterTable(structure, instrument).entries:
            n += 1
            h.update(e.path.encode())
            # + 0.0 folds a signed zero: a zero microstrain DOF comes back
            # −0.0 from lstsq on macOS arm64 and +0.0 on Linux x86-64
            h.update(np.float64(e.value + 0.0).tobytes())
            h.update(f"{e.vary}|{e.locked}|{e.lo!r}|{e.hi!r}".encode())
            h.update(repr(e.tie).encode())
    assert (n, h.hexdigest()) == (CW_TABLE_ROWS, CW_TABLE_HASH)


def test_a_constant_wavelength_source_registers_no_tof_row():
    """The other direction: the fourteen paths exist on a bank and nowhere
    else, so a constant-wavelength plan cannot reach one by a glob."""
    for structure, instrument in _cw_models():
        paths = {e.path for e in ParameterTable(structure, instrument).entries}
        assert not (paths & set(TOF_PATHS))


# ----------------------------------------------------------------------
# 2. the result's abscissa
# ----------------------------------------------------------------------
def _bare_result(**kw):
    """A result with no curves — the state that makes ``axis`` three-valued."""
    from rietx.schemas.common import Provenance
    from rietx.schemas.results import RefinementResult, Statistics

    return RefinementResult(
        status="converged", mode="rietveld", parameters=[],
        statistics=Statistics(rwp=0.1, rp=0.08, rexp=0.09, gof=1.1, chi2=1.2,
                              n_points=100, n_free_parameters=3),
        provenance=Provenance(package_version="test", created_utc="now"), **kw)


def test_a_result_says_which_abscissa_it_holds():
    assert _bare_result(two_theta=[1.0, 2.0]).axis == "two_theta"
    assert _bare_result(tof=[1000.0, 1010.0]).axis == "tof"
    assert _bare_result(two_theta=[1.0, 2.0]).axis_unit == "degrees"
    assert _bare_result(tof=[1000.0]).axis_unit == "microseconds (µs)"
    assert np.array_equal(_bare_result(tof=[1000.0, 1010.0]).x(),
                          [1000.0, 1010.0])


def test_a_result_with_no_curve_names_no_axis():
    """The one place this does not mirror ``PatternData``: a pattern must have
    an abscissa and a result need not, so ``None`` is a real answer rather than
    an impossible state.  The alternative — defaulting to ``"two_theta"`` —
    would have every curve-less result assert an axis nobody measured."""
    bare = _bare_result()
    assert bare.axis is None and bare.axis_unit is None
    assert bare.two_theta is None and bare.tof is None
    assert len(bare.x()) == 0


def test_a_result_carrying_both_abscissae_is_refused():
    with pytest.raises(ValueError, match="at most one abscissa"):
        _bare_result(two_theta=[1.0, 2.0], tof=[1000.0, 1010.0])


def test_a_histogram_slice_carries_its_own_axis():
    """``for_histogram`` must swap *both* fields, or a joint fit over banks of
    different kinds hands histogram h the previous one's axis."""
    from rietx.schemas.results import HistogramResult, Statistics

    st = Statistics(rwp=0.1, rp=0.08, rexp=0.09, gof=1.1, chi2=1.2,
                    n_points=100, n_free_parameters=3)
    joint = _bare_result(two_theta=[1.0, 2.0])
    joint.histograms = [
        HistogramResult(label="cw", statistics=st, two_theta=[1.0, 2.0]),
        HistogramResult(label="bank", statistics=st, tof=[1000.0, 1010.0]),
    ]
    cw, tof = joint.for_histogram(0), joint.for_histogram(1)
    assert (cw.axis, cw.two_theta, cw.tof) == ("two_theta", [1.0, 2.0], None)
    assert (tof.axis, tof.two_theta, tof.tof) == ("tof", None,
                                                  [1000.0, 1010.0])
    assert joint.histograms[1].axis == "tof"
    assert joint.histograms[1].axis_unit == "microseconds (µs)"


def test_the_schema_version_moved_with_the_field():
    """A new observable field on the result is a ``SCHEMA_VERSION`` bump, and
    the bump comment in ``schemas/common.py`` lists what a consumer sees.

    The readers-and-axis rung was 0.53, and this cut is an "Also in 0.61"
    line, the release cycle's number (``schemas/common.py``'s rule; 1.11.0
    shipped 0.60 and ``main`` has moved to 0.61 since): the
    result's abscissa, the intensity basis, the corrections that follow λ
    across a bank, the four sample widths becoming refinable there, and the
    γ-polynomial refusal.  The number is pinned rather than relaxed on
    purpose: what this asserts is that somebody *noticed*, and a test that
    accepted any version would assert nothing."""
    from rietx.schemas.common import SCHEMA_VERSION

    assert SCHEMA_VERSION == "0.61"


def test_a_result_round_trips_through_json_on_either_axis():
    for kw in ({"two_theta": [1.0, 2.0]}, {"tof": [1000.0, 1010.0]}, {}):
        r = _bare_result(**kw)
        back = type(r).model_validate(r.model_dump(mode="json"))
        assert back == r
        assert back.axis == r.axis


def _synthetic_pattern(seed: int = 20260906) -> PatternData:
    """A pattern generated from the model it will be refined against.

    Poisson noise on the compiled curve, so the fit has a known answer and
    χ² ≈ 1 is a real bar rather than a coincidence.
    """
    from rietx.model.forward_tof import compile_tof_model

    grid = np.arange(TOF_LO, TOF_HI + 0.5 * TOF_STEP, TOF_STEP)
    blank = PatternData(tof=grid.tolist(), intensity=[1.0] * len(grid))
    ins = bank()
    ins.background.coefficients[0].value = 40.0
    ins.background.coefficients[1].value = -8.0
    structure = silicon()
    structure.phases[0].scale.value = 12.0
    model = compile_tof_model(structure, ins, blank)
    table = ParameterTable(structure, ins)
    y = np.asarray(model.evaluate(table.decode(table.x0())), dtype=np.float64)
    rng = np.random.default_rng(seed)
    noisy = rng.poisson(np.maximum(y, 0.0)).astype(np.float64)
    return PatternData(tof=grid.tolist(), intensity=noisy.tolist())


# ----------------------------------------------------------------------
# 3. the least-squares driver
# ----------------------------------------------------------------------
def test_both_compiled_models_answer_the_axis_blind_questions():
    """``n_points``, ``grid``, ``x_min``, ``x_max`` and ``axis`` are what the
    seven point counts in ``optimize.least_squares`` and the row layout in
    ``model.rows`` read, so both arms must answer all five — and the 2θ model's
    answers must be exactly the members they replace."""
    from rietx.model.forward import compile_model
    from rietx.model.forward_tof import compile_tof_model
    from tests.test_schemas import make_lab6

    tt = np.linspace(10.0, 90.0, 400)
    cw_data = PatternData(two_theta=tt.tolist(), intensity=[1.0] * len(tt))
    cw = compile_model(make_lab6(),
                       rx.Instrument.debye_scherrer(wavelength=1.5406),
                       cw_data)
    assert cw.axis == "two_theta"
    assert cw.n_points == len(cw.tt)
    assert cw.grid is cw.tt
    assert (cw.x_min, cw.x_max) == (cw.tt_min, cw.tt_max)

    tof = compile_tof_model(silicon(), bank(), _synthetic_pattern())
    assert tof.axis == "tof"
    assert tof.n_points == len(tof.tof)
    assert (tof.x_min, tof.x_max) == (tof.tof_min, tof.tof_max)
    # …and the 2θ accessors still refuse by name rather than being absent
    for name in ("tt", "tt_min", "tt_max"):
        with pytest.raises(ValueError, match="time-of-flight bank"):
            getattr(tof, name)


def test_a_tof_model_takes_the_finite_difference_jacobian():
    """The analytic ladder chains through emission-line planes, a pseudo-Voigt
    basis and FCJ nodes, none of which a bank has, so it is gated off — and the
    proof that it *was* gated off is that ``derivative_bases`` (which raises)
    is never reached while the columns still come out right."""
    from rietx.model.forward_tof import compile_tof_model
    from rietx.optimize.least_squares import _make_jacobian

    structure, instrument = silicon(), bank()
    data = _synthetic_pattern()
    table = ParameterTable(structure, instrument)
    table.set_vary(["phases.0.scale", "phases.0.cell.a",
                    "instrument.source.tzero", "instrument.background.c*"],
                   True)
    model = compile_tof_model(structure, instrument, data,
                              moving_paths=set(table.moving_paths))
    assert model.analytic_jacobian is False
    theta = table.x0()
    jac = _make_jacobian(model, table)(theta)
    assert jac.shape[0] == model.n_points
    assert np.all(np.isfinite(jac))
    # every column moves something: a short column is the WP-1070 failure the
    # gate exists to avoid, and it would show up as an all-zero column here
    assert np.all(np.abs(jac).max(axis=0) > 0.0)


def test_the_width_caps_are_declared_on_a_bank_in_its_own_arithmetic():
    """T-3c's owed item (T-1d): a bank states both tier-1 width caps.

    ``strain_cap``/``size_cap`` bound a width in deg 2θ against a 2θ extent
    and a wavelength, and a bank has neither, so the freeze used to be skipped
    entirely — which was right while these four columns were force-fixed and
    wrong the moment T-3c freed them: a free column with no fence.

    The flight-time arithmetic, both clauses checkable by hand from this
    fixture (DIFC = 12 000 µs/Å over 8000-45 000 µs):

    * **strain** — ΔT = DIFC·ε·d is largest at the longest fitted d, so
      ε ≤ f·(T_max − T_min)/(DIFC·d_max) and the stored coefficient is that
      over π/360;
    * **size** — ``lor_size`` on this arm is K/L in Å⁻¹ and ΔT = DIFC·(K/L)·d²,
      so the cap is the d² backstop f·(T_max − T_min)/(DIFC·d_max²), with
      **no wavelength in it** and, as on a scan since the WP-2002 B8 ruling,
      no size floor.
    """
    from rietx.model.forward_tof import compile_tof_model
    from rietx.optimize.least_squares import _freeze_size_cap, _freeze_strain_cap
    from rietx.params.vector import (
        SIZE_CAP_RANGE_FRACTION,
        STRAIN_CAP_RANGE_FRACTION,
    )

    table = ParameterTable(silicon(), bank())
    model = compile_tof_model(silicon(), bank(), _synthetic_pattern())
    _freeze_strain_cap(model, table)
    _freeze_size_cap(model, table)

    d_max = model.d_range[1]
    expected_strain = (STRAIN_CAP_RANGE_FRACTION
                       * (model.tof_max - model.tof_min)
                       / (DIFC_GEN * d_max) / (math.pi / 360.0))
    assert table._strain_cap == pytest.approx(expected_strain)
    assert table._size_cap == pytest.approx(
        SIZE_CAP_RANGE_FRACTION * (model.tof_max - model.tof_min)
        / (DIFC_GEN * d_max * d_max))
    # the frozen d range and DIFC are what both are read from, and they are a
    # per-stage fact exactly as the windows are
    assert model.difc_stage == DIFC_GEN
    assert model.d_range[0] < 1.0 < model.d_range[1]

    # …and a model that never froze them declares nothing, which is *no claim
    # made* and not a bound that happens to be infinite
    import dataclasses

    blind = dataclasses.replace(model, d_range=None, difc_stage=None)
    blank = ParameterTable(silicon(), bank())
    _freeze_strain_cap(blind, blank)
    _freeze_size_cap(blind, blank)
    assert blank._strain_cap is None and blank._size_cap is None


def test_the_bank_caps_are_generous_and_arm_only_where_reached():
    """The two properties that make a tier-1 cap landable, on this arm.

    A cap is spent only where the value has already gone somewhere the data
    cannot express — a bound is never free, since TRF takes its per-coordinate
    trust-region scale from the distance to it — so a fit inside the range is
    bit-identical to an uncapped build. And the number is generous: this
    bank's strain cap is a Δd/d of 84 %, against the ~10⁻³ a real specimen
    shows.
    """
    from rietx.model.forward_tof import compile_tof_model
    from rietx.optimize.least_squares import _freeze_size_cap, _freeze_strain_cap
    from rietx.params.vector import size_cap_hi, strain_cap_hi

    table = ParameterTable(silicon(), bank())
    model = compile_tof_model(silicon(), bank(), _synthetic_pattern())
    _freeze_strain_cap(model, table)
    _freeze_size_cap(model, table)
    strain_cap_value, size_cap_value = table._strain_cap, table._size_cap
    # generous: as a Δd/d the strain cap is tens of percent, not a per-mille
    assert 0.1 < strain_cap_value * math.pi / 360.0 < 2.0
    # a term well inside it gets no bound at all
    assert strain_cap_hi("lor_strain", 0.01, math.inf,
                         strain_cap_value) == math.inf
    assert size_cap_hi("lor_size", 1e-3, math.inf, size_cap_value) == math.inf
    # one that has reached it is bounded there, and the Gaussian pair take the
    # square of the same width
    assert strain_cap_hi("lor_strain", strain_cap_value, math.inf,
                         strain_cap_value) == strain_cap_value
    assert size_cap_hi("gauss_size", size_cap_value ** 2, math.inf,
                       size_cap_value) == size_cap_value ** 2
    # a finite stored bound is the caller's claim and outranks the cap, which
    # is also the one-line way to switch it off
    assert strain_cap_hi("lor_strain", 1e6, 1e9, strain_cap_value) == 1e9


def test_a_bank_refines_through_run_least_squares():
    """The positive arm at solver level: the cell tied by the table, started
    0.5 % out with TZERO 20 µs off and the scale halved, three rounds with a
    recompile between them — which is what ``Refinement`` does at a stage
    boundary and what re-cuts the frozen windows around the moved peaks."""
    from rietx.model.forward_tof import compile_tof_model
    from rietx.optimize.least_squares import run_least_squares
    from rietx.optimize.statistics import compute_statistics

    data = _synthetic_pattern()
    structure = silicon(a=A_GEN * 1.005)
    structure.phases[0].scale.value = 6.0
    instrument = bank(tzero=TZERO_GEN - 20.0)
    instrument.background.coefficients[0].value = 40.0
    table = ParameterTable(structure, instrument)
    table.set_vary(["phases.0.cell.a", "phases.0.scale",
                    "phases.0.atoms.0.biso", "instrument.source.tzero",
                    "instrument.source.profile_tof.alpha1",
                    "instrument.source.profile_tof.beta0",
                    "instrument.source.profile_tof.sig1",
                    "instrument.background.c*"], True)
    for _ in range(3):
        table.apply_to_models(structure, instrument)
        model = compile_tof_model(structure, instrument, data,
                                  moving_paths=set(table.moving_paths))
        outcome = run_least_squares(model, table, max_iter=60)
        table.commit(outcome.theta)

    values = table.decode(outcome.theta)
    stats = compute_statistics(model.y_obs, model.evaluate(values),
                               model.sigma, n_free=len(table.free_paths),
                               y_background=model.background(values))
    esds = table.stderr_physical(outcome.theta, outcome.stderr_internal,
                                 outcome.correlation)
    assert outcome.status == "converged"
    # the cell is TIED, which a hand-built values dictionary is not: b and c
    # follow a exactly, and it is the tie that keeps a cubic cell cubic
    assert values["phases.0.cell.b"] == values["phases.0.cell.a"]
    assert values["phases.0.cell.c"] == values["phases.0.cell.a"]
    assert abs(values["phases.0.cell.a"] - A_GEN) < 3.0 * esds["phases.0.cell.a"]
    assert abs(values["instrument.source.tzero"] - TZERO_GEN) < 1.0
    assert stats.chi2 < 1.2


# ----------------------------------------------------------------------
# 4. the whole engine: Refinement.fit
# ----------------------------------------------------------------------
def _tof_plan() -> rx.RefinementPlan:
    """A McCusker-ordered plan in the flight-time arm's own parameters.

    Scale and background first, then the one calibration constant this bank's
    standard would free, then the cell, then the profile, then the one
    structural parameter Si on 8a has.  The cell is freed **through the
    table**, which is what ties b and c to a — the tie a hand-built values
    dictionary does not have, and the bug T-1b's harness carried until its
    synthetic round trip caught it (its ``CUBIC_TIE``).
    """
    return rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.c*"]),
        rx.Stage("calibration", ["instrument.source.tzero"]),
        rx.Stage("cell", ["phases.*.cell.a"]),
        rx.Stage("profile", ["instrument.source.profile_tof.alpha1",
                             "instrument.source.profile_tof.beta0",
                             "instrument.source.profile_tof.sig1"]),
        rx.Stage("displacement", ["phases.*.atoms.*.biso"]),
    ])


@pytest.fixture(scope="module")
def tof_fit():
    """The committed acceptance: a synthetic Si bank refined by the engine.

    Started 0.5 % out on the cell, 20 µs out on TZERO and 2× out on the scale —
    the same displacement T-1b's harness started from, so the two arms are
    comparable.
    """
    data = _synthetic_pattern()
    structure = silicon(a=A_GEN * 1.005)
    structure.phases[0].scale.value = 6.0
    instrument = bank(tzero=TZERO_GEN - 20.0)
    instrument.background.coefficients[0].value = 40.0
    ref = rx.Refinement(structure, instrument, history=False)
    result = ref.fit(data, plan=_tof_plan())
    return ref, result


def test_the_engine_recovers_the_generating_bank(tof_fit):
    """Positive arm.  The cell is tied by the table, so a cubic phase stays
    cubic; the calibration and the profile come back where they were put."""
    _ref, result = tof_fit
    assert result.status == "converged"
    a = result.parameter("phases.0.cell.a")
    assert abs(a.value - A_GEN) < 3.0 * a.stderr
    assert abs(result.parameter("instrument.source.tzero").value
               - TZERO_GEN) < 1.0
    for name, want in PROFILE_GEN.items():
        path = f"instrument.source.profile_tof.{name}"
        row = next((p for p in result.parameters if p.path == path), None)
        if row is None or row.stderr is None:
            continue
        assert abs(row.value - want) < 5.0 * row.stderr, path
    assert result.statistics.chi2 < 1.2
    # Bérar-Lelann is already in the quoted esd (Statistics.esd_inflation says
    # by how much) — this asserts the fit reported one at all, since the "3
    # esd" bar above is meaningless without it
    assert result.statistics.esd_inflation > 1.0


def test_the_result_knows_its_axis(tof_fit):
    _ref, result = tof_fit
    assert result.axis == "tof"
    assert result.two_theta is None
    assert result.tof is not None
    assert result.axis_unit == "microseconds (µs)"
    assert np.array_equal(result.x(), np.asarray(result.tof))


def test_no_microsecond_reaches_a_member_called_two_theta(tof_fit):
    """Negative control D(iii), and the one this whole rung exists for.

    ``_build_result`` is the only writer of the field on a single-histogram
    fit, and it writes the pair.  The magnitudes make the assertion sharp: a
    flight time here is in the tens of thousands, which is not a 2θ any
    diffractometer measures, so a leak would be visible rather than plausible.
    """
    _ref, result = tof_fit
    assert max(result.tof) > 1000.0
    assert result.two_theta is None
    for hist in result.histograms:
        assert hist.two_theta is None
    # the ticks travel on the same axis as the curve beside them
    for positions in result.ticks.values():
        assert positions and min(positions) > 1000.0


def test_summary_renders_and_says_what_did_not_run(tof_fit):
    """Survivability, and the shape of it: every 2θ-only check reports that it
    did not run rather than returning an empty list that reads as a pass.

    The two sample-width flags left this list in T-3c: a bank carries a
    crystallite size and a microstrain, so both flags *run* there rather than
    abstaining, and a fit whose specimen widths sit at zero returns no row from
    either — which is the check running and finding nothing, and is the state
    this fixture is in.
    """
    ref, result = tof_fit
    text = ref.summary()
    assert "converged" in text
    assert TOF_NOT_EVALUATED in text
    codes = {d.code for d in result.diagnostics}
    assert "CAPILLARY_OFFSET_UNAVAILABLE" in codes
    assert not ({"STRAIN_UNUSUALLY_LARGE", "SIZE_UNUSUALLY_SMALL"} & codes)
    for d in result.diagnostics:
        if d.code == "CAPILLARY_OFFSET_UNAVAILABLE":
            assert TOF_NOT_EVALUATED in d.message
            assert d.level == "info"


def test_the_report_abstains_rather_than_attributing_degrees(tof_fit):
    """Negative control D(iv): Layer 1's position templates are not applied.

    Asserted on the *diagnostic text*, not on a ``KeyError``.  The bank's
    ``geometry_kind`` is a key ``POSITION_TEMPLATES`` does not have, precisely so
    that a wrong route is loud — but a report that reached that raise would be
    a crash, and what a caller must get is a rendered report that says the
    layer did not run.
    """
    from rietx.report.layer1 import POSITION_TEMPLATES

    ref, result = tof_fit
    report = ref.report()
    assert report.regions == []
    assert report.unmatched == []
    assert report.attribution == []
    assert report.suggested_actions == []
    assert not report.layer1_available
    assert report.abstained_reason is not None
    assert TOF_NOT_EVALUATED in report.summary
    # the axis-free half still speaks
    assert report.rwp == result.statistics.rwp
    assert report.background is not None
    # …and the key really is absent, so the control cannot go inert by a rename
    assert ref._model.geometry_kind not in POSITION_TEMPLATES
    assert set(POSITION_TEMPLATES) == {"bragg_brentano", "debye_scherrer",
                                       "flat_plate_transmission"}


def test_the_result_plots_on_its_own_axis(tof_fit):
    _ref, result = tof_fit
    fig = result.plot(x_axis="tof")
    ax = fig.get_axes()[0]
    assert "flight" in ax.get_xlabel()
    # and the three constant-wavelength coordinates are refused by name
    for x_axis in ("two_theta", "q", "d"):
        with pytest.raises(ValueError, match="flight time in microseconds"):
            result.plot(x_axis=x_axis, wavelength=1.5)


def test_predict_evaluates_on_a_flight_time_grid(tof_fit):
    ref, result = tof_fit
    grid = np.linspace(TOF_LO, TOF_HI, 500)
    y = ref.predict(grid)
    assert y.shape == grid.shape and np.all(np.isfinite(y))
    assert float(np.max(y)) > float(np.min(y))


# ----------------------------------------------------------------------
# the negative controls
# ----------------------------------------------------------------------
def test_a_mismatched_pair_is_refused_at_fit_both_ways():
    """Negative control D(i).  Each message names what the *other* half would
    have to be, because that is the edit the caller has to make."""
    tof_data = _synthetic_pattern()
    cw_data = PatternData(two_theta=np.linspace(10.0, 90.0, 400).tolist(),
                          intensity=[10.0] * 400)
    cw = rx.Instrument.constant_wavelength_neutron(wavelength=1.5401)

    with pytest.raises(ValueError, match="tof_neutron_bank"):
        rx.Refinement(silicon(), cw, history=False).fit(tof_data)
    with pytest.raises(ValueError, match="2θ in degrees"):
        rx.Refinement(silicon(), bank(), history=False).fit(cw_data)
    # both matched pairs construct and compile — the arm that makes the control
    # able to fail rather than a bar chosen to pass
    assert rx.Refinement(silicon(), bank(), history=False)
    assert rx.Refinement(silicon(), cw, history=False)


# ----------------------------------------------------------------------
# 5. the other backends
# ----------------------------------------------------------------------
#: Rows self-skip without their backend, the ``test_cross_backend`` idiom.  jax
#: is installed in this repository's dev extra; torch is optional.
_BACKENDS = ["jax", "torch"]


def _backend_or_skip(name: str):
    from rietx.backend.api import resolve_backend

    try:
        return resolve_backend(name)
    except Exception as exc:  # pragma: no cover - depends on the install
        pytest.skip(f"{name} backend unavailable: {exc}")


@pytest.mark.parametrize("backend", _BACKENDS)
@pytest.mark.parametrize("gam1", [0.0, 8.0], ids=["gaussian", "pseudovoigt"])
def test_the_tof_forward_model_agrees_across_backends(backend, gam1):
    """Both shapes, evaluated on the traced backends and against numpy.

    This is what ``test_cross_backend.py`` cannot cover: every row there
    compares an *analytic* Jacobian column against a backend's, and this arm
    declares it has none.  What has to be checked instead is the forward
    evaluation, and the reason it is not a formality is
    :func:`~rietx.model.profiles.tof.scaled_exp1`: e^z·E₁(z) is a power series
    on one side of a cancellation boundary and a modified-Lentz continued
    fraction on the other, selected by ``xp.where`` over **complex** arguments
    with both branches evaluated on safe values.  Nothing else in the package
    asks a traced backend for that.

    The bar is agreement, not the bit: the two paths associate their
    arithmetic differently and fp addition is not associative.
    """
    from rietx.backend.traced import active
    from rietx.model.forward_tof import compile_tof_model

    xp = _backend_or_skip(backend)
    structure = silicon()
    instrument = bank(**({"gam1": gam1} if gam1 else {}))
    instrument.background.coefficients[0].value = 40.0
    model = compile_tof_model(structure, instrument, _synthetic_pattern())
    assert model.profile_kind == ("pseudovoigt" if gam1 else "gaussian")
    table = ParameterTable(structure, instrument)
    values = table.decode(table.x0())

    y_numpy = np.asarray(model.evaluate(values), dtype=np.float64)
    with active(xp):
        y_traced = np.asarray(model.evaluate(dict(values)), dtype=np.float64)
    rel = np.abs(y_numpy - y_traced) / np.maximum(np.abs(y_numpy), 1e-300)
    assert float(rel.max()) < 1e-12


@pytest.mark.parametrize("backend", _BACKENDS)
def test_a_bank_refines_on_a_traced_backend(backend):
    """And the whole fit runs there, on an **autodiff** Jacobian.

    ``analytic_jacobian = False`` gates the hand-written analytic ladder in
    ``optimize.least_squares``, which is a numpy-only object; it says nothing
    about a backend that differentiates the traced residual itself.  So the
    numpy path here takes finite differences and jax takes ``jax.jvp``, and
    the two must still land in the same place — which is the strongest
    statement available about the finite-difference columns, since the two
    estimators share no code at all.
    """
    _backend_or_skip(backend)
    data = _synthetic_pattern()
    structure = silicon(a=A_GEN * 1.005)
    structure.phases[0].scale.value = 6.0
    instrument = bank(tzero=TZERO_GEN - 20.0)
    instrument.background.coefficients[0].value = 40.0
    traced = rx.Refinement(structure.model_copy(deep=True),
                           instrument.model_copy(deep=True),
                           history=False, backend=backend).fit(
        data, plan=_tof_plan())
    numpy_ = rx.Refinement(structure, instrument, history=False).fit(
        data, plan=_tof_plan())
    assert traced.status == numpy_.status == "converged"
    assert traced.statistics.rwp == pytest.approx(numpy_.statistics.rwp,
                                                  rel=1e-9)
    a_t = traced.parameter("phases.0.cell.a").value
    a_n = numpy_.parameter("phases.0.cell.a").value
    assert a_t == pytest.approx(a_n, abs=1e-7)


# ----------------------------------------------------------------------
# 6. the surfaces around the fit
# ----------------------------------------------------------------------
def test_the_session_surfaces_survive_a_bank(tmp_path):
    """History, a second stage, replay, a checkout, the CIF and suggest.

    Not a feature test: each of these reaches for the abscissa or the
    wavelength somewhere, and what is asserted is that none of them crashes and
    none of them invents an angle.  ``RefinementTree.for_data`` used to
    fingerprint ``data.two_theta`` directly and died on ``len(None)``; the
    exporter used to read ``source.primary_wavelength``.
    """
    from rietx.io.exporters import write_refinement_cif
    from rietx.refine import replay

    data = _synthetic_pattern()
    ref = rx.Refinement(silicon(a=A_GEN * 1.005), bank(tzero=TZERO_GEN - 20.0))
    result = ref.fit(data, plan=_tof_plan(), stage_reports=True)
    assert result.node_id and result.tree_id
    assert len(ref.stage_reports_) == len(_tof_plan().run_stages())

    again = ref.run_stage(data, rx.Stage("more_bkg",
                                         ["instrument.background.c*"]))
    assert again.axis == "tof" and again.two_theta is None

    back = replay(ref.history, result.node_id, data)
    assert back.axis == "tof" and back.two_theta is None

    resumed = rx.Refinement.from_node(ref.history, result.node_id)
    assert resumed.instrument.source.kind == "neutron_tof"

    path = tmp_path / "fit.cif"
    write_refinement_cif(result, ref.fitted_structure, ref.fitted_instrument,
                         str(path))
    text = path.read_text(encoding="utf-8")
    # no invented wavelength, the calibration said in words, and no pattern
    # loop under an angular tag
    assert "_diffrn_radiation_wavelength" not in text
    assert "_pd_calibration_special_details" in text
    assert "time-of-flight bank" in text
    assert "_pd_meas_2theta_scan" not in text
    assert "back-to-back exponentials" in text

    assert ref.suggest(data).n_evaluated > 0


# ----------------------------------------------------------------------
# 6. the variance floor and the γ check (T-1d)
# ----------------------------------------------------------------------
def test_the_sigma_triple_is_floored_at_zero_and_gamma_is_not():
    """Which three carry a floor, and why the other three do not.

    σ²(d) = sig0 + sig1·d² + sig2·d⁴ and γ(d) = gam0 + gam1·d + gam2·d² are
    both polynomials that must stay non-negative over the fitted range, which
    is a *cone* and not a box in either case.  The difference is what the
    coefficients mean: a variance coefficient has no regime in which it is
    negative, while a negative γ₁ beside positive γ₀ and γ₂ is how a
    resolution function narrows and then broadens again.  So σ gets the floor
    and γ gets the compile-time check below.  The floor is the field's
    declared range, which a ``Parameter`` leaving ``min`` unset inherits
    (issue #204); an explicit bound still wins.
    """
    prof = ProfileTOF()
    for name in ("sig0", "sig1", "sig2"):
        entry = getattr(prof, name)
        assert entry.min == 0.0
        # zero stays the default: it is a physical statement (no Gaussian
        # broadening)
        assert entry.value == 0.0
    for name in ("gam0", "gam1", "gam2", "alpha0", "alpha1", "beta0", "beta1"):
        entry = getattr(prof, name)
        assert entry.min == -math.inf
    # the floor survives the bare-float coercion, which is how every harness
    # on this track builds one
    assert ProfileTOF(sig1=300.0).sig1.min == 0.0
    with pytest.raises(ValueError, match=r"outside bounds \[0.0"):
        ProfileTOF(sig2=-6.09544)


def test_a_negative_gamma_polynomial_is_refused_by_name():
    """The Lorentzian twin of the σ² refusal, which had no equivalent.

    Measured: a real bank converged at ``gam1 = −5.749`` — a negative
    Lorentzian FWHM coefficient — and nothing refused or warned, because
    ``compile_tof_model`` checked the variance polynomial and not this one.
    """
    from rietx.model.forward_tof import compile_tof_model

    data = _synthetic_pattern()
    # γ(d) = 1 − 5.749·d is negative over most of this bank's 0.67-3.75 Å
    negative = bank(gam0=1.0, gam1=-5.749)
    with pytest.raises(ValueError) as exc:
        compile_tof_model(silicon(), negative, data)
    message = str(exc.value)
    assert "γ(d) = gam0 + gam1·d + gam2·d²" in message
    assert "gam1=-5.749" in message
    assert "negative total width is not a" in message

    # …and a negative coefficient whose polynomial stays positive is fine,
    # which is the half that makes this a check and not a bound: γ(d) =
    # 20 − 5·d + 2·d² has its minimum at d = 1.25, where it is 16.9
    fine = bank(gam0=20.0, gam1=-5.0, gam2=2.0)
    assert compile_tof_model(silicon(), fine, data).profile_kind == "pseudovoigt"


def test_sig2_freed_from_zero_moves_and_never_refuses_mid_plan():
    """The brief's arm: free ``sig2`` from a seed of exactly 0 and the stage
    must move it, keep it non-negative, and never refuse mid-plan.

    It does — and see the control below, which is what says *why*: on this
    fixture every spelling of the parameter moves, so this arm alone would be
    a control that cannot fail. What the floor buys is measured there.
    """
    data = _synthetic_pattern()
    structure = silicon()
    structure.phases[0].scale.value = 12.0
    instrument = bank()
    instrument.source.profile_tof.sig2 = rx.Parameter(
        value=0.0, min=0.0, unit="us^2/A^4")
    instrument.background.coefficients[0].value = 40.0
    plan = rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.c*"]),
        rx.Stage("profile", ["instrument.source.profile_tof.sig1",
                             "instrument.source.profile_tof.sig2"],
                 seed=1e-3),
        # a stage *after* the profile stage, because the measured failure was a
        # death at the next stage's recompile and not inside the solve
        rx.Stage("displacement", ["phases.*.atoms.*.biso"]),
    ])
    result = rx.Refinement(structure, instrument, history=False).fit(
        data, plan=plan)
    assert [s.status for s in result.stages] == ["converged"] * len(
        plan.run_stages())
    sig2 = result.parameter("instrument.source.profile_tof.sig2")
    assert sig2.value >= 0.0
    assert sig2.value == pytest.approx(0.0852541, rel=1e-3)
    assert sig2.stderr is not None and sig2.stderr > 0.0


def test_what_the_floor_actually_buys_is_the_sign_and_not_a_live_gradient():
    """The discriminating control: what the floor buys is the sign, not a
    revived gradient.

    ``FLAG-8`` diagnosed the measured freeze as a **dead gradient**: ``sig2``
    bounded at zero sits on its bound with no gradient, so TRF cannot move it.
    That does not reproduce: a parameter at its lower bound is moved by the
    projected gradient (``test_sig2_freed_from_zero_moves_and_never_refuses_
    mid_plan``).

    So the floor's value is the **sign**: with ``sig1`` held at 400 against
    the 300 the data was generated with, a free ``sig2`` whose caller states
    ``min=-inf`` walks to a negative Gaussian *variance* coefficient,
    borrowing a d⁴ term to repair a d² one, and that is the value
    ``compile_tof_model`` refuses the moment the reflection list reaches far
    enough in d, which is how a real joint fit died at compile time mid-plan.
    Under the declared floor the same fit stops at the floor instead.
    """
    from rietx.model.forward_tof import compile_tof_model

    data = _synthetic_pattern()

    sig1_hold = 400.0

    def fit(sig2: rx.Parameter) -> float:
        structure = silicon()
        structure.phases[0].scale.value = 12.0
        instrument = bank(sig1=sig1_hold)
        instrument.source.profile_tof.sig2 = sig2
        instrument.background.coefficients[0].value = 40.0
        result = rx.Refinement(structure, instrument, history=False).fit(
            data, plan=rx.RefinementPlan(stages=[
                rx.Stage("scale_bkg", ["phases.*.scale",
                                       "instrument.background.c*"]),
                rx.Stage("profile", ["instrument.source.profile_tof.sig2"]),
                rx.Stage("displacement", ["phases.*.atoms.*.biso"])]))
        return result.parameter("instrument.source.profile_tof.sig2").value

    # unfloored takes a stated bound: an unset one inherits the field's floor
    unfloored = fit(rx.Parameter(value=0.0, min=-math.inf, unit="us^2/A^4"))
    floored = fit(rx.Parameter(value=0.0, min=0.0, unit="us^2/A^4"))
    assert unfloored < -5.0
    assert 0.0 <= floored < 1e-9

    # …and this is what such a value does once the reflection list reaches
    # past sqrt(sig1/|sig2|) = 5.98 Å: the compiler refuses it by name, which
    # in a plan is a death at the *next* stage's recompile. Reproduced on a
    # long-d bank (DIFC 2822 µs/Å over 3500-22000 µs is d = 1.24-7.79 Å, the
    # range the real refusal quoted) over a 12 Å cell, whose (111) is at
    # 6.93 Å. The check is over the **reflections**, not over the window, so
    # the same coefficients on this file's 0.67-3.75 Å bank are silent.
    long_bank = rx.Instrument.tof_neutron_bank(
        difc=2822.36, tzero=0.0, two_theta_bank_deg=35.0,
        profile=ProfileTOF(alpha1=0.45, beta0=0.055, beta1=0.003))
    long_bank.source.profile_tof.sig1 = rx.Parameter(value=sig1_hold)
    long_bank.source.profile_tof.sig2 = rx.Parameter(value=unfloored,
                                                     min=-math.inf)
    long_grid = np.arange(3500.0, 22000.0, 20.0)
    long_pattern = PatternData(tof=long_grid.tolist(),
                               intensity=[1.0] * len(long_grid))
    with pytest.raises(ValueError, match="is negative somewhere in"):
        compile_tof_model(silicon(a=12.0), long_bank, long_pattern)
    # the same coefficients over the small cell compile, which is what makes
    # the sentence above a measurement rather than a restatement
    compile_tof_model(silicon(), long_bank, long_pattern)


def test_a_stored_negative_variance_coefficient_is_now_refused_at_the_schema():
    """Where the refusal moved to, and it moved *earlier*.

    Before the floor a negative ``sig2`` loaded into a ``ProfileTOF``, was
    serialized, round-tripped through a project, and was refused only by
    ``compile_tof_model`` — and only if the reflection list happened to reach
    far enough in d. Now it cannot be stored, and a GSAS-II ``.instprm``
    carrying one is refused **by name** by the reader rather than by pydantic,
    because a reader owes a message naming the file.
    """
    with pytest.raises(ValueError, match=r"outside bounds \[0.0"):
        ProfileTOF(sig2=-6.09544)
    with pytest.raises(ValueError, match=r"outside bounds \[0.0"):
        ProfileTOF(sig1=rx.Parameter(value=-1.0, min=0.0))
