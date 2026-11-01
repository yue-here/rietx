"""The fits behind `docs/docs/guides/holder.md`: a sample-holder line ignored, excluded and declared.

The page shows the lines between each pair of `guide:` markers and quotes what
they print; every quoted number is asserted at the end, so a change that moves
one fails `tests/test_examples.py`.

Data: the GSAS-II `LabData` tutorial fluorapatite, shipped in `rietx.examples`,
with a synthetic steel line added by `_holder_line.py` beside this script.
"""

# guide: start

from _holder_line import with_holder_line

import rietx as rx
from rietx.examples import examples_dir

clean = rx.read_pattern(examples_dir() / "FAP.XRA")
data = with_holder_line(clean)  # adds a steel 110 line at 44.65°


def fluorapatite(extra=()):
    structure = rx.Structure.from_cif(examples_dir() / "fluorapatite.cif")
    instrument = rx.Instrument.bragg_brentano(radiation="CuKa")
    instrument.background = rx.BackgroundChebyshev.with_terms(6)
    instrument.extra_components = list(extra)
    return rx.Refinement(structure, instrument)


def holder_line():
    return rx.PeakComponent(
        label="steel holder 110",
        center=rx.Parameter(value=44.6, min=44.4, max=44.9, unit="deg"),
        area=rx.Parameter(value=10.0, min=0.0, unit="counts*deg"),
        fwhm=rx.Parameter(value=0.1, min=0.02, max=0.4, unit="deg"))


def fit(ref, pattern):
    return ref.fit(pattern, plan="mccusker_structural", two_theta_limits=(15, 130))


before = {p.path: p for p in fit(fluorapatite(), clean).parameters}


def largest_move(result):
    """The parameter furthest from the fit to the pattern without the line, in esds."""
    return max((abs(p.value - before[p.path].value) / before[p.path].stderr, p.path)
               for p in result.parameters
               if ".dof." not in p.path and before.get(p.path) and before[p.path].stderr)


excluded = data.model_copy()
excluded.excluded_regions = [(44.3, 45.1)]  # validated: an inverted pair raises
declared = fluorapatite([holder_line()])
results = {"ignored": fit(fluorapatite(), data), "excluded": fit(fluorapatite(), excluded),
           "declared": fit(declared, data)}
for name, result in results.items():
    move, path = largest_move(result)
    print(f"{name:<9} largest move {move:.2f} esd, {path}")
# guide: end

# guide: line start
result = results["declared"]
for name in ("center", "area", "fwhm"):
    p = result.parameter(f"instrument.extra_components.0.{name}")
    print(f"{name:<6} {rx.format_su(p.value, p.stderr)}")
# guide: line end

# guide: diagnostic start
for d in result.diagnostics:
    if d.code.startswith("EXTRA_PEAK"):
        print(d)
# guide: diagnostic end

# guide: unmatched start
for name in ("ignored", "declared"):
    report = rx.build_report(results[name])
    near = [round(u.two_theta, 2) for u in report.unmatched
            if u.kind == "unmatched_obs" and 44.3 < u.two_theta < 45.1]
    print(f"{name:<9} unmatched peaks between 44.3 and 45.1°: {near}")
# guide: unmatched end

# guide: absent start
absent = fit(fluorapatite([holder_line()]), clean)  # the pattern with no steel line
area = absent.parameter("instrument.extra_components.0.area")
print(f"area {rx.format_su(area.value, area.stderr)}")
for d in absent.diagnostics:
    if any(".extra_components." in path for path in d.where):
        print(d)
# guide: absent end

from _holder_line import AREA, CENTER, FWHM  # noqa: E402

# 2026-10-21, darwin/arm64, identical on RIETX_COMPILED=0.
moves = {name: largest_move(r) for name, r in results.items()}
assert {name: (round(m, 2), path) for name, (m, path) in moves.items()} == {
    "ignored": (1.88, "phases.0.atoms.6.x"), "excluded": (0.28, "phases.0.atoms.6.x"),
    "declared": (0.25, "phases.0.atoms.6.x")}
assert declared.fitted_structure.phases[0].atoms[6].label == "O7"
line = {n: result.parameter(f"instrument.extra_components.0.{n}") for n in ("center", "area", "fwhm")}
assert [rx.format_su(p.value, p.stderr) for p in line.values()] == ["44.6506(77)", "68.8(61)", "0.122(26)"]
# The page: each lies within 1.5 esd of the line as made.
assert all(abs(line[n].value - true) / line[n].stderr < 1.5
           for n, true in (("center", CENTER), ("area", AREA), ("fwhm", FWHM)))
assert round(line["area"].value / line["area"].stderr) == 11  # "eleven esds from zero"
assert [d.code for d in result.diagnostics if d.code.startswith("EXTRA_PEAK")] == [
    "EXTRA_PEAK_ON_REFLECTION"]
# The page: excluding 44.3-45.1° drops (400) and costs at most 4 % on any esd.
esd_before = {p.path: p.stderr for p in before.values() if p.stderr}
growth = max(p.stderr / esd_before[p.path] for p in results["excluded"].parameters
             if p.stderr and p.path in esd_before)
assert 1.03 < growth < 1.04
assert rx.format_su(area.value, area.stderr) == "8.4(97)"
assert sorted(d.where[0] for d in absent.diagnostics if d.code == "BOUND_HIT"
              and ".extra_components." in d.where[0]) == [
    "instrument.extra_components.0.center", "instrument.extra_components.0.eta",
    "instrument.extra_components.0.fwhm"]
# The page: over empty background at 60°, the area refines to zero and the fit says so.
empty = holder_line()
empty.center = rx.Parameter(value=60.0, min=59.8, max=60.3, unit="deg")
empty_result = fit(fluorapatite([empty]), clean)
assert empty_result.parameter("instrument.extra_components.0.area").value == 0.0
assert "EXTRA_PEAK_NO_INTENSITY" in {d.code for d in empty_result.diagnostics}
# The page: on the pattern with no line, the area stays above zero and so
# `EXTRA_PEAK_NO_INTENSITY` stays silent.
assert area.value > 0.0
assert "EXTRA_PEAK_NO_INTENSITY" not in {d.code for d in absent.diagnostics}
