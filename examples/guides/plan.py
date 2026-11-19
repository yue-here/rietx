"""The fit behind `docs/docs/guides/plan.md`: a preset with one stage added.

The page shows the lines between the two `guide:` markers and quotes what they
print; every quoted number is asserted below the second marker, so a change
that moves one fails `tests/test_examples.py`.

Data: the GSAS-II `LabData` tutorial fluorapatite, shipped in `rietx.examples`.
"""

# guide: start

import rietx as rx
from rietx.examples import examples_dir

data = rx.read_pattern(examples_dir() / "FAP.XRA")
structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
instrument.background = rx.BackgroundChebyshev.with_terms(6)

plan = rx.RefinementPlan.mccusker_default()
plan.stages.append(rx.Stage("biso", ["phases.*.atoms.*.biso"]))

ref = rx.Refinement(structure, instrument)
result = ref.fit(data, plan=plan, two_theta_limits=(15, 130))

for stage in result.stages:
    print(f"{stage.name:<12} {len(stage.freed):>2} freed  {stage.status}")
# guide: end

assert result.status == "converged"
assert [(s.name, len(s.freed)) for s in result.stages] == [
    ("scale_bkg", 7), ("zero", 1), ("cell", 2), ("profile_w", 1), ("profile", 4),
    ("biso", 7)]
