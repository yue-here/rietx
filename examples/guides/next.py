"""The fits behind `docs/docs/guides/next.md`: which held parameter to free next.

The page shows the lines between each pair of `guide:` markers and quotes what
they print; every quoted number is asserted at the end, so a change that moves
one fails `tests/test_examples.py`.

Data: the GSAS-II `LabData` tutorial fluorapatite, shipped in `rietx.examples`.
"""

# guide: start

import rietx as rx
from rietx.examples import examples_dir
from rietx.report import compare_freed

data = rx.read_pattern(examples_dir() / "FAP.XRA")
structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
structure.phases[0].extinction = 0.0  # declared, so suggest can weigh it
instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
instrument.background = rx.BackgroundChebyshev.with_terms(6)
ref = rx.Refinement(structure, instrument)

ref.run_stage(data, rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
              two_theta_limits=(15, 130))
ref.run_stage(data, rx.Stage("cell", ["instrument.zero_shift", "phases.*.cell.*"]))

s = ref.suggest(data)
print(f"noise floor {s.noise_floor:.0f} | best: {s.best_or_none()}")
for group in s.groups:
    paths = ", ".join(m.path for m in group.members)
    print(f"{paths:<45} gain {group.gain:8.0f}  dBIC {group.delta_bic:+6.0f}  resolved {group.resolved}")
# guide: end
at_cell = s

# guide: profile start
ref.run_stage(data, rx.Stage("profile", ["instrument.profile.*"]))

s = ref.suggest(data)
for group in s.groups[:3]:
    m = group.members[0]
    print(f"{m.path:<35} gain {group.gain:4.0f}  dBIC {group.delta_bic:+5.1f}")
# guide: profile end
at_profile = s

# guide: narrow start
s = ref.suggest(data, include="phases.*", exclude=["*.occ"])
print(s.summary)
# guide: narrow end
narrowed = s

# guide: again start
base = ref.branch()
again = base.run_stage(data, rx.Stage("again", []))
print(f"Rwp before {ref.result_.statistics.rwp:.4f}, after re-solving {again.statistics.rwp:.4f}")
# guide: again end

# guide: compare start
trial = base.branch()
trial.run_stage(data, rx.Stage("kalpha2", ["instrument.source.lines.1.weight"]))
c = compare_freed(base, trial)
for p in c.freed:
    print(f"{p.path}: {p.held_at} -> {p.value:.3f}({p.esd * 1000:.0f}), t = {p.t_ratio:+.1f}")
print(f"dBIC {c.delta_bic:+.1f} at N_eff {c.n_effective:.0f} (raw N: {c.delta_bic_raw_n:+.0f})")
# guide: compare end

# The page's warning: compare against the re-solved branch.  Since WP-2317 R7
# the `profile` stage has re-solved itself, so extinction freed from `ref` or
# from `base` stays on its floor at 0 and scores alike.
direct = ref.branch()
direct.run_stage(data, rx.Stage("extinction", ["phases.0.extinction"]))
c_direct = compare_freed(ref, direct)
paired = base.branch()
paired.run_stage(data, rx.Stage("extinction", ["phases.0.extinction"]))
c_paired = compare_freed(base, paired)
# The page's second caution: on the re-solved fit the narrowed query favours
# extinction, which sits on its floor with the data pushing it below.
narrowed_again = base.suggest(data, include="phases.*", exclude=["*.occ"])

# The page's declared-margin stage: a stage that declares its own window
# slack is never re-solved, and ends close to where the re-solve lands.
wide = rx.Refinement(rx.Structure.from_cif(examples_dir() / "fluorapatite.cif"), instrument)
wide.run_stage(data, rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
               two_theta_limits=(15, 130))
wide.run_stage(data, rx.Stage("cell", ["instrument.zero_shift", "phases.*.cell.*"]))
wide_profile = wide.run_stage(
    data, rx.Stage("profile", ["instrument.profile.*"], window_slack_deg=1.0))

