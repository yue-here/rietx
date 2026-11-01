"""The PowderLine recipe reader and its four output tables (WP-1306).

Fast arms only: parsing, every refusal, the flag round trip, and the header
contract.  The two refinements against both reference engines are
``test_acceptance_powderline.py``.

Three of these tests exist because the *fixtures* disagree with each other and
the disagreement is the finding — see ``tests/data/README.md`` § v1.3
PowderLine recipe fixtures for the numbers.
"""

import copy
import csv
import json
import math
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.io.recipe import (
    CENTIDEG_TO_DEG,
    FIT_PROFILE_HEADER,
    GAUSS_CENTIDEG2_TO_DEG2,
    PEAK_LIST_HEADER,
    REFINED_PARAMETERS_HEADER,
    SIZE_COEF_DEG,
    STRAIN_COEF_DEG,
    UNIT_CELL_HEADER,
    Recipe,
    RecipeError,
    read_recipe,
    write_recipe_tables,
)

DATA = Path(__file__).parent / "data" / "powderline"
LAB6 = DATA / "example_LaB6"
DRX = DATA / "example_DRX_33"


@pytest.fixture(scope="module")
def lab6_doc() -> dict:
    return json.loads((LAB6 / "input.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def drx_doc() -> dict:
    return json.loads((DRX / "input.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def lab6() -> Recipe:
    return read_recipe(LAB6 / "input.json")


@pytest.fixture(scope="module")
def drx() -> Recipe:
    return read_recipe(DRX / "input.json")


def _edit(doc: dict) -> dict:
    return copy.deepcopy(doc)


def _codes(recipe: Recipe) -> set[str]:
    return {d.code for d in recipe.diagnostics}


# --- both fixtures parse ----------------------------------------------------


def test_lab6_parses_into_the_declared_model(lab6):
    assert lab6.schema_name == "GSASII_Rietveld"
    assert lab6.limits == (1.0, 15.0)
    assert len(lab6.pattern.two_theta) == 4096
    assert lab6.phase_names == ("LaB6",)
    (phase,) = lab6.structure.phases
    assert phase.space_group == "P m -3 m"
    assert phase.cell.a.value == pytest.approx(4.15682)
    assert not phase.cell.a.vary          # an SRM cell, held by the recipe
    assert phase.scale.vary
    assert [a.species for a in phase.atoms] == ["B", "La"]


def test_drx_parses_two_phases_with_the_flagged_cells_free(drx):
    assert drx.phase_names == ("DRX_33", "Li4MgWO6_SG12")
    cubic, mono = drx.structure.phases
    assert cubic.space_group == "F m -3 m"
    assert mono.space_group == "C2/m"
    assert cubic.cell.a.vary
    assert mono.cell.beta.vary
    assert not mono.cell.alpha.vary       # symmetry-fixed, flagged false
    assert mono.cell.beta.value == pytest.approx(109.96)


def test_sigma_is_one_over_root_w(lab6, lab6_doc):
    w = np.asarray(lab6_doc["payload"]["xrd_data"]["Itth_weights"])
    assert np.allclose(np.asarray(lab6.pattern.sigma), 1.0 / np.sqrt(w))


def test_uiso_becomes_biso(lab6, lab6_doc):
    uiso = lab6_doc["payload"]["phases"]["LaB6"]["structure"]["atoms"]["La"]["Uiso"]
    (phase,) = lab6.structure.phases
    la = next(a for a in phase.atoms if a.label == "La")
    assert la.biso.value == pytest.approx(8.0 * math.pi**2 * uiso)


# --- the conventions, measured against the reference output -----------------


def test_conventions_reproduce_the_reference_peak_list(lab6_doc):
    """The read conversion, checked against GSAS-II's own per-reflection widths.

    Their ``LaB6_peak_list_report.csv`` carries ``sigma_squared`` and ``gamma``
    computed by GSAS-II from the *refined* U V W X Y Z, so it is an independent
    statement of the formula and of the unit.  Recomputing it in this package's
    degrees and converting back must land on their number.

    ``gamma`` also carries GSAS-II's default sample broadening — 1 µm and 1000
    microstrain, which the recipe leaves null — and that is asserted here too,
    because it is the measurement behind ``RECIPE_ENGINE_DEFAULT_DECLINED``.

    And it carries a **floor at 0.001 centideg**, which this test found rather
    than assumed: 26 of the 49 reflections sit exactly there.  That is the
    other half of the negative-Y story — above ~6.5 °2θ GSAS-II's
    ``X/cosθ + Y·tanθ + Z`` goes negative and is clamped, so more than half its
    LaB6 reflections carry no Lorentzian at all.  This package's Lorentzian is
    softplus-bounded and monotone in tanθ, so it cannot reproduce that shape —
    which is a stated part of the Rwp gap in ``test_acceptance_powderline.py``.
    """
    lines = (LAB6 / "output/LaB6_peak_list_report.csv").read_text(encoding="utf-8").splitlines()
    head = lines[0].split(",")
    col = {n: i for i, n in enumerate(head)}
    rows = [[float(v) for v in ln.split(",")] for ln in lines[1:]]

    # the refined values, from their own refined_parameters.csv
    refined = {}
    for r in csv.DictReader(
            (LAB6 / "output/refined_parameters.csv").read_text(encoding="utf-8").splitlines()):
        refined[r["descriptive_name"]] = float(r["value"])
    U = refined["instrument_broadening_U"]
    V = refined["instrument_broadening_V"]
    W = refined["instrument_broadening_W"]
    X = refined["instrument_broadening_X"]
    Y = refined["instrument_broadening_Y"]
    Z = refined["instrument_broadening_Z"]
    lam = 0.1665

    floored = 0
    for r in rows:
        th = math.radians(r[col["2theta"]] / 2.0)
        tan, cos = math.tan(th), math.cos(th)
        # Gaussian: sigma_squared IS U tan^2 + V tan + W, in centideg^2
        assert r[col["sigma_squared"]] == pytest.approx(
            U * tan**2 + V * tan + W, rel=1e-6)
        # Lorentzian: the instrument terms plus GSAS-II's own size/strain
        # defaults, in centideg.  Both constants land on round numbers.
        instrument = X / cos + Y * tan + Z
        size = 100.0 * SIZE_COEF_DEG * lam / (math.pi * 1.0 * cos)
        strain = 100.0 * STRAIN_COEF_DEG * 1000.0 * tan / math.pi
        # An **absolute** bar, and the reason is the check itself: the
        # instrument half is X/cos + Y*tan with Y negative, so it is a
        # cancellation (0.572 - 0.316 at the first reflection, and closer to
        # zero further out).  Their refined_parameters.csv carries X and Y to
        # seven significant figures, which is 5e-8 on X and 6.5e-8 on Y*tan —
        # about 1.5e-7 together, and that is exactly the residual seen.  A
        # relative bar would be asserting their file's print precision, not
        # this package's formula.
        expected = instrument + size + strain
        if r[col["gamma"]] == 0.001:
            floored += 1
            assert expected < 0.001         # the floor, not a disagreement
            continue
        assert r[col["gamma"]] == pytest.approx(expected, abs=5e-7)
    assert floored == 26                    # over half, all above ~6.5 deg


def test_gaussian_and_lorentzian_units_are_the_measured_ones(lab6, lab6_doc):
    iparm = lab6_doc["payload"]["instrument"]["initialization"][0]
    p = lab6.instrument.profile
    assert p.u.value == pytest.approx(iparm["U"][1] * GAUSS_CENTIDEG2_TO_DEG2)
    assert p.w.value == pytest.approx(iparm["W"][1] * GAUSS_CENTIDEG2_TO_DEG2)
    assert p.x.value == pytest.approx(iparm["X"][1] * CENTIDEG_TO_DEG)
    # w is a FWHM^2 in deg^2: a 1.147 centideg^2 variance is a 0.0252 deg FWHM
    assert math.sqrt(p.w.value) == pytest.approx(0.02522, abs=1e-5)


def test_size_and_strain_split_by_the_lorentzian_share(drx):
    """LG_eta = 1 puts the whole magnitude in the Lorentzian half."""
    cubic = drx.structure.phases[0]
    lam = drx.instrument.source.lines[0].wavelength.value
    assert cubic.lor_size.value == pytest.approx(
        SIZE_COEF_DEG * lam / (math.pi * 1.0))
    assert cubic.lor_strain.value == pytest.approx(STRAIN_COEF_DEG * 1.0 / math.pi)
    assert cubic.gauss_size.value == 0.0
    assert cubic.gauss_strain.value == 0.0


def test_an_interior_eta_frees_both_halves(drx_doc):
    doc = _edit(drx_doc)
    block = (doc["payload"]["phases"]["DRX_33"]["parameterization"]
             ["peak_broadening"]["size_broadening"])
    block["LG_eta"] = [0.25, True, None, None]
    recipe = read_recipe(doc)
    phase = recipe.structure.phases[0]
    lam = recipe.instrument.source.lines[0].wavelength.value
    total = SIZE_COEF_DEG * lam / math.pi
    assert phase.lor_size.value == pytest.approx(0.25 * total)
    assert phase.gauss_size.value == pytest.approx((0.75 * total) ** 2)
    assert phase.lor_size.vary and phase.gauss_size.vary
    assert "RECIPE_FLAG_TRANSLATED" in _codes(recipe)


def test_an_off_state_half_is_held_and_said(drx):
    """LG_eta = 1: the Gaussian half starts at 0, and freed there it splits the
    width in a way the data does not resolve (``io.recipe._split``), so it is
    held and the hold is said."""
    for phase in drx.structure.phases:
        assert phase.lor_size.vary
        assert not phase.gauss_size.vary
    dropped = [d for d in drx.diagnostics if d.code == "RECIPE_FLAG_DROPPED"]
    assert len(dropped) == 4          # size and strain, both phases
    assert all("off state" in d.message for d in dropped)


def test_the_sh_l_split_is_declared_not_measured(lab6, lab6_doc):
    shl = lab6_doc["payload"]["instrument"]["initialization"][0]["SH/L"][1]
    g = lab6.instrument.geometry
    assert g.axial_sl.value == pytest.approx(shl / 2.0)
    assert g.axial_hl.value == pytest.approx(shl / 2.0)
    assert "RECIPE_CONVENTION_ASSUMED" in _codes(lab6)


def test_this_pattern_cannot_distinguish_the_sh_l_split(lab6):
    """The honest half of the row above: show the fixture cannot decide it.

    An even split against a 3:1 split, on a peak-by-peak calculated profile.
    If the difference were visible the adopted convention would be a claim the
    data could check; it is not, so the docstring's word "adopted" is earned.
    """
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable

    def profile(sl: float, hl: float) -> np.ndarray:
        instrument = lab6.instrument.model_copy(deep=True)
        instrument.geometry.axial_sl.value = sl
        instrument.geometry.axial_hl.value = hl
        model = compile_model(lab6.structure, instrument, lab6.pattern,
                              two_theta_limits=lab6.limits)
        table = ParameterTable(lab6.structure, instrument)
        return model.evaluate(table.decode(table.x0()))

    total = 2.0 * lab6.instrument.geometry.axial_sl.value
    even = profile(total / 2.0, total / 2.0)
    uneven = profile(total * 0.75, total * 0.25)
    scale = float(np.max(even) - np.min(even))
    # S/L here is far below the sizing floor, so since #774 it is drawn with
    # the floor's quadrature nodes (it was 0 nodes, an exact 0.0 difference,
    # when only the free set could raise it); the split now shows at 2.7e-4
    assert float(np.max(np.abs(even - uneven))) < 1e-3 * scale


# --- the refusals -----------------------------------------------------------


def test_a_non_zero_zero_is_refused_naming_both_readings(lab6_doc):
    doc = _edit(lab6_doc)
    doc["payload"]["instrument"]["initialization"][0]["Zero"] = [0.0, 0.03, False]
    with pytest.raises(RecipeError) as exc:
        read_recipe(doc)
    message = str(exc.value)
    assert "Zero" in message
    assert "centidegrees" in message and "degrees 2theta" in message
    assert "100x" in message


def test_a_non_zero_z_is_refused_and_a_zero_one_is_dropped(lab6, lab6_doc):
    assert "RECIPE_FLAG_DROPPED" in _codes(lab6)   # Z flagged at 0
    doc = _edit(lab6_doc)
    doc["payload"]["instrument"]["initialization"][0]["Z"] = [0.3, 0.3, False]
    with pytest.raises(RecipeError, match="constant term in the Lorentzian"):
        read_recipe(doc)


def test_a_negative_width_is_refused_rather_than_silently_zeroed(lab6_doc):
    """A negative X is refused: at θ → 0 it is the whole Lorentzian width.

    Both reference engines converge to a negative Y, and Y has no floor of
    its own since 2026-10-23 (WP-2002).  So the width X/cosθ + Y·tanθ is
    checked over the fitted range: with this recipe's X it crosses zero at
    2θ = 2.04°, under the range's top of 15°, and is refused there; with an
    X that carries it, the same Y is read as stated."""
    init = ["payload", "instrument", "initialization"]

    def edited(**letters):
        doc = _edit(lab6_doc)
        row = doc[init[0]][init[1]][init[2]][0]
        for letter, value in letters.items():
            row[letter] = [value, value, False]
        return doc

    with pytest.raises(RecipeError, match="bounded below at zero"):
        read_recipe(edited(X=-1.5))
    with pytest.raises(RecipeError, match=r"negative above 2θ = 2\.041°"):
        read_recipe(edited(Y=-15.8))
    recipe = read_recipe(edited(X=30.0, Y=-15.8))
    assert recipe.instrument.profile.y.value == pytest.approx(-0.158)


def test_the_spf_schema_is_refused_by_name(lab6_doc):
    doc = _edit(lab6_doc)
    doc["schema_name"] = "GSASII_SPF"
    with pytest.raises(RecipeError, match="single-peak fitting"):
        read_recipe(doc)


def _as_type(doc: dict, kind: str) -> dict:
    """A synthetic recipe: the LaB6 fixture with its instrument ``Type`` swapped."""
    doc = _edit(doc)
    doc["payload"]["instrument"]["initialization"][0]["Type"] = [kind, kind,
                                                                False]
    return doc


def test_a_pnc_recipe_builds_the_neutron_arm_and_refines(lab6_doc):
    """Issue #271: ``PNC`` is 2θ in degrees, so it is built, not refused.

    Synthetic — the LaB6 recipe relabelled ``PNC`` — so the Rwp means nothing;
    what is asserted is the source arm the reader built and that it fits.
    """
    recipe = read_recipe(_as_type(lab6_doc, "PNC"))
    source = recipe.instrument.source
    assert source.kind == "neutron_cw"
    lam = lab6_doc["payload"]["instrument"]["initialization"][0]["Lam"][1]
    assert source.wavelength.value == lam
    assert not source.wavelength.vary
    assert len(source.lines) == 1
    assert source.polarization.value == 1.0 and not source.polarization.vary
    assert source.dispersion is None
    dropped = [d for d in recipe.diagnostics
               if d.code == "RECIPE_FIELD_DROPPED"
               and d.where == ["payload.instrument.initialization[0].Polariz."]]
    assert len(dropped) == 1
    ref = rx.Refinement(recipe.structure, recipe.instrument, history=False)
    result = ref.fit(recipe.pattern, plan=recipe.plan,
                     two_theta_limits=recipe.limits)
    assert np.isfinite(result.statistics.rwp)


def test_a_pnc_recipe_refuses_a_flagged_polarization(lab6_doc):
    doc = _as_type(lab6_doc, "PNC")
    doc["payload"]["instrument"]["parameterization"]["polarization"] = [
        0.99, True, None, None]
    with pytest.raises(RecipeError, match="nothing for the flag to refine"):
        read_recipe(doc)


def test_a_pxc_recipe_is_unchanged_by_the_pnc_arm(lab6):
    source = lab6.instrument.source
    assert source.kind == "xray_cw"
    assert source.polarization.value == 0.99


@pytest.mark.parametrize("kind", ["PNT", "PXE"])
def test_a_non_2theta_type_is_refused_with_its_own_reason(lab6_doc, kind):
    """The refusal names what is true of that type alone (issue #271)."""
    with pytest.raises(RecipeError) as exc:
        read_recipe(_as_type(lab6_doc, kind))
    msg = str(exc.value)
    assert f"{kind!r} is" in msg
    assert "PatternData holds 2θ in degrees" in msg
    assert "'PNC' neutron" not in msg


def test_a_time_of_flight_type_names_flight_time(lab6_doc):
    with pytest.raises(RecipeError, match="time-of-flight neutron.*microseconds"):
        read_recipe(_as_type(lab6_doc, "PNT"))


def test_an_unknown_type_is_refused_without_a_described_reason(lab6_doc):
    with pytest.raises(RecipeError, match="does not know this type"):
        read_recipe(_as_type(lab6_doc, "SXC"))


def test_an_unimplemented_broadening_model_is_refused_by_name(drx_doc):
    doc = _edit(drx_doc)
    (doc["payload"]["phases"]["DRX_33"]["parameterization"]["peak_broadening"]
     ["strain_broadening"])["model"] = "generalized"
    with pytest.raises(RecipeError, match="NotImplementedError"):
        read_recipe(doc)


def test_anisotropic_adps_are_refused_by_name(lab6_doc):
    doc = _edit(lab6_doc)
    doc["payload"]["phases"]["LaB6"]["structure"]["atoms"]["La"]["ADP"] = "Uaniso"
    with pytest.raises(RecipeError, match="Uaniso"):
        read_recipe(doc)


def test_top_level_single_peaks_are_refused_but_background_ones_are_read(
        lab6, lab6_doc):
    assert len(lab6.instrument.extra_components) == 1   # background.single_peaks
    doc = _edit(lab6_doc)
    doc["payload"]["single_peaks"] = {
        "positions": [[2.3, True, None, None]],
        "intensities": [[100.0, True, None, None]],
        "pv_gaussian_sigma_sq": [[0.1, True, None, None]],
        "pv_lorentzian_gamma": [[0.05, True, None, None]]}
    with pytest.raises(RecipeError, match="fit_peaks"):
        read_recipe(doc)


def test_a_wide_hump_gamma_is_refused_and_a_narrow_one_dropped(
        lab6, lab6_doc):
    assert "RECIPE_FIELD_DROPPED" in _codes(lab6)      # gamma 1e-5 centideg
    doc = _edit(lab6_doc)
    doc["payload"]["background"]["single_peaks"]["pv_lorentzian_gamma"] = [
        [50.0, True, None, None]]
    with pytest.raises(RecipeError, match="Gaussian only"):
        read_recipe(doc)


def test_an_inverted_fit_range_is_refused(lab6_doc):
    doc = _edit(lab6_doc)
    doc["payload"]["fit_range"] = [15.0, 1.0]
    with pytest.raises(RecipeError, match="empty or inverted"):
        read_recipe(doc)


def test_a_malformed_parameter_entry_names_its_path(lab6_doc):
    doc = _edit(lab6_doc)
    doc["payload"]["phases"]["LaB6"]["parameterization"]["scale"] = [1.0, True]
    with pytest.raises(RecipeError, match="four elements"):
        read_recipe(doc)


def test_a_missing_file_and_bad_json_both_name_the_file(tmp_path):
    with pytest.raises(RecipeError, match="cannot be read"):
        read_recipe(tmp_path / "nope.json")
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(RecipeError, match="not valid JSON"):
        read_recipe(bad)


# --- what is reported rather than refused -----------------------------------


def test_the_degenerate_hump_is_warned_about(lab6):
    """LaB6 declares a 23.5 deg peak on a 14 deg range, beside six Chebyshev
    terms.  Both reference engines resolved it differently and neither
    resolved it well; the reader says so before the fit does."""
    (warning,) = [d for d in lab6.diagnostics
                  if d.code == "RECIPE_BACKGROUND_PEAK_DEGENERATE"]
    assert warning.level == "warning"
    assert warning.value > 14.0


def test_the_engine_default_is_declined_and_named(lab6):
    declined = [d for d in lab6.diagnostics
                if d.code == "RECIPE_ENGINE_DEFAULT_DECLINED"]
    assert len(declined) == 2                        # size and strain
    assert {d.value for d in declined} == {1.0, 1000.0}


def test_dispersion_is_declined_off_the_table_and_said(lab6):
    assert lab6.instrument.source.dispersion is None
    (d,) = [x for x in lab6.diagnostics
            if x.code == "RECIPE_DISPERSION_DECLINED"]
    assert "74.4" in d.message                        # E = 74.465 keV


def test_dispersion_stays_on_inside_the_table(lab6_doc):
    doc = _edit(lab6_doc)
    doc["payload"]["instrument"]["initialization"][0]["Lam"] = [1.5406, 1.5406,
                                                                False]
    doc["payload"]["instrument"]["parameterization"]["wavelength"] = [
        1.5406, False, None, None]
    recipe = read_recipe(doc)
    assert recipe.instrument.source.dispersion is not None
    assert "RECIPE_DISPERSION_DECLINED" not in _codes(recipe)


def test_the_parameterization_value_overrides_the_initialization(lab6_doc):
    """Both blocks can state a value and the 4-tuple is the specific one.

    Found by the test above: changing only ``initialization`` left λ at 0.1665,
    because the LaB6 recipe *also* states it in ``parameterization.wavelength``.
    Pinned here so the precedence is a decision rather than an accident.
    """
    doc = _edit(lab6_doc)
    doc["payload"]["instrument"]["initialization"][0]["Lam"] = [9.9, 9.9, False]
    doc["payload"]["instrument"]["parameterization"]["wavelength"] = [
        0.1665, False, None, None]
    recipe = read_recipe(doc)
    assert recipe.instrument.source.lines[0].wavelength.value == pytest.approx(
        0.1665)


def test_a_refinable_wavelength_is_refused_with_the_degeneracy_named(lab6_doc):
    doc = _edit(lab6_doc)
    doc["payload"]["instrument"]["parameterization"]["wavelength"] = [
        0.1665, True, None, None]
    with pytest.raises(RecipeError, match="flat direction"):
        read_recipe(doc)


def test_the_channel_count_is_reported_with_the_range(lab6):
    (d,) = [x for x in lab6.diagnostics
            if x.code == "RECIPE_FIT_RANGE_CHANNELS"]
    assert d.value == 3767            # GSAS-II's own fit_profile shows 3768
    assert "1.000356" in d.message


def test_the_reference_engines_fit_one_more_channel_than_this_mask():
    """The measurement behind the diagnostic above, kept where it can rot.

    GSAS-II writes the whole scan with y_calc = 0 outside the fitted range, so
    its own file says which channels it used: 1.000356 to 15.001321, one past
    the recipe's stated upper limit of 15.
    """
    rows = [ln.split() for ln in
            (LAB6 / "output/fit_profile.txt").read_text(encoding="utf-8").splitlines()[1:]]
    a = np.asarray([[float(v) for v in r] for r in rows])
    fitted = a[a[:, 3] != 0.0]
    assert fitted.shape[0] == 3768
    assert fitted[0, 0] == pytest.approx(1.000356, abs=1e-6)
    assert fitted[-1, 0] == pytest.approx(15.0013206, abs=1e-6)


def test_the_scale_is_reseeded_not_carried(lab6, lab6_doc):
    assert lab6_doc["payload"]["phases"]["LaB6"]["parameterization"]["scale"][0] == 1
    (phase,) = lab6.structure.phases
    assert phase.scale.value != 1.0
    assert "RECIPE_SCALE_RESEEDED" in _codes(lab6)


def test_the_background_is_reseeded_with_the_count_and_the_flag(lab6, lab6_doc):
    cheb = lab6_doc["payload"]["background"]["chebyshev"]
    coefficients = lab6.instrument.background.coefficients
    assert len(coefficients) == cheb["num_coefficients"]
    assert all(c.vary is cheb["refine_flag"] for c in coefficients)
    assert all(c.value == 0.0 for c in coefficients)
    assert "RECIPE_BACKGROUND_RESEEDED" in _codes(lab6)


def test_refinement_cycles_is_dropped_with_a_reason(lab6):
    dropped = [d for d in lab6.diagnostics
               if d.code == "RECIPE_FIELD_DROPPED"
               and "refinement_cycles" in d.message]
    assert len(dropped) == 1


def test_an_unknown_schema_version_warns_rather_than_refusing(lab6_doc):
    doc = _edit(lab6_doc)
    doc["schema_version"] = "0.99.0"
    recipe = read_recipe(doc)
    assert "RECIPE_SCHEMA_UNTESTED" in _codes(recipe)
    assert recipe.schema_version == "0.99.0"


# --- the plan ---------------------------------------------------------------


def test_the_plan_frees_exactly_what_the_recipe_flagged(lab6, lab6_doc):
    """The flag round trip: every path the plan frees, and no other, is a
    parameter the recipe flagged true."""
    freed = {p for stage in lab6.plan.stages for p in stage.turn_on}
    assert freed == {
        "phases.0.scale",
        "instrument.profile.u", "instrument.profile.v", "instrument.profile.w",
        "instrument.profile.x", "instrument.profile.y",
        *(f"instrument.background.c{n}" for n in range(6)),
        "instrument.extra_components.0.position",
        "instrument.extra_components.0.height",
        "instrument.extra_components.0.fwhm",
    }


def test_the_plan_is_staged_but_ends_at_the_recipes_own_free_set(drx):
    """Staging is cumulative, so the last stage IS the recipe's single pass."""
    assert len(drx.plan.stages) > 1
    freed = {p for stage in drx.plan.stages for p in stage.turn_on}
    assert "phases.0.cell.a" in freed and "phases.1.cell.beta" in freed
    assert "phases.0.lor_size" in freed
    assert not any(p.endswith(".gauss_size") for p in freed)
    assert [s.name for s in drx.plan.stages] == [
        "scale_bkg", "cell", "sample_broadening"]
    assert "RECIPE_PLAN_STAGED" in _codes(drx)


def test_a_recipe_that_flags_nothing_is_a_simulation(drx_doc):
    doc = _edit(drx_doc)

    def unflag(node):
        if isinstance(node, list) and len(node) == 4 and node[1] is True:
            node[1] = False
        elif isinstance(node, dict):
            for k, v in node.items():
                if k == "refine_flag" and v is True:
                    node[k] = False
                else:
                    unflag(v)
        elif isinstance(node, list):
            for v in node:
                unflag(v)

    unflag(doc["payload"])
    recipe = read_recipe(doc)
    assert "RECIPE_NOTHING_REFINED" in _codes(recipe)
    assert recipe.plan.stages[0].turn_on == []


# --- the four tables --------------------------------------------------------


@pytest.fixture(scope="module")
def written(tmp_path_factory, drx):
    """A short DRX_33 fit, only so the writer has something real to write.

    About 8 s, so every consumer carries ``xdist_group("recipe-tables")``:
    unmarked, xdist dealt them to four workers and each refitted it (WP-2019).
    """
    ref = rx.Refinement(drx.structure, drx.instrument, history=False)
    ref.fit(drx.pattern, plan=drx.plan, two_theta_limits=drx.limits)
    out = tmp_path_factory.mktemp("recipe_tables")
    return ref, out, write_recipe_tables(
        ref, out, phase_names=dict(zip(
            [p.name for p in ref.fitted_structure.phases], drx.phase_names)))


@pytest.mark.xdist_group("recipe-tables")
@pytest.mark.parametrize("engine", ["output", "output/topas"])
@pytest.mark.parametrize(
    "key,name",
    [("refined_parameters", "refined_parameters.csv"),
     ("unit_cell:DRX_33", "DRX_33_unit_cell_report.csv")])
def test_the_contracted_headers_match_both_engines_byte_for_byte(
        written, engine, key, name):
    _, _, paths = written
    theirs = (DRX / engine / name).read_text(encoding="utf-8").splitlines()[0]
    ours = paths[key].read_text(encoding="utf-8").splitlines()[0]
    assert ours == theirs


@pytest.mark.xdist_group("recipe-tables")
def test_the_fit_profile_header_matches_byte_for_byte(written):
    _, _, paths = written
    theirs = (DRX / "output/fit_profile.txt").read_text(encoding="utf-8").splitlines()[0]
    assert paths["fit_profile"].read_text(encoding="utf-8").splitlines()[0] == theirs
    assert theirs.split("\t") == list(FIT_PROFILE_HEADER)


def test_the_peak_list_header_is_not_a_contract_and_says_so():
    """The two reference engines write different peak-list headers.

    Recorded as a test rather than as prose because it is the reason this
    package writes its own columns there: a byte-for-byte assertion against
    "theirs" has no referent when the two of them disagree.
    """
    gsas = (DRX / "output/DRX_33_peak_list_report.csv"
            ).read_text(encoding="utf-8").splitlines()[0].split(",")
    topas = (DRX / "output/topas/DRX_33_peak_list_report.csv"
             ).read_text(encoding="utf-8").splitlines()[0].split(",")
    assert gsas != topas
    shared = [c for c in gsas if c in topas]
    assert len(shared) == 9 and len(gsas) == 15 and len(topas) == 11
    # ours is the shared set, minus F_obs_squared, plus GSAS-II's widths
    assert set(PEAK_LIST_HEADER) < set(gsas)
    assert "F_obs_squared" not in PEAK_LIST_HEADER


@pytest.mark.xdist_group("recipe-tables")
def test_refined_parameters_carries_only_refined_rows_with_esds(written):
    ref, _, paths = written
    rows = list(csv.DictReader(
        paths["refined_parameters"].read_text(encoding="utf-8").splitlines()))
    assert [r["parameter_name"] for r in rows]
    assert all(r["esd"] for r in rows)
    assert {r["category"] for r in rows} >= {
        "background", "scale", "cell", "size_broadening", "strain_broadening"}
    by_path = {r["parameter_name"]: r for r in rows}
    assert by_path["phases.1.cell.beta"]["descriptive_name"] == "cell_beta"
    assert by_path["phases.1.cell.beta"]["phase_name"] == "Li4MgWO6_SG12"
    assert by_path["phases.1.cell.beta"]["phase_idx"] == "1"
    varied = {p.path for p in ref.result_.parameters if p.vary}
    assert set(by_path) == varied


@pytest.mark.xdist_group("recipe-tables")
def test_the_unit_cell_report_writes_a_volume_with_no_esd(written):
    _, _, paths = written
    rows = list(csv.reader(
        paths["unit_cell:DRX_33"].read_text(encoding="utf-8").splitlines()))
    assert rows[0] == list(UNIT_CELL_HEADER)
    names = [r[0] for r in rows[1:]]
    assert names == ["cell_a", "cell_b", "cell_c", "cell_alpha", "cell_beta",
                     "cell_gamma", "cell_volume"]
    volume = rows[-1]
    assert float(volume[1]) > 0.0
    assert volume[2] == ""            # unmeasurable, not zero (WP-1076)
    # a symmetry-fixed angle is *held*, which is what both engines' 0 means
    assert float([r for r in rows if r[0] == "cell_alpha"][0][2]) == 0.0
    assert float([r for r in rows if r[0] == "cell_a"][0][2]) > 0.0


@pytest.mark.xdist_group("recipe-tables")
def test_the_peak_list_widths_round_trip_through_the_read_conversion(written):
    """Written sigma_squared/gamma, converted back, are this fit's own widths."""
    ref, _, paths = written
    rows = list(csv.DictReader(
        paths["peak_list:DRX_33"].read_text(encoding="utf-8").splitlines()))
    assert rows
    phase = ref.fitted_structure.phases[0]
    p = ref.fitted_instrument.profile
    for r in rows[:5]:
        th = math.radians(float(r["2theta"]) / 2.0)
        sig2 = float(r["sigma_squared"])
        gam = float(r["gamma"])
        fwhm_g = math.sqrt(sig2 * GAUSS_CENTIDEG2_TO_DEG2)
        fwhm_l = gam * CENTIDEG_TO_DEG
        expect_g = math.sqrt(
            (p.u.value + phase.gauss_strain.value) * math.tan(th) ** 2
            + p.v.value * math.tan(th) + p.w.value
            + phase.gauss_size.value / math.cos(th) ** 2)
        expect_l = ((p.x.value + phase.lor_size.value) / math.cos(th)
                    + (p.y.value + phase.lor_strain.value) * math.tan(th))
        # 1e-8, which is the CSV's own ``%.8e`` write precision rather than
        # anything about the conversion: the two directions share their
        # constants, so the only loss is the round trip through nine digits.
        assert fwhm_g == pytest.approx(expect_g, rel=1e-8)
        assert fwhm_l == pytest.approx(expect_l, rel=1e-8)


@pytest.mark.xdist_group("recipe-tables")
def test_the_fit_profile_columns_are_what_the_header_names(written):
    ref, _, paths = written
    lines = paths["fit_profile"].read_text(encoding="utf-8").splitlines()
    assert len(lines) - 1 == len(ref.result_.two_theta)
    a = np.asarray([[float(v) for v in ln.split("\t")] for ln in lines[1:]])
    lam = ref.fitted_instrument.source.lines[0].wavelength.value
    assert np.allclose(a[:, 0], ref.result_.two_theta)
    assert np.allclose(a[:, 4], a[:, 1] - a[:, 3])                 # y_diff
    assert np.allclose(a[:, 2], 1.0 / np.square(ref.result_.sigma))  # weights
    s = np.sin(np.radians(a[:, 0] / 2.0))
    assert np.allclose(a[:, 6], 4.0 * np.pi * s / lam)             # q
    assert np.allclose(a[:, 7], lam / (2.0 * s))                   # d
    assert "\r" not in paths["fit_profile"].read_text(encoding="utf-8")            # pure LF


def test_the_writer_refuses_a_refinement_that_has_not_run(drx):
    ref = rx.Refinement(drx.structure, drx.instrument, history=False)
    with pytest.raises(RuntimeError, match="call fit"):
        write_recipe_tables(ref, "/tmp/never-written")


@pytest.mark.xdist_group("recipe-tables")
def test_every_written_header_constant_is_the_one_the_file_carries(written):
    _, _, paths = written
    assert (paths["refined_parameters"].read_text(encoding="utf-8").splitlines()[0]
            == ",".join(REFINED_PARAMETERS_HEADER))
    assert (paths["unit_cell:DRX_33"].read_text(encoding="utf-8").splitlines()[0]
            == ",".join(UNIT_CELL_HEADER))
    assert (paths["peak_list:DRX_33"].read_text(encoding="utf-8").splitlines()[0]
            == ",".join(PEAK_LIST_HEADER))
