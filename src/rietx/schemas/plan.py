"""The serializable mirror of a staged refinement plan — written once.

:class:`strategy.staged.Stage` and :class:`strategy.staged.RefinementPlan` are
dataclasses, constructed positionally (``Stage("cell", ["phases.*.cell.*"])``)
across the plan presets, the tests and the examples; pydantic models have no
positional constructor, so a *mirror* — not a conversion — is what crosses a
JSON boundary (a history node, an agent request, a project file).

Until v1.0 there were **two** mirrors, and the duplication was not merely
redundant — one of them lost data.  ``schemas/history.py`` carried
``from_stage``/``from_plan`` but no ``strain_seed``, reading
``getattr(stage, "seed", 0.0)`` and nothing else, so a Stephens stage's
``strain_seed`` silently round-tripped to **0.0** through the history tree
(un-caught because no Stephens stage had been checked out and re-run).
``agent.py`` carried ``strain_seed`` and the schema descriptions but had no
``from_*`` direction at all.  Both now re-export from here, and
``tests/test_schemas.py`` pins :class:`StageSpec`'s fields against
``dataclasses.fields(Stage)`` so the next field added to ``Stage`` cannot
silently fail to serialize.

``from_stage`` therefore reads every field by direct attribute access: a
``getattr`` default is exactly how the ``strain_seed`` loss was spelled.
"""

from __future__ import annotations

import math
import numbers
from typing import Any

from pydantic import Field, field_validator, model_validator

from .common import Base

#: What :attr:`PlanSpec.intermediate_ftol` and
#: ``strategy.staged.RefinementPlan.intermediate_ftol`` both default to.
#:
#: **Here, at the lower layer, so the two mirrors quote one literal.**
#: ``strategy.staged`` imports this module and cannot be imported back from it
#: (every crossing in that direction is deferred inside a function), so a
#: constant the pydantic field needs at class-definition time cannot live
#: beside the dataclass.  ``strategy.staged`` re-exports it, which is where a
#: reader looking for plan policy will look; ``tests/test_schemas.py`` pins the
#: two names to one object.
#:
#: An expensive stage's evaluations are almost all *tail* — undamped
#: Gauss-Newton walking a near-degenerate direction (zero ↔ sample displacement
#: ↔ the low-order background terms) at ≈0.93 per iteration, the trust region
#: never binding — and 99.99 % of the stage's cost decrease is banked by
#: evaluation 55 of 93.  An intermediate stage's job is to seed its successor,
#: and the plan is cumulative, so the digits it stops short of are refined
#: again by every later stage: the *last* stage inherits the ridge walk once
#: (cpd-1a ``biso`` 47 → 49 evaluations) instead of every stage polishing it.
#: ``strategy.staged.RefinementPlan.stage_ftols`` is the rule that applies it.
#:
#: 1e-6 costs 1.2-1.6× fewer whole-plan evaluations across the WP-1111 harness
#: cases, for every non-degenerate parameter within 0.03 esd of the
#: fully-converged plan and QPA fractions within 0.0014 wt % (WP-1113 priced
#: it, WP-1123 made it the default and re-measured).  Both figures are
#: properties of the tree as much as of the schedule — 1113 measured 1.5-1.7×
#: and 0.02 esd before a Jacobian column changed underneath — so re-measure
#: rather than inherit them.  **The bound is for one fit**: in a warm *chain*
#: each pattern seeds the next, and the effect there is unbounded and not even
#: fixed in sign.  Looser is a real choice and not a silly one — 1e-5 and 1e-4
#: buy 1.9-2.2× at 0.01-0.2 esd — which is why this is a number a plan carries
#: and not a mode with two positions.
INTERMEDIATE_FTOL = 1e-6

#: |ρ| above which a pair of free parameters is reported as highly correlated
#: (``HIGH_CORRELATION``).  The plan, its dataclass and ``run_stage`` each held
#: their own literal 0.98 until WP-2001.
CORRELATION_GUARD = 0.98

