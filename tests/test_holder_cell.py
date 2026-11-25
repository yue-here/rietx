"""A sample holder fitted from its cell beside a Rietveld phase (WP-2108).

The holder's lines are `PeakComponent`s whose centres are formulas of one
holder lattice parameter and one height offset (`Refinement.tie(...,
expression=)`), so their intensities are free while their positions follow
a cell. The pattern is fluorapatite at one height and an aluminium holder
0.120 mm lower, drawn as a textured crystal so its intensities are not its
structure's (Stinton & Evans, 2007, J. Appl. Cryst. 40, 87, example 1).

The milestone's bar (`docs/milestones/parametric.md`, 2108): over 12 pinned
seeds the first phase's structure, both cells and the offset have a mean
z-score under 0.5 in size, and the holder fitted as a structure misses the
truth. The walkthrough is `examples/guides/holder_cell.py`.

The series (WP-2154) holds the same bar on a joint fit of five patterns that
share the holder's cell and offset, each pattern with its own specimen height.
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.examples import examples_dir

pytestmark = [pytest.mark.slow, pytest.mark.xdist_group("holder-cell")]

ZERO, HEIGHT, OFFSET, A_HOLDER = 0.012, 0.040, -0.120, 4.0495  # °, mm, mm, Å
LIMITS = (15.0, 90.0)
REFLECTIONS = {"111": 3, "200": 4, "220": 8, "311": 11, "222": 12}  # hkl: h² + k² + l²
SEEDS = range(100, 112)
OUTPUT = Path(__file__).parent / "output"


def _aluminium():
    cif = ("data_aluminium\n_space_group_name_H-M_alt 'F m -3 m'\n"
           f"_cell_length_a {A_HOLDER}\n_cell_length_b {A_HOLDER}\n_cell_length_c {A_HOLDER}\n"
           "_cell_angle_alpha 90\n_cell_angle_beta 90\n_cell_angle_gamma 90\n"
           "loop_\n_atom_site_label\n_atom_site_type_symbol\n_atom_site_fract_x\n"
           "_atom_site_fract_y\n_atom_site_fract_z\n_atom_site_B_iso_or_equiv\n"
           "Al1 Al 0 0 0 0.8\n")
    with tempfile.TemporaryDirectory() as work:
        path = Path(work) / "aluminium.cif"
        path.write_text(cif, encoding="utf-8")
        return rx.Structure.from_cif(path)


ALUMINIUM = _aluminium()
FLUORAPATITE = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
GRID = np.asarray(rx.read_pattern(examples_dir() / "FAP.XRA").two_theta)
GRID = GRID[(GRID > LIMITS[0] - 1) & (GRID < LIMITS[1] + 1)]


def _instrument(height=0.0, background=(0.0,) * 4, *, true=False):
    instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
    instrument.source.dispersion = None  # declared, never inherited
    instrument.background = rx.BackgroundChebyshev.with_terms(4)
    if true:
        instrument.zero_shift.value = ZERO
        instrument.geometry.sample_displacement.value = height
        instrument.profile.u.value, instrument.profile.w.value = 0.004, 0.002
        for coefficient, value in zip(instrument.background.coefficients, background):
            coefficient.value = value
    return instrument


def _simulate(seed, height=HEIGHT):
    sample = FLUORAPATITE.model_copy(deep=True)
    sample.phases[0].scale.value = 5e-4
    holder = ALUMINIUM.model_copy(deep=True)
    holder.phases[0].scale.value = 1e-3
    holder.phases[0].preferred_orientation = rx.PreferredOrientation(
        axis=(1, 1, 1), r=rx.Parameter(value=0.55))
    y = (rx.Refinement(sample, _instrument(height, (300.0, -60.0, 20.0, -5.0), true=True),
                       history=False).predict(GRID)
         + rx.Refinement(holder, _instrument(height + OFFSET, true=True),
                         history=False).predict(GRID))
    counts = np.random.default_rng(seed).poisson(y).astype(float)
    return rx.PatternData(two_theta=GRID, intensity=counts)


def _plan(*, variables):
    plan = rx.RefinementPlan.mccusker_structural()
    names = [stage.name for stage in plan.stages]
    if variables:
        plan.stages[names.index("zero")] = rx.Stage("zero_height", ["vars.zero", "vars.height"])
        plan.stages[names.index("extra_components")] = rx.Stage(
            "holder", ["instrument.extra_components.*", "vars.a_holder", "vars.offset"])
        plan.stages.insert(1, plan.stages.pop(names.index("extra_components")))
    else:
        plan.stages[names.index("zero")] = rx.Stage(
            "zero_height", ["instrument.zero_shift", "instrument.geometry.sample_displacement"])
    return plan


def _with_lines():
    """An instrument carrying one declared line per holder reflection, each
    started at a 4.05 Å cell."""
    instrument = _instrument()
    wavelength = instrument.source.lines[0].wavelength.value
    for hkl, n in REFLECTIONS.items():
        start = 2 * np.degrees(np.arcsin(wavelength * np.sqrt(n) / (2 * 4.05)))
        instrument.extra_components.append(rx.PeakComponent(
            label=f"aluminium {hkl}",
            center=rx.Parameter(value=start, min=start - 0.4, max=start + 0.4, unit="deg"),
            area=rx.Parameter(value=10.0, min=0.0, unit="counts*deg"),
            fwhm=rx.Parameter(value=0.1, min=0.02, max=0.4, unit="deg")))
    return instrument


def _declared():
    instrument = _with_lines()
    wavelength = instrument.source.lines[0].wavelength.value
    radius = instrument.geometry.goniometer_radius_mm
    ref = rx.Refinement(FLUORAPATITE.model_copy(deep=True), instrument, history=False)
    ref.add_variable("a_holder", 4.05, vary=True, min=4.0, max=4.1, unit="Å")
    ref.add_variable("offset", 0.0, vary=True, min=-0.5, max=0.5, unit="mm")
    ref.add_variable("zero", 0.0, vary=True, min=-0.2, max=0.2, unit="deg")
    ref.add_variable("height", 0.0, vary=True, min=-0.5, max=0.5, unit="mm")
    ref.tie("instrument.zero_shift", "vars.zero")
    ref.tie("instrument.geometry.sample_displacement", "vars.height")
    for j, n in enumerate(REFLECTIONS.values()):
        theta = f"asin({wavelength} * sqrt({n}) / (2 * a_holder))"
        ref.tie(f"instrument.extra_components.{j}.center",
                expression=f"2 * {theta} * 180 / pi + zero"
                           f" - 2 * (height + offset) / {radius} * cos({theta}) * 180 / pi")
    return ref


def _as_phase():
    structure = FLUORAPATITE.model_copy(deep=True)
    structure.phases.append(ALUMINIUM.model_copy(deep=True).phases[0])
    structure.phases[1].cell.a.value = 4.05
    structure.phases[1].cell.b.value = structure.phases[1].cell.c.value = structure.phases[1].cell.a.value  # the cell's ties follow a
    return rx.Refinement(structure, _instrument(), history=False)


def _z(result, path, true):
    p = result.parameter(path)
    return (p.value - true) / p.stderr


def _scores(result, holder_cell, offset):
    """z-scores of the truth: both cells, the offset, and fluorapatite's mean coordinate z."""
    rows = {q.path: q for q in result.parameters}
    true = FLUORAPATITE.phases[0]
    coords = [(rows[path].value - getattr(atom, axis).value) / rows[path].stderr
              for j, atom in enumerate(true.atoms) for axis in "xyz"
              if (path := f"phases.0.atoms.{j}.{axis}") in rows]
    out = {"a": _z(result, "phases.0.cell.a", true.cell.a.value),
           "c": _z(result, "phases.0.cell.c", true.cell.c.value),
           "coordinates": float(np.mean(coords)),
           "coordinates_rms": float(np.sqrt(np.mean(np.square(coords)))),
           "a_holder": _z(result, holder_cell, A_HOLDER)}
    if offset:
        out["offset"] = _z(result, offset, OFFSET)
    return out


