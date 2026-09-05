"""Acceptance: two-phase QPA on an 11-BM LaB6 + cBN histogram.

Real data, real esds, and a solved TOPAS refinement to check against —
``11BM_LaB6_cBN_mg2044.xye``, APS 11-BM, λ = 0.413680 Å from the ``.prm``
ICONS record, 49 496 channels at 0.001° over 0.5–49.99° 2θ.  The specimen is
NIST **SRM 660b LaB6** at ~18 wt % in a cubic-BN matrix, and LaB6's certified
cell is the internal standard that makes cBN's measurable.

**cBN is a diluent, not a second standard**, and that is why the specimen looks
the way it does.  It is light (B, N against La), so it cuts the absorption of an
otherwise very absorbing LaB6 packing without contributing much intensity of its
own; it is hard and well-crystallised, so it gives sharp peaks that do not smear
the standard's; and it is chemically inert against LaB6.  Those are the
properties a diluent is chosen for, and none of them is a certified quantity —
which is the whole reason every claim below is cross-code.

**There is no weighed composition, so the QPA claim is cross-code only.**  The
``.inp``'s ``weight_percent … 17.950`` carries TOPAS's backtick — it is a
*derived output*, not an input, and the folder's ``simulation_quant.txt``
records 17.907 from a second run.  Nothing states how the specimen was made.
So this suite is referenced to TOPAS, at the resolution TOPAS agrees with
itself: its two shipped models of this histogram (``…_cs_mustr`` and
``…_IB-size-strain``) give **LaB6 17.950 and 17.907 wt %** — a 0.043 wt %
model-to-model spread — and **cBN a = 3.616463 and 3.616466 Å**, 0.8 ppm apart.
That spread, not an invented tolerance, is what "agreement" has to mean here.

**σ is the file's, and it is not Poisson** — 11-BM sums twelve analyser
crystals, so the third column is a propagated esd (median σ/√I = 0.94 over the
fitted range but 1.45 below 2.5°, i.e. angle-dependent in a way √I cannot be;
0.98 is the whole-file median, and the fitted-range figure is the right one to
pair against 1.45 here).  ``read_pattern`` uses it; this suite would be
measuring a different quantity if it did not.

The three TOPAS reference files this suite is referenced to —
``lab6_pvii_absorb_cs_mustr.inp``/``.out``, ``lab6_pvii_absorb_IB-size-strain``
``.inp``/``.out`` and ``simulation_quant.txt`` — are **not committed**: they
live on the data owner's archive, not in ``tests/data/``.  The protocol is
transcribed below and the reference values into ``tests/validation_matrix.py``,
so nothing here reads them at run time, but the source files themselves are not
in this repo (see tests/data/README.md).

Protocol, mirrored from ``lab6_pvii_absorb_cs_mustr.inp`` (see
tests/data/README.md):

* ``start_X 5.1`` → the fit starts at 5.1°, discarding 4601 channels.  The
  reference never saw them, so neither does this.
* ``Zero_Error(0.0)`` — zero **held**, specimen displacement refined instead.
  The .inp says why in its own comment: the two are highly correlated.
* LaB6's cell is **held** at the SRM 660b certificate value 4.15689 Å.  That
  is what makes it an internal standard rather than a second unknown.
* Dispersion declined explicitly (WP-1001 made it the default): at 0.4137 Å
  every species here is far above its K edge, but "nearly inert" is a
  measurement and not a licence to leave the setting implicit.

**What this test is really about is the broadening parameterisation**, and the
headline is that the *lowest* Rwp is the *worst* answer.  See
``test_the_lowest_rwp_is_the_worst_answer`` — it is the finding, not a caveat.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import rietx as rx
from rietx.schemas.instrument import BackgroundChebyshev

DATA = Path(__file__).parent / "data"
PATTERN = DATA / "11BM_LaB6_cBN_mg2044.xye"

WAVELENGTH = 0.413680          # .prm ICONS, and `la 1 lo 0.413680` in the .inp
LIMITS = (5.1, 50.0)           # start_X 5.1
#: NIST SRM 660b certificate, read from the certificate PDF that ships beside
#: the data: a = 0.415689 nm +- 0.000008 nm at 22.5 C (k = 2).  **HELD** — that
#: is what makes it an internal standard rather than a second unknown.
#:
#: The scan header records 295.0 K = 21.85 C, so the certificate temperature is
#: 0.65 K away.  At LaB6's expansion that is of order 4 ppm in a — below every
#: band this suite asserts, but stated because the SRM 660c suite documents the
#: same gap and a silent one reads as no gap at all.
A_LAB6 = 4.15689
A_LAB6_CERT_SD = 0.00008

#: The converged TOPAS values, read from the .inp's own recorded numbers.
TOPAS = {
    "rwp": 0.0809856, "rexp": 0.0529264, "gof": 1.53015,
    "a_cbn": 3.616463, "x_b_lab6": 0.19890, "w_lab6": 17.950,
}

#: The composition reference, per the data owner (2026-08-25): the weight
#: fractions in the folder's ``simulation_quant.txt``, LaB6 17.90681 /
#: cBN 82.09319.  Recorded here with what it is and is not — those digits are
#: TOPAS's own output (they match the ``IB-size-strain`` model's refined
#: ``weight_percent ph1_wtpct 17.907``, and both .inp files mark the field with
#: TOPAS's backtick), so this stays a **cross-code** reference.  No balance
#: record exists, and per the owner none is expected: LaB6 is the ~18 wt %
#: internal standard scooped into the cBN matrix, at textbook internal-standard
#: loading, and the exact figure was never the point since neither the loading
#: nor the cBN is certified.  For the curious it is a molar ratio of
#: LaB6 : cBN = 1 : 37.64 and a mass ratio of 1 : 4.58 — neither round, which
#: is what "scooped" looks like and is why no target is recoverable from it.
COMPOSITION_SOURCE = "simulation_quant.txt"

#: TOPAS's **own** spread across its two shipped models of this histogram —
#: ``…_cs_mustr`` and ``…_IB-size-strain``.  Quoted rather than averaged,
#: because the gap between them is the reference's resolution: no comparison
#: here can mean anything tighter, and a bar inside it would be measuring
#: TOPAS's choice of broadening model rather than rietx.
TOPAS_SPREAD = {
    "w_lab6": (17.907, 17.950),          # wt %, 0.043 apart
    "a_cbn": (3.616463, 3.616466),       # Å, 0.8 ppm apart
    "rwp": (0.0804733, 0.0809856),
}

pytestmark = pytest.mark.slow


def _lab6() -> rx.Phase:
    """Pm-3m: La at 1a (0,0,0), B at 6f (x,½,½).  x is the one free coordinate."""
    P = rx.Parameter
    return rx.Phase(
        name="LaB6", space_group="P m -3 m", cell=rx.Cell.cubic(A_LAB6),
        atoms=[
            rx.Atom(label="La1", species="La", x=P(value=0.0), y=P(value=0.0),
                    z=P(value=0.0), biso=P(value=0.44)),
            rx.Atom(label="B1", species="B", x=P(value=0.1989), y=P(value=0.5),
                    z=P(value=0.5), biso=P(value=0.31)),
        ])


def _cbn() -> rx.Phase:
    """F-43m zincblende, in the .inp's own setting: N at 4a, B at 4c."""
    P = rx.Parameter
    return rx.Phase(
        name="cBN", space_group="F -4 3 m", cell=rx.Cell.cubic(3.6164),
        atoms=[
            rx.Atom(label="N1", species="N", x=P(value=0.0), y=P(value=0.0),
                    z=P(value=0.0), biso=P(value=0.31)),
            rx.Atom(label="B1", species="B", x=P(value=0.25), y=P(value=0.25),
                    z=P(value=0.25), biso=P(value=0.47)),
        ])


