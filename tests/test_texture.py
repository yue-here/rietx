"""WP-1960: the spherical-harmonics texture block, its table entries and its refusals."""

import typing

import numpy as np
import pytest

import rietx as rx
from rietx.model.preferred_orientation import TEXTURE_SAMPLE_PSI_DEG
from rietx.optimize.least_squares import _make_jacobian, _make_residual
from rietx.params.vector import ParameterTable
from rietx.refine import _unsupported_phase_paths, mode_fixed_path
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import EmissionLine, Geometry, Instrument, Source
from rietx.schemas.plan import CLOSING_WINDOW_TOL
from rietx.schemas.structure import (
    Atom,
    Cell,
    Phase,
    PreferredOrientation,
    SphericalHarmonicTexture,
    Structure,
)

# declared, not inherited: off by default since WP-2222.  ``predict`` draws a
# truth on the closing windows, so a noise-free recovery fits on them too.
CLOSED = {"closing_window_tol": CLOSING_WINDOW_TOL}


def _cell(a, c, gamma=90.0):
    p = Parameter
    return Cell(a=p(value=a), b=p(value=a), c=p(value=c), alpha=p(value=90.0),
                beta=p(value=90.0), gamma=p(value=gamma))


def _phase(space_group="P -3 m 1", cell=None, **kw):
    cell = cell or _cell(3.15, 4.77, 120.0)
    p = Parameter
    return Phase(name="x", space_group=space_group, cell=cell,
                 atoms=[Atom(label="Mg", species="Mg", x=p(value=0.0), y=p(value=0.0),
                             z=p(value=0.0))], **kw)


def _table(phase):
    instrument = Instrument(source=Source(lines=[EmissionLine(wavelength=1.540598)]))
    return ParameterTable(Structure(phases=[phase]), instrument)


def _texture_rows(table):
    return {e.path: e for e in table.entries if ".texture." in e.path}


# ------------------------------------------------------------------ the schema
def test_the_block_round_trips_through_json():
    phase = _phase(texture=SphericalHarmonicTexture(order=4, coefficients={
        "c2_0": Parameter(value=0.31, vary=True), "c4_3": Parameter(value=-0.05)}))
    again = Phase.model_validate_json(phase.model_dump_json())
    assert again == phase
    assert again.texture.coefficients["c2_0"].vary is True


@pytest.mark.parametrize("order", [0, 1, 3, 7, -2])
def test_an_odd_or_absent_order_is_refused(order):
    with pytest.raises(ValueError, match="even and at least 2"):
        SphericalHarmonicTexture(order=order)


@pytest.mark.parametrize("name", ["c3_0", "c4_5", "c6_0", "c0_0", "C4_0", "c4-4", "c4_m4"])
def test_a_malformed_name_is_refused(name):
    with pytest.raises(ValueError, match="c<l>_<n>"):
        SphericalHarmonicTexture(order=4, coefficients={name: Parameter(value=0.0)})


def test_a_phase_declares_one_orientation_model():
    with pytest.raises(ValueError, match="both preferred_orientation and texture"):
        _phase(preferred_orientation=PreferredOrientation(axis=(0, 0, 1)),
               texture=SphericalHarmonicTexture(order=2))


# ------------------------------------------------------------------- the table
def test_every_allowed_term_gets_an_entry_held_at_zero():
    rows = _texture_rows(_table(_phase(texture=SphericalHarmonicTexture(order=6))))
    # -3m1 to order 6: one term at l = 2, two at l = 4, three at l = 6
    assert list(rows) == [f"phases.0.texture.{n}" for n in
                          ("c2_0", "c4_0", "c4_3", "c6_0", "c6_3", "c6_6")]
    assert all(e.value == 0.0 and not e.vary for e in rows.values())


def test_a_declared_coefficient_keeps_its_value_and_flag():
    block = SphericalHarmonicTexture(order=4, coefficients={
        "c2_0": Parameter(value=0.4, vary=True)})
    rows = _texture_rows(_table(_phase(texture=block)))
    assert rows["phases.0.texture.c2_0"].value == 0.4
    assert rows["phases.0.texture.c2_0"].vary
    assert not rows["phases.0.texture.c4_3"].vary


def test_a_term_the_laue_class_forbids_is_refused_by_name():
    # -3m1 carries sin 3β at l = 4 as c4_3; -3 adds c4_neg3, which -3m1 does not have
    block = SphericalHarmonicTexture(order=4, coefficients={"c4_neg3": Parameter(value=0.1)})
    with pytest.raises(ValueError, match=r"c4_neg3 is not a term .* c2_0, c4_0, c4_3"):
        _table(_phase(texture=block))


