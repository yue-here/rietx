"""The colleague's script the placement round hands every cell, as `fit.py`.

A plausible fluorapatite refinement with two choices a reviewer would query: the
`lab_bragg_brentano` plan, atoms added, frees zero and sample displacement together, and a
24-term Chebyshev background is flexible enough to reach an ADP. Its printed
output is `fit_output.txt` in the workspace, and it fires the codes
`runner.EPISODE_CODES` names (PROTOCOL.md § The episode and § Amendment, 2026-10-24).

Data: `FAP.XRA` and `fluorapatite.cif`, the GSAS-II LabData tutorial pair
(`tests/data/README.md` has their provenance). Nothing here is part of the
round's instrument except its output, which is why it is written as a user
would write it and not as a harness would.
"""

import rietx as rx

data = rx.read_pattern("FAP.XRA")
structure = rx.Structure.from_cif("fluorapatite.cif")

instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
instrument.geometry.axial_sl.value = 0.02
instrument.geometry.axial_hl.value = 0.02
instrument.background = rx.BackgroundChebyshev.with_terms(24)

# The lab plan, with the atoms freed before its last (roughness) stage.
plan = rx.RefinementPlan.lab_bragg_brentano()
plan.stages.insert(-1, rx.Stage("structure", ["phases.*.atoms.*.dof.*",
                                              "phases.*.atoms.*.biso"]))

ref = rx.Refinement(structure, instrument)
result = ref.fit(data, plan=plan, two_theta_limits=(15, 130))

print(f"status {result.status}   Rwp {result.statistics.rwp:.4f}   "
      f"GoF {result.statistics.gof:.2f}")
print()
for path in ("phases.0.cell.a", "phases.0.cell.c",
             "instrument.zero_shift", "instrument.geometry.sample_displacement",
             "instrument.geometry.axial_sl", "instrument.geometry.axial_hl"):
    p = result.parameter(path)
    print(f"{path:42s} {p.value:12.6f} +/- {p.stderr:.6f}")
for i, atom in enumerate(structure.phases[0].atoms):
    p = result.parameter(f"phases.0.atoms.{i}.biso")
    print(f"{atom.label:4s} Biso {p.value:8.4f} +/- {p.stderr:.4f}")
print()
for d in result.diagnostics:
    print(d.level, d.code, d.where, d.message, "->", d.suggestion)
