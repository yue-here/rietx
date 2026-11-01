"""The fits behind `docs/docs/guides/qpa.md`: the weight fractions of a two-phase pattern.

The page shows the lines between each pair of `guide:` markers and quotes what
they print; every quoted number is asserted at the end, so a change that moves
one fails `tests/test_examples.py`.

Data: the GSAS-II tutorial NAC (Na2Ca3Al2F14) scan from APS 11-BM with its
CaF2 impurity, and the NAC structure from COD entry 1000236, both shipped in
`rietx.examples`.
"""

# guide: start

import rietx as rx
from rietx.examples import examples_dir

data = rx.read_pattern(examples_dir() / "11BM_NAC.fxye")


def site(label, species, xyz, biso):
    x, y, z = (rx.Parameter(value=v) for v in xyz)
    return rx.Atom(label=label, species=species, x=x, y=y, z=z,
                   biso=rx.Parameter(value=biso, min=0.0, max=25.0))


def nac_and_fluorite():
    structure = rx.Structure.from_cif(examples_dir() / "cod_1000236.cif")
    structure.phases[0].name = "NAC"
    structure.phases.append(rx.Phase(
        name="CaF2", space_group="F m -3 m", cell=rx.Cell.cubic(5.4631),
        atoms=[site("Ca", "Ca2+", (0, 0, 0), 0.6), site("F", "F1-", (0.25, 0.25, 0.25), 0.9)]))
    instrument = rx.Instrument.debye_scherrer(wavelength=0.4139090)
    instrument.profile.w.value = 2e-5
    instrument.profile.x.value = 2e-3
    instrument.background = rx.BackgroundChebyshev.with_terms(6)
    return rx.Refinement(structure, instrument)


def show(result):
    for row in result.qpa.phases:
        print(f"{row.name:<5} {100 * row.weight_fraction:6.2f} ± {100 * row.weight_fraction_stderr:.2f} wt%")


ref = nac_and_fluorite()
result = ref.fit(data, plan="mccusker_structural", two_theta_limits=(2, 24))
show(result)
# guide: end

# guide: why start
for d in result.diagnostics:
    if d.code in ("HIGH_CORRELATION", "FLOOR_HIT"):
        print(d.code, "|", d.message)
# guide: why end

# guide: hold start
held = nac_and_fluorite()
held.hold(["phases.1.extinction", "phases.1.atoms.*.biso"])
held_result = held.fit(data, plan="mccusker_structural", two_theta_limits=(2, 24))
show(held_result)
# guide: hold end

# guide: profile start
profile = held.profile_fraction(data, "CaF2", axes=["phases.1.lor_strain"])
print(f"admissible {100 * profile.range_low:.2f} to {100 * profile.range_high:.2f} wt%,"
      f" {len(profile.points)} refits")
# guide: profile end

# guide: brindley start
radii = nac_and_fluorite()
radii.hold(["phases.1.extinction", "phases.1.atoms.*.biso"])
radii.structure.phases[0].particle_radius_um = 5.0
radii.structure.phases[1].particle_radius_um = 2.0
corrected = radii.fit(data, plan="mccusker_structural", two_theta_limits=(2, 24))
for row in corrected.qpa.phases:
    print(f"{row.name:<5} µR {row.mu_r:.4f}  {100 * row.weight_fraction:.2f} ->"
          f" {100 * row.weight_fraction_corrected:.2f} wt%")
# guide: brindley end

# The page quotes every printed line; these pin the claims its prose makes.
assert result.qpa.crystalline_only
assert f"{100 * result.qpa.phases[1].weight_fraction:.1f}" == "3.6"
assert "HIGH_CORRELATION" in {d.code for d in result.diagnostics}
assert result.statistics.rwp < held_result.statistics.rwp
assert f"{result.statistics.rwp:.3f}, {held_result.statistics.rwp:.3f}" == "0.082, 0.089"
assert "HOLD_BLOCKED_PLAN" in {d.code for d in held_result.diagnostics}
assert f"{100 * held_result.qpa.phases[1].weight_fraction:.2f}" == "1.37"
assert profile.fit_admissible and profile.excess < 1.0
assert [d.code for d in profile.diagnostics] == ["QPA_FRACTION_RANGE"]
default = nac_and_fluorite().fit(data, plan="mccusker_default", two_theta_limits=(2, 24))
assert f"{100 * default.qpa.phases[1].weight_fraction:.2f}" == "1.38"
assert abs(sum(row.weight_fraction for row in held_result.qpa.phases) - 1.0) < 1e-12