def test_an_order_with_no_term_names_the_lowest_that_has_one():
    cubic = _phase("P m -3 m", _cell(4.2, 4.2), texture=SphericalHarmonicTexture(order=2))
    with pytest.raises(ValueError, match="lowest order that allows one is 4"):
        _table(cubic)


def test_writing_back_fills_in_the_terms_the_block_left_out():
    phase = _phase(texture=SphericalHarmonicTexture(order=4))
    table = _table(phase)
    table.entries[table._paths["phases.0.texture.c4_3"]].value = -0.07
    structure = Structure(phases=[phase.model_copy(deep=True)])
    table.apply_to_models(structure, Instrument(
        source=Source(lines=[EmissionLine(wavelength=1.540598)])))
    written = structure.phases[0].texture.coefficients
    assert sorted(written) == ["c2_0", "c4_0", "c4_3"]
    assert written["c4_3"].value == -0.07


@pytest.mark.parametrize("mode, fixed", [("rietveld", False), ("lebail", True),
                                         ("pawley", True)])
def test_an_intensity_model_force_fixes_the_coefficients(mode, fixed):
    assert mode_fixed_path("phases.0.texture.c2_0", mode) is fixed
    assert mode_fixed_path("phases.0.texture.c4_neg3", mode) is fixed


# ------------------------------------------------------------- the forward model
def test_the_sample_angle_covers_every_geometry():
    """Every stated geometry has a ψ; ``unstated`` has none (WP-2015)."""
    kinds = set(typing.get_args(Geometry.model_fields["kind"].annotation))
    assert set(TEXTURE_SAMPLE_PSI_DEG) == kinds - {"unstated"}


def test_texture_under_an_unstated_geometry_is_refused_by_name():
    """ψ is 0° on a plate and 90° on a capillary, so a texture block needs
    the geometry stated; the predict names the field rather than guessing."""
    space_group, cell, truth = _RECOVERY[sorted(_RECOVERY)[0]]
    ins = Instrument(source=Source(lines=[EmissionLine(wavelength=1.540598)]))
    assert ins.geometry.kind == "unstated"
    with pytest.raises(ValueError, match=r"texture needs the specimen geometry"):
        rx.Refinement(Structure(phases=[_recovery_phase(
            space_group, cell, truth, vary=False)]), ins).predict(
                np.arange(10.0, 60.0, 0.05))


def _textured_state():
    from tests.test_cross_backend import _state_texture

    return _state_texture()[:2]


def test_each_texture_column_is_exact_at_a_whole_unit_step():
    """The branch oracle: the intensity is linear in C, so a difference quotient
    in physical units has no truncation error at any step (root CLAUDE.md)."""
    model, table = _textured_state()
    theta = np.array([table.entries[table._paths[q]].value for q in table.free_paths])
    jac = _make_jacobian(model, table)(theta)
    residual = _make_residual(model, table)
    r0 = residual(theta)
    checked = 0
    for c, path in enumerate(table.free_paths):
        if ".texture." not in path:
            continue
        step = theta.copy()
        step[c] += 1.0
        quotient = residual(step) - r0
        assert np.max(np.abs(jac[:, c] - quotient)) <= 1e-9 * np.max(np.abs(quotient)), path
        checked += 1
    assert checked == 4


def test_zero_coefficients_are_bit_identical_to_no_block():
    grid = np.arange(15.0, 95.0, 0.02)
    with_block = _phase(texture=SphericalHarmonicTexture(order=6))
    without = _phase()
    ins = Instrument.bragg_brentano()
    y_with = rx.Refinement(Structure(phases=[with_block]), ins).predict(grid)
    y_without = rx.Refinement(Structure(phases=[without]), ins).predict(grid)
    assert np.array_equal(np.asarray(y_with), np.asarray(y_without))


def test_the_absent_phase_hold_reaches_the_coefficients():
    """WP-1301's hold selects by column reach under ``phases.{ip}.``, scale aside."""
    model, table = _textured_state()
    held = _unsupported_phase_paths(model, table, support=np.array([0.0]))
    assert {p for p in table.free_paths if ".texture." in p} <= set(held)
    assert "phases.0.scale" not in held