def _inputs():
    structure = rx.Structure(phases=[_lab6(), _cbn()])
    structure.phases[0].scale.value = 2.2e-4
    structure.phases[1].scale.value = 3.2e-3
    ins = rx.Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.source.dispersion = None
    ins.profile.w.value = 2e-5          # 11-BM is a very sharp instrument
    ins.profile.x.value = 2e-3
    ins.background = BackgroundChebyshev.with_terms(16)
    ins.zero_shift.value = 0.0          # held; displacement refines instead
    return structure, ins


#: The shipped schedule, declared rather than inherited (WP-1123).  ``None``
#: is the fully-converged one; this suite wants the default, and says so, so
#: that a future change to ``INTERMEDIATE_FTOL_DEFAULT`` shows up here as a
#: decision rather than as a silent shift in the numbers above.
INTERMEDIATE_FTOL = None   # i.e. plan.intermediate_ftol left at the shipped default

_BASE = [
    rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
    rx.Stage("displacement", ["instrument.geometry.sample_displacement"]),
    rx.Stage("cell_cbn", ["phases.1.cell.*"]),
    rx.Stage("profile_w", ["instrument.profile.w"]),
]
_TAIL = [
    rx.Stage("coordinates", ["phases.*.atoms.*.dof.*"]),
    rx.Stage("biso", ["phases.*.atoms.*.biso"]),
]

