"""The time-of-flight abscissa: the schema, the readers, and the refusals.

Three things are asserted here, and the third is the one this build rests on.

**A pattern's axis is a declaration, not a measurement.**  A flight time of
1000-10 000 µs is a perfectly plausible 10-100° scan: it is strictly
increasing, it is smooth, it has peaks in it, and every check ``PatternData``
applied before it had a ``tof`` field passes on it unchanged.  So every test below that
establishes an axis establishes it from a *field a file filled in* — a GSAS
bintype, a Mantid header line — and the negative controls are the cases where
the numbers look like one thing and the declaration says another.

**The constant-wavelength path did not move.**  ``test_readers.py`` and the
acceptance suite are the real proof of that; what is here is the one assertion
they cannot make, that a ``CONS`` bank with a time-of-flight comment pasted into
it still reads as an angle.

**Every entry point that computes a pattern refuses a TOF one, in words.**
Not "raises" — `ValueError` is what a trig error is too — but with a message
that names the axis, its unit and the door that closed.  This build reads a
bank and refines none, so the fence is only worth what its message is.

**Every fixture here is synthetic.**  None of the real banks that established
the conventions is vendored; the numbers they established are in the module
docstrings of ``io/formats/gsas.py`` and ``io/instrument_tof.py``, and the
arithmetic is reproduced here on hand-written 10-channel banks.
"""

from __future__ import annotations

import numpy as np
import pytest

import rietx as rx
from rietx import read_gsas2_instprm
from rietx.io.formats.gsas import gsas_banks
from rietx.io.instrument_tof import read_gsas_tof_iparm
from rietx.schemas.instrument import ProfileTOF, TOFSource
from rietx.schemas.pattern import PatternData, require_two_theta

#: A bank of ten channels, spelled once.  Small on purpose: every arithmetic
#: below is checkable by hand from these numbers, which is what a synthetic
#: fixture is for.
N = 10

#: Si, a = 5.431 Å — the standard every TOF calibration is refined against, and
#: the one the measured verification used.  Only the first few reflections are
#: needed to show a d axis coming back.
SI_A = 5.431
SI_HKL = ((1, 1, 1), (2, 2, 0), (3, 1, 1), (4, 0, 0), (3, 3, 1))


def si_d() -> list[float]:
    return [SI_A / np.sqrt(h * h + k * k + ll * ll) for h, k, ll in SI_HKL]


# ---------------------------------------------------------------------------
# the schema
# ---------------------------------------------------------------------------

def test_a_pattern_carries_exactly_one_abscissa():
    """Both or neither is refused, and the message says which mistake it was.

    The validator is the only thing standing between a caller and a pattern
    whose axis is *two* quantities — which is not a richer pattern, it is a
    claim that some conversion was applied that nobody checked.
    """
    with pytest.raises(ValueError, match="exactly one abscissa"):
        PatternData(intensity=[1.0, 2.0])
    with pytest.raises(ValueError, match="not both"):
        PatternData(two_theta=[1.0, 2.0], tof=[1000.0, 1001.0],
                    intensity=[1.0, 2.0])
    with pytest.raises(ValueError, match="and neither was given"):
        PatternData(intensity=[1.0, 2.0], sigma=[1.0, 1.0])


def test_the_axis_is_read_off_the_field_and_never_off_the_values():
    """The discriminator, and the trap it exists for.

    These two patterns hold *the same numbers*.  Nothing about 1000-1009 says
    microsecond and nothing says degree; only the field that was filled in
    does, and ``axis`` reports that and nothing else.
    """
    numbers = [1000.0 + i for i in range(N)]
    y = [float(i) for i in range(N)]
    angle = PatternData(two_theta=numbers, intensity=y)
    time = PatternData(tof=numbers, intensity=y)
    assert angle.axis == "two_theta" and time.axis == "tof"
    assert angle.axis_unit == "degrees"
    assert "microsecond" in time.axis_unit
    assert np.array_equal(angle.x(), time.x())


def test_tt_refuses_a_tof_pattern_and_tof_us_refuses_a_2theta_one():
    """The typed views, and why there are two of them beside ``x()``.

    ``tt()`` was total before the axis existed and most modules call it.  Making it
    raise is what turns "this package assumes an angle" from a fact nobody can
    see into a message at the boundary.
    """
    time = PatternData(tof=[1000.0, 1001.0], intensity=[1.0, 2.0])
    angle = PatternData(two_theta=[10.0, 10.1], intensity=[1.0, 2.0])
    with pytest.raises(ValueError, match="time of flight in microseconds"):
        time.tt()
    with pytest.raises(ValueError, match="2θ in degrees, not a time of flight"):
        angle.tof_us()
    assert np.array_equal(time.tof_us(), [1000.0, 1001.0])
    assert np.array_equal(angle.tt(), [10.0, 10.1])
    # x() is the one that works on both, and returns the same array as the
    # typed view does where the typed view works at all
    assert np.array_equal(time.x(), time.tof_us())
    assert np.array_equal(angle.x(), angle.tt())


def test_the_validator_names_the_axis_it_is_talking_about():
    """A refusal about a TOF pattern that says "two_theta" is a wrong statement.

    The CW spellings are unchanged, which is what keeps every existing message
    the sentence it was.
    """
    with pytest.raises(ValueError, match="two_theta must be strictly increasing"):
        PatternData(two_theta=[2.0, 1.0], intensity=[1.0, 2.0])
    with pytest.raises(ValueError, match="tof must be strictly increasing"):
        PatternData(tof=[2000.0, 1000.0], intensity=[1.0, 2.0])
    with pytest.raises(ValueError, match="tof and intensity differ in length"):
        PatternData(tof=[1000.0, 1001.0], intensity=[1.0])
    with pytest.raises(ValueError, match="sigma length does not match tof"):
        PatternData(tof=[1000.0, 1001.0], intensity=[1.0, 2.0], sigma=[1.0])


def test_json_round_trips_both_axes_exactly():
    """The compatibility promise's own check, one axis at a time.

    Exact, not approximate: a pattern that survives a project save and reload
    with its last digit moved is a pattern whose fingerprint no longer matches
    the history it was recorded against.
    """
    for kwargs in ({"two_theta": [10.0 + 0.01 * i for i in range(N)]},
                   {"tof": [1000.0 + 1.5 * i for i in range(N)]}):
        original = PatternData(intensity=[float(i) for i in range(N)],
                               sigma=[1.0] * N, **kwargs)
        again = PatternData.model_validate_json(original.model_dump_json())
        assert again.axis == original.axis
        assert again.two_theta == original.two_theta
        assert again.tof == original.tof
        assert again.model_dump_json() == original.model_dump_json()


def test_crop_and_the_mask_work_on_the_axis_as_measured():
    """Both preserve the kind, and both quote their bounds in its own unit.

    A cropped TOF pattern that came back as 2θ would be the same defect as a
    reader that folded microseconds by 100 — silent, and wrong by a factor.
    """
    time = PatternData(tof=[1000.0 + 10.0 * i for i in range(N)],
                       intensity=[float(i) for i in range(N)],
                       excluded_regions=[(1020.0, 1040.0)])
    cropped = time.crop(1010.0, 1050.0)
    assert cropped.axis == "tof"
    assert cropped.two_theta is None
    assert cropped.tof == [1010.0, 1020.0, 1030.0, 1040.0, 1050.0]
    assert list(time.in_range_mask()) == [
        True, True, False, False, False, True, True, True, True, True]


def test_a_synthetic_bank_converts_back_to_the_d_spacings_it_was_built_from():
    """The positive arm of the axis round trip, on numbers with no file.

    Built forwards from known constants and Si d-spacings, then inverted — so
    what is tested is the relation and its iterative inverse, with the reading
    of a real file's constants tested separately below.  DIFA is deliberately
    non-zero: with DIFA = DIFB = 0 the inverse is one division and proves
    nothing about the iteration.
    """
    source = TOFSource(difc=5123.45, difa=-1.23, tzero=-12.34, difb=0.0,
                       two_theta_bank_deg=61.20)
    d = np.array(si_d())
    back = source.d_from_tof(source.tof_from_d(d))
    assert np.allclose(back, d, atol=1e-9)
    # and the fourth term is not ignored: difB moves the answer
    with_b = TOFSource(difc=5123.45, difa=-1.23, tzero=-12.34, difb=12.5,
                       two_theta_bank_deg=61.20)
    assert not np.allclose(with_b.tof_from_d(d), source.tof_from_d(d))
    assert np.allclose(with_b.d_from_tof(with_b.tof_from_d(d)), d, atol=1e-9)


def test_a_bank_that_is_not_a_bank_is_refused():
    # the bound is a fence on the Parameter itself, so a DIFC of zero is
    # refused before the model validator ever sees it
    with pytest.raises(ValueError, match=r"lies outside bounds \[1.0"):
        TOFSource(difc=0.0, two_theta_bank_deg=90.0)
    with pytest.raises(ValueError, match="difc must be positive"):
        TOFSource(difc=rx.Parameter(value=-5.0, min=-10.0),
                  two_theta_bank_deg=90.0)
    with pytest.raises(ValueError, match="two_theta_bank_deg"):
        TOFSource(difc=1000.0, two_theta_bank_deg=200.0)
    with pytest.raises(ValueError, match="l2_m is a flight path"):
        TOFSource(difc=1000.0, two_theta_bank_deg=90.0, l2_m=-1.0)


def test_a_bare_number_is_a_held_profile_coefficient():
    """``ProfileTOF`` coerces a float exactly as ``TOFSource`` does.

    A profile coefficient arrives from a ``.iparm`` ``PRCF`` block or from a
    seed table as a plain float far more often than as a refinement
    declaration, and ``ProfileTOF(alpha1=0.45)`` reading as a validation
    error where ``TOFSource(difc=5123.45)`` beside it did not would be a
    papercut every caller hits.  Held, like
    every calibration read from a file: it was refined against a standard.
    """
    coerced = ProfileTOF(alpha1=0.45)
    assert coerced.alpha1 == rx.Parameter(value=0.45, vary=False, unit="A/us")
    assert coerced == ProfileTOF(
        alpha1=rx.Parameter(value=0.45, vary=False, unit="A/us"))

    # every field, and the unit is the field's own default rather than a
    # second table: a coerced coefficient and a defaulted one describe
    # themselves the same way
    for name in ProfileTOF.model_fields:
        one = getattr(ProfileTOF(**{name: 1.25}), name)
        assert (one.value, one.vary) == (1.25, False)
        assert one.unit == getattr(ProfileTOF(), name).unit

    # a Parameter passed in inherits what it left out, unit included -- the
    # rule every class with a declared range follows (WP-1321,
    # ``_InheritsDeclaredDefaults``), so the two spellings are one table
    bare = ProfileTOF(alpha1=rx.Parameter(value=0.45))
    assert bare.alpha1.unit == "A/us" and bare == coerced
    assert TOFSource(difc=5123.45, two_theta_bank_deg=61.2).difc == rx.Parameter(
        value=5123.45, vary=False, unit="us/A", min=1.0)

    # …and the coercion is for numbers only: a bool is not a coefficient and
    # a string is still refused
    with pytest.raises(ValueError):
        ProfileTOF(alpha1="0.45")
    with pytest.raises(ValueError):
        ProfileTOF(alpha1=True)