#: One phase per Laue class the recovery runs over, each with the terms it allows to order 4.
_RECOVERY = {
    "m-3m": ("P m -3 m", (4.2, 4.2, 4.2, 90.0, 90.0, 90.0), {"c4_1": 0.4}),
    "6/mmm": ("P 6/m m m", (3.1, 3.1, 5.0, 90.0, 90.0, 120.0),
              {"c2_0": 0.5, "c4_0": -0.2}),
    # brucite's O, not Mg alone: hkl and khl overlap exactly in -3m1 and c4_3's
    # sin 3β takes opposite signs on them, so with equal |F|² the term cancels
    # within every pair and only roundoff is left to fit
    "-3m1": ("P -3 m 1", (3.147, 3.147, 4.769, 90.0, 90.0, 120.0),
             {"c2_0": 0.8, "c4_0": 0.3, "c4_3": -0.15}),
    "mmm": ("P m m m", (3.6, 4.4, 5.2, 90.0, 90.0, 90.0),
            {"c2_0": 0.4, "c2_2": -0.25, "c4_0": 0.1, "c4_2": 0.08, "c4_4": -0.12}),
    "2/m": ("P 1 2/m 1", (4.1, 3.6, 5.3, 90.0, 104.0, 90.0),
            {"c2_neg2": 0.15, "c2_0": 0.45, "c2_2": -0.2, "c4_0": 0.1, "c4_2": 0.05}),
}


def _recovery_phase(space_group, cell, coefficients, *, vary):
    p = Parameter
    lengths = dict(zip(("a", "b", "c", "alpha", "beta", "gamma"), cell))
    return Phase(name="t", space_group=space_group,
                 cell=Cell(**{k: p(value=v) for k, v in lengths.items()}),
                 scale=p(value=1e-3),
                 atoms=[Atom(label="Mg", species="Mg", x=p(value=0.0), y=p(value=0.0),
                             z=p(value=0.0), biso=p(value=0.5))]
                 + ([Atom(label="O", species="O", x=p(value=1 / 3), y=p(value=2 / 3),
                          z=p(value=0.22), biso=p(value=0.8))]
                    if space_group == "P -3 m 1" else []),
                 texture=SphericalHarmonicTexture(order=4, coefficients={
                     k: p(value=v if not vary else 0.0, vary=vary)
                     for k, v in coefficients.items()}))


@pytest.mark.parametrize("geometry", ["bragg_brentano", "debye_scherrer"])
@pytest.mark.parametrize("label", sorted(_RECOVERY))
def test_noise_free_coefficients_are_recovered_from_zero(label, geometry):
    space_group, cell, truth = _RECOVERY[label]
    ins = (Instrument.bragg_brentano() if geometry == "bragg_brentano"
           else Instrument.debye_scherrer(1.540598))
    grid = np.arange(10.0, 120.0, 0.02)
    y = np.asarray(rx.Refinement(Structure(phases=[_recovery_phase(
        space_group, cell, truth, vary=False)]), ins).predict(grid)) + 20.0
    data = rx.PatternData(two_theta=grid.tolist(), intensity=y.tolist())
    fit = rx.Refinement(Structure(phases=[_recovery_phase(
        space_group, cell, truth, vary=True)]), ins.model_copy(deep=True))
    result = fit.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"]),
        rx.Stage("texture", ["phases.*.scale", "instrument.background.c*",
                             "phases.*.texture.*"])], **CLOSED))
    got = {r.path.rsplit(".", 1)[1]: r.value for r in result.parameters
           if ".texture." in r.path}
    for name, value in truth.items():
        assert got[name] == pytest.approx(value, rel=1e-6), name


# -------------------------------------------------------- positivity and the record
def test_the_inequality_rows_reproduce_p_at_the_start():
    from rietx.optimize.least_squares import texture_positivity_inequalities

    model, table = _textured_state()
    x0 = table.x0()
    (block,) = texture_positivity_inequalities(model, table, x0)
    values = table.decode(x0)
    cell = tuple(values[f"phases.0.cell.{k}"] for k in ("a", "b", "c", "alpha", "beta", "gamma"))
    p = np.asarray(model._texture_factors(0, values, cell))
    assert np.allclose(block.T @ x0 + block.c, p, rtol=0, atol=1e-12)


