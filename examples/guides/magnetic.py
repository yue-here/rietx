"""The fits behind `docs/docs/guides/magnetic.md`: a moment refined under a known magnetic space group.

The page shows the lines between each pair of `guide:` markers and quotes what
they print; every number the page quotes or states in prose is asserted at the
end, so a change that moves one fails `tests/test_examples.py`.

Data: LaMnO3 at 50 K from `tests/data/`, loaded by `_lamno3.py` beside this script.
"""

import math

# guide: nuclear start
from _lamno3 import BACKGROUND, LIMITS, REST, SCALE, instrument, nuclear_plan, pattern, structure

import rietx as rx

data = pattern()
nuclear = rx.Refinement(structure(), instrument())
before = nuclear.fit(data, plan=nuclear_plan(), two_theta_limits=LIMITS)
print(f"nuclear only: Rwp {before.statistics.rwp:.3f}")
# guide: nuclear end

# guide: moment start
model = nuclear.fitted_structure.model_copy(deep=True)
phase = model.phases[0]
phase.magnetic_symmetry = "62.448"   # BNS number of Pn'ma'
mn = next(atom for atom in phase.atoms if atom.label == "Mn2")
mn.moment = rx.Moment.from_values((1.0, 0.0, 1.0), "Mn3+", vary=True)
model = rx.Structure.model_validate(model.model_dump())   # re-runs the whole structure's checks
# guide: moment end

# guide: fit start
# the modulus and the polar angle; the azimuth stays at 0, which keeps the moment in the a-c plane
moment = ["phases.0.atoms.1.moment.dof0", "phases.0.atoms.1.moment.dof1"]
plan = rx.RefinementPlan(stages=[
    rx.Stage("moment", [SCALE, *BACKGROUND, *moment], max_iter=200),
    rx.Stage("everything", [SCALE, *BACKGROUND, *moment, *REST], max_iter=200)],
    intermediate_ftol=1e-6)

ref = rx.Refinement(model, nuclear.fitted_instrument.model_copy(deep=True))
result = ref.fit(data, plan=plan, two_theta_limits=LIMITS)
print(f"with the moment: Rwp {result.statistics.rwp:.3f}")
# guide: fit end

# guide: read start
row = ref.report().magnetic[0]
print(f"{row.atom} ({row.ion}): |m| = {row.magnitude:.2f} ± {row.magnitude_esd:.2f} μB,",
      "supported" if row.supported else "not supported")

polar = next(p for p in result.parameters if p.path == "phases.0.atoms.1.moment.dof1")
inside = polar.interval.lower <= math.pi / 2 <= polar.interval.upper
print(f"polar angle: esd {polar.stderr}, 95 % interval includes 90°: {inside}")
print([d.code for d in result.diagnostics if d.code.startswith("MOMENT")])
# guide: read end

# What the page says in prose, asserted here.
assert before.status == result.status == "converged"
assert abs(before.statistics.rwp - 0.138) < 0.0005, before.statistics.rwp
assert abs(result.statistics.rwp - 0.063) < 0.0005, result.statistics.rwp
assert row.supported and row.magnitude / row.magnitude_esd > 50
# "3.56 ± 0.04"; the spin-only moment of Mn3+ is 4 μB
assert abs(row.magnitude - 3.56) < 0.005 and abs(row.magnitude_esd - 0.04) < 0.005
assert row.magnitude + 3 * row.magnitude_esd < 4.0
mx, my, mz = row.crystalaxis
assert my == 0.0 or abs(my) < 1e-12, row.crystalaxis   # the held azimuth
# "about 5° short of 90°": 5.1° on an arm64 Mac, unmoved by 1e-14 nudges to the seeds
tilt = 90.0 - math.degrees(polar.value)
assert 4.5 < tilt < 5.7, tilt
# "dof1 is the angle from c": the components the report derives agree with it
assert abs(math.acos(abs(mz) / row.magnitude) - polar.value) < 1e-6
# "on this site every direction is allowed"
assert row.free_directions == ["polar", "azimuth"] and row.unmeasured_directions == []
# "P n m a forbids (010)": the nuclear fit has no reflection there
nuclear_hkl = {tuple(abs(i) for i in h) for rows in before.tick_hkl.values() for h in rows}
assert (0, 2, 0) in nuclear_hkl and (0, 1, 0) not in nuclear_hkl
assert polar.stderr is None and inside
# "the interval runs about 10° either side of 90°"
assert 8.0 < 90.0 - math.degrees(polar.interval.lower) < 12.0, polar.interval
assert 8.0 < math.degrees(polar.interval.upper) - 90.0 < 12.0, polar.interval
assert abs(mz) < 0.5 and mx > 3.5, row.crystalaxis
