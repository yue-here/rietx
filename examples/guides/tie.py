"""The fits behind `docs/docs/guides/tie.md`: three oxygens' Biso, free and tied.

The page shows the lines between the two `guide:` markers and quotes what they
print; every quoted number is asserted below the second marker, so a change
that moves one fails `tests/test_examples.py`.

Data: the GSAS-II `LabData` tutorial fluorapatite, shipped in `rietx.examples`.
"""

# guide: start

import rietx as rx
from rietx.examples import examples_dir

data = rx.read_pattern(examples_dir() / "FAP.XRA")


def refinement() -> rx.Refinement:
    structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
    instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
    instrument.geometry.axial_sl.value = 0.02
    instrument.geometry.axial_hl.value = 0.02
    instrument.background = rx.BackgroundChebyshev.with_terms(6)
    return rx.Refinement(structure, instrument)


OXYGENS = ["phases.0.atoms.4.biso", "phases.0.atoms.5.biso", "phases.0.atoms.6.biso"]

free = refinement()
free_result = free.fit(data, plan="mccusker_structural", two_theta_limits=(15, 130))

tied = refinement()
tied.tie_equal(OXYGENS)
tied_result = tied.fit(data, plan="mccusker_structural", two_theta_limits=(15, 130))

for result in (free_result, tied_result):
    print(result.statistics.n_free_parameters, f"{result.statistics.rwp:.4f}")
    for path in OXYGENS:
        p = result.parameter(path)
        print(f"  {path}  {p.value:.3f} ± {p.stderr:.3f}")
# guide: end

# Each pair of free values, in units of their combined esd.
free_b = [free_result.parameter(path) for path in OXYGENS]
gaps = [abs(i.value - j.value) / (i.stderr**2 + j.stderr**2) ** 0.5
        for i, j in ((free_b[0], free_b[1]), (free_b[0], free_b[2]), (free_b[1], free_b[2]))]
print("pair gaps:", ", ".join(f"{g:.2f}" for g in gaps))

assert free_result.status == tied_result.status == "converged"
assert free_result.statistics.n_free_parameters - tied_result.statistics.n_free_parameters == 2
tied_b = [tied_result.parameter(path) for path in OXYGENS]
assert len({(p.value, p.stderr) for p in tied_b}) == 1
# The page's claims: the tied esd is under the smallest free one, Rwp moves in
# its fourth figure at most, and no free pair differs by two combined esds.
assert tied_b[0].stderr < min(p.stderr for p in free_b)
assert abs(tied_result.statistics.rwp - free_result.statistics.rwp) < 5e-4
assert max(gaps) < 2.0
# The printed block, as the page quotes it.
assert [free_result.statistics.n_free_parameters, tied_result.statistics.n_free_parameters] == [35, 33]
assert [f"{r.statistics.rwp:.4f}" for r in (free_result, tied_result)] == ["0.0898", "0.0898"]
assert [f"{p.value:.3f} ± {p.stderr:.3f}" for p in free_b] == [
    "0.242 ± 0.150", "0.467 ± 0.160", "0.363 ± 0.114"]
assert f"{tied_b[0].value:.3f} ± {tied_b[0].stderr:.3f}" == "0.360 ± 0.079"
assert [f"{g:.2f}" for g in gaps] == ["1.02", "0.64", "0.53"]