def _negative_density_case(solver):
    """A strongly platy specimen (March-Dollase r = 0.4 along c) fitted at order 2.

    Two terms cannot follow a density that steep, and the best order-2 fit
    wants P < 0 on the (hk0) reflections, so the default driver must stop at
    the face P = 0 there and TRF need not.
    """
    space_group, cell, _ = _RECOVERY["6/mmm"]
    ins = Instrument.bragg_brentano()
    grid = np.arange(10.0, 120.0, 0.02)
    platy = _recovery_phase(space_group, cell, {}, vary=False).model_copy(update={
        "texture": None,
        "preferred_orientation": PreferredOrientation(axis=(0, 0, 1),
                                                      r=Parameter(value=0.4))})
    y = np.asarray(rx.Refinement(Structure(phases=[platy]), ins).predict(grid))
    data = rx.PatternData(two_theta=grid.tolist(), intensity=(y + 50.0).tolist())
    start = _recovery_phase(space_group, cell, {}, vary=False).model_copy(update={
        "texture": SphericalHarmonicTexture(order=2, coefficients={
            "c2_0": Parameter(value=0.0, vary=True)})})
    fit = rx.Refinement(Structure(phases=[start]), ins.model_copy(deep=True),
                        solver=solver)
    return fit.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"]),
        rx.Stage("texture", ["phases.*.scale", "instrument.background.c*",
                             "phases.*.texture.*"])], **CLOSED))


def test_the_default_driver_holds_p_at_the_reflections():
    result = _negative_density_case("lm")
    (row,) = result.texture
    assert row.min_p_reflections >= -1e-9
    assert row.texture_index > 1.0


def test_trf_goes_negative_and_the_guard_says_so():
    result = _negative_density_case("trf")
    (row,) = result.texture
    assert row.min_p_reflections < -0.1
    # the texture stage and the closing stage both fire it, and the result
    # takes it off the answer's vector alone (WP-2002)
    assert [s.name for s in result.stages][-1] == "closing"
    (diag,) = [d for d in result.diagnostics if d.code == "TEXTURE_NOT_POSITIVE"]
    assert diag.where == ["phases.0.texture"]
    assert diag.value == pytest.approx(row.min_p_sphere)
    assert "goes below zero" in diag.message


def test_the_record_matches_its_definition():
    space_group, cell, truth = _RECOVERY["mmm"]
    ins = Instrument.bragg_brentano()
    grid = np.arange(10.0, 120.0, 0.02)
    y = np.asarray(rx.Refinement(Structure(phases=[_recovery_phase(
        space_group, cell, truth, vary=False)]), ins).predict(grid)) + 20.0
    fit = rx.Refinement(Structure(phases=[_recovery_phase(
        space_group, cell, truth, vary=True)]), ins.model_copy(deep=True))
    result = fit.fit(rx.PatternData(two_theta=grid.tolist(), intensity=y.tolist()),
                     plan=rx.RefinementPlan(stages=[
                         rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"]),
                         rx.Stage("texture", ["phases.*.scale", "instrument.background.c*",
                                              "phases.*.texture.*"])], **CLOSED))
    (row,) = result.texture
    expected = 1.0 + sum(v * v / (2 * int(k[1:].split("_")[0]) + 1) for k, v in truth.items())
    assert row.name == "t"
    assert row.texture_index == pytest.approx(expected, rel=1e-6)
    assert row.min_p_sphere <= row.min_p_reflections
    assert not [d for d in result.diagnostics if d.code == "TEXTURE_NOT_POSITIVE"]


def test_the_structural_plan_frees_a_declared_block_with_march_dollase():
    from rietx.strategy.staged import PLAN_PRESETS

    (stage,) = [st for st in PLAN_PRESETS["mccusker_structural"]().stages
                if "phases.*.preferred_orientation.r" in st.turn_on]
    table = _table(_phase(texture=SphericalHarmonicTexture(order=4)))
    assert table.set_vary(stage.turn_on, True) == [
        "phases.0.texture.c2_0", "phases.0.texture.c4_0", "phases.0.texture.c4_3"]


@pytest.mark.parametrize("label", ["-3m1", "mmm"])
def test_poisson_noise_recovers_the_coefficients_within_three_esd(label):
    space_group, cell, truth = _RECOVERY[label]
    ins = Instrument.bragg_brentano()
    grid = np.arange(10.0, 120.0, 0.02)
    clean = np.asarray(rx.Refinement(Structure(phases=[_recovery_phase(
        space_group, cell, truth, vary=False)]), ins).predict(grid)) + 20.0
    counts = np.random.default_rng(1960).poisson(clean).astype(float)
    fit = rx.Refinement(Structure(phases=[_recovery_phase(
        space_group, cell, truth, vary=True)]), ins.model_copy(deep=True))
    result = fit.fit(rx.PatternData(two_theta=grid.tolist(), intensity=counts.tolist()),
                     plan=rx.RefinementPlan(stages=[
                         rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"]),
                         rx.Stage("texture", ["phases.*.scale", "instrument.background.c*",
                                              "phases.*.texture.*"])]))
    rows = {r.path.rsplit(".", 1)[1]: r for r in result.parameters if ".texture." in r.path}
    for name, value in truth.items():
        assert abs(rows[name].value - value) < 3.0 * rows[name].stderr, name