#: **The protocol this suite trusts**, and the reason is identifiability rather
#: than physics.  One Lorentzian broadening, carried by the instrument and
#: shared by both phases.  Lorentzian FWHMs add, so instrument ``X,Y`` and
#: per-phase ``lor_size``/``lor_strain`` are one quantity split three ways —
#: measured at |ρ| = 1.000 — and this is the only one of the three tried that
#: is not degenerate.
#:
#: **It is not the physically complete model, and saying so is the point.**
#: SRM 660b's certificate carries Information Values from NIST's own
#: fundamental-parameters analysis: a Lorentzian FWHM refined for
#: sample-induced broadening, whose 1/cos θ term is *"consistent with a domain
#: size of approximately 0.7 µm"* while the tan θ term *"refined to zero"*.  So
#: the strain half of the shared model is right by certificate, and the size
#: half is an approximation — 0.7 µm domains are finer than SRM 640c Si's
#: 1.4 µm, and at 11-BM's resolution that is not obviously negligible.
#:
#: The symmetric fix — hold *each* phase's ``lor_size`` at its certificate
#: value — is **impossible**, and for a reason worth stating: LaB6 is the
#: certified standard, the cBN came out of a bottle.  It was chosen for sharp
#: peaks, and the measurement existed to *determine* cBN's cell for later use
#: on lab instruments.  There is no cBN certificate and there will not be one.
#:
#: The asymmetric version — pin the standard's broadening, free the unknown's —
#: **was tried and is not better** (measured, see this suite's PR).  LaB6's
#: ``lor_size`` held at the certificate's 0.7 µm gives the closest cBN cell of
#: any variant (+6.7 ppm against TOPAS, versus +14 here) and stays identifiable,
#: but Rwp is 40 % worse and the QPA moves 3.2σ out — and *both* of cBN's
#: broadening terms refine to exactly their softplus floor, i.e. the fit wants
#: negative broadening for cBN once the instrument has absorbed the pinned
#: LaB6 value.  That says the certificate's 0.7 µm is inconsistent with this
#: instrument's resolution *as this profile parameterises it*, which points at
#: the PVII/FPA gap below rather than at a different held number.
PLAN_SHARED = rx.RefinementPlan(stages=[
    *_BASE,
    rx.Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                         "instrument.profile.x", "instrument.profile.y"]),
    *_TAIL,
])