def test_a_coerced_profile_is_the_same_table_as_a_declared_one():
    """The coercion is a constructor convenience and nothing more: the two
    spellings must reach the parameter table as the same rows."""
    from rietx.params.vector import ParameterTable

    prof = dict(alpha1=0.45, beta0=0.055, beta1=0.003, sig1=300.0)
    floats = ProfileTOF(**prof)
    # a coerced coefficient carries the field's own bounds as well as its
    # unit: the σ triple is floored at zero, and a
    # coercion that dropped that would leave the floor reachable only by a
    # caller who typed the whole Parameter out
    params = ProfileTOF(**{k: rx.Parameter(
        value=v, unit=(d := getattr(ProfileTOF(), k)).unit, min=d.min,
        max=d.max) for k, v in prof.items()})
    assert floats == params

    structure, _ = _si()
    rows = []
    for pr in (floats, params):
        ins = rx.Instrument.tof_neutron_bank(
            difc=12000.0, tzero=-5.0, two_theta_bank_deg=90.0, profile=pr)
        rows.append([(e.path, e.value, e.lo, e.hi)
                     for e in ParameterTable(structure, ins).entries])
    assert rows[0] == rows[1]


def test_the_factory_builds_a_frozen_bank_beside_the_cw_neutron_one():
    bank = rx.Instrument.tof_neutron_bank(
        difc=5123.45, difa=-1.23, tzero=-12.34, two_theta_bank_deg=61.20,
        l1_m=32.0, l2_m=2.50)
    assert bank.source.kind == "neutron_tof"
    assert bank.geometry.kind == "debye_scherrer"
    assert bank.source.difb.value == 0.0
    assert not any(getattr(bank.source, n).vary
                   for n in ("difc", "difa", "tzero", "difb"))
    # the neutron facts the CW arm states, restated where a caller reads them
    assert bank.source.polarization.value == 1.0
    assert bank.source.dispersion is None
    assert bank.source.harmonics_supported is False


def test_the_capabilities_arm_grows_a_third_radiation_and_does_not_call_it_one_line():
    """A white beam has no line list, and reporting ``max_emission_lines = 1``
    would be the one wrong statement a derived table could make about it.

    The note is what a client reads to decide whether to hand the build a
    bank, so it may not overstate the answer: it says the arm is read and that
    no flight-time forward model exists here.
    """
    arms = {r.kind: r for r in rx.capabilities().radiations}
    assert set(arms) == {"xray_cw", "neutron_cw", "neutron_tof"}
    tof = arms["neutron_tof"]
    assert tof.max_emission_lines is None
    assert tof.harmonic_contamination is False
    assert tof.anomalous_dispersion is False
    note = tof.scatterer.lower()
    assert "flight time" in note
    assert "read" in note and "refines none" in note


# ---------------------------------------------------------------------------
# the readers
# ---------------------------------------------------------------------------

def time_map_bank(path, *, nchan=N, clock_ns=100.0, first=20000, step=10,
                  flag="ESD"):
    """A ``TIME_MAP`` bank of ``nchan`` channels with one map segment.

    Written the way a real one is: the map first (which is what pushes a real
    file's first ``BANK`` record past the 4 kB sniff window), triples of
    (first channel, flight time, step) in clock ticks on an 8-character field,
    then the terminating flight time at the last channel's start.
    """
    terminator = first + (nchan - 1) * step
    values = [1, first, step, terminator]
    table = "".join(f"{v:8d}" for v in values)
    rows = []
    if flag == "ESD":
        for i in range(0, nchan, 5):
            rows.append("".join(f"{float(10 + j):8.1f}{float(1 + j):8.1f}"
                                for j in range(i, min(i + 5, nchan))))
    else:  # STD, counts only
        rows.append("".join(f"{float(10 + j):8.1f}" for j in range(nchan)))
    path.write_text(
        "a synthetic TIME_MAP bank\n"
        f"TIME_MAP    1    4    1 TIME_MAP  {clock_ns:g}\n"
        f"{table}\n"
        f"BANK   1  {nchan} {len(rows)} TIME_MAP  1 {flag}\n"
        + "\n".join(rows) + "\n", encoding="utf-8")
    return path


def fxye_bank(path, xs, *, bintype="RALF", coefficients="35328 141 35328 0.004"):
    rows = [f"{x:15.5f}{1.0 + i:15.5f}{0.5:15.5f}" for i, x in enumerate(xs)]
    path.write_text(
        "a synthetic Mantid-style bank\n"
        f"BANK 1 {len(xs)} {len(xs)} {bintype} {coefficients} FXYE\n"
        + "\n".join(rows) + "\n", encoding="utf-8")
    return path


def test_a_time_map_bank_reads_as_a_flight_time_from_its_own_step_table(tmp_path):
    """The tabulated arithmetic, checkable by hand.

    Channel *i* (1-based) starts at 20000 + (i−1)·10 ticks and is 10 ticks
    wide; the value returned is the bin **centre**, start + step/2, converted
    at 100 ns per tick.  So channel 1 is (20000 + 5)·100/1000 = 2000.5 µs, and
    channel 10 is (20090 + 5)·100/1000 = 2009.5 µs.
    """
    data = rx.read_pattern(str(time_map_bank(tmp_path / "time_map.gsa")))
    assert data.axis == "tof"
    assert data.two_theta is None
    assert len(data.tof) == N
    assert data.tof[0] == pytest.approx(2000.5)
    assert data.tof[-1] == pytest.approx(2009.5)
    # an ESD bank's second column is the esd, whatever its bintype
    assert data.sigma == [1.0 + i for i in range(N)]


def test_a_time_map_bank_reads_its_counts_only_layout_too(tmp_path):
    """``STD`` is what a bank stating no flag means, and it takes the fallback."""
    data = rx.read_pattern(str(time_map_bank(tmp_path / "std.gsa", flag="STD")))
    assert data.axis == "tof" and len(data.tof) == N
    assert data.sigma is None
    assert data.sig()[0] == pytest.approx(np.sqrt(10.0))


def test_the_clock_width_comes_from_the_record_and_is_not_assumed(tmp_path):
    """It is the whole conversion to microseconds, and it is per file."""
    slow = rx.read_pattern(str(time_map_bank(tmp_path / "slow.gsa",
                                             clock_ns=1000.0)))
    assert slow.tof[0] == pytest.approx(20005.0)


def test_a_time_map_whose_terminator_disagrees_with_the_bank_is_refused(tmp_path):
    """The one internal check the format offers, and it is used.

    A map read one field out of step still produces a perfectly plausible
    axis, so the terminator agreeing with the last triple's extrapolation to
    the bank's declared channel count is what licenses the parse.
    """
    p = time_map_bank(tmp_path / "bad.gsa")
    text = p.read_text(encoding="utf-8").replace(f"{20000 + 9 * 10:8d}", f"{99999:8d}")
    p.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="terminates at 99999"):
        rx.read_pattern(str(p))


def test_a_time_map_bank_naming_a_map_the_file_does_not_hold_is_refused(tmp_path):
    p = time_map_bank(tmp_path / "missing.gsa")
    p.write_text(p.read_text(encoding="utf-8").replace("TIME_MAP  1 ESD",
                                                   "TIME_MAP  7 ESD"),
                 encoding="utf-8")
    with pytest.raises(ValueError, match="names TIME_MAP 7"):
        rx.read_pattern(str(p))


def test_a_ralf_or_slog_bank_reads_its_own_x_column_as_microseconds(tmp_path):
    """The fold is taken off the bintype, as the manual states it.

    The manual says an FXYE x column is "centidegrees for CW data or
    microseconds for TOF data", so only a CW bank is divided by 100.  These
    same bytes under ``CONS`` are the positive control in the test below.
    """
    xs = [1106.19950 * 1.004 ** i for i in range(N)]
    for bintype in ("RALF", "SLOG"):
        data = rx.read_pattern(str(fxye_bank(tmp_path / f"{bintype}.gss", xs,
                                             bintype=bintype)))
        assert data.axis == "tof"
        assert data.tof[0] == pytest.approx(1106.19950, abs=1e-5)
        assert data.tof[-1] == pytest.approx(xs[-1], abs=1e-5)
        assert len(data.tof) == N


def test_the_same_bytes_under_cons_are_still_folded_by_a_hundred(tmp_path):
    """The positive control for the fold, and for the CW path staying put."""
    xs = [1106.19950 * 1.004 ** i for i in range(N)]
    data = rx.read_pattern(str(fxye_bank(tmp_path / "cons.gsa", xs,
                                         bintype="CONS",
                                         coefficients="110620 44")))
    assert data.axis == "two_theta"
    assert data.two_theta[0] == pytest.approx(11.0619950, abs=1e-7)


def test_a_ralf_bank_of_esd_pairs_is_refused_rather_than_approximated(tmp_path):
    """The near-miss refusal, and it names the layout that works.

    The axis would have to be integrated from the four coefficients, and the
    manual's own word for a RALF step is "irregularly".
    """
    p = tmp_path / "ralf_esd.gsa"
    rows = ["".join(f"{float(10 + j):8.1f}{1.0:8.1f}" for j in range(5))
            for _ in range(2)]
    p.write_text(
        "a synthetic RALF bank of ESD pairs\n"
        f"BANK 1 {N} 2 RALF 35328 141 35328 0.004 ESD\n"
        + "\n".join(rows) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="only from a layout that states"):
        rx.read_pattern(str(p))


@pytest.mark.parametrize("bintype", ["LOG6", "COND", "CONQ", "LPSD", "EDS"])
def test_the_remaining_bintypes_are_still_refused_by_name(tmp_path, bintype):
    """And the message now says what the two readable quantities are."""
    p = fxye_bank(tmp_path / f"{bintype}.gsa", [1.0 * i + 1 for i in range(N)],
                  bintype=bintype)
    with pytest.raises(ValueError) as exc:
        rx.read_pattern(str(p))
    message = str(exc.value)
    assert bintype in message
    assert "neither a 2θ nor a TOF" in message


