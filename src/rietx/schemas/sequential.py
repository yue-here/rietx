"""Schemas for a sequential (in-situ / parametric) refinement series.

A series is N separate refinements, ordered, each warm-started from its
predecessor — not one joint residual (that is the multi-histogram path,
``rietx.multi``).  What the user wants back is therefore not N unrelated
results but a **trajectory**: a(T), Biso(t), the weight fractions against the
series coordinate, with esds, and with the per-pattern status of the fit that
produced each point.

Following the history DAG's rule (see :mod:`rietx.schemas.history`), a
:class:`SeriesResult` stores **summaries, not curves**.  Nine 7251-point
patterns' worth of ``y_obs``/``y_calc``/``y_background``/``sigma`` is ~2 MB of
JSON that is already on disk as the input files; the refined values, their
esds, the agreement indices and the diagnostics are what a series is *for*, and
they are a few kB.  The full :class:`~rietx.schemas.results.RefinementResult`
of each pattern stays reachable in memory on the
:class:`~rietx.sequential.SequentialRefinement` that produced it.
"""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import Field

from ..report.schemas import MomentEvidence
from .common import Base, Diagnostic, Mode, Provenance
from .results import (
    DELIVERABLES,
    PhaseAgreement,
    QuantitativePhaseAnalysis,
    RefinedParameter,
    Statistics,
    _diagnostic_lines,
)


class SeriesEntry(Base):
    """One pattern's place in the series: what was fitted and how it went.

    ``n_iterations`` lives here, per pattern — a series has no single pooled
    figure, so it is not on :class:`~rietx.schemas.results.Statistics` even
    though ``statistics`` below is one.
    """

    index: int
    label: str = ""
    #: The series coordinate — temperature, time, pressure, composition.
    #: ``None`` when the caller gave none, in which case ``index`` is the axis.
    x: float | None = None

    status: Literal["converged", "max_iter", "diverged"] = "converged"
    statistics: Statistics | None = None
    parameters: list[RefinedParameter] = Field(default_factory=list)
    qpa: QuantitativePhaseAnalysis | None = None
    #: Per-phase Bragg agreement, copied from each pattern's
    #: :attr:`~rietx.schemas.results.RefinementResult.phase_agreement` by
    #: :func:`rietx.sequential._entry_from_result` (the writer — WP-1076's rule).
    #:
    #: Carried because the signal existed on every underlying result and was
    #: dropped at the series boundary, and because a series is where a per-phase
    #: index is worth *iterating*: one pattern's R_B is a value, sixty are a
    #: trajectory, and a trajectory is a shape a single number cannot be read as.
    #:
    #: **It is not the answer to "is this phase real".**  Neither index is
    #: weighted, and I(obs) is the observed pattern partitioned in proportion to
    #: I(calc) — so a phase whose reflections sit under a stronger phase's peaks
    #: receives the intensity it predicted and scores well for having predicted
    #: it.  The bias is in the definition, not in the fit, and in-repo the
    #: arithmetic runs the *other* way to intuition: 11-BM NAC's 1.35 wt% CaF₂
    #: impurity scores R_B 0.385 against the major phase's 0.052, the whole
    #: misfit sitting in four reflections under strong NAC peaks (WP-1069).  A
    #: *low* R_B on a trace phase is therefore as consistent with a fully
    #: overlapped, self-fulfilling partition as with a real phase, and nothing
    #: here separates the two.
    #: :func:`~rietx.optimize.statistics.structure_r_factors` holds the
    #: definitions and the warning.
    #:
    #: The measurement that does answer that question is ``PHASE_UNCONSTRAINED``
    #: — the phase scale's significance, its value over its esd against
    #: counting noise (WP-1523), reaching an entry through :attr:`diagnostics`
    #: and aggregating over the chain as ``SEQUENTIAL_PERSISTENT_FINDING``.
    #: R_B belongs beside it and
    #: beside the weight with its esd, never in front of either.
    #:
    #: Empty outside Rietveld mode, for the reason it is empty on
    #: ``RefinementResult`` there — in Le Bail the partition *is* the fit and in
    #: Pawley the intensities are parameters, so I(obs) would be compared against
    #: itself.
    phase_agreement: list[PhaseAgreement] = Field(default_factory=list)
    #: The moment arm (WP-1327) for **this pattern**, one row per magnetic
    #: site, written by :meth:`rietx.sequential.SequentialRefinement._chain`
    #: (through ``_moment_evidence``) from the same
    #: :func:`rietx.report.magnetic.analyse_moments` every single-pattern
    #: report uses — never a second reading of it (WP-1076).
    #:
    #: **It is here because a series without it is a trap** (WP-1329).  A
    #: sequential magnetic refinement warm-starts the moment like any other
    #: parameter and hands back a signed ``phases.i.atoms.j.moment.dof0`` row
    #: in :attr:`parameters`; every piece of evidence that stops that number
    #: being misread — ``supported``, the esd the ratio is taken against, the
    #: direction the powder average could not determine, the dipole
    #: approximation in force — lived only on ``Refinement.report().magnetic``,
    #: which a series never built.  A chain of converged fits then hands back
    #: one ``dof0`` value per pattern and no way to tell a supported moment
    #: from an unsupported one, so "|m| against T" plotted from ``dof0`` draws
    #: an unsupported moment as a small one.  That is the whole reason the
    #: field exists.
    #:
    #: Empty for the three reasons ``FitReport.magnetic`` is empty — no phase
    #: declares a moment, no compiled model reached the writer, or the
    #: histogram carries no magnetic term at all — and never "no moment was
    #: found".
    magnetic: list[MomentEvidence] = Field(default_factory=list)
    diagnostics: list[Diagnostic] = Field(default_factory=list)

    #: Total least-squares iterations over **every attempt** on this pattern,
    #: every rung of the escalation ladder included.  The headline warm-start
    #: number: it is what a warm start actually buys, and it is measured rather
    #: than assumed (see WP-0505's acceptance).
    n_iterations: int = 0
    #: True when the warm start was rejected and this pattern was refitted from
    #: the initial models (see ``SEQUENTIAL_RESEED``) — equivalently, when the
    #: ladder ran and ``rung`` came back ``"cold"``.  A reseeded point is
    #: still a good fit — but it is *not* evidence that the trajectory is
    #: continuous there, because its starting point did not come from its
    #: neighbour.  The middle rung does **not** set it: ``"warm_staged"`` is
    #: still a warm start, so the chain is unbroken there.
    reseeded: bool = False
    #: Rwp the **first** (warm) attempt reached, set whenever the ladder
    #: escalated at all.  With ``reseeded`` it says how the escalation ended:
    #: both set means a cold restart rescued the pattern, ``rwp_warm`` alone
    #: means the fence fired but a warm attempt was still the best of the
    #: ones tried — worth seeing, since it marks a pattern the series found
    #: hard for a reason no restart could fix.  ``None`` when that first
    #: attempt raised rather than returned: it reached no Rwp, and
    #: :attr:`rungs_raised` says what it raised.
    rwp_warm: float | None = None
    #: Which attempt produced the values on this entry (WP-1051).  The chain
    #: escalates only on failure: ``"warm"`` is the collapsed warm refit
    #: (``refit="single"``'s first rung), ``"warm_staged"`` the full staged plan
    #: from the warm state, ``"cold"`` the full staged plan from the initial
    #: models.  The **first** pattern of a chain is always ``"cold"`` — it has
    #: no predecessor to warm from — which is why this field says where the
    #: numbers came from while ``reseeded`` says whether the chain was *broken*
    #: here; those are different questions and only the second one has a fence.
    rung: Literal["warm", "warm_staged", "cold"] = "warm"
    #: Every rung attempted on this pattern, in ladder order: one entry for a
    #: pattern that fitted first time, up to three when the ladder ran to the
    #: end.  It is what makes the escalation auditable — ``rung`` alone cannot
    #: say whether the winning attempt was the only one, and the cost in
    #: ``n_iterations`` is the sum over exactly these less the ones in
    #: :attr:`rungs_raised`, which report no count to charge.
    rungs_tried: list[str] = Field(default_factory=list)
    #: The rungs of :attr:`rungs_tried` whose fit **raised** rather than
    #: returned, each with ``repr(exc)`` (WP-1333).  A raised rung is a rung
    #: that lost, and the ladder escalates past it exactly as past a diverged
    #: one, so an entry exists only because a later rung returned; a pattern
    #: on which every rung raised has no entry and is a
    #: :class:`SeriesFailure` instead.  The case that made this a ladder
    #: member rather than a failure is issue #224: a neighbour that converged
    #: with a runaway cell hands it to every warm rung, the enumerator
    #: refuses it at compile, and only the cold rung escapes.  Written by
    #: ``SequentialRefinement._chain``; empty — which is true — wherever no
    #: rung raised.
    rungs_raised: dict[str, str] = Field(default_factory=dict)
    #: The Rwp limit the chain's fence set at this pattern: ``reseed_factor`` ×
    #: the median Rwp of the patterns accepted before it (WP-1469).  Recorded
    #: rather than re-derived because the median is the *chain's* state, and
    #: every fence here is read off the entry so a reloaded
    #: :class:`SeriesResult` reports what the run did; :attr:`above_fence` is
    #: the verdict.  Recorded whatever ``reseed`` says, as the quarantine is:
    #: the limit is a fact about the pattern, not about how hard the chain
    #: tried.  ``None`` where no median existed — the first pattern walked, or
    #: every pattern before it quarantined — and in a document written before
    #: the field: no fence judged it.  Written by
    #: ``SequentialRefinement._chain``.
    rwp_fence: float | None = None

    #: Where this pattern's own history lives (one tree per pattern — a tree is
    #: pinned to one pattern by its data fingerprint).
    node_id: str | None = None
    tree_id: str | None = None

    @property
    def above_fence(self) -> bool:
        """The kept attempt is still above :attr:`rwp_fence` (WP-1469).

        Every rung the chain tried came back above the limit, so the best of
        them is kept but is not like its neighbours: a specimen change the
        model lacks, a bad frame, or fewer counts (a blank frame is the last,
        its Rwp risen with its Rexp).  ``SEQUENTIAL_RWP_OUTLIER`` says so and
        quotes the GoF and Rexp that tell them apart.  The pattern is not
        quarantined — it seeds its successor and joins the median, since a
        lasting change must be able to become the new normal.  False on a
        ``"diverged"`` entry, which ``SEQUENTIAL_UNRECOVERED`` already covers,
        and wherever no fence applied.
        """
        return (self.status != "diverged" and self.rwp_fence is not None
                and self.statistics is not None
                and self.statistics.rwp > self.rwp_fence)

    def value(self, path: str) -> float | None:
        for p in self.parameters:
            if p.path == path:
                return p.value
        return None

    def stderr(self, path: str) -> float | None:
        for p in self.parameters:
            if p.path == path:
                return p.stderr
        return None

    def moment(self, site: str | None = None) -> MomentEvidence | None:
        """This pattern's moment row for ``site``, or ``None``.

        ``site`` is the modulus dot-path (``MomentEvidence.path``) or the atom
        label; ``None`` takes the only row and refuses when there is more than
        one, because "the moment" is not a well-defined quantity on a structure
        with two magnetic sites and silently picking the first is how a
        two-sublattice answer gets quoted as a one-sublattice one.
        """
        if site is None:
            if len(self.magnetic) > 1:
                raise ValueError(
                    f"this entry carries {len(self.magnetic)} magnetic sites "
                    f"({', '.join(e.atom for e in self.magnetic)}); name one "
                    f"by its path or label")
            return self.magnetic[0] if self.magnetic else None
        for e in self.magnetic:
            if site in (e.path, e.atom):
                return e
        return None


