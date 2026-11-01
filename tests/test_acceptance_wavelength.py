"""Acceptance: a refinable wavelength, on the published Nd₂Ru₂O₇ refinement.

The feature exists so that rietx can do what one sentence of a published paper
describes.  Gaultois *et al.*, *J. Phys.: Condens. Matter* (2013), ms.
CM/461205, refined one Nd₂Ru₂O₇ specimen jointly against an APS 11-BM
synchrotron histogram and an NCNR BT-1 constant-wavelength neutron histogram,
and says of its own protocol:

    "the synchrotron X-ray wavelength was fixed while the neutron wavelength
    was allowed to vary, though the refined wavelength was within two standard
    deviations of the starting value"

That is the whole of this WP in the authors' words, and until now rietx refused
it — ``EmissionLine.wavelength`` was a plain float.  The datasets are the two
histograms of that refinement (``tests/data/README.md`` has the provenance and
the published reference values).

**Why the X-ray wavelength is the one to hold**, rather than either being an
arbitrary choice: 49 493 points at λ = 0.4132950 Å against 3 296 points at
λ = 1.54040 Å.  The synchrotron's wavelength calibration is the better known
*and* its angular resolution makes its cell the better determined, so the cell
belongs to the X-ray data; the neutron data's unique contribution is the
structural content that its scattering-length contrast buys.  Holding the
wavelength of the histogram that owns the cell is what makes the other
histogram's monochromator calibration measurable at all.

Measured here, 2026-08-24, single-phase Fd-3m:2, ``mccusker_structural`` plus a
final stage freeing {λ, cell, coordinates}, 8-term Chebyshev backgrounds, X-ray
2-46° and neutron 5-155°, unit histogram weights (each point's esd governs):

===========================  =========  =========  ==============  ==========
protocol                     Rwp X-ray  Rwp n      a (Å)           λ moved
===========================  =========  =========  ==============  ==========
X-ray alone                  0.09364    —          10.342905(61)   —
neutron alone                —          0.05259    10.340285(222)  —
joint, both λ held           0.09373    0.06226    10.342883(60)   —
joint, X-ray held, n free    0.09371    0.05502    10.342904(60)   +257.6 ppm
joint, n held, X-ray free    0.09371    0.05502    10.340249(661)  −256.7 ppm
===========================  =========  =========  ==============  ==========

Three things in that table are the acceptance, and each is a separate test
below.

1. **Forcing one cell with both λ held costs the neutron histogram**, 0.05259
   alone to 0.06226 jointly, while the X-ray histogram barely notices
   (0.09364 → 0.09373).  The joint fit dumps the calibration mismatch onto the
   histogram with less leverage on the cell.  Freeing the neutron λ recovers it
   to 0.05502.
2. **The refined λ measures the mismatch the two solo cells already showed.**
   The solo cells differ by +253 ppm (10.342905 against 10.340285) and the
   refined neutron λ moves +257.6 ppm — the same number by an independent
   route, agreeing to 2 % of itself.  λ(Cu311) 1.540400 → 1.5407968(989).
3. **The answer does not depend on which end you hold.**  Swapping the roles
   gives −256.7 ppm against +257.6, i.e. the same calibration ratio measured
   from either side, agreeing to 0.9 ppm.  That is exactly what
   {eq}`pos-lambda-cell` predicts: the fit determines λ_n/λ_x and one cell
   scale, and *which* λ is "the error" is the user's choice of what to hold.

Honest notes on what this does **not** reproduce:

* The published a = 10.342312(8) Å is 57 ppm below the 10.342904 here.  This is
  a **single-phase** fit; the paper refines 0.5(1) mol % RuO₂ alongside, models
  the Cu(311) monochromator's second-order λ/2 contribution (which the paper
  states explicitly and this package does not model at all), and used its own
  background and 2θ ranges.  x(O 48f) 0.32994(51) against the published
  0.33012(7) is inside this fit's own esd.
* The published λ refined to 1.5406704 Å, +176 ppm, against +258 ppm here — the
  same sign and order from a different code and a different model.  The
  unmodelled λ/2 contamination is the obvious candidate for the difference and
  is out of scope for this WP.
"""

import math
from pathlib import Path