#: The significance a phase must reach to count as one the data can see, in σ,
#: and what :attr:`PlanSpec.phase_support_sigma` and
#: ``strategy.staged.RefinementPlan.phase_support_sigma`` default to.
#: It is a significance, not a height: the phase's scale must sit this many of
#: its own esds from zero, the esd taken against the counting noise
#: (WP-1523).  Three is :data:`~rietx.indexing.workflow.ABSENT_SIGMA`'s value
#: and meaning, the multiple of its propagated σ a line's net intensity must
#: reach to count as present, so a phase and a line are judged present on one
#: footing.  :meth:`~rietx.model.forward.CompiledModel.phase_support` is the
#: cheap screen against it, and ``refine._answer_significance`` the full test
#: where the screen passes.  Until WP-1523 this was 1.0 against one point's
#: height, and a scale fitted to pure noise lifted that point past it.
#:
#: **A plan carries it since WP-2002 (B1, ruled 2026-10-19)**, so a caller can
#: set another threshold or switch the significance test off (``None``; a
#: phase with no line in range is held either way, WP-1958).  It lives here,
#: beside the mirror, for :data:`INTERMEDIATE_FTOL`'s reason: the pydantic
#: field needs it at class definition.  ``model.forward`` re-exports it, where
#: the screen is.
PHASE_SUPPORT_SIGMA = 3.0


def check_phase_support_sigma(value: Any) -> float | None:
    """``value`` as a plan's ``phase_support_sigma``, or ``ValueError``.

    One sentence for every surface that takes it: :class:`PlanSpec`'s
    validator, the runners reading a ``RefinementPlan`` (a dataclass, which
    validates nothing), ``Refinement.run_stage``'s keyword and the ``.rxt``
    parser.  ``None`` is a value here, the hold switched off.  Zero or a
    negative would switch it off too, silently, an infinity would hold every
    phase, and a NaN compares false both ways, so all four are refused.
    """
    if value is None:
        return None
    if (isinstance(value, bool) or not isinstance(value, numbers.Real)
            or not math.isfinite(value) or value <= 0.0):
        raise ValueError(
            f"phase_support_sigma is the number of esds a phase's scale must "
            f"sit from zero to count as seen, a positive finite number, or "
            f"None to switch the significance test off (a phase with no "
            f"line in range is still held); got {value!r}")
    return float(value)