# At the cell pause, four of the five groups tie an instrument width to a
# sample width, `w` stands alone, and no group is a defended winner.
assert at_cell.best_or_none() is None
assert [len(g.members) for g in at_cell.groups] == [2, 2, 1, 2, 2]
assert [g.resolved for g in at_cell.groups] == [False, False, True, False, False]
assert round(at_cell.noise_floor) == 693
assert [round(g.gain) for g in at_cell.groups] == [320387, 187891, 156393, 129080, 39422]
assert [round(g.delta_bic) for g in at_cell.groups] == [784, 329, 263, 201, 45]
# After the widths: the Kα2 weight leads, then two occupancies.
assert [g.members[0].path for g in at_profile.groups[:3]] == [
    "instrument.source.lines.1.weight", "phases.0.atoms.2.occ", "phases.0.atoms.6.occ"]
# Moved with WP-2317 R7 (the `profile` stage re-solves on fresh windows, 2026-11-27):
# gains 478, 215, 182 -> 475, 214, 181 and ΔBIC +15.7, +3.3, +1.7 -> +31.5, +10.1, +7.4.
assert [round(g.gain) for g in at_profile.groups[:3]] == [475, 214, 181]
assert [f"{g.delta_bic:+.1f}" for g in at_profile.groups[:3]] == ["+31.5", "+10.1", "+7.4"]
assert {"instrument.geometry.axial_sl", "instrument.geometry.axial_hl"} <= {
    c.path for c in at_profile.non_separable}
# Narrowed to the phase without occupancies, extinction is left, and `best_or_none`
# names it: it gates on the noise floor and on a tie.  Before WP-2317 R7 (2026-11-27)
# this query ran on the stale `profile` answer, where ΔBIC refused it (−1.8, gain
# 104.5, N_eff 915, floor 29.96); it now runs on the re-solved one.
assert narrowed.best_or_none().path == "phases.0.extinction"
assert f"{narrowed.groups[0].gain:.1f}" == "106.3"
assert f"{narrowed.groups[0].delta_bic:+.1f}" == "+1.4"
assert narrowed.groups[0].members[0].gradient > 0  # "the data push it below 0"
assert round(narrowed.n_effective) == 1297 and narrowed.n_evaluated == 24
assert round(narrowed.noise_floor, 2) == 25.31
assert sorted(c.path for c in narrowed.non_separable) == [
    "phases.0.gauss_size", "phases.0.gauss_strain", "phases.0.lor_size", "phases.0.lor_strain"]
# The re-solve, and the comparison against it.  Every figure below moved with
# WP-2222 (closing stage off by default, 2026-11-19), the stages ending at their
# own 2 % windows: Rwp 0.0970 -> 0.1022, 0.0945 -> 0.0940, 0.0952 -> 0.0947.
# WP-2317 R7: the `profile` stage re-solved itself ("4.4 %"), 0.1022 -> 0.0940.
assert f"{ref.result_.statistics.rwp:.4f}" == "0.0940"
assert f"{100 * ref.result_.stages[-1].window_refit_loss:.1f}" == "4.4"
assert f"{again.statistics.rwp:.4f}" == "0.0940"
assert f"{wide_profile.statistics.rwp:.4f}" == "0.0947"
assert wide_profile.stages[-1].window_refit_loss is None
assert round(100 * (1 - c.freed[0].value / 0.5)) == 7
assert [p.path for p in c.freed] == ["instrument.source.lines.1.weight"]
assert c.freed[0].held_at == 0.5
assert f"{c.freed[0].value:.3f}" == "0.464" and round(c.freed[0].esd * 1000) == 6
assert f"{c.freed[0].t_ratio:+.1f}" == "-6.0"
assert f"{c.delta_bic:+.1f}" == "+30.9" and round(c.n_effective) == 1295
assert round(c.delta_bic_raw_n) == 161
# The warning's numbers: extinction does not move, and with the `profile` stage
# re-solved (WP-2317 R7) both branches score it alike (+148 unpaired before).
assert c_direct.freed[0].value == 0.0 and c_paired.freed[0].value == 0.0
assert round(c_direct.delta_bic) == round(c_paired.delta_bic) == -7
assert narrowed_again.groups[0].members[0].path == "phases.0.extinction"
assert f"{narrowed_again.groups[0].delta_bic:+.1f}" == "+1.4"
assert narrowed_again.groups[0].members[0].gradient > 0  # χ² falls below the floor
assert c_paired.freed[0].t_ratio == 0.0
