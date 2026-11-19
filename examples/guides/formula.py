"""The fit behind `docs/docs/guides/formula.md`: two cell edges as Einstein functions of temperature, sharing one θ.

The page shows the lines between each pair of `guide:` markers and quotes what
they print; every quoted number is asserted at the end, so a change that moves
one fails `tests/test_examples.py`.

Data: seven synthetic rutile patterns from 100 K to 1000 K, made here from a
known a(T) and c(T) under the instrument and noise of `_lab6_ramp.py`.
"""

import tempfile
from pathlib import Path

import numpy as np

import rietx as rx

TEMPERATURES = [100.0, 250.0, 400.0, 550.0, 700.0, 850.0, 1000.0]
A0, GA, C0, GC, THETA = 4.5870, 0.0172, 2.9540, 0.0141, 500.0  # Å, Å, Å, Å, K
TWO_THETA = np.arange(3.0, 24.0, 0.005)
CIF = (
    "data_rutile\n_space_group_name_H-M_alt 'P 42/m n m'\n"
    f"_cell_length_a {A0}\n_cell_length_b {A0}\n_cell_length_c {C0}\n"
    "_cell_angle_alpha 90\n_cell_angle_beta 90\n_cell_angle_gamma 90\n"
    "loop_\n_atom_site_label\n_atom_site_type_symbol\n_atom_site_fract_x\n"
    "_atom_site_fract_y\n_atom_site_fract_z\n_atom_site_B_iso_or_equiv\n"
    "Ti1 Ti 0 0 0 0.4\nO1 O 0.3048 0.3048 0 0.5\n")

with tempfile.TemporaryDirectory() as work:
    path = Path(work) / "rutile.cif"
    path.write_text(CIF, encoding="utf-8")
    RUTILE = rx.Structure.from_cif(path)


def einstein(zero, grad, t):
    return zero + grad / np.expm1(THETA / t)


def simulate(t, seed):
    """One pattern of the true specimen at temperature `t`, with Poisson noise."""
    structure = RUTILE.model_copy(deep=True)
    cell = structure.phases[0].cell
    cell.a.value = cell.b.value = einstein(A0, GA, t)
    cell.c.value = einstein(C0, GC, t)
    structure.phases[0].scale.value = 5e-4
    instrument = rx.Instrument.debye_scherrer(wavelength=0.4139)
    instrument.zero_shift.value = 0.008
    instrument.profile.w.value = 2.5e-4
    instrument.background = rx.BackgroundChebyshev.with_terms(3)
    for coefficient, value in zip(instrument.background.coefficients, (40.0, -6.0, 1.5)):
        coefficient.value = value
    y = rx.Refinement(structure, instrument).predict(TWO_THETA)
    counts = np.random.default_rng(seed).poisson(np.maximum(y, 1.0)).astype(float)
    return rx.PatternData(two_theta=TWO_THETA, intensity=counts)


def starting_instrument():
    instrument = rx.Instrument.debye_scherrer(wavelength=0.4139)
    instrument.profile.w.value = 2.5e-4 * 1.5
    instrument.background = rx.BackgroundChebyshev.with_terms(3)
    return instrument


patterns = [simulate(t, seed=31 + k) for k, t in enumerate(TEMPERATURES)]
structure = RUTILE.model_copy(deep=True)
instruments = [starting_instrument() for _ in patterns]

# guide: start
coordinates = rx.CoordinateTable(columns={"T": TEMPERATURES}, units={"T": "K"})
variables = {
    "a0": rx.Parameter(value=4.587, vary=True, unit="Å"),
    "ga": rx.Parameter(value=0.01, vary=True, unit="Å"),
    "c0": rx.Parameter(value=2.954, vary=True, unit="Å"),
    "gc": rx.Parameter(value=0.01, vary=True, unit="Å"),
    "theta": rx.Parameter(value=400.0, vary=True, min=50.0, max=2000.0, unit="K"),
}
equations = [
    rx.ParametricEquation(name="a", target="phases.0.cell.a", basis="expression",
                          expression="a0 + ga/(exp(theta/T) - 1)"),
    rx.ParametricEquation(name="c", target="phases.0.cell.c", basis="expression",
                          expression="c0 + gc/(exp(theta/T) - 1)"),
]
joint = rx.MultiHistogramRefinement(
    structure, instruments, coordinates=coordinates, variables=variables,
    parametric=equations,
    sharing=rx.SharingMap(shared=["instrument.zero_shift", "instrument.profile.*"]))
for preview in joint.preview_equations():
    low, high = preview.span
    print(f"{preview.name}: {low:.5f} to {high:.5f} Å, reads {preview.variables}")
# guide: end

# guide: fit start
result = joint.fit(patterns, plan="mccusker_default")
rows = {p.path: p for p in result.parameters}
for name in variables:
    row = rows[f"vars.{name}"]
    print(f"{name} = {row.value:.7g} +/- {row.stderr:.2g}")
print([f.rejected for f in result.parametric_form])
# guide: fit end

# guide: value start
print(result.parametric_value("c", {"T": 300.0}))
# guide: value end

# Every variable lies within 2 esd of its truth, and the page quotes these.
truth = {"a0": A0, "ga": GA, "c0": C0, "gc": GC, "theta": THETA}
z = {n: (rows[f"vars.{n}"].value - t) / rows[f"vars.{n}"].stderr for n, t in truth.items()}
assert all(abs(v) < 2 for v in z.values()), z
assert result.status == "converged"
assert f"{rows['vars.theta'].value:.7g}" == "500.1692" and f"{rows['vars.theta'].stderr:.2g}" == "0.61"
assert f"{rows['vars.ga'].value:.7g}" == "0.01720567"
assert [f.rejected for f in result.parametric_form] == [False, False]
assert f"{result.parametric_value('c', {'T': 300.0}).value:.7f}" == "2.9572836"