#: The area each peak's window may drop in a plan's closing stage, and what
#: :attr:`PlanSpec.closing_window_tol` and
#: ``strategy.staged.RefinementPlan.closing_window_tol`` default to (WP-2002,
#: the sixth round's Q1 and Q2, ruled 2026-10-21).  Here for
#: :data:`INTERMEDIATE_FTOL`'s reason: both mirrors quote one literal.
#:
#: **What the closing stage is.**  Every stage freezes its peak windows, its
#: reflection list and its axial-divergence nodes at the values it starts from
#: (root CLAUDE.md § Invariants).  So a plan's last stage computes on a model
#: frozen wherever the stages before it stopped.  Two errors follow.  The
#: windows drop ``forward.WINDOW_AREA_TOL`` (2 %) of each peak's area, more
#: once a peak widens inside a stage, and the answers carry it: up to 0.97 esd
#: on lab data (cpd-1a's zincite scale, the fluorapatite Lorentzian size), the
#: background 2 to 5 esd.  And two starts that stop the early stages in
#: different places reach different answers: Biso started at 0.5 and at
#: 1.5 Å² put cpd-1a's sample displacement 0.75 esd apart.  The closing stage
#: recompiles at the answer with windows dropping this fraction and solves
#: once more with every glob the plan freed.  Measured on 2026-10-21 against
#: the 5e-5 fixed point polished from the same start (macOS arm64, ``[dev]``):
#: within 0.008, 0.018 and 0.019 plain esd on the fluorapatite, cpd-1a and
#: 11-BM NAC, and two Biso starts within 0.000, 0.070 and 0.000 esd.  Through the shipped code
#: the whole fit takes 1.05-1.19× (LaB6), 2.03-2.05× (FAP), 1.37-1.38×
#: (cpd-1a) and 1.12-1.26× (NAC) its time without the closing stage, the last
#: declared stage then stopping at ``intermediate_ftol``; converging that stage
#: again costs 1.04-1.07× the evaluations (WP-2045).  SRM 660c LaB6 lands
#: in its mirrored axial minimum from either start under every setting
#: (WP-2012).
#:
#: **Practice.**  BGMN ends every refinement ladder with a closing run, all
#: free and restarted from the previous answer (Doebelin & Kleeberg 2015,
#: *J. Appl. Cryst.* **48**, 1573, §2).  RIETAN-FP's automatic mode ends with
#: everything refining together, its windows moving at every evaluation.
#: MAUD's wizard has no final cycle.  1e-3 drops less than TOPAS (0.001 of the
#: strongest line's height, 2 % of a Lorentzian), MAUD (±15 FWHM, 2.1 %),
#: RIETAN-FP and FullProf, and more than GSAS-II (0.5 %), BGMN and
#: EasyDiffraction, which compute the whole peak
#: (``docs/practice.md``).  At 1e-3 the window error is under
#: 0.1σ at every point on four families, and the closing answer lies within
#: 0.1 plain esd of the converged tails' on three of them
#: (``tests/test_window_domain.py``).  SRM 660c LaB6 misses by 0.9 esd on U,
#: from the Gaussian-variance clamp its high-angle reflections sit on, which
#: moves U at any window (WP-1467).
CLOSING_WINDOW_TOL = 1e-3


def check_closing_window_tol(value: Any) -> float | None:
    """``value`` as a closing stage's window area fraction, or ``None`` for no closing stage.

    The one check behind :attr:`PlanSpec.closing_window_tol`, the dataclass
    plan's field (read where the runner reads it, since a dataclass validates
    nothing) and the ``.rxt`` parser.  A fraction of a peak's area lies
    strictly between 0 and 1: zero would ask for an infinite window, one for
    none, and a NaN compares false both ways.
    """
    if value is None:
        return None
    if (isinstance(value, bool) or not isinstance(value, numbers.Real)
            or not math.isfinite(value) or not 0.0 < value < 1.0):
        raise ValueError(
            f"closing_window_tol is the fraction of each peak's area the "
            f"closing stage's windows may drop, a number strictly between 0 "
            f"and 1, or None for no closing stage; got {value!r}")
    return float(value)