@pytest.fixture(scope="module")
def runs():
    from rietx.viz.plots import plot_result

    declared, as_phase = [], []
    for seed in SEEDS:
        data = _simulate(seed)
        result = _declared().fit(data, plan=_plan(variables=True), two_theta_limits=LIMITS,
                                 telemetry=False)
        phase_result = _as_phase().fit(data, plan=_plan(variables=False),
                                       two_theta_limits=LIMITS, telemetry=False)
        declared.append(_scores(result, "vars.a_holder", "vars.offset"))
        as_phase.append(_scores(phase_result, "phases.1.cell.a", None))
        if seed == SEEDS[0]:
            OUTPUT.mkdir(exist_ok=True)
            for name, r in (("declared", result), ("as_phase", phase_result)):
                plot_result(r, path=str(OUTPUT / f"holder_cell_{name}_fit.png"))
                plot_result(r, path=str(OUTPUT / f"holder_cell_{name}_zoom.png"),
                            two_theta_limits=(37.5, 46.0))
    return declared, as_phase


def test_declared_lines_recover_both_cells_the_structure_and_the_offset(runs):
    declared, _ = runs
    means = {key: float(np.mean([row[key] for row in declared]))
             for key in declared[0] if key != "coordinates_rms"}
    assert all(abs(m) < 0.5 for m in means.values()), means
    # A signed mean over atoms cancels a +3σ atom against a −3σ one, so the
    # spread is bounded too: measured 0.84 on average and 1.11 at most.
    assert max(row["coordinates_rms"] for row in declared) < 1.6


