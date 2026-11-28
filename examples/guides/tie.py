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
# The printed block, as the page quotes it.  Moved with WP-2222 (closing stage off
# by default, 2026-11-19): Rwp 0.0898 -> 0.0893 and 0.0894, tied Biso 0.360 -> 0.377.
assert [free_result.statistics.n_free_parameters, tied_result.statistics.n_free_parameters] == [34, 32]
assert [f"{r.statistics.rwp:.4f}" for r in (free_result, tied_result)] == ["0.0893", "0.0894"]
assert [f"{p.value:.3f} ± {p.stderr:.3f}" for p in free_b] == [
    "0.264 ± 0.149", "0.467 ± 0.157", "0.385 ± 0.109"]
assert f"{tied_b[0].value:.3f} ± {tied_b[0].stderr:.3f}" == "0.376 ± 0.076"
assert [f"{g:.2f}" for g in gaps] == ["0.94", "0.66", "0.43"]
