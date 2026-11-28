"""The fits behind `docs/docs/guides/stage.md`: a plan run by hand, and a report per stage.

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

stages = [
    rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
    rx.Stage("cell", ["instrument.zero_shift", "phases.*.cell.*"]),
    rx.Stage("profile", ["instrument.profile.*"]),
]
for stage in stages:
    result = ref.run_stage(data, stage, two_theta_limits=(15, 130))
    print(f"{stage.name:<10} {result.status}  Rwp {result.statistics.rwp:.4f}")
# guide: end

# guide: reports start
structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
plan_ref = rx.Refinement(structure, instrument)
plan_ref.fit(data, plan="mccusker_default", two_theta_limits=(15, 130), stage_reports=True)

for report in plan_ref.stage_reports_:
    print(f"{report.stage:<10} Rwp {report.rwp:.4f}")
# guide: reports end

assert [s.name for s in result.stages] == ["profile"]
assert [r.stage for r in plan_ref.stage_reports_] == [
    "scale_bkg", "zero", "cell", "profile_w", "profile"]
# The page quotes each Rwp, and compares the two ends: the hand-run plan frees
# all five widths in one stage, the preset frees `w` first.  The gap is where
# each stage fixed its windows: the hand-run result is stale, and a stage
# freeing nothing new, started from its answer, ends lower than either.
# Moved with WP-2222 (closing stage off by default, 2026-11-19): the preset
# ends at its `profile` stage, 0.0945 -> 0.0988, the hand-run `profile` stage
# 0.0970 -> 0.1022 and the extra stage 0.0945 -> 0.0940.  Moved with WP-2317 R7
# (a stage past its window fraction re-solves on fresh windows, and a stage a later
# one refits sizes its slack from what it frees, 2026-11-27): the hand-run `profile`
# stage 0.1022 -> 0.0940, the preset's stages 0.6050, 0.4921, 0.4920, 0.1932, 0.0988
# -> 0.6063, 0.4926, 0.4923, 0.1944, 0.0939.
assert f"{result.statistics.rwp:.4f}" == "0.0940"
assert [f"{r.rwp:.4f}" for r in plan_ref.stage_reports_] == [
    "0.6063", "0.4926", "0.4923", "0.1944", "0.0939"]
# "4.4 %" and "3.4 %"
assert f"{100 * result.stages[-1].window_refit_loss:.1f}" == "4.4"
assert f"{100 * plan_ref.result_.stages[-1].window_refit_loss:.1f}" == "3.4"

assert [s.name for s in plan_ref.result_.stages][-1] == "profile"
assert result.stages[-1].window_area_tol == 0.02  # `run_stage`'s default windows
assert plan_ref.result_.stages[-1].window_area_tol is None  # a declared stage records none
assert sorted(p.path for p in result.parameters) == sorted(
    p.path for p in plan_ref.result_.parameters)
assert "FROZEN_COMPILE_STALE" not in {d.code for d in result.diagnostics}
again = ref.branch().run_stage(data, rx.Stage("again", []), two_theta_limits=(15, 130))
assert f"{again.statistics.rwp:.4f}" == "0.0940"