#: The same fit with the phases' Lorentzian terms freed *as well*.  Kept as a
#: fixture rather than deleted because it is the control for the finding below.
PLAN_DEGENERATE = rx.RefinementPlan(stages=[
    *_BASE,
    rx.Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                         "instrument.profile.x", "instrument.profile.y"]),
    rx.Stage("size_strain", ["phases.*.lor_size", "phases.*.lor_strain"]),
    *_TAIL,
])


def _fit(plan):
    data = rx.read_pattern(PATTERN)
    structure, ins = _inputs()
    ref = rx.Refinement(structure, ins, history=False)
    return ref.fit(data, plan=plan, two_theta_limits=LIMITS)


@pytest.fixture(scope="module")
def shared():
    if not PATTERN.exists():
        pytest.skip("11-BM LaB6+cBN dataset not present")
    return _fit(PLAN_SHARED)


@pytest.fixture(scope="module")
def degenerate():
    if not PATTERN.exists():
        pytest.skip("11-BM LaB6+cBN dataset not present")
    return _fit(PLAN_DEGENERATE)


def _weight_percent(result, name):
    row = next(r for r in result.qpa.phases if r.name == name)
    sd = row.weight_fraction_stderr
    return 100.0 * row.weight_fraction, (100.0 * sd if sd else None)


# --------------------------------------------------------------- protocol ---
def test_the_protocol_matches_before_any_number_is_compared(shared):
    """Rexp is the check that the two codes fitted the *same* problem.

    It depends only on the channels, their esds and the free-parameter count —
    not on the model — so agreement here means the range, the weighting and the
    excluded region match.  Without it, every comparison below could be
    explained by "they fitted different data", and that must not be one of the
    candidate explanations (the rule ``test_acceptance_nac`` states).
    """
    assert shared.status == "converged"
    assert shared.statistics.rexp == pytest.approx(TOPAS["rexp"], rel=1e-3)
    # start_X 5.1 discarded 4601 of the file's 49 496 channels
    assert len(shared.two_theta) == 44895


def test_the_file_esds_are_used_rather_than_poisson():
    """11-BM sums twelve analysers, so column 3 is not √I and must not be."""
    import numpy as np

    if not PATTERN.exists():
        pytest.skip("11-BM LaB6+cBN dataset not present")
    raw = np.loadtxt(PATTERN, comments=("/", "#"), usecols=(0, 1, 2))
    data = rx.read_pattern(PATTERN)
    assert np.allclose(data.sig(), raw[:, 2])
    # and it is genuinely not Poisson: the ratio to √I varies with angle
    ratio = raw[:, 2] / np.sqrt(np.maximum(raw[:, 1], 1.0))
    assert not np.allclose(ratio, 1.0, atol=0.05)


# ------------------------------------------------------- measured answers ---
def test_the_qpa_agrees_with_topas_within_its_own_esd(shared):
    """Cross-code QPA — there is no weighing, so TOPAS is the only referent.

    The bar is **this fit's own esd**, and the comparison is against TOPAS's
    two-model interval rather than a single number, because that interval is
    the reference's resolution (0.043 wt %).  Asserting tighter than TOPAS
    agrees with itself would be measuring its broadening model, not rietx.
    """
    w, sd = _weight_percent(shared, "LaB6")
    assert sd is not None, "QPA came back without an esd"
    lo, hi = TOPAS_SPREAD["w_lab6"]
    # distance to the interval, zero if inside it
    gap = max(lo - w, w - hi, 0.0)
    assert gap < 3.0 * sd, (
        f"LaB6 {w:.3f} ± {sd:.3f} wt %, {gap:.3f} outside TOPAS's "
        f"[{lo}, {hi}]")
    other, _ = _weight_percent(shared, "cBN")
    assert w + other == pytest.approx(100.0)