import pytest
from scipy.stats import chi2

import rietx as rx
from rietx.schemas.common import Parameter as P
from rietx.schemas.instrument import BackgroundChebyshev, Dispersion
from rietx.schemas.interval import PARAMETER_INTERVAL_CHI2_TOL, PARAMETER_INTERVAL_XTOL
from rietx.schemas.structure import Atom, Cell, Phase, Structure
from rietx.strategy.staged import PLAN_PRESETS, Stage

DATA = Path(__file__).parent / "data"
OUT = Path(__file__).parent / "output"

#: ``mg090.prm`` ICONS — the 11-BM instrument-parameter file's own wavelength.
LAM_XRAY = 0.4132950
#: ``mg090.Cu311.inst`` ICONS — BT-1 with a Cu(311) monochromator.
LAM_NEUTRON = 1.54040

XRAY_LIMITS = (2.0, 46.0)
NEUTRON_LIMITS = (5.0, 155.0)

#: Kennedy & Vogt (1996) is the citable *structure* reference; the numbers this
#: suite compares against are the published combined refinement's, on this
#: specimen — see the module docstring and tests/data/README.md.
A_PUBLISHED = 10.342312
X_O_PUBLISHED = 0.33012

pytestmark = [pytest.mark.slow, pytest.mark.xdist_group("wavelength")]


def _structure() -> Structure:
    """Nd₂Ru₂O₇ pyrochlore, Fd-3m:2, Kennedy & Vogt's site assignment.

    Nd on 16d (½,½,½), Ru on 16c (0,0,0), O1 on 48f (x,⅛,⅛) — the one free
    positional parameter — and O2 on 8b (⅜,⅜,⅜).
    """
    return Structure(phases=[Phase(
        name="Nd2Ru2O7", space_group="F d -3 m :2",
        cell=Cell(a=P(value=10.3423, min=9.5, max=11.0),
                  b=P(value=10.3423), c=P(value=10.3423),
                  alpha=P(value=90.0), beta=P(value=90.0), gamma=P(value=90.0)),
        scale=P(value=1.0, min=0.0, transform="softplus"),
        atoms=[
            Atom(label="Nd", species="Nd", x=P(value=0.5), y=P(value=0.5),
                 z=P(value=0.5), biso=P(value=0.5, min=0.0, max=5.0)),
            Atom(label="Ru", species="Ru", x=P(value=0.0), y=P(value=0.0),
                 z=P(value=0.0), biso=P(value=0.3, min=0.0, max=5.0)),
            Atom(label="O1", species="O", x=P(value=0.3301), y=P(value=0.125),
                 z=P(value=0.125), biso=P(value=0.6, min=0.0, max=5.0)),
            Atom(label="O2", species="O", x=P(value=0.375), y=P(value=0.375),
                 z=P(value=0.375), biso=P(value=0.5, min=0.0, max=5.0)),
        ])])


def _xray_instrument() -> rx.Instrument:
    """11-BM, with the profile seeded from ``mg090.prm``'s own PRCF record.

    GSAS quotes GU/GV/GW in centidegrees² and LX in centidegrees, so the .prm's
    1.163 / −0.126 / 0.063 / 0.173 arrive here divided by 10⁴ and 10²
    (a centidegree is 1e-2 degree, so LX/LY cross ÷1e2 and GU/GV/GW ÷1e4).
    ``rx.read_gsas_prm`` reads the same record and ``test_gsas_prm.py``'s
    ``test_the_unit_conversion_agrees_with_the_hand_transcription`` asserts the
    two agree; the prose here said 10³ until that test was written, against
    arithmetic that was right.
    """
    ins = rx.Instrument.debye_scherrer(wavelength=LAM_XRAY, polarization=0.990)
    ins.profile.u.value = 1.163e-4
    ins.profile.v.value = -1.26e-5
    ins.profile.w.value = 6.3e-6
    ins.profile.x.value = 1.73e-3
    ins.background = BackgroundChebyshev.with_terms(8)
    # Declared rather than inherited (tests/test_validation_matrix.py): f'/f" at
    # 30 keV are applied, which is the package default and the right choice
    # here — Nd's L3 edge is at 6.2 keV and Ru's K edge at 22.1 keV, so both are
    # off-edge at 0.4133 A and the table can answer.  The claim this suite makes
    # is about a *wavelength*, and dispersion is the one correction that is a
    # function of it, so riding a default would be the wrong kind of quiet.
    ins.source.dispersion = Dispersion()
    return ins


