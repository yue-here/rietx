"""From a typed suggestion to the verbs that carry it out (WP-1012).

:mod:`.layer2` says *what* is worth doing, in a closed vocabulary pinned by
``THRESHOLDS_VERSION``.  This module says *how* — and the two halves are
deliberately separate files, because they version differently: the vocabulary is
a contract an agent reads, while the mapping onto verbs is a property of what
this build can actually do and changes when a verb *arrives* (indexing is the
live example: ``reindex_or_recheck_cell`` has been emitted since v0.2 with
nothing behind it).

Three rules.

**An applicable action is one stage.**  :func:`stage_for` returns a
:class:`~rietx.schemas.plan.StageSpec` and executes nothing, so applying a
suggestion travels the path a "Run this stage" button already travels — the same
``run_stage``, the same refusal while a run is in flight (frozen-per-stage
discreteness), the same event stream, the same one history node.  That is also
what makes *undo* a ``checkout`` of the previous head rather than an inverse verb
nobody wrote.

**The action's own ``parameter_paths`` are the globs.**  :data:`RECIPES` declares
only *how* a kind can be carried out, never *which* paths: Layer 2 wrote them,
sometimes with a phase index in them (texture), and a second copy here could
disagree with the rationale printed beside it.

**Not every kind is a button, and each non-button says why in its own terms.**
Four of the eighteen are advice, and none of them for want of effort:

* ``add_impurity_phase`` — nothing is named yet, so there is nothing to free.
  Identifying the phase is the work, and adding it is an ``edit_model``.
* ``collect_better_data`` — there is no verb; the fit is saying the pattern is
  the limit.
* ``increase_background_flexibility`` / ``decrease_background_flexibility`` —
  these change what the background can *absorb* rather than which parameters
  move.  A Chebyshev term, a knot spacing or a ``lambda_smooth`` is a property
  of the model, not a member of ``turn_on``, so there is no glob a stage could
  carry and the edit is an ``edit_model`` move.  What changed in WP-1055 is the
  *evidence*, not the kind: a more flexible background lowers Rwp while biasing
  ADPs up and scales (hence QPA fractions) down, and until then the statistic
  that detects it — the block projection R² of
  :func:`~rietx.optimize.statistics.background_absorption` — reached a caller
  only as the ``BACKGROUND_ABSORPTION`` diagnostic, so these notes could name
  an edit whose effect the report could not show.  It is now
  ``FitReport.background``, which is also what finally gave both kinds an
  emitter (:func:`~rietx.report.layer2.background_actions`); before that they
  were advice with nothing to travel on.

and one — ``reindex_or_recheck_cell`` — is gated on a flag a client can watch:
``capabilities().features["indexing"]``.  The design held up half-way: nothing
here needed editing when the engine landed (WP-1024), but the flag it watches
was mis-derived (``hasattr(rx, "index")`` against an export named
``index_pattern``), so the refusal outlived the engine until WP-1037 fixed the
name.  The gate still runs off the flag a caller passes, so a client talking to
a build that reports no engine still gets the refusal with its reason.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Mapping
from dataclasses import dataclass
from typing import get_args

from ..schemas.plan import StageSpec

# ``How`` is defined beside ``ActionKind`` (WP-1106) so ``SuggestedAction`` can
# carry it typed; the kind→How mapping stays here, in ``RECIPES``.
from .schemas import ActionKind, How, SuggestedAction


@dataclass(frozen=True)
class Recipe:
    """How one :data:`~rietx.report.schemas.ActionKind` is carried out.

    ``note`` is empty exactly when ``how == "stage"``: there the suggestion's own
    rationale is the explanation and a second sentence here would be noise.  For
    everything else the note *is* the deliverable — it is what a panel renders in
    place of a button, and it is pinned non-empty by test.
    """

    kind: ActionKind
    how: How
    note: str = ""


def _stage(kind: ActionKind) -> Recipe:
    return Recipe(kind=kind, how="stage")


#: Every member of the closed ``ActionKind`` vocabulary, classified.  A missing
#: member is a test failure, not a ``KeyError`` at the moment a user clicks:
#: ``ActionKind`` is a ``Literal`` and this table is checked against
#: ``get_args`` of it, the same device the capabilities arms use.
RECIPES: dict[ActionKind, Recipe] = {
    # -- one stage over the paths the suggestion names
    "refine_zero_shift": _stage("refine_zero_shift"),
    "refine_sample_displacement": _stage("refine_sample_displacement"),
    "refine_sample_transparency": _stage("refine_sample_transparency"),
    "refine_capillary_offset_along_beam":
        _stage("refine_capillary_offset_along_beam"),
    "refine_capillary_offset_across_beam":
        _stage("refine_capillary_offset_across_beam"),
    "refine_cell": _stage("refine_cell"),
    "refine_profile_widths": _stage("refine_profile_widths"),
    "refine_sample_size_broadening": _stage("refine_sample_size_broadening"),
    "refine_sample_strain_broadening": _stage("refine_sample_strain_broadening"),
    "refine_axial_asymmetry": _stage("refine_axial_asymmetry"),
    "refine_biso": _stage("refine_biso"),
    "refine_preferred_orientation": _stage("refine_preferred_orientation"),
    "refine_scale": _stage("refine_scale"),

    # -- a search, not a stage
    "reindex_or_recheck_cell": Recipe(
        kind="reindex_or_recheck_cell", how="index",
        note="indexing is a search over cells, not a stage over parameters: "
             "pick the peaks, then run the engines and read the consensus. It is "
             "the one action here that takes minutes rather than seconds, so it "
             "runs through the same run-state machine a fit does."),

    # -- no verb; the note is the answer
    "add_impurity_phase": Recipe(
        kind="add_impurity_phase", how="advice",
        note="no phase is named yet, so there is nothing to free. Identify what "
             "the unindexed peaks belong to (their strongest is in "
             "two_theta_range), then add it to the structure — that is an "
             "edit_model move, and the search for a candidate is not something "
             "this report can do for you."),
    "collect_better_data": Recipe(
        kind="collect_better_data", how="advice",
        note="no parameter can be freed for this one: the fit is saying the "
             "pattern itself is the limit — count longer, use a narrower "
             "receiving slit, or re-mount the specimen."),
    "increase_background_flexibility": Recipe(
        kind="increase_background_flexibility", how="advice",
        note="this changes what the background can absorb, not which parameters "
             "move: a Chebyshev term or a P-spline lambda_smooth is a property "
             "of the model, not a member of turn_on, so add one yourself and "
             "re-run. A more flexible background lowers Rwp while biasing ADPs "
             "up and scales (hence QPA fractions) down, so read "
             "report.background.worst_absorption afterwards (and the "
             "BACKGROUND_ABSORPTION diagnostic, which fires on the same number) "
             "before believing the improvement."),
    "decrease_background_flexibility": Recipe(
        kind="decrease_background_flexibility", how="advice",
        note="the safe direction of the same model edit, and still an edit rather "
             "than a stage: fewer Chebyshev terms, a larger P-spline "
             "lambda_smooth, coarser knots, or hold an estimated curve "
             "additively. Expect Rwp to get worse — that is what stiffening a "
             "background costs, and an unbiased ADP is what it buys; "
             "report.background.worst_absorption is where you see it bought."),
}


def recipe(kind: str) -> Recipe:
    """The recipe for ``kind``, or ``KeyError`` naming the vocabulary."""
    try:
        return RECIPES[kind]  # type: ignore[index]
    except KeyError:
        raise KeyError(f"unknown action kind {kind!r}; the vocabulary is "
                       f"{sorted(RECIPES)}") from None


def stage_for(action: SuggestedAction, *, prefix: str = "apply",
              max_iter: int = 100) -> StageSpec:
    """The one stage that carries ``action`` out.

    The name carries the kind (``apply:refine_cell``) so the history log reads as
    what happened rather than as an anonymous stage, and ``turn_on`` is the
    action's own globs verbatim.  No seeds: a suggestion never proposes a
    floored width or a Stephens block — those arrive through a plan, whose
    stages carry the seeds the pathologies need.
    """
    if recipe(action.kind).how != "stage":
        raise ValueError(f"{action.kind} is not carried out by a stage "
                         f"(how={recipe(action.kind).how})")
    return StageSpec(name=f"{prefix}:{action.kind}",
                     turn_on=list(action.parameter_paths), max_iter=max_iter)


def api_call(stage: StageSpec, *, plan=None) -> str:
    """The public-API line ``stage`` corresponds to.

    Rendered by :meth:`NodeAction.api_call`, which is what the history panel
    already prints for a stage node — so the line an Apply button shows as its
    tooltip and the line that node prints afterwards come from one function rather
    than from two spellings that can drift.  ``plan`` is the plan whose two
    settings the stage will run at (a project's stored one, which
    ``Project.run_stage`` passes on), since the node records them and its line
    then names any that differ from the default (WP-2002, B1).
    """
    from ..schemas.history import NodeAction
    from ..schemas.plan import CLOSING_WINDOW_TOL

    settings = ({} if plan is None else
                {"correlation_guard": plan.correlation_guard,
                 "phase_support_sigma": plan.phase_support_sigma})
    # the fraction run_stage records when given none (WP-2002, the seventh
    # round's Q1), so the tooltip and the node's line agree
    return NodeAction(kind="stage", name=stage.name, turn_on=list(stage.turn_on),
                      max_iter=stage.max_iter, window_area_tol=CLOSING_WINDOW_TOL,
                      **settings).api_call()


def unreachable(action: SuggestedAction, held: Mapping[str, str]) -> dict[str, str]:
    """The action's globs this model cannot act on, each with the reason.

    Reachability is a different question from applicability: a kind can be a
    stage in general and still have nothing to act on *here*, in two distinct
    ways that a panel must not merge.

    * **Absent** — no parameter matches the glob at all.
      ``refine_preferred_orientation`` is the designed case:
      ``phases.2.preferred_orientation.r`` does not exist until the phase
      declares the block, and Layer 2 emits the action anyway on purpose (its
      rationale says which axis to declare).
    * **Held** — the paths exist and every match is held, so freeing them is a
      no-op with a history node attached.  Measured on a real report, this is not
      a corner: a Debye-Scherrer instrument locks ``sample_displacement`` and
      ``sample_transparency`` (``params/vector.py`` force-fixes both off
      Bragg-Brentano, where the aberrations have no meaning), while Layer 2's
      position-template map names them regardless of the geometry measured — so
      the *highest*-confidence suggestion on a capillary fit can be one no verb
      can carry out.  The reason quoted is ``ParameterRow.held_because``,
      verbatim, because it is already the right sentence.

    ``held`` maps every path in the table to why it is held, ``""`` when it is
    refinable — one mapping rather than two arguments, so "absent" and "held"
    cannot be answered from two views of the table.
    """
    out: dict[str, str] = {}
    for glob in action.parameter_paths:
        hits = [p for p in held if fnmatch.fnmatchcase(p, glob)]
        if not hits:
            out[glob] = ("no parameter in this model matches it — the block the "
                         "path names is not declared on the phase yet")
        elif all(held[p] for p in hits):
            out[glob] = f"every match is held ({held[hits[0]]})"
    return out


def refusal(action: SuggestedAction, *, held: Mapping[str, str],
            indexing: bool = False) -> str:
    """Why this action cannot be applied here, or ``""`` when it can.

    Order matters and is the report's own hierarchy: **the veto outranks
    everything** (the strategy engine holds it, and a vetoed action is shown
    greyed rather than hidden), then what kind of verb the kind needs, then
    whether this model has anything for that verb to touch.
    """
    if action.vetoed_by is not None:
        return f"vetoed: {action.vetoed_by}"
    rule = recipe(action.kind)
    if rule.how == "advice":
        return f"not a one-click action — {rule.note}"
    if rule.how == "index" and not indexing:
        return ("this build reports no indexing engine "
                "(capabilities().features['indexing'] is False); "
                f"{rule.note}")
    if not action.parameter_paths:
        # ``predict_then_verify``'s words for the same state, kept the same
        return "action carries no refinable parameter paths"
    blocked = unreachable(action, held)
    if blocked:
        return "; ".join(f"{glob}: {why}" for glob, why in blocked.items())
    return ""


def describe_action(action: SuggestedAction, *, held: Mapping[str, str],
                    indexing: bool = False, plan=None) -> dict:
    """One suggestion's applicability, as the arm a client renders from.

    Served beside the report (``GET /api/report``) rather than computed by the
    panel, so the enabled-ness of a button and the route's willingness to act
    cannot disagree — the same reason ``refinable``/``held_because`` travel on a
    parameter row instead of being re-derived per client.  ``plan`` is
    :func:`api_call`'s.
    """
    rule = recipe(action.kind)
    why = refusal(action, held=held, indexing=indexing)
    stage = (stage_for(action) if rule.how == "stage" and not why else None)
    return {
        "kind": action.kind,
        "how": rule.how,
        "note": rule.note,
        "can_apply": not why,
        "refusal": why,
        "paths": list(action.parameter_paths),
        "stage": None if stage is None else stage.model_dump(mode="json"),
        "api_call": None if stage is None else api_call(stage, plan=plan),
    }


def missing_kinds() -> list[str]:
    """``ActionKind`` members with no recipe — empty, and pinned so by test."""
    return sorted(set(get_args(ActionKind)) - set(RECIPES))
