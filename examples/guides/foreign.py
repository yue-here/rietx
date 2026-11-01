"""The fit behind `docs/docs/guides/foreign.md`: a GSAS experiment opened, refined and written out.

The page shows the lines between each pair of `guide:` markers and quotes what
they print; every quoted number is asserted at the end, so a change that moves
one fails `tests/test_examples.py`.

Data: the GSAS-II `LabData` tutorial fluorapatite and GSAS's own refinement of
it (`FAP.EXP`), both shipped in `rietx.examples`.
"""

# guide: start

import tempfile
from pathlib import Path

import rietx as rx
from rietx.examples import examples_dir

notes = []
model = rx.read_project_model(examples_dir() / "FAP.EXP", diagnostics=notes)
histogram = model.stated.histogram()
print(model.format.name, "| data", histogram.data_file, "| wavelengths", histogram.wavelengths)
print("stated Rwp", model.stated.rwp)
for note in notes:
    print(note.code)
# guide: end

# guide: refine start
structure = model.to_structure()
instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
for line, wavelength in zip(instrument.source.lines, histogram.wavelengths):
    line.wavelength.value = wavelength
instrument.background = rx.BackgroundChebyshev.with_terms(6)

data = rx.read_pattern(examples_dir() / "FAP.XRA")
ref = rx.Refinement(structure, instrument)
result = ref.fit(data, plan="mccusker_structural", two_theta_limits=(15, 130))
print(f"rietx Rwp {result.statistics.rwp:.4f}")
# guide: refine end

# guide: write start
out = Path(tempfile.mkdtemp())  # or the directory you want the files in
rx.write_topas_inp(ref.fitted_structure, out / "fap.inp", free=ref, scale="topas",
                   instrument=ref.fitted_instrument, pattern=data)
rx.write_fullprof_pcr(ref.fitted_structure, out / "fap.pcr", instrument=ref.fitted_instrument,
                      write_zero_shift=True)
rx.write_gsas2_phase_cif(ref.fitted_structure, out / "fap_gsas2.cif")
rx.write_gsas2_instprm(ref.fitted_instrument, out / "fap.instprm")

for name in ("fap.inp", "fap.pcr"):
    print(name, rx.identify_project_format(out / name).name)
# guide: write end

# The page quotes every printed line and names the data file TOPAS's input points at.
assert [n.code for n in notes] == ["GSAS_EXP_BACKGROUND_NOT_CARRIED"]
assert f"{result.statistics.rwp:.4f}" == "0.0953"
# "The fit here can be written because its extinction ended at 0."
assert ref.fitted_structure.phases[0].extinction.value == 0.0
assert model.stated.rwp == 0.1005
assert (out / "fap.xye").exists()
assert '"fap.xye"' in (out / "fap.inp").read_text(encoding="utf-8")
assert rx.read_project_model(out / "fap.pcr").format.name == "fullprof_pcr"