def _neutron_instrument() -> rx.Instrument:
    ins = rx.Instrument.constant_wavelength_neutron(LAM_NEUTRON, fwhm_deg=0.30)
    ins.background = BackgroundChebyshev.with_terms(8)
    # ``NeutronSource.dispersion`` is structurally None — f'/f" is an X-ray
    # core-level effect — so there is nothing to declare on this arm and nothing
    # a moving default could change.
    assert ins.source.dispersion is None
    return ins


def _plan(free_histogram: int | None) -> rx.RefinementPlan:
    """``mccusker_structural`` plus a final stage that frees one λ.

    The glob is **scoped** (``hist.N.…``), which is what makes "all but one"
    expressible: the bare path would free every histogram's copy and be
    refused.  The cell and the coordinates ride along in the same stage because
    λ trades against both, and the staged runner is cumulative — everything
    freed earlier is still free here.
    """
    plan = PLAN_PRESETS["mccusker_structural"]()
    if free_histogram is not None:
        plan.stages.append(Stage(
            "wavelength",
            [f"hist.{free_histogram}.instrument.source.lines.0.wavelength",
             "phases.*.cell.*", "phases.*.atoms.*.dof.*"]))
    # WP-1123's shipped schedule, named rather than inherited: every stage but
    # the last stops at 1e-6 and the last at the solver's 1e-9, which is what a
    # user's own run does.  ``None`` would converge every stage and move the
    # numbers in the module docstring.
    plan.intermediate_ftol = 1e-6
    plan.closing_window_tol = 1e-3   # WP-2002: the shipped closing stage, named rather than inherited
    return plan


def _patterns():
    for name in ("mg090.fxye", "mg090.Cu311.gsas"):
        if not (DATA / name).exists():
            pytest.skip(f"{name} not present")
    return (rx.read_pattern(DATA / "mg090.fxye"),
            rx.read_pattern(DATA / "mg090.Cu311.gsas"))


def _joint(free_histogram: int | None):
    data = _patterns()
    return rx.refine_multi(
        list(data), _structure(),
        [_xray_instrument(), _neutron_instrument()],
        plan=_plan(free_histogram),
        two_theta_limits=[XRAY_LIMITS, NEUTRON_LIMITS])


def _solo_refinement(which: int, nudge: int = 0, *,
                     y_floor: bool = False) -> rx.Refinement:
    """One histogram alone, fitted; the result is its ``result_``.  ``nudge``
    multiplies every refinable nonzero start value by (1 + nudge·1e-14), the
    size of the difference two platforms' arithmetic makes (WP-1929).
    ``y_floor`` declares Y ≥ 0, the floor WP-2002 removed from the default."""
    data = _patterns()[which]
    ins = _xray_instrument() if which == 0 else _neutron_instrument()
    if y_floor:
        ins.profile.y.min = 0.0
    lim = XRAY_LIMITS if which == 0 else NEUTRON_LIMITS
    ref = rx.Refinement(_structure(), ins, history=False)
    if nudge:
        ref.set_values({row.path: row.value * (1.0 + nudge * 1e-14)
                        for row in ref.parameters()
                        if row.refinable and row.value != 0.0})
    ref.fit(data, plan="mccusker_structural", two_theta_limits=lim)
    return ref


def _solo(which: int, nudge: int = 0):
    return _solo_refinement(which, nudge).result_


@pytest.fixture(scope="module")
def solo_xray():
    return _solo(0)


@pytest.fixture(scope="module")
def solo_neutron_refinement():
    """The neutron fit's ``Refinement``, for the probes a result cannot run."""
    return _solo_refinement(1)


@pytest.fixture(scope="module")
def solo_neutron(solo_neutron_refinement):
    return solo_neutron_refinement.result_


@pytest.fixture(scope="module")
def solo_neutron_floored_refinement():
    """The neutron fit with Y ≥ 0 declared by the caller, where Y lands on it."""
    return _solo_refinement(1, y_floor=True)