class StageSpec(Base):
    """One stage of a staged plan as data that round-trips through JSON, mirroring ``Stage``."""

    name: str
    turn_on: list[str] = Field(
        default_factory=list,
        description="dot-path globs freed this stage, e.g. 'phases.*.cell.*'")
    max_iter: int = Field(100, description=(
        "approximate solver iterations for this stage; both drivers cap "
        "evaluations rather than iterations, so it is scaled by the "
        "measured worst-case rejection rate (NFEV_PER_ITERATION)"))
    ftol: float | None = Field(None, gt=0.0, description=(
        "this stage's own relative cost-decrease termination tolerance, "
        "overriding the plan's schedule; null = take it from the plan "
        "(intermediate_ftol for every declared stage but the last, the "
        "solver's 1e-9 for the last declared stage and for the closing stage "
        "when the plan has one)"))
    lebail_cycles: int = 3
    seed: float = Field(0.0, description=(
        "start at this value every parameter this stage frees that sits "
        "exactly on a lower bound of 0 or above (e.g. surface roughness, "
        "whose correction is the identity at 0)"))
    strain_seed: float = Field(0.0, description=(
        "microstrain (ppm) to seed an all-zero Stephens block onto the "
        "isotropic ray (exploding-gradient pathology — the opposite fix)"))
    restraint_weight_scale: float = Field(1.0, ge=0.0, description=(
        "c_w of McCusker eq (7), S = S_y + c_w·S_G: this stage's weight on the "
        "geometric restraints against the diffraction data; high early, "
        "reduced as the model improves.  1.0 = no scaling"))
    window_slack_deg: float | None = Field(None, ge=0.0, description=(
        "absolute window capture slack in deg 2-theta this stage compiles "
        "with, replacing the default WINDOW_MIN_DEG — declared by fits whose "
        "start may sit far from the data (the indexing Le Bail validation); "
        "null = the default"))

    @model_validator(mode="before")
    @classmethod
    def _accept_the_dataclass(cls, value: Any) -> Any:
        """A ``Stage`` read as a ``StageSpec`` — see :meth:`PlanSpec._accept_the_dataclass`."""
        from ..strategy.staged import Stage

        return cls.from_stage(value).model_dump() if isinstance(value, Stage) else value

    @classmethod
    def from_stage(cls, stage: Any) -> "StageSpec":
        return cls(name=stage.name, turn_on=list(stage.turn_on),
                   max_iter=stage.max_iter, ftol=stage.ftol,
                   lebail_cycles=stage.lebail_cycles,
                   seed=stage.seed, strain_seed=stage.strain_seed,
                   restraint_weight_scale=stage.restraint_weight_scale,
                   window_slack_deg=stage.window_slack_deg)

    def to_stage(self) -> Any:
        from ..strategy.staged import Stage

        return Stage(name=self.name, turn_on=list(self.turn_on),
                     max_iter=self.max_iter, ftol=self.ftol,
                     lebail_cycles=self.lebail_cycles,
                     seed=self.seed, strain_seed=self.strain_seed,
                     restraint_weight_scale=self.restraint_weight_scale,
                     window_slack_deg=self.window_slack_deg)


