"""The fits behind `docs/docs/guides/moment.md`: the nuclear model refitted with the moment present.

The page shows the lines between each pair of `guide:` markers and quotes what
they print; every number the page quotes or states in prose is asserted at the
end, so a change that moves one fails `tests/test_examples.py`.

Data: Cr2WO6 at 4 K and 150 K from `tests/data/`, loaded by `_cr2wo6_pair.py`
beside this script.
"""

import tempfile

# guide: reference start
from _cr2wo6_pair import BACKGROUND, CELL, ZERO, instrument, nuclear_plan, pattern, trirutile

import rietx as rx

ordered, paramagnetic = pattern(4), pattern(150)

# above T_N the pattern has no magnetic intensity, so this fit has nothing to absorb
ref150 = rx.Refinement(trirutile(), instrument())
ref150.fit(paramagnetic, plan=nuclear_plan())

# on the ordered pattern, hold that nuclear model except what the temperature moves
free = [*BACKGROUND, ZERO, CELL]
held = rx.Refinement(ref150.structure.model_copy(deep=True),
                     ref150.instrument.model_copy(deep=True))
held.fit(ordered, plan=rx.RefinementPlan(stages=[rx.Stage("lattice", free)]))

# the solver's stages free the moment and those same terms, and nothing else
plan = rx.RefinementPlan(stages=[
    rx.Stage("moduli", ["phases.*.atoms.*.moment.dof0", *free]),
    rx.Stage("moment", ["phases.*.atoms.*.moment.dof*", *free])])
reference = rx.solve_magnetic(held, ordered, sites=["Cr1"], ion="Cr3+", plan=plan)

moment = reference.best.moments[0]
print(reference.verdict, reference.best.bns_number)
print(f"|m| = {moment.magnitude:.2f} ± {moment.esd:.2f} μB")
# guide: reference end

# guide: blind start

# no paramagnetic pattern: the nuclear model is fitted on the ordered pattern itself
blind = rx.Refinement(trirutile(), instrument())
blind.fit(ordered, plan=nuclear_plan())
solution = rx.solve_magnetic(blind, ordered, sites=["Cr1"], ion="Cr3+")

moment = solution.best.moments[0]
print(solution.verdict, solution.best.bns_number)
print(f"|m| = {moment.magnitude:.1f} μB")
print(f"Biso of Cr1 = {blind.fitted_structure.phases[0].atoms[1].biso.value:.1f} Å²")
# guide: blind end

# guide: alternate start

# the winning class as a structure that carries its moment
with tempfile.TemporaryDirectory() as folder:
    cif = next(p for p in solution.write_magcifs(folder)
               if f"class{solution.best.class_index}_" in p)
    structure = rx.Structure.from_cif(cif)
structure.phases[0].scale.value = blind.fitted_structure.phases[0].scale.value
fitted_instrument = blind.fitted_instrument

# every nuclear term, and the moment, free in one stage
everything = rx.RefinementPlan(stages=[rx.Stage("all", [
    "phases.0.scale", *BACKGROUND, "phases.0.atoms.*.moment.dof*",
    "instrument.zero_shift", "phases.0.cell.*", "phases.0.atoms.*.dof.*",
    "phases.0.atoms.*.biso", *(f"instrument.profile.{k}" for k in "uvwx")],
    max_iter=200)], intermediate_ftol=1e-6)

ROUNDS = 5
previous = moment.magnitude
steps = []
for n in range(1, ROUNDS + 1):
    ref = rx.Refinement(structure.model_copy(deep=True), fitted_instrument.model_copy(deep=True))
    result = ref.fit(ordered, plan=everything)
    row = ref.report().magnetic[0]
    print(f"round {n}: |m| = {row.magnitude:.1f} μB, Rwp {result.statistics.rwp:.3f}")
    structure, fitted_instrument = ref.fitted_structure, ref.fitted_instrument
    steps.append((abs(row.magnitude - previous), row.magnitude_esd))
    if abs(row.magnitude - previous) < row.magnitude_esd:
        break
    previous = row.magnitude

scale = ref.fitted_structure.phases[0].scale
shift = scale.value - blind.fitted_structure.phases[0].scale.value
print(f"scale moved {'less' if abs(shift) < scale.stderr else 'more'} than its esd")
# guide: alternate end