def test_a_nearly_symmetric_cell_builds_the_same_terms():
    """The table accepts a fixed angle 1e-3° off and a tied length at any stored
    value; the basis is built on the cell the symmetry demands (review, WP-1960)."""
    off = _phase(cell=_cell(3.15, 4.77, 120.0005), texture=SphericalHarmonicTexture(order=6))
    exact = _phase(texture=SphericalHarmonicTexture(order=6))
    assert list(_texture_rows(_table(off))) == list(_texture_rows(_table(exact)))


# ------------------------------------- TEXTURE_SPHERE_SAMPLES over its domain (B10)
#: what the sampled minimum may sit above the true one, in units of the random
#: powder's P = 1: the last digit the ``TEXTURE_NOT_POSITIVE`` message prints
SPHERE_MIN_BAR = 1e-3
#: one cell per Laue class the domain test samples
_SPHERE_CLASSES = {
    "-1": ("P -1", (5.1, 6.2, 7.3, 80.0, 95.0, 105.0)),
    "mmm": ("P m m m", (3.6, 4.4, 5.2, 90.0, 90.0, 90.0)),
    "-3m1": ("P -3 m 1", (3.147, 3.147, 4.769, 90.0, 90.0, 120.0)),
    "6/mmm": ("P 6/m m m", (3.1, 3.1, 5.0, 90.0, 90.0, 120.0)),
}


def _true_sphere_minimum(basis, v):
    """min over the sphere of K(u)·v: a 20 000-point Fibonacci grid, then
    Nelder-Mead in (polar, azimuth) from its five lowest points."""
    from scipy.optimize import minimize

    from rietx.crystallography.spherical_harmonics import sphere_points

    grid = sphere_points(20_000)
    f = np.asarray(basis.evaluate(grid)) @ v
    lowest = float(f.min())

    def at(t):
        u = np.array([[np.sin(t[0]) * np.cos(t[1]), np.sin(t[0]) * np.sin(t[1]),
                       np.cos(t[0])]])
        return float((np.asarray(basis.evaluate(u)) @ v)[0])

    for k in np.argsort(f)[:5]:
        x = grid[k]
        t0 = (np.arccos(np.clip(x[2], -1.0, 1.0)), np.arctan2(x[1], x[0]))
        r = minimize(at, t0, method="Nelder-Mead",
                     options={"xatol": 1e-10, "fatol": 1e-14})
        lowest = min(lowest, float(r.fun))
    return lowest


def _sphere_minimum_error(order):
    """The largest amount ``texture_summary``'s minimum sits above the true one,
    over two random coefficient draws per Laue class and sample geometry, each
    scaled so the true minimum is exactly 0.  Returns (error, which case)."""
    from rietx.model.forward import compile_model

    rng = np.random.default_rng(order)
    worst = (0.0, None)
    blank = rx.PatternData(two_theta=np.arange(10.0, 20.0, 0.05).tolist(),
                           intensity=np.ones(200).tolist())
    p = Parameter
    for label, (space_group, cell) in _SPHERE_CLASSES.items():
        phase = Phase(name="t", space_group=space_group,
                      cell=Cell(**{k: p(value=v) for k, v in zip(
                          ("a", "b", "c", "alpha", "beta", "gamma"), cell, strict=True)}),
                      atoms=[Atom(label="Mg", species="Mg", x=p(value=0.0), y=p(value=0.0),
                                  z=p(value=0.0))],
                      texture=SphericalHarmonicTexture(order=order))
        for ins in (Instrument.bragg_brentano(), Instrument.debye_scherrer(1.540598)):
            structure = Structure(phases=[phase])
            table = ParameterTable(structure, ins)
            model = compile_model(structure, ins, blank, mode="rietveld")
            cp = model.phases[0]
            if cp.tex_basis is None or not np.any(cp.tex_weights):
                continue
            values = dict(table.decode(table.x0()))
            for _ in range(2):
                c = rng.normal(size=len(cp.tex_paths))
                low = _true_sphere_minimum(cp.tex_basis, cp.tex_weights * c)
                if low >= 0.0:
                    continue
                values.update(zip(cp.tex_paths, -c / low, strict=True))
                _j, _on_reflections, on_sphere = model.texture_summary(0, values)
                assert on_sphere >= -1e-9, f"{label}: sampled below the true minimum"
                worst = max(worst, (on_sphere, f"{label}, {ins.geometry.kind}"),
                            key=lambda t: t[0])
    assert worst[1] is not None, "no case had a negative minimum to scale"
    return worst