def test_the_holder_fitted_as_a_structure_misses_its_cell(runs):
    """A phase shares the specimen's height, so its cell absorbs the 0.120 mm offset."""
    _, as_phase = runs
    assert all(row["a_holder"] < -10.0 for row in as_phase), [r["a_holder"] for r in as_phase]


# -- the series (WP-2154) -----------------------------------------------------

HEIGHTS = [0.040, -0.030, 0.090, 0.010, -0.060]  # mm, one specimen height per pattern


def _joint():
    """The holder over five patterns as one joint fit.

    A joint fit has no ``tie``, so each centre is an expression equation
    (WP-2101's shape): ``a_holder``, ``offset`` and ``zero`` are one column
    each, and ``SharingMap.per_histogram`` gives every pattern its own
    ``height``.  Line areas and widths sit under ``instrument.`` and so are
    per pattern by default; the profile is one instrument's, shared."""
    instruments = [_with_lines() for _ in HEIGHTS]
    wavelength = instruments[0].source.lines[0].wavelength.value
    radius = instruments[0].geometry.goniometer_radius_mm
    variables = {
        "a_holder": rx.Parameter(value=4.05, vary=False, min=4.0, max=4.1, unit="Å"),
        "offset": rx.Parameter(value=0.0, vary=False, min=-0.5, max=0.5, unit="mm"),
        "zero": rx.Parameter(value=0.0, vary=False, min=-0.2, max=0.2, unit="deg"),
        "height": rx.Parameter(value=0.0, vary=False, min=-0.5, max=0.5, unit="mm")}
    equations = [
        rx.ParametricEquation(name="zero_shift", target="instrument.zero_shift",
                              basis="expression", expression="zero"),
        rx.ParametricEquation(name="displacement",
                              target="instrument.geometry.sample_displacement",
                              basis="expression", expression="height")]
    for j, (hkl, n) in enumerate(REFLECTIONS.items()):
        theta = f"asin({wavelength} * sqrt({n}) / (2 * a_holder))"
        equations.append(rx.ParametricEquation(
            name=f"aluminium_{hkl}", target=f"instrument.extra_components.{j}.center",
            basis="expression",
            expression=f"2 * {theta} * 180 / pi + zero"
                       f" - 2 * (height + offset) / {radius} * cos({theta}) * 180 / pi"))
    return rx.JointRefinement(
        FLUORAPATITE.model_copy(deep=True), instruments,
        sharing=rx.SharingMap(shared=["instrument.profile.*"], per_histogram=["vars.height"]),
        variables=variables, parametric=equations)


@pytest.fixture(scope="module")
def series():
    from rietx.viz.plots import plot_result

    out = []
    for seed in SEEDS:
        data = [_simulate(seed * 10 + k, h) for k, h in enumerate(HEIGHTS)]
        result = _joint().fit(data, plan=_plan(variables=True), two_theta_limits=LIMITS,
                              telemetry=False)
        row = _scores(result, "vars.a_holder", "vars.offset")
        for k, h in enumerate(HEIGHTS):
            row[f"height_{k}"] = _z(result, f"pattern.{k}.vars.height", h)
        out.append(row)
        if seed == SEEDS[0]:
            OUTPUT.mkdir(exist_ok=True)
            for h in (0, len(HEIGHTS) - 1):
                plot_result(result.for_pattern(h),
                            path=str(OUTPUT / f"holder_series_h{h}_fit.png"))
                plot_result(result.for_pattern(h),
                            path=str(OUTPUT / f"holder_series_h{h}_zoom.png"),
                            two_theta_limits=(37.5, 46.0))
    return out


@pytest.mark.xdist_group("holder-series")
def test_a_joint_fit_shares_the_holder_cell_and_offset_across_heights(series):
    """Five patterns, one holder cell and one offset, a specimen height each:
    the milestone's bar (mean z under 0.5 in size) for both cells, the
    structure and the offset, and for each pattern's height too.

    Measured 2026-11-22 (macOS arm64, ``[dev]``): every mean z between −0.32
    and +0.26, coordinate RMS 0.85 on average and 1.06 at most.  The offset's
    esd is 0.42-0.49 of one pattern's fitted alone, about 1/√5."""
    means = {key: float(np.mean([row[key] for row in series]))
             for key in series[0] if key != "coordinates_rms"}
    assert all(abs(m) < 0.5 for m in means.values()), means
    assert max(row["coordinates_rms"] for row in series) < 1.6
