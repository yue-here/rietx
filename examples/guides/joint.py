"""The fits behind `docs/docs/guides/joint.md`: one structure against an X-ray and a neutron pattern.

The page shows the lines between each pair of `guide:` markers and quotes what
they print; every quoted number is asserted at the end, so a change that moves
one fails `tests/test_examples.py`.

Data: a synthetic corundum pair from `_corundum_pair.py` beside this script.
"""

# guide: start

from _corundum_pair import LAM_N, LAM_X, corundum, neutron_pattern, xray_pattern

import rietx as rx

xray = rx.Instrument.debye_scherrer(wavelength=LAM_X)
neutron = rx.Instrument.constant_wavelength_neutron(LAM_N, fwhm_deg=0.3)
patterns = [xray_pattern(), neutron_pattern()]

alone = [rx.Refinement(corundum(), instrument).fit(data, plan="mccusker_structural")
         for instrument, data in zip([xray, neutron], patterns)]
for name, result in zip(["X-ray", "neutron"], alone):
    a = result.parameter("phases.0.cell.a")
    print(f"{name:<8} a = {rx.format_su(a.value, a.stderr)} Å")
# guide: end

# guide: joint start
plan = rx.RefinementPlan.mccusker_structural()
plan.stages.append(rx.Stage("wavelength", ["hist.1.instrument.source.lines.0.wavelength"]))

joint = rx.MultiHistogramRefinement(corundum(), [xray, neutron])
result = joint.fit(patterns, plan=plan)
for d in result.histograms[1].diagnostics:
    if d.code == "WAVELENGTH_CALIBRATION":
        print(d)
# guide: joint end

# guide: esd start
for path in ("phases.0.atoms.0.z", "phases.0.atoms.1.x"):
    x, n, j = (r.parameter(path) for r in (*alone, result))
    print(f"{path}  X-ray {rx.format_su(x.value, x.stderr)}  "
          f"neutron {rx.format_su(n.value, n.stderr)}  joint {rx.format_su(j.value, j.stderr)}")
# guide: esd end

from _corundum_pair import CELL, NEUTRON_TRUE, TRUTH  # noqa: E402

# 2026-10-21, darwin/arm64.
cells = [r.parameter("phases.0.cell.a") for r in alone]
assert [rx.format_su(p.value, p.stderr) for p in cells] == ["4.7588824(41)", "4.757487(31)"]
assert round((cells[1].value / cells[0].value - 1) * 1e6) == -293  # "293 ppm short"
lam = result.parameter("hist.1.instrument.source.lines.0.wavelength")
# The page: within an esd of the 300 ppm the pattern was made with, 5.1 ppm a esd.
assert abs(lam.value - NEUTRON_TRUE) < lam.stderr
assert round(lam.stderr / LAM_N * 1e6, 1) == 5.1
# "and the shared cell 1.4 esd from the true one"
a = result.parameter("phases.0.cell.a")
assert f"{abs(a.value - CELL[0]) / a.stderr:.1f}" == "1.4"
assert [d.code for d in result.histograms[1].diagnostics if d.code == "WAVELENGTH_CALIBRATION"] == [
    "WAVELENGTH_CALIBRATION"]
# The page: every coordinate within 2 esd of the truth, and the esd ratios.
for path in ("phases.0.atoms.0.z", "phases.0.atoms.1.x"):
    p = result.parameter(path)
    assert abs(p.value - TRUTH[path]) < 2 * p.stderr, path
esd = {path: [r.parameter(path).stderr for r in (*alone, result)]
       for path in ("phases.0.atoms.0.z", "phases.0.atoms.1.x")}
(x_al, n_al, j_al), (x_o, n_o, j_o) = esd.values()
assert round(n_al / x_al, 1) == 3.6 and round(n_o / x_o, 2) == 0.95
assert round(j_al / x_al, 2) == 0.96 and round(j_o / x_o, 2) == 0.67
# The page: with the neutron wavelength held, a ends 2.6 esd off and both
# coordinates' esds are worse than the X-ray pattern's alone, with nothing said.
held = rx.MultiHistogramRefinement(corundum(), [xray, neutron]).fit(patterns, plan="mccusker_structural")
held_a = held.parameter("phases.0.cell.a")
assert round(abs(held_a.value - CELL[0]) / held_a.stderr, 1) == 2.6
assert round(held.parameter("phases.0.atoms.1.x").stderr / x_o, 1) == 1.2
assert round(held.parameter("phases.0.atoms.0.z").stderr / x_al, 1) == 1.7
assert "WAVELENGTH_CALIBRATION" not in {d.code for h in held.histograms for d in h.diagnostics}
# The page: freeing both wavelengths is refused.
both = rx.RefinementPlan.mccusker_structural()
both.stages.append(rx.Stage("wavelength", ["hist.*.instrument.source.lines.0.wavelength"]))
try:
    rx.MultiHistogramRefinement(corundum(), [xray, neutron]).fit(patterns, plan=both)
except ValueError as refusal:
    assert str(refusal).startswith("2 of 2 wavelengths are free; hold one.")
else:
    raise AssertionError("both wavelengths free was not refused")
