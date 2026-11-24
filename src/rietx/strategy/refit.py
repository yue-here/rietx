"""The re-fit of a converged model: one stage in place of the plan (WP-2224).

A staged plan gets a cold model into the right basin, and each stage
recompiles the peak windows a solve holds frozen.  A model a fit of the same
pattern has already converged is in the basin, and its windows compile at the
answer, so re-walking the stages buys nothing there.  Two callers take that
step: a series' warm pattern (WP-0505, since v0.5) and a second
:meth:`~rietx.refine.Refinement.fit` on a converged model (WP-2224).  Both
collapse the plan here, so the two cannot drift apart.
"""

from __future__ import annotations

from dataclasses import replace

from .staged import RefinementPlan, Stage

#: What ``refit=`` accepts, on :meth:`~rietx.refine.Refinement.fit` and on
#: :meth:`~rietx.sequential.SequentialRefinement.fit` alike, as data rather than
#: as literals inside either.  A caller that has to *offer* the choices (the
#: GUI's series panel, WP-1016) needs the same list this validates against, and
#: a menu that could disagree with the validator would be a second authority —
#: the ``capabilities()`` rule at a smaller scale.
REFIT_MODES = ("single", "stages")

#: The one stage a re-fit runs, by name.  The GUI's status bar reads a run
#: starting it as a one-stage re-fit (WP-2227), so the name is spelled once.
WARM_REFIT_STAGE = "warm_refit"


def _collapse(plan: RefinementPlan) -> RefinementPlan:
    """One stage freeing everything the plan would free, in one solve.

    Never for a plan that fixes (``Stage.turn_off``, WP-2208): one stage
    frees then fixes, and cannot replay a fix that a later stage undid, so
    :meth:`~rietx.sequential.SequentialRefinement.fit` and
    :meth:`~rietx.refine.Refinement.fit` refit such a plan stage by stage.

    The default ``refit="single"`` strategy: with a converged neighbour as the
    starting point the staged turn-on order has already done its job of keeping
    early stages well conditioned, so re-walking it per pattern is mostly
    overhead.  Measured on the round-robin sample-1 series: 904 iterations
    against 1623 for the staged refit and 2863 unchained, for the same weight
    fractions to three decimals.

    The warm refit carries no ``seed``.  ``seed_floored`` lifts every freed
    row sitting exactly on its floor, and a warm start's rows on a floor are
    the neighbour's converged answers.  A stage seed says where a cold solve
    starts.  On a warm start it lifts that answer off its floor before the
    solve begins.  Measured on the
    four-pattern LaB₆ ramp of ``tests/test_sequential.py`` under
    ``mccusker_structural``, the plan's 0.3 lifted pattern 1's converged
    ``instrument.profile.y`` from 0 to 0.3° and ``phases.0.extinction`` from
    0 to 0.3.  That refit ended at χ²_red 1.05828 in 15 iterations, against
    1.05145 in 11 with no seed.  Patterns 2 and 3 lifted extinction alone and
    ended at the same χ² either way.

    ``strain_seed`` does carry over, as the maximum across the plan's
    stages.  ``seed_stephens`` touches only a block that is still all zero,
    and such a block cannot move without it, warm or cold.
    """
    turn_on: list[str] = []
    for stage in plan.stages:
        for glob in stage.turn_on:
            if glob not in turn_on:
                turn_on.append(glob)
    # the cap below is the plan's largest, which a fixed count would run in full,
    # so one stage's stop keeps the collapsed stage stopping
    stops = [s.lebail_tol for s in plan.stages if s.lebail_tol > 0.0]
    # the objective and windows the plan's answer converged under are its last
    # stage's, which the closing stage copies for the same reason
    # (``RefinementPlan.closing_stage``): a restraint weight, an ftol or a
    # window slack set there would otherwise fall back to the default
    last = plan.stages[-1] if plan.stages else Stage(WARM_REFIT_STAGE, [])
    return RefinementPlan(
        stages=[Stage(WARM_REFIT_STAGE, turn_on,
                      max_iter=max((s.max_iter for s in plan.stages), default=100),
                      ftol=last.ftol,
                      restraint_weight_scale=last.restraint_weight_scale,
                      window_slack_deg=last.window_slack_deg,
                      lebail_cycles=max((s.lebail_cycles for s in plan.stages),
                                        default=Stage.lebail_cycles),
                      lebail_tol=min(stops, default=0.0 if plan.stages
                                     else Stage.lebail_tol),
                      seed=0.0,
                      strain_seed=max((s.strain_seed for s in plan.stages),
                                      default=0.0))],
        correlation_guard=plan.correlation_guard,
        # inert, the lone warm stage being the last declared one, which
        # converges whether or not a closing stage follows (WP-2045: at 1e-6
        # the hostile series' cpd-1b warm stage stopped on its frozen windows'
        # plateau at axial_sl 555); carried anyway, because this is the
        # compressed plan rather than a different protocol (WP-1123)
        intermediate_ftol=plan.intermediate_ftol,
        # and the closing stage itself, the protocol's like the two below
        # (WP-2002, the sixth round's Q1 and Q2)
        closing_window_tol=plan.closing_window_tol,
        # the alternation is the protocol's, not a stage's: a collapsed warm
        # refit under mode="lebail" would otherwise run one pass (WP-1323)
        lebail_passes=plan.lebail_passes,
        # the absent-phase hold is the protocol's too: a collapsed warm refit
        # would otherwise hold at the default a phase the caller set free
        # (WP-2002, B1)
        phase_support_sigma=plan.phase_support_sigma)


def _unseeded(plan: RefinementPlan) -> RefinementPlan:
    """``plan`` with no stage ``seed``, for a solve that starts warm.

    A stage seed says where a cold solve starts.  On a warm start a row on its
    floor is the neighbour's converged answer, and seeding it lifts that
    answer before the solve begins (:func:`_collapse` has the measurement).
    ``strain_seed`` stays, for the reason it stays there.  ``plan`` itself
    comes back when no stage seeds.
    """
    if not any(s.seed for s in plan.stages):
        return plan
    return replace(plan, stages=[replace(s, seed=0.0) for s in plan.stages])
