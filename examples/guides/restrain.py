"""The fit behind `docs/docs/guides/restrain.md`: the phosphate group's bonds restrained.

The page shows the lines between the two `guide:` markers and quotes what they
print; every quoted number is asserted below the second marker, so a change
that moves one fails `tests/test_examples.py`.

Data: the GSAS-II `LabData` tutorial fluorapatite, shipped in `rietx.examples`.
"""

# guide: start

import rietx as rx
from rietx.examples import examples_dir
from rietx.schemas.structure import AngleRestraint, BondRestraint

data = rx.read_pattern(examples_dir() / "FAP.XRA")
structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
instrument.geometry.axial_sl.value = 0.02
instrument.geometry.axial_hl.value = 0.02
instrument.background = rx.BackgroundChebyshev.with_terms(6)

# atoms 2, 4, 5 and 6 are P3, O5, O6 and O7
structure.phases[0].restraints = [
    BondRestraint(atom_i=2, atom_j=4, target=1.54, sigma=0.01),
    BondRestraint(atom_i=2, atom_j=5, target=1.54, sigma=0.01),
    BondRestraint(atom_i=2, atom_j=6, target=1.54, sigma=0.01),
    AngleRestraint(atom_i=4, atom_j=2, atom_k=5, target_deg=109.47, sigma=1.0),
]
ref = rx.Refinement(structure, instrument)
result = ref.fit(data, plan="mccusker_structural", two_theta_limits=(15, 130))

for row in result.restraints.rows:
    print(row.kind, row.atoms, f"{row.computed:.3f}", f"{row.deviation_over_sigma:+.1f}")
for d in result.diagnostics:
    if d.code == "RESTRAINT_TENSION":
        print(d.where, d.message)
# guide: end

assert result.status == "converged"
assert [(r.kind, r.atoms, f"{r.computed:.3f}", f"{r.deviation_over_sigma:+.1f}")
        for r in result.restraints.rows] == [
    ("bond", [2, 4], "1.552", "+1.2"),
    ("bond", [2, 5], "1.574", "+3.4"),
    ("bond", [2, 6], "1.526", "-1.4"),
    ("angle", [4, 2, 5], "110.796", "+1.3"),
]
assert result.restraints.weight_scale == 1.0
tension = [d for d in result.diagnostics if d.code == "RESTRAINT_TENSION"]
assert [d.message for d in tension] == [
    "The bond restraint deviates +3.4σ from its target (1.574 vs 1.54)."]

# The page's claim that the data outweighs the restraints: the same fit with
# each σ a thousand times larger, where the rows pull on nothing, puts every
# bond within 0.002 Å of where the restrained fit put it.
loose = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
loose.phases[0].restraints = [r.model_copy(update={"sigma": r.sigma * 1000})
                              for r in structure.phases[0].restraints]
unrestrained = rx.Refinement(loose, instrument).fit(
    data, plan="mccusker_structural", two_theta_limits=(15, 130))
shift = [abs(a.computed - b.computed)
         for a, b in zip(result.restraints.rows[:3], unrestrained.restraints.rows[:3])]
print("bond shifts:", ", ".join(f"{s:.4f}" for s in shift))
assert max(shift) < 0.002