@pytest.fixture(scope="module")
def joint_held():
    """Both wavelengths held — the only protocol available before this WP."""
    return _joint(None)


@pytest.fixture(scope="module")
def joint_neutron_free():
    """The published protocol: X-ray λ fixed, neutron λ refined."""
    return _joint(1)


@pytest.fixture(scope="module")
def joint_xray_free():
    """The same fit with the roles swapped — the consistency check."""
    return _joint(0)


def _cell(result) -> float:
    return next(p.value for p in result.parameters
                if p.path.endswith("phases.0.cell.a"))


def _refined_wavelength(result, h: int):
    path = f"hist.{h}.instrument.source.lines.0.wavelength"
    row = next(p for p in result.parameters if p.path == path)
    return row.value, row.stderr


def _ppm_diagnostic(result, h: int):
    diags = [d for d in result.histograms[h].diagnostics
             if d.code == "WAVELENGTH_CALIBRATION"]
    assert len(diags) == 1, [d.code for d in result.histograms[h].diagnostics]
    return diags[0]


# --- 1. the cost of holding both, and its recovery -----------------------


def test_holding_both_wavelengths_costs_the_neutron_histogram(
        solo_neutron, solo_xray, joint_held):
    """One cell for two uncalibrated wavelengths lands on one histogram.

    This is the *problem statement*, asserted rather than asserted-about: the
    neutron histogram fits worse inside the joint fit than it does alone, by
    much more than the X-ray histogram does, because the shared cell is pinned
    by the histogram with 13× the points and 3.7× the angular leverage.  Read a
    firing of this as "the joint fit has nowhere to put the calibration
    mismatch", never as a data problem.
    """
    solo_n = solo_neutron.statistics.rwp
    solo_x = solo_xray.statistics.rwp
    joint_n = joint_held.histograms[1].statistics.rwp
    joint_x = joint_held.histograms[0].statistics.rwp
    # the neutron histogram degrades, and by an order more than the X-ray one
    assert joint_n > solo_n * 1.10
    assert joint_x == pytest.approx(solo_x, rel=0.01)
    assert (joint_n - solo_n) > 10.0 * abs(joint_x - solo_x)


def test_freeing_the_neutron_wavelength_recovers_its_fit(
        solo_neutron, joint_held, joint_neutron_free):
    """Rwp is *not* the evidence for the feature — it is the symptom.

    The evidence is the ppm diagnostic (next test).  What this asserts is the
    weaker and still necessary claim: the degradation the previous test
    measured goes away, so the extra freedom is absorbing the thing it was
    introduced for rather than buying Rwp somewhere unrelated.  The margin is
    loose on purpose — two independently converged fits differ by more than
    their own ftol (tests/CLAUDE.md).
    """
    solo = solo_neutron.statistics.rwp
    held = joint_held.histograms[1].statistics.rwp
    freed = joint_neutron_free.histograms[1].statistics.rwp
    assert freed < held
    # most of the way back to the solo fit, and never past it: the solo fit has
    # its own cell, so it is the floor this protocol can approach
    assert (held - freed) > 0.5 * (held - solo)
    assert freed > solo * 0.95
    # the X-ray histogram is not paying for it
    assert (joint_neutron_free.histograms[0].statistics.rwp
            == pytest.approx(joint_held.histograms[0].statistics.rwp, rel=0.01))


# --- 2. the refined wavelength is the measured cell mismatch ------------


def test_the_refined_wavelength_is_the_solo_cell_disagreement(
        solo_xray, solo_neutron, joint_neutron_free):
    """+258 ppm from the fit against +253 ppm from two independent fits.

    The two histograms refined separately give two cells, and the ratio of
    those cells is a *prediction* for how far the neutron λ must move to fit
    the X-ray's cell — arrived at without freeing anything.  Agreement between
    the two is the feature working, and it is the assertion this suite exists
    for.  The bar is 20 % of the effect, which is the scatter two separately
    converged single-histogram fits carry, not the solver's tolerance.
    """
    cell_ppm = 1e6 * (_cell(solo_xray) - _cell(solo_neutron)) / _cell(solo_xray)
    lam, esd = _refined_wavelength(joint_neutron_free, 1)
    fit_ppm = 1e6 * (lam - LAM_NEUTRON) / LAM_NEUTRON
    assert cell_ppm > 100.0, "the two solo cells agree; nothing to measure"
    assert fit_ppm == pytest.approx(cell_ppm, rel=0.20)
    # …and it is resolved, which a freed parameter need not be
    assert esd is not None and abs(lam - LAM_NEUTRON) > 2.0 * esd