@pytest.mark.slow  # 10.5 s serial for the four orders, run nightly like the other B10 domain tests
@pytest.mark.parametrize("order", [2, 4, 6, 8])
def test_the_sampled_sphere_minimum_meets_the_true_one(order):
    """``TEXTURE_SPHERE_SAMPLES`` = 2000, polished, over the orders its comment claims.

    B10 (ruled 2026-10-19): tier 1 once a test bounds the error over the
    domain.  The comment claims l to 8 or so.  The quantity is the lowest
    pole density P over the sphere, which ``PhaseTexture.min_p_sphere``
    records and ``TEXTURE_NOT_POSITIVE`` fires on below zero.  Each case
    scales random coefficients so the true minimum is exactly 0, the guard's
    decision point, and then asks ``CompiledModel.texture_summary``, so the
    shipped path is what is measured, reflections included.  Its minimum can
    only sit above the true one, and a density dipping that far below zero
    passes the guard unreported.

    The bar is 1e-3 of the random powder, the last digit the message prints
    (``{on_sphere:+.3f}``).  It is close to a tenth of the strongest peak's
    σ/peak on lab FAP.XRA (7.2e-4), which is what a reflection sitting in
    the dip would see.

    The samples alone failed every order (WP-2002, measured 2026-10-21):
    2.1e-3, 2.0e-3, 7.9e-3 and 5.6e-3 above the true minimum at orders 2-8,
    and 1.4e-2 to 4.4e-2 over eleven Laue classes at orders 8-16 in a probe.
    The error falls as 1/N with the sample count, so 32 000 would have cost
    about ten times the evaluation.  Since the seventh round's Q2 the minimum
    is polished from the five lowest samples
    (``preferred_orientation.sphere_minimum``), and leaves at most 2.6e-10,
    1.1e-9, 9.7e-10 and 1.7e-9 at orders 2-8 (6.7e-9 at 12, 9.4e-9 at 16), at
    9-15 ms a call at order 8 in P -1.

    Made to fail on 2026-10-21: ``TEXTURE_POLISH_STARTS`` set to 0 in the
    source, the sampled minimum alone, failed all four at the numbers above.
    """
    error, case = _sphere_minimum_error(order)
    assert error <= SPHERE_MIN_BAR, (
        f"order {order}: the sampled minimum sits {error:.2e} above the true one "
        f"({case}; bar {SPHERE_MIN_BAR})")


# ------------------------------------------------- the order screen (WP-1974)
def _bare_screen(texture, *, mg_only=False, march_r=None):
    """A −3m1 phase built with ``texture`` (or March-Dollase ``march_r`` on
    (001)), fitted bare (scale and background only, noise-free), and the order
    screen run on the answer."""
    from rietx.model.forward import WINDOW_AREA_TOL, compile_model
    from rietx.report.texture import _order_screen

    p = Parameter

    def phase(tex, r=None):
        atoms = [Atom(label="Mg", species="Mg", x=p(value=0.0), y=p(value=0.0),
                      z=p(value=0.0), biso=p(value=0.5))]
        if not mg_only:
            atoms.append(Atom(label="O", species="O", x=p(value=1 / 3), y=p(value=2 / 3),
                              z=p(value=0.22), biso=p(value=0.8)))
        kw = {"texture": SphericalHarmonicTexture(order=4, coefficients={
            k: p(value=v) for k, v in tex.items()})} if tex else {}
        if r is not None:
            kw = {"preferred_orientation": PreferredOrientation(axis=(0, 0, 1),
                                                                r=p(value=r))}
        return Phase(name="t", space_group="P -3 m 1",
                     cell=_cell(3.147, 4.769, 120.0), scale=p(value=1e-3), atoms=atoms, **kw)

    ins = Instrument.bragg_brentano()
    grid = np.arange(10.0, 120.0, 0.02)
    y = np.asarray(rx.Refinement(Structure(phases=[phase(texture, march_r)]), ins)
                   .predict(grid))
    data = rx.PatternData(two_theta=grid.tolist(), intensity=(y * 2e4 / y.max() + 50.0).tolist())
    bare = phase(None)
    bare.scale.value *= 2e4 / y.max()
    fit = rx.Refinement(Structure(phases=[bare]), ins.model_copy(deep=True))
    fit.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.c*"])]))
    fs, fi = fit.fitted_structure, fit.fitted_instrument
    table = ParameterTable(fs, fi)
    model = compile_model(fs, fi, data, mode="rietveld", window_area_tol=WINDOW_AREA_TOL)
    (screen,) = _order_screen(model, table.decode(table.x0()))
    return screen