class Trajectory(Base):
    """One parameter's path across the series, with its per-point esds.

    ``x`` is the series coordinate when one was given and the pattern index
    otherwise; ``x_label`` says which, so a plot axis is never mislabelled.
    ``value``/``stderr`` are aligned with it, and ``stderr`` entries are
    ``None`` wherever that pattern did not estimate one (a parameter that was
    not free in that fit, or a stage that returned no covariance).
    """

    path: str
    x: list[float] = Field(default_factory=list)
    x_label: str = "index"
    value: list[float] = Field(default_factory=list)
    stderr: list[float | None] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    #: Which entry of ``SeriesResult.entries`` each point came from, by
    #: **position** (WP-1310).  A trajectory skips the patterns a path is
    #: absent from, so it is a subsequence of the series and nothing else here
    #: says which one: ``x`` can repeat when a caller supplies a coordinate,
    #: and ``label`` defaults to ``""`` for every entry.  ``to_table`` needs
    #: the alignment to put a derived path in a row, and without it would have
    #: to re-resolve the path itself — which is the second resolver this field
    #: exists to remove.  Positional rather than ``SeriesEntry.index``, since
    #: the row being filled is a position.
    positions: list[int] = Field(default_factory=list)

    def __len__(self) -> int:
        return len(self.value)

    def arrays(self):
        """``(x, value, stderr)`` as float arrays; missing esds become NaN."""
        import numpy as np

        return (np.asarray(self.x, dtype=float),
                np.asarray(self.value, dtype=float),
                np.asarray([np.nan if s is None else s for s in self.stderr],
                           dtype=float))


def _unservable(series: "SeriesResult", path: str) -> str:
    """Why ``path`` reaches no pattern, and what the caller could have meant.

    A typo in a derived path and a typo in a parameter path fail for different
    reasons and want different lists back: a phase name is checked against the
    phases that *carry that kind of curve*, which is not the same set as the
    QPA phases (a phase can have an agreement index and no weight fraction —
    QPA needs Z and a molar mass and a structure R does not).
    """
    if path.startswith("qpa."):
        known = sorted({r.name for e in series.entries
                        if e.qpa is not None for r in e.qpa.phases})
        what = "carries a weight fraction"
    elif path.startswith("magnetic."):
        sites = series.magnetic_sites()
        site = path[len("magnetic."):]
        return (f"no pattern in this series carries {path!r}: no magnetic "
                f"site {site!r} has a moment row here"
                + (f" (available: {', '.join(sites)})" if sites else
                   " — no pattern of this series carries a moment row at all"))
    elif series.is_derived_path(path):
        known = series.agreement_phases()
        what = "carries an agreement index"
    else:
        return (f"no pattern in this series carries {path!r}: it is not a "
                f"refined parameter of any entry (available: "
                f"{', '.join(series.paths()[:6])}…)")
    prefix, _, phase = path.partition(".")
    return (f"no pattern in this series carries {path!r}: no phase named "
            f"{phase!r} {what} here"
            + (f" (available: {', '.join(known)})" if known else
               f" — no phase in this series carries a {prefix!r} curve at all"))


