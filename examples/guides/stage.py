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
    rx.Stage("cell", ["instrument.geometry.sample_displacement", "phases.*.cell.*"]),
    rx.Stage("profile", ["instrument.profile.*"]),
]
for stage in stages:
    result = ref.run_stage(data, stage, two_theta_limits=(15, 130))
    print(f"{stage.name:<12} {result.status}  Rwp {result.statistics.rwp:.4f}")
# guide: end

# guide: reports start
structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
plan_ref = rx.Refinement(structure, instrument)
plan_ref.fit(data, plan="mccusker_default", two_theta_limits=(15, 130), stage_reports=True)

for report in plan_ref.stage_reports_:
    print(f"{report.stage:<12} Rwp {report.rwp:.4f}")
# guide: reports end

assert [s.name for s in result.stages] == ["profile"]
assert [r.stage for r in plan_ref.stage_reports_] == [
    "scale_bkg", "displacement", "cell", "profile_w", "profile"]
# The page quotes each Rwp, and compares the two ends: the hand-run plan frees
# all five widths in one stage, the preset frees `w` first.  The gap is where
# each stage fixed its windows: the hand-run result is stale, and a stage
# freeing nothing new, started from its answer, ends lower than either.
# Moved with WP-2222 (closing stage off by default, 2026-11-19): the preset
# ends at its `profile` stage, and the hand-run `profile` stage ends at 0.1028.
assert f"{result.statistics.rwp:.4f}" == "0.1028"
assert [f"{r.rwp:.4f}" for r in plan_ref.stage_reports_] == [
    "0.6050", "0.4938", "0.4921", "0.1935", "0.0994"]
assert [s.name for s in plan_ref.result_.stages][-1] == "profile"
assert result.stages[-1].window_area_tol == 0.02  # `run_stage`'s default windows
assert plan_ref.result_.stages[-1].window_area_tol is None  # a declared stage records none
assert sorted(p.path for p in result.parameters) == sorted(
    p.path for p in plan_ref.result_.parameters)
assert "FROZEN_COMPILE_STALE" in {d.code for d in result.diagnostics}
again = ref.branch().run_stage(data, rx.Stage("again", []), two_theta_limits=(15, 130))
assert f"{again.statistics.rwp:.4f}" == "0.0946"
