"""The fits behind `docs/docs/guides/calibrate.md`: a profile from a standard, reused on a sample.

The page shows the lines between each pair of `guide:` markers and quotes what
they print; every quoted number is asserted at the end, so a change that moves
one fails `tests/test_examples.py`.

Data: synthetic LaB6 standards and CeO2 samples on two lab setups, from
`_calibration_pair.py` beside this script.
"""

# guide: start

import tempfile
from pathlib import Path

from _calibration_pair import lab6, sample, standard

import rietx as rx

work = Path(tempfile.mkdtemp())

instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
instrument.background = rx.BackgroundChebyshev.with_terms(4)
instrument.geometry.axial_hl.value = 3 / 200  # receiving slit height / goniometer radius
calibration = rx.Refinement(lab6(), instrument)
calibration.hold(["phases.0.cell.*", "instrument.geometry.axial_hl"])
calibrated = calibration.fit(standard("first"), plan="lab_calibrate")

for name in "uvwxy":
    p = calibrated.parameter(f"instrument.profile.{name}")
    print(f"{name} {rx.format_su(p.value, p.stderr)}")
# guide: end

# guide: check start
for d in calibrated.diagnostics:
    print(d)
# guide: check end

# guide: reuse start
rx.save_instrument_profile(calibration.instrument, work / "first.json")

from _calibration_pair import ceo2  # noqa: E402


def refine_sample(profile, data):
    instrument = rx.load_instrument_profile(profile)
    instrument.background = rx.BackgroundChebyshev.with_terms(4)
    return rx.Refinement(ceo2(), instrument).fit(data, plan="lab_sample_refine")


def show(label, result):
    terms = {t.path: t for t in result.microstructure[0].terms}
    size, strain = terms["phases.0.lor_size"], terms["phases.0.lor_strain"]
    print(f"{label:<28} size {rx.format_su(size.value, size.esd)} Å  "
          f"strain {rx.format_su(strain.value, strain.esd)}  Rwp {result.statistics.rwp:.4f}")


matched = refine_sample(work / "first.json", sample("first"))
show("first profile, first sample", matched)
# guide: reuse end

# guide: mismatch start
second = rx.Refinement(lab6(), instrument)
second.hold(["phases.0.cell.*", "instrument.geometry.axial_hl"])
second.fit(standard("second"), plan="lab_calibrate")
rx.save_instrument_profile(second.instrument, work / "second.json")

crossed = {"second profile, first sample": refine_sample(work / "second.json", sample("first")),
           "first profile, second sample": refine_sample(work / "first.json", sample("second"))}
for label, result in crossed.items():
    show(label, result)
# guide: mismatch end

from _calibration_pair import AXIAL_HL, AXIAL_SL, SETUPS, TRUE_SIZE, TRUE_STRAIN  # noqa: E402

# 2026-10-21, darwin/arm64, identical on RIETX_COMPILED=0.
assert AXIAL_HL == 3 / 200
# The page: swapping the two axial ratios gives the same pattern to the bit, so
# refined together the data cannot choose their order, and nothing is said.
swapped_setup = rx.Instrument.bragg_brentano(radiation="CuKa")
pair = [swapped_setup.model_copy(deep=True) for _ in range(2)]
for inst, (sl, hl) in zip(pair, [(AXIAL_SL, AXIAL_HL), (AXIAL_HL, AXIAL_SL)]):
    inst.geometry.axial_sl.value, inst.geometry.axial_hl.value = sl, hl
first_standard = standard("first")
patterns = [rx.Refinement(lab6(), inst).predict(first_standard.two_theta) for inst in pair]
assert (patterns[0] == patterns[1]).all()
both = rx.Refinement(lab6(), instrument)
both.hold("phases.0.cell.*")
both_result = both.fit(first_standard, plan="lab_calibrate")
ratios = [both_result.parameter(f"instrument.geometry.axial_{n}") for n in ("sl", "hl")]
assert [rx.format_su(p.value, p.stderr) for p in ratios] == ["0.02476(78)", "0.01542(87)"]
assert [d.code for d in both_result.diagnostics] == ["HIGH_CORRELATION"]
assert "axial" not in str(both_result.diagnostics[0].where)
widths = [calibrated.parameter(f"instrument.profile.{n}") for n in "uvwxy"]
assert [rx.format_su(p.value, p.stderr) for p in widths] == [
    "0.00399(17)", "-0.00293(25)", "0.002957(83)", "0.01483(37)", "0.02018(88)"]
# The page: each lies within one esd of the instrument that made the data.
assert all(abs(p.value - true) < p.stderr for p, true in zip(widths, SETUPS["first"]))
assert [d.code for d in calibrated.diagnostics] == ["HIGH_CORRELATION", "HOLD_BLOCKED_PLAN"]
zero = calibrated.parameter("instrument.zero_shift")
displacement = calibrated.parameter("instrument.geometry.sample_displacement")
assert rx.format_su(zero.value, zero.stderr) == "0.01976(61)"
assert rx.format_su(displacement.value, displacement.stderr) == "-0.0006(14)"


def reading(result, path):
    return next(t for t in result.microstructure[0].terms if t.path == path)


size, strain = reading(matched, "phases.0.lor_size"), reading(matched, "phases.0.lor_strain")
assert (rx.format_su(size.value, size.esd), rx.format_su(strain.value, strain.esd)) == (
    "300.7(23)", "0.001016(44)")
assert abs(size.value - TRUE_SIZE) < size.esd and abs(strain.value - TRUE_STRAIN) < strain.esd
# The page: the second calibration finds the second setup's wider W and X.
assert [round(getattr(second.instrument.profile, n).value, 4) for n in "wx"] == [0.0059, 0.0305]
# The page: a crossed profile moves the size by eight to ten esd (9.5 and 8.6),
# and Rwp stays within 0.001 of the matched fit.
for result in crossed.values():
    off = reading(result, "phases.0.lor_size")
    assert 8 < abs(off.value - TRUE_SIZE) / off.esd < 10.5
    assert abs(result.statistics.rwp - matched.statistics.rwp) < 0.001
wide_on_first, first_on_wide = crossed.values()
# The page: the same two FLOOR_HIT findings as the matched fit, on the Gaussian
# size and strain the sample does not have.
assert [d.code for d in matched.diagnostics] == ["FLOOR_HIT", "FLOOR_HIT"]
assert sorted(p for d in matched.diagnostics for p in d.where) == [
    "phases.0.gauss_size", "phases.0.gauss_strain"]
assert [d.code for d in wide_on_first.diagnostics] == [d.code for d in matched.diagnostics]
gauss = reading(first_on_wide, "phases.0.gauss_size")
assert rx.format_su(gauss.value, gauss.esd) == "1440(200)"
assert reading(first_on_wide, "phases.0.gauss_strain").value > 0
assert first_on_wide.diagnostics == []

import shutil  # noqa: E402

shutil.rmtree(work)  # the two saved profiles