def test_the_diagnostic_reports_the_ppm_and_nothing_claims_rwp(
        joint_neutron_free, joint_held):
    """The record field this correction ships with (root CLAUDE.md's rule).

    ``WAVELENGTH_CALIBRATION`` fires exactly where a wavelength was refined and
    nowhere else, carries the ppm as ``Diagnostic.value`` so a client never
    parses the message, and points at the scoped path.
    """
    diag = _ppm_diagnostic(joint_neutron_free, 1)
    lam, _ = _refined_wavelength(joint_neutron_free, 1)
    assert diag.level == "info"
    assert diag.value == pytest.approx(
        1e6 * (lam - LAM_NEUTRON) / LAM_NEUTRON, rel=1e-9)
    assert diag.where == ["hist.1.instrument.source.lines.0.wavelength"]
    # the histogram whose λ was held says nothing, and neither does the fit
    # that held both — silence is the absence of a refinement, not a clean bill
    assert not [d for d in joint_neutron_free.histograms[0].diagnostics
                if d.code == "WAVELENGTH_CALIBRATION"]
    assert not [d for h in joint_held.histograms for d in h.diagnostics
                if d.code == "WAVELENGTH_CALIBRATION"]


def test_the_cell_belongs_to_the_synchrotron(solo_xray, joint_neutron_free):
    """Holding the X-ray λ hands the cell to the X-ray histogram, as intended.

    The joint cell lands on the X-ray solo cell rather than between the two,
    which is the accuracy hierarchy in action: 49 493 points at 0.413 Å own the
    lattice, and the neutron λ moves to meet it.  Also checked against the
    published value, which this single-phase fit sits 57 ppm above — see the
    module docstring for why that gap is expected and not a regression.
    """
    joint = _cell(joint_neutron_free)
    assert joint == pytest.approx(_cell(solo_xray), rel=5e-6)
    assert joint == pytest.approx(A_PUBLISHED, rel=2e-4)
    x_o = next(p.value for p in joint_neutron_free.parameters
               if p.path.endswith("atoms.2.x"))
    assert x_o == pytest.approx(X_O_PUBLISHED, abs=1e-3)


# --- 3. the answer does not depend on which end is held -----------------


def test_swapping_which_wavelength_is_held_measures_the_same_ratio(
        joint_neutron_free, joint_xray_free):
    """The consistency check, and the sharpest statement of the physics.

    A joint fit determines the *ratio* λ_n/λ_x together with one cell scale —
    eq. pos-lambda-cell — so calling one of them "the calibration error" is a
    choice of what to hold, not a result.  Holding the other end must therefore
    give the same mismatch with the opposite sign.  It does, to under 1 ppm on
    an effect of 257, and every histogram's Rwp and the shared x(O) are
    unchanged: the two runs are the same fit in two parameterisations.
    """
    lam_n, _ = _refined_wavelength(joint_neutron_free, 1)
    lam_x, _ = _refined_wavelength(joint_xray_free, 0)
    ppm_n = 1e6 * (lam_n - LAM_NEUTRON) / LAM_NEUTRON
    ppm_x = 1e6 * (lam_x - LAM_XRAY) / LAM_XRAY
    assert ppm_n > 0.0 and ppm_x < 0.0
    # the sizes agree well inside the effect; they are not identical because
    # each ppm is referred to its own λ and the two runs land on different
    # shared cells
    assert abs(ppm_n + ppm_x) < 0.02 * abs(ppm_n)
    for h in (0, 1):
        assert (joint_xray_free.histograms[h].statistics.rwp
                == pytest.approx(
                    joint_neutron_free.histograms[h].statistics.rwp, rel=2e-3))
    x_free_n = next(p.value for p in joint_neutron_free.parameters
                    if p.path.endswith("atoms.2.x"))
    x_free_x = next(p.value for p in joint_xray_free.parameters
                    if p.path.endswith("atoms.2.x"))
    assert x_free_n == pytest.approx(x_free_x, abs=1e-5)


