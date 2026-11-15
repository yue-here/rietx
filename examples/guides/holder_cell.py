"""The fit behind `docs/docs/guides/holder.md` § Tie the holder's lines to its cell.

The page shows the lines between each pair of `guide:` markers and quotes what
they print; every quoted number is asserted at the end, so a change that moves
one fails `tests/test_examples.py`.

Data: one synthetic pattern made here, on the grid of the GSAS-II fluorapatite
scan from 15° to 90° 2θ. The specimen is fluorapatite, with its surface
0.040 mm above the goniometer axis. Under it sits an aluminium holder whose
surface is 0.120 mm lower again. The holder is drawn as a crystal with a
March-Dollase texture along [111], so its line intensities are not those of
its structure. Stinton & Evans (2007, J. Appl. Cryst. 40, 87) fit an aluminium
holder this way, for the same reason.
"""

import tempfile
from pathlib import Path

import numpy as np

import rietx as rx
from rietx.examples import examples_dir

ZERO, HEIGHT, OFFSET, A_HOLDER = 0.012, 0.040, -0.120, 4.0495  # °, mm, mm, Å
CIF = (
    "data_aluminium\n_space_group_name_H-M_alt 'F m -3 m'\n"
    f"_cell_length_a {A_HOLDER}\n_cell_length_b {A_HOLDER}\n_cell_length_c {A_HOLDER}\n"
    "_cell_angle_alpha 90\n_cell_angle_beta 90\n_cell_angle_gamma 90\n"
    "loop_\n_atom_site_label\n_atom_site_type_symbol\n_atom_site_fract_x\n"
    "_atom_site_fract_y\n_atom_site_fract_z\n_atom_site_B_iso_or_equiv\n"
    "Al1 Al 0 0 0 0.8\n")
with tempfile.TemporaryDirectory() as work:
    path = Path(work) / "aluminium.cif"
    path.write_text(CIF, encoding="utf-8")
    ALUMINIUM = rx.Structure.from_cif(path)
FLUORAPATITE = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
TWO_THETA = np.asarray(rx.read_pattern(examples_dir() / "FAP.XRA").two_theta)
TWO_THETA = TWO_THETA[(TWO_THETA > 14.0) & (TWO_THETA < 91.0)]


def true_instrument(height, background):
    instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
    instrument.zero_shift.value = ZERO
    instrument.geometry.sample_displacement.value = height
    instrument.profile.u.value, instrument.profile.w.value = 0.004, 0.002
    instrument.background = rx.BackgroundChebyshev.with_terms(4)
    for coefficient, value in zip(instrument.background.coefficients, background):
        coefficient.value = value
    return instrument


def simulate(seed=7):
    """Fluorapatite at HEIGHT, textured aluminium at HEIGHT + OFFSET, Poisson noise."""
    sample = FLUORAPATITE.model_copy(deep=True)
    sample.phases[0].scale.value = 5e-4
    holder = ALUMINIUM.model_copy(deep=True)
    holder.phases[0].scale.value = 1e-3
    holder.phases[0].preferred_orientation = rx.PreferredOrientation(
        axis=(1, 1, 1), r=rx.Parameter(value=0.55))
    y = (rx.Refinement(sample, true_instrument(HEIGHT, (300.0, -60.0, 20.0, -5.0))).predict(TWO_THETA)
         + rx.Refinement(holder, true_instrument(HEIGHT + OFFSET, (0.0,) * 4)).predict(TWO_THETA))
    counts = np.random.default_rng(seed).poisson(y).astype(float)
    return rx.PatternData(two_theta=TWO_THETA, intensity=counts)


data = simulate()

# guide: start
instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
instrument.background = rx.BackgroundChebyshev.with_terms(4)
wavelength = instrument.source.lines[0].wavelength.value  # Kα1, Å
radius = instrument.geometry.goniometer_radius_mm  # mm

reflections = {"111": 3, "200": 4, "220": 8, "311": 11, "222": 12}  # hkl: h² + k² + l²
for hkl, n in reflections.items():
    start = 2 * np.degrees(np.arcsin(wavelength * np.sqrt(n) / (2 * 4.05)))
    instrument.extra_components.append(rx.PeakComponent(
        label=f"aluminium {hkl}",
        center=rx.Parameter(value=start, min=start - 0.4, max=start + 0.4, unit="deg"),
        area=rx.Parameter(value=10.0, min=0.0, unit="counts*deg"),
        fwhm=rx.Parameter(value=0.1, min=0.02, max=0.4, unit="deg")))

