"""The fit behind `docs/docs/guides/export.md`: a refinement written as a CIF and a reflection table.

The page shows the lines between each pair of `guide:` markers and quotes what
they print; every quoted number is asserted at the end, so a change that moves
one fails `tests/test_examples.py`.

Data: the GSAS-II `LabData` tutorial fluorapatite, shipped in `rietx.examples`.
"""

# guide: start

import tempfile
from pathlib import Path

import rietx as rx
from rietx.examples import examples_dir

out = Path(tempfile.mkdtemp())  # or the directory you want the files in
data = rx.read_pattern(examples_dir() / "FAP.XRA")
structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
instrument.background = rx.BackgroundChebyshev.with_terms(6)
ref = rx.Refinement(structure, instrument)
result = ref.fit(data, plan="mccusker_structural", two_theta_limits=(15, 130))

ref.write_cif(out / "fluorapatite_refined.cif")
ref.write_reflection_table(out / "fluorapatite_hkl.csv")
# guide: end

# guide: cif start
cif = (out / "fluorapatite_refined.cif").read_text(encoding="utf-8").splitlines()
for line in cif:
    if line.startswith(("data_", "_cell_length", "_cell_volume", "_space_group_name_H-M")):
        print(line)
print(sum(line == "loop_" for line in cif), "loops")
# guide: cif end

# guide: hkl start
hkl = (out / "fluorapatite_hkl.csv").read_text(encoding="utf-8").splitlines()
print("\n".join(hkl[:3]))
print(len(hkl) - 1, "rows")
# guide: hkl end

# guide: read start
back = rx.Structure.from_cif(out / "fluorapatite_refined.cif")
pattern = rx.read_pdcif(out / "fluorapatite_refined.cif")
print(back.phases[0].cell.a.value, len(pattern.two_theta))
# guide: read end

# The page quotes every printed line and counts the rows per emission line.
assert "data_fluorapatite" in cif
# "The eleven loops hold the dictionaries the file conforms to, the symmetry operations, ..."
loops = [cif[i + 1].split("_")[1] for i, line in enumerate(cif) if line == "loop_"]
assert loops == ["audit", "space", "atom", "atom", "geom", "geom", "geom", "geom", "diffrn",
                 "pd", "refln"]
rows = ref.reflection_table()
assert len(rows) == 658 and {r.line for r in rows} == {0, 1}
assert sum(r.line == 0 for r in rows) == 329
assert len(pattern.two_theta) == len(data.two_theta) == 5753
assert result.status in ("converged", "max_iter")
