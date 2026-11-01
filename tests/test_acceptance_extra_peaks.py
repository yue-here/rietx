"""v1.4 acceptance: a declared sharp peak on real data (WP-1103).

The design case, measured end to end rather than asserted. A sample holder
diffracting at its own specimen distance puts sharp lines where no phase in the
model has one, and the lines **overlap peaks that matter** — which is the only
case where a `PeakComponent` earns its place, because an intruder in empty
background can simply be excluded at no cost.

The fixture is the NIST SRM 660c LaB6 protocol of
`test_acceptance_srm660c.py` — real CuKα divergent-beam data with a reference
cell — contaminated by injecting a two-line holder doublet onto two LaB6
reflections. The intruder is synthetic because no committed standard carries a
holder line; the *pattern it is injected into* is real, which is what the cell
bias has to be measured against.

Three arms on the same contaminated data:

* **ignore** — refine as if the intruder were not there. The phases absorb it.
* **declare** — two `PeakComponent`s, freed in their own stage.
* **exclude** — `excluded_regions` over both intruders, the alternative a
  caller reaches for today.

and the **clean** arm (the uncontaminated pattern) is the truth all three are
measured against. The package recommends through evidence: the excluded-regions
arm is *quoted*, never gated, and its lost-channel count is quoted beside it,
because whether losing those channels matters is the caller's question.

Measured (2026-09-13, macOS darwin 25.5.0, `[dev]`), two holder lines of area
120 counts·deg and FWHM 0.16° injected onto the LaB6 reflections at 37.4418°
and 43.6205°:

    arm         a (Å)        esd        ppm      Rwp      channels
    clean       4.156895     2.49e-05     0.0    0.08671      5332
    ignore      4.156927     1.88e-04    +7.6    0.31714      5332
    declare     4.156891     2.46e-05    -1.0    0.07701      5332
    exclude     4.156898     2.49e-05    +0.6    0.08625      5076

The esds are 1.5.0's. On the 1.6.0 tree clean is 2.08e-05 and ignore
1.81e-04, 8.7x.

Re-measured on the 1.10.0 tree (macOS arm64, `[dev]`): declare -0.1 ppm,
ignore -0.4 ppm, exclude +0.3 ppm. The ignore arm still inflates the cell's
esd 9.9x and Rwp 4.4x. WP-2002's width twin hold (#1113) moved the ignore arm
from 1.9.0's +6.3 ppm. The two arms' cells are now 0.3 ppm apart against the
ignore arm's esd of 51 ppm, a difference no platform can be trusted to order,
so the test asserts the inflated esd instead (WP-2036, 2026-10-25). That esd
reports the worse fit, since an esd scales with √χ²; it does not measure a
bias (McCusker et al. 1999, §10; `docs/practice.md`).

**The honest reading, and it is not the one this WP assumed.** Declaring
recovers the clean cell (-1.0 ppm) and ignoring does not (+7.6 ppm, with the
esd inflated 7.5x, 8.7x on the 1.6.0 tree, and Rwp 3.7x) — on that tree. Since
WP-2002 ignoring recovers it too (-0.4 ppm, above), and only the inflated esd
separates the arms. But *excluding also
recovers it*, to +0.6 ppm, for 256 channels (4.8 %). On this fixture the case
for declaring is **not** cell accuracy over exclusion. It is that the channels
stay in the fit, and that the intruder is measured rather than discarded:
areas 123.4(36) and 124.5(20) against a truth of 120, centres within 0.005°.

Where exclusion would cost more is where LaB6 costs least — a pattern with few
reflections, or a series whose trajectory needs every one of them. That is the
operando case this member was designed for, and this fixture is not it. Said
here rather than left for a reader to infer from a row that looks like a win.

`EXTRA_PEAK_ON_REFLECTION` fires twice on the declare arm, which is correct:
the lines were injected *onto* reflections, so the intensity split between
phase and component is exactly the degeneracy that diagnostic names. The
slightly-high recovered areas (both ~1-2σ above truth) are that degeneracy
being real, not the fit being wrong.

This module pins the orderings that make the feature worth having, not the
digits.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import PeakComponent
from rietx.schemas.pattern import PatternData

pytestmark = [pytest.mark.slow, pytest.mark.xdist_group("extra-peaks")]

OUT = Path(__file__).parent / "output"

#: Where the injected holder lines sit, in deg 2θ.  Both are placed **on** LaB6
#: reflections rather than beside them: an intruder in empty background is a
#: region a caller can exclude for free, so it would measure nothing here.
#: Chosen from the fitted tick list of the clean arm, not by hand.
HOLDER_AREA = 120.0
HOLDER_FWHM = 0.16


def _inject(data: PatternData, centres, instrument) -> PatternData:
    """Add a holder doublet at each centre, using the package's own evaluator.

    The injected curve is `CompiledModel.extra_peak_curve` itself, which is the
    honest way round: the test is not measuring whether the model can fit its
    own shape (it can, exactly), it is measuring what the *cell* does when the
    intruder is modelled, ignored, or excluded.
    """
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable

    ins = instrument.model_copy(deep=True)
    ins.extra_components = [
        PeakComponent(
            label=f"holder {i}",
            center=Parameter(value=c, min=c - 0.4, max=c + 0.4, unit="deg"),
            area=Parameter(value=HOLDER_AREA, min=0.0, unit="counts*deg",
                           transform="softplus"),
            fwhm=Parameter(value=HOLDER_FWHM, min=0.005, max=0.5, unit="deg",
                           transform="softplus"))
        for i, c in enumerate(centres)]

    from tests.test_acceptance_srm660c import build_srm_inputs
    structure, _ = build_srm_inputs()[1], None
    blank = PatternData(two_theta=list(data.two_theta),
                        intensity=[0.0] * len(data.two_theta))
    table = ParameterTable(structure, ins)
    model = compile_model(structure, ins, blank, mode="rietveld",
                          moving_paths=set(table.moving_paths))
    extra = np.asarray(model.extra_peak_curve(table.decode(table.x0())))

    return PatternData(
        two_theta=list(data.two_theta),
        intensity=(np.asarray(data.intensity) + extra).tolist(),
        sigma=list(data.sigma) if data.sigma is not None else None)


def _plan(extra_stage: bool):
    from tests.test_acceptance_srm660c import _nist_calibrated_plan

    plan = _nist_calibrated_plan()
    if extra_stage:
        stages = list(plan.stages)
        # after scale/background/displacement, before the cell: a component
        # turned on over a pattern whose level has not been set absorbs
        # whatever is nearest, and turned on after the cell it has nothing left
        # to correct
        stages.insert(2, rx.Stage("holder", ["instrument.extra_components.*"]))
        plan = rx.RefinementPlan(stages=stages)
        plan.intermediate_ftol = 1e-6
        plan.closing_window_tol = 1e-3   # WP-2002: the shipped closing stage, named rather than inherited
    return plan


def _fit(data, structure, instrument, *, components=(), excluded=(),
         extra_stage=False):
    ins = instrument.model_copy(deep=True)
    ins.extra_components = list(components)
    ref = rx.Refinement(structure.model_copy(deep=True), ins, history=False)
    kwargs = {}
    if excluded:
        d = PatternData(two_theta=list(data.two_theta),
                        intensity=list(data.intensity),
                        sigma=(list(data.sigma) if data.sigma is not None
                               else None),
                        excluded_regions=list(excluded))
    else:
        d = data
    return ref.fit(d, plan=_plan(extra_stage), **kwargs)


@pytest.fixture(scope="module")
def arms():
    """The four arms, fitted once: clean, ignore, declare, exclude."""
    from tests.test_acceptance_srm660c import build_srm_inputs

    data, structure, instrument = build_srm_inputs()
    # Dispersion DECLINED explicitly, inherited from nothing
    # (tests/test_validation_matrix.py): `build_srm_inputs` already declines it
    # because SRM 660c is this suite's dispersion-OFF anchor, and every arm here
    # is compared against the *clean* arm of the same protocol — so the setting
    # only has to be the same in all four, and it has to be stated rather than
    # ridden in from a default that may move.
    assert instrument.source.dispersion is None

    clean = _fit(data, structure, instrument)

    # two strong LaB6 reflections from the clean fit's own tick list
    ticks = sorted(clean.ticks["LaB6"])
    inside = [t for t in ticks if 30.0 < t < 80.0]
    centres = [inside[2], inside[5]]

    dirty = _inject(data, centres, instrument)

    ignored = _fit(dirty, structure, instrument)

    declared = [
        PeakComponent(
            label=f"holder {i}",
            center=Parameter(value=c, min=c - 0.4, max=c + 0.4, unit="deg"),
            area=Parameter(value=HOLDER_AREA * 0.6, min=0.0,
                           unit="counts*deg", transform="softplus"),
            fwhm=Parameter(value=HOLDER_FWHM * 0.8, min=0.005, max=0.5,
                           unit="deg", transform="softplus"))
        for i, c in enumerate(centres)]
    told = _fit(dirty, structure, instrument, components=declared,
                extra_stage=True)

    # the alternative: mask both intruders, and the sample peaks beneath them
    half = 4.0 * HOLDER_FWHM
    regions = [(c - half, c + half) for c in centres]
    excluded = _fit(dirty, structure, instrument, excluded=regions)

    return {"centres": centres, "regions": regions, "clean": clean,
            "ignore": ignored, "declare": told, "exclude": excluded}


def _a(result) -> tuple[float, float | None]:
    row = result.parameter("phases.0.cell.a")
    return float(row.value), (None if row.stderr is None else float(row.stderr))


def test_declaring_the_intruder_recovers_the_clean_cell(arms):
    """The measurement this WP exists for.

    The cell from the contaminated pattern with the holder lines **declared**
    must land on the cell from the clean pattern, in ppm of the clean cell so
    the bar does not depend on LaB6's own edge length.  With them ignored the
    cell's reported esd must be several times the clean one's: 9.9x measured
    (2026-10-25, macOS arm64, `[dev]`), against a bar of 5.  Which arm lands
    closer is not asserted, being 0.3 ppm against an esd of 51.
    """
    a_clean, sd_clean = _a(arms["clean"])
    a_declare, _ = _a(arms["declare"])
    a_ignore, sd_ignore = _a(arms["ignore"])
    assert sd_clean is not None and sd_ignore is not None, (sd_clean, sd_ignore)

    ppm = lambda a: 1e6 * (a - a_clean) / a_clean          # noqa: E731
    assert abs(ppm(a_declare)) < 20.0, (a_declare, a_clean)
    assert sd_ignore > 5.0 * sd_clean, (sd_ignore, sd_clean)


def test_the_excluded_regions_alternative_is_quoted_and_never_gated(arms):
    """The package recommends through evidence; the caller chooses.

    Excluding both regions is a legitimate answer and this test does not say
    otherwise — on this fixture it is a *good* one, +0.6 ppm against the clean
    cell for 256 channels (see the module docstring, which says so rather than
    letting the comparison read as a win it is not).  What this pins is that
    the choice is *visible*: the alternative runs, produces a cell, and costs a
    countable number of channels — and no code path anywhere refused either
    arm.  The caller decides whether 4.8 % of their pattern is worth the
    intruder being measured instead of masked.
    """
    a_clean, _ = _a(arms["clean"])
    a_exclude, _ = _a(arms["exclude"])
    assert arms["exclude"].status in ("converged", "max_iter")

    lost = len(arms["clean"].two_theta) - len(arms["exclude"].two_theta)
    assert lost > 0
    # the masked channels carried sample peaks: the excluded arm fits fewer
    # reflections, which is the cost the caller is choosing to pay
    assert abs(1e6 * (a_exclude - a_clean) / a_clean) < 500.0


def test_the_declared_holder_lines_come_back_where_they_were_put(arms):
    """A recovered position is what makes the rest of the arm believable."""
    got = sorted(p.value for p in arms["declare"].parameters
                 if p.path.endswith(".center"))
    assert len(got) == 2
    for found, put in zip(got, sorted(arms["centres"]), strict=True):
        assert abs(found - put) < 0.05, (found, put)

    areas = [p for p in arms["declare"].parameters if p.path.endswith(".area")]
    assert all(p.value > 0.0 for p in areas)
    assert all(p.stderr is not None for p in areas)


def test_the_declared_peaks_are_ticks_and_not_background(arms):
    """Clause 2's destination, on real data."""
    from rietx.model.components import EXTRA_TICK_KEY

    result = arms["declare"]
    assert EXTRA_TICK_KEY in result.ticks
    assert len(result.ticks[EXTRA_TICK_KEY]) == 4        # two peaks, two lines

    # The reported background is the Chebyshev alone.  Asserted locally, at
    # each holder centre: across a window a few FWHM wide the background varies
    # by a small fraction of the peak standing on it, which a background
    # carrying the holder line could not do.  (Not asserted as global
    # smoothness — this pattern is 24 stitched scan regions, so the background
    # is genuinely not smooth in *index* space across a region boundary.)
    tt = np.asarray(result.two_theta)
    bkg = np.asarray(result.y_background)
    y = np.asarray(result.y_calc)
    for c in arms["centres"]:
        win = np.abs(tt - c) < 3.0 * HOLDER_FWHM
        assert win.sum() > 10
        peak_height = float(np.max(y[win]) - np.min(bkg[win]))
        bkg_swing = float(np.max(bkg[win]) - np.min(bkg[win]))
        assert bkg_swing < 0.02 * peak_height, (c, bkg_swing, peak_height)


def test_the_arms_are_plotted_for_inspection(arms):
    """obs/calc/diff for every arm, plus a zoom on each injected line.

    Written because a number agreeing is not the same as a fit being right, and
    the zooms are where the difference between the three treatments is actually
    visible.
    """
    from rietx.viz.plots import plot_result

    OUT.mkdir(exist_ok=True)
    written = []
    for name in ("clean", "ignore", "declare", "exclude"):
        path = OUT / f"extra_peaks_{name}.png"
        plot_result(arms[name], path=str(path))
        written.append(path)
        for i, c in enumerate(arms["centres"]):
            zoom = OUT / f"extra_peaks_{name}_zoom{i}.png"
            plot_result(arms[name], path=str(zoom),
                        two_theta_range=(c - 1.5, c + 1.5))
            written.append(zoom)
    assert all(q.exists() and q.stat().st_size > 0 for q in written)