class SeriesStep(Base):
    """One step ``SEQUENTIAL_DISCONTINUITY`` flagged, as fields (WP-1469).

    The diagnostic says it in prose and names the parameter in ``where``;
    this says between *which two patterns* and *how far*, so a caller never
    parses the message for the pair.  One per diagnostic, in the same order,
    and ``path`` is that diagnostic's ``where[0]`` — the scan flags at most
    one step per path, so the path is the key.  The verification pass
    re-measures exactly this pair, and the trajectory plot shades it.
    """

    path: str
    #: the two patterns' labels, earlier first
    labels: tuple[str, str]
    #: their :attr:`SeriesEntry.index`, earlier first
    indices: tuple[int, int]
    #: later minus earlier, **signed**: the verification ratio divides by it,
    #: and two magnitudes divided would call a cold pair that stepped the other
    #: way a reproduction.  The message keeps the magnitude.
    step: float


class SeriesFailure(Base):
    """One pattern the chain could not fit at all — an uncaught exception out
    of :meth:`~rietx.refine.Refinement.fit` on **every** rung of the ladder
    (WP-1333: a rung that raises escalates, so a pattern a later rung rescued
    is an entry with ``rungs_raised`` instead), not a converged-but-bad result
    (that is ``SeriesEntry.status == "diverged"``, a different thing: a
    fit that ran to completion and landed somewhere the reseed fence
    rejected).  This is the fit never finishing — ``LinAlgError: SVD did not
    converge``, and anything else a solver can raise on a genuinely
    near-singular Jacobian.

    ``index``/``label`` place it in the series exactly as
    :class:`SeriesEntry` does; ``exception`` is ``repr(exc)`` (the type and
    message, never the traceback — this is a summary field like the rest of
    this module, not a debugging dump) of the **last** rung's exception,
    captured where ``SequentialRefinement`` caught it.
    """

    index: int
    label: str
    exception: str


class MagneticOnset(Base):
    """Where along the series axis the moment stops being supported (WP-1329).

    **It is a bracket, not a fitted number.**  What the series measures on each
    pattern is a verdict — the modulus is above
    :data:`~rietx.report.schemas.MOMENT_SUPPORT_SIGMA` of its own esd, or it is
    not — so what the series can say about the onset is that it lies between
    the last pattern that supported a moment and the first that did not.
    :attr:`x` is the midpoint of that pair and :attr:`x_esd` **half its width**,
    which is the honest uncertainty of a bracket and is set by the *spacing of
    the measurements*: a ramp with 50 K steps cannot locate T_N to better than
    ±25 K however good each fit is.  Quoting it as a critical temperature with
    a fitted esd would be a claim about a curve nothing here fits — the
    parametric form of m(T) is WP-1325's question and this WP's explicit
    non-goal.

    :attr:`monotone` is the check that makes the bracket meaningful.  A series
    whose ``supported`` flags switch more than once along the axis has no single
    boundary, and then :attr:`x` is ``None`` and :attr:`boundaries` lists every
    switch: an interleaved verdict is a result about the fits (a warm start
    carrying a stale moment, a pattern the ladder rescued) and averaging it into
    one temperature would hide exactly that.
    """

    #: the modulus DOF the onset is about
    path: str = ""
    #: the site's atom label, for a plot title
    atom: str = ""
    #: midpoint of the bracket; ``None`` when there is no single boundary in
    #: the window (every pattern supported, none supported, or not monotone)
    x: float | None = None
    #: half the bracket's width — the measurement spacing, not a fit's esd
    x_esd: float | None = None
    #: ``[x_last_supported, x_first_unsupported]`` ordered along the axis
    bracket: list[float] = Field(default_factory=list)
    #: the two patterns' labels, in the same order as :attr:`bracket`
    bracket_labels: list[str] = Field(default_factory=list)
    #: ``"falls"``: supported at low x and not at high x — the ordinary
    #: temperature ramp.  ``"rises"``: the reverse.  ``"none"``: no boundary.
    sense: Literal["falls", "rises", "none"] = "none"
    #: False when the ``supported`` flags switch more than once along the axis
    monotone: bool = True
    #: every ``(x_low, x_high)`` pair across which the verdict switches
    boundaries: list[list[float]] = Field(default_factory=list)
    n_supported: int = 0
    n_held: int = 0
    #: patterns that carry the site's row and **no verdict**, left out of the
    #: bracket — see :attr:`MagneticTrajectory.measured`
    n_unmeasured: int = 0
    unmeasured_labels: list[str] = Field(default_factory=list)
    #: how many patterns of the window came back other than ``"converged"``
    n_unconverged: int = 0
    #: **Whether neither pattern of the bracket owes its verdict to a fit that
    #: stopped early**, and it is the field that decides whether the bracket
    #: may be quoted at all.  ``supported`` is a ratio |m|/σ against *that*
    #: pattern's own covariance, so a fit cut short at its iteration cap can
    #: hand back a verdict about an intermediate state.
    #:
    #: **The test is asymmetric, and the asymmetry is measured rather than
    #: assumed.**  Only an unconverged fit reporting *supported* is suspect:
    #:
    #: * A modulus **descending to nothing does not terminate.**  |F_m|² ∝ m²,
    #:   so the column vanishes with the moment and the flat direction WP-1327
    #:   holds for the *angles* opens up for the modulus itself once there is
    #:   no moment left.  On the synthetic ramps of
    #:   ``tests/test_magnetic_series.py`` a pattern with no moment can stop at
    #:   its iteration cap, ``"max_iter"``, with the modulus near 10⁻⁶ μ_B.
    #:   That truncation is a property of the answer, not a
    #:   doubt about it, and refusing the bracket for it would refuse every
    #:   ordering transition there is.
    #: * A modulus **climbing out of the floor terminates at once.**  Same
    #:   data, moment seeded *at* the floor against a pattern carrying a real
    #:   4.5 μ_B: ``max_iter=1`` already reaches a supported modulus above
    #:   1 μ_B (``test_the_ascent_out_of_the_floor_terminates_at_once``).  So a
    #:   truncated fit cannot
    #:   manufacture "unsupported" the way it can manufacture "supported".
    #: * And the failure this catches is real: with ``max_iter=1`` on every
    #:   stage, the modulus above the transition came back **supported** and
    #:   the onset moved to a confident, wrong bracket — while neither the
    #:   reseed fence nor the floor carry fired, because Rwp was fine and no
    #:   pattern ever came back unsupported
    #:   (``test_a_starved_chain_reports_a_supported_moment_above_the_``
    #:   ``transition_and_is_flagged``).
    #:
    #: ``None`` wherever there is no bracket to judge — no rows, no verdict,
    #: every pattern supported, none supported, or not monotone — so consumers
    #: ask ``is False``: a defaulted ``True`` there would say "verdicts final"
    #: about a bracket that does not exist.
    bracket_verdicts_final: bool | None = None
    note: str = ""

    def __str__(self) -> str:
        if self.x is None:
            return f"onset: not located — {self.note}"
        return (f"onset: {self.x:g} ± {self.x_esd:g} (bracket "
                f"{self.bracket[0]:g} … {self.bracket[1]:g}, {self.sense}), "
                f"{self.n_supported} supported / {self.n_held} held"
                + ("" if self.bracket_verdicts_final is not False else
                   " — NOT QUOTABLE: a bracket pattern's supported verdict "
                   "came from a fit that stopped early"))