def _bare_fit_screen(texture, *, mg_only=False):
    screen = _bare_screen(texture, mg_only=mg_only)
    return {f.order: f for f in screen.fits}, {s.order: s for s in screen.steps}


def test_the_order_screen_recovers_an_order_4_specimen_fitted_bare():
    """The positive arm: the solve on the partitioned columns returns the
    coefficients the pattern was built with, and order 6 adds nothing.  On the
    unpartitioned K the same fit reads c4_3 as −0.091 (WP-1974, measured
    2026-11-16), because hkl and khl share one extracted correction."""
    truth = {"c2_0": 0.3, "c4_0": 0.4, "c4_3": -0.15}
    fits, steps = _bare_fit_screen(truth)
    assert fits[4].r2 > 0.999 and fits[4].rank == 3
    assert fits[4].rms_p > 0.1   # 0.366 measured: the strength the other two bound
    got = dict(zip(fits[4].names, fits[4].coefficients))
    for name, value in truth.items():
        assert got[name] == pytest.approx(value, abs=0.01), name
    assert steps[6].delta_r2 < 1e-3 < steps[4].delta_r2
    # the statistics say the same (measured 2026-11-16: ΔBIC(4|2) −229.8 at
    # F p 4e-46, ΔBIC(6|4) +10.4 at p 0.99, ΔBIC vs the polished axis −189.7)
    assert steps[4].delta_bic < 0 < steps[6].delta_bic
    assert steps[4].p_value < 1e-6 and steps[6].p_value > 0.05
    assert steps[4].delta_bic_vs_axis < 0


def test_a_march_dollase_specimen_keeps_the_axis_against_every_order():
    """The other arm: −3m1 built with March-Dollase r = 0.8 on (001).  The
    axis is scored at r polished off the axis screen's grid, so the exact
    order solve is not compared with a quantised one: on the grid (R² 0.99852
    against 0.99994 at the polished r) orders 4-8 read ΔBIC vs axis −16.7,
    −65.7 and −57.3, polished +92.5, +43.6 and +52.0 (PR #1604 review,
    measured 2026-11-16).  The axis screen's own r and R² stay the grid's."""
    screen = _bare_screen(None, march_r=0.8)
    assert screen.axis == (0, 0, 1)
    assert all(s.delta_bic_vs_axis > 0 for s in screen.steps)
    assert screen.axis_r == pytest.approx(0.8, abs=0.002)
    assert screen.axis_r2 > 0.999


def test_a_term_the_partition_averages_away_adds_no_rank():
    """c4_3 on a one-atom −3m1 phase: hkl and khl coincide with equal |F|² and
    opposite K, so the extraction sees nothing of it — visibility 0, one rank
    short — and the built texture leaves no misfit for any order to explain:
    what is left is the report windows' own floor (rms P − 1 of 5.5e-5 to
    1.2e-4, measured 2026-11-16), three orders below the weakest built arm
    (0.13, a cubic c4_1 of 0.4)."""
    fits, _steps = _bare_fit_screen({"c4_3": 0.3}, mg_only=True)
    vis = dict(zip(fits[4].names, fits[4].visibility))
    assert vis["c4_3"] < 1e-9 and vis["c4_0"] > 0.9
    assert (fits[4].n_terms, fits[4].rank) == (3, 2)
    assert all(f.rms_p < 1e-3 for f in fits.values())


def test_a_random_powder_fitted_bare_has_no_texture_amplitude():
    """The scale-free numbers alone can speak here: a noise-free random powder
    leaves the misfit of the report's windows against the fit's, which some
    order explains a fraction of (on m-3m order 6 at F p 0.026, WP-1974's
    log).  Its amplitude, 7.9e-5 to 2.6e-4 rms P − 1 here, is the strength a
    suggestion needs beside R²."""
    fits, steps = _bare_fit_screen(None)
    assert all(f.rms_p < 1e-3 for f in fits.values())
    assert all(s.delta_bic > 0 for s in steps.values())   # +3.5 to +10.6 measured


