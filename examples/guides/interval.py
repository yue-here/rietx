"""The fits behind `docs/docs/guides/interval.md`: a profile interval on a bound and off one.

The page shows the lines between each pair of `guide:` markers and quotes what
they print; every quoted number is asserted at the end, so a change that moves
one fails `tests/test_examples.py`.

Data: the GSAS-II `LabData` tutorial fluorapatite, shipped in `rietx.examples`.
"""

# guide: start

import rietx as rx
from rietx.examples import examples_dir

data = rx.read_pattern(examples_dir() / "FAP.XRA")
structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
instrument.background = rx.BackgroundChebyshev.with_terms(6)
ref = rx.Refinement(structure, instrument)
result = ref.fit(data, plan="mccusker_structural", two_theta_limits=(15, 130))

row = result.parameter("phases.0.extinction")
print(f"{row.path}  {row.value:.3f} ± {row.stderr:.3f}  at_bound {row.at_bound}")
# guide: end

# guide: interval start
interval = ref.profile_interval(data, "phases.0.extinction")
print(f"one-sided {interval.one_sided}: {interval.lower:.3f} to {interval.upper:.3f}")
# guide: interval end

# guide: biso start
biso = ref.profile_interval(data, "phases.0.atoms.0.biso")
print(f"{biso.value:.3f} ± {biso.stderr:.3f}  "
      f"one-sided {biso.one_sided}: {biso.lower:.3f} to {biso.upper:.3f}")
# guide: biso end

# The page quotes the row, both intervals, and compares each with the esd.
assert "FLOOR_HIT" in {d.code for d in result.diagnostics}
assert f"{row.value:.3f} ± {row.stderr:.3f}" == "0.000 ± 1.973"
assert interval.at_bound and interval.lower == 0.0
assert interval.lower_stop == "bound" and interval.upper_stop == "threshold"
assert f"{interval.upper:.3f}" == "0.749"
# the 1.645-esd reach a symmetric reading would give is 3.2, "more than four times as far"
assert f"{1.645 * row.stderr:.1f}" == "3.2"
assert 0.2 < interval.upper / (1.645 * row.stderr) < 0.25
assert structure.phases[0].atoms[0].label == "Ca1"
assert f"{biso.lower:.3f} to {biso.upper:.3f}" == "0.359 to 0.586"
# "1.84 esd below the value and 1.90 above"
assert f"{(biso.value - biso.lower) / biso.stderr:.2f}" == "1.84"
assert f"{(biso.upper - biso.value) / biso.stderr:.2f}" == "1.90"
assert interval.fit_is_minimum and biso.fit_is_minimum
# The working state is left where the fit put it.
assert ref.result_ is result
# "blocks no larger than about 0.9 µm": the coefficient is a squared block size
assert f"{interval.upper ** 0.5:.1f}" == "0.9"
