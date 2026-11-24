"""The fits behind `docs/docs/guides/cell.md`: a cell quoted with its esds, and what they leave out.

The page shows the lines between each pair of `guide:` markers and quotes what
they print; every quoted number is asserted at the end, so a change that moves
one fails `tests/test_examples.py`.

Data: the GSAS-II `LabData` tutorial fluorapatite and GSAS's own refinement of
it (`FAP.EXP`), both shipped in `rietx.examples`.
"""

# guide: start

import rietx as rx
from rietx.examples import examples_dir

data = rx.read_pattern(examples_dir() / "FAP.XRA")


def refine(instrument):
    structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
    instrument.background = rx.BackgroundChebyshev.with_terms(6)
    return rx.Refinement(structure, instrument).fit(
        data, plan="mccusker_structural", two_theta_limits=(15, 130))


result = refine(rx.Instrument.bragg_brentano(radiation="CuKa"))
for path in ("phases.0.cell.a", "phases.0.cell.b", "phases.0.cell.c"):
    row = result.parameter(path)
    print(f"{path:<16} {rx.format_su(row.value, row.stderr)}  free {row.vary}")
volume = result.cell_volumes[0]
print(f"V = {rx.format_su(volume.volume, volume.stderr)} Å³")
# guide: end

# guide: inflation start
print(f"Bérar-Lelann factor {result.statistics.esd_inflation:.2f}")
# guide: inflation end

# guide: wavelength start
gsas = rx.read_gsas_exp(examples_dir() / "FAP.EXP")
tutorial = rx.Instrument.bragg_brentano(radiation="CuKa")
for line, wavelength in zip(tutorial.source.lines, gsas.histogram().wavelengths):
    line.wavelength.value = wavelength
other = refine(tutorial)

a, b = result.parameter("phases.0.cell.a"), other.parameter("phases.0.cell.a")
print(f"a with rietx's Cu Ka      {rx.format_su(a.value, a.stderr)}")
print(f"a with the tutorial's     {rx.format_su(b.value, b.stderr)}")
print(f"difference {(a.value / b.value - 1) * 1e6:.0f} ppm, {(a.value - b.value) / a.stderr:.1f} esd")
# guide: wavelength end

# The page quotes every line printed, the lambda gap, the diagonal volume esd
# and GSAS's own cell.
lam_rietx = rx.Instrument.bragg_brentano(radiation="CuKa").source.lines[0].wavelength.value
assert f"{(lam_rietx / gsas.histogram().wavelengths[0] - 1) * 1e6:.0f}" == "60"
assert result.parameter("phases.0.cell.b").vary is False
assert result.parameter("phases.0.cell.b").stderr == result.parameter("phases.0.cell.a").stderr
assert f"{volume.stderr_diagonal:.3f}" == "0.011"
assert rx.format_su(a.value, a.stderr) == "9.370962(82)"
assert rx.format_su(volume.volume, volume.stderr) == "523.629(12)"
assert f"{result.statistics.esd_inflation:.2f}" == "2.15"
assert f"{(a.value / b.value - 1) * 1e6:.0f}" == "66"
cell = gsas.phases[0].cell
assert rx.format_su(cell.a, cell.esd_a) == "9.371724(36)"
assert f"{(b.value / cell.a - 1) * 1e6:.0f}" == "-148"