def test_the_neutron_widths_leave_one_esd_at_every_start(solo_neutron):
    """Issue #831: the neutron fit's Lorentzian ``y`` refined to its floor of
    0, and while widths refined in softplus coordinates its column was
    differenced below rounding.  The noise then set ``x``'s esd: 0.00322 on
    Linux against 0.00664 on macOS, and 0.0032 to 0.0089 on one Mac with every
    start nudged by 1e-14.  Refining in physical units (WP-1938) and behind the
    closing stage (WP-2002) it was 0.0102720 at four starts, spread 1.5e-8.
    Since WP-2002 removed Y's floor (2026-10-23), ``y`` refines to
    −0.0210949(191), inside its own esd of 0, and ``x``'s esd is 0.0102922 at
    the same four starts, spread 1.5e-9 (macOS arm64).  The floor's own case
    is the next test's, with the floor declared.
    """
    fits = [solo_neutron, *(_solo(1, k) for k in (1, -1, 2))]
    rows = [{p.path: p for p in fit.parameters} for fit in fits]
    x = [r["instrument.profile.x"].stderr for r in rows]
    assert x == [pytest.approx(0.0102922, rel=1e-4)] * len(x)
    assert max(x) / min(x) - 1.0 < 1e-6
    for r in rows:
        y = r["instrument.profile.y"]
        assert y.value == pytest.approx(-0.0210949, rel=1e-4)
        assert y.at_bound is False
        assert y.stderr == pytest.approx(0.0190970, rel=1e-4)


def test_a_width_on_its_floor_has_a_one_sided_profile_interval(
        solo_neutron_floored_refinement):
    """WP-1929: ``y`` = 0 ± 0.018101 is no interval, so the profile gives one.
    Y has no floor of its own since WP-2002, so the caller declares one here,
    the case this test keeps: ``y`` = 0 ± 0.0189972 on it.

    The bound is the lower end.  The upper end is where the data's χ² has
    risen by χ²₁(0.90) × χ²_red × f² (Self & Liang's mixture), solved by
    pinned refits.  Measured on macOS arm64: 0.0166098, the same to 5e-10
    relative at six starts nudged by 1e-14, at Δχ² 0.0044 under a cut of
    21.343, in 19 refits and 3 s.  With U and V free to go negative since
    WP-2002 the end is 0.0164535, at a cut of 21.048 (2026-10-23).

    The end is 0.558 of √2.706 × esd = 0.0298, the end a floor that is a
    stationary point would give.  This one is not.  ``at_bound`` reads LM's
    active set, which says the gradient at 0 points out of the range, so χ²
    rises from the floor with a slope as well as a curvature and reaches the
    cut sooner.  Pinned at one esd, Δχ² is 23.5, three times the 7.89 a
    stationary floor would give.  The band is ten times the end's own solve
    tolerance, a thousandth of an esd.
    """
    data = _patterns()[1]
    interval = solo_neutron_floored_refinement.profile_interval(
        data, "instrument.profile.y")
    assert interval.one_sided and interval.at_bound is True
    assert (interval.lower, interval.lower_stop) == (0.0, "bound")
    assert interval.upper_stop == "threshold"
    assert interval.quantile == pytest.approx(chi2.ppf(0.90, 1), rel=1e-12)
    [end] = [p for p in interval.points if p.value == interval.upper]
    assert abs(end.delta_chi2 - interval.delta_chi2_cut) <= (
        PARAMETER_INTERVAL_CHI2_TOL * interval.delta_chi2_cut)
    assert interval.upper < math.sqrt(interval.quantile) * interval.stderr
    assert interval.upper == pytest.approx(
        0.0164535, abs=10 * PARAMETER_INTERVAL_XTOL * interval.stderr)


def test_the_fits_render(joint_neutron_free):
    """obs/calc/diff per histogram, as the other real-data suites write them."""
    OUT.mkdir(exist_ok=True)
    for h in range(2):
        path = OUT / f"mg090_joint_hist{h}.png"
        joint_neutron_free.for_histogram(h).plot(path=str(path))
        assert path.exists()
