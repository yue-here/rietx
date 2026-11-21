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

# guide: held start
WATCHED = ("PARAMETRIC_FORM_REJECTED", "VARIABLE_NOT_FREED")
variables = {"a0": rx.Parameter(value=4.16, vary=True),
             "a1": rx.Parameter(value=0.0)}  # vary=False, the default
formula = rx.ParametricEquation(name="a", target="phases.0.cell.a", basis="expression",
                                expression="a0 + a1*(T - 600)")
held = rx.refine_multi(patterns, starting_model()[0], [starting_model()[1] for _ in patterns],
                       plan="mccusker_default", coordinates=coordinates,
                       variables=variables, parametric=[formula])
print(f"Rwp {held.statistics.rwp:.3f} against {result.statistics.rwp:.3f} with the slope free")
print(f"slope {held.parametric[1].value} +/- {held.parametric[1].esd}")
print([d.code for d in held.diagnostics if d.code in WATCHED])
# guide: held end

# guide: reach start
b_line = rx.ParametricEquation(name="b", target="phases.0.atoms.0.biso",
                               basis="polynomial", terms=[[], ["T"]])
unreached = rx.refine_multi(patterns, starting_model()[0],
                            [starting_model()[1] for _ in patterns], plan="mccusker_default",
                            coordinates=coordinates, parametric=[line, b_line])
for c in unreached.parametric:
    esd = "None" if c.esd is None else f"{c.esd:.1e}"
    print(f"{c.equation} [{c.term}] {c.value:.6g} +/- {esd}")
print([d.code for d in unreached.diagnostics if d.code in WATCHED])
# guide: reach end

# The true slope is 0.05 % of a0 per 100 K; the fitted one lies within 2 esd.
slope = result.parametric[1]
true_slope = TRUE_A[0] * 5e-4 / 100
assert abs(slope.value - true_slope) / slope.esd < 2
assert f"{true_slope:.4e}" == "2.0783e-05"
assert f"{abs(slope.value - true_slope) / slope.esd:.1f}" == "0.1"
cov = result.parametric_equations[0].covariance  # the page's intercept-slope correlation
assert f"{cov[0][1] / (cov[0][0] * cov[1][1]) ** 0.5:.3f}" == "0.001"
assert [c.term for c in result.parametric] == ["1", "T"]
assert f"{result.parametric[0].value:.10f}" == "4.1628327080"
assert f"{result.parametric[0].esd:.1e}" == "1.6e-06"
assert f"{slope.value:.10f}" == "0.0000207819" and f"{slope.esd:.1e}" == "8.2e-09"
assert result.parametric[0].unit == "Å" and slope.unit == "Å/K"
reading = result.parametric_form[0].tied
assert not reading.rejected and f"{reading.statistic:.1f}" == "9.3"
assert f"{reading.cut:.1f}" == "11.1" and reading.dof == 5
value = result.parametric_value("a", {"T": 293.0})
assert f"{value.value:.7f}" == "4.1564527" and value.outside == ["T"]
assert form.rejected and f"{form.tied.statistic:.1f}" == "498.3"

# A slope held at its start: one cell edge for every pattern, and the form test
# rejects the line.
assert f"{held.statistics.rwp:.3f}" == "0.568" and f"{result.statistics.rwp:.3f}" == "0.041"
assert held.parametric[1].term == "a1" and held.parametric[1].esd is None
assert held.parametric[1].value == 0.0
assert [d.code for d in held.diagnostics if d.code in WATCHED] == [
    "PARAMETRIC_FORM_REJECTED", "VARIABLE_NOT_FREED"]
rejected = next(d for d in held.diagnostics if d.code == "PARAMETRIC_FORM_REJECTED")
assert rejected.suggestion.startswith("No stage freed vars.a1")
# A line on a B that no stage of mccusker_default frees: both coefficients keep
# their starts, with no esd, while the cell line refines; VARIABLE_NOT_FREED says so.
b_rows = [c for c in unreached.parametric if c.equation == "b"]
assert [(f"{c.value:.6g}", c.esd, c.vary) for c in b_rows] == [("0.4", None, False),
                                                               ("0", None, False)]
assert [(f"{c.value:.6g}", f"{c.esd:.1e}") for c in unreached.parametric
        if c.equation == "a"] == [("4.16283", "1.6e-06"), ("2.07819e-05", "8.2e-09")]
assert held.parametric[1].vary is False
assert [d.code for d in unreached.diagnostics if d.code in WATCHED] == ["VARIABLE_NOT_FREED"]
idle = next(d for d in unreached.diagnostics if d.code == "VARIABLE_NOT_FREED")
assert idle.where == ["vars.b_0", "vars.b_1"]
assert not any("biso" in p.path for p in unreached.parameters)