ref = rx.Refinement(FLUORAPATITE.model_copy(deep=True), instrument)
ref.add_variable("a_holder", 4.05, vary=True, min=4.0, max=4.1, unit="Å")
ref.add_variable("offset", 0.0, vary=True, min=-0.5, max=0.5, unit="mm")
ref.add_variable("zero", 0.0, vary=True, min=-0.2, max=0.2, unit="deg")
ref.add_variable("height", 0.0, vary=True, min=-0.5, max=0.5, unit="mm")
ref.tie("instrument.zero_shift", "vars.zero")
ref.tie("instrument.geometry.sample_displacement", "vars.height")
for j, n in enumerate(reflections.values()):
    theta = f"asin({wavelength} * sqrt({n}) / (2 * a_holder))"
    ref.tie(f"instrument.extra_components.{j}.center",
            expression=f"2 * {theta} * 180 / pi + zero"
                       f" - 2 * (height + offset) / {radius} * cos({theta}) * 180 / pi")

plan = rx.RefinementPlan.mccusker_structural()
names = [stage.name for stage in plan.stages]
plan.stages[names.index("zero")] = rx.Stage("zero_height", ["vars.zero", "vars.height"])
plan.stages[names.index("extra_components")] = rx.Stage(
    "holder", ["instrument.extra_components.*", "vars.a_holder", "vars.offset"])
plan.stages.insert(1, plan.stages.pop(names.index("extra_components")))

result = ref.fit(data, plan=plan, two_theta_limits=(15, 90))
for name, true in (("a_holder", A_HOLDER), ("offset", OFFSET), ("height", HEIGHT)):
    p = result.parameter(f"vars.{name}")
    print(f"{name:<8} {rx.format_su(p.value, p.stderr):<12} made with {true}")
# guide: end

# guide: phase start
as_phase = FLUORAPATITE.model_copy(deep=True)
as_phase.phases.append(ALUMINIUM.model_copy(deep=True).phases[0])
as_phase.phases[1].cell.a.value = 4.05
geometry_plan = rx.RefinementPlan.mccusker_structural()
geometry_plan.stages[1] = rx.Stage(
    "zero_height", ["instrument.zero_shift", "instrument.geometry.sample_displacement"])
phase_instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
phase_instrument.background = rx.BackgroundChebyshev.with_terms(4)
phase_result = rx.Refinement(as_phase, phase_instrument).fit(
    data, plan=geometry_plan, two_theta_limits=(15, 90))
a = phase_result.parameter("phases.1.cell.a")
print(f"a_holder {rx.format_su(a.value, a.stderr):<12} made with {A_HOLDER}")
# guide: phase end

# guide: known start
ref.set_values({"vars.a_holder": A_HOLDER})
ref.hold("vars.a_holder")
known = ref.fit(data, plan=plan, two_theta_limits=(15, 90))
for name in ("offset", "height"):
    p = known.parameter(f"vars.{name}")
    print(f"{name:<8} {rx.format_su(p.value, p.stderr)}")
# guide: known end



# 2026-11-15, darwin/arm64.
def quoted(r, name):
    p = r.parameter(name)
    return rx.format_su(p.value, p.stderr)


assert [quoted(result, f"vars.{n}") for n in ("a_holder", "offset", "height")] == [
    "4.04948(17)", "-0.1231(21)", "0.018(22)"]
assert quoted(phase_result, "phases.1.cell.a") == "4.04336(20)"
assert [quoted(known, f"vars.{n}") for n in ("offset", "height")] == ["-0.1232(17)", "0.020(12)"]
# The page: each recovered value lies within 1.5 esd of the one it was made with,
# and the holder drawn as a phase misses its cell by about 30 esd.
for name, true in (("a_holder", A_HOLDER), ("offset", OFFSET), ("height", HEIGHT)):
    p = result.parameter(f"vars.{name}")
    assert abs(p.value - true) < 1.5 * p.stderr
assert 28 < (A_HOLDER - a.value) / a.stderr < 34
# The page: zero and height trade against each other, and the fit says so.
assert any(d.code == "FLAT_DIRECTION" and set(d.where) == {"vars.zero", "vars.height"}
           for d in result.diagnostics)
# The page: knowing the holder's cell nearly halves the height's esd.
assert 0.5 < known.parameter("vars.height").stderr / result.parameter("vars.height").stderr < 0.6
# The page: the phase leaves the holder's lines misfit, and the declared lines do not.
assert round(result.statistics.gof, 2) == 1.02 and round(phase_result.statistics.gof, 2) == 1.18