def test_the_cbn_cell_agrees_with_topas_to_better_than_50_ppm(shared):
    """cBN's cell, measured against LaB6's held certificate value.

    A **cross-code consistency** band, not a truth claim — the same status as
    the FAP suite's ±300 ppm. 50 ppm is the measured agreement with headroom,
    and it is only meaningful because LaB6's cell was held: that is what pins
    the length scale for the second phase.
    """
    a = next(p for p in shared.parameters if p.path == "phases.1.cell.a")
    ppm = 1e6 * (a.value - TOPAS["a_cbn"]) / TOPAS["a_cbn"]
    assert abs(ppm) < 50.0, f"cBN a = {a.value:.6f} Å, {ppm:+.1f} ppm from TOPAS"


def test_the_one_free_coordinate_agrees(shared):
    """LaB6's B x is the only free positional parameter in either phase, so it
    is the whole structural content of the fit rather than a detail."""
    x = next(p for p in shared.parameters if p.path == "phases.0.atoms.1.x")
    assert x.value == pytest.approx(TOPAS["x_b_lab6"], abs=2e-3)


# ------------------------------------------------------------ the finding ---
def test_the_lowest_rwp_is_the_worst_answer(shared, degenerate):
    """Freeing the phases' Lorentzian terms improves Rwp and ruins the QPA.

    Lorentzian FWHMs **add** (CLAUDE.md § Conventions), so instrument ``X,Y``
    and per-phase ``lor_size``/``lor_strain`` are one quantity split three
    ways.  Measured here: ρ = −1.000 between ``phases.0.lor_strain`` and
    ``instrument.profile.y``, and +1.000 between the two phases' strains.

    The consequence is the point.  The degenerate fit reaches a **lower Rwp**
    — the extra freedom lets the profile take intensity that belongs to the
    phase partition — and its QPA lands several σ from the weighing, while the
    identifiable fit's lands inside one.  This is the package's own rule about
    what counts as evidence, arriving as a measurement: an Rwp comparison
    would have selected the wrong model here.
    """
    assert degenerate.statistics.rwp < shared.statistics.rwp, (
        "the degenerate fit no longer wins on Rwp; the finding needs re-measuring")

    lo, hi = TOPAS_SPREAD["w_lab6"]
    gap = lambda w: max(lo - w, w - hi, 0.0)  # noqa: E731
    good, good_sd = _weight_percent(shared, "LaB6")
    bad, bad_sd = _weight_percent(degenerate, "LaB6")
    assert gap(good) < good_sd
    assert gap(bad) > 3.0 * bad_sd, (
        f"degenerate QPA {bad:.3f} ± {bad_sd:.3f} is no longer far from "
        f"TOPAS's [{lo}, {hi}], so this control has stopped controlling")


