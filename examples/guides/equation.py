"""The fits behind `docs/docs/guides/equation.md`: a cell edge declared linear in temperature.

The page shows the lines between each pair of `guide:` markers and quotes what
they print; every quoted number is asserted at the end, so a change that moves
one fails `tests/test_examples.py`.

Data: seven synthetic LaB6 patterns from `_lab6_ramp.py` beside this script,
made from a known cell at each temperature.
"""

# guide: start

from _lab6_ramp import TEMPERATURES, TRUE_A, ramp, simulate, starting_model

import rietx as rx

patterns = ramp()
structure, _ = starting_model()
instruments = [starting_model()[1] for _ in patterns]  # one per pattern

coordinates = rx.CoordinateTable(columns={"T": [float(t) for t in TEMPERATURES]},
                                 units={"T": "K"})
line = rx.ParametricEquation(name="a", target="phases.0.cell.a",
                             basis="polynomial", terms=[[], ["T"]])

result = rx.refine_multi(patterns, structure, instruments, plan="mccusker_default",
                         coordinates=coordinates, parametric=[line])
for c in result.parametric:
    print(f"[{c.term}] {c.value:.10f} +/- {c.esd:.1e} {c.unit}")
form = result.parametric_form[0]
print(f"form rejected: {form.rejected} (statistic {form.tied.statistic:.1f}, cut {form.tied.cut:.1f})")
# guide: end

# guide: value start
print(result.parametric_value("a", {"T": 293.0}))
# guide: value end

# guide: bowed start
bowed_a = [a - 9.4e-5 * (1 - ((t - 600) / 300) ** 2) for a, t in zip(TRUE_A, TEMPERATURES)]
bowed = [simulate(a, seed=11 + k) for k, a in enumerate(bowed_a)]
bent = rx.refine_multi(bowed, starting_model()[0], [starting_model()[1] for _ in bowed],
                       plan="mccusker_default", coordinates=coordinates, parametric=[line])
form = bent.parametric_form[0]
print(f"form rejected: {form.rejected} (statistic {form.tied.statistic:.1f}, cut {form.tied.cut:.1f})")
print([d.code for d in bent.diagnostics if d.code.startswith("PARAMETRIC")])
# guide: bowed end

# The true slope is 0.05 % of a0 per 100 K; the fitted one lies within 2 esd.
slope = result.parametric[1]
true_slope = TRUE_A[0] * 5e-4 / 100
assert abs(slope.value - true_slope) / slope.esd < 2
assert f"{true_slope:.4e}" == "2.0783e-05"
assert f"{abs(slope.value - true_slope) / slope.esd:.1f}" == "0.1"
cov = result.parametric_equations[0].covariance  # the page's intercept-slope correlation
assert f"{cov[0][1] / (cov[0][0] * cov[1][1]) ** 0.5:.3f}" == "0.001"
assert [c.term for c in result.parametric] == ["1", "T"]
assert f"{result.parametric[0].value:.10f}" == "4.1628327119"
assert f"{result.parametric[0].esd:.1e}" == "1.6e-06"
assert f"{slope.value:.10f}" == "0.0000207819" and f"{slope.esd:.1e}" == "8.0e-09"
assert result.parametric[0].unit == "Å" and slope.unit == "Å/K"
reading = result.parametric_form[0].tied
assert not reading.rejected and f"{reading.statistic:.1f}" == "9.3"
assert f"{reading.cut:.1f}" == "11.1" and reading.dof == 5
value = result.parametric_value("a", {"T": 293.0})
assert f"{value.value:.7f}" == "4.1564527" and value.outside == ["T"]
assert form.rejected and f"{form.tied.statistic:.1f}" == "501.5"