class MagneticTrajectory(Trajectory):
    """|m| against the series axis, with the held patterns marked as held.

    A :class:`Trajectory` — so it plots, exports and pairs with a cell edge
    through exactly the same code — with the one column a moment trajectory
    cannot do without: :attr:`supported`, per point.

    **The held points keep their value and lose their esd**, and both halves of
    that are deliberate (WP-1329's acceptance).  The value is what the fit
    landed on and it is the numerator of the ratio that called the point
    unsupported, so deleting it would delete the evidence; the esd is withheld
    because an error bar on a number the data does not support reads as a
    small measured moment, which is the single misreading this whole arm
    exists to prevent.  ``arrays()`` therefore hands a plotter NaN there, and
    an errorbar draws nothing.

    A held point is **not zero**.  ``value`` is the modulus the fit reached —
    on the Cr₂WO₆ 150 K pattern a few hundredths of a μ_B against an esd
    larger than itself — and plotting it as zero would claim a measurement of
    zero that no fit made.
    """

    #: per point, whether that pattern's modulus cleared
    #: :data:`~rietx.report.schemas.MOMENT_SUPPORT_SIGMA` of its own esd
    supported: list[bool] = Field(default_factory=list)
    #: per point, whether that pattern gave a verdict **at all**.  False where
    #: the row has no esd to take the ratio against — the modulus was stated
    #: and held, or the pattern did not see the phase and WP-1301 held its
    #: structural paths for the stage, a closed-shutter frame being the plain
    #: case — and where the fit ``"diverged"`` and was quarantined.  **Not**
    #: where the kept fit stayed above the chain's Rwp fence
    #: (:attr:`SeriesEntry.above_fence`): that fence reports and does not
    #: judge (WP-1469), and on the starved-chain ramp of
    #: ``tests/test_magnetic_series.py``, fed 20 iterations, it fires on a
    #: converged, correct pattern — the first above the transition, Rwp 0.0166
    #: against a limit of 0.0151 set by the one ordered pattern before it.
    #: Withholding that verdict widened the right bracket, 10 → 70 K, to
    #: 10 → 80 K.  A bad frame that still sees its phase keeps a verdict
    #: against its own covariance, and ``SEQUENTIAL_RWP_OUTLIER`` names it on
    #: the same series.  Such a
    #: point is neither released nor held by the data: it is plotted, its
    #: ``supported`` is False and its esd ``None``, and :func:`locate_onset`
    #: leaves it out.  Counting it as held put a confident bracket one
    #: pattern early on a ramp with a blank frame beside the transition.
    measured: list[bool] = Field(default_factory=list)
    #: per point, that pattern's fit status — carried because ``supported`` is
    #: a ratio against a covariance and a fit that stopped at its cap does not
    #: have one worth taking a ratio against.  See
    #: :attr:`MagneticOnset.bracket_verdicts_final`.
    status: list[str] = Field(default_factory=list)
    #: the site's atom label and form-factor ion, for a title and a caption
    atom: str = ""
    ion: str = ""
    #: the onset read off :attr:`supported`, never off :attr:`value`
    onset: MagneticOnset | None = None

    @property
    def held(self) -> list[bool]:
        """The complement of :attr:`supported`, spelled the way the WP does."""
        return [not s for s in self.supported]

    def __str__(self) -> str:
        head = (f"MagneticTrajectory {self.atom or self.path} "
                f"({len(self.value)} pattern(s), {self.x_label})")
        rows = []
        measured_col = self.measured or [True] * len(self.value)
        for xv, v, sd, ok, measured, st, lab in zip(
                self.x, self.value, self.stderr, self.supported, measured_col,
                self.status, self.labels, strict=True):
            esd = "held" if sd is None else f"± {sd:.4g}"
            verdict = ("released" if ok else "HELD") if measured else \
                "NO VERDICT"
            rows.append(f"  x={xv:g} |m|={v:.4g} {esd} {verdict}"
                        f"{'' if st == 'converged' else f' [{st}]'}  {lab}")
        if self.onset is not None:
            rows.append(f"  {self.onset}")
        return "\n".join([head, *rows])


def locate_onset(traj: MagneticTrajectory) -> MagneticOnset:
    """The onset of a moment along one trajectory, read off ``supported``.

    The one authority for turning a column of per-pattern verdicts into a
    bracket, and it reads **only** :attr:`MagneticTrajectory.supported` — never
    :attr:`~MagneticTrajectory.value`.  That is the WP's rule and it is not a
    stylistic one: a warm start carries each pattern's modulus into the next,
    so the |m| column of a chain is smooth by construction wherever the fits
    struggle, and an onset read off the values is a reading of the chain while
    an onset read off the verdicts is a reading of the data
    (``test_the_onset_is_read_off_the_verdicts_and_not_off_the_values``).

    Ordering is by the **axis**, not by the walk: a chain refined from high
    temperature down still reports its onset on the temperature axis, so the
    number is comparable between a warming and a cooling pass.  Ties in x keep
    series order.
    """
    status = list(traj.status) or ["converged"] * len(traj.supported)
    measured = list(traj.measured) or [True] * len(traj.supported)
    if not traj.supported:
        onset = MagneticOnset(path=traj.path, atom=traj.atom)
        onset.note = ("no pattern of the series carries a moment row: no "
                      "phase declared one, or no magnetic term was computed")
        return onset
    # A point with no verdict is not evidence either way, so it is left out
    # of the bracket rather than read as held; the bracket then spans it,
    # which is the honest width (the unmeasured labels ride on the onset).
    keep = [i for i in range(len(traj.supported)) if measured[i]]
    onset = MagneticOnset(
        path=traj.path, atom=traj.atom,
        n_supported=sum(1 for i in keep if traj.supported[i]),
        n_held=sum(1 for i in keep if not traj.supported[i]),
        n_unconverged=sum(1 for i in keep if status[i] != "converged"),
        n_unmeasured=len(traj.supported) - len(keep),
        unmeasured_labels=[traj.labels[i]
                           for i in range(len(traj.supported))
                           if not measured[i]])
    n = len(keep)
    if n == 0:
        onset.note = (
            f"none of the {onset.n_unmeasured} pattern(s) gives a verdict on "
            f"the moment — each was held, or diverged — so there is no onset "
            f"to locate")
        return onset
    order = sorted(keep, key=lambda i: (traj.x[i], i))
    xs = [traj.x[i] for i in order]
    ok = [traj.supported[i] for i in order]
    labels = [traj.labels[i] for i in order]
    states = [status[i] for i in order]
    if all(ok):
        onset.note = (
            f"every one of the {n} pattern(s) supports a moment: the onset is "
            f"outside the measured window, above x = {max(xs):g}")
        return onset
    if not any(ok):
        onset.note = (
            f"not one of the {n} pattern(s) supports a moment, so there is no "
            f"onset to locate — the moment is unsupported across the whole "
            f"window, which is a result about the window and not about the "
            f"specimen")
        return onset
    switches = [i for i in range(n - 1) if ok[i] != ok[i + 1]]
    onset.boundaries = [[xs[i], xs[i + 1]] for i in switches]
    if len(switches) > 1:
        onset.monotone = False
        onset.note = (
            f"the supported/held verdict switches {len(switches)} times along "
            f"the axis ({', '.join(f'{a:g}–{b:g}' for a, b in onset.boundaries)}"
            f"), so the series has no single onset. An interleaved verdict is a "
            f"statement about the fits — a warm start carrying a stale moment, "
            f"a pattern the ladder rescued cold, a specimen that changed — and "
            f"the bracket a monotone series would give is withheld rather than "
            f"averaged over them")
        return onset
    i = switches[0]
    onset.bracket = [xs[i], xs[i + 1]]
    onset.bracket_labels = [labels[i], labels[i + 1]]
    onset.sense = "falls" if ok[i] else "rises"
    onset.x = 0.5 * (xs[i] + xs[i + 1])
    onset.x_esd = 0.5 * abs(xs[i + 1] - xs[i])
    released, held = ((labels[i], labels[i + 1]) if ok[i]
                      else (labels[i + 1], labels[i]))
    # the asymmetric test the field documents: a *supported* verdict from a
    # fit that stopped early is the one that can be an artefact of the stop
    onset.bracket_verdicts_final = not any(
        ok[j] and states[j] != "converged" for j in (i, i + 1))
    onset.note = (
        f"the moment is supported on {released} and not on {held}, so the "
        f"onset lies between x = {xs[i]:g} and {xs[i + 1]:g}. The ± is half "
        f"that gap — the spacing of the measurements — and not a fitted esd: "
        f"nothing here fits a form for |m|(x), which is WP-1325's question")
    inside = [traj.labels[j] for j in range(len(traj.supported))
              if not measured[j] and xs[i] <= traj.x[j] <= xs[i + 1]]
    if inside:
        onset.note += (
            f". The bracket spans {', '.join(inside)}, which gives no verdict "
            f"(held or diverged) and is left out rather than read as held")
    if onset.bracket_verdicts_final is False:
        bad = [labels[j] for j in (i, i + 1)
               if ok[j] and states[j] != "converged"]
        onset.note += (
            f". Do not quote it: {' and '.join(bad)} reports a *supported* "
            f"moment from a fit that stopped early, and 'supported' is |m| "
            f"against that pattern's own esd — a modulus that has not "
            f"finished falling is exactly how a moment above the transition "
            f"survives as a small confident number")
    return onset


