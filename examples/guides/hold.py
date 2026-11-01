"""The fit behind `docs/docs/guides/hold.md`: a held cell through a plan that frees it.

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

ref = rx.Refinement(structure, instrument)
held = ref.hold("phases.0.cell.*")
result = ref.fit(data, plan="lab_bragg_brentano", two_theta_limits=(15, 130))

print(ref.fitted_structure.phases[0].cell.a.value)
for stage in result.stages:
    if stage.blocked_by_hold:
        print(stage.name, stage.blocked_by_hold)
for d in result.diagnostics:
    if d.code == "HOLD_BLOCKED_PLAN":
        print(d.message)
# guide: end

# The last stage converges on darwin and can stop on its iteration budget on
# Linux CI (2026-10-17); the page quotes no status, and the hold is the claim.
assert result.status in ("converged", "max_iter")
assert held == ["phases.0.cell.a", "phases.0.cell.alpha", "phases.0.cell.b",
                "phases.0.cell.beta", "phases.0.cell.c", "phases.0.cell.gamma"]
assert ref.fitted_structure.phases[0].cell.a.value == 9.3717
assert ref.fitted_structure.phases[0].cell.c.value == 6.8859
assert [(s.name, s.blocked_by_hold) for s in result.stages if s.blocked_by_hold] == [
    ("cell", ["phases.0.cell.a", "phases.0.cell.c"]),
    ("closing", ["phases.0.cell.a", "phases.0.cell.c"])]

# The same fit without the hold moves the cell: the plan's `cell` stage frees it.
free = rx.Refinement(rx.Structure.from_cif(examples_dir() / "fluorapatite.cif"), instrument)
free.fit(data, plan="lab_bragg_brentano", two_theta_limits=(15, 130))
a_held = ref.fitted_structure.phases[0].cell.a.value
a_free = free.fitted_structure.phases[0].cell.a.value
ppm = 1e6 * (a_held - a_free) / a_held
# 281 ppm on the compiled path and 324 on the numpy one (RIETX_COMPILED=0) on
# macOS arm64, measured 2026-10-21, and 348.5 on Linux x86-64, which became
# 351.9 once the CIF's Ca1 was read on 1/3 (WP-2037, 2026-10-24): a free cell
# lands at one of several nearby points.  Rounded to 100 ppm, that range
# straddles 350, so the line states the floor every platform clears.
print("without the hold: a moves by more than 250 ppm")
assert 250 <= ppm < 400, ppm
