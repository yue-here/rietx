""":func:`index_pattern` — the public entry point — and the whole-profile
validation it drives.

``index_pattern`` runs the engines, deduplicates their candidates as reduced
cells, enumerates geometrical ambiguities, validates the survivors by a Le Bail
fit, and gates confidence on **agreement**.  Its API cannot express a confident
wrong singleton: it returns an
:class:`~rietx.schemas.indexing.IndexingResult`, which has no ``.cell``, and the
only route to one cell is ``best_or_none()``.

The rest of this module is that validation step, and it exists because the
figure-of-merit panel is computed on ≤20 lines and is structurally blind to three
things the whole pattern sees — the third being the one no figure of merit can be
patched to see:

1. **lines beyond the panel** — a cell can index the first twenty and fail from
   twenty-one;
2. **impurity content** — observed peaks with nothing calculated near them;
3. **reflections predicted where there is no intensity** — the classic
   doubled/oversized-cell false positive.  M₂₀ penalises it only through its
   ``N_poss`` denominator, which is Oishi-Tomiyasu's (2013) critique of the de
   Wolff figure, and both source papers on autoindexing (Bergmann *et al.* 2004;
   Altomare *et al.* 2019) close on whole-profile validation for exactly this
   reason.

So validation is **mandatory, not an option**: with no pattern every candidate
caps at ``"medium"`` and ``INDEX_NOT_VALIDATED`` fires — the *result* abstains
rather than one field being quietly downgraded.

**The plan's detector for (3) was measured wrong, and the replacement is
measured.**  WP-1024's plan named Layer 0's ``unmatched_calc`` — its
strong-negative-residual count — as ``predicted_but_absent``.  It cannot serve,
and the reason is structural rather than a threshold: Le Bail extraction sets each
reflection's intensity from ``max(y_obs − y_bkg, 0)``, so a reflection predicted
where there is nothing is assigned ~nothing and produces **no negative residual
to detect**.  What the detector then finds is 5σ noise excursions that happen to
sit near a tick.  Measured on a synthetic LaB₆ pattern (Poisson noise, 15-145° 2θ
at 0.02°, the protocol ``tests/test_indexing_consensus.py`` pins),
``unmatched_calc`` fired on **19 of the certified cell's own 28 reflections** and
on 84 of a doubled cell's 153 — 68 % against 55 %, no more often on the wrong
cell, so it does not separate them at all.  :func:`absent_reflections` asks the question directly instead — is there net
intensity above the *fitted* background at this position? — and separates them
cleanly: 0 of 28 against 117 of 153.

**The two detectors and ``lebail_rwp`` catch different failures, which is why all
three are reported.**  Same measurement, four cells:

| candidate | Rwp | predicted_but_absent | unmatched_observed |
|---|---|---|---|
| truth | 0.216 | 0/28 | 0 |
| doubled cell | 0.379 | **117/153** | 0 |
| a·√5 supercell | 0.957 | 27/204 | 4 |
| metric 1 % off | 0.984 | 0/30 | **95** |

Read the table by column.  Rwp is decisive on a *wrong metric* (0.98 against 0.22)
and nearly silent on an *oversized* one (0.379 — well under twice the truth's, and
on real data a gap that size is inside the spread between specimens); the oversized
cell is caught only by column three.  A wrong metric is caught from the other side
by column four, where 95 observed peaks have no calculated reflection.  The a·√5
row is the useful reminder that these overlap: its fit is already refuted by Rwp,
so its low absent *fraction* costs nothing — a badly-fitted background is what
makes that count unreliable, and a badly-fitted background comes with an Rwp that
says so.

``lebail_rwp`` is the figure the literature names; it is **not** a member of the
ranking panel.  The panel ranks every candidate and this costs a refinement, so
it is computed for the shortlist only — and ranking on it would reintroduce the
blind spot validation exists to close, since a bigger cell with more free
intensities fits better.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import replace

import numpy as np

from ..schemas.common import Diagnostic
from ..schemas.indexing import CellCandidate, LeBailValidation, PeakList
from ..schemas.instrument import Instrument
from ..schemas.pattern import PatternData, require_two_theta
from ..schemas.structure import DUMMY_SPECIES, Structure, lebail_scaffold
from .fom import lattice_group

#: Multiples of the window's propagated σ the net intensity must reach for a
#: predicted reflection to count as **present**.  Three, the same 99.7 % window
#: :data:`~rietx.indexing.fom.MATCH_SIGMA` uses on positions, so one number
#: means one thing across the package.
#:
#: **Its failure mode is on a correct cell and is worth knowing before you read a
#: count.**  A genuinely weak reflection — a space-group extinction that is not
#: yet known to be one (the extinction screen runs after this and asks the same
#: question with a different null model), or a high-angle line the counting time
#: did not reach — is absent for reasons that have nothing to do with the lattice, and
#: this test cannot tell it from an oversized cell's phantom.  That is
#: ``predicted_seen_fraction``'s documented blind spot one level down, and it is
#: why the 2θ of every flagged reflection travels with the count: a caller can
#: look at the pattern, which no threshold can do for them.
ABSENT_SIGMA = 3.0
#: The metric wrongness, as |Δd|/d, whose displacement the Le Bail
#: validation's windows must *capture* rather than lose (an assumed tolerance
#: stated as one, like :data:`~rietx.indexing.engines.DEFAULT_UNKNOWN_SHIFT_DEG`
#: one level down).  The candidate under test may be metrically wrong — that
#: is what the validation exists to measure — and a wrong metric must read as
#: *displaced* intensity (high Rwp, unmatched observed lines), never as
#: *absent*, which is the oversized-cell signal.  1 % is the canonical wrong
#: metric the separation table grades (``test_indexing_consensus``).
VALIDATION_METRIC_REL = 0.01
#: Bounds on the derived slack: the floor keeps a short-range synchrotron
#: validation from collapsing to tail-only windows (a candidate also carries
#: zero-shift wrongness), the cap keeps tan θ from exploding near 180°.
VALIDATION_SLACK_BOUNDS_DEG = (0.3, 6.0)


def validation_window_slack_deg(two_theta_max: float) -> float:
    """The capture slack (°2θ) a validation fit compiles its windows with.

    Δ2θ = 2·tan θ·|Δd|/d is where a ±``VALIDATION_METRIC_REL`` metric error
    puts a line at the pattern's top angle — a lab pattern to 140° needs
    ≈ 3.2°, a synchrotron pattern to 24° only the floor — so the slack is
    derived from the range rather than fixed: a constant wide enough for the
    lab case makes a synchrotron validation absurdly wide (and measurably
    flips marginal weak lines of a *correct* cell to "absent" by moving the
    fitted background).  The refinement default (``forward.WINDOW_MIN_DEG``)
    is sized for a fit whose start is roughly right and must NOT be widened
    to serve this case — WP-1112 split the window's tail-coverage and
    capture-range jobs apart, and ``Stage.window_slack_deg`` is the capture
    half's declaration.
    """
    lo, hi = VALIDATION_SLACK_BOUNDS_DEG
    slack = np.degrees(2.0 * np.tan(np.radians(two_theta_max / 2.0))
                       * VALIDATION_METRIC_REL)
    return float(np.clip(slack, lo, hi))
#: Half-width of the integration window, in predicted FWHM.  Half a FWHM rather
#: than a whole one: the question is whether there is intensity *at the position*,
#: and a wider window on a dense supercell would collect a neighbour's tail and
#: report a phantom reflection as present.
ABSENT_WINDOW_FWHM = 0.5


def structure_from_candidate(candidate: CellCandidate, *,
                             space_group: str | None = None,
                             name: str = "candidate") -> Structure:
    """A single-phase :class:`Structure` for Le Bail validation of a cell.

    The scaffold itself — the cell and the mandatory dummy atom — is
    :func:`~rietx.schemas.structure.lebail_scaffold`, shared with the cell a
    person types into the GUI's wizard (WP-1206).  What is here is the one thing
    a *candidate* adds, and it is a footgun:

    **``space_group`` defaults to the absence-free lattice group**, never to a
    plausible-looking space group.  The default is the highest-symmetry group of
    the lattice with **no extra absences** (``P m -3 m``, ``P 4/m m m``,
    ``P 6/m m m``, ``P -3 m 1``, ``P m m m``, ``P 1 2/m 1``, ``P -1``, plus the
    centring), so validation tests the **lattice** — which is the only thing that
    has been determined.  A group carrying reflection conditions would hide
    exactly the reflections whose absence is not yet established, and hiding them
    is how an oversized cell passes: every phantom it predicts would be excused as
    an extinction.

    The real conditions are determined afterwards by
    :func:`rietx.indexing.extinction.determine_extinction_symbol`, which passes
    a class's representative in here as ``space_group`` — but the *validation*
    call above it must keep using the default, or the gate loses the detector.

    The six numbers go in as the candidate refined them.  They are **not** put
    through ``symmetry.complete_cell``, which the typed route uses: a candidate's
    derived angles already sit within 1.4e-14° of exactly 90/120 (``refine_candidate``
    solves A..F inside the symmetry subspace), and rebuilding them from the free
    parameters would move every stored number in the indexing acceptance suite for
    nothing.
    """
    symbol = space_group or candidate.lattice_group or lattice_group(
        candidate.system, candidate.centring)
    return lebail_scaffold(symbol, candidate.cell, name=name)


def absent_reflections(two_theta: np.ndarray, y_obs: np.ndarray,
                       y_background: np.ndarray, sigma: np.ndarray,
                       positions: np.ndarray, fwhm: np.ndarray, *,
                       k_sigma: float = ABSENT_SIGMA,
                       ) -> tuple[list[float], list[float]]:
    """Predicted positions with no net intensity above the **fitted** background.

    Returns ``(two_theta, net_over_sigma)`` for the reflections that failed.
    Integrates ``y_obs − y_background`` over ±:data:`ABSENT_WINDOW_FWHM` FWHM and
    compares the sum with the propagated σ of the same channels — so the test is
    "the pattern has nothing here", measured against the noise the pattern
    actually carries rather than against a fraction of the strongest peak.

    The *fitted* background is what makes this better than the same question
    asked of the peak list: a Le Bail fit has co-refined it under the P-spline or
    Chebyshev model, so a sloping background is not mistaken for intensity.  The
    same fact is the test's limit — a badly-fitted background makes the count
    unreliable, which is why the module docstring reads the count beside Rwp
    rather than alone.  **Measured how bad that gets** (WP-1043, magnetite's P
    rival): the count's inputs are the *candidate's own fit's* to buy, and a
    wrong candidate needing intensity under 163 predicted reflections bought it
    by driving the co-refined background **negative** (mean −5.8 counts —
    nothing floors it at the physical zero), at which point net cleared 3σ at
    99.6 % of channels and zero of 163 read absent; with the correct candidate's
    background under the same positions, 8-14 absences return.  The acceptance
    row regenerates that pathology, and the repair direction — inputs the
    candidate cannot buy — is recorded there, with an Rwp ratio ruled out.
    """
    tt = np.asarray(two_theta, dtype=np.float64)
    net = np.asarray(y_obs, dtype=np.float64) - np.asarray(y_background,
                                                           dtype=np.float64)
    sig = np.asarray(sigma, dtype=np.float64)
    pos_bad: list[float] = []
    ratio_bad: list[float] = []
    for pos, width in zip(np.asarray(positions, dtype=np.float64),
                          np.asarray(fwhm, dtype=np.float64)):
        inside = np.abs(tt - pos) <= ABSENT_WINDOW_FWHM * max(float(width), 1e-6)
        if not np.any(inside):
            continue                     # outside the fitted range: not evidence
        total = float(net[inside].sum())
        noise = float(np.sqrt((sig[inside] ** 2).sum()))
        if total < k_sigma * noise:
            pos_bad.append(float(pos))
            ratio_bad.append(total / max(noise, 1e-300))
    return pos_bad, ratio_bad


def _shift_path(candidate: CellCandidate, instrument: Instrument) -> str:
    """The one peak-position parameter the validation fit frees.

    **One, not three.**  The three templates are collinear over a limited 2θ
    range — that is what ``quality.fit_shift_model`` refuses to resolve and what
    Layer 1 measured one rank down (a joint fit of collinear templates reported a
    0.02° zero-point error as 1.8°) — so freeing more than one here would put two
    columns with ρ ≈ 1 into the same solve.

    Which one comes from the candidate's *own* declared template, translated
    through ``diagnostics.SHIFT_CAUSE``'s mapping: one physical cause, one name,
    package-wide.  A ``cos_theta`` candidate names the specimen displacement,
    which is live only in ``bragg_brentano`` geometry — on a capillary only
    ``zero_shift`` moves the peaks at all, so the request falls back to it rather
    than freeing a parameter with no gradient.
    """
    by_template = {
        "constant": "instrument.zero_shift",
        "cos_theta": "instrument.geometry.sample_displacement",
        "sin_2theta": "instrument.geometry.sample_transparency",
    }
    path = by_template.get(candidate.shift_template or "constant",
                           "instrument.zero_shift")
    if (path != "instrument.zero_shift"
            and instrument.geometry.kind != "bragg_brentano"):
        return "instrument.zero_shift"
    return path


def validation_plan(candidate: CellCandidate, instrument: Instrument,
                    two_theta_max: float | None = None, *,
                    freeze_profile: bool = False):
    """The staged plan a Le Bail validation runs, and what it deliberately omits.

    ``freeze_profile`` (C3) drops the two width stages: the profile stays at
    the instrument's declared values, seeded from the peak list's measured
    width by :func:`seed_widths` where the declared one is inconsistent, so
    every candidate is fitted with one **shared** profile the way the
    extinction screen's ``_screen_plan`` fits every class with one.  The
    reason is the same: a per-candidate profile lets a wrong cell buy back an
    unmatched observed line by broadening its neighbour.  The absent count no
    longer reads this fit at all (the line screen does), so what the fit
    keeps is the forward question — is there a reflection under every
    observed peak — and an Rwp for a reader.  **Off by default, measured**:
    frozen at the *declared* profile, SRM 660c's own cell validates at Rwp
    0.57 against 0.10 with the widths free, and the rival/truth Rwp ratio the
    acceptance rows read falls from above 2 to 1.78, while nothing the fit
    reports gates any more.  The shared pre-fit F1 asked for needs a
    cell-free width law fitted to the peak list; until that lands,
    ``validate_by_lebail(freeze_profile=True)`` is the caller's choice.

    **The cell is held.**  ``profile_only`` — the ordinary Le Bail plan — frees
    ``phases.*.cell.*``, and it must not here: the candidate *is* the hypothesis
    under test, and letting it walk means validating a different cell from the one
    the result reports.  A candidate whose metric is slightly wrong is supposed to
    validate badly; that is the measurement.

    What is freed: the background (a candidate cannot be judged against a
    background nobody fitted), exactly one peak-position parameter
    (:func:`_shift_path`), and then the widths in the ``profile_only`` order —
    ``w`` alone before ``u``/``v``/``x``/``y``, because ``w`` is the only width
    term that is non-zero at 2θ = 0 and freeing the four together from a
    mis-declared instrument is what the staged order exists to prevent.

    **The convergence schedule is the package's** (``intermediate_ftol``,
    WP-1123), named here because a verdict is where inheriting a default is
    worth a second look.  It survives one: the stage that produces the number
    a candidate is judged on is the last, which converges at the solver's own
    tolerance whatever the schedule says, and the earlier three are cumulative
    — the background and the shift keep refining inside it.  The ranking is
    what checks this, not the argument: ``tests/test_acceptance_indexing.py``
    is unchanged across the flip.
    """
    from ..strategy.staged import RefinementPlan, Stage

    # capture slack derived from the fitted range (see the function); a
    # caller without a range gets the conservative cap
    slack = (validation_window_slack_deg(two_theta_max)
             if two_theta_max is not None else VALIDATION_SLACK_BOUNDS_DEG[1])
    stages = [
        Stage("bkg", ["instrument.background.*"], window_slack_deg=slack),
        Stage("shift", [_shift_path(candidate, instrument)],
              window_slack_deg=slack),
    ]
    if not freeze_profile:
        stages += [
            Stage("profile_w", ["instrument.profile.w"], window_slack_deg=slack),
            Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                              "instrument.profile.x", "instrument.profile.y"],
                  window_slack_deg=slack),
        ]
    # a validation verdict compares candidates fitted alike, and pays for no
    # closing stage (WP-2002, the sixth round's Q1 and Q2)
    return RefinementPlan(stages=stages, closing_window_tol=None)


def seed_widths(instrument: Instrument, peaks: PeakList) -> tuple[Instrument, bool]:
    """Put the instrument's Gaussian ``w`` on the peak list's measured width.

    Returns ``(instrument, seeded)``; the input is never mutated.

    Only when the declared instrument is *inconsistent* with the data, judged by
    the same ``WIDTH_MISMATCH_RATIO`` the ``PEAK_WIDTH_LAW_MISMATCH`` diagnostic
    uses — so a calibrated instrument is left exactly as declared and the
    ``ProfileTCHZ`` default (``W = 1e-3 deg²``, FWHM ≈ 0.03°, a *synchrotron*
    line, which lands near a factor 13 on lab data) does not make every candidate
    validate badly for a reason that has nothing to do with its cell.

    ``w`` is a Gaussian *variance* in deg²(2θ), so the seed is the measured FWHM
    squared: with ``u = v = 0`` the Caglioti law gives Γ_G = √w.  It is a seed and
    the plan's first width stage refines it.
    """
    from .diagnostics import WIDTH_MISMATCH_RATIO
    from .peaks import predicted_fwhm

    usable = peaks.usable()
    if not usable:
        return instrument, False
    measured = float(np.median([p.fwhm for p in usable]))
    tt = np.array([p.two_theta for p in usable], dtype=np.float64)
    predicted = float(np.median(predicted_fwhm(tt, instrument)))
    if predicted <= 0.0:
        return instrument, False
    ratio = measured / predicted
    if 1.0 / WIDTH_MISMATCH_RATIO < ratio < WIDTH_MISMATCH_RATIO:
        return instrument, False
    out = instrument.model_copy(deep=True)
    out.profile.w.value = float(measured ** 2)
    return out, True


def validate_by_lebail(candidate: CellCandidate, data: PatternData,
                       instrument: Instrument, *,
                       peaks: PeakList | None = None,
                       space_group: str | None = None,
                       two_theta_limits: tuple[float, float] | None = None,
                       k_sigma: float = ABSENT_SIGMA,
                       with_result: bool = False,
                       cancel=None, screen=None,
                       pattern_screen=None,
                       freeze_profile: bool = False) -> LeBailValidation:
    """Fit ``candidate`` to the whole pattern by Le Bail and report the three
    detectors.

    **Since C3 the absent count is the line screen's, not this fit's.**  With
    a ``peaks`` list the candidate is screened against the picker's envelope
    and the peak list's widths and shapes (``indexing/screen.py``), inputs it
    cannot buy, and ``predicted_but_absent`` is that count with the
    uncancellable and windowed-uncancellable counts beside it
    (``absent_source="line_screen"``); the fit keeps the forward question and
    an Rwp for a reader, with the widths free unless ``freeze_profile``
    (:func:`validation_plan` says why the default is free).  ``screen`` is a ready
    :class:`~rietx.indexing.screen.LineScreen` for this candidate and
    ``pattern_screen`` the run's :class:`~rietx.indexing.screen.PatternScreen`,
    both optional; ``index_pattern`` passes the second so the pattern is
    enveloped once.  With no peak list the count is the fitted-background
    detector's (``"fitted_background"``), whose measured failure is in
    :func:`absent_reflections`.

    ``with_result=True`` additionally returns the
    :class:`~rietx.schemas.results.RefinementResult` the fit produced, as
    ``(validation, result)`` — ``result`` is ``None`` when the fit raised, which
    is the state ``status="failed"`` describes.  It is **opt-in and not a field
    on** :class:`~rietx.schemas.indexing.LeBailValidation` for the reason
    history nodes store state rather than curves: the validation object is a
    JSON-round-tripped schema of a few hundred bytes, and a result carries
    y_obs/y_calc/y_background over every channel.  So the caller who wants a
    picture asks for one, and every caller who wants a verdict is unaffected —
    ``index_pattern`` among them, which stores the verdict on the candidate.

    **What the validation asks is discrete, and it is not this fit's Rwp.**  A
    cell is a hypothesis about *where lines can be* and about nothing else, so
    the question is a counting one: is there a reflection under every observed
    peak, and is there intensity under every predicted reflection.  Those are the
    two counts returned here (``unmatched_observed``, ``predicted_but_absent``).
    The fit exists to place the reflections over the whole profile and to give
    those counts a fitted background and width law to be counted against — a
    candidate that makes sense fits many peaks at once, and one that does not
    leaves the mismatch somewhere the counts can see it.

    **Structure-free because at indexing time there is no structure**, so the
    per-hkl intensities have to be free: a Rietveld validation would test the
    lattice and a structure hypothesis at once and could refute a right cell for
    a wrong structure.  That freedom is the point *and* the limit — free
    intensities carry no information about the cell, so ``rwp`` is reported for a
    reader and is **not evidence on its own**.  WP-1020 said the same thing when
    it kept ``lebail_rwp`` out of the FoM panel: the statistic *rewards
    flexibility*, and a cell predicting more reflections has more of it.  Reading
    a fit statistic as the evidence for a correction is the habit CLAUDE.md's
    "never an Rwp comparison as its evidence" rule exists to break.

    **Le Bail rather than Pawley is a cost choice, not a discrimination one.**
    Both extractions leave one free intensity per reflection, and the intensities
    are arbitrary in both: this partition hands overlapping reflections whatever
    share of ``max(y_obs − y_bkg, 0)`` the current profile ratio asks for, which
    is no more constrained than a least-squares intensity is.  What it costs is
    nothing in θ, where Pawley appends a
    :class:`~rietx.model.forward.PawleyBlock` and its overlap restraints for
    every candidate validated.  (A previous revision argued the opposite — that
    Le Bail is the *constrained* fit and therefore the discriminating one — from
    a measured magnetite Rwp pair.  The numbers were real, the mechanism was not
    established, and it contradicted both this module's own detector and
    WP-1020's panel decision; WP-1043 carries the retraction.)

    Single-phase by construction, and that is a measured constraint rather than a
    simplification: ``CompiledModel.lebail_update`` partitions
    ``max(y_obs − y_bkg, 0)`` per phase with nothing to arbitrate two phases
    claiming the same channel, so two phases inflate one another without bound
    (WP-1028, measured Rwp 742-9 281 % against 7.5-24.8 % for one phase, and it
    survives seeding both the widths and the background — so it is the partition,
    not the starting point).  A candidate is never validated against a
    multi-phase hypothesis.

    A fit that *raises* comes back as ``status="failed"`` with an infinite Rwp
    rather than as an exception: a candidate the physics refuses is evidence
    about the candidate, and the gate reads it as such (the ``validation_failed``
    caveat), where a traceback would abandon every other candidate with it.

    **Except a cancellation, which is evidence about nothing** (WP-1037).
    ``cancel`` may be the caller's token or ``index_pattern``'s whole-run
    :class:`~rietx.indexing.engines.Deadline`; either way the fit it stops is
    a fit that *ran out of time*, and letting ``RefinementCancelled`` fall into
    the generic handler would hand the gate a ``validation_failed`` — a
    **refuting** caveat — for a cell the run merely could not afford to check.
    So it re-raises, the caller stops the loop, and the candidate keeps
    ``lebail = None``, which reads as ``not_validated`` (capping): the honest
    state, and the same one an unreached candidate was always in.
    """
    require_two_theta(data, "validate_by_lebail()", instrument=instrument)
    from ..optimize.cancel import RefinementCancelled
    from ..refine import Refinement
    from ..report.layer0 import build_layer0
    from .peaks import predicted_fwhm

    structure = structure_from_candidate(candidate, space_group=space_group)
    symbol = structure.phases[0].space_group
    ins = instrument
    if peaks is not None:
        ins, _seeded = seed_widths(ins, peaks)
        if screen is None:
            from .screen import PatternScreen, screen_for

            if pattern_screen is None or not pattern_screen.has_pattern:
                # the search's matching window and this call's fitted range,
                # as index_pattern's run-wide screen has them: the per-line
                # σ is the measurement, not the tolerance a search matched
                # with, and lines the fit never covered are not absent
                from .engines import DEFAULT_UNKNOWN_SHIFT_DEG, absence_window
                from .screen import MATCH_SIGMA

                pattern_screen = PatternScreen.from_peaks(
                    peaks, q_match=absence_window(peaks), data=data,
                    instrument=instrument, two_theta_limits=two_theta_limits,
                    p0_floor_deg=MATCH_SIGMA * DEFAULT_UNKNOWN_SHIFT_DEG)
            screen = screen_for(pattern_screen, candidate, peaks)
    tt_max = float(np.max(data.tt()))
    if two_theta_limits is not None:
        tt_max = min(tt_max, float(two_theta_limits[1]))
    plan = validation_plan(candidate, ins, two_theta_max=tt_max,
                           freeze_profile=freeze_profile)

    ref = Refinement(structure, ins, history=False)
    try:
        result = ref.fit(data, mode="lebail", plan=plan,
                         two_theta_limits=two_theta_limits, cancel=cancel,
                         # one validation fit per candidate: a run directory
                         # each would bury the search that asked for them
                         telemetry=False)
    except RefinementCancelled:
        raise                       # before the generic handler — see docstring
    except Exception as exc:                        # noqa: BLE001
        failed = LeBailValidation(
            rwp=float("inf"), gof=float("inf"), space_group=symbol,
            n_reflections=0, status="failed",
            diagnostics=[Diagnostic(
                level="warning", code="INDEX_VALIDATION_FAILED",
                message=(f"The Le Bail validation of {candidate.system} "
                         f"{symbol} raised {type(exc).__name__}: "
                         f"{str(exc).rstrip('.')}."),
                where=[f"cell {candidate.cell}"],
                suggestion=("Check the instrument first, since a mis-declared "
                            "profile or a wavelength on an absorption edge "
                            "fails every candidate alike."))])
        return (failed, None) if with_result else failed

    rows = [r for r in ref.reflection_table() if r.line == 0]
    extra: dict = {}
    if screen is not None and screen.absent is not None:
        absent_tt = screen.absent_two_theta
        extra = dict(
            predicted_but_absent_uncancellable=screen.n_absent_uncancellable,
            predicted_but_absent_uncancellable_in_window=(
                screen.n_absent_uncancellable_in_window),
            absent_source="line_screen", n_lines_screened=screen.n_lines)
    else:
        positions = np.array([r.two_theta for r in rows], dtype=np.float64)
        absent_tt, _ratio = absent_reflections(
            np.asarray(result.two_theta), np.asarray(result.y_obs),
            np.asarray(result.y_background), np.asarray(result.sigma),
            positions, predicted_fwhm(positions, ref.fitted_instrument),
            k_sigma=k_sigma) if len(positions) else ([], [])

    layer0 = build_layer0(result)
    unmatched = [u.two_theta for u in layer0.unmatched
                 if u.kind == "unmatched_obs"]
    validation = LeBailValidation(
        rwp=float(result.statistics.rwp), gof=float(result.statistics.gof),
        space_group=symbol, n_reflections=len(rows),
        predicted_but_absent=len(absent_tt),
        unmatched_observed=len(unmatched),
        predicted_but_absent_two_theta=[round(v, 4) for v in absent_tt],
        unmatched_observed_two_theta=[round(float(v), 4) for v in unmatched],
        status=result.status, n_stages=len(result.stages), **extra)
    return (validation, result) if with_result else validation


# ----------------------------------------------------------------------
# the entry point
# ----------------------------------------------------------------------
def _pair_shift_diagnostics(quality) -> list[Diagnostic]:
    """``INDEX_SHIFT_FROM_PAIRS``, when the pair screen actually measured one."""
    from .engines import shift_from_pairs_diagnostic

    shift = getattr(quality, "shift", None)
    if shift is None or shift.source != "reflection_pairs" or shift.pairs is None:
        return []
    return [shift_from_pairs_diagnostic(shift)]


def _adopt_measured_shift(spec, quality):
    """Adopt a pair-measured shift *template* into the spec, when it is safe to name.

    Measuring the shift's **magnitude** and naming its **cause** are separate
    permissions, and this function is where the second one is refused.  The
    magnitude reaches the search through ``effective_shift_allowance`` and needs no
    template; adopting a template additionally tells ``refine_with_shift`` which
    *shape* to fit once a candidate survives, and fitting the wrong shape biases
    the cell it corrects.

    So adoption requires the cause to be safe to name — ``separable``, or the
    competitive templates disagreeing, over the angles actually sampled, by less
    than the list's own median σ.  **Measured (WP-1038), that is rare and the
    refusal is the common case**: on corundum the two collinear templates predict
    corrections differing by 0.0505° against a median σ of 0.0056°, because cos θ
    runs from ~1 to ~0.26 across 5-150° while a constant does not.  A caller who
    knows the cause declares ``spec.shift_template`` and is never overridden here.

    **Clearing the caveat without adopting a template would be the trap.**  A cell
    found inside a widened window has absorbed the shift — +1400 ppm, measured on
    corundum — so when nothing is adopted the run keeps saying so.
    """
    from ..schemas.indexing import TRUSTED_SHIFT_SOURCES

    shift = getattr(quality, "shift", None)
    if (spec.shift_template is not None or shift is None
            or shift.source not in TRUSTED_SHIFT_SOURCES or shift.best is None):
        return spec
    median_sigma = float(getattr(quality, "sigma_two_theta_median", 0.0) or 0.0)
    nameable = bool(shift.separable
                    or (shift.prediction_spread_deg <= median_sigma
                        and median_sigma > 0.0))
    if not nameable:
        return spec
    return replace(spec, shift_template=shift.best)


def _restrict_to_supported(spec, quality):
    """Below the scoring bar, search only the systems the line count supports.

    WP-1043's split, the search half: a list short of the twenty the classical
    figures are defined on is still searched, but over
    ``quality.systems_supported`` — the per-system :data:`MIN_LINES_PER_DOF`
    authority — rather than the full request, because a system with fewer lines
    per metric DOF than that is not over-determined and any cell found there
    would be fitting noise.  No second searchability criterion: this reuses the
    computation ``assess_peak_list`` already makes.

    At or above the bar nothing changes — a caller's declared systems are
    honored exactly as before.  And a caller whose declared systems share
    *nothing* with the supported set is honored too, the same never-overridden
    rule as :func:`_adopt_measured_shift`: the quality diagnostics still say
    those systems are under-determined, but an explicit request is not silently
    replaced by an empty search.
    """
    if not getattr(quality, "fom_undefined", None):
        return spec
    supported = set(getattr(quality, "systems_supported", ()) or ())
    allowed = tuple(s for s in spec.systems if s in supported)
    if not allowed or allowed == tuple(spec.systems):
        return spec
    return replace(spec, systems=allowed)


def _stream_system_snapshot(progress, system: str, units: dict, names,
                            peaks, spec, quality, top: int,
                            screen=None) -> None:
    """Grade what every completed system holds so far, and stream it (WP-1042).

    Runs as its **own ladder unit** (``consensus:<system>``, ``add``-ed like the
    probe and validation units, on the existing kinds — no
    ``EVENT_SCHEMA_VERSION`` move), because it is real work the run does, and
    only when a stream is listening: an event-less run pays nothing.

    What it emits is the cumulative ranked list over every system completed so
    far, each candidate in the WP-1043 evidence shape
    (:func:`~rietx.schemas.indexing.candidate_evidence` — shared, never
    forked), graded by the same gate as the final answer with two questions
    deliberately still open: nothing is validated yet and no ambiguity has
    been enumerated (``consensus(..., ambiguity=False)`` — the enumeration is
    the measured long pole, 45 s of a 105 s corundum run).  Both read as
    capping caveats, so a streamed grade can only *rise* when the full
    consensus and validation run — never fall.  Raw candidates from units of a
    system still in progress are different: they have been through no
    consensus at all, and ride the search units' ``provisional`` field with no
    confidence at all (``engines.provisional_payload``).
    """
    from ..schemas.indexing import candidate_evidence
    from .consensus import apply_gate, consensus
    from .engines import merge_engine_units

    results = [merge_engine_units(units[name]) for name in names
               if units[name]]
    outcome = consensus(results, peaks, spec=spec, quality=quality, top=top,
                        ambiguity=False, screen=screen)
    apply_gate(outcome.candidates, engines_run=outcome.engines_run,
               panel_disagrees=outcome.fom_panel_disagrees, validated=False,
               search_complete=outcome.search_complete,
               shift_allowance_assumed=outcome.shift_allowance_assumed,
               checked=outcome.ambiguity_checked, quality=quality)
    m20 = [c.fom_value("m20") for c in outcome.candidates]
    m20 = [v for v in m20 if v is not None]
    label = f"consensus:{system}"
    progress.add(1)
    progress.start(label, system=system, consensus=True)
    progress.end(label, system=system, consensus=True,
                 n_candidates=len(outcome.candidates),
                 best_m20=round(max(m20), 2) if m20 else None,
                 candidates=[candidate_evidence(i, c).model_dump(mode="json")
                             for i, c in enumerate(outcome.candidates)])


def index_pattern(peaks: PeakList | None = None, *,
                  data: PatternData | None = None,
                  instrument: Instrument | None = None,
                  spec=None,
                  preset: str | None = None,
                  engines: Sequence[str] | None = None,
                  quality=None,
                  shift_from_pairs: bool = True,
                  validate: bool = True,
                  check_top: int | None = None,
                  two_theta_limits: tuple[float, float] | None = None,
                  formula: str | None = None, temperature: float = 298.0,
                  events=None, cancel=None):
    """Find the unit cell, or say in the shape of the answer that it cannot be found.

    Give it a :class:`~rietx.schemas.indexing.PeakList`, or a ``data`` +
    ``instrument`` pair it will pick peaks from.  Supplying ``data`` is what turns
    whole-profile validation on: without a pattern every candidate caps at
    ``"medium"`` and ``INDEX_NOT_VALIDATED`` fires, because the figure-of-merit
    panel is blind to three things only the profile shows
    (:func:`validate_by_lebail`).

    ``engines`` names which searches to run, from the **live registry**
    (``engines.engine_names()``); the default is all of them, and that default is
    the one to keep — ``high`` confidence *means* every engine that ran found the
    same lattice, so restricting the list narrows what the answer can say.

    ``cancel`` is WP-1006's :class:`~rietx.optimize.cancel.CancelToken` and works
    here unchanged: the check is cooperative, read between units of search work, so
    it needs no stages, no Rwp and no history node.  A cancelled search returns
    what it has rather than raising — an indexing run has nothing to abandon,
    unlike a seeding refinement stage.

    ``spec.total_budget_seconds`` (WP-1037) is the whole-run ceiling — search,
    probe *and* validation, where ``budget_seconds`` is one (engine × system)
    slice.  It is enforced as a :class:`~rietx.indexing.engines.Deadline`,
    a clock shaped as a cancel token, so it nests under every cooperative
    check above with no engine changes and the run still returns a complete
    :class:`~rietx.schemas.indexing.IndexingResult` over what was reached.
    ``systems_searched`` then distinguishes three states — a system searched to
    completion (``search_complete`` true), one truncated mid-search (false),
    and one never reached (absent) — and ``INDEX_BUDGET_EXHAUSTED`` names them.
    ``estimate_ceiling`` is the pre-run arithmetic for choosing the value.

    ``preset`` names a row of ``engines.SEARCH_PRESETS`` and defaults to
    ``"quick"`` (WP-1042): all engines, all requested systems, and a whole-run
    ceiling of ``QUICK_TOTAL_BUDGET_SECONDS`` filled into
    ``spec.total_budget_seconds`` **only when the caller left it None** — a
    declared spec field is never overridden, the same rule as
    :func:`_adopt_measured_shift`.  ``preset="full"`` is the pre-1.0
    behaviour: no ceiling beyond ``budget_seconds`` per (engine × system).
    The result records which preset governed (``IndexingResult.preset`` —
    ``"custom"`` when the caller's own ceiling did), and under a declared
    ceiling each validation fit draws an equal **slice** of the remaining
    clock, so one heavy candidate cannot starve the rest of the shortlist
    (measured: unbudgeted fits were 74 of fap's 84 s).

    **The (engine × system) units run system-major** (WP-1042): every engine
    finishes one system before any engine starts the next, in ``SYSTEM_ORDER``
    (cheapest metric first).  A binding deadline therefore sacrifices trailing
    systems for every engine *equally* — a completed system holds all engines'
    answers, which is what the agreement gate needs — where the engine-major
    loop this replaced truncated whole engines, so which candidates kept their
    finders depended on which engine the clock happened to catch.

    **Abstention is checked before any budget is spent, and it is about
    searchability, not scorability** (WP-1043).  A peak list that cannot support
    a search *in any system* (``MIN_LINES_PER_DOF``) comes back with the
    candidates empty and ``INDEX_DATA_INSUFFICIENT`` from the quality gate,
    never as an exception and never as a ranked list with nothing behind it.  A
    list that is merely short of the twenty lines the classical figures of
    merit are defined on is **searched anyway**, over the supported systems
    only (:func:`_restrict_to_supported`), ranked by the reduced panel, and
    capped by the ``fom_panel_reduced`` caveat — each absent figure named with
    its reason on ``quality.fom_undefined``.

    ``formula`` checks each candidate against the chemistry (WP-1510).  The
    number of formula units a cell's volume implies, by Hofmann's (2002) volumes
    at ``temperature`` in K, is reported as ``INDEX_Z_NOT_INTEGER`` when it is
    far from a whole number.  It reports and never narrows.  The search window
    a formula implies is :meth:`~rietx.indexing.engines.SearchSpec.from_formula`,
    declared by the caller, because narrowing is the caller's own act.  A
    formula the table cannot read raises before peaks are picked.
    """
    from ..history.events import as_event_stream
    from ..optimize.cancel import RefinementCancelled
    from ..refine import _VERSION, _utcnow
    from ..report.schemas import THRESHOLDS_VERSION
    from ..schemas.common import Provenance
    from ..schemas.indexing import IndexingResult
    from .consensus import CONSENSUS_CHECK_TOP, apply_gate, checked_indices, consensus
    from .diagnostics import candidate_diagnostics, index_diagnostics
    from .engines import (
        DEFAULT_SEARCH_PRESET,
        INLIERS,
        SEARCH_PRESETS,
        SYSTEM_ORDER,
        Deadline,
        Progress,
        SearchSpec,
        budget_exhausted_diagnostic,
        engine_names,
        get_engine,
        inlier_retry_diagnostic,
        merge_engine_units,
        search_anchors,
        search_line_order,
        single_engine_diagnostic,
    )
    from .pick import pick_peaks
    from .quality import assess_peak_list

    if formula is not None:
        from ..crystallography.atomic_volume import formula_unit_volume

        formula_unit_volume(formula, temperature)   # a bad formula raises here
    if data is not None:
        # Checked whether or not the peaks are picked here: ``data`` also drives
        # whole-profile validation below, so a TOF pattern handed in beside a
        # ready-made PeakList would still reach a Le Bail fit.
        require_two_theta(data, "index_pattern()", instrument=instrument)
    if peaks is None:
        if data is None or instrument is None:
            raise ValueError(
                "index_pattern needs a PeakList, or a data= + instrument= pair to "
                "pick one from; it cannot index a pattern whose wavelength and "
                "profile it does not know")
        peaks = pick_peaks(data, instrument)
    spec = spec or SearchSpec()
    preset_name = DEFAULT_SEARCH_PRESET if preset is None else preset
    if preset_name not in SEARCH_PRESETS:
        raise ValueError(f"unknown search preset {preset_name!r}; "
                         f"available: {', '.join(SEARCH_PRESETS)}")
    ran_preset = preset_name
    if spec.total_budget_seconds is None:
        ceiling = SEARCH_PRESETS[preset_name]
        if ceiling is not None:
            spec = replace(spec, total_budget_seconds=float(ceiling))
    else:
        # the caller's own ceiling governed, not the preset's — a declared
        # spec field is never overridden, and the record must not name a
        # preset that decided nothing
        ran_preset = "custom"
    if quality is None:
        quality = assess_peak_list(peaks, shift_from_pairs=shift_from_pairs,
                                   pair_seed=spec.seed, instrument=instrument)
    spec = _adopt_measured_shift(spec, quality)
    spec = _restrict_to_supported(spec, quality)
    names = tuple(engines) if engines is not None else engine_names()
    top = CONSENSUS_CHECK_TOP if check_top is None else check_top
    # the line screen's candidate-independent facts, once per run (C3): the
    # envelope and the peak-list model with a pattern, the resolution windows
    # and the chance rate without one
    from .engines import absence_window, effective_shift_allowance
    from .screen import PatternScreen

    # the screen's indexed set feeds the containment refuter, an absence
    # test, so it reads the assumed bound and never the widths' window (#951)
    pattern_screen = PatternScreen.from_peaks(
        peaks, q_match=absence_window(peaks, spec, quality), k_sigma=spec.k_sigma,
        data=data if validate else None, instrument=instrument,
        p0_floor_deg=spec.k_sigma * effective_shift_allowance(spec, quality)[0])

    # analogue priors steer the queue (WP-1045): the systems they name run
    # first, everything else keeps SYSTEM_ORDER — reordered, never narrowed
    jumped: list[str] = []
    if spec.prior_cells or spec.prior_spacegroups:
        from .priors import prior_systems

        jumped = prior_systems(spec)

    # the whole-run clock, if one was declared: a Deadline both *is* the token
    # every cooperative check reads (so it binds the engines, the probe and the
    # validation fits alike) and *carries* the caller's own token, so either
    # stops the run and cancelled_by_user() says which did.  When validation
    # is going to run, the *search* gets a nested deadline ending a reserve
    # early (WP-1045): measured on three heavy patterns, the search consumed
    # the whole ceiling and validation got zero fits, while a fit costs
    # 0.3-1.9 s against 11-60 s for a trailing system — scheduling within the
    # ceiling, which itself never moves
    deadline = None
    run_cancel = cancel
    search_cancel = cancel
    if spec.total_budget_seconds is not None:
        from .engines import VALIDATION_RESERVE_FRACTION

        deadline = Deadline(spec.total_budget_seconds, cancel=cancel)
        run_cancel = deadline
        search_cancel = deadline
        if validate and data is not None and instrument is not None:
            reserve = VALIDATION_RESERVE_FRACTION * spec.total_budget_seconds
            search_cancel = Deadline(spec.total_budget_seconds - reserve,
                                     cancel=deadline)

    provenance = Provenance(
        package_version=_VERSION, created_utc=_utcnow(),
        report_thresholds_version=THRESHOLDS_VERSION,
        notes=_spec_notes(spec, names, quality, ran_preset))
    stream = as_event_stream(events)
    if stream is not None:
        extra = ({"total_budget_seconds": float(spec.total_budget_seconds)}
                 if spec.total_budget_seconds is not None else {})
        stream.emit("index_start", engines=list(names),
                    systems=[s for s in spec.systems],
                    n_usable_lines=len(peaks.usable()),
                    wavelength=peaks.wavelength,
                    supports_indexing=quality.supports_indexing, **extra)
    # one flat ladder over everything the run does (WP-1037): a search unit per
    # (engine × system), plus probe and validation units add()-ed when their
    # counts become known — never a second per-engine ladder beside it, which
    # is what made a progress bar jump (two writers, one ``n_stages``)
    ordered_systems = [s for s in SYSTEM_ORDER if s in spec.systems]
    if jumped:
        ordered_systems = (jumped
                           + [s for s in ordered_systems if s not in jumped])
    progress = Progress(stream, total=len(names) * len(ordered_systems),
                        deadline=deadline)

    if not quality.supports_indexing:
        # abstention *is* the result: the gate has already decided the data cannot
        # support a search, and running one anyway returns a rank order with
        # nothing behind it
        result = IndexingResult(
            engines_run=[], systems_searched=[], quality=quality,
            wavelength=peaks.wavelength, n_usable_lines=len(peaks.usable()),
            validated=False, provenance=provenance, preset=ran_preset,
            diagnostics=list(quality.diagnostics))
        out = result.model_copy(update={
            "diagnostics": list(result.diagnostics)
            + index_diagnostics(result, instrument)})
        _emit_end(stream, out)
        return out

    # ------------------------------------------------------------------
    # the scheduler (WP-1042): (engine × system) units, system-major
    # ------------------------------------------------------------------
    # Every engine finishes one system before any engine starts the next, so a
    # binding deadline sacrifices trailing *systems* for every engine equally
    # rather than whole engines — under the engine-major loop this replaces,
    # which candidates kept their finders depended on which engine the clock
    # happened to catch, and a candidate found only by the engine that ran
    # first graded ``low`` structurally.  ``SYSTEM_ORDER`` stays the one
    # authority for the order (cheapest metric first); per-(engine × system)
    # progress is still emitted by the engines themselves through ``progress``
    # (the per-engine stage pair was *replaced*, not nested — WP-1037's trap 2).
    unit_kwargs: dict[str, dict] = {name: {} for name in names}
    if "trial_error" in unit_kwargs:
        # its dominant-zone probe explains a *whole-run* silence, which a
        # per-system unit cannot know — deferred below, asked once
        unit_kwargs["trial_error"]["probe"] = False
    def run_units(spec):
        units: dict[str, list] = {name: [] for name in names}
        for system in ordered_systems:
            if search_cancel is not None and bool(search_cancel):
                break
            for name in names:
                if search_cancel is not None and bool(search_cancel):
                    break
                unit_spec = replace(spec, systems=(system,))
                units[name].append(get_engine(name)(
                    peaks, spec=unit_spec, quality=quality,
                    cancel=search_cancel, progress=progress,
                    **unit_kwargs[name]))
            if stream is not None \
                    and not (search_cancel is not None and bool(search_cancel)):
                # a *completed* system has been through consensus and streams
                # graded (WP-1042); a system the token interrupted has not,
                # and its candidates stay provisional in the log
                _stream_system_snapshot(progress, system, units, names, peaks,
                                        spec, quality, top,
                                        screen=pattern_screen)
        return [merge_engine_units(units[name]) for name in names
                if units[name]]

    results = run_units(spec)
    retry_spec = replace(spec, n_unindexed=INLIERS)
    if (spec.n_unindexed is None and _no_agreement(results)
            and not (search_cancel is not None and bool(search_cancel))
            # a list of one intensity has no anchor, so its inlier rule *is*
            # the count of two and a retry would repeat the first pass
            and len(search_anchors(peaks, search_line_order(peaks, spec),
                                   retry_spec))):
        # the inlier retry (indexing C4): the absolute count of two is what a
        # list with more foreign lines than that cannot pass, so a run that
        # ends with no lattice two engines agree on is searched again under
        # the inlier rule — and only such a run, because the rule changes the
        # pool the panel ranks (``engines.INLIER_FRACTION``)
        first = sum(len(r.candidates) for r in results)
        first_pass = {r.engine: r for r in results}
        spec = retry_spec
        # the retry repeats every unit, so the ladder grows by the same count
        progress.add(len(names) * len(ordered_systems))
        retried = run_units(spec)
        # the retry adds and never removes (#951): a first-pass candidate
        # indexes all but two driven lines, which is what a single-engine truth
        # (a lab pattern's dichotomy-only cell, replaced by its a/2 subcell)
        # needs to stay in the list even where the retry's anchors would have
        # refused it.  First, so a lattice both passes found keeps the stricter
        # fit.  An engine the retry never reached (deadline, cancel) keeps its
        # first-pass result whole, and one it reached only in part keeps the
        # first pass's systems
        results = []
        for name in names:
            prev = first_pass.get(name)
            now = next((r for r in retried if r.engine == name), None)
            if now is None:
                if prev is not None:
                    results.append(prev)
                continue
            if prev is not None:
                now.candidates[:0] = prev.candidates
                now.systems_searched += tuple(
                    s for s in prev.systems_searched
                    if s not in now.systems_searched)
                now.search_complete = {**prev.search_complete,
                                       **now.search_complete}
            results.append(now)
        if results:
            results[0].diagnostics.append(inlier_retry_diagnostic(first))
    trial = next((r for r in results if r.engine == "trial_error"), None)
    if (trial is not None and not trial.candidates and trial.systems_searched
            and not (search_cancel is not None and bool(search_cancel))):
        # the deferred probe: once, over the systems the engine entered, and
        # only when the whole harvest is empty — a cancelled run's silence is
        # explained by the token, not by an index table.  Search phase, so it
        # runs against the search's own deadline, not the reserve
        from .trial_error import dominant_zone_probe

        t0 = time.monotonic()
        hit = dominant_zone_probe(peaks, systems=trial.systems_searched,
                                  spec=spec, quality=quality,
                                  cancel=search_cancel, progress=progress)
        trial.stats["probe.seconds"] = round(time.monotonic() - t0, 3)
        if hit is not None:
            trial.diagnostics.append(hit)

    prior_cands, prior_reports = [], []
    if spec.prior_cells or spec.prior_spacegroups:
        # the stated cells, checked the engines' own way — what survives
        # joins consensus as finder "prior", never as an engine
        from .priors import build_prior_candidates

        prior_cands, prior_reports = build_prior_candidates(
            peaks, spec, quality)
    # ambiguity is deferred to *after* validation (WP-1045): the enumeration
    # is the other unbudgeted per-candidate tail (measured, 45 s of a
    # ceiling-bound corundum run, one candidate's sweep uninterruptible), and
    # run first it consumed the whole validation reserve — while validation
    # is the mandatory check.  Ordering two independent per-candidate
    # computations changes no answer, only which one a stopped clock leaves
    # unasked
    outcome = consensus(results, peaks, spec=spec, quality=quality, top=top,
                        cancel=run_cancel, priors=prior_cands,
                        ambiguity=False, screen=pattern_screen)
    if len(names) == 1:
        outcome.diagnostics.append(single_engine_diagnostic(names[0]))
    if prior_reports:
        from .priors import prior_used_diagnostic

        outcome.diagnostics.append(prior_used_diagnostic(
            prior_reports, jumped, outcome.candidates))
    checked = checked_indices(outcome.candidates, outcome.engines_run, top=top)
    validated = False
    slices_expired = 0
    if validate and data is not None and instrument is not None:
        progress.add(len(checked))
        for pos, i in enumerate(checked):
            if run_cancel is not None and bool(run_cancel):
                break
            cand = outcome.candidates[i]
            label = f"validate:{cand.system} {cand.centring}"
            progress.start(label, system=cand.system, validation=True)
            # budgeted validation (WP-1042): under a declared ceiling each fit
            # draws an equal slice of the remaining clock, so one heavy
            # candidate cannot starve the rest of the shortlist (unbudgeted
            # fits measured 74 of fap's 84 s).  A fast fit's surplus flows to
            # the later slices, which re-divide what actually remains.
            fit_cancel = run_cancel
            slice_deadline = None
            if deadline is not None:
                slice_deadline = Deadline(
                    max(deadline.remaining, 1e-3) / (len(checked) - pos),
                    cancel=run_cancel)
                fit_cancel = slice_deadline
            try:
                cand.lebail = validate_by_lebail(
                    cand, data, instrument, peaks=peaks,
                    two_theta_limits=two_theta_limits, cancel=fit_cancel,
                    pattern_screen=pattern_screen)
            except RefinementCancelled:
                # a truncated fit is not evidence about the candidate: leave
                # ``lebail = None``, which reads ``not_validated`` (capping)
                progress.end(label, validation=True, status="cancelled")
                if slice_deadline is not None \
                        and not slice_deadline.cancelled_by_user():
                    # only this candidate's slice ran out — the next still
                    # gets its share of what remains
                    slices_expired += 1
                    continue
                break
            progress.end(label, validation=True, status=cand.lebail.status)
        validated = True

    # the deferred ambiguity pass, on whatever clock validation left — read
    # between candidates and between one candidate's derivative cells (#895),
    # so a fired token leaves the question unasked
    # (capping) rather than half-answered
    from .consensus import enumerate_ambiguity

    enumerate_ambiguity(outcome, peaks, top=top, cancel=run_cancel)

    # the reserve boundary is part of the ceiling's scheduling: a search it
    # stopped is a budget statement exactly as the ceiling itself is
    search_expired = (search_cancel is not None
                      and search_cancel is not run_cancel
                      and bool(search_cancel))
    if deadline is not None and not deadline.cancelled_by_user() \
            and (deadline.expired() or search_expired or slices_expired):
        requested = ordered_systems
        outcome.diagnostics.append(budget_exhausted_diagnostic(
            float(spec.total_budget_seconds),
            engines_not_run=[n for n in names if n not in outcome.engines_run],
            systems_truncated=[s for s, ok in outcome.search_complete.items()
                               if not ok],
            systems_not_reached=[s for s in requested
                                 if s not in outcome.systems_searched],
            candidates_not_validated=sum(
                1 for i in checked if outcome.candidates[i].lebail is None)
            if validated else 0,
            ceiling_hit=deadline.expired() or search_expired))

    # the gate's ``checked`` is what the enumeration actually covered, not what
    # was scheduled: under a fired token the two differ, and a candidate whose
    # ambiguity question was never asked must not read as answered (WP-1037)
    apply_gate(outcome.candidates, engines_run=outcome.engines_run,
               panel_disagrees=outcome.fom_panel_disagrees, validated=validated,
               search_complete=outcome.search_complete,
               shift_allowance_assumed=outcome.shift_allowance_assumed,
               checked=outcome.ambiguity_checked, quality=quality)
    for cand in outcome.candidates:
        cand.diagnostics = list(cand.diagnostics) + candidate_diagnostics(
            cand, formula=formula, temperature=temperature)

    result = IndexingResult(
        candidates=outcome.candidates, engines_run=outcome.engines_run,
        systems_searched=outcome.systems_searched,
        search_complete=outcome.search_complete,
        engine_stats=outcome.engine_stats,
        fom_panel_disagrees=outcome.fom_panel_disagrees, quality=quality,
        validated=validated, wavelength=peaks.wavelength,
        n_usable_lines=len(peaks.usable()), provenance=provenance,
        preset=ran_preset,
        diagnostics=list(quality.diagnostics) + outcome.diagnostics
        + _pair_shift_diagnostics(quality))
    out = result.model_copy(update={
        "diagnostics": list(result.diagnostics)
        + index_diagnostics(result, instrument)})
    _emit_end(stream, out)
    return out


def _emit_end(stream, result) -> None:
    if stream is None:
        return
    best = result.best_or_none()
    stream.emit("index_end", n_candidates=len(result.candidates),
                confidence=[c.confidence for c in result.candidates],
                abstained=best is None,
                cell=list(best.cell) if best is not None else None,
                validated=result.validated)


def _no_agreement(results) -> bool:
    """No lattice that :data:`~rietx.indexing.engines.MIN_AGREEMENT` engines
    stand behind — or, with fewer engines than that, no candidate at all.  The
    inlier retry's trigger: what the absolute count leaves when it is the cap
    that bound (no cell, or only single-engine cells that explain the foreign
    lines by having a line everywhere)."""
    from .consensus import merge_engine_candidates
    from .engines import MIN_AGREEMENT, corroborated

    if len(results) < MIN_AGREEMENT:
        return not any(r.candidates for r in results)
    return not any(corroborated(c) for c in merge_engine_candidates(results))


def _spec_notes(spec, names: Sequence[str], quality,
                preset: str) -> dict[str, str]:
    """The search's own settings, recorded so a run is reproducible from what it
    reports — including ``seed``, which is the only field a stochastic engine
    would need and which is therefore recorded whether one ran or not.
    ``preset`` is the name that governed the ceiling (WP-1042), so the two keys
    read together: ``full`` writes no ``total_budget_seconds`` because it sets
    none.  Since WP-1045 **every** ``SearchSpec`` field is here — the optional
    narrowings (``centrings``, ``max_volume``, ``shift_template``) only when
    declared, because for those the absence *is* the record (the envelope came
    from the quality report beside this, and no template was adopted) — so two
    chairs handing identical controls to this run produce identical notes,
    which is what the WP's acceptance asserts.
    """
    from .engines import ANCHOR_LINES, DEFAULT_N_UNINDEXED, INLIER_FRACTION

    optional = {
        "max_volume": None if spec.max_volume is None else (
            f"{spec.max_volume:g}" if not isinstance(spec.max_volume, dict)
            else ", ".join(f"{s}:{v:g}"
                           for s, v in sorted(spec.max_volume.items()))),
        "centrings": None if spec.centrings is None else (
            "; ".join(f"{s}:{''.join(spec.centrings_for(s))}"
                      for s in sorted(spec.centrings))),
        "shift_template": spec.shift_template,
        "total_budget_seconds": (
            None if spec.total_budget_seconds is None
            else f"{spec.total_budget_seconds:g}"),
        "prior_cells": None if not spec.prior_cells else "; ".join(
            "(" + ", ".join(f"{v:g}" for v in c) + ")"
            for c in spec.prior_cells),
        "prior_spacegroups": (None if not spec.prior_spacegroups
                              else "; ".join(spec.prior_spacegroups)),
    }
    return {
        "preset": preset,
        "engines": ", ".join(names),
        "systems": ", ".join(spec.systems),
        "d_axis_range_A": f"{spec.min_d_axis:g}-{spec.max_d_axis:g}",
        "min_volume": f"{spec.min_volume:g}",
        "n_unindexed": (
            f"{DEFAULT_N_UNINDEXED}, then inliers if no two engines agree"
            if spec.n_unindexed is None
            else f"inliers >= {INLIER_FRACTION:g}·N and the {ANCHOR_LINES} "
                 f"strongest ({DEFAULT_N_UNINDEXED} on a list of one "
                 "intensity)" if spec.inliers else str(spec.n_unindexed)),
        "n_search_lines": str(spec.n_search_lines),
        "k_sigma": f"{spec.k_sigma:g}",
        "shift_allowance_deg": f"{spec.shift_allowance_deg:g}",
        "budget_seconds": f"{spec.budget_seconds:g}",
        "max_candidates": str(spec.max_candidates),
        **{k: v for k, v in optional.items() if v is not None},
        "seed": str(spec.seed),
        "indexing_thresholds_version": quality.thresholds_version,
    }


__all__ = ["ABSENT_SIGMA", "ABSENT_WINDOW_FWHM", "DUMMY_SPECIES",
           "absent_reflections", "index_pattern", "seed_widths",
           "structure_from_candidate", "validate_by_lebail", "validation_plan"]