class SeriesResult(Base):
    """The result of a sequential refinement over an ordered set of patterns.

    Iterating it yields :class:`SeriesEntry` in series order.  Series-level
    diagnostics (path dependence, discontinuities, reseeds) sit on
    :attr:`diagnostics`; per-pattern ones stay on their entry.
    """

    mode: Mode = "rietveld"
    entries: list[SeriesEntry] = Field(default_factory=list)
    x_label: str = "index"
    #: ``"forward"``/``"backward"``: the chain direction whose fits are
    #: reported in :attr:`entries`.  ``"both"`` means the series was run twice
    #: and the two trajectories compared — the reported entries are the forward
    #: ones, and the comparison is in :attr:`diagnostics`.
    direction: Literal["forward", "backward", "both"] = "forward"
    #: the reverse chain, present iff ``direction == "both"`` (WP-1076).
    #: Its own ``backward`` is always ``None``: it is one extra level, not a
    #: cycle.  Without it a caller of :func:`~rietx.refine_sequential` received
    #: the ``SEQUENTIAL_PATH_DEPENDENT`` diagnostics and had no way to reach
    #: the trajectory they are about — the comparison was reachable only from
    #: ``SequentialRefinement.backward_``, which the one-shot API never
    #: returns.
    backward: "SeriesResult | None" = None
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    #: Every ``SEQUENTIAL_DISCONTINUITY`` in :attr:`diagnostics` as a
    #: :class:`SeriesStep`, in the same order (WP-1469): the pair the
    #: diagnostic names in prose.  ``None`` in a document written before the
    #: field, which may carry the diagnostics without them — "not recorded",
    #: never "no step".  Written by ``SequentialRefinement.fit``; ``[]`` on a
    #: series that flagged nothing.
    discontinuities: list[SeriesStep] | None = None
    #: every pattern on which every rung of the ladder raised, so the chain
    #: has no entry for it — see :class:`SeriesFailure`.  Populated under the
    #: default ``on_error="carry"`` and under ``"skip"``; under ``"raise"``
    #: ``SequentialRefinement.fit`` never returns, and the same list is on
    #: ``SequentialRefinement.failures_`` and the exception.  Empty — which is
    #: true — on a chain where every pattern returned a fit.  On
    #: :attr:`backward` it is the verification chain's own, which costs the
    #: path-dependence comparison those patterns and nothing else.
    failures: list[SeriesFailure] = Field(default_factory=list)
    #: ``len(failures)``, carried as its own field because a consumer
    #: checking "did every pattern fit" wants a number, not a list to count —
    #: the same reason ``StageResult.n_degenerate_cell_probes`` sits beside a
    #: guard that could otherwise only be read by counting diagnostics.
    n_failed: int = 0
    provenance: Provenance | None = None

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self):  # type: ignore[override]
        return iter(self.entries)

    def __getitem__(self, i: int) -> SeriesEntry:
        return self.entries[i]

    @property
    def labels(self) -> list[str]:
        return [e.label for e in self.entries]

    @property
    def x(self) -> list[float]:
        """The series axis: the given coordinate, or the pattern index."""
        return [float(e.index) if e.x is None else e.x for e in self.entries]

    @property
    def rwp(self) -> list[float]:
        return [e.statistics.rwp if e.statistics else float("nan")
                for e in self.entries]

    @property
    def n_iterations(self) -> int:
        """Least-squares iterations over the chain this result *reports*.

        That is :attr:`entries`, so under ``direction="both"`` it is the
        forward chain only and **not what the run cost** — the reverse chain is
        a second complete set of fits, and its own count is
        ``result.backward.n_iterations`` (WP-1076; the docstring said "over the
        whole series", which was true of a one-directional run and false of
        this one).  Measured on the eight-mixture round robin: 816 either way,
        against a wall clock of 33.7 s forward and 83.7 s for ``"both"``.
        """
        return sum(e.n_iterations for e in self.entries)

    def trajectory(self, path: str) -> Trajectory:
        """One parameter's trajectory across the series.

        Patterns where the path is absent are skipped rather than filled — a
        gap in a trajectory is a real thing (a phase that was not in the model
        yet, a stage that did not run) and inventing a value for it would be
        exactly the confident-wrong-singleton failure the FitReport gates
        against.
        """
        traj = Trajectory(path=path, x_label=self.x_label)
        for i, (e, xv) in enumerate(zip(self.entries, self.x, strict=True)):
            found = next((p for p in e.parameters if p.path == path), None)
            if found is None:
                continue
            traj.x.append(xv)
            traj.value.append(found.value)
            traj.stderr.append(found.stderr)
            traj.labels.append(e.label)
            traj.positions.append(i)
        return traj

    def paths(self, *, varied_only: bool = False) -> list[str]:
        """Every parameter path present in the series, in first-seen order.

        A :class:`~rietx.schemas.results.RefinementResult` records the
        parameters the fit *determined* — free ones and the tied ones that
        follow them (a hexagonal ``cell.b`` is not free but is every bit as
        measured as ``cell.a``), so the default keeps both.  ``varied_only``
        drops the tied ones.
        """
        out: list[str] = []
        seen: set[str] = set()
        for e in self.entries:
            for p in e.parameters:
                if varied_only and not p.vary:
                    continue
                if p.path not in seen:
                    seen.add(p.path)
                    out.append(p.path)
        return out

    def qpa_trajectory(self, phase: str) -> Trajectory:
        """A phase's weight fraction (as a percentage) across the series."""
        traj = Trajectory(path=f"qpa.{phase}", x_label=self.x_label)
        for i, (e, xv) in enumerate(zip(self.entries, self.x, strict=True)):
            if e.qpa is None:
                continue
            row = next((r for r in e.qpa.phases if r.name == phase), None)
            if row is None:
                continue
            traj.x.append(xv)
            traj.value.append(100.0 * row.weight_fraction)
            traj.stderr.append(None if row.weight_fraction_stderr is None
                               else 100.0 * row.weight_fraction_stderr)
            traj.labels.append(e.label)
            traj.positions.append(i)
        return traj

    def agreement_trajectory(self, phase: str, *,
                             metric: str = "r_bragg") -> Trajectory:
        """A phase's structure agreement index across the series.

        ``qpa_trajectory``'s shape, over the ``phase_agreement`` each entry now
        carries.  ``metric`` is ``"r_bragg"`` (McCusker et al. 1999 eq 14) or
        ``"r_f"`` (eq 13); a fit quotes at least one of them, and *which* is a
        reader's convention rather than something this method should choose.

        **Every ``stderr`` is ``None``, and that is a fact rather than a gap.**
        A residual is not a fitted parameter: R_Bragg has no covariance entry
        to propagate from, so unlike :meth:`trajectory` and
        :meth:`qpa_trajectory` — where a ``None`` means *this* pattern did not
        estimate one — the whole column is empty for every series. Kept as a
        ``Trajectory`` anyway so plotting and export need no second shape, and
        :meth:`Trajectory.arrays` turns it into the NaNs an errorbar ignores.

        Absent for cause outside Rietveld mode: in Le Bail the partition *is*
        the fit and in Pawley the intensities are refined, so ``refine`` leaves
        ``phase_agreement`` empty there and the trajectory is legitimately
        empty rather than zero.  Patterns missing the phase are skipped, not
        filled, for :meth:`trajectory`'s reason.
        """
        if metric not in ("r_bragg", "r_f"):
            raise ValueError(
                f"metric must be 'r_bragg' or 'r_f', got {metric!r}")
        traj = Trajectory(path=f"{metric}.{phase}", x_label=self.x_label)
        for i, (e, xv) in enumerate(zip(self.entries, self.x, strict=True)):
            row = next((r for r in e.phase_agreement if r.name == phase), None)
            if row is None:
                continue
            value = getattr(row, metric)
            # ``None`` only for a phase with no partitionable scattering power
            # at all — a real absence, so it is skipped like a missing phase
            # rather than carried as a hole in an otherwise aligned column.
            if value is None:
                continue
            traj.x.append(xv)
            traj.value.append(value)
            traj.stderr.append(None)
            traj.labels.append(e.label)
            traj.positions.append(i)
        return traj

    # -- the moment arm (WP-1329) --------------------------------------
    def magnetic_sites(self) -> list[str]:
        """Modulus dot-paths carrying a moment row, in first-seen order.

        The peer of :meth:`agreement_phases`: a site that appears on one
        pattern of the series appears here, so a chain where the moment block
        was added part-way through still names it.
        """
        out: list[str] = []
        for e in self.entries:
            for row in e.magnetic:
                if row.path not in out:
                    out.append(row.path)
        return out

    def magnetic_trajectory(self, site: str | None = None
                            ) -> "MagneticTrajectory":
        """|m| against the series axis for one magnetic site (WP-1329).

        ``site`` is the modulus dot-path or the atom label; ``None`` takes the
        only site and refuses when the structure carries more than one, for
        :meth:`SeriesEntry.moment`'s reason.

        The **esd is withheld on every unsupported point** and the point is
        still plotted, which is the shape the WP asks for: a held pattern is a
        measurement that came back "not distinguishable from none", and it is
        neither a gap in the ramp nor a zero with an error bar.  The magnitude
        and its esd both come from that pattern's own
        :class:`~rietx.report.schemas.MomentEvidence` — this method copies,
        never recomputes, and in particular never re-decides ``supported``.

        Patterns with no row for the site are skipped rather than filled, for
        :meth:`trajectory`'s reason.
        """
        sites = self.magnetic_sites()
        if site is None:
            if len(sites) > 1:
                raise ValueError(
                    f"this series carries {len(sites)} magnetic sites "
                    f"({', '.join(sites)}); name one by its path or label")
            site = sites[0] if sites else ""
        traj = MagneticTrajectory(path=site, x_label=self.x_label)
        for i, (e, xv) in enumerate(zip(self.entries, self.x, strict=True)):
            row = e.moment(site) if site else None
            if row is None:
                continue
            traj.path = row.path or site
            traj.atom, traj.ion = row.atom, row.ion
            traj.x.append(xv)
            traj.value.append(float(row.magnitude))
            measured = row.supported is not None and e.status != "diverged"
            traj.stderr.append(row.magnitude_esd
                               if measured and row.supported else None)
            traj.supported.append(bool(row.supported) and measured)
            traj.measured.append(measured)
            traj.status.append(e.status)
            traj.labels.append(e.label)
            traj.positions.append(i)
        traj.onset = locate_onset(traj)
        return traj

    #: Prefixes :meth:`resolve_trajectory` dispatches on, longest first so a
    #: future dotted sub-namespace like ``qpa.sub.`` could not be swallowed by
    #: ``qpa.``.  The trailing dot already rules out an underscore sibling like
    #: ``qpa_x.`` — it never starts with ``qpa.`` — so the ordering guards a
    #: nested namespace, not that.
    _TRAJECTORY_PREFIXES: ClassVar[tuple[str, ...]] = (
        "r_bragg.", "r_f.", "qpa.", "magnetic.")

    #: Prefixes whose trajectories carry no esd **by construction**, as
    #: distinct from one whose esd a given fit happened not to estimate
    #: (WP-1310).  An agreement index is a residual rather than a fitted
    #: parameter, so it has no covariance entry to propagate from and every
    #: ``stderr`` is ``None`` for every series — see
    #: :meth:`agreement_trajectory`.  ``to_table`` reads this to leave the
    #: ``_esd`` column out rather than emit one that is blank in every row,
    #: which is the ambiguity WP-1076 exists to prevent: a reader cannot tell
    #: a blank meaning "zero" from one meaning "never defined".
    _ESDLESS_PREFIXES: ClassVar[tuple[str, ...]] = ("r_bragg.", "r_f.")

    def resolve_trajectory(self, path: str) -> Trajectory:
        """The trajectory a *prefixed* path names, whichever kind it is.

        The one authority for turning a display path into a curve.  Before
        this, ``viz/plots.py`` and ``gui/series.py`` each carried their own
        copy of the same two-branch conditional, so a third kind meant editing
        both and a reader had to check they still agreed — the shape this
        repo's "one authority per fact" rule exists to remove.

        An unprefixed path is an ordinary parameter dot-path and goes to
        :meth:`trajectory`, which is what makes this safe to call
        unconditionally: ``instrument.zero_shift`` contains no prefix and
        cannot be mistaken for one.
        """
        for prefix in self._TRAJECTORY_PREFIXES:
            if path.startswith(prefix):
                name = path[len(prefix):]
                if prefix == "qpa.":
                    return self.qpa_trajectory(name)
                if prefix == "magnetic.":
                    # ``"magnetic."`` alone names the only site, which is what
                    # a one-sublattice structure has and what a plot of it
                    # should not have to spell out
                    return self.magnetic_trajectory(name or None)
                return self.agreement_trajectory(name,
                                                 metric=prefix.rstrip("."))
        return self.trajectory(path)

    def is_derived_path(self, path: str) -> bool:
        """Whether ``path`` names a *derived* curve rather than a refined
        parameter — a QPA or one of the McCusker agreement indices.

        The one question the two layers outside this class need to put to the
        prefix set: the GUI's forward/backward guard (a derived curve gets no
        backward chain, since ``_disagreement`` divides by a σ a residual does
        not have) and the server test that skips those rows.  They ask this
        rather than reading :attr:`_TRAJECTORY_PREFIXES`, so the tuple stays a
        private detail of the dispatch and this class stays its one authority.
        """
        return path.startswith(self._TRAJECTORY_PREFIXES)

    def agreement_phases(self) -> list[str]:
        """Phase names carrying an agreement index, in first-seen order.

        The peer of the inline QPA-phase gather in ``gui/series.py``; a series
        may report agreement for a phase that has no QPA at all, since QPA
        needs Z and a molar mass and a structure R does not.
        """
        out: list[str] = []
        for e in self.entries:
            for row in e.phase_agreement:
                if row.name not in out:
                    out.append(row.name)
        return out

    # -- tabular export ------------------------------------------------
    def to_table(self, *, paths: list[str] | None = None
                 ) -> tuple[list[str], list[list]]:
        """``(header, rows)``: one row per pattern, a column per path (+ esd
        where that kind of path has one).

        The wide form is what gets plotted or pasted into a paper; the columns
        are ``index, label, x, status, rung, rwp, gof, <path>, <path>_esd, …``.
        ``rung`` travels beside ``status`` because it is the other half of "how
        much should I trust this point": a rescued point is a good fit whose
        starting values did not come from its neighbour, and a table that hides
        that reads as a continuous trajectory.

        **A path is resolved by** :meth:`resolve_trajectory`, **the same one
        authority the plots and the GUI use** (WP-1310, issue #162), so a
        derived path — ``qpa.<phase>``, ``r_bragg.<phase>``, ``r_f.<phase>`` —
        exports its curve rather than a column of blanks.  Two consequences.
        A path **no entry in the series carries raises**, naming it: an empty
        column is indistinguishable from a measured absence, which is the
        confident-wrong-empty-state WP-1076 is about.  And a kind with no esd
        **by construction** gets no ``_esd`` column at all
        (:attr:`_ESDLESS_PREFIXES`) rather than one blank in every row; a kind
        that *has* esds keeps its column even when this series estimated none,
        because there the blank carries information.

        **The axis column takes** :attr:`x_label`, **unless that name is
        already a column**, in which case it is ``x`` (WP-1076).  ``x_label``
        defaults to ``"index"`` — it is a human label, and it is the right axis
        title for a series with no coordinate — so before that rule the default
        header carried ``index`` twice, and anything keying by name collided
        (pandas silently renames the second to ``index.1``).  The column count,
        order and meaning are unchanged, so a consumer keying by position never
        saw it either way.
        """
        paths = self.paths() if paths is None else list(paths)
        fixed = ["index", "label", "status", "rung", "rwp", "gof"]
        x_col = "x" if self.x_label in fixed else self.x_label
        header = ["index", "label", x_col, "status", "rung", "rwp", "gof"]

        # One resolver, not two (WP-1310, issue #162).  Before this, the loop
        # below called ``SeriesEntry.value``, which scans ``parameters`` only —
        # so every derived path produced a well-formed column of ``None``
        # rather than the curve or a refusal.
        resolved: dict[str, dict[int, tuple[float, float | None]]] = {}
        with_esd: list[bool] = []
        for p in paths:
            traj = self.resolve_trajectory(p)
            if not traj.positions and self.entries:
                raise ValueError(_unservable(self, p))
            resolved[p] = {pos: (v, s) for pos, v, s
                           in zip(traj.positions, traj.value, traj.stderr,
                                  strict=True)}
            # an esd-less *kind* loses the column; a kind that has esds keeps
            # it even when this particular series estimated none, because there
            # the blank means "not estimated here" and that is a fact
            with_esd.append(not p.startswith(self._ESDLESS_PREFIXES))

        for p, esd in zip(paths, with_esd, strict=True):
            header += [p, f"{p}_esd"] if esd else [p]

        rows: list[list] = []
        for i, (e, xv) in enumerate(zip(self.entries, self.x, strict=True)):
            row: list = [e.index, e.label, xv, e.status, e.rung,
                         e.statistics.rwp if e.statistics else None,
                         e.statistics.gof if e.statistics else None]
            for p, esd in zip(paths, with_esd, strict=True):
                value, stderr = resolved[p].get(i, (None, None))
                row += [value, stderr] if esd else [value]
            rows.append(row)
        return header, rows

    def write_csv(self, path, *, delimiter: str | None = None,
                  paths: list[str] | None = None) -> None:
        """Write :meth:`to_table` to CSV/TSV (delimiter inferred from suffix)."""
        import csv
        from pathlib import Path as _Path

        p = _Path(path)
        if delimiter is None:
            delimiter = "\t" if p.suffix.lower() in (".tsv", ".tab") else ","
        header, rows = self.to_table(paths=paths)
        with p.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh, delimiter=delimiter)
            w.writerow(header)
            for row in rows:
                w.writerow(["" if v is None else v for v in row])

    def plot(self, paths: list[str] | str, *, path=None, **kw):
        """Plot one or more trajectories against the series axis."""
        from ..viz.plots import plot_trajectory

        return plot_trajectory(self, paths, path=path, **kw)

    def __str__(self) -> str:
        return self.summary()

    def summary(self, *, max_entries: int = 5,
                deliverable: str | None = None) -> str:
        """The series termination view (WP-1302): the trajectory table, the
        ``SEQUENTIAL_*`` rows, first and last ``max_entries`` with the count.

        A per-entry ``RefinementResult.__str__`` is not repeated here — a
        60-pattern series printing 60 nested reports is not a summary — so
        this reads each entry's own :attr:`SeriesEntry.status`/``rwp`` and
        leaves the full termination view to ``result.entries[i]`` (which is
        not a ``RefinementResult`` and carries no ``__str__`` of its own for
        exactly that reason: it is the row, not the fit).

        ``deliverable="series"`` adds §4b's fourth deliverable — a parameter
        as a function of the series variable — as its deciding rows, printed
        **after** the trajectory: the table is the answer, and these are what
        would have to be wrong for it to be wrong (WP-1305).  The other three
        purposes are decided on one pattern's own fit and are refused here by
        name.
        """
        n = len(self.entries)
        lines = [f"SeriesResult: {n} pattern(s), {self.mode}, "
                 f"direction={self.direction}"]
        # the same renderer RefinementResult.__str__ calls (schemas/results.py)
        # — one diagnostics-line format for the whole package, never a second
        # copy that a future change to it would not know to keep in step with
        lines += _diagnostic_lines(self.diagnostics)
        lines.append(f"  trajectory ({self.x_label}):")
        shown = (list(range(n)) if n <= 2 * max_entries else
                [*range(max_entries), None, *range(n - max_entries, n)])
        for i in shown:
            if i is None:
                lines.append(f"    … {n - 2 * max_entries} more …")
                continue
            e = self.entries[i]
            rwp = f"{e.statistics.rwp:.4f}" if e.statistics else "n/a"
            lines.append(f"    [{i + 1}/{n}] {e.label} x={self.x[i]:g} "
                         f"{e.status} Rwp={rwp}")
        if deliverable is not None:
            lines += self._deliverable_lines(deliverable)
        return "\n".join(lines)

    def _deliverable_lines(self, deliverable: str) -> list[str]:
        """§4b's fourth deliverable: the rows that decide a trajectory.

        Four of them are diagnostics this class already carries, read as
        stopping criteria rather than as messages; the last two are the ones
        **no diagnostic can supply**, because nothing in a pattern file records
        them — what pins the 2θ scale, and which of precision and accuracy the
        esds are about.  They print as an instruction to state them, since a
        blank there is exactly how an unanchored absolute gets quoted.
        """
        if deliverable in DELIVERABLES and deliverable != "series":
            raise ValueError(
                f"{deliverable!r} is decided on one pattern's own fit, not on "
                f"a series: print it from that pattern's "
                f"Refinement.summary(deliverable={deliverable!r}) — the series' "
                f"own deliverable is 'series'")
        if deliverable != "series":
            raise ValueError(
                f"unknown deliverable {deliverable!r}; one of "
                f"{', '.join(repr(d) for d in DELIVERABLES)}")

        by_code: dict[str, list[Diagnostic]] = {}
        for d in self.diagnostics:
            by_code.setdefault(d.code, []).append(d)
        lines = ["  deliverable: series (a parameter against the series axis)"]

        depend = by_code.get("SEQUENTIAL_PATH_DEPENDENT", [])
        # `direction` is what was *asked for*; the comparison exists only when
        # the reverse chain actually completed.  A cancel takes the backward
        # pass out (forward-cancelled: it is never started, so `backward` stays
        # None despite direction="both"; backward-cancelled: the pass is
        # recorded but `_path_dependence_diagnostics` is not run) — and an
        # empty `depend` then reads as "checked, nothing disagreed", which is
        # the confident wrong answer this row exists to avoid.
        interrupted = any(d.code == "SEQUENTIAL_CANCELLED"
                          for d in self.diagnostics)
        # WP-1333's record of the comparison, which is the authority where it
        # exists: ``warning`` is "did not run" and says why (a backward pass
        # that *raised* is not a cancel, and the row must not call it one),
        # ``info`` is "ran on less than the series".  A series stored before
        # schema 0.25 carries neither, and the cancel test above still speaks.
        incomplete = by_code.get("SEQUENTIAL_PATH_CHECK_INCOMPLETE", [])
        not_run = [d for d in incomplete if d.level == "warning"]
        partial = [d for d in incomplete if d.level != "warning"]
        if self.direction == "both" and self.backward is not None \
                and not interrupted and not not_run:
            paths = ", ".join(p for d in depend for p in d.where) or "none"
            lines.append(f"    ordering artefact: measured both ways, "
                         f"{len(depend)} parameter(s) disagree ({paths})")
            for d in partial:
                lines.append(f"      but {d.message}")
        elif self.direction == "both":
            why = (not_run[0].message if not_run else
                   "direction='both' was asked for but the chain was "
                   "cancelled before the two directions could be compared")
            lines.append(f"    ordering artefact: NOT measured — {why}, so an "
                         f"empty disagreement list is silence, not agreement")
        else:
            lines.append(f"    ordering artefact: NOT measured — this chain ran "
                         f"{self.direction} only, and direction='both' is the "
                         f"one check that separates a trajectory from the order "
                         f"it was refined in")

        persistent = by_code.get("SEQUENTIAL_PERSISTENT_FINDING", [])
        lines.append(f"    persistent findings: {len(persistent)}")
        for d in persistent[:5]:
            lines.append(f"      {d.message}")

        # a width that grew while the fit got worse (WP-1465): the one reading
        # of a trajectory that says a phase stood in for something missing
        growth = by_code.get("SEQUENTIAL_WIDTH_GROWTH", [])
        # a series stamped before thresholds 1.9 never ran the check, and its
        # zero would read as "checked, none" — the row the ordering artefact
        # above already refuses to print for a comparison that did not run
        stamped = (None if self.provenance is None
                   else self.provenance.report_thresholds_version)
        try:
            predates = (stamped is not None and tuple(
                int(p) for p in stamped.split(".")[:2]) < (1, 9))
        except ValueError:
            predates = False
        if predates and not growth:
            lines.append(f"    widths grown with a worsening fit: NOT measured "
                         f"— this series was stamped at thresholds {stamped}, "
                         f"before SEQUENTIAL_WIDTH_GROWTH existed (1.9)")
        else:
            lines.append(f"    widths grown with a worsening fit: {len(growth)}")
        for d in growth[:5]:
            lines.append(f"      {d.message}")

        steps = by_code.get("SEQUENTIAL_DISCONTINUITY", [])
        lines.append(f"    steps: {len(steps)}")
        for d in steps:
            where = ", ".join(d.where)
            # `value` absent covers two cases and the row must not pick one:
            # the check was never asked for, and the check ran and the cold
            # pair did not determine this parameter (the diagnostic's own
            # message says which).  Naming only the first tells a caller who
            # already ran it to run it again.
            verdict = ("not verified — pass fit(verify_discontinuities=True), "
                       "or, if it was passed, the cold pair did not determine "
                       "this parameter (the message says which)"
                       if d.value is None else
                       f"an independent cold pair reproduces {d.value:.2f}× of it")
            lines.append(f"      {where}: {verdict}")

        held = sorted({p for e in self.entries for d in e.diagnostics
                       if d.code == "PHASE_UNCONSTRAINED" for p in d.where})
        n_held = sum(any(d.code == "PHASE_UNCONSTRAINED" for d in e.diagnostics)
                     for e in self.entries)
        if held:
            lines.append(f"    phase support: held in {n_held} of "
                         f"{len(self.entries)} patterns ({', '.join(held[:4])}"
                         f"{' …' if len(held) > 4 else ''}) — a held value is "
                         f"the one you handed in, not a measurement, so it is "
                         f"not a point on a trajectory either")
        else:
            lines.append("    phase support: every phase carried the data in "
                         "every pattern (no PHASE_UNCONSTRAINED)")

        lines.append("    2θ-scale anchor: state it — an internal standard, a "
                     "calibrant, or none. Nothing in this result knows")
        lines.append("    precision vs accuracy: the esds are precision on the "
                     "*shape*; without an anchor there is no accuracy claim on "
                     "the absolute")
        lines.append("    good enough: when every number you quote names the "
                     "one thing that would have to be wrong for it to be wrong, "
                     "and that thing has been checked")
        return lines