#: Laue classes the order screen's rank gap is recorded over: (group, cell, O site).
_GAP_CASES = {
    "-1": ("P -1", (4.1, 3.6, 5.3, 85.0, 104.0, 95.0), (0.31, 0.17, 0.23)),
    "-1 short range": ("P -1", (4.1, 3.6, 5.3, 85.0, 104.0, 95.0), (0.31, 0.17, 0.23)),
    "2/m": ("P 1 2/m 1", (4.1, 3.6, 5.3, 90.0, 104.0, 90.0), (0.5, 0.5, 0.5)),
    "mmm": ("P m m m", (3.6, 4.4, 5.2, 90.0, 90.0, 90.0), (0.5, 0.5, 0.5)),
    "-3m1": ("P -3 m 1", (3.147, 3.147, 4.769, 90.0, 90.0, 120.0), (1 / 3, 2 / 3, 0.22)),
    "-3m1 Mg only": ("P -3 m 1", (3.147, 3.147, 4.769, 90.0, 90.0, 120.0), None),
    "6/mmm": ("P 6/m m m", (3.1, 3.1, 5.0, 90.0, 90.0, 120.0), (1 / 3, 2 / 3, 0.5)),
    "m-3m": ("P m -3 m", (4.2, 4.2, 4.2, 90.0, 90.0, 90.0), (0.5, 0.5, 0.5)),
}


@pytest.mark.parametrize("label", list(_GAP_CASES))
def test_the_order_screen_rank_tolerance_sits_in_a_gap(label):
    """``_ORDER_RANK_TOL`` (1e-8) cuts singular values of the partitioned
    design, columns scaled to their unpartitioned norm, at orders 2-8.  Measured
    2026-11-16 over these seven phases: largest dropped 7.6e-16 (the one-atom
    −3m1 phase's c4_3, c6_3 and c8_3, which the partition averages away),
    smallest kept 0.13 (−3m1 at order 8), so on those six any tolerance from
    1e-12 to 1e-2 returns the same ranks.  The seventh, a P −1 phase read only
    to 2θ = 60° ("-1 short range"), is where collinearity among visible terms
    shrinks singular values: kept 5.9e-3 at order 6 and 2.1e-4 at order 8, and
    13 of order 8's 44 terms dropped at 1.3e-15 (rank 31).  The window over all
    seven is therefore 1e-12 to 1e-4: the dropped values are roundoff, 1.3e-15
    on arm64 and above 1e-14 on the Linux py3.14 CI leg (PR #1604 review).  Where no gap exists
    (visible terms nearly but not exactly collinear) the cut itself decides the
    rank that ``added_rank`` and ΔBIC read: the screen reports the rank it
    kept (``min_kept_sv`` shows how close to the cut) and does not warn.  The
    design does not depend on f, so the model is read at its own values."""
    from rietx.model.forward import WINDOW_AREA_TOL, compile_model
    from rietx.report.texture import _ORDER_RANK_TOL, _order_screen

    space_group, cell, o_site = _GAP_CASES[label]
    p = Parameter
    atoms = [Atom(label="Mg", species="Mg", x=p(value=0.0), y=p(value=0.0), z=p(value=0.0),
                  biso=p(value=0.5))]
    if o_site is not None:
        atoms.append(Atom(label="O", species="O", x=p(value=o_site[0]), y=p(value=o_site[1]),
                          z=p(value=o_site[2]), biso=p(value=0.8)))
    structure = Structure(phases=[Phase(
        name="t", space_group=space_group, scale=p(value=1e-3), atoms=atoms,
        cell=Cell(**{k: p(value=v) for k, v in zip(
            ("a", "b", "c", "alpha", "beta", "gamma"), cell)}))])
    ins = Instrument.bragg_brentano()
    grid = np.arange(10.0, 60.0 if "short" in label else 120.0, 0.02)
    y = np.asarray(rx.Refinement(structure, ins).predict(grid)) + 20.0
    y *= 1.0 + 0.05 * np.random.default_rng(7).standard_normal(len(y))
    data = rx.PatternData(two_theta=grid.tolist(), intensity=y.tolist())
    model = compile_model(structure, ins, data, mode="rietveld", window_area_tol=WINDOW_AREA_TOL)
    table = ParameterTable(structure, ins)
    (screen,) = _order_screen(model, table.decode(table.x0()))
    kept = [f.min_kept_sv for f in screen.fits if f.rank]
    dropped = [f.max_dropped_sv for f in screen.fits if f.rank < f.n_terms]
    # the gap each side of the cut: every kept value above 1e4 x the cut, every
    # dropped one below 1e-4 x it (roundoff differs by platform) (on the short-range P -1 phase the smallest
    # kept is 2.1e-4, so the cut's safe window ends at 1e-4, not 1e-2)
    assert kept and min(kept) > 1e4 * _ORDER_RANK_TOL
    assert all(d < 1e-4 * _ORDER_RANK_TOL for d in dropped)
    assert bool(dropped) == (label in ("-3m1 Mg only", "-1 short range"))