# What the page says in prose, asserted here.
assert reference.verdict == solution.verdict == "solved"
assert reference.best.bns_number == solution.best.bns_number == "58.395"
assert n == 2 and row.magnitude_esd < 0.05
assert 2.08 < reference.best.moments[0].magnitude < 2.14
assert blind.fitted_structure.phases[0].atoms[1].biso.value < -1
assert abs(shift) < scale.stderr
# the three moments the "Read the result" section compares, and the two checks it names
# the blind solve stops at one of several points, and rounding picks which: 2.0300, 2.0346
# and 2.0383 on macOS arm64 under start nudges of 1e-14, and Linux's printed 2.02 (WP-2002,
# 2026-10-23), so the page prints one decimal and quotes the range
blind_m = solution.best.moments[0]
assert 2.015 < blind_m.magnitude < 2.04 and abs(blind_m.esd - 0.05) < 0.005, (blind_m.magnitude, blind_m.esd)
assert abs(reference.best.moments[0].magnitude - 2.09) < 0.005 and abs(reference.best.moments[0].esd - 0.03) < 0.005
assert abs(row.magnitude - 2.12) < 0.01 and abs(row.magnitude_esd - 0.04) < 0.006, (row.magnitude, row.magnitude_esd)
# "the blind moment is 0.05 to 0.07 and 0.09 to 0.11 μB below the other two, which agree
# within their esds"
ref_m = reference.best.moments[0]
assert 0.045 < ref_m.magnitude - blind_m.magnitude < 0.075
assert 0.085 < row.magnitude - blind_m.magnitude < 0.115
assert abs(row.magnitude - ref_m.magnitude) < row.magnitude_esd + ref_m.esd
# "about half its esd": the rounds stop at one of two points, 0.41 or 0.47 esd, and rounding
# picks which (WP-2002, 2026-10-22); the page quotes only what both share
assert 0.35 < abs(shift) / scale.stderr < 0.6
assert abs(blind.fitted_structure.phases[0].atoms[1].biso.value + 1.4) < 0.05
assert abs(ref.fitted_structure.phases[0].atoms[1].biso.value - 0.4) < 0.05
# "round 1 moves the moment by 0.07 to 0.09 μB, more than its esd of 0.04, and round 2 by less
# than its esd": round 2's step is where round 1 stopped, under 1e-5 μB on an arm64 Mac and
# 0.002 or more on some Linux runners since #1161 (WP-2036), so the page quotes the loop's rule
assert 0.06 < steps[0][0] < 0.10 and steps[0][0] > steps[0][1] and abs(steps[0][1] - 0.04) < 0.006, steps
assert steps[1][0] < steps[1][1], steps

# Holding the lattice at its 150 K values as well leaves a nuclear model that does not
# describe the 4 K pattern: Rwp 0.23 against 0.115, and the moment barely moves.
frozen = rx.Refinement(ref150.structure.model_copy(deep=True),
                       ref150.instrument.model_copy(deep=True))
frozen.fit(ordered, plan=rx.RefinementPlan(stages=[rx.Stage("background", BACKGROUND)]))
only = rx.RefinementPlan(stages=[
    rx.Stage("moduli", ["phases.*.atoms.*.moment.dof0", *BACKGROUND]),
    rx.Stage("moment", ["phases.*.atoms.*.moment.dof*", *BACKGROUND])])
lattice_held = rx.solve_magnetic(frozen, ordered, sites=["Cr1"], ion="Cr3+", plan=only)
print(f"lattice held: Rwp {lattice_held.best.rwp:.2f}, |m| = {lattice_held.best.moments[0].magnitude:.2f}")
print(f"lattice freed: Rwp {reference.best.rwp:.2f}")
assert abs(lattice_held.best.rwp - 0.23) < 0.005 and abs(reference.best.rwp - 0.115) < 0.005
assert abs(lattice_held.best.moments[0].magnitude - 2.07) < 0.03
assert abs(lattice_held.best.moments[0].magnitude - reference.best.moments[0].magnitude) < 0.05

# Freeing the profile too, as the page says.
from _cr2wo6_pair import PROFILE  # noqa: E402

wide = [*BACKGROUND, ZERO, CELL, *PROFILE]
profiled = rx.Refinement(ref150.structure.model_copy(deep=True),
                         ref150.instrument.model_copy(deep=True))
profiled.fit(ordered, plan=rx.RefinementPlan(stages=[rx.Stage("lattice", wide)]))
freed = rx.solve_magnetic(profiled, ordered, sites=["Cr1"], ion="Cr3+", plan=rx.RefinementPlan(stages=[
    rx.Stage("moduli", ["phases.*.atoms.*.moment.dof0", *wide]),
    rx.Stage("moment", ["phases.*.atoms.*.moment.dof*", *wide])]))
fm = freed.best.moments[0]
print(f"profile freed: Rwp {freed.best.rwp:.3f}, |m| = {fm.magnitude:.2f} ± {fm.esd:.2f}")
assert abs(freed.best.rwp - 0.107) < 0.005 and abs(fm.magnitude - 2.10) < 0.03 and fm.esd < 0.04
