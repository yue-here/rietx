"""The fits behind `docs/docs/guides/peak_equation.md`: a width, a position and an
intensity written as equations.

The page shows the lines between each pair of `guide:` markers and quotes what
they print; every quoted number is asserted at the end, so a change that moves
one fails `tests/test_examples.py`.

Data: one synthetic brucite pattern made from known coefficients, with Poisson
noise.
"""

import numpy as np

import rietx as rx

TWO_THETA = np.arange(10.0, 120.0, 0.02)
TRUE = {"w0": 0.15, "w1": 0.06, "p": 0.7, "sq": 2.4, "ln": -1.5}


def brucite(w0, w1, p):
    """Mg(OH)2 with a Lorentzian width that differs between the hk0 reflections
    and the rest, and an intensity factor on the reflections with l != 0."""
    q = rx.Parameter
    cell = rx.Cell(a=q(value=3.147), b=q(value=3.147), c=q(value=4.769),
                   alpha=q(value=90.0), beta=q(value=90.0), gamma=q(value=120.0))
    phase = rx.Phase(
        name="brucite", space_group="P -3 m 1", cell=cell, scale=q(value=2e-2),
        atoms=[rx.Atom(label="Mg", species="Mg", x=q(value=0.0), y=q(value=0.0),
                       z=q(value=0.0)),
               rx.Atom(label="O", species="O", x=q(value=1 / 3), y=q(value=2 / 3),
                       z=q(value=0.22))],
        peak_equations=[
            rx.PeakEquation(target="lor_fwhm",
                            expression="if(l == 0, w0, w1)*tan(theta)",
                            coefficients={"w0": q(value=w0, min=0.0),
                                          "w1": q(value=w1, min=0.0)}),
            rx.PeakEquation(target="intensity_factor", expression="if(l == 0, 1, p)",
                            coefficients={"p": q(value=p, min=0.0)})])
    return rx.Structure(phases=[phase])


def instrument(sq, ln):
    """A lab diffractometer whose 2θ scale bends: a calibration curve about 60°."""
    ins = rx.Instrument.bragg_brentano()
    ins.profile.w.value = 2e-3
    ins.background = rx.BackgroundChebyshev.with_terms(1)
    ins.background.coefficients[0].value = 50.0
    ins.peak_equations = [rx.PeakEquation(
        target="shift", expression="1e-5*sq*(two_theta - 60)^2 + 1e-3*ln*(two_theta - 60)",
        coefficients={"sq": rx.Parameter(value=sq), "ln": rx.Parameter(value=ln)})]
    return ins


truth = rx.Refinement(brucite(TRUE["w0"], TRUE["w1"], TRUE["p"]),
                      instrument(TRUE["sq"], TRUE["ln"]))
y = truth.predict(TWO_THETA)
data = rx.PatternData(two_theta=TWO_THETA,
                      intensity=np.random.default_rng(7).poisson(np.maximum(y, 1.0))
                      .astype(float))

# guide: start
ref = rx.Refinement(brucite(w0=0.08, w1=0.10, p=1.0), instrument(sq=0.0, ln=0.0))
equations = ["phases.*.scale", "instrument.background.*",
             "phases.*.peak_equations.*", "instrument.peak_equations.*"]
plan = rx.RefinementPlan(stages=[
    rx.Stage("scale", ["phases.*.scale", "instrument.background.*"]),
    rx.Stage("equations", equations)])
result = ref.fit(data, plan=plan)
for path in ("phases.0.peak_equations.0.w0", "phases.0.peak_equations.0.w1",
             "phases.0.peak_equations.1.p", "instrument.peak_equations.0.sq",
             "instrument.peak_equations.0.ln"):
    row = result.parameter(path)
    print(f"{path:31} {row.value:8.4f} +/- {row.stderr:.4f}")
print(f"GoF {result.statistics.gof:.2f}")
# guide: end

# guide: orbit start
q = rx.Parameter
rocksalt = rx.Phase(
    name="NaCl", space_group="F m -3 m",
    cell=rx.Cell(a=q(value=5.64), b=q(value=5.64), c=q(value=5.64),
                 alpha=q(value=90.0), beta=q(value=90.0), gamma=q(value=90.0)),
    atoms=[rx.Atom(label="Na", species="Na", x=q(value=0.0), y=q(value=0.0), z=q(value=0.0)),
           rx.Atom(label="Cl", species="Cl", x=q(value=0.5), y=q(value=0.5), z=q(value=0.5))],
    peak_equations=[rx.PeakEquation(target="lor_fwhm",
                                    expression="if(l == 0, w0, w1)*tan(theta)",
                                    coefficients={"w0": q(value=0.05), "w1": q(value=0.03)})])
try:
    rx.Refinement(rx.Structure(phases=[rocksalt]), instrument(0.0, 0.0)).predict(TWO_THETA)
except ValueError as err:
    print(err)
# guide: orbit end

# Every coefficient lies within 2 esd of the value the pattern was made with.
for path, key in (("phases.0.peak_equations.0.w0", "w0"), ("phases.0.peak_equations.0.w1", "w1"),
                  ("phases.0.peak_equations.1.p", "p"), ("instrument.peak_equations.0.sq", "sq"),
                  ("instrument.peak_equations.0.ln", "ln")):
    row = result.parameter(path)
    assert abs(row.value - TRUE[key]) < 2 * row.stderr, (path, row.value, row.stderr)
assert result.status == "converged"
worst = max(abs(result.parameter(p).value - TRUE[k]) / result.parameter(p).stderr
            for p, k in (("phases.0.peak_equations.0.w0", "w0"),
                         ("phases.0.peak_equations.0.w1", "w1"),
                         ("phases.0.peak_equations.1.p", "p"),
                         ("instrument.peak_equations.0.sq", "sq"),
                         ("instrument.peak_equations.0.ln", "ln")))
assert worst < 1.0, worst  # the page's "within 1.0 esd"