def test_a_file_mixing_a_cons_bank_and_a_time_map_bank_is_refused(tmp_path):
    """Negative control (iii): which bank was written first must not decide
    what the pattern's abscissa *means*."""
    p = tmp_path / "mixed.gsa"
    p.write_text(
        "a file with two kinds of axis\n"
        "TIME_MAP    1    4    1 TIME_MAP  100\n"
        f"{1:8d}{20000:8d}{10:8d}{20090:8d}\n"
        "BANK 1 4 1 CONS 1000 20 STD\n"
        "    10.0    11.0    12.0    13.0\n"
        "BANK 2 4 1 TIME_MAP 1 STD\n"
        "    10.0    11.0    12.0    13.0\n", encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        rx.read_pattern(str(p))
    assert "not all on the same quantity" in str(exc.value)
    assert "2θ in degrees" in str(exc.value)
    assert "flight time in microseconds" in str(exc.value)


def test_several_banks_of_one_kind_need_one_named(tmp_path):
    """Same axis, several banks — a choice, and it is the caller's.

    The reader used to return bank 1 and calling that "the pattern" was harmless only
    while every readable bank was a 2θ scan of one specimen.  A bank is a
    *detector*, and a six-bank Mantid ``SaveGSS`` file is six of them, so the
    file is now refused naming what it holds and ``bank=`` is what chooses.
    """
    p = tmp_path / "three.gsa"
    banks = "".join(f"BANK {i} 4 1 CONS {1000 * i} 20 STD\n"
                    "    10.0    11.0    12.0    13.0\n"
                    for i in range(1, 4))
    p.write_text("three CONS banks\n" + banks, encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        rx.read_pattern(str(p))
    assert "holds 3 banks (1, 2, 3)" in str(exc.value)
    # and each one is reachable by the number its own record declares: bank 2's
    # start angle is 2000 centidegrees, bank 3's 3000
    assert rx.read_pattern(str(p), bank=2).two_theta[0] == pytest.approx(20.0)
    assert rx.read_pattern(str(p), bank=3).two_theta[0] == pytest.approx(30.0)


def six_bank_ralf(path, *, nchan=N):
    """A six-bank Mantid-style ``SaveGSS`` file, the shape ISIS GEM exports.

    Each bank starts at its own flight time and steps in its own pseudo-Δt/t,
    so which bank a read returned is visible in the first channel alone — the
    property a synthetic fixture needs here, since a real six-bank GEM export
    established this and is not vendored.
    Mantid's own between-bank comment line goes in too: it is what the body
    loop has to skip rather than treat as a terminator.
    """
    rows = []
    for bank in range(1, 7):
        first = 1000.0 * bank
        step = 1.0 + 0.001 * bank
        xs = [first * step ** i for i in range(nchan)]
        rows.append(f"BANK {bank} {nchan} {nchan} RALF "
                    f"{int(first * 32)} {int(step * 32)} {int(first * 32)} "
                    f"{step - 1.0:.5f} FXYE")
        rows.extend(f"{x:15.5f}{1.0 + i:15.5f}{0.5:15.5f}"
                    for i, x in enumerate(xs))
        rows.append(f"# Data for spectrum :{bank - 1}")
    path.write_text("Y3Al5O12 synthetic\n"
                    "# File generated by Mantid:\n"
                    "# with Y multiplied by the bin widths.\n"
                    + "\n".join(rows) + "\n", encoding="utf-8")
    return path


def test_a_six_bank_file_is_refused_until_a_bank_is_named(tmp_path):
    """The measured failure: unreachable past bank 1, and silently so.

    ``read_gsas`` returned the first ``BANK`` record for its whole life and
    took no bank argument, so the ordinary ISIS GEM export was unreachable
    past bank 1 — a real refinement was worked around by splitting such a
    file into six single-bank files by hand.  Contrast
    :func:`~rietx.io.instrument_tof.read_gsas_tof_iparm`, which has always
    returned ``{bank: Instrument}`` for exactly the stated reason: a TOF
    diffractometer *is* several banks.  The data reader and the instrument
    reader no longer disagree about what a file is.
    """
    p = six_bank_ralf(tmp_path / "gem.gss")
    with pytest.raises(ValueError) as exc:
        rx.read_pattern(str(p))
    message = str(exc.value)
    assert "holds 6 banks (1, 2, 3, 4, 5, 6)" in message
    assert "bank=" in message and "gsas_banks" in message


def test_each_bank_comes_back_by_the_number_its_record_declares(tmp_path):
    """By declared number, never by position: it is the number every other
    file of the experiment uses (a ``.iparm``'s ``INS  3ICONS``)."""
    p = six_bank_ralf(tmp_path / "gem.gss")
    for bank in range(1, 7):
        data = rx.read_pattern(str(p), bank=bank)
        assert data.axis == "tof"
        assert len(data.tof) == N
        assert data.tof[0] == pytest.approx(1000.0 * bank, abs=1e-4)


def test_a_bank_the_file_does_not_hold_is_refused_naming_the_ones_it_does(tmp_path):
    p = six_bank_ralf(tmp_path / "gem.gss")
    with pytest.raises(ValueError) as exc:
        rx.read_pattern(str(p), bank=9)
    assert "no BANK 9" in str(exc.value)
    assert "1, 2, 3, 4, 5, 6" in str(exc.value)


def test_gsas_banks_lists_what_there_is_to_choose_between(tmp_path):
    """The listing a caller needs *before* naming a bank, and it is honest
    about which quantity each range is on."""
    banks = gsas_banks(str(six_bank_ralf(tmp_path / "gem.gss")))
    assert [b.number for b in banks] == [1, 2, 3, 4, 5, 6]
    assert {b.bintype for b in banks} == {"RALF"}
    assert {b.type_flag for b in banks} == {"FXYE"}
    assert {b.n_channels for b in banks} == {N}
    assert {b.axis for b in banks} == {"tof"}
    assert all(b.refused is None for b in banks)
    lo, hi = banks[2].x_range
    assert lo == pytest.approx(3000.0, abs=1e-4)
    assert hi == pytest.approx(3000.0 * 1.003 ** (N - 1), abs=1e-4)


def test_gsas_banks_reports_a_bank_it_cannot_read_rather_than_raising(tmp_path):
    """A listing must not fail on account of one bank nobody asked for.

    The bank refused here is the near-miss case: ``RALF`` binning constants
    under an ``ESD`` layout, where the axis would have to be integrated.  It
    still raises from :func:`read_gsas` — only the *enumeration* reports it.
    """
    p = tmp_path / "mixed_layouts.gsa"
    good = [f"{1000.0 * 1.001 ** i:15.5f}{1.0 + i:15.5f}{0.5:15.5f}"
            for i in range(N)]
    esd = ["".join(f"{float(10 + j):8.1f}{1.0:8.1f}" for j in range(5))
           for _ in range(2)]
    p.write_text(
        "two RALF banks in two layouts\n"
        f"BANK 1 {N} {N} RALF 32000 32 32000 0.00100 FXYE\n"
        + "\n".join(good) + "\n"
        + f"BANK 2 {N} 2 RALF 32000 32 32000 0.00100 ESD\n"
        + "\n".join(esd) + "\n", encoding="utf-8")
    banks = gsas_banks(str(p))
    assert banks[0].refused is None and banks[0].x_range is not None
    assert banks[1].x_range is None
    assert "only from a layout that states" in banks[1].refused
    with pytest.raises(ValueError, match="only from a layout that states"):
        rx.read_pattern(str(p), bank=2)


def test_a_mixed_axis_file_stays_refused_however_the_bank_is_named(tmp_path):
    """``bank=`` chooses a record; it cannot make a file that disagrees with
    itself about its own abscissa agree."""
    p = tmp_path / "mixed.gsa"
    p.write_text(
        "a file with two kinds of axis\n"
        "TIME_MAP    1    4    1 TIME_MAP  100\n"
        f"{1:8d}{20000:8d}{10:8d}{20090:8d}\n"
        "BANK 1 4 1 CONS 1000 20 STD\n"
        "    10.0    11.0    12.0    13.0\n"
        "BANK 2 4 1 TIME_MAP 1 STD\n"
        "    10.0    11.0    12.0    13.0\n", encoding="utf-8")
    for bank in (None, 1, 2):
        with pytest.raises(ValueError, match="not all on the same quantity"):
            rx.read_pattern(str(p), bank=bank)


def test_a_bank_option_on_a_format_that_has_no_banks_is_reported(tmp_path):
    """``READER_OPTION_IGNORED``'s rule, reached by the new option: a caller
    who passed ``bank=2`` believed they had selected something."""
    p = tmp_path / "plain.xy"
    p.write_text("\n".join(f"{10.0 + 0.1 * i} {100.0}" for i in range(20)),
                 encoding="utf-8")
    diagnostics: list = []
    rx.read_pattern(str(p), bank=2, diagnostics=diagnostics)
    assert any(d.code == "READER_OPTION_IGNORED" and "bank=2" in d.message
               for d in diagnostics)


def test_a_mantid_header_makes_an_xye_a_flight_time(tmp_path):
    """The stated unit, verbatim from a POWGEN export."""
    p = tmp_path / "pg3.xye"
    rows = "\n".join(f"{7000.0 + 3.0 * i:15.5f}{1.0 + i:15.5f}{0.5:10.5f}"
                     for i in range(N))
    p.write_text("' File generated by Mantid:\n"
                 "' Instrument: POWGEN\n"
                 "' The X-axis unit is: Time-of-flight\n"
                 "' The Y-axis unit is: Counts per microAmp.hour\n"
                 + rows + "\n", encoding="utf-8")
    data = rx.read_pattern(str(p))
    assert data.axis == "tof"
    assert data.tof[0] == pytest.approx(7000.0)
    assert data.metadata["x_label"] == "Time-of-flight"


def test_a_bare_three_column_file_is_unchanged(tmp_path):
    """No declaration, no change: this is the behaviour every existing `.xye`
    fixture depends on, restated where the new branch could have taken it."""
    p = tmp_path / "plain.xye"
    # σ varies by channel, so the constant-σ check has nothing to say either
    p.write_text("\n".join(f"{10.0 + 0.02 * i} {i} {1.0 + 0.1 * i}"
                           for i in range(N)) + "\n", encoding="utf-8")
    notes = []
    data = rx.read_pattern(str(p), diagnostics=notes)
    assert data.axis == "two_theta"
    assert notes == []


def test_a_flight_time_mentioned_but_not_stated_is_read_as_2theta_and_says_so(tmp_path):
    """A mention is not a declaration.

    "tof" appears in file names and provenance comments, and flipping the
    abscissa on a substring would change what every number in a file means on
    the strength of a coincidence.  So the axis does not move — and the reader
    does not go quiet either.
    """
    p = tmp_path / "hint.xye"
    p.write_text("# Time-of-flight    Y    E\n"
                 + "\n".join(f"{10.0 + 0.02 * i} {i} {1.0 + 0.1 * i}"
                              for i in range(N))
                 + "\n", encoding="utf-8")
    notes = []
    data = rx.read_pattern(str(p), diagnostics=notes)
    assert data.axis == "two_theta"
    assert [n.code for n in notes] == ["PATTERN_X_AXIS_ASSUMED"]
    assert "state no x-axis unit" in notes[0].message


@pytest.mark.parametrize(
    ("unit", "what"),
    [("dSpacing", "d-spacing"), ("MomentumTransfer", "momentum transfer"),
     ("Wavelength", "wavelength"), ("Energy", "energy")])
def test_a_stated_unit_that_is_neither_axis_is_refused_by_name(tmp_path, unit, what):
    p = tmp_path / f"{unit}.xye"
    p.write_text(f"# The X-axis unit is: {unit}\n"
                 + "\n".join(f"{1.0 + 0.02 * i} {i}" for i in range(N)) + "\n",
                 encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        rx.read_pattern(str(p))
    assert unit in str(exc.value) and what in str(exc.value)


def test_a_cons_bank_with_a_tof_comment_pasted_in_still_reads_as_an_angle(tmp_path):
    """Negative control (ii): the bintype wins over a comment.

    The comment is the exact line that turns an `.xye` into a flight time one
    format over, which is what makes this control able to fail.
    """
    p = tmp_path / "cons_with_comment.gsa"
    p.write_text(
        "' The X-axis unit is: Time-of-flight\n"
        "BANK 1 4 1 CONS 1000 20 STD\n"
        "    10.0    11.0    12.0    13.0\n", encoding="utf-8")
    data = rx.read_pattern(str(p))
    assert data.axis == "two_theta"
    assert data.two_theta[0] == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# the instrument-parameter readers
# ---------------------------------------------------------------------------

IPARM = """\
COMMENT1  a synthetic two-bank PNTR file
INS   BANK      2
INS   FPATH1   32.00
INS   HTYPE   PNTR
INS  1 ICONS   5123.45 -1.23     -12.340
INS  1BNKNAM bank_45
INS  1BNKPAR      2.50     61.20
INS  1I ITYP    1    8.0000   49.0000     37556
INS  1ICOFF1   0.500000E+01   0.800000E+03   0.110000E+00   0.900000E+03
INS  1ICOFF2   0.450000E-02   0.100000E+04   0.500000E-03  -0.140000E+04
INS  1ICOFF3   0.340000E-03   0.000000E+00   0.000000E+00   0.000000E+00
INS  1IECOF1   0.120000E+00   0.100000E+02   0.440000E-03   0.600000E+01
INS  1IECOF2   0.180000E-04   0.580000E+01   0.260000E-05   0.390000E+02
INS  1IECOF3   0.650000E-05   0.000000E+00   0.000000E+00   0.000000E+00
INS  1IECOR1 1.000-0.093 0.612-0.047-0.501 0.198 0.058 0.003-0.001 0.000
INS  1PRCF1     1   12   0.01000
INS  1PRCF11   0.000000E+00   0.123456E+00   0.345678E-01   0.123457E-01
INS  1PRCF12   0.000000E+00   0.234567E+03   0.000000E+00   0.000000E+00
INS  1PRCF13   0.000000E+00   0.000000E+00   0.000000E+00   0.000000E+00
INS  2 ICONS  10231.58   -1.7200   -2.9100
INS  2BNKPAR      1.50     90.00
INS  2PRCF1     1   12   0.00100
INS  2PRCF11   0.000000E+00   0.200000E+00   0.298413E+02   0.472056E+02
INS  2PRCF12   0.000000E+00   0.154817E+03   0.000000E+00   0.000000E+00
INS  2PRCF13   0.000000E+00   0.000000E+00   0.000000E+00   0.000000E+00
INS  2PRCF2     2   15   0.00100
INS  2PRCF21   0.000000E+00   0.200000E+00   0.298413E+02   0.472056E+02
INS  2PRCF22   0.000000E+00   0.154817E+03   0.000000E+00   0.000000E+00
INS  2PRCF23   0.000000E+00   0.000000E+00   0.000000E+00   0.000000E+00
INS  2PRCF24   0.000000E+00   0.000000E+00   0.000000E+00
"""

INSTPRM = """\
#GSAS-II instrument parameter file; do not add/delete items!
beta-0:0.001
fltPath:41.527
Bank:1.0
sig-1:10.0
2-theta:90.0
sig-q:0.0
sig-0:0.0
sig-2:391.208417563
beta-1:3.63
Zero:0.0
difC:19873.4106827
X:0.0
Azimuth:0.0
Y:0.0
alpha:4.0
beta-q:0.0
Z:0.0
Type:PNT
difB:0.0
difA:-0.734106295581
"""


def test_a_gsas_i_tof_file_gives_one_instrument_per_bank(tmp_path):
    """Several banks is what a TOF diffractometer *is*, so none is picked.

    Bank 1 declares a type-1 default set; bank 2 a type-1 default and a
    type-2 second set, which is reported and skipped because set 1 is the
    default whatever its function (GSAS Technical Manual p. 223).
    """
    p = tmp_path / "synthetic.iparm"
    p.write_text(IPARM, encoding="utf-8")
    notes = []
    banks = read_gsas_tof_iparm(str(p), diagnostics=notes)
    assert sorted(banks) == [1, 2]
    one = banks[1].source
    assert (one.difc.value, one.difa.value, one.tzero.value) == (5123.45, -1.23, -12.34)
    assert one.two_theta_bank_deg == 61.20
    # DIST is carried as l2 and the file-level FPATH1 as l1 (WP-2032: not a
    # record the manual lists, and SNS files write it)
    assert (one.l1_m, one.l2_m) == (32.00, 2.50)
    assert banks[2].source.difc.value == 10231.58
    # a calibration arrives frozen, exactly as load_instrument_profile's does
    assert not any(getattr(one, n).vary for n in ("difc", "difa", "tzero", "difb"))
    assert not any(getattr(one.profile_tof, f).vary for f in ProfileTOF.model_fields)
    assert one.profile_tof.alpha1.value == pytest.approx(0.123456)
    assert one.profile_tof.sig1.value == pytest.approx(234.567)
    assert banks[2].source.profile_tof.sig1.value == pytest.approx(154.817)
    # one read per bank, and bank 2's second set declined by name
    read = [n for n in notes if n.code == "GSAS_IPARM_PROFILE_READ"]
    declined = [n for n in notes if n.code == "GSAS_IPARM_PROFILE_DECLINED"]
    assert len(read) == 2
    assert all("function 1 with 12" in n.message for n in read)
    assert len(declined) == 1 and "PRCF set 2 (profile function 2)" in declined[0].message
    dropped = [n for n in notes if n.code == "GSAS_IPARM_FIELD_DROPPED"]
    assert dropped
    # IECOR has no slot and is dropped; ICOFF and IECOF are read and so are
    # *not* in the drop list, which is the half of this that would rot
    # silently if only the message were asserted
    where = [w for n in dropped for w in n.where]
    assert any("IECOR" in w for w in where)
    assert not any("ICOFF" in w or "IECOF" in w for w in where)

    # the incident spectrum: bank 1 declares one, bank 2 has no ITYP record at
    # all and therefore has none
    spec = one.incident_spectrum
    assert spec.itype == 1
    assert (spec.tof_min_us, spec.tof_max_us) == (8000.0, 49000.0)
    assert [p.value for p in spec.coefficients] == [
        5.0, 800.0, 0.11, 900.0, 0.0045, 1000.0, 5e-4, -1400.0, 3.4e-4,
        0.0, 0.0]
    # eleven, not twelve: type 1 uses eleven and the block's twelfth slot is
    # a slot the function does not read
    assert len(spec.coefficients) == 11
    assert spec.coefficients[1].stderr == 10.0
    assert not any(p.vary for p in spec.coefficients)
    assert banks[2].source.incident_spectrum.itype == 0
    assert banks[2].source.incident_spectrum.coefficients == []


#: A one-bank ``.iparm`` with a type-1 default ``PRCF`` set of the documented
#: twelve coefficients (GSAS Technical Manual p. 144, 223).  The
#: numbers are invented, not a real bank's.
PRCF1_IPARM = """\
INS   BANK      1
INS   HTYPE   PNTR
INS  1 ICONS   5123.45   -1.2300  -12.3400
INS  1BNKPAR      2.50     61.20
INS  1PRCF1     1   12   0.01000
INS  1PRCF11   0.500000E-02   0.123456E+00   0.345678E-01   0.123457E-01
INS  1PRCF12   0.700000E+01   0.234567E+03   0.110000E+02   0.000000E+00
INS  1PRCF13   0.000000E+00   0.000000E+00   0.000000E+00   0.000000E+00
"""


def test_the_profile_is_read_whether_or_not_diagnostics_were_asked_for(tmp_path):
    """What a reader *returns* must not depend on whether anyone asked it to
    explain itself — the walk used to live inside the diagnostics guard."""
    p = tmp_path / "prcf1.iparm"
    p.write_text(PRCF1_IPARM, encoding="utf-8")
    quiet = read_gsas_tof_iparm(str(p))[1].source.profile_tof
    loud = read_gsas_tof_iparm(str(p), diagnostics=[])[1].source.profile_tof
    assert quiet.model_dump() == loud.model_dump()
    assert quiet.sig1.value == pytest.approx(234.567)


@pytest.mark.parametrize(
    ("edit", "why", "match"),
    [("   0.700000E+01   0.234567E+03   0.110000E+02   0.000000E+00",
      "   0.700000E+01   0.234567E+03   0.110000E+02   0.250000E+00",
      "s1ec = 0.25 is non-zero"),
     ("   0.700000E+01   0.234567E+03   0.110000E+02   0.000000E+00",
      "   0.700000E+01  -0.234567E+03   0.110000E+02   0.000000E+00",
      "sig1 = -234.567 is a variance coefficient and is negative")],
    ids=["a nonzero s1ec", "a negative variance coefficient"])
def test_a_type_one_block_that_disagrees_with_the_layout_is_refused(
        tmp_path, edit, why, match):
    """Two signs that the block is not a model ``ProfileTOF`` can hold, and
    both are refused by name rather than read past.

    ``s1ec`` is an anisotropic term with no slot here, so dropping it would be
    silent; a negative ``sig`` is a variance with the wrong sign.
    """
    p = tmp_path / "odd.iparm"
    p.write_text(PRCF1_IPARM.replace(edit, why), encoding="utf-8")
    with pytest.raises(ValueError, match=match):
        read_gsas_tof_iparm(str(p), diagnostics=[])


def test_a_declined_profile_is_refused_or_reported_never_read_past(tmp_path):
    """No silent calibration from a profile the reader did not read.

    A default set of a function this package does not evaluate (PTYP 2,
    Ikeda-Carpenter) is refused at read.  A bank with no ``PRCF`` set at all is
    read with a ``GSAS_IPARM_PROFILE_DECLINED`` diagnostic and an all-zero
    ``ProfileTOF``, which says plainly that nothing was calibrated.
    """
    p = tmp_path / "declined.iparm"
    p.write_text(PRCF1_IPARM.replace("     1   12   0.01000",
                                     "     2   15   0.01000"), encoding="utf-8")
    with pytest.raises(ValueError, match="PTYP = 2"):
        read_gsas_tof_iparm(str(p))

    bare = "".join(ln + "\n" for ln in PRCF1_IPARM.splitlines()
                   if "PRCF" not in ln)
    p.write_text(bare, encoding="utf-8")
    notes = []
    instrument = read_gsas_tof_iparm(str(p), diagnostics=notes)[1]
    assert [n.code for n in notes if "PROFILE" in n.code] == [
        "GSAS_IPARM_PROFILE_DECLINED"]
    assert instrument.source.profile_tof == ProfileTOF()


def test_the_iparm_reader_refuses_a_spectrum_block_that_disagrees_with_its_type(
        tmp_path):
    """Three ways a file can say two different things, each refused by name.

    A count that disagrees with the declared type has three faces in a real file: a short block, a
    non-zero number in a slot the declared function does not read, and a type
    the manual does not define.  Padding, truncating or defaulting any of them
    would read the file as a file it is not.
    """
    def write(text):
        q = tmp_path / "bad.iparm"
        q.write_text(text, encoding="utf-8")
        return str(q)

    short = IPARM.replace(
        "INS  1ICOFF3   0.340000E-03   0.000000E+00   0.000000E+00   0.000000E+00\n",
        "")
    with pytest.raises(ValueError, match="holds 8"):
        read_gsas_tof_iparm(write(short))

    # the twelfth slot carries a number the type-1 function never reads
    used = IPARM.replace(
        "INS  1ICOFF3   0.340000E-03   0.000000E+00   0.000000E+00   0.000000E+00",
        "INS  1ICOFF3   0.340000E-03   0.000000E+00   0.000000E+00   0.700000E+00")
    with pytest.raises(ValueError, match="P12 = 0.7"):
        read_gsas_tof_iparm(write(used))

    unknown = IPARM.replace("INS  1I ITYP    1 ", "INS  1I ITYP    7 ")
    with pytest.raises(ValueError, match="ITYP 7 is not an incident-spectrum"):
        read_gsas_tof_iparm(write(unknown))

    # ITYP 10 exists and is refused for its own reason: it is a measured
    # spectrum in a second file this reader is never handed
    measured = IPARM.replace("INS  1I ITYP    1 ", "INS  1I ITYP   10 ")
    with pytest.raises(ValueError, match="point-by-point"):
        read_gsas_tof_iparm(write(measured))

    # a gap in the sequence tags would shift four coefficients into the wrong
    # slots, and every one of them is a different power of the flight time
    gap = IPARM.replace(
        "INS  1ICOFF2   0.450000E-02   0.100000E+04   0.500000E-03  -0.140000E+04\n",
        "")
    with pytest.raises(ValueError, match="consecutive run"):
        read_gsas_tof_iparm(write(gap))


def test_a_constant_wavelength_prm_is_refused_and_told_where_to_go(tmp_path):
    p = tmp_path / "cw.prm"
    p.write_text(IPARM.replace("PNTR", "PXCR"), encoding="utf-8")
    with pytest.raises(ValueError, match="read_gsas_prm"):
        read_gsas_tof_iparm(str(p))
    p.write_text(IPARM.replace("PNTR", "WHAT"), encoding="utf-8")
    with pytest.raises(ValueError, match="unrecognised GSAS HTYPE"):
        read_gsas_tof_iparm(str(p))


def test_a_bank_with_no_angle_is_refused(tmp_path):
    """DIFC alone does not give the angle back — it is one number from two."""
    p = tmp_path / "noangle.iparm"
    p.write_text(IPARM.replace("INS  1BNKPAR      2.50     61.20\n", ""),
                 encoding="utf-8")
    with pytest.raises(ValueError, match="no BNKPAR record"):
        read_gsas_tof_iparm(str(p))


def test_a_gsas_ii_instprm_reads_every_named_coefficient(tmp_path):
    p = tmp_path / "bank2.instprm"
    p.write_text(INSTPRM, encoding="utf-8")
    notes = []
    source = read_gsas2_instprm(str(p), diagnostics=notes).source
    assert source.difc.value == pytest.approx(19873.4106827)
    assert source.difa.value == pytest.approx(-0.734106295581)
    assert source.tzero.value == 0.0
    assert source.two_theta_bank_deg == 90.0
    profile = source.profile_tof
    # the lone ``alpha`` maps to alpha1, not alpha0: profile function 3 has
    # α = α₁/d (GSAS Technical Manual p. 148)
    assert (profile.alpha0.value, profile.alpha1.value) == (0.0, 4.0)
    assert (profile.beta0.value, profile.beta1.value) == (0.001, 3.63)
    assert (profile.sig0.value, profile.sig1.value) == (0.0, 10.0)
    assert profile.sig2.value == pytest.approx(391.208417563)
    assert not any(getattr(profile, f).vary for f in ProfileTOF.model_fields)
    dropped = [n for n in notes if n.code == "GSAS2_INSTPRM_FIELD_DROPPED"]
    assert len(dropped) == 1
    assert "fltPath" in dropped[0].message and "Bank" in dropped[0].message


def test_a_nonzero_difb_round_trips(tmp_path):
    """Negative control (iv): the silent-truncation trap.

    A reader built to the documented three-term relation drops this without a
    word, and every peak of the project moves.
    """
    p = tmp_path / "difb.instprm"
    p.write_text(INSTPRM.replace("difB:0.0", "difB:-24.5"), encoding="utf-8")
    source = read_gsas2_instprm(str(p)).source
    assert source.difb.value == pytest.approx(-24.5)
    d = np.array(si_d())
    plain = TOFSource(difc=source.difc.value, difa=source.difa.value,
                      tzero=source.tzero.value,
                      two_theta_bank_deg=source.two_theta_bank_deg)
    shift = source.tof_from_d(d) - plain.tof_from_d(d)
    assert np.all(np.abs(shift) > 1.0), (
        f"difB moves the peaks by {shift} µs, and a three-term reader would "
        "drop it with nothing said")


def test_a_gsas_ii_width_term_this_package_has_no_slot_for_is_refused_at_drift(tmp_path):
    """Dropped at 0, refused away from it — the ``read_gsas_prm`` rule."""
    p = tmp_path / "betaq.instprm"
    p.write_text(INSTPRM.replace("beta-q:0.0", "beta-q:0.31"), encoding="utf-8")
    with pytest.raises(ValueError, match="beta-q is 0.31"):
        read_gsas2_instprm(str(p))


def test_the_type_line_decides_the_arm(tmp_path):
    """One reader on ``Type``: the same keys stated as ``PXC`` go to the
    constant-wavelength arm, which asks for the wavelength a bank never has."""
    p = tmp_path / "cw.instprm"
    p.write_text(INSTPRM.replace("Type:PNT", "Type:PXC"), encoding="utf-8")
    with pytest.raises(ValueError, match="neither Lam nor Lam1"):
        read_gsas2_instprm(str(p))


# ---------------------------------------------------------------------------
# the refusals
# ---------------------------------------------------------------------------

@pytest.fixture
def tof_pattern() -> PatternData:
    return PatternData(tof=[1000.0 + 10.0 * i for i in range(200)],
                       intensity=[10.0] * 200)


@pytest.fixture
def cw_models():
    return _si()


def _si():
    structure = rx.Structure(phases=[rx.Phase(
        name="Si", space_group="Fd-3m:2",
        cell=rx.Cell.cubic(SI_A),
        atoms=[rx.Atom(label="Si", species="Si",
                       x=rx.Parameter(value=0.125),
                       y=rx.Parameter(value=0.125),
                       z=rx.Parameter(value=0.125))])])
    return structure, rx.Instrument.constant_wavelength_neutron(1.5)


def _assert_authored(exc: pytest.ExceptionInfo, where: str) -> None:
    """Every refusal names the door, the axis and the unit.

    The assertion the fence is actually about: a ``ValueError`` is what a trig
    error raises too, so what is checked is the *message*.
    """
    message = str(exc.value)
    assert message.startswith(where), message
    assert "time of flight" in message
    assert "microseconds" in message
    assert "issue #193" in message


def test_fit_refuses_a_tof_pattern_against_a_cw_instrument(tof_pattern,
                                                           cw_models):
    """No flight-time forward model exists in this build, so the matched pair
    is refused at construction (a bank) and the crossed pair at ``fit``."""
    structure, instrument = cw_models
    for call in (lambda: rx.Refinement(structure, instrument).fit(tof_pattern),
                 lambda: rx.refine(tof_pattern, structure, instrument)):
        with pytest.raises(ValueError) as exc:
            call()
        _assert_authored(exc, "Refinement.fit()")


def test_the_multi_histogram_entry_names_which_histogram(tof_pattern, cw_models):
    """A joint fit is where a TOF bank most plausibly arrives beside CW ones,
    so the refusal names which histogram of how many."""
    structure, instrument = cw_models
    cw = PatternData(two_theta=[10.0 + 0.02 * i for i in range(200)],
                     intensity=[10.0] * 200)
    with pytest.raises(ValueError) as exc:
        rx.MultiHistogramRefinement(structure, [instrument, instrument]).fit(
            [cw, tof_pattern])
    _assert_authored(exc, "MultiHistogramRefinement.fit(), histogram 1 of 2")


def test_the_sequential_entry_names_which_pattern(tof_pattern, cw_models):
    structure, instrument = cw_models
    cw = PatternData(two_theta=[10.0 + 0.02 * i for i in range(200)],
                     intensity=[10.0] * 200)
    with pytest.raises(ValueError) as exc:
        rx.refine_sequential([cw, tof_pattern], structure, instrument)
    _assert_authored(exc, "refine_sequential(), pattern 1 of 2")


def test_the_indexing_entries_refuse_a_tof_pattern(tof_pattern, cw_models):
    _, instrument = cw_models
    with pytest.raises(ValueError) as exc:
        rx.pick_peaks(tof_pattern, instrument)
    _assert_authored(exc, "pick_peaks()")
    with pytest.raises(ValueError) as exc:
        rx.index_pattern(data=tof_pattern, instrument=instrument)
    _assert_authored(exc, "index_pattern()")


def test_the_background_entries_refuse_a_tof_pattern(tof_pattern):
    with pytest.raises(ValueError) as exc:
        rx.auto_background(tof_pattern)
    _assert_authored(exc, "auto_background()")
    with pytest.raises(ValueError) as exc:
        rx.diagnose(tof_pattern)
    _assert_authored(exc, "background.diagnose()")


def test_the_pattern_plot_refuses_a_tof_pattern(tof_pattern):
    """``PatternData.plot`` (WP-1444) draws 2θ, Q or d, each through an angle."""
    pytest.importorskip("matplotlib")
    with pytest.raises(ValueError) as exc:
        tof_pattern.plot()
    _assert_authored(exc, "plot_pattern()")


def test_the_extinction_screen_refuses_before_its_own_try_block(tof_pattern, cw_models):
    """It swallows exceptions into a failed screen, which is right for a fit
    that would not converge and wrong for a pattern it cannot read at all."""
    from rietx.schemas.indexing import CellCandidate

    _, instrument = cw_models
    candidate = CellCandidate(cell=(SI_A, SI_A, SI_A, 90.0, 90.0, 90.0),
                              cell_esd=(1e-4,) * 3 + (0.0,) * 3,
                              system="cubic", centring="F")
    with pytest.raises(ValueError) as exc:
        rx.determine_extinction_symbol(tof_pattern, candidate, instrument)
    _assert_authored(exc, "determine_extinction_symbol()")


def test_compile_model_is_the_backstop(tof_pattern, cw_models):
    """Below every public entry, so a hand-assembled compile refuses too."""
    from rietx.model.forward import compile_model

    structure, instrument = cw_models
    with pytest.raises(ValueError) as exc:
        compile_model(structure, instrument, tof_pattern)
    _assert_authored(exc, "compile_model()")


def _remaining_entries(tof_pattern, structure, instrument):
    """Every other public entry that takes a pattern and computes from it.

    Each refuses at its own door, before anything it would check first (a fit
    that has not run, a history that is off): the axis is the earlier fact,
    and a refusal that names ``compile_model()`` or ``tt()`` points the caller
    at a function they never called.
    """
    from rietx.background import select_arpls_lambda, select_chebyshev_order
    from rietx.indexing import detect_peaks, validate_by_lebail
    from rietx.io.exporters import refinement_cif_doc
    from rietx.report.body_misfit import rigid_body_misfit
    from rietx.schemas.indexing import CellCandidate

    ref = rx.Refinement(structure, instrument, history=False)
    candidate = CellCandidate(cell=(SI_A, SI_A, SI_A, 90.0, 90.0, 90.0),
                              cell_esd=(1e-4,) * 3 + (0.0,) * 3,
                              system="cubic", centring="F")
    return [
        ("Refinement.run_stage()",
         lambda: ref.run_stage(tof_pattern, rx.Stage(name="s", turn_on=["*.scale"]))),
        ("Refinement.predict()", lambda: ref.predict(tof_pattern)),
        ("Refinement.suggest()", lambda: ref.suggest(tof_pattern)),
        ("Refinement.profile_fraction()",
         lambda: ref.profile_fraction(tof_pattern, 0)),
        ("Refinement.cherry_pick()", lambda: ref.cherry_pick("n0001", tof_pattern)),
        ("replay()", lambda: rx.replay(None, "n0001", tof_pattern)),
        ("solve_magnetic()", lambda: rx.solve_magnetic(ref, tof_pattern)),
        ("fit_peaks()", lambda: rx.fit_peaks(tof_pattern, instrument, [1500.0])),
        ("detect_peaks()", lambda: detect_peaks(tof_pattern, instrument)),
        ("validate_by_lebail()",
         lambda: validate_by_lebail(candidate, tof_pattern, instrument)),
        ("select_arpls_lambda()", lambda: select_arpls_lambda(tof_pattern)),
        ("select_chebyshev_order()", lambda: select_chebyshev_order(tof_pattern)),
        ("Refinement.check_rigid_bodies()",
         lambda: ref.check_rigid_bodies(tof_pattern)),
        ("rigid_body_misfit()", lambda: rigid_body_misfit(ref, tof_pattern)),
        ("write_refinement_cif()",
         lambda: rx.write_refinement_cif(None, structure, instrument, "never.cif",
                                         pattern=tof_pattern)),
        ("refinement_cif_doc()",
         lambda: refinement_cif_doc(None, structure, instrument,
                                    pattern=tof_pattern)),
    ]


def test_every_remaining_pattern_entry_refuses_by_its_own_name(tof_pattern,
                                                                 cw_models):
    structure, instrument = cw_models
    for where, call in _remaining_entries(tof_pattern, structure, instrument):
        with pytest.raises(ValueError) as exc:
            call()
        _assert_authored(exc, where)


def test_a_project_reopened_on_a_flight_time_is_refused(tmp_path, cw_models):
    """``Project.open`` asks again rather than trusting the create: the pattern
    file sits beside an editable ``project.json``, so a bank can arrive there
    with a matching hash."""
    import hashlib
    import json

    structure, instrument = cw_models
    cw = tmp_path / "si.xye"
    cw.write_text("\n".join(f"{10.0 + 0.05 * i} {1.0 + i % 7} 0.5"
                            for i in range(400)) + "\n", encoding="utf-8")
    proj = tmp_path / "proj.rex"
    rx.Project.create(proj, pattern=cw, structure=structure,
                      instrument=instrument)
    doc_path = proj / "project.json"
    doc = json.loads(doc_path.read_text(encoding="utf-8"))
    stored = proj / doc["patterns"][0]["filename"]
    stored.write_text("' The X-axis unit is: Time-of-flight\n"
                      + "\n".join(f"{7000.0 + 3.0 * i} {1.0 + i} 0.5"
                                   for i in range(50)) + "\n", encoding="utf-8")
    doc["patterns"][0]["sha256"] = hashlib.sha256(stored.read_bytes()).hexdigest()
    doc_path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        rx.Project.open(proj)
    _assert_authored(exc, "Project.open()")


def test_the_indexing_plots_refuse_a_tof_pattern(tof_pattern, cw_models):
    """They draw the pattern under 2θ peak positions, so a flight time would be
    drawn on a degree axis beside them."""
    pytest.importorskip("matplotlib")
    from rietx.viz import plot_indexing, plot_peak_list

    _, instrument = cw_models
    with pytest.raises(ValueError) as exc:
        plot_peak_list(None, tof_pattern)
    _assert_authored(exc, "plot_peak_list()")
    with pytest.raises(ValueError) as exc:
        plot_indexing(None, None, data=tof_pattern, instrument=instrument)
    _assert_authored(exc, "plot_indexing()")


def test_the_instrument_writers_refuse_a_bank_by_name(tmp_path, cw_models):
    """Each writes a constant-wavelength instrument, and on a bank reached an
    ``AttributeError`` for a wavelength or a harmonic it does not have."""
    structure, _ = cw_models
    bank = rx.Instrument.tof_neutron_bank(difc=5123.45, two_theta_bank_deg=90.0)
    for where, call in (
            ("write_gsas_prm()", lambda: rx.write_gsas_prm(bank, tmp_path / "b.prm")),
            ("write_gsas2_instprm()",
             lambda: rx.write_gsas2_instprm(bank, tmp_path / "b.instprm")),
            ("write_fullprof_pcr()",
             lambda: rx.write_fullprof_pcr(structure, tmp_path / "b.pcr",
                                           instrument=bank)),
            ("write_topas_inp()",
             lambda: rx.write_topas_inp(structure, tmp_path / "b.inp",
                                        instrument=bank))):
        with pytest.raises(ValueError) as exc:
            call()
        message = str(exc.value)
        assert message.startswith(where), message
        assert "neutron_tof bank" in message
        assert "issue #193" in message
    assert not list(tmp_path.iterdir())


def test_a_tof_instrument_is_refused_at_construction(cw_models):
    """The mistake seen from the other side, refused before anything reads a
    wavelength the source does not have.

    Without this it surfaces as an ``AttributeError`` for a wavelength the
    source does not have, which tells a caller nothing about what they did.
    The single and the joint constructor both read one, so both refuse; an
    edit that swaps a bank in is the same door.
    """
    structure, instrument = cw_models
    bank = rx.Instrument.tof_neutron_bank(difc=5123.45, two_theta_bank_deg=61.2)
    for call, where in (
            (lambda: rx.Refinement(structure, bank), "Refinement()"),
            (lambda: rx.MultiHistogramRefinement(structure, [instrument, bank]),
             "MultiHistogramRefinement(), instrument 1 of 2"),
            (lambda: rx.Refinement(structure, instrument, history=False).edit(
                instrument=bank), "Refinement.edit()")):
        with pytest.raises(ValueError) as exc:
            call()
        message = str(exc.value)
        assert message.startswith(where), message
        assert "neutron_tof bank" in message
        assert "issue #193" in message


def test_require_two_theta_passes_a_constant_wavelength_pattern(cw_models):
    """The helper's positive arm: it must be able to *not* fire."""
    _, instrument = cw_models
    cw = PatternData(two_theta=[10.0, 10.02], intensity=[1.0, 2.0])
    assert require_two_theta(cw, "somewhere", instrument=instrument) is None


def test_the_project_and_gui_doors_refuse_one_too(tmp_path, tof_pattern, cw_models):
    """The two paths a pattern reaches a *session* by, rather than a call.

    ``Project.create`` would otherwise reach ``len(None)`` building a
    ``DataRef`` whose field is called ``two_theta_range``, and the GUI's upload
    step would reach ``np.asarray(None)``.  Both are the same failure seen
    through a different door.
    """
    from rietx.gui.imports import UploadRefused

    p = tmp_path / "pg3.xye"
    p.write_text("' The X-axis unit is: Time-of-flight\n"
                 + "\n".join(f"{7000.0 + 3.0 * i} {1.0 + i} 0.5"
                              for i in range(50)) + "\n", encoding="utf-8")
    structure, instrument = cw_models
    with pytest.raises(ValueError) as exc:
        rx.Project.create(tmp_path / "proj.rex", pattern=p,
                          structure=structure, instrument=instrument)
    _assert_authored(exc, "Project.create()")

    with pytest.raises(ValueError) as exc:
        rx.project.fitted_mask(tof_pattern, None)
    _assert_authored(exc, "project.fitted_mask()")

    # the GUI's own door: an upload is refused with the same words, wrapped in
    # the type the wizard shows rather than as a bare ValueError
    from rietx.gui.imports import UploadStore, preview_pattern

    store = UploadStore(tmp_path / "uploads")
    try:
        upload = store.stage("pattern", "pg3.xye", p.read_bytes())
        with pytest.raises(UploadRefused) as up:
            preview_pattern(upload)
        assert "time of flight" in str(up.value)
        assert "issue #193" in str(up.value)
    finally:
        store.close()


# ---------------------------------------------------------------------------
# the bank's parameter table (issue #442)
# ---------------------------------------------------------------------------

def test_a_bank_carries_its_own_rows_and_not_the_constant_wavelength_ones():
    """Issue #442's answer: a bank's widths, zero and position calibration
    live under its own names, so the constant-wavelength rows that play those
    parts are not registered at all.

    Registered force-fixed, ``instrument.profile.*`` would *match* on a bank
    and free nothing, which WP-1414's "matched, not freed" rule reads as
    reached; absent, the glob matches nothing there, so a joint stage that
    frees the CW widths and nothing of a bank's is what ``STAGE_FREED_NOTHING``
    already reports, with no new rule.  The rows with nothing to refine on a
    bank (axial divergence, the capillary offsets) stay, force-fixed — the
    capillary case the rule is right about.
    """
    from rietx.params.vector import BANK_ABSENT_PATHS, ParameterTable

    structure, cw = _si()
    bank = rx.Instrument.tof_neutron_bank(difc=5123.45, difa=-1.23,
                                          two_theta_bank_deg=61.2)
    tof_rows = {e.path: e for e in ParameterTable(structure, bank).entries}
    cw_rows = {e.path for e in ParameterTable(structure, cw).entries}
    assert set(BANK_ABSENT_PATHS) <= cw_rows
    assert not set(BANK_ABSENT_PATHS) & set(tof_rows)
    for own in ("instrument.source.difc", "instrument.source.tzero",
                "instrument.source.profile_tof.sig1"):
        assert own in tof_rows and not tof_rows[own].vary
    assert tof_rows["instrument.geometry.axial_sl"].locked
    assert not any(p.startswith("instrument.source.lines.") for p in tof_rows)

    table = ParameterTable(structure, bank)
    assert table.set_vary(["instrument.profile.*"], True) == []
    assert ParameterTable(structure, cw).set_vary(["instrument.profile.*"], True)
    assert table.set_vary(["instrument.source.difc"], True) == [
        "instrument.source.difc"]


def test_a_declared_free_cw_row_on_a_bank_is_refused_by_name():
    """A ``vary=True`` the caller wrote on a row the bank does not carry is a
    claim about a parameter that does not exist, so it is refused rather than
    quietly dropped with the row."""
    from rietx.params.vector import ParameterTable

    structure, _ = _si()
    bank = rx.Instrument.tof_neutron_bank(difc=5123.45, two_theta_bank_deg=61.2)
    bank.zero_shift.vary = True
    with pytest.raises(ValueError, match=r"instrument\.zero_shift cannot vary "
                                         r"on a neutron_tof bank.*tzero"):
        ParameterTable(structure, bank)


def test_a_bank_table_writes_its_calibration_back():
    """The collector and the write-back walk one list, so a value set in the
    table reaches the model and nothing absent is asked for."""
    from rietx.params.vector import ParameterTable

    structure, _ = _si()
    bank = rx.Instrument.tof_neutron_bank(difc=5123.45, two_theta_bank_deg=61.2)
    table = ParameterTable(structure, bank)
    table.entries[table._paths["instrument.source.difc"]].value = 5200.0
    s2, b2 = structure.model_copy(deep=True), bank.model_copy(deep=True)
    table.apply_to_models(s2, b2)
    assert b2.source.difc.value == 5200.0
    assert b2.zero_shift == bank.zero_shift


def test_a_project_made_before_bank_existed_still_opens_on_a_multi_bank_file(
        tmp_path, cw_models):
    """The reader answered a multi-bank file with its first bank for its whole
    life, so a project written then records no ``bank``.  An old project must
    always open: the reopen asks for the file's first bank by number."""
    import json

    structure, instrument = cw_models
    one = tmp_path / "one.gsa"
    one.write_text("one bank\nBANK 1 4 1 CONS 1000 20 STD\n"
                   "    10.0    11.0    12.0    13.0\n", encoding="utf-8")
    proj = tmp_path / "proj.rex"
    rx.Project.create(proj, pattern=one, structure=structure,
                      instrument=instrument)
    doc = json.loads((proj / "project.json").read_text(encoding="utf-8"))
    assert "bank" not in doc["patterns"][0]["options"]
    # the same project, but the file it points at now holds three banks — the
    # first being the one the project was fitted on, so the bytes are
    # re-hashed and the fingerprint is untouched
    stored = proj / doc["patterns"][0]["filename"]
    stored.write_text(stored.read_text(encoding="utf-8")
                      + "BANK 2 4 1 CONS 2000 20 STD\n"
                        "    10.0    11.0    12.0    13.0\n", encoding="utf-8")
    import hashlib
    doc["patterns"][0]["sha256"] = hashlib.sha256(stored.read_bytes()).hexdigest()
    (proj / "project.json").write_text(json.dumps(doc), encoding="utf-8")
    reopened = rx.Project.open(proj)
    assert reopened.data.two_theta[0] == pytest.approx(10.0)


def test_a_refused_bank_edit_leaves_the_working_state_where_it_was(cw_models):
    """``edit`` refuses a bank, and the refusal comes before any state moves:
    the structure, the user ties and the head are all as they were."""
    structure, instrument = cw_models
    ref = rx.Refinement(structure, instrument)
    ref.tie_equal(["instrument.profile.u", "instrument.profile.v"])
    assert ref._ties
    ties_before = dict(ref._ties)
    head_before = ref._head_id
    s2 = structure.model_copy(deep=True)
    s2.phases[0].cell.a.value += 0.5
    bank = rx.Instrument.tof_neutron_bank(difc=5123.45, two_theta_bank_deg=90.0)
    with pytest.raises(ValueError) as exc:
        ref.edit(structure=s2, instrument=bank)
    assert str(exc.value).startswith("Refinement.edit()")
    assert ref.structure.phases[0].cell.a.value == structure.phases[0].cell.a.value
    assert ref._ties == ties_before
    assert ref._head_id == head_before


def test_a_flight_time_pattern_prints_and_says_which_axis_it_is(tof_pattern):
    """Reading a bank and looking at it is what the build offers; ``str`` went
    through ``tt()``, which refuses a flight-time axis, so ``print(data)`` and a
    notebook cell both raised."""
    text = str(tof_pattern)
    assert "1000–2990 µs time of flight" in text
    assert "median step 10 µs" in text
    assert "° 2θ" not in text
    cw = PatternData(two_theta=[10.0, 10.5, 11.0], intensity=[1.0, 2.0, 3.0])
    assert "10–11° 2θ, median step 0.5°" in str(cw)


def test_a_profile_holding_a_bank_is_refused_by_name_at_both_doors(tmp_path):
    """The writer produced a file the loader could not read (an
    ``AttributeError`` for ``source.polarization``, a 500 in the GUI's
    preview).  The writer now refuses, and a file written before that is
    refused by the loader in the same words."""
    import json

    bank = rx.Instrument.tof_neutron_bank(difc=5123.45, two_theta_bank_deg=90.0)
    with pytest.raises(ValueError) as exc:
        rx.save_instrument_profile(bank, tmp_path / "bank.json")
    assert str(exc.value).startswith("save_instrument_profile()")
    assert not (tmp_path / "bank.json").exists()

    cw = rx.Instrument.constant_wavelength_neutron(1.5)
    rx.save_instrument_profile(cw, tmp_path / "cw.json")
    doc = json.loads((tmp_path / "cw.json").read_text(encoding="utf-8"))
    doc["instrument"] = bank.model_dump(
        mode="json", exclude={"background", "extra_components"})
    (tmp_path / "old.json").write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        rx.load_instrument_profile(tmp_path / "old.json")
    assert str(exc.value).startswith(
        f"{tmp_path / 'old.json'}: load_instrument_profile()")


def test_an_esd_time_map_bank_padded_to_ten_fields_is_checked_at_its_declared_count(
        tmp_path):
    """A real ESD record is padded with explicit zero pairs, so a bank whose
    channel count is not a multiple of five arrives with 1-4 extra pairs; the
    map's terminator check wants the declared count, not the padded one."""
    p = time_map_bank(tmp_path / "pad.gsa", nchan=7)
    text = p.read_text(encoding="utf-8").rstrip("\n")
    p.write_text(text + f"{0.0:8.1f}" * 6 + "\n", encoding="utf-8")
    data = rx.read_pattern(str(p))
    assert len(data.tof) == 7
    assert data.tof[0] == pytest.approx(2000.5)


@pytest.mark.parametrize("record, stated", [
    ("TIME_MAP ESD", "'ESD'"),
    ("TIME_MAP  2.0 ESD", "'2.0'"),
])
def test_a_time_map_bank_with_no_readable_map_number_is_refused_by_name(
        tmp_path, record, stated):
    """Map 1 would otherwise be assumed, and a map 1 that happens to fit the
    channel count passes the terminator check with no diagnostic."""
    p = time_map_bank(tmp_path / "nomap.gsa")
    p.write_text(p.read_text(encoding="utf-8").replace("TIME_MAP  1 ESD", record),
                 encoding="utf-8")
    with pytest.raises(ValueError, match="nomap.gsa") as exc:
        rx.read_pattern(str(p))
    assert stated in str(exc.value)
    assert "number of its time map" in str(exc.value)


def test_a_clock_width_that_is_not_a_number_names_the_file(tmp_path):
    p = time_map_bank(tmp_path / "clk.gsa")
    p.write_text(p.read_text(encoding="utf-8").replace("TIME_MAP  100",
                                                   "TIME_MAP  ."),
                 encoding="utf-8")
    with pytest.raises(ValueError, match="clk.gsa") as exc:
        rx.read_pattern(str(p))
    assert "clock width" in str(exc.value)


@pytest.mark.parametrize("bintype, axis", [
    ("CONS", "two_theta"), ("RALF", "tof"), ("COND", None), ("EDS", None),
    ("LPSD", None)])
def test_gsas_banks_names_an_axis_only_for_a_bintype_that_has_one(
        tmp_path, bintype, axis):
    """``COND``/``CONQ``/``LPSD``/``EDS`` are neither angle nor time; listing
    them as ``"tof"`` told a caller filtering on ``axis`` something false."""
    p = tmp_path / "one.gsa"
    p.write_text(f"BANK 1 4 1 {bintype} 1000 20 STD\n"
                 "    10.0    11.0    12.0    13.0\n", encoding="utf-8")
    (bank,) = gsas_banks(str(p))
    assert bank.axis == axis


@pytest.mark.parametrize("unit", ["2-Theta", "2 Theta", "2theta", "Two-Theta",
                                  "2θ (deg)"])
def test_a_file_stating_its_2theta_axis_in_any_spelling_draws_no_assumption(
        tmp_path, unit):
    """``2-Theta`` was captured as a stated unit, matched no pattern, and drew
    ``PATTERN_X_AXIS_ASSUMED`` on a file that had stated its axis."""
    p = tmp_path / "stated.xye"
    p.write_text(f"# The X-axis unit is: {unit}\n"
                 + "\n".join(f"{10.0 + 0.02 * i} {i} {1.0 + 0.1 * i}"
                             for i in range(N)) + "\n", encoding="utf-8")
    notes = []
    data = rx.read_pattern(str(p), diagnostics=notes)
    assert data.axis == "two_theta"
    assert notes == []


def test_the_descending_and_repeat_notes_name_the_flight_time_on_a_bank(tmp_path):
    """They said "2θ" and ``where=["two_theta"]`` about a Mantid TOF file written
    high to low."""
    p = tmp_path / "desc.xye"
    rows = [(7000.0 + 3.0 * i, 1.0 + i, 0.5 + i) for i in range(N)][::-1]
    rows.insert(3, rows[3])
    p.write_text("# The X-axis unit is: Time-of-flight\n"
                 + "\n".join(f"{x} {y} {e}" for x, y, e in rows) + "\n",
                 encoding="utf-8")
    notes = []
    data = rx.read_pattern(str(p), diagnostics=notes)
    assert data.axis == "tof"
    by = {n.code: n for n in notes}
    assert "high flight-time to low" in by["PATTERN_SCAN_REVERSED"].message
    assert "2θ" not in by["PATTERN_SCAN_REVERSED"].message
    assert by["PATTERN_SCAN_REVERSED"].where == ["tof"]
    assert "flight-time value(s)" in by["PATTERN_DUPLICATE_POINTS"].message


# ---------------------------------------------------------------------------
# WP-2032: the T-1 readers' review follow-ups (yue-here/rietx#1120)
# ---------------------------------------------------------------------------

def time_map_after_the_rows(path, *, flag="ESD"):
    """:func:`time_map_bank`'s file with its ``TIME_MAP`` record moved to
    *after* the bank's rows — the same bytes in the other legal order.

    The GSAS Technical Manual (Larson & Von Dreele 2004, LAUR 86-748, p. 219)
    says a file's header-plus-records sets "may be repeated in any order", and
    that a time map is only "usually" at the head of the file.  So the record
    may follow the rows, and the rows must end where it starts.
    """
    lines = time_map_bank(path, flag=flag).read_text(encoding="utf-8").splitlines()
    title, header, table, bank, *rows = lines
    path.write_text("\n".join([title, bank, *rows, header, table]) + "\n",
                    encoding="utf-8")
    return path


@pytest.mark.parametrize("flag", ["ESD", "STD"])
def test_a_time_map_record_after_the_rows_ends_the_bank(tmp_path, flag):
    """The record is a header, never data: the bank read is the one the
    map-first file gives, channel for channel."""
    before = rx.read_pattern(str(time_map_bank(tmp_path / "first.gsa", flag=flag)))
    after = rx.read_pattern(str(time_map_after_the_rows(tmp_path / "last.gsa",
                                                        flag=flag)))
    assert after.axis == "tof" and len(after.tof) == N
    assert after.tof == before.tof
    assert after.intensity == before.intensity
    assert after.sigma == before.sigma


def test_a_time_map_record_between_two_banks_belongs_to_neither(tmp_path):
    """Between banks, with a ``#`` comment before it as the manual (p. 217)
    places one: bank 1's rows end at the comment's header, and bank 2 still
    finds the map it names."""
    lines = time_map_bank(tmp_path / "one.gsa").read_text(encoding="utf-8").splitlines()
    title, header, table, bank, *rows = lines
    p = tmp_path / "between.gsa"
    p.write_text("\n".join([title, bank, *rows, "# the time map for both banks",
                            header, table, bank.replace("BANK   1", "BANK   2"),
                            *rows]) + "\n", encoding="utf-8")
    one = rx.read_pattern(str(p), bank=1)
    two = rx.read_pattern(str(p), bank=2)
    assert len(one.tof) == len(two.tof) == N
    assert one.intensity == two.intensity == [10.0 + j for j in range(N)]


def test_a_line_after_the_rows_that_is_no_header_is_still_refused_by_name(tmp_path):
    """The negative arm: only a ``BANK`` or ``TIME_MAP`` header ends a bank.  Any
    other line where a record belongs is refused naming the file, not skipped."""
    lines = time_map_bank(tmp_path / "x.gsa").read_text(encoding="utf-8").splitlines()
    p = tmp_path / "stray.gsa"
    p.write_text("\n".join(lines + ["TIMEMAP 1 4 1"]) + "\n", encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        rx.read_pattern(str(p))
    assert p.name in str(exc.value)


def _bank_profile_file(tmp_path):
    """A profile file holding a bank, as a version before the writer refused
    one could have saved it."""
    import json

    bank = rx.Instrument.tof_neutron_bank(difc=5123.45, two_theta_bank_deg=90.0)
    cw = rx.Instrument.constant_wavelength_neutron(1.5)
    rx.save_instrument_profile(cw, tmp_path / "cw.json")
    doc = json.loads((tmp_path / "cw.json").read_text(encoding="utf-8"))
    doc["instrument"] = bank.model_dump(
        mode="json", exclude={"background", "extra_components"})
    path = tmp_path / "old_bank_profile.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def test_load_instrument_profile_names_the_file_it_refuses(tmp_path):
    """A reader raises naming the file (CLAUDE.md § Invariants, WP-1047): the
    door alone says which function closed and not on what."""
    path = _bank_profile_file(tmp_path)
    with pytest.raises(ValueError) as exc:
        rx.load_instrument_profile(path)
    message = str(exc.value)
    assert str(path) in message
    assert "load_instrument_profile()" in message
    assert "neutron_tof" in message


def test_project_open_records_the_bank_it_read_and_a_reopen_reads_it_again(
        tmp_path, cw_models):
    """The reader call is part of the reference (CLAUDE.md § Project), so the
    bank an old project's reopen chose is written into its ``DataRef``.

    The positive arm: once recorded, the bank is asked for by number, so the
    same file with its banks written in the other order still reads bank 1.
    The control: the same swap with the record removed reads the file's
    *first* bank, bank 2, and the fingerprint refuses it.
    """
    import hashlib
    import json

    structure, instrument = cw_models
    bank1 = "BANK 1 4 1 CONS 1000 20 STD\n    10.0    11.0    12.0    13.0\n"
    bank2 = "BANK 2 4 1 CONS 2000 20 STD\n    20.0    21.0    22.0    23.0\n"
    one = tmp_path / "one.gsa"
    one.write_text("one bank\n" + bank1, encoding="utf-8")
    proj = tmp_path / "proj.rex"
    rx.Project.create(proj, pattern=one, structure=structure,
                      instrument=instrument)
    doc_path = proj / "project.json"
    doc = json.loads(doc_path.read_text(encoding="utf-8"))
    assert "bank" not in doc["patterns"][0]["options"]
    stored = proj / doc["patterns"][0]["filename"]

    def rewrite(text: str, *, keep_bank: bool = True) -> None:
        stored.write_text(text, encoding="utf-8")
        d = json.loads(doc_path.read_text(encoding="utf-8"))
        d["patterns"][0]["sha256"] = hashlib.sha256(stored.read_bytes()).hexdigest()
        if not keep_bank:
            d["patterns"][0]["options"].pop("bank", None)
        doc_path.write_text(json.dumps(d), encoding="utf-8")

    # an old project: no bank recorded, and the file now holds two
    rewrite("two banks\n" + bank1 + bank2)
    opened = rx.Project.open(proj)
    assert opened.data_ref.options == {"bank": "1"}
    opened.save()
    saved = json.loads(doc_path.read_text(encoding="utf-8"))
    assert saved["patterns"][0]["options"] == {"bank": "1"}

    rewrite("two banks\n" + bank2 + bank1)
    again = rx.Project.open(proj)
    assert again.data.two_theta[0] == pytest.approx(10.0)
    assert again.data_ref.options == {"bank": "1"}

    rewrite("two banks\n" + bank2 + bank1, keep_bank=False)
    with pytest.raises(ValueError, match="parses them differently"):
        rx.Project.open(proj)


def test_fpath1_is_read_as_every_banks_primary_flight_path(tmp_path):
    """``FPATH1`` is not in the manual's record list (p. 221-223), and SNS
    writes it: NOMAD's ``FPATH1 19.50`` beside ``BNKPAR`` DIST 2.010 is the
    "Primary flight path 19.5m" and "Total flight path 21.510m" its own
    data file states for that bank.  It is one number for the whole file."""
    p = tmp_path / "synthetic.iparm"
    p.write_text(IPARM, encoding="utf-8")
    notes = []
    banks = read_gsas_tof_iparm(str(p), diagnostics=notes)
    assert [banks[b].source.l1_m for b in (1, 2)] == [32.0, 32.0]
    where = [w for n in notes if n.code == "GSAS_IPARM_FIELD_DROPPED"
             for w in n.where]
    assert not any("FPATH" in w for w in where)


def test_fpath1_written_past_ten_columns_is_still_one_number(tmp_path):
    """POWGEN writes ``FPATH1     60.000000``, fourteen columns after the key;
    the record has no documented layout, so it is read as one number."""
    p = tmp_path / "powgen_width.iparm"
    p.write_text(IPARM.replace("INS   FPATH1   32.00",
                               "INS   FPATH1     60.000000"), encoding="utf-8")
    banks = read_gsas_tof_iparm(str(p))
    assert banks[1].source.l1_m == 60.0


@pytest.mark.parametrize("payload, why", [
    ("   thirty", "not a number"),
    ("   32.00   2.50", "one number"),
    ("   -32.00", "must be positive"),
])
def test_an_fpath1_that_is_not_one_flight_path_is_refused_naming_the_file(
        tmp_path, payload, why):
    p = tmp_path / "bad_fpath.iparm"
    p.write_text(IPARM.replace("INS   FPATH1   32.00", "INS   FPATH1" + payload),
                 encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        read_gsas_tof_iparm(str(p))
    assert str(p) in str(exc.value)
    assert why in str(exc.value)


def test_a_file_with_no_fpath1_leaves_the_primary_path_unstated(tmp_path):
    p = tmp_path / "no_fpath.iparm"
    p.write_text(IPARM.replace("INS   FPATH1   32.00\n", ""), encoding="utf-8")
    assert read_gsas_tof_iparm(str(p))[1].source.l1_m is None


def test_the_spectrum_type_is_validated_against_spectrum_types(monkeypatch, tmp_path):
    """``SPECTRUM_TYPES`` is what decides whether an ITYP exists, at both
    places a type is validated: the schema and the ``.iparm`` reader.  Shown
    by removing a type from it and watching both refuse that type."""
    from rietx.model import tof_spectrum
    from rietx.schemas.common import Parameter
    from rietx.schemas.instrument import IncidentSpectrum

    twelve = [Parameter(value=1.0) for _ in range(12)]
    p = tmp_path / "ityp3.iparm"
    # type 3 reads all twelve ICOFF slots, so the type-1 block is a valid one
    p.write_text(IPARM.replace("INS  1I ITYP    1", "INS  1I ITYP    3"),
                 encoding="utf-8")
    # the positive arm: with the table whole, type 3 is accepted at both
    assert IncidentSpectrum(itype=3, coefficients=twelve).itype == 3
    assert read_gsas_tof_iparm(str(p))[1].source.incident_spectrum.itype == 3
    monkeypatch.setattr(tof_spectrum, "SPECTRUM_TYPES",
                        {k: v for k, v in tof_spectrum.SPECTRUM_TYPES.items()
                         if k != 3})
    with pytest.raises(ValueError, match="ITYP 3 is not"):
        IncidentSpectrum(itype=3, coefficients=twelve)
    with pytest.raises(ValueError, match="ITYP 3 is not"):
        read_gsas_tof_iparm(str(p))


def test_a_coefficient_count_refusal_names_the_function():
    """The refusal says which function the type is, from the same table."""
    from rietx.model.tof_spectrum import SPECTRUM_TYPES
    from rietx.schemas.common import Parameter
    from rietx.schemas.instrument import IncidentSpectrum

    with pytest.raises(ValueError) as exc:
        IncidentSpectrum(itype=3, coefficients=[Parameter(value=1.0)] * 11)
    assert SPECTRUM_TYPES[3] in str(exc.value)


def test_the_two_spectrum_tables_name_the_same_types():
    """``COEFFICIENT_COUNTS`` answers how many numbers a type takes only for a
    type ``SPECTRUM_TYPES`` defines, so the two may not drift apart."""
    from rietx.model.tof_spectrum import COEFFICIENT_COUNTS, SPECTRUM_TYPES

    assert SPECTRUM_TYPES.keys() == COEFFICIENT_COUNTS.keys()