def test_the_correlation_diagnostic_separates_the_two(shared, degenerate):
    """And it separates them *without* being told which is which.

    ``HIGH_CORRELATION`` is silent about **the broadening split** on the
    identifiable fit and fires on the degenerate one at ρ → 1.  A user who
    never compared the two would still be told which numbers are not
    quotable, which is the whole purpose of the diagnostic channel.

    **The bar is the phase broadening terms, not an empty list, and the
    reason is measured.**  This assertion read ``corr(shared) == []`` until
    the bounds fix of issue #204, when it began failing on
    ``instrument.profile.u ~ instrument.profile.v``.  That is not a
    degeneracy the fix introduced.  The Gaussian triple ``u, v, w`` is
    flat in *both* builds — this plan frees all three on an instrument whose
    ``w`` starts at 2e-5, and the pair sat at **ρ = −0.9793 before the fix
    against a 0.98 guard, i.e. 0.0007 under the bar**, with ρ(v, w) = −0.947
    and ρ(u, w) = +0.882 beside it.  Bounding ``biso`` reparameterises the
    solve, which moved the landing point along that already-flat direction to
    ρ(u, v) = −0.9918 and ρ(v, w) = −0.9822 — at an Rwp 0.026 pp *better*
    (0.164550 against 0.164806) and a QPA 0.03 pp closer to TOPAS.  So the
    old assertion was passing on 7e-4 of margin over a flat direction, which
    is a coin flip across platforms and BLAS builds rather than a property of
    the model.  Neither ρ is the truer number: they are two stopping points on
    one flat valley, and only one of them is the one a user gets.

    **And "no bound is reached, so the optimum cannot move" is false here**,
    which is the natural objection to the paragraph above.  ``run_least_squares``
    passes ``bounds=(lo, hi)`` to scipy unconditionally, and TRF scales each
    direction by the distance to the bound the *gradient points at* — ``ub - x``
    where ``g < 0``, ``x - lb`` where ``g > 0``, and 1 only where that bound is
    infinite (``CL_scaling_vector``, scipy ``optimize/_lsq/common.py``).  So a
    ``biso`` at 0.44 under (0, 25) goes from a step scale of 1 to one of 0.44
    where the gradient pushes it down and 24.56 where it pushes it up, the
    trust region is shaped differently in those directions, and the walk stops
    elsewhere in the same valley — with nothing at a bound at any point.  Not an algorithm switch either: ``u`` and ``v``
    carry finite declared bounds already, so this fit was in ``trf_bounds``
    both before and after.

    Asserting on the phase terms keeps what this suite is *for* — the
    Lorentzian split of ``lor_size``/``lor_strain`` against instrument
    ``X, Y``, which is why ``PLAN_SHARED`` exists and is the thing
    ``PLAN_DEGENERATE`` controls for.  Making the Gaussian triple
    identifiable too would mean holding ``w`` (or ``u``), and that moves every
    number this suite measures against TOPAS — a protocol change, deliberately
    not smuggled in with a bounds fix.
    """
    def corr(result):
        return [d for d in result.diagnostics if d.code == "HIGH_CORRELATION"]

    # ``where`` rather than ``message``: the paths are a structured field and
    # the message is prose that may be reworded.
    finding = ("phases.0.lor_size", "phases.0.lor_strain",
               "phases.1.lor_size", "phases.1.lor_strain",
               "instrument.profile.y")
    split = [d for d in corr(shared)
             if any(p in finding for p in (d.where or []))]
    assert split == [], (
        "the identifiable plan's broadening split is no longer identifiable: "
        f"{[(d.where, d.message) for d in split]}")

    # Asserted as a separation, not as silence.  The Gaussian Caglioti triple
    # is flat in both builds and the 0.98 guard sits *inside* ρ(u, v)'s range
    # on this histogram, so whether it is flagged is a property of where the
    # walk stopped.  What must stay true is that nothing *else* is flagged:
    # a new degeneracy anywhere outside that triple fails here.
    caglioti = {"instrument.profile.u", "instrument.profile.v",
                "instrument.profile.w"}
    stragglers = [d for d in corr(shared)
                  if not set(d.where or []) <= caglioti]
    assert stragglers == [], (
        "HIGH_CORRELATION on the identifiable fit outside the Gaussian "
        f"Caglioti triple: {[(d.where, d.message) for d in stragglers]}")

    flagged = corr(degenerate)
    assert flagged, "the degenerate fit raised no HIGH_CORRELATION at all"
    assert any("lor_strain" in d.message for d in flagged)


def test_rwp_is_worse_than_topas_and_the_reason_is_the_peak_shape(shared):
    """Recorded rather than asserted away: rietx does not have PVII.

    TOPAS fitted ``PVII_Peak_Type`` with six free shape parameters; rietx
    offers TCHZ pseudo-Voigt and a true Voigt.  On this instrument that costs
    roughly a factor two in Rwp, and the misfit is concentrated at the peak
    **tops** (84.5 % of χ² in the 9 % of channels that are more than half
    Bragg, mean Δ/σ = +0.49) rather than in the background or the flanks —
    a shape deficit, not a scale or background one.

    The band is deliberately loose and one-sided.  It exists to catch a
    regression, not to certify the profile: the answers this suite trusts are
    the QPA and the cell, which are the things a shape deficit does *not*
    move once the broadening is identifiable.
    """
    assert TOPAS["rwp"] < shared.statistics.rwp < 4.0 * TOPAS["rwp"]