class PlanSpec(Base):
    """A staged plan as data that round-trips through JSON, mirroring ``RefinementPlan``.

    ``stages`` is deliberately *not* ``min_length=1`` here, because this schema
    also has to read history trees written by earlier versions and a header is
    persisted before the first stage runs.  The agent surface, which validates
    a request a caller is about to spend minutes on, rejects an empty stage
    list in ``agent._RequestBase._known_plan`` instead.
    """

    stages: list[StageSpec] = Field(default_factory=list)
    correlation_guard: float = CORRELATION_GUARD
    intermediate_ftol: float | None = Field(
        INTERMEDIATE_FTOL, gt=0.0, description=(
            "the tolerance every declared stage but the last stops at, unless it "
            "declares its own ftol; null = the solver default (1e-9) "
            "everywhere, i.e. the fully-converged schedule.  1e-6 is "
            "1.2-1.6x fewer whole-plan evaluations for answers within "
            "0.03 esd on a single fit (WP-1113/1123)"))
    lebail_passes: int = Field(
        1, ge=1, description=(
            "the cap on Le Bail passes: under mode='lebail' the plan is run "
            "again from where it ended, up to this many times, stopping at the "
            "first pass that does not lower Rwp and keeping the best.  1 is a "
            "single run; the field does nothing in any other mode (WP-1323)"))
    phase_support_sigma: float | None = Field(
        PHASE_SUPPORT_SIGMA, description=(
            "the absent-phase hold's threshold, in esds: at each stage start a "
            "phase whose scale sits fewer than this many esds from zero has its "
            "cell, positions, widths and displacements held for the stage, its "
            "scale left free; at the stage's answer a held phase that now passes "
            "is released and one that fell under is restored and held, with one "
            "more solve.  The default cell window follows the same number.  "
            "null = no hold, no release, no restore and no window "
            "(PHASE_UNCONSTRAINED still reports a phase under the default 3); "
            "WP-1301/1523, a caller's option since WP-2002 B1.  A phase with no "
            "reflection in the fitted range is held whole, scale included, at "
            "any value here, null too (WP-1958)"))

    closing_window_tol: float | None = Field(
        CLOSING_WINDOW_TOL, description=(
            "after the last declared stage, one more stage recompiles at the "
            "answer with peak windows dropping this fraction of each peak's "
            "area and solves with every glob the plan freed.  Earlier stages "
            "drop 2 %, which moves lab answers by up to an esd; 1e-3 meets "
            "0.1 esd on three of four families at 1.2-2.3x the fit time.  Any "
            "value under 2 % keeps the closing stage's finer axial-divergence "
            "sampling.  null = no closing stage, today's answers bit for bit "
            "(WP-2002)"))

    @field_validator("phase_support_sigma")
    @classmethod
    def _a_threshold_or_none(cls, value: Any) -> float | None:
        return check_phase_support_sigma(value)

    @field_validator("closing_window_tol")
    @classmethod
    def _a_fraction_or_none(cls, value: Any) -> float | None:
        return check_closing_window_tol(value)

    @model_validator(mode="before")
    @classmethod
    def _accept_the_dataclass(cls, value: Any) -> Any:
        """A ``RefinementPlan`` read as a ``PlanSpec`` (WP-1110 item 15).

        The mirror is written once — this module — and it is *crossed* in two
        places, this one inbound and ``strategy.staged.resolve_plan`` outbound.
        Before WP-1110 it was crossed nowhere, so a caller had to know which of
        two same-shaped types each surface wanted: two agents driving the
        trigger dataset took a preset out of ``PLAN_PRESETS``, were refused by
        the JSON request surface of the day, and rebuilt the plan field by
        field.  Here rather than at any one boundary because every JSON
        boundary in the package asks the same question — a ``TreeHeader``, a
        ``ProjectDoc``, whatever a caller validates — and one of them answering
        differently is the duplication ``schemas/plan.py`` exists to end.  (The
        request surface that provoked it went in WP-1303; the other boundaries
        are why the rule outlived it.)

        By ``isinstance`` on the real class, never by duck-typing on
        ``.stages``: the two types share **every** field name, which is what
        makes one silently usable where the other is meant.  Measured on this
        tree — ``fit(plan=PlanSpec(...))`` ran to a bit-identical answer through
        the annotation ``RefinementPlan | str``, so a structural test would have
        certified an accident.  The import is local; ``strategy.staged`` imports
        this module.
        """
        from ..strategy.staged import RefinementPlan

        return cls.from_plan(value).model_dump() if isinstance(value, RefinementPlan) else value

    @classmethod
    def from_plan(cls, plan: Any) -> "PlanSpec":
        return cls(stages=[StageSpec.from_stage(s) for s in plan.stages],
                   correlation_guard=plan.correlation_guard,
                   intermediate_ftol=plan.intermediate_ftol,
                   lebail_passes=plan.lebail_passes,
                   phase_support_sigma=plan.phase_support_sigma,
                   closing_window_tol=plan.closing_window_tol)

    def to_plan(self) -> Any:
        from ..strategy.staged import RefinementPlan

        return RefinementPlan(stages=[s.to_stage() for s in self.stages],
                              correlation_guard=self.correlation_guard,
                              intermediate_ftol=self.intermediate_ftol,
                              lebail_passes=self.lebail_passes,
                              phase_support_sigma=self.phase_support_sigma,
                              closing_window_tol=self.closing_window_tol)

    def preset_name(self) -> str | None:
        """The registered preset this plan equals, or ``None`` if it was edited.

        **Derived, never stored.**  A project records the *expanded* plan (that
        is what will run, verbatim), so "which preset was this?" has no field to
        read — and adding one would be a second authority that can disagree with
        the stages beside it.  Two consumers already ask: the GUI's plan editor,
        which labels the menu, and the text document, which prints
        ``plan mccusker_default`` instead of eight stage lines.
        """
        from ..strategy.staged import PLAN_PRESETS

        for name, build in PLAN_PRESETS.items():
            if PlanSpec.from_plan(build()) == self:
                return name
        return None
